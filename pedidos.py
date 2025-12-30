# =====================================================================
# 📥 MÓDULO DE PEDIDOS INTERNOS - FERTI CHAT
# Archivo: pedidos.py  (IMPORTANTE: minúscula para Streamlit Cloud)
# =====================================================================

import streamlit as st
import pandas as pd
from typing import List, Tuple
import re
import io

# Importar conexión a DB
from sql_queries import ejecutar_consulta, get_db_connection

# =====================================================================
# CONFIGURACIÓN
# =====================================================================

USUARIO_NOTIFICACIONES = "gvelazquez"

SECCIONES = {
    "LP": "Limpieza",
    "FB": "Microbiología",
    "ID": "Inmunodiagnóstico",
    "XX": "Hormonas",
    "G": "Generales",
    "HT": "Hematología",
    "CT": "Citometría",
    "TR": "Tronco Comun",
    "AF": "Alejandra Fajardo",
    "BE": "Microbiologia"
}

# =====================================================================
# FUNCIONES DE BASE DE DATOS
# =====================================================================

def generar_numero_pedido() -> str:
    query = "SELECT MAX(numero_pedido) FROM pedidos"
    df = ejecutar_consulta(query)

    if df is None or df.empty or df.iloc[0, 0] is None:
        return "A00001"

    ultimo = str(df.iloc[0, 0])
    try:
        numero = int(ultimo[1:]) + 1
    except:
        numero = 1
    return f"A{numero:05d}"


