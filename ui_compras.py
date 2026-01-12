# =========================
# UI_COMPRAS.PY - COMPRAS Y FACTURAS INTEGRADAS
# =========================

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional

from ia_interpretador import interpretar_pregunta, obtener_info_tipo
from utils_openai import responder_con_openai
import sql_compras as sqlq_compras
import sql_comparativas as sqlq_comparativas
import sql_facturas as sqlq_facturas


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


def render_dashboard_compras_vendible(df: pd.DataFrame, titulo: str = "Resultado", key_prefix: str = ""):
    if df is None or df.empty:
        st.warning("⚠️ No hay resultados para mostrar.")
        return

    # CSS liviano (no pisa el resto)
    st.markdown(
        """
        <style>
        .fc-subtle { color: rgba(49,51,63,0.65); font-size: 0.9rem; }
        .fc-title { font-size: 1.05rem; font-weight: 700; margin: 0 0 4px 0; }
        </style>
        """,
        unsafe_allow_html=True
    )

    df_view = df.copy()

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

    if col_total:
        df_view["__total_num__"] = df_view[col_total].apply(_safe_to_float)
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

    st.markdown(f"<div class='fc-title'>{titulo}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='fc-subtle'>Filas: <b>{filas_total}</b> · Facturas: <b>{facturas}</b> · Proveedores: <b>{proveedores}</b> · Artículos: <b>{articulos}</b>{rango_txt}</div>",
        unsafe_allow_html=True
    )
    st.write("")

    # KPIs (sobre TODO el resultado, antes de filtros)
    tot_uyu = float(df_view.loc[df_view["__moneda_view__"] == "UYU", "__total_num__"].sum())
    tot_usd = float(df_view.loc[df_view["__moneda_view__"] == "USD", "__total_num__"].sum())

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Total UYU", _fmt_compact_money(tot_uyu, "UYU"), help=f"Valor exacto: $ {tot_uyu:,.2f}".replace(",", "."))
    with k2:
        st.metric("Total USD", _fmt_compact_money(tot_usd, "USD"), help=f"Valor exacto: U$S {tot_usd:,.2f}".replace(",", "."))
    with k3:
        st.metric("Facturas", f"{facturas}")
    with k4:
        st.metric("Proveedores", f"{proveedores}")

    # ============================================================
    # FILTROS + ACCIONES (solo afectan la vista)
    # ============================================================
    # Defaults fecha
    d_ini_default, d_fin_default = None, None
    if df_view["__fecha_view__"].notna().any():
        d_ini_default = df_view["__fecha_view__"].min().date()
        d_fin_default = df_view["__fecha_view__"].max().date()

    with st.expander("🔎 Filtros (vista) / Exportar / Guardar vista", expanded=False):
        f1, f2, f3, f4 = st.columns([2, 2, 1.2, 1.6])

        sel_prov = []
        if col_proveedor:
            provs = sorted([p for p in df_view[col_proveedor].dropna().astype(str).unique().tolist() if p.strip()])
            provs = provs[:3000]
            with f1:
                sel_prov = st.multiselect("Proveedor", options=provs, default=st.session_state.get(f"{key_prefix}f_prov", []), key=f"{key_prefix}f_prov")

        sel_art = []
        if col_articulo:
            arts = sorted([a for a in df_view[col_articulo].dropna().astype(str).unique().tolist() if a.strip()])
            arts = arts[:2000]
            with f2:
                sel_art = st.multiselect("Artículo", options=arts, default=st.session_state.get(f"{key_prefix}f_art", []), key=f"{key_prefix}f_art")

        with f3:
            sel_mon = st.selectbox("Moneda", options=["TODAS", "UYU", "USD", "OTRA"], index=0, key=f"{key_prefix}f_mon")

        d_ini, d_fin = None, None
        with f4:
            if d_ini_default and d_fin_default:
                rango = st.date_input(
                    "Rango fecha",
                    value=st.session_state.get(f"{key_prefix}f_date", (d_ini_default, d_fin_default)),
                    min_value=d_ini_default,
                    max_value=d_fin_default,
                    key=f"{key_prefix}f_date"
                )
                if isinstance(rango, tuple) and len(rango) == 2:
                    d_ini, d_fin = rango[0], rango[1]
                else:
                    d_ini, d_fin = d_ini_default, d_fin_default

        # Búsqueda simple
        search_txt = st.text_input(
            "Buscar (proveedor / artículo / nro)",
            value=st.session_state.get(f"{key_prefix}f_search", ""),
            key=f"{key_prefix}f_search",
            placeholder="Ej: roche / VITEK / A00060907"
        ).strip()

        # Guardar / cargar vista
        _init_saved_views()
        vcol1, vcol2, vcol3 = st.columns([1.4, 1.4, 1.2])

        with vcol1:
            view_name = st.text_input("Nombre de vista", value="", key=f"{key_prefix}view_name", placeholder="Ej: Roche Nov 2025")

        with vcol2:
            view_pick = st.selectbox(
                "Vistas guardadas",
                options=["(ninguna)"] + _get_saved_view_names(),
                index=0,
                key=f"{key_prefix}view_pick"
            )

        with vcol3:
            b1 = st.button("💾 Guardar", key=f"{key_prefix}btn_save_view")
            b2 = st.button("↩️ Aplicar", key=f"{key_prefix}btn_load_view")

        if b1:
            _save_view(
                view_name,
                {
                    "sel_prov": sel_prov,
                    "sel_art": sel_art,
                    "sel_mon": sel_mon,
                    "d_ini": d_ini,
                    "d_fin": d_fin,
                    "search_txt": search_txt,
                }
            )
            st.success("Vista guardada.")

        if b2 and view_pick and view_pick != "(ninguna)":
            vdata = _load_view(view_pick) or {}
            try:
                st.session_state[f"{key_prefix}f_prov"] = vdata.get("sel_prov", [])
                st.session_state[f"{key_prefix}f_art"] = vdata.get("sel_art", [])
                st.session_state[f"{key_prefix}f_mon"] = vdata.get("sel_mon", "TODAS")
                if vdata.get("d_ini") and vdata.get("d_fin"):
                    st.session_state[f"{key_prefix}f_date"] = (vdata.get("d_ini"), vdata.get("d_fin"))
                st.session_state[f"{key_prefix}f_search"] = vdata.get("search_txt", "")
                st.rerun()
            except Exception:
                pass

    # ============================================================
    # APLICAR FILTROS
    # ============================================================
    df_f = df_view.copy()

    if sel_prov and col_proveedor:
        df_f = df_f[df_f[col_proveedor].astype(str).isin(sel_prov)]

    if sel_art and col_articulo:
        df_f = df_f[df_f[col_articulo].astype(str).isin(sel_art)]

    if sel_mon != "TODAS":
        df_f = df_f[df_f["__moneda_view__"] == sel_mon]

    if d_ini and d_fin:
        df_f = df_f[
            (df_f["__fecha_view__"].dt.date >= d_ini) &
            (df_f["__fecha_view__"].dt.date <= d_fin)
        ]

    if search_txt:
        mask = pd.Series([False] * len(df_f), index=df_f.index)
        for c in [col_proveedor, col_articulo, col_nro]:
            if c and c in df_f.columns:
                try:
                    mask = mask | df_f[c].astype(str).str.contains(search_txt, case=False, na=False)
                except Exception:
                    pass
        df_f = df_f[mask]

    st.caption(f"Resultados en vista: {len(df_f)}")

    # ============================================================
    # ACCIONES: DESCARGAS (vista filtrada)
    # ============================================================
    df_export = _df_export_clean(df_f)
    if len(df_export) > 0:
        d1, d2, d3 = st.columns([1, 1, 2])
        with d1:
            st.download_button(
                "⬇️ CSV (vista)",
                data=_df_to_csv_bytes(df_export),
                file_name="compras_vista.csv",
                mime="text/csv",
                key=f"{key_prefix}dl_csv"
            )
        with d2:
            st.download_button(
                "⬇️ Excel (vista)",
                data=_df_to_excel_bytes(df_export),
                file_name="compras_vista.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{key_prefix}dl_xlsx"
            )
        with d3:
            st.caption("Descarga la vista filtrada (sin columnas internas).")

    # ============================================================
    # TABS (SIN GRAFICO/TABLA EN VISTA GENERAL)
    # ============================================================
    tab_all, tab_uyu, tab_usd, tab_graf, tab_tabla = st.tabs(
        ["Vista general", "Pesos (UYU)", "Dólares (USD)", "Gráfico (Top 10 artículos)", "Tabla"]
    )

def _render_resumen_top_proveedores(df_tab: pd.DataFrame, etiqueta: str):
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


with tab_all:
    _render_resumen_top_proveedores(df_f, "todas las monedas")

with tab_uyu:
    _render_resumen_top_proveedores(df_f[df_f["__moneda_view__"] == "UYU"], "UYU")

with tab_usd:
    _render_resumen_top_proveedores(df_f[df_f["__moneda_view__"] == "USD"], "USD")

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
        # ✅ Usa sql_compras para incluir filtro de Tipo Comprobante
        df = sqlq_compras.get_facturas_proveedor_detalle(
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

    elif tipo == "facturas_articulo":
        df = sqlq_facturas.get_facturas_articulo(
            parametros["articulo"],
            solo_ultima=parametros.get("solo_ultima", False),
            limite=parametros.get("limite", 50),
        )
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
        df = sqlq_compras.get_total_facturas_por_moneda_todos_anios()
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

    inicializar_historial()

    st.markdown("### 🤖 Asistente de Compras y Facturas")

    if st.button("🗑️ Limpiar chat"):
        st.session_state["historial_compras"] = []
        _dbg_set_interpretacion({})
        _dbg_set_sql(None, "", [], None)
        st.rerun()

    st.markdown("---")

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
