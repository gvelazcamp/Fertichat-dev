import re
from typing import Dict, List, Any

# =====================================================================
# ALIASES DE ARTÍCULOS (MÍNIMO PARA FUNCIONAR)
# =====================================================================
ARTICULO_ALIASES = {
    "vitek": {"tipo": "articulo", "modo_sql": "LIKE_NORMALIZADO", "valor": "vitek"},  # ✅ Artículo/marca
    "ast": {"tipo": "articulo", "modo_sql": "LIKE_NORMALIZADO", "valor": "ast"},  # ✅ Artículo/marca
    "gn": {"tipo": "articulo", "modo_sql": "LIKE_NORMALIZADO", "valor": "gn"},  # ✅ Artículo/marca
    "id20": {"tipo": "articulo", "modo_sql": "LIKE_NORMALIZADO", "valor": "id20"},  # ✅ Artículo/marca
    "test": {"tipo": "familia", "modo_sql": "LIKE_FAMILIA", "valor": "test"},  # ✅ Familia
    "kit": {"tipo": "familia", "modo_sql": "LIKE_FAMILIA", "valor": "kit"},  # ✅ Familia
    "coba": {"tipo": "familia", "modo_sql": "LIKE_FAMILIA", "valor": "coba"},  # ✅ Familia
    "elecsys": {"tipo": "familia", "modo_sql": "LIKE_FAMILIA", "valor": "elecsys"},  # ✅ Familia
}

# =====================================================================
# FAMILIAS VÁLIDAS (familias reales: test, kit, coba, elecsys)
# =====================================================================
FAMILIAS_VALIDAS = {
    "test", "kit", "coba", "elecsys"
}

# =====================================================================
# FUNCIONES AUXILIARES
# =====================================================================
def _extraer_anios(texto: str) -> List[int]:
    anios = re.findall(r"(2023|2024|2025|2026)", texto)
    out = []
    for a in anios:
        try:
            out.append(int(a))
        except Exception:
            pass
    seen = set()
    out2 = []
    for x in out:
        if x not in seen:
            seen.add(x)
            out2.append(x)
    return out2

def _extraer_meses(texto: str) -> List[str]:
    meses_nombres = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "setiembre", "octubre", "noviembre", "diciembre"]
    meses_yyyymm = re.findall(r"(2023|2024|2025|2026)[-/](0[1-9]|1[0-2])", texto)
    out = []
    for m in meses_nombres:
        if m in texto.lower():
            out.append(m)
    out.extend(meses_yyyymm)
    return list(set(out))

def detectar_articulo(tokens, catalogo_articulos):
    for token in tokens:
        t = token.strip().lower()
        if len(t) < 4:
            continue
        for art in catalogo_articulos:
            if art and t in art.lower():  # ✅ Agregado check if art para evitar 'NoneType' object has no attribute 'lower'
                return art
    return None

# =====================================================================
# INTERPRETADOR PRINCIPAL DE ARTÍCULOS
# =====================================================================
def interpretar_articulo(texto: str, anios: List[int] = None, meses: List[str] = None) -> Dict[str, Any]:
    """
    Interpreta consultas de artículos.
    Prioriza aliases, luego búsqueda en BD.
    """
    if not texto:
        return {"tipo": "no_entendido", "parametros": {}, "debug": "texto vacío"}

    texto_lower = texto.lower().strip()
    tokens = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]+", texto_lower)

    if not anios:
        anios = _extraer_anios(texto)
    if not meses:
        meses = _extraer_meses(texto)

    print(f"\n[ARTÍCULOS] Interpretando: '{texto}'")
    print(f"  Tokens   : {tokens}")
    print(f"  Años     : {anios}")
    print(f"  Meses    : {meses}")

    # ============================================
    # PASO 1: DETECTAR ALIAS DE ARTÍCULO
    # ============================================
    for token in tokens:
        t = token.strip().lower()
        if t in ARTICULO_ALIASES:
            config = ARTICULO_ALIASES[t]
            tipo = config["tipo"]
            valor = config["valor"]
            
            # 🔴 REGLA CLAVE: Decidir modo SQL correctamente
            valor_lower = valor.lower().strip()
            if valor_lower in FAMILIAS_VALIDAS:
                modo_sql = "LIKE_FAMILIA"
            else:
                modo_sql = "LIKE_NORMALIZADO"  # Para artículos específicos

            print(f"  Alias encontrado: '{t}' -> {config} | Modo SQL: {modo_sql}")

            if anios:
                return {
                    "tipo": "compras_articulo_anio",
                    "parametros": {
                        "modo_sql": modo_sql,
                        "valor": valor,
                        "anios": anios
                    },
                    "debug": f"alias '{t}' ({tipo}) + años {anios} | modo: {modo_sql}"
                }

            if meses:
                return {
                    "tipo": "compras_articulo_mes",
                    "parametros": {
                        "modo_sql": modo_sql,
                        "valor": valor,
                        "meses": meses
                    },
                    "debug": f"alias '{t}' ({tipo}) + meses {meses} | modo: {modo_sql}"
                }

            return {
                "tipo": "compras_articulo_anio",
                "parametros": {
                    "modo_sql": modo_sql,
                    "valor": valor,
                    "anios": [2025]  # Default a 2025 si no hay tiempo
                },
                "debug": f"alias '{t}' ({tipo}) + default 2025 | modo: {modo_sql}"
            }

    # ============================================
    # PASO 2: BÚSQUEDA EN CATÁLOGO DE BD
    # ============================================
    try:
        from sql_compras import get_lista_articulos
        catalogo_articulos = get_lista_articulos()
        print(f"  Catálogo BD: {len(catalogo_articulos)} artículos")

        articulo = detectar_articulo(tokens, catalogo_articulos)

        if articulo:
            print(f"  Artículo encontrado en BD: '{articulo}'")

            # Para artículos de BD, usar LIKE_NORMALIZADO (búsqueda exacta)
            modo_sql = "LIKE_NORMALIZADO"

            if anios:
                return {
                    "tipo": "compras_articulo_anio",
                    "parametros": {
                        "modo_sql": modo_sql,
                        "valor": articulo,
                        "anios": anios
                    },
                    "debug": f"BD '{articulo}' + años {anios} | modo: {modo_sql}"
                }

            if meses:
                return {
                    "tipo": "compras_articulo_mes",
                    "parametros": {
                        "modo_sql": modo_sql,
                        "valor": articulo,
                        "meses": meses
                    },
                    "debug": f"BD '{articulo}' + meses {meses} | modo: {modo_sql}"
                }

            return {
                "tipo": "compras_articulo_anio",
                "parametros": {
                    "modo_sql": modo_sql,
                    "valor": articulo,
                    "anios": [2025]
                },
                "debug": f"BD '{articulo}' + default 2025 | modo: {modo_sql}"
            }

    except Exception as e:
        print(f"  Error cargando catálogo: {e}")

    # ============================================
    # PASO 3: NO ENCONTRADO
    # ============================================
    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Ej: compras vitek 2025 | compras fb 2024 | compras kit noviembre 2025",
        "debug": "no encontrado en aliases ni BD"
    }
