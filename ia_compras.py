# =========================================================================================
# IA_COMPRAS.PY - INTÉRPRETE COMPRAS (CANÓNICO) - VERSIÓN COMPLETA CON DOCUMENTACIÓN
# =========================================================================================
"""
📋 DOCUMENTACIÓN COMPLETA - AI INTÉRPRETE COMPRAS

🎯 OBJETIVO:
    Interpretar consultas en lenguaje natural sobre compras de Fertilab y convertirlas
    en queries SQL precisas contra la tabla chatbot_raw en Supabase.

📊 ESTRUCTURA DE LA TABLA chatbot_raw:
    ╔══════════════════════════╗
    ║   chatbot_raw            ║
    ╠══════════════════════════╣
    ║ 📄 Tipo Comprobante      ║ → "Compra Crédito", "Compra Contado"
    ║ 📄 Tipo CFE              ║ → NULL (generalmente)
    ║ 📄 Nro. Comprobante      ║ → "A00055313"
    ║ 💰 Moneda                ║ → "UYU" o "USD"
    ║ 💰 Cliente / Proveedor   ║ → "BIOKEY SRL", "ROCHE URUGUAY S.A."
    ║ 📦 Familia               ║ → "FB", "AF", "TR"
    ║ 📦 Tipo Articulo         ║ → "REACTIVOS", "INSUMOS"
    ║ 📦 Articulo              ║ → "OBIS - PYR X 60 DET"
    ║ 📅 Año                   ║ → 2025 (INTEGER)
    ║ 📅 Mes                   ║ → "2025-12" (STRING formato YYYY-MM)
    ║ 📅 Fecha                 ║ → "2025-12-23" (STRING formato YYYY-MM-DD)
    ║ 💵 Cantidad              ║ → "  1,00 " (STRING con espacios)
    ║ 💵 Monto Neto            ║ → "  194,40 " o "(194,40)" negativo
    ║ 📊 stock_actual          ║ → 1.00 (NUMERIC, puede ser NULL)
    ╚══════════════════════════╝

🔍 REGLAS CRÍTICAS DE INTERPRETACIÓN:

    1️⃣ EXTRACCIÓN DE AÑO:
        - Usuario NUNCA pregunta "2025", pregunta: "compras 2025" o "noviembre 2025"
        - Fuentes posibles:
            ✅ Columna "Año" → Valor directo: 2025
            ✅ Columna "Mes" → Extraer: "2025-12" → 2025
            ✅ Columna "Fecha" → Extraer: "2025-12-23" → 2025
        - SQL: WHERE "Año" = 2025

    2️⃣ EXTRACCIÓN DE MES:
        - Usuario SIEMPRE pregunta con NOMBRE: "noviembre 2025", "compras diciembre"
        - Conversión necesaria: "noviembre" → "11" → "2025-11"
        - Fuentes posibles:
            ✅ Columna "Mes" → Ya está en formato "2025-12"
            ✅ Columna "Fecha" → Extraer: "2025-12-23" → "2025-12"
        - SQL: WHERE "Mes" = '2025-11' OR "Fecha" LIKE '2025-11-%'

    3️⃣ EXTRACCIÓN DE PROVEEDOR:
        - Usuario puede preguntar:
            ✅ Nombre exacto: "compras Roche"
            ✅ Nombre parcial: "compras biokey"
            ✅ Nombre completo: "compras ROCHE URUGUAY S.A."
        - Normalización: lowercase + sin acentos + TRIM
        - SQL: WHERE LOWER(TRIM("Cliente / Proveedor")) LIKE '%roche%'

    4️⃣ FORMATO DE MONTOS:
        A) Positivo: "  1.500,00 " → 1500.00
        B) Negativo: "(1.500,00)" → -1500.00
        - Punto (.) = separador de miles → ELIMINAR
        - Coma (,) = separador decimal → REEMPLAZAR por punto
        - Paréntesis = negativo → multiplicar por -1

    5️⃣ FORMATO DE CANTIDADES:
        - Similar a montos pero SIEMPRE positivo
        - "  1,00 " → 1.00
        - " 150,50 " → 150.50

🎯 TIPOS DE CONSULTAS SOPORTADAS:

    📌 TIPO 1: compras_mes
        - "compras noviembre 2025"
        - "compras diciembre"
        - Parámetros: {"mes": "2025-11"}

    📌 TIPO 2: compras_anio
        - "compras 2025"
        - "compras del año pasado"
        - Parámetros: {"anio": 2025}

    📌 TIPO 3: compras_proveedor_mes
        - "compras roche noviembre 2025"
        - "cuánto compré a biokey en diciembre"
        - Parámetros: {"proveedor": "roche", "mes": "2025-11"}

    📌 TIPO 4: compras_proveedor_anio
        - "compras roche 2025"
        - "cuánto gasté en biokey este año"
        - Parámetros: {"proveedor": "roche", "anio": 2025}

    📌 TIPO 5: compras_articulo_mes
        - "compras de reactivos noviembre 2025"
        - "cuánto compré de OBIS en diciembre"
        - Parámetros: {"articulo": "reactivos", "mes": "2025-11"}

    📌 TIPO 6: compras_articulo_anio
        - "compras de reactivos 2025"
        - Parámetros: {"articulo": "reactivos", "anio": 2025}

⚠️ CASOS ESPECIALES:

    🔸 Usuario no especifica año:
        → Asumir año actual (2025)
        → "compras noviembre" → "2025-11"

    🔸 Usuario no especifica moneda:
        → Por defecto UYU (pesos uruguayos)
        → Si pregunta "en dólares" → USD

    🔸 Proveedor no encontrado:
        → Intentar match parcial con LIKE '%keyword%'
        → Usar "proveedor libre" (texto extraído)

    🔸 Múltiples proveedores detectados:
        → Tomar el primero (max 5)

    🔸 Montos negativos:
        → Representan devoluciones o notas de crédito
        → Se restan automáticamente del total

🧪 EJEMPLOS DE INTERPRETACIÓN:

    Input: "compras noviembre 2025"
    Output: {
        "tipo": "compras_mes",
        "parametros": {"mes": "2025-11"},
        "debug": "compras mes (nombre+anio)"
    }

    Input: "compras roche noviembre 2025"
    Output: {
        "tipo": "compras_proveedor_mes",
        "parametros": {"proveedor": "ROCHE URUGUAY S.A.", "mes": "2025-11"},
        "debug": "compras proveedor mes (nombre+anio)"
    }

    Input: "compras 2025"
    Output: {
        "tipo": "compras_anio",
        "parametros": {"anio": 2025},
        "debug": "compras año"
    }

📚 PRIORIDAD DE FUENTES:

    Para AÑO:
        1. Columna "Año" (más confiable)
        2. Columna "Mes" (extraer primeros 4 chars)
        3. Columna "Fecha" (extraer primeros 4 chars)

    Para MES:
        1. Columna "Mes" (ya está en formato YYYY-MM)
        2. Columna "Fecha" (extraer primeros 7 chars)

    Para PROVEEDOR:
        1. Match exacto en lista de proveedores
        2. Match parcial con LIKE
        3. Proveedor libre (texto extraído)

🔧 VALIDACIONES OBLIGATORIAS:

    ✅ Año está en rango válido (2023-2026)
    ✅ Mes está en rango válido (01-12)
    ✅ Formato de mes es YYYY-MM
    ✅ Proveedor/artículo no está vacío
    ✅ Hay al menos UN filtro temporal (mes O año)

🚀 SQL TEMPLATES PARA CADA TIPO:

    compras_mes:
        SELECT "Cliente / Proveedor", COUNT(*), SUM(monto)
        FROM chatbot_raw
        WHERE "Mes" = '2025-11'
        AND "Moneda" = 'UYU'
        GROUP BY "Cliente / Proveedor"
        ORDER BY SUM(monto) DESC

    compras_anio:
        SELECT "Cliente / Proveedor", COUNT(*), SUM(monto)
        FROM chatbot_raw
        WHERE "Año" = 2025
        AND "Moneda" = 'UYU'
        GROUP BY "Cliente / Proveedor"
        ORDER BY SUM(monto) DESC

    compras_proveedor_mes:
        SELECT "Articulo", COUNT(*), SUM(cantidad), SUM(monto)
        FROM chatbot_raw
        WHERE LOWER(TRIM("Cliente / Proveedor")) LIKE '%roche%'
        AND "Mes" = '2025-11'
        AND "Moneda" = 'UYU'
        GROUP BY "Articulo"
        ORDER BY SUM(monto) DESC

    compras_proveedor_anio:
        SELECT "Mes", COUNT(*), SUM(monto)
        FROM chatbot_raw
        WHERE LOWER(TRIM("Cliente / Proveedor")) LIKE '%roche%'
        AND "Año" = 2025
        AND "Moneda" = 'UYU'
        GROUP BY "Mes"
        ORDER BY "Mes" DESC

📖 PARSEO DE MONTOS (SQL):

    CASE
        -- Si tiene paréntesis (negativo)
        WHEN REPLACE("Monto Neto",' ','') LIKE '(%)' THEN
            -1 * CAST(
                REPLACE(
                    REPLACE(
                        SUBSTRING(REPLACE("Monto Neto",' ',''), 2,
                            LENGTH(REPLACE("Monto Neto",' ','')) - 2),
                        '.', ''
                    ),
                    ',', '.'
                ) AS NUMERIC
            )
        -- Si es monto normal
        ELSE
            CAST(
                REPLACE(
                    REPLACE(REPLACE("Monto Neto",' ',''), '.', ''),
                    ',', '.'
                ) AS NUMERIC
            )
    END

📖 PARSEO DE CANTIDADES (SQL):

    CAST(
        REPLACE(REPLACE("Cantidad", '.', ''), ',', '.')
        AS NUMERIC
    )

✨ CASOS NO SOPORTADOS (devolver "no_entendido"):

    - Comparaciones entre años ("compara 2024 vs 2025")
    - Queries con múltiples proveedores ("compras roche y biokey")
    - Fechas específicas ("compras del 15 de noviembre")
    - Artículos sin contexto temporal

    Sugerencia: "Probá: compras roche noviembre 2025 | compras noviembre 2025 | compras 2025"
"""

