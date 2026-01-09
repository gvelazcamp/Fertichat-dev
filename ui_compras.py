# =========================
# UI_COMPRAS.PY - CON COMPRAS Y FACTURAS INTEGRADAS
# =========================

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import re
import difflib
import unicodedata
from typing import Optional, Dict, List, Tuple

import ia_compras as iaq_compras

# IMPORTS
from ia_router import interpretar_pregunta, obtener_info_tipo
from utils_openai import responder_con_openai

# IMPORTS DE SQL
import sql_compras as sqlq_compras
import sql_comparativas as sqlq_comparativas
import sql_facturas as sqlq_facturas  # ✅ NUEVO


# =========================
# DEBUG HELPERS (NO ROMPEN NADA)
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
# INICIALIZAR HISTORIAL
# =========================
def inicializar_historial():
    if "historial_compras" not in st.session_state:
        st.session_state["historial_compras"] = []


# =========================
# CALCULAR TOTALES POR MONEDA
# =========================
def calcular_totales_por_moneda(df: pd.DataFrame) -> dict:
    """Calcula totales separados por moneda"""
    if df is None or len(df) == 0:
        return {"Pesos": 0, "USD": 0}

    col_moneda = None
    for col in df.columns:
        if col.lower() in ["moneda", "currency"]:
            col_moneda = col
            break

    col_total = None
    for col in df.columns:
        if col.lower() in ["total", "monto", "importe", "valor"]:
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

        pesos_df = df_calc[df_calc[col_moneda].astype(str).str.contains(r"\$|peso|ARS|ars", case=False, na=False)]
        totales["Pesos"] = pesos_df[col_total].sum()

        usd_df = df_calc[df_calc[col_moneda].astype(str).str.contains(r"USD|US|dolar|dólar", case=False, na=False)]
        totales["USD"] = usd_df[col_total].sum()

        return totales

    except Exception as e:
        print(f"Error calculando totales: {e}")
        return None


