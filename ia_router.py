# =========================================================================================
# 🔥 IA_ROUTER CARGADO DESDE ESTE ARCHIVO 🔥
# =========================================================================================

# Archivo completo: ia_router.py
# Versión corregida con bloque duro al inicio de interpretar_pregunta

import os
import re
import json
import unicodedata
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime

import streamlit as st
from openai import OpenAI
from config import OPENAI_MODEL
from sql_core import ejecutar_consulta

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
# EXCLUSIÓN DE NOMBRES PERSONALES
# =====================================================================
NOMBRES_PERSONALES_EXCLUIR = [
    "gonzalo",
    "daniela",
    "andres",
    "sndres",
    "juan",
]

# =====================================================================
# EXCLUSIÓN DE PALABRAS CLAVE DE ARTÍCULOS PARA NO CONFUNDIR CON PROVEEDORES
# =====================================================================
PALABRAS_CLAVE_ARTICULOS = [
    "vitek", "ast", "gn", "id20", "test", "kit", "coba", "elecsys"
]

# =====================================================================
# ALIAS / SINÓNIMOS DE PROVEEDOR (fallback cuando BD falla)
# =====================================================================
ALIAS_PROVEEDOR = {
    "roche": "roche",
    "rocheinternational": "roche",
    "laboratoriotresul": "tresul",
    "tresul": "tresul",
    "tesul": "tresul",
    "biodiagnostico": "biodiagnostico",
    "bio": "biodiagnostico",
    "cabinsur": "biodiagnostico",
}

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

def _alias_proveedor(prov: str) -> str:
    k = _key(prov)
    return ALIAS_PROVEEDOR.get(k, prov)

_NOMBRES_PERSONALES_KEYS = set(_key(n) for n in (NOMBRES_PERSONALES_EXCLUIR or []) if n)

def _tokens(texto: str) -> List[str]:
    raw = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]+", (texto or "").lower())
    out: List[str] = []
    for t in raw:
        k = _key(t)
        if len(k) >= 3:
            if k in _NOMBRES_PERSONALES_KEYS:
                continue
            out.append(k)
    return out

def normalizar_texto(texto: str) -> str:
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"(.)\1{1,}", r"\1", texto)  # elimina letras repetidas
    texto = re.sub(r"[^a-z0-9 ]+", " ", texto)
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

def _extraer_proveedor_libre(texto_lower_original: str) -> Optional[str]:
    """
    Fallback para NO depender de listas de Supabase.
    Devuelve un proveedor "usable" (ej: 'roche', 'tresul', 'biodiagnostico') si aparece.
    """
    if not texto_lower_original:
        return None

    toks = _tokens(texto_lower_original)

    ignorar = set(
        [
            "todas", "todoas", "toda", "todaslas",
            "factura", "facturas", "comprobante", "comprobantes",
            "compra", "compras",
            "gasto", "gastos", "documento", "documentos",
            "comparar", "comparame", "compara",
            "detalle", "nro", "numero",
            "total", "totales",
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "setiembre", "octubre", "noviembre", "diciembre",
            "2023", "2024", "2025", "2026",
            "usd", "dolar", "dolares", "dólar", "dólares", "dollar",
            "pesos", "peso", "uyu", "uru",
        ]
    )

    for tk in toks:
        if not tk or tk in ignorar:
            continue
        # EXCLUSIÓN: Si es palabra clave de artículo, no considerarlo proveedor
        if tk in PALABRAS_CLAVE_ARTICULOS:
            continue
        if tk in ALIAS_PROVEEDOR:
            return ALIAS_PROVEEDOR[tk]

    for tk in toks:
        if not tk or tk in ignorar:
            continue
        # EXCLUSIÓN: Si es palabra clave de artículo, no considerarlo proveedor
        if tk in PALABRAS_CLAVE_ARTICULOS:
            continue
        if len(tk) >= 3:
            return tk

    return None

def detectar_articulo_valido(tokens, catalogo_articulos):
    for token in tokens:
        t = token.strip().lower()

        # ❌ NO permitir tokens numéricos puros
        if t.isdigit():
            continue

        # ❌ NO permitir tokens mayormente numéricos (ej: 2183118a)
        if sum(c.isdigit() for c in t) >= len(t) * 0.6:
            continue

        if len(t) < 4:
            continue

        for art in catalogo_articulos:
            if t in art.lower():
                return art
    return None

def es_saludo(texto: str) -> bool:
    saludos = [
        "hola",
        "buenas",
        "buen día",
        "buen dia",
        "buenas tardes",
        "buenas noches",
        "como andas",
        "como estás",
        "qué tal",
        "que tal"
    ]
    t = texto.lower().strip()
    return any(t.startswith(s) or s in t for s in saludos)

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

