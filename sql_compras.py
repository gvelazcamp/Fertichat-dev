# =========================
# SQL COMPRAS - CONSULTAS TRANSACCIONALES
# =========================

import re
import pandas as pd
from typing import List, Optional, Any
import streamlit as st

from sql_core import (
    ejecutar_consulta,
    _sql_total_num_expr,
    _sql_total_num_expr_usd,
    _sql_total_num_expr_general,
    get_ultimo_mes_disponible_hasta
)


# =====================================================================
# COMPRAS POR AÑO (SIN FILTRO DE PROVEEDOR/ARTÍCULO)
# =====================================================================

def get_compras_anio(anio: int, limite: int = 5000) -> pd.DataFrame:
    """Todas las compras de un año."""
    # Usar expresión simple para evitar errores de parseo
    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            TRIM("Nro. Comprobante") AS Nro_Factura,
            "Fecha",
            "Cantidad",
            "Moneda",
            TRIM("Monto Neto") AS Total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año" = %s
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT %s
    """
    return ejecutar_consulta(sql, (anio, limite))


def get_todas_facturas_anio(anio: int, limite: int = 5000) -> pd.DataFrame:
    """Alias para get_compras_anio: Todas las facturas/compras de un año sin filtro de proveedor."""
    return get_compras_anio(anio, limite)


def get_total_compras_anio(anio: int) -> dict:
    """Total de compras de un año (resumen)."""
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()
    sql = f"""
        SELECT
            COUNT(*) AS registros,
            COALESCE(SUM(CASE WHEN TRIM("Moneda") = '$' THEN {total_pesos} ELSE 0 END), 0) AS total_pesos,
            COALESCE(SUM(CASE WHEN TRIM("Moneda") IN ('U$S', 'U$$') THEN {total_usd} ELSE 0 END), 0) AS total_usd,
            COUNT(DISTINCT TRIM("Cliente / Proveedor")) AS proveedores,
            COUNT(DISTINCT TRIM("Articulo")) AS articulos
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año" = %s
    """
    df = ejecutar_consulta(sql, (anio,))
    if df is not None and not df.empty:
        return {
            "registros": int(df["registros"].iloc[0] or 0),
            "total_pesos": float(df["total_pesos"].iloc[0] or 0),
            "total_usd": float(df["total_usd"].iloc[0] or 0),
            "proveedores": int(df["proveedores"].iloc[0] or 0),
            "articulos": int(df["articulos"].iloc[0] or 0)
        }
    return {"registros": 0, "total_pesos": 0.0, "total_usd": 0.0, "proveedores": 0, "articulos": 0}


# =====================================================================
# COMPRAS PROVEEDOR AÑO (NUEVA FUNCIÓN PARA SIMPLIFICAR CONSULTAS SIMPLES)
# =====================================================================

def get_compras_proveedor_anio(proveedor_like: str, anio: int, limite: int = 5000) -> pd.DataFrame:
    """Detalle de compras de un proveedor en un año específico."""
    # Llama a la función existente para consistencia
    return get_detalle_facturas_proveedor_anio(
        proveedores=[proveedor_like],
        anios=[anio],
        moneda=None,
        limite=limite
    )


# =====================================================================
# COMPRAS MÚLTIPLES: PROVEEDORES, MESES Y AÑOS (NUEVA FUNCIÓN)
# =====================================================================

def get_compras_multiples(
    proveedores: List[str], 
    meses: Optional[List[str]] = None, 
    anios: Optional[List[int]] = None, 
    limite: int = 5000
) -> pd.DataFrame:
    """
    Detalle de compras para múltiples proveedores, meses y años.
    Ejemplo: proveedores=["roche", "biodiagnostico"], meses=["2025-07"], anios=[2025]

    FIX: el filtro por meses se hace por "Mes" (directo, sin rangos de fecha),
    para consistencia con otras consultas y evitar problemas con formatos de "Fecha".
    """
    if not proveedores:
        return pd.DataFrame()

    where_parts = [
        # '("Tipo Comprobante" = \'Compra Contado\' OR "Tipo Comprobante" LIKE \'Compra%\')'  # TEMPORAL: Quitado para probar
    ]
    params: List[Any] = []

    # Proveedores (normalización simple, igual que función única)
    prov_clauses = []
    for p in proveedores:
        p = str(p).strip().lower()
        if not p:
            continue
        prov_clauses.append(
            "LOWER(TRIM(\"Cliente / Proveedor\")) LIKE %s"
        )
        params.append(f"%{p}%")

    if prov_clauses:
        where_parts.append("(" + " OR ".join(prov_clauses) + ")")

    # Meses -> por "Mes" (con TRIM para manejar espacios)
    if meses:
        mes_clauses = []
        for m in (meses or []):
            if not m:
                continue
            mes_clauses.append('TRIM("Mes") = %s')
            params.append(m)
        if mes_clauses:
            where_parts.append("(" + " OR ".join(mes_clauses) + ")")

    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            TRIM("Nro. Comprobante") AS Nro_Factura,
            "Fecha",
            "Cantidad",
            "Moneda",
            TRIM("Monto Neto") AS Total
        FROM chatbot_raw
        WHERE {" AND ".join(where_parts)}
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT {limite}
    """
    return ejecutar_consulta(sql, tuple(params))


