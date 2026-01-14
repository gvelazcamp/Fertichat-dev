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

    /* Botón como tarjeta (MUCHO MÁS GRANDE) */
    div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button{
        border:1px solid rgba(15,23,42,0.10);
        background:rgba(255,255,255,0.82);
        border-radius:20px;

        /* tamaño fijo MUCHO MÁS ALTO */
        height: 140px;
        min-height: 140px;

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
        top: calc(50% + 70px);          /* <-- AJUSTADO PARA 140px */
        transform: translateY(-50%);
        z-index: 5;

        pointer-events:none; /* no bloquea el click */
        box-shadow:0 10px 18px rgba(2,6,23,0.07);
        user-select:none;
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

    /* Responsive */
    @media (max-width: 900px){
        div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .fc-home-tile{
            width:48px;
            height:48px;
            border-radius:14px;
            font-size:24px;
            left: 14px;
            top: calc(50% + 44px);      /* <-- BAJADO ~0.5cm MÁS MOBILE */
        }
        div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button{
            height: 92px;
            min-height: 92px;
            padding:14px 14px 14px 78px;
        }
        div[data-testid="stAppViewContainer"]:has(#fc-home-desktop-marker) .stButton > button::first-line{
            font-size:15px;
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
    # Secciones con botones - CON CSS PADDING CERO + MARGEN NEGATIVO
    # =========================
    st.markdown("<div style='max-width:1100px;margin:-80px auto 0 auto;'>", unsafe_allow_html=True)
    st.markdown("<div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:0 0 10px 6px;display:flex;align-items:center;gap:8px;'>📌 Módulos principales</div>", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown('<div class="fc-home-tile tile-compras">🛒</div>', unsafe_allow_html=True)
        if st.button("Compras IA\nConsultas inteligentes", key="compras"):
            st.query_params["go"] = "compras"
            st.rerun()
    with col2:
        st.markdown('<div class="fc-home-tile tile-buscador">🔎</div>', unsafe_allow_html=True)
        if st.button("Buscador IA\nBuscar facturas / lotes", key="buscador"):
            st.query_params["go"] = "buscador"
            st.rerun()
    with col3:
        st.markdown('<div class="fc-home-tile tile-stock">📦</div>', unsafe_allow_html=True)
        if st.button("Stock IA\nConsultar inventario", key="stock"):
            st.query_params["go"] = "stock"
            st.rerun()
    with col4:
        st.markdown('<div class="fc-home-tile tile-dashboard">📊</div>', unsafe_allow_html=True)
        if st.button("Dashboard\nVer estadísticas", key="dashboard"):
            st.query_params["go"] = "dashboard"
            st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)  # Cierra el contenedor con margen negativo

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    st.markdown("<div style='max-width:1100px;margin:-30px auto 0 auto;'>", unsafe_allow_html=True)
    st.markdown("<div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:0 0 10px 6px;display:flex;align-items:center;gap:8px;'>📋 Gestión</div>", unsafe_allow_html=True)

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.markdown('<div class="fc-home-tile tile-pedidos">📄</div>', unsafe_allow_html=True)
        if st.button("Pedidos internos\nGestionar pedidos", key="pedidos"):
            st.query_params["go"] = "pedidos"
            st.rerun()
    with col6:
        st.markdown('<div class="fc-home-tile tile-baja">🧾</div>', unsafe_allow_html=True)
        if st.button("Baja de stock\nRegistrar bajas", key="baja"):
            st.query_params["go"] = "baja"
            st.rerun()
    with col7:
        st.markdown('<div class="fc-home-tile tile-ordenes">📦</div>', unsafe_allow_html=True)
        if st.button("Órdenes de compra\nCrear órdenes", key="ordenes"):
            st.query_params["go"] = "ordenes"
            st.rerun()
    with col8:
        st.markdown('<div class="fc-home-tile tile-indicadores">📈</div>', unsafe_allow_html=True)
        if st.button("Indicadores\nPower BI", key="indicadores"):
            st.query_params["go"] = "indicadores"
            st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)  # Cierra el contenedor con margen negativo

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
        <div style="max-width:1100px;margin:-10px auto 0 auto;">
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
