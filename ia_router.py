# =========================
# IA_ROUTER.PY - ROUTER (COMPRAS / COMPARATIVAS / STOCK)
# =========================

import os
import re
import json
import unicodedata
from typing import Dict, Optional
from datetime import datetime
from ia_interpretador import interpretar_pregunta as interpretar_canonico
from ia_comparativas import interpretar_comparativas
import streamlit as st
from openai import OpenAI
from config import OPENAI_MODEL
from ia_interpretador import limpiar_consulta

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
# HELPERS
# =====================================================================
def _extraer_anios(texto: str) -> list:
    """Extrae años (2023-2026)"""
    return sorted(list(set([int(a) for a in re.findall(r"(2023|2024|2025|2026)", texto)])))

def _extraer_meses_nombre(texto: str) -> list:
    """Extrae meses por nombre"""
    return [m for m in MESES.keys() if m in texto.lower()]

def _extraer_proveedor(texto: str) -> str:
    """Extrae proveedor básico (mejora según necesites)"""
    # Remover keywords y fechas
    tmp = re.sub(r"\b(compras?|noviembre|diciembre|enero|febrero|2023|2024|2025|2026)\b", "", texto.lower())
    tmp = re.sub(r"\s+", " ", tmp).strip()
    return tmp if len(tmp) >= 3 else None

# =====================================================================
# INTÉRPRETE DE COMPRAS (BÁSICO)
# =====================================================================
def interpretar_compras(pregunta: str) -> Dict:
    """
    Interpreta consultas de compras simples:
    - compras 2025
    - compras roche 2025
    - compras roche noviembre 2025
    """
    texto = pregunta.strip()
    texto_lower = texto.lower()
    
    anios = _extraer_anios(texto)
    meses_nombre = _extraer_meses_nombre(texto)
    proveedor = _extraer_proveedor(texto)
    
    # Caso: compras noviembre 2025
    if meses_nombre and anios:
        anio = anios[0]
        mes_nombre = meses_nombre[0]
        mes_yyyymm = f"{anio}-{MESES[mes_nombre]}"
        
        if proveedor:
            # compras roche noviembre 2025
            return {
                "tipo": "compras_proveedor_mes",
                "parametros": {
                    "proveedor": proveedor,
                    "mes": mes_yyyymm,
                },
                "debug": f"compras proveedor mes: {proveedor} {mes_yyyymm}",
            }
        else:
            # compras noviembre 2025
            return {
                "tipo": "compras_mes",
                "parametros": {
                    "mes": mes_yyyymm,
                },
                "debug": f"compras mes: {mes_yyyymm}",
            }
    
    # Caso: compras 2025 o compras roche 2025
    if anios:
        anio = anios[0]
        
        if proveedor:
            # compras roche 2025
            return {
                "tipo": "compras_proveedor_anio",
                "parametros": {
                    "proveedor": proveedor,
                    "anio": anio,
                },
                "debug": f"compras proveedor año: {proveedor} {anio}",
            }
        else:
            # compras 2025
            return {
                "tipo": "compras_anio",
                "parametros": {
                    "anio": anio,
                },
                "debug": f"compras año: {anio}",
            }
    
    # No entendido
    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: compras roche noviembre 2025 | compras 2025",
        "debug": "compras: no match",
    }

# =====================================================================
# INTÉRPRETE DE STOCK (BÁSICO)
# =====================================================================
def interpretar_stock(pregunta: str) -> Dict:
    """
    Interpreta consultas de stock:
    - stock total
    - stock vitek
    """
    texto_lower = pregunta.lower()
    
    if "total" in texto_lower:
        return {
            "tipo": "stock_total",
            "parametros": {},
            "debug": "stock total",
        }
    
    # Extraer artículo (básico)
    articulo = re.sub(r"\b(stock|de|del|el)\b", "", texto_lower).strip()
    
    if articulo and len(articulo) >= 3:
        return {
            "tipo": "stock_articulo",
            "parametros": {
                "articulo": articulo,
            },
            "debug": f"stock artículo: {articulo}",
        }
    
    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: stock total | stock vitek",
        "debug": "stock: no match",
    }

# =====================================================================
# ROUTER PRINCIPAL
# =====================================================================
def interpretar_pregunta(pregunta: str) -> Dict:
    """
    Router principal que decide qué intérprete usar
    """
    if not pregunta or not pregunta.strip():
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "Escribe una consulta.",
            "debug": "Pregunta vacía.",
        }

    texto = pregunta.strip()
    texto_lower = texto.lower().strip()

    # Saludos / conversación
    saludos = {"hola", "buenas", "buenos", "gracias", "ok", "dale", "perfecto", "genial"}
    if any(re.search(rf"\b{re.escape(w)}\b", texto_lower) for w in saludos):
        if not any(k in texto_lower for k in ["compra", "compar", "stock"]):
            return {"tipo": "conversacion", "parametros": {}, "debug": "saludo"}

    # ✅ ROUTING POR KEYWORDS
    if "stock" in texto_lower:
        return interpretar_stock(pregunta)

    if "comparar" in texto_lower or "comparame" in texto_lower or "compara" in texto_lower:
        return interpretar_comparativas(pregunta)

    if "compra" in texto_lower or "compras" in texto_lower:
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
                "debug": f"openai error: {str(e)[:80]}",
            }

    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: compras roche noviembre 2025 | comparar compras roche 2024 2025",
        "debug": "router: no match.",
    }

# =====================================================================
# MAPEO TIPO → FUNCIÓN SQL
# =====================================================================
MAPEO_FUNCIONES = {
    "compras_anio": {
        "funcion": "get_compras_anio",
        "params": ["anio"],
    },
    "compras_proveedor_anio": {
        "funcion": "get_detalle_compras_proveedor_anio",
        "params": ["proveedor", "anio"],
    },
    "compras_proveedor_mes": {
        "funcion": "get_detalle_compras_proveedor_mes",
        "params": ["proveedor", "mes"],
    },
    "compras_mes": {
        "funcion": "get_compras_por_mes_excel",
        "params": ["mes"],
    },
    "comparar_proveedor_meses": {
        "funcion": "get_comparacion_proveedor_meses",
        "params": ["proveedor", "mes1", "mes2", "label1", "label2"],
    },
    "comparar_proveedor_anios": {
        "funcion": "get_comparacion_proveedor_anios_like",
        "params": ["proveedor", "anios"],
    },
    "ultima_factura": {
        "funcion": "get_ultima_factura_inteligente",
        "params": ["patron"],
    },
    "stock_total": {
        "funcion": "get_stock_total",
        "params": [],
    },
    "stock_articulo": {
        "funcion": "get_stock_articulo",
        "params": ["articulo"],
    },
}

def obtener_info_tipo(tipo: str) -> Optional[Dict]:
    return MAPEO_FUNCIONES.get(tipo)

def es_tipo_valido(tipo: str) -> bool:
    tipos_especiales = ["conversacion", "conocimiento", "no_entendido"]
    return tipo in MAPEO_FUNCIONES or tipo in tipos_especiales
