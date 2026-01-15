# =========================
# UI_COMPRAS.PY - COMPRAS Y FACTURAS INTEGRADAS
# =========================

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional
import plotly.express as px  # Added for graphs

from ia_interpretador import interpretar_pregunta, obtener_info_tipo
from utils_openai import responder_con_openai
import sql_compras as sqlq_compras
import sql_comparativas as sqlq_comparativas
import sql_facturas as sqlq_facturas
from sql_core import get_unique_proveedores, get_unique_articulos  # Agregado

# Temporary fix for get_unique functions
def get_unique_proveedores():
    try:
        from sql_core import ejecutar_consulta
        sql = '''
            SELECT DISTINCT TRIM("Cliente / Proveedor") AS prov 
            FROM chatbot_raw 
            WHERE TRIM("Cliente / Proveedor") != '' 
            ORDER BY prov
        '''
        # ⚠️ SIN LIMIT - trae TODOS
        df = ejecutar_consulta(sql, ())
        if df is None or df.empty:
            return []
        provs = df['prov'].tolist()
        print(f"🐛 DEBUG: Cargados {len(provs)} proveedores únicos")  # Debug
        return provs
    except Exception as e:
        print(f"❌ Error cargando proveedores: {e}")
        return []

def get_unique_articulos():
    try:
        from sql_core import ejecutar_consulta
        sql = 'SELECT DISTINCT TRIM("Articulo") AS art FROM chatbot_raw WHERE TRIM("Articulo") != \'\' ORDER BY art'
        df = ejecutar_consulta(sql)
        return df['art'].tolist() if not df.empty else []
    except:
        return []

# =========================
# CONVERSIÓN DE MESES A NOMBRES
# =========================
def convertir_mes_a_nombre(mes_str):
    if not mes_str or '-' not in mes_str:
        return mes_str
    try:
        year, month = mes_str.split('-')
        month_num = int(month)
        meses = {
            1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio',
            7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
        }
        return f"{meses.get(month_num, 'desconocido')} {year}"
    except:
        return mes_str


# =========================
# DEBUG HELPERS
# =========================
def _dbg_set_interpretacion(obj: dict):
    try:
        st.session_state["DBG_INT_LAST"] = obj or {}
    except Exception:
        pass


def _dbg_set_sql(tag: Optional[str], query: str, params, df: Optional[pd.DataFrame] = None):
    try:
        st.session_state["DBG_SQL_LAST_TAG"] = tag
        st.session_state["DBG_SQL_LAST_QUERY"] = query or ""
        st.session_state["DBG_SQL_LAST_PARAMS"] = params if params is not None else []
        if isinstance(df, pd.DataFrame):
            st.session_state["DBG_SQL_ROWS"] = int(len(df))
            st.session_state["DBG_SQL_COLS"] = list(df.columns)
        else:
            st.session_state["DBG_SQL_ROWS"] = None
            st.session_state["DBG_SQL_COLS"] = []
    except Exception:
        pass


def _dbg_set_result(df: Optional[pd.DataFrame]):
    try:
        if isinstance(df, pd.DataFrame):
            st.session_state["DBG_SQL_ROWS"] = int(len(df))
            st.session_state["DBG_SQL_COLS"] = list(df.columns)
    except Exception:
        pass


# =========================
# HISTORIAL
# =========================
def inicializar_historial():
    if "historial_compras" not in st.session_state:
        st.session_state["historial_compras"] = []


# =========================
# TOTALES
# =========================
def calcular_totales_por_moneda(df: pd.DataFrame) -> dict:
    """
    Devuelve totales por moneda (para las cards):
    - Pesos: UYU / $ / pesos / ARS (pero excluye USD/U$S)
    - USD: USD / U$S / US$
    """
    if df is None or len(df) == 0:
        return {"Pesos": 0, "USD": 0}

    col_moneda = None
    for col in df.columns:
        if col.lower() in ["moneda", "currency"]:
            col_moneda = col
            break

    col_total = None
    for col in df.columns:
        if col.lower() in ["total", "monto", "importe", "valor", "monto_neto"]:
            col_total = col
            break

    if not col_moneda or not col_total:
        return None

    try:
        df_calc = df.copy()

        df_calc[col_total] = (
            df_calc[col_total]
            .astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.replace("$", "", regex=False)
            .str.strip()
        )
        df_calc[col_total] = pd.to_numeric(df_calc[col_total], errors="coerce").fillna(0)

        mon = df_calc[col_moneda].astype(str)

        # USD (incluye U$S)
        usd_mask = mon.str.contains(r"USD|U\$S|US\$|U\$|dolar|dólar", case=False, na=False)

        # Pesos (UYU/$/pesos) pero excluyendo USD (porque U$S contiene $)
        pesos_mask = mon.str.contains(r"UYU|\$|peso|ARS", case=False, na=False) & (~usd_mask)

        totales = {}
        totales["Pesos"] = df_calc.loc[pesos_mask, col_total].sum()
        totales["USD"] = df_calc.loc[usd_mask, col_total].sum()

        return totales

    except Exception as e:
        print(f"Error calculando totales: {e}")
        return None


# =========================
# DASHBOARD VENDIBLE (UI) - NUEVO
# (NO TOCA SQL / NO ROMPE LO EXISTENTE)
# =========================
import io


def _find_col(df: pd.DataFrame, candidates_lower: list) -> Optional[str]:
    for c in df.columns:
        if str(c).lower() in candidates_lower:
            return c
    return None


def _norm_moneda_view(x: str) -> str:
    s = ("" if x is None else str(x)).strip().upper()
    if not s:
        return "OTRA"
    if "U$S" in s or "USD" in s or "US$" in s or s == "U$" or "DOLAR" in s or "DÓLAR" in s:
        return "USD"
    if s == "$" or "UYU" in s or "PESO" in s:
        return "UYU"
    return s


def _safe_to_float(v) -> float:
    try:
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if not s:
            return 0.0
        s = s.replace(" ", "")
        # soporta "1.234,56" (LATAM) y "1,234.56" (EN) de forma básica
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        else:
            if "," in s and "." not in s:
                s = s.replace(",", ".")
        return float(s)
    except Exception:
        return 0.0


def _fmt_compact_money(v: float, moneda: str) -> str:
    try:
        v = float(v or 0.0)
    except Exception:
        v = 0.0

    sign = "-" if v < 0 else ""
    a = abs(v)

    if moneda == "USD":
        prefix = "U$S "
        decimals = 2
    else:
        prefix = "$ "
        decimals = 0 if a >= 1000 else 2

    if a >= 1_000_000_000:
        return f"{sign}{prefix}{a/1_000_000_000:,.2f}B".replace(",", ".")
    if a >= 1_000_000:
        return f"{sign}{prefix}{a/1_000_000:,.2f}M".replace(",", ".")
    if a >= 1_000:
        return f"{sign}{prefix}{a/1_000:,.2f}K".replace(",", ".")
    return f"{sign}{prefix}{a:,.{decimals}f}".replace(",", ".")