import os
import re
import unicodedata
from typing import Dict, List, Tuple, Optional
from datetime import datetime

import streamlit as st

# =========================================================================================
# CONFIGURACIÓN
# =========================================================================================

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
    "setiembre": "09",  # Variante uruguaya
    "octubre": "10",
    "noviembre": "11",
    "diciembre": "12",
}

ANIOS_VALIDOS = {2023, 2024, 2025, 2026}

# Límites de detección
MAX_PROVEEDORES = 5
MAX_ARTICULOS = 5
MAX_MESES = 6
MAX_ANIOS = 4

# Año por defecto si no se especifica
ANIO_DEFAULT = 2025

# Moneda por defecto
MONEDA_DEFAULT = "UYU"

# =========================================================================================
# HELPERS NORMALIZACIÓN
# =========================================================================================

def _strip_accents(s: str) -> str:
    """
    Elimina acentos de un string.
    
    Ejemplo:
        _strip_accents("Artículo") → "Articulo"
    """
    if not s:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _key(s: str) -> str:
    """
    Normaliza un string: lowercase, sin acentos, solo alfanumérico.
    
    Ejemplo:
        _key("ROCHE URUGUAY S.A.") → "rocheuruguaysa"
    """
    s = _strip_accents((s or "").lower().strip())
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _tokens(texto: str) -> List[str]:
    """
    Extrae tokens válidos (palabras) de un texto.
    Solo incluye tokens con 3+ caracteres normalizados.
    
    Ejemplo:
        _tokens("compras Roche noviembre 2025") → ["compras", "roche", "noviembre", "2025"]
    """
    raw = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]+", (texto or "").lower())
    out: List[str] = []
    for t in raw:
        k = _key(t)
        if len(k) >= 3:
            out.append(k)
    return out


