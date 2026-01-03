# =========================
# MAIN.PY - SIDEBAR NATIVO (PC OK) + CONTROL NATIVO EN MÓVIL (Z FLIP 5)
# =========================

import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="FertiChat",
    page_icon="🦋",
    layout="wide",
    initial_sidebar_state="auto"
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


# =========================
# INICIALIZACIÓN
# =========================
init_db()
require_auth()

user = get_current_user() or {}

if "radio_menu" not in st.session_state:
    st.session_state["radio_menu"] = "🏠 Inicio"

# Obtener notificaciones
usuario_actual = user.get("usuario", user.get("email", ""))
cant_pendientes = 0
if usuario_actual:
    cant_pendientes = contar_notificaciones_no_leidas(usuario_actual)


# =========================
# CSS COMPLETO
# =========================
st.markdown(f"""
<style>
/* Ocultar elementos (sin romper el control nativo del sidebar) */
#MainMenu, footer {{ display: none !important; }}
div[data-testid="stDecoration"] {{ display: none !important; }}

/* Theme general */
:root {{
    --fc-bg-1: #f6f4ef; 
    --fc-bg-2: #f3f6fb;
    --fc-primary: #0b3b60; 
    --fc-accent: #f59e0b;
}}

html, body {{ 
    font-family: Inter, system-ui, sans-serif; 
    color: #0f172a; 
}}

[data-testid="stAppViewContainer"] {{ 
    background: linear-gradient(135deg, var(--fc-bg-1), var(--fc-bg-2)); 
}}

.block-container {{ 
    max-width: 1240px; 
    padding-top: 1.25rem; 
    padding-bottom: 2.25rem; 
}}

/* ==========================================
   SIDEBAR - ESTILOS BASE (PC Y MÓVIL)
========================================== */
section[data-testid="stSidebar"] {{ 
    border-right: 1px solid rgba(15, 23, 42, 0.08); 
}}

section[data-testid="stSidebar"] > div {{
    background: rgba(255,255,255,0.95) !important;
    backdrop-filter: blur(8px);
}}

/* Forzar fondo blanco en TODOS los elementos del sidebar */
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"],
section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"],
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] .stTextInput,
section[data-testid="stSidebar"] .stButton,
section[data-testid="stSidebar"] .stRadio {{
    background: transparent !important;
}}

/* Radio buttons del menú */
div[data-testid="stSidebar"] div[role="radiogroup"] label {{
    border-radius: 12px; 
    padding: 8px 10px; 
    margin: 3px 0; 
    border: 1px solid transparent;
    background: rgba(255,255,255,0.5) !important;
}}

div[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{ 
    background: rgba(37,99,235,0.06) !important; 
}}

div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{
    background: rgba(245,158,11,0.10) !important; 
    border: 1px solid rgba(245,158,11,0.18);
}}

/* Header móvil - oculto por defecto */
#mobile-header {{ 
    display: none; 
}}

/* ==========================================
   DESKTOP (mouse/trackpad)
========================================== */
@media (hover: hover) and (pointer: fine) {{
    div[data-testid="stToolbarActions"] {{ display: none !important; }}

    /* No permitir colapsar sidebar en PC */
    div[data-testid="collapsedControl"] {{ display: none !important; }}
    [data-testid="baseButton-header"],
    button[data-testid="stSidebarCollapseButton"],
    button[data-testid="stSidebarExpandButton"],
    button[title="Close sidebar"],
    button[title="Open sidebar"] {{
        display: none !important;
    }}
}}

/* ==========================================
   MÓVIL (touch) - Z FLIP 5 y similares
========================================== */
@media (hover: none) and (pointer: coarse) {{
    
    /* Ocultar título y campana del contenido principal en móvil */
    #desktop-header {{
        display: none !important;
    }}
    
    /* Padding para el header móvil */
    .block-container {{ 
        padding-top: 70px !important; 
    }}

    /* Header móvil con campana */
    #mobile-header {{
        display: flex !important;
        position: fixed;
        top: 0; 
        left: 0; 
        right: 0;
        height: 56px;
        background: #0b3b60;
        z-index: 999996;
        align-items: center;
        justify-content: space-between;
        padding: 0 16px 0 56px;  /* deja lugar al control nativo a la izquierda */
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }}

    #mobile-header .logo {{
        color: white;
        font-size: 20px;
        font-weight: 800;
        display: flex;
        align-items: center;
        gap: 8px;
    }}

    #mobile-header .notif {{
        background: transparent;
        border: none;
        font-size: 24px;
        cursor: pointer;
        position: relative;
        padding: 8px;
    }}
    
    #mobile-header .notif-badge {{
        position: absolute;
        top: 2px;
        right: 2px;
        background: #ef4444;
        color: white;
        font-size: 11px;
        font-weight: 700;
        min-width: 18px;
        height: 18px;
        border-radius: 9px;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 4px;
    }}

    /* Control nativo para abrir sidebar */
    div[data-testid="collapsedControl"],
    button[data-testid="stSidebarExpandButton"],
    button[title="Open sidebar"] {{
        display: inline-flex !important;
        position: fixed !important;
        top: 12px !important;
        left: 12px !important;
        z-index: 1000000 !important;
    }}

    /* Control nativo para cerrar sidebar */
    [data-testid="baseButton-header"],
    button[data-testid="stSidebarCollapseButton"],
    button[title="Close sidebar"] {{
        display: inline-flex !important;
    }}

    /* ==========================================
       SIDEBAR MÓVIL - FONDO BLANCO
    ========================================== */
    section[data-testid="stSidebar"] {{
        background: white !important;
    }}
    
    section[data-testid="stSidebar"] > div {{
        background: white !important;
    }}
    
    section[data-testid="stSidebar"] > div > div {{
        background: white !important;
    }}
    
    /* Forzar blanco en todos los contenedores internos */
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
        background: white !important;
    }}
    
    section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {{
        background: white !important;
    }}
    
    /* Texto del sidebar legible */
    section[data-testid="stSidebar"] * {{
        color: #0f172a !important;
    }}
    
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label {{
        color: #0f172a !important;
    }}

    /* Ocultar la barra negra de Streamlit en móvil (Share, estrella, etc) */
    header[data-testid="stHeader"] {{
        background: transparent !important;
        height: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
    }}
    
    div[data-testid="stToolbar"] {{
        display: none !important;
    }}
}}
</style>
""", unsafe_allow_html=True)