# =====================================================================
# DETALLE COMPRAS: PROVEEDOR + MES
# =====================================================================

def get_detalle_compras_proveedor_mes(proveedor_like: str, mes_key: str, anio: Optional[int] = None) -> pd.DataFrame:
    """Detalle de compras de un proveedor en un mes específico, opcionalmente filtrado por año."""
    proveedor_like = (proveedor_like or "").strip().lower()
    
    # Construir la consulta con filtro opcional de año
    anio_filter = f'AND "Año" = {anio}' if anio else ""
    
    # Usar Total simple para evitar errores de parseo
    sql = f"""
        SELECT 
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            TRIM("Nro. Comprobante") AS Nro_Factura,
            "Fecha",
            "Cantidad",
            "Moneda",
            TRIM("Monto Neto") AS Total
        FROM chatbot_raw 
        WHERE LOWER(TRIM("Cliente / Proveedor")) LIKE %s
          AND TRIM("Mes") = %s
          {anio_filter}
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        ORDER BY "Fecha" DESC NULLS LAST
    """
    
    df = ejecutar_consulta(sql, (f"%{proveedor_like}%", mes_key))
    
    # FALLBACK AUTOMÁTICO DE MES (solo si no hay año especificado, o ajusta si es necesario)
    if df is None or df.empty:
        mes_alt = get_ultimo_mes_disponible_hasta(mes_key)
        if mes_alt and mes_alt != mes_key:
            sql_alt = f"""
                SELECT 
                    TRIM("Cliente / Proveedor") AS Proveedor,
                    TRIM("Articulo") AS Articulo,
                    TRIM("Nro. Comprobante") AS Nro_Factura,
                    "Fecha",
                    "Cantidad",
                    "Moneda",
                    TRIM("Monto Neto") AS Total
                FROM chatbot_raw 
                WHERE LOWER(TRIM("Cliente / Proveedor")) LIKE %s
                  AND TRIM("Mes") = %s
                  {anio_filter}
                  AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
                ORDER BY "Fecha" DESC NULLS LAST
            """
            df = ejecutar_consulta(sql_alt, (f"%{proveedor_like}%", mes_alt))
            if df is not None and not df.empty:
                df.attrs["fallback_mes"] = mes_alt
    
    return df if df is not None else pd.DataFrame()


# =====================================================================
# DETALLE COMPRAS: PROVEEDOR + AÑO
# =====================================================================

