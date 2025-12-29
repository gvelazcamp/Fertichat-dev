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

# Usuario que recibe TODAS las notificaciones de pedidos
USUARIO_NOTIFICACIONES = "gvelazquez"

# Secciones/Familias disponibles
SECCIONES = {
    "LP": "Limpieza",
    "FB": "Microbiología",
    "ID": "Inmunodiagnóstico",
    "XX": "Hormonas",
    "G": "Generales",
    "HT": "Hematología",
    "CT": "Citometría",
    "TR": "Transporte",
    "AF": "Administración",
    "BE": "Bienes de Uso"
}

# =====================================================================
# FUNCIONES DE BASE DE DATOS
# =====================================================================

def generar_numero_pedido() -> str:
    """Genera número de pedido secuencial: A00001, A00002..."""
    query = "SELECT MAX(numero_pedido) FROM pedidos"
    df = ejecutar_consulta(query)

    if df is None or df.empty or df.iloc[0, 0] is None:
        return "A00001"

    ultimo = str(df.iloc[0, 0])  # Ej: "A00015"
    try:
        numero = int(ultimo[1:]) + 1
    except:
        numero = 1
    return f"A{numero:05d}"


def crear_pedido(usuario: str, nombre_usuario: str, seccion: str,
                 lineas: List[dict], observaciones: str = "") -> Tuple[bool, str, str]:
    """
    Crea un pedido nuevo con sus líneas.
    lineas = [{"codigo": "123", "articulo": "Guantes", "cantidad": 5}, ...]
    Returns: (éxito, mensaje, numero_pedido)
    """
    conn = get_db_connection()
    if not conn:
        return False, "Error de conexión a DB", ""

    numero_pedido = ""
    try:
        cursor = conn.cursor()
        numero_pedido = generar_numero_pedido()

        # Insertar pedido principal
        cursor.execute("""
            INSERT INTO pedidos (numero_pedido, usuario, nombre_usuario, seccion, observaciones)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (numero_pedido, usuario, nombre_usuario, seccion, observaciones))

        pedido_id_row = cursor.fetchone()
        pedido_id = pedido_id_row[0] if pedido_id_row else None

        if not pedido_id:
            conn.rollback()
            conn.close()
            return False, "No se pudo obtener el ID del pedido.", ""

        # Insertar líneas de detalle
        for linea in lineas:
            cursor.execute("""
                INSERT INTO pedidos_detalle (pedido_id, codigo, articulo, cantidad)
                VALUES (%s, %s, %s, %s)
            """, (
                pedido_id,
                linea.get("codigo", "") or "",
                linea.get("articulo", ""),
                linea.get("cantidad", 1)
            ))

        # Crear notificación para el usuario destino
        mensaje = f"Nuevo pedido {numero_pedido} de {nombre_usuario} ({seccion})"
        cursor.execute("""
            INSERT INTO notificaciones (pedido_id, usuario_destino, mensaje)
            VALUES (%s, %s, %s)
        """, (pedido_id, USUARIO_NOTIFICACIONES, mensaje))

        conn.commit()
        conn.close()

        return True, f"✅ Pedido {numero_pedido} creado correctamente", numero_pedido

    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        try:
            conn.close()
        except:
            pass
        return False, f"Error al crear pedido: {str(e)}", ""


def obtener_pedidos(usuario: str = None, estado: str = None) -> pd.DataFrame:
    """Obtiene pedidos filtrados"""
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

    query += " ORDER BY p.fecha_creacion DESC LIMIT 100"

    return ejecutar_consulta(query, tuple(params) if params else None)


def obtener_detalle_pedido(pedido_id: int) -> pd.DataFrame:
    """Obtiene las líneas de un pedido"""
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


def actualizar_estado_pedido(numero_pedido: str, nuevo_estado: str) -> Tuple[bool, str]:
    """Actualiza el estado de un pedido"""
    conn = get_db_connection()
    if not conn:
        return False, "Error de conexión"

    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pedidos
            SET estado = %s, fecha_actualizacion = NOW()
            WHERE numero_pedido = %s
        """, (nuevo_estado, numero_pedido))
        conn.commit()
        conn.close()
        return True, f"Estado actualizado a: {nuevo_estado}"
    except Exception as e:
        try:
            conn.close()
        except:
            pass
        return False, str(e)


