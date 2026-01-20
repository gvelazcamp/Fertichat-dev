# =========================
# IA_ROUTER.PY - ROUTER (COMPRAS / COMPARATIVAS / STOCK / FACTURAS)
# =========================

import os
import re
import json
from typing import Dict, Optional

import streamlit as st
from openai import OpenAI
from config import OPENAI_MODEL

# Intérpretes específicos
from ia_interpretador import interpretar_pregunta as interpretar_canonico
from ia_comparativas import interpretar_comparativas
from ia_facturas import interpretar_facturas, es_consulta_facturas

# =====================================================================
# CONFIGURACIÓN OPENAI
# =====================================================================
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

USAR_OPENAI_PARA_DATOS = False

# =====================================================================
# MESES
# =====================================================================
MESES = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "setiembre": "09", "octubre": "10",
    "noviembre": "11", "diciembre": "12",
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
    - facturas -> ia_facturas
    - comparativas -> ia_comparativas
    - compras -> CANÓNICO (ia_interpretador)
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
        if not any(k in texto_lower for k in ["compra", "compras", "compar", "stock", "factura", "facturas"]):
            return {"tipo": "conversacion", "parametros": {}, "debug": "saludo"}

    # ROUTING POR KEYWORDS (orden importa)
    
    # 1. FACTURAS (antes de compras para evitar conflictos)
    if es_consulta_facturas(pregunta):
        return interpretar_facturas(pregunta)

    # 2. STOCK
    if "stock" in texto_lower:
        return interpretar_stock(pregunta)

    # 3. COMPRAS (va al CANÓNICO) - MOVIDO ANTES DE COMPARATIVAS PARA PRIORIDAD
    if any(k in texto_lower for k in ["compra", "compras", "comprobante", "comprobantes"]):
        return interpretar_canonico(pregunta)

    # 4. COMPARATIVAS
    if re.search(r"\b(comparar|comparame|compara)\b", texto_lower):
        return interpretar_comparativas(pregunta)

    # OPENAI (opcional)
    if client and USAR_OPENAI_PARA_DATOS:
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Interpreta consultas de compras/stock/facturas"},
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
        "sugerencia": "Probá: todas las facturas roche 2025 | detalle factura 273279 | compras 2025",
        "debug": "router: no match.",
    }


# =====================================================================
# MAPEO TIPO → FUNCIÓN SQL
# =====================================================================
MAPEO_FUNCIONES = {
    # COMPRAS
    "compras_anio": {"funcion": "get_compras_anio", "params": ["anio"]},
    "compras_proveedor_anio": {"funcion": "get_detalle_compras_proveedor_anio", "params": ["proveedor", "anio"]},
    "compras_proveedor_mes": {"funcion": "get_detalle_compras_proveedor_mes", "params": ["proveedor", "mes"]},
    "compras_mes": {"funcion": "get_compras_por_mes_excel", "params": ["mes"]},

    # 🆕 COMPRAS POR ARTÍCULO
    "compras_articulo_anio": {
        "funcion": "get_compras_articulo_anio",
        "params": ["articulo", "anios"],
    },

    # FACTURAS
    "detalle_factura": {"funcion": "get_detalle_factura_por_numero", "params": ["nro_factura"]},
    "facturas_proveedor": {
        "funcion": "get_facturas_proveedor",
        "params": ["proveedores", "meses", "anios", "desde", "hasta", "articulo", "moneda", "limite"],
    },
    "ultima_factura": {"funcion": "get_ultima_factura_inteligente", "params": ["patron"]},
    "facturas_articulo": {"funcion": "get_facturas_articulo", "params": ["articulo", "solo_ultima", "limite"]},
    "resumen_facturas": {"funcion": "get_resumen_facturas_por_proveedor", "params": ["meses", "anios", "moneda"]},
    "facturas_rango_monto": {
        "funcion": "get_facturas_por_rango_monto",
        "params": ["monto_min", "monto_max", "proveedores", "meses", "anios", "moneda", "limite"],
    },

    # COMPARATIVAS
    "comparar_proveedor_meses": {
        "funcion": "get_comparacion_proveedor_meses",
        "params": ["proveedor", "mes1", "mes2", "label1", "label2"],
    },
    "comparar_proveedor_anios": {
        "funcion": "get_comparacion_proveedor_anios_like",
        "params": ["proveedor", "anios"],
    },
    "comparar_proveedores_meses_multi": {
        "funcion": "get_comparacion_proveedores_meses_multi",
        "params": ["proveedores", "meses"],
    },

    # STOCK
    "stock_total": {"funcion": "get_stock_total", "params": []},
    "stock_articulo": {"funcion": "get_stock_articulo", "params": ["articulo"]},
}


def obtener_info_tipo(tipo: str) -> Optional[Dict]:
    return MAPEO_FUNCIONES.get(tipo)


def es_tipo_valido(tipo: str) -> bool:
    tipos_especiales = ["conversacion", "conocimiento", "no_entendido"]
    return tipo in MAPEO_FUNCIONES or tipo in tipos_especiales


# =====================================================================
# EJECUTOR PRINCIPAL (CORREGIDO CON ORDEN OBLIGATORIO)
# =====================================================================
def ejecutar_decision(decision: Dict) -> Optional[any]:
    """
    Ejecutor con orden obligatorio:
    1. Tipos específicos mapeados
    2. Fallback general
    """
    tipo = decision.get("tipo")
    parametros = decision.get("parametros", {})

    print("ROUTER TIPO:", tipo)
    print("ROUTER PARAMS:", parametros)

    # =========================
    # 1️⃣ TIPOS ESPECÍFICOS (PRIMERO)
    # =========================
    if tipo in MAPEO_FUNCIONES:
        info = MAPEO_FUNCIONES[tipo]
        funcion = info["funcion"]
        params_keys = info["params"]
        # Asume que las funciones están disponibles via importar o globals
        # Ejemplo: from sql_core import ejecutar_consulta
        # Aquí se llamaría ejecutar_consulta(funcion, **parametros_mapeados)
        # Para este ejemplo, retornamos un placeholder
        return f"Ejecutando {funcion} con params { {k: parametros.get(k) for k in params_keys} }"

    # =========================
    # 2️⃣ FALLBACK GENERAL (ÚLTIMO)
    # =========================
    if tipo == "compras":
        # Llamar a función general de compras
        return "Ejecutando compras_generales()"

    return None
