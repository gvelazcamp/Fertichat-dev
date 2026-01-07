# =========================
# IA_INTERPRETADOR.PY - CANÓNICO (DETECCIÓN BD + COMPARATIVAS)
# =========================

import os
import re
import json
import unicodedata
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime

import streamlit as st
from openai import OpenAI
from config import OPENAI_MODEL

# =====================================================================
# CONFIGURACIÓN OPENAI (opcional)
# =====================================================================
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Si querés "sacar OpenAI" para datos: dejalo False (recomendado).
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
    "sndres",
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
# TABLA CANÓNICA (50 combinaciones permitidas)
# =====================================================================
TABLA_CANONICA_50 = r"""
| # | ACCIÓN | OBJETO | TIEMPO | MULTI | TIPO (output) | PARAMS |
|---|--------|--------|--------|-------|---------------|--------|
| 01 | compras | (ninguno) | anio | no | compras_anio | anio |
| 02 | compras | (ninguno) | mes | no | compras_mes | mes |
| 03 | compras | proveedor | anio | no | compras_proveedor_anio | proveedor, anio |
| 04 | compras | proveedor | mes | no | compras_proveedor_mes | proveedor, mes |
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

_NOMBRES_PERSONALES_KEYS = set(_key(n) for n in (NOMBRES_PERSONALES_EXCLUIR or []) if n)

def _tokens(texto: str) -> List[str]:
    raw = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]+", texto.lower())
    out: List[str] = []
    for t in raw:
        k = _key(t)
        if len(k) >= 3:
            if k in _NOMBRES_PERSONALES_KEYS:
                continue
            out.append(k)
    return out

def normalizar_texto(texto: str) -> str:
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

def limpiar_consulta(texto: str) -> str:
    if not texto:
        return ""

    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")

    for nombre in NOMBRES_PERSONALES_EXCLUIR:
        texto = re.sub(rf"\b{re.escape(nombre)}\b", " ", texto)

    ruido = [
        "quiero", "por favor", "las", "los", "un", "una", "a", "de", "en", "para",
        "cuáles fueron", "cuales fueron", "dame", "analisis", "realizadas", "durante"
    ]
    for palabra in ruido:
        texto = re.sub(rf"\b{re.escape(palabra)}\b", " ", texto)

    texto = re.sub(r"\s{2,}", " ", texto).strip()
    return texto

# =====================================================================
# HELPERS DE KEYWORDS
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
# FACTURAS
# =====================================================================
def contiene_factura(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return bool(
        re.search(
            r"\b(detalle\s+)?factura(s)?\b"
            r"|\bnro\.?\s*(comprobante|factura)\b"
            r"|\bnro\.?\s*comprobante\b"
            r"|\bcomprobante\b",
            t,
            flags=re.IGNORECASE
        )
    )

def _normalizar_nro_factura(nro: str) -> str:
    nro = (nro or "").strip().upper()
    return nro

def _extraer_nro_factura(texto: str) -> Optional[str]:
    if not texto:
        return None

    t = str(texto).strip()

    m = re.search(
        r"\b(detalle\s+)?(factura|comprobante|nro\.?\s*comprobante|nro\.?\s*factura)\b\s*[:#-]?\s*([A-Za-z]?\d{3,})\b",
        t,
        flags=re.IGNORECASE
    )
    if m:
        raw = str(m.group(3)).strip()
        nro = _normalizar_nro_factura(raw)
        return nro or None

    if re.fullmatch(r"[A-Za-z]?\d{3,}", t):
        nro = _normalizar_nro_factura(t)
        return nro or None

    return None

# =====================================================================
# EXTRACCIÓN SIMPLE DE PARÁMETROS
# =====================================================================
def extraer_parametros(texto: str) -> Dict:
    MESES_LOCAL = {
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
        "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
        "septiembre": "09", "setiembre": "09", "octubre": "10",
        "noviembre": "11", "diciembre": "12"
    }

    parametros = {"proveedor": None, "mes": None, "anio": None}

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
# CARGA LISTAS DESDE SUPABASE
# =====================================================================
@st.cache_data(ttl=60 * 60)
def _cargar_listas_supabase() -> Dict[str, List[str]]:
    proveedores: List[str] = []
    articulos: List[str] = []

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

    toks_set = set(toks)
    for orig, norm in index:
        if norm in toks_set:
            return [orig]

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
# HELPER MULTI-PROVEEDOR
# =====================================================================
def _extraer_lista_proveedores_desde_texto(texto_lower: str, provs_detectados: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for p in (provs_detectados or []):
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out

# =====================================================================
# NUEVO: PARSEO DE RANGO DE FECHAS + MONEDA
# =====================================================================
def _extraer_rango_fechas(texto: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Devuelve (desde, hasta) en formato YYYY-MM-DD si detecta 2 fechas.
    Soporta:
    - YYYY-MM-DD
    - DD/MM/YYYY o DD-MM-YYYY
    """
    if not texto:
        return None, None

    t = str(texto)

    # ISO: YYYY-MM-DD
    iso = re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", t)
    if len(iso) >= 2:
        return iso[0], iso[1]

    # LatAm: DD/MM/YYYY o DD-MM-YYYY
    lat = re.findall(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", t)
    if len(lat) >= 2:
        def _fmt(d, m, y):
            try:
                dt = datetime(int(y), int(m), int(d))
                return dt.strftime("%Y-%m-%d")
            except Exception:
                return None
        d1 = _fmt(*lat[0])
        d2 = _fmt(*lat[1])
        return d1, d2

    return None, None

def _extraer_moneda(texto: str) -> Optional[str]:
    """
    Detecta moneda pedida por el usuario.
    Retorna: "USD" o "$" o None
    """
    if not texto:
        return None
    t = texto.lower()

    if re.search(r"\b(usd|u\$s|u\$\$|dolar|dolares|dólar|dólares|us\$)\b", t):
        return "USD"
    if re.search(r"\b(peso|pesos|uyu|uru)\b", t) or "$" in t:
        return "$"
    return None

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
# PROMPT OpenAI
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
# OPENAI (opcional)
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
            "sugerencia": "Intentá: comparar compras roche junio julio 2025 o comparar compras roche 2024 2025.",
            "debug": f"Condiciones insuficientes: años={anios}, meses={meses_nombre}",
        }

    # STOCK
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

    # DEFAULT
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
# MAPEO TIPO → FUNCIÓN SQL
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
    "detalle_factura_numero": {
        "funcion": "get_detalle_factura_por_numero",
        "params": ["nro_factura"]
    },
    "comparar_proveedor_meses": {
        "funcion": "get_comparacion_proveedor_meses",
        "params": ["proveedor", "mes1", "mes2", "label1", "label2"]
    },
    "comparar_proveedor_anios": {
        "funcion": "get_comparacion_proveedor_anios",
        "params": ["proveedor", "anios", "label1", "label2"]
    },
    "comparar_proveedores_meses": {
        "funcion": "get_comparacion_proveedores_meses",
        "params": ["proveedores", "mes1", "mes2", "label1", "label2"]
    },
    "comparar_proveedores_anios": {
        "funcion": "get_comparacion_proveedores_anios",
        "params": ["proveedores", "anios", "label1", "label2"]
    },
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

    # =========================
    # NUEVO: TODAS LAS FACTURAS DE UN PROVEEDOR (DETALLE)
    # =========================
    "compras_Todas las facturas de un Proveedor": {
        "funcion": "get_facturas_proveedor_detalle",
        "params": ["proveedores", "meses", "anios", "desde", "hasta", "articulo", "moneda", "limite"]
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
        "comparar_proveedores_meses",
        "comparar_proveedores_anios",
    ]
    return tipo in MAPEO_FUNCIONES or tipo in tipos_especiales


