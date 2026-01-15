# =========================
# UI_INICIO_MOBILE.PY - PANTALLA DE INICIO PARA CELULAR (CORPORATIVO)
# =========================

import streamlit as st
from datetime import datetime
import random
import textwrap


def mostrar_inicio_mobile():
    """Pantalla de inicio con accesos rápidos a los módulos (look corporativo para celular)"""

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
    # Header (saludo) - MÁS COMPACTO
    # =========================
    st.markdown(
        f"""
        <div style="max-width:600px;margin:0 auto;text-align:center;padding:8px 0 14px 0;">
            <h2 style="margin:0;color:#0f172a;font-size:26px;font-weight:800;letter-spacing:-0.02em;">
                {saludo}, {nombre.split()[0]}! 👋
            </h2>
            <p style="margin:6px 0 0 0;color:#64748b;font-size:14px;">
                ¿Qué querés hacer hoy?
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # =========================
    # MARCADOR MOBILE (para aplicar CSS SOLO en esta pantalla)
    # =========================
    st.markdown('<div id="fc-home-mobile-marker" style="display:none;"></div>', unsafe_allow_html=True)

    # =========================
    # CSS para botones como tarjetas (SOLO HOME MOBILE)
    # =========================
    st.markdown("""
    <style>
    /* =========================================================
       SOLO HOME (scoped): si el marcador existe, aplico estilos
       ========================================================= */
    div[data-testid="stAppViewContainer"]:has(#fc-home-mobile-marker) div[data-testid="column"]{
        position: relative; /* el tile se posiciona dentro de la columna */
    }

    /* Botón como tarjeta (MÁS COMPACTO PARA MOBILE) */
    div[data-testid="stAppViewContainer"]:has(#fc-home-mobile-marker) .stButton > button{
        border:1px solid rgba(15,23,42,0.10);
        background:rgba(255,255,255,0.82);
        border-radius:16px;

        /* Más compacto */
        height: 80px;
        min-height: 80px;

        /* Menos padding */
        padding:12px 12px 12px 72px;

        box-shadow:0 8px 20px rgba(2,6,23,0.06);
        cursor:pointer;
        transition:transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease, background 140ms ease;

        width:100% !important;
        max-width: 100% !important;
        text-align:left;

        white-space: pre-line;
        font-size:12.5px;
        font-weight:600;
        color:#334155;
        line-height:1.3;

        display:block;
        position: relative;
        margin:0 0 8px 0;  /* Espacio entre tarjetas */
    }

    /* Recomendado (Compras IA) - Señal visual sutil */
    div[data-testid="stAppViewContainer"]:has(#fc-home-mobile-marker) .stButton:has(button[key="compras"]) > button {
        border:2px solid rgba(37,99,235,0.30);
        background:rgba(255,255,255,0.95);
        box-shadow:0 12px 28px rgba(37,99,235,0.10);
    }
    div[data-testid="stAppViewContainer"]:has(#fc-home-mobile-marker) .stButton:has(button[key="compras"]) > button:hover {
        border-color:rgba(37,99,235,0.50);
        box-shadow:0 16px 38px rgba(37,99,235,0.15);
    }

    /* Primera línea como título - más pequeño */
    div[data-testid="stAppViewContainer"]:has(#fc-home-mobile-marker) .stButton > button::first-line{
        font-size:14.5px;
        font-weight:900;
        color:#0f172a;
        letter-spacing:-0.01em;
    }

    /* Hover */
    div[data-testid="stAppViewContainer"]:has(#fc-home-mobile-marker) .stButton > button:hover{
        transform:translateY(-2px);
        box-shadow:0 14px 34px rgba(2,6,23,0.09);
        border-color:rgba(37,99,235,0.22);
        background:rgba(255,255,255,0.90);
    }
    div[data-testid="stAppViewContainer"]:has(#fc-home-mobile-marker) .stButton > button:active{
        transform:translateY(0);
        box-shadow:0 10px 24px rgba(2,6,23,0.06);
    }
    div[data-testid="stAppViewContainer"]:has(#fc-home-mobile-marker) .stButton > button:focus{
        outline:none;
        box-shadow:0 0 0 3px rgba(37,99,235,0.12), 0 10px 24px rgba(2,6,23,0.06);
    }

    /* Tile (ícono) -> más pequeño y mejor posicionado */
    div[data-testid="stAppViewContainer"]:has(#fc-home-mobile-marker) .fc-home-tile{
        width:46px;
        height:46px;
        border-radius:13px;
        display:flex;
        align-items:center;
        justify-content:center;

        border:1px solid rgba(15,23,42,0.08);
        background:rgba(255,255,255,0.86);
        font-size:22px;

        position:absolute;
        left: 12px;
        top: 50%;
        transform: translateY(-50%);
        z-index: 5;

        pointer-events:none;
        box-shadow:0 8px 16px rgba(2,6,23,0.07);
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

    /* Responsive - pantallas muy pequeñas */
    @media (max-width: 400px){
        div[data-testid="stAppViewContainer"]:has(#fc-home-mobile-marker) .fc-home-tile{
            width:42px;
            height:42px;
            border-radius:12px;
            font-size:20px;
            left: 10px;
        }
        div[data-testid="stAppViewContainer"]:has(#fc-home-mobile-marker) .stButton > button{
            height: 76px;
            min-height: 76px;
            padding:10px 10px 10px 64px;
            font-size:12px;
        }
        div[data-testid="stAppViewContainer"]:has(#fc-home-mobile-marker) .stButton > button::first-line{
            font-size:13.5px;
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
    # Secciones con botones - 2 COLUMNAS COMPACTAS
    # =========================
    st.markdown("<div style='max-width:600px;margin:0 auto;'><div style='color:#64748b;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:12px 0 8px 8px;display:flex;align-items:center;gap:6px;'>📌 Inteligencia y consulta</div></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="small")
    with col1:
        st.markdown('<div class="fc-home-tile tile-compras">🛒</div>', unsafe_allow_html=True)
        if st.button("Compras IA\nConsultas inteligentes de compras y gastos", key="compras"):
            st.query_params["go"] = "compras"
            st.rerun()
        
        st.markdown('<div class="fc-home-tile tile-stock">📦</div>', unsafe_allow_html=True)
        if st.button("Stock IA\nConsultar inventario, stock y vencimientos completos", key="stock"):
            st.query_params["go"] = "stock"
            st.rerun()
    
    with col2:
        st.markdown('<div class="fc-home-tile tile-buscador">🔎</div>', unsafe_allow_html=True)
        if st.button("Buscador IA\nBuscar facturas, artículos y lotes detalladamente", key="buscador"):
            st.query_params["go"] = "buscador"
            st.rerun()
        
        st.markdown('<div class="fc-home-tile tile-dashboard">📊</div>', unsafe_allow_html=True)
        if st.button("Dashboard\nAnálisis y resúmenes ejecutivos avanzados", key="dashboard"):
            st.query_params["go"] = "dashboard"
            st.rerun()

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    st.markdown("<div style='max-width:600px;margin:0 auto;'><div style='color:#64748b;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:12px 0 8px 8px;display:flex;align-items:center;gap:6px;'>⚙️ Gestión operativa</div></div>", unsafe_allow_html=True)

    col3, col4 = st.columns(2, gap="small")
    with col3:
        st.markdown('<div class="fc-home-tile tile-pedidos">📄</div>', unsafe_allow_html=True)
        if st.button("Pedidos internos\nGestionar pedidos y solicitudes completas", key="pedidos"):
            st.query_params["go"] = "pedidos"
            st.rerun()
        
        st.markdown('<div class="fc-home-tile tile-ordenes">📦</div>', unsafe_allow_html=True)
        if st.button("Órdenes de compra\nGenerar órdenes de compra detalladas", key="ordenes"):
            st.query_params["go"] = "ordenes"
            st.rerun()
    
    with col4:
        st.markdown('<div class="fc-home-tile tile-baja">🧾</div>', unsafe_allow_html=True)
        if st.button("Baja de stock\nRegistrar consumo y bajas completas", key="baja"):
            st.query_params["go"] = "baja"
            st.rerun()
        
        st.markdown('<div class="fc-home-tile tile-indicadores">📈</div>', unsafe_allow_html=True)
        if st.button("Indicadores\nPower BI - Análisis avanzado completo", key="indicadores"):
            st.query_params["go"] = "indicadores"
            st.rerun()

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
        <div style="max-width:600px;margin:20px auto 0 auto;padding:0 8px;">
            <div style="
                background: rgba(255,255,255,0.70);
                border: 1px solid rgba(15,23,42,0.10);
                border-left: 4px solid rgba(37,99,235,0.55);
                border-radius: 14px;
                padding: 12px 14px;
                box-shadow: 0 8px 20px rgba(2,6,23,0.06);
            ">
                <p style="margin:0;color:#0b3b60;font-size:13px;font-weight:600;line-height:1.4;">
                    {tip}
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
