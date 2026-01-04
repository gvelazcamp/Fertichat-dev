# =========================
# UTILS_OPENAI.PY - FUNCIONES OPENAI
# =========================

import os
import re
import json
from typing import Tuple, Optional
from datetime import datetime
import pandas as pd

from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL
from intent_detector import normalizar_texto
from sql_queries import ejecutar_consulta

# Cliente OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# =====================================================================
# OPENAI - RESPUESTAS CONVERSACIONALES
# =====================================================================

def es_saludo_o_conversacion(texto: str) -> bool:
    """Detecta si es un saludo o conversación casual (sin consulta de datos)"""
    texto_norm = normalizar_texto(texto)

    # Palabras que indican consulta de datos (NO es saludo si hay alguna de estas)
    palabras_consulta = [
        'compras', 'compra', 'compre', 'compramos', 'comprado',
        'comparar', 'comparame', 'compara', 'comparacion',
        'gastos', 'gasto', 'gastamos', 'gastado', 'gastar',
        'cuanto', 'cuanta', 'cuantos', 'cuantas',
        'proveedor', 'proveedores', 'articulo', 'articulos',
        'factura', 'facturas', 'familia', 'familias',
        'stock', 'lote', 'lotes', 'vencimiento', 'vencer',
        'total', 'detalle', 'ultima', 'ultimo', 'top', 'ranking',
        '2020', '2021', '2022', '2023', '2024', '2025', '2026',
        'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
        'ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'
    ]

    # Si hay palabras de consulta, NO es saludo (es una consulta con saludo incluido)
    for p in palabras_consulta:
        if p in texto_norm:
            print(f"🔍 es_saludo_o_conversacion: encontró '{p}' → NO es saludo")
            return False

    saludos = [
        'hola', 'buenos dias', 'buenas tardes', 'buenas noches',
        'hey', 'hi', 'hello', 'que tal', 'como estas', 'como andas',
        'gracias', 'muchas gracias', 'chau', 'adios', 'hasta luego',
        'buen dia', 'saludos'
    ]

    for saludo in saludos:
        if saludo in texto_norm:
            return True

    # Mensajes muy cortos sin palabras de datos
    if len(texto_norm.split()) <= 3:
        return True

    return False

def es_pregunta_conocimiento(texto: str) -> bool:
    """Detecta si es una pregunta de conocimiento general"""
    texto_norm = normalizar_texto(texto)

    patrones = [
        r'^que es\b',
        r'^que son\b',
        r'^como funciona\b',
        r'^para que sirve\b',
        r'^cual es\b',
        r'^cuales son\b',
        r'^explicame\b',
        r'^que significa\b',
        r'^definicion de\b',
    ]

    for patron in patrones:
        if re.search(patron, texto_norm):
            palabras_datos = ['compras', 'gastos', 'proveedor', 'articulo', 'factura', 'familia']
            if not any(p in texto_norm for p in palabras_datos):
                return True

    return False

def responder_con_openai(pregunta: str, tipo: str) -> str:
    """Responde con OpenAI (conversación o conocimiento)"""
    if tipo == "conversacion":
        system_msg = """Eres un asistente amigable de un sistema de análisis de compras de laboratorio.
Responde de forma natural, cálida y breve a saludos y conversación casual.
Menciona que estás aquí para ayudar con consultas de compras, gastos, proveedores y facturas.
Responde en español."""
        max_tok = 200
    else:
        system_msg = """Eres un asistente experto que trabaja en un laboratorio clínico.
Responde preguntas de conocimiento general de forma clara, precisa y útil.
Si la pregunta es sobre términos médicos, científicos o de laboratorio, explícalos bien.
Responde en español de forma concisa pero completa."""
        max_tok = 500

    try:
        if not OPENAI_API_KEY:
            return "⚠️ La API de OpenAI no está configurada. Configurá OPENAI_API_KEY en las variables de entorno."
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": pregunta}
            ],
            temperature=0.5,
            max_tokens=max_tok
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Error OpenAI: {e}")
        return f"⚠️ Error al conectar con OpenAI: {str(e)[:100]}"

def recomendar_como_preguntar(pregunta: str) -> str:
    system_prompt = """
Eres un Asistente Guía para un chatbot de laboratorio.
Tu tarea NO es devolver datos ni SQL.

Debes:
- Entender qué intenta preguntar el usuario
- Recomendar cómo formular la pregunta usando preguntas estándar del sistema
- Sugerir ejemplos claros y variantes humanas (errores de tipeo, abreviaturas)
- Si falta info, pedir solo UNA aclaración

Nunca devuelvas JSON.
Nunca devuelvas resultados.
Solo recomendaciones de cómo preguntar.

Usa frases como:
- "Probá con:"
- "También podés escribir:"
- "Una forma clara de preguntarlo es:"
"""

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pregunta}
            ],
            temperature=0.3,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "No pude ayudarte a reformular la pregunta."


