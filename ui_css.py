# =========================
# UI_CSS.PY - CSS GLOBAL (APP + LOGIN + SIDEBAR CLARO CORPORATIVO + TABLAS RESPONSIVAS PARA MÓVIL)
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
} /* <-- CIERRE CORRECTO del @media 768 del login */

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

/* =========================
   VARIABLES SIDEBAR CORPORATIVO CLARO
   ========================= */
:root{
  --fc-sb-bg1:#ffffff;          /* blanco puro */
  --fc-sb-bg2:#f8fafc;          /* gris muy claro */
  --fc-sb-border:rgba(15,23,42,0.08);
  --fc-sb-text:#0f172a;         /* negro */
  --fc-sb-text-dim:#64748b;     /* gris medio */
  --fc-sb-active:#e0f2fe;       /* azul celeste claro */
  --fc-sb-hover:#f1f5f9;        /* gris hover */
  --fc-sb-chip:rgba(15,23,42,0.05);
  --fc-sb-shadow:0 10px 25px rgba(0,0,0,0.08);
  --fc-sb-radius:16px;
}

/* =========================
   CONTENEDOR SIDEBAR CLARO
   ========================= */
section[data-testid="stSidebar"]{
  background: linear-gradient(180deg, var(--fc-sb-bg1) 0%, var(--fc-sb-bg2) 100%) !important;
  border-right: 1px solid var(--fc-sb-border) !important;
}

/* Padding interno */
section[data-testid="stSidebar"] > div{
  padding: 14px 12px 12px 12px !important;
}

/* =========================
   CABECERA (logo + título)
   ========================= */
