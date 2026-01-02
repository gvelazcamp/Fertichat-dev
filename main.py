# =========================
# MAIN.PY - CON MENÚ MÓVIL CUSTOM QUE SÍ FUNCIONA
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
# CSS + MENÚ MÓVIL CUSTOM
# =========================
def inject_mobile_menu():
    st.markdown(
        """
        <style>
        /* OCULTAR ELEMENTOS DE STREAMLIT */
        div.stAppToolbar,
        div[data-testid="stToolbar"],
        div[data-testid="stToolbarActions"],
        div[data-testid="stDecoration"],
        #MainMenu,
        footer{
          display: none !important;
        }

        header[data-testid="stHeader"]{
          display: block !important;
          height: 0 !important;
          min-height: 0 !important;
          background: transparent !important;
          border: 0 !important;
          box-shadow: none !important;
          margin: 0 !important;
          padding: 0 !important;
        }

        /* THEME */
        :root{
            --fc-bg-1: #f6f4ef;
            --fc-bg-2: #f3f6fb;
            --fc-primary: #0b3b60;
            --fc-accent: #f59e0b;
        }

        html, body, [class*="css"]{
            font-family: Inter, system-ui, -apple-system, sans-serif;
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
            border: 1px solid rgba(37,99,235,0.10);
        }
        div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){
            background: rgba(245,158,11,0.10);
            border: 1px solid rgba(245,158,11,0.18);
        }

        /* ========================================
           MENÚ MÓVIL CUSTOM - BOTÓN + DRAWER
        ======================================== */
        @media (max-width: 768px){
            
            /* OCULTAR SIDEBAR NATIVO EN MÓVIL */
            section[data-testid="stSidebar"]{
                display: none !important;
            }

            /* Padding para el botón */
            .block-container{
                padding-top: 70px !important;
            }

            /* BOTÓN MENÚ FLOTANTE */
            #mobile-menu-btn{
                position: fixed;
                top: 12px;
                left: 12px;
                z-index: 9999;
                width: 52px;
                height: 52px;
                background: #ffffff;
                border: 2px solid #0b3b60;
                border-radius: 14px;
                box-shadow: 0 8px 24px rgba(0,0,0,0.2);
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 26px;
            }

            /* DRAWER (menú deslizable) */
            #mobile-drawer{
                position: fixed;
                top: 0;
                left: -100%;
                width: 280px;
                height: 100vh;
                background: rgba(255,255,255,0.98);
                box-shadow: 8px 0 24px rgba(0,0,0,0.15);
                z-index: 9998;
                transition: left 0.3s ease;
                overflow-y: auto;
                padding: 20px;
            }

            #mobile-drawer.open{
                left: 0;
            }

            /* OVERLAY */
            #mobile-overlay{
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                z-index: 9997;
                display: none;
            }

            #mobile-overlay.open{
                display: block;
            }

            /* Items del menú */
            .mobile-menu-item{
                padding: 12px 14px;
                margin: 6px 0;
                border-radius: 10px;
                background: rgba(248,250,252,0.8);
                border: 1px solid rgba(15,23,42,0.1);
                cursor: pointer;
                color: #0f172a;
                font-size: 15px;
                font-weight: 500;
            }

            .mobile-menu-item.active{
                background: rgba(245,158,11,0.15);
                border-color: rgba(245,158,11,0.3);
                font-weight: 700;
                color: #0b3b60;
            }

            .mobile-menu-item:active{
                transform: scale(0.98);
            }
        }

        /* PC - sin cambios */
        @media (min-width: 769px){
            #mobile-menu-btn,
            #mobile-drawer,
            #mobile-overlay{
                display: none !important;
            }
        }
        </style>

        <!-- MENÚ MÓVIL HTML -->
        <div id="mobile-menu-btn" onclick="toggleMenu()">☰</div>
        
        <div id="mobile-overlay" onclick="toggleMenu()"></div>
        
        <div id="mobile-drawer">
            <div style="text-align:center; margin-bottom:20px; padding-bottom:15px; border-bottom:1px solid #e2e8f0;">
                <div style="font-size:22px; font-weight:800; color:#0f172a;">🦋 FertiChat</div>
                <div style="font-size:11px; color:#64748b; margin-top:4px;">Sistema de Gestión</div>
            </div>
            
            <div id="menu-items">
                <!-- Se generan con JS -->
            </div>

            <div style="margin-top:20px; padding-top:15px; border-top:1px solid #e2e8f0;">
                <div class="mobile-menu-item" onclick="logout()">🚪 Cerrar sesión</div>
            </div>
        </div>

        <script>
        const MENU_OPTIONS = [
            "🏠 Inicio",
            "🛒 Compras IA",
            "📦 Stock IA",
            "🔎 Buscador IA",
            "📥 Ingreso de comprobantes",
            "📊 Dashboard",
            "📄 Pedidos internos",
            "🧾 Baja de stock",
            "📈 Indicadores (Power BI)",
            "📦 Órdenes de compra",
            "📒 Ficha de stock",
            "📚 Artículos",
            "🏬 Depósitos",
            "🧩 Familias"
        ];

        function toggleMenu(){
            document.getElementById('mobile-drawer').classList.toggle('open');
            document.getElementById('mobile-overlay').classList.toggle('open');
        }

        function selectMenu(option){
            // Cambiar parámetro en URL
            const url = new URL(window.location.href);
            url.searchParams.set('menu', option);
            window.location.href = url.toString();
        }

        function logout(){
            const url = new URL(window.location.href);
            url.searchParams.set('logout', '1');
            window.location.href = url.toString();
        }

        // Generar items del menú
        window.addEventListener('DOMContentLoaded', function(){
            const container = document.getElementById('menu-items');
            const urlParams = new URLSearchParams(window.location.search);
            const currentMenu = urlParams.get('menu') || '🏠 Inicio';
            
            MENU_OPTIONS.forEach(option => {
                const div = document.createElement('div');
                div.className = 'mobile-menu-item' + (option === currentMenu ? ' active' : '');
                div.textContent = option;
                div.onclick = () => selectMenu(option);
                container.appendChild(div);
            });
        });
        </script>
        """,
        unsafe_allow_html=True
    )