def obtener_sugerencia_ejecutable(pregunta: str) -> dict:
    """
    ✅ VERSIÓN MEJORADA: Interpreta TODAS las variaciones de lenguaje natural
    """
    hoy = datetime.now()
    anio_actual = hoy.year
    meses_es = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    mes_actual_es = meses_es[hoy.month - 1]

    system_prompt = f"""Eres un intérprete experto para un chatbot de compras de laboratorio.
Tu tarea es entender CUALQUIER forma en que el usuario pregunte y traducirla al formato exacto que el sistema entiende.

IMPORTANTE: Responde SOLO en JSON válido, sin markdown.

CONTEXTO DE FECHA:
- Fecha actual: {hoy.strftime('%Y-%m-%d')}
- Mes actual: {mes_actual_es} {anio_actual}
- Si el usuario dice "este mes", "mes actual", "en el mes", usá SIEMPRE: {mes_actual_es} {anio_actual}

FORMATOS QUE EL SISTEMA ENTIENDE:

COMPRAS (todas estas variaciones son válidas):
✅ "compras {{proveedor}} {{año}}" → compras roche 2025
✅ "compras {{proveedor}} {{mes}} {{año}}" → compras roche noviembre 2025
✅ "detalle compras {{proveedor}} {{año}}" → detalle compras roche 2025
✅ "total compras {{mes}} {{año}}" → total compras noviembre 2025

VARIACIONES QUE DEBES ENTENDER Y TRADUCIR:
- "cuales fueron las compras a roche en noviembre 2025" → "compras roche noviembre 2025"
- "cuanto le compramos a roche en noviembre 2025" → "compras roche noviembre 2025"
- "mostrame las compras de roche noviembre 2025" → "compras roche noviembre 2025"
- "dame las compras a roche de noviembre 2025" → "compras roche noviembre 2025"
- "compras realizadas a roche en noviembre 2025" → "compras roche noviembre 2025"
- "que compramos a roche en noviembre 2025" → "compras roche noviembre 2025"
- "cuanto gastamos en roche noviembre 2025" → "compras roche noviembre 2025"

PALABRAS CLAVE QUE INDICAN "COMPRAS":
- "compras", "compré", "compramos", "comprado", "comprando"
- "cuanto le compramos", "cuanto compramos", "cuanto gastamos"
- "qué compramos", "que compras hicimos"
- "cuales fueron las compras"
- "mostrame las compras", "dame las compras"
- "compras realizadas a", "compras hechas a"

PREPOSICIONES QUE DEBES IGNORAR:
- "a", "de", "en", "del", "al", "para", "con"

COMPARACIONES:
✅ "comparar {{proveedor}} {{año1}} {{año2}}" → comparar roche 2023 2024
✅ "comparar {{proveedor}} {{mes}} {{año1}} vs {{mes}} {{año2}}" → comparar roche noviembre 2023 vs noviembre 2024
✅ "comparar gastos familias {{año1}} {{año2}}" → comparar gastos familias 2023 2024

FACTURAS:
✅ "última factura {{proveedor/artículo}}" → última factura vitek
✅ "detalle factura {{número}}" → detalle factura 275217

GASTOS:
✅ "gastos familias {{mes}} {{año}}" → gastos familias noviembre 2025
✅ "top proveedores {{mes}} {{año}}" → top proveedores noviembre 2025

ERRORES COMUNES QUE DEBES CORREGIR:
- "novimbre", "novienbre", "novimbr" → noviembre
- "setiembre", "septirmbre" → septiembre
- "oct", "nov", "dic" → octubre, noviembre, diciembre
- "ultima" → última
- "cuanto" → cuánto

EJEMPLOS REALES:
Usuario: "cuales fueron las compras a roche en noviembre 2025"
Respuesta: {{"entendido": "Querés ver las compras realizadas al proveedor ROCHE en noviembre 2025", "sugerencia": "compras roche noviembre 2025", "alternativas": ["detalle compras roche noviembre 2025", "total compras roche noviembre 2025"]}}

Usuario: "cuanto le compramos a biodiagnostico este mes"
Respuesta: {{"entendido": "Querés ver las compras a BIODIAGNOSTICO del mes actual", "sugerencia": "compras biodiagnostico {mes_actual_es} {anio_actual}", "alternativas": ["total compras biodiagnostico {mes_actual_es} {anio_actual}"]}}

Usuario: "compras roche 2025"
Respuesta: {{"entendido": "Querés ver todas las compras a ROCHE en 2025", "sugerencia": "compras roche 2025", "alternativas": ["detalle compras roche 2025", "comparar roche 2024 2025"]}}

RESPONDE SOLO JSON (sin ```json):
{{"entendido": "descripción clara", "sugerencia": "comando exacto", "alternativas": ["opción 1", "opción 2"]}}
"""

    try:
        print(f"🤖 Llamando a IA con: {pregunta}")
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pregunta}
            ],
            temperature=0.1,
            max_tokens=250,
            timeout=15
        )
        content = response.choices[0].message.content.strip()
        print(f"🤖 IA respondió: {content}")

        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)
        content = content.strip()

        resultado = json.loads(content)
        print(f"🤖 JSON parseado: {resultado}")
        return resultado

    except json.JSONDecodeError as e:
        print(f"❌ Error parseando JSON: {e}")
        print(f"❌ Contenido recibido: {content if 'content' in dir() else 'N/A'}")
        return {'entendido': '', 'sugerencia': '', 'alternativas': []}
    except Exception as e:
        print(f"❌ Error en obtener_sugerencia_ejecutable: {e}")
        return {'entendido': '', 'sugerencia': '', 'alternativas': []}



