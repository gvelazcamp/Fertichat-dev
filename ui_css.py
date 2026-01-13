import streamlit as st
import hashlib

# CSS GLOBAL INTEGRADO (tu ui_css.py)
CSS_GLOBAL = r"""
<style>

/* =========================
   Ocultar basura (no rompe menú/sidebar)
   ========================= */
footer { visibility: hidden; }
div[data-testid="stDecoration"] { display: none !important; }

/* =========================
   FORZAR MODO CLARO (GLOBAL)
   ========================= */
:root, html, body, .stApp {
  color-scheme: light !important;
}
/* ================================
   FORZAR LIGHT MODE (ANTI DARK)
   ================================ */

/* Decirle al navegador que SOLO usamos light */
:root {
  color-scheme: light !important;
}

/* Evitar dark automático de Chrome */
html {
  background-color: #f6f4ef !important;
}

/* Inputs, cards, contenedores */
* {
  background-color: inherit;
}

/* Anti "forced dark" de Chrome */
@media (prefers-color-scheme: dark) {
  html, body {
    background: #f6f4ef !important;
    color: #0f172a !important;
  }

  * {
    filter: none !important;
  }
}
html, body {
  background: #f6f4ef !important;
  color: #0f172a !important;
}

/* Si el sistema está dark, igual lo dejamos claro */
@media (prefers-color-scheme: dark) {
  :root, html, body, .stApp {
    color-scheme: light !important;
  }
  html, body {
    background: #f6f4ef !important;
    color: #0f172a !important;
  }
}

/* =========================
   Fondo principal APP
   ========================= */
:root {
  --fc-bg-1: #f6f4ef;
  --fc-bg-2: #f3f6fb;
  --fc-text: #0f172a;
}

html, body,
.stApp,
div[data-testid="stApp"],
div[data-testid="stAppViewContainer"],
div[data-testid="stAppViewContainer"] > .main,
div[data-testid="stAppViewContainer"] > .main > div {
  background: linear-gradient(135deg, var(--fc-bg-1), var(--fc-bg-2)) !important;
  color: var(--fc-text) !important;
}

html, body {
  font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

/* =========================
   OCULTAR SOLO el linkcito del H1 (ícono ancla)
   ========================= */
[data-testid="stHeaderActionElements"] { display: none !important; }
h1 > span.eqpbrs03, h2 > span.eqpbrs03, h3 > span.eqpbrs03 { display: none !important; }

/* =========================
   OCULTAR EL H1 "Inicio" gigante
   ========================= */
h1#inicio { display: none !important; }

/* =========================
   (Opcional) ocultar tus cosas custom si quedaron
   ========================= */
#campana-mobile { display: none !important; }
#mobile-header .logo { display: none !important; }

/* =========================
   SIDEBAR: blanco + texto negro
   ========================= */
section[data-testid="stSidebar"] { border-right: 1px solid rgba(15,23,42,0.08); }

section[data-testid="stSidebar"] > div,
div[data-testid="stSidebar"] > div {
  background: rgba(255,255,255,0.92) !important;
  backdrop-filter: blur(8px);
}

section[data-testid="stSidebar"] *,
div[data-testid="stSidebar"] * {
  color: #0f172a !important;
}

/* =========================
   INPUTS / SELECT / DATE: blanco + texto negro (GLOBAL)
   ========================= */
div[data-baseweb="base-input"],
div[data-baseweb="input"],
div[data-baseweb="select"],
div[data-baseweb="datepicker"],
textarea {
  background: #ffffff !important;
  background-color: #ffffff !important;
  color: #0f172a !important;
  border-color: #e2e8f0 !important;
}

div[data-baseweb="base-input"] input,
div[data-baseweb="input"] input,
div[data-baseweb="select"] input,
div[data-baseweb="datepicker"] input,
textarea {
  background: transparent !important;
  color: #0f172a !important;
  -webkit-text-fill-color: #0f172a !important;
}

/* Dropdowns (popover/menu) */
div[data-baseweb="popover"],
div[data-baseweb="popover"] *,
div[data-baseweb="menu"],
div[data-baseweb="menu"] * {
  background: #ffffff !important;
  color: #0f172a !important;
}

/* =========================
   LOGIN: fondo violeta + card (se activa SOLO si existe #fc-login-marker)
   (con :has + fallback por overlay)
   ========================= */

/* Fallback: overlay violeta detrás (funciona aunque :has falle) */
#fc-login-marker {
  position: fixed;
  inset: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
  z-index: 0;
  pointer-events: none;
}
div[data-testid="stAppViewContainer"] > .main {
  position: relative;
  z-index: 1;
}

/* Si el navegador soporta :has, afinamos TODO el login */
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) header[data-testid="stHeader"] {
  visibility: hidden !important;
}

div[data-testid="stAppViewContainer"]:has(#fc-login-marker) .block-container {
  padding-top: 2rem !important;
  padding-bottom: 1rem !important;
}

div[data-testid="stAppViewContainer"]:has(#fc-login-marker) [data-testid="stForm"] {
  background: rgba(255, 255, 255, 0.95) !important;
  border-radius: 24px !important;
  padding: 32px 36px !important;
  border: none !important;
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15) !important;
  backdrop-filter: blur(10px) !important;
}

/* Tabs login */
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) [data-baseweb="tab-list"] {
  background: #f1f5f9 !important;
  border-radius: 12px !important;
  padding: 4px !important;
  gap: 4px !important;
}
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) button[data-baseweb="tab"] {
  color: #64748b !important;
  font-weight: 600 !important;
  border-radius: 10px !important;
  padding: 10px 20px !important;
  background: transparent !important;
}
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) button[data-baseweb="tab"][aria-selected="true"] {
  color: #667eea !important;
  background: white !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
}

/* Inputs login (incluye botón ojo) */
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) div[data-baseweb="base-input"],
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) div[data-baseweb="input"] {
  background: #f8fafc !important;
  border: 2px solid #e2e8f0 !important;
  border-radius: 12px !important;
  box-shadow: none !important;
  overflow: hidden !important;
}
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) div[data-baseweb="base-input"] input,
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) div[data-baseweb="input"] input {
  border: none !important;
  outline: none !important;
  background: transparent !important;
  color: #1e293b !important;
  -webkit-text-fill-color: #1e293b !important;
  padding: 12px 16px !important;
  font-size: 16px !important;
}
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) div[data-baseweb="base-input"] button,
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) div[data-baseweb="input"] button {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  color: #475569 !important;
  padding-right: 10px !important;
}

/* Botón login */
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) .stForm button[kind="secondaryFormSubmit"],
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) .stForm button[type="submit"] {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
  color: white !important;
  border-radius: 12px !important;
  font-weight: 700 !important;
  font-size: 16px !important;
  padding: 14px 28px !important;
  border: none !important;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4) !important;
  text-transform: none !important;
}

/* Responsive login */
@media (max-width: 768px) {
  div[data-testid="stAppViewContainer"]:has(#fc-login-marker) [data-testid="stForm"] {
    padding: 24px 20px !important;
    border-radius: 20px !important;
  }
  div[data-testid="stAppViewContainer"]:has(#fc-login-marker) .block-container {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
    padding-bottom: 4rem !important;
  }
/* ========================================================= */
/* 🔒 FORZAR LIGHT MODE – ignorar dark mode del sistema */
/* ========================================================= */

:root {
  color-scheme: light !important;
}

html, body {
  background-color: #f6f4ef !important;
  color: #0f172a !important;
}

/* Anula prefers-color-scheme: dark del navegador */
@media (prefers-color-scheme: dark) {
  html, body,
  [data-testid="stAppViewContainer"],
  [data-testid="stSidebar"],
  section[data-testid="stSidebar"] > div,
  .block-container,
  input, textarea, select, button {
    background-color: #ffffff !important;
    color: #0f172a !important;
  }
}
@media (max-width: 480px) {
  div[data-testid="stAppViewContainer"]:has(#fc-login-marker) [data-testid="stForm"] {
    padding: 22px 18px !important;
  }
}

/* Mover FertiChat y campana al toolbar */
.stAppToolbar {
  position: relative;
  min-height: 40px;
}
.stAppToolbar::before {
  content: "FertiChat 🔔";
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
  background: rgba(255, 255, 255, 0.95);
  padding: 4px 8px;
  border-radius: 6px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

/* Ocultar header de escritorio siempre */
.header-desktop-wrapper {
  display: none !important;
}

</style>
"""

