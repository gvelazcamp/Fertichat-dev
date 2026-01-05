# =========================
# IA_COMPARATIVAS.PY - INTÉRPRETE COMPARATIVAS (CANÓNICO)
# =========================
# CAMBIOS (mínimos, sin romper lo existente):
# 1) Agregada TABLA_CANONICA_COMPARATIVAS (solo comparativas) para guiar sugerencias.
# 2) Mejorada detección de "comparativa/comparacion" + extracción robusta de proveedor (aliases + libre) tipo TRESUL/BIODIAGNOSTICO/CABINSUR.
# 3) Agregadas sugerencias cuando falte 2do año/mes (ej: "comparar 2025" -> pedir 2 años o 2 meses).

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
# TABLA CANÓNICA (SOLO COMPARATIVAS)
# =====================================================================
TABLA_CANONICA_COMPARATIVAS = r"""
| # | ACCIÓN | OBJETO | TIEMPO | MULTI | TIPO (output) | PARAMS |
|---|--------|--------|--------|-------|---------------|--------|
| 16 | comparar | proveedor | mes+mes (mismo anio) | no | comparar_proveedor_meses | proveedor, mes1, mes2, label1, label2 |
| 17 | comparar | proveedor | anio+anio | no | comparar_proveedor_anios | proveedor, anios |
| 18 | comparar compras | proveedor | mes+mes | no | comparar_proveedor_meses | proveedor, mes1, mes2 |
| 19 | comparar compras | proveedor | anio+anio | no | comparar_proveedor_anios | proveedor, anios |
| 20 | comparar | proveedor+proveedor | mismo mes | si (<=5) | compras_proveedor_mes | proveedor(s), mes |
| 21 | comparar | proveedor+proveedor | mismo anio | si (<=5) | compras_proveedor_anio | proveedor(s), anio |
| 22 | comparar | proveedor | meses (lista) | si (<=6) | comparar_proveedor_meses | proveedor, mes1, mes2 (si hay 2) |
| 23 | comparar | proveedor | anios (lista) | si (<=4) | comparar_proveedor_anios | proveedor, anios |
| 30 | comparar compras | proveedor | mes(YYYY-MM)+mes(YYYY-MM) | no | comparar_proveedor_meses | proveedor, mes1, mes2 |
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
# PROVEEDORES: ALIASES + LIBRE (PARA QUE SQL LIKE FUNCIONE)
# =====================================================================
_ALIAS_PROVEEDORES = {
    # el usuario escribe -> posibles "claves" a detectar en el texto
    "tresul": ["tresul", "laboratoriotresul"],
    "biodiagnostico": ["biodiagnostico", "biodiagnostico", "bio", "bio-diagnostico", "biodiagnost"],
    "cabinsur": ["cabinsur", "cabinsursrl", "cabinsuruy"],
    "roche": ["roche"],
}

def _detectar_aliases_proveedor(texto_lower: str) -> List[str]:
    """
    Devuelve términos-candidatos a usar como filtro LIKE en SQL.
    No necesita que exista en tabla proveedores, porque SQL filtra por LIKE.
    """
    tlk = _key(texto_lower)
    hits: List[str] = []

    for canon, patrones in _ALIAS_PROVEEDORES.items():
        for p in patrones:
            if p and p in tlk:
                hits.append(canon)
                break

    # únicos, en orden
    seen = set()
    out: List[str] = []
    for x in hits:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out[:MAX_PROVEEDORES]

def _extraer_proveedor_libre(texto_lower: str) -> Optional[str]:
    """
    Extrae proveedor como texto libre, ignorando todo lo que no sean "funciones".
    """
    tmp = texto_lower

    # sacar disparadores
    tmp = re.sub(r"\b(comparar|comparame|compara|comparativa|comparacion|comparación)\b", " ", tmp)
    tmp = re.sub(r"\b(compras?|compra)\b", " ", tmp)

    # sacar meses
    tmp = re.sub(
        r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\b",
        " ",
        tmp,
    )

    # sacar años
    tmp = re.sub(r"\b(2023|2024|2025|2026)\b", " ", tmp)

    # sacar conectores típicos (para que no quede "vs")
    tmp = re.sub(r"\b(vs|versus|contra|y|e|entre)\b", " ", tmp)

    # normalizar espacios
    tmp = re.sub(r"[\(\)\[\]\{\}\|]", " ", tmp)
    tmp = re.sub(r"[,:;]", " ", tmp)
    tmp = re.sub(r"\s+", " ", tmp).strip()

    if tmp and len(tmp) >= 3:
        return tmp
    return None

def _resolver_proveedor(texto_lower: str, idx_prov: List[Tuple[str, str]]) -> Optional[str]:
    """
    Prioridad:
    1) Aliases (tresul/biodiagnostico/cabinsur/roche) -> devuelve el alias como filtro LIKE (sirve en SQL)
    2) Match por lista (tabla proveedores) -> devuelve nombre completo de lista
    3) Fallback libre -> devuelve texto libre como filtro LIKE
    """
    aliases = _detectar_aliases_proveedor(texto_lower)
    if aliases:
        return aliases[0]

    provs = _match_best(texto_lower, idx_prov, max_items=MAX_PROVEEDORES)
    if provs:
        return provs[0]

    return _extraer_proveedor_libre(texto_lower)

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
# INTÉRPRETE COMPARATIVAS
# =====================================================================
def interpretar_comparativas(pregunta: str) -> Dict:
    texto = (pregunta or "").strip()
    texto_lower = texto.lower().strip()

    idx_prov, idx_art = _get_indices()

    anios = _extraer_anios(texto_lower)
    meses_nombre = _extraer_meses_nombre(texto_lower)
    meses_yyyymm = _extraer_meses_yyyymm(texto_lower)

    # disparadores (acepta "comparativa" / "comparacion")
    hay_comparar = (
        ("comparar" in texto_lower) or
        ("comparame" in texto_lower) or
        ("compara" in texto_lower) or
        ("comparativa" in texto_lower) or
        ("comparacion" in texto_lower) or
        ("comparación" in texto_lower)
    )
    hay_compras = ("compra" in texto_lower) or ("compras" in texto_lower)

    if hay_comparar and (not hay_compras):
        # el usuario dijo "comparar ..." pero no indicó qué (por tu regla: sugerir "comparar compras ...")
        sug = "Probá: comparar compras roche 2024 2025 | comparar compras roche junio julio 2025"
        if len(anios) == 1:
            a = anios[0]
            a2 = a - 1 if a > 2023 else 2024
            sug = f"Te falta otro período. Probá: comparar compras roche {a2} {a}"
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": sug,
            "debug": "comparar: falta palabra compras/compra",
        }

    # ==========================================================
    # COMPARAR COMPRAS PROVEEDOR MES VS MES / AÑO VS AÑO
    # ==========================================================
    if hay_comparar and hay_compras:
        proveedor_final = _resolver_proveedor(texto_lower, idx_prov)

        if not proveedor_final:
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": "No reconocí el proveedor. Probá: comparar compras tresul 2024 2025 | comparar compras biodiagnostico 2024 2025",
                "debug": "comparar: proveedor no reconocido",
            }

        # --- mes vs mes (YYYY-MM) ---
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

        # --- mes vs mes (nombre + año) ---
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

        # --- año vs año ---
        if len(anios) >= 2:
            return {
                "tipo": "comparar_proveedor_anios",
                "parametros": {
                    "proveedor": proveedor_final,
                    "anios": [anios[0], anios[1]],
                },
                "debug": "comparar proveedor años",
            }

        # --- sugerencias cuando falta el 2do periodo ---
        if len(anios) == 1:
            a = anios[0]
            a2 = a - 1 if a > 2023 else 2024
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": f"Te falta otro año para comparar. Probá: comparar compras {proveedor_final} {a2} {a}",
                "debug": "comparar: falta segundo año",
            }

        if len(meses_nombre) == 1 and len(anios) >= 1:
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": f"Te falta otro mes para comparar. Probá: comparar compras {proveedor_final} junio julio {anios[0]}",
                "debug": "comparar: falta segundo mes",
            }

        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": f"Probá: comparar compras {proveedor_final} 2024 2025 | comparar compras {proveedor_final} junio julio 2025",
            "debug": "comparar: faltan meses/años",
        }

    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: comparar compras roche 2024 2025 | comparar compras roche junio julio 2025",
        "debug": "comparar: no match",
    }
