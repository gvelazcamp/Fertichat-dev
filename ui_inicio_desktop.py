# =========================
# UI_INICIO_DESKTOP.PY - PANTALLA DE INICIO PARA PC (CORPORATIVO)
# =========================

import streamlit as st
from datetime import datetime
import random


def mostrar_inicio_desktop():
    """Pantalla de inicio con accesos rápidos a los módulos (look corporativo para PC)"""

    # FORZAR DETECCIÓN DESKTOP (para que el router sepa que es PC)
    st.session_state["is_mobile"] = False
    
    # =========================
    # Datos usuario / saludo
    # =========================
    user = st.session_state.get("user", {})
    nombre = user.get("nombre", "Usuario")

    hora = datetime.now().hour
    if hora < 12:
        saludo = "¡Buenos días"
    elif hora < 19:
        saludo = "¡Buenas tardes"
    else:
        saludo = "¡Buenas noches"

    # =========================
    # MARCADOR DESKTOP (para aplicar CSS SOLO en esta pantalla)
    # =========================
    st.markdown('<div id="fc-home-desktop-marker" style="display:none;"></div>', unsafe_allow_html=True)

    # =========================
    # CSS CORPORATIVO LIMPIO - Estilo imagen (fondo blanco, iconos line-style)
    # =========================
    st.markdown("""
    <style>
    /* =========================================================
       ELIMINAR TODO EL PADDING SUPERIOR - AGRESIVO
       ========================================================= */
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
    
    /* =========================================================
       TARJETAS CORPORATIVAS - ESTILO IMAGEN (fondo blanco limpio)
       ========================================================= */
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) div[data-testid="column"] {
        position: relative;
    }

    /* Botón como tarjeta - Fondo blanco profesional */
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button {
        border: 1px solid rgba(148, 163, 184, 0.25);
        background: #ffffff;
        border-radius: 12px;
        
        height: 200px;
        min-height: 200px;
        
        padding: 24px 20px;
        
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

    /* Título de la tarjeta - Bold y oscuro */
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button::first-line {
        font-size: 17px;
        font-weight: 700;
        color: #1e293b;
        letter-spacing: -0.01em;
    }

    /* Hover corporativo - Solo sombra y borde azul */
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
        border-color: rgba(59, 130, 246, 0.5);
    }
    
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button:active {
        transform: translateY(0);
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
    }

    /* Icono - Tamaño grande, line-style */
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .fc-home-tile {
        width: 72px;
        height: 72px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 40px;
        margin-bottom: 16px;
        color: #3b82f6;
        filter: drop-shadow(0 2px 4px rgba(59, 130, 246, 0.12));
        pointer-events: none;
        user-select: none;
    }

    /* Badge rojo (solo para las tarjetas que lo necesiten) */
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
    }

    /* Responsive */
    @media (max-width: 900px) {
        div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button {
            height: 160px;
            min-height: 160px;
            padding: 18px 16px;
        }
        div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .fc-home-tile {
            width: 56px;
            height: 56px;
            font-size: 32px;
            margin-bottom: 12px;
        }
        div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button::first-line {
            font-size: 15px;
        }
    }

    /* SIDEBAR LIGHT */
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

    # =========================
    # GRID DE TARJETAS - 2 FILAS
    # =========================
    st.markdown("<div style='max-width:1200px;margin:100px auto 0 auto;'>", unsafe_allow_html=True)

    # FILA 1 - Inteligencia y consulta
    st.markdown("<div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:0 0 24px 6px;display:flex;align-items:center;gap:8px;'>📌 Inteligencia y consulta</div>", unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4, gap="large")
    
    with col1:
        st.markdown('<div class="fc-home-tile">🛒</div>', unsafe_allow_html=True)
        if st.button("Compras IA\nConsultas inteligentes de compras y gastos", key="compras", use_container_width=True):
            st.query_params["go"] = "compras"
            st.rerun()
    
    with col2:
        st.markdown('<div class="fc-home-tile">🔎</div>', unsafe_allow_html=True)
        if st.button("Buscador IA\nBuscar facturas, artículos y lotes", key="buscador", use_container_width=True):
            st.query_params["go"] = "buscador"
            st.rerun()
    
    with col3:
        st.markdown('<div class="fc-home-tile">📦</div>', unsafe_allow_html=True)
        # Badge solo en Stock si hay alertas
        st.markdown('<div class="fc-badge">1</div>', unsafe_allow_html=True)
        if st.button("Stock IA\nConsultar inventario y vencimientos", key="stock", use_container_width=True):
            st.query_params["go"] = "stock"
            st.rerun()
    
    with col4:
        st.markdown('<div class="fc-home-tile">📊</div>', unsafe_allow_html=True)
        if st.button("Dashboard\nAnálisis y resúmenes ejecutivos", key="dashboard", use_container_width=True):
            st.query_params["go"] = "dashboard"
            st.rerun()

    st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)

    # FILA 2 - Gestión operativa
    st.markdown("<div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:0 0 24px 6px;display:flex;align-items:center;gap:8px;'>⚙️ Gestión operativa</div>", unsafe_allow_html=True)
    
    col5, col6, col7, col8 = st.columns(4, gap="large")
    
    with col5:
        st.markdown('<div class="fc-home-tile">📄</div>', unsafe_allow_html=True)
        if st.button("Pedidos internos\nGestionar pedidos y solicitudes", key="pedidos", use_container_width=True):
            st.query_params["go"] = "pedidos"
            st.rerun()
    
    with col6:
        st.markdown('<div class="fc-home-tile">🧾</div>', unsafe_allow_html=True)
        if st.button("Baja de stock\nRegistrar consumo y bajas", key="baja", use_container_width=True):
            st.query_params["go"] = "baja"
            st.rerun()
    
    with col7:
        st.markdown('<div class="fc-home-tile">📦</div>', unsafe_allow_html=True)
        if st.button("Órdenes de compra\nGenerar órdenes de compra", key="ordenes", use_container_width=True):
            st.query_params["go"] = "ordenes"
            st.rerun()
    
    with col8:
        st.markdown('<div class="fc-home-tile">📈</div>', unsafe_allow_html=True)
        if st.button("Indicadores\nPower BI - Análisis avanzado", key="indicadores", use_container_width=True):
            st.query_params["go"] = "indicadores"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # =========================
    # TIP DEL DÍA
    # =========================
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
