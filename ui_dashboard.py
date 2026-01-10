# =========================
# UI_DASHBOARD.PY - MÓDULO DASHBOARD
# =========================

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from config import DEBUG_MODE, POWERBI_URL
from utils_format import _fmt_num_latam, _safe_float
from sql_core import (
    ejecutar_consulta,
    _sql_total_num_expr_general,
)
from sql_stock import (
    get_alertas_vencimiento_multiple,
)

# =========================
# PLACEHOLDER FUNCTIONS (TODO: Implement these in sql_compras or sql_dashboard)
# =========================

def get_dashboard_totales(anio: int) -> dict:
    """Placeholder function - needs implementation"""
    return {'total_pesos': 0, 'total_usd': 0, 'proveedores': 0, 'facturas': 0}

def get_dashboard_compras_por_mes(anio: int) -> pd.DataFrame:
    """Placeholder function - needs implementation"""
    return pd.DataFrame()

def get_dashboard_top_proveedores(anio: int, limite: int, moneda: str) -> pd.DataFrame:
    """Placeholder function - needs implementation"""
    return pd.DataFrame()

def get_dashboard_gastos_familia(anio: int) -> pd.DataFrame:
    """Placeholder function - needs implementation"""
    return pd.DataFrame()

def get_dashboard_ultimas_compras(limite: int) -> pd.DataFrame:
    """Placeholder function - needs implementation"""
    return pd.DataFrame()

# =========================
# 📊 DASHBOARD
# =========================

