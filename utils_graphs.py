# =========================
# UTILS_GRAPHS.PY - GRÁFICOS Y VISUALIZACIONES
# =========================

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional

from intent_detector import normalizar_texto
from utils_format import _fmt_num_latam, _latam_to_float, _fmt_money_latam, _pick_col

def _df_get_numeric(df: pd.DataFrame, col: str) -> pd.Series:
    if col is None or df is None or df.empty or col not in df.columns:
        return pd.Series([0.0] * (len(df) if df is not None else 0))
    ser = df[col]
    # si ya es numérico, usarlo
    if pd.api.types.is_numeric_dtype(ser):
        return pd.to_numeric(ser, errors="coerce").fillna(0.0)
    # si es string (por formatear_dataframe), parsear LATAM
    return ser.apply(_latam_to_float).fillna(0.0)


def _df_get_datetime(df: pd.DataFrame, col: str) -> Optional[pd.Series]:
    if df is None or df.empty or not col or col not in df.columns:
        return None
    try:
        # dayfirst=True por DD/MM/YYYY que aparece a veces
        return pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    except Exception:
        return None


def _es_df_compras(df: pd.DataFrame) -> bool:
    """Heurística: si parece detalle de compras (artículo/proveedor/total/fecha)."""
    if df is None or df.empty:
        return False
    c_art = _pick_col(df, ["articulo", "Artículo", "Articulo"])
    c_prov = _pick_col(df, ["proveedor", "Proveedor", "cliente / proveedor", "Cliente / Proveedor"])
    c_tot = _pick_col(df, ["total", "monto", "importe", "monto neto"])
    c_fec = _pick_col(df, ["fecha", "Fecha"])
    # basta con artículo + (total o cantidad) o proveedor + total
    c_cant = _pick_col(df, ["cantidad", "Cantidad"])
    return bool((c_art and (c_tot or c_cant)) or (c_prov and c_tot) or (c_fec and c_tot))


def _fmt_money_latam(valor: float, moneda: str = "$", dec: int = 2) -> str:
    if moneda and moneda.strip().upper() in ["U$S", "USD", "U$$"]:
        pref = "U$S "
    else:
        pref = "$ "
    return pref + _fmt_num_latam(valor, dec)


def _build_resumen_compras(df: pd.DataFrame) -> dict:
    """Devuelve métricas + top artículos."""
    if df is None or df.empty:
        return {}

    c_art = _pick_col(df, ["articulo", "Artículo", "Articulo"])
    c_prov = _pick_col(df, ["proveedor", "Proveedor", "cliente / proveedor", "Cliente / Proveedor"])
    c_fec = _pick_col(df, ["fecha", "Fecha"])
    c_mon = _pick_col(df, ["moneda", "Moneda"])
    c_fac = _pick_col(df, ["nro_factura", "N Factura", "Nro Factura", "Factura", "Nro. Comprobante", "Nro. Comprobante "])
    c_tot = _pick_col(df, ["total", "Total", "monto", "Monto", "importe", "Importe", "monto neto", "Monto Neto"])
    c_cant = _pick_col(df, ["cantidad", "Cantidad"])

    total_num = _df_get_numeric(df, c_tot) if c_tot else pd.Series([0.0] * len(df))
    cant_num = _df_get_numeric(df, c_cant) if c_cant else None

    # Totales por moneda (si existe)
    totales_por_moneda = {}
    if c_mon and c_tot:
        for m in df[c_mon].dropna().astype(str).unique():
            sub = df[df[c_mon].astype(str) == str(m)]
            sub_total = _df_get_numeric(sub, c_tot).sum()
            totales_por_moneda[str(m).strip()] = float(sub_total)

    # Fechas
    dt = _df_get_datetime(df, c_fec) if c_fec else None
    fecha_min = None
    fecha_max = None
    if dt is not None:
        try:
            fecha_min = dt.min()
            fecha_max = dt.max()
        except Exception:
            pass

    # Proveedor principal (si es casi único)
    prov_modo = None
    if c_prov:
        try:
            vc = df[c_prov].dropna().astype(str).value_counts()
            if not vc.empty:
                prov_modo = vc.index[0]
        except Exception:
            pass

    # Facturas únicas
    facturas_unicas = None
    if c_fac:
        try:
            facturas_unicas = int(df[c_fac].dropna().astype(str).nunique())
        except Exception:
            facturas_unicas = None

    # Artículos: top por total (o por cantidad si no hay total)
    top_items_df = pd.DataFrame()
    if c_art:
        if c_tot:
            tmp = df[[c_art]].copy()
            tmp["_total_"] = total_num.values
            top_items_df = (
                tmp.groupby(c_art, as_index=False)["_total_"]
                   .sum()
                   .sort_values("_total_", ascending=False)
                   .head(10)
            )
            top_items_df = top_items_df.rename(columns={c_art: "Artículo", "_total_": "Total"})
        elif c_cant:
            tmp = df[[c_art]].copy()
            tmp["_cant_"] = cant_num.values
            top_items_df = (
                tmp.groupby(c_art, as_index=False)["_cant_"]
                   .sum()
                   .sort_values("_cant_", ascending=False)
                   .head(10)
            )
            top_items_df = top_items_df.rename(columns={c_art: "Artículo", "_cant_": "Cantidad"})

    # Cantidad total (si existe)
    cantidad_total = None
    if c_cant:
        try:
            cantidad_total = float(_df_get_numeric(df, c_cant).sum())
        except Exception:
            cantidad_total = None

    return {
        "rows": int(len(df)),
        "col_total": c_tot,
        "col_moneda": c_mon,
        "col_fecha": c_fec,
        "col_factura": c_fac,
        "col_articulo": c_art,
        "col_proveedor": c_prov,
        "total_sum": float(total_num.sum()) if c_tot else None,
        "totales_por_moneda": totales_por_moneda,
        "fecha_min": fecha_min,
        "fecha_max": fecha_max,
        "proveedor_modo": prov_modo,
        "facturas_unicas": facturas_unicas,
        "cantidad_total": cantidad_total,
        "top_items_df": top_items_df
    }


