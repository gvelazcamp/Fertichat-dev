# =========================
# UI_CSS.PY - CSS GLOBAL CORPORATIVO (BLANCO + CELESTE - VENDIBLE)
# =========================

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
  background-color: #ffffff !important;
}

/* Inputs, cards, contenedores */
* {
  background-color: inherit;
}

/* Anti "forced dark" de Chrome */
@media (prefers-color-scheme: dark) {
  html, body {
    background: #ffffff !important;
    color: #0f172a !important;
  }

  * {
    filter: none !important;
  }
}
html, body {
  background: #ffffff !important;
  color: #0f172a !important;
}

/* Si el sistema está dark, igual lo dejamos claro */
@media (prefers-color-scheme: dark) {
  :root, html, body, .stApp {
    color-scheme: light !important;
  }
  html, body {
    background: #ffffff !important;
    color: #0f172a !important;
  }
}

/* =========================
   Fondo principal APP (blanco + celeste suave)
   ========================= */
:root {
  --fc-bg-1: #ffffff;  /* Blanco puro */
  --fc-bg-2: #e0f2fe;  /* Celeste claro */
  --fc-text: #0f172a;  /* Negro oscuro para texto */
  --fc-accent: #0284c7;  /* Azul celeste corporativo */
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
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;  /* Fuente corporativa */
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
   SIDEBAR: blanco + texto negro + borde celeste
   ========================= */
section[data-testid="stSidebar"] { border-right: 1px solid var(--fc-accent); }

section[data-testid="stSidebar"] > div,
div[data-testid="stSidebar"] > div {
  background: rgba(255,255,255,0.98) !important;
  backdrop-filter: blur(8px);
}

section[data-testid="stSidebar"] *,
div[data-testid="stSidebar"] * {
  color: var(--fc-text) !important;
}

/* =========================
   INPUTS / SELECT / DATE: blanco + borde celeste + texto negro (GLOBAL)
   ========================= */
div[data-baseweb="base-input"],
div[data-baseweb="input"],
div[data-baseweb="select"],
div[data-baseweb="datepicker"],
textarea {
  background: #ffffff !important;
  background-color: #ffffff !important;
  color: var(--fc-text) !important;
  border-color: var(--fc-accent) !important;
  border-radius: 8px !important;
  box-shadow: 0 1px 3px rgba(2, 132, 199, 0.1) !important;
}

div[data-baseweb="base-input"] input,
div[data-baseweb="input"] input,
div[data-baseweb="select"] input,
div[data-baseweb="datepicker"] input,
textarea {
  background: transparent !important;
  color: var(--fc-text) !important;
  -webkit-text-fill-color: var(--fc-text) !important;
}

/* Dropdowns (popover/menu) */
div[data-baseweb="popover"],
div[data-baseweb="popover"] *,
div[data-baseweb="menu"],
div[data-baseweb="menu"] * {
  background: #ffffff !important;
  color: var(--fc-text) !important;
}

/* =========================
   BOTONES GENERALES: celeste + hover suave
   ========================= */
.stButton > button {
  background: linear-gradient(135deg, var(--fc-accent), #0ea5e9) !important;
  color: white !important;
  border-radius: 8px !important;
  border: none !important;
  box-shadow: 0 2px 4px rgba(2, 132, 199, 0.2) !important;
  transition: all 0.2s ease !important;
}

.stButton > button:hover {
  background: linear-gradient(135deg, #0ea5e9, var(--fc-accent)) !important;
  box-shadow: 0 4px 8px rgba(2, 132, 199, 0.3) !important;
  transform: translateY(-1px);
}

/* =========================
   LOGIN: fondo celeste gradiente + card blanca (se activa SOLO si existe #fc-login-marker)
   ========================= */

/* Fondo gradiente celeste */
#fc-login-marker {
  position: fixed;
  inset: 0;
  background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 50%, #7dd3fc 100%);
  z-index: 0;
  pointer-events: none;
}
div[data-testid="stAppViewContainer"] > .main {
  position: relative;
  z-index: 1;
}

/* Header login oculto */
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) header[data-testid="stHeader"] {
  visibility: hidden !important;
}

div[data-testid="stAppViewContainer"]:has(#fc-login-marker) .block-container {
  padding-top: 2rem !important;
  padding-bottom: 1rem !important;
}

div[data-testid="stAppViewContainer"]:has(#fc-login-marker) [data-testid="stForm"] {
  background: rgba(255, 255, 255, 0.98) !important;
  border-radius: 16px !important;
  padding: 32px 36px !important;
  border: 1px solid var(--fc-accent) !important;
  box-shadow: 0 10px 25px rgba(2, 132, 199, 0.15) !important;
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
  color: var(--fc-accent) !important;
  background: white !important;
  box-shadow: 0 2px 8px rgba(2, 132, 199, 0.1) !important;
}

/* Inputs login */
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) div[data-baseweb="base-input"],
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) div[data-baseweb="input"] {
  background: #f8fafc !important;
  border: 2px solid #bae6fd !important;
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
  background: linear-gradient(135deg, var(--fc-accent), #0ea5e9) !important;
  color: white !important;
  border-radius: 12px !important;
  font-weight: 700 !important;
  font-size: 16px !important;
  padding: 14px 28px !important;
  border: none !important;
  box-shadow: 0 4px 15px rgba(2, 132, 199, 0.4) !important;
  text-transform: none !important;
}

/* Responsive login */
@media (max-width: 768px) {
  div[data-testid="stAppViewContainer"]:has(#fc-login-marker) [data-testid="stForm"] {
    padding: 24px 20px !important;
    border-radius: 12px !important;
  }
  div[data-testid="stAppViewContainer"]:has(#fc-login-marker) .block-container {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
    padding-bottom: 4rem !important;
  }
}
@media (max-width: 480px) {
  div[data-testid="stAppViewContainer"]:has(#fc-login-marker) [data-testid="stForm"] {
    padding: 22px 18px !important;
  }
}

/* ========================================================= */
/* 🔒 FORZAR LIGHT MODE – ignorar dark mode del sistema */
/* ========================================================= */

:root {
  color-scheme: light !important;
}

html, body {
  background-color: #ffffff !important;
  color: var(--fc-text) !important;
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
    color: var(--fc-text) !important;
  }
}

/* =========================
   CARDS Y COMPONENTES EXTRA (vendible)
   ========================= */
.stCard {
  background: rgba(255, 255, 255, 0.9) !important;
  border: 1px solid #e0f2fe !important;
  border-radius: 12px !important;
  box-shadow: 0 4px 6px rgba(2, 132, 199, 0.1) !important;
}

/* Texto corporativo */
h1, h2, h3, h4, h5, h6 {
  color: var(--fc-text) !important;
  font-weight: 600 !important;
}

/* Enlaces en celeste */
a {
  color: var(--fc-accent) !important;
  text-decoration: none !important;
}

a:hover {
  color: #0ea5e9 !important;
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
  color: var(--fc-accent);
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
  background: rgba(255, 255, 255, 0.95);
  padding: 4px 8px;
  border-radius: 6px;
  box-shadow: 0 2px 4px rgba(2, 132, 199, 0.1);
}

/* Ocultar header de escritorio siempre */
.header-desktop-wrapper {
  display: none !important;
}

</style>
"""
