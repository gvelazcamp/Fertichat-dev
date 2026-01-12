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

    # Filtros (solo afectan la vista)
    with st.expander("🔎 Filtros (vista)", expanded=False):
        f1, f2, f3, f4 = st.columns([2, 2, 1.2, 1.6])

        sel_prov = []
        if col_proveedor:
            provs = sorted([p for p in df_view[col_proveedor].dropna().astype(str).unique().tolist() if p.strip()])
            provs = provs[:3000]
            with f1:
                sel_prov = st.multiselect("Proveedor", options=provs, default=[], key=f"{key_prefix}f_prov")

        sel_art = []
        if col_articulo:
            arts = sorted([a for a in df_view[col_articulo].dropna().astype(str).unique().tolist() if a.strip()])
            arts = arts[:2000]
            with f2:
                sel_art = st.multiselect("Artículo", options=arts, default=[], key=f"{key_prefix}f_art")

        with f3:
            sel_mon = st.selectbox("Moneda", options=["TODAS", "UYU", "USD", "OTRA"], index=0, key=f"{key_prefix}f_mon")

        d_ini, d_fin = None, None
        if df_view["__fecha_view__"].notna().any():
            min_d = df_view["__fecha_view__"].min().date()
            max_d = df_view["__fecha_view__"].max().date()
            with f4:
                rango = st.date_input(
                    "Rango fecha",
                    value=(min_d, max_d),
                    min_value=min_d,
                    max_value=max_d,
                    key=f"{key_prefix}f_date"
                )
            if isinstance(rango, tuple) and len(rango) == 2:
                d_ini, d_fin = rango[0], rango[1]
            else:
                d_ini, d_fin = min_d, max_d

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

    st.caption(f"Resultados en vista: {len(df_f)}")

    # Tabs por moneda
    tab_all, tab_uyu, tab_usd = st.tabs(["Vista general", "Pesos (UYU)", "Dólares (USD)"])

    def _render_tab(df_tab: pd.DataFrame, etiqueta: str):
        if df_tab is None or df_tab.empty:
            st.info(f"Sin resultados en {etiqueta}.")
            return

        # Resumen simple (sin OpenAI)
        if col_proveedor:
            top = (
                df_tab.groupby(col_proveedor)["__total_num__"]
                .sum()
                .sort_values(ascending=False)
            )
            total_val = float(df_tab["__total_num__"].sum())
            if len(top) > 0 and total_val:
                prov_top = str(top.index[0])
                val_top = float(top.iloc[0])
                share = val_top / total_val * 100.0
                st.markdown(f"**Resumen:** principal proveedor **{prov_top}** con **{share:.1f}%** del total en {etiqueta}.")

            # Top proveedores (tabla + gráfico)
            df_top = top.head(12).reset_index()
            df_top.columns = [col_proveedor, "Total"]
            st.dataframe(df_top, use_container_width=True, hide_index=True, height=260)

            try:
                chart_df = df_top.set_index(col_proveedor)["Total"]
                st.bar_chart(chart_df)
            except Exception:
                pass

        st.write("")
        # Tabla detalle (orden preferido)
        pref = []
        for c in [col_proveedor, col_articulo, col_nro, col_fecha, col_cantidad, col_moneda, col_total]:
            if c and c in df_tab.columns:
                pref.append(c)
        resto = [c for c in df_tab.columns if c not in pref and not str(c).startswith("__")]
        show_cols = pref + resto

        st.dataframe(df_tab[show_cols], use_container_width=True, height=420)

    with tab_all:
        _render_tab(df_f, "todas las monedas")

    with tab_uyu:
        _render_tab(df_f[df_f["__moneda_view__"] == "UYU"], "UYU")

    with tab_usd:
        _render_tab(df_f[df_f["__moneda_view__"] == "USD"], "USD")


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
        # ✅ CAMBIO: Usar sql_compras en lugar de sql_facturas para incluir filtro de Tipo Comprobante
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
        # Asumiendo que tienes una función en sql_compras o crea una; si no, ajusta
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

    # ===== NO IMPLEMENTADO =====
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

                # Dashboard vendible (si falla, cae al render viejo sin romper)
                try:
                    st.markdown("---")
                    render_dashboard_compras_vendible(
                        df,
                        titulo="Datos",
                        key_prefix=f"hist_{idx}_"
                    )
                except Exception as e:
                    # Fallback viejo
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

                # ✅ AGREGADO: Convertir "Mes" a nombres de meses antes de mostrar
                if isinstance(resultado_sql, pd.DataFrame) and 'Mes' in resultado_sql.columns:
                    resultado_sql['Mes'] = resultado_sql['Mes'].apply(convertir_mes_a_nombre)

                if isinstance(resultado_sql, pd.DataFrame):
                    if len(resultado_sql) == 0:
                        respuesta_content = "⚠️ No se encontraron resultados"
                    else:
                        if tipo == "detalle_factura":
                            nro = parametros.get("nro_factura", "")
                            respuesta_content = (
                                f"✅ **Factura {nro}** - {len(resultado_sql)} artículos"
                            )
                        elif tipo.startswith("facturas_"):
                            respuesta_content = (
                                f"✅ Encontré **{len(resultado_sql)}** facturas"
                            )
                        elif tipo.startswith("compras_"):
                            respuesta_content = (
                                f"✅ Encontré **{len(resultado_sql)}** compras"
                            )
                        elif tipo.startswith("comparar_"):
                            respuesta_content = (
                                f"✅ Comparación lista - {len(resultado_sql)} filas"
                            )
                        elif tipo.startswith("stock_"):
                            respuesta_content = (
                                f"✅ Stock encontrado - {len(resultado_sql)} filas"
                            )
                        elif tipo == "listado_facturas_anio":
                            anio = parametros.get("anio", "")
                            respuesta_content = (
                                f"✅ **Listado de Facturas {anio}** - {len(resultado_sql)} proveedores"
                            )
                        elif tipo == "total_facturas_por_moneda_anio":
                            anio = parametros.get("anio", "")
                            respuesta_content = (
                                f"✅ **Totales de Facturas {anio} por Moneda** - {len(resultado_sql)} monedas"
                            )
                        elif tipo == "total_facturas_por_moneda_generico":
                            respuesta_content = (
                                f"✅ **Totales de Facturas por Moneda (Todos los años)** - {len(resultado_sql)} monedas"
                            )
                        elif tipo == "total_compras_por_moneda_generico":
                            respuesta_content = (
                                f"✅ **Totales de Compras por Moneda (Todos los años)** - {len(resultado_sql)} monedas"
                            )
                        else:
                            respuesta_content = (
                                f"✅ Encontré **{len(resultado_sql)}** resultados"
                            )

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
