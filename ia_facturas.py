# =========================
# IA_FACTURAS.PY - INTÉRPRETE ESPECÍFICO PARA FACTURAS
# =========================

import re
from typing import Dict, List, Optional
from datetime import datetime



# ==================================================
# MESES Y HELPERS
# =====================================================================

MESES = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "setiembre": "09", "octubre": "10",
    "noviembre": "11", "diciembre": "12",
}


def _extraer_anios(texto: str) -> List[int]:
    """Extrae años del texto (2023-2026)"""
    return sorted(list(set([int(a) for a in re.findall(r"\b(2023|2024|2025|2026)\b", texto)])))


def _extraer_meses_nombre(texto: str) -> List[str]:
    """Extrae nombres de meses del texto"""
    return [m for m in MESES.keys() if m in texto.lower()]


def _extraer_proveedor(texto: str) -> Optional[str]:
    """Extrae nombre de proveedor del texto"""
    # Remover palabras comunes
    tmp = re.sub(
        r"\b(facturas?|comprobantes?|detalle|todas?|los?|las?|de|del|en|noviembre|diciembre|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|2023|2024|2025|2026)\b",
        "",
        texto.lower()
    )
    tmp = re.sub(r"\s+", " ", tmp).strip()
    return tmp if len(tmp) >= 3 else None


def _normalizar_nro_factura(nro: str) -> str:
    """Normaliza número de factura"""
    nro = str(nro or "").strip().upper()
    if not nro:
        return ""

    # Solo números -> A + 8 dígitos
    if re.fullmatch(r"\d+", nro):
        return "A" + nro.zfill(8)

    # Letra + números -> asegurar 8 dígitos
    m = re.fullmatch(r"([A-Z])(\d+)", nro)
    if m:
        letra = m.group(1)
        dig = m.group(2)
        if len(dig) < 8:
            dig = dig.zfill(8)
        return letra + dig

    return nro


def _extraer_nro_factura(texto: str) -> Optional[str]:
    """Extrae número de factura del texto"""
    if not texto:
        return None

    t = str(texto).strip()

    # Caso: el texto ES solo el nro (A00273279 o 273279)
    if re.fullmatch(r"[A-Za-z]?\d{5,}", t):
        return _normalizar_nro_factura(t)

    # Caso: "detalle factura 273279" / "factura A00273279"
    m = re.search(
        r"\b(?:detalle\s+)?(?:factura|comprobante|nro\.?\s*factura|nro\.?\s*comprobante|numero)\b\s*[:#-]?\s*([A-Za-z]?\d{3,})\b",
        t,
        flags=re.IGNORECASE
    )
    if m:
        return _normalizar_nro_factura(m.group(1))

    # Buscar cualquier patrón que parezca número de factura
    m = re.search(r"\b([A-Za-z]?\d{5,})\b", t)
    if m:
        return _normalizar_nro_factura(m.group(1))

    return None


def _extraer_montos(texto: str) -> Dict[str, float]:
    """Extrae rangos de montos del texto"""
    resultado = {"min": None, "max": None}
    
    # Patrones: "entre X y Y", "de X a Y", "más de X", "menos de X"
    
    # Entre X y Y
    m = re.search(r"entre\s+(\d+(?:[.,]\d+)?)\s+y\s+(\d+(?:[.,]\d+)?)", texto, re.IGNORECASE)
    if m:
        resultado["min"] = float(m.group(1).replace(",", "."))
        resultado["max"] = float(m.group(2).replace(",", "."))
        return resultado
    
    # De X a Y
    m = re.search(r"de\s+(\d+(?:[.,]\d+)?)\s+a\s+(\d+(?:[.,]\d+)?)", texto, re.IGNORECASE)
    if m:
        resultado["min"] = float(m.group(1).replace(",", "."))
        resultado["max"] = float(m.group(2).replace(",", "."))
        return resultado
    
    # Más de X / Mayor a X
    m = re.search(r"(?:m[aá]s\s+de|mayor\s+a?)\s+(\d+(?:[.,]\d+)?)", texto, re.IGNORECASE)
    if m:
        resultado["min"] = float(m.group(1).replace(",", "."))
        return resultado
    
    # Menos de X / Menor a X
    m = re.search(r"(?:menos\s+de|menor\s+a?)\s+(\d+(?:[.,]\d+)?)", texto, re.IGNORECASE)
    if m:
        resultado["max"] = float(m.group(1).replace(",", "."))
        return resultado
    
    return resultado


def _extraer_proveedores_multi(texto: str) -> List[str]:
    """Extrae múltiples proveedores separados por coma o 'y'"""
    # Remover palabras clave de facturas
    tmp = re.sub(
        r"\b(facturas?|comprobantes?|detalle|todas?|los?|las?|de|del|en|2023|2024|2025|2026)\b",
        "",
        texto.lower()
    )
    
    # Separar por comas o 'y'
    proveedores = re.split(r"[,y]", tmp)
    
    # Limpiar y filtrar
    resultado = []
    for p in proveedores:
        p_clean = p.strip()
        # Remover meses
        for mes in MESES.keys():
            p_clean = p_clean.replace(mes, "")
        p_clean = p_clean.strip()
        
        if len(p_clean) >= 3:
            resultado.append(p_clean)
    
    return resultado


# =====================================================================
# INTÉRPRETE PRINCIPAL DE FACTURAS
# =====================================================================