# =========================================================================================
# CARGA LISTAS DESDE SUPABASE (cache)
# =========================================================================================

@st.cache_data(ttl=60 * 60)
def _cargar_listas_supabase() -> Dict[str, List[str]]:
    """
    Carga listas de proveedores y artículos desde Supabase.
    
    Retorna:
        {"proveedores": [...], "articulos": [...]}
    
    Tablas consultadas:
        - proveedores: columna "nombre"
        - articulos: columna "Descripción"
    """
    proveedores: List[str] = []
    articulos: List[str] = []

    try:
        from supabase_client import supabase  # type: ignore
        if supabase is None:
            return {"proveedores": [], "articulos": []}

        # ======= PROVEEDORES =======
        # Intentar diferentes variantes de nombre de columna
        for col in ["nombre", "Nombre", "NOMBRE"]:
            try:
                res = supabase.table("proveedores").select(col).execute()
                data = res.data or []
                proveedores = [str(r.get(col)).strip() for r in data if r.get(col)]
                if proveedores:
                    break
            except Exception:
                continue

        # ======= ARTÍCULOS =======
        # Intentar diferentes variantes de nombre de columna
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

    # Limpiar duplicados y ordenar
    proveedores = sorted(list(set([p for p in proveedores if p])))
    articulos = sorted(list(set([a for a in articulos if a])))

    return {"proveedores": proveedores, "articulos": articulos}