# =====================================================================
# INTERPRETADOR PRINCIPAL
# =====================================================================

def interpretar_pregunta(pregunta: str) -> Dict[str, Any]:
    """
    Interpretador canónico:
    - Detecta intención y extrae parámetros sin inventar.
    - NO ejecuta SQL, solo devuelve {tipo, parametros}.
    """
    if not pregunta or not pregunta.strip():
        return {"tipo": "no_entendido", "parametros": {}, "debug": "pregunta vacía"}

    texto_original = pregunta.strip()
    texto_lower_original = texto_original.lower()

    # =========================
    # FAST-PATH: detalle factura por número
    # =========================
    if contiene_factura(texto_lower_original):
        nro = _extraer_nro_factura(texto_original)
        if nro:
            return {
                "tipo": "detalle_factura_numero",
                "parametros": {"nro_factura": nro},
                "debug": f"factura nro={nro}"
            }

    # =========================
    # Normalización base
    # =========================
    texto_limpio = limpiar_consulta(texto_original)
    texto_lower = texto_limpio.lower()

    # =========================
    # Índices (proveedores / artículos) desde BD
    # =========================
    idx_prov, idx_art = _get_indices()
    provs = _match_best(texto_lower, idx_prov, max_items=MAX_PROVEEDORES)
    arts = _match_best(texto_lower, idx_art, max_items=MAX_ARTICULOS)

    # =========================
    # Tiempo: años y meses
    # =========================
    anios = _extraer_anios(texto_lower)
    meses_nombre = _extraer_meses_nombre(texto_lower)
    meses_yyyymm = _extraer_meses_yyyymm(texto_lower)

    # =================================================================
    # NUEVO: TODAS LAS FACTURAS DE UN PROVEEDOR (DETALLE)
    # - Se activa si el usuario pide "facturas" / "comprobantes" sin nro específico
    # =================================================================
    if contiene_factura(texto_lower_original) and (not _extraer_nro_factura(texto_original)):
        # Intento multi-proveedor: asigna "mejor match" por token
        proveedores_lista: List[str] = []
        seen_prov = set()
        toks = _tokens(texto_lower)

        # tokens a ignorar (ruido / tiempo)
        ignorar = set([
            "todas", "toda", "todaslas", "factura", "facturas",
            "comprobante", "comprobantes", "compra", "compras",
            "enero","febrero","marzo","abril","mayo","junio","julio","agosto",
            "septiembre","setiembre","octubre","noviembre","diciembre",
            "2023","2024","2025","2026"
        ])

        for tk in toks:
            if (not tk) or (tk in ignorar):
                continue

            best_orig = None
            best_score = None
            for orig, norm in idx_prov:
                if tk in norm:
                    score = (len(tk) * 1000) - len(norm)
                    if (best_score is None) or (score > best_score):
                        best_score = score
                        best_orig = orig

            if best_orig and best_orig not in seen_prov:
                seen_prov.add(best_orig)
                proveedores_lista.append(best_orig)
                if len(proveedores_lista) >= MAX_PROVEEDORES:
                    break

        # Si no logró multi, fallback al match estándar (1 proveedor)
        if not proveedores_lista and provs:
            proveedores_lista = (provs or [])[:MAX_PROVEEDORES]

        # Fallback: si no detectó proveedor por lista, intentar "libre"
        if not proveedores_lista:
            tmp = texto_lower
            tmp = re.sub(r"\b(todas|todas las|facturas?|comprobantes?|de|del|la|el)\b", " ", tmp)
            tmp = re.sub(r"\b(compras?|comparar|comparame|compara)\b", " ", tmp)
            tmp = re.sub(
                r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\b",
                " ",
                tmp
            )
            tmp = re.sub(r"\b(2023|2024|2025|2026)\b", " ", tmp)
            tmp = re.sub(r"\s+", " ", tmp).strip()
            if tmp and len(tmp) >= 3:
                proveedores_lista = [tmp]

        if not proveedores_lista:
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": "Indicá el proveedor. Ej: todas las facturas de Roche noviembre 2025.",
                "debug": "facturas: no encontré proveedor",
            }

        # Rango de fechas exacto (prioridad)
        desde, hasta = _extraer_rango_fechas(texto_original)

        # Meses (lista YYYY-MM)
        meses_out: List[str] = []
        if meses_yyyymm:
            meses_out = meses_yyyymm[:MAX_MESES]
        else:
            if meses_nombre and anios:
                for a in anios:
                    for mn in meses_nombre:
                        meses_out.append(_to_yyyymm(a, mn))
                        if len(meses_out) >= MAX_MESES:
                            break
                    if len(meses_out) >= MAX_MESES:
                        break

        moneda = _extraer_moneda(texto_lower_original)
        articulo = arts[0] if arts else None

        return {
            "tipo": "compras_Todas las facturas de un Proveedor",
            "parametros": {
                "proveedores": proveedores_lista,
                "meses": meses_out or None,
                "anios": anios or None,
                "desde": desde,
                "hasta": hasta,
                "articulo": articulo,
                "moneda": moneda,
            },
            "debug": "facturas proveedor detalle",
        }

