# =========================
# IA_COMPARATIVAS.PY - INTÉRPRETE COMPARATIVAS (CANÓNICO)
# =========================
# IDEA (TUYA, IMPLEMENTADA SIN IA):
# - Lo único que importa es mapear la pregunta a una "FUNCIÓN" definida por:
#   ACCIÓN | OBJETO | TIEMPO | MULTI | TIPO (output) | PARAMS
# - Todo lo que esté antes/después (hola, insultos, contexto) NO importa.
# - Si el usuario dice "comparar" pero NO alcanza para ejecutar (ej: "comparar 2025"),
#   NO se inventa nada: se sugiere el formato correcto (ej: "comparar compras proveedor 2024 2025").
# - No hace falta IA: con reglas + tabla canónica alcanza (más estable y controlable).

import os
import re
import unicodedata
from typing import Dict, List, Tuple, Optional

import streamlit as st

MESES = {
    "enero": "01",
    "febrero": "02",
    "marzo": "03",
    "abril": "04",
    "mayo": "05",
    "junio": "06",
    "julio": "07",
    "agosto": "08",
    "septiembre": "09",
    "setiembre": "09",
    "octubre": "10",
    "noviembre": "11",
    "diciembre": "12",
}

MAX_PROVEEDORES = 5
MAX_ARTICULOS = 5
MAX_MESES = 6
MAX_ANIOS = 4

# =====================================================================
# TABLA CANÓNICA SOLO COMPARATIVAS (CONTRATO)
# - Sirve como referencia de qué "funciones" (tipos) existen.
# =====================================================================
TABLA_CANONICA_COMPARATIVAS = r"""
| # | ACCIÓN | OBJETO | TIEMPO | MULTI | TIPO (output) | PARAMS |
|---|--------|--------|--------|-------|---------------|--------|
| 16 | comparar | proveedor | mes+mes (mismo anio) | no | comparar_proveedor_meses | proveedor, mes1, mes2, label1, label2 |
| 17 | comparar | proveedor | anio+anio | no | comparar_proveedor_anios | proveedor, anios |
| 18 | comparar compras | proveedor | mes+mes | no | comparar_proveedor_meses | proveedor, mes1, mes2 |
| 19 | comparar compras | proveedor | anio+anio | no | comparar_proveedor_anios | proveedor, anios |
| 22 | comparar | proveedor | meses (lista) | si (<=6) | comparar_proveedor_meses | proveedor, mes1, mes2 (si hay 2) |
| 23 | comparar | proveedor | anios (lista) | si (<=4) | comparar_proveedor_anios | proveedor, anios |
| 30 | comparar compras | proveedor | mes(YYYY-MM)+mes(YYYY-MM) | no | comparar_proveedor_meses | proveedor, mes1, mes2 |
| 31 | comparar compras | proveedor | anio+anio | no | comparar_proveedor_anios | proveedor, anios |
| 34 | comparar compras | proveedor | "junio julio 2025" | no | comparar_proveedor_meses | proveedor, 2025-06, 2025-07 |
| 35 | comparar compras | proveedor | "noviembre diciembre 2025" | no | comparar_proveedor_meses | proveedor, 2025-11, 2025-12 |
| 36 | comparar compras | proveedor | "2024 2025" | no | comparar_proveedor_anios | proveedor, [2024,2025] |
| 41 | comparar compras | proveedor | "enero febrero" (sin año) | no | comparar_proveedor_meses | proveedor, pedir año |
| 46 | comparar | proveedor | mes vs mes | no | comparar_proveedor_meses | proveedor, mes1, mes2 |
| 47 | comparar | proveedor | anio vs anio | no | comparar_proveedor_anios | proveedor, anios |
"""

# =====================================================================
# HELPERS NORMALIZACIÓN
# =====================================================================
def _strip_accents(s: str) -> str:
    if not s:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )

def _key(s: str) -> str:
    s = _strip_accents((s or "").lower().strip())
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s

def _tokens(texto: str) -> List[str]:
    raw = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]+", (texto or "").lower())
    out: List[str] = []
    for t in raw:
        k = _key(t)
        if len(k) >= 3:
            out.append(k)
    return out


