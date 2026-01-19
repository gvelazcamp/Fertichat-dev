# =========================
# sugerencias.py - LÓGICA + DATOS + UI (CARDS)
# =========================

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Importar helpers UI y config
from ui_sugerencias import (
    CSS_SUGERENCIAS_PEDIDOS,
    render_title,
    render_section_title,
    render_card,
    render_alert_grid,        # (queda importado por compatibilidad, no lo usamos acá)
    render_sugerencia_card,
    render_actions,
    render_divider
)
from config import DEBUG_MODE
from sql_compras import get_cantidad_anual_por_articulo, get_total_compras_anio  # Importar funciones necesarias

# =========================
# FUNCIONES DE DATOS Y LÓGICA
# =========================

def calcular_dias_stock(stock_actual: float, consumo_diario: float) -> float:
    if consumo_diario <= 0:
        return float("inf")
    return round(stock_actual / consumo_diario, 1)

def clasificar_urgencia(dias_stock: float) -> str:
    if dias_stock <= 3:
        return "urgente"
    if dias_stock <= 7:
        return "proximo"
    if dias_stock <= 15:
        return "planificar"
    return "saludable"

def calcular_cantidad_sugerida(
    consumo_diario: float,
    dias_cobertura_objetivo: int,
    stock_actual: float,
    lote_minimo: float
) -> float:
    cantidad = (consumo_diario * dias_cobertura_objetivo) - stock_actual
    if cantidad < lote_minimo:
        cantidad = lote_minimo
    return max(round(cantidad, 1), 0)

def get_datos_sugerencias(anio: int) -> pd.DataFrame:
    df = get_cantidad_anual_por_articulo(anio)

    if df is None or df.empty:
        return pd.DataFrame()

    df["cantidad_anual"] = df["cantidad_anual"].fillna(0)

    df["consumo_diario"] = df["cantidad_anual"] / 365
    df["stock_actual"] = 0
    df["lote_minimo"] = df["consumo_diario"] * 7
    df["unidad"] = "un"

    df["dias_stock"] = df.apply(
        lambda r: float("inf") if r["consumo_diario"] <= 0 else round(r["stock_actual"] / r["consumo_diario"], 1),
        axis=1
    )

    df["urgencia"] = df["dias_stock"].apply(clasificar_urgencia)

    df["cantidad_sugerida"] = df.apply(
        lambda r: calcular_cantidad_sugerida(
            r["consumo_diario"], 30, r["stock_actual"], r["lote_minimo"]
        ),
        axis=1
    )

    return df

def get_mock_alerts(df_sugerencias: pd.DataFrame):
    if df_sugerencias.empty:
        return [
            {"title": "URGENTE", "value": "0", "subtitle": "0–3 días", "class": "fc-urgente"},
            {"title": "PRÓXIMAMENTE", "value": "0", "subtitle": "4–7 días", "class": "fc-proximo"},
            {"title": "PLANIFICAR", "value": "0", "subtitle": "8–15 días", "class": "fc-planificar"},
            {"title": "STOCK SALUDABLE", "value": "0", "subtitle": "> 15 días", "class": "fc-saludable"},
        ]

    urgente = len(df_sugerencias[df_sugerencias['urgencia'] == 'urgente'])
    proximo = len(df_sugerencias[df_sugerencias['urgencia'] == 'proximo'])
    planificar = len(df_sugerencias[df_sugerencias['urgencia'] == 'planificar'])
    saludable = len(df_sugerencias[df_sugerencias['urgencia'] == 'saludable'])

    return [
        {"title": "URGENTE", "value": str(urgente), "subtitle": "0–3 días", "class": "fc-urgente"},
        {"title": "PRÓXIMAMENTE", "value": str(proximo), "subtitle": "4–7 días", "class": "fc-proximo"},
        {"title": "PLANIFICAR", "value": str(planificar), "subtitle": "8–15 días", "class": "fc-planificar"},
        {"title": "STOCK SALUDABLE", "value": str(saludable), "subtitle": "> 15 días", "class": "fc-saludable"},
    ]

def filtrar_sugerencias(sugerencias: pd.DataFrame, filtro_urgencia: str):
    if filtro_urgencia == "Todas":
        return sugerencias
    return sugerencias[sugerencias['urgencia'] == filtro_urgencia.lower()]

def _fmt_fecha(x) -> str:
    try:
        if pd.isna(x):
            return "-"
        if hasattr(x, "strftime"):
            return x.strftime("%Y-%m-%d")
        return str(x)
    except Exception:
        return str(x)

# =========================
# LÓGICA PRINCIPAL DE LA PÁGINA
# =========================