def _shorten_text(x, max_len: int = 52) -> str:
    s = "" if x is None else str(x)
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _df_export_clean(df: pd.DataFrame) -> pd.DataFrame:
    # No exportar columnas internas __*
    cols = [c for c in df.columns if not str(c).startswith("__")]
    return df[cols].copy() if cols else df.copy()


def _df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    try:
        return df.to_csv(index=False).encode("utf-8")
    except Exception:
        return b""


def _df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    try:
        buff = io.BytesIO()
        with pd.ExcelWriter(buff, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="datos")
        return buff.getvalue()
    except Exception:
        return b""


def _init_saved_views():
    if "FC_SAVED_VIEWS" not in st.session_state:
        st.session_state["FC_SAVED_VIEWS"] = []


def _save_view(view_name: str, data: dict):
    _init_saved_views()
    name = (view_name or "").strip()
    if not name:
        return
    # Reemplaza si existe
    out = []
    for v in st.session_state["FC_SAVED_VIEWS"]:
        if str(v.get("name", "")).strip().lower() == name.lower():
            continue
        out.append(v)
    out.append({"name": name, "data": data})
    st.session_state["FC_SAVED_VIEWS"] = out


def _get_saved_view_names() -> list:
    _init_saved_views()
    names = [v.get("name") for v in st.session_state.get("FC_SAVED_VIEWS", []) if v.get("name")]
    return sorted(names, key=lambda s: str(s).lower())


def _load_view(name: str) -> Optional[dict]:
    _init_saved_views()
    for v in st.session_state.get("FC_SAVED_VIEWS", []):
        if str(v.get("name", "")).strip().lower() == str(name or "").strip().lower():
            return v.get("data") or {}
    return None


def _paginate(df_in: pd.DataFrame, page: int, page_size: int) -> pd.DataFrame:
    if df_in is None or df_in.empty:
        return df_in
    page_size = max(1, int(page_size or 25))
    page = max(1, int(page or 1))
    start = (page - 1) * page_size
    end = start + page_size
    return df_in.iloc[start:end]


# Agregado: Mapeo de meses para display amigable
month_names = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
month_num = {name: f"{i+1:02d}" for i, name in enumerate(month_names)}

MONTH_MAPPING = {}
for year in [2023, 2024, 2025, 2026]:
    for month, num in month_num.items():
        MONTH_MAPPING[f"{year}-{num}"] = f"{month} {year}"

def code_to_display(code: str) -> str:
    return MONTH_MAPPING.get(code, code)

def display_to_code(display: str) -> str:
    reverse_mapping = {v: k for k, v in MONTH_MAPPING.items()}
    return reverse_mapping.get(display, display)

def rename_month_columns(df: pd.DataFrame) -> pd.DataFrame:
    df_renamed = df.copy()
    df_renamed.rename(columns=MONTH_MAPPING, inplace=True)
    return df_renamed


