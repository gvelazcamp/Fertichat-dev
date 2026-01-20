import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from sql_core import ejecutar_consulta  # Asegúrate de que esta función exista y funcione con PostgreSQL

# ============ CSS =============
CSS_SUGERENCIAS_PEDIDOS = """
<style>
.fc-alert {
    background: #f3f6fc;
    border-radius: 14px;
    padding: 18px 14px 10px 16px;
    margin-bottom: 8px;
    border: 1px solid #dde7f9;
    box-shadow: 0 3px 12px 0 rgba(16, 26, 48, 0.07);
}
.fc-alert .t { font-size: 15px; font-weight: 600; color: #2768a8; }
.fc-alert .v { font-size: 22px; font-weight: 800; color: #1e293b; }
.fc-alert .s { font-size: 13px; color: #8997ad; margin-bottom: 4px;}
</style>
"""

# ========== HELPERS UI ===========
def render_title(t, stitle=""):
    st.markdown(f"<h2 style='font-weight:900; color:#246;'>{t}</h2>", unsafe_allow_html=True)
    if stitle:
        st.markdown(f"<div style='color:#88A'>{stitle}</div>", unsafe_allow_html=True)

def render_section_title(txt):
    st.markdown(f"<h5 style='color:#308; font-weight:700; margin-top:16px;'>{txt}</h5>", unsafe_allow_html=True)

def render_divider():
    st.markdown("<hr style='margin:10px 0 15px 0; border: none; border-top: 1.5px solid #e2e8f0;'>", unsafe_allow_html=True)

def render_card(html):
    st.markdown(html, unsafe_allow_html=True)

