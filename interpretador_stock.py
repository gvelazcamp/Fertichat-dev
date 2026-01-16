# interpretador_stock.py
"""
Interpretador dedicado SOLO para preguntas de stock
Carga familias dinámicamente desde Supabase
"""

import re
import streamlit as st
from typing import Dict, List, Optional

# =====================================================================
# CARGA DINÁMICA DE FAMILIAS
# =====================================================================
@st.cache_data(ttl=60 * 60)
def _cargar_familias_stock() -> List[str]:
    """Carga las familias desde la tabla stock"""
    try:
        from supabase_client import supabase
        if supabase is None:
            return []
        
        # Ejecutar el SQL que me pasaste
        query = """
        SELECT DISTINCT
            TRIM("FAMILIA") AS familia
        FROM public.stock
        WHERE "FAMILIA" IS NOT NULL
          AND TRIM("FAMILIA") <> ''
          AND UPPER(TRIM("FAMILIA")) <> 'SIN FAMILIA'
        ORDER BY familia
        """
        
        result = supabase.rpc('exec_sql', {'query': query}).execute()
        
        if result.data:
            familias = [row['familia'] for row in result.data if row.get('familia')]
            return familias
        
        return []
    
    except Exception as e:
        print(f"❌ Error cargando familias: {e}")
        # Fallback a lista mínima
        return ["AF", "BE", "CM", "FB", "G", "HT", "ID", "MY", "TEST", "TR", "XX"]


def _normalizar_texto(texto: str) -> str:
    """Normaliza texto para comparación"""
    return texto.lower().strip()


# =====================================================================
# FUNCIÓN PRINCIPAL
# =====================================================================
def interpretar_pregunta_stock(pregunta: str) -> Dict:
    """
    Interpreta preguntas de stock y devuelve tipo + parámetros
    
    Returns:
        {"tipo": "stock_familia", "parametros": {"familia": "ID"}}
        {"tipo": "stock_articulo", "parametros": {"articulo": "vitek"}}
        {"tipo": "no_stock", "parametros": {}}
    """
    if not pregunta or not isinstance(pregunta, str):
        return {"tipo": "no_entendido", "parametros": {}}
    
    texto = pregunta.lower().strip()
    
    # Verificar si es pregunta de stock
    if not _es_pregunta_stock(texto):
        return {"tipo": "no_stock", "parametros": {}}
    
    # ===== STOCK DE FAMILIA ESPECÍFICA =====
    familia = _extraer_familia(texto)
    if familia:
        return {
            "tipo": "stock_familia",
            "parametros": {"familia": familia}
        }
    
    # ===== STOCK POR FAMILIA (RESUMEN) =====
    if re.search(r"\bpor\s+familia", texto):
        return {
            "tipo": "stock_por_familia_resumen",
            "parametros": {}
        }
    
    # ===== STOCK POR DEPÓSITO (RESUMEN) =====
    if re.search(r"\bpor\s+dep[oó]sito", texto):
        return {
            "tipo": "stock_por_deposito_resumen",
            "parametros": {}
        }
    
    # ===== STOCK TOTAL =====
    if re.search(r"\bstock\s+total\b", texto) or re.search(r"\bcu[aá]nto\s+stock", texto):
        return {
            "tipo": "stock_total",
            "parametros": {}
        }
    
    # ===== VENCIMIENTOS =====
    if _es_pregunta_vencimiento(texto):
        dias = _extraer_dias(texto)
        return {
            "tipo": "vencimientos",
            "parametros": {"dias": dias}
        }
    
    # ===== STOCK BAJO =====
    if _es_pregunta_stock_bajo(texto):
        return {
            "tipo": "stock_bajo",
            "parametros": {}
        }
    
    # ===== STOCK DE ARTÍCULO (fallback) =====
    articulo = _extraer_articulo(texto)
    if articulo:
        return {
            "tipo": "stock_articulo",
            "parametros": {"articulo": articulo}
        }
    
    return {"tipo": "no_entendido", "parametros": {}}


# =====================================================================
# HELPERS
# =====================================================================

