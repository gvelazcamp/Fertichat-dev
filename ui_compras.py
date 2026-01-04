# =========================
# UI_COMPRAS.PY - CON HISTORIAL PERSISTENTE
# =========================

import streamlit as st
import pandas as pd
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
    """Inicializa el historial del chat en session_state"""
    if "historial_compras" not in st.session_state:
        st.session_state["historial_compras"] = []


# =========================
# FUNCIÓN ROUTER PARA EJECUTAR SQL
# =========================

def ejecutar_consulta_por_tipo(tipo: str, parametros: dict):
    """Router que ejecuta la función SQL correcta según el tipo"""
    
    # COMPRAS
    if tipo == "compras_anio":
        return get_compras_anio(parametros["anio"])
    
    elif tipo == "compras_proveedor_mes":
        return get_detalle_compras_proveedor_mes(
            parametros["proveedor"], 
            parametros["mes"]
        )
    
    elif tipo == "compras_proveedor_anio":
        return get_detalle_compras_proveedor_anio(
            parametros["proveedor"],
            parametros["anio"]
        )
    
    elif tipo == "compras_articulo_mes":
        return get_detalle_compras_articulo_mes(
            parametros["articulo"],
            parametros["mes"]
        )
    
    elif tipo == "compras_articulo_anio":
        return get_detalle_compras_articulo_anio(
            parametros["articulo"],
            parametros["anio"]
        )
    
    elif tipo == "compras_mes":
        return get_compras_por_mes_excel(parametros["mes"])
    
    # FACTURAS
    elif tipo == "ultima_factura":
        return get_ultima_factura_inteligente(parametros["patron"])
    
    elif tipo == "facturas_articulo":
        return get_facturas_de_articulo(parametros["articulo"])
    
    elif tipo == "detalle_factura":
        return get_detalle_factura_por_numero(parametros["nro_factura"])
    
    # COMPARACIONES
    elif tipo == "comparar_proveedor_meses":
        return get_comparacion_proveedor_meses(
            parametros["mes1"],
            parametros["mes2"],
            parametros["proveedor"]
        )
    
    elif tipo == "comparar_proveedor_anios":
        return get_comparacion_proveedor_anios_monedas(
            parametros["anios"],
            parametros["proveedor"]
        )
    
    elif tipo == "comparar_articulo_meses":
        return get_comparacion_articulo_meses(
            parametros["mes1"],
            parametros["mes2"],
            parametros["articulo"]
        )
    
    elif tipo == "comparar_articulo_anios":
        return get_comparacion_articulo_anios(
            parametros["anios"],
            parametros["articulo"]
        )
    
    elif tipo == "comparar_familia_meses":
        moneda = parametros.get("moneda", "pesos")
        return get_comparacion_familia_meses_moneda(
            parametros["mes1"],
            parametros["mes2"],
            moneda
        )
    
    elif tipo == "comparar_familia_anios":
        return get_comparacion_familia_anios_monedas(parametros["anios"])
    
    # GASTOS
    elif tipo == "gastos_familias_mes":
        return get_gastos_todas_familias_mes(parametros["mes"])
    
    elif tipo == "gastos_familias_anio":
        return get_gastos_todas_familias_anio(parametros["anio"])
    
    elif tipo == "gastos_secciones":
        return get_gastos_secciones_detalle_completo(
            parametros["familias"],
            parametros["mes"]
        )
    
    # TOP
    elif tipo == "top_proveedores":
        moneda = parametros.get("moneda", "pesos")
        anio = parametros.get("anio")
        mes = parametros.get("mes")
        return get_top_10_proveedores_chatbot(moneda, anio, mes)
    
    # STOCK
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
        raise ValueError(f"❌ Tipo '{tipo}' no tiene función implementada")


# =========================
# FUNCIÓN PARA OBTENER RESUMEN
# =========================

def obtener_resumen_si_existe(tipo: str, parametros: dict):
    """Obtiene resumen si existe para el tipo de consulta"""
    info_tipo = obtener_info_tipo(tipo)
    if not info_tipo:
        return None
    
    funcion_resumen = info_tipo.get("resumen")
    if not funcion_resumen:
        return None
    
    try:
        if funcion_resumen == "get_total_compras_anio":
            return get_total_compras_anio(parametros["anio"])
        
        elif funcion_resumen == "get_total_compras_proveedor_anio":
            return get_total_compras_proveedor_anio(
                parametros["proveedor"],
                parametros["anio"]
            )
        
        elif funcion_resumen == "get_total_compras_articulo_anio":
            return get_total_compras_articulo_anio(
                parametros["articulo"],
                parametros["anio"]
            )
        
        return None
    except:
        return None


# =========================
# UI PRINCIPAL - COMPRAS IA
# =========================

