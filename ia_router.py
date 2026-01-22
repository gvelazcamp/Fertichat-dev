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
from ia_interpretador_articulos import interpretar_articulo as interpretar_articulos
from ia_stock import interpretar_stock as interpretar_stock_alt
from ia_compras import interpretar_compras

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
# DETECTOR SIMPLE DE ARTÍCULOS
# =====================================================================
def detecta_articulo_simple(texto: str) -> bool:
    texto_lower = texto.lower()
    keywords_articulos = ["vitek", "roche", "coba", "elecsys", "ast", "n422", "gn", "id20", "test", "kit"]
    return any(k in texto_lower for k in keywords_articulos)

# =====================================================================
# EJECUTOR POR INTERPRETACIÓN (SIEMPRE DEVUELVE ALGO)
# =====================================================================
def ejecutar_por_interpretacion(resultado):
    from sql_facturas import get_facturas_proveedor as ejecutar_facturas_proveedor
    from sql_compras import get_compras_articulo_anio as ejecutar_compras_articulo_anio

    if not resultado or "tipo" not in resultado:
        return {
            "ok": False,
            "mensaje": "No pude interpretar la consulta."
        }

    tipo = resultado["tipo"]
    params = resultado.get("parametros", {})

    if tipo == "facturas_proveedor":
        df = ejecutar_facturas_proveedor(**params)
        return {
            "ok": True,
            "tipo": tipo,
            "df": df
        }

    if tipo == "compras_articulo_anio":
        df = ejecutar_compras_articulo_anio(
            modo_sql=params["modo_sql"],
            valor=params["valor"],
            anios=params["anios"]
        )
        return {
            "ok": True,
            "tipo": tipo,
            "df": df
        }

    elif tipo == "compras_articulos_anios":
        from sql_compras import get_compras_articulos_anios
        df = get_compras_articulos_anios(**params)
        return {
            "ok": True,
            "tipo": tipo,
            "df": df
        }

    elif tipo == "dashboard_top_proveedores":
        from sql_compras import get_dashboard_top_proveedores
        anio = params.get("anio")
        top_n = params.get("top_n", 10)
        moneda = params.get("moneda", "$")
        if not anio:
            return {
                "ok": False,
                "mensaje": "No se especificó año para el dashboard de top proveedores."
            }
        df = get_dashboard_top_proveedores(anio=anio, top_n=top_n, moneda=moneda)
        return {
            "ok": True,
            "tipo": tipo,
            "df": df
        }

    return {
        "ok": False,
        "mensaje": f"Tipo no soportado: {tipo}"
    }

# =====================================================================
# ROUTER PRINCIPAL (EXPORTA interpretar_pregunta PARA EL SISTEMA)
# =====================================================================
def interpretar_pregunta(pregunta: str) -> Dict:
    """
    Router principal con PRIORIDAD ABSOLUTA para "compras <AÑO>"
    """
    if not pregunta or not str(pregunta).strip():
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "Escribe una consulta.",
            "debug": "Pregunta vacía.",
        }

    texto_lower = str(pregunta).lower().strip()
    texto_normalizado = re.sub(r'[^\w\s]', ' ', texto_lower).strip()

    # =================================================================
    # 🔥 PRIORIDAD ABSOLUTA #1: "compras <AÑO>" → SIEMPRE canónico
    # DEBE ESTAR PRIMERO, ANTES DE TODO
    # =================================================================
    # Match exacto: "compras 2025", "compra 2024", etc.
    if re.search(r'\b(compra|compras)\s+\d{4}\b', texto_lower):
        print(f"🔥 BLOQUE FORZADO: '{pregunta}' → intérprete canónico")
        return interpretar_canonico(pregunta)

    # =================================================================
    # Saludos / conversación
    # =================================================================
    saludos = {"hola", "buenas", "buenos", "gracias", "ok", "dale", "perfecto", "genial"}
    if any(re.search(rf"\b{re.escape(w)}\b", texto_lower) for w in saludos):
        if not any(k in texto_lower for k in ["compra", "compras", "compar", "stock", "factura", "facturas"]):
            return {"tipo": "conversacion", "parametros": {}, "debug": "saludo"}

    # =================================================================
    # ROUTING POR KEYWORDS (en orden de prioridad)
    # =================================================================
    
    # 1. FACTURAS (prioridad alta)
    if es_consulta_facturas(pregunta):
        return interpretar_facturas(pregunta)

    # 2. STOCK
    if "stock" in texto_lower:
        return interpretar_stock(pregunta)

    # 3. COMPARATIVAS
    if re.search(r"\b(comparar|comparame|compara)\b", texto_lower):
        return interpretar_comparativas(pregunta)

    # 4. COMPRAS (antes de artículos)
    if any(k in texto_lower for k in ["compra", "compras", "comprobante", "comprobantes"]):
        # 🔥 VALIDACIÓN ADICIONAL: protección extra para "compras <AÑO>"
        if re.search(r'\b(compra|compras)\s+\d{4}\b', texto_lower):
            print(f"🔥 BLOQUE FORZADO 2: '{pregunta}' → intérprete canónico")
            return interpretar_canonico(pregunta)
        
        # Probar intérprete de artículos SOLO si no matcheó "compras <año>"
        from ia_interpretador_articulos import interpretar_articulo
        resultado_art = interpretar_articulo(pregunta)
        if isinstance(resultado_art, dict) and resultado_art.get("tipo") not in (
            "no_entendido",
            "sin_resultado",
        ):
            return resultado_art

        # Fallback al canónico para otras consultas de compras
        return interpretar_canonico(pregunta)

    # 5. ARTÍCULOS (último recurso)
    # Solo llega acá si NO tiene keywords de compras/facturas/stock/comparativas
    if "articulo" in texto_normalizado or detecta_articulo_simple(pregunta):
        return interpretar_articulos(pregunta)

    # =================================================================
    # OPENAI (fallback)
    # =================================================================
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
            content = re.sub(r"```json\s*", "", content).strip()
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
    "compras_anio": {"funcion": "get_top_proveedores_por_anios", "params": ["anios", "limite"]},
    "compras_proveedor_anio": {"funcion": "get_detalle_compras_proveedor_anio", "params": ["proveedor", "anio"]},
    "compras_proveedor_mes": {"funcion": "get_detalle_compras_proveedor_mes", "params": ["proveedor", "mes"]},
    "compras_mes": {"funcion": "get_compras_por_mes_excel", "params": ["mes"]},
    "compras_articulo_anio": {
        "funcion": "get_compras_articulo_anio",
        "params": ["modo_sql", "valor", "anios"],
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

    # DASHBOARD TOP PROVEEDORES
    "dashboard_top_proveedores": {
        "funcion": "get_dashboard_top_proveedores",
        "params": ["anio", "top_n", "moneda"],
    },
}

def obtener_info_tipo(tipo: str) -> Optional[Dict]:
    return MAPEO_FUNCIONES.get(tipo)

def es_tipo_valido(tipo: str) -> bool:
    tipos_especiales = ["conversacion", "conocimiento", "no_entendido"]
    return tipo in MAPEO_FUNCIONES or tipo in tipos_especiales
