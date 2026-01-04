# =========================
# IA_INTERPRETADOR.PY - VERSIÓN MEJORADA
# =========================

import os
import re
import json
from typing import Dict, Optional
from datetime import datetime

import streamlit as st
from openai import OpenAI
from config import OPENAI_MODEL

# =====================================================================
# CONFIGURACIÓN
# =====================================================================

OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
client = OpenAI(api_key=OPENAI_API_KEY)


# =====================================================================
# TABLA DE TIPOS
# =====================================================================

TABLA_TIPOS = """
| TIPO | DESCRIPCIÓN | PARÁMETROS | EJEMPLOS |
|------|-------------|------------|----------|
| compras_anio | Todas las compras de un año | anio | "compras 2025", "que compramos en 2025" |
| compras_proveedor_mes | Compras de un proveedor en un mes | proveedor, mes (YYYY-MM) | "compras roche enero 2025", "que le compramos a biodiagnostico en enero 2025" |
| compras_proveedor_anio | Compras de un proveedor en un año | proveedor, anio | "compras roche 2025" |
| compras_mes | Todas las compras de un mes | mes (YYYY-MM) | "compras enero 2025" |
| ultima_factura | Última factura de un artículo/proveedor | patron | "ultima factura vitek" |
| facturas_articulo | Todas las facturas de un artículo | articulo | "cuando vino vitek" |
| stock_total | Resumen total de stock | (ninguno) | "stock total" |
| stock_articulo | Stock de un artículo | articulo | "stock vitek" |
| conversacion | Saludos y charla casual | (ninguno) | "hola", "gracias", "buenos días" |
| conocimiento | Preguntas de conocimiento general | (ninguno) | "que es HPV", "para que sirve" |
| no_entendido | No se entiende | sugerencia | (ambiguo) |
"""


# =====================================================================
# PROMPT DEL SISTEMA
# =====================================================================

def _get_system_prompt() -> str:
    hoy = datetime.now()
    mes_actual = hoy.strftime('%Y-%m')
    anio_actual = hoy.year
    
    meses_nombres = {
        1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
        5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
        9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
    }
    mes_nombre = meses_nombres[hoy.month]
    
    return f"""Eres un intérprete EXPERTO en lenguaje natural para un chatbot de laboratorio.

FECHA ACTUAL: {hoy.strftime('%Y-%m-%d')}
MES ACTUAL: {mes_nombre} {anio_actual} (formato: {mes_actual})
AÑO ACTUAL: {anio_actual}

TU TAREA:
Analizar la pregunta del usuario y devolver JSON con el TIPO y PARÁMETROS.

REGLAS CRÍTICAS:
1. "este mes" → {mes_actual}
2. "enero 2025" → 2025-01
3. Ignorar palabras: "a", "de", "en", "del", "le", "los", "las", "que", "cual", "cuanto"
4. SIEMPRE extraer el proveedor/artículo sin las palabras de relleno

DETECCIÓN DE SALUDOS (tipo: "conversacion"):
- "hola", "buenos días", "buenas tardes", "hey", "gracias", "chau"
- Si SOLO es saludo SIN pedir datos → tipo: "conversacion"

DETECCIÓN DE CONOCIMIENTO (tipo: "conocimiento"):
- "que es X", "para que sirve X", "como funciona X"
- Si NO menciona compras/stock/proveedores → tipo: "conocimiento"

EJEMPLOS CRÍTICOS:

Usuario: "hola"
{{"tipo": "conversacion", "parametros": {{}}, "debug": "saludo simple"}}

Usuario: "que es HPV"
{{"tipo": "conocimiento", "parametros": {{}}, "debug": "pregunta de conocimiento médico"}}

Usuario: "buenos días"
{{"tipo": "conversacion", "parametros": {{}}, "debug": "saludo"}}

Usuario: "compras 2025"
{{"tipo": "compras_anio", "parametros": {{"anio": 2025}}, "debug": "todas las compras de 2025"}}

Usuario: "que le compre a biodiagnostico en enero 2025"
{{"tipo": "compras_proveedor_mes", "parametros": {{"proveedor": "biodiagnostico", "mes": "2025-01"}}, "debug": "compras BIODIAGNOSTICO enero 2025"}}

Usuario: "cuanto le compramos a roche este mes"
{{"tipo": "compras_proveedor_mes", "parametros": {{"proveedor": "roche", "mes": "{mes_actual}"}}, "debug": "compras ROCHE {mes_nombre} {anio_actual}"}}

Usuario: "compras roche noviembre 2025"
{{"tipo": "compras_proveedor_mes", "parametros": {{"proveedor": "roche", "mes": "2025-11"}}, "debug": "compras ROCHE noviembre 2025"}}

Usuario: "stock vitek"
{{"tipo": "stock_articulo", "parametros": {{"articulo": "vitek"}}, "debug": "stock de VITEK"}}

Usuario: "ultima factura roche"
{{"tipo": "ultima_factura", "parametros": {{"patron": "roche"}}, "debug": "última factura ROCHE"}}

IMPORTANTE:
- Responde SOLO JSON válido
- NO uses ```json ni markdown
- Extrae nombres LIMPIOS (sin "a", "de", "en", "le")
- Si dudas, usa "no_entendido"

TABLA DE TIPOS:
{TABLA_TIPOS}
"""


