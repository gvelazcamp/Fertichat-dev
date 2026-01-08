# =========================
# SQL COMPRAS - CONSULTAS TRANSACCIONALES
# =========================

import re
import pandas as pd
from typing import List, Optional, Any
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
    total_expr = _sql_total_num_expr_general()
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
          AND "Año"::int = %s
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT %s
    """
    return ejecutar_consulta(sql, (anio, limite))


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
          AND "Año"::int = %s
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
# DETALLE COMPRAS: PROVEEDOR + MES
# =====================================================================

def get_detalle_compras_proveedor_mes(proveedor_like: str, mes_key: str) -> pd.DataFrame:
    proveedor_like = (proveedor_like or "").strip().lower()
    total_expr = _sql_total_num_expr_general()

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
        WHERE LOWER(TRIM("Cliente / Proveedor")) LIKE %s
          AND TRIM("Mes") = %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        ORDER BY "Fecha" DESC NULLS LAST
    """

    df = ejecutar_consulta(sql, (f"%{proveedor_like}%", mes_key))

    # FALLBACK AUTOMÁTICO DE MES
    if df.empty:
        mes_alt = get_ultimo_mes_disponible_hasta(mes_key)
        if mes_alt and mes_alt != mes_key:
            df = ejecutar_consulta(sql, (f"%{proveedor_like}%", mes_alt))
            if not df.empty:
                df.attrs["fallback_mes"] = mes_alt

    return df


# =====================================================================
# DETALLE COMPRAS: PROVEEDOR + AÑO
# =====================================================================

def get_detalle_compras_proveedor_anio(proveedor_like: str, anio: int, moneda: str = None) -> pd.DataFrame:
    """Detalle de compras de un proveedor en un año."""
    proveedor_like = (proveedor_like or "").split("(")[0].strip().lower()
    total_expr = _sql_total_num_expr_general()

    moneda_sql = ""
    if moneda and str(moneda).strip().upper() in ("U$S", "USD", "U$$"):
        moneda_sql = "AND TRIM(\"Moneda\") IN ('U$S','U$$')"
    elif moneda and str(moneda).strip() in ("$", "UYU"):
        moneda_sql = "AND TRIM(\"Moneda\") = '$'"

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
          AND LOWER(TRIM("Cliente / Proveedor")) LIKE %s
          AND "Año"::int = %s
          {moneda_sql}
        ORDER BY "Fecha" DESC NULLS LAST
    """
    return ejecutar_consulta(sql, (f"%{proveedor_like}%", anio))


def get_total_compras_proveedor_anio(proveedor_like: str, anio: int) -> dict:
    """Total de compras de un proveedor en un año."""
    proveedor_like = (proveedor_like or "").split("(")[0].strip().lower()
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            COUNT(*) AS registros,
            COALESCE(SUM({total_expr}), 0) AS total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND LOWER(TRIM("Cliente / Proveedor")) LIKE %s
          AND "Año"::int = %s
    """
    df = ejecutar_consulta(sql, (f"%{proveedor_like}%", anio))
    if df is not None and not df.empty:
        return {
            "registros": int(df["registros"].iloc[0] or 0),
            "total": float(df["total"].iloc[0] or 0)
        }
    return {"registros": 0, "total": 0.0}


def get_detalle_compras_proveedor_anios(anios: List[int], proveedores: List[str] = None) -> pd.DataFrame:
    """Detalle de compras por proveedor en varios años."""
    total_expr = _sql_total_num_expr_general()
    anios = sorted(anios)
    anios_sql = ", ".join(str(y) for y in anios)

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
            "Año",
            "Moneda",
            {total_expr} AS Total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año"::int IN ({anios_sql})
          {prov_where}
        ORDER BY "Año" DESC, TRIM("Cliente / Proveedor"), TRIM("Articulo")
        LIMIT 500
    """
    return ejecutar_consulta(sql, tuple(prov_params) if prov_params else None)


# =====================================================================
# DETALLE COMPRAS: ARTÍCULO + MES
# =====================================================================

def get_detalle_compras_articulo_mes(articulo_like: str, mes_key: str) -> pd.DataFrame:
    """Detalle de compras de un artículo en un mes específico."""
    articulo_like = (articulo_like or "").strip().lower()
    total_expr = _sql_total_num_expr_general()
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
        WHERE LOWER(TRIM("Articulo")) LIKE %s
          AND "Mes" = %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        ORDER BY "Fecha" DESC NULLS LAST
    """
    return ejecutar_consulta(sql, (f"%{articulo_like}%", mes_key))


