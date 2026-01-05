# =========================
# IA_INTERPRETADOR.PY - CANÓNICO (DETECCIÓN BD + COMPARATIVAS)
# =========================

import os
import re
import json
import unicodedata
from typing import Dict, Optional, List, Tuple
from datetime import datetime

import streamlit as st
from openai import OpenAI
from config import OPENAI_MODEL

# =====================================================================
# CONFIGURACIÓN OPENAI (opcional)
# =====================================================================
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Si querés “sacar OpenAI” para datos: dejalo False (recomendado).
USAR_OPENAI_PARA_DATOS = False

# =====================================================================
# REGLAS FIJAS
# =====================================================================
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
# EJEMPLOS DE PROVEEDORES (CANÓNICOS OBLIGATORIOS)
# - ROCHE: roche, roche laboratorio, roche diagnostics,
#          roche international, roche international ltd
# - BIODIAGNOSTICO: biodiagnostico, biodiagnóstico,
#                   cabinsur, cabin sur, cabinsur srl
# - TRESUL: tresul, tresul s.a, laboratorio tresul
# =====================================================================

# =====================================================================
# TABLA DE TIPOS
# =====================================================================
TABLA_TIPOS = """
| TIPO | DESCRIPCIÓN | PARÁMETROS | EJEMPLOS |
|------|-------------|------------|----------|
| compras_anio | Todas las compras de un año | anio | "compras 2025" |
| compras_mes | Todas las compras de un mes | mes (YYYY-MM) | "compras noviembre 2025" |
| compras_proveedor_anio | Compras de un proveedor en un año | proveedor, anio | "compras roche 2025" |
| compras_proveedor_mes | Compras de un proveedor en un mes | proveedor, mes (YYYY-MM) | "compras roche noviembre 2025" |
| comparar_proveedor_meses | Comparar proveedor mes vs mes | proveedor, mes1, mes2, label1, label2 | "comparar compras roche junio julio 2025" |
| comparar_proveedor_anios | Comparar proveedor año vs año | proveedor, anios | "comparar compras roche 2024 2025" |
| ultima_factura | Última factura de un artículo/proveedor | patron | "ultima factura vitek" |
| facturas_articulo | Todas las facturas de un artículo | articulo | "cuando vino vitek" |
| stock_total | Resumen total de stock | (ninguno) | "stock total" |
| stock_articulo | Stock de un artículo | articulo | "stock vitek" |
| conversacion | Saludos | (ninguno) | "hola", "gracias" |
| conocimiento | Preguntas generales | (ninguno) | "que es HPV" |
| no_entendido | No se entiende | sugerencia | - |
"""

# =====================================================================
# TABLA CANÓNICA (50 combinaciones) - guía para IA (si se usa)
# =====================================================================
# =====================================================================
# TABLA CANÓNICA (50 combinaciones permitidas) - PARA GUIAR A LA IA
# (No rompe nada: es guía / contrato mental del intérprete)
# =====================================================================

