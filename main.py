# =========================
# MAIN.PY - MENÚ HAMBURGUESA ARRIBA (ESTILO GNS+)
# =========================

import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="FertiChat",
    page_icon="🦋",
    layout="wide",
    initial_sidebar_state="expanded"  # Solo para PC
)

# =========================
# IMPORTS
# =========================
from config import MENU_OPTIONS, DEBUG_MODE
from auth import init_db
from login_page import require_auth, get_current_user, logout
from pedidos import mostrar_pedidos_internos, contar_notificaciones_no_leidas
from bajastock import mostrar_baja_stock
from ordenes_compra import mostrar_ordenes_compra
from ui_compras import Compras_IA
from ui_buscador import mostrar_buscador_ia
from ui_stock import mostrar_stock_ia, mostrar_resumen_stock_rotativo
from ui_dashboard import mostrar_dashboard, mostrar_indicadores_ia, mostrar_resumen_compras_rotativo
from ingreso_comprobantes import mostrar_ingreso_comprobantes
from ui_inicio import mostrar_inicio
from ficha_stock import mostrar_ficha_stock
from articulos import mostrar_articulos
from depositos import mostrar_depositos
from familias import mostrar_familias


# =========================
# CSS (IGUAL AL ORIGINAL, SIN OCULTAR SIDEBAR EN MÓVIL)
# =========================
def inject_css():
    st.markdown(
        """
        <style>
        /* Ocultar elementos de Streamlit */
        div.stAppToolbar,
        div[data-testid="stToolbar"],
        div[data-testid="stToolbarActions"],
        div[data-testid="stDecoration"],
        #MainMenu,
        footer{
          display: none !important;
        }

        header[data-testid="stHeader"]{
          height: 0 !important;
          background: transparent !important;
        }

        /* Theme */
        :root{
            --fc-bg-1: #f6f4ef;
            --fc-bg-2: #f3f6fb;
            --fc-primary: #0b3b60;
            --fc-accent: #f59e0b;
        }

        html, body{
            font-family: Inter, system-ui, sans-serif;
            color: #0f172a;
        }

        [data-testid="stAppViewContainer"]{
            background: linear-gradient(135deg, var(--fc-bg-1), var(--fc-bg-2));
        }

        .block-container{
            max-width: 1240px;
            padding-top: 1.25rem;
            padding-bottom: 2.25rem;
        }

        /* Sidebar PC y MÓVIL (ya no se oculta en móvil) */
        section[data-testid="stSidebar"]{
            border-right: 1px solid rgba(15, 23, 42, 0.08);
        }
        section[data-testid="stSidebar"] > div{
            background: rgba(255,255,255,0.70);
            backdrop-filter: blur(8px);
        }

        div[data-testid="stSidebar"] div[role="radiogroup"] label{
            border-radius: 12px;
            padding: 8px 10px;
            margin: 3px 0;
            border: 1px solid transparent;
        }
        div[data-testid="stSidebar"] div[role="radiogroup"] label:hover{
            background: rgba(37,99,235,0.06);
        }
        div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){
            background: rgba(245,158,11,0.10);
            border: 1px solid rgba(245,158,11,0.18);
        }

        /* =========================
   HEADER / SIDEBAR FIX MOBILE
   ========================= */

/* PC: ocultar header */
@media (min-width: 769px){
  header[data-testid="stHeader"],
  div[data-testid="stToolbar"],
  div.stAppToolbar{
    display: none !important;
  }
}

/* CELULAR: header VISIBLE (CLAVE) */
@media (max-width: 768px){
  header[data-testid="stHeader"]{
    display: block !important;
    height: auto !important;
    background: transparent !important;
  }

  /* Botón hamburguesa */
  button[data-testid="stExpandSidebarButton"]{
    display: inline-flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    z-index: 999999 !important;
  }
}

        </style>
        """,
        unsafe_allow_html=True
    )


# =========================
# INICIALIZACIÓN
# =========================
inject_css()
init_db()
require_auth()

user = get_current_user() or {}

# Inicializar menú
if "radio_menu" not in st.session_state:
    st.session_state["radio_menu"] = "🏠 Inicio"

