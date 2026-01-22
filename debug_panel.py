# ========================================
# debug_panel.py - Módulo de Debug Independiente
# ========================================
"""
Módulo para debugging visual en Streamlit.
Uso:
    1. Importar: from debug_panel import DebugPanel
    2. Inicializar: debug = DebugPanel()
    3. Loggear pasos: debug.log("paso", data)
    4. Mostrar panel: debug.render()
"""

import streamlit as st
import pandas as pd
import datetime
import json
import traceback


class DebugPanel:
    """Panel de debugging visual para Streamlit"""
    
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
    
    def clear(self):
        """Limpia todos los logs"""
        st.session_state[self.session_key] = []
    
    def render(self):
        """Renderiza el panel de debug completo"""
        st.markdown("### 🔬 Panel de Debug - Flujo Completo")
        st.markdown("Visualiza todo el flujo de interpretación y ejecución en tiempo real.")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption("Se registran todos los pasos desde que ingresás una consulta hasta que se renderiza el resultado")
        with col2:
            if st.button("🗑️ Limpiar debug", key="clear_debug_btn"):
                self.clear()
                st.rerun()
        
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
            - 🔀 Router usado
            - 💾 SQL ejecutado
            - 📊 DataFrame resultado
            - 🎨 Función de renderizado
            - ❌ Errores (si los hay)
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
    
    st.title("Demo del Panel de Debug")
    
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
            debug.log("💾 SQL Ejecutado", """
                SELECT Proveedor, SUM(Total) AS Total
                FROM chatbot_raw
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
        
        if st.button("Simular error"):
            debug.log("📝 Input Usuario", "compras xyz")
            debug.log("🧠 Interpretación", {"tipo": "no_entendido"})
            debug.log("❌ Error", "No se pudo interpretar la consulta")
            st.error("¡Error simulado! Ve a la pestaña Debug")
    
    with tab2:
        debug.render()
