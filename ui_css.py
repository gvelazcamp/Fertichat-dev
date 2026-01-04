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

/* =========================================================
   DESKTOP
   ========================================================= */
@media (hover: hover) and (pointer: fine) {
  div[data-testid="stToolbarActions"],
  div[data-testid="collapsedControl"] {
    display: none !important;
  }
}

/* =========================================================
   MÓVIL
   ========================================================= */
@media (hover: none) and (pointer: coarse) {
  .block-container { padding-top: 70px !important; }

  section[data-testid="stSidebar"] > div {
    background: #ffffff !important;
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

/* Título */
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

/* Fondo general */
.stApp {
  background: linear-gradient(135deg, #f6f4ef, #f3f6fb) !important;
}

</style>
"""
