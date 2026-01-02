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
# CSS + MENÚ MÓVIL HAMBURGUESA
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

        /* Sidebar PC */
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

        /* ========================================
           MÓVIL - Ocultar sidebar y ajustar padding
        ======================================== */
        @media (max-width: 768px){
            
            /* Ocultar sidebar de Streamlit en móvil */
            section[data-testid="stSidebar"]{
                display: none !important;
            }

            /* Padding para el header móvil (el menú se renderiza aparte) */
            .block-container{
                padding-top: 70px !important;
            }
        }

        /* PC - Normal */
        @media (min-width: 769px){
            .block-container{
                padding-top: 1.25rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    )


# =========================
# MENÚ MÓVIL HTML
# =========================
def render_mobile_menu():
    import streamlit.components.v1 as components
    
    user = st.session_state.get("user", {})
    menu_actual = st.session_state.get("radio_menu", "🏠 Inicio")
    
    menu_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            
            body {{
                font-family: Inter, system-ui, sans-serif;
            }}
            
            /* Header móvil fijo arriba */
            #mobile-header{{
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                height: 56px;
                background: #0b3b60;
                z-index: 9999;
                display: flex;
                align-items: center;
                padding: 0 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            }}

            /* Botón hamburguesa */
            #menu-toggle{{
                width: 40px;
                height: 40px;
                background: transparent;
                border: none;
                cursor: pointer;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                gap: 5px;
                padding: 0;
            }}

            #menu-toggle span{{
                width: 24px;
                height: 3px;
                background: white;
                border-radius: 2px;
                transition: all 0.3s;
                display: block;
            }}

            /* Animación del botón cuando está abierto */
            #menu-toggle.open span:nth-child(1){{
                transform: rotate(45deg) translate(6px, 6px);
            }}
            #menu-toggle.open span:nth-child(2){{
                opacity: 0;
            }}
            #menu-toggle.open span:nth-child(3){{
                transform: rotate(-45deg) translate(6px, -6px);
            }}

            /* Logo en el header */
            #mobile-logo{{
                color: white;
                font-size: 20px;
                font-weight: 800;
                margin-left: 12px;
            }}

            /* Menú desplegable */
            #mobile-menu{{
                position: fixed;
                top: 56px;
                left: 0;
                width: 280px;
                height: calc(100vh - 56px);
                background: rgba(255,255,255,0.98);
                backdrop-filter: blur(12px);
                box-shadow: 4px 0 12px rgba(0,0,0,0.15);
                transform: translateX(-100%);
                transition: transform 0.3s ease;
                z-index: 9998;
                overflow-y: auto;
                padding: 16px;
            }}

            #mobile-menu.open{{
                transform: translateX(0);
            }}

            /* Overlay */
            #mobile-overlay{{
                position: fixed;
                top: 56px;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.5);
                z-index: 9997;
                opacity: 0;
                visibility: hidden;
                transition: all 0.3s;
            }}

            #mobile-overlay.open{{
                opacity: 1;
                visibility: visible;
            }}

            /* Items del menú móvil */
            .mobile-menu-item{{
                padding: 12px 14px;
                margin: 6px 0;
                border-radius: 10px;
                background: rgba(248,250,252,0.8);
                border: 1px solid rgba(15,23,42,0.1);
                cursor: pointer;
                color: #0f172a;
                font-size: 15px;
                font-weight: 500;
                transition: all 0.15s;
                display: block;
                text-decoration: none;
            }}

            .mobile-menu-item:hover{{
                background: rgba(245,158,11,0.1);
                border-color: rgba(245,158,11,0.2);
            }}

            .mobile-menu-item.active{{
                background: rgba(245,158,11,0.15);
                border-color: rgba(245,158,11,0.3);
                font-weight: 700;
                color: #0b3b60;
            }}

            /* Info del usuario en menú móvil */
            .mobile-user-info{{
                background: rgba(248,250,252,0.9);
                padding: 14px;
                border-radius: 12px;
                margin-bottom: 16px;
                border: 1px solid rgba(15,23,42,0.1);
            }}

            .mobile-user-info div{{
                color: #0f172a;
                font-size: 14px;
                margin: 4px 0;
            }}
            
            /* Ocultar en PC */
            @media (min-width: 769px) {{
                #mobile-header,
                #mobile-menu,
                #mobile-overlay {{
                    display: none !important;
                }}
            }}
        </style>
    </head>
    <body>
        <!-- Header móvil -->
        <div id="mobile-header">
            <button id="menu-toggle" onclick="toggleMenu()">
                <span></span>
                <span></span>
                <span></span>
            </button>
            <div id="mobile-logo">🦋 FertiChat</div>
        </div>

        <!-- Overlay -->
        <div id="mobile-overlay" onclick="toggleMenu()"></div>

        <!-- Menú desplegable -->
        <div id="mobile-menu">
            <div class="mobile-user-info">
                <div style="font-weight:700;">👤 {user.get('nombre', 'Usuario')}</div>
                <div style="font-size:12px;color:#64748b;">🏢 {user.get('empresa', 'Empresa')}</div>
                <div style="font-size:12px;color:#64748b;">📧 {user.get('Usuario', '')}</div>
            </div>

            <div style="color:#64748b;font-size:11px;font-weight:800;text-transform:uppercase;margin:12px 0 8px 4px;">
                📌 Menú
            </div>
    """
    
    # Generar items del menú
    for opcion in MENU_OPTIONS:
        active_class = "active" if opcion == menu_actual else ""
        menu_html += f"""
            <a href="?menu={opcion}" class="mobile-menu-item {active_class}">
                {opcion}
            </a>
        """
    
    menu_html += """
            <a href="?logout=1" class="mobile-menu-item" style="margin-top:16px;border-top:1px solid #e5e7eb;padding-top:16px;">
                🚪 Cerrar sesión
            </a>
        </div>

        <script>
            function toggleMenu() {
                document.getElementById('menu-toggle').classList.toggle('open');
                document.getElementById('mobile-menu').classList.toggle('open');
                document.getElementById('mobile-overlay').classList.toggle('open');
            }
        </script>
    </body>
    </html>
    """
    
    components.html(menu_html, height=0)


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

# Manejar navegación desde menú móvil
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

# Renderizar menú móvil
render_mobile_menu()

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
