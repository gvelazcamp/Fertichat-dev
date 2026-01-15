# =========================
# UI_INICIO_DESKTOP.PY - PANTALLA DE INICIO PARA PC (CORPORATIVO)
# =========================

import streamlit as st
from datetime import datetime
import random
import textwrap


def mostrar_inicio_desktop():
    """Pantalla de inicio con accesos rápidos a los módulos (look corporativo para PC)"""

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
    # CSS para botones como tarjetas (SOLO HOME DESKTOP)
    # =========================
    st.markdown("""
    <style>
    /* =========================================================
       ELIMINAR TODO EL PADDING SUPERIOR - AGRESIVO
       ========================================================= */
    /* Cuando estamos en home desktop, eliminar TODOS los paddings superiores */
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
    
    /* MÁS ESPECÍFICO: Todos los selectores posibles para block-container */
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) [data-testid="stMainBlockContainer"],
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .block-container,
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) div.block-container {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* Eliminar gap y padding de vertical blocks también */
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stVerticalBlock,
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) [data-testid="stVerticalBlock"] {
        padding-top: 0 !important;
        margin-top: 0 !important;
        gap: 0 !important;
    }
    
    /* Oculta el título "Inicio" de Streamlit */
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) h1 {
        display: none !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* =========================================================
       SOLO HOME DESKTOP (scoped): si el marcador existe, aplico estilos
       ========================================================= */
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) div[data-testid="column"]{
        position: relative; /* el tile se posiciona dentro de la columna */
    }

    /* Botón como tarjeta - TAMAÑOS DIFERENCIADOS */
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button{
        border:1px solid rgba(15,23,42,0.10);
        background:rgba(255,255,255,0.82);
        border-radius:20px;

        /* tamaño base */
        height: 160px;
        min-height: 160px;

        /* espacio para el tile */
        padding:20px 20px 20px 90px;

        box-shadow:0 10px 24px rgba(2,6,23,0.06);
        cursor:pointer;
        transition:transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease, background 140ms ease;

        width:100%;
        text-align:left;

        white-space: pre-line; /* respeta \n del texto */
        font-size:14.5px;      /* desc más grande */
        font-weight:600;
        color:#334155;
        line-height:1.35;

        display:block;
        position: relative;
        margin:0;
    }

    /* Variaciones de tamaño */
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button.card-inteligencia{
        height: 200px;
        min-height: 200px;
    }
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button.card-operaciones{
        height: 140px;
        min-height: 140px;
    }
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button.card-control{
        height: 140px;
        min-height: 140px;
    }
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button.card-rapida{
        height: 120px;
        min-height: 120px;
        padding:16px 16px 16px 80px;
    }

    /* Recomendado */
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button.recomendado{
        border:2px solid rgba(37,99,235,0.30);
        background:rgba(255,255,255,0.95);
        box-shadow:0 12px 28px rgba(37,99,235,0.10);
    }
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button.recomendado:hover{
        border-color:rgba(37,99,235,0.50);
        box-shadow:0 16px 38px rgba(37,99,235,0.15);
    }

    /* Primera línea como título - MÁS GRANDE */
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button::first-line{
        font-size:18px;
        font-weight:900;
        color:#0f172a;
        letter-spacing:-0.01em;
    }

    /* Hover */
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button:hover{
        transform:translateY(-2px);
        box-shadow:0 14px 34px rgba(2,6,23,0.09);
        border-color:rgba(37,99,235,0.22);
        background:rgba(255,255,255,0.90);
    }
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button:active{
        transform:translateY(0);
        box-shadow:0 10px 24px rgba(2,6,23,0.06);
    }
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button:focus{
        outline:none;
        box-shadow:0 0 0 3px rgba(37,99,235,0.12), 0 10px 24px rgba(2,6,23,0.06);
    }

    /* Tile (ícono) -> MÁS GRANDE y ajustado */
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .fc-home-tile{
        width:60px;
        height:60px;
        border-radius:18px;
        display:flex;
        align-items:center;
        justify-content:center;

        border:1px solid rgba(15,23,42,0.08);
        background:rgba(255,255,255,0.86);
        font-size:30px;

        position:absolute;
        left: 16px;
        top: calc(50% + 80px);          /* <-- AJUSTADO PARA BASE 160px */
        transform: translateY(-50%);
        z-index: 5;

        pointer-events:none; /* no bloquea el click */
        box-shadow:0 10px 18px rgba(2,6,23,0.07);
        user-select:none;
    }

    /* Ajustes de tile por clase */
    .card-inteligencia ~ .fc-home-tile { top: calc(50% + 100px); }
    .card-operaciones ~ .fc-home-tile { top: calc(50% + 70px); }
    .card-control ~ .fc-home-tile { top: calc(50% + 70px); }
    .card-rapida ~ .fc-home-tile { 
        width:50px; height:50px; font-size:26px; border-radius:14px;
        top: calc(50% + 60px);
        left: 14px;
    }

    /* Colores tiles */
    .tile-compras { background:rgba(16,185,129,0.10); border-color:rgba(16,185,129,0.18); }
    .tile-buscador { background:rgba(59,130,246,0.10); border-color:rgba(59,130,246,0.18); }
    .tile-stock { background:rgba(245,158,11,0.12); border-color:rgba(245,158,11,0.22); }
    .tile-dashboard { background:rgba(139,92,246,0.10); border-color:rgba(139,92,246,0.18); }
    .tile-pedidos { background:rgba(2,132,199,0.10); border-color:rgba(2,132,199,0.18); }
    .tile-baja { background:rgba(244,63,94,0.10); border-color:rgba(244,63,94,0.18); }
    .tile-ordenes { background:rgba(100,116,139,0.10); border-color:rgba(100,116,139,0.18); }
    .tile-indicadores { background:rgba(34,197,94,0.10); border-color:rgba(34,197,94,0.18); }

    /* Badge recomendado */
    .badge-recomendado {
        position: absolute;
        top: -8px;
        right: -8px;
        background: rgba(37,99,235,0.90);
        color: white;
        font-size: 10px;
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 10px;
        z-index: 10;
        box-shadow: 0 2px 8px rgba(37,99,235,0.20);
    }

    /* Responsive */
    @media (max-width: 900px){
        div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .fc-home-tile{
            width:48px;
            height:48px;
            border-radius:14px;
            font-size:24px;
            left: 14px;
            top: calc(50% + 56px);      /* <-- BASE MOBILE */
        }
        div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button{
            height: 112px;
            min-height: 112px;
            padding:14px 14px 14px 78px;
        }
        div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button::first-line{
            font-size:15px;
        }
        /* Ajustes mobile */
        .card-inteligencia { height: 140px; min-height: 140px; }
        .card-operaciones { height: 100px; min-height: 100px; }
        .card-control { height: 100px; min-height: 100px; }
        .card-rapida { height: 90px; min-height: 90px; padding:12px 12px 12px 70px; }
        .card-inteligencia ~ .fc-home-tile { top: calc(50% + 70px); }
        .card-operaciones ~ .fc-home-tile { top: calc(50% + 50px); }
        .card-control ~ .fc-home-tile { top: calc(50% + 50px); }
        .card-rapida ~ .fc-home-tile { 
            width:42px; height:42px; font-size:22px; border-radius:12px;
            top: calc(50% + 45px);
            left: 12px;
        }
    }

    /* SIDEBAR LIGHT SOLO EN HOME */
    section[data-testid="stSidebar"] {
      background: #ffffff !important;
      background-color: #ffffff !important;
      background-image: none !important;
      border-right: 1px solid rgba(15,23,42,0.08);
      color: #0f172a !important;
    }

    section[data-testid="stSidebar"] > div,
    div[data-testid="stSidebar"] > div {
      background: #ffffff !important;
      background-color: #ffffff !important;
      backdrop-filter: none !important;
    }

    section[data-testid="stSidebar"] *,
    section[data-testid="stSidebar"] li,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] div,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label {
      color: #0f172a !important;
      background: transparent !important;
    }

    /* Específico para radio buttons */
    section[data-testid="stSidebar"] .stRadio label {
      color: #0f172a !important;
    }

    /* Específico para botones */
    section[data-testid="stSidebar"] .stButton button {
      background: #f1f5f9 !important;
      color: #0f172a !important;
      border: 1px solid #e2e8f0 !important;
    }

    section[data-testid="stSidebar"] .stButton button:hover {
      background: #e2e8f0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # =========================
    # ACCIONES RÁPIDAS
    # =========================
    st.markdown("<div style='max-width:1100px;margin:120px auto 0 auto;'>", unsafe_allow_html=True)
    st.markdown("<div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:0 0 24px 6px;display:flex;align-items:center;gap:8px;'>⚡ Acciones rápidas</div>", unsafe_allow_html=True)

    col_rapida1, col_rapida2, col_rapida3 = st.columns(3)
    with col_rapida1:
        st.markdown('<div class="fc-home-tile tile-compras"></div>', unsafe_allow_html=True)
        if st.button("🔍 Consultar compras\nCompras IA", key="rapida_compras", help="Acceso directo a consultas inteligentes de compras"):
            st.query_params["go"] = "compras"
            st.rerun()
    with col_rapida2:
        st.markdown('<div class="fc-home-tile tile-stock"></div>', unsafe_allow_html=True)
        if st.button("📦 Consultar stock\nStock IA", key="rapida_stock", help="Acceso directo a consultas de inventario"):
            st.query_params["go"] = "stock"
            st.rerun()
    with col_rapida3:
        st.markdown('<div class="fc-home-tile tile-dashboard"></div>', unsafe_allow_html=True)
        if st.button("📊 Ver resumen\nDashboard", key="rapida_dashboard", help="Acceso directo a vista ejecutiva"):
            st.query_params["go"] = "dashboard"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # =========================
    # INTELIGENCIA
    # =========================
    st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)
    st.markdown("<div style='max-width:1100px;margin:0 auto 0 auto;'>", unsafe_allow_html=True)
    st.markdown("<div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:0 0 36px 6px;display:flex;align-items:center;gap:8px;'>🧠 Inteligencia</div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="fc-home-tile tile-compras"><div class="badge-recomendado">⭐ Recomendado</div></div>', unsafe_allow_html=True)
        if st.button("Compras IA\nConsultas inteligentes de compras y gastos", key="compras", help="Análisis avanzado de adquisiciones"):
            st.query_params["go"] = "compras"
            st.rerun()
    with col2:
        st.markdown('<div class="fc-home-tile tile-buscador">🔎</div>', unsafe_allow_html=True)
        if st.button("Buscador IA\nBuscar facturas, artículos y lotes", key="buscador", help="Búsqueda inteligente en todo el sistema"):
            st.query_params["go"] = "buscador"
            st.rerun()
    with col3:
        st.markdown('<div class="fc-home-tile tile-stock">📦</div>', unsafe_allow_html=True)
        if st.button("Stock IA\nConsultar inventario y vencimientos", key="stock", help="Gestión inteligente de existencias"):
            st.query_params["go"] = "stock"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # =========================
    # GESTIÓN OPERATIVA
    # =========================
    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
    st.markdown("<div style='max-width:1100px;margin:0 auto 0 auto;'>", unsafe_allow_html=True)
    st.markdown("<div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:0 0 36px 6px;display:flex;align-items:center;gap:8px;'>⚙️ Gestión operativa</div>", unsafe_allow_html=True)

    col4, col5, col6 = st.columns(3)
    with col4:
        st.markdown('<div class="fc-home-tile tile-pedidos">📄</div>', unsafe_allow_html=True)
        if st.button("Pedidos internos\nGestionar pedidos y solicitudes", key="pedidos", help="Administración de pedidos internos"):
            st.query_params["go"] = "pedidos"
            st.rerun()
    with col5:
        st.markdown('<div class="fc-home-tile tile-baja">🧾</div>', unsafe_allow_html=True)
        if st.button("Baja de stock\nRegistrar consumo y bajas", key="baja", help="Control de salidas de inventario"):
            st.query_params["go"] = "baja"
            st.rerun()
    with col6:
        st.markdown('<div class="fc-home-tile tile-ordenes">📦</div>', unsafe_allow_html=True)
        if st.button("Órdenes de compra\nGenerar órdenes de compra", key="ordenes", help="Creación de órdenes de adquisición"):
            st.query_params["go"] = "ordenes"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # =========================
    # CONTROL & REPORTING
    # =========================
    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
    st.markdown("<div style='max-width:1100px;margin:0 auto 0 auto;'>", unsafe_allow_html=True)
    st.markdown("<div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:0 0 36px 6px;display:flex;align-items:center;gap:8px;'>📊 Control & reporting</div>", unsafe_allow_html=True)

    col7, col8 = st.columns(2)
    with col7:
        st.markdown('<div class="fc-home-tile tile-dashboard">📊</div>', unsafe_allow_html=True)
        if st.button("Dashboard\nAnálisis y resúmenes ejecutivos", key="dashboard", help="Vista general del negocio"):
            st.query_params["go"] = "dashboard"
            st.rerun()
    with col8:
        st.markdown('<div class="fc-home-tile tile-indicadores">📈</div>', unsafe_allow_html=True)
        if st.button("Indicadores\nPower BI - Análisis avanzado", key="indicadores", help="Reportes detallados y KPIs"):
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
        <div style="max-width:1100px;margin:40px auto 0 auto;">
            <div style="
                background: rgba(255,255,255,0.70);
                border: 1px solid rgba(15,23,42,0.10);
                border-left: 4px solid rgba(37,99,235,0.55);
                border-radius: 16px;
                padding: 14px 16px;
                box-shadow: 0 10px 26px rgba(2,6,23,0.06);
            ">
                <p style="margin:0;color:#0b3b60;font-size:14px;font-weight:600;">
                    {tip}
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
