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

# Definición de restricciones o proveedores inválidos
PROVEEDORES_INVALIDOS = []

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
    return bool(re.search(rf"\b{re.escape(palabra)}\b", texto_lower))

def _tiene_alguna_palabra(texto_lower: str, palabras: List[str]) -> bool:
    return any(_tiene_palabra(texto_lower, p) for p in palabras)

# =====================================================================
# CARGA LISTAS DESDE SUPABASE (cache)
# =====================================================================
@st.cache_data(ttl=60 * 60)
def _cargar_listas_supabase() -> Dict[str, List[str]]:
    proveedores = []
    articulos = []

    try:
        from supabase_client import supabase
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

        for col in ["Descripción", "DESCRIPCIÓN", "descripcion"]:
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

    toks_set = set(toks)
    for orig, norm in index:
        if norm in toks_set:
            return [orig]

    candidatos = []
    for orig, norm in index:
        for tk in toks:
            if tk and tk in norm:
                score = (len(tk) * 1000) - len(norm)
                candidatos.append((score, orig))

    candidatos.sort(key=lambda x: (-x[0], x[1]))
    out = []
    seen = set()
    for _, orig in candidatos:
        if orig not in seen:
            seen.add(orig)
            out.append(orig)
        if len(out) >= max_items:
            break
    return out

# Resolver alias de proveedor
def _resolver_proveedor_alias(texto_lower: str, idx_prov: List[Tuple[str, str]]) -> Optional[str]:
    alias_terms = [
        "tresul",
        "laboratorio tresul",
        "biodiagnostico",
        "cabinsur",
        "roche",
    ]

    for alias_term in alias_terms:
        if alias_term in texto_lower:
            best_candidate = None
            best_score = 0
            for original_name, normalized_name in idx_prov:
                if alias_term in normalized_name:
                    score = len(alias_term) / len(normalized_name)
                    if score > best_score:
                        best_score = score
                        best_candidate = original_name
            return best_candidate
    return None

# Parseo de tiempo
def _extraer_anios(texto: str) -> List[int]:
    anios = re.findall(r"(2023|2024|2025|2026)", texto or "")
    out = []
    seen = set()
    for a in anios:
        a = int(a)
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out[:MAX_ANIOS]

def _extraer_meses_nombre(texto: str) -> List[str]:
    return list(filter(lambda m: m in texto, MESES.keys()))[:MAX_MESES]

def _extraer_meses_yyyymm(texto: str) -> List[str]:
    ms = re.findall(r"(2023|2024|2025|2026)-[0-9]{2}", texto or "")
    seen = set()
    return [x for x in ms if not (x in seen or seen.add(x))][:MAX_MESES]

def _to_yyyymm(anio: int, mes_nombre: str) -> str:
    return f"{anio}-{MESES.get(mes_nombre, '01')}"

# Extraer proveedor libre
def _extraer_proveedor_libre(texto_lower: str) -> Optional[str]:
    tmp = re.sub(r"\b(comparar|compras?|enero|febrero|202[34])\b", "", texto_lower)
    tmp = re.sub(r"[^\s]+", " ", tmp).strip()
    return tmp if tmp and len(tmp) > 3 else None

def interpretar_comparativas(pregunta: str) -> Dict:
    texto = (pregunta or "").strip().lower()
    idx_prov, _ = _get_indices()
    provs = _match_best(texto, idx_prov, MAX_PROVEEDORES)

    # Extraer alias y nombres del proveedor
    proveedor_alias = _resolver_proveedor_alias(texto, idx_prov)
    proveedor_libre = _extraer_proveedor_libre(texto)
    proveedor_final = proveedor_alias or proveedor_libre or (provs[0] if provs else None)

    if not proveedor_final or proveedor_final in PROVEEDORES_INVALIDOS:
        return {"tipo": "no_entendido", "sugerencia": "Intenta escribir el nombre completo: Tresul, Roche…"}

    # Extraer años de la pregunta
    anios = _extraer_anios(texto)
    if len(anios) < 2:
        return {"tipo": "no_entendido", "sugerencia": "Necesito al menos dos años para comparar."}

    # Retornar tipo y parámetros
    return {
        "tipo": "comparar_proveedor_anios",
        "parametros": {
            "proveedor": proveedor_final,
            "anios": anios,
        },
        "debug": f"Proveedor: {proveedor_final}, Años: {anios}"
    }

# Test
if __name__ == "__main__":
    pruebas = ["comparar compras tresul 2024 2025", "comparar compras roche 2024 2025"]
    for p in pruebas:
        print(interpretar_comparativas(p))
