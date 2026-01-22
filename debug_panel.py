# ========================================
# debug_panel.py - Módulo de Debug Independiente con Trazabilidad
# ========================================
"""
Módulo para debugging visual en Streamlit con detección automática de errores.
Uso:
    1. Importar: from debug_panel import DebugPanel
    2. Inicializar: debug = DebugPanel()
    3. Loggear pasos: debug.log("paso", data)
    4. Loggear módulo: debug.log_module("ui_compras", "ui_compras.py")
    5. Mostrar panel: debug.render()
"""

import streamlit as st
import pandas as pd
import datetime
import json
import traceback


class DebugPanel:
    """Panel de debugging visual para Streamlit con trazabilidad y validaciones"""
    
    def __init__(self, session_key="debug_flow"):
        """Inicializa el panel de debug"""
        self.session_key = session_key
        if self.session_key not in st.session_state:
            st.session_state[self.session_key] = []
    
    def log(self, step: str, data: any):
        """
        Registra un paso en el flujo de debug
        
        Args:
            step: Descripción del paso (ej: "📝 Input Usuario")
            data: Datos a registrar (dict, DataFrame, string, etc)
        """
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        st.session_state[self.session_key].append({
            "timestamp": timestamp,
            "step": step,
            "data": data
        })
    
    def log_module(self, module_name: str, file_path: str = None):
        """
        Registra el módulo o archivo usado en el flujo
        
        Args:
            module_name: Nombre del módulo (ej: "ui_compras")
            file_path: Ruta del archivo (opcional, ej: "ui_compras.py")
        """
        data = {"module": module_name}
        if file_path:
            data["file"] = file_path
        
        self.log(f"🔀 Módulo usado: {module_name}", data)
    
    def log_sql(self, function_name: str, params: dict, query: str = None):
        """
        Registra una llamada SQL con información detallada
        
        Args:
            function_name: Nombre de la función SQL (ej: "get_compras_anio")
            params: Parámetros pasados a la función
            query: Query SQL real (opcional)
        """
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        data = {
            "función": function_name,
            "parámetros": params
        }
        
        if query:
            data["query_sql"] = query
        
        st.session_state[self.session_key].append({
            "timestamp": timestamp,
            "step": "💾 SQL Query",
            "data": data,
            "is_sql": True  # Marca especial para renderizado
        })
    
    def clear(self):
        """Limpia todos los logs"""
        st.session_state[self.session_key] = []
    
    def validate(self):
        """
        Valida automáticamente el flujo en busca de errores comunes
        
        Returns:
            list: Lista de mensajes de error encontrados
        """
        logs = st.session_state.get(self.session_key, [])
        errors = []
        modules = []
        files = []
        sqls = []
        functions = []
        interpretations = []
        
        for entry in logs:
            if "Módulo usado" in entry["step"]:
                modules.append(entry["data"].get("module", ""))
                if "file" in entry["data"]:
                    files.append(entry["data"]["file"])
            
            if entry.get("is_sql"):
                sql = entry["data"].get("query_sql", "").upper()
                func = entry["data"].get("función", "").lower()
                sqls.append(sql)
                functions.append(func)
                
                # Validación específica: SQL vs Función
                if "FACTURAS" in sql and "compras" in func:
                    errors.append(f"❌ Error en '{entry['timestamp']}': SQL de FACTURAS usado en función '{func}'. El error está aquí - este SQL no corresponde a la función de compras.")
                if "COMPRAS" in sql and "facturas" in func:
                    errors.append(f"❌ Error en '{entry['timestamp']}': SQL de COMPRAS usado en función '{func}'. El error está aquí - este SQL no corresponde a la función de facturas.")
            
            if "Interpretación" in entry["step"]:
                interpretations.append(entry["data"])
        
        # Validación especial: Patrón detectado pero no_entendido
        for interp in interpretations:
            if interp.get("tipo") == "no_entendido" and "patron_detectado" in interp:
                patron = interp.get("patron_detectado", "")
                match_text = ""
                if "validaciones" in interp:
                    for bloque, val in interp["validaciones"].items():
                        if val.get("match"):
                            match_text = val.get("match_text", "")
                            break
                errors.append(f"❌ Patrón '{patron}' detectado en '{match_text}', pero el sistema lo clasificó como 'no_entendido'. El error está aquí - revisa la lógica del interpretador: probablemente el patrón no está siendo procesado correctamente en el router, o falta en aliases/BD.")
        
        # Detectar SQLs duplicados
        unique_sqls = set(sql for sql in sqls if sql)
        if len(unique_sqls) < len([sql for sql in sqls if sql]):
            errors.append("❌ Hay consultas SQL duplicadas en el flujo. Revisa los logs para identificar cuáles se están pisando.")
        
        # Detectar archivos duplicados
        if len(set(files)) < len(files):
            errors.append("❌ Hay archivos duplicados o el mismo archivo usado múltiples veces. Verifica si hay módulos redundantes.")
        
        # Múltiples módulos inconsistentes
        unique_modules = set(modules)
        if len(unique_modules) > 1:
            module_list = ", ".join(unique_modules)
            errors.append(f"⚠️ Se usaron múltiples módulos: {module_list}. Verifica si esto es correcto o si se está yendo al módulo equivocado (ej: ui_compras en lugar de ui_facturas).")
        
        return errors
    
    def render(self):
        """Renderiza el panel de debug completo con validaciones"""
        st.markdown("### 🔬 Panel de Debug - Flujo Completo con Trazabilidad")
        st.markdown("Visualiza todo el flujo de interpretación y ejecución en tiempo real, con detección automática de errores.")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption("Se registran todos los pasos desde que ingresás una consulta hasta que se renderiza el resultado, incluyendo módulos y validaciones.")
        with col2:
            if st.button("🗑️ Limpiar debug", key="clear_debug_btn"):
                self.clear()
                st.rerun()
        
        # Validaciones automáticas
        validations = self.validate()
        if validations:
            st.markdown("### ⚠️ Validaciones Automáticas")
            for error in validations:
                st.error(error)
            st.markdown("**💡 Solución:** Revisa los logs abajo para identificar exactamente dónde ocurre el error y corrígelo profesionalmente.")
        else:
            st.success("✅ Flujo validado correctamente - no se detectaron errores comunes.")
        
        # Mostrar flow
        if st.session_state.get(self.session_key):
            st.markdown("---")
            
            for i, entry in enumerate(reversed(st.session_state[self.session_key])):
                timestamp = entry["timestamp"]
                step = entry["step"]
                data = entry["data"]
                
                # Determinar color e icono
                color, icon = self._get_style(step)
                
                with st.expander(f"{icon} `{timestamp}` - {step}", expanded=(i < 3)):
                    self._render_data(data, color, step)
        else:
            st.info("👋 El debug flow estará vacío hasta que ejecutes una consulta.")
            st.markdown("""
            **Qué verás aquí:**
            - 📝 Input del usuario
            - 🧠 Interpretación (tipo y parámetros)
            - 🔀 Módulo usado (con archivo si se especifica)
            - 💾 SQL ejecutado
            - 📊 DataFrame resultado
            - 🎨 Función de renderizado
            - ❌ Errores (si los hay)
            - ⚠️ Validaciones automáticas para detectar inconsistencias
            """)
    
    def _get_style(self, step: str):
        """Determina color e icono según el tipo de paso"""
        step_lower = step.lower()
        
        if "❌" in step or "error" in step_lower:
            return "#fee2e2", "❌"  # Rojo
        elif "✅" in step or "success" in step_lower or "exitoso" in step_lower:
            return "#dcfce7", "✅"  # Verde
        elif "🧠" in step or "interpret" in step_lower:
            return "#dbeafe", "🧠"  # Azul
        elif "💾" in step or "sql" in step_lower:
            return "#fef3c7", "💾"  # Amarillo
        elif "📊" in step or "dataframe" in step_lower:
            return "#e9d5ff", "📊"  # Púrpura
        elif "🔀" in step or "módulo" in step_lower:
            return "#fed7aa", "🔀"  # Naranja
        else:
            return "#f3f4f6", "📝"  # Gris
    
    def _render_data(self, data, color, step):
        """Renderiza los datos según su tipo"""
        border_color = "#ef4444" if "❌" in step else "#10b981" if "✅" in step else "#3b82f6"
        
        st.markdown(f"""
        <div style="
            background: {color};
            padding: 12px;
            border-radius: 8px;
            border-left: 4px solid {border_color};
            margin: 8px 0;
        ">
        """, unsafe_allow_html=True)
        
        try:
            if isinstance(data, pd.DataFrame):
                st.dataframe(data.head(10), use_container_width=True)
                st.caption(f"📏 Shape: {data.shape[0]} filas × {data.shape[1]} columnas")
                st.caption(f"📋 Columnas: {', '.join(data.columns.tolist())}")
                
            elif isinstance(data, dict):
                # Renderizado especial para módulos
                if "module" in data:
                    st.markdown("**🏗️ Módulo:**")
                    st.code(data["module"], language="python")
                    if "file" in data:
                        st.markdown("**📁 Archivo:**")
                        st.code(data["file"], language="text")
                
                # Renderizado especial para SQL queries
                elif "query_sql" in data:
                    st.markdown("**🎯 Función SQL:**")
                    st.code(data.get("función", "N/A"), language="python")
                    
                    st.markdown("**📝 Parámetros:**")
                    st.json(data.get("parámetros", {}))
                    
                    if data.get("query_sql"):
                        st.markdown("**💾 Query SQL Real:**")
                        st.code(data["query_sql"], language="sql")
                
                # Renderizado especial para interpretaciones con detalles
                elif "tipo" in data and "interpretador_usado" in data:
                    st.markdown("**🎯 Tipo detectado:**")
                    tipo_color = "#10b981" if data.get("tipo") != "no_entendido" else "#ef4444"
                    st.markdown(f"<span style='color: {tipo_color}; font-weight: bold;'>{data.get('tipo', 'N/A')}</span>", unsafe_allow_html=True)
                    
                    if "patron_detectado" in data:
                        st.markdown("**🔍 Patrón detectado:**")
                        st.code(data["patron_detectado"], language="regex")
                    
                    if "debug" in data:
                        st.markdown("**🐛 Debug info:**")
                        st.text(data["debug"])
                    
                    if "validaciones" in data:
                        st.markdown("**✅ Validaciones:**")
                        st.json(data["validaciones"])
                    
                    st.markdown("**📝 Parámetros:**")
                    st.json(data.get("parametros", {}))
                    
                    if "sugerencia" in data:
                        st.markdown("**💡 Sugerencia:**")
                        st.info(data["sugerencia"])
                else:
                    st.json(data)
                
            elif isinstance(data, str):
                if len(data) > 100 or "\n" in data:
                    # Detectar tipo de código
                    if "SELECT" in data.upper() or "FROM" in data.upper():
                        st.code(data, language="sql")
                    elif "def " in data or "import " in data:
                        st.code(data, language="python")
                    else:
                        st.code(data)
                else:
                    st.text(data)
                    
            elif isinstance(data, (list, tuple)):
                st.json(data)
                
            else:
                st.code(str(data))
                
        except Exception as e:
            st.error(f"Error renderizando data: {e}")
            st.code(str(data))
        
        st.markdown("</div>", unsafe_allow_html=True)