# Función para hash de contraseña (simple demo)
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Usuarios demo (en producción, usa DB)
USERS = {
    "admin": hash_password("123"),
    "user": hash_password("456")
}

# Aplicar CSS
st.markdown(CSS_GLOBAL, unsafe_allow_html=True)

# Estado de login
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    # Pantalla de login
    st.markdown('<div id="fc-login-marker"></div>', unsafe_allow_html=True)
    
    with st.form("login_form"):
        st.title("🔐 Iniciar Sesión")
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        
        # Usa selectbox en lugar de tabs (no funciona en form)
        tab = st.selectbox("Tipo", ["Login", "Registro"])
        
        submitted = st.form_submit_button("Entrar")
        if submitted:
            if tab == "Login" and username in USERS and USERS[username] == hash_password(password):
                st.session_state.logged_in = True
                st.success("Login exitoso!")
                st.rerun()
            elif tab == "Registro":
                st.info("Registro demo - usuario agregado.")
                USERS[username] = hash_password(password)
                st.success("Registrado!")
            else:
                st.error("Usuario o contraseña incorrectos.")
else:
    # Panel corporativo después de login
    st.title("🏢 Panel Corporativo - Bienvenido!")
    
    # Sidebar
    with st.sidebar:
        st.title("📊 Panel Corporativo")
        st.markdown("---")
        
        menu = st.radio("Menú Principal", ["Inicio", "Compras IA", "Buscador IA", "Stock IA", "Dashboard", "Configuración"])
        
        st.markdown("---")
        st.subheader("Herramientas")
        if st.button("📈 Reportes"):
            st.info("Generando reporte...")
        if st.button("📧 Notificaciones"):
            st.info("Enviando notificación...")
        
        st.markdown("---")
        if st.button("Cerrar Sesión"):
            st.session_state.logged_in = False
            st.rerun()
        st.caption("Versión 1.0 | Empresa XYZ")
    
    # Contenido según menú
    if menu == "Inicio":
        st.markdown("Bienvenido al dashboard.")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Ventas", "1.2M", "+10%")
        with col2:
            st.metric("Clientes", "5.4K", "+5%")
        with col3:
            st.metric("Pedidos", "892", "+12%")
    elif menu == "Compras IA":
        st.write("Análisis de compras.")
    # Agrega más
    
    st.markdown("---")
    st.caption("© 2023 Empresa XYZ")
