# =========================
# SUGERENCIAS.PY - LÓGICA Y DATOS PARA SUGERENCIAS DE PEDIDOS
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
    render_alert_grid,
    render_sugerencia_card,
    render_actions,
    render_divider
)
from config import DEBUG_MODE
from sql_compras import get_compras_anio, get_total_compras_anio  # Importar funciones necesarias

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
    """
    Obtiene datos reales de sugerencias usando datos de compras.
    Calcula consumo diario basado en compras del año.
    Nota: Stock actual se asume 0 ya que no está en datos de compras.
    """
    # Obtener todas las compras del año
    df_compras = get_compras_anio(anio, limite=10000)  # Aumentar límite para más datos
    
    if df_compras is None or df_compras.empty:
        return pd.DataFrame()
    
    # Agrupar por artículo para calcular estadísticas
    df_agrupado = df_compras.groupby('articulo').agg({
        'Cantidad': 'sum',
        'proveedor': 'first',  # Tomar el primer proveedor
        'Fecha': 'max'  # Última fecha de compra
    }).reset_index()
    
    # Convertir Cantidad a numérico (maneja formatos como "2.000,00")
    df_agrupado['Cantidad'] = pd.to_numeric(
        df_agrupado['Cantidad'].astype(str).str.replace('.', '').str.replace(',', '.'),
        errors='coerce'
    ).fillna(0)
    
    # Calcular consumo diario aproximado: total comprado / 365 días
    df_agrupado['consumo_diario'] = df_agrupado['Cantidad'] / 365
    df_agrupado['consumo_diario'] = df_agrupado['consumo_diario'].round(2)  # Cambiado a .round(2) para decimales
    
    # Valores por defecto/estimados
    df_agrupado['stock_actual'] = 0  # No disponible en datos de compras
    df_agrupado['stock_minimo'] = (df_agrupado['consumo_diario'] * 30).round(1)  # 30 días de cobertura mínima
    df_agrupado['lote_minimo'] = df_agrupado['consumo_diario'] * 7  # Lote mínimo = 1 semana
    df_agrupado['unidad'] = 'un'  # Unidad por defecto
    df_agrupado['ultima_compra'] = df_agrupado['Fecha']
    
    # Renombrar columnas
    df_agrupado = df_agrupado.rename(columns={
        'articulo': 'producto',
        'proveedor': 'proveedor'
    })
    
    # Seleccionar columnas relevantes
    columnas = ['producto', 'proveedor', 'stock_actual', 'stock_minimo', 
                'consumo_diario', 'ultima_compra', 'lote_minimo', 'unidad', 'Cantidad']
    
    return df_agrupado[columnas]

def get_mock_alerts(df_sugerencias: pd.DataFrame):
    """
    Genera datos para las alertas basados en los datos reales.
    """
    if df_sugerencias.empty:
        return [
            {"title": "📦 Artículos críticos", "value": "0", "subtitle": "Necesitan pedido urgente", "class": "fc-urgente"},
            {"title": "⏰ Próximos a agotarse", "value": "0", "subtitle": "Pedir en los próximos 7 días", "class": "fc-proximo"},
            {"title": "📈 Para planificar", "value": "0", "subtitle": "Sugerencias para stock óptimo", "class": "fc-planificar"},
            {"title": "✅ Stock saludable", "value": "0", "subtitle": "No requieren acción inmediata", "class": "fc-saludable"}
        ]
    
    urgente = len(df_sugerencias[df_sugerencias['urgencia'] == 'urgente'])
    proximo = len(df_sugerencias[df_sugerencias['urgencia'] == 'proximo'])
    planificar = len(df_sugerencias[df_sugerencias['urgencia'] == 'planificar'])
    saludable = len(df_sugerencias[df_sugerencias['urgencia'] == 'saludable'])
    
    return [
        {"title": "📦 Artículos críticos", "value": str(urgente), "subtitle": "Necesitan pedido urgente", "class": "fc-urgente"},
        {"title": "⏰ Próximos a agotarse", "value": str(proximo), "subtitle": "Pedir en los próximos 7 días", "class": "fc-proximo"},
        {"title": "📈 Para planificar", "value": str(planificar), "subtitle": "Sugerencias para stock óptimo", "class": "fc-planificar"},
        {"title": "✅ Stock saludable", "value": str(saludable), "subtitle": "No requieren acción inmediata", "class": "fc-saludable"}
    ]

def filtrar_sugerencias(sugerencias: pd.DataFrame, filtro_urgencia: str):
    """
    Filtra las sugerencias por urgencia.
    """
    if filtro_urgencia == "Todas":
        return sugerencias
    return sugerencias[sugerencias['urgencia'] == filtro_urgencia.lower()]

