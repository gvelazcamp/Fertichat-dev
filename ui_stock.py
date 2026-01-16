import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Tuple, Optional, Dict, Any
import time
import json

from utils_format import formatear_dataframe, df_to_excel
from sql_stock import (
    get_stock_total,
    get_stock_por_familia,
    get_stock_por_deposito,
    get_stock_articulo,
    get_stock_familia,
    get_lotes_por_vencer,
    get_lotes_vencidos,
    get_stock_bajo,
    get_stock_lote_especifico,
    get_alertas_vencimiento_multiple,
    get_lista_articulos_stock,  # ✅ IMPORTAR PARA LISTA DE ARTÍCULOS
)
# from sql_compras import get_compras_articulo  # REMOVIDO PARA EVITAR IMPORTERROR

# =====================================================================
# OPENAI PARA CLASIFICACIÓN DE PREGUNTAS
# =====================================================================
import os
from openai import OpenAI
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

def clasificar_pregunta_stock(pregunta: str) -> Dict[str, Any]:
    """
    Usa OpenAI para clasificar preguntas sobre stock contextual.
    """
    if not client:
        return {"tipo": "stock_total", "detalles": "OpenAI no disponible"}
    
    prompt = f"""
    Analiza esta pregunta sobre stock de un artículo:
    "{pregunta}"
    
    Clasifica en uno de estos tipos:
    - vencimiento: cuando vence, próximo a vencer, lotes que vencen
    - ultima_compra: cuándo compramos, última vez que entró, cuándo fue la última compra
    - deposito: dónde está, en qué depósito, dónde hay stock
    - lote_antiguo: lote más viejo, lote más antiguo
    - stock_total: cuánto hay, stock actual
    - comparacion_temporal: evolución en el tiempo, cómo cambió, estamos comprando más
    
    Responde SOLO con JSON:
    {{"tipo": "...", "detalles": "..."}}
    """
    
    try:
        respuesta = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=100
        )
        content = respuesta.choices[0].message.content.strip()
        return json.loads(content)
    except Exception as e:
        print(f"Error en OpenAI: {e}")
        return {"tipo": "stock_total", "detalles": "Error en clasificación"}

# =====================================================================
# NUEVA FUNCIÓN: PREGUNTAS SOBRE TABLA ESPECÍFICA
# =====================================================================

def procesar_pregunta_sobre_tabla(pregunta: str, codigo_articulo: str, df_stock: pd.DataFrame) -> str:
    """
    Responde preguntas contextuales sobre un artículo específico usando OpenAI
    """
    if not client or pregunta.strip() == "":
        return "OpenAI no disponible o pregunta vacía"
    
    # Construir contexto
    contexto = f"""
    Artículo: {codigo_articulo}
    Stock total: {df_stock['STOCK'].sum() if 'STOCK' in df_stock.columns else 0}
    Lotes disponibles: {df_stock['LOTE'].tolist() if 'LOTE' in df_stock.columns else []}
    Vencimientos: {df_stock['VENCIMIENTO'].tolist() if 'VENCIMIENTO' in df_stock.columns else []}
    Depósitos: {df_stock['DEPOSITO'].unique().tolist() if 'DEPOSITO' in df_stock.columns else []}
    Días para vencer: {df_stock['Dias_Para_Vencer'].tolist() if 'Dias_Para_Vencer' in df_stock.columns else []}
    """
    
    try:
        respuesta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un asistente que responde preguntas sobre stock de inventario. Responde de forma concisa y directa en español."},
                {"role": "user", "content": f"Contexto:\n{contexto}\n\nPregunta: {pregunta}"}
            ],
            temperature=0.1,
            max_tokens=200
        )
        return respuesta.choices[0].message.content.strip()
    except Exception as e:
        return f"Error al procesar pregunta: {str(e)}"

# =========================
# HELPERS DE UI PARA STOCK
# =========================

def render_stock_header(descripcion_articulo: str, total_stock: int):
    """Header estándar para todas las consultas de stock"""
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 1.5rem; 
                border-radius: 12px; 
                margin: 1rem 0;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
        <h2 style='color: white; margin: 0; display: flex; align-items: center;'>
            📦 {descripcion_articulo}
        </h2>
        <div style='color: rgba(255,255,255,0.95); 
                    font-size: 1.1rem; 
                    margin-top: 0.5rem;
                    font-weight: 500;'>
            Stock total: <strong>{total_stock:,.0f}</strong> unidades
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_stock_table(df: pd.DataFrame, height: int = 400):
    """Tabla estandarizada con coloreado por vencimiento"""
    df_display = df.copy()
    
    # Agregar columna Días para vencer si no existe y hay fecha
    if 'Dias_Para_Vencer' not in df_display.columns and 'VENCIMIENTO' in df_display.columns:
        df_display['Dias_Para_Vencer'] = (
            pd.to_datetime(df_display['VENCIMIENTO'], errors='coerce') - datetime.now()
        ).dt.days.fillna(-1).astype(int)
    
    # Función para colorear filas
    def highlight_vencimiento(row):
        if 'Dias_Para_Vencer' in row.index:
            dias = row['Dias_Para_Vencer']
            if pd.notna(dias) and dias >= 0:
                if dias < 30:
                    return ['background-color: #fee2e2'] * len(row)  # Rojo claro
                elif dias < 90:
                    return ['background-color: #fef3c7'] * len(row)  # Amarillo claro
        return [''] * len(row)
    
    st.dataframe(
        df_display.style.apply(highlight_vencimiento, axis=1),
        use_container_width=True,
        hide_index=True,
        height=min(height, len(df_display) * 35 + 50)
    )

