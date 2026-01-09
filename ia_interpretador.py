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
# TABLA DE TIPOS
# =====================================================================
TABLA_TIPOS = """
| TIPO | DESCRIPCIÓN | PARÁMETROS | EJEMPLOS |
|------|-------------|------------|----------|
| compras_anio | Todas las compras de un año | anio | "compras 2025" |
| compras_mes | Todas las compras de un mes | mes (YYYY-MM) | "compras noviembre 2025" |
| compras_proveedor_mes | Compras de un proveedor en un mes | proveedor, mes (YYYY-MM) | "compras roche noviembre 2025" |
| comparar_proveedor_meses | Comparar proveedor mes vs mes | proveedor, mes1, mes2, label1, label2 | "comparar compras roche junio julio 2025" |
| comparar_proveedor_anios | Comparar proveedor año vs año | proveedor, anios | "comparar compras roche 2024 2025" |
| detalle_factura_numero | Detalle por número de factura | nro_factura | "detalle factura 273279" / "detalle factura A00273279" |
| facturas_proveedor | Listado de facturas/compras de un proveedor (fusionado) | proveedores, meses?, anios?, desde?, hasta?, articulo?, moneda?, limite? | "todas las facturas roche noviembre 2025" / "compras roche 2025" |
| ultima_factura | Última factura de un artículo/proveedor | patron | "ultima factura vitek" |
| facturas_articulo | Todas las facturas de un artículo | articulo | "cuando vino vitek" |
| stock_total | Resumen total de stock | (ninguno) | "stock total" |
| stock_articulo | Stock de un artículo | articulo | "stock vitek" |
| conversacion | Saludos | (ninguno) | "hola", "gracias" |
| conocimiento | Preguntas generales | (ninguno) | "que es HPV" |
| no_entendido | No se entiende | sugerencia | - |
"""