# =====================================================================
# DETALLE COMPRAS: ARTÍCULO + AÑO
# =====================================================================

def get_detalle_compras_articulo_anio(articulo_like: str, anio: int, limite: int = 500) -> pd.DataFrame:
    """Detalle de compras de un artículo en un año."""
    total_expr = _sql_total_num_expr_general()
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
            {total_expr} AS Total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año"::int = %s
          AND LOWER(TRIM("Articulo")) LIKE %s
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT %s
    """
    return ejecutar_consulta(sql, (anio, f"%{articulo_like.lower()}%", limite))


def get_total_compras_articulo_anio(articulo_like: str, anio: int) -> dict:
    """Total de compras de un artículo en un año."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            COUNT(*) AS registros,
            COALESCE(SUM({total_expr}), 0) AS total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año"::int = %s
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
# FACTURAS
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

    return df


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

    return df


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
    if df.empty:
        return None
    return str(df["nro_factura"].iloc[0]).strip() or None


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
# TODAS LAS FACTURAS DE PROVEEDOR (DETALLE)
# =========================
def get_facturas_proveedor_detalle(
    proveedores: List[str],
    meses: Optional[List[str]] = None,
    anios: Optional[List[int]] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    articulo: Optional[str] = None,
    moneda: Optional[str] = None,
    limite: int = 5000,
):
    """Devuelve detalle de facturas filtrando por proveedor y tiempo."""

    def _short_token_prov(p: str) -> Optional[str]:
        if not p:
            return None
            
        stop = {
            "laboratorio", "lab", "sa", "srl", "ltda", "lt", "inc", "ltd",
            "uruguay", "uy", "sociedad", "anonima", "anónima", "de", "del",
            "la", "el", "y", "e", "international",
        }
        
        raw = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]+", (p or "").lower())
        toks = []
        
        for t in raw:
            tt = re.sub(r"[^a-z0-9]+", "", t.lower())
            if len(tt) < 3:
                continue
            if tt in stop:
                continue
            toks.append(tt)
        
        if not toks:
            return None
        
        toks.sort(key=lambda x: len(x), reverse=True)
        return toks[0] if toks else None

    if not proveedores:
        return pd.DataFrame()

    limite = int(limite or 5000)
    if limite <= 0:
        limite = 5000

    where_parts = [
        '("Tipo Comprobante" = \'Compra Contado\' OR "Tipo Comprobante" LIKE \'Compra%\')'
    ]
    params: List[Any] = []

    # Proveedores (OR)
    prov_clauses: List[str] = []
    for p in [str(x).strip() for x in proveedores if str(x).strip()]:
        p_full = p.lower().strip()
        p_short = _short_token_prov(p)
        
        if p_short and p_short != p_full and len(p_short) >= 3:
            prov_clauses.append('(LOWER(TRIM("Cliente / Proveedor")) LIKE %s OR LOWER(TRIM("Cliente / Proveedor")) LIKE %s)')
            params.append(f"%{p_full}%")
            params.append(f"%{p_short}%")
        else:
            prov_clauses.append('LOWER(TRIM("Cliente / Proveedor")) LIKE %s')
            params.append(f"%{p_full}%")

    where_parts.append("(" + " OR ".join(prov_clauses) + ")")

    # Filtro artículo
    if articulo and str(articulo).strip():
        where_parts.append('LOWER(TRIM("Articulo")) LIKE %s')
        params.append(f"%{str(articulo).lower().strip()}%")

    # Filtro moneda
    if moneda and str(moneda).strip():
        m = str(moneda).strip().upper()
        if m in ("USD", "U$S", "U$$", "US$"):
            where_parts.append('TRIM("Moneda") IN (\'U$S\', \'U$$\', \'USD\', \'US$\')')
        elif m in ("$", "PESOS", "UYU", "URU"):
            where_parts.append('TRIM("Moneda") = \'$\'')
        else:
            where_parts.append('UPPER(TRIM("Moneda")) LIKE %s')
            params.append(f"%{m}%")

    # Tiempo
    if desde and hasta:
        where_parts.append('"Fecha"::date BETWEEN %s AND %s')
        params.extend([desde, hasta])
    else:
        # Meses
        if meses:
            meses_ok = [m for m in (meses or []) if m]
            if meses_ok:
                ph = ", ".join(["%s"] * len(meses_ok))
                where_parts.append(f'TRIM("Mes") IN ({ph})')
                params.extend(meses_ok)
        
        # Años (solo si NO hay meses)
        if (not meses) and anios:
            anios_ok = [int(a) for a in (anios or []) if a]
            if anios_ok:
                ph = ", ".join(["%s"] * len(anios_ok))
                where_parts.append(f'"Año"::int IN ({ph})')
                params.extend(anios_ok)

    where_clause_str = " AND ".join(where_parts)
    query = """
    SELECT
        "Fecha",
        TRIM("Cliente / Proveedor") AS Proveedor,
        TRIM("Nro. Comprobante") AS NroFactura,
        TRIM("Tipo Comprobante") AS Tipo,
        TRIM("Articulo") AS Articulo,
        "Moneda",
        "Total"
    FROM chatbot_raw
    WHERE {where_clause}
    ORDER BY "Fecha" DESC NULLS LAST
    LIMIT {limite}
    """.format(where_clause=where_clause_str, limite=limite)
    
    # DEBUG
    try:
        import streamlit as st
        if st.session_state.get("DEBUG_SQL", False):
            st.session_state["DBG_SQL_LAST_QUERY"] = query
            st.session_state["DBG_SQL_LAST_PARAMS"] = list(params)
            st.session_state["DBG_SQL_LAST_TAG"] = "get_facturas_proveedor_detalle"
    except Exception:
        pass

    return ejecutar_consulta(query, tuple(params))


