# =========================
# UI_INICIO.PY - PANTALLA DE INICIO CON ACCESOS RÁPIDOS (CORPORATIVO)
# =========================

import streamlit as st
from datetime import datetime
import random
import textwrap


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
                {saludo}, {nombre.split()[0]}! 👋
            </h2>
            <p style="margin:8px 0 0 0;color:#64748b;font-size:16px;">
                ¿Qué querés hacer hoy?
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # =========================
    # CSS para botones como tarjetas
    # =========================
    st.markdown("""
    <style>
    /* =========================================================
       SOLO HOME: Estilos aplicados únicamente a los botones
       que están justo después de un "tile" (icono).
       (Scope con :has() para no romper otros botones del sistema)
       ========================================================= */

    /* Tile (ícono) */
    .fc-home-tile {
        width:54px;
        height:54px;
        border-radius:16px;
        display:flex;
        align-items:center;
        justify-content:center;
        border:1px solid rgba(15,23,42,0.08);
        background:rgba(255,255,255,0.85);
        font-size:26px;

        /* clave: que “se meta” sobre la tarjeta */
        position: relative;
        top: 14px;
        left: 14px;
        z-index: 5;
        margin-bottom: -44px;

        /* clave: no bloquear el click del botón debajo */
        pointer-events: none;

        box-shadow: 0 10px 20px rgba(2,6,23,0.07);
        user-select: none;
    }

    .tile-compras { background:rgba(16,185,129,0.10); border-color:rgba(16,185,129,0.18); }
    .tile-buscador { background:rgba(59,130,246,0.10); border-color:rgba(59,130,246,0.18); }
    .tile-stock { background:rgba(245,158,11,0.12); border-color:rgba(245,158,11,0.22); }
    .tile-dashboard { background:rgba(139,92,246,0.10); border-color:rgba(139,92,246,0.18); }
    .tile-pedidos { background:rgba(2,132,199,0.10); border-color:rgba(2,132,199,0.18); }
    .tile-baja { background:rgba(244,63,94,0.10); border-color:rgba(244,63,94,0.18); }
    .tile-ordenes { background:rgba(100,116,139,0.10); border-color:rgba(100,116,139,0.18); }
    .tile-indicadores { background:rgba(34,197,94,0.10); border-color:rgba(34,197,94,0.18); }

    /* Botón tarjeta SOLO si está inmediatamente después de un tile */
    div[data-testid="element-container"]:has(.fc-home-tile) + div[data-testid="element-container"] .stButton > button {
        border:1px solid rgba(15,23,42,0.10);
        background:rgba(255,255,255,0.78);
        border-radius:18px;

        /* espacio para el tile “superpuesto” */
        padding:18px 18px 16px 84px;
        min-height: 98px;

        box-shadow:0 10px 24px rgba(2,6,23,0.06);
        cursor:pointer;
        transition:transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease, background 140ms ease;
        height: auto;
        width: 100%;

        text-align:left;
        margin: 0;
        white-space: pre-line;

        /* tipografía base (segunda línea) */
        font-size:13.5px;
        font-weight:600;
        color:#334155;
        line-height:1.25;

        display:block;
        position:relative;

        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
    }

    /* Primera línea como “título” (sin tocar tu texto) */
    div[data-testid="element-container"]:has(.fc-home-tile) + div[data-testid="element-container"] .stButton > button::first-line {
        font-size:16px;
        font-weight:800;
        color:#0f172a;
        letter-spacing:-0.01em;
    }

    /* Flechita sutil a la derecha */
    div[data-testid="element-container"]:has(.fc-home-tile) + div[data-testid="element-container"] .stButton > button::after {
        content: "›";
        position:absolute;
        right:14px;
        top:16px;
        font-size:22px;
        color: rgba(100,116,139,0.65);
        transition: transform 140ms ease, color 140ms ease;
    }

    div[data-testid="element-container"]:has(.fc-home-tile) + div[data-testid="element-container"] .stButton > button:hover {
        transform:translateY(-2px);
        box-shadow:0 14px 34px rgba(2,6,23,0.09);
        border-color:rgba(37,99,235,0.22);
        background:rgba(255,255,255,0.86);
    }

    div[data-testid="element-container"]:has(.fc-home-tile) + div[data-testid="element-container"] .stButton > button:hover::after {
        transform: translateX(2px);
        color: rgba(37,99,235,0.85);
    }

    div[data-testid="element-container"]:has(.fc-home-tile) + div[data-testid="element-container"] .stButton > button:active {
        transform:translateY(0);
        box-shadow:0 10px 24px rgba(2,6,23,0.06);
    }

    div[data-testid="element-container"]:has(.fc-home-tile) + div[data-testid="element-container"] .stButton > button:focus {
        outline: none;
        box-shadow: 0 0 0 3px rgba(37,99,235,0.12), 0 10px 24px rgba(2,6,23,0.06);
    }

    /* Responsive */
    @media (max-width: 900px) {
        .fc-home-tile {
            width:48px;
            height:48px;
            border-radius:14px;
            font-size:24px;
            top: 12px;
            left: 12px;
            margin-bottom: -38px;
        }
        div[data-testid="element-container"]:has(.fc-home-tile) + div[data-testid="element-container"] .stButton > button {
            padding:16px 16px 14px 74px;
            min-height: 90px;
        }
        div[data-testid="element-container"]:has(.fc-home-tile) + div[data-testid="element-container"] .stButton > button::first-line {
            font-size:15px;
        }
    }

    /* (Dejo tus clases por si las usás después) */
    .btn-title {
        margin: 0;
        font-size:16px;
        font-weight:800;
        letter-spacing:-0.01em;
    }
    .btn-desc {
        margin: 0;
        font-size:13px;
        color:#64748b;
        font-weight: normal;
    }
    </style>
    """, unsafe_allow_html=True)

    # =========================
    # Secciones con botones
    # =========================
    st.markdown("<div style='max-width:1100px;margin:0 auto;'><div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:18px 0 10px 6px;display:flex;align-items:center;gap:8px;'>📌 Módulos principales</div></div>", unsafe_allow_html=True)

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

    st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)
    st.markdown("<div style='max-width:1100px;margin:0 auto;'><div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:18px 0 10px 6px;display:flex;align-items:center;gap:8px;'>📋 Gestión</div></div>", unsafe_allow_html=True)

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
        <div style="max-width:1100px;margin:16px auto 0 auto;">
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
