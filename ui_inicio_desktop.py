# =========================
# UI_INICIO_DESKTOP.PY - PANTALLA DE INICIO PARA PC (CORPORATIVO)
# =========================

import streamlit as st
from datetime import datetime
import random


def mostrar_inicio_desktop():
    st.session_state["is_mobile"] = False
    
    user = st.session_state.get("user", {})
    nombre = user.get("nombre", "Usuario")

    hora = datetime.now().hour
    if hora < 12:
        saludo = "¡Buenos días"
    elif hora < 19:
        saludo = "¡Buenas tardes"
    else:
        saludo = "¡Buenas noches"

    st.markdown('<div id="fc-home-desktop-marker" style="display:none;"></div>', unsafe_allow_html=True)

    st.markdown("""
    <style>
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) > div {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .main {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .main .block-container {
        padding-top: 0 !important;
        margin-top: 0 !important;
        padding-bottom: 1rem !important;
        max-width: 100% !important;
    }
    
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) section.main > div {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) [data-testid="stMainBlockContainer"],
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .block-container,
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) div.block-container {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stVerticalBlock,
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) [data-testid="stVerticalBlock"] {
        padding-top: 0 !important;
        margin-top: 0 !important;
        gap: 0 !important;
    }
    
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) h1 {
        display: none !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) div[data-testid="column"] {
        position: relative;
    }

    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button {
        border: 1px solid rgba(148, 163, 184, 0.25);
        background: #ffffff;
        border-radius: 12px;
        height: 200px;
        min-height: 200px;
        padding: 80px 20px 20px 20px;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
        cursor: pointer;
        transition: all 180ms cubic-bezier(0.4, 0, 0.2, 1);
        width: 100%;
        text-align: center;
        white-space: pre-line;
        font-size: 14px;
        font-weight: 400;
        color: #64748b;
        line-height: 1.6;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-start;
        position: relative;
        margin: 0;
    }

    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button::first-line {
        font-size: 17px;
        font-weight: 700;
        color: #1e293b;
        letter-spacing: -0.01em;
    }

    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
        border-color: rgba(59, 130, 246, 0.5);
    }
    
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button:active {
        transform: translateY(0);
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
    }

    .fc-badge {
        position: absolute;
        top: 12px;
        right: 12px;
        background: #ef4444;
        color: white;
        font-size: 11px;
        font-weight: 700;
        padding: 4px 9px;
        border-radius: 6px;
        box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
        z-index: 10;
    }

    @media (max-width: 900px) {
        div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button {
            height: 160px;
            min-height: 160px;
            padding: 65px 16px 16px 16px;
        }
        div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button::first-line {
            font-size: 15px;
        }
    }

    section[data-testid="stSidebar"] {
        background: #ffffff !important;
        border-right: 1px solid rgba(148, 163, 184, 0.2);
    }

    section[data-testid="stSidebar"] *,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p {
        color: #1e293b !important;
    }

    section[data-testid="stSidebar"] .stButton button {
        background: #f1f5f9 !important;
        color: #1e293b !important;
        border: 1px solid #e2e8f0 !important;
    }

    section[data-testid="stSidebar"] .stButton button:hover {
        background: #e2e8f0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown('<div style="text-align:center;font-size:18px;font-weight:700;color:#1e293b;margin-bottom:20px;">📊 FertiChat</div>', unsafe_allow_html=True)
        st.markdown("---")
        
        st.markdown("**PRINCIPAL**")
        if st.button("🏠 Inicio", key="sidebar_inicio"):
            if "go" in st.query_params:
                del st.query_params["go"]
            st.rerun()
        if st.button("🛒 Compras IA", key="sidebar_compras"):
            st.query_params["go"] = "compras"
            st.rerun()
        if st.button("🔍 Buscador IA", key="sidebar_buscador"):
            st.query_params["go"] = "buscador"
            st.rerun()
        if st.button("📦 Stock IA [1]", key="sidebar_stock"):
            st.query_params["go"] = "stock"
            st.rerun()
        
        st.markdown("**ANÁLISIS**")
        if st.button("📊 Dashboard", key="sidebar_dashboard"):
            st.query_params["go"] = "dashboard"
            st.rerun()
        if st.button("📈 Indicadores", key="sidebar_indicadores"):
            st.query_params["go"] = "indicadores"
            st.rerun()
        
        st.markdown("**OPERACIONES**")
        if st.button("📋 Pedidos internos", key="sidebar_pedidos"):
            st.query_params["go"] = "pedidos"
            st.rerun()
        if st.button("⬇️ Baja de stock", key="sidebar_baja"):
            st.query_params["go"] = "baja"
            st.rerun()
        if st.button("🛍️ Órdenes de compra", key="sidebar_ordenes"):
            st.query_params["go"] = "ordenes"
            st.rerun()
        
        st.markdown("**CATÁLOGO**")
        if st.button("📝 Artículos", key="sidebar_articulos"):
            st.query_params["go"] = "articulos"
            st.rerun()
        if st.button("🏷️ Familias", key="sidebar_familias"):
            st.query_params["go"] = "familias"
            st.rerun()
        if st.button("🏭 Depósitos", key="sidebar_depositos"):
            st.query_params["go"] = "depositos"
            st.rerun()
        
        st.markdown("**VALIDACIÓN**")
        if st.button("✅ Comprobantes", key="sidebar_comprobantes"):
            st.query_params["go"] = "comprobantes"
            st.rerun()
        if st.button("📄 Ficha de stock", key="sidebar_ficha"):
            st.query_params["go"] = "ficha"
            st.rerun()
        
        st.markdown("---")
        if st.button("⚙️ Debug SQL", key="sidebar_debug"):
            st.query_params["go"] = "debug"
            st.rerun()
        if st.button("🚪 Cerrar sesión", key="sidebar_logout"):
            st.session_state.clear()
            st.query_params["go"] = "logout"
            st.rerun()

    # Main content
    st.markdown(f"<div style='text-align:center;margin:100px auto 0 auto;font-size:24px;color:#1e293b;'>{saludo}, {nombre}!</div>", unsafe_allow_html=True)

    tips = [
        "💡 Escribí 'compras roche 2025' para ver todas las compras a Roche este año",
        "💡 Usá 'lotes por vencer' en Stock IA para ver vencimientos próximos",
        "💡 Probá 'comparar roche 2024 2025' para ver la evolución de compras",
        "💡 En el Buscador podés filtrar por proveedor, artículo y fechas",
        "💡 Usá 'top 10 proveedores 2025' para ver el ranking de compras",
    ]
    tip = random.choice(tips)

    st.markdown(
        f"""
        <div style="max-width:1200px;margin:40px auto 0 auto;">
            <div style="
                background: #ffffff;
                border: 1px solid rgba(148, 163, 184, 0.25);
                border-left: 4px solid #3b82f6;
                border-radius: 12px;
                padding: 16px 20px;
                box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
            ">
                <p style="margin:0;color:#475569;font-size:14px;font-weight:500;">
                    {tip}
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