def mostrar_dashboard():
    """Dashboard con gráficos de compras y stock"""

    st.title("📊 Dashboard")

    # Selector de año
    anio_actual = datetime.now().year
    col_filtro, col_espacio = st.columns([1, 3])
    with col_filtro:
        anio = st.selectbox("Año:", [anio_actual, anio_actual - 1, anio_actual - 2], index=0)

    st.markdown("---")

    # =====================
    # MÉTRICAS PRINCIPALES
    # =====================
    try:
        totales = get_dashboard_totales(anio)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_fmt = f"${totales['total_pesos']:,.0f}".replace(',', '.')
            st.metric("💰 Total Compras $", total_fmt)

        with col2:
            usd_fmt = f"U$S {totales['total_usd']:,.0f}".replace(',', '.')
            st.metric("💵 Total USD", usd_fmt)

        with col3:
            st.metric("🏭 Proveedores", totales['proveedores'])

        with col4:
            st.metric("📄 Facturas", totales['facturas'])
    except Exception as e:
        st.error(f"Error cargando métricas: {e}")

    st.markdown("---")

    # =====================
    # GRÁFICOS EN 2 COLUMNAS
    # =====================
    col_izq, col_der = st.columns(2)

    # GRÁFICO 1: Compras por Mes (Barras)
    with col_izq:
        st.subheader("📈 Compras por Mes")
        try:
            df_meses = get_dashboard_compras_por_mes(anio)
            if df_meses is not None and not df_meses.empty:
                fig_meses = px.bar(
                    df_meses,
                    x='Mes',
                    y='Total',
                    color='Total',
                    color_continuous_scale='Blues',
                    labels={'Total': 'Monto ($)', 'Mes': ''}
                )
                fig_meses.update_layout(
                    showlegend=False,
                    coloraxis_showscale=False,
                    height=350,
                    margin=dict(l=20, r=20, t=30, b=20)
                )
                fig_meses.update_traces(
                    texttemplate='%{y:,.0f}',
                    textposition='outside',
                    textfont_size=10
                )
                st.plotly_chart(fig_meses, use_container_width=True)
            else:
                st.info("No hay datos para este año")
        except Exception as e:
            st.error(f"Error: {e}")

    # GRÁFICO 2: Top Proveedores (por moneda)
    with col_der:
        st.subheader("🏆 Top Proveedores (por moneda)")
        try:
            tabs = st.tabs(["$ Pesos", "U$S USD"])

            with tabs[0]:
                df_provs = get_dashboard_top_proveedores(anio, 10, moneda="$")
                if df_provs is not None and not df_provs.empty:
                    fig_provs = px.bar(
                        df_provs,
                        x='Total',
                        y='Proveedor',
                        orientation='h',
                        color='Total',
                        color_continuous_scale='Oranges',
                        labels={'Total': 'Monto ($)', 'Proveedor': ''}
                    )
                    fig_provs.update_layout(
                        showlegend=False,
                        coloraxis_showscale=False,
                        height=350,
                        margin=dict(l=20, r=20, t=30, b=20)
                    )
                    st.plotly_chart(fig_provs, use_container_width=True)
                else:
                    st.info("No hay datos en $ para este año")

            with tabs[1]:
                df_provs_usd = get_dashboard_top_proveedores(anio, 10, moneda="U$S")
                if df_provs_usd is not None and not df_provs_usd.empty:
                    fig_provs_usd = px.bar(
                        df_provs_usd,
                        x='Total',
                        y='Proveedor',
                        orientation='h',
                        color='Total',
                        color_continuous_scale='Oranges',
                        labels={'Total': 'Monto (U$S)', 'Proveedor': ''}
                    )
                    fig_provs_usd.update_layout(
                        showlegend=False,
                        coloraxis_showscale=False,
                        height=350,
                        margin=dict(l=20, r=20, t=30, b=20)
                    )
                    st.plotly_chart(fig_provs_usd, use_container_width=True)
                else:
                    st.info("No hay datos en U$S para este año")

        except Exception as e:
            st.error(f"Error: {e}")

    # SEGUNDA FILA DE GRÁFICOS
    col_izq2, col_der2 = st.columns(2)

    # GRÁFICO 3: Gastos por Familia (Torta)
    with col_izq2:
        st.subheader("🥧 Gastos por Familia")
        try:
            df_familias = get_dashboard_gastos_familia(anio)
            if df_familias is not None and not df_familias.empty:
                fig_torta = px.pie(
                    df_familias,
                    values='Total',
                    names='Familia',
                    color_discrete_sequence=px.colors.qualitative.Set3,
                    hole=0.4  # Donut chart
                )
                fig_torta.update_layout(
                    height=350,
                    margin=dict(l=20, r=20, t=30, b=20),
                    showlegend=True,
                    legend=dict(
                        orientation="v",
                        yanchor="middle",
                        y=0.5,
                        xanchor="left",
                        x=1.02
                    )
                )
                fig_torta.update_traces(
                    textposition='inside',
                    textinfo='percent',
                    textfont_size=11
                )
                st.plotly_chart(fig_torta, use_container_width=True)
            else:
                st.info("No hay datos para este año")
        except Exception as e:
            st.error(f"Error: {e}")

    # GRÁFICO 4: Alertas y Últimas Compras
    with col_der2:
        st.subheader("🚨 Alertas y Actividad")

        # Alertas de vencimiento
        try:
            alertas = get_alertas_vencimiento_multiple(5)
            if alertas:
                st.markdown("**⚠️ Próximos vencimientos:**")
                for alerta in alertas[:3]:
                    # ✅ FIX mínimo: soportar ambos nombres de clave (dias_restantes / dias)
                    dias = alerta.get('dias_restantes', alerta.get('dias', None))
                    try:
                        dias = int(dias) if dias is not None else 999999
                    except:
                        dias = 999999

                    if dias <= 7:
                        color = "🔴"
                    elif dias <= 30:
                        color = "🟠"
                    else:
                        color = "🟡"

                    st.markdown(f"{color} **{alerta['articulo'][:30]}** - {alerta['vencimiento']} ({dias} días)")
            else:
                st.success("✅ No hay vencimientos próximos")
        except:
            pass

        st.markdown("---")

        # Últimos artículos comprados
        try:
            st.markdown("**🛒 Últimos artículos comprados:**")
            df_ultimas = get_dashboard_ultimas_compras(5)
            if df_ultimas is not None and not df_ultimas.empty:
                for _, row in df_ultimas.iterrows():
                    total_fmt = f"${row['Total']:,.0f}".replace(',', '.') if pd.notna(row['Total']) else "$0"
                    articulo = str(row['Articulo'])[:25] + "..." if len(str(row['Articulo'])) > 25 else str(row['Articulo'])
                    proveedor = str(row['Proveedor'])[:15] if pd.notna(row['Proveedor']) else ""
                    st.markdown(f"• {row['Fecha']} - **{articulo}** - {proveedor} - {total_fmt}")
            else:
                st.info("No hay compras recientes")
        except Exception as e:
            st.error(f"Error: {e}")


# =========================
# 📈 INDICADORES IA (POWER BI)
# =========================

def mostrar_indicadores_ia():
    url = "https://app.powerbi.com/view?r=eyJrIjoiMTBhMGY0ZjktYmM1YS00OTM4LTg3ZjItMTEzYWVmZWNkMGIyIiwidCI6ImQxMzBmYmU3LTFiZjAtNDczNi1hM2Q5LTQ1YjBmYWUwMDVmYSIsImMiOjR9"

    scale = 0.50  # ✅ Zoom 65%

    st.markdown(
        f"""
        <style>
          .pbi-wrap {{
            width: 100%;
            height: 92vh;
            padding: 18px 24px;   /* aire alrededor */
            box-sizing: border-box;
            overflow: hidden;     /* evita scroll extra por el scale */
          }}

          .pbi-iframe {{
            width: calc(100% / {scale});
            height: calc(92vh / {scale});
            transform: scale({scale});
            transform-origin: top left;
            border: 0;
            border-radius: 14px;
          }}
        </style>

        <div class="pbi-wrap">
          <iframe class="pbi-iframe" src="{url}" allowfullscreen="true"></iframe>
        </div>
        """,
        unsafe_allow_html=True
    )


