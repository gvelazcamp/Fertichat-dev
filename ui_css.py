# =========================
# UI_CSS.PY - CSS GLOBAL
# =========================

CSS_GLOBAL = r"""
<style>

/* ===== RESET BÁSICO ===== */
#MainMenu, footer {
  display: none !important;
}

/* ===== FORZAR MODO CLARO ===== */
html, body {
  color-scheme: light !important;
  background: #f6f4ef !important;
  font-family: Inter, system-ui, sans-serif;
}

/* ===== CONTENEDOR PRINCIPAL ===== */
.stApp,
div[data-testid="stApp"],
div[data-testid="stAppViewContainer"],
div[data-testid="stAppViewContainer"] > .main {
  background: linear-gradient(135deg, #f6f4ef, #f3f6fb) !important;
  color: #0f172a !important;
}

/* ===== LOGIN - TARJETA ===== */
div[data-testid="stForm"] {
  background: #ffffff !important;
  border-radius: 22px !important;
  padding: 32px 36px !important;
  box-shadow: 0 20px 45px rgba(15,23,42,0.15) !important;
  border: 1px solid rgba(15,23,42,0.08) !important;
}

/* ===== INPUTS ===== */
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

/* ===== BOTÓN ===== */
button[type="submit"] {
  background: #0b3b60 !important;
  color: #ffffff !important;
  border-radius: 12px !important;
  font-weight: 700 !important;
}

</style>
"""