TABLA_CANONICA_50 = r"""
| # | ACCIÓN | OBJETO | TIEMPO | MULTI | TIPO (output) | PARAMS |
|---|--------|--------|--------|-------|---------------|--------|
| 01 | compras | (ninguno) | anio | no | compras_anio | anio |
| 02 | compras | (ninguno) | mes | no | compras_mes | mes |
| 03 | compras | proveedor | anio | no | compras_proveedor_anio | proveedor, anio |
| 04 | compras | proveedor | mes | no | compras_proveedor_mes | proveedor, mes |
| 05 | compras | proveedor | mes | si (<=5) | compras_proveedor_mes | proveedor(s), mes |
| 06 | compras | proveedor | anio | si (<=5) | compras_proveedor_anio | proveedor(s), anio |
| 07 | compras | (ninguno) | meses | si (<=6) | compras_mes | mes(s) |
| 08 | compras | (ninguno) | anios | si (<=4) | compras_anio | anio(s) |
| 09 | compras | articulo | (ninguno) | no | facturas_articulo | articulo |
| 10 | compras | articulo | anio | no | facturas_articulo | articulo (+ filtro anio si existiera) |
| 11 | compras | articulo | mes | no | facturas_articulo | articulo (+ filtro mes si existiera) |
| 12 | stock | (ninguno) | (ninguno) | no | stock_total | - |
| 13 | stock | articulo | (ninguno) | no | stock_articulo | articulo |
| 14 | ultima_factura | articulo | (ninguno) | no | ultima_factura | patron |
| 15 | ultima_factura | proveedor | (ninguno) | no | ultima_factura | patron |
| 16 | comparar | proveedor | mes+mes (mismo anio) | no | comparar_proveedor_meses | proveedor, mes1, mes2, label1, label2 |
| 17 | comparar | proveedor | anio+anio | no | comparar_proveedor_anios | proveedor, anios |
| 18 | comparar compras | proveedor | mes+mes | no | comparar_proveedor_meses | proveedor, mes1, mes2 |
| 19 | comparar compras | proveedor | anio+anio | no | comparar_proveedor_anios | proveedor, anios |
| 20 | comparar | proveedor+proveedor | mismo mes | si (<=5) | compras_proveedor_mes | proveedor(s), mes |
| 21 | comparar | proveedor+proveedor | mismo anio | si (<=5) | compras_proveedor_anio | proveedor(s), anio |
| 22 | comparar | proveedor | meses (lista) | si (<=6) | comparar_proveedor_meses | proveedor, mes1, mes2 (si hay 2) |
| 23 | comparar | proveedor | anios (lista) | si (<=4) | comparar_proveedor_anios | proveedor, anios |
| 24 | compras | proveedor | "este mes" | no | compras_proveedor_mes | proveedor, mes(actual) |
| 25 | compras | (ninguno) | "este mes" | no | compras_mes | mes(actual) |
| 26 | compras | proveedor | "este anio" | no | compras_proveedor_anio | proveedor, anio(actual) |
| 27 | compras | (ninguno) | "este anio" | no | compras_anio | anio(actual) |
| 28 | compras | proveedor | mes (YYYY-MM) | no | compras_proveedor_mes | proveedor, mes |
| 29 | compras | (ninguno) | mes (YYYY-MM) | no | compras_mes | mes |
| 30 | comparar compras | proveedor | mes(YYYY-MM)+mes(YYYY-MM) | no | comparar_proveedor_meses | proveedor, mes1, mes2 |
| 31 | comparar compras | proveedor | anio+anio | no | comparar_proveedor_anios | proveedor, anios |
| 32 | compras | proveedor | "noviembre 2025" | no | compras_proveedor_mes | proveedor, 2025-11 |
| 33 | compras | (ninguno) | "noviembre 2025" | no | compras_mes | 2025-11 |
| 34 | comparar compras | proveedor | "junio julio 2025" | no | comparar_proveedor_meses | proveedor, 2025-06, 2025-07 |
| 35 | comparar compras | proveedor | "noviembre diciembre 2025" | no | comparar_proveedor_meses | proveedor, 2025-11, 2025-12 |
| 36 | comparar compras | proveedor | "2024 2025" | no | comparar_proveedor_anios | proveedor, [2024,2025] |
| 37 | compras | proveedor | "2025" | no | compras_proveedor_anio | proveedor, 2025 |
| 38 | compras | proveedor | "enero 2026" | no | compras_proveedor_mes | proveedor, 2026-01 |
| 39 | compras | proveedor | "enero" (sin año) | no | compras_proveedor_mes | proveedor, mes(actual o pedir año) |
| 40 | compras | (ninguno) | "enero" (sin año) | no | compras_mes | mes(actual o pedir año) |
| 41 | comparar compras | proveedor | "enero febrero" (sin año) | no | comparar_proveedor_meses | proveedor, pedir año |
| 42 | compras | proveedor | rango meses | si | compras_proveedor_mes | proveedor, mes(s) |
| 43 | compras | proveedor | rango anios | si | compras_proveedor_anio | proveedor, anio(s) |
| 44 | compras | proveedor+proveedor | mes | si | compras_proveedor_mes | proveedor(s), mes |
| 45 | compras | proveedor+proveedor | anio | si | compras_proveedor_anio | proveedor(s), anio |
| 46 | comparar | proveedor | mes vs mes | no | comparar_proveedor_meses | proveedor, mes1, mes2 |
| 47 | comparar | proveedor | anio vs anio | no | comparar_proveedor_anios | proveedor, anios |
| 48 | stock | proveedor | (ninguno) | no | no_entendido | sugerir: "compras proveedor ..." |
| 49 | compras | articulo | (texto libre) | no | facturas_articulo | articulo |
| 50 | no | (ambiguo) | (ambiguo) | - | no_entendido | sugerencia |
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
    raw = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]+", texto.lower())
    out = []
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

    # Dedup
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

    # ==========================================================
    # 1) PRIORIDAD ABSOLUTA: MATCH EXACTO
    # ==========================================================
    toks_set = set(toks)
    for orig, norm in index:
        if norm in toks_set:
            return [orig]

    # ==========================================================
    # 2) FALLBACK: substring + score (lógica original)
    # ==========================================================
    candidatos: List[Tuple[int, str]] = []
    for orig, norm in index:
        for tk in toks:
            if tk and tk in norm:
                score = (len(tk) * 1000) - len(norm)
                candidatos.append((score, orig))

    if not candidatos:
        return []

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


# =====================================================================
# RESOLUCIÓN FINAL: PROVEEDOR → SI NO, ARTÍCULO
# =====================================================================
def detectar_proveedor_o_articulo(texto: str) -> Dict[str, List[str]]:
    prov_index, art_index = _get_indices()

    proveedores = _match_best(texto, prov_index, max_items=1)
    if proveedores:
        return {
            "tipo": "proveedor",
            "valores": proveedores,
        }

    articulos = _match_best(texto, art_index, max_items=1)
    if articulos:
        return {
            "tipo": "articulo",
            "valores": articulos,
        }

    return {
        "tipo": "ninguno",
        "valores": [],
    }


# =====================================================================
# PARSEO TIEMPO
# =====================================================================
def _extraer_anios(texto: str) -> List[int]:
    anios = re.findall(r"(2023|2024|2025|2026)", texto)
    out = []
    for a in anios:
        try:
            out.append(int(a))
        except Exception:
            pass
    # unique orden
    seen = set()
    out2 = []
    for x in out:
        if x not in seen:
            seen.add(x)
            out2.append(x)
    return out2[:MAX_ANIOS]

def _extraer_meses_nombre(texto: str) -> List[str]:
    ms = [m for m in MESES.keys() if m in texto.lower()]
    seen = set()
    out = []
    for m in ms:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out[:MAX_MESES]

def _extraer_meses_yyyymm(texto: str) -> List[str]:
    # acepta 2025-06 o 2025/06
    ms = re.findall(r"(2023|2024|2025|2026)[-/](0[1-9]|1[0-2])", texto)
    out = [f"{a}-{m}" for a, m in ms]
    seen = set()
    out2 = []
    for x in out:
        if x not in seen:
            seen.add(x)
            out2.append(x)
    return out2[:MAX_MESES]

def _to_yyyymm(anio: int, mes_nombre: str) -> str:
    return f"{anio}-{MESES[mes_nombre]}"

# =====================================================================
# PROMPT OpenAI (solo si lo habilitás)
# =====================================================================
def _get_system_prompt() -> str:
    hoy = datetime.now()
    mes_actual = hoy.strftime("%Y-%m")
    anio_actual = hoy.year
    return f"""