def _get_indices() -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """
    Obtiene índices de proveedores y artículos.
    
    Retorna:
        ([(nombre_original, nombre_normalizado), ...],
         [(articulo_original, articulo_normalizado), ...])
    
    Ejemplo:
        ([("ROCHE URUGUAY S.A.", "rocheuruguaysa"), ...],
         [("OBIS - PYR X 60 DET", "obispyrx60det"), ...])
    """
    listas = _cargar_listas_supabase()
    prov = [(p, _key(p)) for p in (listas.get("proveedores") or []) if p]
    art = [(a, _key(a)) for a in (listas.get("articulos") or []) if a]
    return prov, art


def _match_best(texto: str, index: List[Tuple[str, str]], max_items: int = 1) -> List[str]:
    """
    Encuentra los mejores matches de un texto contra un índice.
    
    Prioridad:
        1. Match exacto (token normalizado == nombre normalizado)
        2. Substring (token está contenido en nombre, ordenado por score)
    
    Args:
        texto: Texto de consulta del usuario
        index: Lista de (nombre_original, nombre_normalizado)
        max_items: Máximo número de resultados
    
    Retorna:
        Lista de nombres originales que hacen match
    
    Ejemplo:
        _match_best("roche", index_proveedores, 1) → ["ROCHE URUGUAY S.A."]
    """
    toks = _tokens(texto)
    if not toks or not index:
        return []

    # ======= PRIORIDAD 1: MATCH EXACTO =======
    toks_set = set(toks)
    for orig, norm in index:
        if norm in toks_set:
            return [orig]  # Retorna inmediatamente el match exacto

    # ======= PRIORIDAD 2: SUBSTRING + SCORE =======
    candidatos: List[Tuple[int, str]] = []
    for orig, norm in index:
        for tk in toks:
            if tk and tk in norm:
                # Score: prioriza matches largos en nombres cortos
                score = (len(tk) * 1000) - len(norm)
                candidatos.append((score, orig))

    if not candidatos:
        return []

    # Ordenar por score descendente, luego alfabéticamente
    candidatos.sort(key=lambda x: (-x[0], x[1]))
    
    # Retornar top N sin duplicados
    out: List[str] = []
    seen = set()
    for _, orig in candidatos:
        if orig not in seen:
            seen.add(orig)
            out.append(orig)
        if len(out) >= max_items:
            break

    return out


# =========================================================================================
# PARSEO TIEMPO
# =========================================================================================

def _extraer_anios(texto: str) -> List[int]:
    """
    Extrae años válidos del texto (2023-2026).
    
    Ejemplo:
        _extraer_anios("compras roche 2025") → [2025]
        _extraer_anios("2024 vs 2025") → [2024, 2025]
    """
    anios = re.findall(r"(2023|2024|2025|2026)", texto or "")
    out: List[int] = []
    for a in anios:
        try:
            out.append(int(a))
        except Exception:
            pass
    
    # Remover duplicados preservando orden
    seen = set()
    out2: List[int] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            out2.append(x)
    
    return out2[:MAX_ANIOS]


def _extraer_meses_nombre(texto: str) -> List[str]:
    """
    Extrae nombres de meses del texto.
    
    Ejemplo:
        _extraer_meses_nombre("compras noviembre") → ["noviembre"]
        _extraer_meses_nombre("enero y febrero") → ["enero", "febrero"]
    """
    tl = (texto or "").lower()
    ms = [m for m in MESES.keys() if m in tl]
    
    # Remover duplicados preservando orden
    seen = set()
    out: List[str] = []
    for m in ms:
        if m not in seen:
            seen.add(m)
            out.append(m)
    
    return out[:MAX_MESES]


