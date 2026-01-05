# =========================
# IA_COMPARATIVAS.PY - INTÉRPRETE COMPARATIVAS (CANÓNICO)
# =========================

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
# - Esto es el "spec" de funciones: ACCIÓN | OBJETO | TIEMPO | MULTI | TIPO | PARAMS
# - El texto extra antes/después no importa; nos centramos en mapear a una función (TIPO) con PARAMS.
# =====================================================================
TABLA_CANONICA_COMPARATIVAS = r"""
| # | ACCIÓN | OBJETO | TIEMPO | MULTI | TIPO (output) | PARAMS |
|---|--------|--------|--------|-------|---------------|--------|
| 16 | comparar / comparar compras | proveedor | mes+mes (mismo año o YYYY-MM) | no | comparar_proveedor_meses | proveedor/proveedores, mes1, mes2, label1, label2 |
| 17 | comparar / comparar compras | proveedor | anio+anio | no | comparar_proveedor_anios | proveedor/proveedores, anios |
| 20 | comparar | proveedor+proveedor | mismo mes | si (<=5) | compras_proveedor_mes | proveedores, mes |
| 21 | comparar | proveedor+proveedor | mismo anio | si (<=5) | compras_proveedor_anio | proveedores, anio |
| 22 | comparar | proveedor | meses (lista) | si (<=6) | comparar_proveedor_meses | proveedor, mes1, mes2 (si hay 2) |
| 23 | comparar | proveedor | anios (lista) | si (<=4) | comparar_proveedor_anios | proveedor, anios |
| 30 | comparar compras | proveedor | mes(YYYY-MM)+mes(YYYY-MM) | no | comparar_proveedor_meses | proveedor, mes1, mes2 |
| 36 | comparar compras | proveedor | "2024 2025" | no | comparar_proveedor_anios | proveedor, [2024,2025] |
| 41 | comparar compras | proveedor | "enero febrero" (sin año) | no | comparar_proveedor_meses | proveedor, pedir año |
| 46 | comparar | proveedor | mes vs mes | no | comparar_proveedor_meses | proveedor, mes1, mes2 |
| 47 | comparar | proveedor | anio vs anio | no | comparar_proveedor_anios | proveedor, anios |
"""

# =====================================================================
# KEYWORDS (comparativas)
# =====================================================================
_COMPARA_WORDS = [
    "comparar",
    "comparame",
    "compara",
    "comparativa",
    "comparativas",
    "comparativo",
    "comparativos",
]

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

def _tiene_palabra(texto_lower: str, palabra: str) -> bool:
    # match por palabra completa (evita que "compara" se dispare dentro de otras cosas raras)
    return bool(re.search(rf"\b{re.escape(palabra)}\b", texto_lower))

