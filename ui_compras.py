# =========================
# UI_COMPRAS.PY - CON TOTALES Y PESTAÑAS
# =========================

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# IMPORTS
from ia_interpretador import interpretar_pregunta, obtener_info_tipo
from utils_openai import responder_con_openai

# IMPORTS DE SQL
from sql_queries import (
    get_compras_anio,
    get_detalle_compras_proveedor_mes,
    get_detalle_compras_proveedor_anio,
    get_detalle_compras_articulo_mes,
    get_detalle_compras_articulo_anio,
    get_compras_por_mes_excel,
    get_ultima_factura_inteligente,
    get_facturas_de_articulo,
    get_detalle_factura_por_numero,
    get_comparacion_proveedor_meses,
    get_comparacion_proveedor_anios_monedas,
    get_comparacion_articulo_meses,
    get_comparacion_articulo_anios,
    get_comparacion_familia_meses_moneda,
    get_comparacion_familia_anios_monedas,
    get_gastos_todas_familias_mes,
    get_gastos_todas_familias_anio,
    get_gastos_secciones_detalle_completo,
    get_top_10_proveedores_chatbot,
    get_stock_total,
    get_stock_articulo,
    get_stock_familia,
    get_stock_por_familia,
    get_stock_por_deposito,
    get_lotes_por_vencer,
    get_lotes_vencidos,
    get_stock_bajo,
    get_stock_lote_especifico,
    get_total_compras_anio,
    get_total_compras_proveedor_anio,
    get_total_compras_articulo_anio
)


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
    """
    Calcula totales separados por moneda si la columna 'Moneda' existe
    """
    if df is None or len(df) == 0:
        return {"Pesos": 0, "USD": 0}

    # Verificar si existe columna de moneda
    col_moneda = None
    for col in df.columns:
        if col.lower() in ["moneda", "currency"]:
            col_moneda = col
            break

    # Verificar si existe columna de total
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
    """
    Genera una explicación natural y completa de los resultados
    """
    try:
        if df is None or len(df) == 0:
            return "No se encontraron datos para esta consulta."

        explicacion = []

        explicacion.append("### 📊 Análisis de la consulta\n")
        explicacion.append(f"Se encontraron **{len(df)} registros** que coinciden con tu búsqueda.\n")

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

        # Top proveedores (si existe columna proveedor)
        if "proveedor" in df.columns:
            top_proveedores = df.groupby("proveedor").size().sort_values(ascending=False).head(3)

            explicacion.append("\n#### 🏢 Proveedores principales\n")
            explicacion.append("Los proveedores con más movimientos fueron:\n")

            # Detectar columna total si existe
            col_total = None
            for c in df.columns:
                if c.lower() in ["total", "monto", "importe", "valor"]:
                    col_total = c
                    break

            for i, (prov, cant) in enumerate(top_proveedores.items(), 1):
                if col_total:
                    df_prov = df[df["proveedor"] == prov].copy()
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
        elif "articulo" in df.columns:
            top_articulos = df.groupby("articulo").size().sort_values(ascending=False).head(3)

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
    """
    Genera un gráfico según el tipo de consulta
    """
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

        # Top 10 proveedores por total
        if "proveedor" in df_clean.columns and col_total:
            df_grouped = df_clean.groupby("proveedor")[col_total].sum().sort_values(ascending=False).head(10)

            fig = px.bar(
                x=df_grouped.values,
                y=df_grouped.index,
                orientation="h",
                title="Top 10 Proveedores por Total",
                labels={"x": "Total ($)", "y": "Proveedor"},
                text=df_grouped.values,
            )

            fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
            fig.update_layout(height=500, xaxis_title="Total", yaxis_title="Proveedor", showlegend=False, xaxis={"tickformat": "$,.0f"})
            return fig

        # Top 10 artículos por total
        if "articulo" in df_clean.columns and col_total:
            df_grouped = df_clean.groupby("articulo")[col_total].sum().sort_values(ascending=False).head(10)

            fig = px.bar(
                x=df_grouped.values,
                y=df_grouped.index,
                orientation="h",
                title="Top 10 Artículos por Total",
                labels={"x": "Total ($)", "y": "Artículo"},
                text=df_grouped.values,
            )

            fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
            fig.update_layout(height=500, xaxis_title="Total", yaxis_title="Artículo", showlegend=False, xaxis={"tickformat": "$,.0f"})
            return fig

        # Línea temporal si hay fecha
        if "Fecha" in df_clean.columns or "fecha" in df_clean.columns:
            col_fecha = "Fecha" if "Fecha" in df_clean.columns else "fecha"
            df_temp = df_clean.copy()
            df_temp[col_fecha] = pd.to_datetime(df_temp[col_fecha], errors="coerce")
            df_temp = df_temp.dropna(subset=[col_fecha])

            if len(df_temp) > 0:
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
# ROUTER SQL
# =========================