# ========================
# 📊 RESUMEN RÁPIDO
# ========================
def _safe_float(x) -> float:
    try:
        if x is None:
            return 0.0
        return float(x)
    except Exception:
        return 0.0


@st.cache_data(ttl=300)
def _get_totales_anio(anio: int) -> dict:
    total_expr = _sql_total_num_expr_general()

    query = f"""
        SELECT
            SUM(CASE WHEN TRIM(COALESCE("Moneda",'')) = '$'
                     THEN {total_expr} ELSE 0 END) AS total_pesos,
            SUM(CASE WHEN TRIM(COALESCE("Moneda",'')) IN ('U$S','U$$')
                     THEN {total_expr} ELSE 0 END) AS total_usd
        FROM chatbot_raw
        WHERE
            ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
            AND "Año"::int = %s
    """

    params = (anio,)

    # DEBUG (opcional)
    if DEBUG_MODE:
        st.session_state.debug = {
            "pregunta": "total compras por año",
            "proveedor": None,
            "mes": None,
            "anio": anio,
            "sql": query,
            "params": params,
            "ruta": "TOTAL_COMPRAS_ANIO",
        }

    df = ejecutar_consulta(query, params)
    if df is None or df.empty:
        return {"pesos": 0.0, "usd": 0.0}

    return {
        "pesos": _safe_float(df["total_pesos"].iloc[0]),
        "usd": _safe_float(df["total_usd"].iloc[0]),
    }


@st.cache_data(ttl=300)
def _get_totales_mes(mes_key: str) -> dict:
    total_expr = _sql_total_num_expr_general()

    query = f"""
        SELECT
            SUM(CASE WHEN TRIM(COALESCE("Moneda",'')) = '$'
                     THEN {total_expr} ELSE 0 END) AS total_pesos,
            SUM(CASE WHEN TRIM(COALESCE("Moneda",'')) IN ('U$S','U$$')
                     THEN {total_expr} ELSE 0 END) AS total_usd
        FROM chatbot_raw
        WHERE
            ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
            AND TRIM("Mes") = %s
    """
    df = ejecutar_consulta(query, (mes_key,))
    if df is None or df.empty:
        return {"pesos": 0.0, "usd": 0.0}

    return {
        "pesos": _safe_float(df["total_pesos"].iloc[0]),
        "usd": _safe_float(df["total_usd"].iloc[0]),
    }