def contiene_gastos_o_documentos(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return bool(re.search(r"\b(gastos?|documentos?)\b", t))

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
            r"|\bcomprobante(s)?\b",
            t,
            flags=re.IGNORECASE
        )
    )

def _normalizar_nro_factura(nro: str) -> str:
    return (nro or "").strip().upper()

def _extraer_nro_factura(texto: str) -> Optional[str]:
    """
    Extrae número de factura del texto.
    CRÍTICO: debe detectar números después de "detalle factura", "factura", etc.
    """
    if not texto:
        return None

    t = str(texto).strip()

    # Patrón 1: "detalle factura 60907", "factura 60907", etc.
    m = re.search(
        r"\b(detalle\s+)?(factura|comprobante|nro\.?\s*comprobante|nro\.?\s*factura)\b\s*[:#-]?\s*([A-Za-z]?\d{3,})\b",
        t,
        flags=re.IGNORECASE
    )
    if m:
        raw = str(m.group(3)).strip()

        # ❌ NO confundir años con números de factura
        if raw.isdigit():
            try:
                n = int(raw)
                if n in ANIOS_VALIDOS:
                    return None
            except Exception:
                pass

        nro = _normalizar_nro_factura(raw)
        return nro or None

    # Patrón 2: Si el texto es SOLO un número (fallback)
    # Ejemplo: "60907" → debe ser factura, no año
    if re.fullmatch(r"[A-Za-z]?\d{3,}", t):
        if t.isdigit():
            try:
                n = int(t)
                # ❌ NO confundir años (2023, 2024, etc)
                if n in ANIOS_VALIDOS:
                    return None
            except Exception:
                pass

        nro = _normalizar_nro_factura(t)
        return nro or None

    return None

# =====================================================================
# Extraer limite
# =====================================================================
def _extraer_limite(texto: str, predeterminado: int = 500) -> int:
    import re
    numeros = re.findall(r"\b\d+\b", texto)
    for numero in numeros:
        n = int(numero)
        if n > 0:
            return n
    return predeterminado

# =====================================================================
# Extraer Monedas
# =====================================================================
def _extraer_moneda(texto: str) -> Optional[str]:
    texto = texto.lower()
    patrones_moneda = {
        "USD": ["usd", "u$s", "u$$", "dólares", "dolares", "dollar", "dólar", "dolar"],
        "UYU": ["pesos", "uyu", "$", "moneda nacional"],
    }
    for moneda, palabras_clave in patrones_moneda.items():
        for palabra in palabras_clave:
            if palabra in texto:
                return moneda
    return None

# =====================================================================
# Extraer rango fechas
# =====================================================================
def _extraer_rango_fechas(texto: str) -> Tuple[Optional[str], Optional[str]]:
    patron_fecha = r"\b(\d{4}-\d{2}-\d{2})\b"
    fechas = re.findall(patron_fecha, texto)
    if len(fechas) >= 2:
        return fechas[0], fechas[1]
    elif len(fechas) == 1:
        return fechas[0], None
    return None, None

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
    # Filter out common words that shouldn't match articles/providers
    ignore_words = {"compras", "compra", "factura", "facturas", "total", "totales", "comparar", "compara", "2023", "2024", "2025", "2026", "usd", "u$s", "pesos", "uyu"}
    toks = [t for t in toks if t not in ignore_words]
    if not toks or not index:
        return []

    scores: Dict[str, int] = {}
    for tok in toks:
        for orig, key_val in index:
            if tok in key_val:
                scores[orig] = scores.get(orig, 0) + len(tok)

    if not scores:
        return []

    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [it[0] for it in sorted_items[:max_items]]

# =====================================================================
# EXTRACCIONES TEMPORALES
# =====================================================================
def _extraer_anios(texto: str) -> List[int]:
    """Extrae años válidos (2023-2026)"""
    anios = []
    for m in re.finditer(r"\b(20\d{2})\b", texto):
        a = int(m.group(1))
        if a in ANIOS_VALIDOS:
            anios.append(a)
    return sorted(list(set(anios)))

def _extraer_meses_nombre(texto: str) -> List[str]:
    """Extrae meses mencionados por nombre (enero, febrero, etc)"""
    t = texto.lower()
    out: List[str] = []
    for nombre, cod in MESES.items():
        if nombre in t:
            out.append(cod)
    return sorted(list(set(out)))

