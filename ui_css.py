# =========================
# UI_CSS.PY - CSS GLOBAL (APP + LOGIN)
# =========================

CSS_GLOBAL = r"""
<style>
/* =========================
   OCULTAR ELEMENTOS (suave)
   ========================= */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
div[data-testid="stDecoration"] { display: none !important; }

/* =========================================================
   OCULTAR: ancla/link al lado del H1 (el iconito de enlace)
   Ej: <span data-testid="stHeaderActionElements">...</span>
   PC + CEL
   ========================================================= */
[data-testid="stHeaderActionElements"] {
  display: none !important;
}

/* Por si Streamlit cambia el atributo y queda como clase */
h1 > span.eqpbrs03,
h2 > span.eqpbrs03,
h3 > span.eqpbrs03 {
  display: none !important;
}

/* =========================================================
   OCULTAR SOLO el H1 "Inicio" que te queda gigante
   (PC + CEL)
   ========================================================= */
h1#inicio {
  display: none !important;
}

/* =========================================================
   OCULTAR: <div class="logo">🦋 FertiChat</div>
   (tu header mobile custom)
   PC + CEL
   ========================================================= */
#mobile-header .logo,
div#mobile-header .logo {
  display: none !important;
}

/* Si la clase "logo" existe en otros lados, NO la matamos global.
   Solo dentro de #mobile-header. */

/* =========================================================
   OCULTAR: campana mobile <a id="campana-mobile">🔔</a>
   PC + CEL
   ========================================================= */
#campana-mobile {
  display: none !important;
}

/* =========================
   FORZAR MODO CLARO GLOBAL
   ========================= */
html, body {
  color-scheme: light !important;
  background: #f6f4ef !important;
}

:root {
  --fc-bg-1: #f6f4ef;
  --fc-bg-2: #f3f6fb;
  --fc-text: #0f172a;
  --fc-primary: #0b3b60;
}

/* Fondo general APP */
html, body,
.stApp,
div[data-testid="stApp"],
div[data-testid="stAppViewContainer"],
div[data-testid="stAppViewContainer"] > .main,
div[data-testid="stAppViewContainer"] > .main > div {
  background: linear-gradient(135deg, var(--fc-bg-1), var(--fc-bg-2)) !important;
  color: var(--fc-text) !important;
}

/* Tipografía */
html, body {
  font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  color: var(--fc-text) !important;
}

.block-container {
  max-width: 1240px;
  padding-top: 1.25rem;
  padding-bottom: 2.25rem;
}

/* =========================
   SIDEBAR (blanco + texto negro)
   ========================= */
section[data-testid="stSidebar"] { border-right: 1px solid rgba(15,23,42,0.08); }

section[data-testid="stSidebar"] > div,
div[data-testid="stSidebar"] > div {
  background: rgba(255,255,255,0.92) !important;
}

section[data-testid="stSidebar"],
section[data-testid="stSidebar"] *,
div[data-testid="stSidebar"],
div[data-testid="stSidebar"] * {
  color: var(--fc-text) !important;
}

/* =========================
   INPUTS / SELECT / DATE: SIEMPRE BLANCO + TEXTO NEGRO
   ========================= */
div[data-baseweb="select"] div[role="button"],
div[data-baseweb="select"] div[role="combobox"],
div[data-baseweb="select"] input,
div[data-baseweb="datepicker"] input,
div[data-baseweb="input"] input,
div[data-baseweb="base-input"] input,
textarea {
  background: #ffffff !important;
  background-color: #ffffff !important;
  color: var(--fc-text) !important;
  -webkit-text-fill-color: var(--fc-text) !important;
}

div[data-baseweb="select"],
div[data-baseweb="datepicker"],
div[data-baseweb="input"],
div[data-baseweb="base-input"],
textarea {
  border-color: #e2e8f0 !important;
}

/* Menús desplegables (popover) */
div[data-baseweb="popover"],
div[data-baseweb="popover"] *,
div[data-baseweb="menu"],
div[data-baseweb="menu"] * {
  background: #ffffff !important;
  color: var(--fc-text) !important;
}

/* =========================
   PC: ocultar toolbar/share (SOLO PC)
   IMPORTANTE: NO lo hacemos en mobile
   ========================= */
@media (hover: hover) and (pointer: fine) and (min-width: 901px) {
  [data-testid="stToolbar"] { display: none !important; }
  [data-testid="stToolbarActions"] { display: none !important; }

  /* Si en PC querés ocultar los controles de colapsar/expandir */
  div[data-testid="collapsedControl"] { display: none !important; }
  button[data-testid="stSidebarCollapseButton"],
  button[data-testid="stSidebarExpandButton"],
  button[title="Close sidebar"],
  button[title="Open sidebar"] { display: none !important; }
}

/* =========================
   MOBILE / PANTALLA CHICA: aseguramos ☰ visible
   (aunque el teléfono “se haga pasar” por escritorio)
   ========================= */
@media (max-width: 900px) {
  div[data-testid="collapsedControl"],
  button[data-testid="stSidebarExpandButton"],
  button[title="Open sidebar"] {
    display: inline-flex !important;
  }
}

/* =========================
   LOGIN (VIOLETA) - solo cuando existe #fc-login-marker
   ========================= */

/* Ocultar header/toolbar en login (para que no aparezca campana/share) */
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) header[data-testid="stHeader"] {
  visibility: hidden !important;
}
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) [data-testid="stToolbar"],
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) [data-testid="stToolbarActions"] {
  display: none !important;
}
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) .stDeployButton {
  display: none !important;
}

/* Fondo violeta login */
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) .stApp {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%) !important;
  min-height: 100vh;
}

/* Padding login */
div[data-testid="stAppViewContainer"]:has(#fc-login-marker) .block-container {
  padding-top: 2rem !important;
  padding-bottom: 1rem !important;
}

/* Card del formulario */
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

/* Inputs login + botón ojo */
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
}

@media (max-width: 480px) {
  div[data-testid="stAppViewContainer"]:has(#fc-login-marker) [data-testid="stForm"] {
    padding: 22px 18px !important;
  }
}
</style>
"""


