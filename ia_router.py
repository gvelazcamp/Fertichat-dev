# =========================
# IA_ROUTER.PY - ROUTER (COMPRAS / COMPARATIVAS / STOCK)
# =========================
# Cambios mínimos:
# 1) Se evita recursión: compras/facturas ahora van a interpretar_canonico (ia_interpretador)
# 2) Se elimina import circular con orquestador (no debe estar en el router)
# 3) Se agrega/asegura mapeo "facturas_proveedor" en MAPEO_FUNCIONES

import os
import re
import json
import unicodedata
from typing import Dict, Optional
from datetime import datetime

import streamlit as st
from openai import OpenAI
from config import OPENAI_MODEL

# ✅ CANÓNICO (no se redefine ni se llama a sí mismo)
from ia_interpretador import interpretar_pregunta as interpretar_canonico
from ia_interpretador import limpiar_consulta  # (si lo usás en otros lados, lo dejo importado)

from ia_comparativas import interpretar_comparativas

# =====================================================================
# CONFIGURACIÓN OPENAI (opcional)
# =====================================================================
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

USAR_OPENAI_PARA_DATOS = False

# =====================================================================
# MESES (para parseo)
# =====================================================================
MESES = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "setiembre": "09", "octubre": "10",
    "noviembre": "11", "diciembre": "12",
}

# =====================================================================
# HELPERS (opcionales; no rompen)
# =====================================================================
def _extraer_anios(texto: str) -> list:
    """Extrae años (2023-2026)"""
    return sorted(list(set([int(a) for a in re.findall(r"(2023|2024|2025|2026)", texto)])))

def _extraer_meses_nombre(texto: str) -> list:
    """Extrae meses por nombre"""
    return [m for m in MESES.keys() if m in texto.lower()]

def _extraer_proveedor(texto: str) -> Optional[str]:
    """Extrae proveedor básico (NO canónico; se deja por compat)"""
    tmp = re.sub(
        r"\b(compras?|facturas?|comprobantes?|noviembre|diciembre|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|2023|2024|2025|2026)\b",
        "",
        texto.lower()
    )
    tmp = re.sub(r"\s+", " ", tmp).strip()
    return tmp if len(tmp) >= 3 else None

# =====================================================================
# INTÉRPRETE DE COMPRAS (BÁSICO) - NO SE USA EN ROUTING PRINCIPAL
# (Lo dejo por si lo llamabas en otro lado, pero el router usa CANÓNICO)
# =====================================================================
def interpretar_compras(pregunta: str) -> Dict:
    texto = pregunta.strip()
    anios = _extraer_anios(texto)
    meses_nombre = _extraer_meses_nombre(texto)
    proveedor = _extraer_proveedor(texto)

    if meses_nombre and anios:
        anio = anios[0]
        mes_nombre = meses_nombre[0]
        mes_yyyymm = f"{anio}-{MESES[mes_nombre]}"

        if proveedor:
            return {
                "tipo": "compras_proveedor_mes",
                "parametros": {"proveedor": proveedor, "mes": mes_yyyymm},
                "debug": f"compras proveedor mes (basico): {proveedor} {mes_yyyymm}",
            }
        return {
            "tipo": "compras_mes",
            "parametros": {"mes": mes_yyyymm},
            "debug": f"compras mes (basico): {mes_yyyymm}",
        }

    if anios:
        anio = anios[0]
        if proveedor:
            return {
                "tipo": "compras_proveedor_anio",
                "parametros": {"proveedor": proveedor, "anio": anio},
                "debug": f"compras proveedor año (basico): {proveedor} {anio}",
            }
        return {
            "tipo": "compras_anio",
            "parametros": {"anio": anio},
            "debug": f"compras año (basico): {anio}",
        }

    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: compras roche noviembre 2025 | compras 2025",
        "debug": "compras (basico): no match",
    }

# =====================================================================
# INTÉRPRETE DE STOCK (BÁSICO)
# =====================================================================
def interpretar_stock(pregunta: str) -> Dict:
    texto_lower = (pregunta or "").lower()

    if "total" in texto_lower:
        return {"tipo": "stock_total", "parametros": {}, "debug": "stock total"}

    articulo = re.sub(r"\b(stock|de|del|el|la|los|las)\b", "", texto_lower).strip()
    if articulo and len(articulo) >= 3:
        return {"tipo": "stock_articulo", "parametros": {"articulo": articulo}, "debug": f"stock artículo: {articulo}"}

    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: stock total | stock vitek",
        "debug": "stock: no match",
    }

