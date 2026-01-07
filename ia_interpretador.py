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

USAR_OPENAI_PARA_DATOS = False


# =====================================================================
# NORMALIZACIÓN
# =====================================================================
def normalizar_texto(texto: str) -> str:
    if texto is None:
        return ""
    texto = str(texto)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join([c for c in texto if not unicodedata.combining(c)])
    texto = texto.lower().strip()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def limpiar_consulta(texto: str) -> str:
    if texto is None:
        return ""
    texto = str(texto)
    texto = texto.strip()
    texto = re.sub(r"\s+", " ", texto)
    return texto


# =====================================================================
# HELPERS DETECCIÓN
# =====================================================================
def contiene_stock(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return bool(re.search(r"\bstock\b", t))


def contiene_compras(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return bool(re.search(r"\b(compra|compras|gaste|gastamos|gasto)\b", t))


def contiene_facturas(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return bool(re.search(r"\b(factura|facturas|comprobante|comprobantes)\b", t))


def contiene_comparar(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return bool(re.search(r"\b(comparar|comparame|compara)\b", t))


def contiene_total(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return bool(re.search(r"\b(total|totales)\b", t))


# =====================================================================
# EXTRACCIONES
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


def _extraer_anios(texto: str) -> List[int]:
    if not texto:
        return []
    anios = re.findall(r"(2020|2021|2022|2023|2024|2025|2026)", texto)
    out = []
    for a in anios:
        try:
            out.append(int(a))
        except Exception:
            pass
    return sorted(list(set(out)))


def _extraer_meses_nombre(texto: str) -> List[str]:
    if not texto:
        return []
    t = texto.lower()
    return [m for m in MESES.keys() if re.search(rf"\b{re.escape(m)}\b", t)]


def _extraer_limite(texto: str) -> Optional[int]:
    if not texto:
        return None
    t = texto.lower()
    m = re.search(r"\blimite\s*(\d+)\b", t)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def _extraer_fecha_rango(texto: str) -> Tuple[Optional[str], Optional[str]]:
    # Soporta:
    # - 01/11/2025 a 07/11/2025
    # - 01-11-2025 a 07-11-2025
    # - desde 01/11/2025 hasta 07/11/2025
    if not texto:
        return None, None
    t = texto.lower()

    m = re.search(
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s*(a|hasta)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        t,
    )
    if m:
        return _parse_fecha(m.group(1)), _parse_fecha(m.group(3))

    m2 = re.search(
        r"desde\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s*hasta\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        t,
    )
    if m2:
        return _parse_fecha(m2.group(1)), _parse_fecha(m2.group(2))

    return None, None


def _parse_fecha(fecha_str: str) -> Optional[str]:
    if not fecha_str:
        return None
    fs = fecha_str.strip().replace("-", "/")
    try:
        dt = datetime.strptime(fs, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def _extraer_proveedor(texto: str) -> Optional[str]:
    if not texto:
        return None
    # Heurística simple: sacar keywords + fechas y dejar el resto
    tmp = texto.lower()
    tmp = re.sub(r"\b(compras?|facturas?|total|totales|comprobante|comprobantes)\b", " ", tmp)
    tmp = re.sub(r"\b(2020|2021|2022|2023|2024|2025|2026)\b", " ", tmp)
    for mes in MESES.keys():
        tmp = re.sub(rf"\b{re.escape(mes)}\b", " ", tmp)
    tmp = re.sub(r"\s+", " ", tmp).strip()
    return tmp if len(tmp) >= 3 else None


# =====================================================================
# INTERPRETADOR PRINCIPAL
# =====================================================================
def interpretar_pregunta(pregunta: str) -> Dict:
    if not pregunta or not str(pregunta).strip():
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "Escribe una consulta.",
            "debug": "Pregunta vacía.",
        }

    texto_original = limpiar_consulta(pregunta)
    texto_lower_original = texto_original.lower().strip()

    # =========================
    # STOCK
    # =========================
    if contiene_stock(texto_lower_original):
        # Stock total
        if re.search(r"\btotal\b", texto_lower_original):
            return {"tipo": "stock_total", "parametros": {}, "debug": "stock total"}
        # Stock artículo (simple)
        articulo = re.sub(r"\b(stock|de|del|el|la|los|las)\b", " ", texto_lower_original)
        articulo = re.sub(r"\s+", " ", articulo).strip()
        if articulo:
            return {"tipo": "stock_articulo", "parametros": {"articulo": articulo}, "debug": f"stock articulo: {articulo}"}

    # =========================
    # FACTURAS PROVEEDOR (DETALLE / TOTAL)
    # =========================
    dispara_facturas_listado = contiene_facturas(texto_lower_original)

    if dispara_facturas_listado:
        proveedor = _extraer_proveedor(texto_original)
        anios = _extraer_anios(texto_lower_original)
        meses_nombre = _extraer_meses_nombre(texto_lower_original)
        desde, hasta = _extraer_fecha_rango(texto_lower_original)
        limite = _extraer_limite(texto_lower_original)

        meses = []
        if meses_nombre and anios:
            # si hay mes + año -> YYYY-MM
            meses = [f"{anios[0]}-{MESES[meses_nombre[0]]}"]
        elif meses_nombre and not anios:
            # si hay mes sin año, no forzar (deja meses vacío)
            meses = []

        proveedores = [proveedor] if proveedor else []

        # IMPORTANTE: para "facturas proveedor" NO forzamos artículo si no lo pidieron explícito
        articulo = None

        tipo_facturas = "total_facturas_proveedor" if contiene_total(texto_lower_original) else "facturas_proveedor"

        return {
            "tipo": tipo_facturas,
            "parametros": {
                "proveedores": proveedores,
                "meses": meses,
                "anios": anios,
                "desde": desde,
                "hasta": hasta,
                "articulo": articulo,
                "moneda": None,
                "limite": limite,
            },
            "debug": "facturas proveedor (canónico)",
        }

    # =========================
    # COMPRAS (fallback simple)
    # =========================
    if contiene_compras(texto_lower_original):
        anios = _extraer_anios(texto_lower_original)
        meses_nombre = _extraer_meses_nombre(texto_lower_original)
        proveedor = _extraer_proveedor(texto_original)

        if meses_nombre and anios:
            mes_yyyymm = f"{anios[0]}-{MESES[meses_nombre[0]]}"
            if proveedor:
                return {"tipo": "compras_proveedor_mes", "parametros": {"proveedor": proveedor, "mes": mes_yyyymm}, "debug": "compras proveedor mes"}
            return {"tipo": "compras_mes", "parametros": {"mes": mes_yyyymm}, "debug": "compras mes"}

        if anios:
            if proveedor:
                return {"tipo": "compras_proveedor_anio", "parametros": {"proveedor": proveedor, "anio": anios[0]}, "debug": "compras proveedor anio"}
            return {"tipo": "compras_anio", "parametros": {"anio": anios[0]}, "debug": "compras anio"}

    # =========================
    # OPENAI opcional
    # =========================
    if client and USAR_OPENAI_PARA_DATOS:
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Interpreta consultas de compras/stock/facturas."},
                    {"role": "user", "content": texto_original},
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
            return out
        except Exception as e:
            return {"tipo": "no_entendido", "parametros": {}, "sugerencia": "No pude interpretar.", "debug": f"openai error: {str(e)[:80]}"}

    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: compras roche noviembre 2025 | total facturas roche 2025",
        "debug": "no match",
    }


# =====================================================================
# MAPEO TIPO → FUNCIÓN SQL
# =====================================================================
MAPEO_FUNCIONES = {
    "compras_anio": {"funcion": "get_compras_anio", "params": ["anio"]},
    "compras_proveedor_anio": {"funcion": "get_detalle_compras_proveedor_anio", "params": ["proveedor", "anio"]},
    "compras_proveedor_mes": {"funcion": "get_detalle_compras_proveedor_mes", "params": ["proveedor", "mes"]},
    "compras_mes": {"funcion": "get_compras_por_mes_excel", "params": ["mes"]},

    "facturas_proveedor": {
        "funcion": "get_facturas_proveedor_detalle",
        "params": ["proveedores", "meses", "anios", "desde", "hasta", "articulo", "moneda", "limite"],
    },

    "total_facturas_proveedor": {
        "funcion": "get_total_facturas_proveedor",
        "params": ["proveedores", "meses", "anios", "desde", "hasta", "articulo", "moneda", "limite"],
    },

    "stock_total": {"funcion": "get_stock_total", "params": []},
    "stock_articulo": {"funcion": "get_stock_articulo", "params": ["articulo"]},
}


def obtener_info_tipo(tipo: str) -> Optional[Dict]:
    return MAPEO_FUNCIONES.get(tipo)


def es_tipo_valido(tipo: str) -> bool:
    tipos_especiales = ["conversacion", "conocimiento", "no_entendido"]
    return tipo in MAPEO_FUNCIONES or tipo in tipos_especiales