# =====================================================================
# FUNCIÓN PRINCIPAL DE INTERPRETACIÓN
# =====================================================================

def interpretar_pregunta(pregunta: str) -> Dict:
    """
    Interpreta la pregunta del usuario usando OpenAI
    """
    
    if not pregunta or not pregunta.strip():
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "Por favor, escribí tu consulta.",
            "debug": "pregunta vacía"
        }
    
    # DETECCIÓN RÁPIDA DE SALUDOS (antes de llamar a OpenAI)
    texto_lower = pregunta.lower().strip()
    saludos_simples = [
        'hola', 'hey', 'buenos dias', 'buenas tardes', 'buenas noches',
        'buen dia', 'hola!', 'hey!', 'hi', 'hello'
    ]
    
    # Si es SOLO un saludo (sin otras palabras importantes)
    if texto_lower in saludos_simples:
        return {
            "tipo": "conversacion",
            "parametros": {},
            "debug": f"saludo detectado: {texto_lower}"
        }
    
    # Si empieza con saludo pero tiene más texto, seguir procesando
    palabras_datos = ['compra', 'stock', 'factura', 'proveedor', 'gasto', 'familia', 'comparar']
    tiene_datos = any(palabra in texto_lower for palabra in palabras_datos)
    
    if not tiene_datos and any(saludo in texto_lower for saludo in ['hola', 'gracias', 'chau', 'adios']):
        return {
            "tipo": "conversacion",
            "parametros": {},
            "debug": "conversación casual"
        }
    
    if not OPENAI_API_KEY:
        return _fallback_basico(pregunta)
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _get_system_prompt()},
                {"role": "user", "content": pregunta}
            ],
            temperature=0.1,
            max_tokens=500,
            timeout=15
        )
        
        content = response.choices[0].message.content.strip()
        
        # Limpiar respuesta
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)
        content = content.strip()
        
        resultado = json.loads(content)
        
        if "tipo" not in resultado:
            resultado["tipo"] = "no_entendido"
        if "parametros" not in resultado:
            resultado["parametros"] = {}
        if "debug" not in resultado:
            resultado["debug"] = ""
            
        print(f"🤖 IA interpretó: {resultado}")
        return resultado
        
    except json.JSONDecodeError as e:
        print(f"❌ Error parseando JSON: {e}")
        print(f"❌ Contenido recibido: {content if 'content' in locals() else 'N/A'}")
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "No pude entender tu pregunta. ¿Podrías reformularla?",
            "debug": f"error JSON: {str(e)[:50]}"
        }
    except Exception as e:
        print(f"❌ Error en interpretar_pregunta: {e}")
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "Hubo un error procesando tu pregunta.",
            "debug": f"error: {str(e)[:50]}"
        }


def _fallback_basico(pregunta: str) -> Dict:
    """Fallback muy básico sin IA"""
    texto = pregunta.lower().strip()
    
    # Saludos
    if any(s in texto for s in ['hola', 'buenos', 'gracias', 'chau']):
        return {"tipo": "conversacion", "parametros": {}, "debug": "saludo detectado"}
    
    # Stock
    if 'stock' in texto:
        return {"tipo": "stock_total", "parametros": {}, "debug": "fallback stock"}
    
    # Compras
    if 'compra' in texto:
        anio = re.search(r'(202\d)', texto)
        if anio:
            return {"tipo": "compras_anio", "parametros": {"anio": int(anio.group(1))}, "debug": "fallback compras año"}
    
    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "No pude entender. Probá con: compras 2025",
        "debug": "fallback básico"
    }


# =====================================================================
# MAPEO TIPO → FUNCIÓN SQL
# =====================================================================

MAPEO_FUNCIONES = {
    "compras_anio": {
        "funcion": "get_compras_anio",
        "params": ["anio"],
        "resumen": "get_total_compras_anio"
    },
    "compras_proveedor_mes": {
        "funcion": "get_detalle_compras_proveedor_mes",
        "params": ["proveedor", "mes"]
    },
    "compras_proveedor_anio": {
        "funcion": "get_detalle_compras_proveedor_anio",
        "params": ["proveedor", "anio"],
        "resumen": "get_total_compras_proveedor_anio"
    },
    "compras_mes": {
        "funcion": "get_compras_por_mes_excel",
        "params": ["mes"]
    },
    "ultima_factura": {
        "funcion": "get_ultima_factura_inteligente",
        "params": ["patron"]
    },
    "facturas_articulo": {
        "funcion": "get_facturas_de_articulo",
        "params": ["articulo"]
    },
    "stock_total": {
        "funcion": "get_stock_total",
        "params": []
    },
    "stock_articulo": {
        "funcion": "get_stock_articulo",
        "params": ["articulo"]
    },
}


def obtener_info_tipo(tipo: str) -> Optional[Dict]:
    """Obtiene la información de mapeo para un tipo"""
    return MAPEO_FUNCIONES.get(tipo)


def es_tipo_valido(tipo: str) -> bool:
    """Verifica si un tipo es válido"""
    tipos_especiales = ["conversacion", "conocimiento", "no_entendido"]
    return tipo in MAPEO_FUNCIONES or tipo in tipos_especiales