# =========================
# GRÁFICOS COMPRAS (ROBUSTO)
# =========================
def _render_graficos_compras(df: pd.DataFrame, key_base: str = "detalle_df"):
    """
    Render de gráficos para compras:
    - Top artículos por total (barh)
    - Evolución por fecha (line)
    - Total por moneda (bar)

    Arregla el error típico de Plotly:
    cuando 'serie' queda como Series o DF sin reset_index().
    """
    if df is None:
        return

    if not hasattr(df, "columns"):
        return

    cols = list(df.columns)

    def _pick_col(candidates):
        for cand in candidates:
            for c in cols:
                if str(c).strip().lower() == str(cand).strip().lower():
                    return c
        return None

    col_fecha = _pick_col(["Fecha", "fecha"])
    col_total = _pick_col(["Total", "total", "Monto Neto", "monto neto", "monto_neto", "importe", "Importe"])
    col_articulo = _pick_col(["Articulo", "articulo", "Artículo", "artículo"])
    col_moneda = _pick_col(["Moneda", "moneda"])

    if col_total is None:
        st.warning("No pude armar gráficos: no encuentro la columna de total (Total/total/Monto Neto).")
        return

    # Copia local
    dfg = df.copy()

    # Limpieza numérica UY: "7.606,28" -> 7606.28 ; "(1.234,00)" -> -1234.00 ; "$" / "U$S" fuera
    def _to_number_uy(x):
        try:
            s = str(x).strip()
            if s == "" or s.lower() == "nan":
                return None
            s = s.replace("U$S", "").replace("US$", "").replace("$", "").strip()
            s = s.replace(" ", "")
            s = s.replace("\u00a0", "")
            s = s.replace("(", "-").replace(")", "")
            s = s.replace(".", "").replace(",", ".")
            return float(s)
        except Exception:
            return None

    # Total a numérico
    try:
        dfg[col_total] = dfg[col_total].apply(_to_number_uy)
        dfg[col_total] = pd.to_numeric(dfg[col_total], errors="coerce")
    except Exception:
        pass

    # Fecha a datetime si existe
    if col_fecha is not None:
        try:
            dfg[col_fecha] = pd.to_datetime(dfg[col_fecha], errors="coerce", dayfirst=True)
        except Exception:
            pass

    # Filtramos filas inválidas para graficar
    try:
        dfg = dfg.dropna(subset=[col_total])
    except Exception:
        pass

    if dfg.empty:
        st.warning("No hay datos numéricos válidos para graficar (Total vacío/no convertible).")
        return

    # Tabs
    tab1, tab2, tab3 = st.tabs(["🏷️ Top artículos", "📈 Evolución", "💱 Monedas"])

    # -------------------------
    # TOP ARTÍCULOS
    # -------------------------
    with tab1:
        if col_articulo is None:
            st.info("No encuentro columna de artículo (Articulo/articulo).")
        else:
            try:
                top = (
                    dfg.groupby(col_articulo, dropna=False)[col_total]
                    .sum()
                    .sort_values(ascending=False)
                    .head(10)
                    .reset_index()
                    .rename(columns={col_articulo: "Artículo", col_total: "Total"})
                )

                if top.empty:
                    st.info("No hay datos para Top artículos.")
                else:
                    fig1 = px.bar(top, x="Total", y="Artículo", orientation="h")
                    st.plotly_chart(fig1, use_container_width=True, key=f"{key_base}_bar_top")
            except Exception:
                st.info("No pude generar el gráfico de Top artículos (pero la app sigue).")

    # -------------------------
    # EVOLUCIÓN
    # -------------------------
    with tab2:
        if col_fecha is None:
            st.info("No encuentro columna de fecha (Fecha/fecha).")
        else:
            try:
                serie = (
                    dfg.dropna(subset=[col_fecha])
                    .groupby(col_fecha)[col_total]
                    .sum()
                    .reset_index()
                    .rename(columns={col_fecha: "Fecha", col_total: "Total"})
                    .sort_values("Fecha")
                )

                if serie.empty:
                    st.info("No hay datos para la evolución por fecha.")
                else:
                    fig2 = px.line(serie, x="Fecha", y="Total", markers=True)
                    st.plotly_chart(fig2, use_container_width=True, key=f"{key_base}_line_evo")
            except Exception:
                st.info("No pude generar el gráfico de evolución (pero la app sigue).")

    # -------------------------
    # MONEDAS
    # -------------------------
    with tab3:
        if col_moneda is None:
            st.info("No encuentro columna de moneda (Moneda/moneda).")
        else:
            try:
                mon = (
                    dfg.groupby(col_moneda, dropna=False)[col_total]
                    .sum()
                    .reset_index()
                    .rename(columns={col_moneda: "Moneda", col_total: "Total"})
                    .sort_values("Total", ascending=False)
                )

                if mon.empty:
                    st.info("No hay datos para monedas.")
                else:
                    fig3 = px.bar(mon, x="Moneda", y="Total")
                    st.plotly_chart(fig3, use_container_width=True, key=f"{key_base}_bar_mon")
            except Exception:
                st.info("No pude generar el gráfico por moneda (pero la app sigue).")


