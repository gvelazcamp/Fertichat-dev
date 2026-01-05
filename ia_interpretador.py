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
TABLA_CANONICA_50 = r"""
(la dejo igual que antes; si querés que sea literal con 50 filas, se puede, pero no afecta la lógica)
- compras + proveedor + mes
- compras + proveedor + año
- compras + mes
- compras + año
- comparar compras + proveedor + mes mes + año
- comparar compras + proveedor + año año
- stock + artículo
- stock total
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

    candidatos: List[Tuple[int, str]] = []
    for orig, norm in index:
        for tk in toks:
            if tk and tk in norm:
                # score: token largo manda, y preferimos nombre más específico
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

        # si el usuario claramente escribió un “objeto” pero no matcheó proveedor:
        # evitamos caer en compras_mes (que trae todo)
        if not proveedor:
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": "No reconocí el proveedor. Probá: compras ROCHE noviembre 2025",
                "debug": "comparar: proveedor no reconocido (bd)",
            }

        # caso YYYY-MM explícitos
        if len(meses_yyyymm) >= 2:
            mes1, mes2 = meses_yyyymm[0], meses_yyyymm[1]
            return {
                "tipo": "comparar_proveedor_meses",
                "parametros": {
                    "proveedor": proveedor,
                    "mes1": mes1,
                    "mes2": mes2,
                    "label1": mes1,
                    "label2": mes2,
                },
                "debug": "comparar proveedor meses (YYYY-MM)",
            }

        # caso meses por nombre + 1 año
        if len(meses_nombre) >= 2 and len(anios) >= 1:
            anio = anios[0]
            mes1 = _to_yyyymm(anio, meses_nombre[0])
            mes2 = _to_yyyymm(anio, meses_nombre[1])
            return {
                "tipo": "comparar_proveedor_meses",
                "parametros": {
                    "proveedor": proveedor,
                    "mes1": mes1,
                    "mes2": mes2,
                    "label1": f"{meses_nombre[0]} {anio}",
                    "label2": f"{meses_nombre[1]} {anio}",
                },
                "debug": "comparar proveedor meses (nombre+anio)",
            }

        # comparar años (si te sirve)
        if len(anios) >= 2:
            return {
                "tipo": "comparar_proveedor_anios",
                "parametros": {"proveedor": proveedor, "anios": [anios[0], anios[1]]},
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

        # proveedor + mes(YYYY-MM)
        if proveedor and len(meses_yyyymm) >= 1:
            return {
                "tipo": "compras_proveedor_mes",
                "parametros": {"proveedor": proveedor, "mes": meses_yyyymm[0]},
                "debug": "compras proveedor mes (YYYY-MM)",
            }

        # proveedor + mes(nombre) + anio
        if proveedor and len(meses_nombre) >= 1 and len(anios) >= 1:
            anio = anios[0]
            mes = _to_yyyymm(anio, meses_nombre[0])
            return {
                "tipo": "compras_proveedor_mes",
                "parametros": {"proveedor": proveedor, "mes": mes},
                "debug": "compras proveedor mes (nombre+anio)",
            }

        # proveedor + anio
        if proveedor and len(anios) >= 1 and len(meses_nombre) == 0 and len(meses_yyyymm) == 0:
            anio = anios[0]
            return {
                "tipo": "compras_proveedor_anio",
                "parametros": {"proveedor": proveedor, "anio": anio},
                "debug": "compras proveedor año",
            }

        # si el usuario escribió algo como "compras X noviembre 2025" y no matcheó proveedor:
        # evitamos traer todo.
        if not proveedor and len(meses_nombre) >= 1 and len(anios) >= 1:
            # detectamos probable “objeto” (la palabra entre compras y mes)
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": "No reconocí el proveedor. Probá escribirlo como está en la lista (ej: ROCHE).",
                "debug": "compras: mes+anio pero proveedor no reconocido (bd)",
            }

        # compras_mes
        if not proveedor and len(meses_yyyymm) >= 1:
            return {
                "tipo": "compras_mes",
                "parametros": {"mes": meses_yyyymm[0]},
                "debug": "compras mes (YYYY-MM)",
            }
        if not proveedor and len(meses_nombre) >= 1 and len(anios) >= 1:
            mes = _to_yyyymm(anios[0], meses_nombre[0])
            return {
                "tipo": "compras_mes",
                "parametros": {"mes": mes},
                "debug": "compras mes (nombre+anio)",
            }

        # compras_anio
        if not proveedor and len(anios) >= 1:
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
# MAPEO TIPO → FUNCIÓN SQL (se mantiene como estaba)
# =====================================================================
MAPEO_FUNCIONES = {
    "compras_anio": {"funcion": "get_compras_anio", "params": ["anio"], "resumen": "get_total_compras_anio"},
    "compras_proveedor_mes": {"funcion": "get_detalle_compras_proveedor_mes", "params": ["proveedor", "mes"]},
    "compras_proveedor_anio": {"funcion": "get_detalle_compras_proveedor_anio", "params": ["proveedor", "anio"], "resumen": "get_total_compras_proveedor_anio"},
    "compras_mes": {"funcion": "get_compras_por_mes_excel", "params": ["mes"]},
    "ultima_factura": {"funcion": "get_ultima_factura_inteligente", "params": ["patron"]},
    "facturas_articulo": {"funcion": "get_facturas_de_articulo", "params": ["articulo"]},
    "stock_total": {"funcion": "get_stock_total", "params": []},
    "stock_articulo": {"funcion": "get_stock_articulo", "params": ["articulo"]},
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