def get_detalle_facturas_proveedor_anio(
    proveedores: List[str], 
    anios: List[int], 
    moneda: Optional[str] = None, 
    limite: int = 5000
) -> pd.DataFrame:
    """Detalle de facturas de un proveedor en uno o varios años."""
    
    anios = sorted(anios)
    anios_sql = ", ".join(map(str, anios))  # "2024, 2025"
    
    # Usar Total simple
    moneda_sql = ""
    if moneda:
        moneda = moneda.strip().upper()
        if moneda in ("U$S", "USD", "U$$", "US$"):
            moneda_sql = "AND TRIM(\"Moneda\") IN ('U$S', 'U$$', 'USD', 'US$')"
        elif moneda in ("$", "UYU"):
            moneda_sql = "AND TRIM(\"Moneda\") = '$'"

    prov_where = ""
    prov_params = []
    if proveedores:
        parts = [f"LOWER(TRIM(\"Cliente / Proveedor\")) LIKE %s" for _ in proveedores]
        prov_params = [f"%{p.lower()}%" for p in proveedores]
        prov_where = f"AND ({' OR '.join(parts)})"

    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            TRIM("Nro. Comprobante") AS Nro_Factura,
            "Fecha",
            "Año",
            "Moneda",
            TRIM("Monto Neto") AS Total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año" IN ({anios_sql})
          {prov_where}
          {moneda_sql}
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT {limite}
    """
    return ejecutar_consulta(sql, tuple(prov_params))


def get_total_compras_proveedor_anio(
    proveedor_like: str, 
    anio: int
) -> dict:
    """Resumen total de compras de un proveedor en un solo año."""
    proveedor_like = (proveedor_like or "").split("(")[0].strip().lower()
    sql = f"""
        SELECT
            COUNT(*) AS registros,
            COALESCE(SUM(CAST(NULLIF(TRIM("Monto Neto"), '') AS NUMERIC)), 0) AS total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND LOWER(TRIM("Cliente / Proveedor")) LIKE %s
          AND "Año" = %s
    """
    df = ejecutar_consulta(sql, (f"%{proveedor_like}%", anio))
    if df is not None and not df.empty:
        return {
            "registros": int(df["registros"].iloc[0] or 0),
            "total": float(df["total"].iloc[0] or 0)
        }
    return {"registros": 0, "total": 0.0}


# =====================================================================
# DETALLE COMPRAS: ARTÍCULO + MES
# =====================================================================

def get_detalle_compras_articulo_mes(articulo_like: str, mes_key: str) -> pd.DataFrame:
    """Detalle de compras de un artículo en un mes específico."""
    articulo_like = (articulo_like or "").strip().lower()
    sql = f"""
        SELECT 
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            TRIM("Nro. Comprobante") AS Nro_Factura,
            "Fecha",
            "Cantidad",
            "Moneda",
            TRIM("Monto Neto") AS Total
        FROM chatbot_raw 
        WHERE LOWER(TRIM("Articulo")) LIKE %s
          AND TRIM("Mes") = %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        ORDER BY "Fecha" DESC NULLS LAST
    """
    return ejecutar_consulta(sql, (f"%{articulo_like}%", mes_key))


# =====================================================================
# DETALLE COMPRAS: ARTÍCULO + AÑO
# =====================================================================

def get_detalle_compras_articulo_anio(articulo_like: str, anio: int, limite: int = 500) -> pd.DataFrame:
    """Detalle de compras de un artículo en un año."""
    if limite is None:
        limite = 500
    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            TRIM("Nro. Comprobante") AS Nro_Factura,
            "Fecha",
            "Cantidad",
            "Moneda",
            TRIM("Monto Neto") AS Total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año" = %s
          AND LOWER(TRIM("Articulo")) LIKE %s
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT %s
    """
    return ejecutar_consulta(sql, (anio, f"%{articulo_like.lower()}%", limite))