@st.cache_data(ttl=300)
def _get_top_proveedores_anio(anio: int, top_n: int = 20) -> pd.DataFrame:
    total_expr = _sql_total_num_expr_general()

    query = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS "Proveedor",
            SUM(CASE WHEN TRIM(COALESCE("Moneda",'')) = '$'
                     THEN {total_expr} ELSE 0 END) AS "Total_$",
            SUM(CASE WHEN TRIM(COALESCE("Moneda",'')) IN ('U$S','U$$')
                     THEN {total_expr} ELSE 0 END) AS "Total_USD"
        FROM chatbot_raw
        WHERE
            ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
            AND "Año"::int = %s
            AND "Cliente / Proveedor" IS NOT NULL
            AND TRIM("Cliente / Proveedor") <> ''
        GROUP BY TRIM("Cliente / Proveedor")
        ORDER BY "Total_$" DESC, "Total_USD" DESC
        LIMIT {int(top_n)}
    """
    df = ejecutar_consulta(query, (anio,))
    if df is None:
        return pd.DataFrame(columns=["Proveedor", "Total_$", "Total_USD"])
    return df
        
# =========================
# 🧾 RESUMEN COMPRAS (ROTATIVO) - RESPONSIVE Z FLIP 5
# =========================
def mostrar_resumen_compras_rotativo():
    # 🔄 re-ejecuta cada 5 segundos
    tick = 0
    try:
        from streamlit_autorefresh import st_autorefresh
        tick = st_autorefresh(interval=5000, key="__rotar_proveedor_5s__") or 0
    except Exception:
        tick = 0
    
    # Usar 2025 ya que 2026 no tiene datos todavía
    anio = 2025
    mes_key = "2025-12"  # Último mes con datos
    
    tot_anio = _get_totales_anio(anio)
    tot_mes = _get_totales_mes(mes_key)
    dfp = _get_top_proveedores_anio(anio, top_n=20)
    
    prov_nom = "—"
    prov_pesos = 0.0
    prov_usd = 0.0
    
    if dfp is not None and not dfp.empty:
        idx = int(tick) % len(dfp)
        row = dfp.iloc[idx]
        for col in dfp.columns:
            if col.lower() == "proveedor":
                nombre = str(row[col]) if pd.notna(row[col]) else "—"
                prov_nom = " ".join(nombre.split()[:2])  # ✅ SOLO 2 PALABRAS
            elif col.lower() == "total_$":
                prov_pesos = _safe_float(row[col])
            elif col.lower() == "total_usd":
                prov_usd = _safe_float(row[col])
    
    total_anio_txt = f"$ {_fmt_num_latam(tot_anio['pesos'], 0)}"
    total_anio_sub = f"U$S {_fmt_num_latam(tot_anio['usd'], 0)}"
    prov_sub = f"$ {_fmt_num_latam(prov_pesos, 0)} | U$S {_fmt_num_latam(prov_usd, 0)}"
    mes_txt = f"$ {_fmt_num_latam(tot_mes['pesos'], 0)}"
    mes_sub = f"U$S {_fmt_num_latam(tot_mes['usd'], 0)}"
    
    # 🎨 CSS – RESPONSIVE PARA Z FLIP 5
    st.markdown(
        """
        <style>
          .mini-resumen {
            display: flex;
            gap: 16px;
            margin: 16px 0 20px 0;
          }
          
          .mini-card {
            flex: 1;
            min-width: 0;
            height: 145px;
            border-radius: 16px;
            padding: 16px 18px;
            background: #1f2933;
            border: 1px solid #374151;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
          }
          
          .mini-t {
            font-size: 0.85rem;
            font-weight: 600;
            color: #9ca3af;
            margin: 0;
          }
          
          .mini-v {
            font-size: 1.25rem;
            font-weight: 800;
            color: #f9fafb;
            margin: 4px 0 0 0;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          
          .mini-s {
            font-size: 0.9rem;
            color: #d1d5db;
            margin: 0;
          }
          
          /* ========================================
             MOBILE RESPONSIVE (Z Flip 5 y similares)
             ======================================== */
          @media (max-width: 768px) {
            .mini-resumen {
              flex-direction: column;
              gap: 12px;
              margin: 12px 0 16px 0;
            }
            
            .mini-card {
              height: auto;
              min-height: 110px;
              padding: 14px 16px;
              background: #f6f4ef !important;
              border: 1px solid #e2e8f0 !important;
            }
            
            .mini-t {
              font-size: 0.8rem;
              color: #64748b !important;
              margin-bottom: 6px;
            }
            
            .mini-v {
              font-size: 1.35rem;
              font-weight: 800;
              color: #0f172a !important;
              margin: 0 0 6px 0;
              line-height: 1.2;
            }
            
            .mini-s {
              font-size: 0.85rem;
              color: #475569 !important;
              font-weight: 500;
            }
          }
          
          /* Para pantallas MUY pequeñas (< 400px) */
          @media (max-width: 400px) {
            .mini-card {
              padding: 12px 14px;
              min-height: 100px;
            }
            
            .mini-v {
              font-size: 1.2rem;
            }
            
            .mini-s {
              font-size: 0.8rem;
            }
          }
          
          /* ========================================
             FIX INPUT BUSCADOR EN MÓVIL
             ======================================== */
          @media (max-width: 768px) {
            /* Input de búsqueda "Escribí tu consulta..." */
            .block-container input[type="text"],
            .block-container textarea,
            [data-baseweb="input"] input,
            [data-baseweb="textarea"] textarea {
              font-size: 14px !important;
              padding: 10px 12px !important;
              min-height: 42px !important;
              height: auto !important;
            }
            
            /* Contenedor del input */
            [data-baseweb="input"],
            [data-baseweb="textarea"] {
              min-height: auto !important;
            }
            
            /* Placeholder text */
            .block-container input::placeholder,
            .block-container textarea::placeholder {
              font-size: 14px !important;
              opacity: 0.6;
            }
          }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    # 🧾 HTML FINAL
    st.markdown(
        f"""
        <div class="mini-resumen">
          <div class="mini-card">
            <p class="mini-t">💰 Total {anio}</p>
            <p class="mini-v">{total_anio_txt}</p>
            <p class="mini-s">{total_anio_sub}</p>
          </div>
          <div class="mini-card">
            <p class="mini-t">🏭 Proveedor</p>
            <p class="mini-v" title="{prov_nom}">{prov_nom}</p>
            <p class="mini-s">{prov_sub}</p>
          </div>
          <div class="mini-card">
            <p class="mini-t">🗓️ Mes actual</p>
            <p class="mini-v">{mes_txt}</p>
            <p class="mini-s">{mes_sub}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )
