import streamlit as st

st.set_page_config(
    page_title="FertiChat",
    page_icon="🦋",
    layout="wide",
    initial_sidebar_state="auto"
)

from ui_css import CSS_GLOBAL
from login_page import require_auth

st.markdown(CSS_GLOBAL, unsafe_allow_html=True)

require_auth()

st.title("Inicio")


# =========================
# IMPORTS
# =========================
from config import MENU_OPTIONS, DEBUG_MODE
from auth import init_db
from login_page import require_auth, get_current_user, logout
from pedidos import mostrar_pedidos_internos, contar_notificaciones_no_leidas
from bajastock import mostrar_baja_stock
from ordenes_compra import mostrar_ordenes_compra
from ui_compras import Compras_IA
from ui_buscador import mostrar_buscador_ia
from ui_stock import mostrar_stock_ia, mostrar_resumen_stock_rotativo
from ui_dashboard import mostrar_dashboard, mostrar_indicadores_ia, mostrar_resumen_compras_rotativo
from ingreso_comprobantes import mostrar_ingreso_comprobantes
from ui_inicio import mostrar_inicio
from ficha_stock import mostrar_ficha_stock
from articulos import mostrar_articulos
from depositos import mostrar_depositos
from familias import mostrar_familias
from comprobantes import mostrar_menu_comprobantes
from ui_chat_chainlit import mostrar_chat_chainlit
from sql_core import get_lista_proveedores, get_valores_unicos, ejecutar_consulta
from ia_interpretador import normalizar_texto

from ui_css import CSS_GLOBAL

# =========================
# INICIALIZACIÓN
# =========================
init_db()
require_auth()

user = get_current_user() or {}

if "radio_menu" not in st.session_state:
    st.session_state["radio_menu"] = "🏠 Inicio"

# =========================
# CSS (CARGADO DESDE ui_css.py)
# =========================
st.markdown(f"<style>{CSS_GLOBAL}</style>", unsafe_allow_html=True)

# =========================
# OBTENER NOTIFICACIONES
# =========================
usuario_actual = user.get("usuario", user.get("email", ""))
cant_pendientes = 0
if usuario_actual:
    cant_pendientes = contar_notificaciones_no_leidas(usuario_actual)

# =========================
# DETECCIÓN DE NAVEGACIÓN DESDE TARJETAS
# =========================
try:
    go = st.query_params.get("go")
    if go:
        mapping = {
            "compras": "🛒 Compras IA",
            "buscador": "🔎 Buscador IA",
            "stock": "📦 Stock IA",
            "dashboard": "📊 Dashboard",
            "pedidos": "📄 Pedidos internos",
            "baja": "🧾 Baja de stock",
            "ordenes": "📦 Órdenes de compra",
            "indicadores": "📈 Indicadores (Power BI)",
        }
        destino = mapping.get(go.lower())
        if destino:
            st.session_state["radio_menu"] = destino
            st.query_params.clear()
            st.rerun()
except Exception:
    pass

# =========================
# MANEJAR CLICK CAMPANA
# =========================
try:
    if st.query_params.get("ir_notif") == "1":
        st.session_state["radio_menu"] = "📄 Pedidos internos"
        st.query_params.clear()
        st.rerun()
except Exception:
    pass

# =========================
# HEADER MÓVIL
# =========================
badge_html = ""
if cant_pendientes > 0:
    badge_html = f'<span class="notif-badge">{cant_pendientes}</span>'

st.markdown(f"""
<div id="mobile-header">
    <div class="logo">🦋 FertiChat</div>
</div>
<a id="campana-mobile" href="?ir_notif=1">
    🔔
    {badge_html}
</a>
""", unsafe_allow_html=True)

# =========================
# TÍTULO PC
# =========================
campana_html = '<span style="font-size:26px;">🔔</span>'
if cant_pendientes > 0:
    campana_html = f'<a href="?ir_notif=1" style="text-decoration:none;font-size:18px;background:#0b3b60;color:white;padding:6px 12px;border-radius:8px;">🔔 {cant_pendientes}</a>'