# =====================================================================
# SERIES TEMPORALES Y DATASET COMPLETO
# =====================================================================

def get_serie_compras_agregada(where_clause: str, params: tuple) -> pd.DataFrame:
    """Serie temporal agregada."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            "Fecha"::date AS Fecha,
            SUM({total_expr}) AS Total
        FROM chatbot_raw
        WHERE {where_clause}
        GROUP BY "Fecha"::date
        ORDER BY "Fecha"::date
    """
    return ejecutar_consulta(sql, params)


def get_dataset_completo(where_clause: str, params: tuple):
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            "Fecha",
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            "Cantidad",
            "Moneda",
            {total_expr} AS Total
        FROM chatbot_raw
        WHERE {where_clause}
    """
    return ejecutar_consulta(sql, params)


def get_detalle_compras(where_clause: str, params: tuple) -> pd.DataFrame:
    """Detalle de compras con where personalizado."""
    total_expr = _sql_total_num_expr_general()
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
        WHERE {where_clause}
        ORDER BY "Fecha" DESC NULLS LAST
    """
    return ejecutar_consulta(sql, params)


def get_compras_por_mes_excel(mes_key: str) -> pd.DataFrame:
    """Compras de un mes para exportar a Excel."""
    total_expr = _sql_total_num_expr_general()
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
        WHERE TRIM("Mes") = %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        ORDER BY "Fecha" DESC, TRIM("Cliente / Proveedor")
    """
    return ejecutar_consulta(sql, (mes_key,))


# =====================================================================
# TOP PROVEEDORES
# =====================================================================

def get_top_10_proveedores_chatbot(moneda: str = None, anio: int = None, mes: str = None) -> pd.DataFrame:
    """Top 10 proveedores."""
    total_expr = _sql_total_num_expr_general()
    condiciones = ["(\"Tipo Comprobante\" = 'Compra Contado' OR \"Tipo Comprobante\" LIKE 'Compra%%')"]
    params = []

    if moneda:
        mon = moneda.strip().upper()
        if mon in ("U$S", "U$$", "USD"):
            total_expr = _sql_total_num_expr_usd()
            condiciones.append("TRIM(\"Moneda\") IN ('U$S', 'U$$')")
        else:
            total_expr = _sql_total_num_expr()
            condiciones.append("TRIM(\"Moneda\") = '$'")

    if mes:
        condiciones.append("TRIM(\"Mes\") = %s")
        params.append(mes)
    elif anio:
        condiciones.append("\"Año\"::int = %s")
        params.append(anio)

    where_sql = " AND ".join(condiciones)
    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            SUM({total_expr}) AS Total,
            COUNT(*) AS Registros
        FROM chatbot_raw
        WHERE {where_sql}
          AND "Cliente / Proveedor" IS NOT NULL
          AND TRIM("Cliente / Proveedor") <> ''
        GROUP BY TRIM("Cliente / Proveedor")
        ORDER BY Total DESC
        LIMIT 10
    """
    return ejecutar_consulta(sql, tuple(params) if params else None)


