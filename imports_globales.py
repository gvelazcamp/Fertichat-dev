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

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    print("⚠️ streamlit-autorefresh no instalado")

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
