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

        totales = {}
        pesos_df = df_calc[
            df_calc[col_moneda].astype(str).str.contains(
                r"\$|peso|ARS|ars", case=False, na=False
            )
        ]
        totales["Pesos"] = pesos_df[col_total].sum()

        usd_df = df_calc[
            df_calc[col_moneda].astype(str).str.contains(
                r"USD|US|dolar|dólar", case=False, na=False
            )
        ]
        totales["USD"] = usd_df[col_total].sum()

        return totales

    except Exception as e:
        print(f"Error calculando totales: {e}")
        return None


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