# =========================
# LÓGICA PRINCIPAL DE LA PÁGINA
# =========================

def main():
    # Aplicar CSS directamente (para asegurar que se aplique y render_alert_grid se vea como cards)
    st.markdown(CSS_SUGERENCIAS_PEDIDOS, unsafe_allow_html=True)
    
    # Título con render_title
    render_title(
        "Sugerencia de pedidos",
        "Sistema inteligente de recomendaciones de compra basado en consumo histórico"
    )
    
    # Filtros con render_section_title
    render_section_title("Filtros y opciones")
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        anio_seleccionado = st.selectbox(
            "Año de análisis:",
            [2025, 2024, 2023],
            key="anio_seleccionado"
        )
    with col2:
        filtro_urgencia = st.selectbox(
            "Filtrar por urgencia:",
            ["Todas", "Urgente", "Próximo", "Planificar", "Saludable"],
            key="filtro_urgencia"
        )
    with col3:
        st.write("")  # Espacio
    
    render_divider()
    
    # Obtener datos reales
    df = get_datos_sugerencias(anio_seleccionado)
    
    if df.empty:
        st.warning(f"No se encontraron datos de compras para el año {anio_seleccionado}.")
        return
    
    # Preprocesar datos
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
    
    # Alertas con render_section_title y render_alert_grid (ahora con CSS aplicado, se verán como cards)
    render_section_title("Resumen de situación")
    alerts = get_mock_alerts(df)
    render_alert_grid(alerts)
    
    render_divider()
    
    # Sugerencias con render_section_title
    render_section_title("Sugerencias de pedido")
    
    # Filtrar sugerencias
    df_filtrado = filtrar_sugerencias(df, filtro_urgencia)
    
    if df_filtrado.empty:
        st.info("No hay sugerencias que cumplan con los criterios de filtro.")
    else:
        for _, r in df_filtrado.iterrows():
            badge_text = {
                "urgente": "🚨 Urgente",
                "proximo": "⚠️ Próximo",
                "planificar": "📅 Planificar",
                "saludable": "✅ Saludable"
            }.get(r["urgencia"], "✅ Saludable")
            
            badge_class = r["urgencia"]
            
            render_sugerencia_card(
                title=f"{r['producto']}",
                subtitle=f"Proveedor: {r['proveedor']} | Última compra: {r['ultima_compra']}",
                badge=badge_text,
                badge_class=badge_class,
                metrics=[
                    {"key": "Compras anuales", "value": f"{r['Cantidad']:.0f} {r['unidad']}"},
                    {"key": "Compras mensuales", "value": f"{(r['Cantidad'] / 12):.1f} {r['unidad']}"},
                    {"key": "Compra sugerida", "value": f"{r['cantidad_sugerida']} {r['unidad']}"},
                    {"key": "Stock actual", "value": f"{r['stock_actual']} {r['unidad']}"}
                ]
            )
        
        render_divider()
        
        # Acciones con render_section_title
        render_section_title("Acciones")
        
        # Calcular totales
        total_cantidad = df_filtrado["cantidad_sugerida"].sum()
        total_productos = len(df_filtrado)
        
        info_html = f"""
        <div class="fc-info">
            <p><strong>Total sugerido:</strong> {total_cantidad:.1f} unidades en {total_productos} productos</p>
            <p>Esta sugerencia se basa en el consumo promedio del año {anio_seleccionado} y niveles de stock estimados.</p>
        </div>
        """
        render_card(info_html, "fc-info")
        
        # Botones de acción
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("📤 Exportar a Excel", key="export_excel", help="Descargar sugerencias en formato Excel"):
                # Lógica de exportación
                csv = df_filtrado.to_csv(index=False)
                st.download_button(
                    label="Descargar CSV",
                    data=csv,
                    file_name=f"sugerencias_pedidos_{anio_seleccionado}.csv",
                    mime="text/csv"
                )
        with col2:
            if st.button("📧 Enviar por email", key="send_email", help="Enviar sugerencias por correo"):
                st.success("Funcionalidad de email no implementada aún.")
        with col3:
            if st.button("🛒 Crear orden de compra", key="create_order", help="Generar orden de compra automática"):
                st.success("Funcionalidad de orden de compra no implementada aún.")
        with col4:
            if st.button("🔄 Actualizar datos", key="refresh_data", help="Recargar datos desde la base de datos"):
                st.rerun()

# =========================
# EJECUCIÓN
# =========================
if __name__ == "__main__":
    main()
