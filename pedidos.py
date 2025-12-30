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
# CONSULTAS PEDIDOS (PARA TAB "MIS PEDIDOS")
# =====================================================================

def obtener_pedidos(usuario: str = None, estado: str = None) -> pd.DataFrame:
    query = """
        SELECT
            p.numero_pedido AS "Nro Pedido",
            p.nombre_usuario AS "Usuario",
            p.seccion AS "Sección",
            p.estado AS "Estado",
            TO_CHAR(p.fecha_creacion, 'DD/MM/YYYY HH24:MI') AS "Fecha",
            p.observaciones AS "Observaciones",
            p.id
        FROM pedidos p
        WHERE 1=1
    """
    params = []

    if usuario:
        query += " AND p.usuario = %s"
        params.append(usuario)

    if estado:
        query += " AND p.estado = %s"
        params.append(estado)

    query += " ORDER BY p.fecha_creacion DESC LIMIT 200"

    return ejecutar_consulta(query, tuple(params) if params else None)


def obtener_detalle_pedido(pedido_id: int) -> pd.DataFrame:
    query = """
        SELECT
            codigo AS "Código",
            articulo AS "Artículo",
            cantidad AS "Cantidad"
        FROM pedidos_detalle
        WHERE pedido_id = %s
        ORDER BY id
    """
    return ejecutar_consulta(query, (pedido_id,))


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
    # TAB 1 – TEXTO LIBRE + SUGERENCIAS (REEMPLAZA EN LA TABLA)
    # =============================================================
    with tab1:
        st.subheader("✍️ Escribir pedido")

        seccion = st.selectbox(
            "Sección (opcional):",
            [""] + [f"{k} - {v}" for k, v in SECCIONES.items()],
            key="tab1_seccion"
        )
        seccion_codigo = seccion.split(" - ")[0] if seccion else ""

        texto_pedido = st.text_area("Pedido:", height=150, key="tab1_texto")

        # Si cambia el texto, regenerar la tabla base
        texto_prev = st.session_state.get("tab1_texto_prev", "")
        if texto_pedido != texto_prev:
            st.session_state["tab1_texto_prev"] = texto_pedido
            if texto_pedido and texto_pedido.strip():
                st.session_state["df_pedido"] = pd.DataFrame(parsear_texto_pedido(texto_pedido))
            else:
                st.session_state["df_pedido"] = pd.DataFrame(columns=["codigo", "articulo", "cantidad"])
            st.session_state["tab1_editor_ver"] = int(st.session_state.get("tab1_editor_ver", 0)) + 1

        if "df_pedido" not in st.session_state:
            st.session_state["df_pedido"] = pd.DataFrame(columns=["codigo", "articulo", "cantidad"])

        editor_key = f"tab1_editor_{int(st.session_state.get('tab1_editor_ver', 0))}"

        df_edit = st.data_editor(
            st.session_state["df_pedido"],
            hide_index=True,
            num_rows="dynamic",
            key=editor_key
        )

        st.session_state["df_pedido"] = df_edit.copy()

        st.markdown("### 🔎 Sugerencias")

        bloquear_envio = False
        necesita_refresh = False

        for idx, fila in df_edit.iterrows():
            art = str(fila.get("articulo", "")).strip()
            if not art:
                continue

            texto_limpio = limpiar_texto_para_busqueda(art)
            sugerencias = sugerir_articulos_similares(texto_limpio, seccion_codigo)

            # Varias coincidencias → obligar selección
            if len(sugerencias) > 1:
                st.warning(f"⚠️ **{art}** puede ser:")

                elegido = st.selectbox(
                    f"Seleccioná el artículo correcto para '{art}':",
                    ["— Elegir —"] + sugerencias,
                    key=f"tab1_sug_{idx}_{editor_key}"
                )

                if elegido != "— Elegir —":
                    if st.session_state["df_pedido"].at[idx, "articulo"] != elegido:
                        st.session_state["df_pedido"].at[idx, "articulo"] = elegido
                        necesita_refresh = True
                else:
                    bloquear_envio = True

            # Una sola coincidencia → autocompletar
            elif len(sugerencias) == 1:
                sug = sugerencias[0]
                st.info(f"🔹 {art} → {sug}")
                if st.session_state["df_pedido"].at[idx, "articulo"] != sug:
                    st.session_state["df_pedido"].at[idx, "articulo"] = sug
                    necesita_refresh = True

        # Refrescar editor para que “arriba” se vea el artículo reemplazado
        if necesita_refresh:
            st.session_state["tab1_editor_ver"] = int(st.session_state.get("tab1_editor_ver", 0)) + 1
            st.rerun()

        # Preparar líneas a enviar (sin vacíos)
        lineas_enviar = []
        for _, r in st.session_state["df_pedido"].iterrows():
            a = str(r.get("articulo", "")).strip()
            if not a:
                continue
            c = r.get("cantidad", 1)
            try:
                c = int(float(c))
            except:
                c = 1
            if c < 1:
                c = 1

            lineas_enviar.append({
                "codigo": str(r.get("codigo", "") or ""),
                "articulo": a,
                "cantidad": c
            })

        if st.button("📨 Enviar pedido", type="primary", disabled=bloquear_envio, key="tab1_btn_enviar"):
            ok, msg, _ = crear_pedido(
                usuario,
                nombre_usuario,
                seccion_codigo,
                lineas_enviar,
                ""
            )
            if ok:
                st.success(msg)
                # Limpiar
                st.session_state["tab1_texto_prev"] = ""
                st.session_state["tab1_texto"] = ""
                st.session_state["df_pedido"] = pd.DataFrame(columns=["codigo", "articulo", "cantidad"])
                st.session_state["tab1_editor_ver"] = int(st.session_state.get("tab1_editor_ver", 0)) + 1
                st.rerun()
            else:
                st.error(msg)

    # =============================================================
    # TAB 2 – SELECCIONAR PRODUCTOS (TABLA + CHECK + CANTIDAD + TR)
    # =============================================================
    with tab2:
        st.subheader("✅ Seleccionar productos")

        seccion2 = st.selectbox(
            "Sección:",
            [""] + [f"{k} - {v}" for k, v in SECCIONES.items()],
            key="tab2_seccion"
        )
        seccion2_codigo = seccion2.split(" - ")[0] if seccion2 else ""

        incluir_tr = st.checkbox("Incluir TR (Tronco Común)", value=True, key="tab2_incluir_tr")
        buscar = st.text_input("Buscar artículo (opcional):", key="tab2_buscar")

        if "tab2_sel" not in st.session_state:
            st.session_state["tab2_sel"] = {}  # articulo -> {"codigo":..., "articulo":..., "cantidad":...}

        if not seccion2_codigo:
            st.info("Elegí una sección para listar productos.")
        else:
            familias = [seccion2_codigo]
            if incluir_tr and "TR" not in familias:
                familias.append("TR")

            if len(familias) == 1:
                fam_clause = 'UPPER(TRIM("FAMILIA")) = %s'
                fam_params = [familias[0].upper()]
            else:
                fam_clause = 'UPPER(TRIM("FAMILIA")) IN (' + ",".join(["%s"] * len(familias)) + ')'
                fam_params = [f.upper() for f in familias]

            query = f'''
                SELECT
                    COALESCE(CAST("CODIGO" AS TEXT), '') AS "CODIGO",
                    COALESCE(CAST("ARTICULO" AS TEXT), '') AS "ARTICULO",
                    COALESCE(CAST("FAMILIA" AS TEXT), '') AS "FAMILIA"
                FROM stock
                WHERE {fam_clause}
            '''
            params = list(fam_params)

            if buscar and buscar.strip():
                query += ' AND "ARTICULO" ILIKE %s'
                params.append(f"%{buscar.strip()}%")

            query += ' ORDER BY "ARTICULO" LIMIT 500'

            df_stock = ejecutar_consulta(query, tuple(params))

            if df_stock is None or df_stock.empty:
                st.warning("No encontré artículos para esa sección/filtro.")
            else:
                sel_map = st.session_state["tab2_sel"]

                filas = []
                for _, r in df_stock.iterrows():
                    codigo = str(r.get("CODIGO", "") or "")
                    articulo = str(r.get("ARTICULO", "") or "")
                    familia = str(r.get("FAMILIA", "") or "")

                    if not articulo:
                        continue

                    if articulo in sel_map:
                        sel = True
                        try:
                            cant = int(float(sel_map[articulo].get("cantidad", 0)))
                        except:
                            cant = 0
                    else:
                        sel = False
                        cant = 0  # ✅ default en 0

                    filas.append({
                        "Sel": sel,
                        "Código": codigo,
                        "Artículo": articulo,
                        "Familia": familia,
                        "Cantidad": cant
                    })

                df_tab2 = pd.DataFrame(filas)

                df_tab2_edit = st.data_editor(
                    df_tab2,
                    hide_index=True,
                    num_rows="fixed",
                    column_config={
                        "Sel": st.column_config.CheckboxColumn("Sel"),
                        "Cantidad": st.column_config.NumberColumn("Cantidad", min_value=0, step=1),  # ✅ permite 0
                    },
                    disabled=["Código", "Artículo", "Familia"],
                    key="tab2_editor"
                )

                # Guardar selección
                nuevo = {}
                for _, rr in df_tab2_edit.iterrows():
                    if bool(rr.get("Sel", False)):
                        art = str(rr.get("Artículo", "")).strip()
                        if not art:
                            continue
                        cod = str(rr.get("Código", "") or "")
                        try:
                            cant = int(float(rr.get("Cantidad", 0)))
                        except:
                            cant = 0
                        if cant < 0:
                            cant = 0

                        nuevo[art] = {"codigo": cod, "articulo": art, "cantidad": cant}

                st.session_state["tab2_sel"] = nuevo
                sel_map = st.session_state["tab2_sel"]  # refrescar referencia

                colA, colB = st.columns([1, 1])

                with colA:
                    if st.button("🧹 Limpiar selección", key="tab2_btn_limpiar"):
                        st.session_state["tab2_sel"] = {}
                        st.rerun()

                with colB:
                    st.write(f"Seleccionados: **{len(sel_map)}**")

                # ============================
                # ➖ [cantidad] ➕ (carrito)
                # ============================
                hay_cero = False

                if sel_map:
                    st.markdown("#### 🧺 Cantidades (➖ 0 ➕)")

                    for i, art in enumerate(sorted(sel_map.keys())):
                        it = sel_map[art]
                        cod = str(it.get("codigo", "") or "")
                        nombre = str(it.get("articulo", art) or art)

                        try:
                            cant_actual = int(float(it.get("cantidad", 0) or 0))
                        except:
                            cant_actual = 0

                        c0, c1, c2, c3 = st.columns([6, 1, 2, 1])

                        with c0:
                            st.write(f"**{cod}** — {nombre}")

                        with c1:
                            if st.button("➖", key=f"tab2_minus_{i}"):
                                st.session_state["tab2_sel"][art]["cantidad"] = max(0, cant_actual - 1)
                                st.rerun()

                        with c2:
                            nuevo_cant = st.number_input(
                                "Cantidad",
                                min_value=0,
                                step=1,
                                value=cant_actual,
                                key=f"tab2_qty_{i}",
                                label_visibility="collapsed"
                            )
                            nuevo_cant = int(nuevo_cant)
                            if nuevo_cant != cant_actual:
                                st.session_state["tab2_sel"][art]["cantidad"] = nuevo_cant

                        with c3:
                            if st.button("➕", key=f"tab2_plus_{i}"):
                                st.session_state["tab2_sel"][art]["cantidad"] = cant_actual + 1
                                st.rerun()

                    # verificar si hay 0
                    for v in st.session_state["tab2_sel"].values():
                        try:
                            c = int(float(v.get("cantidad", 0) or 0))
                        except:
                            c = 0
                        if c == 0:
                            hay_cero = True
                            break

                    if hay_cero:
                        st.warning("⚠️ Tenés artículos seleccionados con cantidad 0. Ajustá la cantidad para poder enviar.")

                    st.markdown("#### ✅ Selección final")
                    st.dataframe(
                        pd.DataFrame(list(st.session_state["tab2_sel"].values()))[["codigo", "articulo", "cantidad"]],
                        use_container_width=True
                    )

                # Enviar (bloquea si hay 0)
                if st.button(
                    "📨 Enviar pedido",
                    type="primary",
                    key="tab2_btn_enviar",
                    disabled=(len(sel_map) == 0) or hay_cero
                ):
                    ok, msg, _ = crear_pedido(
                        usuario,
                        nombre_usuario,
                        seccion2_codigo,
                        list(st.session_state["tab2_sel"].values()),
                        ""
                    )
                    if ok:
                        st.success(msg)
                        st.session_state["tab2_sel"] = {}
                        st.rerun()
                    else:
                        st.error(msg)


    # =============================================================
    # TAB 3 – SUBIR EXCEL/CSV (codigo/articulo/cantidad)
    # =============================================================
    with tab3:
        st.subheader("📤 Subir Excel")

        seccion3 = st.selectbox(
            "Sección:",
            [""] + [f"{k} - {v}" for k, v in SECCIONES.items()],
            key="tab3_seccion"
        )
        seccion3_codigo = seccion3.split(" - ")[0] if seccion3 else ""

        archivo = st.file_uploader("Subí un Excel/CSV con columnas: codigo, articulo, cantidad", type=["xlsx", "xls", "csv"])

        if archivo is not None:
            try:
                nombre = (archivo.name or "").lower()

                if nombre.endswith(".csv"):
                    df_up = pd.read_csv(archivo)
                else:
                    df_up = pd.read_excel(archivo)

                # Normalizar nombres de columnas
                cols = {c.strip().lower(): c for c in df_up.columns}
                c_codigo = cols.get("codigo") or cols.get("código") or cols.get("cod")
                c_art = cols.get("articulo") or cols.get("artículo") or cols.get("art")
                c_cant = cols.get("cantidad") or cols.get("cant") or cols.get("qty")

                if not c_art:
                    st.error("No encontré la columna 'articulo'. Asegurate que exista.")
                else:
                    if not c_codigo:
                        df_up["codigo"] = ""
                        c_codigo = "codigo"
                    if not c_cant:
                        df_up["cantidad"] = 1
                        c_cant = "cantidad"

                    df_lineas = df_up[[c_codigo, c_art, c_cant]].copy()
                    df_lineas.columns = ["codigo", "articulo", "cantidad"]

                    df_lineas = df_lineas.fillna({"codigo": "", "articulo": "", "cantidad": 1})
                    df_lineas["articulo"] = df_lineas["articulo"].astype(str).str.strip()

                    st.markdown("#### Revisar antes de enviar")
                    df_edit3 = st.data_editor(df_lineas, hide_index=True, num_rows="dynamic", key="tab3_editor")

                    lineas3 = []
                    for _, r in df_edit3.iterrows():
                        art = str(r.get("articulo", "")).strip()
                        if not art:
                            continue
                        try:
                            cant = int(float(r.get("cantidad", 1)))
                        except:
                            cant = 1
                        if cant < 1:
                            cant = 1
                        lineas3.append({
                            "codigo": str(r.get("codigo", "") or ""),
                            "articulo": art,
                            "cantidad": cant
                        })

                    if st.button("📨 Enviar pedido", type="primary", key="tab3_btn_enviar", disabled=(len(lineas3) == 0 or not seccion3_codigo)):
                        if not seccion3_codigo:
                            st.error("Elegí una sección antes de enviar.")
                        else:
                            ok, msg, _ = crear_pedido(usuario, nombre_usuario, seccion3_codigo, lineas3, "")
                            st.success(msg) if ok else st.error(msg)

            except Exception as e:
                st.error(f"Error leyendo el archivo: {e}")

    # =============================================================
    # TAB 4 – MIS PEDIDOS (LISTA + DETALLE)
    # =============================================================
    with tab4:
        st.subheader("📋 Mis pedidos")

        solo_mios = st.checkbox("Solo mis pedidos", value=True, key="tab4_solo_mios")

        estado_op = st.selectbox(
            "Estado:",
            ["(Todos)", "Pendiente", "En proceso", "Entregado", "Cancelado"],
            key="tab4_estado"
        )
        estado_f = None if estado_op == "(Todos)" else estado_op

        df_p = obtener_pedidos(usuario=usuario if solo_mios else None, estado=estado_f)

        if df_p is None or df_p.empty:
            st.info("No hay pedidos para mostrar.")
        else:
            st.dataframe(df_p.drop(columns=["id"], errors="ignore"), use_container_width=True)

            # Ver detalle
            try:
                opciones = df_p[["Nro Pedido", "id"]].dropna()
                nro_sel = st.selectbox("Ver detalle del pedido:", opciones["Nro Pedido"].tolist(), key="tab4_detalle_sel")
                pedido_id = int(opciones.loc[opciones["Nro Pedido"] == nro_sel, "id"].iloc[0])

                df_det = obtener_detalle_pedido(pedido_id)
                if df_det is None or df_det.empty:
                    st.warning("No encontré detalle para ese pedido.")
                else:
                    st.markdown("#### Detalle")
                    st.dataframe(df_det, use_container_width=True)
            except Exception:
                pass


