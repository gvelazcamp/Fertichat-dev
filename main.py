# =========================
# MAIN.PY - SIDEBAR NATIVO (PC OK) + CONTROL NATIVO EN MÓVIL (Z FLIP 5)
# =========================

import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="FertiChat",
    page_icon="🦋",
    layout="wide",
    initial_sidebar_state="auto"  # ✅ PC abierto / móvil auto (nativo)
)

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


# =========================
# INICIALIZACIÓN
# =========================
init_db()
require_auth()

user = get_current_user() or {}

if "radio_menu" not in st.session_state:
    st.session_state["radio_menu"] = "🏠 Inicio"


# =========================
# CSS (CLAVE: NO OCULTAR stToolbar EN MÓVIL)
# =========================
st.markdown(r"""
<style>
/* Ocultar elementos (sin romper el control nativo del sidebar) */
#MainMenu, footer { display: none !important; }
div[data-testid="stDecoration"] { display: none !important; }

/* ✅ NO ocultar stToolbar ni stHeader globalmente */
/* Si ocultás stToolbar, en Z Flip 5 desaparece el botón ☰/flecha */

/* Theme general */
:root {
    --fc-bg-1: #f6f4ef; --fc-bg-2: #f3f6fb;
    --fc-primary: #0b3b60; --fc-accent: #f59e0b;
}

html, body { font-family: Inter, system-ui, sans-serif; color: #0f172a; }
[data-testid="stAppViewContainer"] { background: linear-gradient(135deg, var(--fc-bg-1), var(--fc-bg-2)); }
.block-container { max-width: 1240px; padding-top: 1.25rem; padding-bottom: 2.25rem; }

/* Sidebar look */
section[data-testid="stSidebar"] { border-right: 1px solid rgba(15, 23, 42, 0.08); }
section[data-testid="stSidebar"] > div {
    background: rgba(255,255,255,0.70);
    backdrop-filter: blur(8px);
}
div[data-testid="stSidebar"] div[role="radiogroup"] label {
    border-radius: 12px; padding: 8px 10px; margin: 3px 0; border: 1px solid transparent;
}
div[data-testid="stSidebar"] div[role="radiogroup"] label:hover { background: rgba(37,99,235,0.06); }
div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
    background: rgba(245,158,11,0.10); border: 1px solid rgba(245,158,11,0.18);
}

/* Header móvil visual (solo estética) */
#mobile-header { display: none; }

/* Campana mobile oculta por defecto */
#campana-mobile { display: none; }

/* =========================================================
   DESKTOP REAL (mouse/trackpad):
   - sidebar siempre visible
   - oculto controles de colapsar/expandir para que no lo puedan cerrar en PC
   - puedo ocultar toolbar actions sin romper nada
========================================================= */
@media (hover: hover) and (pointer: fine) {
  div[data-testid="stToolbarActions"] { display: none !important; }

  /* No permitir colapsar sidebar en PC */
  div[data-testid="collapsedControl"] { display: none !important; }
  [data-testid="baseButton-header"],
  button[data-testid="stSidebarCollapseButton"],
  button[data-testid="stSidebarExpandButton"],
  button[title="Close sidebar"],
  button[title="Open sidebar"] {
    display: none !important;
  }
}

/* =========================================================
   MÓVIL REAL (touch):
   - mostrar SI o SI el control nativo (☰ / flecha)
   - mantener visible el botón de cerrar del sidebar
========================================================= */
@media (hover: none) and (pointer: coarse) {
  .block-container { padding-top: 70px !important; }

  #mobile-header {
    display: flex !important;
    position: fixed;
    top: 0; left: 0; right: 0;
    height: 60px;
    background: #0b3b60;
    z-index: 999996;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px 0 56px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  }

  #mobile-header .logo {
    color: white;
    font-size: 20px;
    font-weight: 800;
  }

  /* Campana al lado de la flechita del sidebar */
  #campana-mobile {
    display: flex !important;
    position: fixed !important;
    top: 12px !important;
    left: 52px !important;
    z-index: 1000001 !important;
    font-size: 22px;
    text-decoration: none;
    padding: 6px;
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.15);
  }
  
  #campana-mobile .notif-badge {
    position: absolute;
    top: -4px;
    right: -4px;
    background: #ef4444;
    color: white;
    font-size: 10px;
    font-weight: 700;
    min-width: 16px;
    height: 16px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 3px;
  }

  /* ✅ Abrir sidebar (nativo) */
  div[data-testid="collapsedControl"],
  button[data-testid="stSidebarExpandButton"],
  button[title="Open sidebar"] {
    display: inline-flex !important;
    position: fixed !important;
    top: 12px !important;
    left: 12px !important;
    z-index: 1000000 !important;
  }

  /* ✅ Cerrar sidebar (nativo) */
  [data-testid="baseButton-header"],
  button[data-testid="stSidebarCollapseButton"],
  button[title="Close sidebar"] {
    display: inline-flex !important;
  }
}

/* =========================================================
   CAMBIOS VISUALES MÓVIL (max-width para asegurar)
========================================================= */
@media (max-width: 768px) {
  /* CONTENIDO PRINCIPAL - LETRAS NEGRAS */
  .block-container h1,
  .block-container h2,
  .block-container h3,
  .block-container h4,
  .block-container p,
  .block-container span,
  .block-container label,
  .block-container div,
  .block-container li,
  .block-container td,
  .block-container th,
  [data-testid="stMarkdownContainer"] *,
  [data-testid="stText"] *,
  [data-testid="stCaption"] * {
    color: #0f172a !important;
  }
  
  /* TARJETAS/CARDS - fondo beige */
  .block-container div[style*="background"],
  .block-container div[style*="border-radius"],
  [data-testid="stMetric"],
  [data-testid="metric-container"],
  [data-testid="stVerticalBlock"] div[style*="padding"],
  [data-testid="stHorizontalBlock"] div[style*="padding"] {
    background: #f6f4ef !important;
    background-color: #f6f4ef !important;
    color: #0f172a !important;
  }
  
  /* SELECTBOX/DROPDOWN - fondo claro */
  [data-baseweb="select"],
  [data-baseweb="select"] > div,
  [data-baseweb="select"] > div > div,
  [data-baseweb="popover"],
  [data-baseweb="popover"] > div,
  [data-baseweb="menu"],
  [data-baseweb="menu"] > div,
  div[data-baseweb="select"] div[class*="container"],
  div[data-baseweb="select"] div[class*="control"],
  div[data-baseweb="select"] div[class*="value"],
  div[data-baseweb="select"] input {
    background: #f8fafc !important;
    background-color: #f8fafc !important;
    color: #0f172a !important;
    border-color: #e2e8f0 !important;
  }
  
  /* Selectbox texto */
  [data-baseweb="select"] span,
  [data-baseweb="select"] div,
  [data-baseweb="select"] p {
    color: #0f172a !important;
  }
  
  /* Inputs con fondo claro y texto negro */
  .block-container input,
  .block-container textarea,
  .block-container select,
  [data-baseweb="input"],
  [data-baseweb="input"] > div,
  [data-baseweb="base-input"],
  [data-baseweb="base-input"] > div {
    background: #f8fafc !important;
    background-color: #f8fafc !important;
    color: #0f172a !important;
    border-color: #e2e8f0 !important;
  }
  
  /* Textarea */
  [data-baseweb="textarea"],
  [data-baseweb="textarea"] > div,
  [data-baseweb="textarea"] textarea {
    background: #f8fafc !important;
    color: #0f172a !important;
  }
  
  /* Radio buttons con fondo claro */
  .block-container [role="radiogroup"] label {
    background: #f8fafc !important;
    color: #0f172a !important;
  }
  
  /* Date input */
  [data-baseweb="datepicker"],
  [data-baseweb="datepicker"] > div {
    background: #f8fafc !important;
    color: #0f172a !important;
  }
  
  /* BOTONES - fondo claro */
  .block-container button,
  .block-container [data-testid="stButton"] button,
  .block-container [data-testid="stFormSubmitButton"] button,
  .stButton > button,
  button[kind="primary"],
  button[kind="secondary"],
  button[data-testid="baseButton-primary"],
  button[data-testid="baseButton-secondary"] {
    background: #f8fafc !important;
    background-color: #f8fafc !important;
    color: #0f172a !important;
    border: 1px solid #e2e8f0 !important;
  }
  
  /* Botones con icono */
  .block-container button span,
  .block-container button p,
  .block-container button div {
    color: #0f172a !important;
  }
  
  /* TABLAS/DATAFRAMES - fondo claro */
  [data-testid="stDataFrame"],
  [data-testid="stDataFrame"] > div,
  [data-testid="stTable"],
  [data-testid="stTable"] > div,
  .stDataFrame,
  div[class*="glideDataEditor"],
  div[class*="dvn-scroller"] {
    background: #f8fafc !important;
    background-color: #f8fafc !important;
  }
  
  /* Celdas de tabla */
  [data-testid="stDataFrame"] td,
  [data-testid="stDataFrame"] th,
  [data-testid="stTable"] td,
  [data-testid="stTable"] th {
    background: #f8fafc !important;
    color: #0f172a !important;
  }
  
  /* Tabs */
  [data-baseweb="tab-list"],
  [data-baseweb="tab-panel"],
  button[data-baseweb="tab"] {
    background: transparent !important;
    color: #0f172a !important;
  }
  
  /* Expander */
  [data-testid="stExpander"],
  [data-testid="stExpander"] > div {
    background: #f8fafc !important;
    color: #0f172a !important;
  }
  
  /* Alertas/Info boxes mantener sus colores pero texto negro */
  [data-testid="stAlert"] p,
  [data-testid="stAlert"] span,
  .stAlert p,
  .stAlert span {
    color: #0f172a !important;
  }

  /* SIDEBAR - FONDO BLANCO */
  section[data-testid="stSidebar"],
  section[data-testid="stSidebar"] > div,
  section[data-testid="stSidebar"] > div > div,
  section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
    background: #ffffff !important;
    background-color: #ffffff !important;
  }
  
  /* SIDEBAR - LETRAS NEGRAS */
  section[data-testid="stSidebar"] p,
  section[data-testid="stSidebar"] span,
  section[data-testid="stSidebar"] label,
  section[data-testid="stSidebar"] h1,
  section[data-testid="stSidebar"] h2,
  section[data-testid="stSidebar"] h3,
  section[data-testid="stSidebar"] div,
  section[data-testid="stSidebar"] strong,
  section[data-testid="stSidebar"] em {
    color: #0f172a !important;
  }
  
  /* Radio buttons */
  section[data-testid="stSidebar"] div[role="radiogroup"] label {
    background: #f8fafc !important;
  }
  
  section[data-testid="stSidebar"] div[role="radiogroup"] label span {
    color: #0f172a !important;
  }
  
  /* Input buscar */
  section[data-testid="stSidebar"] input {
    background: #f8fafc !important;
    color: #0f172a !important;
  }
  
  /* Botón cerrar sesión */
  section[data-testid="stSidebar"] button {
    background: #f1f5f9 !important;
    color: #0f172a !important;
  }
  
  section[data-testid="stSidebar"] button span {
    color: #0f172a !important;
  }
  
  /* FIX INPUTS/TEXTAREA - TAMAÑO Y FONDO BEIGE */
  .block-container input[type="text"],
  .block-container textarea,
  [data-baseweb="input"] input,
  [data-baseweb="textarea"] textarea {
    font-size: 14px !important;
    padding: 10px 12px !important;
    min-height: 42px !important;
  }

  .block-container input::placeholder,
  .block-container textarea::placeholder {
    font-size: 14px !important;
    opacity: 0.6;
    color: #64748b !important;
  }

  .block-container [data-testid="stChatInput"] input,
  .block-container [data-testid="stChatInput"] textarea,
  .block-container [data-testid="stChatInput"] [data-baseweb="input"],
  .block-container [data-testid="stChatInput"] [data-baseweb="base-input"] {
    font-size: 14px !important;
    padding: 10px 12px !important;
    min-height: 42px !important;
    background: #f8fafc !important;
    color: #0f172a !important;
  }
  
  .block-container [data-testid="stChatInput"] > div {
    background: #f8fafc !important;
  }

  .block-container [data-testid="stChatInput"] button {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
  }
}
  /* =========================================================
     FIX INPUTS/TEXTAREA - TAMAÑO Y FONDO BEIGE
     ======================================================== */
  
  /* Ajustar tamaño de inputs y textareas en contenido principal */
  .block-container input[type="text"],
  .block-container textarea,
  [data-baseweb="input"] input,
  [data-baseweb="textarea"] textarea {
    font-size: 14px !important;
    padding: 10px 12px !important;
    min-height: 42px !important;
    height: auto !important;
    line-height: 1.4 !important;
  }

  /* Contenedor del input */
  [data-baseweb="input"],
  [data-baseweb="textarea"],
  [data-baseweb="input"] > div,
  [data-baseweb="textarea"] > div {
    min-height: auto !important;
    height: auto !important;
  }

  /* Placeholder text más pequeño */
  .block-container input::placeholder,
  .block-container textarea::placeholder {
    font-size: 14px !important;
    opacity: 0.6;
    color: #64748b !important;
  }

  /* Text inputs específicos */
  .block-container [data-testid="stTextInput"] input,
  .block-container [data-testid="stTextInput"] > div,
  .block-container [data-testid="stTextInput"] [data-baseweb="input"] {
    font-size: 14px !important;
    padding: 10px 12px !important;
    height: 42px !important;
  }

  /* Text area específico */
  .block-container [data-testid="stTextArea"] textarea,
  .block-container [data-testid="stTextArea"] > div,
  .block-container [data-testid="stTextArea"] [data-baseweb="textarea"] {
    font-size: 14px !important;
    padding: 10px 12px !important;
    min-height: 80px !important;
    line-height: 1.4 !important;
  }

  /* FORZAR fondo claro en TODOS los contenedores de input */
  .block-container [data-testid="stTextInput"],
  .block-container [data-testid="stTextArea"],
  .block-container [data-testid="stChatInput"] {
    background: transparent !important;
  }

  .block-container [data-testid="stTextInput"] > div,
  .block-container [data-testid="stTextArea"] > div,
  .block-container [data-testid="stChatInput"] > div {
    background: #f8fafc !important;
    border-radius: 8px;
  }

  /* Chat input específico (el de "Compras IA") */
  .block-container [data-testid="stChatInput"] input,
  .block-container [data-testid="stChatInput"] textarea,
  .block-container [data-testid="stChatInput"] [data-baseweb="input"],
  .block-container [data-testid="stChatInput"] [data-baseweb="textarea"],
  .block-container [data-testid="stChatInput"] [data-baseweb="base-input"] {
    background: #f8fafc !important;
    background-color: #f8fafc !important;
    color: #0f172a !important;
    font-size: 14px !important;
  }

  /* Botón de envío del input también proporcional */
  .block-container button {
    font-size: 14px !important;
    padding: 10px 16px !important;
    min-height: 42px !important;
  }

  /* Botón de envío en chat input (flecha) */
  .block-container [data-testid="stChatInput"] button {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
  }
}

# =========================
# OBTENER NOTIFICACIONES (antes del header móvil)
# =========================
usuario_actual = user.get("usuario", user.get("email", ""))
cant_pendientes = 0
if usuario_actual:
    cant_pendientes = contar_notificaciones_no_leidas(usuario_actual)


# =========================
# HEADER MÓVIL (visual) CON CAMPANA AL LADO DE LA FLECHITA
# =========================
badge_html = ""
if cant_pendientes > 0:
    badge_html = f'<span class="notif-badge">{cant_pendientes}</span>'

st.markdown(f"""
<div id="mobile-header">
    <div class="logo">&#129419; FertiChat</div>
</div>
<a id="campana-mobile" href="?ir_notif=1">
    &#128276;
    {badge_html}
</a>
""", unsafe_allow_html=True)

# =========================
# MANEJAR CLICK EN CAMPANA MÓVIL
# =========================
try:
    if st.query_params.get("ir_notif") == "1":
        st.session_state["radio_menu"] = "📄 Pedidos internos"
        st.query_params.clear()
        st.rerun()
except:
    pass


# =========================
# TÍTULO Y CAMPANITA (SOLO PC - todo en HTML para poder ocultar)
# =========================
campana_html = '<span style="font-size:26px;">&#128276;</span>'
if cant_pendientes > 0:
    campana_html = '<a href="?ir_notif=1" style="text-decoration:none;font-size:18px;background:#0b3b60;color:white;padding:6px 12px;border-radius:8px;">&#128276; ' + str(cant_pendientes) + '</a>'

st.markdown(
    """
    <style>
    @media (max-width: 768px) {
        .header-desktop-wrapper {
            display: none !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)


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
# SIDEBAR
# =========================
with st.sidebar:
    st.markdown(f"""
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
    if user.get('empresa'):
        st.markdown(f"🏢 {user.get('empresa')}")
    st.markdown(f"📧 _{user.get('Usuario', user.get('usuario', ''))}_")

    st.markdown("---")

    if st.button("🚪 Cerrar sesión", key="btn_logout_sidebar", use_container_width=True):
        logout()
        st.rerun()

    st.markdown("---")
    st.markdown("## 📌 Menú")

    st.radio("Ir a:", MENU_OPTIONS, key="radio_menu")


# =========================
# ROUTER
# =========================
menu_actual = st.session_state["radio_menu"]

if menu_actual == "🏠 Inicio":
    mostrar_inicio()
elif menu_actual == "🛒 Compras IA":
    mostrar_resumen_compras_rotativo()
    Compras_IA()
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