def render_dashboard_compras_vendible(df: pd.DataFrame, titulo: str = "Resultado", key_prefix: str = ""):
    if df is None or df.empty:
        st.warning("⚠️ No hay resultados para mostrar.")
        return

    # CSS MODERNO (header gradiente + tarjetas)
    st.markdown(
        """
        <style>
        /* Header con gradiente */
        .fc-header-modern {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px;
            padding: 20px 24px;
            margin-bottom: 20px;
            color: white;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
        }
        
        .fc-title-modern {
            font-size: 1.3rem;
            font-weight: 700;
            margin: 0 0 8px 0;
            color: white;
        }
        
        .fc-badge-modern {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.85rem;
            color: white;
        }
        
        .fc-meta-modern {
            font-size: 0.85rem;
            opacity: 0.9;
            margin: 4px 0 0 0;
            color: rgba(255, 255, 255, 0.9);
        }
        
        /* Grid de métricas */
        .fc-metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 20px;
        }
        
        .fc-metric-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 18px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            transition: all 0.2s ease;
        }
        
        .fc-metric-card:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            transform: translateY(-2px);
        }
        
        .fc-metric-label {
            font-size: 0.85rem;
            color: #6b7280;
            margin: 0 0 6px 0;
            font-weight: 500;
        }
        
        .fc-metric-value {
            font-size: 1.6rem;
            font-weight: 700;
            color: #111827;
            margin: 0;
        }
        
        .fc-metric-help {
            font-size: 0.75rem;
            color: #9ca3af;
            margin: 4px 0 0 0;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .fc-metrics-grid {
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
            }
            .fc-metric-value {
                font-size: 1.3rem;
            }
        }
        
        /* Legacy (mantener compatibilidad) */
        .fc-subtle { color: rgba(49,51,63,0.65); font-size: 0.9rem; }
        .fc-title { font-size: 1.05rem; font-weight: 700; margin: 0 0 4px 0; }
        
        /* ==========================================
           OCULTAR BOTÓN NATIVO DE STREAMLIT
           ========================================== */
        [data-testid="stDataFrameToolbar"] {
            display: none !important;
        }
        
        /* Botón de exportación arriba */
        .fc-export-btn {
            text-align: right;
            margin-bottom: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    df_view = rename_month_columns(df.copy())  # Renombra columnas de meses para display

    col_proveedor = _find_col(df_view, ["proveedor", "cliente / proveedor"])
    col_articulo = _find_col(df_view, ["articulo", "artículo"])
    col_fecha = _find_col(df_view, ["fecha"])
    col_moneda = _find_col(df_view, ["moneda", "currency"])
    col_total = _find_col(df_view, ["total", "monto", "importe", "valor", "monto_neto"])
    col_nro = _find_col(df_view, ["nro_factura", "nro. comprobante", "nro comprobante", "nro_comprobante"])
    col_cantidad = _find_col(df_view, ["cantidad"])

    if col_moneda:
        df_view["__moneda_view__"] = df_view[col_moneda].apply(_norm_moneda_view)
    else:
        df_view["__moneda_view__"] = "OTRA"

    if col_fecha:
        df_view["__fecha_view__"] = pd.to_datetime(df_view[col_fecha], errors="coerce")
    else:
        df_view["__fecha_view__"] = pd.NaT

    # FIX: Calcular __total_num__ correctamente para comparaciones
    if col_total:
        df_view["__total_num__"] = df_view[col_total].apply(_safe_to_float)
    else:
        numeric_cols = [c for c in df_view.columns if c != col_proveedor and pd.api.types.is_numeric_dtype(df_view[c])]
        if numeric_cols:
            # Para comparaciones: suma las columnas numéricas (ej: "2024-11" + "2025-11")
            df_view["__total_num__"] = df_view[numeric_cols].sum(axis=1)
        else:
            df_view["__total_num__"] = 0.0

    # Contexto
    filas_total = int(len(df_view))
    facturas = int(df_view[col_nro].nunique()) if col_nro else 0
    proveedores = int(df_view[col_proveedor].nunique()) if col_proveedor else 0
    articulos = int(df_view[col_articulo].nunique()) if col_articulo else 0

    # Rango fechas
    rango_txt = ""
    if df_view["__fecha_view__"].notna().any():
        dmin = df_view["__fecha_view__"].min()
        dmax = df_view["__fecha_view__"].max()
        try:
            rango_txt = f" · {dmin.date()} → {dmax.date()}"
        except Exception:
            rango_txt = ""

    # ==========================================
    # HEADER MODERNO CON GRADIENTE
    # ==========================================
    st.markdown(f"""
    <div class="fc-header-modern">
        <h2 class="fc-title-modern">📊 {titulo}</h2>
        <div class="fc-badge-modern">
            ✅ {filas_total} registros encontrados
        </div>
        <p class="fc-meta-modern">
            Facturas: {facturas} · Proveedores: {proveedores} · Artículos: {articulos}{rango_txt}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ==========================================
    # MÉTRICAS CON TARJETAS MODERNAS
    # ==========================================
    tot_uyu = float(df_view.loc[df_view["__moneda_view__"] == "UYU", "__total_num__"].sum())
    tot_usd = float(df_view.loc[df_view["__moneda_view__"] == "USD", "__total_num__"].sum())
    # FIX: Si no hay columna moneda (como en comparaciones), mostrar total general en UYU
    if not col_moneda:
        tot_uyu = float(df_view["__total_num__"].sum())
        tot_usd = 0.0

    st.markdown(f"""
    <div class="fc-metrics-grid">
        <div class="fc-metric-card">
            <p class="fc-metric-label">Total UYU 💰</p>
            <p class="fc-metric-value">{_fmt_compact_money(tot_uyu, "UYU")}</p>
            <p class="fc-metric-help">Valor exacto: $ {tot_uyu:,.2f}</p>
        </div>
        <div class="fc-metric-card">
            <p class="fc-metric-label">Total USD 💵</p>
            <p class="fc-metric-value">{_fmt_compact_money(tot_usd, "USD")}</p>
            <p class="fc-metric-help">Valor exacto: U$S {tot_usd:,.2f}</p>
        </div>
        <div class="fc-metric-card">
            <p class="fc-metric-label">{"Facturas 📄" if col_nro else "Registros 📄"}</p>
            <p class="fc-metric-value">{facturas if col_nro else filas_total}</p>
        </div>
        <div class="fc-metric-card">
            <p class="fc-metric-label">Proveedores 🏭</p>
            <p class="fc-metric-value">{proveedores}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ============================================================
    # FILTROS + ACCIONES - DESHABILITADO (simplificado)
    # ============================================================
    # Defaults
    sel_prov = []
    sel_art = []
    sel_mon = "TODAS"
    d_ini, d_fin = None, None
    search_txt = ""
    
    # EXPANDER COMENTADO - USAR SI NECESITAS FILTROS AVANZADOS
    # with st.expander("🔎 Filtros...", expanded=False):
    #     ...

    # ============================================================
    # SIN FILTROS (mostrar todo)
    # ============================================================
    df_f = df_view.copy()

    # ============================================================
    # BOTONES DE EXPORTACIÓN MOVIDOS ABAJO (ver tabs)
    # ============================================================

    # ============================================================
    # TABS
    # ============================================================
    tab_all, tab_uyu, tab_usd, tab_graf, tab_tabla = st.tabs(
        ["Vista general", "Pesos (UYU)", "Dólares (USD)", "Gráfico (Top 10 artículos)", "Tabla"]
    )

    def _render_resumen_top_proveedores(df_tab: pd.DataFrame, etiqueta: str):
        """Solo se usa cuando HAY columna de proveedor"""
        if df_tab is None or df_tab.empty:
            st.info(f"Sin resultados en {etiqueta}.")
            return

        if not col_proveedor:
            st.caption("No hay columna de proveedor para resumir.")
            return

        # Top proveedores con total (tabla chica)
        top = (
            df_tab.groupby(col_proveedor)["__total_num__"]
            .sum()
            .sort_values(ascending=False)
        )

        total_val = float(df_tab["__total_num__"].sum()) if "__total_num__" in df_tab.columns else 0.0

        if len(top) > 0 and total_val:
            prov_top = str(top.index[0])
            share = float(top.iloc[0]) / total_val * 100.0
            st.markdown(
                f"**Resumen:** principal proveedor **{prov_top}** con **{share:.1f}%** del total en {etiqueta}."
            )
        else:
            st.caption("No hay totales suficientes para generar resumen.")

        df_top = top.head(10).reset_index()
        df_top.columns = [col_proveedor, "Total"]

        # Formato de Total para que se vea prolijo (LATAM)
        df_top["Total"] = df_top["Total"].apply(
            lambda x: f"{float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        st.dataframe(df_top, use_container_width=True, hide_index=True, height=260)
        st.caption("Detalle completo solo en la pestaña **Tabla**.")

    def _render_tabla_simple(df_tab: pd.DataFrame, etiqueta: str):
        """Muestra tabla simple sin agrupar (para casos sin proveedor)"""
        if df_tab is None or df_tab.empty:
            st.info(f"Sin resultados en {etiqueta}.")
            return

        # Preparar columnas para mostrar
        pref = []
        for c in [col_moneda, col_total, _find_col(df_tab, ["anio", "año"]), _find_col(df_tab, ["total_facturas"])]:
            if c and c in df_tab.columns:
                pref.append(c)
        resto = [c for c in df_tab.columns if c not in pref and not str(c).startswith("__")]
        show_cols = pref + resto

        df_show = df_tab[show_cols].copy()
        
        # Formato LATAM para columna de total
        if col_total and col_total in df_show.columns:
            df_show[col_total] = df_show[col_total].apply(
                lambda x: f"{_safe_to_float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )

        st.dataframe(df_show, use_container_width=True, hide_index=True, height=320)

    with tab_all:
        # ✅ Botón Excel arriba a la derecha
        col_space, col_export = st.columns([5, 1])
        with col_export:
            df_export = _df_export_clean(df_f)
            st.download_button(
                "📥 Excel",
                data=_df_to_excel_bytes(df_export),
                file_name="vista_general.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{key_prefix}xlsx_all",
                type="secondary"
            )
        
        if col_proveedor:
            _render_resumen_top_proveedores(df_f, "todas las monedas")
        else:
            _render_tabla_simple(df_f, "todas las monedas")

    with tab_uyu:
        # ✅ Botón Excel arriba
        col_space, col_export = st.columns([5, 1])
        with col_export:
            df_uyu = df_f[df_f["__moneda_view__"] == "UYU"]
            df_export = _df_export_clean(df_uyu)
            st.download_button(
                "📥 Excel",
                data=_df_to_excel_bytes(df_export),
                file_name="pesos_uyu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{key_prefix}xlsx_uyu",
                type="secondary"
            )
        
        df_uyu = df_f[df_f["__moneda_view__"] == "UYU"]
        if col_proveedor:
            _render_resumen_top_proveedores(df_uyu, "UYU")
        else:
            _render_tabla_simple(df_uyu, "UYU")

    with tab_usd:
        # ✅ Botón Excel arriba
        col_space, col_export = st.columns([5, 1])
        with col_export:
            df_usd = df_f[df_f["__moneda_view__"] == "USD"]
            df_export = _df_export_clean(df_usd)
            st.download_button(
                "📥 Excel",
                data=_df_to_excel_bytes(df_export),
                file_name="dolares_usd.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{key_prefix}xlsx_usd",
                type="secondary"
            )
        
        df_usd = df_f[df_f["__moneda_view__"] == "USD"]
        if col_proveedor:
            _render_resumen_top_proveedores(df_usd, "USD")
        else:
            _render_tabla_simple(df_usd, "USD")

    with tab_graf:
        if df_f is None or df_f.empty or not col_articulo:
            st.info("Sin datos suficientes para gráfico.")
        else:
            g_mon = st.selectbox(
                "Moneda del gráfico",
                options=["TODAS", "UYU", "USD"],
                index=0,
                key=f"{key_prefix}g_mon"
            )
            df_g = df_f.copy()
            if g_mon != "TODAS":
                df_g = df_g[df_g["__moneda_view__"] == g_mon]

            top_art = (
                df_g.groupby(col_articulo)["__total_num__"]
                .sum()
                .sort_values(ascending=False)
            ).head(10)

            if len(top_art) == 0:
                st.info("Sin resultados para ese filtro.")
            else:
                df_top_art = top_art.reset_index()
                df_top_art.columns = [col_articulo, "Total"]
                df_top_art[col_articulo] = df_top_art[col_articulo].apply(lambda x: _shorten_text(x, 60))

                st.dataframe(df_top_art, use_container_width=True, hide_index=True, height=320)

                try:
                    chart_df = df_top_art.set_index(col_articulo)["Total"]
                    st.bar_chart(chart_df)
                except Exception:
                    pass

    with tab_tabla:
        if df_f is None or df_f.empty:
            st.info("Sin resultados para mostrar.")
        else:
            # ✅ Botón Excel arriba a la derecha
            col_space, col_export = st.columns([5, 1])
            with col_export:
                df_export = _df_export_clean(df_f)
                st.download_button(
                    "📥 Excel",
                    data=_df_to_excel_bytes(df_export),
                    file_name="tabla_completa.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"{key_prefix}xlsx_tabla",
                    type="secondary"
            )
            
            # Orden preferido (mantiene columnas originales)
            pref = []
            for c in [col_proveedor, col_articulo, col_nro, col_fecha, col_cantidad, col_moneda, col_total]:
                if c and c in df_f.columns:
                    pref.append(c)
            resto = [c for c in df_f.columns if c not in pref and not str(c).startswith("__")]
            show_cols = pref + resto

            # Paginación
            t1, t2, t3 = st.columns([1.2, 1.0, 1.8])
            with t1:
                page_size = st.selectbox(
                    "Filas por página",
                    options=[25, 50, 100, 250],
                    index=0,
                    key=f"{key_prefix}page_size"
                )
            max_pages = max(1, int((len(df_f) + int(page_size) - 1) / int(page_size)))
            with t2:
                page = st.number_input(
                    "Página",
                    min_value=1,
                    max_value=max_pages,
                    value=min(st.session_state.get(f"{key_prefix}page", 1), max_pages),
                    step=1,
                    key=f"{key_prefix}page"
                )
            with t3:
                st.caption(f"Página {int(page)} de {max_pages} · Total filas: {len(df_f)}")

            df_page = _paginate(df_f[show_cols], int(page), int(page_size)).copy()

            # Recortar textos para vista limpia
            if col_proveedor and col_proveedor in df_page.columns:
                df_page[col_proveedor] = df_page[col_proveedor].apply(lambda x: _shorten_text(x, 60))
            if col_articulo and col_articulo in df_page.columns:
                df_page[col_articulo] = df_page[col_articulo].apply(lambda x: _shorten_text(x, 60))

            st.dataframe(df_page, use_container_width=True, height=460)

            # Drill-down por factura
            if col_nro and col_nro in df_f.columns:
                st.markdown("#### Detalle por factura")
                nros = [n for n in df_f[col_nro].dropna().astype(str).unique().tolist() if str(n).strip()]
                nros = sorted(nros)[:5000]

                det_col1, det_col2 = st.columns([1.2, 2.8])
                with det_col1:
                    det_search = st.text_input(
                        "Buscar nro factura",
                        value="",
                        key=f"{key_prefix}det_search",
                        placeholder="Ej: A00060907"
                    ).strip()

                nro_opts = nros
                if det_search:
                    nro_opts = [n for n in nros if det_search.lower() in str(n).lower()]
                    nro_opts = nro_opts[:200]

                with det_col2:
                    nro_sel = st.selectbox(
                        "Seleccionar factura",
                        options=["(ninguna)"] + nro_opts,
                        index=0,
                        key=f"{key_prefix}det_nro_sel"
                    )

                if nro_sel and nro_sel != "(ninguna)":
                    df_fac = df_f[df_f[col_nro].astype(str) == str(nro_sel)].copy()

                    tot_fac = float(df_fac["__total_num__"].sum())
                    mon_fac = "USD" if (df_fac["__moneda_view__"] == "USD").any() and not (df_fac["__moneda_view__"] == "UYU").any() else "UYU"
                    st.markdown(
                        f"**Factura:** `{nro_sel}` · **Items:** {len(df_fac)} · **Total:** {_fmt_compact_money(tot_fac, mon_fac)}"
                    )

                    pref_fac = []
                    for c in [col_articulo, col_cantidad, col_total, col_fecha, col_moneda]:
                        if c and c in df_fac.columns:
                            pref_fac.append(c)
                    resto_fac = [c for c in df_fac.columns if c not in pref_fac and not str(c).startswith("__")]
                    show_cols_fac = pref_fac + resto_fac

                    df_fac_disp = df_fac[show_cols_fac].copy()
                    if col_articulo and col_articulo in df_fac_disp.columns:
                        df_fac_disp[col_articulo] = df_fac_disp[col_articulo].apply(lambda x: _shorten_text(x, 70))

                    st.dataframe(df_fac_disp, use_container_width=True, height=320)


# =========================
# ROUTER SQL (ahora incluye compras, comparativas y stock)
# =========================
def ejecutar_consulta_por_tipo(tipo: str, parametros: dict):

    _dbg_set_sql(
        tag=tipo,
        query=f"-- Ejecutando tipo: {tipo}\n-- (SQL real en sql_compras/sql_comparativas/sql_facturas)\n",
        params=parametros,
        df=None,
    )

    # ===== FACTURAS =====
    if tipo == "detalle_factura":
        df = sqlq_facturas.get_detalle_factura_por_numero(parametros["nro_factura"])
        _dbg_set_result(df)
        return df

    elif tipo == "facturas_proveedor":
        # ✅ Usa la función corregida de sql_facturas.py
        df = sqlq_facturas.get_facturas_proveedor(
            proveedores=parametros.get("proveedores", []),
            meses=parametros.get("meses"),
            anios=parametros.get("anios"),
            desde=parametros.get("desde"),
            hasta=parametros.get("hasta"),
            articulo=parametros.get("articulo"),
            moneda=parametros.get("moneda"),
            limite=parametros.get("limite", 5000),
        )
        _dbg_set_result(df)
        return df

    elif tipo == "ultima_factura":
        df = sqlq_facturas.get_ultima_factura_inteligente(parametros["patron"])
        _dbg_set_result(df)
        return df

    elif tipo == "resumen_facturas":
        df = sqlq_facturas.get_resumen_facturas_por_proveedor(
            meses=parametros.get("meses"),
            anios=parametros.get("anios"),
            moneda=parametros.get("moneda"),
        )
        _dbg_set_result(df)
        return df

    elif tipo == "facturas_rango_monto":
        df = sqlq_facturas.get_facturas_por_rango_monto(
            monto_min=parametros.get("monto_min", 0),
            monto_max=parametros.get("monto_max", 999999999),
            proveedores=parametros.get("proveedores"),
            meses=parametros.get("meses"),
            anios=parametros.get("anios"),
            moneda=parametros.get("moneda"),
            limite=parametros.get("limite", 100),
        )
        _dbg_set_result(df)
        return df

    # ===== COMPRAS =====
    elif tipo == "compras_anio":
        df = sqlq_compras.get_compras_anio(parametros["anio"])
        _dbg_set_result(df)
        return df

    elif tipo == "compras_mes":
        df = sqlq_compras.get_compras_por_mes_excel(parametros["mes"])
        _dbg_set_result(df)
        return df

    elif tipo == "compras_proveedor_mes":
        df = sqlq_compras.get_detalle_compras_proveedor_mes(parametros["proveedor"], parametros["mes"])
        _dbg_set_result(df)
        return df

    # AGREGADO: COMPRAS MÚLTIPLES
    elif tipo == "compras_multiples":
        df = sqlq_compras.get_compras_multiples(
            proveedores=parametros.get("proveedores", []),
            meses=parametros.get("meses", []),
            anios=parametros.get("anios", []),
            limite=parametros.get("limite", 5000)
        )
        _dbg_set_result(df)
        return df

    # ===== COMPARATIVAS =====
    elif tipo == "comparar_proveedor_meses":
        df = sqlq_comparativas.get_comparacion_proveedor_meses(
            parametros["proveedor"], parametros["mes1"], parametros["mes2"], parametros["label1"], parametros["label2"]
        )
        _dbg_set_result(df)
        return df

    elif tipo == "comparar_proveedor_anios":
        df = sqlq_comparativas.get_comparacion_proveedor_anios(
            parametros["proveedor"], parametros["anios"], parametros["label1"], parametros["label2"]
        )
        _dbg_set_result(df)
        return df

    elif tipo == "comparar_proveedores_meses":
        df = sqlq_comparativas.get_comparacion_proveedores_meses(
            parametros["proveedores"], parametros["mes1"], parametros["mes2"], parametros["label1"], parametros["label2"]
        )
        _dbg_set_result(df)
        return df

    elif tipo == "comparar_proveedores_anios":
        df = sqlq_comparativas.get_comparacion_proveedores_anios(
            parametros["proveedores"], parametros["anios"], parametros["label1"], parametros["label2"]
        )
        _dbg_set_result(df)
        return df

    # AGREGADO: Comparación multi proveedores multi meses
    elif tipo == "comparar_proveedores_meses_multi":
        df = sqlq_comparativas.get_comparacion_proveedores_meses_multi(
            proveedores=parametros.get("proveedores", []),
            meses=parametros.get("meses", []),
            articulos=parametros.get("articulos", [])  # Agregado articulos
        )
        _dbg_set_result(df)
        return df
        
    # ===== COMPARATIVAS MULTI (NUEVO - TODOS LOS PROVEEDORES) =====
    elif tipo == "comparar_proveedores_anios_multi":
        proveedores = parametros.get("proveedores", [])
        anios = parametros.get("anios", [])
        
        # Si proveedores está vacío, significa TODOS
        if not proveedores:
            proveedores = None
        
        print(f"🐛 DEBUG ejecutar_consulta: comparar_proveedores_anios_multi")
        print(f"   Proveedores: {proveedores or 'TODOS'}")
        print(f"   Años: {anios}")
        
        df = sqlq_comparativas.get_comparacion_proveedores_anios_multi(
            proveedores=proveedores,
            anios=anios
        )
        _dbg_set_result(df)
        return df

    # ===== STOCK =====
    elif tipo == "stock_total":
        df = sqlq_compras.get_stock_total()  # Ajusta si es otro módulo
        _dbg_set_result(df)
        return df

    elif tipo == "stock_articulo":
        df = sqlq_compras.get_stock_articulo(parametros["articulo"])  # Ajusta si es otro módulo
        _dbg_set_result(df)
        return df

    # ===== LISTADO FACTURAS AÑO =====
    elif tipo == "listado_facturas_anio":
        df = sqlq_compras.get_listado_facturas_por_anio(parametros["anio"])
        _dbg_set_result(df)
        return df

    # ===== TOTAL FACTURAS POR MONEDA AÑO =====
    elif tipo == "total_facturas_por_moneda_anio":
        df = sqlq_compras.get_total_facturas_por_moneda_anio(parametros["anio"])
        _dbg_set_result(df)
        return df

    # ===== TOTAL FACTURAS POR MONEDA GENÉRICO (TODOS LOS AÑOS) =====
    elif tipo == "total_facturas_por_moneda_generico":
        df = sqlq_facturas.get_total_facturas_por_moneda_todos_anios()
        _dbg_set_result(df)
        return df

    # ===== TOTAL COMPRAS POR MONEDA GENÉRICO (TODOS LOS AÑOS) =====
    elif tipo == "total_compras_por_moneda_generico":
        df = sqlq_compras.get_total_compras_por_moneda_todos_anios()
        _dbg_set_result(df)
        return df

    raise ValueError(f"Tipo '{tipo}' no implementado en ejecutar_consulta_por_tipo")


# =========================
# 🎨 DASHBOARD COMPARATIVAS MODERNO
# =========================
def render_dashboard_comparativas_moderno(df: pd.DataFrame, titulo: str = "Comparativas"):
    """
    Dashboard con diseño moderno tipo card (similar a la imagen)
    """
    
    # Calcular métricas
    total_uyu = df[df['Moneda'] == '$'].sum(numeric_only=True).sum() if 'Moneda' in df.columns else 0
    total_usd = df[df['Moneda'].isin(['U$S', 'USD'])].sum(numeric_only=True).sum() if 'Moneda' in df.columns else 0
    num_proveedores = df['Proveedor'].nunique() if 'Proveedor' in df.columns else 0
    num_facturas = len(df)
    
    # CSS Moderno
    st.markdown("""
    <style>
        /* ==========================================
           HEADER CON TÍTULO Y METADATA
           ========================================== */
        .dash-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px;
            padding: 24px 28px;
            margin-bottom: 24px;
            color: white;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
        }
        
        .dash-title {
            font-size: 1.5rem;
            font-weight: 700;
            margin: 0 0 12px 0;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .dash-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9rem;
            margin-bottom: 8px;
        }
        
        .dash-meta {
            font-size: 0.85rem;
            opacity: 0.9;
            margin: 0;
        }
        
        /* ==========================================
           TARJETAS DE MÉTRICAS (4 columnas)
           ========================================== */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }
        
        .metric-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            transition: all 0.2s ease;
        }
        
        .metric-card:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            transform: translateY(-2px);
        }
        
        .metric-label {
            font-size: 0.85rem;
            color: #6b7280;
            margin: 0 0 8px 0;
            font-weight: 500;
        }
        
        .metric-value {
            font-size: 1.75rem;
            font-weight: 700;
            color: #111827;
            margin: 0;
        }
        
        /* ==========================================
           CARD PROVEEDOR PRINCIPAL
           ========================================== */
        .provider-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }
        
        .provider-header {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 16px;
        }
        
        .provider-icon {
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            color: white;
            font-weight: 700;
        }
        
        .provider-info {
            flex: 1;
        }
        
        .provider-name {
            font-size: 1.1rem;
            font-weight: 700;
            color: #111827;
            margin: 0 0 4px 0;
        }
        
        .provider-subtitle {
            font-size: 0.85rem;
            color: #6b7280;
            margin: 0;
        }
        
        .provider-amount {
            font-size: 1.5rem;
            font-weight: 700;
            color: #111827;
            text-align: right;
        }
        
        .provider-amount-sub {
            font-size: 0.85rem;
            color: #6b7280;
            text-align: right;
            margin-top: 4px;
        }
        
        /* Barra de progreso */
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
            margin: 12px 0;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 4px;
            transition: width 0.3s ease;
        }
        
        /* ==========================================
           TABS Y BOTONES
           ========================================== */
        .action-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            padding: 12px 0;
            border-bottom: 1px solid #e5e7eb;
        }
        
        .btn-export {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: white;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            padding: 8px 16px;
            font-size: 0.9rem;
            font-weight: 500;
            color: #374151;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .btn-export:hover {
            background: #f9fafb;
            border-color: #9ca3af;
        }
        
        /* ==========================================
           RESPONSIVE (MOBILE)
           ========================================== */
        @media (max-width: 768px) {
            .metrics-grid {
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
            }
            
            .metric-value {
                font-size: 1.4rem;
            }
            
            .provider-header {
                flex-direction: column;
                align-items: flex-start;
            }
            
            .provider-amount {
                text-align: left;
                margin-top: 8px;
            }
            
            .dash-title {
                font-size: 1.2rem;
            }
        }
    </style>
    """, unsafe_allow_html=True)
    
    # ==========================================
    # HTML ESTRUCTURA
    # ==========================================
    
    # HEADER
    st.markdown(f"""
    <div class="dash-header">
        <h2 class="dash-title">
            📊 {titulo}
        </h2>
        <div class="dash-badge">
            ✅ Resultado: Se encontraron {len(df)} registros
        </div>
        <p class="dash-meta">
            📅 Última actualización: {datetime.now().strftime("%d/%m/%Y %H:%M")}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # MÉTRICAS
    st.markdown(f"""
    <div class="metrics-grid">
        <div class="metric-card">
            <p class="metric-label">Total UYU 💰</p>
            <p class="metric-value">$ {total_uyu/1_000_000:.2f}M</p>
        </div>
        <div class="metric-card">
            <p class="metric-label">Total USD 💵</p>
            <p class="metric-value">U$S {total_usd:,.0f}</p>
        </div>
        <div class="metric-card">
            <p class="metric-label">Facturas 📄</p>
            <p class="metric-value">{num_facturas}</p>
        </div>
        <div class="metric-card">
            <p class="metric-label">Proveedores 🏭</p>
            <p class="metric-value">{num_proveedores}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # PROVEEDOR PRINCIPAL (si existe)
    if 'Proveedor' in df.columns and not df.empty:
        # Calcular proveedor con mayor monto
        df_prov = df.groupby('Proveedor').sum(numeric_only=True)
        top_prov = df_prov.sum(axis=1).idxmax()
        top_monto = df_prov.sum(axis=1).max()
        top_porc = (top_monto / df.sum(numeric_only=True).sum()) * 100
        
        # Iniciales para el ícono
        iniciales = "".join([p[0] for p in top_prov.split()[:2]]).upper()
        
        st.markdown(f"""
        <div class="provider-card">
            <div class="provider-header">
                <div class="provider-icon">{iniciales}</div>
                <div class="provider-info">
                    <p class="provider-name">{top_prov}</p>
                    <p class="provider-subtitle">Principal Proveedor</p>
                </div>
                <div>
                    <p class="provider-amount">$ {top_monto:,.2f}</p>
                    <p class="provider-amount-sub">$ {top_monto/1_000_000:.2f}M UYU</p>
                </div>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {top_porc}%"></div>
            </div>
            <p style="margin: 8px 0 0 0; font-size: 0.85rem; color: #6b7280;">
                Total: $ {top_monto/1_000_000:.2f}M UYU ({top_porc:.1f}% del total)
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # TABS CON DATOS
    tabs = st.tabs(["📊 Vista General", "💵 Pesos (UYU)", "💰 Dólares (USD)", "📈 Gráfico", "📋 Tabla"])
    
    with tabs[0]:
        st.dataframe(df, use_container_width=True, height=400)
    
    with tabs[1]:
        df_pesos = df[df['Moneda'] == '$'] if 'Moneda' in df.columns else df
        st.dataframe(df_pesos, use_container_width=True, height=400)
    
    with tabs[2]:
        df_usd = df[df['Moneda'].isin(['U$S', 'USD'])] if 'Moneda' in df.columns else pd.DataFrame()
        if not df_usd.empty:
            st.dataframe(df_usd, use_container_width=True, height=400)
        else:
            st.info("No hay datos en dólares")
    
    with tabs[3]:
        # Gráfico de barras por proveedor
        if 'Proveedor' in df.columns:
            fig = px.bar(
                df.groupby('Proveedor').sum(numeric_only=True).reset_index(),
                x='Proveedor',
                y=df.select_dtypes(include='number').columns[0],
                title="Distribución por Proveedor"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tabs[4]:
        st.dataframe(df, use_container_width=True, height=600)


# =========================
# UI PRINCIPAL
# =========================
def Compras_IA():

    inicializar_historial()

    st.markdown("### 🤖 Asistente de Compras y Facturas")

    # Persistencia de selecciones en Comparativas
    if "prov_multi" not in st.session_state:
        st.session_state["prov_multi"] = []
    if "meses_multi" not in st.session_state:
        st.session_state["meses_multi"] = ["2024-11", "2025-11"]
    if "art_multi" not in st.session_state:
        st.session_state["art_multi"] = []

    # Fetch opciones dinámicas - TODOS sin límite
    prov_options = get_unique_proveedores()  # ✅ Sin límite
    print(f"🐛 Proveedores disponibles: {len(prov_options)}")  # Debug

    art_options = get_unique_articulos()[:100]

    # TABS PRINCIPALES: Chat IA + Comparativas
    tab_chat, tab_comparativas = st.tabs(["💬Compras", "📊 Comparativas"])

    with tab_chat:
        # BOTÓN LIMPIAR (solo en chat)
        if st.button("🗑️ Limpiar chat"):
            st.session_state["historial_compras"] = []
            _dbg_set_interpretacion({})
            _dbg_set_sql(None, "", [], None)
            st.rerun()

        # st.markdown("---")  # ← COMENTADA - ocupaba espacio al pedo

        # Mostrar historial
        for idx, msg in enumerate(st.session_state["historial_compras"]):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

                if "df" in msg and msg["df"] is not None:
                    df = msg["df"]

                    # Dashboard vendible compacto
                    try:
                        st.markdown("---")
                        render_dashboard_compras_vendible(
                            df,
                            titulo="Datos",
                            key_prefix=f"hist_{idx}_"
                        )
                    except Exception as e:
                        # Fallback viejo (no romper nada)
                        totales = calcular_totales_por_moneda(df)
                        if totales:
                            col1, col2, col3 = st.columns([2, 2, 3])

                            with col1:
                                pesos = totales.get("Pesos", 0)
                                pesos_str = (
                                    f"${pesos/1_000_000:,.2f}M"
                                    if pesos >= 1_000_000
                                    else f"${pesos:,.2f}"
                                )
                                st.metric(
                                    "💵 Total Pesos",
                                    pesos_str,
                                    help=f"Valor exacto: ${pesos:,.2f}",
                                )

                            with col2:
                                usd = totales.get("USD", 0)
                                usd_str = (
                                    f"${usd/1_000_000:,.2f}M"
                                    if usd >= 1_000_000
                                    else f"${usd:,.2f}"
                                )
                                st.metric(
                                    "💵 Total USD",
                                    usd_str,
                                    help=f"Valor exacto: ${usd:,.2f}",
                                )

                        st.markdown("---")
                        st.dataframe(df, use_container_width=True, height=400)
                        st.caption(f"⚠️ Dashboard vendible falló: {e}")

        # =========================
        # TIPS / EJEMPLOS (CAJA AMARILLA ANTES DEL INPUT)
        # =========================
        tips_html = """
        <div style="
            background: rgba(255, 243, 205, 0.85);
            border: 1px solid rgba(245, 158, 11, 0.30);
            border-left: 4px solid rgba(245, 158, 11, 0.75);
            border-radius: 12px;
            padding: 16px 20px;
            margin: 20px 0 16px 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        ">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
                <span style="font-size: 22px;">💡</span>
                <span style="font-size: 16px; font-weight: 700; color: #78350f;">Ejemplos de preguntas:</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px 24px; font-size: 14px; color: #451a03;">
                <div>• Compras roche 2024</div>
                <div>• Facturas roche noviembre 2025</div>
                <div>• Compras roche, tresul 2024 2025</div>
                <div>• Detalle factura A00060907</div>
                <div>• Total facturas por moneda</div>
                <div>• Top proveedores 2025</div>
                <div>• Compras 2025</div>
                <div>• Compras vitek 2024</div>
                <div>• Comparar roche 2024 2025</div>
                <div>• Total compras octubre 2025</div>
            </div>
        </div>
        """
        st.markdown(tips_html, unsafe_allow_html=True)

    # Input
    pregunta = st.chat_input("Escribí tu consulta sobre compras o facturas...")

    if pregunta:
        st.session_state["historial_compras"].append(
            {
                "role": "user",
                "content": pregunta,
                "timestamp": datetime.now().timestamp(),
            }
        )

        resultado = interpretar_pregunta(pregunta)
        _dbg_set_interpretacion(resultado)

        tipo = resultado.get("tipo", "")
        parametros = resultado.get("parametros", {})

        respuesta_content = ""
        respuesta_df = None

        if tipo == "conversacion":
            respuesta_content = responder_con_openai(pregunta, tipo="conversacion")

        elif tipo == "conocimiento":
            respuesta_content = responder_con_openai(pregunta, tipo="conocimiento")

        elif tipo == "no_entendido":
            respuesta_content = "🤔 No entendí bien tu pregunta."
            sugerencia = resultado.get("sugerencia", "")
            if sugerencia:
                respuesta_content += f"\n\n**Sugerencia:** {sugerencia}"

        else:
            try:
                resultado_sql = ejecutar_consulta_por_tipo(tipo, parametros)

                # Convertir "Mes" a nombres antes de mostrar
                if isinstance(resultado_sql, pd.DataFrame) and 'Mes' in resultado_sql.columns:
                    resultado_sql['Mes'] = resultado_sql['Mes'].apply(convertir_mes_a_nombre)

                if isinstance(resultado_sql, pd.DataFrame):
                    if len(resultado_sql) == 0:
                        respuesta_content = "⚠️ No se encontraron resultados"
                    else:
                        if tipo == "detalle_factura":
                            nro = parametros.get("nro_factura", "")
                            respuesta_content = f"✅ **Factura {nro}** - {len(resultado_sql)} artículos"
                        elif tipo.startswith("facturas_"):
                            respuesta_content = f"✅ Encontré **{len(resultado_sql)}** facturas"
                        elif tipo.startswith("compras_"):
                            respuesta_content = f"✅ Encontré **{len(resultado_sql)}** compras"
                        elif tipo.startswith("comparar_"):
                            respuesta_content = f"✅ Comparación lista - {len(resultado_sql)} filas"
                        elif tipo.startswith("stock_"):
                            respuesta_content = f"✅ Stock encontrado - {len(resultado_sql)} filas"
                        elif tipo == "listado_facturas_anio":
                            anio = parametros.get("anio", "")
                            respuesta_content = f"✅ **Listado de Facturas {anio}** - {len(resultado_sql)} proveedores"
                        elif tipo == "total_facturas_por_moneda_anio":
                            anio = parametros.get("anio", "")
                            respuesta_content = f"✅ **Totales de Facturas {anio} por Moneda** - {len(resultado_sql)} monedas"
                        elif tipo == "total_facturas_por_moneda_generico":
                            respuesta_content = f"✅ **Totales de Facturas por Moneda (Todos los años)** - {len(resultado_sql)} monedas"
                        elif tipo == "total_compras_por_moneda_generico":
                            respuesta_content = f"✅ **Totales de Compras por Moneda (Todos los años)** - {len(resultado_sql)} monedas"
                        else:
                            respuesta_content = f"✅ Encontré **{len(resultado_sql)}** resultados"

                        respuesta_df = resultado_sql
                else:
                    respuesta_content = str(resultado_sql)

            except Exception as e:
                _dbg_set_sql(
                    tipo,
                    f"-- Error ejecutando consulta_por_tipo: {str(e)}",
                    parametros,
                    None,
                )
                respuesta_content = f"❌ Error: {str(e)}"

        st.session_state["historial_compras"].append(
            {
                "role": "assistant",
                "content": respuesta_content,
                "df": respuesta_df,
                "tipo": tipo,
                "pregunta": pregunta,
                "timestamp": datetime.now().timestamp(),
            }
        )

        st.rerun()

    with tab_comparativas:
        st.markdown("### 📊 Menú Comparativas Fáciles")
        st.markdown("Selecciona opciones y compara proveedores/meses/años directamente (sin chat).")

        # Agregado: Submenús Compras y Comparativas
        tipo_consulta = st.selectbox("Tipo de consulta", options=["Compras", "Comparativas"], index=0, key="tipo_consulta")

        if tipo_consulta == "Compras":
            st.markdown("#### 🛒 Consultas de Compras")
            
            anio_compras = st.selectbox("Año", options=[2023, 2024, 2025, 2026], index=2, key="anio_compras")
            mes_compras = st.selectbox("Mes", options=month_names + ["Todos"], index=len(month_names), key="mes_compras")
            proveedor_compras = st.selectbox("Proveedor", options=["Todos"] + prov_options[:50], index=0, key="proveedor_compras")
            
            if st.button("🔍 Buscar Compras", key="btn_buscar_compras"):
                try:
                    if mes_compras == "Todos":
                        if proveedor_compras == "Todos":
                            df = sqlq_compras.get_compras_anio(anio_compras)
                        else:
                            df = sqlq_facturas.get_facturas_proveedor(proveedores=[proveedor_compras], anios=[anio_compras])
                    else:
                        mes_code = f"{anio_compras}-{month_num[mes_compras]}"
                        if proveedor_compras == "Todos":
                            df = sqlq_compras.get_compras_por_mes_excel(mes_code)
                        else:
                            df = sqlq_compras.get_detalle_compras_proveedor_mes(proveedor_compras, mes_code)
                    
                    if df is not None and not df.empty:
                        render_dashboard_compras_vendible(df, titulo="Compras")
                    elif df is not None:
                        st.warning("⚠️ No se encontraron resultados para esa búsqueda.")
                except Exception as e:
                    st.error(f"❌ Error en búsqueda: {e}")

        elif tipo_consulta == "Comparativas":
            st.markdown("#### 📊 Comparativas")
            
            # ✅ PROVEEDORES (ancho completo, sin columnas)
            proveedores_disponibles = prov_options  # Ya tiene todos los proveedores
            proveedores_sel = st.multiselect(
                "Proveedores",
                options=proveedores_disponibles,
                default=[],
                key="comparativas_proveedores_multi",
                help="Dejá vacío para comparar TODOS. Escribí para filtrar y seleccioná con Enter."
            )
            
            if proveedores_sel:
                proveedores = proveedores_sel
            else:
                proveedores = None
            
            meses_sel = st.multiselect("Meses", options=month_names, default=["Noviembre"], key="meses_sel")
            anios = st.multiselect("Años", options=[2023, 2024, 2025, 2026], default=[2024, 2025], key="anios_sel")
            # Generar combinaciones
            meses = []
            for a in anios:
                for m in meses_sel:
                    meses.append(f"{a}-{month_num[m]}")
            st.session_state["meses_multi"] = meses
            articulos = st.multiselect("Artículos", options=art_options, default=[x for x in st.session_state.get("art_multi", []) if x in art_options], key="art_multi")

            # Botón comparar
            if st.button("🔍 Comparar", type="primary", key="btn_comparar_anios"):
                if len(anios) < 2:
                    st.error("Seleccioná al menos 2 años para comparar")
                else:
                    # ✅ PAUSAR auto-refresh
                    st.session_state.comparativa_activa = True
                    
                    with st.spinner("Comparando..."):
                        try:
                            df = sqlq_comparativas.comparar_compras(
                                anios=anios,
                                proveedores=proveedores
                            )
                            
                            if df is not None and not df.empty:
                                # ✅ GUARDAR EN SESSION_STATE (esto lo hace persistente)
                                st.session_state["comparativa_resultado"] = df
                                st.session_state["comparativa_titulo"] = f"Comparación {' vs '.join(map(str, anios))}"
                                st.session_state["comparativa_activa"] = True  # Pausar auto-refresh
                                
                                st.success(f"✅ Comparación lista - {len(df)} filas")
                            else:
                                st.warning("No se encontraron datos")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
                            st.exception(e)
            
            # ✅ MOSTRAR RESULTADO GUARDADO (persiste entre refreshes)
            if "comparativa_resultado" in st.session_state:
                df_guardado = st.session_state["comparativa_resultado"]
                titulo_guardado = st.session_state.get("comparativa_titulo", "Comparación")
                
                # Botón para limpiar
                if st.button("🗑️ Limpiar resultados", key="btn_limpiar_comparativa"):
                    del st.session_state["comparativa_resultado"]
                    del st.session_state["comparativa_titulo"]
                    st.session_state["comparativa_activa"] = False  # Reactivar auto-refresh
                    st.rerun()
                
                # Mostrar dashboard con datos guardados
                render_dashboard_comparativas_moderno(
                    df_guardado,
                    titulo=titulo_guardado
                )

        # Explicación técnica (comentada)
        # st.markdown(
        #     """
        #     Función **única** para todas las variantes:<br>
        #     • Comparar proveedores años [2024,2025]<br>
        #     • Proveedores + meses<br>
        #     • Por artículo<br>
        #     • Prioriza meses si hay (meses+año); si no, años.<br>
        #     <b>Siempre usa solo UN botón comparar.</b>
        #     """, 
        #     unsafe_allow_html=True
        # )

# ... existing code ...