.fc-sb-header{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:10px;
  padding: 10px 10px 14px 10px;
  margin: 4px 6px 10px 6px;
  border-bottom: 1px solid var(--fc-sb-border);
}
.fc-sb-brand{
  display:flex;
  align-items:center;
  gap:10px;
}
.fc-sb-logo{
  width:34px;height:34px;
  border-radius:10px;
  background: linear-gradient(135deg, #22c55e 0%, #60a5fa 55%, #1d4ed8 100%);
  box-shadow: 0 8px 16px rgba(34, 197, 94, 0.2);
}
.fc-sb-title{
  color: var(--fc-sb-text);
  font-weight: 800;
  font-size: 20px;
  letter-spacing: .6px;
  margin:0;
}
.fc-sb-menuicon{
  width:34px;height:34px;
  border-radius:12px;
  background: var(--fc-sb-chip);
  border: 1px solid var(--fc-sb-border);
  display:flex;
  align-items:center;
  justify-content:center;
  color: var(--fc-sb-text);
}

/* =========================
   BUSCADOR (input)
   ========================= */
section[data-testid="stSidebar"] input{
  background: var(--fc-sb-chip) !important;
  color: var(--fc-sb-text) !important;
  border: 1px solid var(--fc-sb-border) !important;
  border-radius: 14px !important;
}
section[data-testid="stSidebar"] input::placeholder{
  color: var(--fc-sb-text-dim) !important;
}
section[data-testid="stSidebar"] div[data-baseweb="input"]{
  background: transparent !important;
}

/* =========================
   RADIO/MENÚ (estilo “lista”)
   ========================= */

/* Quitar caja blanca del widget */
section[data-testid="stSidebar"] div[role="radiogroup"]{
  background: transparent !important;
  padding: 4px 4px 2px 4px !important;
}

/* Cada opción como “fila” */
section[data-testid="stSidebar"] div[role="radiogroup"] > div{
  border-radius: 14px !important;
  transition: background .15s ease, transform .12s ease;
}

/* Hover */
section[data-testid="stSidebar"] div[role="radiogroup"] > div:hover{
  background: var(--fc-sb-hover) !important;
  transform: translateY(-1px);
}

/* Texto de cada opción */
section[data-testid="stSidebar"] div[role="radiogroup"] label{
  color: var(--fc-sb-text) !important;
  font-weight: 600 !important;
}

/* Subtexto/ayudas si aparecen */
section[data-testid="stSidebar"] div[role="radiogroup"] span{
  color: var(--fc-sb-text) !important;
}

/* “Check”/círculo del radio */
section[data-testid="stSidebar"] input[type="radio"]{
  accent-color: #0ea5e9 !important;
}

/* Opción seleccionada */
section[data-testid="stSidebar"] div[role="radiogroup"] > div:has([aria-checked="true"]),
section[data-testid="stSidebar"] div[role="radiogroup"] > div:has(input[type="radio"]:checked){
  background: var(--fc-sb-active) !important;
  border: 1px solid rgba(14, 165, 233, 0.2) !important;
}

/* Padding de opciones */
section[data-testid="stSidebar"] div[role="radiogroup"] > div label{
  padding: 10px 10px !important;
}

/* =========================
   FOOTER PERFIL
   ========================= */
.fc-sb-user{
  position: sticky;
  bottom: 10px;
  margin: 14px 6px 4px 6px;
  padding: 12px 12px;
  border-radius: var(--fc-sb-radius);
  background: var(--fc-sb-chip);
  border: 1px solid var(--fc-sb-border);
  box-shadow: var(--fc-sb-shadow);
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
}
.fc-sb-user-left{
  display:flex;
  align-items:center;
  gap:10px;
}
.fc-sb-avatar{
  width:42px;height:42px;
  border-radius: 999px;
  background: var(--fc-sb-chip);
  border: 1px solid var(--fc-sb-border);
}
.fc-sb-user-name{
  color: var(--fc-sb-text);
  font-weight: 800;
  font-size: 14px;
  line-height: 1.1;
  margin:0;
}
.fc-sb-user-mail{
  color: var(--fc-sb-text-dim);
  font-weight: 600;
  font-size: 12px;
  margin:2px 0 0 0;
}
.fc-sb-gear{
  width:40px;height:40px;
  border-radius: 14px;
  background: var(--fc-sb-chip);
  border: 1px solid var(--fc-sb-border);
  display:flex;
  align-items:center;
  justify-content:center;
  color: var(--fc-sb-text);
}

/* =========================================================
   RESPONSIVE GENERAL (APP) - PARA QUE SE VEA BIEN EN CELULAR
   ========================================================= */
@media (max-width: 768px) {

  /* Evitar scroll horizontal */
  html, body, .stApp, [data-testid="stAppViewContainer"] {
    overflow-x: hidden !important;
  }

  /* Contenedor principal: padding real de móvil */
  .block-container {
    padding-left: 0.85rem !important;
    padding-right: 0.85rem !important;
    padding-top: 1rem !important;
    padding-bottom: 4rem !important;
    max-width: 100% !important;
  }

  /* Tabs más compactas */
  button[data-baseweb="tab"] {
    font-size: 0.85rem !important;
    padding: 6px 8px !important;
  }

  /* Métricas más chicas */
  [data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    line-height: 1.1 !important;
  }
  [data-testid="stMetricLabel"] {
    font-size: 0.9rem !important;
  }

  /* Tablas/DataFrame: RESPONSIVAS PARA MÓVIL (SIN GIRAR EL CELULAR) */
  .stDataFrame, .stTable {
    overflow-x: auto !important;  /* Scroll horizontal interno */
    -webkit-overflow-scrolling: touch !important;  /* Smooth en iOS */
    width: 100% !important;
    max-width: 100% !important;
  }
  .stDataFrame table, .stTable table {
    min-width: 100% !important;  /* Evita que se comprima demasiado */
    font-size: 0.85rem !important;  /* Fuente más pequeña en móvil */
    width: auto !important;  /* Deja que la tabla se expanda si es necesario */
  }
  .stDataFrame th, .stDataFrame td, .stTable th, .stTable td {
    padding: 8px 6px !important;  /* Padding reducido */
    white-space: nowrap !important;  /* Evita wrap de texto */
    text-align: left !important;
  }
  .stDataFrame th, .stTable th {
    font-weight: 700 !important;
    background: rgba(15,23,42,0.05) !important;
    border-bottom: 2px solid rgba(15,23,42,0.1) !important;
  }

  /* Toolbar: evitar que el título “empuje” */
  .stAppToolbar::before {
    font-size: 15px !important;
    padding: 3px 6px !important;
  }
}

@media (max-width: 480px) {
  .block-container {
    padding-left: 0.75rem !important;
    padding-right: 0.75rem !important;
  }
  [data-testid="stMetricValue"] {
    font-size: 1.45rem !important;
  }
  button[data-baseweb="tab"] {
    font-size: 0.82rem !important;
    padding: 6px 7px !important;
  }

  /* Tablas aún más compactas en pantallas muy pequeñas */
  .stDataFrame table, .stTable table {
    font-size: 0.8rem !important;
  }
  .stDataFrame th, .stDataFrame td, .stTable th, .stTable td {
    padding: 6px 4px !important;
  }
}

</style>
"""  
