# =========================
# UI_INICIO.PY - PANTALLA DE INICIO CON ACCESOS RÁPIDOS (CORPORATIVO)
# VERSIÓN CON BOTONES STREAMLIT - CLICKS 100% CONFIABLES
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
    # CSS PARA TARJETAS CON BOTONES
    # =========================
    st.markdown("""
    <style>
      /* Ocultar label de botones */
      .element-container:has(.stButton) + .element-container:has(.stButton) {
        margin-top: 0 !important;
      }
      
      /* Estilos para las tarjetas */
      div[data-testid="column"] > div > div > div > div.stButton > button {
        border: 1px solid rgba(15,23,42,0.10);
        background: rgba(255,255,255,0.72);
        border-radius: 18px;
        padding: 16px 16px;
        box-shadow: 0 10px 26px rgba(2,6,23,0.06);
        cursor: pointer;
        transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
        user-select: none;
        width: 100%;
        height: 80px;
        text-align: left;
        font-size: 16px;
        font-weight: 800;
        color: #0f172a;
        letter-spacing: -0.01em;
      }
      
      div[data-testid="column"] > div > div > div > div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 14px 34px rgba(2,6,23,0.09);
        border-color: rgba(37,99,235,0.20);
      }
      
      div[data-testid="column"] > div > div > div > div.stButton > button:active {
        transform: translateY(0);
        box-shadow: 0 10px 26px rgba(2,6,23,0.06);
      }

      @media (max-width: 768px) {
        div[data-testid="column"] > div > div > div > div.stButton > button {
          height: 75px;
          font-size: 15px;
          padding: 14px;
        }
      }
    </style>
    """, unsafe_allow_html=True)

    # =========================
    # MÓDULOS PRINCIPALES
    # =========================
    st.markdown("""
    <div style="max-width:1100px;margin:0 auto;">
        <div style="color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;
                    letter-spacing:1px;margin:18px 0 10px 6px;display:flex;align-items:center;gap:8px;">
            📌 Módulos principales
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🛒 **Compras IA**\n\nConsultas inteligentes", key="btn_compras", use_container_width=True):
            st.session_state["radio_menu"] = "🛒 Compras IA"
            st.rerun()
    
    with col2:
        if st.button("🔎 **Buscador IA**\n\nBuscar facturas / lotes", key="btn_buscador", use_container_width=True):
            st.session_state["radio_menu"] = "🔎 Buscador IA"
            st.rerun()
    
    with col3:
        if st.button("📦 **Stock IA**\n\nConsultar inventario", key="btn_stock", use_container_width=True):
            st.session_state["radio_menu"] = "📦 Stock IA"
            st.rerun()
    
    with col4:
        if st.button("📊 **Dashboard**\n\nVer estadísticas", key="btn_dashboard", use_container_width=True):
            st.session_state["radio_menu"] = "📊 Dashboard"
            st.rerun()

    st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)

    # =========================
    # GESTIÓN
    # =========================
    st.markdown("""
    <div style="max-width:1100px;margin:0 auto;">
        <div style="color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;
                    letter-spacing:1px;margin:18px 0 10px 6px;display:flex;align-items:center;gap:8px;">
            📋 Gestión
        </div>
    </div>
    """, unsafe_allow_html=True)

    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        if st.button("📄 **Pedidos internos**\n\nGestionar pedidos", key="btn_pedidos", use_container_width=True):
            st.session_state["radio_menu"] = "📄 Pedidos internos"
            st.rerun()
    
    with col6:
        if st.button("🧾 **Baja de stock**\n\nRegistrar bajas", key="btn_baja", use_container_width=True):
            st.session_state["radio_menu"] = "🧾 Baja de stock"
            st.rerun()
    
    with col7:
        if st.button("📦 **Órdenes de compra**\n\nCrear órdenes", key="btn_ordenes", use_container_width=True):
            st.session_state["radio_menu"] = "📦 Órdenes de compra"
            st.rerun()
    
    with col8:
        if st.button("📈 **Indicadores**\n\nPower BI", key="btn_indicadores", use_container_width=True):
            st.session_state["radio_menu"] = "📈 Indicadores (Power BI)"
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
