# =========================
# IA INTERPRETADOR - NUEVO SISTEMA CENTRALIZADO
# =========================
# La IA interpreta la pregunta y devuelve:
# - tipo: nombre de la consulta
# - parametros: dict con los valores extraídos
# - Si no entiende: sugerencia para el usuario
# =========================

import os
import re
import json
from typing import Dict, Optional, Tuple
from datetime import datetime
from openai import OpenAI

# =====================================================================
# CONFIGURACIÓN
# =====================================================================

try:
    from config_runtime import get_secret
    OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
except:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

try:
    from config import OPENAI_MODEL
except:
    OPENAI_MODEL = "gpt-4o-mini"

client = OpenAI(api_key=OPENAI_API_KEY)


# =====================================================================
# TABLA DE TIPOS - BASADA EN sql_queries.py
# =====================================================================
# Esta tabla define TODOS los tipos de consulta que el sistema soporta
# La IA debe devolver uno de estos tipos con sus parámetros

TABLA_TIPOS = """
| TIPO | DESCRIPCIÓN | PARÁMETROS | EJEMPLOS DE USUARIO |
|------|-------------|------------|---------------------|
| compras_anio | Todas las compras de un año (sin filtro) | anio | "compras 2025", "mostrame las compras del 2024", "que compramos en 2025" |
| compras_proveedor_mes | Compras de un proveedor en un mes | proveedor, mes (YYYY-MM) | "compras roche enero 2026", "cuanto le compramos a biodiagnostico en diciembre 2025" |
| compras_proveedor_anio | Compras de un proveedor en un año | proveedor, anio | "compras roche 2025", "que le compramos a wiener en 2024" |
| compras_articulo_mes | Compras de un artículo en un mes | articulo, mes (YYYY-MM) | "compras vitek noviembre 2025", "cuanto compramos de glucosa en enero 2026" |
| compras_articulo_anio | Compras de un artículo en un año | articulo, anio | "compras vitek 2025", "que compramos de hemoglobina en 2024" |
| compras_mes | Todas las compras de un mes | mes (YYYY-MM) | "compras de enero 2026", "listado compras diciembre 2025" |
| ultima_factura | Última factura de un artículo o proveedor | patron | "ultimo vitek", "cuando vino ultimo roche", "ultima factura de glucosa", "cuando llego ultimo hemograma" |
| facturas_articulo | Todas las facturas de un artículo | articulo | "cuando vino vitek", "facturas de glucosa", "en que fechas llego roche" |
| detalle_factura | Detalle de una factura por número | nro_factura | "factura 275217", "detalle factura A0275217", "ver factura 123456" |
| comparar_proveedor_meses | Comparar proveedor entre 2 meses | proveedor, mes1 (YYYY-MM), mes2 (YYYY-MM) | "comparar roche octubre noviembre 2025", "comparar biodiagnostico enero febrero 2026" |
| comparar_proveedor_anios | Comparar proveedor entre 2+ años | proveedor, anios[] | "comparar roche 2024 2025", "comparar wiener 2023 2024 2025" |
| comparar_articulo_meses | Comparar artículo entre 2 meses | articulo, mes1 (YYYY-MM), mes2 (YYYY-MM) | "comparar vitek octubre noviembre 2025" |
| comparar_articulo_anios | Comparar artículo entre 2+ años | articulo, anios[] | "comparar vitek 2024 2025", "comparar glucosa 2023 2024" |
| comparar_familia_meses | Comparar familias entre 2 meses | mes1 (YYYY-MM), mes2 (YYYY-MM), moneda? | "comparar gastos familias octubre noviembre 2025", "comparar familias enero febrero 2026" |
| comparar_familia_anios | Comparar familias entre 2+ años | anios[], moneda? | "comparar familias 2024 2025", "comparar gastos familias 2023 2024" |
| gastos_familias_mes | Gastos por familia en un mes | mes (YYYY-MM) | "gastos familias enero 2026", "cuanto gastamos por familia en diciembre 2025" |
| gastos_familias_anio | Gastos por familia en un año | anio | "gastos familias 2025", "gastos por seccion 2024" |
| gastos_secciones | Gastos de familias específicas | familias[], mes (YYYY-MM) | "gastos secciones G FB enero 2026", "gastos familia ID diciembre 2025" |
| top_proveedores | Top 10 proveedores | anio?, mes?, moneda? | "top proveedores 2025", "ranking proveedores enero 2026", "mayores proveedores en dolares 2025" |
| stock_total | Resumen total de stock | (ninguno) | "stock total", "resumen de stock", "cuanto stock tenemos" |
| stock_articulo | Stock de un artículo | articulo | "stock vitek", "cuanto hay de glucosa", "stock de hemoglobina" |
| stock_familia | Stock de una familia/sección | familia | "stock familia ID", "stock seccion G" |
| stock_por_familia | Stock agrupado por familias | (ninguno) | "stock por familia", "stock por seccion" |
| stock_por_deposito | Stock agrupado por depósito | (ninguno) | "stock por deposito", "stock por ubicacion" |
| stock_lotes_vencer | Lotes próximos a vencer | dias? (default 90) | "lotes por vencer", "que vence pronto", "proximos a vencer" |
| stock_lotes_vencidos | Lotes ya vencidos | (ninguno) | "lotes vencidos", "que ya vencio" |
| stock_bajo | Artículos con stock bajo | minimo? (default 10) | "stock bajo", "que hay poco", "articulos con poco stock" |
| stock_lote | Buscar un lote específico | lote | "lote ABC123", "buscar lote XYZ" |
| conversacion | Saludos y charla casual | (ninguno) | "hola", "gracias", "chau", "como estas" |
| conocimiento | Preguntas de conocimiento general | (ninguno) | "que es un hemograma", "para que sirve la glucosa" |
| no_entendido | Cuando no se entiende la pregunta | sugerencia | (cualquier cosa ambigua) |
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
    
    return f"""Eres un intérprete experto para un chatbot de compras y stock de laboratorio.
