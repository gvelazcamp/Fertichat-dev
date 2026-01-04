# =========================
# UI_COMPRAS.PY - VERSIÓN CORREGIDA CON IA_INTERPRETADOR
# =========================

import streamlit as st
import pandas as pd
from datetime import datetime

# ✅ IMPORT CORREGIDO - EL ARCHIVO SE LLAMA ia_interpretador.py
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
# FUNCIÓN ROUTER PARA EJECUTAR SQL
# =========================

def ejecutar_consulta_por_tipo(tipo: str, parametros: dict):
    """
    Router que ejecuta la función SQL correcta según el tipo
    """
    
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
# FUNCIÓN PARA OBTENER RESUMEN (SI EXISTE)
# =========================

def obtener_resumen_si_existe(tipo: str, parametros: dict):
    """
    Algunas consultas tienen una versión 'resumen' además del detalle.
    """
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
    """
    Interfaz principal del chatbot de compras con IA
    """
    
    st.markdown("### 🤖 Asistente de Compras IA")
    st.markdown("Preguntá en lenguaje natural sobre compras, gastos, proveedores y más.")
    
    # Ejemplos
    with st.expander("💡 Ver ejemplos de preguntas"):
        st.markdown("""
        **Compras:**
        - "compras roche noviembre 2025"
        - "cuánto le compramos a biodiagnóstico este mes"
        - "compras 2025"
        - "detalle compras wiener 2024"
        
        **Comparaciones:**
        - "comparar roche octubre noviembre 2025"
        - "comparar gastos familias 2024 2025"
        - "comparar vitek 2023 2024"
        
        **Facturas:**
        - "última factura vitek"
        - "cuando vino vitek"
        - "detalle factura 275217"
        
        **Stock:**
        - "stock vitek"
        - "lotes por vencer"
        - "stock total"
        - "stock bajo"
        
        **Gastos:**
        - "gastos familias enero 2026"
        - "top proveedores 2025"
        - "gastos secciones G FB enero 2026"
        
        **Conversación:**
        - "hola"
        - "gracias"
        - "qué puedes hacer"
        """)
    
    # Debug mode toggle
    if st.checkbox("🔍 Modo debug", value=False, key="debug_mode_compras"):
        st.session_state["debug_mode"] = True
    else:
        st.session_state["debug_mode"] = False
    
    st.markdown("---")
    
    # Input del usuario
    pregunta = st.chat_input("Escribí tu consulta aquí...")
    
    if pregunta:
        # Mostrar mensaje del usuario
        with st.chat_message("user"):
            st.write(pregunta)
        
        # Interpretar con IA
        with st.spinner("🤔 Analizando tu pregunta..."):
            resultado = interpretar_pregunta(pregunta)
        
        tipo = resultado.get("tipo", "")
        parametros = resultado.get("parametros", {})
        debug = resultado.get("debug", "")
        
        # Mostrar debug si está activado
        if st.session_state.get("debug_mode", False):
            with st.expander("🔍 Información de debug"):
                st.json({
                    "tipo": tipo,
                    "parametros": parametros,
                    "debug": debug,
                    "resultado_completo": resultado
                })
        
        # Procesar según el tipo
        with st.chat_message("assistant"):
            
            # CASO 1: CONVERSACIÓN
            if tipo == "conversacion":
                with st.spinner("💬 Generando respuesta..."):
                    respuesta = responder_con_openai(pregunta, tipo="conversacion")
                st.write(respuesta)
            
            # CASO 2: CONOCIMIENTO GENERAL
            elif tipo == "conocimiento":
                with st.spinner("🧠 Buscando información..."):
                    respuesta = responder_con_openai(pregunta, tipo="conocimiento")
                st.write(respuesta)
            
            # CASO 3: NO ENTENDIDO
            elif tipo == "no_entendido":
                st.warning("🤔 No entendí bien tu pregunta.")
                
                if resultado.get("sugerencia"):
                    st.write(f"**¿Quisiste decir:** {resultado['sugerencia']}")
                
                if resultado.get("alternativas"):
                    st.write("**O probá con:**")
                    for alt in resultado["alternativas"]:
                        st.write(f"- `{alt}`")
            
            # CASO 4: CONSULTA DE DATOS
            else:
                # Verificar que el tipo tenga mapeo
                info_tipo = obtener_info_tipo(tipo)
                
                if not info_tipo:
                    st.error(f"❌ El tipo '{tipo}' no tiene una función SQL asociada")
                    st.info("Esto es un error de configuración. Por favor reportalo al desarrollador.")
                    return
                
                # Ejecutar la consulta
                try:
                    with st.spinner("📊 Consultando base de datos..."):
                        resultado_sql = ejecutar_consulta_por_tipo(tipo, parametros)
                    
                    # Obtener resumen si existe
                    resumen = obtener_resumen_si_existe(tipo, parametros)
                    
                    # MOSTRAR RESULTADOS
                    
                    # Si hay resumen, mostrarlo primero
                    if resumen and isinstance(resumen, dict):
                        st.success("📈 Resumen:")
                        cols = st.columns(len(resumen))
                        for idx, (key, value) in enumerate(resumen.items()):
                            with cols[idx]:
                                st.metric(label=key, value=value)
                        st.markdown("---")
                    
                    # Mostrar detalle
                    if isinstance(resultado_sql, pd.DataFrame):
                        if len(resultado_sql) == 0:
                            st.warning("⚠️ No se encontraron resultados para esta consulta.")
                        else:
                            st.success(f"✅ Encontré **{len(resultado_sql)}** resultados")
                            
                            # Mostrar tabla
                            st.dataframe(
                                resultado_sql, 
                                use_container_width=True,
                                height=400
                            )
                            
                            # Botón de descarga
                            csv = resultado_sql.to_csv(index=False, encoding='utf-8-sig')
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            st.download_button(
                                label="📥 Descargar CSV",
                                data=csv,
                                file_name=f"consulta_{tipo}_{timestamp}.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
                    
                    elif isinstance(resultado_sql, dict):
                        # Es un diccionario (resumen/métricas)
                        st.success("✅ Resultado:")
                        cols = st.columns(len(resultado_sql))
                        for idx, (key, value) in enumerate(resultado_sql.items()):
                            with cols[idx]:
                                st.metric(label=key, value=value)
                    
                    elif isinstance(resultado_sql, str):
                        # Es un mensaje de texto
                        st.info(resultado_sql)
                    
                    else:
                        # Otro tipo de resultado
                        st.write(resultado_sql)
                
                except Exception as e:
                    st.error(f"❌ Error ejecutando consulta: {str(e)}")
                    
                    if st.session_state.get("debug_mode", False):
                        st.exception(e)
                    else:
                        st.info("💡 Activá el modo debug para ver más detalles del error")
