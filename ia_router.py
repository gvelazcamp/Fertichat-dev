# =========================
# IA_ROUTER.PY - ROUTER (COMPRAS / COMPARATIVAS / STOCK)
# =========================
# NOTA:
# - Router único: decide qué intérprete usar.
# - Los intérpretes NO se llaman entre sí.
# - OpenAI para datos queda deshabilitado (USAR_OPENAI_PARA_DATOS = False).
# =========================

import os
import re
import json
import unicodedata
from typing import Dict, Optional
from datetime import datetime

import streamlit as st
from openai import OpenAI  # opcional
from config import OPENAI_MODEL

# =====================================================================
# CONFIGURACIÓN OPENAI (opcional)
# =====================================================================
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Si querés “sacar OpenAI” para datos: dejalo False (recomendado).
USAR_OPENAI_PARA_DATOS = False

# =====================================================================
# TABLA DE TIPOS + CANÓNICA (se conservan como referencia / guía)
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
| ultima_factura | Última factura de un artículo/proveedor | patron | "ultima factura vitek" |
| facturas_articulo | Todas las facturas de un artículo | articulo | "cuando vino vitek" |
| stock_total | Resumen total de stock | (ninguno) | "stock total" |
| stock_articulo | Stock de un artículo | articulo | "stock vitek" |
| conversacion | Saludos | (ninguno) | "hola", "gracias" |
| conocimiento | Preguntas generales | (ninguno) | "que es HPV" |
| no_entendido | No se entiende | sugerencia | - |
"""

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
# ROUTER PRINCIPAL
# =====================================================================
def interpretar_pregunta(pregunta: str) -> Dict:
    if not pregunta or not pregunta.strip():
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "Escribe una consulta.",
            "debug": "Pregunta vacía.",
        }

    texto = pregunta.strip()
    texto_lower = texto.lower().strip()

    # -------- conversación / cortos --------
    saludos = {"hola", "buenas", "buenos", "gracias", "ok", "dale", "perfecto", "genial"}
    if any(re.search(rf"\b{re.escape(w)}\b", texto_lower) for w in saludos):
        # Si además incluye una intención clara, que pase a módulo.
        if not any(k in texto_lower for k in ["compra", "compar", "stock"]):
            return {"tipo": "conversacion", "parametros": {}, "debug": "saludo"}

    # Dominio: stock / comparativas / compras
    if "stock" in texto_lower:
        return interpretar_stock(pregunta)

    if "comparar" in texto_lower or "comparame" in texto_lower or "compara" in texto_lower:
        return interpretar_comparativas(pregunta)

    if "compra" in texto_lower or "compras" in texto_lower:
        return interpretar_compras(pregunta)

    # OPENAI (opcional)
    if client and USAR_OPENAI_PARA_DATOS:
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": _get_system_prompt()},
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
            if "debug" not in out:
                out["debug"] = "openai"
            return out
        except Exception as e:
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": "No pude interpretar. Prueba: compras roche noviembre 2025",
                "debug": f"openai error: {str(e)[:80]}",
            }

    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Prueba: compras roche noviembre 2025 | comparar compras roche junio julio 2025 | stock total",
        "debug": "router: no match.",
    }

# =====================================================================
# MAPEO TIPO → FUNCIÓN SQL (CANÓNICO)
# =====================================================================
MAPEO_FUNCIONES = {
    "compras_anio": {
        "funcion": "get_compras_anio",
        "params": ["anio"],
        "resumen": "get_total_compras_anio",
    },
    "compras_proveedor_anio": {
        "funcion": "get_detalle_compras_proveedor_anio",
        "params": ["proveedor", "anio"],
        "resumen": "get_total_compras_proveedor_anio",
    },
    "compras_proveedor_mes": {
        "funcion": "get_detalle_compras_proveedor_mes",
        "params": ["proveedor", "mes"],
    },
    "compras_mes": {
        "funcion": "get_compras_por_mes_excel",
        "params": ["mes"],
    },
    # =========================
    # COMPARATIVAS
    # =========================
    "comparar_proveedor_meses": {
        "funcion": "get_comparacion_proveedor_meses",
        "params": ["proveedor", "mes1", "mes2", "label1", "label2"],
    },
    "comparar_proveedor_anios": {
        "funcion": "get_comparacion_proveedor_anios",
        "params": ["proveedor", "anios", "label1", "label2"],
    },
    # =========================
    # OTROS
    # =========================
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