st.markdown("""
<style>
@media (max-width: 768px) {
  .header-desktop-wrapper { display: none !important; }
}
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="header-desktop-wrapper">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
            <h1 style="margin:0; font-size:38px; font-weight:900; color:#0f172a;">FertiChat</h1>
            <p style="margin:4px 0 0 0; font-size:15px; color:#64748b;">Sistema de Gestión de Compras</p>
        </div>
        <div>{campana_html}</div>
    </div>
    <hr style="margin-top:16px; border:none; border-top:1px solid #e2e8f0;">
</div>
""", unsafe_allow_html=True)

# =========================
# MAIN.PY - GO DESDE TARJETAS (QUERY PARAMS) - SOLO COMPRAS
# PONER ANTES DE ARMAR EL MENU/SIDEBAR
# =========================
def _get_qp_first(key: str):
    try:
        v = st.query_params.get(key)
        if isinstance(v, list):
            return v[0] if v else None
        return v
    except Exception:
        qp = st.experimental_get_query_params()
        lst = qp.get(key)
        return lst[0] if isinstance(lst, list) and lst else None

def _clear_qp():
    try:
        st.query_params.clear()
    except Exception:
        st.experimental_set_query_params()

_go = _get_qp_first("go")

if _go == "compras":
    _target = None
    for _opt in MENU_OPTIONS:
        if "compras" in (_opt or "").lower():
            _target = _opt
            break

    if _target:
        st.session_state["menu"] = _target

    _clear_qp()
    st.rerun()


# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.markdown("""
        <div style='
            background: rgba(255,255,255,0.85);
            padding: 16px;
            border-radius: 18px;
            margin-bottom: 14px;
            border: 1px solid rgba(15, 23, 42, 0.10);
            box-shadow: 0 10px 26px rgba(2, 6, 23, 0.06);
        '>
            <div style='display:flex; align-items:center; gap:10px; justify-content:center;'>
                <div style='font-size: 26px;'>🦋</div>
                <div style='font-size: 20px; font-weight: 800; color:#0f172a;'>FertiChat</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.text_input("Buscar...", key="sidebar_search", label_visibility="collapsed", placeholder="Buscar...")

    st.markdown(f"👤 **{user.get('nombre', 'Usuario')}**")
    if user.get("empresa"):
        st.markdown(f"🏢 {user.get('empresa')}")
    st.markdown(f"📧 _{user.get('Usuario', user.get('usuario', ''))}_")

    st.markdown("---")

    if st.button("🚪 Cerrar sesión", key="btn_logout_sidebar", use_container_width=True):
        logout()
        st.rerun()

    st.markdown("---")

    # =========================
    # DEBUG SQL (checkbox)
    # =========================
    st.session_state["DEBUG_SQL"] = st.checkbox("Debug SQL", value=False, key="debug_sql")

    st.markdown("---")
    st.markdown("## 📌 Menú")

    st.radio("Ir a:", MENU_OPTIONS, key="radio_menu")