def render_sugerencia_card(producto, proveedor, ultima_compra, urgencia, compras_anuales, compras_mensuales, compra_sugerida, stock_actual, unidad):
    card_html = f"""
    <div style='border:1px solid #e2e8f0; border-radius:8px; padding:12px; margin-bottom:10px; background:#fff;'>
        <h6 style='margin:0; font-weight:600;'>{producto}</h6>
        <p style='margin:5px 0; font-size:14px;'>Proveedor: {proveedor} | Última compra: {ultima_compra}</p>
        <p style='margin:5px 0; font-size:14px;'>Urgencia: {urgencia} | Compras anuales: {compras_anuales} | Mensuales: {compras_mensuales}</p>
        <p style='margin:5px 0; font-size:14px;'>Compra sugerida: {compra_sugerida} {unidad} | Stock actual: {stock_actual}</p>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

def _fmt_fecha(fecha):
    if pd.isna(fecha) or fecha == "–":
        return "–"
    try:
        return pd.to_datetime(fecha).strftime("%d/%m/%Y")
    except:
        return str(fecha)

# ========== FUNCIONES DE DATOS CON FUSIÓN (JOIN) ===========
def get_proveedores_anio(anio: int) -> list:
    """
    Obtiene lista de proveedores únicos para un año.
    Respeta reglas: LOWER(TRIM("Cliente / Proveedor")).
    """
    sql = """
    SELECT DISTINCT TRIM("Cliente / Proveedor") AS proveedor
    FROM chatbot_raw
    WHERE "Año" = %s
      AND TRIM("Cliente / Proveedor") IS NOT NULL
      AND TRIM("Cliente / Proveedor") <> ''
    ORDER BY proveedor;
    """
    df = ejecutar_consulta(sql, (anio,))
    if df is None or df.empty:
        return []
    return df['proveedor'].tolist()

def get_datos_sugerencias(anio: int, proveedor_like: str = None) -> pd.DataFrame:
    """
    Fusiona compras de chatbot_raw con stock de tabla stock via LEFT JOIN.
    Stock real limpiado LATAM. Si no hay stock, =0.
    Respeta todas las reglas.
    """
    base_sql = """
    SELECT
        cr."Articulo",
        cr.proveedor,
        cr.ultima_compra,
        cr.cantidad_anual,
        COALESCE(
            CAST(
                REPLACE(
                    REPLACE(
                        REPLACE(
                            REPLACE(TRIM(s."STOCK"), '(', ''),
                        ')', ''),
                    '.', ''),
                ',', '.')
            AS NUMERIC),
            0
        ) AS stock_actual
    FROM (
        SELECT
            TRIM("Articulo") AS "Articulo",
            (ARRAY_AGG(TRIM("Cliente / Proveedor") ORDER BY "Fecha" DESC))[1] AS proveedor,
            MAX(TRIM("Fecha")) AS ultima_compra,
            SUM(
                CAST(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(TRIM("Cantidad"), '(', ''),
                            ')', ''),
                        '.', ''),
                    ',', '.')
                AS NUMERIC)
            ) AS cantidad_anual
        FROM chatbot_raw
        WHERE "Año" = %s
          AND TRIM("Articulo") IS NOT NULL
          AND TRIM("Articulo") <> ''
          AND TRIM("Cantidad") IS NOT NULL
          AND TRIM("Cantidad") <> ''
    """
    
    params = [anio]
    
    if proveedor_like:
        base_sql += " AND LOWER(TRIM(\"Cliente / Proveedor\")) LIKE %s"
        params.append(proveedor_like)
    
    base_sql += """
        GROUP BY TRIM("Articulo")
    ) cr
    LEFT JOIN stock s ON TRIM(cr."Articulo") = TRIM(s."ARTICULO");
    """
    
    df = ejecutar_consulta(base_sql, tuple(params))
    return df

# ========== FUNCIONES UTILITARIAS AJUSTADAS ===========
def calcular_dias_stock(stock_actual, consumo_diario):
    if consumo_diario > 0:
        return stock_actual / consumo_diario
    return float('inf')

def clasificar_urgencia(dias_stock):
    if dias_stock <= 7:
        return "urgente"
    elif dias_stock <= 14:
        return "proximo"
    elif dias_stock <= 30:
        return "planificar"
    else:
        return "saludable"

def calcular_cantidad_sugerida(consumo_diario, dias_cobertura_objetivo, stock_actual, lote_minimo):
    lote_minimo = lote_minimo if lote_minimo > 0 else 1
    sugerida = max(0, consumo_diario * dias_cobertura_objetivo - stock_actual)
    return max(sugerida, lote_minimo)

def filtrar_sugerencias(df, filtro_urgencia):
    if filtro_urgencia == "Todas":
        return df
    return df[df["urgencia"] == filtro_urgencia.lower()]

def get_mock_alerts(df):
    if df is None or df.empty:
        return [{"title": "Sin datos", "value": "0", "subtitle": "No hay alertas", "class": "warning"}]
    urgente = len(df[df["urgencia"] == "urgente"]) if "urgencia" in df.columns else 0
    proximo = len(df[df["urgencia"] == "proximo"]) if "urgencia" in df.columns else 0
    planificar = len(df[df["urgencia"] == "planificar"]) if "urgencia" in df.columns else 0
    saludable = len(df[df["urgencia"] == "saludable"]) if "urgencia" in df.columns else 0
    return [
        {"title": "Urgentes", "value": str(urgente), "subtitle": "Pedir ya", "class": "urgent"},
        {"title": "Próximos", "value": str(proximo), "subtitle": "En 14 días", "class": "warning"},
        {"title": "Planificar", "value": str(planificar), "subtitle": "En 30 días", "class": "info"},
        {"title": "Saludables", "value": str(saludable), "subtitle": "Ok por ahora", "class": "success"}
    ]

# ========== FUNCIÓN MAIN() CON FUSIÓN Y DEBUG ===========
def main():
    # CSS
    st.markdown(CSS_SUGERENCIAS_PEDIDOS, unsafe_allow_html=True)

    # Header
    render_title(
        "Sistema de Sugerencias Inteligentes",
        "Optimiza tus pedidos de inventario"
    )

    # =========================
    # FILTRO PRINCIPAL (AÑO Y PROVEEDOR)
    # =========================
    render_section_title("Filtros y opciones")
    colA, colB, colC = st.columns([1, 1, 2])

    with colA:
        anio_seleccionado = st.selectbox(
            "Año de análisis:",
            [2025, 2024, 2023],
            key="anio_seleccionado"
        )
    
    # Obtener proveedores para el año seleccionado
    proveedores = get_proveedores_anio(anio_seleccionado)
    
    with colB:
        proveedor_sel = st.selectbox(
            "Proveedor:",
            ["Todos"] + proveedores,
            key="proveedor_sel"
        )
    
    with colC:
        st.write("")

    render_divider()

    # =========================
    # DATOS CON FUSIÓN
    # =========================
    proveedor_like = f"%{proveedor_sel.lower()}%" if proveedor_sel != "Todos" else None
    df = get_datos_sugerencias(anio_seleccionado, proveedor_like)

    # 🔍 DEBUG AGREGADO
    st.write("🔍 DEBUG:")
    st.write(f"Año: {anio_seleccionado}, Proveedor: {proveedor_sel}")
    st.write(f"Proveedor_like: {proveedor_like}")

    # Prueba SQL simple sin JOIN
    sql_simple = """
    SELECT COUNT(*) as total
    FROM chatbot_raw
    WHERE "Año" = %s
    """
    total = ejecutar_consulta(sql_simple, (anio_seleccionado,))
    st.write(f"Total filas en chatbot_raw para {anio_seleccionado}: {total.iloc[0]['total'] if total is not None else 'Error'}")

    # Prueba subquery sin JOIN
    sql_sub = """
    SELECT COUNT(*) as total
    FROM (
        SELECT TRIM("Articulo") AS "Articulo"
        FROM chatbot_raw
        WHERE "Año" = %s
          AND TRIM("Articulo") IS NOT NULL
          AND TRIM("Articulo") <> ''
          AND TRIM("Cantidad") IS NOT NULL
          AND TRIM("Cantidad") <> ''
        GROUP BY TRIM("Articulo")
    ) cr
    """
    sub_total = ejecutar_consulta(sql_sub, (anio_seleccionado,))
    st.write(f"Total artículos válidos: {sub_total.iloc[0]['total'] if sub_total is not None else 'Error'}")

    if df is not None:
        st.write(f"Filas devueltas por get_datos_sugerencias: {len(df)}")
    else:
        st.write("get_datos_sugerencias devolvió None")

    # ✅ Verificación
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        st.warning(f"No se encontraron datos de compras para el año {anio_seleccionado} {'y proveedor seleccionado' if proveedor_sel != 'Todos' else ''}.")
        return

    # Preproceso con stock real de tabla stock
    df["consumo_diario"] = df["cantidad_anual"] / 365
    # stock_actual ya viene del JOIN
    df["dias_stock"] = df.apply(lambda r: calcular_dias_stock(r["stock_actual"], r["consumo_diario"]), axis=1)
    df["urgencia"] = df["dias_stock"].apply(clasificar_urgencia)
    df["cantidad_sugerida"] = df.apply(lambda r: calcular_cantidad_sugerida(r["consumo_diario"], 30, r["stock_actual"], 1), axis=1)
    df["unidad"] = "un"

    # =========================
    # DASHBOARD DE ALERTAS
    # =========================
    render_section_title("Dashboard de Alertas")
    alerts = get_mock_alerts(df)

    a1, a2, a3, a4 = st.columns(4, gap="small")
    cols_alert = [a1, a2, a3, a4]

    for i, a in enumerate(alerts[:4]):
        with cols_alert[i]:
            st.markdown(
                f"""
                <div class="fc-alert {a.get("class","")}">
                    <div class="t">{a.get("title","")}</div>
                    <div class="v">{a.get("value","")}</div>
                    <div class="s">{a.get("subtitle","")}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

    render_divider()

    # =========================
    # LAYOUT: FILTROS IZQ + LISTA DER
    # =========================
    col_filters, col_list = st.columns([1, 3], gap="large")

    # ---- Filtros (izquierda) ----
    with col_filters:
        render_section_title("Filtros")

        filtro_urgencia = st.selectbox(
            "Urgencia:",
            ["Todas", "Urgente", "Próximo", "Planificar", "Saludable"],
            key="filtro_urgencia"
        )

        q_art = st.text_input("Buscar artículo:", value="", key="q_articulo")

    # ---- Aplicar filtros ----
    df_scope = df.copy()

    if q_art.strip():
        qq = q_art.strip().lower()
        df_scope = df_scope[df_scope["Articulo"].astype(str).str.lower().str.contains(qq, na=False)]

    df_filtrado = df_scope.copy()
    df_filtrado = filtrar_sugerencias(df_filtrado, filtro_urgencia)

    # =========================
    # LISTADO - CARDS
    # =========================
    with col_list:
        render_section_title("Sugerencias de pedido")

        if df_filtrado is None or (isinstance(df_filtrado, pd.DataFrame) and df_filtrado.empty):
            st.info("No hay sugerencias que cumplan con los criterios de filtro.")
        else:
            orden = {"urgente": 0, "proximo": 1, "planificar": 2, "saludable": 3}
            df_filtrado = df_filtrado.copy()
            df_filtrado["_ord"] = df_filtrado["urgencia"].map(orden).fillna(9)
            df_filtrado = df_filtrado.sort_values(["_ord", "Articulo"]).drop(columns=["_ord"])

            for _, r in df_filtrado.iterrows():
                compras_anuales = float(r.get("cantidad_anual", 0) or 0)
                compras_mensuales = round(compras_anuales / 12, 2)

                render_sugerencia_card(
                    producto=str(r.get("Articulo", "")),
                    proveedor=str(r.get("proveedor", "–")),
                    ultima_compra=_fmt_fecha(r.get("ultima_compra", "–")),
                    urgencia=str(r.get("urgencia", "saludable")),
                    compras_anuales=round(compras_anuales, 2),
                    compras_mensuales=compras_mensuales,
                    compra_sugerida=float(r.get("cantidad_sugerida", 0) or 0),
                    stock_actual=float(r.get("stock_actual", 0) or 0),
                    unidad=str(r.get("unidad", "un"))
                )

    # =========================
    # ACCIONES
    # =========================
    render_divider()
    render_section_title("Acciones")

    total_cantidad = df_filtrado["cantidad_sugerida"].sum() if df_filtrado is not None and isinstance(df_filtrado, pd.DataFrame) and not df_filtrado.empty else 0
    total_productos = len(df_filtrado) if df_filtrado is not None and isinstance(df_filtrado, pd.DataFrame) and not df_filtrado.empty else 0

    info_html = f"""
    <p><strong>Total sugerido:</strong> {total_cantidad:.1f} unidades en {total_productos} productos</p>
    <p>Esta sugerencia se basa en el consumo promedio del año {anio_seleccionado} y niveles de stock reales.</p>
    """
    render_card(info_html)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("Exportar a Excel", key="export_excel", help="Descargar sugerencias en formato Excel"):
            csv = df_filtrado.to_csv(index=False)
            st.download_button(
                label="Descargar CSV",
                data=csv,
                file_name=f"sugerencias_pedidos_{anio_seleccionado}.csv",
                mime="text/csv"
            )

    with col2:
        if st.button("Enviar por email", key="send_email", help="Enviar sugerencias por correo"):
            st.success("Funcionalidad de email no implementada aún.")

    with col3:
        if st.button("Crear orden de compra", key="create_order", help="Generar orden de compra automática"):
            st.success("Funcionalidad de orden de compra no implementada aún.")

    with col4:
        if st.button("Actualizar datos", key="refresh_data", help="Recargar datos desde la base de datos"):
            st.rerun()