def render_stock_alerts(df: pd.DataFrame):
    """Alerta compacta para vencimientos"""
    if 'Dias_Para_Vencer' not in df.columns:
        return
    
    proximos_vencer = df[(df['Dias_Para_Vencer'] >= 0) & (df['Dias_Para_Vencer'] <= 90)]
    if not proximos_vencer.empty:
        st.warning(f"⚠️ {len(proximos_vencer)} lote(s) vence(n) en los próximos 90 días")
    else:
        st.success("✅ No hay lotes próximos a vencer")

def render_chat_compacto(codigo_articulo: str, df_stock: pd.DataFrame):
    """Chat compacto simplificado: botón al lado de descargar, input aparece al clickear"""
    
    # ─── Botones: Descargar + Preguntar (solo si hay artículo específico) ───
    if codigo_articulo != "general":
        col1, col2 = st.columns(2)
        with col1:
            excel_data = df_to_excel(df_stock)
            st.download_button(
                label="📥 Descargar Excel",
                data=excel_data,
                file_name=f"stock_{codigo_articulo}.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True,
                key=f"download_chat_{codigo_articulo}"
            )
        with col2:
            if st.button("💬 Preguntar", key=f"btn_preguntar_{codigo_articulo}", use_container_width=True):
                st.session_state[f'mostrar_input_{codigo_articulo}'] = True
    else:
        # Solo descargar para casos generales
        excel_data = df_to_excel(df_stock)
        st.download_button(
            label="📥 Descargar Excel",
            data=excel_data,
            file_name=f"consulta_stock.xlsx",
            mime="application/vnd.ms-excel",
            use_container_width=True,
            key=f"download_general"
        )
    
    # ─── Input de pregunta (solo si clickearon "Preguntar" y hay artículo) ───
    if codigo_articulo != "general" and st.session_state.get(f'mostrar_input_{codigo_articulo}', False):
        st.markdown("<br>", unsafe_allow_html=True)
        
        col_input, col_enviar = st.columns([5, 1])
        
        with col_input:
            pregunta = st.text_input(
                "input_pregunta",
                placeholder="Ej: ¿cuándo se compró? ¿última entrada? ¿dónde está?",
                label_visibility="collapsed",
                key=f"input_{codigo_articulo}"
            )
        
        with col_enviar:
            if st.button("🚀", key=f"enviar_{codigo_articulo}", use_container_width=True):
                if pregunta.strip():
                    with st.spinner("🔍"):
                        respuesta = procesar_pregunta_sobre_tabla(
                            pregunta=pregunta,
                            codigo_articulo=codigo_articulo,
                            df_stock=df_stock
                        )
                    st.info(f"💡 {respuesta}")
                else:
                    st.warning("Escribe una pregunta primero")

# =====================================================================
# NUEVA FUNCIÓN: CONSULTA CONTEXTUAL
# =====================================================================