def _extraer_meses_yyyymm(texto: str) -> List[str]:
    """Extrae meses en formato YYYY-MM"""
    out: List[str] = []
    for m in re.finditer(r"\b(20\d{2})[/-](0[1-9]|1[0-2])\b", texto):
        out.append(f"{m.group(1)}-{m.group(2)}")
    return sorted(list(set(out)))

def _to_yyyymm(anio: int, mes_cod: str) -> str:
    """Convierte año + código mes → YYYY-MM"""
    return f"{anio}-{mes_cod}"

# =====================================================================
# OPENAI (OPCIONAL)
# =====================================================================
def _get_system_prompt() -> str:
    return """
Sos un asistente que interpreta preguntas sobre compras de un laboratorio.
Devolvé SIEMPRE JSON con esta estructura:
{
  "tipo": "<tipo_de_consulta>",
  "parametros": { ... }
}

TIPOS VÁLIDOS:
- compras_anio: si pregunta por compras de un año completo
- compras_proveedor_mes: si pregunta compras de proveedor + mes
- compras_mes: si pregunta compras de un mes sin proveedor
- detalle_factura_numero: si pregunta por número de factura
- comparar_proveedor_meses: comparar un proveedor entre 2 meses
- comparar_proveedor_anios: comparar un proveedor entre 2 años
- stock_total: si pregunta stock general
- stock_articulo: si pregunta stock de un artículo
- no_entendido: si no entendés la pregunta

IMPORTANTE:
- Si hay número de factura: tipo = detalle_factura_numero
- Si hay años 2023-2026: extraelos como enteros
- Si hay meses: extraelos como "01", "02", etc
- Si hay proveedor: normaliza el nombre
"""

def _interpretar_con_openai(pregunta: str) -> Optional[Dict[str, Any]]:
    if not USAR_OPENAI_PARA_DATOS or not client:
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
        content = re.sub(r"```json\s*", "", content).strip()
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
            "sugerencia": "Probá: compras roche noviembre 2025 | comparar compras roche junio julio 2025 | detalle factura 273279",
            "debug": "openai error",
        }

# ==================================================
# DETALLE FACTURA POR NÚMERO (MATCH ROBUSTO)
# ==================================================

def get_detalle_factura_por_numero(nro_factura: str):
    """
    Devuelve el detalle de una factura buscando por coincidencia parcial
    en 'Nro. Comprobante' (tolera prefijos tipo A000, ceros, etc.)
    """

    sql = """
        SELECT
            *
        FROM chatbot_raw
        WHERE
            REPLACE(TRIM("Nro. Comprobante"), ' ', '') ILIKE '%' || %s || '%'
        ORDER BY "Fecha"
    """

    return ejecutar_consulta(sql, (nro_factura,))

# =====================================================================
# INTERPRETADOR PRINCIPAL (AGENTIC AI = DECIDE, NO EJECUTA)
# =====================================================================

