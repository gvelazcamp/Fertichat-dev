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

EJEMPLOS CRÍTICOS - TODAS LAS VARIACIONES:

=== SALUDOS ===
Usuario: "hola" / "hey" / "buenos días" / "buenas" / "hola!" / "que tal"
{{"tipo": "conversacion", "parametros": {{}}, "debug": "saludo"}}

Usuario: "gracias" / "muchas gracias" / "perfecto gracias" / "ok gracias"
{{"tipo": "conversacion", "parametros": {{}}, "debug": "agradecimiento"}}

Usuario: "chau" / "adios" / "hasta luego" / "nos vemos"
{{"tipo": "conversacion", "parametros": {{}}, "debug": "despedida"}}

=== CONOCIMIENTO ===
Usuario: "que es HPV" / "que es un hemograma" / "para que sirve la glucosa"
{{"tipo": "conocimiento", "parametros": {{}}, "debug": "pregunta de conocimiento"}}

=== COMPRAS AÑO (todas estas son iguales) ===
Usuario: "compras 2025"
Usuario: "que compramos en 2025"
Usuario: "mostrame las compras del 2025"
Usuario: "dame las compras de 2025"
Usuario: "listado de compras 2025"
Usuario: "todas las compras del año 2025"
{{"tipo": "compras_anio", "parametros": {{"anio": 2025}}, "debug": "todas las compras de 2025"}}

=== COMPRAS PROVEEDOR MES (todas estas son iguales) ===
Usuario: "que le compre a biodiagnostico en enero 2025"
Usuario: "compras biodiagnostico enero 2025"
Usuario: "cuanto le compramos a biodiagnostico en enero 2025"
Usuario: "mostrame las compras de biodiagnostico en enero 2025"
Usuario: "dame las compras a biodiagnostico enero 2025"
Usuario: "compras realizadas a biodiagnostico en enero del 2025"
Usuario: "cuanto gastamos en biodiagnostico enero 2025"
Usuario: "facturas de biodiagnostico enero 2025"
Usuario: "que pedimos a biodiagnostico en enero 2025"
{{"tipo": "compras_proveedor_mes", "parametros": {{"proveedor": "biodiagnostico", "mes": "2025-01"}}, "debug": "compras BIODIAGNOSTICO enero 2025"}}

=== COMPRAS PROVEEDOR AÑO (todas estas son iguales) ===
Usuario: "compras roche 2025"
Usuario: "que le compramos a roche en 2025"
Usuario: "cuanto gastamos en roche 2025"
Usuario: "mostrame las compras de roche del 2025"
Usuario: "facturas de roche en 2025"
Usuario: "pedidos a roche 2025"
{{"tipo": "compras_proveedor_anio", "parametros": {{"proveedor": "roche", "anio": 2025}}, "debug": "compras ROCHE 2025"}}

=== COMPRAS MES (todas estas son iguales) ===
Usuario: "compras enero 2025"
Usuario: "que compramos en enero 2025"
Usuario: "compras del mes de enero 2025"
Usuario: "mostrame las compras de enero 2025"
Usuario: "listado compras enero 2025"
{{"tipo": "compras_mes", "parametros": {{"mes": "2025-01"}}, "debug": "compras enero 2025"}}

=== ÚLTIMA FACTURA (todas estas son iguales) ===
Usuario: "ultima factura vitek"
Usuario: "cuando llego vitek"
Usuario: "cuando vino el ultimo vitek"
Usuario: "cual fue la ultima factura de vitek"
Usuario: "ultima vez que vino vitek"
Usuario: "ultimo pedido vitek"
{{"tipo": "ultima_factura", "parametros": {{"patron": "vitek"}}, "debug": "última factura VITEK"}}

=== FACTURAS ARTÍCULO (todas estas son iguales) ===
Usuario: "cuando vino vitek"
Usuario: "todas las facturas de vitek"
Usuario: "en que fechas llego vitek"
Usuario: "historial de vitek"
Usuario: "listado facturas vitek"
{{"tipo": "facturas_articulo", "parametros": {{"articulo": "vitek"}}, "debug": "todas las facturas VITEK"}}