def _tiene_alguna_palabra(texto_lower: str, palabras: List[str]) -> bool:
    for p in palabras:
        if _tiene_palabra(texto_lower, p):
            return True
    return False

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
# RESOLVER ALIASES DE PROVEEDOR (si existe en tu lista de proveedores)
# - Importante: si NO existe (porque tu tabla proveedores no tiene "LABORATORIO TRESUL"),
#   igual vamos a pasar el proveedor "libre" (ej: "tresul") para que el SQL filtre con LIKE.
# =====================================================================
def _resolver_proveedor_alias(texto_lower: str, idx_prov: List[Tuple[str, str]]) -> Optional[str]:
    tlk = _key(texto_lower)

    alias_terms = [
        "tresul",
        "biodiagnostico",
        "cabinsur",
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
            if "laboratorio" in norm:
                score += 200
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
# EXTRAER "PROVEEDOR LIBRE" (robusto)
# - Ignora texto alrededor, se queda con lo que parece proveedor luego de sacar keywords y fechas.
# =====================================================================
def _extraer_proveedor_libre(texto_lower: str) -> Optional[str]:
    tmp = texto_lower

    # sacar keywords de comparar (por palabra completa)
    tmp = re.sub(
        r"\b(comparar|comparame|compara|comparativa|comparativas|comparativo|comparativos)\b",
        " ",
        tmp,
        flags=re.IGNORECASE,
    )

    # sacar compras
    tmp = re.sub(r"\bcompras?\b", " ", tmp, flags=re.IGNORECASE)

    # sacar meses
    tmp = re.sub(
        r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\b",
        " ",
        tmp,
        flags=re.IGNORECASE,
    )

    # sacar años
    tmp = re.sub(r"\b(2023|2024|2025|2026)\b", " ", tmp)

    # limpiar basura típica (mínimo, sin romper)
    tmp = re.sub(r"\s+", " ", tmp).strip()

    if tmp and len(tmp) >= 3:
        return tmp

    return None

# =====================================================================
# INTÉRPRETE COMPARATIVAS
# =====================================================================
def interpretar_comparativas(pregunta: str) -> Dict:
    texto = (pregunta or "").strip()
    texto_lower = texto.lower().strip()

    idx_prov, idx_art = _get_indices()
    provs = _match_best(texto_lower, idx_prov, max_items=MAX_PROVEEDORES)

    anios = _extraer_anios(texto_lower)
    meses_nombre = _extraer_meses_nombre(texto_lower)
    meses_yyyymm = _extraer_meses_yyyymm(texto_lower)

# =========================
# DEBUG COMPARATIVAS (VISIBLE)
# =========================
if st.session_state.get("DEBUG_MODE", True):
    st.markdown("### 🐞 Debug comparativa")

    st.code({
        "pregunta": pregunta,
        "tipo": res.get("tipo"),
        "parametros": res.get("parametros"),
        "debug": res.get("debug"),
        "sugerencia": res.get("sugerencia"),
    }, language="python")
    
    # ==========================================================
    # DETECCIÓN "MODO COMPARATIVA"
    # - Si aparece alguna keyword de comparar, entramos.
    # - Si además dice compras, mejor (pero no es obligatorio para sugerir).
    # ==========================================================
    es_comparativa = _tiene_alguna_palabra(texto_lower, _COMPARA_WORDS)
    menciona_compras = _tiene_palabra(texto_lower, "compra") or _tiene_palabra(texto_lower, "compras")

    if es_comparativa:
        # 1) alias contra lista de proveedores (si existe)
        proveedor_alias = _resolver_proveedor_alias(texto_lower, idx_prov)

        # 2) match por lista supabase
        proveedor_lista = provs[0] if provs else None

        # 3) fallback proveedor libre (CLAVE para casos como "tresul" cuando tu tabla proveedores no lo tiene)
        proveedor_libre = _extraer_proveedor_libre(texto_lower)

        proveedor_final = proveedor_alias or proveedor_lista

        if not proveedor_final and proveedor_libre:
            if proveedor_libre not in PROVEEDORES_INVALIDOS:
                proveedor_final = proveedor_libre



        # --------------------------
        # SUGERENCIAS si falta "compras"
        # --------------------------
        if not menciona_compras:
            # Ej: "comparar 2025" -> sugerir explícito "comparar compras ..."
            if len(anios) == 1:
                y = anios[0]
                sug = f"Te falta el segundo año. Probá: comparar compras {y-1} {y}"
            else:
                sug = "Probá: comparar compras roche 2024 2025 | comparar compras tresul 2024 2025"
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": sug,
                "debug": "comparar: falta palabra 'compras'",
            }

        # --------------------------
        # si no hay proveedor -> sugerir
        # --------------------------
        if not proveedor_final:
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": "No reconocí el proveedor. Probá: comparar compras tresul 2024 2025 | comparar compras biodiagnostico 2024 2025",
                "debug": "comparar: proveedor no reconocido",
            }

        # ==========================================================
        # 1) mes vs mes (YYYY-MM)
        # ==========================================================
        if len(meses_yyyymm) >= 2:
            mes1, mes2 = meses_yyyymm[0], meses_yyyymm[1]
            return {
                "tipo": "comparar_proveedor_meses",
                "parametros": {
                    # compat: algunos flujos usan 'proveedor', otros 'proveedores'
                    "proveedor": proveedor_final,
                    "proveedores": [proveedor_final],
                    "mes1": mes1,
                    "mes2": mes2,
                    "label1": mes1,
                    "label2": mes2,
                },
                "debug": "comparar proveedor meses (YYYY-MM)",
            }

        # ==========================================================
        # 2) mes vs mes (nombre + año)
        # ==========================================================
        if len(meses_nombre) >= 2 and len(anios) >= 1:
            anio = anios[0]
            mes1 = _to_yyyymm(anio, meses_nombre[0])
            mes2 = _to_yyyymm(anio, meses_nombre[1])
            return {
                "tipo": "comparar_proveedor_meses",
                "parametros": {
                    "proveedor": proveedor_final,
                    "proveedores": [proveedor_final],
                    "mes1": mes1,
                    "mes2": mes2,
                    "label1": f"{meses_nombre[0]} {anio}",
                    "label2": f"{meses_nombre[1]} {anio}",
                },
                "debug": "comparar proveedor meses (nombre+anio)",
            }

        # ==========================================================
        # 3) año vs año
        # ==========================================================
        if len(anios) >= 2:
            return {
                "tipo": "comparar_proveedor_anios",
                "parametros": {
                    "proveedor": proveedor_final,
                    "proveedores": [proveedor_final],  # CLAVE para SQL que espera lista
                    "anios": [anios[0], anios[1]],
                },
                "debug": "comparar proveedor años",
            }

        # ==========================================================
        # Sugerencias cuando falta el "qué comparar"
        # ==========================================================
        if len(anios) == 1:
            y = anios[0]
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": f"Te falta el segundo año. Probá: comparar compras {proveedor_final} {y-1} {y}",
                "debug": "comparar: solo un año",
            }

        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": f"Probá: comparar compras {proveedor_final} 2024 2025 | comparar compras {proveedor_final} junio julio 2025",
            "debug": "comparar: faltan meses/años",
        }

    # ==========================================================
    # FALLBACK FINAL
    # ==========================================================
    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: comparar compras roche 2024 2025 | comparar compras tresul 2024 2025",
        "debug": "comparar: no match",
    }
