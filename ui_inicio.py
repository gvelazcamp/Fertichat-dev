# =========================
# UI_INICIO.   PY - PANTALLA DE INICIO CON ACCESOS RÁPIDOS (CORPORATIVO)
# =========================

import streamlit as st
from datetime import datetime
import random
import streamlit. components.v1 as components


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
        <div style="max-width: 1100px;margin:0 auto;text-align:center;padding:10px 0 18px 0;">
            <h2 style="margin:0;color:#0f172a;font-size:34px;font-weight:800;letter-spacing:-0.02em;">
                {saludo}, {nombre.  split()[0]}!  👋
            </h2>
            <p style="margin:8px 0 0 0;color:#64748b;font-size:16px;">
                ¿Qué querés hacer hoy? 
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # =========================
    # CSS (MISMO DE SIEMPRE - NO TOCAR)
    # =========================
    st.markdown("""
    <style>
    .block-container{
        padding-left: 0. 65rem ! important;
        padding-right: 0.65rem !important;
    }

    /* Tarjeta móvil - MISMO TAMAÑO FORZADO */
    .fc-mcard{
        display:flex;
        align-items:center;
        gap:14px;

        width:100%;
        box-sizing:border-box;

        height:  104px;
        min-height:  104px;
        max-height:  104px;

        border-radius:20px;
        border:  1px solid rgba(15,23,42,0.10);
        background:rgba(255,255,255,0.88);
        box-shadow:  0 10px 24px rgba(2,6,23,0.06);

        padding:14px 14px;
        cursor:pointer;
        transition:transform 140ms ease, box-shadow 140ms ease;
        margin-bottom:  14px;
    }

    .fc-mcard:active{
        transform:scale(0.98);
    }

    /* icon */
    .fc-micon{
        width:54px;
        height:54px;
        border-radius:16px;
        display:flex;
        align-items:center;
        justify-content:center;
        font-size:26px;

        border:  1px solid rgba(15,23,42,0.08);
        background:rgba(255,255,255,0.90);
        box-shadow: 0 10px 18px rgba(2,6,23,0.07);

        flex:   0 0 54px;
    }

    /* text block */
    .fc-mtxt{
        display:flex;
        flex-direction:column;
        gap:4px;
        min-width:0;
    }

    . fc-mtitle{
        margin:  0;
        font-size:16px;
        font-weight: 900;
        color:#0f172a;
        line-height:1.05;
    }

    .fc-msub{
        margin:  0;
        font-size:  13px;
        font-weight:600;
        color:#64748b;
        line-height:1.2;
    }

    /* Colores tiles */
    .tile-compras { background:  rgba(16,185,129,0.10); border-color: rgba(16,185,129,0.18); }
    .tile-buscador { background:  rgba(59,130,246,0.10); border-color: rgba(59,130,246,0.18); }
    .tile-stock { background:rgba(245,158,11,0.12); border-color:rgba(245,158,11,0.22); }
    .tile-dashboard { background:rgba(139,92,246,0.10); border-color:rgba(139,92,246,0.18); }
    .tile-pedidos { background:rgba(2,132,199,0.10); border-color:rgba(2,132,199,0.18); }
    .tile-baja { background:rgba(244,63,94,0.10); border-color:rgba(244,63,94,0.18); }
    .tile-ordenes { background:rgba(100,116,139,0.10); border-color:rgba(100,116,139,0.18); }
    .tile-indicadores { background:rgba(34,197,94,0.10); border-color:rgba(34,197,94,0.18); }
    </style>
    """, unsafe_allow_html=True)

    # =========================
    # TARJETAS CON JAVASCRIPT QUE SÍ FUNCIONA
    # =========================
    st. markdown(
        "<div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:18px 0 10px 6px;'>📌 Módulos principales</div>",
        unsafe_allow_html=True
    )

    components.html("""
    <div class="fc-mcard" onclick="window.parent.location.href='? go=compras'">
        <div class="fc-micon tile-compras">🛒</div>
        <div class="fc-mtxt">
            <p class="fc-mtitle">Compras IA</p>
            <p class="fc-msub">Consultas inteligentes</p>
        </div>
    </div>
    
    <div class="fc-mcard" onclick="window.parent. location.href='?go=buscador'">
        <div class="fc-micon tile-buscador">🔎</div>
        <div class="fc-mtxt">
            <p class="fc-mtitle">Buscador IA</p>
            <p class="fc-msub">Buscar facturas / lotes</p>
        </div>
    </div>
    
    <div class="fc-mcard" onclick="window.parent.location.href='?go=stock'">
        <div class="fc-micon tile-stock">📦</div>
        <div class="fc-mtxt">
            <p class="fc-mtitle">Stock IA</p>
            <p class="fc-msub">Consultar inventario</p>
        </div>
    </div>
    
    <div class="fc-mcard" onclick="window. parent.location.href='?go=dashboard'">
        <div class="fc-micon tile-dashboard">📊</div>
        <div class="fc-mtxt">
            <p class="fc-mtitle">Dashboard</p>
            <p class="fc-msub">Ver estadísticas</p>
        </div>
    </div>
    """, height=500)

    st.markdown(
        "<div style='color:#64748b;font-size: 12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin: 18px 0 10px 6px;'>📋 Gestión</div>",
        unsafe_allow_html=True
    )

    components.html("""
    <div class="fc-mcard" onclick="window.parent.location.href='?go=pedidos'">
        <div class="fc-micon tile-pedidos">📄</div>
        <div class="fc-mtxt">
            <p class="fc-mtitle">Pedidos internos</p>
            <p class="fc-msub">Gestionar pedidos</p>
        </div>
    </div>
    
    <div class="fc-mcard" onclick="window.parent.location.href='?go=baja'">
        <div class="fc-micon tile-baja">🧾</div>
        <div class="fc-mtxt">
            <p class="fc-mtitle">Baja de stock</p>
            <p class="fc-msub">Registrar bajas</p>
        </div>
    </div>
    
    <div class="fc-mcard" onclick="window. parent.location.href='?go=ordenes'">
        <div class="fc-micon tile-ordenes">📦</div>
        <div class="fc-mtxt">
            <p class="fc-mtitle">Órdenes de compra</p>
            <p class="fc-msub">Crear órdenes</p>
        </div>
    </div>
    
    <div class="fc-mcard" onclick="window.parent.location.href='?go=indicadores'">
        <div class="fc-micon tile-indicadores">📈</div>
        <div class="fc-mtxt">
            <p class="fc-mtitle">Indicadores</p>
            <p class="fc-msub">Power BI</p>
        </div>
    </div>
    """, height=500)

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
        <div style="max-width:  1100px;margin:16px auto 0 auto;">
            <div style="
                background:  rgba(255,255,255,0.70);
                border: 1px solid rgba(15,23,42,0.10);
                border-left:  4px solid rgba(37,99,235,0.55);
                border-radius: 16px;
                padding: 14px 16px;
                box-shadow:   0 10px 26px rgba(2,6,23,0.06);
            ">
                <p style="margin:0;color:#0b3b60;font-size:14px;font-weight:600;">
                    {tip}
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
