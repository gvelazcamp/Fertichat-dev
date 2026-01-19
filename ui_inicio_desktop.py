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
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<div style='max-width:1200px;margin:100px auto 0 auto;'>", unsafe_allow_html=True)
    st.markdown("<div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:0 0 24px 6px;display:flex;align-items:center;gap:8px;'>📌 Inteligencia y consulta</div>", unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4, gap="large")
    
    with col1:
        st.markdown("""
        <div style="text-align:center;margin-bottom:-200px;pointer-events:none;position:relative;z-index:1;">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
                <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
            </svg>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Compras IA\nConsultas inteligentes de compras y gastos", key="compras", use_container_width=True):
            st.query_params["go"] = "compras"
            st.rerun()
    
    with col2:
        st.markdown("""
        <div style="text-align:center;margin-bottom:-200px;pointer-events:none;position:relative;z-index:1;">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Buscador IA\nBuscar facturas, artículos y lotes", key="buscador", use_container_width=True):
            st.query_params["go"] = "buscador"
            st.rerun()
    
    with col3:
        st.markdown('<div class="fc-badge">1</div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align:center;margin-bottom:-200px;pointer-events:none;position:relative;z-index:1;">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                <polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
            </svg>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Stock IA\nConsultar inventario y vencimientos", key="stock", use_container_width=True):
            st.query_params["go"] = "stock"
            st.rerun()
    
    with col4:
        st.markdown("""
        <div style="text-align:center;margin-bottom:-200px;pointer-events:none;position:relative;z-index:1;">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/>
                <line x1="6" y1="20" x2="6" y2="14"/>
            </svg>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Dashboard\nAnálisis y resúmenes ejecutivos", key="dashboard", use_container_width=True):
            st.query_params["go"] = "dashboard"
            st.rerun()

    st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)
    st.markdown("<div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:0 0 24px 6px;display:flex;align-items:center;gap:8px;'>⚙️ Gestión operativa</div>", unsafe_allow_html=True)
    
    col5, col6, col7, col8 = st.columns(4, gap="large")
    
    with col5:
        st.markdown("""
        <div style="text-align:center;margin-bottom:-200px;pointer-events:none;position:relative;z-index:1;">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
            </svg>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Pedidos internos\nGestionar pedidos y solicitudes", key="pedidos", use_container_width=True):
            st.query_params["go"] = "pedidos"
            st.rerun()
    
    with col6:
        st.markdown("""
        <div style="text-align:center;margin-bottom:-200px;pointer-events:none;position:relative;z-index:1;">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/>
                <line x1="9" y1="15" x2="15" y2="15"/>
            </svg>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Baja de stock\nRegistrar consumo y bajas", key="baja", use_container_width=True):
            st.query_params["go"] = "baja"
            st.rerun()
    
    with col7:
        st.markdown("""
        <div style="text-align:center;margin-bottom:-200px;pointer-events:none;position:relative;z-index:1;">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                <polyline points="7.5 4.21 12 6.81 16.5 4.21"/><polyline points="7.5 19.79 7.5 14.6 3 12"/>
                <polyline points="21 12 16.5 14.6 16.5 19.79"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
                <line x1="12" y1="22.08" x2="12" y2="12"/>
            </svg>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Órdenes de compra\nGenerar órdenes de compra", key="ordenes", use_container_width=True):
            st.query_params["go"] = "ordenes"
            st.rerun()
    
    with col8:
        st.markdown("""
        <div style="text-align:center;margin-bottom:-200px;pointer-events:none;position:relative;z-index:1;">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/>
                <line x1="6" y1="20" x2="6" y2="16"/>
            </svg>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Indicadores\nPower BI - Análisis avanzado", key="indicadores", use_container_width=True):
            st.query_params["go"] = "indicadores"
            st.rerun()

    # ← NUEVA SECCIÓN PARA SUGERENCIAS
    st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)
    st.markdown("<div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:0 0 24px 6px;display:flex;align-items:center;gap:8px;'>📋 Análisis y sugerencias</div>", unsafe_allow_html=True)
    
    col9, col10, col11, col12 = st.columns(4, gap="large")
    
    with col9:
        st.markdown("""
        <div style="text-align:center;margin-bottom:-200px;pointer-events:none;position:relative;z-index:1;">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 12l2 2 4-4"/><path d="M21 12c-1 0-3-1-3-3s2-3 3-3 3 1 3 3-2 3-3 3"/><path d="M3 12c1 0 3-1 3-3s-2-3-3-3-3 1-3 3 2 3 3 3"/><path d="M12 3v6"/><path d="M12 15v6"/>
            </svg>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Sugerencia de pedidos\nRecomendaciones inteligentes de compra", key="sugerencias", use_container_width=True):
            st.query_params["go"] = "sugerencias"
            st.rerun()

    # Rellenar las otras columnas para mantener el diseño (opcional)
    with col10:
        st.empty()
    
    with col11:
        st.empty()
    
    with col12:
        st.empty()

    st.markdown("</div>", unsafe_allow_html=True)

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
