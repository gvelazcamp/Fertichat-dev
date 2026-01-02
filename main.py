# =========================
# MAIN.PY - ORQUESTADOR PRINCIPAL (MINIMALISTA)
# =========================

import streamlit as st
from datetime import datetime

# =========================
# CONFIGURACIÓN STREAMLIT
# =========================
st.set_page_config(
    page_title="FertiChat",
    page_icon="🦋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# IMPORTS
# =========================
from config import MENU_OPTIONS, DEBUG_MODE

# Autenticación (ya existen)
from auth import init_db
from login_page import (
    require_auth,
    show_user_info_sidebar,
    get_current_user,
    logout,
    LOGIN_CSS
)

# Módulos externos (ya existen)
from pedidos import mostrar_pedidos_internos, contar_notificaciones_no_leidas
from bajastock import mostrar_baja_stock
from ordenes_compra import mostrar_ordenes_compra
from supabase_client import supabase

# Módulos nuevos
from ui_compras import Compras_IA, render_orquestador_output
from orquestador import procesar_pregunta_router
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
# CSS RESPONSIVE + TEMA CORPORATIVO
# =========================
def inject_css_responsive():
    st.markdown(
        """
        <style>
        /* =========================
           OCULTAR BARRA SUPERIOR STREAMLIT (Share / menú / icons / barra blanca)
           (NO ocultamos el botón de sidebar en mobile; lo estilizamos)
        ========================= */
        div.stAppToolbar,
        div[data-testid="stToolbar"],
        div[data-testid="stToolbarActions"],
        header,
        header[data-testid="stHeader"],
        div[data-testid="stDecoration"],
        #MainMenu,
        footer{
          display: none !important;
          height: 0 !important;
          min-height: 0 !important;
          padding: 0 !important;
          margin: 0 !important;
        }

        /* =========================
           THEME (look & feel tipo mockup)
        ========================= */
        :root{
            --fc-bg-1: #f6f4ef;
            --fc-bg-2: #f3f6fb;
            --fc-surface: #ffffff;
            --fc-border: rgba(15, 23, 42, 0.10);
            --fc-text: #0f172a;
            --fc-muted: #64748b;
            --fc-primary: #0b3b60;
            --fc-primary-2: #2563eb;
            --fc-accent: #f59e0b;
            --fc-radius: 18px;
            --fc-radius-sm: 12px;
            --fc-shadow: 0 14px 40px rgba(2, 6, 23, 0.08);
            --fc-shadow-sm: 0 8px 22px rgba(2, 6, 23, 0.06);
        }

        html, body, [class*="css"]{
            font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Noto Sans", "Liberation Sans", sans-serif;
            color: var(--fc-text);
        }

        [data-testid="stAppViewContainer"]{
            background:
                radial-gradient(1200px 600px at 20% 10%, rgba(245,158,11,0.10), transparent 55%),
                radial-gradient(900px 520px at 90% 20%, rgba(37,99,235,0.10), transparent 55%),
                linear-gradient(135deg, var(--fc-bg-1), var(--fc-bg-2));
        }

        [data-testid="stAppViewContainer"]::before{
            content:"";
            position: fixed;
            inset: 0;
            pointer-events: none;
            opacity: 0.20;
            background-image: url("data:image/svg+xml;utf8,<?xml version='1.0' encoding='UTF-8'?>\
<svg xmlns='http://www.w3.org/2000/svg' width='1600' height='900' viewBox='0 0 1600 900'>\
<path d='M0,680 C260,610 420,740 720,670 C1020,600 1200,740 1600,640 L1600,900 L0,900 Z' fill='%230b3b60' fill-opacity='0.06'/>\
<path d='M0,720 C260,650 440,800 760,720 C1080,640 1220,760 1600,690 L1600,900 L0,900 Z' fill='%232563eb' fill-opacity='0.05'/>\
</svg>");
            background-size: cover;
            background-repeat: no-repeat;
            background-position: center bottom;
        }

        /* ✅ Como ocultamos stHeader/stToolbar, dejamos padding-top normal */
        .block-container{
            max-width: 1240px;
            padding-top: 1.25rem;
            padding-bottom: 2.25rem;
        }

        /* Sidebar base (PC) */
        section[data-testid="stSidebar"]{
            border-right: 1px solid rgba(15, 23, 42, 0.08);
        }
        section[data-testid="stSidebar"] > div{
            background: rgba(255,255,255,0.70);
            backdrop-filter: blur(8px);
        }

        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"]{
            border-radius: 999px !important;
        }

        div[data-testid="stSidebar"] div[role="radiogroup"] label{
            border-radius: 12px;
            padding: 8px 10px;
            margin: 3px 0;
            border: 1px solid transparent;
            transition: all 120ms ease;
        }
        div[data-testid="stSidebar"] div[role="radiogroup"] label:hover{
            background: rgba(37,99,235,0.06);
            border: 1px solid rgba(37,99,235,0.10);
        }
        div[data-testid="stSidebar"] div[role="radiogroup"] label input:checked + div{
            font-weight: 700 !important;
            color: var(--fc-primary) !important;
        }
        div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){
            background: rgba(245,158,11,0.10);
            border: 1px solid rgba(245,158,11,0.18);
        }

        .stButton > button{
            border-radius: 14px !important;
            border: 1px solid rgba(15,23,42,0.10) !important;
            box-shadow: var(--fc-shadow-sm);
        }

        hr{
            border: none;
            border-top: 1px solid rgba(15,23,42,0.10);
            margin: 14px 0;
        }

        /* (queda por compatibilidad si algún módulo usa fc-header) */
        .fc-header{
            background: rgba(255,255,255,0.70);
            border: 1px solid rgba(15,23,42,0.10);
            box-shadow: var(--fc-shadow);
            border-radius: var(--fc-radius);
            padding: 16px 18px;
        }
        .fc-brand h1{
            letter-spacing: -0.02em;
        }
        .fc-subtitle{
            color: var(--fc-muted);
        }
        .fc-notif button{
            width: 100%;
        }

        /* =========================
           ✅ HEADER REAL (sin div vacío)
           Estiliza el bloque de columnas que viene después del ancla
        ========================= */
        #fc_header_anchor{
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        #fc_header_anchor + div[data-testid="stHorizontalBlock"]{
            background: rgba(255,255,255,0.70) !important;
            border: 1px solid rgba(15,23,42,0.10) !important;
            box-shadow: var(--fc-shadow) !important;
            border-radius: var(--fc-radius) !important;
            padding: 16px 18px !important;
        }

        /* Por si quedó algún fc-header vacío viejo, lo mata */
        div.fc-header:empty{
            display: none !important;
            padding: 0 !important;
            margin: 0 !important;
            border: 0 !important;
            box-shadow: none !important;
            height: 0 !important;
        }

        /* ✅ Más negro el texto default (por ejemplo "Fertilab") y placeholders */
        .stApp input,
        .stApp input:disabled{
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            opacity: 1 !important;
        }

        .stApp input::placeholder{
            color: #64748b !important;
            -webkit-text-fill-color: #64748b !important;
            opacity: 1 !important;
        }

        .stApp label{
            color: #0f172a !important;
        }

        /* =========================
           RESPONSIVE (MÓVIL)
           - Sidebar blanco como PC
           - Quita el “punto/radio” gigante
           - Botón flotante de abrir sidebar con look pro
        ========================= */
        @media (max-width: 768px){

            /* Contenido */
            .block-container{
                padding-top: 0.9rem !important;
                padding-left: 0.8rem !important;
                padding-right: 0.8rem !important;
                padding-bottom: 4.5rem !important;
            }

            /* ✅ Sidebar drawer blanco (cuando se abre en móvil) */
            section[data-testid="stSidebar"]{
                background: transparent !important;
            }
            section[data-testid="stSidebar"] > div,
            div[data-testid="stSidebarContent"]{
                background: rgba(255,255,255,0.88) !important;
                backdrop-filter: blur(10px) !important;
            }

            /* Inputs del sidebar (evita que se vean “negros”) */
            section[data-testid="stSidebar"] .stTextInput input{
                background: rgba(255,255,255,0.92) !important;
                color: #0f172a !important;
                -webkit-text-fill-color: #0f172a !important;
                border: 1px solid rgba(15,23,42,0.12) !important;
            }

            /* ✅ Botón flotante para abrir sidebar (la “mancha blanca”) */
            button[data-testid="stExpandSidebarButton"]{
                position: fixed !important;
                top: 12px !important;
                left: 12px !important;
                z-index: 999999 !important;
                width: 44px !important;
                height: 44px !important;
                border-radius: 14px !important;
                background: rgba(255,255,255,0.88) !important;
                border: 1px solid rgba(15,23,42,0.12) !important;
                box-shadow: 0 10px 26px rgba(2, 6, 23, 0.12) !important;
            }
            button[data-testid="stExpandSidebarButton"] svg,
            button[data-testid="stExpandSidebarButton"] span{
                color: #0f172a !important;
                opacity: 1 !important;
            }

            /* ✅ Quitar el radio “punto” gigante del menú en móvil */
            section[data-testid="stSidebar"] div[role="radiogroup"] div[data-baseweb="radio"]{
                display: none !important;
            }
            section[data-testid="stSidebar"] div[role="radiogroup"] label{
                padding-left: 10px !important;
            }

            /* Tipografías */
            h1 { font-size: 1.35rem !important; line-height: 1.2 !important; }
            h2 { font-size: 1.15rem !important; line-height: 1.2 !important; }
            h3 { font-size: 1.05rem !important; line-height: 1.2 !important; }

            .stMarkdown, .stText, .stCaption, p, li{
                font-size: 0.95rem !important;
                line-height: 1.25 !important;
            }

            div[data-testid="stContainer"]{
                padding: 0.55rem !important;
            }

            div[role="radiogroup"] label{
                font-size: 0.95rem !important;
                margin-bottom: 0.25rem !important;
            }

            input, textarea{
                font-size: 1rem !important;
            }

            .stButton > button{
                width: 100% !important;
                padding: 0.60rem 0.9rem !important;
                font-size: 1rem !important;
            }

            div[data-testid="stDataFrame"],
            div[data-testid="stDataFrame"] *{
                font-size: 0.85rem !important;
            }

            details summary{
                font-size: 0.95rem !important;
            }

            div[data-testid="stHorizontalBlock"]{
                flex-wrap: wrap !important;
                gap: 0.5rem !important;
            }

            div[data-testid="column"]{
                min-width: 280px !important;
                flex: 1 1 280px !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    )

# =========================
# INICIALIZACIÓN
# =========================
inject_css_responsive()
init_db()
require_auth()

user = get_current_user() or {}

# =========================
# TÍTULO Y CAMPANITA
# =========================
usuario_actual = user.get("usuario", user.get("email", ""))
cant_pendientes = 0
if usuario_actual:
    cant_pendientes = contar_notificaciones_no_leidas(usuario_actual)

# ✅ Ancla: estiliza el bloque de columnas (evita <div class="fc-header"></div> vacío)
st.markdown("<div id='fc_header_anchor'></div>", unsafe_allow_html=True)

col_logo, col_spacer, col_notif = st.columns([7, 2, 1])

with col_logo:
    st.markdown("""
        <div class="fc-brand" style="display: flex; align-items: center; gap: 12px;">
            <div>
                <h1 style="margin: 0; font-size: 38px; font-weight: 900; color: #0f172a; letter-spacing: -0.02em;">
                    FertiChat
                </h1>
                <p class="fc-subtitle" style="margin: 4px 0 0 0; font-size: 15px;">
                    Sistema de Gestión de Compras
                </p>
            </div>
        </div>
    """, unsafe_allow_html=True)

with col_notif:
    st.markdown("<div class='fc-notif' style='display:flex; justify-content:flex-end; align-items:center; height:100%;'>", unsafe_allow_html=True)
    if cant_pendientes > 0:
        if st.button(f"🔔 {cant_pendientes}", key="campanita_global", help="Tenés pedidos internos pendientes"):
            st.session_state["ir_a_pedidos"] = True
            st.rerun()
    else:
        st.markdown("<div style='text-align:right; font-size:26px; padding-top:6px;'>🔔</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)


# =========================
# SIDEBAR
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
            <div style='font-size: 12px; text-align:center; color:#64748b; margin-top:2px;'>
                Sistema de Gestión
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.text_input("Buscar...", value="", key="sidebar_search", label_visibility="collapsed", placeholder="Buscar...")

    st.markdown(f"👤 **{user.get('nombre', 'Usuario')}**")
    if user.get('empresa'):
        st.markdown(f"🏢 {user.get('empresa')}")
    st.markdown(f"📧 _{user.get('Usuario', '')}_")

    st.markdown("---")

    if st.button("🚪 Cerrar sesión", key="btn_logout_sidebar", use_container_width=True, type="secondary"):
        logout()
        st.rerun()

    st.markdown("---")
    st.markdown("## 📌 Menú")

    if st.session_state.get("ir_a_pedidos"):
        st.session_state["radio_menu"] = "📄 Pedidos internos"
        st.session_state["ir_a_pedidos"] = False

    if st.session_state.get("navegacion_destino"):
        st.session_state["radio_menu"] = st.session_state["navegacion_destino"]
        del st.session_state["navegacion_destino"]

    if "radio_menu" not in st.session_state:
        st.session_state["radio_menu"] = "🏠 Inicio"

    menu = st.radio(
        "Ir a:",
        MENU_OPTIONS,
        key="radio_menu"
    )


# =========================
# ROUTER
# =========================
if menu == "🏠 Inicio":
    mostrar_inicio()

elif menu == "🛒 Compras IA":
    mostrar_resumen_compras_rotativo()
    Compras_IA()

elif menu == "📦 Stock IA":
    mostrar_resumen_stock_rotativo()
    mostrar_stock_ia()

elif menu == "🔎 Buscador IA":
    mostrar_buscador_ia()

elif menu == "📥 Ingreso de comprobantes":
    mostrar_ingreso_comprobantes()

elif menu == "📊 Dashboard":
    mostrar_dashboard()

elif menu == "📄 Pedidos internos":
    mostrar_pedidos_internos()

elif menu == "🧾 Baja de stock":
    mostrar_baja_stock()

elif menu == "📈 Indicadores (Power BI)":
    mostrar_indicadores_ia()

elif menu == "📦 Órdenes de compra":
    mostrar_ordenes_compra()

elif menu == "📒 Ficha de stock":
    mostrar_ficha_stock()

elif menu == "📚 Artículos":
    mostrar_articulos()

elif menu == "🏬 Depósitos":
    mostrar_depositos()

elif menu == "🧩 Familias":
    mostrar_familias()