# =========================
# FUNCIÓN PARA MOSTRAR DEBUG (PANTALLA SEPARADA)
# =========================
def mostrar_debug():
    st.header("🔍 Pantalla de Debug Completa")
    st.write("Aquí se muestra toda la información de debug para diagnosticar problemas en las consultas.")
    
    # Última Interpretación
    if "DBG_INT_LAST" in st.session_state:
        st.subheader("🎯 Última Interpretación de Pregunta")
        st.json(st.session_state["DBG_INT_LAST"])
    else:
        st.write("No hay interpretación reciente.")
    
    # Origen de Facturas
    if "DBG_FACTURAS_ORIGEN" in st.session_state:
        st.subheader("📋 Origen de Funciones de Facturas")
        st.write(f"**Usando:** {st.session_state['DBG_FACTURAS_ORIGEN']}")
    
    # Debug SQL
    st.subheader("🛠 Debug SQL")
    if st.checkbox("Mostrar detalles SQL (último)", key="show_sql_debug"):
        st.write("**Tag:**", st.session_state.get("DBG_SQL_LAST_TAG", "N/A"))
        st.write("**Query:**")
        st.code(st.session_state.get("DBG_SQL_LAST_QUERY", "No query"), language="sql")
        st.write("**Params:**", st.session_state.get("DBG_SQL_LAST_PARAMS", []))
        st.write("**Resultado:**")
        st.write("- Filas:", st.session_state.get("DBG_SQL_ROWS", 0))
        st.write("- Columnas:", st.session_state.get("DBG_SQL_COLS", []))
    else:
        st.write("Activa el checkbox para ver detalles SQL.")
    
    # Estado del Orquestador
    st.subheader("🚀 Estado del Sistema")
    st.write(f"**ORQUESTADOR_CARGADO:** {st.session_state.get('ORQUESTADOR_CARGADO', 'No')}")
    st.write(f"**DEBUG_SQL activado:** {st.session_state.get('DEBUG_SQL', False)}")
    
    # Logs Simulados (puedes agregar logs reales aquí)
    st.subheader("📝 Logs Recientes")
    logs = [
        "2024-10-01 10:00: Consulta procesada: 'compras roche'",
        "2024-10-01 10:05: Error en SQL: tabla no encontrada",
        # Agrega logs dinámicos si tienes un sistema de logging
    ]
    for log in logs:
        st.text(log)
    
    # Opciones de Debug
    st.subheader("⚙️ Opciones de Debug")
    if st.button("Limpiar Debug"):
        keys_to_clear = ["DBG_INT_LAST", "DBG_SQL_LAST_TAG", "DBG_SQL_LAST_QUERY", "DBG_SQL_LAST_PARAMS", "DBG_SQL_ROWS", "DBG_SQL_COLS", "DBG_FACTURAS_ORIGEN"]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.success("Debug limpiado.")
        st.rerun()
    
    # Espacio para más info
    st.subheader("💡 Consejos para Debug")
    st.markdown("""
    - Activa "Debug SQL" en el sidebar para capturar consultas.
    - Revisa la consola del servidor (logs de Streamlit) para prints adicionales.
    - Si no hay resultados, verifica que la BD tenga datos para el filtro aplicado.
    - Para facturas, asegúrate de que 'Tipo Comprobante' incluya 'Factura%' además de 'Compra%'.
    """)

# =========================
# ROUTER
# =========================
menu_actual = st.session_state["radio_menu"]

if menu_actual == "🏠 Inicio":
    mostrar_inicio()

elif "Chat (Chainlit)" in menu_actual:
    mostrar_chat_chainlit()

elif menu_actual == "🛒 Compras IA":
    mostrar_resumen_compras_rotativo()
    Compras_IA()

    # =========================
    # DEBUG (última consulta) - SOLO EN COMPRAS IA
    # =========================
    if st.session_state.get("DEBUG_SQL", False):
        with st.expander("🛠 Debug (última consulta)", expanded=True):
            st.subheader("Interpretación")
            st.json(st.session_state.get("DBG_INT_LAST", {}))

            st.subheader("SQL ejecutado")
            st.write("Origen:", st.session_state.get("DBG_SQL_LAST_TAG"))
            st.code(st.session_state.get("DBG_SQL_LAST_QUERY", ""), language="sql")
            st.write("Params:", st.session_state.get("DBG_SQL_LAST_PARAMS", []))

            st.subheader("Resultado")
            st.write("Filas:", st.session_state.get("DBG_SQL_ROWS"))
            st.write("Columnas:", st.session_state.get("DBG_SQL_COLS", []))

elif menu_actual == "🔍 Debug":
    mostrar_debug()

elif menu_actual == "📦 Stock IA":
    mostrar_resumen_stock_rotativo()
    mostrar_stock_ia()

elif menu_actual == "🔎 Buscador IA":
    mostrar_buscador_ia()

elif menu_actual == "📥 Ingreso de comprobantes":
    mostrar_ingreso_comprobantes()

elif menu_actual == "📊 Dashboard":
    mostrar_dashboard()

elif menu_actual == "📄 Pedidos internos":
    mostrar_pedidos_internos()

elif menu_actual == "🧾 Baja de stock":
    mostrar_baja_stock()

elif menu_actual == "📈 Indicadores (Power BI)":
    mostrar_indicadores_ia()

elif menu_actual == "📦 Órdenes de compra":
    mostrar_ordenes_compra()

elif menu_actual == "📒 Ficha de stock":
    mostrar_ficha_stock()

elif menu_actual == "📚 Artículos":
    mostrar_articulos()

elif menu_actual == "🏬 Depósitos":
    mostrar_depositos()

elif menu_actual == "🧩 Familias":
    mostrar_familias()

elif menu_actual == "📑 Comprobantes":
    mostrar_menu_comprobantes()


st.write("ORQUESTADOR_CARGADO =", st.session_state.get("ORQUESTADOR_CARGADO"))
