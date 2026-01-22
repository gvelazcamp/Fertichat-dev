# ========================================
# 🔬 DEBUG PANEL - Agregar a ui_compras.py
# ========================================
"""
Agregar este código al final de la función Compras_IA(), 
justo antes de las tabs principales (línea ~2400).

Esto crea una pestaña "🔬 Debug" que muestra TODO el flujo.
"""

# ========================================
# VARIABLES DE DEBUG (agregar al inicio del archivo, después de los imports)
# ========================================
if "debug_flow" not in st.session_state:
    st.session_state["debug_flow"] = []

def log_debug(step: str, data: any):
    """Registra cada paso del flujo para debugging"""
    import datetime
    st.session_state["debug_flow"].append({
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3],
        "step": step,
        "data": data
    })

# ========================================
# PANEL DE DEBUG (agregar como nueva tab)
# ========================================

# MODIFICAR la línea donde defines las tabs para agregar tab_debug:
# ANTES:
# tab_chat, tab_comparativas = st.tabs(["💬 Chat", "📊 Menú Comparativas"])

# DESPUÉS:
tab_chat, tab_comparativas, tab_debug = st.tabs(["💬 Chat", "📊 Menú Comparativas", "🔬 Debug"])

# ... (código existente de tab_chat y tab_comparativas) ...

# ========================================
# NUEVA TAB DEBUG (agregar al final)
# ========================================
with tab_debug:
    st.markdown("### 🔬 Panel de Debug - Flujo Completo")
    st.markdown("Visualiza todo el flujo de interpretación y ejecución en tiempo real.")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption("Se registran todos los pasos desde que ingresás una consulta hasta que se renderiza el resultado")
    with col2:
        if st.button("🗑️ Limpiar debug", key="clear_debug"):
            st.session_state["debug_flow"] = []
            st.rerun()
    
    # Mostrar flow en orden inverso (más reciente primero)
    if st.session_state.get("debug_flow"):
        st.markdown("---")
        
        for i, entry in enumerate(reversed(st.session_state["debug_flow"])):
            timestamp = entry["timestamp"]
            step = entry["step"]
            data = entry["data"]
            
            # Color según el tipo de paso
            if "❌" in step or "error" in step.lower():
                color = "#fee2e2"  # Rojo suave
                icon = "❌"
            elif "✅" in step or "success" in step.lower():
                color = "#dcfce7"  # Verde suave
                icon = "✅"
            elif "🧠" in step or "interpret" in step.lower():
                color = "#dbeafe"  # Azul suave
                icon = "🧠"
            elif "💾" in step or "sql" in step.lower():
                color = "#fef3c7"  # Amarillo suave
                icon = "💾"
            elif "📊" in step or "dataframe" in step.lower():
                color = "#e9d5ff"  # Púrpura suave
                icon = "📊"
            else:
                color = "#f3f4f6"  # Gris suave
                icon = "📝"
            
            with st.expander(f"{icon} `{timestamp}` - {step}", expanded=(i < 3)):
                st.markdown(f"""
                <div style="
                    background: {color};
                    padding: 12px;
                    border-radius: 8px;
                    border-left: 4px solid #{'ef4444' if '❌' in step else '10b981' if '✅' in step else '3b82f6'};
                    margin: 8px 0;
                ">
                """, unsafe_allow_html=True)
                
                # Renderizar data según el tipo
                if isinstance(data, dict):
                    st.json(data)
                elif isinstance(data, pd.DataFrame):
                    st.dataframe(data.head(5), use_container_width=True)
                    st.caption(f"Shape: {data.shape[0]} filas × {data.shape[1]} columnas")
                    st.caption(f"Columnas: {', '.join(data.columns.tolist())}")
                elif isinstance(data, str) and len(data) > 100:
                    st.code(data, language="sql" if "SELECT" in data else "python")
                else:
                    st.code(str(data))
                
                st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("👋 El debug flow estará vacío hasta que ejecutes una consulta en el chat.")
        st.markdown("""
        **Qué verás aquí:**
        - 📝 Input del usuario
        - 🧠 Interpretación (tipo y parámetros)
        - 🔀 Router usado (ia_router, ia_compras, etc)
        - 💾 SQL ejecutado
        - 📊 DataFrame resultado
        - 🎨 Función de renderizado
        - ❌ Errores (si los hay)
        """)

