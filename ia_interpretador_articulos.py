# Archivo: ia_interpretador_articulos.py
# Versión completa con lógica avanzada para familias y aliases de artículos.

import re
from sql_compras import get_lista_articulos

# =====================================================================
# ALIASES DE ARTÍCULOS (MÍNIMO PARA FUNCIONAR)
# =====================================================================
ARTICULO_ALIASES = {
    # Familia VITEK (todos los insumos y reactivos)
    "vitek": {
        "tipo": "familia",
        "match": ["vitek"],
        "descripcion": "Todos los insumos y reactivos VITEK"
    },
    
    # Específicos (opcionales, agregar luego)
    "vitek_ast_n422": {
        "tipo": "articulo",
        "match": ["ast-n422", "ast 422"],
        "canonical": "VITEK AST-N422 TEST KIT 20 DET (TARJETA AST 422)"
    },
    "vitek_gn_id_20": {
        "tipo": "articulo",
        "match": ["gn id 20"],
        "canonical": "VITEK GN ID 20 (ID GN)"
    }
}

def normalizar(txt: str) -> str:
    txt = txt.lower().strip()
    txt = re.sub(r"[^\w\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt

def detectar_articulo(texto: str, articulos_db: list[str]) -> str | None:
    texto_n = normalizar(texto)

    candidatos = []

    for art in articulos_db:
        art_n = normalizar(art)

        # match flexible, como proveedor
        if art_n in texto_n or texto_n in art_n:
            candidatos.append(art)

    if not candidatos:
        return None

    # elegimos el más específico (más largo)
    return max(candidatos, key=len)

def detectar_alias(texto: str) -> str | None:
    """
    Detecta si el texto contiene un alias conocido.
    Retorna el key del alias si coincide.
    """
    texto_n = normalizar(texto)
    
    for alias_key, config in ARTICULO_ALIASES.items():
        for match in config["match"]:
            if match in texto_n:
                return alias_key
    
    return None

def interpretar_articulo(texto: str, anios: list[int], meses=None):
    """
    Intérprete avanzado para artículos.
    Maneja familias semánticas + aliases, no exige coincidencia exacta.
    Regla: Si contiene 'vitek' → buscar familia VITEK, no artículo exacto.
    """
    # 1. Verificar aliases primero (familias o específicos)
    alias_detectado = detectar_alias(texto)
    if alias_detectado:
        config = ARTICULO_ALIASES[alias_detectado]
        
        if config["tipo"] == "familia":
            # Para familias como VITEK, usar LIKE con el match
            articulo_param = f"%{config['match'][0]}%"  # e.g., "%vitek%"
        elif config["tipo"] == "articulo":
            # Para específicos, usar canonical exacto
            articulo_param = config["canonical"]
        
        if anios:
            return {
                "tipo": "compras_articulo_anio",
                "parametros": {
                    "articulo": articulo_param,
                    "anios": anios
                },
                "debug": f"alias '{alias_detectado}' ({config['tipo']}) + año"
            }
        
        return {
            "tipo": "compras_articulo_anio",  # Usar anio por defecto si no hay
            "parametros": {
                "articulo": articulo_param,
                "anios": anios or [2025]  # Default si no hay años
            },
            "debug": f"alias '{alias_detectado}' ({config['tipo']})"
        }
    
    # 2. Si no hay alias, usar lógica de token (como antes)
    texto_lower = texto.lower().strip()
    tokens = re.findall(r'\b\w+\b', texto_lower)
    ignorar = {"compras", "compra", "de", "del", "el", "la", "los", "las", "en", "2023", "2024", "2025", "2026"}
    tokens_filtrados = [t for t in tokens if t not in ignorar and len(t) >= 3]
    
    if not tokens_filtrados:
        return {
            "tipo": "sin_resultado",
            "debug": "no token principal encontrado"
        }

    # Usar el primer token como artículo (con LIKE para flexibilidad)
    articulo = tokens_filtrados[0].lower().strip()
    sql_param = f"%{articulo}%"  # LIKE para familias

    if anios:
        return {
            "tipo": "compras_articulo_anio",
            "parametros": {
                "articulo": sql_param,
                "anios": anios
            },
            "debug": f"compras articulo token '{articulo}' + año"
        }

    return {
        "tipo": "compras_articulo_anio",
        "parametros": {
            "articulo": sql_param,
            "anios": anios or [2025]
        },
        "debug": f"compras articulo token '{articulo}'"
    }
