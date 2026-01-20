# ia_interpretador_articulos.py

import re

# palabras que NO son artículo
STOPWORDS = {
    "compras", "compra", "comprar",
    "facturas", "factura",
    "del", "de", "la", "el", "los", "las",
    "por", "para"
}

def _limpiar_tokens(texto: str) -> list[str]:
    texto = texto.lower()
    texto = re.sub(r"[^\w\s]", " ", texto)
    return [t for t in texto.split() if t and t not in STOPWORDS]

def detectar_articulo(texto: str) -> str | None:
    tokens = _limpiar_tokens(texto)

    # estrategia simple y segura:
    # el primer token útil largo
    for t in tokens:
        if len(t) >= 3 and not t.isdigit():
            return t

    return None

def interpretar_articulo(texto: str, anios: list[int], meses: list[str] | None = None):
    articulo = detectar_articulo(texto)

    if not articulo:
        return {
            "tipo": "sin_resultado",
            "debug": "no se pudo detectar articulo"
        }

    # artículo + año(s)
    if anios:
        return {
            "tipo": "compras_articulo_anio",
            "parametros": {
                "articulo": articulo,
                "anios": anios
            },
            "debug": "articulo + año (interpretador articulos)"
        }

    # solo artículo
    return {
        "tipo": "compras_articulo",
        "parametros": {
            "articulo": articulo
        },
        "debug": "solo articulo (interpretador articulos)"
    }