def _extraer_meses_yyyymm(texto: str) -> List[str]:
    """
    Extrae meses en formato YYYY-MM del texto.
    
    Ejemplo:
        _extraer_meses_yyyymm("2025-11") → ["2025-11"]
        _extraer_meses_yyyymm("2024/03") → ["2024-03"]
    """
    ms = re.findall(r"(2023|2024|2025|2026)[-/](0[1-9]|1[0-2])", texto or "")
    out = [f"{a}-{m}" for a, m in ms]
    
    # Remover duplicados preservando orden
    seen = set()
    out2: List[str] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            out2.append(x)
    
    return out2[:MAX_MESES]


def _to_yyyymm(anio: int, mes_nombre: str) -> str:
    """
    Convierte año + nombre de mes a formato YYYY-MM.
    
    Ejemplo:
        _to_yyyymm(2025, "noviembre") → "2025-11"
        _to_yyyymm(2024, "enero") → "2024-01"
    """
    return f"{anio}-{MESES[mes_nombre]}"


def _detectar_moneda(texto: str) -> str:
    """
    Detecta si el usuario especificó una moneda.
    
    Ejemplo:
        _detectar_moneda("compras en dólares") → "USD"
        _detectar_moneda("compras roche") → "UYU"
    """
    texto_lower = texto.lower()
    
    # Detectar USD / dólares
    if any(kw in texto_lower for kw in ["dolar", "dólar", "usd", "dolares", "dólares"]):
        return "USD"
    
    # Detectar EUR / euros
    if any(kw in texto_lower for kw in ["euro", "euros", "eur"]):
        return "EUR"
    
    # Default: UYU
    return MONEDA_DEFAULT


# =========================================================================================
# EXTRACCIÓN DE PROVEEDOR LIBRE
# =========================================================================================

def _extraer_proveedor_libre(texto: str, meses_encontrados: List[str], anios_encontrados: List[int]) -> Optional[str]:
    """
    Intenta extraer un proveedor "libre" del texto cuando no hay match en la lista.
    
    Proceso:
        1. Remueve palabra "compras"
        2. Remueve nombres de meses
        3. Remueve años
        4. Lo que queda (si tiene 3+ chars) es el proveedor
    
    Ejemplo:
        _extraer_proveedor_libre("compras biokey noviembre 2025", ["noviembre"], [2025])
        → "biokey"
    """
    tmp = texto.lower()
    
    # Remover palabra "compras"
    tmp = re.sub(r"\bcompras?\b", "", tmp).strip()
    
    # Remover nombres de meses
    for mes in MESES.keys():
        tmp = re.sub(rf"\b{mes}\b", "", tmp)
    
    # Remover años
    tmp = re.sub(r"\b(2023|2024|2025|2026)\b", "", tmp).strip()
    
    # Limpiar espacios múltiples
    tmp = re.sub(r"\s+", " ", tmp).strip()
    
    # Si queda algo con 3+ caracteres, es un proveedor
    if tmp and len(tmp) >= 3:
        return tmp
    
    return None


# =========================================================================================
# INTÉRPRETE PRINCIPAL
# =========================================================================================

