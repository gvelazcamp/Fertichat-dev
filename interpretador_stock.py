# interpretador_stock.py
# Módulo dedicado exclusivamente a interpretar preguntas de stock

import re
from typing import Dict, Optional, List

def interpretar_pregunta_stock(pregunta: str) -> Dict:
    """
    Interpreta preguntas relacionadas con stock.
    Retorna un diccionario con tipo y parámetros.
    """
    pregunta_lower = pregunta.lower().strip()
    
    # 1. Detectar si es pregunta de stock
    palabras_clave = ["stock", "artículo", "articulo", "lote", "familia", "depósito", "deposito", "vence", "vencimiento"]
    es_pregunta_stock = any(palabra in pregunta_lower for palabra in palabras_clave)
    
    if not es_pregunta_stock:
        return {"tipo": "no_stock", "parametros": {}}
    
    # 2. Extraer parámetros usando regex y lógica simple
    params = extraer_parametros_stock(pregunta_lower)
    
    # 3. Determinar tipo de consulta
    tipo = determinar_tipo_consulta(pregunta_lower, params)
    
    return {
        "tipo": tipo,
        "parametros": params
    }


def extraer_parametros_stock(pregunta: str) -> Dict:
    """
    Extrae parámetros de la pregunta usando regex
    """
    params = {}
    
    # Extraer familia
    familia_match = re.search(r'familia\s+(\w+)', pregunta)
    if familia_match:
        familia = familia_match.group(1).upper()
        if familia in ['ID', 'FB', 'G', 'TR', 'XX', 'HM', 'MI']:
            params['familia'] = familia
    
    # Extraer artículo (lo que queda después de quitar palabras comunes)
    palabras_excluir = ['stock', 'cuanto', 'cuánto', 'hay', 'de', 'del', 'tenemos', 'disponible', 'el', 'la', 'los', 'las', 'que', 'es', 'un', 'una', 'cual', 'familia', 'lote']
    palabras = [p for p in pregunta.split() if p not in palabras_excluir and len(p) > 2]
    if palabras:
        params['articulo'] = ' '.join(palabras)
    
    # Extraer lote
    lote_match = re.search(r'lote\s+(\w+)', pregunta)
    if lote_match:
        params['lote'] = lote_match.group(1)
    
    # Extraer días para vencimientos
    dias_match = re.search(r'(\d+)\s*(dias|día|dia)', pregunta)
    if dias_match:
        params['dias'] = int(dias_match.group(1))
    
    return params


def determinar_tipo_consulta(pregunta: str, params: Dict) -> str:
    """
    Determina el tipo de consulta basado en la pregunta y parámetros
    """
    if params.get('familia'):
        return 'familia_especifica'
    
    if 'por familia' in pregunta or 'familias' in pregunta:
        return 'por_familia'
    
    if 'por depósito' in pregunta or 'por deposito' in pregunta:
        return 'por_deposito'
    
    if params.get('lote'):
        return 'lote'
    
    if 'vence' in pregunta or 'vencimiento' in pregunta:
        if 'ya venc' in pregunta or 'vencido' in pregunta:
            return 'vencidos'
        return 'vencimientos'
    
    if 'bajo' in pregunta or 'crítico' in pregunta:
        return 'stock_bajo'
    
    if 'total' in pregunta:
        return 'total'
    
    if params.get('articulo'):
        return 'articulo'
    
    return 'busqueda_libre'