Eres un intérprete de consultas.
- Mes SIEMPRE YYYY-MM.
- Años válidos: 2023–2026.
- Devuelve SOLO JSON: tipo, parametros, debug/sugerencia si aplica.

TABLA TIPOS:
{TABLA_TIPOS}

CANÓNICA:
{TABLA_CANONICA_50}

FECHA: {hoy.strftime("%Y-%m-%d")} (mes actual {mes_actual}, año {anio_actual})
""".strip()

# =====================================================================
# INTERPRETADOR PRINCIPAL
# =====================================================================
def interpretar_pregunta(pregunta: str) -> Dict:
    if not pregunta or not pregunta.strip():
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "Escribí una consulta.",
            "debug": "pregunta vacía",
        }

    texto = pregunta.strip()
    texto_lower = texto.lower().strip()

    # -------- conversacion (solo si es "solo saludo") --------
    saludos_simples = {
        "hola", "hola!", "hey", "hey!",
        "buenos dias", "buen día", "buenas tardes", "buenas noches",
        "gracias", "chau", "adios", "buenas"
    }
    if texto_lower in saludos_simples:
        return {"tipo": "conversacion", "parametros": {}, "debug": "saludo simple"}

    # -------- conocimiento --------
    if any(x in texto_lower for x in ["que es ", "qué es ", "para que sirve", "para qué sirve", "como funciona", "cómo funciona"]) and \
       not any(k in texto_lower for k in ["compra", "compras", "stock", "factura", "proveedor", "gasto", "familia", "comparar"]):
        return {"tipo": "conocimiento", "parametros": {}, "debug": "pregunta de conocimiento"}

    # Cargar índices BD
    idx_prov, idx_art = _get_indices()
    provs = _match_best(texto_lower, idx_prov, max_items=MAX_PROVEEDORES)
    arts = _match_best(texto_lower, idx_art, max_items=MAX_ARTICULOS)

    anios = _extraer_anios(texto_lower)
    meses_nombre = _extraer_meses_nombre(texto_lower)
    meses_yyyymm = _extraer_meses_yyyymm(texto_lower)

# ==========================================================
# COMPARAR COMPRAS PROVEEDOR MES VS MES
# - comparar compras roche junio julio 2025
# - comparar compras roche 2025-06 2025-07
# ==========================================================
if "comparar" in texto_lower and "compra" in texto_lower:
    proveedor = provs[0] if provs else None

    # ==========================================================
    # FALLBACK: proveedor libre (si no matcheó índice)
    # ==========================================================
    proveedor_libre = None
    if not proveedor:
        tmp = texto_lower
        tmp = re.sub(r"(comparar|compras?)", "", tmp)
        tmp = re.sub(
            r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)",
            "",
            tmp
        )
        tmp = re.sub(r"(2023|2024|2025|2026)", "", tmp)
        tmp = tmp.strip()
        if tmp and len(tmp) >= 3:
            proveedor_libre = tmp

    proveedor_final = proveedor or proveedor_libre

    if not proveedor_final:
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "No reconocí el proveedor. Probá: comparar compras roche junio julio 2025",
            "debug": "comparar: proveedor no reconocido (ni índice ni libre)",
        }

    # ==========================================================
    # meses explícitos YYYY-MM
    # ==========================================================
    if len(meses_yyyymm) >= 2:
        mes1, mes2 = meses_yyyymm[0], meses_yyyymm[1]
        return {
            "tipo": "comparar_proveedor_meses",
            "parametros": {
                "proveedor": proveedor_final,
                "mes1": mes1,
                "mes2": mes2,
                "label1": mes1,  # ← ✅ AGREGAR LABELS
                "label2": mes2,  # ← ✅ AGREGAR LABELS
            },
            "debug": "comparar proveedor meses (YYYY-MM)",
        }

    # ==========================================================
    # meses por nombre + año
    # ==========================================================
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
                "label1": f"{meses_nombre[0]} {anio}",  # ← ✅ LABEL LEGIBLE
                "label2": f"{meses_nombre[1]} {anio}",  # ← ✅ LABEL LEGIBLE
            },
            "debug": "comparar proveedor meses (nombre+anio)",
        }

    # ==========================================================
    # comparar por años
    # ==========================================================
    if len(anios) >= 2:
        return {
            "tipo": "comparar_proveedor_anios",
            "parametros": {
                "proveedor": proveedor_final,
                "anios": [anios[0], anios[1]],
            },
            "debug": "comparar proveedor años",
        }

    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: comparar compras roche junio julio 2025",
        "debug": "comparar: faltan meses/año",
    }
    
    # ==========================================================
    # COMPRAS
    # - compras roche noviembre 2025  => compras_proveedor_mes
    # - compras noviembre 2025        => compras_mes
    # - compras roche 2025            => compras_proveedor_anio
    # - compras 2025                  => compras_anio
    # ==========================================================
    if "compra" in texto_lower or "compras" in texto_lower:
        proveedor = provs[0] if provs else None

        # ==========================================================
        # FALLBACK: proveedor libre (si no matcheó índice)
        # ==========================================================
        proveedor_libre = None
        if not proveedor:
            tmp = texto_lower
            tmp = re.sub(r"(compras?|comparar)", "", tmp)
            tmp = re.sub(
                r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)",
                "",
                tmp
            )
            tmp = re.sub(r"(2023|2024|2025|2026)", "", tmp)
            tmp = tmp.strip()
            if tmp and len(tmp) >= 3:
                proveedor_libre = tmp

        proveedor_final = proveedor or proveedor_libre

        # ==========================================================
        # proveedor + mes (YYYY-MM)
        # ==========================================================
        if proveedor_final and len(meses_yyyymm) >= 1:
            return {
                "tipo": "compras_proveedor_mes",
                "parametros": {
                    "proveedor": proveedor_final,
                    "mes": meses_yyyymm[0]
                },
                "debug": "compras proveedor mes (YYYY-MM)",
            }

        # ==========================================================
        # proveedor + mes (nombre) + año
        # ==========================================================
        if proveedor_final and len(meses_nombre) >= 1 and len(anios) >= 1:
            anio = anios[0]
            mes = _to_yyyymm(anio, meses_nombre[0])
            return {
                "tipo": "compras_proveedor_mes",
                "parametros": {
                    "proveedor": proveedor_final,
                    "mes": mes
                },
                "debug": "compras proveedor mes (nombre+anio)",
            }

        # ==========================================================
        # proveedor + año
        # ==========================================================
        if proveedor_final and len(anios) >= 1 and len(meses_nombre) == 0 and len(meses_yyyymm) == 0:
            anio = anios[0]
            return {
                "tipo": "compras_proveedor_anio",
                "parametros": {
                    "proveedor": proveedor_final,
                    "anio": anio
                },
                "debug": "compras proveedor año",
            }

        # ==========================================================
        # compras por mes (sin proveedor)
        # ==========================================================
        if not proveedor_final and len(meses_yyyymm) >= 1:
            return {
                "tipo": "compras_mes",
                "parametros": {"mes": meses_yyyymm[0]},
                "debug": "compras mes (YYYY-MM)",
            }

        if not proveedor_final and len(meses_nombre) >= 1 and len(anios) >= 1:
            mes = _to_yyyymm(anios[0], meses_nombre[0])
            return {
                "tipo": "compras_mes",
                "parametros": {"mes": mes},
                "debug": "compras mes (nombre+anio)",
            }

        # ==========================================================
        # compras por año (sin proveedor)
        # ==========================================================
        if not proveedor_final and len(anios) >= 1:
            return {
                "tipo": "compras_anio",
                "parametros": {"anio": anios[0]},
                "debug": "compras año",
            }

    # ==========================================================
    # STOCK
    # ==========================================================
    if "stock" in texto_lower:
        if arts:
            return {"tipo": "stock_articulo", "parametros": {"articulo": arts[0]}, "debug": "stock articulo (bd)"}
        return {"tipo": "stock_total", "parametros": {}, "debug": "stock total"}

    # ==========================================================
    # OPENAI (opcional)
    # ==========================================================
    if client and USAR_OPENAI_PARA_DATOS:
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": _get_system_prompt()},
                    {"role": "user", "content": pregunta},
                ],
                temperature=0.1,
                max_tokens=500,
                timeout=15,
            )
            content = response.choices[0].message.content.strip()
            content = re.sub(r"```json\s*", "", content)
            content = re.sub(r"```\s*", "", content).strip()
            out = json.loads(content)
            if "tipo" not in out:
                out["tipo"] = "no_entendido"
            if "parametros" not in out:
                out["parametros"] = {}
            if "debug" not in out:
                out["debug"] = "openai"
            return out
        except Exception as e:
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": "No pude interpretar. Probá: compras roche noviembre 2025",
                "debug": f"openai error: {str(e)[:80]}",
            }

    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: compras roche noviembre 2025 | comparar compras roche junio julio 2025",
        "debug": "no match",
    }

# =====================================================================
# MAPEO TIPO → FUNCIÓN SQL (CANÓNICO)
# =====================================================================
MAPEO_FUNCIONES = {
    "compras_anio": {
        "funcion": "get_compras_anio",
        "params": ["anio"],
        "resumen": "get_total_compras_anio"
    },

    "compras_proveedor_anio": {
        "funcion": "get_detalle_compras_proveedor_anio",
        "params": ["proveedor", "anio"],
        "resumen": "get_total_compras_proveedor_anio"
    },

    "compras_proveedor_mes": {
        "funcion": "get_detalle_compras_proveedor_mes",
        "params": ["proveedor", "mes"]
    },

    "compras_mes": {
        "funcion": "get_compras_por_mes_excel",
        "params": ["mes"]
    },

    # =========================
    # COMPARATIVAS
    # =========================
    "comparar_proveedor_meses": {
        "funcion": "get_comparacion_proveedor_meses",
        "params": ["proveedor", "mes1", "mes2", "label1", "label2"]
    },

    "comparar_proveedor_anios": {
        "funcion": "get_comparacion_proveedor_anios",
        "params": ["proveedor", "anios", "label1", "label2"]
    },

    # =========================
    # OTROS
    # =========================
    "ultima_factura": {
        "funcion": "get_ultima_factura_inteligente",
        "params": ["patron"]
    },

    "facturas_articulo": {
        "funcion": "get_facturas_de_articulo",
        "params": ["articulo"]
    },

    "stock_total": {
        "funcion": "get_stock_total",
        "params": []
    },

    "stock_articulo": {
        "funcion": "get_stock_articulo",
        "params": ["articulo"]
    },
}

def obtener_info_tipo(tipo: str) -> Optional[Dict]:
    return MAPEO_FUNCIONES.get(tipo)

def es_tipo_valido(tipo: str) -> bool:
    tipos_especiales = [
        "conversacion",
        "conocimiento",
        "no_entendido",
        "comparar_proveedor_meses",
        "comparar_proveedor_anios",
    ]
    return tipo in MAPEO_FUNCIONES or tipo in tipos_especiales