def interpretar_compras(pregunta: str) -> Dict:
    """
    Interpreta una consulta de compras en lenguaje natural.
    
    Args:
        pregunta: Consulta del usuario
    
    Retorna:
        {
            "tipo": str,              # Tipo de consulta
            "parametros": dict,       # Parámetros extraídos
            "debug": str,             # Info de debug
            "moneda": str,            # Moneda detectada (opcional)
            "sugerencia": str         # Sugerencia (si no_entendido)
        }
    
    Tipos soportados:
        - compras_mes
        - compras_anio
        - compras_proveedor_mes
        - compras_proveedor_anio
        - compras_articulo_mes
        - compras_articulo_anio
        - no_entendido
    
    Ejemplos:
        interpretar_compras("compras noviembre 2025")
        → {"tipo": "compras_mes", "parametros": {"mes": "2025-11"}, ...}
        
        interpretar_compras("compras roche 2025")
        → {"tipo": "compras_proveedor_anio", "parametros": {"proveedor": "ROCHE...", "anio": 2025}, ...}
    """
    texto = (pregunta or "").strip()
    texto_lower = texto.lower().strip()

    # ======= CARGAR ÍNDICES =======
    idx_prov, idx_art = _get_indices()
    
    # ======= EXTRAER ENTIDADES =======
    provs = _match_best(texto_lower, idx_prov, max_items=MAX_PROVEEDORES)
    arts = _match_best(texto_lower, idx_art, max_items=MAX_ARTICULOS)
    
    # ======= EXTRAER TIEMPO =======
    anios = _extraer_anios(texto_lower)
    meses_nombre = _extraer_meses_nombre(texto_lower)
    meses_yyyymm = _extraer_meses_yyyymm(texto_lower)
    
    # ======= DETECTAR MONEDA =======
    moneda = _detectar_moneda(texto_lower)

    # =========================================================================================
    # LÓGICA DE INTERPRETACIÓN - COMPRAS
    # =========================================================================================
    
    if ("compra" in texto_lower) and ("comparar" not in texto_lower):
        
        # ======= FALLBACK: PROVEEDOR LIBRE =======
        proveedor_libre = None
        if not provs:
            proveedor_libre = _extraer_proveedor_libre(texto_lower, meses_nombre, anios)
        
        proveedor_final = provs[0] if provs else proveedor_libre
        articulo_final = arts[0] if arts else None

        # =========================================================================================
        # CASO 1: COMPRAS PROVEEDOR + MES
        # =========================================================================================
        if proveedor_final:
            # Mes en formato YYYY-MM explícito
            if len(meses_yyyymm) >= 1:
                return {
                    "tipo": "compras_proveedor_mes",
                    "parametros": {
                        "proveedor": proveedor_final,
                        "mes": meses_yyyymm[0]
                    },
                    "moneda": moneda,
                    "debug": "compras proveedor mes (YYYY-MM)",
                }

            # Mes nombre + año
            if len(meses_nombre) >= 1 and len(anios) >= 1:
                mes_key = _to_yyyymm(anios[0], meses_nombre[0])
                return {
                    "tipo": "compras_proveedor_mes",
                    "parametros": {
                        "proveedor": proveedor_final,
                        "mes": mes_key
                    },
                    "moneda": moneda,
                    "debug": "compras proveedor mes (nombre+anio)",
                }
            
            # Solo mes nombre (asume año actual)
            if len(meses_nombre) >= 1:
                mes_key = _to_yyyymm(ANIO_DEFAULT, meses_nombre[0])
                return {
                    "tipo": "compras_proveedor_mes",
                    "parametros": {
                        "proveedor": proveedor_final,
                        "mes": mes_key
                    },
                    "moneda": moneda,
                    "debug": f"compras proveedor mes (nombre, asume año {ANIO_DEFAULT})",
                }

        # =========================================================================================
        # CASO 2: COMPRAS PROVEEDOR + AÑO
        # =========================================================================================
            if len(anios) >= 1:
                return {
                    "tipo": "compras_proveedor_anio",
                    "parametros": {
                        "proveedor": proveedor_final,
                        "anio": anios[0]
                    },
                    "moneda": moneda,
                    "debug": "compras proveedor año",
                }

        # =========================================================================================
        # CASO 3: COMPRAS ARTÍCULO + MES
        # =========================================================================================
        if articulo_final:
            # Mes en formato YYYY-MM explícito
            if len(meses_yyyymm) >= 1:
                return {
                    "tipo": "compras_articulo_mes",
                    "parametros": {
                        "articulo": articulo_final,
                        "mes": meses_yyyymm[0]
                    },
                    "moneda": moneda,
                    "debug": "compras articulo mes (YYYY-MM)",
                }

            # Mes nombre + año
            if len(meses_nombre) >= 1 and len(anios) >= 1:
                mes_key = _to_yyyymm(anios[0], meses_nombre[0])
                return {
                    "tipo": "compras_articulo_mes",
                    "parametros": {
                        "articulo": articulo_final,
                        "mes": mes_key
                    },
                    "moneda": moneda,
                    "debug": "compras articulo mes (nombre+anio)",
                }
            
            # Solo mes nombre (asume año actual)
            if len(meses_nombre) >= 1:
                mes_key = _to_yyyymm(ANIO_DEFAULT, meses_nombre[0])
                return {
                    "tipo": "compras_articulo_mes",
                    "parametros": {
                        "articulo": articulo_final,
                        "mes": mes_key
                    },
                    "moneda": moneda,
                    "debug": f"compras articulo mes (nombre, asume año {ANIO_DEFAULT})",
                }

        # =========================================================================================
        # CASO 4: COMPRAS ARTÍCULO + AÑO
        # =========================================================================================
            if len(anios) >= 1:
                return {
                    "tipo": "compras_articulo_anio",
                    "parametros": {
                        "articulo": articulo_final,
                        "anio": anios[0]
                    },
                    "moneda": moneda,
                    "debug": "compras articulo año",
                }

        # =========================================================================================
        # CASO 5: COMPRAS (SIN PROVEEDOR/ARTÍCULO) + MES
        # =========================================================================================
        
        # Mes en formato YYYY-MM explícito
        if len(meses_yyyymm) >= 1:
            return {
                "tipo": "compras_mes",
                "parametros": {"mes": meses_yyyymm[0]},
                "moneda": moneda,
                "debug": "compras mes (YYYY-MM)",
            }

        # Mes nombre + año
        if len(meses_nombre) >= 1 and len(anios) >= 1:
            mes_key = _to_yyyymm(anios[0], meses_nombre[0])
            return {
                "tipo": "compras_mes",
                "parametros": {"mes": mes_key},
                "moneda": moneda,
                "debug": "compras mes (nombre+anio)",
            }
        
        # Solo mes nombre (asume año actual)
        if len(meses_nombre) >= 1:
            mes_key = _to_yyyymm(ANIO_DEFAULT, meses_nombre[0])
            return {
                "tipo": "compras_mes",
                "parametros": {"mes": mes_key},
                "moneda": moneda,
                "debug": f"compras mes (nombre, asume año {ANIO_DEFAULT})",
            }

        # =========================================================================================
        # CASO 6: COMPRAS (SIN PROVEEDOR/ARTÍCULO) + AÑO
        # =========================================================================================
        if len(anios) >= 1:
            return {
                "tipo": "compras_anio",
                "parametros": {"anio": anios[0]},
                "moneda": moneda,
                "debug": "compras año",
            }

    # =========================================================================================
    # FALLBACK FINAL - NO ENTENDIDO
    # =========================================================================================
    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: compras roche noviembre 2025 | compras noviembre 2025 | compras 2025",
        "debug": "compras: no match",
    }