# ========================================
# MODIFICACIONES EN EL CÓDIGO EXISTENTE
# ========================================

"""
Ahora necesitás agregar log_debug() en los lugares clave:

1. CUANDO SE RECIBE INPUT:
   (en la parte donde procesas st.chat_input)
   
   pregunta = st.chat_input("Escribe tu consulta...")
   if pregunta:
       log_debug("📝 Input Usuario", pregunta)

2. DESPUÉS DE INTERPRETAR:
   
   resultado = interpretar_pregunta(pregunta)
   log_debug("🧠 Interpretación", resultado)

3. ANTES DE EJECUTAR SQL:
   
   tipo = resultado.get("tipo")
   parametros = resultado.get("parametros")
   log_debug("🔀 Router", {"tipo": tipo, "parametros": parametros})

4. DESPUÉS DE EJECUTAR SQL:
   
   resultado_sql = ejecutar_consulta_por_tipo(tipo, parametros)
   log_debug("💾 SQL Resultado", {
       "tipo": type(resultado_sql).__name__,
       "shape": resultado_sql.shape if isinstance(resultado_sql, pd.DataFrame) else "N/A"
   })
   
   if isinstance(resultado_sql, pd.DataFrame):
       log_debug("📊 DataFrame", resultado_sql)

5. AL RENDERIZAR:
   
   try:
       render_dashboard_compras_vendible(df, titulo="Datos")
       log_debug("✅ Renderizado exitoso", "Dashboard vendible")
   except Exception as e:
       log_debug("❌ Error en renderizado", str(e))

6. CUANDO HAY ERRORES:
   
   except Exception as e:
       log_debug("❌ Error", {"mensaje": str(e), "tipo": type(e).__name__})
"""

# ========================================
# EJEMPLO DE INTEGRACIÓN COMPLETA
# ========================================

"""
Aquí está cómo se vería el bloque del chat_input modificado:

if pregunta:
    log_debug("📝 Input Usuario", pregunta)
    
    st.session_state["historial_compras"].append(
        {"role": "user", "content": pregunta}
    )

    resultado = interpretar_pregunta(pregunta)
    log_debug("🧠 Interpretación", resultado)
    
    tipo = resultado.get("tipo", "")
    parametros = resultado.get("parametros", {})
    
    log_debug("🔀 Tipo detectado", {"tipo": tipo, "parametros": parametros})

    respuesta_content = ""
    respuesta_df = None

    if tipo == "conversacion":
        # ... código existente ...
        log_debug("💬 Respuesta conversacional", respuesta_content)
        
    elif tipo == "no_entendido":
        # ... código existente ...
        log_debug("❓ No entendido", resultado.get("sugerencia", ""))
        
    else:
        try:
            log_debug("⚙️ Ejecutando consulta", {"tipo": tipo})
            
            resultado_sql = ejecutar_consulta_por_tipo(tipo, parametros)
            
            if isinstance(resultado_sql, pd.DataFrame):
                log_debug("📊 DataFrame obtenido", {
                    "shape": resultado_sql.shape,
                    "columns": resultado_sql.columns.tolist()
                })
                log_debug("📊 Preview DataFrame", resultado_sql)
                
                if len(resultado_sql) == 0:
                    respuesta_content = "⚠️ No se encontraron resultados"
                    log_debug("⚠️ Sin resultados", "DataFrame vacío")
                else:
                    # Generar mensaje según tipo
                    if tipo.startswith("compras_"):
                        respuesta_content = f"✅ Encontré **{len(resultado_sql)}** compras"
                        log_debug("✅ Compras encontradas", len(resultado_sql))
                    # ... etc
                    
                    respuesta_df = resultado_sql
            else:
                respuesta_content = str(resultado_sql)
                log_debug("📄 Resultado texto", respuesta_content)
                
        except Exception as e:
            log_debug("❌ ERROR", {
                "tipo": type(e).__name__,
                "mensaje": str(e),
                "traceback": traceback.format_exc()
            })
            respuesta_content = f"❌ Error: {str(e)}"

    st.session_state["historial_compras"].append({
        "role": "assistant",
        "content": respuesta_content,
        "df": respuesta_df,
        "tipo": tipo,
        "pregunta": pregunta,
    })
    
    log_debug("✅ Agregado al historial", {
        "tipo": tipo,
        "tiene_df": respuesta_df is not None
    })

    st.rerun()
"""