def ejecutar_consulta_por_tipo(tipo: str, parametros: dict):

    if tipo == "compras_anio":
        return get_compras_anio(parametros["anio"])

    elif tipo == "compras_proveedor_mes":
        return get_detalle_compras_proveedor_mes(parametros["proveedor"], parametros["mes"])

    elif tipo == "compras_proveedor_anio":
        return get_detalle_compras_proveedor_anio(parametros["proveedor"], parametros["anio"])

    elif tipo == "compras_articulo_mes":
        return get_detalle_compras_articulo_mes(parametros["articulo"], parametros["mes"])

    elif tipo == "compras_articulo_anio":
        return get_detalle_compras_articulo_anio(parametros["articulo"], parametros["anio"])

    elif tipo == "compras_mes":
        return get_compras_por_mes_excel(parametros["mes"])

    elif tipo == "ultima_factura":
        return get_ultima_factura_inteligente(parametros["patron"])

    elif tipo == "facturas_articulo":
        return get_facturas_de_articulo(parametros["articulo"])

    elif tipo == "detalle_factura":
        return get_detalle_factura_por_numero(parametros["nro_factura"])

    elif tipo == "comparar_proveedor_meses":
        return get_comparacion_proveedor_meses(parametros["mes1"], parametros["mes2"], parametros["proveedor"])

    elif tipo == "comparar_proveedor_anios":
        return get_comparacion_proveedor_anios_monedas(parametros["anios"], parametros["proveedor"])

    elif tipo == "comparar_articulo_meses":
        return get_comparacion_articulo_meses(parametros["mes1"], parametros["mes2"], parametros["articulo"])

    elif tipo == "comparar_articulo_anios":
        return get_comparacion_articulo_anios(parametros["anios"], parametros["articulo"])

    elif tipo == "comparar_familia_meses":
        moneda = parametros.get("moneda", "pesos")
        return get_comparacion_familia_meses_moneda(parametros["mes1"], parametros["mes2"], moneda)

    elif tipo == "comparar_familia_anios":
        return get_comparacion_familia_anios_monedas(parametros["anios"])

    elif tipo == "gastos_familias_mes":
        return get_gastos_todas_familias_mes(parametros["mes"])

    elif tipo == "gastos_familias_anio":
        return get_gastos_todas_familias_anio(parametros["anio"])

    elif tipo == "gastos_secciones":
        return get_gastos_secciones_detalle_completo(parametros["familias"], parametros["mes"])

    elif tipo == "top_proveedores":
        moneda = parametros.get("moneda", "pesos")
        anio = parametros.get("anio")
        mes = parametros.get("mes")
        return get_top_10_proveedores_chatbot(moneda, anio, mes)

    elif tipo == "stock_total":
        return get_stock_total()

    elif tipo == "stock_articulo":
        return get_stock_articulo(parametros["articulo"])

    elif tipo == "stock_familia":
        return get_stock_familia(parametros["familia"])

    elif tipo == "stock_por_familia":
        return get_stock_por_familia()

    elif tipo == "stock_por_deposito":
        return get_stock_por_deposito()

    elif tipo == "stock_lotes_vencer":
        dias = parametros.get("dias", 90)
        return get_lotes_por_vencer(dias)

    elif tipo == "stock_lotes_vencidos":
        return get_lotes_vencidos()

    elif tipo == "stock_bajo":
        minimo = parametros.get("minimo", 10)
        return get_stock_bajo(minimo)

    elif tipo == "stock_lote":
        return get_stock_lote_especifico(parametros["lote"])

    else:
        raise ValueError(f"Tipo '{tipo}' no implementado")


# =========================
# UI PRINCIPAL
# =========================

def Compras_IA():

    inicializar_historial()

    st.markdown("### 🤖 Asistente de Compras IA")

    if st.button("🗑️ Limpiar chat"):
        st.session_state["historial_compras"] = []
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
    pregunta = st.chat_input("Escribí tu consulta...")

    if pregunta:
        st.session_state["historial_compras"].append({
            "role": "user",
            "content": pregunta,
            "timestamp": datetime.now().timestamp(),
        })

        resultado = interpretar_pregunta(pregunta)
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
            if resultado.get("sugerencia"):
                respuesta_content += f"\n\n**Sugerencia:** {resultado['sugerencia']}"

        else:
            try:
                resultado_sql = ejecutar_consulta_por_tipo(tipo, parametros)

                if isinstance(resultado_sql, pd.DataFrame):
                    if len(resultado_sql) == 0:
                        respuesta_content = "⚠️ No se encontraron resultados"
                    else:
                        respuesta_content = f"✅ Encontré **{len(resultado_sql)}** resultados"
                        respuesta_df = resultado_sql
                else:
                    respuesta_content = str(resultado_sql)

            except Exception as e:
                respuesta_content = f"❌ Error: {str(e)}"

        st.session_state["historial_compras"].append({
            "role": "assistant",
            "content": respuesta_content,
            "df": respuesta_df,
            "tipo": tipo,
            "pregunta": pregunta,
            "timestamp": datetime.now().timestamp(),
        })

        st.rerun()