def procesar_consulta_stock_contextual(pregunta: str, codigo_articulo: str = None):
    """
    Maneja preguntas sobre stock de un artículo específico con contexto.
    
    Ejemplos:
    - "stock de vitek cuando vence" → Extrae artículo + pregunta
    - "¿cuándo fue la última compra?" → Usa artículo del contexto (selectbox)
    """
    # 1. Identificar artículo (del contexto o de la pregunta)
    if not codigo_articulo:
        # Extraer de la pregunta
        tokens = pregunta.lower().split()
        # Buscar en lista de artículos
        lista_art = get_lista_articulos_stock()[1:]  # Sin "Todos"
        for art in lista_art:
            art_lower = art.lower()
            if any(word in art_lower for word in tokens):
                codigo_articulo = art
                break
    
    if not codigo_articulo:
        st.error("No pude identificar el artículo. Selecciona uno del selectbox o mencionalo en la pregunta.")
        return
    
    # 2. Obtener datos
    df_stock = get_stock_articulo(codigo_articulo)
    # df_compras = get_compras_articulo(codigo_articulo)  # REMOVIDO PARA EVITAR IMPORTERROR
    df_compras = pd.DataFrame()  # Placeholder vacío
    
    if df_stock.empty and df_compras.empty:
        st.warning(f"No hay datos para '{codigo_articulo}'.")
        return
    
    # 3. Clasificar pregunta con OpenAI
    clasificacion = clasificar_pregunta_stock(pregunta)
    tipo_pregunta = clasificacion.get('tipo', 'stock_total')
    
    # 4. Responder según tipo
    respuesta = ""
    mostrar_tabla = True  # ✅ NUEVO: Flag para decidir si mostrar tabla
    
    if tipo_pregunta == "vencimiento":
        if not df_stock.empty and 'Dias_Para_Vencer' in df_stock.columns:
            proximo = df_stock.nsmallest(1, 'Dias_Para_Vencer')
            lote = proximo['LOTE'].iloc[0] if not proximo.empty else '-'
            venc = proximo['VENCIMIENTO'].iloc[0] if not proximo.empty else '-'
            dias = proximo['Dias_Para_Vencer'].iloc[0] if not proximo.empty else 0
            respuesta = f"📅 El lote {lote} vence el {venc} ({dias} días)"
        else:
            respuesta = "No hay información de vencimientos"
    
    elif tipo_pregunta == "ultima_compra":
        mostrar_tabla = True  # ✅ Mostrar tabla con el último lote
        if not df_compras.empty:
            # Asume columna FECHA_COMPRA
            ultima = df_compras.nlargest(1, 'FECHA_COMPRA') if 'FECHA_COMPRA' in df_compras.columns else pd.DataFrame()
            fecha = ultima['FECHA_COMPRA'].iloc[0] if not ultima.empty else '-'
            cant = ultima['CANTIDAD'].iloc[0] if not ultima.empty else 0
            respuesta = f"🛒 Última compra: {fecha} - {cant} unidades"
            # Filtrar df_stock si hay compras, pero como es fallback, no
        else:
            # ✅ FALLBACK: Usar el lote con fecha de vencimiento más reciente
            if not df_stock.empty and 'VENCIMIENTO' in df_stock.columns:
                # Asegurar que VENCIMIENTO sea datetime
                df_stock_copy = df_stock.copy()
                df_stock_copy['VENCIMIENTO'] = pd.to_datetime(df_stock_copy['VENCIMIENTO'], errors='coerce')
                ultimo_lote = df_stock_copy.sort_values('VENCIMIENTO', ascending=False).head(1)  # Más reciente primero
                lote = ultimo_lote['LOTE'].iloc[0] if not ultimo_lote.empty else '-'
                venc = ultimo_lote['VENCIMIENTO'].iloc[0] if not ultimo_lote.empty else '-'
                stock = ultimo_lote['STOCK'].iloc[0] if not ultimo_lote.empty else 0
                respuesta = f"🛒 Último lote disponible: {lote} - Vence: {venc.strftime('%Y-%m-%d') if pd.notna(venc) else '-'} - Stock: {stock}"
                # Filtrar df_stock para mostrar solo este lote
                df_stock = ultimo_lote  # Mostrar solo el último lote
            else:
                respuesta = "No hay información de lotes"
                mostrar_tabla = False
    
    elif tipo_pregunta == "deposito":
        if not df_stock.empty:
            depositos = df_stock['DEPOSITO'].unique()
            respuesta = f"🏢 Depósitos: {', '.join(depositos)}"
        else:
            respuesta = "No hay información de depósitos"
            mostrar_tabla = False  # Si no hay stock, no mostrar tabla
    
    elif tipo_pregunta == "lote_antiguo":
        if not df_stock.empty and 'VENCIMIENTO' in df_stock.columns:
            # Asegurar datetime
            df_stock_copy = df_stock.copy()
            df_stock_copy['VENCIMIENTO'] = pd.to_datetime(df_stock_copy['VENCIMIENTO'], errors='coerce')
            antiguo = df_stock_copy.nsmallest(1, 'VENCIMIENTO')
            lote = antiguo['LOTE'].iloc[0] if not antiguo.empty else '-'
            venc = antiguo['VENCIMIENTO'].iloc[0] if not antiguo.empty else '-'
            respuesta = f"📦 Lote más antiguo: {lote} (vence {venc.strftime('%Y-%m-%d') if pd.notna(venc) else '-'})"
        else:
            respuesta = "No hay información de lotes"
    
    elif tipo_pregunta == "stock_total":
        total = df_stock['STOCK'].sum() if not df_stock.empty and 'STOCK' in df_stock.columns else 0
        respuesta = f"📊 Stock total: {total} unidades"
    
    elif tipo_pregunta == "comparacion_temporal":
        respuesta = "📈 Análisis temporal: [Implementar comparación histórica]"
        mostrar_tabla = False
    
    else:
        respuesta = "No entendí la pregunta específica"
        mostrar_tabla = False
    
    # 5. Mostrar respuesta
    st.success(respuesta)
    
    # 6. Mostrar tabla SOLO si es relevante (stock actual)
    if mostrar_tabla and not df_stock.empty:
        total_stock = df_stock['STOCK'].sum() if 'STOCK' in df_stock.columns else 0
        render_stock_header(codigo_articulo, int(total_stock))
        render_stock_table(df_stock)
        render_stock_alerts(df_stock)
        render_chat_compacto(codigo_articulo, df_stock)

# =====================================================================
# MÓDULO STOCK IA (CHATBOT)
# =====================================================================