def _es_pregunta_stock(texto: str) -> bool:
    """Detecta si es una pregunta relacionada con stock"""
    keywords = [
        r"\bstock\b",
        r"\binventario\b",
        r"\blote[s]?\b",
        r"\bvenc(e|imiento)",
        r"\bcu[aá]nto\s+(hay|tengo)",
        r"\bd[oó]nde\s+est[aá]",
    ]
    return any(re.search(pattern, texto) for pattern in keywords)


def _extraer_familia(texto: str) -> Optional[str]:
    """
    Extrae nombre de familia de la pregunta
    Busca en la lista de familias cargadas de la BD
    
    Ejemplos:
    - "cual es el stock de id" → "ID"
    - "stock familia id" → "ID"
    - "cuanto hay de id" → "ID"
    """
    # Cargar familias dinámicamente
    familias = _cargar_familias_stock()
    
    # Normalizar texto de búsqueda
    texto_norm = _normalizar_texto(texto)
    
    # Palabras a ignorar
    ignorar = {
        "cual", "cuál", "que", "qué", "es", "el", "la", "los", "las",
        "de", "stock", "hay", "tengo", "tiene", "familia", "por", "del"
    }
    
    # Buscar cada familia en el texto
    for familia in familias:
        familia_norm = _normalizar_texto(familia)
        
        # Buscar como palabra completa
        patron = rf"\b{re.escape(familia_norm)}\b"
        if re.search(patron, texto_norm):
            return familia  # Retornar la familia original (con mayúsculas)
    
    return None


def _extraer_articulo(texto: str) -> Optional[str]:
    """Extrae nombre de artículo (palabras después de 'de' o 'stock')"""
    # Remover palabras comunes
    palabras_ignorar = {
        "cual", "cuál", "que", "qué", "es", "el", "la", "los", "las",
        "de", "stock", "hay", "tengo", "tiene", "familia", "por"
    }
    
    # Patrón: buscar después de "stock de" o "de"
    match = re.search(r"(?:stock\s+de|de)\s+(\w+)", texto)
    if match:
        palabra = match.group(1)
        if palabra not in palabras_ignorar:
            return palabra
    
    # Fallback: última palabra significativa
    words = texto.split()
    for word in reversed(words):
        if word not in palabras_ignorar and len(word) > 2:
            return word
    
    return None


def _es_pregunta_vencimiento(texto: str) -> bool:
    """Detecta preguntas sobre vencimientos"""
    patterns = [
        r"\bvenc(e|imiento|idos?)",
        r"\bpr[oó]ximo[s]?\s+a\s+vencer",
        r"\bcu[aá]ndo\s+venc",
        r"\bd[ií]as?\s+para\s+venc",
    ]
    return any(re.search(p, texto) for p in patterns)


def _extraer_dias(texto: str) -> int:
    """Extrae número de días o usa default"""
    # Buscar "30 días", "90 días", etc.
    match = re.search(r"(\d+)\s*d[ií]as?", texto)
    if match:
        return int(match.group(1))
    
    # Defaults según contexto
    if "mes" in texto or "30" in texto:
        return 30
    if "semana" in texto or "7" in texto:
        return 7
    
    return 90  # Default


def _es_pregunta_stock_bajo(texto: str) -> bool:
    """Detecta preguntas sobre stock bajo"""
    patterns = [
        r"\bstock\s+bajo\b",
        r"\bpedir\b",
        r"\bcr[ií]tico\b",
        r"\bfalta\b",
        r"\bsin\s+stock\b",
        r"\bstock\s*=?\s*0\b",
    ]
    return any(re.search(p, texto) for p in patterns)


# =====================================================================
# DEBUG / TEST
# =====================================================================
if __name__ == "__main__":
    # Tests
    preguntas_test = [
        "cual es el stock de id",
        "stock de ID",
        "familia id",
        "qué stock hay por familia",
        "stock total",
        "que vence en 30 dias",
    ]
    
    print("\n=== TESTS INTERPRETADOR STOCK ===\n")
    for p in preguntas_test:
        resultado = interpretar_pregunta_stock(p)
        print(f"{p:40} → {resultado['tipo']:30} | {resultado['parametros']}")