# =====================================================================
# ROUTER PRINCIPAL (EXPORTA interpretar_pregunta PARA EL SISTEMA)
# =====================================================================
def interpretar_pregunta(pregunta: str) -> Dict:
    """
    Router principal:
    - comparativas -> ia_comparativas
    - compras/facturas/comprobantes -> CANÓNICO (ia_interpretador)
    - stock -> interpretar_stock
    """
    if not pregunta or not str(pregunta).strip():
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "Escribe una consulta.",
            "debug": "Pregunta vacía.",
        }

    texto_lower = str(pregunta).lower().strip()

    # Saludos / conversación
    saludos = {"hola", "buenas", "buenos", "gracias", "ok", "dale", "perfecto", "genial"}
    if any(re.search(rf"\b{re.escape(w)}\b", texto_lower) for w in saludos):
        if not any(k in texto_lower for k in ["compra", "compras", "compar", "stock", "factura", "facturas", "comprobante", "comprobantes"]):
            return {"tipo": "conversacion", "parametros": {}, "debug": "saludo"}

    # ROUTING POR KEYWORDS (orden importa)
    if "stock" in texto_lower:
        return interpretar_stock(pregunta)

    if re.search(r"\b(comparar|comparame|compara)\b", texto_lower):
        return interpretar_comparativas(pregunta)

    # ✅ TODO lo de compras/facturas va al CANÓNICO (evita recursión)
    if any(k in texto_lower for k in ["compra", "compras", "factura", "facturas", "comprobante", "comprobantes"]):
        return interpretar_canonico(pregunta)

    # OPENAI (opcional)
    if client and USAR_OPENAI_PARA_DATOS:
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Interpreta consultas de compras/stock"},
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
            return out
        except Exception as e:
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": "No pude interpretar.",
                "debug": f"openai error: {str(e)[:120]}",
            }

    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: compras roche noviembre 2025 | comparar compras roche 2024 2025 | todas las facturas roche 2025",
        "debug": "router: no match.",
    }

# =====================================================================
# MAPEO TIPO → FUNCIÓN SQL
# =====================================================================
MAPEO_FUNCIONES = {
    "compras_anio": {"funcion": "get_compras_anio", "params": ["anio"]},
    "compras_proveedor_anio": {"funcion": "get_detalle_compras_proveedor_anio", "params": ["proveedor", "anio"]},
    "compras_proveedor_mes": {"funcion": "get_detalle_compras_proveedor_mes", "params": ["proveedor", "mes"]},
    "compras_mes": {"funcion": "get_compras_por_mes_excel", "params": ["mes"]},

    "comparar_proveedor_meses": {
        "funcion": "get_comparacion_proveedor_meses",
        "params": ["proveedor", "mes1", "mes2", "label1", "label2"],
    },
    "comparar_proveedor_anios": {
        "funcion": "get_comparacion_proveedor_anios_like",
        "params": ["proveedor", "anios"],
    },

    # Multi-proveedor
    "comparar_proveedores_meses_multi": {
        "funcion": "get_comparacion_proveedores_meses_multi",
        "params": ["proveedores", "meses"],
    },

    "ultima_factura": {"funcion": "get_ultima_factura_inteligente", "params": ["patron"]},

    "stock_total": {"funcion": "get_stock_total", "params": []},
    "stock_articulo": {"funcion": "get_stock_articulo", "params": ["articulo"]},

    # ✅ CORRECTO (lo que usa tu intérprete canónico)
    "facturas_proveedor": {
        "funcion": "get_facturas_proveedor_detalle",
        "params": ["proveedores", "meses", "anios", "desde", "hasta", "articulo", "moneda", "limite"],
    },

    # (Dejo tu clave rara por compat, pero NO la usa el canónico)
    "compras_Todas las facturas de un Proveedor": {
        "funcion": "get_facturas_proveedor_detalle",
        "params": ["proveedores", "meses", "anios", "desde", "hasta", "articulo", "moneda"],
    },
}

def obtener_info_tipo(tipo: str) -> Optional[Dict]:
    return MAPEO_FUNCIONES.get(tipo)

def es_tipo_valido(tipo: str) -> bool:
    tipos_especiales = ["conversacion", "conocimiento", "no_entendido"]
    return tipo in MAPEO_FUNCIONES or tipo in tipos_especiales
