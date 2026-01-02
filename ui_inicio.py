# =========================
# UI_INICIO.PY - PANTALLA DE INICIO CON ACCESOS RÁPIDOS (CORPORATIVO)
# =========================

import streamlit as st
from datetime import datetime
import random


def mostrar_inicio():
    """Pantalla de inicio con accesos rápidos a los módulos (look corporativo)"""

    # Obtener nombre del usuario
    user = st.session_state.get("user", {})
    nombre = user.get("nombre", "Usuario")

    # Saludo según hora del día
    hora = datetime.now().hour
    if hora < 12:
        saludo = "¡Buenos días"
    elif hora < 19:
        saludo = "¡Buenas tardes"
    else:
        saludo = "¡Buenas noches"

    # =========================
    # CSS (solo para Inicio)
    # =========================
    st.markdown(
        """
        <style>
        .fc-home-wrap{
            max-width: 1100px;
            margin: 0 auto;
        }

        .fc-home-hero{
            text-align: center;
            padding: 10px 0 18px 0;
        }
        .fc-home-hero h2{
            margin: 0;
            color: #0f172a;
            font-size: 34px;
            font-weight: 800;
            letter-spacing: -0.02em;
        }
        .fc-home-hero p{
            margin: 8px 0 0 0;
            color: #64748b;
            font-size: 16px;
        }

        .fc-section-title{
            color: #64748b;
            font-size: 12px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin: 18px 0 10px 6px;
            display:flex;
            align-items:center;
            gap:8px;
        }

        /* Card container (botón) */
        .fc-card-btn{
            width: 100%;
            height: 100%;
            border: 1px solid rgba(15,23,42,0.10) !important;
            background: rgba(255,255,255,0.72) !important;
            border-radius: 18px !important;
            padding: 16px 16px !important;
            box-shadow: 0 10px 26px rgba(2,6,23,0.06) !important;
            transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
            text-align: left !important;
        }
        .fc-card-btn:hover{
            transform: translateY(-2px);
            box-shadow: 0 14px 34px rgba(2,6,23,0.09) !important;
            border-color: rgba(37,99,235,0.20) !important;
        }

        /* Layout interno */
        .fc-card{
            display:flex;
            align-items:center;
            gap:14px;
        }
        .fc-tile{
            width: 54px;
            height: 54px;
            border-radius: 16px;
            display:flex;
            align-items:center;
            justify-content:center;
            border: 1px solid rgba(15,23,42,0.08);
            background: rgba(255,255,255,0.70);
        }
        .fc-icon{
            font-size: 26px;
            line-height: 1;
        }
        .fc-card-text h3{
            margin: 0;
            color: #0f172a;
            font-size: 16px;
            font-weight: 800;
            letter-spacing: -0.01em;
        }
        .fc-card-text p{
            margin: 3px 0 0 0;
            color: #64748b;
            font-size: 13px;
        }

        /* Variantes suaves por módulo (solo tile) */
        .tile-compras{ background: rgba(16, 185, 129, 0.10); border-color: rgba(16,185,129,0.18); }
        .tile-buscador{ background: rgba(59, 130, 246, 0.10); border-color: rgba(59,130,246,0.18); }
        .tile-stock{ background: rgba(245, 158, 11, 0.12); border-color: rgba(245,158,11,0.22); }
        .tile-dashboard{ background: rgba(139, 92, 246, 0.10); border-color: rgba(139,92,246,0.18); }

        .tile-pedidos{ background: rgba(2, 132, 199, 0.10); border-color: rgba(2,132,199,0.18); }
        .tile-baja{ background: rgba(244, 63, 94, 0.10); border-color: rgba(244,63,94,0.18); }
        .tile-ordenes{ background: rgba(100, 116, 139, 0.10); border-color: rgba(100,116,139,0.18); }
        .tile-indicadores{ background: rgba(34, 197, 94, 0.10); border-color: rgba(34,197,94,0.18); }

        /* Botones de streamlit (solo los de inicio) */
        div[data-testid="stVerticalBlock"] div[data-testid="column"] div.stButton > button{
            white-space: normal !important;
            line-height: 1.25 !important;
        }

        /* Tip box */
        .fc-tip{
            background: rgba(255,255,255,0.70);
            border: 1px solid rgba(15,23,42,0.10);
            border-left: 4px solid rgba(37,99,235,0.55);
            border-radius: 16px;
            padding: 14px 16px;
            box-shadow: 0 10px 26px rgba(2,6,23,0.06);
        }
        .fc-tip p{
            margin: 0;
            color: #0b3b60;
            font-size: 14px;
            font-weight: 600;
        }

        @media (max-width: 768px){
            .fc-home-hero h2{ font-size: 26px; }
            .fc-home-hero p{ font-size: 14px; }
            .fc-card-btn{ padding: 14px 14px !important; }
            .fc-tile{ width: 50px; height: 50px; border-radius: 14px; }
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # =========================
    # Header (saludo)
    # =========================
    st.markdown(
        f"""
        <div class="fc-home-wrap">
            <div class="fc-home-hero">
                <h2>{saludo}, {nombre.split()[0]}! 👋</h2>
                <p>¿Qué querés hacer hoy?</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Helper: render card button
    def _card_button(key: str, icon: str, title: str, desc: str, destino: str, tile_class: str):
        label_html = f"""
        <div class="fc-card">
            <div class="fc-tile {tile_class}">
                <div class="fc-icon">{icon}</div>
            </div>
            <div class="fc-card-text">
                <h3>{title}</h3>
                <p>{desc}</p>
            </div>
        </div>
        """
        if st.button(label_html, key=key, use_container_width=True):
            st.session_state["navegacion_destino"] = destino
            st.rerun()

    # =========================
    # MÓDULOS PRINCIPALES
    # =========================
    st.markdown(
        """
        <div class="fc-home-wrap">
            <div class="fc-section-title">📌 Módulos principales</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        _card_button(
            key="home_card_compras",
            icon="🛒",
            title="Compras IA",
            desc="Consultas inteligentes",
            destino="🛒 Compras IA",
            tile_class="tile-compras",
        )
    with col2:
        _card_button(
            key="home_card_buscador",
            icon="🔎",
            title="Buscador IA",
            desc="Buscar facturas / lotes",
            destino="🔎 Buscador IA",
            tile_class="tile-buscador",
        )
    with col3:
        _card_button(
            key="home_card_stock",
            icon="📦",
            title="Stock IA",
            desc="Consultar inventario",
            destino="📦 Stock IA",
            tile_class="tile-stock",
        )
    with col4:
        _card_button(
            key="home_card_dashboard",
            icon="📊",
            title="Dashboard",
            desc="Ver estadísticas",
            destino="📊 Dashboard",
            tile_class="tile-dashboard",
        )

    st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)

    # =========================
    # GESTIÓN
    # =========================
    st.markdown(
        """
        <div class="fc-home-wrap">
            <div class="fc-section-title">📋 Gestión</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        _card_button(
            key="home_card_pedidos",
            icon="📄",
            title="Pedidos internos",
            desc="Gestionar pedidos",
            destino="📄 Pedidos internos",
            tile_class="tile-pedidos",
        )
    with col6:
        _card_button(
            key="home_card_baja",
            icon="🧾",
            title="Baja de stock",
            desc="Registrar bajas",
            destino="🧾 Baja de stock",
            tile_class="tile-baja",
        )
    with col7:
        _card_button(
            key="home_card_ordenes",
            icon="📦",
            title="Órdenes de compra",
            desc="Crear órdenes",
            destino="📦 Órdenes de compra",
            tile_class="tile-ordenes",
        )
    with col8:
        _card_button(
            key="home_card_indicadores",
            icon="📈",
            title="Indicadores",
            desc="Power BI",
            destino="📈 Indicadores (Power BI)",
            tile_class="tile-indicadores",
        )

    st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)

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
        <div class="fc-home-wrap">
            <div class="fc-tip"><p>{tip}</p></div>
        </div>
        """,
        unsafe_allow_html=True
    )