# =====================================================================
# OPENAI - FALLBACK SQL
# =====================================================================

def _extraer_json_de_texto(s: str) -> Optional[dict]:
    """Extrae JSON de respuesta de OpenAI"""
    if not s:
        return None
    s = s.strip()

    m = re.search(r"```json\s*(\{.*?\})\s*```", s, flags=re.DOTALL | re.IGNORECASE)
    if m:
        s = m.group(1).strip()

    m2 = re.search(r"```\s*(\{.*?\})\s*```", s, flags=re.DOTALL)
    if m2:
        s = m2.group(1).strip()

    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None
    return None

def _sql_es_seguro(sql: str) -> bool:
    """Verifica que el SQL sea solo SELECT y seguro"""
    if not sql:
        return False
    s = sql.strip().lower()

    if ";" in s:
        return False
    if not s.startswith("select"):
        return False
    if "from chatbot" not in s:
        return False

    bloqueos = [
        "insert ", "update ", "delete ", "drop ", "alter ", "create ",
        "truncate ", "grant ", "revoke ", "information_schema", "mysql.",
        "into outfile", "load_file(", "sleep(", "benchmark("
    ]
    for b in bloqueos:
        if b in s:
            return False

    return True

def fallback_openai_sql(pregunta: str, motivo: str) -> Tuple[Optional[str], Optional[pd.DataFrame], Optional[str]]:
    """
    ✅ FALLBACK MEJORADO: Genera SQL SIN LIMIT para traer datos completos
    """
    hoy = datetime.now()
    mes_actual = hoy.strftime('%Y-%m')

    schema_info = """
ESQUEMA DE LA BASE DE DATOS:
- Tabla: chatbot
- Columnas:
  * tipo_comprobante (texto) - Filtrar compras: tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%'
  * Proveedor (texto)
  * Familia (texto)
  * Tipo Articulo (texto)
  * Articulo (texto)
  * Mes (texto) - formato YYYY-MM
  * fecha (texto) - YYYY-MM-DD o DD/MM/YYYY
  * cantidad (texto) - número con coma decimal
  * Total (texto) - formato 78.160,33 (puntos miles, coma decimal)
  * N Factura (texto)

REGLAS:
1. SIEMPRE filtrar: (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%')
2. Para Total numérico: CAST(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(TRIM(Total), '.', ''), ',', '.'), '(', '-'), ')', ''), '$', '') AS DECIMAL(15,2))
3. Para Mes: TRIM(Mes) = 'YYYY-MM'
4. ✅ NO USES LIMIT - Trae TODOS los registros (el sistema limitará en UI si es necesario)
5. SOLO SELECT
"""

    system_prompt = f"""Eres un experto en SQL para MySQL. Convierte la pregunta a SQL.

{schema_info}

Fecha actual: {hoy.strftime('%Y-%m-%d')}, Mes actual: {mes_actual}

✅ IMPORTANTE: NO agregues LIMIT a las queries. El sistema necesita todos los datos para cálculos correctos.

Responde SOLO con JSON:
{{"sql": "SELECT ...", "titulo": "descripción corta", "respuesta": "explicación breve de qué hace"}}
"""

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Motivo: {motivo}\n\nPregunta: {pregunta}"}
            ],
            temperature=0.1,
            max_tokens=800
        )

        content = response.choices[0].message.content.strip()
        obj = _extraer_json_de_texto(content)

        if not obj:
            return None, None, None

        sql = str(obj.get("sql", "")).strip()
        titulo = str(obj.get("titulo", "Resultado")).strip()
        respuesta = str(obj.get("respuesta", "")).strip()

        # ✅ Remover LIMIT si OpenAI lo agregó
        sql = re.sub(r'\s+LIMIT\s+\d+\s*$', '', sql, flags=re.IGNORECASE)

        if not _sql_es_seguro(sql):
            return None, None, None

        df = ejecutar_consulta(sql)
        return titulo, df, respuesta

    except Exception as e:
        print(f"❌ Error en fallback_openai_sql: {e}")
        return None, None, None