Tu ÚNICA tarea es analizar lo que el usuario pregunta y devolver un JSON con el TIPO de consulta y los PARÁMETROS.

FECHA ACTUAL: {hoy.strftime('%Y-%m-%d')}
MES ACTUAL: {mes_nombre} {anio_actual} (formato: {mes_actual})
AÑO ACTUAL: {anio_actual}

REGLAS DE INTERPRETACIÓN:
1. "este mes" = {mes_actual}
2. "este año" = {anio_actual}
3. "mes pasado" = calcular el mes anterior
4. Los meses SIEMPRE en formato YYYY-MM (ej: 2025-11 para noviembre 2025)
5. Si dice un mes sin año, asumir {anio_actual}
6. Corregir errores de tipeo: "novimbre"→"noviembre", "setiembre"→"septiembre"
7. Si dice "ultimo X" o "cuando vino ultimo X" → tipo: ultima_factura
8. Si dice "cuando vino X" (SIN ultimo) → tipo: facturas_articulo (todas las facturas)

TABLA DE TIPOS DISPONIBLES:
{TABLA_TIPOS}

FORMATO DE RESPUESTA (SOLO JSON, sin markdown):

Si ENTENDISTE la pregunta:
{{
  "tipo": "nombre_del_tipo",
  "parametros": {{...}},
  "debug": "explicación corta de lo que entendiste"
}}

Si NO ENTENDISTE o es AMBIGUO:
{{
  "tipo": "no_entendido",
  "parametros": {{}},
  "sugerencia": "¿Quisiste decir: compras roche enero 2026?",
  "alternativas": ["compras roche 2025", "compras enero 2026"],
  "debug": "No pude identificar el proveedor/artículo"
}}

EJEMPLOS:

Usuario: "cuales fueron las compras de roche este mes"
Respuesta: {{"tipo": "compras_proveedor_mes", "parametros": {{"proveedor": "roche", "mes": "{mes_actual}"}}, "debug": "compras de ROCHE en {mes_nombre} {anio_actual}"}}

Usuario: "compras 2025"
Respuesta: {{"tipo": "compras_anio", "parametros": {{"anio": 2025}}, "debug": "todas las compras de 2025"}}

Usuario: "comparar roche octubre noviembre 2025"
Respuesta: {{"tipo": "comparar_proveedor_meses", "parametros": {{"proveedor": "roche", "mes1": "2025-10", "mes2": "2025-11"}}, "debug": "comparar ROCHE octubre vs noviembre 2025"}}

