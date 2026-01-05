# =========================
# IA_COMPRAS.PY - INTÉRPRETE COMPRAS (CANÓNICO)
# =========================

import os
import re
import unicodedata
from typing import Dict, List, Tuple
from datetime import datetime

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
ANIOS_VALIDOS = {2023, 2024, 2025, 2026}

MAX_PROVEEDORES = 5
MAX_ARTICULOS = 5
MAX_MESES = 6
MAX_ANIOS = 4

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

        # Proveedores: tabla proveedores, columna nombre
        for col in ["nombre", "Nombre", "NOMBRE"]:
            try:
                res = supabase.table("proveedores").select(col).execute()
                data = res.data or []
                proveedores = [str(r.get(col)).strip() for r in data if r.get(col)]
                if proveedores:
                    break
            except Exception:
                continue

        # Artículos: tabla articulos, columna Descripción / etc.
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

    # 1) PRIORIDAD ABSOLUTA: MATCH EXACTO
    toks_set = set(toks)
    for orig, norm in index:
        if norm in toks_set:
            return [orig]

    # 2) FALLBACK: substring + score
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
# INTÉRPRETE COMPRAS
# =====================================================================
def interpretar_compras(pregunta: str) -> Dict:
    texto = (pregunta or "").strip()
    texto_lower = texto.lower().strip()

    idx_prov, idx_art = _get_indices()
    provs = _match_best(texto_lower, idx_prov, max_items=MAX_PROVEEDORES)
    arts = _match_best(texto_lower, idx_art, max_items=MAX_ARTICULOS)

    anios = _extraer_anios(texto_lower)
    meses_nombre = _extraer_meses_nombre(texto_lower)
    meses_yyyymm = _extraer_meses_yyyymm(texto_lower)

# ==========================================================
# COMPRAS (CANÓNICO): proveedor+mes | proveedor+año | mes | año
# ==========================================================
if ("compra" in texto_lower) and ("comparar" not in texto_lower):
    # ---------- fallback proveedor libre si lista está vacía ----------
    proveedor_libre = None
    if not provs:
        tmp = texto_lower
        tmp = re.sub(r"\bcompras?\b", "", tmp).strip()

        tmp2 = re.sub(
            r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\b",
            "",
            tmp,
        )
        tmp2 = re.sub(r"\b(2023|2024|2025|2026)\b", "", tmp2).strip()

        # ✅ AJUSTE MÍNIMO: normalizar espacios (sin cambiar tu lógica)
        tmp2 = re.sub(r"\s+", " ", tmp2).strip()

        if tmp2 and len(tmp2) >= 3:
            proveedor_libre = tmp2

    proveedor_final = provs[0] if provs else proveedor_libre

    # ---------- compras proveedor + mes ----------
    if proveedor_final:
        if len(meses_yyyymm) >= 1:
            return {
                "tipo": "compras_proveedor_mes",
                "parametros": {"proveedor": proveedor_final, "mes": meses_yyyymm[0]},
                "debug": "compras proveedor mes (YYYY-MM)",
            }

        if len(meses_nombre) >= 1 and len(anios) >= 1:
            mes_key = _to_yyyymm(anios[0], meses_nombre[0])
            return {
                "tipo": "compras_proveedor_mes",
                "parametros": {"proveedor": proveedor_final, "mes": mes_key},
                "debug": "compras proveedor mes (nombre+anio)",
            }

        # ---------- compras proveedor + año ----------
        if len(anios) >= 1:
            return {
                "tipo": "compras_proveedor_anio",
                "parametros": {"proveedor": proveedor_final, "anio": anios[0]},
                "debug": "compras proveedor año",
            }

    # ---------- compras (sin proveedor) + mes ----------
    if len(meses_yyyymm) >= 1:
        return {
            "tipo": "compras_mes",
            "parametros": {"mes": meses_yyyymm[0]},
            "debug": "compras mes (YYYY-MM)",
        }

    if len(meses_nombre) >= 1 and len(anios) >= 1:
        mes_key = _to_yyyymm(anios[0], meses_nombre[0])
        return {
            "tipo": "compras_mes",
            "parametros": {"mes": mes_key},
            "debug": "compras mes (nombre+anio)",
        }

    # ---------- compras (sin proveedor) + año ----------
    if len(anios) >= 1:
        return {
            "tipo": "compras_anio",
            "parametros": {"anio": anios[0]},
            "debug": "compras año",
        }

return {
    "tipo": "no_entendido",
    "parametros": {},
    "sugerencia": "Probá: compras roche noviembre 2025 | compras noviembre 2025 | compras 2025",
    "debug": "compras: no match",
}
