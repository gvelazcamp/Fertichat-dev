# =========================
# MAIN.PY - SOLUCIÓN DEFINITIVA CON BOTONES NATIVOS
# =========================

import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="FertiChat",
    page_icon="🦋",
    layout="wide",
    initial_sidebar_state="expanded"
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
# CSS GLOBAL
# =========================
st.markdown("""
<style>
/* Ocultar UI de Streamlit */
div.stAppToolbar,
div[data-testid="stToolbar"],
div[data-testid="stToolbarActions"],
div[data-testid="stDecoration"],
#MainMenu,
footer {
  display: none !important;
}

header[data-testid="stHeader"] {
  height: 0 !important;
  background: transparent !important;
}

/* Theme general */
:root {
    --fc-bg-1: #f6f4ef;
    --fc-bg-2: #f3f6fb;
    --fc-primary: #0b3b60;
    --fc-accent: #f59e0b;
}

html, body {
    font-family: Inter, system-ui, sans-serif;
    color: #0f172a;
}

[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, var(--fc-bg-1), var(--fc-bg-2));
}

.block-container {
    max-width: 1240px;
    padding-top: 1.25rem;
    padding-bottom: 2.25rem;
}

/* Sidebar PC */
section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(15, 23, 42, 0.08);
}
section[data-testid="stSidebar"] > div {
    background: rgba(255,255,255,0.70);
    backdrop-filter: blur(8px);
}

div[data-testid="stSidebar"] div[role="radiogroup"] label {
    border-radius: 12px;
    padding: 8px 10px;
    margin: 3px 0;
    border: 1px solid transparent;
}
div[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
    background: rgba(37,99,235,0.06);
}
div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
    background: rgba(245,158,11,0.10);
    border: 1px solid rgba(245,158,11,0.18);
}

/* PC: ocultar menú móvil */
@media (min-width: 769px) {
    #fc-mobile-header,
    #fc-mobile-menu-container {
        display: none !important;
    }
}

/* MÓVIL: menú propio */
@media (max-width: 768px) {
    section[data-testid="stSidebar"] {
        display: none !important;
    }

    .block-container {
        padding-top: 70px !important;
    }

    #fc-mobile-header {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 56px;
        background: #0b3b60;
        z-index: 999999;
        display: flex;
        align-items: center;
        padding: 0 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }

    #fc-mobile-logo {
        color: white;
        font-size: 18px;
        font-weight: 800;
        margin-left: 12px;
        letter-spacing: -0.01em;
    }

    #fc-mobile-menu-container {
        position: fixed;
        top: 56px;
        left: 0;
        width: 290px;
        height: calc(100vh - 56px);
        background: rgba(255,255,255,0.98);
        box-shadow: 4px 0 12px rgba(0,0,0,0.15);
        z-index: 999998;
        overflow-y: auto;
        padding: 16px;
        transform: translateX(-100%);
        transition: transform 0.25s ease;
    }

    #fc-mobile-menu-container.open {
        transform: translateX(0);
    }

    .fc-user-info {
        background: rgba(248,250,252,0.95);
        padding: 14px;
        border-radius: 12px;
        margin-bottom: 14px;
        border: 1px solid rgba(15,23,42,0.10);
    }

    .fc-user-line {
        color: #0f172a;
        font-size: 14px;
        margin: 4px 0;
        line-height: 1.2;
    }

    .fc-user-sub {
        color: #64748b;
        font-size: 12px;
    }

    .fc-section-label {
        color: #64748b;
        font-size: 11px;
        font-weight: 800;
        text-transform: uppercase;
        margin: 12px 0 8px 4px;
    }

    /* Estilizar botones de Streamlit como tu menú */
    #fc-mobile-menu-container button[kind="secondary"] {
        display: block !important;
        width: 100%;
        padding: 14px 14px;
        margin: 6px 0;
        border-radius: 10px;
        background: rgba(248,250,252,0.92) !important;
        border: 1px solid rgba(15,23,42,0.10) !important;
        cursor: pointer;
        color: #0f172a !important;
        font-size: 15px;
        font-weight: 500;
        text-decoration: none;
        text-align: left;
    }

    #fc-mobile-menu-container button[kind="secondary"]:hover {
        background: rgba(245,158,11,0.10) !important;
        border-color: rgba(245,158,11,0.20) !important;
    }

    #fc-mobile-menu-container button[kind="primary"] {
        display: block !important;
        width: 100%;
        padding: 14px 14px;
        margin: 14px 0 6px 0;
        border-radius: 10px;
        background: rgba(244,63,94,0.08) !important;
        border: 1px solid rgba(244,63,94,0.20) !important;
        cursor: pointer;
        color: #dc2626 !important;
        font-size: 15px;
        font-weight: 700;
    }

    .fc-menu-toggle {
        width: 44px;
        height: 44px;
        background: transparent;
        border: none;
        cursor: pointer;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        gap: 5px;
        padding: 0;
    }

    .fc-menu-toggle span {
        width: 24px;
        height: 3px;
        background: white;
        border-radius: 2px;
        transition: all 0.20s;
        display: block;
    }

    #fc-overlay {
        position: fixed;
        top: 56px;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0,0,0,0.5);
        z-index: 999997;
        opacity: 0;
        visibility: hidden;
        transition: all 0.25s;
    }

    #fc-overlay.open {
        opacity: 1;
        visibility: visible;
    }
}
</style>
""", unsafe_allow_html=True)