# =========================
# HEADER MÓVIL CON CAMPANA (HTML)
# =========================
badge_html = ""
if cant_pendientes > 0:
    badge_html = f'<span class="notif-badge">{cant_pendientes}</span>'

st.markdown(f"""
<div id="mobile-header">
    <div class="logo">🦋 FertiChat</div>
    <a href="?ir_notif=1" class="notif" style="text-decoration:none;">
        🔔
        {badge_html}
    </a>
</div>
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
# TÍTULO Y CAMPANITA (SOLO PC - se oculta en móvil con CSS)
# =========================
st.markdown('<div id="desktop-header">', unsafe_allow_html=True)

col_logo, col_spacer, col_notif = st.columns([7, 2, 1])

with col_logo:
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 12px;">
            <div>
                <h1 style="margin: 0; font-size: 38px; font-weight: 900; color: #0f172a;">
                    FertiChat
                </h1>
                <p style="margin: 4px 0 0 0; font-size: 15px; color: #64748b;">
                    Sistema de Gestión de Compras
                </p>
            </div>
        </div>
    """, unsafe_allow_html=True)

with col_notif:
    if cant_pendientes > 0:
        if st.button(f"🔔 {cant_pendientes}", key="campanita_global"):
            st.session_state["radio_menu"] = "📄 Pedidos internos"
            st.rerun()
    else:
        st.markdown("<div style='text-align:right; font-size:26px;'>🔔</div>", unsafe_allow_html=True)

st.markdown('<hr></div>', unsafe_allow_html=True)


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
