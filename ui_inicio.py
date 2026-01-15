# =========================
# UI_INICIO.PY - ROUTER AUTOMÁTICO (DETECTA DESKTOP/MOBILE)
# =========================

import streamlit as st
from ui_inicio_desktop import mostrar_inicio_desktop
from ui_inicio_mobile import mostrar_inicio_mobile


def detectar_dispositivo():
    """
    Detecta si el usuario está en mobile o desktop.
    
    Métodos de detección (en orden de prioridad):
    1. Selector manual del sidebar (si el usuario lo cambió)
    2. Session_state si ya lo detectaste antes
    3. Viewport_width si lo tenés guardado
    4. Por defecto: desktop
    
    Returns:
        bool: True si es mobile, False si es desktop
    """
    
    # Método 1: Si el usuario eligió manualmente en el sidebar
    if "selector_dispositivo_manual" in st.session_state:
        return st.session_state.get("is_mobile", False)
    
    # Método 2: Si ya detectaste antes (guardado en session_state)
    if "is_mobile" in st.session_state:
        return st.session_state["is_mobile"]
    
    # Método 3: Si tenés el ancho de viewport guardado
    if "viewport_width" in st.session_state:
        ancho = st.session_state["viewport_width"]
        return ancho < 768  # True si es mobile (< 768px)
    
    # Método 4: Default a desktop
    return False


def mostrar_inicio():
    """
    Función principal que decide qué versión mostrar.
    
    Esta es la función que se llama desde main.py cuando el usuario
    selecciona "🏠 Inicio" en el menú.
    
    Detecta automáticamente si el usuario está en mobile o desktop
    y llama a la versión correspondiente:
    - mostrar_inicio_mobile() para celulares
    - mostrar_inicio_desktop() para PC
    """
    
    # FORZAR MOBILE PARA QUE CAMBIEN LOS MENÚS (quitar después de probar)
    es_mobile = True
    
    # DEBUG (opcional - descomentar para ver qué versión se está mostrando)
    # with st.sidebar:
    #     st.caption(f"🔍 Versión: {'📱 Mobile' if es_mobile else '🖥️ Desktop'}")
    
    if es_mobile:
        # Mostrar versión mobile
        mostrar_inicio_mobile()
    else:
        # Mostrar versión desktop
        mostrar_inicio_desktop()