# =====================================================================
# TABLA CANÓNICA (mínimo; podés extenderla sin romper nada)
# =====================================================================
TABLA_CANONICA_50 = r"""
| # | ACCIÓN | OBJETO | TIEMPO | MULTI | TIPO (output) | PARAMS |
|---|--------|--------|--------|-------|---------------|--------|
| 01 | compras | (ninguno) | anio | no | compras_anio | anio |
| 02 | compras | (ninguno) | mes | no | compras_mes | mes |
| 03 | compras | proveedor | anio | no | facturas_proveedor | proveedores, anios |
| 04 | compras | proveedor | mes | no | compras_proveedor_mes | proveedor, mes |
| 05 | facturas | proveedor | (opcional) | no | facturas_proveedor | proveedores, meses?, anios?, desde?, hasta? |
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
            "comparar", "comparame", "compara",
            "detalle", "nro", "numero",
            "total", "totales",
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "setiembre", "octubre", "noviembre", "diciembre",
            "2023", "2024", "2025", "2026",
            "usd", "dolar", "dolares", "dólar", "dólares", "dollar", "dólar", "dolar",
            "pesos", "peso", "uyu", "uru",
        ]
    )

    # Primero: si alguna palabra está en ALIAS_PROVEEDOR, usar esa
    for tk in toks:
        if not tk or tk in ignorar:
            continue
        if tk in ALIAS_PROVEEDOR:
            return ALIAS_PROVEEDOR[tk]

    # Segundo: devolver primer token "posible" (mínimo 3)
    for tk in toks:
        if not tk or tk in ignorar:
            continue
        if len(tk) >= 3:
            return tk

    return None

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
            r"|\bcomprobante(s)?\b",
            t,
            flags=re.IGNORECASE
        )
    )

def _normalizar_nro_factura(nro: str) -> str:
    return (nro or "").strip().upper()

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

        # =========================
        # 🔧 PARCHE MÍNIMO:
        # Evitar confundir AÑO (2023–2026) como "nro_factura"
        # Ej: "todas las facturas roche 2025" NO debe ir a detalle_factura_numero
        # =========================
        if raw.isdigit():
            try:
                n = int(raw)
                if n in ANIOS_VALIDOS:
                    return None
            except Exception:
                pass

        nro = _normalizar_nro_factura(raw)
        return nro or None

    if re.fullmatch(r"[A-Za-z]?\d{3,}", t):
        # Idem: si el texto ES un año válido, no es nro de factura
        if t.isdigit():
            try:
                n = int(t)
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
    """
    Extrae el límite (número máximo de registros) especificado en el texto.
    Si no se encuentra, devuelve un valor predeterminado.
    """

    # Buscar valores numéricos en el texto
    import re
    numeros = re.findall(r"\b\d+\b", texto)

    # Si se encuentra un número, usar el primero como límite
    for numero in numeros:
        n = int(numero)
        if n > 0:  # Asegurarse de que el límite sea válido
            return n

    # Si no se encuentra ningún número, retornar el valor predeterminado
    return predeterminado

# =====================================================================
# Extraer Monedas
# =====================================================================
def _extraer_moneda(texto: str) -> Optional[str]:
    """
    Extrae la moneda especificada en el texto.
    Retorna:
        - "USD" si detecta dólar,
        - "UYU" o "$" si detecta pesos,
        - None si no se menciona ninguna moneda.
    """

    texto = texto.lower()  # Convertir el texto a minúsculas para simplificar la búsqueda.

    # Monedas y sus palabras clave
    patrones_moneda = {
        "USD": ["usd", "u$s", "u$$", "dólares", "dolares", "dollar", "dólar", "dolar"],
        "UYU": ["pesos", "uyu", "$", "moneda nacional"],
    }

    for moneda, palabras_clave in patrones_moneda.items():
        for palabra in palabras_clave:
            if palabra in texto:
                return moneda

    # No se detectó ninguna moneda
    return None

# =====================================================================
# Extraer rango fechas
# =====================================================================
def _extraer_rango_fechas(texto: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrae un rango de fechas del texto dado.
    Si no encuentra fechas, retorna (None, None).
    """

    # Regex para encontrar fechas en formato YYYY-MM-DD
    patron_fecha = r"\b(\d{4}-\d{2}-\d{2})\b"
    fechas = re.findall(patron_fecha, texto)

    # Si se encuentran 2 o más fechas, las tratamos como rango:
    if len(fechas) >= 2:
        return fechas[0], fechas[1]
    # Si solo hay una fecha, podría estar incompleta:
    elif len(fechas) == 1:
        return fechas[0], None
    # Si no encuentra fechas, retorna None.
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

# =====================================================================
# PARSEO DE PARÁMETROS: Mes a Meses y nuevos campos
# =====================================================================
def normalizar_parametros(params: dict) -> dict:
    """
    Normaliza parámetros relacionados con mes, meses, rango de fechas, moneda y límites.
    """
    if "mes" in params:
        mes = params.get("mes")
        params["meses"] = [mes] if isinstance(mes, str) else mes

    # Manejo de otras claves si necesitas normalizaciones adicionales
    return params

# =====================================================================
#  PARSEO DE RANGO DE FECHAS + MONEDA + LÍMITE
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
    fecha_str = hoy.strftime("%Y-%m-%d")
    return f"""Eres un intérprete de consultas.
- Mes SIEMPRE YYYY-MM.
- Años válidos: 2023–2026.
- Devuelve SOLO JSON: tipo, parametros, debug/sugerencia si aplica.

TABLA TIPOS:
{TABLA_TIPOS}

CANÓNICA:
{TABLA_CANONICA_50}

FECHA: {fecha_str} (mes actual {mes_actual}, año {anio_actual})""".strip()

# =====================================================================
# OPENAI (opcional)
# =====================================================================
def _interpretar_con_openai(pregunta: str) -> Optional[Dict]:
    if not (client and USAR_OPENAI_PARA_DATOS):
        return None

    try:
        response = client.chat_completions.create(
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
            "sugerencia": "Probá: compras roche noviembre 2025 | comparar compras roche junio julio 2025 | detalle factura 273279",
            "debug": "openai error",
        }