def crear_pedido(usuario: str, nombre_usuario: str, seccion: str,
                 lineas: List[dict], observaciones: str = "") -> Tuple[bool, str, str]:

    conn = get_db_connection()
    if not conn:
        return False, "Error de conexión a DB", ""

    try:
        cursor = conn.cursor()
        numero_pedido = generar_numero_pedido()

        cursor.execute("""
            INSERT INTO pedidos (numero_pedido, usuario, nombre_usuario, seccion, observaciones)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (numero_pedido, usuario, nombre_usuario, seccion, observaciones))

        pedido_id = cursor.fetchone()[0]

        for linea in lineas:
            cursor.execute("""
                INSERT INTO pedidos_detalle (pedido_id, codigo, articulo, cantidad)
                VALUES (%s, %s, %s, %s)
            """, (
                pedido_id,
                linea.get("codigo", ""),
                linea.get("articulo", ""),
                linea.get("cantidad", 1)
            ))

        cursor.execute("""
            INSERT INTO notificaciones (pedido_id, usuario_destino, mensaje)
            VALUES (%s, %s, %s)
        """, (
            pedido_id,
            USUARIO_NOTIFICACIONES,
            f"Nuevo pedido {numero_pedido} de {nombre_usuario} ({seccion})"
        ))

        conn.commit()
        conn.close()
        return True, f"✅ Pedido {numero_pedido} creado correctamente", numero_pedido

    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except:
            pass
        return False, f"Error al crear pedido: {e}", ""
# =====================================================================
# NOTIFICACIONES
# =====================================================================

def contar_notificaciones_no_leidas(usuario: str) -> int:
    df = ejecutar_consulta("""
        SELECT COUNT(*)
        FROM notificaciones
        WHERE usuario_destino = %s AND leida = FALSE
    """, (usuario,))
    return int(df.iloc[0, 0]) if df is not None and not df.empty else 0


def obtener_notificaciones(usuario: str) -> pd.DataFrame:
    return ejecutar_consulta("""
        SELECT
            n.id,
            n.mensaje,
            n.leida,
            TO_CHAR(n.fecha, 'DD/MM HH24:MI') AS fecha,
            p.numero_pedido
        FROM notificaciones n
        LEFT JOIN pedidos p ON n.pedido_id = p.id
        WHERE n.usuario_destino = %s
        ORDER BY n.fecha DESC
        LIMIT 50
    """, (usuario,))


def marcar_notificacion_leida(notif_id: int) -> bool:
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE notificaciones SET leida = TRUE WHERE id = %s",
            (notif_id,)
        )
        conn.commit()
        conn.close()
        return True
    except:
        try:
            conn.close()
        except:
            pass
        return False


# =====================================================================
# NORMALIZACIÓN DE TEXTO PARA SUGERENCIAS
# =====================================================================

def limpiar_texto_para_busqueda(texto: str) -> str:
    if not texto:
        return ""

    texto = texto.upper()
    texto = re.sub(r'\d+', ' ', texto)
    texto = re.sub(r'[^A-Z\s]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()

    return texto


# =====================================================================
# PARSEO TEXTO LIBRE
# =====================================================================

def parsear_texto_pedido(texto: str) -> List[dict]:
    lineas = []
    items = re.split(r'[,;\n]+', texto)

    for item in items:
        item = item.strip()
        if not item:
            continue

        cantidad = 1
        articulo = item

        match = re.search(r'^(.+?)\s*[x\-]\s*(\d+(?:[.,]\d+)?)$', item, re.I)
        if match:
            articulo = match.group(1).strip()
            cantidad = float(match.group(2).replace(',', '.'))

        lineas.append({
            "codigo": "",
            "articulo": articulo.title(),
            "cantidad": cantidad
        })

    return lineas


# =====================================================================
# 🔎 SUGERENCIAS DE ARTÍCULOS (SECCIÓN + TR)
# =====================================================================

def sugerir_articulos_similares(texto_articulo: str, seccion: str = "") -> List[str]:
    """
    Busca artículos similares en stock.
    - Usa ILIKE (case insensitive real)
    - Incluye siempre TR como familia transversal
    """
    if not texto_articulo or len(texto_articulo.strip()) < 3:
        return []

    palabras = [p for p in texto_articulo.split() if len(p) >= 3]

    if not palabras:
        return []

    condiciones = []
    params = []

    for p in palabras:
        condiciones.append('"ARTICULO" ILIKE %s')
        params.append(f"%{p}%")

    where_articulo = " AND ".join(condiciones)

    query = f"""
        SELECT DISTINCT "ARTICULO"
        FROM stock
        WHERE {where_articulo}
    """

    if seccion:
        query += ' AND UPPER(TRIM("FAMILIA")) IN (%s, %s)'
        params.extend([seccion.upper(), 'TR'])

    query += " ORDER BY 1 LIMIT 10"

    df = ejecutar_consulta(query, tuple(params))

    if df is None or df.empty:
        return []

    return df.iloc[:, 0].astype(str).tolist()



# =====================================================================
# INTERFAZ
# =====================================================================

def mostrar_pedidos_internos():

    st.title("📥 Pedidos Internos")

    user = st.session_state.get('user', {})
    usuario = user.get('usuario', user.get('email', 'anonimo'))
    nombre_usuario = user.get('nombre', usuario)

    tab1, tab2, tab3, tab4 = st.tabs([
        "✍️ Escribir pedido",
        "✅ Seleccionar productos",
        "📤 Subir Excel",
        "📋 Mis pedidos"
    ])

    # =============================================================
    # TAB 1 – TEXTO LIBRE + SUGERENCIAS (REEMPLAZO EN LA TABLA)
    # =============================================================
    with tab1:
        st.subheader("✍️ Escribir pedido")

        seccion = st.selectbox(
            "Sección (opcional):",
            [""] + [f"{k} - {v}" for k, v in SECCIONES.items()],
            key="pedido_tab1_seccion"
        )
        seccion_codigo = seccion.split(" - ")[0] if seccion else ""

        texto_pedido = st.text_area("Pedido:", height=150, key="pedido_tab1_texto")

        # Si cambia el texto, regenero el DF base
        if texto_pedido and st.session_state.get("pedido_tab1_texto_last") != texto_pedido:
            st.session_state["pedido_tab1_texto_last"] = texto_pedido
            st.session_state["df_pedido"] = pd.DataFrame(parsear_texto_pedido(texto_pedido))

        if "df_pedido" not in st.session_state:
            st.session_state["df_pedido"] = pd.DataFrame(columns=["codigo", "articulo", "cantidad"])

        df_edit = st.data_editor(
            st.session_state["df_pedido"],
            hide_index=True,
            num_rows="dynamic",
            key="editor_pedido_tab1"
        )

        # Guardar lo editado siempre
        st.session_state["df_pedido"] = df_edit.copy()

        st.markdown("### 🔎 Sugerencias")

        bloquear_envio = False
        necesita_rerun = False

        for idx, fila in df_edit.iterrows():
            art = str(fila.get("articulo", "")).strip()
            if not art:
                continue

            texto_limpio = limpiar_texto_para_busqueda(art)
            sugerencias = sugerir_articulos_similares(texto_limpio, seccion_codigo)

            if len(sugerencias) > 1:
                st.warning(f"⚠️ **{art}** puede ser:")

                elegido = st.selectbox(
                    f"Seleccioná el artículo correcto para '{art}':",
                    ["— Elegir —"] + sugerencias,
                    key=f"sug_tab1_{idx}"
                )

                if elegido != "— Elegir —":
                    if st.session_state["df_pedido"].at[idx, "articulo"] != elegido:
                        st.session_state["df_pedido"].at[idx, "articulo"] = elegido
                        necesita_rerun = True
                else:
                    bloquear_envio = True

            elif len(sugerencias) == 1:
                sug = sugerencias[0]
                st.info(f"🔹 {art} → {sug}")
                if st.session_state["df_pedido"].at[idx, "articulo"] != sug:
                    st.session_state["df_pedido"].at[idx, "articulo"] = sug
                    necesita_rerun = True

        if necesita_rerun:
            try:
                st.rerun()
            except Exception:
                st.experimental_rerun()

        if st.button("📨 Enviar pedido", type="primary", disabled=bloquear_envio, key="btn_enviar_tab1"):
            lineas = st.session_state["df_pedido"].to_dict("records")
            ok, msg, _ = crear_pedido(
                usuario,
                nombre_usuario,
                seccion_codigo,
                lineas,
                ""
            )
            st.success(msg) if ok else st.error(msg)

    # =============================================================
    # TAB 2 – SELECCIONAR PRODUCTOS (LISTA + CANTIDADES)
    # =============================================================
    with tab2:
        st.subheader("✅ Seleccionar productos")

        seccion2 = st.selectbox(
            "Sección (opcional):",
            [""] + [f"{k} - {v}" for k, v in SECCIONES.items()],
            key="pedido_tab2_seccion"
        )
        seccion2_codigo = seccion2.split(" - ")[0] if seccion2 else ""

        incluir_tr = st.checkbox("Incluir TR (Tronco Comun)", value=True, key="pedido_tab2_incluir_tr")
        buscar = st.text_input("Buscar artículo (opcional):", key="pedido_tab2_buscar")

        # Armar familias a incluir (si no elige sección: por defecto TR solo, para no traer infinito)
        familias = []
        if seccion2_codigo:
            familias.append(seccion2_codigo.upper())
            if incluir_tr and seccion2_codigo.upper() != "TR":
                familias.append("TR")
        else:
            # sin sección → solo TR (y listo)
            familias.append("TR")

        params = []
        where_parts = []

        # filtro por familias (IN)
        if familias:
            placeholders = ", ".join(["%s"] * len(familias))
            where_parts.append(f'UPPER(TRIM("FAMILIA")) IN ({placeholders})')
            params.extend(familias)

        # filtro por búsqueda
        if buscar and len(buscar.strip()) >= 2:
            where_parts.append('UPPER("ARTICULO") ILIKE %s')
            params.append(f"%{buscar.strip().upper()}%")

        where_sql = " AND ".join(where_parts) if where_parts else "1=1"

        q = f"""
            SELECT DISTINCT "ARTICULO"
            FROM stock
            WHERE {where_sql}
            ORDER BY 1
            LIMIT 400
        """
        df_art = ejecutar_consulta(q, tuple(params) if params else None)
        articulos = df_art.iloc[:, 0].astype(str).tolist() if df_art is not None and not df_art.empty else []

        if not articulos:
            st.info("No se encontraron artículos con esos filtros.")
        else:
            seleccionados = st.multiselect(
                "Seleccioná artículos:",
                articulos,
                key="pedido_tab2_multiselect"
            )

            if "tab2_cantidades" not in st.session_state:
                st.session_state["tab2_cantidades"] = {}

            lineas_tab2 = []
            for a in seleccionados:
                key_c = f"cant_{a}"
                if key_c not in st.session_state["tab2_cantidades"]:
                    st.session_state["tab2_cantidades"][key_c] = 1

                cant = st.number_input(
                    f"Cantidad para: {a}",
                    min_value=1,
                    step=1,
                    value=int(st.session_state["tab2_cantidades"][key_c]),
                    key=f"pedido_tab2_{key_c}"
                )
                st.session_state["tab2_cantidades"][key_c] = int(cant)

                lineas_tab2.append({
                    "codigo": "",
                    "articulo": a,
                    "cantidad": int(cant)
                })

            if lineas_tab2:
                st.markdown("### 🧾 Resumen")
                st.dataframe(pd.DataFrame(lineas_tab2), hide_index=True)

                if st.button("📨 Enviar pedido (selección)", type="primary", key="btn_enviar_tab2"):
                    ok, msg, _ = crear_pedido(
                        usuario,
                        nombre_usuario,
                        seccion2_codigo,
                        lineas_tab2,
                        ""
                    )
                    st.success(msg) if ok else st.error(msg)

    # =============================================================
    # TAB 3 – SUBIR EXCEL/CSV (MAPEO SIMPLE + ENVÍO)
    # =============================================================
    with tab3:
        st.subheader("📤 Subir Excel / CSV")

        seccion3 = st.selectbox(
            "Sección (opcional):",
            [""] + [f"{k} - {v}" for k, v in SECCIONES.items()],
            key="pedido_tab3_seccion"
        )
        seccion3_codigo = seccion3.split(" - ")[0] if seccion3 else ""

        archivo = st.file_uploader("Subí un archivo .xlsx, .xls o .csv", type=["xlsx", "xls", "csv"], key="pedido_tab3_file")

        if archivo is not None:
            try:
                if archivo.name.lower().endswith(".csv"):
                    df_up = pd.read_csv(archivo)
                else:
                    df_up = pd.read_excel(archivo)
            except Exception as e:
                st.error(f"No pude leer el archivo: {e}")
                df_up = None

            if df_up is not None and not df_up.empty:
                st.caption("Detecté estas columnas. Elegí cuál corresponde a Artículo / Cantidad (Código opcional).")

                cols = list(df_up.columns)

                def _guess_col(posibles):
                    for c in cols:
                        if str(c).strip().lower() in posibles:
                            return c
                    for c in cols:
                        lc = str(c).strip().lower()
                        for p in posibles:
                            if p in lc:
                                return c
                    return None

                col_art_guess = _guess_col(["articulo", "artículo", "item", "producto", "descripcion", "descripción"])
                col_cant_guess = _guess_col(["cantidad", "cant", "qty", "cantidad solicitada"])
                col_cod_guess = _guess_col(["codigo", "código", "cod", "code"])

                col_art = st.selectbox("Columna de ARTÍCULO:", cols, index=cols.index(col_art_guess) if col_art_guess in cols else 0, key="map_art")
                col_cant = st.selectbox("Columna de CANTIDAD:", cols, index=cols.index(col_cant_guess) if col_cant_guess in cols else 0, key="map_cant")
                col_cod = st.selectbox("Columna de CÓDIGO (opcional):", ["(sin código)"] + cols,
                                       index=(cols.index(col_cod_guess) + 1) if col_cod_guess in cols else 0,
                                       key="map_cod")

                df_lineas = pd.DataFrame()
                df_lineas["codigo"] = "" if col_cod == "(sin código)" else df_up[col_cod].astype(str)
                df_lineas["articulo"] = df_up[col_art].astype(str)
                df_lineas["cantidad"] = pd.to_numeric(df_up[col_cant], errors="coerce").fillna(1).astype(int)

                st.markdown("### 🧾 Vista previa (editable)")
                df_edit3 = st.data_editor(df_lineas, hide_index=True, num_rows="dynamic", key="editor_tab3")

                if st.button("📨 Enviar pedido (archivo)", type="primary", key="btn_enviar_tab3"):
                    ok, msg, _ = crear_pedido(
                        usuario,
                        nombre_usuario,
                        seccion3_codigo,
                        df_edit3.to_dict("records"),
                        ""
                    )
                    st.success(msg) if ok else st.error(msg)

    # =============================================================
    # TAB 4 – MIS PEDIDOS (LISTA + DETALLE)
    # =============================================================
    with tab4:
        st.subheader("📋 Mis pedidos")

        estado = st.selectbox("Filtrar por estado (opcional):", ["", "Pendiente", "En proceso", "Entregado", "Cancelado"], key="pedido_tab4_estado")
        estado_f = estado if estado else None

        df_p = obtener_pedidos(usuario=usuario, estado=estado_f)

        if df_p is None or df_p.empty:
            st.info("No tenés pedidos para mostrar.")
        else:
            st.dataframe(df_p.drop(columns=["id"], errors="ignore"), hide_index=True)

            # selector por ID interno
            ids = df_p["id"].tolist() if "id" in df_p.columns else []
            if ids:
                pid = st.selectbox("Ver detalle del pedido:", ids, key="pedido_tab4_pid")
                df_det = obtener_detalle_pedido(int(pid))
                if df_det is None or df_det.empty:
                    st.info("No hay detalle para ese pedido.")
                else:
                    st.markdown("### 🧾 Detalle")
                    st.dataframe(df_det, hide_index=True)
