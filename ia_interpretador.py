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
# NUEVO: EXCLUSIÓN DE NOMBRES PERSONALES (AGREGADO)
# - Evita que "gonzalo ..." se tome como proveedor
# =====================================================================
NOMBRES_PERSONALES_EXCLUIR = [
    "gonzalo",
    "daniela",
    "andres",
    "sndres",   # por si lo escriben mal
    "juan",
]

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
| detalle_factura_numero | Detalle por número de factura | nro_factura | "detalle factura 273279" / "detalle factura A00273279" |
| ultima_factura | Última factura de un artículo/proveedor | patron | "ultima factura vitek" |
| facturas_articulo | Todas las facturas de un artículo | articulo | "cuando vino vitek" |
| stock_total | Resumen total de stock | (ninguno) | "stock total" |
| stock_articulo | Stock de un artículo | articulo | "stock vitek" |
| conversacion | Saludos | (ninguno) | "hola", "gracias" |
| conocimiento | Preguntas generales | (ninguno) | "que es HPV" |
| no_entendido | No se entiende | sugerencia | - |
"""

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

# =====================================================================
# NUEVO: set de keys de nombres personales (AGREGADO)
# =====================================================================
_NOMBRES_PERSONALES_KEYS = set(_key(n) for n in (NOMBRES_PERSONALES_EXCLUIR or []) if n)

def _tokens(texto: str) -> List[str]:
    raw = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]+", texto.lower())
    out: List[str] = []
    for t in raw:
        k = _key(t)
        if len(k) >= 3:
            # ✅ NUEVO: ignorar nombres personales para evitar match como proveedor
            if k in _NOMBRES_PERSONALES_KEYS:
                continue
            out.append(k)
    return out

def normalizar_texto(texto: str) -> str:
    """
    Normaliza un texto quitando acentos, ruido y palabras no relevantes.
    """
    if not texto:
        return ""

    ruido = ["gonzalo", "daniela", "andres", "sndres", "juan", "quiero", "por favor", "las", "los", "una", "un"]
    texto = texto.lower().strip()
    for r in ruido:
        texto = re.sub(fr"\b{re.escape(r)}\b", "", texto)

    texto = "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    texto = re.sub(r"[^\w\s]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto

# =====================================================================
# NUEVO: LIMPIEZA CANÓNICA (AGREGADO)
# =====================================================================
def limpiar_consulta(texto: str) -> str:
    """
    Esta función limpia el texto de entrada quitando palabras irrelevantes (ruido)
    y normaliza para que todo sea compatible con la tabla canónica.
    """
    if not texto:
        return ""

    # Convertir a minúsculas y eliminar tildes
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")

    # ✅ NUEVO: quitar nombres personales ANTES de matchear proveedor
    for nombre in NOMBRES_PERSONALES_EXCLUIR:
        texto = re.sub(rf"\b{re.escape(nombre)}\b", " ", texto)

    # Palabras irrelevantes (ruido)
    ruido = [
        "quiero", "por favor", "las", "los", "un", "una", "a", "de", "en", "para",
        "cuáles fueron", "cuales fueron", "dame", "analisis", "realizadas", "durante"
    ]
    for palabra in ruido:
        texto = re.sub(rf"\b{re.escape(palabra)}\b", " ", texto)

    # Ajustar espacios y conectores
    texto = re.sub(r"\s{2,}", " ", texto).strip()

    return texto

# =====================================================================
# NUEVO: HELPERS DE KEYWORDS (AGREGADO)
# Útil para router: si contiene "compras", mandalo acá SIEMPRE.
# =====================================================================
def contiene_compras(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return bool(re.search(r"\bcompras?\b", t))

def contiene_comparar(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return bool(re.search(r"\b(comparar|comparame|compara)\b", t))

# =====================================================================
# NUEVO: FACTURAS (AGREGADO)
# - Querés que "detalle factura ..." sea un tipo más (como compras/comparar)
# =====================================================================
def contiene_factura(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return bool(re.search(r"\b(detalle\s+)?factura(s)?\b|\bnro\.?\s*comprobante\b|\bnro\.?\s*factura\b|\bcomprobante\b", t))

def _normalizar_nro_factura(nro: str) -> str:
    nro = (nro or "").strip().upper()
    if not nro:
        return ""
    # Si viene solo número, en tu dataset suele ser A + 8 dígitos (ej: A00273279)
    if nro.isdigit() and len(nro) <= 8:
        return "A" + nro.zfill(8)
    return nro

def _extraer_nro_factura(texto: str) -> Optional[str]:
    if not texto:
        return None

    t = str(texto).strip()

    # 1) patrón: "detalle factura 273279" / "factura A00273279" / "nro comprobante 273279"
    m = re.search(
        r"\b(detalle\s+)?(factura|comprobante|nro\.?\s*comprobante|nro\.?\s*factura)\b\s*[:#-]?\s*([A-Za-z]?\d{3,})\b",
        t,
        flags=re.IGNORECASE
    )
    if m:
        raw = str(m.group(3)).strip()
        nro = _normalizar_nro_factura(raw)
        return nro or None

    # 2) patrón: si el texto ES "A00273279" (solo si viene con letra+digitos)
    if re.fullmatch(r"[A-Za-z]\d{5,}", t):
        return _normalizar_nro_factura(t)

    return None

# =====================================================================
# NUEVO: EXTRACCIÓN SIMPLE DE PARÁMETROS (AGREGADO)
# (No reemplaza tu lógica actual; queda disponible por si lo querés usar)
# =====================================================================
def extraer_parametros(texto: str) -> Dict:
    """
    Extrae los parámetros relevantes de una consulta limpia según los tipos definidos
    en la tabla canónica.
    """
    MESES_LOCAL = {
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
        "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
        "septiembre": "09", "setiembre": "09", "octubre": "10",
        "noviembre": "11", "diciembre": "12"
    }

    parametros = {
        "proveedor": None,
        "mes": None,
        "anio": None
    }

    anios = re.findall(r"(2023|2024|2025|2026)", texto)
    if anios:
        parametros["anio"] = int(anios[0])

    for mes_nombre, mes_num in MESES_LOCAL.items():
        if mes_nombre in texto:
            parametros["mes"] = mes_num
            break

    PROVEEDORES = ["roche", "biodiagnostico", "tresul"]
    for proveedor in PROVEEDORES:
        if proveedor in texto:
            parametros["proveedor"] = proveedor
            break

    return parametros

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
# RESOLUCIÓN FINAL: PROVEEDOR → SI NO, ARTÍCULO
# =====================================================================
def detectar_proveedor_o_articulo(texto: str) -> Dict[str, List[str]]:
    prov_index, art_index = _get_indices()

    proveedores = _match_best(texto, prov_index, max_items=1)
    if proveedores:
        return {"tipo": "proveedor", "valores": proveedores}

    articulos = _match_best(texto, art_index, max_items=1)
    if articulos:
        return {"tipo": "articulo", "valores": articulos}

    return {"tipo": "ninguno", "valores": []}

# =====================================================================
# PARSEO TIEMPO
# =====================================================================
def _extraer_anios(texto: str) -> List[int]:
    anios = re.findall(r"(2023|2024|2025|2026)", texto)
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
    ms = [m for m in MESES.keys() if m in texto.lower()]
    seen = set()
    out: List[str] = []
    for m in ms:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out[:MAX_MESES]

def _extraer_meses_yyyymm(texto: str) -> List[str]:
    ms = re.findall(r"(2023|2024|2025|2026)[-/](0[1-9]|1[0-2])", texto)
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
# OPENAI (opcional) - SOLO COMO FALLBACK (CORRECTO)
# =====================================================================
def _interpretar_con_openai(pregunta: str) -> Optional[Dict]:
    if not (client and USAR_OPENAI_PARA_DATOS):
        return None

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _get_system_prompt()},
                {"role": "user", "content": pregunta},
            ],
            temperature=0.1,
            max_tokens=500,
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

    except Exception:
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "No pude interpretar. Probá: compras roche noviembre 2025",
            "debug": "openai error",
        }

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

    # NUEVO: aplicar limpieza canónica sin romper la lógica
    texto_original = pregunta.strip()
    texto_limpio = limpiar_consulta(texto_original)

    texto_lower_original = texto_original.lower().strip()
    texto_lower = texto_limpio.lower().strip()

    # ✅ REGLA: detectar "factura" como intención propia (igual que compras/comparar)
    flag_factura = contiene_factura(texto_lower_original) or contiene_factura(texto_lower)
    nro_factura = _extraer_nro_factura(texto_original) if flag_factura else None
    if nro_factura:
        return {
            "tipo": "detalle_factura_numero",
            "parametros": {"nro_factura": nro_factura},
            "debug": f"detalle factura detectado ({nro_factura})",
        }

    # ✅ REGLA: si el original contiene "compras", debe entrar acá igual
    flag_compras = contiene_compras(texto_lower_original) or contiene_compras(texto_lower)
    flag_comparar = contiene_comparar(texto_lower_original) or contiene_comparar(texto_lower)

    idx_prov, idx_art = _get_indices()
    provs = _match_best(texto_lower, idx_prov, max_items=MAX_PROVEEDORES)
    arts = _match_best(texto_lower, idx_art, max_items=MAX_ARTICULOS)

    anios = _extraer_anios(texto_lower)
    meses_nombre = _extraer_meses_nombre(texto_lower)
    meses_yyyymm = _extraer_meses_yyyymm(texto_lower)

    # ==========================================================
    # COMPRAS (CANÓNICO): proveedor+mes | proveedor+año | mes | año
    # ==========================================================
    if flag_compras and (not flag_comparar):
        proveedor_libre = None
        if not provs:
            tmp = texto_lower
            tmp = re.sub(r"\bcompras?\b", "", tmp).strip()

            tmp2 = re.sub(
                r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\b",
                "",
                tmp
            )
            tmp2 = re.sub(r"\b(2023|2024|2025|2026)\b", "", tmp2).strip()

            if tmp2 and len(tmp2) >= 3:
                proveedor_libre = tmp2

        proveedor_final = provs[0] if provs else proveedor_libre

        # compras proveedor + mes
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

            # compras proveedor + año
            if len(anios) >= 1:
                return {
                    "tipo": "compras_proveedor_anio",
                    "parametros": {"proveedor": proveedor_final, "anio": anios[0]},
                    "debug": "compras proveedor año",
                }

        # compras (sin proveedor) + mes
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

        # compras (sin proveedor) + año
        if len(anios) >= 1:
            return {
                "tipo": "compras_anio",
                "parametros": {"anio": anios[0]},
                "debug": "compras año",
            }

    # ==========================================================
    # COMPARAR COMPRAS PROVEEDOR MES VS MES / AÑO VS AÑO
    # ==========================================================
    if flag_comparar and flag_compras:
        proveedor = provs[0] if provs else None

        if not proveedor:
            tmp = re.sub(r"(comparar|comparame|compara|compras?)", "", texto_lower)
            tmp = re.sub(
                r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)",
                "",
                tmp
            )
            tmp = re.sub(r"(2023|2024|2025|2026)", "", tmp).strip()
            if len(tmp) >= 2:
                proveedor = tmp

        if not proveedor:
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": "No encontré al proveedor, intentá: comparar compras roche junio julio 2025.",
                "debug": f"Proveedor='{proveedor}', texto={texto_lower}",
            }

        # Caso 1: meses YYYY-MM
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
                "debug": "Comparando meses en formato YYYY-MM.",
            }

        # Caso 2: meses por nombre + año
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
                "debug": "Comparando meses por nombre y año explícito.",
            }

        # Caso 3: años
        if len(anios) >= 2:
            a1, a2 = anios[0], anios[1]
            return {
                "tipo": "comparar_proveedor_anios",
                "parametros": {
                    "proveedor": proveedor,
                    "anios": [a1, a2],
                    "label1": str(a1),
                    "label2": str(a2),
                },
                "debug": "Comparando diferentes años.",
            }

        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "Intentá: comparar compras roche junio julio 2025 o comparar compras roche 2024 2025.",
            "debug": f"Condiciones insuficientes: años={anios}, meses={meses_nombre}",
        }

    # ==========================================================
    # STOCK
    # ==========================================================
    if "stock" in texto_lower:
        if arts:
            return {
                "tipo": "stock_articulo",
                "parametros": {"articulo": arts[0]},
                "debug": "stock articulo",
            }
        return {
            "tipo": "stock_total",
            "parametros": {},
            "debug": "stock total",
        }

    # ==========================================================
    # DEFAULT (si está habilitado OpenAI, intenta fallback; si no, no_entendido)
    # ==========================================================
    out_ai = _interpretar_con_openai(texto_original)
    if out_ai:
        return out_ai

    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: compras roche noviembre 2025 | comparar compras roche junio julio 2025 | detalle factura 273279",
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
    # FACTURAS (AGREGADO)
    # =========================
    "detalle_factura_numero": {
        "funcion": "get_detalle_factura_por_numero",
        "params": ["nro_factura"]
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
    return tipo in MAPEO_FUNCIONES or tipo in tipos_especiales    # =========================
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
# NUEVO: EXCLUSIÓN DE NOMBRES PERSONALES (AGREGADO)
# - Evita que "gonzalo ..." se tome como proveedor
# =====================================================================
NOMBRES_PERSONALES_EXCLUIR = [
    "gonzalo",
    "daniela",
    "andres",
    "sndres",   # por si lo escriben mal
    "juan",
]

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
| detalle_factura_numero | Detalle de factura por número | nro_factura | "detalle factura A00273279" / "factura 27379" |
| ultima_factura | Última factura de un artículo/proveedor | patron | "ultima factura vitek" |
| facturas_articulo | Todas las facturas de un artículo | articulo | "cuando vino vitek" |
| stock_total | Resumen total de stock | (ninguno) | "stock total" |
| stock_articulo | Stock de un artículo | articulo | "stock vitek" |
| conversacion | Saludos | (ninguno) | "hola", "gracias" |
| conocimiento | Preguntas generales | (ninguno) | "que es HPV" |
| no_entendido | No se entiende | sugerencia | - |
"""

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