def interpretar_pregunta(pregunta: str) -> Dict[str, Any]:
    """
    Interpretador canónico (Agentic AI):
    - Detecta intención y extrae parámetros sin inventar.
    - NO ejecuta SQL, solo devuelve {tipo, parametros}.
    """
    if not pregunta or not str(pregunta).strip():
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "debug": {"origen": "ia_router", "intentos": ["router: pregunta_vacia"]}
        }

    intentos = []

    texto_original = str(pregunta).strip()
    texto_lower_original = texto_original.lower()

    # ==================================================
    # 🔒 PRIORIDAD ABSOLUTA – COMPRAS SOLO POR AÑO
    # ==================================================
    texto_q = texto_lower_original.strip()

    m = re.search(r"\b(compras?|compra)\s+(202[3-6])\b", texto_q)
    if m:
        anio = int(m.group(2))

        from sql_compras import get_total_compras_anio

        return {
            "tipo": "compras_anio",
            "parametros": {
                "anio": anio
            },
            "debug": f"router → compras {anio}"
        }

    texto_q = texto_lower_original.strip()

    m = re.fullmatch(r"(compras|compra)\s+(\d{4})", texto_q)
    if m:
        anio = int(m.group(2))

        from sql_facturas import get_compras_totales_por_anio
        resultado = get_compras_totales_por_anio(anio)

        return {
            "tipo": "compras_anio",
            "parametros": {"anio": anio},
            "resultado": resultado
        }

    # ==================================================
    # COMPRAS POR AÑO (IA ROUTER NATURAL)
    # ==================================================
    anios = _extraer_anios(texto_lower_original)

    if contiene_compras(texto_lower_original) and len(anios) == 1:
        return {
            "tipo": "compras_anio",
            "parametros": {
                "anio": anios[0]
            },
            "debug": {
                "origen": "ia_router",
                "regla": "compras + año"
            }
        }

    # ----------------------------------
    # 2️⃣ NORMALIZACIÓN (DESPUÉS)
    # ----------------------------------
    texto_norm = normalizar_texto(texto_original)

    # ==================================================
    # 🔒 HARD BLOCK – COMPRAS SOLO POR AÑO
    # PRIORIDAD ABSOLUTA – DESPUÉS DE FACTURA
    # ==================================================
    anios = _extraer_anios(texto_lower_original)

    if contiene_compras(texto_lower_original) and anios:
        return {
            "tipo": "compras_anio",
            "parametros": {
                "anio": anios[0]
            },
            "debug": {
                "origen": "ia_router",
                "hard_block": "compras_anio"
            }
        }

    # ============================
    # SALUDOS
    # ============================
    if es_saludo(texto_lower_original):
        usuario = st.session_state.get("nombre", "👋")

        return {
            "tipo": "saludo",
            "mensaje": (
                f"Hola **{usuario}** 👋\n\n"
                "¿En qué puedo ayudarte hoy?\n\n"
                "Puedo ayudarte con:\n"
                "• 🛒 **Compras**\n"
                "• 📦 **Stock**\n"
                "• 📊 **Comparativas**\n"
                "• 🧪 **Artículos**\n\n"
                "Escribí lo que necesites 👇"
            ),
            "debug": {"origen": "ia_router", "intentos": intentos}
        }

    # ============================
    # CONOCIMIENTO (preguntas qué es, etc.)
    # ============================
    palabras_conocimiento = ["qué es", "que es", "qué significa", "que significa", 
                             "explica", "explicame", "explícame", "define", 
                             "dime sobre", "qué son", "que son", "cuál es", "cual es",
                             "para qué sirve", "para que sirve", "cómo funciona", "como funciona"]
    
    if any(palabra in texto_lower_original for palabra in palabras_conocimiento):
        return {
            "tipo": "conocimiento",
            "parametros": {},
            "debug": {"origen": "ia_router", "intentos": intentos}
        }

    # FAST-PATH: listado facturas por año
    if re.search(r"\b(listado|lista)\b", texto_lower_original) and re.search(r"\bfacturas?\b", texto_lower_original):
        anios_listado = _extraer_anios(texto_lower_original)
        if anios_listado:
            anio = anios_listado[0]
            return {
                "tipo": "listado_facturas_anio",
                "parametros": {"anio": anio},
                "debug": {"origen": "ia_router", "intentos": intentos}
            }

    # FAST-PATH: total facturas por moneda año
    if re.search(r"\b(total|totales)\b", texto_lower_original) and re.search(r"\b(2023|2024|2025|2026)\b", texto_lower_original):
        anios_total = _extraer_anios(texto_lower_original)
        if anios_total:
            anio = anios_total[0]
            return {
                "tipo": "total_facturas_por_moneda_anio",
                "parametros": {"anio": anio},
                "debug": {"origen": "ia_router", "intentos": intentos}
            }

    # FAST-PATH: total facturas por moneda generico (sin año)
    if re.search(r"\b(total|totales)\b", texto_lower_original) and re.search(r"\bfacturas?\b", texto_lower_original) and re.search(r"\bmoneda\b", texto_lower_original) and not re.search(r"\d{4}", texto_lower_original):
        return {
            "tipo": "total_facturas_por_moneda_generico",
            "parametros": {},
            "debug": {"origen": "ia_router", "intentos": intentos}
        }

    # FAST-PATH: total compras por moneda generico (sin año)
    if re.search(r"\b(total|totales)\b", texto_lower_original) and re.search(r"\bcompras?\b", texto_lower_original) and re.search(r"\bmoneda\b", texto_lower_original) and not re.search(r"\d{4}", texto_lower_original):
        return {
            "tipo": "total_compras_por_moneda_generico",
            "parametros": {},
            "debug": {"origen": "ia_router", "intentos": intentos}
        }

    texto_limpio = limpiar_consulta(texto_original)
    texto_lower = texto_limpio.lower()

    idx_prov, idx_art = _get_indices()
    provs = _match_best(texto_lower, idx_prov, max_items=MAX_PROVEEDORES)
    arts = _match_best(texto_lower, idx_art, max_items=MAX_ARTICULOS)

    if not provs:
        prov_libre = _extraer_proveedor_libre(texto_lower_original)
        if prov_libre:
            provs = [_alias_proveedor(prov_libre)]

    tokens = _tokens(texto_lower_original)

    # EXTRACCIÓN BASE (OBLIGATORIA ANTES DE LOS IF)
    anios = _extraer_anios(texto_lower)
    meses_nombre = _extraer_meses_nombre(texto_lower)
    meses_yyyymm = _extraer_meses_yyyymm(texto_lower)

    # Fallback de artículo
    if not arts:
        listas = _cargar_listas_supabase()
        articulos_db = listas.get("articulos", [])
        tokens_restantes = [t for t in tokens if t not in provs]
        articulo = detectar_articulo_valido(tokens_restantes, articulos_db)
        if articulo:
            arts = [articulo]

    # ==================================================
    # 🔒 CASO BASE: COMPRAS SOLO POR AÑO (SIN PROVEEDOR / ARTÍCULO)
    # ==================================================
    if (
        contiene_compras(texto_lower)
        and anios
        and not provs
        and not arts
        and not meses_nombre
        and not meses_yyyymm
    ):
        return {
            "tipo": "compras_anio",
            "parametros": {"anio": anios[0]},
            "debug": "router → compras año (solo)"
        }

    # RUTA ARTÍCULOS (CANÓNICA)
    if (
        contiene_compras(texto_lower_original)
        and not provs
        and not anios
    ):
        intentos.append("router: ruta_articulos_canonica")  # Registro de intento
        from ia_interpretador_articulos import interpretar_articulo
        meses = meses_nombre + meses_yyyymm
        try:
            result = interpretar_articulo(texto_original, [], meses)
            # Propagar intentos del módulo destino
            if isinstance(result.get("debug"), dict) and "intentos" in result["debug"]:
                intentos.extend(result["debug"]["intentos"])
            result["debug"] = {"origen": "ia_router", "intentos": intentos}
            return result
        except Exception as e:
            intentos.append(f"router: error_ruta_articulos - {str(e)}")
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "debug": {"origen": "ia_router", "intentos": intentos}
            }

    # COMPRAS POR PROVEEDOR / ARTÍCULO + AÑO
    if provs and anios:
        tipo = "facturas_proveedor"

    elif arts and anios:
        intentos.append("router: delegar_a_interpretador_articulos")

        meses = meses_nombre + meses_yyyymm

        from ia_interpretador_articulos import interpretar_articulo

        resultado = interpretar_articulo(
            texto_original,
            anios=anios,
            meses=meses
        )

        # Normalizar debug a dict
        if "debug" not in resultado or not isinstance(resultado["debug"], dict):
            resultado["debug"] = {
                "mensaje": resultado.get("debug")
            }

        resultado["debug"]["intentos"] = intentos + resultado["debug"].get("intentos", [])

        return resultado

    # FACTURAS PROVEEDOR (LISTADO)
    dispara_facturas_listado = False

    if contiene_factura(texto_lower_original) and (_extraer_nro_factura(texto_original) is None):
        dispara_facturas_listado = True

    if (
        re.search(r"\b(todas|todoas)\b", texto_lower_original)
        and re.search(r"\b(compras?|facturas?|comprobantes?)\b", texto_lower_original)
        and (_extraer_nro_factura(texto_original) is None)
    ):
        dispara_facturas_listado = True

    if (
        (not contiene_comparar(texto_lower_original))
        and provs
        and contiene_gastos_o_documentos(texto_lower_original)
        and (_extraer_nro_factura(texto_original) is None)
    ):
        dispara_facturas_listado = True

    if dispara_facturas_listado:
        proveedores_lista: List[str] = []
        if provs:
            proveedores_lista = [provs[0]]
        else:
            prov_libre = _extraer_proveedor_libre(texto_lower_original)
            if prov_libre:
                proveedores_lista = [_alias_proveedor(prov_libre)]

        if not proveedores_lista:
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": "Indicá el proveedor. Ej: todas las facturas de Roche noviembre 2025.",
                "debug": {"origen": "ia_router", "intentos": intentos}
            }

        desde, hasta = _extraer_rango_fechas(texto_original)

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

        articulo = None
        if re.search(r"\b(articulo|artículo|producto)\b", texto_lower_original):
            articulo = arts[0] if arts else None

        limite = _extraer_limite(texto_lower_original)

        return {
            "tipo": "facturas_proveedor",
            "parametros": {
                "proveedores": proveedores_lista,
                "meses": meses_out or None,
                "anios": anios or None,
                "desde": desde,
                "hasta": hasta,
                "articulo": articulo,
                "moneda": moneda,
                "limite": limite,
            },
            "debug": {"origen": "ia_router", "intentos": intentos}
        }

    # COMPRAS (fusionado con facturas_proveedor)
    if contiene_compras(texto_lower_original) and not contiene_comparar(texto_lower_original):

        # EXTRAER PROVEEDORES CON COMA (MÚLTIPLES)
        proveedores_multiples: List[str] = []
        parts = texto_lower_original.split()

        if "compras" in parts or "compra" in parts:
            idx = parts.index("compras") if "compras" in parts else parts.index("compra")
            after_compras = parts[idx + 1:]

            # Encontrar el primer mes o año para detener
            first_stop = None
            for i, p in enumerate(after_compras):
                clean_p = re.sub(r"[^\w]", "", p)
                if clean_p in MESES or (clean_p.isdigit() and int(clean_p) in ANIOS_VALIDOS):
                    first_stop = i
                    break

            if first_stop is not None:
                proveedores_texto = " ".join(after_compras[:first_stop])
            else:
                proveedores_texto = " ".join(after_compras)

            if "," in proveedores_texto:
                proveedores_multiples = [
                    _alias_proveedor(p.strip())
                    for p in proveedores_texto.split(",")
                    if p.strip()
                ]
            elif proveedores_texto:
                proveedores_multiples = [_alias_proveedor(proveedores_texto)]

        if proveedores_multiples:
            provs = proveedores_multiples

        # COMPRAS POR ARTÍCULO + AÑO
        if arts and anios and not provs:
            return {
                "tipo": "compras_articulo_anio",
                "parametros": {
                    "articulo": arts[0],
                    "anios": anios
                },
                "debug": {"origen": "ia_router", "intentos": intentos}
            }

        # PRIORIZAR MES SOBRE AÑO
        if provs and (meses_yyyymm or (meses_nombre and anios)):
            if len(provs) > 1:
                # MÚLTIPLES PROVEEDORES + MES/AÑO
                meses_out = []
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

                return {
                    "tipo": "compras_multiples",
                    "parametros": {
                        "proveedores": provs[:MAX_PROVEEDORES],
                        "meses": meses_out or None,
                        "anios": anios or None
                    },
                    "debug": {"origen": "ia_router", "intentos": intentos}
                }
            else:
                # UN SOLO PROVEEDOR + MES
                if meses_yyyymm:
                    mes = meses_yyyymm[0]
                elif meses_nombre and anios:
                    mes = _to_yyyymm(anios[0], meses_nombre[0])
                else:
                    mes = None

                if mes:
                    return {
                        "tipo": "compras_proveedor_mes",
                        "parametros": {
                            "proveedor": provs[0],
                            "mes": mes
                        },
                        "debug": {"origen": "ia_router", "intentos": intentos}
                    }

        # COMPRAS PROVEEDOR + AÑO (SIN MES)
        if provs and anios:
            return {
                "tipo": "facturas_proveedor",
                "parametros": {
                    "proveedores": [provs[0]],
                    "meses": None,
                    "anios": anios,
                    "desde": None,
                    "hasta": None,
                    "articulo": None,
                    "moneda": None,
                    "limite": 500,
                },
                "debug": {"origen": "ia_router", "intentos": intentos}
            }

    # COMPARACIONES
    if contiene_comparar(texto_lower_original):
        proveedores_comparar: List[str] = []

        if provs:
            proveedores_comparar = provs
        else:
            prov_libre = _extraer_proveedor_libre(texto_lower_original)
            if prov_libre:
                proveedores_comparar = [_alias_proveedor(prov_libre)]

        # COMPARAR MESES
        meses_cmp: List[str] = []
        if meses_yyyymm:
            meses_cmp = meses_yyyymm[:2]
        elif len(meses_nombre) >= 2 and anios:
            meses_cmp = [_to_yyyymm(anios[0], meses_nombre[0]), _to_yyyymm(anios[0], meses_nombre[1])]

        if len(meses_cmp) >= 2:
            if len(proveedores_comparar) >= 2:
                return {
                    "tipo": "comparar_proveedores_meses",
                    "parametros": {
                        "proveedores": proveedores_comparar[:MAX_PROVEEDORES],
                        "mes1": meses_cmp[0],
                        "mes2": meses_cmp[1],
                        "label1": meses_cmp[0],
                        "label2": meses_cmp[1],
                    },
                    "debug": {"origen": "ia_router", "intentos": intentos}
                }
            elif len(proveedores_comparar) == 1:
                return {
                    "tipo": "comparar_proveedor_meses",
                    "parametros": {
                        "proveedor": proveedores_comparar[0],
                        "mes1": meses_cmp[0],
                        "mes2": meses_cmp[1],
                        "label1": meses_cmp[0],
                        "label2": meses_cmp[1],
                    },
                    "debug": {"origen": "ia_router", "intentos": intentos}
                }
            else:
                return {
                    "tipo": "comparar_proveedores_meses_multi",
                    "parametros": {
                        "proveedores": [],  # Vacío = todos
                        "meses": meses_cmp,
                    },
                    "debug": {"origen": "ia_router", "intentos": intentos}
                }
        
        # COMPARAR AÑOS
        if len(anios) >= 2:
            if len(proveedores_comparar) >= 2:
                return {
                    "tipo": "comparar_proveedores_anios",
                    "parametros": {
                        "proveedores": proveedores_comparar[:MAX_PROVEEDORES],
                        "anios": anios[:2],
                        "label1": str(anios[0]),
                        "label2": str(anios[1]),
                    },
                    "debug": {"origen": "ia_router", "intentos": intentos}
                }
            elif len(proveedores_comparar) == 1:
                return {
                    "tipo": "comparar_proveedor_anios",
                    "parametros": {
                        "proveedor": proveedores_comparar[0],
                        "anios": anios[:2],
                        "label1": str(anios[0]),
                        "label2": str(anios[1]),
                    },
                    "debug": {"origen": "ia_router", "intentos": intentos}
                }
            else:
                return {
                    "tipo": "comparar_proveedores_anios_multi",
                    "parametros": {
                        "proveedores": [],  # Vacío = todos
                        "anios": anios[:2],
                    },
                    "debug": {"origen": "ia_router", "intentos": intentos}
                }
        
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "Ej: comparar compras roche junio julio 2025 | comparar compras roche 2024 2025 | comparar 2024 2025",
            "debug": {"origen": "ia_router", "intentos": intentos}
        }

    # STOCK
    if "stock" in texto_lower_original:
        if arts:
            return {"tipo": "stock_articulo", "parametros": {"articulo": arts[0]}, "debug": {"origen": "ia_router", "intentos": intentos}}
        return {"tipo": "stock_total", "parametros": {}, "debug": {"origen": "ia_router", "intentos": intentos}}

    # TOP PROVEEDORES POR AÑO/MES
    if (
        any(k in texto_lower_original for k in ["top", "ranking", "principales"])
        and "proveedor" in texto_lower_original
        and anios
    ):
        top_n = 10
        match = re.search(r'top\s+(\d+)', texto_lower_original)
        if match:
            top_n = int(match.group(1))

        moneda_extraida = _extraer_moneda(texto_lower_original)
        if moneda_extraida and moneda_extraida.upper() in ("USD", "U$S", "U$$", "US$"):
            moneda_param = "U$S"
        else:
            moneda_param = "$"

        meses_param = None
        if meses_yyyymm:
            meses_param = meses_yyyymm
        elif meses_nombre:
            meses_param = [_to_yyyymm(anios[0], mn) for mn in meses_nombre]

        return {
            "tipo": "dashboard_top_proveedores",
            "parametros": {
                "anio": anios[0],
                "meses": meses_param,
                "top_n": top_n,
                "moneda": moneda_param,
            },
            "debug": {"origen": "ia_router", "intentos": intentos}
        }

    if "compras" in texto_lower_original:
        anios = _extraer_anios(texto_lower_original)
        if anios:
            intentos.append("router: compras_anio_fastpath")

            return {
                "tipo": "compras_anio",
                "parametros": {
                    "anio": anios[0]
                },
                "debug": {
                    "origen": "ia_router",
                    "intentos": intentos
                }
            }

    # ==================================================
    # 🛒 DERIVACIÓN A INTÉRPRETE DE COMPRAS
    # ==================================================
    if "compra" in texto_lower_original or "compras" in texto_lower_original:
        from ia_compras import interpretar_compras

        anios = _extraer_anios(texto_lower_original)

        resultado = interpretar_compras(
            texto_lower_original,
            anios=anios
        )

        if resultado and resultado.get("tipo") != "no_entendido":
            resultado.setdefault("debug", {})
            resultado["debug"]["origen"] = "ia_router → ia_compras"
            return resultado

    out_ai = _interpretar_con_openai(texto_original)
    if out_ai:
        return out_ai

    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: compras roche noviembre 2025 | comparar compras roche junio julio 2025 | detalle factura 273279 | todas las facturas roche 2025 | listado facturas 2025 | total 2025 | total facturas por moneda | total compras por moneda | comparar 2024 2025",
        "debug": {"origen": "ia_router", "intentos": intentos}
    }