# =========================
# GENERAR EXPLICACIÓN
# =========================
def generar_explicacion_ia(df: pd.DataFrame, pregunta: str, tipo: str) -> str:
    """Genera una explicación natural y completa de los resultados"""
    try:
        if df is None or len(df) == 0:
            return "No se encontraron datos para esta consulta."

        explicacion = []

        # ✅ DETECTAR SI ES FACTURA
        es_factura = tipo in ["detalle_factura", "facturas_proveedor", "ultima_factura", "facturas_articulo", "resumen_facturas"]
        
        if es_factura:
            explicacion.append("### 🧾 Análisis de Facturas\n")
        else:
            explicacion.append("### 📊 Análisis de la consulta\n")

        # Detalle de factura única
        if tipo == "detalle_factura":
            explicacion.append(f"Se encontró el detalle completo de la factura.\n")
            
            totales = calcular_totales_por_moneda(df)
            if totales:
                pesos = totales.get("Pesos", 0)
                usd = totales.get("USD", 0)
                
                if pesos > 0:
                    explicacion.append(f"\n**Total de la factura:** ${pesos:,.2f} pesos\n")
                if usd > 0:
                    explicacion.append(f"\n**Total de la factura:** ${usd:,.2f} dólares\n")
            
            explicacion.append(f"\n**Cantidad de artículos:** {len(df)}\n")
            
        else:
            explicacion.append(f"Se encontraron **{len(df)} registros** que coinciden con tu búsqueda.\n")

            # Número de facturas únicas (si aplica)
            if es_factura and ("NroFactura" in df.columns or "nro_factura" in df.columns):
                col_factura = "NroFactura" if "NroFactura" in df.columns else "nro_factura"
                num_facturas = df[col_factura].nunique()
                explicacion.append(f"\n**Cantidad de facturas únicas:** {num_facturas}\n")

            totales = calcular_totales_por_moneda(df)
            if totales:
                explicacion.append("#### 💰 Totales\n")

                pesos = totales.get("Pesos", 0)
                usd = totales.get("USD", 0)

                if pesos > 0 and usd > 0:
                    explicacion.append(f"El gasto total fue de **${pesos:,.2f} pesos** y **${usd:,.2f} dólares**.\n")
                elif pesos > 0:
                    explicacion.append(f"El gasto total fue de **${pesos:,.2f} pesos**.\n")
                elif usd > 0:
                    explicacion.append(f"El gasto total fue de **${usd:,.2f} dólares**.\n")

        # Detectar columnas
        col_prov = None
        col_art = None
        for c in df.columns:
            if c.lower() == "proveedor":
                col_prov = c
            if c.lower() == "articulo":
                col_art = c

        # Top proveedores
        if col_prov:
            top_proveedores = df.groupby(col_prov).size().sort_values(ascending=False).head(3)

            explicacion.append("\n#### 🏢 Proveedores principales\n")
            explicacion.append("Los proveedores con más movimientos fueron:\n")

            col_total = None
            for c in df.columns:
                if c.lower() in ["total", "monto", "importe", "valor"]:
                    col_total = c
                    break

            for i, (prov, cant) in enumerate(top_proveedores.items(), 1):
                if col_total:
                    df_prov = df[df[col_prov] == prov].copy()
                    df_prov[col_total] = (
                        df_prov[col_total]
                        .astype(str)
                        .str.replace(".", "", regex=False)
                        .str.replace(",", ".", regex=False)
                        .str.replace("$", "", regex=False)
                        .str.strip()
                    )
                    df_prov[col_total] = pd.to_numeric(df_prov[col_total], errors="coerce").fillna(0)
                    total_prov = df_prov[col_total].sum()
                    explicacion.append(f"{i}. **{prov}**: {cant} registros por un total de ${total_prov:,.2f}\n")
                else:
                    explicacion.append(f"{i}. **{prov}**: {cant} registros\n")

        # Top artículos
        elif col_art:
            top_articulos = df.groupby(col_art).size().sort_values(ascending=False).head(3)

            explicacion.append("\n#### 📦 Artículos principales\n")
            explicacion.append("Los artículos más comprados fueron:\n")

            for i, (art, cant) in enumerate(top_articulos.items(), 1):
                explicacion.append(f"{i}. **{art}**: {cant} registros\n")

        # Rango de fechas
        if "Fecha" in df.columns or "fecha" in df.columns:
            col_fecha = "Fecha" if "Fecha" in df.columns else "fecha"
            df_temp = df.copy()
            df_temp[col_fecha] = pd.to_datetime(df_temp[col_fecha], errors="coerce")
            df_temp = df_temp.dropna(subset=[col_fecha])

            if len(df_temp) > 0:
                fecha_min = df_temp[col_fecha].min()
                fecha_max = df_temp[col_fecha].max()
                explicacion.append("\n#### 📅 Período\n")
                explicacion.append(
                    f"Los datos abarcan desde **{fecha_min.strftime('%d/%m/%Y')}** hasta **{fecha_max.strftime('%d/%m/%Y')}**.\n"
                )

        explicacion.append("\n---\n")
        explicacion.append("💡 *Tip: Podés descargar estos datos en Excel usando el botón en la pestaña 'Tabla'.*")

        return "".join(explicacion)

    except Exception as e:
        print(f"Error generando explicación: {e}")
        return f"Se encontraron {len(df)} resultados. Los datos están disponibles en la pestaña 'Tabla'."


