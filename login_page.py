# =====================================================================
# 🔐 PÁGINA DE LOGIN - FERTI CHAT
# =====================================================================
# Login por USUARIO (SIN CSS – hereda CSS_GLOBAL)
# =====================================================================

import streamlit as st
from auth import login_user, change_password, init_db

# Inicializar base de datos
init_db()

# =====================================================================
# UI COMPONENTS
# =====================================================================

def show_logo():
    st.markdown("""
        <div style="text-align:center; padding:10px 0 30px 0;">
            <div style="
                display:inline-block;
                background: rgba(255,255,255,0.9);
                border-radius: 20px;
                padding: 20px 40px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.10);
            ">
                <h1 style="
                    font-size: 42px;
                    font-weight: 800;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                    margin: 0;
                    letter-spacing: -1px;
                ">🦋 FertiChat</h1>
                <p style="
                    color: #64748b;
                    font-size: 15px;
                    margin: 8px 0 0 0;
                    font-weight: 500;
                ">Sistema de Gestión de Compras</p>
            </div>
        </div>
    """, unsafe_allow_html=True)


def show_footer():
    st.markdown("""
        <div style="
            text-align: center;
            color: rgba(255,255,255,0.85);
            font-size: 13px;
            padding-top: 30px;
            font-weight: 500;
        ">
            🦋 FertiChat © 2025 — Todos los derechos reservados
        </div>
    """, unsafe_allow_html=True)

# =====================================================================
# FORMULARIOS
# =====================================================================

def login_form():
    with st.form("login_form", clear_on_submit=False):

        st.markdown(
            "<p style='text-align:center;'>Ingresá tus credenciales para continuar</p>",
            unsafe_allow_html=True
        )

        st.text_input("🏢 Empresa", value="Fertilab", disabled=True)
        usuario = st.text_input("👤 Usuario", placeholder="Ingresá tu usuario")
        password = st.text_input("🔒 Contraseña", type="password", placeholder="Ingresá tu contraseña")

        submitted = st.form_submit_button("Ingresar", use_container_width=True)

        if submitted:
            if not usuario or not password:
                st.error("⚠️ Por favor completá todos los campos")
            else:
                ok, msg, user_data = login_user(usuario, password)
                if ok:
                    st.session_state["user"] = user_data
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")


def change_password_form():
    with st.form("change_password_form", clear_on_submit=True):

        st.markdown(
            "<p style='text-align:center;'>Actualizá tu contraseña de acceso</p>",
            unsafe_allow_html=True
        )

        usuario = st.text_input("👤 Usuario", placeholder="Tu usuario")
        old_password = st.text_input("🔑 Contraseña actual", type="password")
        new_password = st.text_input("🔒 Nueva contraseña", type="password")
        new_password2 = st.text_input("🔒 Confirmar nueva", type="password")

        submitted = st.form_submit_button("Cambiar contraseña", use_container_width=True)

        if submitted:
            if not usuario or not old_password or not new_password:
                st.error("⚠️ Por favor completá todos los campos")
            elif new_password != new_password2:
                st.error("⚠️ Las contraseñas nuevas no coinciden")
            elif len(new_password) < 4:
                st.error("⚠️ La contraseña debe tener al menos 4 caracteres")
            else:
                ok, msg = change_password(usuario, old_password, new_password)
                if ok:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")

# =====================================================================
# LOGIN PAGE PRINCIPAL
# =====================================================================

def show_login_page():
    # Marcador: el CSS global detecta login con esto
    st.markdown('<div id="fc-login-marker"></div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        show_logo()

        tab1, tab2 = st.tabs(["🔐 Ingresar", "🔑 Cambiar clave"])
        with tab1:
            login_form()
        with tab2:
            change_password_form()

        show_footer()

# =====================================================================
# GESTIÓN DE SESIÓN
# =====================================================================

def get_current_user() -> dict:
    """Obtiene el usuario actual de la sesión"""
    return st.session_state.get("user")


def logout():
    """Cierra la sesión del usuario"""
    st.session_state["user"] = None


def require_auth():
    """Requiere autenticación - muestra login si no hay sesión"""
    if "user" not in st.session_state or st.session_state["user"] is None:
        show_login_page()
        st.stop()

# =====================================================================
# SIDEBAR INFO
# =====================================================================

def show_user_info_sidebar(user: dict):
    """Muestra info del usuario en el sidebar"""
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"👤 **{user.get('nombre', '')}**")
    st.sidebar.markdown(f"🏢 {user.get('empresa', '')}")
    st.sidebar.markdown("---")

    if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
        logout()
        st.rerun()