def get_total_compras_articulo_anio(articulo_like: str, anio: int) -> dict:
    """Total de compras de un artículo en un año."""
    sql = f"""
        SELECT
            COUNT(*) AS registros,
            COALESCE(SUM(CAST(NULLIF(TRIM("Monto Neto"), '') AS NUMERIC)), 0) AS total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año" = %s
          AND LOWER(TRIM("Articulo")) LIKE %s
    """
    df = ejecutar_consulta(sql, (anio, f"%{articulo_like.lower()}%"))
    if df is not None and not df.empty:
        return {
            "registros": int(df["registros"].iloc[0] or 0),
            "total": float(df["total"].iloc[0] or 0)
        }
    return {"registros": 0, "total": 0.0}


# =====================================================================
# FACTURAS (mantener expresiones complejas donde sea necesario)
# =====================================================================

def _factura_variantes(nro_factura: str) -> List[str]:
    """Genera variantes de número de factura."""
    s = (nro_factura or "").strip().upper()
    if not s:
        return []

    variantes = [s]

    if s.isdigit():
        if len(s) <= 8:
            variantes.append("A" + s.zfill(8))
        if len(s) < 8:
            variantes.append(s.zfill(8))
    else:
        i = 0
        while i < len(s) and s[i].isalpha():
            i += 1
        pref = s[:i]
        dig = s[i:]

        if dig.isdigit() and dig:
            variantes.append(dig)
            variantes.append(dig.lstrip("0") or dig)
            if pref and len(dig) < 8:
                variantes.append(pref + dig.zfill(8))

    out: List[str] = []
    seen = set()
    for v in variantes:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def get_detalle_factura_por_numero(nro_factura: str) -> pd.DataFrame:
    """Detalle de una factura por número."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            TRIM("Nro. Comprobante") AS nro_factura,
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            "Cantidad",
            "Moneda",
            {total_expr} AS Total
        FROM chatbot_raw
        WHERE TRIM("Nro. Comprobante") = %s
          AND TRIM("Nro. Comprobante") <> 'A0000000'
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        ORDER BY TRIM("Articulo")
    """

    variantes = _factura_variantes(nro_factura)
    if not variantes:
        return ejecutar_consulta(sql, ("",))

    df = ejecutar_consulta(sql, (variantes[0],))
    if df is not None and not df.empty:
        return df

    for alt in variantes[1:]:
        df2 = ejecutar_consulta(sql, (alt,))
        if df2 is not None and not df2.empty:
            df2.attrs["nro_factura_fallback"] = alt
            return df2

    return df if df is not None else pd.DataFrame()


def get_total_factura_por_numero(nro_factura: str) -> pd.DataFrame:
    """Total de una factura."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT COALESCE(SUM({total_expr}), 0) AS total_factura
        FROM chatbot_raw
        WHERE TRIM("Nro. Comprobante") = %s
    """

    variantes = _factura_variantes(nro_factura)
    if not variantes:
        return ejecutar_consulta(sql, ("",))

    df = ejecutar_consulta(sql, (variantes[0],))
    if df is not None and not df.empty:
        return df

    for alt in variantes[1:]:
        df2 = ejecutar_consulta(sql, (alt,))
        if df2 is not None and not df2.empty:
            df2.attrs["nro_factura_fallback"] = alt
            return df2

    return df if df is not None else pd.DataFrame()


def get_ultima_factura_de_articulo(patron_articulo: str) -> pd.DataFrame:
    """Última factura de un artículo."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            "Cantidad",
            TRIM("Nro. Comprobante") AS nro_factura,
            "Moneda",
            {total_expr} AS total_linea,
            "Fecha"
        FROM chatbot_raw
        WHERE LOWER(TRIM("Articulo")) LIKE %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT 1
    """
    return ejecutar_consulta(sql, (f"%{patron_articulo.lower()}%",))