def main():
    # CSS
    st.markdown(CSS_SUGERENCIAS_PEDIDOS, unsafe_allow_html=True)

    # Header
    render_title(
        "Sistema de Sugerencias Inteligentes",
        "Optimiza tus pedidos de inventario"
    )

    # =========================
    # FILTRO PRINCIPAL (AÑO)
    # =========================
    render_section_title("Filtros y opciones")
    colA, colB, colC = st.columns([1, 1, 2])

    with colA:
        anio_seleccionado = st.selectbox(
            "Año de análisis:",
            [2025, 2024, 2023],
            key="anio_seleccionado"
        )
    with colB:
        st.write("")
    with colC:
        st.write("")

    render_divider()

    # =========================
    # DATOS
    # =========================
    df = get_datos_sugerencias(anio_seleccionado)

    if df is None or df.empty:
        st.warning(f"No se encontraron datos de compras para el año {anio_seleccionado}.")
        return

    # Preproceso (igual que tu versión)
    df["dias_stock"] = df.apply(
        lambda r: calcular_dias_stock(r["stock_actual"], r["consumo_diario"]),
        axis=1
    )
    df["urgencia"] = df["dias_stock"].apply(clasificar_urgencia)
    df["cantidad_sugerida"] = df.apply(
        lambda r: calcular_cantidad_sugerida(
            consumo_diario=r["consumo_diario"],
            dias_cobertura_objetivo=30,
            stock_actual=r["stock_actual"],
            lote_minimo=r["lote_minimo"]
        ),
        axis=1
    )

    # =========================
    # DASHBOARD DE ALERTAS (SIEMPRE EN FILA)
    # =========================
    render_section_title("Dashboard de Alertas")
    alerts = get_mock_alerts(df)

    a1, a2, a3, a4 = st.columns(4, gap="small")
    cols_alert = [a1, a2, a3, a4]

    for i, a in enumerate(alerts[:4]):
        with cols_alert[i]:
            # Card de alerta (1 por columna) -> SIEMPRE al lado
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

        # Urgencia (principal del panel)
        filtro_urgencia = st.selectbox(
            "Urgencia:",
            ["Todas", "Urgente", "Próximo", "Planificar", "Saludable"],
            key="filtro_urgencia"
        )

        # Proveedor (desde datos)
        st.selectbox(
            "Proveedores:",
            ["(no disponible)"],
            key="proveedor_sel_disabled",
            disabled=True
        )
        proveedor_sel = "(no disponible)"

        # Categoría (solo si existe columna; si no, queda deshabilitado)
        if "categoria" in df.columns:
            categorias = ["Todos"] + sorted([str(x) for x in df["categoria"].dropna().unique().tolist()])
            categoria_sel = st.selectbox("Categoría:", categorias, key="categoria_sel")
        else:
            st.selectbox("Categoría:", ["(no disponible)"], key="categoria_sel_disabled", disabled=True)
            categoria_sel = "(no disponible)"

        # Búsqueda por artículo
        q_art = st.text_input("Buscar artículo:", value="", key="q_articulo")

    # ---- Aplicar filtros (sobre df) ----
    df_scope = df.copy()

    # Proveedor
    # if proveedor_sel != "Todos":
    #     df_scope = df_scope[df_scope["proveedor"].astype(str) == str(proveedor_sel)]

    # Categoría (si existe)
    if "categoria" in df_scope.columns and categoria_sel != "Todos":
        df_scope = df_scope[df_scope["categoria"].astype(str) == str(categoria_sel)]

    # Búsqueda
    if q_art.strip():
        qq = q_art.strip().lower()
        df_scope = df_scope[df_scope["articulo"].astype(str).str.lower().str.contains(qq, na=False)]

    # Para la lista: además aplicar urgencia
    df_filtrado = df_scope.copy()
    df_filtrado = filtrar_sugerencias(df_filtrado, filtro_urgencia)

    # =========================
    # LISTADO (derecha) - CARDS
    # =========================
    with col_list:
        render_section_title("Sugerencias de pedido")

        if df_filtrado.empty:
            st.info("No hay sugerencias que cumplan con los criterios de filtro.")
        else:
            # Orden sugerido: urgentes primero, luego próximos, etc.
            orden = {"urgente": 0, "proximo": 1, "planificar": 2, "saludable": 3}
            df_filtrado = df_filtrado.copy()
            df_filtrado["_ord"] = df_filtrado["urgencia"].map(orden).fillna(9)
            df_filtrado = df_filtrado.sort_values(["_ord", "articulo"]).drop(columns=["_ord"])

            for _, r in df_filtrado.iterrows():
                compras_anuales = float(r.get("cantidad_anual", 0) or 0)
                compras_mensuales = round(compras_anuales / 12, 2)

                render_sugerencia_card(
                    producto=str(r.get("articulo", "")),
                    proveedor="—",
                    ultima_compra="—",
                    urgencia=str(r.get("urgencia", "saludable")),
                    compras_anuales=round(compras_anuales, 2),
                    compras_mensuales=compras_mensuales,
                    compra_sugerida=float(r.get("cantidad_sugerida", 0) or 0),
                    stock_actual=float(r.get("stock_actual", 0) or 0),
                    unidad=str(r.get("unidad", "un"))
                )

    # =========================
    # ACCIONES (como tu versión)
    # =========================
    render_divider()
    render_section_title("Acciones")

    total_cantidad = df_filtrado["cantidad_sugerida"].sum() if df_filtrado is not None and not df_filtrado.empty else 0
    total_productos = len(df_filtrado) if df_filtrado is not None and not df_filtrado.empty else 0

    info_html = f"""
    <p><strong>Total sugerido:</strong> {total_cantidad:.1f} unidades en {total_productos} productos</p>
    <p>Esta sugerencia se basa en el consumo promedio del año {anio_seleccionado} y niveles de stock estimados.</p>
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

# =========================
# EJECUCIÓN
# =========================
if __name__ == "__main__":
    main()