def interpretar_facturas(pregunta: str) -> Dict:
    """
    Intérprete específico para consultas de facturas.
    Retorna dict con: tipo, parametros, debug, sugerencia
    """
    
    texto = pregunta.strip().lower()
    
    # =========================================================
    # DETALLE DE FACTURA POR NÚMERO
    # =========================================================
    
    nro_factura = _extraer_nro_factura_raw(pregunta)
    
    if nro_factura and any(k in texto for k in ["detalle", "factura", "comprobante"]):
        return {
            "tipo": "detalle_factura_numero",  # ✅ CAMBIO AQUÍ: era "detalle_factura"
            "parametros": {"nro_factura": nro_factura},
            "debug": f"detalle factura (raw): {nro_factura}",
        }
    
    # =========================================================
    # TODAS LAS FACTURAS DE PROVEEDOR(ES)
    # =========================================================
    
    if any(k in texto for k in ["todas las facturas", "facturas de", "facturas del"]):
        
        # Extraer proveedores
        proveedores = _extraer_proveedores_multi(pregunta)
        
        if not proveedores:
            proveedor = _extraer_proveedor(pregunta)
            if proveedor:
                proveedores = [proveedor]
        
        if proveedores:
            anios = _extraer_anios(pregunta)
            meses_nombre = _extraer_meses_nombre(pregunta)
            
            # Convertir meses a formato YYYY-MM
            meses = []
            if meses_nombre and anios:
                anio = anios[0]
                meses = [f"{anio}-{MESES[m]}" for m in meses_nombre]
            
            # Detectar moneda
            moneda = None
            if "dolar" in texto or "usd" in texto or "u$s" in texto:
                moneda = "USD"
            elif "peso" in texto or "$" in texto:
                moneda = "$"
            
            return {
                "tipo": "facturas_proveedor",
                "parametros": {
                    "proveedores": proveedores,
                    "meses": meses if meses else None,
                    "anios": anios if anios and not meses else None,
                    "moneda": moneda,
                    "limite": 5000
                },
                "debug": f"facturas proveedor(es): {', '.join(proveedores)} | meses: {meses} | años: {anios}",
            }
    
    # =========================================================
    # ÚLTIMA FACTURA (ARTÍCULO O PROVEEDOR)
    # =========================================================
    
    if any(k in texto for k in ["ultima factura", "última factura", "ultimo comprobante"]):
        patron = _extraer_proveedor(pregunta)
        
        if patron:
            return {
                "tipo": "ultima_factura",
                "parametros": {"patron": patron},
                "debug": f"ultima factura: {patron}",
            }
    
    # =========================================================
    # FACTURAS POR ARTÍCULO
    # =========================================================
    
    if "facturas de" in texto or "facturas del articulo" in texto:
        articulo = _extraer_proveedor(pregunta)  # reutilizamos la función
        
        if articulo:
            return {
                "tipo": "facturas_articulo",
                "parametros": {"articulo": articulo, "limite": 50},
                "debug": f"facturas artículo: {articulo}",
            }
    
    # =========================================================
    # RESUMEN DE FACTURAS POR PROVEEDOR
    # =========================================================
    
    if "resumen" in texto and "facturas" in texto:
        anios = _extraer_anios(pregunta)
        meses_nombre = _extraer_meses_nombre(pregunta)
        
        meses = []
        if meses_nombre and anios:
            anio = anios[0]
            meses = [f"{anio}-{MESES[m]}" for m in meses_nombre]
        
        moneda = None
        if "dolar" in texto or "usd" in texto:
            moneda = "USD"
        elif "peso" in texto:
            moneda = "$"
        
        return {
            "tipo": "resumen_facturas",
            "parametros": {
                "meses": meses if meses else None,
                "anios": anios if anios and not meses else None,
                "moneda": moneda
            },
            "debug": f"resumen facturas: meses={meses}, años={anios}",
        }
    
    # =========================================================
    # FACTURAS POR RANGO DE MONTO
    # =========================================================
    
    montos = _extraer_montos(pregunta)
    
    if montos.get("min") is not None or montos.get("max") is not None:
        proveedores = _extraer_proveedores_multi(pregunta)
        anios = _extraer_anios(pregunta)
        
        moneda = None
        if "dolar" in texto or "usd" in texto:
            moneda = "USD"
        elif "peso" in texto:
            moneda = "$"
        
        return {
            "tipo": "facturas_rango_monto",
            "parametros": {
                "monto_min": montos.get("min", 0),
                "monto_max": montos.get("max", 999999999),
                "proveedores": proveedores if proveedores else None,
                "anios": anios if anios else None,
                "moneda": moneda,
                "limite": 100
            },
            "debug": f"facturas rango: {montos}",
        }
    
    # =========================================================
    # NO ENTENDIDO
    # =========================================================
    
    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: todas las facturas roche 2025 | detalle factura 273279 | ultima factura vitek",
        "debug": "facturas: no match",
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
# VALIDACIÓN Y HELPERS
# =====================================================================

def es_consulta_facturas(texto: str) -> bool:
    """Detecta si una consulta es sobre facturas"""
    keywords = [
        "factura", "facturas", "comprobante", "comprobantes",
        "detalle factura", "todas las facturas", "ultima factura",
        "resumen facturas"
    ]
    texto_lower = texto.lower()
    return any(k in texto_lower for k in keywords)



def _extraer_nro_factura_raw(texto: str) -> Optional[str]:
    """
    Extrae el número de factura SIN normalizar.
    Devuelve solo el token que escribió el usuario.
    """
    if not texto:
        return None

    m = re.search(r"\b([A-Za-z]?\d{3,})\b", texto)
    if m:
        return m.group(1).strip()

    return None
