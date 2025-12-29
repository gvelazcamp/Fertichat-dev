# =====================================================================
# 🔐 PÁGINA DE LOGIN - FERTI CHAT
# =====================================================================
# Diseño minimalista y profesional
# Fecha: 27 Diciembre 2024
# =====================================================================

import streamlit as st
from auth import login_user, change_password, init_db  # ✅ SACAR register_user

# Inicializar base de datos
init_db()

# =====================================================================
# ESTILOS CSS - DISEÑO MINIMALISTA COMPACTO
# =====================================================================

LOGIN_CSS = """
<style>
    /* Ocultar elementos de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* Fondo general - gris muy claro */
    .stApp {
        background: linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%);
        min-height: 100vh;
    }
    
    /* Contenedor del formulario - más compacto */
    [data-testid="stForm"] {
        background: white;
        border-radius: 16px;
        padding: 25px 30px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border: 1px solid #e5e7eb;
    }
    
    /* Inputs - más compactos */
    .stTextInput > div > div > input {
        border-radius: 10px !important;
        border: 2px solid #e5e7eb !important;
        padding: 12px 14px !important;
        font-size: 14px !important;
        background: #f9fafb !important;
        transition: all 0.2s ease !important;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #f97316 !important;
        box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.15) !important;
        background: white !important;
    }
    
    .stTextInput > div > div > input:disabled {
        background: #f3f4f6 !important;
        color: #6b7280 !important;
        cursor: not-allowed !important;
    }
    
    /* Labels - más compactos */
    .stTextInput > label {
        color: #374151 !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        margin-bottom: 4px !important;
    }
    
    /* Botón principal - CORAL/ROJO */
    .stFormSubmitButton > button {
        background: linear-gradient(135deg, #f97316 0%, #ea580c 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 12px 24px !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        width: 100% !important;
        cursor: pointer !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 14px rgba(249, 115, 22, 0.35) !important;
        margin-top: 8px !important;
    }
    
    .stFormSubmitButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(249, 115, 22, 0.45) !important;
    }
    
    /* Tabs - más compactos */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: #f3f4f6;
        border-radius: 10px;
        padding: 3px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: #6b7280;
        font-weight: 500;
        font-size: 13px;
        padding: 8px 16px;
    }
    
    .stTabs [aria-selected="true"] {
        background: white !important;
        color: #f97316 !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    
    /* Checkbox */
    .stCheckbox > label {
        color: #6b7280 !important;
        font-size: 13px !important;
    }
    
    /* Reducir espacios en general */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 1rem !important;
    }
    
    /* Tabs content padding */
    .stTabs [data-baseweb="tab-panel"] {
        padding-top: 15px !important;
    }
</style>
"""

# =====================================================================
# COMPONENTES UI
# =====================================================================

def show_logo():
    """Muestra el logo de Ferti Chat - mariposa inline"""
    st.markdown("""
        <div style='text-align: center; padding: 15px 0 20px 0;'>
            <h1 style='
                font-size: 34px;
                font-weight: 700;
                color: #1f2937;
                margin: 0;
                letter-spacing: -0.5px;
            '>🦋 Ferti Chat</h1>
            <p style='
                color: #6b7280;
                font-size: 14px;
                margin-top: 6px;
                font-weight: 400;
            '>Sistema de Gestión de Compras</p>
        </div>
    """, unsafe_allow_html=True)

def show_footer():
    """Footer minimalista"""
    st.markdown("""
        <div style='
            text-align: center;
            padding: 20px 0 5px 0;
            color: #9ca3af;
            font-size: 12px;
        '>
            🦋 Ferti Chat © 2025
        </div>
    """, unsafe_allow_html=True)

# =====================================================================
# FORMULARIOS
# =====================================================================

def login_form():
    """Formulario de inicio de sesión con empresa fija (login por USUARIO)"""

    with st.form("login_form", clear_on_submit=False):
        # Empresa bloqueada
        empresa = st.text_input("Empresa", value="Fertilab", disabled=True, key="login_empresa")

        # ✅ Antes decía Email. Tu auth es por usuario.
        usuario = st.text_input("Usuario", placeholder="gvelazquez", key="login_usuario")
        password = st.text_input("Contraseña", type="password", placeholder="••••••••", key="login_pass")

        remember = st.checkbox("Recordarme", value=True)

        submitted = st.form_submit_button("Ingresar", use_container_width=True)

        if submitted:
            if not usuario or not password:
                st.error("⚠️ Completá todos los campos")
            else:
                success, message, user_data = login_user(usuario, password)
                if success:
                    st.session_state['authenticated'] = True
                    st.session_state['user'] = user_data
                    st.success("✅ ¡Bienvenido!")
                    st.rerun()
                else:
                    st.error(f"❌ {message}")

def change_password_form():
    """Formulario para cambiar contraseña (por USUARIO)"""

    with st.form("change_password_form", clear_on_submit=True):
        # ✅ Antes decía Email
        usuario = st.text_input("Usuario", placeholder="gvelazquez", key="chg_usuario")
        old_password = st.text_input("Contraseña actual", type="password", key="chg_old")
        new_password = st.text_input("Nueva contraseña", type="password", placeholder="Mínimo 4 caracteres", key="chg_new")
        new_password2 = st.text_input("Confirmar nueva", type="password", key="chg_new2")

        submitted = st.form_submit_button("Cambiar contraseña", use_container_width=True)

        if submitted:
            if not usuario or not old_password or not new_password:
                st.error("⚠️ Completá todos los campos")
            elif new_password != new_password2:
                st.error("⚠️ Las contraseñas no coinciden")
            elif len(new_password) < 4:
                st.error("⚠️ Mínimo 4 caracteres")
            else:
                success, message = change_password(usuario, old_password, new_password)
                if success:
                    st.success(f"✅ {message}")
                else:
                    st.error(f"❌ {message}")

# =====================================================================
# PÁGINA PRINCIPAL DE LOGIN
# =====================================================================

def show_login_page():
    """Muestra la página de login completa"""

    st.markdown(LOGIN_CSS, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.3, 1])

    with col2:
        show_logo()

        tab1, tab2 = st.tabs(["🔐 Ingresar", "🔑 Cambiar clave"])

        with tab1:
            login_form()

        with tab2:
            change_password_form()

        show_footer()

# =====================================================================
# FUNCIONES DE SESIÓN
# =====================================================================

def is_authenticated() -> bool:
    return st.session_state.get('authenticated', False)

def get_current_user() -> dict:
    return st.session_state.get('user', {})

def logout():
    st.session_state['authenticated'] = False
    st.session_state['user'] = None

def require_auth():
    if not is_authenticated():
        show_login_page()
        return False
    return True

# =====================================================================
# SIDEBAR CON INFO DE USUARIO
# =====================================================================

def show_user_info_sidebar():
    user = get_current_user()

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"👤 **{user.get('nombre', 'Usuario')}**")
    st.sidebar.markdown(f"📧 {user.get('email', '')}")

    if user.get('empresa'):
        st.sidebar.markdown(f"🏢 {user.get('empresa')}")

    st.sidebar.markdown("---")

    if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
        logout()
        st.rerun()

# =====================================================================
# TEST
# =====================================================================

if __name__ == "__main__":
    st.set_page_config(
        page_title="Ferti Chat - Iniciar Sesión",
        page_icon="🦋",
        layout="centered",
        initial_sidebar_state="collapsed"
    )

    if not require_auth():
        st.stop()

    st.title("🦋 Ferti Chat")
    st.success(f"¡Bienvenido {get_current_user().get('nombre')}!")
    show_user_info_sidebar()