def _render_explicacion_compras(df: pd.DataFrame, contexto_respuesta: str = "") -> None:
    """Explicación simple y útil sin IA (100% determinística)."""
    info = _build_resumen_compras(df)
    if not info:
        st.info("No hay datos para explicar.")
        return

    rows = info["rows"]
    total_sum = info["total_sum"]
    totales_por_moneda = info["totales_por_moneda"] or {}
    prov = info["proveedor_modo"]
    facs = info["facturas_unicas"]
    cant_total = info["cantidad_total"]
    fmin = info["fecha_min"]
    fmax = info["fecha_max"]
    top_df = info["top_items_df"]

    st.markdown("### 🧠 Explicación")
    if contexto_respuesta:
        st.caption(contexto_respuesta)

    st.markdown(
        "- El **Total** se calcula como la **suma del importe de cada renglón** (cada renglón suele ser un artículo/línea dentro de una factura)."
    )
    st.markdown(f"- Se encontraron **{rows}** renglones (registros) en el detalle.")

    if facs is not None:
        st.markdown(f"- Facturas únicas detectadas: **{facs}**.")

    if prov:
        st.markdown(f"- Proveedor más frecuente en el detalle: **{prov}**.")

    if fmin is not None and fmax is not None:
        try:
            st.markdown(
                f"- Rango de fechas: **{fmin.date().strftime('%d/%m/%Y')}** → **{fmax.date().strftime('%d/%m/%Y')}**."
            )
        except Exception:
            pass

    # Totales por moneda si aplica
    if totales_por_moneda:
        st.markdown("#### 💰 Total por moneda")
        for mon, val in totales_por_moneda.items():
            mon_norm = str(mon).strip()
            if mon_norm.upper() in ["U$S", "USD", "U$$"]:
                st.markdown(f"- **{mon_norm}**: **{_fmt_money_latam(val, 'U$S')}**")
            else:
                st.markdown(f"- **{mon_norm or '$'}**: **{_fmt_money_latam(val, '$')}**")
    else:
        # Total general si no hay moneda
        if total_sum is not None:
            st.markdown(f"- Total (sumatoria): **{_fmt_money_latam(total_sum, '$')}**")

    if cant_total is not None and cant_total > 0:
        st.markdown(f"- Cantidad total (sumatoria de cantidades): **{_fmt_num_latam(cant_total, 2)}**")

    # Top artículos
    if top_df is not None and not top_df.empty:
        st.markdown("#### 🏷️ Artículos que más impactan")
        show = top_df.copy()
        if "Total" in show.columns:
            show["Total"] = show["Total"].apply(lambda x: _fmt_money_latam(float(x), "$"))
        st.dataframe(show, use_container_width=True, hide_index=True)

        st.markdown(
            "- Estos son los artículos con **mayor impacto** (por importe o por cantidad, según lo que tenga el detalle)."
        )