# =========================
# AGENTIC AI - API PÚBLICA (NO EJECUTA SQL)
# =========================
# Nota: En tu arquitectura, "Agentic AI" = este interpretador.
# El orquestador sigue siendo el que ejecuta SQL/funciones.
# Esto es solo un alias/wrapper para que lo uses explítamente como "agente".

def agentic_decidir(pregunta: str) -> Dict[str, Any]:
    """
    API Agentic:
    - Devuelve una DECISIÓN (tipo + parametros)
    - Mantiene compatibilidad: retorna exactamente lo mismo que interpretar_pregunta()
    """
    return interpretar_pregunta(pregunta)


def agentic_es_ejecutable(decision: Dict[str, Any]) -> bool:
    """
    True si la decisión tiene tipo válido para el orquestador.
    No ejecuta nada: solo valida formato mínimo.
    """
    if not isinstance(decision, dict):
        return False
    tipo = decision.get("tipo")
    if not tipo:
        return False
    tipos_especiales = [
        "conversacion",
        "conocimiento",
        "no_entendido",
        "comparar_proveedor_meses",
        "comparar_proveedor_anios",
        "comparar_proveedores_meses",
        "comparar_proveedores_anios",
        "comparar_proveedores_meses_multi",
        "comparar_proveedores_anios_multi",
    ]
    return tipo in MAPEO_FUNCIONES or tipo in tipos_especiales