def get_ultima_factura_inteligente(patron: str) -> pd.DataFrame:
    """Busca última factura por artículo O proveedor."""
    patron = (patron or "").strip().lower()
    total_expr = _sql_total_num_expr_general()

    sql_art = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            "Cantidad",
            TRIM("Nro. Comprobante") AS nro_factura,
            "Moneda",
            {total_expr} AS total_linea,
            "Fecha"
        FROM chatbot_raw
        WHERE LOWER(TRIM("Articulo")) LIKE %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT 1
    """
    df = ejecutar_consulta(sql_art, (f"%{patron}%",))

    if df is not None and not df.empty:
        return df

    sql_prov = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            "Cantidad",
            TRIM("Nro. Comprobante") AS nro_factura,
            "Moneda",
            {total_expr} AS total_linea,
            "Fecha"
        FROM chatbot_raw
        WHERE LOWER(TRIM("Cliente / Proveedor")) LIKE %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT 1
    """
    return ejecutar_consulta(sql_prov, (f"%{patron}%",))


def get_ultima_factura_numero_de_articulo(patron_articulo: str) -> Optional[str]:
    """Obtiene solo el número de la última factura."""
    sql = """
        SELECT TRIM("Nro. Comprobante") AS nro_factura
        FROM chatbot_raw
        WHERE LOWER(TRIM("Articulo")) LIKE %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT 1
    """
    df = ejecutar_consulta(sql, (f"%{patron_articulo.lower()}%",))
    if df is not None and not df.empty:
        return str(df["nro_factura"].iloc[0]).strip() or None
    return None