# =========================================================================================
# HELPER PARA GENERAR SQL (OPCIONAL - para referencia)
# =========================================================================================

def generar_sql_referencia(resultado: Dict) -> str:
    """
    Genera SQL de referencia para cada tipo de consulta.
    
    NOTA: Esta función es solo para DOCUMENTACIÓN. El SQL real se genera
          en el módulo que consume este intérprete.
    
    Args:
        resultado: Dict retornado por interpretar_compras()
    
    Retorna:
        String con SQL de ejemplo
    """
    tipo = resultado.get("tipo")
    params = resultado.get("parametros", {})
    moneda = resultado.get("moneda", "UYU")
    
    # Template de parseo de montos
    monto_parse = """
        CASE
            WHEN REPLACE("Monto Neto",' ','') LIKE '(%)' THEN
                -1 * CAST(
                    REPLACE(
                        REPLACE(
                            SUBSTRING(REPLACE("Monto Neto",' ',''), 2, 
                                LENGTH(REPLACE("Monto Neto",' ','')) - 2),
                            '.', ''
                        ),
                        ',', '.'
                    ) AS NUMERIC
                )
            ELSE
                CAST(
                    REPLACE(
                        REPLACE(REPLACE("Monto Neto",' ',''), '.', ''),
                        ',', '.'
                    ) AS NUMERIC
                )
        END
    """
    
    if tipo == "compras_mes":
        mes = params.get("mes")
        return f"""
SELECT 
    "Cliente / Proveedor" as proveedor,
    COUNT(*) as operaciones,
    SUM({monto_parse}) as total_{moneda.lower()}
FROM chatbot_raw
WHERE "Mes" = '{mes}'
    AND "Moneda" = '{moneda}'
    AND "Monto Neto" IS NOT NULL
GROUP BY "Cliente / Proveedor"
ORDER BY total_{moneda.lower()} DESC
LIMIT 10;
        """
    
    elif tipo == "compras_anio":
        anio = params.get("anio")
        return f"""
SELECT 
    "Cliente / Proveedor" as proveedor,
    COUNT(*) as operaciones,
    SUM({monto_parse}) as total_{moneda.lower()}
FROM chatbot_raw
WHERE "Año" = {anio}
    AND "Moneda" = '{moneda}'
    AND "Monto Neto" IS NOT NULL
GROUP BY "Cliente / Proveedor"
ORDER BY total_{moneda.lower()} DESC
LIMIT 10;
        """
    
    elif tipo == "compras_proveedor_mes":
        proveedor = params.get("proveedor", "").lower()
        mes = params.get("mes")
        return f"""
SELECT 
    "Articulo",
    COUNT(*) as operaciones,
    SUM({monto_parse}) as monto_total
FROM chatbot_raw
WHERE LOWER(TRIM("Cliente / Proveedor")) LIKE '%{proveedor}%'
    AND "Mes" = '{mes}'
    AND "Moneda" = '{moneda}'
    AND "Monto Neto" IS NOT NULL
GROUP BY "Articulo"
ORDER BY monto_total DESC
LIMIT 10;
        """
    
    elif tipo == "compras_proveedor_anio":
        proveedor = params.get("proveedor", "").lower()
        anio = params.get("anio")
        return f"""
SELECT 
    "Mes",
    COUNT(*) as operaciones,
    SUM({monto_parse}) as monto_total
FROM chatbot_raw
WHERE LOWER(TRIM("Cliente / Proveedor")) LIKE '%{proveedor}%'
    AND "Año" = {anio}
    AND "Moneda" = '{moneda}'
    AND "Monto Neto" IS NOT NULL
GROUP BY "Mes"
ORDER BY "Mes" DESC;
        """
    
    elif tipo == "compras_articulo_mes":
        articulo = params.get("articulo", "").lower()
        mes = params.get("mes")
        return f"""
SELECT 
    "Cliente / Proveedor" as proveedor,
    COUNT(*) as operaciones,
    SUM({monto_parse}) as monto_total
FROM chatbot_raw
WHERE LOWER(TRIM("Articulo")) LIKE '%{articulo}%'
    AND "Mes" = '{mes}'
    AND "Moneda" = '{moneda}'
    AND "Monto Neto" IS NOT NULL
GROUP BY "Cliente / Proveedor"
ORDER BY monto_total DESC
LIMIT 10;
        """
    
    elif tipo == "compras_articulo_anio":
        articulo = params.get("articulo", "").lower()
        anio = params.get("anio")
        return f"""
SELECT 
    "Mes",
    COUNT(*) as operaciones,
    SUM({monto_parse}) as monto_total
FROM chatbot_raw
WHERE LOWER(TRIM("Articulo")) LIKE '%{articulo}%'
    AND "Año" = {anio}
    AND "Moneda" = '{moneda}'
    AND "Monto Neto" IS NOT NULL
GROUP BY "Mes"
ORDER BY "Mes" DESC;
        """
    
    else:
        return "-- Tipo de consulta no reconocido"


# =========================================================================================
# TESTING (descomentar para probar)
# =========================================================================================

if __name__ == "__main__":
    # Casos de prueba
    casos = [
        "compras noviembre 2025",
        "compras roche noviembre 2025",
        "compras 2025",
        "compras roche 2025",
        "compras de reactivos noviembre 2025",
        "compras biokey",
        "compras en dólares noviembre",
    ]
    
    print("=" * 80)
    print("TESTING IA_COMPRAS.PY")
    print("=" * 80)
    
    for caso in casos:
        print(f"\n📝 Input: {caso}")
        resultado = interpretar_compras(caso)
        print(f"✅ Tipo: {resultado['tipo']}")
        print(f"📋 Parámetros: {resultado['parametros']}")
        if 'moneda' in resultado:
            print(f"💰 Moneda: {resultado['moneda']}")
        print(f"🔍 Debug: {resultado['debug']}")
        
        # Mostrar SQL de referencia
        if resultado['tipo'] != "no_entendido":
            sql = generar_sql_referencia(resultado)
            print(f"\n💻 SQL de referencia:")
            print(sql)
    
    print("\n" + "=" * 80)