# =========================
# INICIALIZACIÓN
# =========================
inject_mobile_menu()
init_db()
require_auth()

user = get_current_user() or {}

# =========================
# MANEJAR MENÚ MÓVIL
# =========================
try:
    # Logout desde móvil
    if st.query_params.get("logout") == "1":
        logout()
        st.query_params.clear()
        st.rerun()
    
    # Cambio de menú desde móvil
    menu_param = st.query_params.get("menu")
    if menu_param and menu_param in MENU_OPTIONS:
        st.session_state["radio_menu"] = menu_param
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

st.markdown("<div id='fc_header_anchor'></div>", unsafe_allow_html=True)

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
            st.session_state["ir_a_pedidos"] = True
            st.rerun()
    else:
        st.markdown("<div style='text-align:right; font-size:26px;'>🔔</div>", unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)


# =========================
# SIDEBAR (SOLO PC)
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

    st.text_input("Buscar...", value="", key="sidebar_search", label_visibility="collapsed", placeholder="Buscar...")

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

    if st.session_state.get("ir_a_pedidos"):
        st.session_state["radio_menu"] = "📄 Pedidos internos"
        st.session_state["ir_a_pedidos"] = False

    if st.session_state.get("navegacion_destino"):
        st.session_state["radio_menu"] = st.session_state["navegacion_destino"]
        del st.session_state["navegacion_destino"]

    if "radio_menu" not in st.session_state:
        st.session_state["radio_menu"] = "🏠 Inicio"

    menu = st.radio("Ir a:", MENU_OPTIONS, key="radio_menu")


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
