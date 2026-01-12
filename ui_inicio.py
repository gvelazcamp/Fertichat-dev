# =========================
# UI_INICIO.  PY - PANTALLA DE INICIO CON ACCESOS RÁPIDOS (CORPORATIVO)
# =========================

import streamlit as st
from datetime import datetime
import random


def mostrar_inicio():
    """Pantalla de inicio con accesos rápidos a los módulos (look corporativo)"""

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
    # Header (saludo)
    # =========================
    st.markdown(
        f"""
        <div style="max-width:1100px;margin:0 auto;text-align:center;padding:10px 0 18px 0;">
            <h2 style="margin:0;color:#0f172a;font-size:34px;font-weight:800;letter-spacing:-0.02em;">
                {saludo}, {nombre. split()[0]}! 👋
            </h2>
            <p style="margin:8px 0 0 0;color:#64748b;font-size:16px;">
                ¿Qué querés hacer hoy? 
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # =========================
    # MARCADOR (para aplicar CSS SOLO en esta pantalla)
    # =========================
    st.markdown('<div id="fc-home-marker" style="display:none;"></div>', unsafe_allow_html=True)

    # =========================
    # CSS para HOME - BOTONES QUE SE VEN COMO TARJETAS PERFECTAS
    # =========================
    st. markdown("""
    <style>
    /* =========================================================
       SOLO HOME (scoped)
       ========================================================= */
    
    /* Padding ajustado */
    div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .block-container{
        padding-left: 0. 65rem ! important;
        padding-right: 0.65rem !important;
    }

    /* Wrapper del botón full width */
    div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .stButton{
        width:  100% !important;
    }

    /* Botón como tarjeta PERFECTA - MISMO DISEÑO */
    div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .stButton > button{
        /* Layout */
        display: flex ! important;
        align-items:  center !important;
        gap: 14px !important;
        
        /* Tamaño FORZADO */
        width: 100% !important;
        height: 104px !important;
        min-height: 104px !important;
        max-height: 104px !important;
        box-sizing: border-box !important;
        
        /* Estilo */
        border-radius: 20px !important;
        border: 1px solid rgba(15,23,42,0.10) !important;
        background:  rgba(255,255,255,0.88) !important;
        box-shadow: 0 10px 24px rgba(2,6,23,0.06) !important;
        padding: 14px 14px !important;
        
        /* Texto */
        text-align: left !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        color: #64748b !important;
        line-height: 1.2 !important;
        white-space: pre-line !important;
        
        /* Interacción */
        cursor: pointer ! important;
        transition: transform 140ms ease, box-shadow 140ms ease ! important;
        
        margin:  0 ! important;
        overflow: hidden !important;
    }

    div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .stButton > button:active{
        transform: scale(0.98) !important;
    }

    /* Primera línea (título) */
    div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .stButton > button:: first-line{
        font-size: 16px !important;
        font-weight: 900 !important;
        color:  #0f172a !important;
    }

    /* Colores tiles (clases en el container del botón) */
    .tile-compras { background: rgba(16,185,129,0.10) !important; border-color: rgba(16,185,129,0.18) !important; }
    . tile-buscador { background: rgba(59,130,246,0.10) !important; border-color: rgba(59,130,246,0.18) !important; }
    .tile-stock { background: rgba(245,158,11,0.12) !important; border-color:  rgba(245,158,11,0.22) !important; }
    . tile-dashboard { background: rgba(139,92,246,0.10) !important; border-color: rgba(139,92,246,0.18) !important; }
    .tile-pedidos { background: rgba(2,132,199,0.10) !important; border-color: rgba(2,132,199,0.18) !important; }
    .tile-baja { background: rgba(244,63,94,0.10) !important; border-color: rgba(244,63,94,0.18) !important; }
    .tile-ordenes { background: rgba(100,116,139,0.10) !important; border-color: rgba(100,116,139,0.18) !important; }
    .tile-indicadores { background: rgba(34,197,94,0.10) !important; border-color: rgba(34,197,94,0.18) !important; }

    /* Ícono dentro del botón */
    div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .fc-icon{
        width: 54px !important;
        height:  54px !important;
        border-radius: 16px !important;
        display:  flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 26px !important;
        border: 1px solid rgba(15,23,42,0.08) !important;
        background: rgba(255,255,255,0.90) !important;
        box-shadow: 0 10px 18px rgba(2,6,23,0.07) !important;
        flex:  0 0 54px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # =========================
    # LAYOUT con botones Streamlit
    # =========================
    st. markdown(
        "<div style='max-width:1100px;margin:0 auto;'><div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:18px 0 10px 6px;display:flex;align-items:center;gap:8px;'>📌 Módulos principales</div></div>",
        unsafe_allow_html=True
    )

    # Módulo 1: Compras
    st.markdown('<div class="tile-compras"><div class="fc-icon">🛒</div></div>', unsafe_allow_html=True)
    if st.button("Compras IA\nConsultas inteligentes", key="compras"):
        st.query_params["go"] = "compras"
        st.rerun()

    # Módulo 2: Buscador
    st.markdown('<div class="tile-buscador"><div class="fc-icon">🔎</div></div>', unsafe_allow_html=True)
    if st.button("Buscador IA\nBuscar facturas / lotes", key="buscador"):
        st.query_params["go"] = "buscador"
        st.rerun()

    # Módulo 3: Stock
    st.markdown('<div class="tile-stock"><div class="fc-icon">📦</div></div>', unsafe_allow_html=True)
    if st.button("Stock IA\nConsultar inventario", key="stock"):
        st.query_params["go"] = "stock"
        st.rerun()

    # Módulo 4: Dashboard
    st.markdown('<div class="tile-dashboard"><div class="fc-icon">📊</div></div>', unsafe_allow_html=True)
    if st.button("Dashboard\nVer estadísticas", key="dashboard"):
        st.query_params["go"] = "dashboard"
        st.rerun()

    st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)

    st.markdown(
        "<div style='max-width:1100px;margin:0 auto;'><div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:18px 0 10px 6px;display:flex;align-items:center;gap:8px;'>📋 Gestión</div></div>",
        unsafe_allow_html=True
    )

    # Módulo 5: Pedidos
    st.markdown('<div class="tile-pedidos"><div class="fc-icon">📄</div></div>', unsafe_allow_html=True)
    if st.button("Pedidos internos\nGestionar pedidos", key="pedidos"):
        st.query_params["go"] = "pedidos"
        st.rerun()

    # Módulo 6: Baja
    st. markdown('<div class="tile-baja"><div class="fc-icon">🧾</div></div>', unsafe_allow_html=True)
    if st.button("Baja de stock\nRegistrar bajas", key="baja"):
        st.query_params["go"] = "baja"
        st.rerun()

    # Módulo 7: Órdenes
    st.markdown('<div class="tile-ordenes"><div class="fc-icon">📦</div></div>', unsafe_allow_html=True)
    if st.button("Órdenes de compra\nCrear órdenes", key="ordenes"):
        st.query_params["go"] = "ordenes"
        st.rerun()

    # Módulo 8: Indicadores
    st. markdown('<div class="tile-indicadores"><div class="fc-icon">📈</div></div>', unsafe_allow_html=True)
    if st.button("Indicadores\nPower BI", key="indicadores"):
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
    tip = random. choice(tips)

    st.markdown(
        f"""
        <div style="max-width: 1100px;margin:16px auto 0 auto;">
            <div style="
                background:  rgba(255,255,255,0.70);
                border: 1px solid rgba(15,23,42,0.10);
                border-left: 4px solid rgba(37,99,235,0.55);
                border-radius: 16px;
                padding: 14px 16px;
                box-shadow:  0 10px 26px rgba(2,6,23,0.06);
            ">
                <p style="margin:0;color:#0b3b60;font-size:14px;font-weight:600;">
                    {tip}
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