# Agregado: Mapeo de tipos a funciones SQL (para compatibilidad)
MAPEO_FUNCIONES = {
    "compras_anio": {
        "funcion": "get_compras_anio",
        "params": ["anio"],
        "resumen": "get_total_compras_anio",
    },
    "compras_proveedor_mes": {
        "funcion": "get_detalle_compras_proveedor_mes",
        "params": ["proveedor", "mes"],
    },
    "compras_mes": {
        "funcion": "get_compras_por_mes_excel",
        "params": ["mes"],
    },
    "compras_multiples": {
        "funcion": "get_compras_multiples",
        "params": ["proveedores", "meses", "anios"],
    },
    "compras_articulo_anio": {
        "funcion": "get_detalle_compras_articulo_anio",
        "params": ["articulo", "anios"],
    },
    "detalle_factura_numero": {
        "funcion": "get_detalle_factura_por_numero",
        "params": ["nro_factura"],
    },
    "comparar_proveedor_meses": {
        "funcion": "get_comparacion_proveedor_meses",
        "params": ["proveedor", "mes1", "mes2", "label1", "label2"],
    },
    "comparar_proveedor_anios": {
        "funcion": "get_comparacion_proveedor_anios",
        "params": ["proveedor", "anios", "label1", "label2"],
    },
    "comparar_proveedores_meses": {
        "funcion": "get_comparacion_proveedores_meses",
        "parametros": ["proveedores", "mes1", "mes2", "label1", "label2"],
    },
    "comparar_proveedores_anios": {
        "funcion": "get_comparacion_proveedores_anios",
        "parametros": ["proveedores", "anios", "label1", "label2"],
    },
    "ultima_factura": {
        "funcion": "get_ultima_factura_inteligente",
        "params": ["patron"],
    },
    "facturas_articulo": {
        "funcion": "get_facturas_articulo",
        "params": ["articulo"],
    },
    "stock_total": {
        "funcion": "get_stock_total",
        "params": [],
    },
    "stock_articulo": {
        "funcion": "get_stock_articulo",
        "params": ["articulo"],
    },
    "facturas_proveedor": {
        "funcion": "get_facturas_proveedor_detalle",
        "params": ["proveedores", "meses", "anios", "desde", "hasta", "articulo", "moneda", "limite"],
    },
    "listado_facturas_anio": {
        "funcion": "get_listado_facturas_por_anio",
        "params": ["anio"],
    },
    "total_facturas_por_moneda_anio": {
        "funcion": "get_total_facturas_por_moneda_anio",
        "params": ["anio"],
    },
    "total_facturas_por_moneda_generico": {
        "funcion": "get_total_facturas_por_moneda_todos_anios",
        "params": [],
    },
    "total_compras_por_moneda_generico": {
        "funcion": "get_total_compras_por_moneda_todos_anios",
        "params": [],
    },
    "dashboard_top_proveedores": {
        "funcion": "get_dashboard_top_proveedores",
        "params": ["anio", "top_n", "moneda"],
    },
}

def obtener_info_tipo(tipo: str) -> Optional[Dict]:
    return MAPEO_FUNCIONES.get(tipo)