# =====================================================================
# CARGA LISTAS DESDE SUPABASE (cache)
# =====================================================================
@st.cache_data(ttl=60 * 60)
def _cargar_listas_supabase() -> Dict[str, List[str]]:
    proveedores: List[str] = []
    articulos: List[str] = []

    try:
        from supabase_client import supabase  # type: ignore
        if supabase is None:
            return {"proveedores": [], "articulos": []}

        for col in ["nombre", "Nombre", "NOMBRE"]:
            try:
                res = supabase.table("proveedores").select(col).execute()
                data = res.data or []
                proveedores = [str(r.get(col)).strip() for r in data if r.get(col)]
                if proveedores:
                    break
            except Exception:
                continue

        for col in ["Descripción", "Descripcion", "descripcion", "DESCRIPCION", "DESCRIPCIÓN"]:
            try:
                res = supabase.table("articulos").select(col).execute()
                data = res.data or []
                articulos = [str(r.get(col)).strip() for r in data if r.get(col)]
                if articulos:
                    break
            except Exception:
                continue

    except Exception:
        return {"proveedores": [], "articulos": []}

    proveedores = sorted(list(set([p for p in proveedores if p])))
    articulos = sorted(list(set([a for a in articulos if a])))

    return {"proveedores": proveedores, "articulos": articulos}

def _get_indices() -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    listas = _cargar_listas_supabase()
    prov = [(p, _key(p)) for p in (listas.get("proveedores") or []) if p]
    art = [(a, _key(a)) for a in (listas.get("articulos") or []) if a]
    return prov, art

def _match_best(texto: str, index: List[Tuple[str, str]], max_items: int = 1) -> List[str]:
    toks = _tokens(texto)
    if not toks or not index:
        return []

    # 1) EXACT token match
    toks_set = set(toks)
    for orig, norm in index:
        if norm in toks_set:
            return [orig]

    # 2) substring + score
    candidatos: List[Tuple[int, str]] = []
    for orig, norm in index:
        for tk in toks:
            if tk and tk in norm:
                score = (len(tk) * 1000) - len(norm)
                candidatos.append((score, orig))

    if not candidatos:
        return []

    candidatos.sort(key=lambda x: (-x[0], x[1]))
    out: List[str] = []
    seen = set()
    for _, orig in candidatos:
        if orig not in seen:
            seen.add(orig)
            out.append(orig)
        if len(out) >= max_items:
            break

    return out


# =====================================================================
# RESOLVER ALIASES DE PROVEEDOR (TRESUL / BIODIAGNOSTICO / ROCHE)
# - Objetivo: que "tresul" termine en el nombre real de tu lista (ej: "LABORATORIO TRESUL ...")
# - Esto evita que el SQL compare por un string corto que no coincide con la BD.
# =====================================================================
def _resolver_proveedor_alias(texto_lower: str, idx_prov: List[Tuple[str, str]]) -> Optional[str]:
    tlk = _key(texto_lower)

    # alias -> buscar dentro del "norm" de la lista supabase
    # (no renombra nada, solo elige el proveedor real existente)
    alias_terms = [
        "tresul",
        "biodiagnostico",
        "cabinsur",
        "cabinsursrl",
        "cabinsuruy",
        "roche",
    ]

    hit = None
    for a in alias_terms:
        if a in tlk:
            hit = a
            break

    if not hit:
        return None

    best_orig = None
    best_score = None

    for orig, norm in idx_prov:
        if hit in norm:
            score = 1000

            # preferir nombres más "formales" cuando aplica
            if "laboratorio" in norm:
                score += 200
            if "diagnostics" in norm or "diagnostico" in norm:
                score += 80

            # evitar quedarse con el más corto si hay uno más descriptivo
            score -= int(len(norm) / 10)

            if best_score is None or score > best_score:
                best_score = score
                best_orig = orig

    return best_orig


# =====================================================================
# PARSEO TIEMPO
# =====================================================================
def _extraer_anios(texto: str) -> List[int]:
    anios = re.findall(r"(2023|2024|2025|2026)", texto or "")
    out: List[int] = []
    for a in anios:
        try:
            out.append(int(a))
        except Exception:
            pass
    seen = set()
    out2: List[int] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            out2.append(x)
    return out2[:MAX_ANIOS]

def _extraer_meses_nombre(texto: str) -> List[str]:
    tl = (texto or "").lower()
    ms = [m for m in MESES.keys() if m in tl]
    seen = set()
    out: List[str] = []
    for m in ms:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out[:MAX_MESES]

def _extraer_meses_yyyymm(texto: str) -> List[str]:
    ms = re.findall(r"(2023|2024|2025|2026)[-/](0[1-9]|1[0-2])", texto or "")
    out = [f"{a}-{m}" for a, m in ms]
    seen = set()
    out2: List[str] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            out2.append(x)
    return out2[:MAX_MESES]

def _to_yyyymm(anio: int, mes_nombre: str) -> str:
    return f"{anio}-{MESES[mes_nombre]}"


