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
    articulos_db = get_lista_articulos()

    articulo = detectar_articulo(texto, articulos_db)

    if not articulo:
        return {
            "tipo": "sin_resultado",
            "debug": "articulo no detectado en BD"
        }

    if anios:
        return {
            "tipo": "compras_articulo_anio",
            "parametros": {
                "articulo": articulo,
                "anios": anios
            },
            "debug": "compras articulo + año (canónico)"
        }

    return {
        "tipo": "compras_articulo",
        "parametros": {
            "articulo": articulo
        },
        "debug": "compras articulo (canónico)"
    }