# =========================
# GENERAR GRÁFICO
# =========================
def generar_grafico(df: pd.DataFrame, tipo: str):
    """Genera un gráfico según el tipo de consulta"""
    try:
        if df is None or len(df) == 0:
            return None

        df_clean = df.copy()

        col_total = None
        for col in df_clean.columns:
            if col.lower() in ["total", "monto", "importe", "valor"]:
                col_total = col
                break

        if col_total:
            df_clean[col_total] = (
                df_clean[col_total]
                .astype(str)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
                .str.replace("$", "", regex=False)
                .str.strip()
            )
            df_clean[col_total] = pd.to_numeric(df_clean[col_total], errors="coerce").fillna(0)

        # Detectar columnas
        col_prov = None
        col_art = None
        for c in df_clean.columns:
            if c.lower() == "proveedor":
                col_prov = c
            if c.lower() == "articulo":
                col_art = c

        # ✅ GRÁFICO PARA DETALLE DE FACTURA
        if tipo == "detalle_factura" and col_art and col_total:
            fig = px.bar(
                df_clean,
                x=col_art,
                y=col_total,
                title="Detalle de Artículos en la Factura",
                labels={col_art: "Artículo", col_total: "Total ($)"},
                text=col_total,
            )
            fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
            fig.update_layout(
                height=500,
                xaxis_tickangle=-45,
                showlegend=False,
            )
            return fig

        # Top 10 proveedores por total
        if col_prov and col_total:
            df_grouped = df_clean.groupby(col_prov)[col_total].sum().sort_values(ascending=False).head(10)

            fig = px.bar(
                x=df_grouped.values,
                y=df_grouped.index,
                orientation="h",
                title="Top 10 Proveedores por Total",
                labels={"x": "Total ($)", "y": "Proveedor"},
                text=df_grouped.values,
            )

            fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
            fig.update_layout(
                height=500,
                xaxis_title="Total",
                yaxis_title="Proveedor",
                showlegend=False,
                xaxis={"tickformat": "$,.0f"},
            )
            return fig

        # Top 10 artículos por total
        if col_art and col_total:
            df_grouped = df_clean.groupby(col_art)[col_total].sum().sort_values(ascending=False).head(10)

            fig = px.bar(
                x=df_grouped.values,
                y=df_grouped.index,
                orientation="h",
                title="Top 10 Artículos por Total",
                labels={"x": "Total ($)", "y": "Artículo"},
                text=df_grouped.values,
            )

            fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
            fig.update_layout(
                height=500,
                xaxis_title="Total",
                yaxis_title="Artículo",
                showlegend=False,
                xaxis={"tickformat": "$,.0f"},
            )
            return fig

        # Línea temporal
        if "Fecha" in df_clean.columns or "fecha" in df_clean.columns:
            col_fecha = "Fecha" if "Fecha" in df_clean.columns else "fecha"
            df_temp = df_clean.copy()
            df_temp[col_fecha] = pd.to_datetime(df_temp[col_fecha], errors="coerce")
            df_temp = df_temp.dropna(subset=[col_fecha])

            if len(df_temp) > 0:
                if col_total:
                    # Evolución por mes
                    df_temp["Mes"] = df_temp[col_fecha].dt.to_period("M")
                    df_grouped = df_temp.groupby("Mes")[col_total].sum()
                    
                    fig = px.line(
                        x=[str(p) for p in df_grouped.index],
                        y=df_grouped.values,
                        title="Evolución por Mes",
                        labels={"x": "Mes", "y": "Total ($)"},
                        markers=True,
                    )
                    fig.update_layout(height=400)
                    return fig
                else:
                    # Cantidad por mes
                    df_grouped = df_temp.groupby(df_temp[col_fecha].dt.to_period("M")).size()
                    fig = px.line(
                        x=[str(p) for p in df_grouped.index],
                        y=df_grouped.values,
                        title="Cantidad de Registros por Mes",
                        labels={"x": "Mes", "y": "Cantidad"},
                        markers=True,
                    )
                    fig.update_layout(height=400)
                    return fig

        return None

    except Exception as e:
        print(f"Error generando gráfico: {e}")
        return None