Usuario: "ultimo vitek"
Respuesta: {{"tipo": "ultima_factura", "parametros": {{"patron": "vitek"}}, "debug": "última factura de VITEK"}}

Usuario: "cuando vino vitek"
Respuesta: {{"tipo": "facturas_articulo", "parametros": {{"articulo": "vitek"}}, "debug": "todas las facturas de VITEK"}}

Usuario: "cuando vino ultimo vitek"
Respuesta: {{"tipo": "ultima_factura", "parametros": {{"patron": "vitek"}}, "debug": "última factura de VITEK"}}

Usuario: "cuanto gastamos"
Respuesta: {{"tipo": "no_entendido", "parametros": {{}}, "sugerencia": "¿Quisiste decir: cuanto gastamos en {mes_nombre} {anio_actual}?", "alternativas": ["gastos familias {mes_actual}", "compras {anio_actual}"], "debug": "falta especificar período"}}

Usuario: "stock vitek"
Respuesta: {{"tipo": "stock_articulo", "parametros": {{"articulo": "vitek"}}, "debug": "stock de VITEK"}}

Usuario: "hola"
Respuesta: {{"tipo": "conversacion", "parametros": {{}}, "debug": "saludo"}}

IMPORTANTE:
- Responde SOLO con JSON válido
- NO uses ```json ni ningún markdown
- Si hay duda, usa "no_entendido" con sugerencia útil
"""


# =====================================================================
# FUNCIÓN PRINCIPAL DE INTERPRETACIÓN
# =====================================================================

def interpretar_pregunta(pregunta: str) -> Dict:
    """
    Interpreta la pregunta del usuario usando OpenAI.
    
    Retorna:
    {
        "tipo": "nombre_del_tipo",
        "parametros": {...},
        "debug": "explicación",
        "sugerencia": "..." (solo si no_entendido),
        "alternativas": [...] (solo si no_entendido)
    }
    """
    
    if not pregunta or not pregunta.strip():
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "Por favor, escribí tu consulta.",
            "alternativas": [],
            "debug": "pregunta vacía"
        }
    
    if not OPENAI_API_KEY:
        # Fallback básico si no hay API key
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
        
        # Validar que tenga los campos mínimos
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
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "No pude entender tu pregunta. ¿Podrías reformularla?",
            "alternativas": _generar_alternativas_genericas(),
            "debug": f"error JSON: {str(e)[:50]}"
        }
    except Exception as e:
        print(f"❌ Error en interpretar_pregunta: {e}")
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "Hubo un error procesando tu pregunta.",
            "alternativas": _generar_alternativas_genericas(),
            "debug": f"error: {str(e)[:50]}"
        }


def _generar_alternativas_genericas() -> list:
    """Genera alternativas genéricas basadas en la fecha actual"""
    hoy = datetime.now()
    mes_actual = hoy.strftime('%Y-%m')
    anio_actual = hoy.year
    
    return [
        f"compras {anio_actual}",
        f"gastos familias {mes_actual}",
        f"top proveedores {anio_actual}",
        "stock total"
    ]


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
        "alternativas": ["compras 2025", "stock total"],
        "debug": "fallback básico"
    }


# =====================================================================
# MAPEO TIPO → FUNCIÓN SQL
# =====================================================================

# Este diccionario mapea cada tipo a la función de sql_queries.py que debe llamarse
MAPEO_FUNCIONES = {
    # COMPRAS
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
    "compras_articulo_mes": {
        "funcion": "get_detalle_compras_articulo_mes",
        "params": ["articulo", "mes"]
    },
    "compras_articulo_anio": {
        "funcion": "get_detalle_compras_articulo_anio",
        "params": ["articulo", "anio"],
        "resumen": "get_total_compras_articulo_anio"
    },
    "compras_mes": {
        "funcion": "get_compras_por_mes_excel",
        "params": ["mes"]
    },
    
    # FACTURAS
    "ultima_factura": {
        "funcion": "get_ultima_factura_inteligente",
        "params": ["patron"]
    },
    "facturas_articulo": {
        "funcion": "get_facturas_de_articulo",
        "params": ["articulo"]
    },
    "detalle_factura": {
        "funcion": "get_detalle_factura_por_numero",
        "params": ["nro_factura"]
    },
    
    # COMPARACIONES
    "comparar_proveedor_meses": {
        "funcion": "get_comparacion_proveedor_meses",
        "params": ["mes1", "mes2", "proveedor"]
    },
    "comparar_proveedor_anios": {
        "funcion": "get_comparacion_proveedor_anios_monedas",
        "params": ["anios", "proveedor"]
    },
    "comparar_articulo_meses": {
        "funcion": "get_comparacion_articulo_meses",
        "params": ["mes1", "mes2", "articulo"]
    },
    "comparar_articulo_anios": {
        "funcion": "get_comparacion_articulo_anios",
        "params": ["anios", "articulo"]
    },
    "comparar_familia_meses": {
        "funcion": "get_comparacion_familia_meses_moneda",
        "params": ["mes1", "mes2", "moneda"]
    },
    "comparar_familia_anios": {
        "funcion": "get_comparacion_familia_anios_monedas",
        "params": ["anios"]
    },
    
    # GASTOS
    "gastos_familias_mes": {
        "funcion": "get_gastos_todas_familias_mes",
        "params": ["mes"]
    },
    "gastos_familias_anio": {
        "funcion": "get_gastos_todas_familias_anio",
        "params": ["anio"]
    },
    "gastos_secciones": {
        "funcion": "get_gastos_secciones_detalle_completo",
        "params": ["familias", "mes"]
    },
    
    # TOP
    "top_proveedores": {
        "funcion": "get_top_10_proveedores_chatbot",
        "params": ["moneda", "anio", "mes"]
    },
    
    # STOCK
    "stock_total": {
        "funcion": "get_stock_total",
        "params": []
    },
    "stock_articulo": {
        "funcion": "get_stock_articulo",
        "params": ["articulo"]
    },
    "stock_familia": {
        "funcion": "get_stock_familia",
        "params": ["familia"]
    },
    "stock_por_familia": {
        "funcion": "get_stock_por_familia",
        "params": []
    },
    "stock_por_deposito": {
        "funcion": "get_stock_por_deposito",
        "params": []
    },
    "stock_lotes_vencer": {
        "funcion": "get_lotes_por_vencer",
        "params": ["dias"]
    },
    "stock_lotes_vencidos": {
        "funcion": "get_lotes_vencidos",
        "params": []
    },
    "stock_bajo": {
        "funcion": "get_stock_bajo",
        "params": ["minimo"]
    },
    "stock_lote": {
        "funcion": "get_stock_lote_especifico",
        "params": ["lote"]
    },
}


# =====================================================================
# FUNCIÓN PARA OBTENER INFO DEL MAPEO
# =====================================================================

def obtener_info_tipo(tipo: str) -> Optional[Dict]:
    """Obtiene la información de mapeo para un tipo"""
    return MAPEO_FUNCIONES.get(tipo)


def es_tipo_valido(tipo: str) -> bool:
    """Verifica si un tipo es válido"""
    tipos_especiales = ["conversacion", "conocimiento", "no_entendido"]
    return tipo in MAPEO_FUNCIONES or tipo in tipos_especiales


# =====================================================================
# TEST
# =====================================================================

if __name__ == "__main__":
    # Pruebas
    pruebas = [
        "compras roche enero 2026",
        "cuales fueron las compras de biodiagnostico este mes",
        "comparar roche octubre noviembre 2025",
        "ultimo vitek",
        "cuando vino vitek",
        "cuando vino ultimo vitek",
        "cuanto gastamos",
        "stock vitek",
        "hola",
        "compras 2025"
    ]
    
    print("=" * 60)
    print("PRUEBAS DEL INTERPRETADOR")
    print("=" * 60)
    
    for p in pruebas:
        print(f"\n📝 Pregunta: {p}")
        resultado = interpretar_pregunta(p)
        print(f"   Tipo: {resultado.get('tipo')}")
        print(f"   Params: {resultado.get('parametros')}")
        if resultado.get('sugerencia'):
            print(f"   Sugerencia: {resultado.get('sugerencia')}")
        print(f"   Debug: {resultado.get('debug')}")
