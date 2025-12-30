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
    "TR": "Transporte",
    "AF": "Administración",
    "BE": "Bienes de Uso"
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

    numero_pedido = ""
    try:
        cursor = conn.cursor()
        numero_pedido = generar_numero_pedido()

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
            conn.close()
        except:
            pass
        return False, f"Error al crear pedido: {str(e)}", ""


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

    query += " ORDER BY p.fecha_creacion DESC LIMIT 100"
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


def actualizar_estado_pedido(numero_pedido: str, nuevo_estado: str) -> Tuple[bool, str]:
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
# NOTIFICACIONES
# =====================================================================

def contar_notificaciones_no_leidas(usuario: str) -> int:
    df = ejecutar_consulta("""
        SELECT COUNT(*) FROM notificaciones
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
# 🔎 SUGERENCIAS DE ARTÍCULOS (NUEVO – NO ROMPE NADA)
# =====================================================================

def sugerir_articulos_similares(texto_articulo: str, seccion: str = "") -> List[str]:
    if not texto_articulo or len(texto_articulo.strip()) < 3:
        return []

    query = """
        SELECT DISTINCT "ARTICULO"
        FROM stock
        WHERE UPPER("ARTICULO") LIKE %s
    """
    params = [f"%{texto_articulo.upper()}%"]

    if seccion:
        query += ' AND UPPER(TRIM("FAMILIA")) = %s'
        params.append(seccion.upper())

    query += " ORDER BY 1 LIMIT 10"

    df = ejecutar_consulta(query, tuple(params))
    return df.iloc[:, 0].tolist() if df is not None and not df.empty else []

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
    # TAB 1 – TEXTO LIBRE + SUGERENCIAS
    # =============================================================
    with tab1:
        st.subheader("✍️ Escribir pedido")
        seccion = st.selectbox(
            "Sección (opcional):",
            [""] + [f"{k} - {v}" for k, v in SECCIONES.items()]
        )
        seccion_codigo = seccion.split(" - ")[0] if seccion else ""

        texto_pedido = st.text_area("Pedido:", height=150)

        if texto_pedido:
            lineas = parsear_texto_pedido(texto_pedido)
            df = pd.DataFrame(lineas)

            df_edit = st.data_editor(df, hide_index=True, num_rows="dynamic")

            st.markdown("### 🔎 Sugerencias")
            for _, fila in df_edit.iterrows():
                art = str(fila.get("articulo", "")).strip()
                sugerencias = sugerir_articulos_similares(art, seccion_codigo)
                if len(sugerencias) > 1:
                    st.warning(f"⚠️ **{art}** puede ser:")
                    for s in sugerencias:
                        st.markdown(f"- {s}")
                elif len(sugerencias) == 1:
                    st.info(f"🔹 {art} → {sugerencias[0]}")

            if st.button("📨 Enviar pedido", type="primary"):
                ok, msg, _ = crear_pedido(
                    usuario,
                    nombre_usuario,
                    seccion_codigo,
                    df_edit.to_dict("records"),
                    ""
                )
                st.success(msg) if ok else st.error(msg)
