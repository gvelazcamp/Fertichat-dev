# Archivo: ia_interpretador_articulos.py
# Nota: Modificado según el cambio conceptual mínimo.

import re
from sql_compras import get_lista_articulos

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

def interpretar_articulo(texto: str, anios: list[int], meses=None):
    # 🔧 CAMBIO CONCEPTUAL MÍNIMO
    # Extraer el token principal (asumiendo es la primera palabra relevante)
    texto_lower = texto.lower().strip()
    tokens = re.findall(r'\b\w+\b', texto_lower)
    # Filtrar tokens comunes
    ignorar = {"compras", "compra", "de", "del", "el", "la", "los", "las", "en", "2023", "2024", "2025", "2026"}
    tokens_filtrados = [t for t in tokens if t not in ignorar and len(t) >= 3]
    
    if not tokens_filtrados:
        return {
            "tipo": "sin_resultado",
            "debug": "no token principal encontrado"
        }

    # ✅ Usar el primer token como artículo
    articulo = tokens_filtrados[0].lower().strip()
    sql_param = f"%{articulo}%"  # Para LIKE en SQL

    if anios:
        return {
            "tipo": "compras_articulo_anio",
            "parametros": {
                "articulo": sql_param,  # Usar el param con %
                "anios": anios
            },
            "debug": f"compras articulo token '{articulo}' + año"
        }

    return {
        "tipo": "compras_articulo",
        "parametros": {
            "articulo": sql_param
        },
        "debug": f"compras articulo token '{articulo}'"
    }# Archivo: ia_interpretador_articulos.py
# Nota: Modificado según el cambio conceptual mínimo.

import re
from sql_compras import get_lista_articulos

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

def interpretar_articulo(texto: str, anios: list[int], meses=None):
    # 🔧 CAMBIO CONCEPTUAL MÍNIMO
    # Extraer el token principal (asumiendo es la primera palabra relevante)
    texto_lower = texto.lower().strip()
    tokens = re.findall(r'\b\w+\b', texto_lower)
    # Filtrar tokens comunes
    ignorar = {"compras", "compra", "de", "del", "el", "la", "los", "las", "en", "2023", "2024", "2025", "2026"}
    tokens_filtrados = [t for t in tokens if t not in ignorar and len(t) >= 3]
    
    if not tokens_filtrados:
        return {
            "tipo": "sin_resultado",
            "debug": "no token principal encontrado"
        }

    # ✅ Usar el primer token como artículo
    articulo = tokens_filtrados[0].lower().strip()
    sql_param = f"%{articulo}%"  # Para LIKE en SQL

    if anios:
        return {
            "tipo": "compras_articulo_anio",
            "parametros": {
                "articulo": sql_param,  # Usar el param con %
                "anios": anios
            },
            "debug": f"compras articulo token '{articulo}' + año"
        }

    return {
        "tipo": "compras_articulo",
        "parametros": {
            "articulo": sql_param
        },
        "debug": f"compras articulo token '{articulo}'"
    }