# =====================================================================
# NUEVO: set de keys de nombres personales (AGREGADO)
# =====================================================================
_NOMBRES_PERSONALES_KEYS = set(_key(n) for n in (NOMBRES_PERSONALES_EXCLUIR or []) if n)

def _tokens(texto: str) -> List[str]:
    raw = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]+", texto.lower())
    out: List[str] = []
    for t in raw:
        k = _key(t)
        if len(k) >= 3:
            # ✅ NUEVO: ignorar nombres personales para evitar match como proveedor
            if k in _NOMBRES_PERSONALES_KEYS:
                continue
            out.append(k)
    return out

def normalizar_texto(texto: str) -> str:
    """
    Normaliza un texto quitando acentos, ruido y palabras no relevantes.
    """
    if not texto:
        return ""

    ruido = ["gonzalo", "daniela", "andres", "sndres", "juan", "quiero", "por favor", "las", "los", "una", "un"]
    texto = texto.lower().strip()
    for r in ruido:
        texto = re.sub(fr"\b{re.escape(r)}\b", "", texto)

    texto = "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    texto = re.sub(r"[^\w\s]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto

# =====================================================================
# NUEVO: LIMPIEZA CANÓNICA (AGREGADO)
# =====================================================================
def limpiar_consulta(texto: str) -> str:
    """
    Esta función limpia el texto de entrada quitando palabras irrelevantes (ruido)
    y normaliza para que todo sea compatible con la tabla canónica.
    """
    if not texto:
        return ""

    # Convertir a minúsculas y eliminar tildes
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")

    # ✅ NUEVO: quitar nombres personales ANTES de matchear proveedor
    for nombre in NOMBRES_PERSONALES_EXCLUIR:
        texto = re.sub(rf"\b{re.escape(nombre)}\b", " ", texto)

    # Palabras irrelevantes (ruido)
    ruido = [
        "quiero", "por favor", "las", "los", "un", "una", "a", "de", "en", "para",
        "cuáles fueron", "cuales fueron", "dame", "analisis", "realizadas", "durante"
    ]
    for palabra in ruido:
        texto = re.sub(rf"\b{re.escape(palabra)}\b", " ", texto)

    # Ajustar espacios y conectores
    texto = re.sub(r"\s{2,}", " ", texto).strip()

    return texto