def Compras_IA():
    """Interfaz principal del chatbot de compras con IA"""
    
    # Inicializar historial
    inicializar_historial()
    
    st.markdown("### 🤖 Asistente de Compras IA")
    st.markdown("Preguntá en lenguaje natural sobre compras, gastos, proveedores y más.")
    
    # Ejemplos
    with st.expander("💡 Ver ejemplos de preguntas"):
        st.markdown("""
        **Compras:**
        - "compras roche noviembre 2025"
        - "cuánto le compramos a biodiagnóstico este mes"
        - "compras 2025"
        
        **Comparaciones:**
        - "comparar roche octubre noviembre 2025"
        - "comparar gastos familias 2024 2025"
        
        **Facturas:**
        - "última factura vitek"
        - "cuando vino vitek"
        
        **Stock:**
        - "stock vitek"
        - "lotes por vencer"
        
        **Conversación:**
        - "hola"
        - "gracias"
        """)
    
    # Botones de control
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        if st.button("🗑️ Limpiar chat", use_container_width=True):
            st.session_state["historial_compras"] = []
            st.rerun()
    
    with col2:
        debug_mode = st.checkbox("🔍 Debug", value=False)
    
    st.markdown("---")
    
    # ========================================
    # MOSTRAR TODO EL HISTORIAL
    # ========================================
    for mensaje in st.session_state["historial_compras"]:
        with st.chat_message(mensaje["role"]):
            st.write(mensaje["content"])
            
            # Si hay datos adicionales (tablas, métricas)
            if "data" in mensaje and mensaje["data"]:
                data = mensaje["data"]
                
                # Mostrar resumen si existe
                if "resumen" in data and data["resumen"]:
                    st.success("📈 Resumen:")
                    cols = st.columns(len(data["resumen"]))
                    for idx, (key, value) in enumerate(data["resumen"].items()):
                        with cols[idx]:
                            st.metric(label=key, value=value)
                    st.markdown("---")
                
                # Mostrar tabla si existe
                if "dataframe" in data and data["dataframe"] is not None:
                    df = data["dataframe"]
                    st.success(f"✅ Encontré **{len(df)}** resultados")
                    st.dataframe(df, use_container_width=True, height=400)
                    
                    # Botón de descarga
                    csv = df.to_csv(index=False, encoding='utf-8-sig')
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    st.download_button(
                        label="📥 Descargar CSV",
                        data=csv,
                        file_name=f"consulta_{timestamp}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key=f"download_{mensaje.get('id', timestamp)}"
                    )
    
    # ========================================
    # INPUT DEL USUARIO
    # ========================================
    pregunta = st.chat_input("Escribí tu consulta aquí...")
    
    if pregunta:
        # Agregar pregunta al historial
        st.session_state["historial_compras"].append({
            "role": "user",
            "content": pregunta,
            "id": datetime.now().timestamp()
        })
        
        # Interpretar con IA
        with st.spinner("🤔 Analizando tu pregunta..."):
            resultado = interpretar_pregunta(pregunta)
        
        tipo = resultado.get("tipo", "")
        parametros = resultado.get("parametros", {})
        debug = resultado.get("debug", "")
        
        # Debug info
        if debug_mode:
            st.info(f"🔍 Debug: Tipo={tipo}, Params={parametros}")
        
        # Preparar respuesta
        respuesta_texto = ""
        respuesta_data = {}
        
        # PROCESAR SEGÚN TIPO
        if tipo == "conversacion":
            respuesta_texto = responder_con_openai(pregunta, tipo="conversacion")
        
        elif tipo == "conocimiento":
            respuesta_texto = responder_con_openai(pregunta, tipo="conocimiento")
        
        elif tipo == "no_entendido":
            respuesta_texto = "🤔 No entendí bien tu pregunta."
            if resultado.get("sugerencia"):
                respuesta_texto += f"\n\n**¿Quisiste decir:** {resultado['sugerencia']}"
            if resultado.get("alternativas"):
                respuesta_texto += "\n\n**O probá con:**"
                for alt in resultado["alternativas"]:
                    respuesta_texto += f"\n- `{alt}`"
        
        else:
            # CONSULTA DE DATOS
            info_tipo = obtener_info_tipo(tipo)
            
            if not info_tipo:
                respuesta_texto = f"❌ El tipo '{tipo}' no tiene una función SQL asociada"
            else:
                try:
                    # Ejecutar consulta
                    resultado_sql = ejecutar_consulta_por_tipo(tipo, parametros)
                    resumen = obtener_resumen_si_existe(tipo, parametros)
                    
                    # Guardar datos
                    respuesta_data = {
                        "resumen": resumen if isinstance(resumen, dict) else None,
                        "dataframe": resultado_sql if isinstance(resultado_sql, pd.DataFrame) else None
                    }
                    
                    # Texto de respuesta
                    if isinstance(resultado_sql, pd.DataFrame):
                        if len(resultado_sql) == 0:
                            respuesta_texto = "⚠️ No se encontraron resultados para esta consulta."
                        else:
                            respuesta_texto = f"📊 Consulta ejecutada correctamente"
                    elif isinstance(resultado_sql, dict):
                        respuesta_texto = "✅ Resultado obtenido"
                        respuesta_data["resumen"] = resultado_sql
                    else:
                        respuesta_texto = str(resultado_sql)
                
                except Exception as e:
                    respuesta_texto = f"❌ Error ejecutando consulta: {str(e)}"
                    if debug_mode:
                        respuesta_texto += f"\n\n```\n{str(e)}\n```"
        
        # Agregar respuesta al historial
        st.session_state["historial_compras"].append({
            "role": "assistant",
            "content": respuesta_texto,
            "data": respuesta_data,
            "id": datetime.now().timestamp()
        })
        
        # Rerun para mostrar
        st.rerun()