# =========================
# ROUTER SQL (CON FACTURAS INTEGRADAS)
# =========================
def ejecutar_consulta_por_tipo(tipo: str, parametros: dict):

    _dbg_set_sql(
        tag=tipo,
        query=f"-- Ejecutando tipo: {tipo}\n-- (SQL real en sql_compras/sql_comparativas/sql_facturas)\n",
        params=parametros,
        df=None
    )

    # =========================
    # ✅ FACTURAS (NUEVAS)
    # =========================
    
    if tipo == "detalle_factura":
        df = sqlq_facturas.get_detalle_factura_por_numero(parametros["nro_factura"])
        _dbg_set_result(df)
        return df

    elif tipo == "facturas_proveedor":
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

    elif tipo == "facturas_articulo":
        df = sqlq_facturas.get_facturas_articulo(
            parametros["articulo"],
            solo_ultima=parametros.get("solo_ultima", False),
            limite=parametros.get("limite", 50)
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
            limite=parametros.get("limite", 100)
        )
        _dbg_set_result(df)
        return df

    # =========================
    # COMPRAS (EXISTENTES)
    # =========================
    
    if tipo == "compras_anio":
        df = sqlq_compras.get_compras_anio(parametros["anio"])
        _dbg_set_result(df)
        return df

    elif tipo == "compras_proveedor_mes":
        df = sqlq_compras.get_detalle_compras_proveedor_mes(parametros["proveedor"], parametros["mes"])
        _dbg_set_result(df)
        return df

    elif tipo == "compras_proveedor_anio":
        df = sqlq_compras.get_detalle_compras_proveedor_anio(parametros["proveedor"], parametros["anio"])
        _dbg_set_result(df)
        return df

    elif tipo == "compras_articulo_mes":
        df = sqlq_compras.get_detalle_compras_articulo_mes(parametros["articulo"], parametros["mes"])
        _dbg_set_result(df)
        return df

    elif tipo == "compras_articulo_anio":
        df = sqlq_compras.get_detalle_compras_articulo_anio(parametros["articulo"], parametros["anio"])
        _dbg_set_result(df)
        return df

    elif tipo == "compras_mes":
        df = sqlq_compras.get_compras_por_mes_excel(parametros["mes"])
        _dbg_set_result(df)
        return df

    # =========================
    # COMPARATIVAS
    # =========================
    
    elif tipo == "comparar_proveedor_meses":
        proveedor = parametros.get("proveedor")
        mes1 = parametros.get("mes1")
        mes2 = parametros.get("mes2")
        label1 = parametros.get("label1", mes1)
        label2 = parametros.get("label2", mes2)

        df = sqlq_comparativas.get_comparacion_proveedor_meses(
            proveedor,
            mes1,
            mes2,
            label1,
            label2,
        )
        _dbg_set_result(df)
        return df

    elif tipo == "comparar_proveedor_anios":
        proveedor = parametros.get("proveedor")
        anios = parametros.get("anios", [])
        df = sqlq_comparativas.get_comparacion_proveedor_anios_like(proveedor, anios)
        _dbg_set_result(df)
        return df

    elif tipo in ("comparar_proveedores_meses", "comparar_proveedores_meses_multi"):
        proveedores = parametros.get("proveedores", [])
        if (not proveedores) and parametros.get("proveedor"):
            proveedores = [parametros.get("proveedor")]

        meses = parametros.get("meses")
        if not meses:
            mes1 = parametros.get("mes1")
            mes2 = parametros.get("mes2")
            if mes1 and mes2:
                meses = [mes1, mes2]
            elif mes1:
                meses = [mes1]

        df = sqlq_comparativas.get_comparacion_proveedores_meses_multi(
            proveedores,
            meses or []
        )
        _dbg_set_result(df)
        return df

    elif tipo in ("comparar_proveedores_anios", "comparar_proveedores_anios_multi"):
        proveedores = parametros.get("proveedores", [])
        if (not proveedores) and parametros.get("proveedor"):
            proveedores = [parametros.get("proveedor")]

        anios = parametros.get("anios", [])
        df = sqlq_comparativas.get_comparacion_proveedores_anios_multi(
            proveedores,
            anios
        )
        _dbg_set_result(df)
        return df

    # =========================
    # STOCK
    # =========================
    
    elif tipo == "stock_total":
        df = sqlq_compras.get_stock_total()
        _dbg_set_result(df)
        return df

    elif tipo == "stock_articulo":
        df = sqlq_compras.get_stock_articulo(parametros["articulo"])
        _dbg_set_result(df)
        return df

    else:
        raise ValueError(f"Tipo '{tipo}' no implementado")


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

    # MOSTRAR HISTORIAL
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
                        pesos_str = f"${pesos/1_000_000:,.2f}M" if pesos >= 1_000_000 else f"${pesos:,.2f}"
                        st.metric("💵 Total Pesos", pesos_str, help=f"Valor exacto: ${pesos:,.2f}")

                    with col2:
                        usd = totales.get("USD", 0)
                        usd_str = f"${usd/1_000_000:,.2f}M" if usd >= 1_000_000 else f"${usd:,.2f}"
                        st.metric("💵 Total USD", usd_str, help=f"Valor exacto: ${usd:,.2f}")

                st.markdown("---")

                tab1, tab2, tab3 = st.tabs(["📊 Tabla", "📈 Gráfico", "💡 Explicación"])

                with tab1:
                    st.dataframe(df, use_container_width=True, height=400)

                    from io import BytesIO
                    buffer = BytesIO()
                    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                        df.to_excel(writer, index=False, sheet_name="Resultados")
                    buffer.seek(0)

                    st.download_button(
                        "📥 Descargar Excel",
                        buffer,
                        f"resultado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"dl_{msg.get('timestamp', 0)}_{idx}",
                    )

                with tab2:
                    fig = generar_grafico(df, msg.get("tipo", ""))
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No se puede generar gráfico para este tipo de datos")

                with tab3:
                    explicacion = generar_explicacion_ia(df, msg.get("pregunta", ""), msg.get("tipo", ""))
                    st.markdown(explicacion)

    # INPUT
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
                        # ✅ MENSAJE SEGÚN TIPO
                        if tipo == "detalle_factura":
                            nro = parametros.get("nro_factura", "")
                            respuesta_content = f"✅ **Factura {nro}** - {len(resultado_sql)} artículos"
                        elif tipo.startswith("facturas_"):
                            respuesta_content = f"✅ Encontré **{len(resultado_sql)}** facturas"
                        else:
                            respuesta_content = f"✅ Encontré **{len(resultado_sql)}** resultados"
                        
                        respuesta_df = resultado_sql
                else:
                    respuesta_content = str(resultado_sql)

            except Exception as e:
                _dbg_set_sql(tipo, f"-- Error: {str(e)}", parametros, None)
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
