# =====================================================================
# 🔐 PÁGINA DE LOGIN - FERTI CHAT
# =====================================================================
# Login por USUARIO
# =====================================================================

import streamlit as st
from auth import login_user, change_password, init_db

# Inicializar base de datos
init_db()

# =====================================================================
# 🎨 ESTILOS CSS (LOGIN OSCURO – ESTILO APP)
# =====================================================================

LOGIN_CSS = """
<style>
    /* Ocultar elementos de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}

    /* Fondo general */
    .stApp {
        background: linear-gradient(180deg, #020617 0%, #0f172a 100%);
        min-height: 100vh;
    }

    /* Contenedor central */
    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 1rem !important;
    }

    /* Tarjeta del formulario */
    [data-testid="stForm"] {
        background: #020617;
        border-radius: 18px;
        padding: 28px 32px;
        border: 1px solid #1e293b;
        box-shadow: 0 15px 45px rgba(0, 0, 0, 0.55);
    }

    /* Inputs */
    input {
        background-color: #020617 !important;
        color: #e5e7eb !important;
        border: 1px solid #1e293b !important;
        border-radius: 10px !important;
    }

    /* Labels */
    label {
        color: #cbd5f5 !important;
        font-weight: 500;
    }

    /* Tabs */
    button[data-baseweb="tab"] {
        color: #94a3b8 !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color: #e5e7eb !important;
        border-bottom: 2px solid #dc2626;
    }

    /* Botón principal */
    button[kind="primary"] {
        background: linear-gradient(180deg, #b91c1c, #7f1d1d) !important;
        border-radius: 12px !important;
        font-weight: 600;
        border: none;
    }

    button[kind="primary"]:hover {
        background: linear-gradient(180deg, #dc2626, #991b1b) !important;
    }

    /* Mensajes */
    .stAlert {
        border-radius: 10px;
    }
</style>
"""

# =====================================================================
# UI
# =====================================================================

def show_logo():
    st.markdown("""
        <div style="text-align:center; padding:20px 0 18px 0;">
            <h1 style="font-size:36px; font-weight:800; color:#e5e7eb;">
                🦋 Ferti Chat
            </h1>
            <p style="color:#94a3b8; font-size:15px;">
                Sistema de Gestión de Compras
            </p>
        </div>
    """, unsafe_allow_html=True)


def show_footer():
    st.markdown("""
        <div style="text-align:center; color:#64748b; font-size:12px; padding-top:22px;">
            🦋 Ferti Chat © 2025
        </div>
    """, unsafe_allow_html=True)

# =====================================================================
# FORMULARIOS
# =====================================================================

def login_form():
    with st.form("login_form", clear_on_submit=False):
        st.text_input("Empresa", value="Fertilab", disabled=True)
        usuario = st.text_input("Usuario", placeholder="gvelazquez")
        password = st.text_input("Contraseña", type="password")

        submitted = st.form_submit_button("Ingresar", use_container_width=True)

        if submitted:
            if not usuario or not password:
                st.error("⚠️ Completá todos los campos")
            else:
                ok, msg, user_data = login_user(usuario, password)
                if ok:
                    st.session_state["user"] = user_data
                    st.rerun()
                else:
                    st.error(msg)


def change_password_form():
    with st.form("change_password_form", clear_on_submit=True):
        usuario = st.text_input("Usuario")
        old_password = st.text_input("Contraseña actual", type="password")
        new_password = st.text_input("Nueva contraseña", type="password")
        new_password2 = st.text_input("Confirmar nueva", type="password")

        submitted = st.form_submit_button("Cambiar contraseña", use_container_width=True)

        if submitted:
            if not usuario or not old_password or not new_password:
                st.error("⚠️ Completá todos los campos")
            elif new_password != new_password2:
                st.error("⚠️ Las contraseñas no coinciden")
            else:
                ok, msg = change_password(usuario, old_password, new_password)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

# =====================================================================
# LOGIN PAGE
# =====================================================================

def show_login_page():
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.25, 1])
    with col2:
        show_logo()
        tab1, tab2 = st.tabs(["🔐 Ingresar", "🔑 Cambiar clave"])
        with tab1:
            login_form()
        with tab2:
            change_password_form()
        show_footer()

# =====================================================================
# SESIÓN
# =====================================================================

def get_current_user() -> dict:
    return st.session_state.get("user")

def logout():
    st.session_state["user"] = None

def require_auth():
    if "user" not in st.session_state or st.session_state["user"] is None:
        show_login_page()
        st.stop()

# =====================================================================
# SIDEBAR
# =====================================================================

def show_user_info_sidebar(user: dict):
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"👤 **{user.get('nombre', '')}**")
    st.sidebar.markdown(f"🏢 {user.get('empresa', '')}")
    st.sidebar.markdown("---")

    if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
        logout()
        st.rerun()