# =========================
# INICIALIZACIÓN
# =========================
init_db()
require_auth()

user = get_current_user() or {}

if "radio_menu" not in st.session_state:
    st.session_state["radio_menu"] = "🏠 Inicio"

if "menu_open" not in st.session_state:
    st.session_state["menu_open"] = False


# =========================
# HEADER MÓVIL (SIEMPRE VISIBLE)
# =========================
st.markdown(f"""
<div id="fc-mobile-header">
  <div class="fc-menu-toggle" onclick="window.parent.document.querySelector('#fc-mobile-menu-container').classList.toggle('open'); window.parent.document.querySelector('#fc-overlay').classList.toggle('open');">
    <span></span><span></span><span></span>
  </div>
  <div id="fc-mobile-logo">🦋 FertiChat</div>
</div>
<div id="fc-overlay" onclick="this.classList.remove('open'); window.parent.document.querySelector('#fc-mobile-menu-container').classList.remove('open');"></div>
""", unsafe_allow_html=True)


# =========================
# MENÚ MÓVIL CON BOTONES NATIVOS DE STREAMLIT
# =========================
menu_container = st.container()
with menu_container:
    st.markdown('<div id="fc-mobile-menu-container">', unsafe_allow_html=True)
    
    # Info usuario
    st.markdown(f"""
    <div class="fc-user-info">
        <div class="fc-user-line" style="font-weight:800;">👤 {user.get('nombre', 'Usuario')}</div>
        <div class="fc-user-line fc-user-sub">🏢 {user.get('empresa', 'Empresa')}</div>
        <div class="fc-user-line fc-user-sub">📧 {user.get('Usuario', user.get('usuario', ''))}</div>
    </div>
    <div class="fc-section-label">Menú</div>
    """, unsafe_allow_html=True)
    
    # Botones del menú (usando st.button que NO recarga la página)
    for opcion in MENU_OPTIONS:
        if st.button(opcion, key=f"mobile_menu_{opcion}", type="secondary", use_container_width=True):
            st.session_state["radio_menu"] = opcion
            st.session_state["menu_open"] = False
            st.rerun()
    
    # Botón logout
    if st.button("🚪 Cerrar sesión", key="mobile_logout", type="primary", use_container_width=True):
        logout()
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)


# =========================
# TÍTULO Y CAMPANITA
# =========================
usuario_actual = user.get("usuario", user.get("email", ""))
cant_pendientes = 0
if usuario_actual:
    cant_pendientes = contar_notificaciones_no_leidas(usuario_actual)

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

st.markdown("<hr>", unsafe_allow_html=True)


# =========================
# SIDEBAR (PC)
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

    menu = st.radio("Ir a:", MENU_OPTIONS, key="radio_menu")


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