def detectar_intencion_stock(texto: str) -> dict:
    """Detecta la intención para consultas de stock"""
    texto_lower = texto.lower().strip()

    # ✅ MOVER STOCK_ARTICULO ANTES DE VENCIMIENTOS PARA PRIORIZAR ARTÍCULO ESPECÍFICO
    # Stock de artículo específico (casos 1 y 4)
    if any(k in texto_lower for k in ['stock', 'cuanto hay', 'cuánto hay', 'tenemos', 'disponible', 'hay']):
        # Extraer nombre del artículo
        palabras_excluir = ['stock', 'cuanto', 'cuánto', 'hay', 'de', 'del', 'tenemos', 'disponible', 'el', 'la', 'los', 'las', 'que']
        palabras = [p for p in texto_lower.split() if p not in palabras_excluir and len(p) > 2]
        if palabras:
            articulo = ' '.join(palabras)
            return {'tipo': 'stock_articulo', 'articulo': articulo, 'debug': f'Stock de artículo: {articulo}'}

    # Vencimientos
    if any(k in texto_lower for k in ['vencer', 'vencen', 'vencimiento', 'vence', 'por vencer']):
        if 'vencido' in texto_lower or 'ya vencio' in texto_lower:
            return {'tipo': 'lotes_vencidos', 'debug': 'Lotes vencidos'}
        # Extraer días si se menciona
        import re
        match = re.search(r'(\d+)\s*(dias|día|dia|días)', texto_lower)
        dias = int(match.group(1)) if match else 90
        return {'tipo': 'lotes_por_vencer', 'dias': dias, 'debug': f'Lotes por vencer en {dias} días'}

    # Vencidos
    if any(k in texto_lower for k in ['vencido', 'vencidos', 'ya vencio', 'caducado']):
        return {'tipo': 'lotes_vencidos', 'debug': 'Lotes vencidos'}

    # Stock bajo
    if any(k in texto_lower for k in ['stock bajo', 'poco stock', 'bajo stock', 'quedan pocos', 'se acaba', 'reponer']):
        return {'tipo': 'stock_bajo', 'debug': 'Stock bajo'}

    # Lote específico
    if any(k in texto_lower for k in ['lote', 'nro lote', 'numero de lote']):
        # Buscar patrón de lote (alfanumérico)
        import re
        match = re.search(r'lote\s+(\w+)', texto_lower)
        if match:
            return {'tipo': 'lote_especifico', 'lote': match.group(1), 'debug': f'Lote específico: {match.group(1)}'}

    # Stock por familia
    if any(k in texto_lower for k in ['familia', 'familias', 'por familia', 'seccion', 'secciones']):
        # Ver si menciona una familia específica
        familias_conocidas = ['id', 'fb', 'g', 'tr', 'xx', 'hm', 'mi']
        for fam in familias_conocidas:
            if fam in texto_lower.split():
                return {'tipo': 'stock_familia', 'familia': fam.upper(), 'debug': f'Stock familia {fam.upper()}'}
        return {'tipo': 'stock_por_familia', 'debug': 'Stock por familias'}

    # ✅ NUEVO: Lista de artículos
    if any(k in texto_lower for k in ['listado', 'lista', 'todos los artículos', 'artículos disponibles', 'qué artículos hay']):
        return {'tipo': 'lista_articulos', 'debug': 'Lista de artículos'}

    # ✅ NUEVO: Preguntas comparativas
    if any(k in texto_lower for k in ['qué artículo tiene más stock', 'cuál tiene más stock', 'artículo con más stock']):
        return {'tipo': 'stock_comparativo', 'subtipo': 'mas_stock', 'debug': 'Artículo con más stock'}
    if any(k in texto_lower for k in ['qué artículo tiene menos stock', 'cuál tiene menos stock', 'artículo con menos stock']):
        return {'tipo': 'stock_comparativo', 'subtipo': 'menos_stock', 'debug': 'Artículo con menos stock'}
    if any(k in texto_lower for k in ['qué artículos están bajos', 'artículos bajos de stock']):
        return {'tipo': 'stock_bajo', 'debug': 'Artículos bajos de stock'}

    # ✅ NUEVO: Detectar familias cortas ANTES de buscar artículos
    familias_conocidas = ['id', 'fb', 'g', 'tr', 'xx', 'hm', 'mi']
    palabras = texto_lower.split()
    for fam in familias_conocidas:
        if fam in palabras:
            return {'tipo': 'stock_familia', 'familia': fam.upper(), 'debug': f'Stock familia {fam.upper()}'}

    # Stock por depósito
    if any(k in texto_lower for k in ['deposito', 'depósito', 'depositos', 'depósitos', 'almacen']):
        return {'tipo': 'stock_por_deposito', 'debug': 'Stock por depósito'}

    # Al final, por defecto buscar artículo
    return {'tipo': 'stock_articulo', 'articulo': texto, 'debug': f'Búsqueda general: {texto}'}