# =====================================================================
# NOTIFICACIONES (CAMPANITA)
# =====================================================================

def contar_notificaciones_no_leidas(usuario: str) -> int:
    """Cuenta notificaciones no leídas para un usuario"""
    query = """
        SELECT COUNT(*)
        FROM notificaciones
        WHERE usuario_destino = %s AND leida = FALSE
    """
    df = ejecutar_consulta(query, (usuario,))
    if df is not None and not df.empty:
        return int(df.iloc[0, 0])
    return 0


def obtener_notificaciones(usuario: str, solo_no_leidas: bool = False) -> pd.DataFrame:
    """Obtiene notificaciones de un usuario"""
    query = """
        SELECT
            n.id,
            n.mensaje,
            n.leida,
            TO_CHAR(n.fecha, 'DD/MM HH24:MI') AS fecha,
            p.numero_pedido
        FROM notificaciones n
        LEFT JOIN pedidos p ON n.pedido_id = p.id
        WHERE n.usuario_destino = %s
    """
    if solo_no_leidas:
        query += " AND n.leida = FALSE"

    query += " ORDER BY n.fecha DESC LIMIT 50"

    return ejecutar_consulta(query, (usuario,))


def marcar_notificacion_leida(notif_id: int) -> bool:
    """Marca una notificación como leída"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE notificaciones SET leida = TRUE WHERE id = %s", (notif_id,))
        conn.commit()
        conn.close()
        return True
    except:
        try:
            conn.close()
        except:
            pass
        return False


def marcar_todas_leidas(usuario: str) -> bool:
    """Marca todas las notificaciones como leídas"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE notificaciones
            SET leida = TRUE
            WHERE usuario_destino = %s AND leida = FALSE
        """, (usuario,))
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
# PARSEO DE TEXTO LIBRE
# =====================================================================

def parsear_texto_pedido(texto: str) -> List[dict]:
    """
    Convierte texto libre en líneas de pedido.
    Ej: "papel higienico x 2, guantes M x 5" → [{"articulo": "papel higienico", "cantidad": 2}, ...]
    """
    lineas = []

    items = re.split(r'[,;\n]+', texto)

    for item in items:
        item = item.strip()
        if not item:
            continue

        cantidad = 1
        articulo = item

        match = re.search(r'^(.+?)\s*[x\-]\s*(\d+(?:[.,]\d+)?)\s*$', item, re.IGNORECASE)
        if match:
            articulo = match.group(1).strip()
            cantidad = float(match.group(2).replace(',', '.'))
        else:
            match = re.search(r'^(\d+(?:[.,]\d+)?)\s+(.+)$', item)
            if match:
                cantidad = float(match.group(1).replace(',', '.'))
                articulo = match.group(2).strip()
            else:
                match = re.search(r'^(.+?)\s+(\d+(?:[.,]\d+)?)\s*$', item)
                if match:
                    articulo = match.group(1).strip()
                    cantidad = float(match.group(2).replace(',', '.'))

        if articulo:
            lineas.append({
                "codigo": "",
                "articulo": articulo.title(),
                "cantidad": cantidad
            })

    return lineas


# =====================================================================
# OBTENER ARTÍCULOS DE STOCK POR SECCIÓN
# =====================================================================

def obtener_articulos_por_seccion(seccion: str) -> pd.DataFrame:
    """Obtiene artículos de stock filtrados por sección/familia"""
    query = """
        SELECT DISTINCT
            "CODIGO"   AS codigo,
            "ARTICULO" AS articulo,
            "FAMILIA"  AS familia
        FROM stock
        WHERE UPPER(TRIM("FAMILIA")) = %s
        ORDER BY "ARTICULO"
        LIMIT 500
    """
    return ejecutar_consulta(query, (seccion.upper(),))

def render_campanita(usuario: str):
    """
    Muestra la campanita de notificaciones en Streamlit
    """
    count = contar_notificaciones_no_leidas(usuario)

    col_icon, col_text = st.columns([1, 8])

    with col_icon:
        if st.button(f"🔔 {count}" if count > 0 else "🔔", key="btn_campanita"):
            st.session_state["ver_notificaciones"] = True

    with col_text:
        if count > 0:
            st.markdown(f"**Tenés {count} notificación(es) pendiente(s)**")


# =====================================================================
# INTERFAZ STREAMLIT
# =====================================================================

def mostrar_pedidos_internos():
    """Pantalla principal del módulo de Pedidos Internos"""

    st.title("📥 Pedidos Internos")

    # -----------------------------------------------------
    # Usuario actual
    # -----------------------------------------------------
    user = st.session_state.get('user', {})
    usuario = user.get('usuario', user.get('email', 'anonimo'))
    nombre_usuario = user.get('nombre', usuario)

    # -----------------------------------------------------
    # Detectar navegación forzada desde campanita global
    # -----------------------------------------------------
    ir_a_mis_pedidos = st.session_state.pop("ir_a_mis_pedidos", False)

    # -----------------------------------------------------
    # Campanita local (solo para usuario notificaciones)
    # -----------------------------------------------------
    if usuario == USUARIO_NOTIFICACIONES:
        col_titulo, col_notif = st.columns([4, 1])
        with col_notif:
            count = contar_notificaciones_no_leidas(usuario)
            if count > 0:
                if st.button(f"🔔 {count}", key="btn_notif_local"):
                    st.session_state['ver_notificaciones'] = True
                    st.rerun()

    # -----------------------------------------------------
    # Vista de notificaciones
    # -----------------------------------------------------
    if st.session_state.get('ver_notificaciones') and usuario == USUARIO_NOTIFICACIONES:
        st.markdown("---")
        st.subheader("🔔 Notificaciones")

        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("✓ Marcar todas leídas"):
                marcar_todas_leidas(usuario)
                st.rerun()

        df_notif = obtener_notificaciones(usuario)
        if df_notif is not None and not df_notif.empty:
            for _, row in df_notif.iterrows():
                icono = "📩" if not bool(row['leida']) else "📭"
                st.markdown(f"{icono} **{row['fecha']}** - {row['mensaje']}")
                if not bool(row['leida']):
                    if st.button("Marcar leída", key=f"leer_{row['id']}"):
                        marcar_notificacion_leida(int(row['id']))
                        st.rerun()
        else:
            st.info("No hay notificaciones")

        if st.button("← Volver"):
            st.session_state['ver_notificaciones'] = False
            st.rerun()
        return

    st.markdown("---")

    # =========================================================================
    # TABS
    # =========================================================================

    ir_a_mis_pedidos = st.session_state.pop("ir_a_mis_pedidos", False)

    if ir_a_mis_pedidos:
        tab1, tab2, tab3, tab4 = st.tabs([
            "📋 Mis pedidos"
        ])
        tab_mis_pedidos = tab1
    else:
        tab1, tab2, tab3, tab4 = st.tabs([
            "✍️ Escribir pedido",
            "✅ Seleccionar productos",
            "📤 Subir Excel",
            "📋 Mis pedidos"
        ])
        tab_mis_pedidos = tab4

    # =========================================================================
    # TAB 1: ESCRIBIR PEDIDO
    # =========================================================================
    with tab1:
        st.subheader("✍️ Escribir pedido en texto libre")
        st.caption("Ej: guantes M x 5, alcohol x 2")

        seccion = st.selectbox(
            "Sección (opcional):",
            [""] + [f"{k} - {v}" for k, v in SECCIONES.items()],
            key="seccion_texto"
        )
        seccion_codigo = seccion.split(" - ")[0] if seccion else ""

        texto_pedido = st.text_area(
            "Escribí tu pedido:",
            height=150,
            key="texto_pedido"
        )

        observaciones = st.text_input("Observaciones (opcional):", key="obs_texto")

        if texto_pedido:
            lineas = parsear_texto_pedido(texto_pedido)
            if lineas:
                df_preview = pd.DataFrame(lineas)

                df_editado = st.data_editor(
                    df_preview,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="dynamic",
                    key="editor_texto"
                )

                if st.button("📨 Enviar pedido", type="primary", key="enviar_texto"):
                    lineas_validas = [
                        l for l in df_editado.to_dict("records")
                        if str(l.get("articulo", "")).strip() and float(l.get("cantidad", 0)) > 0
                    ]

                    if lineas_validas:
                        ok, msg, _ = crear_pedido(
                            usuario,
                            nombre_usuario,
                            seccion_codigo,
                            lineas_validas,
                            observaciones
                        )
                        if ok:
                            st.success(msg)
                            st.balloons()
                        else:
                            st.error(msg)
                    else:
                        st.warning("No hay líneas válidas para enviar")

    # =========================================================================
    # TAB 2: SELECCIONAR PRODUCTOS
    # =========================================================================
    with tab2:
        st.subheader("✅ Seleccionar productos de la lista")

        seccion2 = st.selectbox(
            "Elegí la sección:",
            [f"{k} - {v}" for k, v in SECCIONES.items()],
            key="seccion_select"
        )
        seccion_codigo2 = seccion2.split(" - ")[0]

        df_articulos = obtener_articulos_por_seccion(seccion_codigo2)

        if df_articulos is not None and not df_articulos.empty:
            if "productos_seleccionados" not in st.session_state:
                st.session_state.productos_seleccionados = {}

            for idx, row in enumerate(df_articulos.head(50).iterrows()):
                _, row = row
                codigo = str(row.get("codigo", ""))
                articulo = str(row.get("articulo", ""))

                col1, col2, col3 = st.columns([0.5, 3, 1])

                key_chk = f"chk_{seccion_codigo2}_{idx}"
                key_qty = f"qty_{seccion_codigo2}_{idx}"

                with col1:
                    seleccionado = st.checkbox("", key=key_chk)

                with col2:
                    st.markdown(f"**{articulo}** `{codigo}`")

                with col3:
                    cantidad = st.number_input(
                        "Cant",
                        min_value=0,
                        value=0,
                        key=key_qty,
                        label_visibility="collapsed"
                    )

                if seleccionado and cantidad > 0:
                    st.session_state.productos_seleccionados[codigo] = {
                        "codigo": codigo,
                        "articulo": articulo,
                        "cantidad": cantidad
                    }
                else:
                    st.session_state.productos_seleccionados.pop(codigo, None)

            if st.session_state.productos_seleccionados:
                st.markdown("---")
                st.dataframe(
                    pd.DataFrame(st.session_state.productos_seleccionados.values()),
                    use_container_width=True,
                    hide_index=True
                )

                obs2 = st.text_input("Observaciones:", key="obs_select")

                if st.button("📨 Enviar pedido", type="primary", key="enviar_select"):
                    ok, msg, _ = crear_pedido(
                        usuario,
                        nombre_usuario,
                        seccion_codigo2,
                        list(st.session_state.productos_seleccionados.values()),
                        obs2
                    )
                    if ok:
                        st.success(msg)
                        st.session_state.productos_seleccionados = {}
                        st.balloons()
                    else:
                        st.error(msg)

    # =========================================================================
    # TAB 3 y TAB 4
    # (quedan iguales a como ya los tenías)
    # =========================================================================


    # =========================================================================
    # TAB 3: SUBIR EXCEL
    # =========================================================================
    with tab3:
        st.subheader("📤 Subir pedido desde Excel")

        st.markdown("**1️⃣ Descargá la plantilla:**")

        plantilla = pd.DataFrame({
            "codigo": ["", "", ""],
            "articulo": ["Ejemplo producto 1", "Ejemplo producto 2", "Ejemplo producto 3"],
            "cantidad": [1, 2, 3]
        })

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            plantilla.to_excel(writer, index=False, sheet_name='Pedido')

        st.download_button(
            label="📥 Descargar plantilla Excel",
            data=buffer.getvalue(),
            file_name="plantilla_pedido.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.markdown("---")
        st.markdown("**2️⃣ Subí tu archivo:**")

        seccion3 = st.selectbox(
            "Sección:",
            [f"{k} - {v}" for k, v in SECCIONES.items()],
            key="seccion_excel"
        )
        seccion_codigo3 = seccion3.split(" - ")[0]

        archivo = st.file_uploader(
            "Seleccioná el archivo Excel:",
            type=['xlsx', 'xls'],
            key="upload_excel"
        )

        if archivo:
            try:
                df_excel = pd.read_excel(archivo)

                columnas_req = ['articulo', 'cantidad']
                columnas_excel = [str(c).lower().strip() for c in df_excel.columns]

                if not all(c in columnas_excel for c in columnas_req):
                    st.error("El archivo debe tener columnas: articulo, cantidad")
                else:
                    df_excel.columns = [str(c).lower().strip() for c in df_excel.columns]

                    df_excel = df_excel.dropna(subset=['articulo'])
                    df_excel['cantidad'] = pd.to_numeric(df_excel['cantidad'], errors='coerce').fillna(1)

                    if 'codigo' not in df_excel.columns:
                        df_excel['codigo'] = ""

                    st.markdown("**3️⃣ Previsualización:**")
                    st.dataframe(df_excel, use_container_width=True, hide_index=True)

                    st.success(f"✅ {len(df_excel)} líneas encontradas")

                    obs3 = st.text_input("Observaciones:", key="obs_excel")

                    if st.button("📨 Enviar pedido", type="primary", key="enviar_excel"):
                        lineas = df_excel.to_dict('records')
                        ok, msg, nro = crear_pedido(
                            usuario, nombre_usuario, seccion_codigo3,
                            lineas, obs3
                        )
                        if ok:
                            st.success(msg)
                            st.balloons()
                        else:
                            st.error(msg)

            except Exception as e:
                st.error(f"Error al leer archivo: {str(e)}")

    # =========================================================================
    # TAB 4: MIS PEDIDOS
    # =========================================================================
    with tab4:
        st.subheader("📋 Mis pedidos")

        if usuario == USUARIO_NOTIFICACIONES:
            ver_todos = st.checkbox("Ver todos los pedidos", value=True)
            filtro_usuario = None if ver_todos else usuario
        else:
            filtro_usuario = usuario

        filtro_estado = st.selectbox(
            "Filtrar por estado:",
            ["Todos", "Pendiente", "En proceso", "Completado", "Cancelado"],
            key="filtro_estado"
        )

        df_pedidos = obtener_pedidos(
            usuario=filtro_usuario,
            estado=filtro_estado if filtro_estado != "Todos" else None
        )

        if df_pedidos is not None and not df_pedidos.empty:
            for _, row in df_pedidos.iterrows():
                estado_icon = {
                    "Pendiente": "🟡",
                    "En proceso": "🔵",
                    "Completado": "🟢",
                    "Cancelado": "🔴"
                }.get(row['Estado'], "⚪")

                with st.expander(f"{estado_icon} **{row['Nro Pedido']}** - {row['Usuario']} - {row['Fecha']}"):
                    st.markdown(f"**Sección:** {row['Sección']}")
                    st.markdown(f"**Estado:** {row['Estado']}")
                    if row['Observaciones']:
                        st.markdown(f"**Obs:** {row['Observaciones']}")

                    df_det = obtener_detalle_pedido(int(row['id']))
                    if df_det is not None and not df_det.empty:
                        st.dataframe(df_det, use_container_width=True, hide_index=True)

                    if usuario == USUARIO_NOTIFICACIONES:
                        estados = ["Pendiente", "En proceso", "Completado", "Cancelado"]
                        idx = estados.index(row['Estado']) if row['Estado'] in estados else 0

                        nuevo_estado = st.selectbox(
                            "Cambiar estado:",
                            estados,
                            index=idx,
                            key=f"estado_{row['Nro Pedido']}"
                        )

                        if nuevo_estado != row['Estado']:
                            if st.button("Actualizar", key=f"act_{row['Nro Pedido']}"):
                                ok, msg = actualizar_estado_pedido(row['Nro Pedido'], nuevo_estado)
                                if ok:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
        else:
            st.info("No hay pedidos registrados")