# =====================================================================
# MAPEO TIPO → FUNCIÓN SQL
# =====================================================================
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
        "params": ["proveedores", "mes1", "mes2", "label1", "label2"],
    },
    "comparar_proveedores_anios": {
        "funcion": "get_comparacion_proveedores_anios",
        "params": ["proveedores", "anios", "label1", "label2"],
    },
    "ultima_factura": {
        "funcion": "get_ultima_factura_inteligente",
        "params": ["patron"],
    },
    "facturas_articulo": {
        "funcion": "get_facturas_de_articulo",
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
    if not pregunta or not str(pregunta).strip():
        return {"tipo": "no_entendido", "parametros": {}, "debug": "pregunta vacía"}

    texto_original = str(pregunta).strip()
    texto_lower_original = texto_original.lower()

    # =========================
    # FAST-PATH: detalle factura por número (NO mezclar con listado facturas)
    # =========================
    if contiene_factura(texto_lower_original):
        nro = _extraer_nro_factura(texto_original)
        if nro:
            return {
                "tipo": "detalle_factura_numero",
                "parametros": {"nro_factura": nro},
                "debug": f"factura nro={nro}",
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
    # Fallback proveedor (si BD no detectó)
    # =========================
    if not provs:
        prov_libre = _extraer_proveedor_libre(texto_lower_original)
        if prov_libre:
            provs = [_alias_proveedor(prov_libre)]

    # =========================
    # Tiempo: años y meses
    # =========================
    anios = _extraer_anios(texto_lower)
    meses_nombre = _extraer_meses_nombre(texto_lower)
    meses_yyyymm = _extraer_meses_yyyymm(texto_lower)

    # =================================================================
    # FACTURAS PROVEEDOR (LISTADO/DETALLE) - Fusionado con "todas las compras"
    # =================================================================
    dispara_facturas_listado = False

    # Si pide facturas/comprobantes y NO dio nro -> listado
    if contiene_factura(texto_lower_original) and (_extraer_nro_factura(texto_original) is None):
        dispara_facturas_listado = True

    # Fusionar: También "todas las compras/facturas/comprobantes" -> listado
    if (
        re.search(r"\b(todas|todoas)\b", texto_lower_original)
        and re.search(r"\b(compras?|facturas?|comprobantes?)\b", texto_lower_original)
        and (_extraer_nro_factura(texto_original) is None)
    ):
        dispara_facturas_listado = True

    if dispara_facturas_listado:
        # ✅ CORREGIDO: usar fallback si BD no detectó proveedor
        proveedores_lista: List[str] = []
        if provs:
            proveedores_lista = [provs[0]]
        else:
            # 🔧 FALLBACK: intentar extraer proveedor libre
            prov_libre = _extraer_proveedor_libre(texto_lower_original)
            if prov_libre:
                proveedores_lista = [_alias_proveedor(prov_libre)]

        if not proveedores_lista:
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": "Indicá el proveedor. Ej: todas las facturas de Roche noviembre 2025.",
                "debug": "facturas_proveedor: no encontró proveedor (ni en BD ni libre)",
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

        # 🔴 CLAVE: artículo SOLO si el usuario lo pidió explícitamente
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
            "debug": f"facturas/compras proveedor(es): {', '.join(proveedores_lista)} | meses: {meses_out} | años: {anios}",
        }

    # =========================
    # COMPRAS (no comparar, fusionado con facturas_proveedor para proveedor+año)
    # =========================
    if contiene_compras(texto_lower_original) and not contiene_comparar(texto_lower_original):
        # Fusionar: compras con proveedor + año -> facturas_proveedor (mismo SQL que facturas)
        if provs and anios:
            proveedor = _alias_proveedor(provs[0])
            return {
                "tipo": "facturas_proveedor",
                "parametros": {
                    "proveedores": [proveedor],
                    "anios": [anios[0]],
                    "limite": 5000,
                },
                "debug": "compras proveedor año (fusionado con facturas_proveedor)",
            }

        # Compras proveedor (mes) - queda separado si no hay año
        if provs and (meses_yyyymm or (meses_nombre and anios)):
            proveedor = _alias_proveedor(provs[0])
            if meses_yyyymm:
                mes = meses_yyyymm[0]
            else:
                mes = _to_yyyymm(anios[0], meses_nombre[0]) if anios and meses_nombre else None

            if mes:
                return {
                    "tipo": "compras_proveedor_mes",
                    "parametros": {"proveedor": proveedor, "mes": mes},
                    "debug": "compras proveedor mes",
                }

        # Compras mes
        if meses_yyyymm:
            return {"tipo": "compras_mes", "parametros": {"mes": meses_yyyymm[0]}, "debug": "compras mes (yyyymm)"}
        if meses_nombre and anios:
            mes = _to_yyyymm(anios[0], meses_nombre[0])
            return {"tipo": "compras_mes", "parametros": {"mes": mes}, "debug": "compras mes (nombre+año)"}

        # Compras año (sin proveedor)
        if anios:
            return {"tipo": "compras_anio", "parametros": {"anio": anios[0]}, "debug": "compras año"}

    # =========================
    # COMPARAR COMPRAS
    # =========================
    if contiene_comparar(texto_lower_original):
        meses_cmp: List[str] = []
        if meses_yyyymm:
            meses_cmp = meses_yyyymm[:2]
        elif meses_nombre and anios:
            for mn in meses_nombre[:2]:
                meses_cmp.append(_to_yyyymm(anios[0], mn))

        if len(meses_cmp) == 2:
            if len(provs) >= 2:
                return {
                    "tipo": "comparar_proveedores_meses",
                    "parametros": {
                        "proveedores": [_alias_proveedor(p) for p in provs[:MAX_PROVEEDORES]],
                        "mes1": meses_cmp[0],
                        "mes2": meses_cmp[1],
                        "label1": meses_cmp[0],
                        "label2": meses_cmp[1],
                    },
                    "debug": "comparar proveedores meses",
                }
            if len(provs) == 1:
                return {
                    "tipo": "comparar_proveedor_meses",
                    "parametros": {
                        "proveedor": _alias_proveedor(provs[0]),
                        "mes1": meses_cmp[0],
                        "mes2": meses_cmp[1],
                        "label1": meses_cmp[0],
                        "label2": meses_cmp[1],
                    },
                    "debug": "comparar proveedor meses",
                }

        if len(anios) >= 2:
            if len(provs) >= 2:
                return {
                    "tipo": "comparar_proveedores_anios",
                    "parametros": {
                        "proveedores": [_alias_proveedor(p) for p in provs[:MAX_PROVEEDORES]],
                        "anios": anios[:2],
                        "label1": str(anios[0]),
                        "label2": str(anios[1]),
                    },
                    "debug": "comparar proveedores años",
                }
            if len(provs) == 1:
                return {
                    "tipo": "comparar_proveedor_anios",
                    "parametros": {
                        "proveedor": _alias_proveedor(provs[0]),
                        "anios": anios[:2],
                        "label1": str(anios[0]),
                        "label2": str(anios[1]),
                    },
                    "debug": "comparar proveedor años",
                }

        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "Ej: comparar compras roche junio julio 2025 | comparar compras roche 2024 2025",
            "debug": "comparar: faltan 2 meses o 2 años (o proveedor)",
        }

    # =========================
    # STOCK
    # =========================
    if "stock" in texto_lower_original:
        if arts:
            return {"tipo": "stock_articulo", "parametros": {"articulo": arts[0]}, "debug": "stock articulo"}
        return {"tipo": "stock_total", "parametros": {}, "debug": "stock total"}

    # =========================
    # DEFAULT: OpenAI (si está habilitado)
    # =========================
    out_ai = _interpretar_con_openai(texto_original)
    if out_ai:
        return out_ai

    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: compras roche noviembre 2025 | comparar compras roche junio julio 2025 | detalle factura 273279 | todas las facturas roche 2025",
        "debug": "no match",
    }