=== COMPARAR PROVEEDOR MESES ===
Usuario: "comparar roche octubre noviembre 2025"
Usuario: "comparar roche octubre vs noviembre 2025"
Usuario: "diferencia roche octubre noviembre 2025"
{{"tipo": "comparar_proveedor_meses", "parametros": {{"proveedor": "roche", "mes1": "2025-10", "mes2": "2025-11"}}, "debug": "comparar ROCHE oct vs nov 2025"}}

=== COMPARAR PROVEEDOR AÑOS ===
Usuario: "comparar roche 2024 2025"
Usuario: "comparar roche 2024 vs 2025"
Usuario: "diferencia roche entre 2024 y 2025"
{{"tipo": "comparar_proveedor_anios", "parametros": {{"proveedor": "roche", "anios": [2024, 2025]}}, "debug": "comparar ROCHE 2024 vs 2025"}}

=== STOCK ===
Usuario: "stock vitek"
Usuario: "cuanto stock tenemos de vitek"
Usuario: "cuanto hay de vitek"
Usuario: "inventario vitek"
{{"tipo": "stock_articulo", "parametros": {{"articulo": "vitek"}}, "debug": "stock VITEK"}}

Usuario: "stock total"
Usuario: "cuanto stock tenemos"
Usuario: "resumen de stock"
Usuario: "inventario total"
{{"tipo": "stock_total", "parametros": {{}}, "debug": "stock total"}}

=== GASTOS ===
Usuario: "gastos familias enero 2026"
Usuario: "cuanto gastamos por familia en enero 2026"
Usuario: "gastos por seccion enero 2026"
{{"tipo": "gastos_familias_mes", "parametros": {{"mes": "2026-01"}}, "debug": "gastos familias enero 2026"}}

Usuario: "top proveedores 2025"
Usuario: "ranking proveedores 2025"
Usuario: "mayores proveedores 2025"
{{"tipo": "top_proveedores", "parametros": {{"anio": 2025}}, "debug": "top 10 proveedores 2025"}}

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

# =========================
        # NORMALIZACIÓN COMPARATIVAS (NO ROMPE NADA)
        # =========================

        texto = pregunta.lower()

        meses_map = {
            "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
            "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
            "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
        }

        # comparar proveedor mes vs mes año
        if "comparar" in texto:
            proveedor = resultado.get("parametros", {}).get("proveedor")

            meses_en_texto = [m for m in meses_map if m in texto]
            anio_match = re.search(r"(202\d)", texto)

            if proveedor and len(meses_en_texto) == 2 and anio_match:
                anio = anio_match.group(1)
                mes1 = f"{anio}-{meses_map[meses_en_texto[0]]}"
                mes2 = f"{anio}-{meses_map[meses_en_texto[1]]}"

                resultado = {
                    "tipo": "comparar_proveedor_meses",
                    "parametros": {
                        "proveedor": proveedor,
                        "mes1": mes1,
                        "mes2": mes2
                    },
                    "debug": f"comparativa forzada {proveedor} {mes1} vs {mes2}"
                }     
        # =========================
        # NORMALIZACIÓN EXTRA (NO ROMPE LO EXISTENTE)
        # =========================

        tipo = resultado.get("tipo")
        params = resultado.get("parametros", {})

        # Si hay proveedor + mes → SIEMPRE es compras_proveedor_mes
        if (
            tipo == "compras_proveedor_anio"
            and "proveedor" in params
            and "mes" in params
        ):
            resultado["tipo"] = "compras_proveedor_mes"
            # si viene anio separado, lo eliminamos (el SQL usa mes YYYY-MM)
            params.pop("anio", None)
            resultado["parametros"] = params
            resultado["debug"] = resultado.get("debug", "") + " | normalizado a proveedor_mes"

        # Si la IA devolvió mes como texto (enero 2025), intentar corregir
        if tipo == "compras_proveedor_mes" and isinstance(params.get("mes"), str):
            m = re.search(r'(202\d)[-/ ]?(0[1-9]|1[0-2])', params["mes"])
            if m:
                params["mes"] = f"{m.group(1)}-{m.group(2)}"
                resultado["parametros"] = params
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
    tipos_especiales = [
        "conversacion",
        "conocimiento",
        "no_entendido",
        "comparar_proveedor_meses",
        "comparar_proveedor_anios"
    ]
    return tipo in MAPEO_FUNCIONES or tipo in tipos_especiales