def get_facturas_de_articulo(patron_articulo: str, solo_ultima: bool = False) -> pd.DataFrame:
    """Lista de facturas de un artículo."""
    total_expr = _sql_total_num_expr_general()
    limit_sql = "LIMIT 1" if solo_ultima else "LIMIT 50"
    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            TRIM("Nro. Comprobante") AS Nro_Factura,
            "Fecha",
            "Cantidad",
            "Moneda",
            {total_expr} AS Total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND LOWER(TRIM("Articulo")) LIKE %s
        ORDER BY "Fecha" DESC NULLS LAST
        {limit_sql}
    """
    return ejecutar_consulta(sql, (f"%{patron_articulo.lower()}%",))

# =========================
# TOTAL FACTURAS POR PROVEEDOR
# =========================
def get_total_facturas_proveedor(
    proveedores: List[str],
    meses: Optional[List[str]] = None,
    anios: Optional[List[int]] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
):
    if not proveedores:
        return pd.DataFrame()

    where_parts = [
        '("Tipo Comprobante" = \'Compra Contado\' OR "Tipo Comprobante" LIKE \'Compra%\')'
    ]
    params: List[Any] = []

    prov_clauses = []
    for p in proveedores:
        p = str(p).strip().lower()
        if p:
            prov_clauses.append('LOWER(TRIM(regexp_replace("Cliente / Proveedor", \'[áéíóúÁÉÍÓÚñÑ]\', \'[aeiouAEIOUñN]\', \'g\'))) LIKE %s')
            params.append(f"%{p}%")

    if prov_clauses:
        where_parts.append("(" + " OR ".join(prov_clauses) + ")")

    if desde and hasta:
        where_parts.append('"Fecha"::date BETWEEN %s AND %s')
        params.extend([desde, hasta])

    elif meses:
        ph = ", ".join(["%s"] * len(meses))
        where_parts.append(f'LOWER(TRIM("Mes")) IN ({ph})')  # ✅ LOWER agregado
        params.extend([m.lower() for m in meses])  # ✅ .lower() agregado

    elif anios:
        ph = ", ".join(["%s"] * len(anios))
        where_parts.append(f'"Año" IN ({ph})')
        params.extend(anios)

    query = f"""
        SELECT
            TRIM("Moneda") AS Moneda,
            COALESCE(SUM(CAST(NULLIF(TRIM("Monto Neto"), '') AS NUMERIC)), 0) AS Total
        FROM chatbot_raw
        WHERE {" AND ".join(where_parts)}
        GROUP BY TRIM("Moneda")
        ORDER BY Total DESC
    """

    return ejecutar_consulta(query, tuple(params))


# =========================
# FACTURAS PROVEEDOR (DETALLE) - MODIFICADO PARA MANEJAR "TODAS" Y AUMENTAR LÍMITE PARA TODAS LAS FACTURAS
# =========================
def get_facturas_proveedor_detalle(proveedores, meses, anios, desde, hasta, articulo, moneda, limite):
    """
    Listado/detalle de facturas para proveedor(es) con filtros opcionales.
    Ahora maneja palabras como "todas", "las", "all" como indicadores de sin filtro de proveedor.
    Para consultas generales (sin proveedores), aumenta el límite a 10000 para traer más datos.
    """

    # ✅ FIX: Si proveedores contiene palabras genéricas como "todas", "las", "all", setear vacío para traer TODAS
    if proveedores:
        proveedores_filtrados = []
        for p in proveedores:
            p_clean = str(p).strip().lower()
            if p_clean not in ("todas", "las", "all", "todos", "todo"):
                proveedores_filtrados.append(p)
        proveedores = proveedores_filtrados if proveedores_filtrados else None

    print("\n[SQL_COMPRAS] get_facturas_proveedor_detalle() llamado con:")
    print(f"  proveedores = {proveedores}")
    print(f"  meses       = {meses}")
    print(f"  anios       = {anios}")
    print(f"  desde       = {desde}")
    print(f"  hasta       = {hasta}")
    print(f"  articulo    = {articulo}")
    print(f"  moneda      = {moneda}")
    print(f"  limite      = {limite}")

    if limite is None:
        limite = 5000
    try:
        limite = int(limite)
    except Exception:
        limite = 5000
    if limite <= 0:
        limite = 5000

    # Si no hay proveedores, meses, desde/hasta, articulo, moneda, solo anios, usar get_compras_anio con límite mayor
    if not proveedores and not meses and not desde and not hasta and not articulo and not moneda and anios:
        # Caso general: todas las facturas del año, aumentar límite a 10000
        return get_compras_anio(anios[0], max(limite, 10000))

    # QUERY SIMPLIFICADO PARA EVITAR ERRORES EN CONSTRUCCIÓN DE WHERE
    if len(proveedores or []) == 1 and anios and not meses and not desde and not hasta and not articulo and not moneda:
        # Caso simple: solo proveedores y años
        prov_like = f"%{proveedores[0].lower()}%"
        anio_val = anios[0]
        sql = f"""
            SELECT
                TRIM("Cliente / Proveedor") AS Proveedor,
                TRIM("Articulo") AS Articulo,
                TRIM("Nro. Comprobante") AS Nro_Factura,
                "Fecha",
                "Cantidad",
                "Moneda"
            FROM chatbot_raw
            WHERE LOWER(TRIM(regexp_replace("Cliente / Proveedor", \'[áéíóúÁÉÍÓÚñÑ]\', \'[aeiouAEIOUñN]\', \'g\'))) LIKE %s
              AND "Año" = %s
              AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
            ORDER BY "Fecha" DESC NULLS LAST
            LIMIT %s
        """
        params = (prov_like, anio_val, limite)
        print(f"\n🛠 SQL simplificado: {sql}")
        print(f"🛠 Params: {params}")
        df = ejecutar_consulta(sql, params)
        return df if df is not None else pd.DataFrame()

    # Para otros casos, usar el query complejo original (sin Total para debug)
    where_parts = [
        '("Tipo Comprobante" = \'Compra Contado\' OR "Tipo Comprobante" LIKE \'Compra%\')'
    ]
    params: List[Any] = []

    prov_clauses = []
    if proveedores:  # Solo agregar filtro si hay proveedores reales
        for p in proveedores:
            p = str(p).strip().lower()
            if not p:
                continue
            prov_clauses.append('LOWER(TRIM(regexp_replace("Cliente / Proveedor", \'[áéíóúÁÉÍÓÚñÑ]\', \'[aeiouAEIOUñN]\', \'g\'))) LIKE %s')
            params.append(f"%{p}%")

    if prov_clauses:
        where_parts.append("(" + " OR ".join(prov_clauses) + ")")

    if articulo and str(articulo).strip():
        where_parts.append('LOWER(TRIM("Articulo")) LIKE %s')
        params.append(f"%{str(articulo).lower().strip()}%")

    if moneda and str(moneda).strip():
        m = str(moneda).upper().strip()
        if m in ("USD", "U$S", "U$$", "US$"):
            where_parts.append('TRIM("Moneda") IN (\'U$S\', \'U$$\', \'USD\', \'US$\')')
        elif m in ("$", "UYU", "PESOS"):
            where_parts.append('TRIM("Moneda") = \'$\'')

    # MODIFICACIÓN: Permitir filtros combinados de meses y años (eliminé elif y usé if para ambos)
    if meses:
        meses_ok = [m for m in (meses or []) if m]
        if meses_ok:
            ph = ", ".join(["%s"] * len(meses_ok))
            where_parts.append(f'LOWER(TRIM("Mes")) IN ({ph})')  # ✅ LOWER agregado
            params.extend([m.lower() for m in meses_ok])  # ✅ .lower() agregado

    if anios:
        anios_ok: List[int] = []
        for a in (anios or []):
            if isinstance(a, int):
                anios_ok.append(a)
        if anios_ok:
            ph = ", ".join(["%s"] * len(anios_ok))
            where_parts.append(f'"Año" IN ({ph})')
            params.extend(anios_ok)

    if desde and hasta:
        where_parts.append('"Fecha"::date BETWEEN %s AND %s')
        params.extend([desde, hasta])

    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            TRIM("Nro. Comprobante") AS Nro_Factura,
            "Fecha",
            "Cantidad",
            "Moneda"
        FROM chatbot_raw
        WHERE {" AND ".join(where_parts)}
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT {limite}
    """
    df = ejecutar_consulta(sql, tuple(params))
    return df if df is not None else pd.DataFrame()


# =========================
# =========================
# TOTAL FACTURAS POR MONEDA AÑO - CORREGIDA
# =========================
def get_total_facturas_por_moneda_anio(anio: int) -> pd.DataFrame:
    """Total de facturas por moneda en un año específico."""
    total_expr = _sql_total_num_expr_general()  # Usa la expresión estándar para consistencia
    sql = f"""
        SELECT
            TRIM("Moneda") AS Moneda,
            COUNT(DISTINCT "Nro. Comprobante") AS total_facturas,
            COALESCE(SUM({total_expr}), 0) AS monto_total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año" = %s
        GROUP BY TRIM("Moneda")
        ORDER BY monto_total DESC  -- Cambiado a DESC para un ordenamiento más útil
    """
    return ejecutar_consulta(sql, (anio,))

# =========================
# TOTAL FACTURAS POR MONEDA - GENÉRICO (TODOS LOS AÑOS, AGRUPADO POR AÑO)
# =========================
def get_total_facturas_por_moneda_todos_anios() -> pd.DataFrame:
    """Total de facturas por moneda y año, mostrando todos los años disponibles."""
    total_expr = _sql_total_num_expr_general()  # Usa la expresión estándar para consistencia
    sql = f"""
        SELECT
            "Año" AS Anio,
            TRIM("Moneda") AS Moneda,
            COUNT(DISTINCT "Nro. Comprobante") AS total_facturas,
            COALESCE(SUM({total_expr}), 0) AS monto_total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        GROUP BY "Año", TRIM("Moneda")
        ORDER BY "Año" ASC, monto_total DESC
    """
    return ejecutar_consulta(sql, ())

# =========================
# TOTAL COMPRAS POR MONEDA - GENÉRICO (TODOS LOS AÑOS, AGRUPADO POR AÑO)
# =========================
def get_total_compras_por_moneda_todos_anios() -> pd.DataFrame:
    """Total de compras por moneda y año, mostrando todos los años disponibles."""
    total_expr = _sql_total_num_expr_general()  # Usa la expresión estándar para consistencia
    sql = f"""
        SELECT
            "Año" AS Anio,
            TRIM("Moneda") AS Moneda,
            COALESCE(SUM({total_expr}), 0) AS Total_Compras
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        GROUP BY "Año", TRIM("Moneda")
        ORDER BY "Año" ASC, Total_Compras DESC
    """
    return ejecutar_consulta(sql, ())

# =========================
# TOTAL COMPRAS POR MONEDA AÑO
# =========================
def get_total_compras_por_moneda_anio(anio: int) -> pd.DataFrame:
    """Total de compras (monto) por moneda en un año específico."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            TRIM("Moneda") AS Moneda,
            COALESCE(SUM({total_expr}), 0) AS Total_Compras
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año" = %s
        GROUP BY TRIM("Moneda")
        ORDER BY Total_Compras DESC
    """
    return ejecutar_consulta(sql, (anio,))


# =========================
# FUNCIONES PARA DASHBOARD
# =========================

def get_dashboard_totales(anio: int) -> dict:
    """Totales generales para métricas del dashboard."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            COALESCE(SUM(CASE WHEN TRIM("Moneda") = '$' THEN {total_expr} ELSE 0 END), 0) AS total_pesos,
            COALESCE(SUM(CASE WHEN TRIM("Moneda") IN ('U$S', 'U$$') THEN {total_expr} ELSE 0 END), 0) AS total_usd,
            COUNT(DISTINCT TRIM("Cliente / Proveedor")) AS proveedores,
            COUNT(DISTINCT TRIM("Nro. Comprobante")) AS facturas
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año" = %s
    """
    df = ejecutar_consulta(sql, (anio,))
    if df is not None and not df.empty:
        return {
            "total_pesos": float(df["total_pesos"].iloc[0] or 0),
            "total_usd": float(df["total_usd"].iloc[0] or 0),
            "proveedores": int(df["proveedores"].iloc[0] or 0),
            "facturas": int(df["facturas"].iloc[0] or 0)
        }
    return {"total_pesos": 0.0, "total_usd": 0.0, "proveedores": 0, "facturas": 0}


def get_dashboard_compras_por_mes(anio: int) -> pd.DataFrame:
    """Datos para gráfico de barras mensual."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            TRIM("Mes") AS Mes,
            COALESCE(SUM({total_expr}), 0) AS Total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año" = %s
        GROUP BY TRIM("Mes")
        ORDER BY MIN("Fecha") ASC
    """
    return ejecutar_consulta(sql, (anio,))


def get_dashboard_top_proveedores(anio: int, top_n: int = 10, moneda: str = "$") -> pd.DataFrame:
    """Top proveedores por moneda."""
    total_expr = _sql_total_num_expr_general()
    moneda_filter = f"TRIM(\"Moneda\") = '{moneda}'" if moneda == "$" else f"TRIM(\"Moneda\") IN ('U$S', 'U$$')"
    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            COALESCE(SUM({total_expr}), 0) AS Total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año" = %s
          AND {moneda_filter}
          AND TRIM("Cliente / Proveedor") <> ''
        GROUP BY TRIM("Cliente / Proveedor")
        ORDER BY Total DESC
        LIMIT %s
    """
    return ejecutar_consulta(sql, (anio, top_n))


def get_dashboard_gastos_familia(anio: int) -> pd.DataFrame:
    """Datos para gráfico de torta por familia."""
    # Asumiendo que hay una columna "Familia" o similar; ajusta según tu esquema
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            COALESCE(TRIM("Familia"), 'Sin Clasificar') AS Familia,
            COALESCE(SUM({total_expr}), 0) AS Total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año" = %s
        GROUP BY COALESCE(TRIM("Familia"), 'Sin Clasificar')
        ORDER BY Total DESC
    """
    return ejecutar_consulta(sql, (anio,))


def get_dashboard_ultimas_compras(limite: int = 5) -> pd.DataFrame:
    """Últimas compras recientes."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            "Fecha",
            {total_expr} AS Total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT %s
    """
    return ejecutar_consulta(sql, (limite,))
