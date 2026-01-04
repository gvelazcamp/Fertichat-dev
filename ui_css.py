# =========================
# UI_CSS.PY - CSS GLOBAL (PC + MÓVIL)
# =========================

CSS_GLOBAL = r"""
<style>

/* Ocultar elementos */
#MainMenu, footer { display: none !important; }
div[data-testid="stDecoration"] { display: none !important; }

/* FORZAR MODO CLARO GLOBAL */
html, body {
  color-scheme: light !important;
  background: #f6f4ef !important;
}

/* Variables */
:root {
  --fc-bg-1: #f6f4ef;
  --fc-bg-2: #f3f6fb;
  --fc-primary: #0b3b60;
  --fc-accent: #f59e0b;

  --background-color: #f6f4ef;
  --secondary-background-color: #ffffff;
  --text-color: #0f172a;
}

/* Contenedores principales */
html, body,
.stApp,
div[data-testid="stApp"],
div[data-testid="stAppViewContainer"],
div[data-testid="stAppViewContainer"] > .main,
div[data-testid="stAppViewContainer"] > .main > div {
  background: linear-gradient(135deg, var(--fc-bg-1), var(--fc-bg-2)) !important;
  color: #0f172a !important;
}

html, body {
  font-family: Inter, system-ui, sans-serif;
  color: #0f172a;
}

.block-container {
  max-width: 1240px;
  padding-top: 1.25rem;
  padding-bottom: 2.25rem;
}

/* =========================================================
   SIDEBAR GLOBAL
   ========================================================= */
section[data-testid="stSidebar"] {
  border-right: 1px solid rgba(15, 23, 42, 0.08);
}

section[data-testid="stSidebar"] > div,
div[data-testid="stSidebar"] > div {
  background: rgba(255,255,255,0.92) !important;
  backdrop-filter: blur(8px);
}

section[data-testid="stSidebar"],
section[data-testid="stSidebar"] *,
div[data-testid="stSidebar"],
div[data-testid="stSidebar"] * {
  color: #0f172a !important;
}

/* Radio menu */
div[data-testid="stSidebar"] div[role="radiogroup"] label {
  border-radius: 12px;
  padding: 8px 10px;
  margin: 3px 0;
  border: 1px solid transparent;
}

div[data-testid="stSidebar"] div[role="radiogroup"] label * {
  color: #0f172a !important;
}

div[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
  background: rgba(37,99,235,0.06);
}

div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
  background: rgba(245,158,11,0.10);
  border: 1px solid rgba(245,158,11,0.18);
}

/* Ocultar headers custom por defecto */
#mobile-header,
#campana-mobile {
  display: none;
}

/* =========================================================
   DESKTOP (no tocar look PC)
   ========================================================= */
@media (hover: hover) and (pointer: fine) {

  [data-testid="stHeader"],
  .stAppHeader,
  [data-testid="stToolbar"] {
    background: var(--fc-bg-1) !important;
  }

  div[data-testid="stToolbarActions"],
  div[data-testid="collapsedControl"],
  [data-testid="baseButton-header"],
  button[data-testid="stSidebarCollapseButton"],
  button[data-testid="stSidebarExpandButton"],
  button[title="Close sidebar"],
  button[title="Open sidebar"] {
    display: none !important;
  }
}

/* =========================================================
   FORZAR CLARO AUNQUE EL SISTEMA SEA DARK
   ========================================================= */
@media (prefers-color-scheme: dark) {

  html, body { color-scheme: light !important; }

  html, body,
  .stApp,
  div[data-testid="stApp"],
  div[data-testid="stAppViewContainer"],
  div[data-testid="stAppViewContainer"] > .main,
  div[data-testid="stAppViewContainer"] > .main > div {
    background: linear-gradient(135deg, var(--fc-bg-1), var(--fc-bg-2)) !important;
    color: #0f172a !important;
  }

  section[data-testid="stSidebar"] > div,
  div[data-testid="stSidebar"] > div {
    background: rgba(255,255,255,0.95) !important;
    backdrop-filter: blur(8px) !important;
  }

  section[data-testid="stSidebar"] *,
  div[data-testid="stSidebar"] * {
    color: #0f172a !important;
  }
}

/* =========================================================
   MÓVIL (touch)
   ========================================================= */
@media (hover: none) and (pointer: coarse) {

  .block-container { padding-top: 70px !important; }

  section[data-testid="stSidebar"] > div,
  div[data-testid="stSidebar"] > div {
    background: #ffffff !important;
    backdrop-filter: none !important;
  }

  section[data-testid="stSidebar"] *,
  div[data-testid="stSidebar"] * {
    color: #0f172a !important;
  }

  div[data-testid="collapsedControl"],
  button[data-testid="stSidebarExpandButton"],
  button[title="Open sidebar"] {
    display: inline-flex !important;
    position: fixed !important;
    top: 12px !important;
    left: 12px !important;
    z-index: 1000000 !important;
  }

  /* BaseWeb inputs */
  div[data-baseweb="select"],
  div[data-baseweb="select"] *,
  div[data-baseweb="input"],
  div[data-baseweb="base-input"],
  div[data-baseweb="datepicker"],
  textarea {
    background: #ffffff !important;
    color: #0f172a !important;
    border-color: #e2e8f0 !important;
  }
}

/* =========================================================
   LOGIN - TARJETA CENTRAL
   ========================================================= */

div[data-testid="stForm"] {
  background: #ffffff !important;
  border-radius: 22px !important;
  padding: 32px 36px !important;
  box-shadow: 0 20px 45px rgba(15, 23, 42, 0.12) !important;
  border: 1px solid rgba(15, 23, 42, 0.08) !important;
}

/* Título (FertiChat) */
.block-container h1 {
  color: #0b3b60 !important;
  font-weight: 800 !important;
}

/* Inputs */
div[data-baseweb="input"],
div[data-baseweb="base-input"] {
  background: #ffffff !important;
  border: 1px solid #e2e8f0 !important;
  border-radius: 12px !important;
}

/* Texto dentro del input */
div[data-baseweb="input"] input,
div[data-baseweb="base-input"] input {
  color: #0f172a !important;
  background: transparent !important;
}

/* Botón principal */
button[kind="secondaryFormSubmit"],
button[type="submit"] {
  background: #0b3b60 !important;
  color: #ffffff !important;
  border-radius: 12px !important;
  font-weight: 700 !important;
}

/* Fondo general (login + app) */
.stApp {
  background: linear-gradient(135deg, #f6f4ef, #f3f6fb) !important;
}