# Manejar navegación desde tarjetas de inicio (query params)
try:
    menu_param = st.query_params.get("menu")
    if menu_param and menu_param in MENU_OPTIONS:
        st.session_state["radio_menu"] = menu_param
        st.query_params.clear()
        st.rerun()
    
    if st.query_params.get("logout") == "1":
        logout()
        st.query_params.clear()
        st.rerun()
except:
    pass

# =========================
# TÍTULO Y CAMPANITA
# =========================
usuario_actual = user.get("usuario", user.get("email", ""))
cant_pendientes = 0
if usuario_actual:
    cant_pendientes = contar_notificaciones_no_leidas(usuario_actual)

col_logo, col_spacer, col_notif = st.columns([7, 2, 1])

with col_logo:
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 12px;">
            <div>
                <h1 style="margin: 0; font-size: 38px; font-weight: 900; color: #0f172a;">
                    FertiChat
                </h1>
                <p style="margin: 4px 0 0 0; font-size: 15px; color: #64748b;">
                    Sistema de Gestión de Compras
                </p>
            </div>
        </div>
    """, unsafe_allow_html=True)

with col_notif:
    if cant_pendientes > 0:
        if st.button(f"🔔 {cant_pendientes}", key="campanita_global"):
            st.session_state["radio_menu"] = "📄 Pedidos internos"
            st.rerun()
    else:
        st.markdown("<div style='text-align:right; font-size:26px;'>🔔</div>", unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)


# =========================
# SIDEBAR (PC Y MÓVIL - AHORA FUNCIONA EN AMBOS)
# =========================
with st.sidebar:
    st.markdown(f"""
        <div style='
            background: rgba(255,255,255,0.85);
            padding: 16px;
            border-radius: 18px;
            margin-bottom: 14px;
            border: 1px solid rgba(15, 23, 42, 0.10);
            box-shadow: 0 10px 26px rgba(2, 6, 23, 0.06);
        '>
            <div style='display:flex; align-items:center; gap:10px; justify-content:center;'>
                <div style='font-size: 26px;'>🦋</div>
                <div style='font-size: 20px; font-weight: 800; color:#0f172a;'>FertiChat</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.text_input("Buscar...", key="sidebar_search", label_visibility="collapsed", placeholder="Buscar...")

    st.markdown(f"👤 **{user.get('nombre', 'Usuario')}**")
    if user.get('empresa'):
        st.markdown(f"🏢 {user.get('empresa')}")
    st.markdown(f"📧 _{user.get('Usuario', '')}_")

    st.markdown("---")

    if st.button("🚪 Cerrar sesión", key="btn_logout_sidebar", use_container_width=True):
        logout()
        st.rerun()

    st.markdown("---")
    st.markdown("## 📌 Menú")

    menu = st.radio("Ir a:", MENU_OPTIONS, key="radio_menu")


# =========================
# ROUTER
# =========================
menu_actual = st.session_state["radio_menu"]

if menu_actual == "🏠 Inicio":
    mostrar_inicio()
elif menu_actual == "🛒 Compras IA":
    mostrar_resumen_compras_rotativo()
    Compras_IA()
elif menu_actual == "📦 Stock IA":
    mostrar_resumen_stock_rotativo()
    mostrar_stock_ia()
elif menu_actual == "🔎 Buscador IA":
    mostrar_buscador_ia()
elif menu_actual == "📥 Ingreso de comprobantes":
    mostrar_ingreso_comprobantes()
elif menu_actual == "📊 Dashboard":
    mostrar_dashboard()
elif menu_actual == "📄 Pedidos internos":
    mostrar_pedidos_internos()
elif menu_actual == "🧾 Baja de stock":
    mostrar_baja_stock()
elif menu_actual == "📈 Indicadores (Power BI)":
    mostrar_indicadores_ia()
elif menu_actual == "📦 Órdenes de compra":
    mostrar_ordenes_compra()
elif menu_actual == "📒 Ficha de stock":
    mostrar_ficha_stock()
elif menu_actual == "📚 Artículos":
    mostrar_articulos()
elif menu_actual == "🏬 Depósitos":
    mostrar_depositos()
elif menu_actual == "🧩 Familias":
    mostrar_familias()
