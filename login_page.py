# =====================================================================
# 🔐 PÁGINA DE LOGIN - FERTI CHAT
# =====================================================================
# Login por USUARIO - Diseño Moderno
# =====================================================================

import streamlit as st
from auth import login_user, change_password, init_db

# Inicializar base de datos
init_db()

# =====================================================================
# 🎨 ESTILOS CSS - DISEÑO MODERNO Y LUMINOSO
# =====================================================================

LOGIN_CSS = """
<style>
    /* Ocultar elementos de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}

    /* Fondo con gradiente suave */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        min-height: 100vh;
    }

    /* Contenedor central */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 1rem !important;
    }

    /* Tarjeta del formulario - Glassmorphism */
    [data-testid="stForm"] {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 24px;
        padding: 32px 36px;
        border: none;
        box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
        backdrop-filter: blur(10px);
    }

    /* =========================================================
       FIX MOBILE: INPUTS + BOTÓN OJO (evitar zona negra)
       Streamlit usa BaseWeb wrappers; en móvil se nota más.
    ========================================================= */

    /* Wrapper de BaseWeb (incluye el botón del ojo) */
    div[data-baseweb="base-input"],
    div[data-baseweb="input"]{
        background: #f8fafc !important;
        border: 2px solid #e2e8f0 !important;
        border-radius: 12px !important;
        box-shadow: none !important;
        overflow: hidden !important; /* evita “bloques” raros */
    }

    /* Estado focus del wrapper */
    div[data-baseweb="base-input"]:focus-within,
    div[data-baseweb="input"]:focus-within{
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2) !important;
    }

    /* Input real: sin borde (el borde lo maneja el wrapper) */
    div[data-baseweb="base-input"] input,
    div[data-baseweb="input"] input{
        border: none !important;
        outline: none !important;
        background: transparent !important;
        color: #1e293b !important;
        -webkit-text-fill-color: #1e293b !important;
        padding: 12px 16px !important;
        font-size: 16px !important;
    }

    /* Botón del ojo (no negro) */
    div[data-baseweb="base-input"] button,
    div[data-baseweb="input"] button{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #475569 !important;
        padding-right: 10px !important;
    }

    /* Disabled: “Fertilab” bien oscuro también en cel */
    div[data-baseweb="base-input"] input:disabled,
    div[data-baseweb="input"] input:disabled{
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
        opacity: 1 !important;
        background: transparent !important;
    }

    /* Placeholder visible */
    div[data-baseweb="base-input"] input::placeholder,
    div[data-baseweb="input"] input::placeholder{
        color: #64748b !important;
        -webkit-text-fill-color: #64748b !important;
        opacity: 1 !important;
    }

    /* Labels */
    label {
        color: #374151 !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        margin-bottom: 6px !important;
    }

    /* Tabs */
    [data-baseweb="tab-list"] {
        background: #f1f5f9;
        border-radius: 12px;
        padding: 4px;
        gap: 4px;
    }

    button[data-baseweb="tab"] {
        color: #64748b !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        padding: 10px 20px !important;
        background: transparent !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color: #667eea !important;
        background: white !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
    }

    /* Botón principal */
    .stForm button[kind="secondaryFormSubmit"],
    .stForm button[type="submit"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
        font-size: 16px !important;
        padding: 14px 28px !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4) !important;
        transition: all 0.3s ease !important;
        text-transform: none !important;
    }

    .stForm button[kind="secondaryFormSubmit"]:hover,
    .stForm button[type="submit"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5) !important;
    }

    /* Mensajes de error/éxito */
    .stAlert {
        border-radius: 12px !important;
        border: none !important;
    }

    [data-testid="stAlert"] {
        background: #fef2f2 !important;
        border-left: 4px solid #ef4444 !important;
    }

    /* Success message */
    [data-testid="stAlert"][data-baseweb="notification"] {
        background: #f0fdf4 !important;
        border-left: 4px solid #22c55e !important;
    }

    /* Responsive */
    @media (max-width: 768px) {
        [data-testid="stForm"] {
            padding: 24px 20px;
            border-radius: 20px;
        }

        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-bottom: 4rem !important; /* más scroll con teclado */
        }
    }

/* =========================
   FIX: Input "Usuario" siempre blanco (móvil/auto-fill)
   ========================= */
div[data-testid="stForm"] input,
div[data-testid="stForm"] textarea {
    background-color: #f8fafc !important;
    color: #1e293b !important;
    -webkit-text-fill-color: #1e293b !important;
}

/* Autofill (Chrome/Android) */
div[data-testid="stForm"] input:-webkit-autofill,
div[data-testid="stForm"] input:-webkit-autofill:hover,
div[data-testid="stForm"] input:-webkit-autofill:focus,
div[data-testid="stForm"] input:-webkit-autofill:active {
    -webkit-box-shadow: 0 0 0 1000px #f8fafc inset !important;
    box-shadow: 0 0 0 1000px #f8fafc inset !important;
    -webkit-text-fill-color: #1e293b !important;
    caret-color: #1e293b !important;
    transition: background-color 9999s ease-in-out 0s !important;
}

    @media (max-width: 480px) {
        /* un poco más compacto aún */
        [data-testid="stForm"] {
            padding: 22px 18px !important;
        }
    }
</style>
"""

# =====================================================================
# UI COMPONENTS
# =====================================================================

def show_logo():
    st.markdown("""
        <div style="text-align:center; padding:10px 0 30px 0;">
            <div style="
                display: inline-block;
                background: rgba(255,255,255,0.9);
                border-radius: 20px;
                padding: 20px 40px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.1);
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
                ">
                    🦋 FertiChat
                </h1>
                <p style="
                    color: #64748b;
                    font-size: 15px;
                    margin: 8px 0 0 0;
                    font-weight: 500;
                ">
                    Sistema de Gestión de Compras
                </p>
            </div>
        </div>
    """, unsafe_allow_html=True)


def show_footer():
    st.markdown("""
        <div style="
            text-align: center;
            color: rgba(255,255,255,0.8);
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
        st.markdown("""
            <p style="
                text-align: center;
                color: #64748b;
                font-size: 14px;
                margin-bottom: 20px;
            ">
                Ingresá tus credenciales para continuar
            </p>
        """, unsafe_allow_html=True)

        st.text_input("🏢 Empresa", value="Fertilab", disabled=True)
        usuario = st.text_input("👤 Usuario", placeholder="Ingresá tu usuario")
        password = st.text_input("🔒 Contraseña", type="password", placeholder="Ingresá tu contraseña")

        st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)

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
        st.markdown("""
            <p style="
                text-align: center;
                color: #64748b;
                font-size: 14px;
                margin-bottom: 20px;
            ">
                Actualizá tu contraseña de acceso
            </p>
        """, unsafe_allow_html=True)

        usuario = st.text_input("👤 Usuario", placeholder="Tu usuario")
        old_password = st.text_input("🔑 Contraseña actual", type="password", placeholder="Contraseña actual")
        new_password = st.text_input("🔒 Nueva contraseña", type="password", placeholder="Nueva contraseña")
        new_password2 = st.text_input("🔒 Confirmar nueva", type="password", placeholder="Repetí la nueva contraseña")

        st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)

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
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)

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
