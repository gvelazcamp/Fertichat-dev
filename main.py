# =========================
# MAIN.PY - ORQUESTADOR PRINCIPAL (MINIMALISTA)
# =========================

import streamlit as st
from datetime import datetime

# =========================
# CONFIGURACIÓN STREAMLIT
# =========================
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

# Autenticación (ya existen)
from auth import init_db
from login_page import (
    require_auth,
    show_user_info_sidebar,
    get_current_user,
    logout,
    LOGIN_CSS
)

# Módulos externos (ya existen)
from pedidos import mostrar_pedidos_internos, contar_notificaciones_no_leidas
from bajastock import mostrar_baja_stock
from ordenes_compra import mostrar_ordenes_compra
from supabase_client import supabase

# Módulos nuevos
from ui_compras import Compras_IA, render_orquestador_output
from orquestador import procesar_pregunta_router
from ui_buscador import mostrar_buscador_ia
from ui_stock import mostrar_stock_ia, mostrar_resumen_stock_rotativo
from ui_dashboard import mostrar_dashboard, mostrar_indicadores_ia, mostrar_resumen_compras_rotativo

# =========================
# CSS RESPONSIVE
# =========================
def inject_css_responsive():
    st.markdown(
        """
        <style>
        @media (max-width: 768px){
            .block-container{
                padding-top: 0.9rem !important;
                padding-left: 0.8rem !important;
                padding-right: 0.8rem !important;
                padding-bottom: 4.5rem !important;
            }
            h1 { font-size: 1.35rem !important; line-height: 1.2 !important; }
            h2 { font-size: 1.15rem !important; line-height: 1.2 !important; }
            h3 { font-size: 1.05rem !important; line-height: 1.2 !important; }
            .stMarkdown, .stText, .stCaption, p, li{
                font-size: 0.95rem !important;
                line-height: 1.25 !important;
            }
            div[data-testid="stContainer"]{
                padding: 0.55rem !important;
            }
            div[role="radiogroup"] label{
                font-size: 0.95rem !important;
                margin-bottom: 0.25rem !important;
            }
            input, textarea{
                font-size: 1rem !important;
            }
            .stButton > button{
                width: 100% !important;
                padding: 0.60rem 0.9rem !important;
                font-size: 1rem !important;
            }
            div[data-testid="stDataFrame"]{
                font-size: 0.85rem !important;
            }
            div[data-testid="stDataFrame"] *{
                font-size: 0.85rem !important;
            }
            details summary{
                font-size: 0.95rem !important;
            }
            div[data-testid="stHorizontalBlock"]{
                flex-wrap: wrap !important;
                gap: 0.5rem !important;
            }
            div[data-testid="column"]{
                min-width: 280px !important;
                flex: 1 1 280px !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    )


# =========================
# INICIALIZACIÓN
# =========================
inject_css_responsive()
init_db()
require_auth()

user = get_current_user() or {}

# =========================
# TÍTULO Y CAMPANITA
# =========================
st.title("🦋 FertiChat")
st.caption("Sistema de Gestión de Compras")

usuario_actual = user.get("usuario", user.get("email", ""))

if usuario_actual:
    cant_pendientes = contar_notificaciones_no_leidas(usuario_actual)
    col_notif, col_space = st.columns([1, 9])

    with col_notif:
        if cant_pendientes > 0:
            if st.button(
                f"🔔 {cant_pendientes}",
                key="campanita_global",
                help="Tenés pedidos internos pendientes"
            ):
                st.session_state["ir_a_pedidos"] = True
                st.rerun()
        else:
            st.markdown("🔔")

    st.markdown("---")

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.markdown(f"""
        <div style='
            background: linear-gradient(135deg, #1e3a5f, #3d7ab5);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            color: white;
        '>
            <div style='font-size: 24px; text-align: center; margin-bottom: 5px;'>🦋</div>
            <div style='font-size: 18px; font-weight: bold; text-align: center;'>Ferti Chat</div>
            <div style='font-size: 12px; text-align: center; opacity: 0.8;'>Sistema de Gestión</div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown(f"👤 **{user.get('nombre', 'Usuario')}**")
    if user.get('empresa'):
        st.markdown(f"🏢 {user.get('empresa')}")
    st.markdown(f"📧 _{user.get('Usuario', '')}_")

    st.markdown("---")

    if st.button("🚪 Cerrar sesión", key="btn_logout_sidebar", use_container_width=True, type="secondary"):
        logout()
        st.rerun()

    st.markdown("---")
    st.markdown("## 📌 Menú")

    if st.session_state.get("ir_a_pedidos"):
        st.session_state["menu_principal"] = "📄 Pedidos internos"
        st.session_state["ir_a_pedidos"] = False

    default_opt = st.session_state.get("menu_principal", "🛒 Compras IA")
    if default_opt not in MENU_OPTIONS:
        default_opt = MENU_OPTIONS[0]
        st.session_state["menu_principal"] = default_opt

    menu = st.radio("Ir a:", MENU_OPTIONS, index=MENU_OPTIONS.index(default_opt), key="menu_principal")

# =========================
# ROUTER
# =========================
if menu == "🛒 Compras IA":
    mostrar_resumen_compras_rotativo()
    Compras_IA()

elif menu == "🔎 Buscador IA":
    mostrar_buscador_ia()

elif menu == "📦 Stock IA":
    mostrar_resumen_stock_rotativo()
    mostrar_stock_ia()

elif menu == "📊 Dashboard":
    mostrar_dashboard()

elif menu == "📄 Pedidos internos":
    mostrar_pedidos_internos()

elif menu == "🧾 Baja de stock":
    mostrar_baja_stock()

elif menu == "📈 Indicadores (Power BI)":
    mostrar_indicadores_ia()

elif menu == "📦 Órdenes de compra":
    mostrar_ordenes_compra()
