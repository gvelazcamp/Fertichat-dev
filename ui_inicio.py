# =========================
# UI_INICIO.PY - FIX RENDER HTML (NO SE VEA COMO CÓDIGO)
# SOLO CAMBIA: import + cards_html = dedent(...)
# =========================

import streamlit as st
from datetime import datetime
import random
import textwrap  # ✅ NUEVO


def mostrar_inicio():
    # ... tu código de saludo igual ...

    # =========================
    # Cards HTML - SIN SCRIPT TAG
    # (✅ FIX: dedent + lstrip para que Streamlit renderice HTML)
    # =========================
    cards_html = textwrap.dedent("""
    <style>
      .fc-home-wrap{max-width:1100px;margin:0 auto;}
      .fc-section-title{
        color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;
        letter-spacing:1px;margin:18px 0 10px 6px;display:flex;align-items:center;gap:8px;
      }
      .fc-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:22px;}

      .fc-card-link{
        text-decoration:none !important;
        color:inherit !important;
        display:block;
      }

      .fc-card{
        border:1px solid rgba(15,23,42,0.10);
        background:rgba(255,255,255,0.72);
        border-radius:18px;
        padding:16px 16px;
        box-shadow:0 10px 26px rgba(2,6,23,0.06);
        cursor:pointer;
        transition:transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
        user-select:none;
        height:100%;
      }
      .fc-card:hover{
        transform:translateY(-2px);
        box-shadow:0 14px 34px rgba(2,6,23,0.09);
        border-color:rgba(37,99,235,0.20);
      }
      .fc-card:active{
        transform:translateY(0);
        box-shadow:0 10px 26px rgba(2,6,23,0.06);
      }
      .fc-row{display:flex;align-items:center;gap:14px;}
      .fc-tile{
        width:54px;height:54px;border-radius:16px;display:flex;align-items:center;justify-content:center;
        border:1px solid rgba(15,23,42,0.08);background:rgba(255,255,255,0.70);
        flex:0 0 54px;
      }
      .fc-ico{font-size:26px;line-height:1;}
      .fc-txt h3{
        margin:0;color:#0f172a;font-size:16px;font-weight:800;letter-spacing:-0.01em;
      }
      .fc-txt p{margin:3px 0 0 0;color:#64748b;font-size:13px;}

      .tile-compras{background:rgba(16,185,129,0.10);border-color:rgba(16,185,129,0.18);}

      @media (max-width: 980px){
        .fc-grid{grid-template-columns:repeat(2,minmax(0,1fr));}
      }
      @media (max-width: 520px){
        .fc-grid{grid-template-columns:1fr;}
        .fc-tile{width:50px;height:50px;border-radius:14px;flex:0 0 50px;}
        .fc-ico{font-size:24px;}
        .fc-txt h3{font-size:15px;}
        .fc-txt p{font-size:12px;}
      }
    </style>

    <div class="fc-home-wrap">
      <div class="fc-section-title">📌 Módulos principales</div>
      <div class="fc-grid">

        <!-- SOLO COMPRAS (click por href, sin JS inline) -->
        <a class="fc-card-link" href="?go=compras">
          <div class="fc-card">
            <div class="fc-row">
              <div class="fc-tile tile-compras"><div class="fc-ico">🛒</div></div>
              <div class="fc-txt"><h3>Compras IA</h3><p>Consultas inteligentes</p></div>
            </div>
          </div>
        </a>

      </div>
    </div>
    """).lstrip()

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
