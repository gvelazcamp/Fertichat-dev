"""
IMPORTS GLOBALES DE FERTICHAT
==============================
Importa TODAS las dependencias externas necesarias.
Usar: from imports_globales import *

Esto asegura que todas las librerías estén disponibles en todos los módulos.
"""

# ============ STREAMLIT ============
import streamlit as st
from streamlit import session_state

# ============ DATOS ============
import pandas as pd
import numpy as np

# ============ VISUALIZACIÓN ============
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ============ BASE DE DATOS ============
try:
    from supabase import create_client, Client
except ImportError:
    print("⚠️ Supabase no instalado")

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("⚠️ psycopg2 no instalado")

# ============ IA ============
try:
    from openai import OpenAI
    import openai
except ImportError:
    print("⚠️ OpenAI no instalado")

# ============ ARCHIVOS ============
try:
    import openpyxl
    from openpyxl import Workbook, load_workbook
except ImportError:
    print("⚠️ openpyxl no instalado")

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
except ImportError:
    print("⚠️ reportlab no instalado")

# ============ STREAMLIT COMPONENTS ============
try:
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
    from st_aggrid.shared import JsCode
except ImportError:
    print("⚠️ streamlit-aggrid no instalado")

# ============ AUTO-REFRESH CONFIGURACIÓN ============
AUTOREFRESH_HABILITADO = True  # ← Cambiar a False para desactivar en TODOS los menús
AUTOREFRESH_INTERVALO = 60000   # ← Intervalo en milisegundos (60000 = 1 minuto)

try:
    from streamlit_autorefresh import st_autorefresh
    
    def iniciar_autorefresh(intervalo_ms=None, key="autorefresh_global", solo_si_habilitado=True):
        """
        Inicia el autorefresh con configuración personalizada.
        
        Parámetros:
        - intervalo_ms: Intervalo en milisegundos (None = usa AUTOREFRESH_INTERVALO)
        - key: Clave única para el autorefresh
        - solo_si_habilitado: Si True, respeta la variable AUTOREFRESH_HABILITADO
        
        Retorna:
        - Contador de refrescos
        
        Ejemplos de uso:
        
        # Opción 1: Usar configuración global
        iniciar_autorefresh()
        
        # Opción 2: Personalizar intervalo para este menú
        iniciar_autorefresh(intervalo_ms=30000)  # 30 segundos
        
        # Opción 3: Forzar autorefresh aunque esté deshabilitado globalmente
        iniciar_autorefresh(solo_si_habilitado=False)
        """
        if solo_si_habilitado and not AUTOREFRESH_HABILITADO:
            return 0
        
        if intervalo_ms is None:
            intervalo_ms = AUTOREFRESH_INTERVALO
        
        return st_autorefresh(interval=intervalo_ms, key=key)
    
    # AUTOREFRESH AUTOMÁTICO GLOBAL
    # Si AUTOREFRESH_HABILITADO = True, se activará en todos los menús automáticamente
    if AUTOREFRESH_HABILITADO:
        _autorefresh_count = st_autorefresh(interval=AUTOREFRESH_INTERVALO, key="global_autorefresh")
    
except ImportError:
    print("⚠️ streamlit-autorefresh no instalado")
    
    def iniciar_autorefresh(intervalo_ms=None, key="autorefresh_global", solo_si_habilitado=True):
        """Función dummy cuando autorefresh no está instalado"""
        return 0

# ============ UTILIDADES ============
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, date
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

# ============ PYTHON ESTÁNDAR ============
import sys
import time
import warnings
from collections import defaultdict
import base64
import io

# Cargar variables de entorno
load_dotenv()

# Suprimir warnings molestos
warnings.filterwarnings('ignore')

print("✅ Imports globales cargados correctamente")
if AUTOREFRESH_HABILITADO:
    print(f"🔄 Autorefresh activado: {AUTOREFRESH_INTERVALO/1000}s")
else:
    print("⏸️  Autorefresh desactivado")