# ========================================
# WRAPPER DECORADOR (Opcional - Avanzado)
# ========================================

def debug_step(step_name: str):
    """
    Decorador para loggear automáticamente funciones
    
    Uso:
        @debug_step("🔍 Buscando proveedores")
        def buscar_proveedores(query):
            return resultados
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            debug = DebugPanel()
            try:
                debug.log(f"⏩ Iniciando: {step_name}", {
                    "funcion": func.__name__,
                    "args": str(args)[:100],
                    "kwargs": str(kwargs)[:100]
                })
                result = func(*args, **kwargs)
                debug.log(f"✅ Completado: {step_name}", {
                    "funcion": func.__name__,
                    "resultado_tipo": type(result).__name__
                })
                return result
            except Exception as e:
                debug.log(f"❌ Error en: {step_name}", {
                    "funcion": func.__name__,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                raise
        return wrapper
    return decorator


# ========================================
# EJEMPLO DE USO
# ========================================

if __name__ == "__main__":
    # Este es un ejemplo de cómo usarlo
    st.set_page_config(page_title="Debug Panel Demo", layout="wide")
    
    debug = DebugPanel()
    
    st.title("Demo del Panel de Debug con Trazabilidad")
    
    # Tabs de ejemplo
    tab1, tab2 = st.tabs(["Demo", "🔬 Debug"])
    
    with tab1:
        st.header("Demo")
        
        if st.button("Simular consulta exitosa"):
            debug.log("📝 Input Usuario", "compras 2025")
            debug.log("🧠 Interpretación", {
                "tipo": "compras_anio",
                "parametros": {"anios": [2025]}
            })
            debug.log_module("ui_compras", "ui_compras.py")
            debug.log_sql("get_compras_anio", {"anios": [2025]}, """
                SELECT Proveedor, SUM(Total) AS Total
                FROM compras_raw
                WHERE Año = 2025
                GROUP BY Proveedor
                ORDER BY Total DESC
                LIMIT 20
            """)
            debug.log("📊 DataFrame", pd.DataFrame({
                "Proveedor": ["ROCHE", "BIOKEY"],
                "Total": [1000000, 500000]
            }))
            debug.log("✅ Renderizado exitoso", "Dashboard mostrado correctamente")
            st.success("¡Consulta simulada! Ve a la pestaña Debug")
        
        if st.button("Simular error de módulo"):
            debug.log("📝 Input Usuario", "facturas 2025")
            debug.log("🧠 Interpretación", {
                "tipo": "facturas_anio",
                "parametros": {"anios": [2025]}
            })
            debug.log_module("ui_compras", "ui_compras.py")  # Error: módulo equivocado
            debug.log_sql("get_facturas_anio", {"anios": [2025]}, """
                SELECT Proveedor, SUM(Total) AS Total
                FROM facturas_raw
                WHERE Año = 2025
                GROUP BY Proveedor
                ORDER BY Total DESC
                LIMIT 20
            """)
            debug.log("❌ Error", "Módulo incorrecto usado")
            st.error("¡Error simulado! Ve a la pestaña Debug")
        
        if st.button("Simular SQL duplicado"):
            debug.log("📝 Input Usuario", "compras 2025")
            debug.log_module("ui_compras", "ui_compras.py")
            debug.log_sql("get_compras_anio", {"anios": [2025]}, "SELECT * FROM compras")
            debug.log_sql("get_compras_anio", {"anios": [2025]}, "SELECT * FROM compras")  # Duplicado
            st.warning("¡SQL duplicado simulado! Ve a la pestaña Debug")
        
        if st.button("Simular patrón detectado pero no_entendido"):
            debug.log("📝 Input Usuario", "compras 2025")
            debug.log("🧠 Interpretación", {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": "Ej: compras vitek 2025 | compras fb 2024 | compras kit noviembre 2025",
                "debug": "no encontrado en aliases ni BD",
                "interpretador_usado": "interpretar_canonico",
                "bloques_ejecutados": ["BLOQUE_FORZADO_COMPRAS_ANIO"],
                "validaciones": {
                    "bloque_compras_anio": {
                        "patron": r"\b(compra|compras)\s+\d{4}\b",
                        "match": True,
                        "match_text": "compras 2025"
                    }
                },
                "patron_detectado": r"\b(compra|compras)\s+\d{4}\b"
            })
            debug.log("❓ No entendido", {
                "sugerencia": "Ej: compras vitek 2025 | compras fb 2024 | compras kit noviembre 2025"
            })
            st.error("¡Patrón detectado pero no_entendido simulado! Ve a la pestaña Debug")
    
    with tab2:
        debug.render()
