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
    # CSS para tarjetas y botones invisibles
    # =========================
    st.markdown("""
    <style>
    .fc-card{
      position:relative;
      border:1px solid rgba(15,23,42,0.10);
      background:rgba(255,255,255,0.72);
      border-radius:18px;
      padding:16px 16px;
      box-shadow:0 10px 26px rgba(2,6,23,0.06);
      cursor:pointer;
      transition:transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
      user-select:none;
      height:100%;
      width:100%;
      display: flex;
      align-items: flex-start;
      gap: 14px;
    }
    .fc-card:hover{
      transform:translateY(-2px);
      box-shadow:0 14px 34px rgba(2,6,23,0.09);
      border-color:rgba(37,99,235,0.20);
    }
    .fc-tile{
      width:54px;height:54px;border-radius:16px;display:flex;align-items:center;justify-content:center;
      border:1px solid rgba(15,23,42,0.08);background:rgba(255,255,255,0.70);
      flex:0 0 54px;
    }
    .fc-ico{font-size:26px;line-height:1;}
    .fc-txt .fc-h3{
      margin:0;color:#0f172a;font-size:16px;font-weight:800;letter-spacing:-0.01em;
    }
    .fc-txt p{margin:3px 0 0 0;color:#64748b;font-size:13px;}

    .tile-compras{background:rgba(16,185,129,0.10);border-color:rgba(16,185,129,0.18);}
    .tile-buscador{background:rgba(59,130,246,0.10);border-color:rgba(59,130,246,0.18);}
    .tile-stock{background:rgba(245,158,11,0.12);border-color:rgba(245,158,11,0.22);}
    .tile-dashboard{background:rgba(139,92,246,0.10);border-color:rgba(139,92,246,0.18);}
    .tile-pedidos{background:rgba(2,132,199,0.10);border-color:rgba(2,132,199,0.18);}
    .tile-baja{background:rgba(244,63,94,0.10);border-color:rgba(244,63,94,0.18);}
    .tile-ordenes{background:rgba(100,116,139,0.10);border-color:rgba(100,116,139,0.18);}
    .tile-indicadores{background:rgba(34,197,94,0.10);border-color:rgba(34,197,94,0.18);}

    .stButton > button {
      position:absolute;
      top:0;
      left:0;
      width:100%;
      height:100%;
      opacity:0;
      cursor:pointer;
      border:none;
      background:none;
      z-index:1;
    }

    @media (max-width: 980px){
      .fc-card{display:block;}
    }
    @media (max-width: 520px){
      .fc-tile{width:50px;height:50px;border-radius:14px;flex:0 0 50px;}
      .fc-ico{font-size:24px;}
      .fc-txt .fc-h3{font-size:15px;}
      .fc-txt p{font-size:12px;}
    }
    </style>
    """, unsafe_allow_html=True)

    # =========================
    # Secciones con tarjetas
    # =========================
    st.markdown("<div style='max-width:1100px;margin:0 auto;'><div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:18px 0 10px 6px;display:flex;align-items:center;gap:8px;'>📌 Módulos principales</div></div>", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("""
        <div class="fc-card">
          <div class="fc-tile tile-compras"><div class="fc-ico">🛒</div></div>
          <div class="fc-txt"><div class="fc-h3">Compras IA</div><p>Consultas inteligentes</p></div>
        </div>
        """, unsafe_allow_html=True)
        st.button("", on_click=lambda: (st.query_params.update({"go": "compras"}), st.rerun()), key="btn_compras")
    with col2:
        st.markdown("""
        <div class="fc-card">
          <div class="fc-tile tile-buscador"><div class="fc-ico">🔎</div></div>
          <div class="fc-txt"><div class="fc-h3">Buscador IA</div><p>Buscar facturas / lotes</p></div>
        </div>
        """, unsafe_allow_html=True)
        st.button("", on_click=lambda: (st.query_params.update({"go": "buscador"}), st.rerun()), key="btn_buscador")
    with col3:
        st.markdown("""
        <div class="fc-card">
          <div class="fc-tile tile-stock"><div class="fc-ico">📦</div></div>
          <div class="fc-txt"><div class="fc-h3">Stock IA</div><p>Consultar inventario</p></div>
        </div>
        """, unsafe_allow_html=True)
        st.button("", on_click=lambda: (st.query_params.update({"go": "stock"}), st.rerun()), key="btn_stock")
    with col4:
        st.markdown("""
        <div class="fc-card">
          <div class="fc-tile tile-dashboard"><div class="fc-ico">📊</div></div>
          <div class="fc-txt"><div class="fc-h3">Dashboard</div><p>Ver estadísticas</p></div>
        </div>
        """, unsafe_allow_html=True)
        st.button("", on_click=lambda: (st.query_params.update({"go": "dashboard"}), st.rerun()), key="btn_dashboard")

    st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)
    st.markdown("<div style='max-width:1100px;margin:0 auto;'><div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:18px 0 10px 6px;display:flex;align-items:center;gap:8px;'>📋 Gestión</div></div>", unsafe_allow_html=True)

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.markdown("""
        <div class="fc-card">
          <div class="fc-tile tile-pedidos"><div class="fc-ico">📄</div></div>
          <div class="fc-txt"><div class="fc-h3">Pedidos internos</div><p>Gestionar pedidos</p></div>
        </div>
        """, unsafe_allow_html=True)
        st.button("", on_click=lambda: (st.query_params.update({"go": "pedidos"}), st.rerun()), key="btn_pedidos")
    with col6:
        st.markdown("""
        <div class="fc-card">
          <div class="fc-tile tile-baja"><div class="fc-ico">🧾</div></div>
          <div class="fc-txt"><div class="fc-h3">Baja de stock</div><p>Registrar bajas</p></div>
        </div>
        """, unsafe_allow_html=True)
        st.button("", on_click=lambda: (st.query_params.update({"go": "baja"}), st.rerun()), key="btn_baja")
    with col7:
        st.markdown("""
        <div class="fc-card">
          <div class="fc-tile tile-ordenes"><div class="fc-ico">📦</div></div>
          <div class="fc-txt"><div class="fc-h3">Órdenes de compra</div><p>Crear órdenes</p></div>
        </div>
        """, unsafe_allow_html=True)
        st.button("", on_click=lambda: (st.query_params.update({"go": "ordenes"}), st.rerun()), key="btn_ordenes")
    with col8:
        st.markdown("""
        <div class="fc-card">
          <div class="fc-tile tile-indicadores"><div class="fc-ico">📈</div></div>
          <div class="fc-txt"><div class="fc-h3">Indicadores</div><p>Power BI</p></div>
        </div>
        """, unsafe_allow_html=True)
        st.button("", on_click=lambda: (st.query_params.update({"go": "indicadores"}), st.rerun()), key="btn_indicadores")

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
