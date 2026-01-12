# =========================
# UI_INICIO.PY - PANTALLA DE INICIO CON ACCESOS RÁPIDOS (CORPORATIVO)
# (look similar a la imagen: fondo suave, cards, tiles, secciones y tip)
# =========================

import streamlit as st
from datetime import datetime
import random
import textwrap


def _inyectar_estilos_globales():
    """
    Estilos globales para que el fondo y el layout se parezcan a la captura.
    Nota: Streamlit cambia clases internas entre versiones; por eso apunto a .stApp y body.
    """
    st.markdown(
        """
        <style>
          /* Fondo general tipo "corporativo" */
          html, body, .stApp {
            background:
              radial-gradient(1200px 600px at 50% 10%, rgba(59,130,246,0.10), rgba(255,255,255,0) 60%),
              radial-gradient(900px 500px at 15% 45%, rgba(16,185,129,0.10), rgba(255,255,255,0) 55%),
              radial-gradient(900px 500px at 85% 55%, rgba(139,92,246,0.10), rgba(255,255,255,0) 55%),
              linear-gradient(180deg, #f8fafc 0%, #eef2ff 35%, #f8fafc 100%) !important;
          }

          /* Reduce un poco el padding superior del bloque principal */
          section.main > div {
            padding-top: 0.6rem;
          }

          /* Evita que el contenido quede demasiado angosto */
          .block-container{
            padding-top: 0.5rem;
            padding-bottom: 2.2rem;
            max-width: 1200px;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def mostrar_inicio():
    """Pantalla de inicio con accesos rápidos a los módulos (look corporativo)"""

    _inyectar_estilos_globales()

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

    nombre_corto = (nombre.split()[0] if isinstance(nombre, str) and nombre.strip() else "Usuario")

    # =========================
    # Header (saludo)
    # =========================
    st.markdown(
        f"""
        <div style="max-width:1100px;margin:0 auto;text-align:center;padding:14px 0 18px 0;">
            <div style="color:#0f172a;font-weight:800;font-size:44px;letter-spacing:-0.03em;line-height:1.05;margin:0;">
                FertiChat
            </div>
            <div style="color:#64748b;font-size:14px;margin-top:4px;">
                Sistema de Gestión de Compras
            </div>

            <div style="height:18px;"></div>

            <h2 style="margin:0;color:#0f172a;font-size:40px;font-weight:900;letter-spacing:-0.02em;">
                {saludo}, {nombre_corto}! 👋
            </h2>
            <p style="margin:10px 0 0 0;color:#64748b;font-size:16px;">
                ¿Qué querés hacer hoy?
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # =========================
    # Cards HTML (DIV + onclick)
    # =========================
    cards_html = textwrap.dedent(
        """
        <style>
          .fc-home-wrap{max-width:1100px;margin:0 auto;}

          .fc-section-title{
            color:#64748b;font-size:12px;font-weight:900;text-transform:uppercase;
            letter-spacing:1.2px;margin:18px 0 10px 6px;display:flex;align-items:center;gap:8px;
          }

          .fc-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:22px;}

          .fc-card{
            border:1px solid rgba(15,23,42,0.10);
            background:rgba(255,255,255,0.72);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border-radius:18px;
            padding:18px 18px;
            box-shadow:0 10px 26px rgba(2,6,23,0.06);
            cursor:pointer;
            transition:transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease, background 140ms ease;
            user-select:none;
            height:100%;
          }

          .fc-card:hover{
            transform:translateY(-2px);
            box-shadow:0 16px 38px rgba(2,6,23,0.10);
            border-color:rgba(37,99,235,0.22);
            background:rgba(255,255,255,0.82);
          }

          .fc-card:active{
            transform:translateY(0);
            box-shadow:0 10px 26px rgba(2,6,23,0.06);
          }

          .fc-row{display:flex;align-items:center;gap:14px;}

          .fc-tile{
            width:56px;height:56px;border-radius:18px;
            display:flex;align-items:center;justify-content:center;
            border:1px solid rgba(15,23,42,0.08);
            background:rgba(255,255,255,0.70);
            flex:0 0 56px;
            box-shadow: inset 0 0 0 1px rgba(255,255,255,0.35);
          }

          .fc-ico{font-size:26px;line-height:1;}

          .fc-txt h3{
            margin:0;color:#0f172a;font-size:16px;font-weight:900;letter-spacing:-0.01em;
          }
          .fc-txt p{margin:4px 0 0 0;color:#64748b;font-size:13px;font-weight:600;}

          /* Colores de tiles */
          .tile-compras{background:rgba(16,185,129,0.12);border-color:rgba(16,185,129,0.18);}
          .tile-buscador{background:rgba(59,130,246,0.12);border-color:rgba(59,130,246,0.18);}
          .tile-stock{background:rgba(245,158,11,0.14);border-color:rgba(245,158,11,0.22);}
          .tile-dashboard{background:rgba(139,92,246,0.12);border-color:rgba(139,92,246,0.18);}
          .tile-pedidos{background:rgba(2,132,199,0.12);border-color:rgba(2,132,199,0.18);}
          .tile-baja{background:rgba(244,63,94,0.12);border-color:rgba(244,63,94,0.18);}
          .tile-ordenes{background:rgba(100,116,139,0.12);border-color:rgba(100,116,139,0.18);}
          .tile-indicadores{background:rgba(34,197,94,0.12);border-color:rgba(34,197,94,0.18);}

          @media (max-width: 1100px){
            .fc-grid{grid-template-columns:repeat(2,minmax(0,1fr));}
          }
          @media (max-width: 520px){
            .fc-grid{grid-template-columns:1fr;}
            .fc-tile{width:52px;height:52px;border-radius:16px;flex:0 0 52px;}
            .fc-ico{font-size:24px;}
            .fc-txt h3{font-size:15px;}
            .fc-txt p{font-size:12px;}
          }
        </style>

        <div class="fc-home-wrap">
          <div class="fc-section-title">📌 Módulos principales</div>
          <div class="fc-grid">
            <div class="fc-card" onclick="window.location.href='?go=compras'">
              <div class="fc-row">
                <div class="fc-tile tile-compras"><div class="fc-ico">🛒</div></div>
                <div class="fc-txt"><h3>Compras IA</h3><p>Consultas inteligentes</p></div>
              </div>
            </div>

            <div class="fc-card" onclick="window.location.href='?go=buscador'">
              <div class="fc-row">
                <div class="fc-tile tile-buscador"><div class="fc-ico">🔎</div></div>
                <div class="fc-txt"><h3>Buscador IA</h3><p>Buscar facturas / lotes</p></div>
              </div>
            </div>

            <div class="fc-card" onclick="window.location.href='?go=stock'">
              <div class="fc-row">
                <div class="fc-tile tile-stock"><div class="fc-ico">📦</div></div>
                <div class="fc-txt"><h3>Stock IA</h3><p>Consultar inventario</p></div>
              </div>
            </div>

            <div class="fc-card" onclick="window.location.href='?go=dashboard'">
              <div class="fc-row">
                <div class="fc-tile tile-dashboard"><div class="fc-ico">📊</div></div>
                <div class="fc-txt"><h3>Dashboard</h3><p>Ver estadísticas</p></div>
              </div>
            </div>
          </div>

          <div style="height:22px;"></div>

          <div class="fc-section-title">📋 Gestión</div>
          <div class="fc-grid">
            <div class="fc-card" onclick="window.location.href='?go=pedidos'">
              <div class="fc-row">
                <div class="fc-tile tile-pedidos"><div class="fc-ico">📄</div></div>
                <div class="fc-txt"><h3>Pedidos internos</h3><p>Gestionar pedidos</p></div>
              </div>
            </div>

            <div class="fc-card" onclick="window.location.href='?go=baja'">
              <div class="fc-row">
                <div class="fc-tile tile-baja"><div class="fc-ico">🧾</div></div>
                <div class="fc-txt"><h3>Baja de stock</h3><p>Registrar bajas</p></div>
              </div>
            </div>

            <div class="fc-card" onclick="window.location.href='?go=ordenes'">
              <div class="fc-row">
                <div class="fc-tile tile-ordenes"><div class="fc-ico">📦</div></div>
                <div class="fc-txt"><h3>Órdenes de compra</h3><p>Crear órdenes</p></div>
              </div>
            </div>

            <div class="fc-card" onclick="window.location.href='?go=indicadores'">
              <div class="fc-row">
                <div class="fc-tile tile-indicadores"><div class="fc-ico">📈</div></div>
                <div class="fc-txt"><h3>Indicadores</h3><p>Power BI</p></div>
              </div>
            </div>
          </div>
        </div>
        """
    ).strip()

    st.markdown(cards_html, unsafe_allow_html=True)

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
                background: rgba(255,255,255,0.72);
                backdrop-filter: blur(8px);
                -webkit-backdrop-filter: blur(8px);
                border: 1px solid rgba(15,23,42,0.10);
                border-left: 4px solid rgba(37,99,235,0.55);
                border-radius: 16px;
                padding: 14px 16px;
                box-shadow: 0 10px 26px rgba(2,6,23,0.06);
            ">
                <p style="margin:0;color:#0b3b60;font-size:14px;font-weight:700;">
                    {tip}
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