# =====================================================================
# NUEVO: HELPERS DE KEYWORDS (AGREGADO)
# Útil para router: si contiene "compras", mandalo acá SIEMPRE.
# =====================================================================
def contiene_compras(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return bool(re.search(r"\bcompras?\b", t))

def contiene_comparar(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return bool(re.search(r"\b(comparar|comparame|compara)\b", t))

# =====================================================================
# NUEVO: EXTRACCIÓN SIMPLE DE PARÁMETROS (AGREGADO)
# (No reemplaza tu lógica actual; queda disponible por si lo querés usar)
# =====================================================================
def extraer_parametros(texto: str) -> Dict:
    """
    Extrae los parámetros relevantes de una consulta limpia según los tipos definidos
    en la tabla canónica.
    """
    MESES_LOCAL = {
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
        "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
        "septiembre": "09", "setiembre": "09", "octubre": "10",
        "noviembre": "11", "diciembre": "12"
    }

    parametros = {
        "proveedor": None,
        "mes": None,
        "anio": None
    }

    anios = re.findall(r"(2023|2024|2025|2026)", texto)
    if anios:
        parametros["anio"] = int(anios[0])

    for mes_nombre, mes_num in MESES_LOCAL.items():
        if mes_nombre in texto:
            parametros["mes"] = mes_num
            break

    PROVEEDORES = ["roche", "biodiagnostico", "tresul"]
    for proveedor in PROVEEDORES:
        if proveedor in texto:
            parametros["proveedor"] = proveedor
            break

    return parametros

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
# RESOLUCIÓN FINAL: PROVEEDOR → SI NO, ARTÍCULO
# =====================================================================
def detectar_proveedor_o_articulo(texto: str) -> Dict[str, List[str]]:
    prov_index, art_index = _get_indices()

    proveedores = _match_best(texto, prov_index, max_items=1)
    if proveedores:
        return {"tipo": "proveedor", "valores": proveedores}

    articulos = _match_best(texto, art_index, max_items=1)
    if articulos:
        return {"tipo": "articulo", "valores": articulos}

    return {"tipo": "ninguno", "valores": []}

# =====================================================================
# PARSEO TIEMPO
# =====================================================================
def _extraer_anios(texto: str) -> List[int]:
    anios = re.findall(r"(2023|2024|2025|2026)", texto)
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
    ms = [m for m in MESES.keys() if m in texto.lower()]
    seen = set()
    out: List[str] = []
    for m in ms:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out[:MAX_MESES]

def _extraer_meses_yyyymm(texto: str) -> List[str]:
    ms = re.findall(r"(2023|2024|2025|2026)[-/](0[1-9]|1[0-2])", texto)
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
# NUEVO: EXTRACTOR NRO FACTURA (AGREGADO)
# - Soporta: "detalle factura A00273279", "factura 273279", "A00273279"
# - Normaliza: "273279" -> "A00273279" (A + zfill(8))
# =====================================================================
def _extraer_nro_factura(texto: str) -> Optional[str]:
    if not texto:
        return None

    t = str(texto).strip()

    m = re.search(r"\b(detalle\s+)?factura\b\s*[:#-]?\s*([A-Za-z]?\d{3,})\b", t, flags=re.IGNORECASE)
    if m:
        nro = str(m.group(2)).strip().upper()
        if nro.isdigit() and len(nro) <= 8:
            nro = "A" + nro.zfill(8)
        return nro

    if re.fullmatch(r"[A-Za-z]?\d{3,}", t):
        nro = t.upper()
        if nro.isdigit() and len(nro) <= 8:
            nro = "A" + nro.zfill(8)
        return nro

    return None
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
# OPENAI (opcional) - SOLO COMO FALLBACK (CORRECTO)
# =====================================================================
def _interpretar_con_openai(pregunta: str) -> Optional[Dict]:
    if not (client and USAR_OPENAI_PARA_DATOS):
        return None

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _get_system_prompt()},
                {"role": "user", "content": pregunta},
            ],
            temperature=0.1,
            max_tokens=500,
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

    except Exception:
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "No pude interpretar. Probá: compras roche noviembre 2025",
            "debug": "openai error",
        }

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

    texto_original = pregunta.strip()
    texto_lower_original = texto_original.lower().strip()

    # ==========================================================
    # NUEVO: DETALLE FACTURA (AGREGADO)
    # - Esto arregla el caso de tu screenshot: "Detalle factura A00273279"
    # ==========================================================
    nro_fact = _extraer_nro_factura(texto_original)
    if nro_fact:
        return {
            "tipo": "detalle_factura_numero",
            "parametros": {"nro_factura": nro_fact},
            "debug": "detalle factura por número",
        }

    # NUEVO: aplicar limpieza canónica sin romper la lógica
    texto_limpio = limpiar_consulta(texto_original)

    texto_lower = texto_limpio.lower().strip()

    # ✅ REGLA: si el original contiene "compras", debe entrar acá igual
    flag_compras = contiene_compras(texto_lower_original) or contiene_compras(texto_lower)
    flag_comparar = contiene_comparar(texto_lower_original) or contiene_comparar(texto_lower)

    idx_prov, idx_art = _get_indices()
    provs = _match_best(texto_lower, idx_prov, max_items=MAX_PROVEEDORES)
    arts = _match_best(texto_lower, idx_art, max_items=MAX_ARTICULOS)

    anios = _extraer_anios(texto_lower)
    meses_nombre = _extraer_meses_nombre(texto_lower)
    meses_yyyymm = _extraer_meses_yyyymm(texto_lower)

    # ==========================================================
    # COMPRAS (CANÓNICO): proveedor+mes | proveedor+año | mes | año
    # ==========================================================
    if flag_compras and (not flag_comparar):
        proveedor_libre = None
        if not provs:
            tmp = texto_lower
            tmp = re.sub(r"\bcompras?\b", "", tmp).strip()

            tmp2 = re.sub(
                r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\b",
                "",
                tmp
            )
            tmp2 = re.sub(r"\b(2023|2024|2025|2026)\b", "", tmp2).strip()

            if tmp2 and len(tmp2) >= 3:
                proveedor_libre = tmp2

        proveedor_final = provs[0] if provs else proveedor_libre

        # compras proveedor + mes
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

            # compras proveedor + año
            if len(anios) >= 1:
                return {
                    "tipo": "compras_proveedor_anio",
                    "parametros": {"proveedor": proveedor_final, "anio": anios[0]},
                    "debug": "compras proveedor año",
                }

        # compras (sin proveedor) + mes
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

        # compras (sin proveedor) + año
        if len(anios) >= 1:
            return {
                "tipo": "compras_anio",
                "parametros": {"anio": anios[0]},
                "debug": "compras año",
            }

    # ==========================================================
    # COMPARAR COMPRAS PROVEEDOR MES VS MES / AÑO VS AÑO
    # ==========================================================
    if flag_comparar and flag_compras:
        proveedor = provs[0] if provs else None

        if not proveedor:
            tmp = re.sub(r"(comparar|comparame|compara|compras?)", "", texto_lower)
            tmp = re.sub(
                r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)",
                "",
                tmp
            )
            tmp = re.sub(r"(2023|2024|2025|2026)", "", tmp).strip()
            if len(tmp) >= 2:
                proveedor = tmp

        if not proveedor:
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": "No encontré al proveedor, intentá: comparar compras roche junio julio 2025.",
                "debug": f"Proveedor='{proveedor}', texto={texto_lower}",
            }

        # Caso 1: meses YYYY-MM
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
                "debug": "Comparando meses en formato YYYY-MM.",
            }

        # Caso 2: meses por nombre + año
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
                "debug": "Comparando meses por nombre y año explícito.",
            }

        # Caso 3: años
        if len(anios) >= 2:
            a1, a2 = anios[0], anios[1]
            return {
                "tipo": "comparar_proveedor_anios",
                "parametros": {
                    "proveedor": proveedor,
                    "anios": [a1, a2],
                    "label1": str(a1),
                    "label2": str(a2),
                },
                "debug": "Comparando diferentes años.",
            }

        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "Intentá: comparar compras roche junio julio 2025 o comparar compras roche 2024 2025.",
            "debug": f"Condiciones insuficientes: años={anios}, meses={meses_nombre}",
        }

    # ==========================================================
    # STOCK
    # ==========================================================
    if "stock" in texto_lower:
        if arts:
            return {
                "tipo": "stock_articulo",
                "parametros": {"articulo": arts[0]},
                "debug": "stock articulo",
            }
        return {
            "tipo": "stock_total",
            "parametros": {},
            "debug": "stock total",
        }

    # ==========================================================
    # DEFAULT (si está habilitado OpenAI, intenta fallback; si no, no_entendido)
    # ==========================================================
    out_ai = _interpretar_con_openai(texto_original)
    if out_ai:
        return out_ai

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
    # FACTURA (AGREGADO)
    # =========================
    "detalle_factura_numero": {
        "funcion": "get_detalle_factura_por_numero",
        "params": ["nro_factura"],
        "resumen": "get_total_factura_por_numero"
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