# =====================================================================
# SUGERENCIAS CANÓNICAS (cuando falta info)
# - Esto implementa lo que dijiste: si ponen "comparar 2025" es inválido,
#   entonces sugerimos "comparar compras <proveedor> 2024 2025" o "junio julio 2025"
# =====================================================================
def _sugerencia_canonica_comparar() -> str:
    return (
        "Probá así:\n"
        "- comparar compras roche 2024 2025\n"
        "- comparame compras tresul 2025 2026\n"
        "- comparar compras biodiagnostico junio julio 2025\n"
        "- comparar compras roche noviembre diciembre 2025"
    )


# =====================================================================
# INTÉRPRETE COMPARATIVAS
# =====================================================================
def interpretar_comparativas(pregunta: str) -> Dict:
    texto = (pregunta or "").strip()
    texto_lower = texto.lower().strip()

    idx_prov, _idx_art = _get_indices()
    provs = _match_best(texto_lower, idx_prov, max_items=MAX_PROVEEDORES)

    anios = _extraer_anios(texto_lower)
    meses_nombre = _extraer_meses_nombre(texto_lower)
    meses_yyyymm = _extraer_meses_yyyymm(texto_lower)

    # ==========================================================
    # DETECTOR DE "FUNCIÓN" COMPARATIVA
    # - lo demás no importa: hola/ruido/contexto no se usa
    # ==========================================================
    es_comparar = ("comparar" in texto_lower) or ("comparame" in texto_lower) or ("compara" in texto_lower)
    es_compras = ("compra" in texto_lower) or ("compras" in texto_lower)

    if es_comparar and es_compras:
        # 1) alias duros primero (tresul/biodiagnostico/roche)
        proveedor_alias = _resolver_proveedor_alias(texto_lower, idx_prov)

        # 2) si no hay alias, intento lista
        proveedor = proveedor_alias or (provs[0] if provs else None)

        # 3) fallback libre (solo si no detecté nada en lista)
        proveedor_libre = None
        if not proveedor:
            tmp = texto_lower
            tmp = re.sub(r"(comparar|comparame|compara|compras?)", "", tmp)
            tmp = re.sub(
                r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)",
                "",
                tmp,
            )
            tmp = re.sub(r"(2023|2024|2025|2026)", "", tmp).strip()
            tmp = re.sub(r"\s+", " ", tmp).strip()

            if tmp and len(tmp) >= 3:
                proveedor_libre = tmp

        proveedor_final = proveedor or proveedor_libre

        # Si el usuario dijo "comparar compras" pero NO hay proveedor -> sugerir
        if not proveedor_final:
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": _sugerencia_canonica_comparar(),
                "debug": "comparar: falta proveedor",
            }

        # --- CASO 1: mes vs mes (YYYY-MM) ---
        if len(meses_yyyymm) >= 2:
            mes1, mes2 = meses_yyyymm[0], meses_yyyymm[1]
            return {
                "tipo": "comparar_proveedor_meses",
                "parametros": {
                    "proveedor": proveedor_final,
                    "mes1": mes1,
                    "mes2": mes2,
                    "label1": mes1,
                    "label2": mes2,
                },
                "debug": "comparar proveedor meses (YYYY-MM)",
            }

        # --- CASO 2: mes vs mes (nombre + año) ---
        if len(meses_nombre) >= 2 and len(anios) >= 1:
            anio = anios[0]
            mes1 = _to_yyyymm(anio, meses_nombre[0])
            mes2 = _to_yyyymm(anio, meses_nombre[1])
            return {
                "tipo": "comparar_proveedor_meses",
                "parametros": {
                    "proveedor": proveedor_final,
                    "mes1": mes1,
                    "mes2": mes2,
                    "label1": f"{meses_nombre[0]} {anio}",
                    "label2": f"{meses_nombre[1]} {anio}",
                },
                "debug": "comparar proveedor meses (nombre+anio)",
            }

        # --- CASO 3: año vs año (mínimo 2 años) ---
        if len(anios) >= 2:
            return {
                "tipo": "comparar_proveedor_anios",
                "parametros": {
                    "proveedor": proveedor_final,
                    "anios": [anios[0], anios[1]],
                },
                "debug": "comparar proveedor años",
            }

        # --- Si llegó acá: el usuario dijo "comparar" pero le faltan parámetros ---
        # Ejemplo: "comparar 2025" -> no se puede ejecutar: falta proveedor y 2do año
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": _sugerencia_canonica_comparar(),
            "debug": "comparar: faltan meses/años",
        }

    # Si la pregunta no es comparativa de compras, no la tomamos acá
    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": _sugerencia_canonica_comparar(),
        "debug": "comparar: no match",
    }
