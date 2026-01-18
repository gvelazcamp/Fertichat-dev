import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional

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


def render_dashboard_compras_vendible(df: pd.DataFrame, titulo: str = "Resultado", key_prefix: str = "", hide_metrics: bool = False):
    if df is None or df.empty:
        st.warning("⚠️ No hay resultados para mostrar.")
        return

    # CSS MODERNO (header gradiente + tarjetas)
    st.markdown(
        """
        <style>
        /* ==========================================
           HEADER CON TÍTULO Y METADATA
           ========================================== */
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
            margin: 0;
            color: rgba(255,255,255,0.9);
        }
        
        /* ==========================================
           TARJETAS DE MÉTRICAS (4 columnas)
           ========================================== */
        .fc-metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 32px;  /* ← Aumentado de 16px a 32px para más separación */
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
        
        /* ==========================================
           CARD TOTAL GRANDE
           ========================================== */
        .total-summary-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px;
            padding: 40px 32px;
            margin-bottom: 24px;
            color: white;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
            text-align: center;
        }
        
        .total-summary-value {
            font-size: 3rem;
            font-weight: 700;
            margin: 0 0 8px 0;
        }
        
        .total-summary-label {
            font-size: 1.2rem;
            opacity: 0.9;
            margin: 0;
        }
        
        /* ==========================================
           CARD RESUMEN EJECUTIVO
           ========================================== */
        .resumen-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }
        
        .resumen-title {
            font-size: 1rem;
            font-weight: 700;
            margin: 0 0 8px 0;
            color: #374151;
        }
        
        .resumen-text {
            font-size: 0.9rem;
            color: #6b7280;
            margin: 0;
        }
        
        /* ==========================================
           PROVIDER CARD
           ========================================== */
        .provider-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }
        
        .provider-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }
        
        .provider-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
            color: white;
            font-weight: 700;
        }
        
        .provider-info {
            flex: 1;
        }
        
        .provider-name {
            font-size: 0.95rem;
            font-weight: 700;
            color: #111827;
            margin: 0 0 2px 0;
        }
        
        .provider-subtitle {
            font-size: 0.8rem;
            color: #6b7280;
            margin: 0;
        }
        
        .provider-amount {
            font-size: 1.2rem;
            font-weight: 700;
            color: #111827;
            text-align: right;
        }
        
        .provider-amount-sub {
            font-size: 0.8rem;
            color: #6b7280;
            text-align: right;
            margin-top: 2px;
        }
        
        .progress-bar {
            width: 100%;
            height: 6px;
            background: #e5e7eb;
            border-radius: 3px;
            overflow: hidden;
            margin: 8px 0;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 3px;
        }
        
        /* ==========================================
           RESPONSIVE (MOBILE)
           ========================================== */
        @media (max-width: 768px) {
            .fc-metrics-grid {
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
            }
            .fc-metric-value {
                font-size: 1.3rem;
            }
            .total-summary-value {
                font-size: 2.5rem;
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
        
        /* ==========================================
           OCULTAR LÍNEAS HORIZONTALES (hr) GENERADAS POR st.markdown("---")
           ========================================== */
        hr {
            display: none !important;
        }
        
        /* Botón de exportación arriba */
        .fc-export-btn {
            text-align: right;
            margin-bottom: 8px;
        }
        """ + (".fc-metrics-grid { display: none !important; }" if hide_metrics else "") + """
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
    # MÉTRICAS CON TARJETAS MODERNAS (ocultas si hide_metrics)
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
    # SIN FILTROS (mostrar todo)
    # ============================================================
    df_f = df_view.copy()

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
        # Resumen ejecutivo
        col_resumen, col_top = st.columns([2, 1])
        
        with col_resumen:
            # PERÍODO
            st.markdown(f"""
            <div class="resumen-card">
                <h4 class="resumen-title">📅 Período Analizado</h4>
                <p class="resumen-text">{rango_txt if rango_txt else 'Sin datos de fecha'}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # ACTIVIDAD EN EL TIEMPO
            if col_fecha and not df_f.empty:
                df_f['fecha_dt'] = pd.to_datetime(df_f[col_fecha], errors='coerce')
                df_f['fecha_str'] = df_f['fecha_dt'].dt.strftime('%d/%m')
                gasto_diario = df_f.groupby('fecha_str')['__total_num__'].sum()
                if col_nro:
                    facturas_diario = df_f.groupby('fecha_str')[col_nro].nunique()
                else:
                    facturas_diario = df_f.groupby('fecha_str').size()
                
                if not gasto_diario.empty:
                    dia_mayor_gasto = gasto_diario.idxmax()
                    mayor_gasto = gasto_diario.max()
                    
                    dia_mas_facturas = facturas_diario.idxmax()
                    mas_facturas = facturas_diario.max()
                    
                    promedio_diario = gasto_diario.mean()
                    
                    st.markdown(f"""
                    <div class="resumen-card">
                        <h4 class="resumen-title">⏰ Actividad en el Tiempo</h4>
                        <p class="resumen-text">
                            Día con mayor gasto: {dia_mayor_gasto} — {_fmt_compact_money(mayor_gasto, "UYU")}<br>
                            Día con más facturas: {dia_mas_facturas} — {mas_facturas} facturas<br>
                            Promedio diario: {_fmt_compact_money(promedio_diario, "UYU")}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
            
            # PRINCIPAL PROVEEDOR (si hay más de 1)
            if proveedores > 1 and col_proveedor:
                # Calcular proveedor con mayor monto
                df_prov = df_view.groupby(col_proveedor)["__total_num__"].sum().sort_values(ascending=False)
                top_prov = df_prov.index[0]
                top_monto = df_prov.iloc[0]
                top_porc = (top_monto / df_view["__total_num__"].sum()) * 100
                
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
                        {top_porc:.1f}% del total
                    </p>
                </div>
                """, unsafe_allow_html=True)
        
        with col_top:
            # ✅ TOP 5 ARTÍCULOS EN DOS TARJETAS SEPARADAS
            if col_articulo and not df_f.empty:
                top_art = (
                    df_f.groupby(col_articulo)["__total_num__"]
                    .sum()
                    .sort_values(ascending=False)
                ).head(5)
                
                if len(top_art) > 0:
                    # Primera tarjeta: Título
                    st.markdown("""
                    <div class="resumen-card">
                        <h4 class="resumen-title">🏆 Top 5 Artículos</h4>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Segunda tarjeta: Lista
                    top_list = "<br>".join([f"<span class='numero-badge'>{i+1}</span> {_shorten_text(art, 30)} - {_fmt_compact_money(tot, 'UYU')}" for i, (art, tot) in enumerate(top_art.items())])
                    
                    st.markdown(f"""
                    <div class="resumen-card">
                        <p class="resumen-text">
                            {top_list}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div class="resumen-card">
                        <h4 class="resumen-title">🏆 Top 5 Artículos</h4>
                        <p class="resumen-text">Sin artículos para mostrar.</p>
                    </div>
                    """, unsafe_allow_html=True)

    with tab_uyu:
        # Calcular total UYU
        total_uyu_tab = df_f[df_f["__moneda_view__"] == "UYU"]["__total_num__"].sum()
        
        st.markdown(f"""
        <div class="total-summary-card">
            <p class="total-summary-value">{_fmt_compact_money(total_uyu_tab, "UYU")}</p>
            <p class="total-summary-label">Total Pesos (UYU)</p>
        </div>
        """, unsafe_allow_html=True)

    with tab_usd:
        # Calcular total USD
        total_usd_tab = df_f[df_f["__moneda_view__"] == "USD"]["__total_num__"].sum()
        
        st.markdown(f"""
        <div class="total-summary-card">
            <p class="total-summary-value">{_fmt_compact_money(total_usd_tab, "USD")}</p>
            <p class="total-summary-label">Total Dólares (USD)</p>
        </div>
        """, unsafe_allow_html=True)

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
# DASHBOARD COMPARATIVAS MODERNO
# =========================
def render_dashboard_comparativas_moderno(df: pd.DataFrame, titulo: str = "Comparativas"):
    """
    Dashboard con diseño moderno tipo card (similar a la imagen)
    """
    
    if df is None or df.empty:
        st.warning("⚠️ No hay datos para mostrar")
        return
    
    # ==========================================
    # CALCULAR MÉTRICAS CORRECTAMENTE
    # ==========================================
    
    # Identificar columnas numéricas (años/meses: 2024, 2025, 2024-11, etc)
    # Excluir "Diferencia" para no contar doble
    cols_numericas = [c for c in df.columns if c not in ['Proveedor', 'Moneda', 'Diferencia'] and pd.api.types.is_numeric_dtype(df[c])]
    
    # Calcular totales por moneda
    if 'Moneda' in df.columns:
        df_pesos = df[df['Moneda'] == '$']
        df_usd = df[df['Moneda'].isin(['U$S', 'USD', 'U$$'])]
        
        # Sumar SOLO las columnas de años/meses (no la diferencia)
        total_uyu = df_pesos[cols_numericas].sum().sum() if not df_pesos.empty else 0
        total_usd = df_usd[cols_numericas].sum().sum() if not df_usd.empty else 0
        
        # ✅ FIX: Si no hay separación por moneda, sumar todo como UYU
        if total_uyu == 0 and total_usd == 0:
            total_uyu = df[cols_numericas].sum().sum()
            total_usd = 0
    else:
        # Sin columna moneda: asumir todo UYU
        total_uyu = df[cols_numericas].sum().sum()
        total_usd = 0
    
    # Número de proveedores y registros
    num_proveedores = df['Proveedor'].nunique() if 'Proveedor' in df.columns else 0
    num_registros = len(df)
    
    # Identificar qué años/meses se están comparando
    periodos = [c for c in cols_numericas if c.isdigit() or '-' in str(c)]
    num_periodos = len(periodos)
    
    # ==========================================
    # BARRA DE ACCIONES SUPERIOR (CSV, Excel, Guardar Vista, Filtros)
    # ==========================================
    st.markdown("""
    <style>
        .action-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 20px;
            gap: 12px;
        }
        
        .action-left {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .action-right {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .btn-action {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: white;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 0.85rem;
            font-weight: 500;
            color: #374151;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .btn-action:hover {
            background: #f9fafb;
            border-color: #9ca3af;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Barra de acciones
    col_actions_left, col_actions_right = st.columns([3, 1])
    with col_actions_left:
        st.markdown("""
        <div class="action-bar">
            <div class="action-left">
                <button class="btn-action">📊 CSV</button>
                <button class="btn-action">📥 Excel</button>
                <button class="btn-action">💾 Guardar vista</button>
            </div>
            <div class="action-right">
                <button class="btn-action">🔍 Filtros</button>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # CSS Moderno (restante)
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
            gap: 32px;  /* ← Aumentado de 16px a 32px para más separación */
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
           CARD PROVEEDOR DESTACADO (para 1 proveedor)
           ========================================== */
        .single-provider-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px;
            padding: 32px 28px;
            margin-bottom: 24px;
            color: white;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
            text-align: center;
        }
        
        .single-provider-icon {
            width: 64px;
            height: 64px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 16px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 16px;
        }
        
        .single-provider-name {
            font-size: 1.5rem;
            font-weight: 700;
            margin: 0 0 8px 0;
        }
        
        .single-provider-detail {
            font-size: 0.9rem;
            opacity: 0.9;
            margin: 0;
        }
        
        /* ==========================================
           CARD PROVEEDOR PRINCIPAL
           ========================================== */
        .provider-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }
        
        .provider-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }
        
        .provider-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
            color: white;
            font-weight: 700;
        }
        
        .provider-info {
            flex: 1;
        }
        
        .provider-name {
            font-size: 0.95rem;
            font-weight: 700;
            color: #111827;
            margin: 0 0 2px 0;
        }
        
        .provider-subtitle {
            font-size: 0.8rem;
            color: #6b7280;
            margin: 0;
        }
        
        .provider-amount {
            font-size: 1.2rem;
            font-weight: 700;
            color: #111827;
            text-align: right;
        }
        
        .provider-amount-sub {
            font-size: 0.8rem;
            color: #6b7280;
            text-align: right;
            margin-top: 2px;
        }
        
        .progress-bar {
            width: 100%;
            height: 6px;
            background: #e5e7eb;
            border-radius: 3px;
            overflow: hidden;
            margin: 8px 0;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 3px;
        }
        
        /* ==========================================
           TABS Y BOTONES
           ========================================== */
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
            
            .action-bar {
                flex-direction: column;
                align-items: stretch;
            }
            
            .action-left, .action-right {
                justify-content: center;
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
        <h2 class="dash-title">📊 {titulo}</h2>
        <div class="dash-badge">
            ✅ Resultado: Se encontraron {len(df)} registros
        </div>
        <p class="dash-meta">
            📅 Última actualización: {datetime.now().strftime("%d/%m/%Y %H:%M")}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # MÉTRICAS
    # Formatear totales
    total_uyu_fmt = f"$ {total_uyu/1_000_000:.2f}M" if total_uyu >= 1_000_000 else f"$ {total_uyu:,.0f}".replace(",", ".")
    total_usd_fmt = f"U$S {total_usd/1_000:.0f}K" if total_usd >= 1_000 else f"U$S {total_usd:,.0f}"
    
    st.markdown(f"""
    <div class="metrics-grid">
        <div class="metric-card">
            <p class="metric-label">Total UYU 💰</p>
            <p class="metric-value">{total_uyu_fmt}</p>
            <p style="font-size: 0.75rem; color: #9ca3af; margin-top: 4px;">
                Suma de {len(periodos)} período(s)
            </p>
        </div>
        <div class="metric-card">
            <p class="metric-label">Total USD 💵</p>
            <p class="metric-value">{total_usd_fmt}</p>
            <p style="font-size: 0.75rem; color: #9ca3af; margin-top: 4px;">
                Suma de {len(periodos)} período(s)
            </p>
        </div>
        <div class="metric-card">
            <p class="metric-label">Registros 📄</p>
            <p class="metric-value">{num_registros}</p>
            <p style="font-size: 0.75rem; color: #9ca3af; margin-top: 4px;">
                {len(df_pesos) if 'Moneda' in df.columns and not df_pesos.empty else 0} en pesos, {len(df_usd) if 'Moneda' in df.columns and not df_usd.empty else 0} en USD
            </p>
        </div>
        <div class="metric-card">
            <p class="metric-label">Proveedores 🏭</p>
            <p class="metric-value">{num_proveedores}</p>
            <p style="font-size: 0.75rem; color: #9ca3af; margin-top: 4px;">
                Comparando {', '.join(map(str, periodos[:3]))}{"..." if len(periodos) > 3 else ""}
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ==========================================
    # CARD DESTACADA PARA 1 PROVEEDOR
    # ==========================================
    if num_proveedores == 1 and 'Proveedor' in df.columns:
        prov_name = df['Proveedor'].iloc[0]
        iniciales = "".join([p[0] for p in prov_name.split()[:2]]).upper()
        
        st.markdown(f"""
        <div class="single-provider-card">
            <div class="single-provider-icon">{iniciales}</div>
            <h3 class="single-provider-name">{prov_name}</h3>
            <p class="single-provider-detail">
                Comparación de {len(periodos)} períodos | Total: {total_uyu_fmt}
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # PROVEEDOR PRINCIPAL (si hay más de 1)
    elif num_proveedores > 1 and 'Proveedor' in df.columns and not df.empty:
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
            try:
                import plotly.express as px
                fig = px.bar(
                    df.groupby('Proveedor').sum(numeric_only=True).reset_index(),
                    x='Proveedor',
                    y=df.select_dtypes(include='number').columns[0],
                    title="Distribución por Proveedor"
                )
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                st.info("Plotly no disponible")
            except Exception:
                st.info("No se pudo generar el gráfico")
    
    with tabs[4]:
        st.dataframe(df, use_container_width=True, height=600)


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
# UI PRINCIPAL
# =========================
def Compras_IA():

    # =========================
    # DISEÑO MÁS COMPACTO Y VISIBLE
    # =========================
    st.markdown("""
    <style>
    /* ========================================
       HEADER MÁS COMPACTO
       ======================================== */
    .fc-header-modern,
    .dash-header {
        padding: 12px 16px !important;  /* Más pequeño */
        margin-bottom: 16px !important;
        border-radius: 10px !important;
    }
    
    .fc-title-modern,
    .dash-title {
        font-size: 1rem !important;  /* Más pequeño */
        margin-bottom: 4px !important;
        font-weight: 700 !important;
    }
    
    .fc-badge-modern,
    .dash-badge {
        font-size: 0.7rem !important;  /* Más pequeño */
        padding: 3px 8px !important;
        border-radius: 10px !important;
        margin-bottom: 4px !important;
    }
    
    .fc-meta-modern,
    .dash-meta {
        font-size: 0.7rem !important;  /* Más pequeño */
        margin: 0 !important;
        line-height: 1.2 !important;
    }
    
    /* ========================================
       TARJETAS MÉTRICAS MÁS CHICAS
       ======================================== */
    .fc-metrics-grid,
    .metrics-grid {
        gap: 16px !important;  /* Más pequeño para más tarjetas visibles */
        margin-bottom: 24px !important;
    }
    
    .fc-metric-card,
    .metric-card {
        padding: 12px 16px !important;  /* Más pequeño */
        border-radius: 10px !important;
    }
    
    .fc-metric-label,
    .metric-label {
        font-size: 0.75rem !important;  /* Más pequeño */
        margin-bottom: 4px !important;
    }
    
    .fc-metric-value,
    .metric-value {
        font-size: 1.2rem !important;  /* Más pequeño pero legible */
        font-weight: 700 !important;
    }
    
    .fc-metric-help {
        font-size: 0.65rem !important;  /* Más pequeño */
    }
    
    /* ========================================
       CARDS DE RESUMEN CON MISMO ALTO + MÁS ESPACIO
       ======================================== */
    
    /* Todas las cards de resumen con altura uniforme */
    .resumen-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 14px 18px !important;
        margin-bottom: 24px !important;  /* ← MÁS ESPACIO ENTRE CARDS (antes 12px) */
        min-height: 120px !important;  /* ← MÁS BAJA (antes 140px) */
        display: flex !important;
        flex-direction: column !important;
        box-sizing: border-box !important;
    }
    
    /* Título de la card */
    .resumen-title {
        font-size: 0.8rem !important;  /* Un poco más pequeño */
        font-weight: 700 !important;
        margin: 0 0 6px 0 !important;
        color: #374151;
    }
    
    /* Texto de la card */
    .resumen-text {
        font-size: 0.7rem !important;  /* Un poco más pequeño */
        color: #6b7280;
        margin: 0 !important;
        line-height: 1.3 !important;  /* Menos interlineado */
    }
    
    /* Badge para números en lista */
    .numero-badge {
        display: inline-block;
        background: #667eea;  /* Violeta */
        color: white;
        border-radius: 50%;
        padding: 1px 5px;
        font-size: 0.7rem;
        font-weight: bold;
        margin-right: 4px;
        width: 18px;
        height: 18px;
        text-align: center;
        line-height: 16px;
    }
    
    /* Provider card también con mismo alto */
    .provider-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 16px !important;
        margin-bottom: 24px !important;  /* ← MÁS ESPACIO */
        min-height: 120px !important;  /* ← MÁS BAJA */
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        display: flex !important;
        flex-direction: column !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px !important;  /* Más pequeño */
        margin-bottom: 16px !important;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-size: 0.8rem !important;  /* Más pequeño */
        padding: 5px 10px !important;
    }
    
    /* Total summary card */
    .total-summary-card {
        padding: 16px 14px !important;  /* Más pequeño */
        margin-bottom: 16px !important;
    }
    
    .total-summary-value {
        font-size: 1.6rem !important;  /* Más pequeño */
    }
    
    .total-summary-label {
        font-size: 0.85rem !important;
    }
    
    /* Provider card destacado */
    .single-provider-card {
        padding: 16px 14px !important;  /* Más pequeño */
        margin-bottom: 16px !important;
    }
    
    .single-provider-icon {
        width: 40px !important;  /* Más pequeño */
        height: 40px !important;
        font-size: 1.3rem !important;
    }
    
    .single-provider-name {
        font-size: 1rem !important;
    }
    
    /* Responsive - Mobile */
    @media (max-width: 768px) {
        .main .block-container {
            padding: 0.5rem 1rem !important;
        }
        
        .fc-metrics-grid,
        .metrics-grid {
            gap: 8px !important;
            grid-template-columns: repeat(2, 1fr) !important;
        }
        
        .fc-metric-value,
        .metric-value {
            font-size: 1rem !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    inicializar_historial()

    # ✅ INICIALIZAR FLAG PARA PAUSAR AUTOREFRESH
    if "pause_autorefresh" not in st.session_state:
        st.session_state["pause_autorefresh"] = False

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
    tab_chat, tab_comparativas = st.tabs(["💬Compras", "Filtros de Comparación"])

    with tab_chat:
        # BOTÓN LIMPIAR (solo en chat)
        if st.button("🗑️ Limpiar chat"):
            st.session_state["historial_compras"] = []
            _dbg_set_interpretacion({})
            _dbg_set_sql(None, "", [], None)
            st.session_state["pause_autorefresh"] = False  # ✅ REACTIVAR AUTOREFRESH
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
            padding: 12px 16px;
            margin: 16px 0 12px 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        ">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                <span style="font-size: 18px;">💡</span>
                <span style="font-size: 14px; font-weight: 700; color: rgb(234, 88, 12);">Ejemplos de preguntas:</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px 20px; font-size: 12px; color: rgb(154, 52, 18);">
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
        # ✅ PAUSAR AUTOREFRESH AL HACER UNA PREGUNTA
        st.session_state["pause_autorefresh"] = True

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
        # ==========================================
        # CSS PROFESIONAL PARA EL MENÚ COMPARATIVAS
        # ==========================================
        st.markdown("""
        <style>
        /* ==============================================
           MENÚ COMPARATIVAS - DISEÑO PROFESIONAL
           ============================================== */

        /* Header con título y selector de tipo */
        .comparativas-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }

        .comparativas-title-section {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        /* Icono SVG azul */
        .comparativas-title-section svg {
            width: 24px;
            height: 24px;
            fill: #2563eb;
        }

        .comparativas-title-section h4 {
            margin: 0;
            font-size: 1.2rem;
            font-weight: 600;
            color: #1e293b;
        }

        /* Selector "Comparativas" arriba a la derecha */
        section[data-testid="stMain"] div[data-baseweb="select"]:first-of-type {
            max-width: 180px;
        }

        /* Subtítulo descriptivo */
        section[data-testid="stMain"] > div > div > div > p:first-of-type {
            color: #64748b;
            font-size: 0.9rem;
            margin-bottom: 1.5rem;
        }

        /* Labels de los campos */
        section[data-testid="stMain"] label {
            font-weight: 500;
            color: #334155;
            font-size: 0.95rem;
            margin-bottom: 0.5rem;
        }

        /* Selectboxes y multiselects */
        section[data-testid="stMain"] div[data-baseweb="select"] {
            border-radius: 8px;
            border: 1.5px solid #e2e8f0;
            transition: all 0.2s ease;
        }

        section[data-testid="stMain"] div[data-baseweb="select"]:hover {
            border-color: #3b82f6;
        }

        section[data-testid="stMain"] div[data-baseweb="select"]:focus-within {
            border-color: #2563eb;
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
        }

        /* Pills de selección (2024, 2025, 30G ANA PROFILE, etc) */
        section[data-testid="stMain"] span[data-baseweb="tag"] {
            background-color: #1e40af !important;
            color: white !important;
            border-radius: 6px !important;
            padding: 5px 12px !important;
            font-size: 0.875rem !important;
            font-weight: 500 !important;
        }

        section[data-testid="stMain"] span[data-baseweb="tag"] svg {
            color: white !important;
            opacity: 0.9;
        }

        section[data-testid="stMain"] span[data-baseweb="tag"]:hover svg {
            opacity: 1;
        }

        /* ==============================================
           BOTONES PRINCIPALES (Comparar y Limpiar)
           ============================================== */

        /* Container de botones principales */
        section[data-testid="stMain"] .row-widget.stButton {
            display: inline-block;
            margin-right: 12px;
        }

        /* Botón Comparar - Azul con gradiente */
        section[data-testid="stMain"] button[kind="primary"] {
            background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.6rem 2rem !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25) !important;
            transition: all 0.3s ease !important;
            min-width: 140px !important;
        }

        section[data-testid="stMain"] button[kind="primary"]:hover {
            box-shadow: 0 6px 16px rgba(37, 99, 235, 0.35) !important;
            transform: translateY(-2px) !important;
        }

        /* Botón Limpiar resultados - Gris suave */
        section[data-testid="stMain"] button[kind="secondary"] {
            background: white !important;
            color: #64748b !important;
            border: 1.5px solid #e5e7eb !important;
            border-radius: 8px !important;
            padding: 0.6rem 1.5rem !important;
            font-weight: 500 !important;
            font-size: 0.95rem !important;
            transition: all 0.2s ease !important;
            min-width: 180px !important;
        }

        section[data-testid="stMain"] button[kind="secondary"]:hover {
            background: #f8fafc !important;
            border-color: #cbd5e1 !important;
        }

        /* ==============================================
           BOTONES SECUNDARIOS (CSV, Excel, Guardar, Filtros)
           ============================================== */

        /* Separación entre botones principales y secundarios */
        section[data-testid="stMain"] .stButton + .stButton + .stButton {
            margin-top: 1.5rem;
        }

        /* Botones secundarios más pequeños */
        section[data-testid="stMain"] button:not([kind="primary"]):not([kind="secondary"]) {
            background: white !important;
            color: #64748b !important;
            border: 1px solid #e5e7eb !important;
            border-radius: 6px !important;
            padding: 0.4rem 0.9rem !important;
            font-size: 0.85rem !important;
            font-weight: 500 !important;
            transition: all 0.2s ease !important;
            margin-right: 8px !important;
        }

        section[data-testid="stMain"] button:not([kind="primary"]):not([kind="secondary"]):hover {
            background: #f9fafb !important;
            border-color: #cbd5e1 !important;
        }

        /* Espaciado entre campos del formulario */
        section[data-testid="stMain"] div[data-testid="stVerticalBlock"] > div {
            margin-bottom: 1rem;
        }

        /* Mejorar dropdown options hover */
        section[data-testid="stMain"] li[role="option"]:hover {
            background-color: #eff6ff !important;
        }

        /* ==============================================
           RESPONSIVE MOBILE
           ============================================== */
        @media (max-width: 768px) {
            .comparativas-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 12px;
            }
            
            section[data-testid="stMain"] div[data-baseweb="select"]:first-of-type {
                max-width: 100%;
            }
            
            section[data-testid="stMain"] button {
                width: 100% !important;
                margin-bottom: 0.5rem !important;
                margin-right: 0 !important;
            }
        }

        /* ==============================================
           OCULTAR ELEMENTOS INNECESARIOS
           ============================================== */

        /* Ocultar título duplicado de Streamlit */
        section[data-testid="stMain"] h3:has(span:contains("Comparativas")),
        section[data-testid="stMain"] h4:has(span:contains("Comparativas")) {
            display: none !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # HTML Header
        st.markdown("""
        <div class="comparativas-header">
            <div class="comparativas-title-section">
                <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M9 11H7v8h2v-8zm4-4h-2v12h2V7zm4-4h-2v16h2V3z"/>
                </svg>
                <h4>Filtros de Comparación</h4>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("Selecciona opciones y compara proveedores, meses y años directamente.")

        # Selector de tipo de consulta (Comparativas) - arriba a la derecha
        tipo_consulta = st.selectbox("", options=["Comparativas"], index=0, key="tipo_consulta", label_visibility="collapsed")

        if tipo_consulta == "Comparativas":
            # ✅ PAUSAR AUTOREFRESH EN COMPARATIVAS
            st.session_state["pause_autorefresh"] = True
            
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

            # Botones principales (en columnas para que queden lado a lado)
            col_btn1, col_btn2, col_resto = st.columns([1.2, 1.5, 3])
            with col_btn1:
                if st.button("🔍 Comparar", key="btn_comparar", type="primary"):
                    if len(anios) < 2:
                        st.error("Seleccioná al menos 2 años para comparar")
                    else:
                        # ✅ PAUSAR AUTOREFRESH
                        st.session_state.comparativa_activa = True
                        
                        with st.spinner("Comparando..."):
                            try:
                                df = sqlq_comparativas.comparar_compras(
                                    anios=anios,
                                    proveedores=proveedores,
                                    articulos=articulos  # ← AGREGADO: Pasar artículos seleccionados
                                )
                                
                                if df is not None and not df.empty:
                                    # ✅ CONSTRUIR TÍTULO CON PROVEEDOR
                                    titulo_provs = ""
                                    if proveedores_sel:
                                        if len(proveedores_sel) == 1:
                                            # Un solo proveedor: mostrar nombre completo
                                            titulo_provs = f"{proveedores_sel[0]} - "
                                        elif len(proveedores_sel) <= 3:
                                            # 2-3 proveedores: mostrar todos
                                            titulo_provs = f"{', '.join(proveedores_sel)} - "
                                        else:
                                            # Más de 3: mostrar cantidad
                                            titulo_provs = f"{len(proveedores_sel)} proveedores - "
                                    else:
                                        titulo_provs = "Todos los proveedores - "
                                    
                                    # ✅ GUARDAR EN SESSION_STATE
                                    st.session_state["comparativa_resultado"] = df
                                    st.session_state["comparativa_titulo"] = f"{titulo_provs}Comparación {' vs '.join(map(str, anios))}"
                                    st.session_state["comparativa_activa"] = True
                                    
                                    st.success(f"✅ Comparación lista - {len(df)} filas")
                                else:
                                    st.warning("No se encontraron datos")
                            except Exception as e:
                                st.error(f"❌ Error: {e}")
                                st.exception(e)

            with col_btn2:
                if st.button("🗑️ Limpiar resultados", key="btn_limpiar", type="secondary"):
                    if "comparativa_resultado" in st.session_state:
                        del st.session_state["comparativa_resultado"]
                    if "comparativa_titulo" in st.session_state:
                        del st.session_state["comparativa_titulo"]
                    st.session_state["comparativa_activa"] = False  # Reactivar auto-refresh
                    st.rerun()

            # Espacio y botones secundarios
            st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

            col_csv, col_excel, col_guardar, col_filtros = st.columns([1, 1, 1.2, 5])
            with col_csv:
                st.button("📊 CSV")
            with col_excel:
                st.button("📥 Excel")
            with col_guardar:
                st.button("💾 Guardar vista")
            # col_filtros queda vacío para empujar "Filtros" a la derecha si lo necesitás
            
            # ✅ MOSTRAR RESULTADO GUARDADO (persiste entre refreshes)
            if "comparativa_resultado" in st.session_state:
                df_guardado = st.session_state["comparativa_resultado"]
                titulo_guardado = st.session_state.get("comparativa_titulo", "Comparación")
                
                # Mostrar dashboard con datos guardados
                render_dashboard_comparativas_moderno(
                    df_guardado,
                    titulo=titulo_guardado
                )

        # Botón para reanudar auto-refresh (opcional, si se pausa)
        if st.session_state.get("pause_autorefresh", False):
            st.markdown("---")
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("▶️ Reanudar auto-refresh", help="Reactivar auto-refresh automático"):
                    st.session_state["pause_autorefresh"] = False
                    st.rerun()

    # ✅ AUTOREFRESH CONDICIONAL: SOLO SI NO ESTÁ PAUSADO
    if not st.session_state.get("pause_autorefresh", False):
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=5000, key="fc_keepalive")
        except Exception:
            pass