# =====================================================================
# DASHBOARD
# =====================================================================

def get_dashboard_totales(anio: int) -> dict:
    """Totales para dashboard."""
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()
    sql = f"""
        SELECT
            COALESCE(SUM(CASE WHEN TRIM("Moneda") = '$' THEN {total_pesos} ELSE 0 END), 0) AS total_pesos,
            COALESCE(SUM(CASE WHEN TRIM("Moneda") IN ('U$S', 'U$$') THEN {total_usd} ELSE 0 END), 0) AS total_usd,
            COUNT(DISTINCT "Cliente / Proveedor") AS proveedores,
            COUNT(DISTINCT "Nro. Comprobante") AS facturas
        FROM chatbot_raw
        WHERE "Año"::int = %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
    """
    df = ejecutar_consulta(sql, (anio,))
    if df is not None and not df.empty:
        return {
            "total_pesos": float(df["total_pesos"].iloc[0] or 0),
            "total_usd": float(df["total_usd"].iloc[0] or 0),
            "proveedores": int(df["proveedores"].iloc[0] or 0),
            "facturas": int(df["facturas"].iloc[0] or 0)
        }
    return {"total_pesos": 0, "total_usd": 0, "proveedores": 0, "facturas": 0}


def get_dashboard_compras_por_mes(anio: int) -> pd.DataFrame:
    """Compras por mes para dashboard."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            TRIM("Mes") AS Mes,
            SUM({total_expr}) AS Total
        FROM chatbot_raw
        WHERE "Año"::int = %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        GROUP BY TRIM("Mes")
        ORDER BY TRIM("Mes")
    """
    return ejecutar_consulta(sql, (anio,))


def get_dashboard_top_proveedores(anio: int, top_n: int = 10, moneda: str = "$") -> pd.DataFrame:
    """Top proveedores para dashboard."""
    if moneda in ("U$S", "U$$", "USD"):
        total_expr = _sql_total_num_expr_usd()
        mon_filter = "TRIM(\"Moneda\") IN ('U$S', 'U$$')"
    else:
        total_expr = _sql_total_num_expr()
        mon_filter = "TRIM(\"Moneda\") = '$'"

    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            SUM({total_expr}) AS Total
        FROM chatbot_raw
        WHERE "Año"::int = %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND {mon_filter}
          AND "Cliente / Proveedor" IS NOT NULL
          AND TRIM("Cliente / Proveedor") <> ''
        GROUP BY TRIM("Cliente / Proveedor")
        ORDER BY Total DESC
        LIMIT %s
    """
    return ejecutar_consulta(sql, (anio, top_n))


def get_dashboard_gastos_familia(anio: int) -> pd.DataFrame:
    """Gastos por familia para dashboard."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            TRIM(COALESCE("Familia", 'SIN FAMILIA')) AS Familia,
            SUM({total_expr}) AS Total
        FROM chatbot_raw
        WHERE "Año"::int = %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        GROUP BY TRIM(COALESCE("Familia", 'SIN FAMILIA'))
        ORDER BY Total DESC
        LIMIT 10
    """
    return ejecutar_consulta(sql, (anio,))


def get_dashboard_ultimas_compras(limite: int = 10) -> pd.DataFrame:
    """Últimas compras para dashboard."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            "Fecha",
            TRIM("Articulo") AS Articulo,
            TRIM("Cliente / Proveedor") AS Proveedor,
            {total_expr} AS Total
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT %s
    """
    return ejecutar_consulta(sql, (limite,))


def get_total_compras_proveedor_moneda_periodos(periodos: List[str], monedas: List[str] = None) -> pd.DataFrame:
    """Total de compras por proveedor en múltiples períodos."""
    total_expr = _sql_total_num_expr_general()
    periodos_sql = ", ".join(["%s"] * len(periodos))
    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Mes") AS Mes,
            "Moneda",
            SUM({total_expr}) AS Total
        FROM chatbot_raw
        WHERE TRIM("Mes") IN ({periodos_sql})
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        GROUP BY TRIM("Cliente / Proveedor"), TRIM("Mes"), "Moneda"
        ORDER BY TRIM("Mes"), Total DESC
    """
    return ejecutar_consulta(sql, tuple(periodos))
