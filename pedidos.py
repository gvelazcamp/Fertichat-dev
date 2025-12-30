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
            df = pd.DataFrame(parsear_texto_pedido(texto_pedido))
            df_edit = st.data_editor(df, hide_index=True, num_rows="dynamic")

            st.markdown("### 🔎 Sugerencias")

            lineas_finales = []
            bloquear_envio = False

            for idx, fila in df_edit.iterrows():
                art = str(fila.get("articulo", "")).strip()
                cant = fila.get("cantidad", 1)

                if not art:
                    continue

                texto_limpio = limpiar_texto_para_busqueda(art)
                sugerencias = sugerir_articulos_similares(texto_limpio, seccion_codigo)

                if len(sugerencias) > 1:
                    st.warning(f"⚠️ **{art}** puede ser:")

                    elegido = st.selectbox(
                        f"Seleccioná el artículo correcto para '{art}':",
                        ["— Elegir —"] + sugerencias,
                        key=f"sug_{idx}"
                    )

                    if elegido == "— Elegir —":
                        bloquear_envio = True
                        lineas_finales.append(fila.to_dict())
                    else:
                        lineas_finales.append({
                            "codigo": "",
                            "articulo": elegido,
                            "cantidad": cant
                        })

                elif len(sugerencias) == 1:
                    st.info(f"🔹 {art} → {sugerencias[0]}")
                    lineas_finales.append({
                        "codigo": "",
                        "articulo": sugerencias[0],
                        "cantidad": cant
                    })

                else:
                    lineas_finales.append(fila.to_dict())

            if bloquear_envio:
                st.caption("ℹ️ Seleccioná todas las opciones antes de enviar.")

            if st.button(
                "📨 Enviar pedido",
                type="primary",
                disabled=bloquear_envio
            ):
                ok, msg, _ = crear_pedido(
                    usuario,
                    nombre_usuario,
                    seccion_codigo,
                    lineas_finales,
                    ""
                )
                st.success(msg) if ok else st.error(msg)

