# =========================
# MAIN.PY - PC con SIDEBAR + MÓVIL con MENÚ PROPIO (SIN LINKS / SIN RECARGA)
# =========================

import streamlit as st
from datetime import datetime
from urllib.parse import quote, unquote  # (se deja, no molesta aunque ya no se use)

st.set_page_config(
    page_title="FertiChat",
    page_icon="🦋",
    layout="wide",
    initial_sidebar_state="expanded"  # PC
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
# CSS GLOBAL (PC igual) + CSS MÓVIL (header + drawer)
# =========================
def inject_css():
    st.markdown(
        """
        <style>
        /* =========================
           OCULTAR UI DE STREAMLIT
        ========================= */
        div.stAppToolbar,
        div[data-testid="stToolbar"],
        div[data-testid="stToolbarActions"],
        div[data-testid="stDecoration"],
        #MainMenu,
        footer {
          display: none !important;
        }

        header[data-testid="stHeader"]{
          height: 0 !important;
          background: transparent !important;
        }

        /* =========================
           THEME GENERAL
        ========================= */
        :root{
            --fc-bg-1: #f6f4ef;
            --fc-bg-2: #f3f6fb;
            --fc-primary: #0b3b60;
            --fc-accent: #f59e0b;
            --fc-text: #0f172a;
            --fc-muted: #64748b;
        }

        html, body{
            font-family: Inter, system-ui, sans-serif;
            color: var(--fc-text);
        }

        [data-testid="stAppViewContainer"]{
            background: linear-gradient(135deg, var(--fc-bg-1), var(--fc-bg-2));
        }

        .block-container{
            max-width: 1240px;
            padding-top: 1.25rem;
            padding-bottom: 2.25rem;
        }

        /* =========================
           SIDEBAR PC (tu estilo)
        ========================= */
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
           PC: ocultar header/drawer móvil
        ========================= */
        @media (min-width: 769px){
            #fc_mobile_header_anchor,
            #fc_mobile_drawer_anchor{
                display: none !important;
            }
            #fc_mobile_header_anchor + div[data-testid="stHorizontalBlock"],
            #fc_mobile_drawer_anchor + div[data-testid="stVerticalBlock"],
            .fc-mobile-overlay{
                display: none !important;
            }
        }

        /* =========================
           MÓVIL: header fijo + drawer fijo
        ========================= */
        @media (max-width: 768px){

            /* Ocultar sidebar nativo SOLO en móvil */
            section[data-testid="stSidebar"]{
                display: none !important;
            }

            /* Dejar espacio para header móvil fijo */
            .block-container{
                padding-top: 70px !important;
            }

            /* HEADER MÓVIL: bloque de columnas inmediatamente después del ancla */
            #fc_mobile_header_anchor{
                height: 0 !important;
                margin: 0 !important;
                padding: 0 !important;
            }

            #fc_mobile_header_anchor + div[data-testid="stHorizontalBlock"]{
                position: fixed !important;
                top: 0 !important;
                left: 0 !important;
                right: 0 !important;
                height: 56px !important;
                background: #0b3b60 !important;
                z-index: 999999 !important;
                display: flex !important;
                align-items: center !important;
                padding: 6px 10px !important;
                box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
            }

            /* Botón hamburguesa (Streamlit) dentro del header */
            #fc_mobile_header_anchor + div[data-testid="stHorizontalBlock"] .stButton > button{
                background: transparent !important;
                border: 0 !important;
                color: white !important;
                font-size: 22px !important;
                padding: 6px 10px !important;
                box-shadow: none !important;
                border-radius: 10px !important;
            }

            .fc-mobile-title{
                color: white !important;
                font-weight: 900 !important;
                font-size: 18px !important;
                letter-spacing: -0.01em !important;
            }

            .fc-mobile-sub{
                color: rgba(255,255,255,0.75) !important;
                font-size: 11px !important;
                margin-top: -2px !important;
            }

            /* OVERLAY (solo cuando existe en el DOM) */
            .fc-mobile-overlay{
                position: fixed !important;
                top: 56px !important;
                left: 0 !important;
                right: 0 !important;
                bottom: 0 !important;
                background: rgba(0,0,0,0.45) !important;
                z-index: 999998 !important;
            }

            /* DRAWER: contenedor inmediatamente después del ancla */
            #fc_mobile_drawer_anchor{
                height: 0 !important;
                margin: 0 !important;
                padding: 0 !important;
            }

            #fc_mobile_drawer_anchor + div[data-testid="stVerticalBlock"]{
                position: fixed !important;
                top: 56px !important;
                left: 0 !important;
                width: 290px !important;
                height: calc(100dvh - 56px) !important;
                background: rgba(255,255,255,0.98) !important;
                z-index: 999999 !important;
                overflow-y: auto !important;
                padding: 14px !important;
                box-shadow: 4px 0 12px rgba(0,0,0,0.15) !important;
                border-right: 1px solid rgba(15,23,42,0.10) !important;
            }

            /* Botones del drawer (menú) */
            #fc_mobile_drawer_anchor + div[data-testid="stVerticalBlock"] .stButton > button{
                width: 100% !important;
                text-align: left !important;
                padding: 12px 12px !important;
                border-radius: 10px !important;
                background: rgba(248,250,252,0.92) !important;
                border: 1px solid rgba(15,23,42,0.10) !important;
                color: #0f172a !important;
                box-shadow: none !important;
            }

            #fc_mobile_drawer_anchor + div[data-testid="stVerticalBlock"] .stButton > button:hover{
                background: rgba(245,158,11,0.10) !important;
                border-color: rgba(245,158,11,0.20) !important;
            }

            .fc-drawer-section{
                color: #64748b !important;
                font-size: 11px !important;
                font-weight: 900 !important;
                text-transform: uppercase !important;
                margin: 10px 0 6px 4px !important;
            }

            .fc-user-card{
                background: rgba(248,250,252,0.95);
                padding: 12px;
                border-radius: 12px;
                border: 1px solid rgba(15,23,42,0.10);
                margin-bottom: 10px;
            }
            .fc-user-line{
                margin: 2px 0;
                color: #0f172a;
                font-size: 13px;
                line-height: 1.2;
            }
            .fc-user-subline{
                color: #64748b;
                font-size: 12px;
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

# Estado menú principal
if "radio_menu" not in st.session_state:
    st.session_state["radio_menu"] = "🏠 Inicio"

# Estado drawer móvil
if "mobile_menu_open" not in st.session_state:
    st.session_state["mobile_menu_open"] = False


# =========================
# HEADER MÓVIL (SOLO SE VE EN CEL POR CSS)
# =========================
st.markdown("<div id='fc_mobile_header_anchor'></div>", unsafe_allow_html=True)
mcol_btn, mcol_title, mcol_notif = st.columns([1, 6, 1])

with mcol_btn:
    if st.button("☰", key="fc_mobile_toggle"):
        st.session_state["mobile_menu_open"] = not st.session_state["mobile_menu_open"]
        st.rerun()

with mcol_title:
    st.markdown(
        """
        <div>
          <div class="fc-mobile-title">🦋 FertiChat</div>
          <div class="fc-mobile-sub">Sistema de Gestión</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# campanita en móvil (opcional)
usuario_actual = user.get("usuario", user.get("email", ""))
cant_pendientes = 0
if usuario_actual:
    cant_pendientes = contar_notificaciones_no_leidas(usuario_actual)

with mcol_notif:
    if cant_pendientes > 0:
        if st.button(f"🔔 {cant_pendientes}", key="fc_mobile_notif"):
            st.session_state["radio_menu"] = "📄 Pedidos internos"
            st.session_state["mobile_menu_open"] = False
            st.rerun()
    else:
        st.markdown("<div style='text-align:right; font-size:18px; color:white; padding-top:6px;'>🔔</div>", unsafe_allow_html=True)


# =========================
# DRAWER MÓVIL (SOLO SI ESTÁ ABIERTO)
# =========================
if st.session_state["mobile_menu_open"]:

    # overlay visual (sin click-close; se cierra con ☰ o con botón Cerrar)
    st.markdown("<div class='fc-mobile-overlay'></div>", unsafe_allow_html=True)

    st.markdown("<div id='fc_mobile_drawer_anchor'></div>", unsafe_allow_html=True)
    with st.container():

        if st.button("✕ Cerrar menú", key="fc_mobile_close", use_container_width=True):
            st.session_state["mobile_menu_open"] = False
            st.rerun()

        st.markdown(
            f"""
            <div class="fc-user-card">
              <div class="fc-user-line" style="font-weight:900;">👤 {user.get('nombre', 'Usuario')}</div>
              <div class="fc-user-line fc-user-subline">🏢 {user.get('empresa', 'Empresa')}</div>
              <div class="fc-user-line fc-user-subline">📧 {user.get('Usuario', user.get('usuario', ''))}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown("<div class='fc-drawer-section'>Menú</div>", unsafe_allow_html=True)

        # Botones del menú (NO recargan, NO rompen sesión)
        for i, opcion in enumerate(MENU_OPTIONS):
            if st.button(opcion, key=f"fc_m_{i}", use_container_width=True):
                st.session_state["radio_menu"] = opcion
                st.session_state["mobile_menu_open"] = False
                st.rerun()

        st.markdown("<div class='fc-drawer-section'>Sesión</div>", unsafe_allow_html=True)
        if st.button("🚪 Cerrar sesión", key="fc_m_logout", use_container_width=True):
            logout()
            st.rerun()


# =========================
# HEADER NORMAL (TUYO, QUEDA IGUAL)
# =========================
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
# SIDEBAR (PC)
# (En móvil queda oculto por CSS, pero el código queda igual)
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
    st.markdown(f"📧 _{user.get('Usuario', user.get('usuario', ''))}_")

    st.markdown("---")

    if st.button("🚪 Cerrar sesión", key="btn_logout_sidebar", use_container_width=True):
        logout()
        st.rerun()

    st.markdown("---")
    st.markdown("## 📌 Menú")

    menu = st.radio("Ir a:", MENU_OPTIONS, key="radio_menu")


# =========================
# ROUTER (IGUAL AL TUYO)
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