def _clean_stock_df(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia el DataFrame de stock: filtra (INACTIVO), si hay stock >0 mostrar solo esos; si todo =0 mostrar 1 fila genérica."""
    if df is None or df.empty:
        return df
    
    df = df.copy()
    df['STOCK'] = df['STOCK'].apply(lambda x: float(str(x).replace(',', '.').replace(' ', '')) if pd.notna(x) else 0)
    
    # ✅ FILTRAR ARTÍCULOS (INACTIVO) ANTES DE PROCESAR
    df = df[~df['ARTICULO'].str.lower().str.contains('(inactivo)', na=False)]
    
    if df.empty:
        return df
    
    grouped = df.groupby('ARTICULO')
    cleaned_rows = []
    
    for articulo, group in grouped:
        stock_positive = group[group['STOCK'] > 0]
        if not stock_positive.empty:
            # ✅ Si hay lotes con stock >0, mostrar SOLO esos (sin filas genéricas de 0)
            cleaned_rows.extend(stock_positive.to_dict('records'))
        else:
            # ✅ Si todos =0, mostrar 1 fila genérica para pedir
            row_dict = group.iloc[0].to_dict()
            row_dict['LOTE'] = '-'
            row_dict['VENCIMIENTO'] = None
            row_dict['Dias_Para_Vencer'] = None
            cleaned_rows.append(row_dict)
    
    return pd.DataFrame(cleaned_rows)


def procesar_pregunta_stock(pregunta: str) -> Tuple[str, Optional[pd.DataFrame]]:
    """Procesa una pregunta sobre stock"""

    intencion = detectar_intencion_stock(pregunta)
    tipo = intencion.get('tipo')

    print(f"🔍 STOCK IA - Intención: {tipo}")
    print(f"📋 Debug: {intencion.get('debug')}")

    # ✅ NUEVO: Lista de artículos (caso 3)
    if tipo == 'lista_articulos':
        lista = get_lista_articulos_stock()
        if lista and len(lista) > 1:
            df_lista = pd.DataFrame({'Artículo': lista[1:]})  # Excluye "Todos"
            return "📋 Lista de artículos disponibles:", df_lista
        return "No encontré artículos.", None

    # ✅ NUEVO: Comparativas simples (caso 2)
    if tipo == 'stock_comparativo':
        subtipo = intencion.get('subtipo')
        if subtipo == 'mas_stock':
            # Obtener artículo con más stock total
            df_total = get_stock_total()
            if df_total is not None and not df_total.empty:
                # Asumir que get_stock_total() devuelve totales por artículo (ajustar si no)
                articulo_top = "Ejemplo: Artículo con más stock"  # Placeholder, ajustar con SQL real
                return f"🏆 Artículo con más stock: {articulo_top}", None
            return "No hay datos para comparar.", None
        elif subtipo == 'menos_stock':
            # Similar, artículo con menos stock
            return "🏆 Artículo con menos stock: [Implementar SQL]", None

    # Stock total
    if tipo == 'stock_total':
        df = get_stock_total()
        if df is not None and not df.empty:
            return "📦 Resumen de stock total:", df
        return "No pude obtener el stock total.", None

    # Stock por familia
    if tipo == 'stock_por_familia':
        df = get_stock_por_familia()
        if df is not None and not df.empty:
            return "📊 Stock agrupado por familia:", df
        return "No encontré datos de stock por familia.", None

    # Stock de una familia específica
    if tipo == 'stock_familia':
        familia = intencion.get('familia', '')
        df = get_stock_familia(familia)
        if df is not None and not df.empty:
            df = _clean_stock_df(df)  # ✅ Limpiar stock 0
            return f"📦 Stock de familia {familia}:", df
        return f"No encontré stock para la familia {familia}.", None

    # Stock por depósito
    if tipo == 'stock_por_deposito':
        df = get_stock_por_deposito()
        if df is not None and not df.empty:
            return "🏢 Stock agrupado por depósito:", df
        return "No encontré datos de stock por depósito.", None

    # Lotes por vencer
    if tipo == 'lotes_por_vencer':
        dias = intencion.get('dias', 90)
        df = get_lotes_por_vencer(dias)
        if df is not None and not df.empty:
            df = _clean_stock_df(df)  # ✅ Limpiar stock 0
            return f"⚠️ Lotes que vencen en los próximos {dias} días:", df
        return f"No hay lotes que venzan en los próximos {dias} días.", None

    # Lotes vencidos
    if tipo == 'lotes_vencidos':
        df = get_lotes_vencidos()
        if df is not None and not df.empty:
            df = _clean_stock_df(df)  # ✅ Limpiar stock 0
            return "🚨 Lotes ya vencidos:", df
        return "No hay lotes vencidos registrados.", None

    # Stock bajo
    if tipo == 'stock_bajo':
        df = get_stock_bajo(10)
        if df is not None and not df.empty:
            df = _clean_stock_df(df)  # ✅ Limpiar stock 0
            return "📉 Artículos con stock bajo (≤10 unidades):", df
        return "No hay artículos con stock bajo.", None

    # Lote específico
    if tipo == 'lote_especifico':
        lote = intencion.get('lote', '')
        df = get_stock_lote_especifico(lote)
        if df is not None and not df.empty:
            df = _clean_stock_df(df)  # ✅ LIMPIAR stock 0
            return f"🔍 Información del lote {lote}:", df
        return f"No encontré el lote {lote}.", None

    # Stock de artículo (casos 1 y 4)
    if tipo == 'stock_articulo':
        articulo = intencion.get('articulo', pregunta)
        df = get_stock_articulo(articulo)
        if df is not None and not df.empty:
            df = _clean_stock_df(df)  # ✅ Limpiar stock 0
            return f"📦 Stock de '{articulo}':", df
        return f"No encontré stock para '{articulo}'.", None

    return "No entendí la consulta. Probá con: 'stock vitek', 'lotes por vencer', 'stock bajo', 'listado de artículos'.", None


# =========================
# 📦 RESUMEN STOCK (ROTATIVO CADA 5s)
# =========================
def _stock_to_float(x) -> float:
    try:
        if x is None:
            return 0.0
        s = str(x).strip().replace(" ", "")
        s = s.replace(",", ".")
        return float(s)
    except Exception:
        return 0.0


# Removido @st.cache_data para debug
def _get_stock_cantidad_1(top_n: int = 200) -> pd.DataFrame:
    # Cambiar a stock bajo (<=10) en lugar de exactamente =1
    df = get_stock_bajo(10)
    # DEBUG removido
    if df is None or df.empty:
        return pd.DataFrame(columns=["FAMILIA", "CODIGO", "ARTICULO", "DEPOSITO", "LOTE", "VENCIMIENTO", "STOCK"])

    # No filtrar a ≈1, mostrar todos con stock <=10
    dfx = df.copy()
    return dfx.head(int(top_n))


# Removido @st.cache_data para debug
def _get_lotes_proximos_a_vencer(dias: int = 365) -> pd.DataFrame:  # ✅ CAMBIADO A 365 DÍAS
    df = get_lotes_por_vencer(dias)
    # DEBUG removido
    if df is None or df.empty:
        return pd.DataFrame(columns=["FAMILIA", "CODIGO", "ARTICULO", "DEPOSITO", "LOTE", "VENCIMIENTO", "STOCK", "Dias_Para_Vencer"])
    return df


def mostrar_resumen_stock_rotativo(dias_vencer: int = 365):  # ✅ CAMBIADO DEFAULT A 365
    # ✅ No auto-refresh mientras el usuario está escribiendo en el input del Stock
    pregunta_actual = ""
    try:
        pregunta_actual = str(st.session_state.get(f"input_stock_{st.session_state.get('stock_input_counter', 0)}", "") or "")
    except Exception:
        pregunta_actual = ""

    # ✅ AGREGAR CONDICIÓN PARA PAUSAR AUTOREFFRESH GLOBAL
    if st.session_state.get("pause_autorefresh_stock", False):
        return  # No mostrar ni refrescar si está pausado

    tick = 0
    if not pregunta_actual.strip():
        try:
            from streamlit_autorefresh import st_autorefresh
            tick = st_autorefresh(interval=5000, key="__rotar_stock_5s__") or 0
        except Exception:
            tick = 0  # si no está instalado, queda fijo

    df_stock_1 = _get_stock_cantidad_1(top_n=200)
    df_vencer = _get_lotes_proximos_a_vencer(dias=int(dias_vencer))

    stock1_txt = "—"
    stock1_sub = "Sin registros con stock bajo"
    stock1_count = 0

    if df_stock_1 is not None and not df_stock_1.empty:
        stock1_count = len(df_stock_1)
        idx1 = int(tick) % stock1_count
        r1 = df_stock_1.iloc[idx1]

        art = str(r1.get("ARTICULO", "—"))
        lote = str(r1.get("LOTE", "—"))
        dep = str(r1.get("DEPOSITO", "—"))
        ven = str(r1.get("VENCIMIENTO", "—"))
        stk = str(r1.get("STOCK", "—"))

        stock1_txt = art
        stock1_sub = f"Lote {lote} | Depósito {dep} | Venc {ven} | Stock {stk}"

    vencer_txt = "—"
    vencer_sub = f"Sin lotes que venzan en {dias_vencer} días"
    vencer_count = 0

    if df_vencer is not None and not df_vencer.empty:
        vencer_count = len(df_vencer)
        idx2 = int(tick) % vencer_count
        r2 = df_vencer.iloc[idx2]

        art = str(r2.get("ARTICULO", "—"))
        lote = str(r2.get("LOTE", "—"))
        dep = str(r2.get("DEPOSITO", "—"))
        ven = str(r2.get("VENCIMIENTO", "—"))
        stk = str(r2.get("STOCK", "—"))
        dias = str(r2.get("Dias_Para_Vencer", "—"))

        vencer_txt = art
        vencer_sub = f"Lote {lote} | Depósito {dep} | Venc {ven} ({dias} días) | Stock {stk}"

    st.markdown("""
    <style>
      .mini-stock-wrap{
        display:flex;
        gap:12px;
        margin: 6px 0 10px 0;
      }
      .mini-stock-card{
        flex:1;
        border:1px solid #e5e7eb;
        border-radius:12px;
        padding:10px 12px;
        background: rgba(255,255,255,0.85);
      }
      .mini-stock-t{
        font-size:0.80rem;
        font-weight:600;
        opacity:0.85;
        margin:0;
      }
      .mini-stock-v{
        font-size:1.00rem;
        font-weight:700;
        margin:4px 0 0 0;
        line-height:1.15;
      }
      .mini-stock-s{
        font-size:0.80rem;
        opacity:0.75;
        margin:4px 0 0 0;
        line-height:1.2;
      }
      .mini-stock-badge{
        font-size:0.75rem;
        opacity:0.75;
        border:1px solid #e5e7eb;
        padding:2px 8px;
        border-radius:999px;
        background: rgba(255,255,255,0.7);
        white-space:nowrap;
        margin:4px 0 0 0;
      }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
      <div class="mini-stock-wrap">
        <div class="mini-stock-card">
          <div class="mini-stock-t">📉 Artículos con STOCK bajo (≤10)</div>
          <div class="mini-stock-v">{stock1_txt}</div>
          <div class="mini-stock-s">{stock1_sub}</div>
          <div class="mini-stock-badge">{stock1_count} regs</div>
        </div>

        <div class="mini-stock-card">
          <div class="mini-stock-t">⏳ Lotes próximos a vencer ({dias_vencer} días)</div>
          <div class="mini-stock-v">{vencer_txt}</div>
          <div class="mini-stock-s">{vencer_sub}</div>
          <div class="mini-stock-badge">{vencer_count} regs</div>
        </div>
      </div>
    """, unsafe_allow_html=True)


# =========================
# 📦 STOCK IA (SIN TARJETAS ADENTRO)
# =========================
def mostrar_stock_ia():
    """Módulo Stock IA - Chat para consultas de stock"""

    # ✅ INICIALIZAR FLAG PARA PAUSAR AUTOREFRESH
    if "pause_autorefresh_stock" not in st.session_state:
        st.session_state["pause_autorefresh_stock"] = False

    # ✅ Inicializar contador para forzar reset del input
    if "stock_input_counter" not in st.session_state:
        st.session_state["stock_input_counter"] = 0

    # ✅ NUEVO: CONTEXTO DEL ARTÍCULO SELECCIONADO
    if "articulo_contexto" not in st.session_state:
        st.session_state["articulo_contexto"] = None

    # Agregar espacio superior para compensar padding removido
    st.markdown("<div style='margin-top: 2.5rem;'></div>", unsafe_allow_html=True)
    
    st.title("📦 Stock IA")
    st.markdown("*Consultas de stock con lenguaje natural*")

    # ⛔ IMPORTANTE: NO LLAMAR mostrar_resumen_stock_rotativo() ACÁ
    # porque se renderiza arriba del menú desde main()

    st.markdown("---")

    # ✅ NUEVO: SELECTBOX PARA SELECCIONAR ARTÍCULO (caso 5)
    lista_articulos = get_lista_articulos_stock()
    articulo_seleccionado = st.selectbox(
        "Seleccionar artículo para contexto:",
        options=["Ninguno"] + lista_articulos,
        index=0,
        key="select_articulo_stock"
    )
    if articulo_seleccionado and articulo_seleccionado != "Ninguno":
        st.session_state["articulo_contexto"] = articulo_seleccionado
        st.session_state["pause_autorefresh_stock"] = True  # ✅ PAUSAR AUTOREFFRESH CUANDO HAY CONTEXTO
        
        if articulo_seleccionado == "Todos":
            # ✅ MOSTRAR STOCK POR FAMILIA, LÓGICA SIMILAR A "stock de id" PERO PARA TODOS
            df_art = get_stock_por_familia()
            descripcion_articulo = "Stock por Familia"
            # No limpiar stock 0, ya que es agrupado
        else:
            # Mostrar stock del artículo seleccionado
            df_art = get_stock_articulo(articulo_seleccionado)
            descripcion_articulo = articulo_seleccionado
            df_art = _clean_stock_df(df_art)
        
        if df_art is not None and not df_art.empty:
            total_stock = df_art['STOCK'].sum() if 'STOCK' in df_art.columns else 0
            render_stock_header(descripcion_articulo, int(total_stock))
            render_stock_table(df_art)
            render_stock_alerts(df_art)
            render_chat_compacto(articulo_seleccionado, df_art)
        else:
            st.warning(f"No hay stock para '{articulo_seleccionado}'.")
    else:
        st.session_state["articulo_contexto"] = None
        st.session_state["pause_autorefresh_stock"] = False  # ✅ REACTIVAR AUTOREFFRESH CUANDO NO HAY CONTEXTO

    st.markdown("---")

    if 'historial_stock' not in st.session_state:
        st.session_state.historial_stock = []

    with st.sidebar:
        st.header("📦 Stock IA - Ayuda")
        st.markdown("""
        **Este módulo entiende:**

        📊 **Consultas generales:**
        - "stock total"
        - "stock por familia"
        - "stock por depósito"
        - "listado de artículos"

        🔍 **Búsquedas específicas:**
        - "stock vitek"
        - "lote D250829AF"
        - "stock familia ID"

        ⚠️ **Vencimientos:**
        - "lotes por vencer"
        - "vencen en 30 días"
        - "lotes vencidos"

        📉 **Alertas:**
        - "stock bajo"
        - "artículos a reponer"
        
        💡 **Preguntas contextuales (con artículo seleccionado):**
        - "¿cuándo vence?"
        - "¿última compra?"
        - "¿en qué depósito está?"
        """)

        st.markdown("---")

        if st.button("🗑️ Limpiar historial", key="limpiar_stock", use_container_width=True):
            st.session_state.historial_stock = []
            st.session_state["pause_autorefresh_stock"] = False  # ✅ REACTIVAR AUTOREFFRESH
            st.rerun()

    # ✅ ALERTAS ARRIBA DEL INPUT (SOLO SI NO HAY HISTORIAL Y NO ESTÁ PAUSADO)
    if not st.session_state.historial_stock and not st.session_state.get("pause_autorefresh_stock", False):
        try:
            alertas = get_alertas_vencimiento_multiple(5)
            if alertas:
                import time
                indice = int(time.time() // 5) % len(alertas)
                alerta = alertas[indice]

                # ✅ CORREGIDO: usar 'dias_restantes' en vez de 'dias'
                dias = alerta['dias_restantes']
                articulo = alerta['articulo']
                lote = alerta['lote']
                venc = alerta['vencimiento']
                stock = alerta['stock']

                # Contador
                contador = f"<div style='text-align: center; font-size: 0.8em; color: #666; margin-top: 5px;'>{indice + 1} de {len(alertas)} alertas</div>"

                html = ""
                if dias <= 7:
                    # Crítico - rojo
                    html = """
                    <div style="background-color: #fee2e2; border-left: 5px solid #dc2626; padding: 15px; border-radius: 5px; margin: 10px 0;">
                        <span style="color: #dc2626; font-weight: bold; font-size: 1.1em;">🚨 ¡ALERTA CRÍTICA!</span><br>
                        <span style="color: #7f1d1d;"><b>{}</b> - Lote: <b>{}</b></span><br>
                        <span style="color: #7f1d1d;">Vence: <b>{}</b> ({} días) | Stock: {}</span>
                    </div>
                    {}
                    """.format(articulo, lote, venc, dias, stock, contador)
                elif dias <= 30:
                    # Urgente - naranja
                    html = """
                    <div style="background-color: #fff7ed; border-left: 5px solid #ea580c; padding: 15px; border-radius: 5px; margin: 10px 0;">
                        <span style="color: #ea580c; font-weight: bold; font-size: 1.1em;">⚠️ PRÓXIMO A VENCER</span><br>
                        <span style="color: #9a3412;"><b>{}</b> - Lote: <b>{}</b></span><br>
                        <span style="color: #9a3412;">Vence: <b>{}</b> ({} días) | Stock: {}</span>
                    </div>
                    {}
                    """.format(articulo, lote, venc, dias, stock, contador)
                else:
                    # Atención - amarillo
                    html = """
                    <div style="background-color: #fefce8; border-left: 5px solid #ca8a04; padding: 15px; border-radius: 5px; margin: 10px 0;">
                        <span style="color: #ca8a04; font-weight: bold; font-size: 1.1em;">📋 Próximo vencimiento</span><br>
                        <span style="color: #854d0e;"><b>{}</b> - Lote: <b>{}</b></span><br>
                        <span style="color: #854d0e;">Vence: <b>{}</b> ({} días) | Stock: {}</span>
                    </div>
                    {}
                    """.format(articulo, lote, venc, dias, stock, contador)

                st.markdown(html, unsafe_allow_html=True)
        except Exception as e:
            print(f"⚠️ Error en alertas de vencimiento: {e}")
            pass  # Si falla la alerta, no afecta el resto

    # ✅ Crear un contenedor para el input (se limpia después de procesar)
    col_input = st.container()
    with col_input:
        pregunta = st.text_input(
            "Escribe tu consulta de stock:",
            placeholder="Ej: stock vitek / lotes por vencer / stock bajo",
            key=f"input_stock_{st.session_state['stock_input_counter']}"  # ✅ Key dinámica
        )

    if pregunta and pregunta.strip():
        # ✅ NUEVO: SI HAY CONTEXTO DE ARTÍCULO, USAR CONSULTA CONTEXTUAL
        articulo_contexto = st.session_state.get("articulo_contexto")
        if articulo_contexto and articulo_contexto != "Ninguno":
            # ✅ PAUSAR AUTOREFRESH TAMBIÉN PARA CONSULTAS CONTEXTUALES
            st.session_state["pause_autorefresh_stock"] = True
            # Procesar pregunta contextual sobre el artículo seleccionado
            with st.spinner("🔍 Consultando stock contextual..."):
                procesar_consulta_stock_contextual(pregunta, articulo_contexto)
            # No agregar al historial normal, ya que es contextual
        else:
            # ✅ PAUSAR AUTOREFRESH AL HACER PREGUNTA
            st.session_state["pause_autorefresh_stock"] = True
            
            with st.spinner("🔍 Consultando stock."):
                respuesta, df = procesar_pregunta_stock(pregunta)
                
                st.session_state.historial_stock.append({
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'pregunta': pregunta,
                    'respuesta': respuesta,
                    'df': df,  # ✅ Agregar DataFrame
                    'tiene_datos': df is not None and not df.empty
                })

                # ✅ Incrementar contador para crear nuevo input (esto limpia el campo)
                st.session_state["stock_input_counter"] += 1
            st.rerun()

    # ✅ MOSTRAR HISTORIAL CON DASHBOARD MODERNO ESTANDARIZADO
    if st.session_state.historial_stock:
        st.markdown("---")
        
        for idx, item in enumerate(st.session_state.historial_stock):
            with st.chat_message("user"):
                st.markdown(item['pregunta'])
            
            with st.chat_message("assistant"):
                st.markdown(item['respuesta'])
                
                if 'df' in item and item['df'] is not None and not item['df'].empty:
                    df = item['df']
                    
                    # ✅ NUEVO: FORMATO ESTANDARIZADO PARA TODAS LAS CONSULTAS
                    if "📦 Stock de" in item['respuesta']:
                        # Stock de artículo específico
                        import re
                        match = re.search(r"📦 Stock de '(.+?)':", item['respuesta'])
                        descripcion_articulo = match.group(1) if match else "Artículo"
                        total_stock = df['STOCK'].sum() if 'STOCK' in df.columns else 0
                        render_stock_header(descripcion_articulo, int(total_stock))
                        render_stock_table(df)
                        render_stock_alerts(df)
                        render_chat_compacto(descripcion_articulo, df)
                    
                    elif "📉 Artículos con stock bajo" in item['respuesta']:
                        # Stock bajo: mostrar cada artículo con su header y mini métricas
                        st.info(f"📉 Se encontraron **{len(df)}** artículos con stock bajo")
                        grouped = df.groupby('ARTICULO')
                        for articulo, group in grouped:
                            total_stock = group['STOCK'].sum() if 'STOCK' in group.columns else 0
                            render_stock_header(articulo, int(total_stock))
                            # Mini métricas para el primer lote
                            first_row = group.iloc[0]
                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("Lote", first_row.get('LOTE', '-') or '-')
                            col2.metric("Depósito", first_row.get('DEPOSITO', '-'))
                            col3.metric("Vencimiento", str(first_row.get('VENCIMIENTO', '-'))[:10])
                            col4.metric("Stock", first_row.get('STOCK', 0))
                            st.divider()
                            render_chat_compacto(articulo, group)
                        render_chat_compacto("stock_bajo", df)
                    
                    else:
                        # Otras consultas: header genérico + tabla + descarga
                        total_stock = df['STOCK'].sum() if 'STOCK' in df.columns else len(df)
                        descripcion = item['respuesta'].split(':')[0].strip() if ':' in item['respuesta'] else "Consulta"
                        render_stock_header(descripcion, int(total_stock))
                        render_stock_table(df)
                        if "lotes" in item['respuesta'].lower():
                            render_stock_alerts(df)
                        render_chat_compacto(descripcion.replace(" ", "_").lower()[:20], df)

    # ✅ AUTOREFRESH CONDICIONAL: SOLO SI NO ESTÁ PAUSADO
    if not st.session_state.get("pause_autorefresh_stock", False):
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=5000, key="stock_keepalive")
        except Exception:
            pass
