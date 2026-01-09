# =========================
# SQL_FACTURAS.PY - CONSULTAS DE FACTURAS
# =========================

import re
import pandas as pd
from typing import List, Optional, Any, Dict
from sql_core import (
    ejecutar_consulta,
    _sql_total_num_expr,
    _sql_total_num_expr_usd,
    _sql_total_num_expr_general,
)

# =====================================================================
# CONSTANTE: MISMA LÓGICA QUE TU SQL MANUAL
# (incluye Compra Crédito, Compra Contado, etc.)
# =====================================================================

_SQL_WHERE_TIPO_COMPRA = '(TRIM("Tipo Comprobante") = \'Compra Contado\' OR TRIM("Tipo Comprobante") ILIKE \'Compra%\' OR TRIM("Tipo Comprobante") ILIKE \'Factura%\')'


# =====================================================================
# HELPERS DE NORMALIZACIÓN DE FACTURA
# =====================================================================

def _factura_variantes(nro_factura: str) -> List[str]:
    """
    Genera variantes de números de factura:
    - "275015" -> ["275015", "A00275015", "00275015"]
    - "A00275015" -> ["A00275015", "00275015", "275015"]
    """
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


# =====================================================================
# DETALLE DE FACTURA POR NÚMERO
# =====================================================================

def get_detalle_factura_por_numero(nro_factura: str) -> pd.DataFrame:
    """Detalle completo de una factura por número (con fallback de variantes)."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            TRIM("Nro. Comprobante") AS nro_factura,
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            "Fecha",
            "Cantidad",
            "Precio Unitario",
            "Moneda",
            "Monto Neto",
            {total_expr} AS Total
        FROM chatbot_raw
        WHERE TRIM("Nro. Comprobante") = %s
          AND TRIM("Nro. Comprobante") <> 'A0000000'
          AND {_SQL_WHERE_TIPO_COMPRA}
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


def get_total_factura_por_numero(nro_factura: str) -> Dict[str, Any]:
    """Total de una factura (devuelve dict para uso directo)."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT 
            COALESCE(SUM({total_expr}), 0) AS total_factura,
            COUNT(*) AS lineas,
            TRIM("Moneda") AS Moneda
        FROM chatbot_raw
        WHERE TRIM("Nro. Comprobante") = %s
          AND {_SQL_WHERE_TIPO_COMPRA}
        GROUP BY TRIM("Moneda")
    """

    variantes = _factura_variantes(nro_factura)
    if not variantes:
        return {"total": 0, "lineas": 0, "moneda": ""}

    df = ejecutar_consulta(sql, (variantes[0],))
    if df is None or df.empty:
        for alt in variantes[1:]:
            df2 = ejecutar_consulta(sql, (alt,))
            if df2 is not None and not df2.empty:
                df = df2
                break

    if df is not None and not df.empty:
        return {
            "total": float(df["total_factura"].iloc[0] or 0),
            "lineas": int(df["lineas"].iloc[0] or 0),
            "moneda": str(df["Moneda"].iloc[0] or "")
        }

    return {"total": 0, "lineas": 0, "moneda": ""}


# =====================================================================
# FACTURAS POR PROVEEDOR (MISMA LÓGICA QUE TU SQL MANUAL)
# =====================================================================

def get_facturas_proveedor(
    proveedores: List[str],
    meses: Optional[List[str]] = None,
    anios: Optional[List[int]] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    articulo: Optional[str] = None,
    moneda: Optional[str] = None,
    limite: int = 5000,
) -> pd.DataFrame:
    """
    Lista facturas (que en tu DB están como compras) por proveedor.
    Mismo WHERE que tu SQL manual:
      - Tipo Comprobante = 'Compra Contado' OR ILIKE 'Compra%' OR ILIKE 'Factura%'
      - Agrupado por factura, con total sumado
    """
    if not proveedores:
        return pd.DataFrame()

    limite = int(limite or 5000)
    if limite <= 0:
        limite = 5000

    where_parts = [_SQL_WHERE_TIPO_COMPRA]
    params: List[Any] = []

    # Proveedores (OR)
    prov_clauses: List[str] = []
    for p in [str(x).strip() for x in proveedores if str(x).strip()]:
        p_clean = p.lower().strip()
        prov_clauses.append('LOWER(TRIM("Cliente / Proveedor")) LIKE %s')
        params.append(f"%{p_clean}%")
    where_parts.append("(" + " OR ".join(prov_clauses) + ")")

    # Artículo (opcional)
    if articulo and str(articulo).strip():
        where_parts.append('LOWER(TRIM("Articulo")) LIKE %s')
        params.append(f"%{str(articulo).lower().strip()}%")

    # Moneda (opcional)
    if moneda and str(moneda).strip():
        m = str(moneda).strip().upper()
        if m in ("USD", "U$S", "U$$", "US$"):
            where_parts.append('TRIM("Moneda") IN (\'U$S\', \'U$$\', \'USD\', \'US$\')')
        elif m in ("$", "PESOS", "UYU", "URU"):
            where_parts.append('TRIM("Moneda") = \'$\'')
        else:
            where_parts.append('UPPER(TRIM("Moneda")) LIKE %s')
            params.append(f"%{m}%")

    # Tiempo (prioridad: rango exacto)
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
                if len(anios_ok) == 1:
                    where_parts.append('"Año"::int = %s')
                    params.append(anios_ok[0])
                else:
                    ph = ", ".join(["%s"] * len(anios_ok))
                    where_parts.append(f'"Año"::int IN ({ph})')
                    params.extend(anios_ok)

    total_expr = _sql_total_num_expr_general()

    # Query agrupada por factura, como el SQL de Supabase
    query = f"""
        SELECT
            ROW_NUMBER() OVER (ORDER BY "Fecha"::date, "Nro. Comprobante") AS nro,
            TRIM("Cliente / Proveedor") AS Proveedor,
            "Fecha",
            TRIM("Tipo Comprobante") AS TipoComprobante,
            TRIM("Nro. Comprobante") AS NroFactura,
            "Moneda",
            SUM({total_expr}) AS Total
        FROM chatbot_raw
        WHERE {" AND ".join(where_parts)}
        GROUP BY
            TRIM("Cliente / Proveedor"),
            "Fecha",
            "Tipo Comprobante",
            "Nro. Comprobante",
            "Moneda"
        ORDER BY nro
        LIMIT {limite};
    """

    return ejecutar_consulta(query, tuple(params))


def get_total_facturas_proveedor(
    proveedores: List[str],
    meses: Optional[List[str]] = None,
    anios: Optional[List[int]] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    articulo: Optional[str] = None,
    moneda: Optional[str] = None,
) -> dict:
    """Totales por proveedor(es)."""
    if not proveedores:
        return {"registros": 0, "total_pesos": 0, "total_usd": 0, "facturas": 0}

    where_parts = [_SQL_WHERE_TIPO_COMPRA]
    params: List[Any] = []

    prov_clauses: List[str] = []
    for p in [str(x).strip() for x in proveedores if str(x).strip()]:
        p_lower = p.lower().strip()
        prov_clauses.append('LOWER(TRIM("Cliente / Proveedor")) LIKE %s')
        params.append(f"%{p_lower}%")
    where_parts.append("(" + " OR ".join(prov_clauses) + ")")

    if articulo and str(articulo).strip():
        where_parts.append('LOWER(TRIM("Articulo")) LIKE %s')
        params.append(f"%{str(articulo).lower().strip()}%")

    if moneda and str(moneda).strip():
        m = str(moneda).strip().upper()
        if m in ("USD", "U$S", "U$$", "US$"):
            where_parts.append('TRIM("Moneda") IN (\'U$S\', \'U$$\', \'USD\', \'US$\')')
        elif m in ("$", "PESOS", "UYU", "URU"):
            where_parts.append('TRIM("Moneda") = \'$\'')

    if desde and hasta:
        where_parts.append('"Fecha"::date BETWEEN %s AND %s')
        params.extend([desde, hasta])
    else:
        if meses:
            meses_ok = [m for m in (meses or []) if m]
            if meses_ok:
                ph = ", ".join(["%s"] * len(meses_ok))
                where_parts.append(f'TRIM("Mes") IN ({ph})')
                params.extend(meses_ok)

        if (not meses) and anios:
            anios_ok = [int(a) for a in (anios or []) if a]
            if anios_ok:
                if len(anios_ok) == 1:
                    where_parts.append('"Año"::int = %s')
                    params.append(anios_ok[0])
                else:
                    ph = ", ".join(["%s"] * len(anios_ok))
                    where_parts.append(f'"Año"::int IN ({ph})')
                    params.extend(anios_ok)

    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()

    sql = f"""
        SELECT
            COUNT(*) AS registros,
            COUNT(DISTINCT TRIM("Nro. Comprobante")) AS facturas,
            COALESCE(SUM(CASE WHEN TRIM("Moneda") = '$' THEN {total_pesos} ELSE 0 END), 0) AS total_pesos,
            COALESCE(SUM(CASE WHEN TRIM("Moneda") IN ('U$S', 'U$$', 'USD', 'US$') THEN {total_usd} ELSE 0 END), 0) AS total_usd
        FROM chatbot_raw
        WHERE {" AND ".join(where_parts)}
    """

    df = ejecutar_consulta(sql, tuple(params))
    if df is not None and not df.empty:
        return {
            "registros": int(df["registros"].iloc[0] or 0),
            "facturas": int(df["facturas"].iloc[0] or 0),
            "total_pesos": float(df["total_pesos"].iloc[0] or 0),
            "total_usd": float(df["total_usd"].iloc[0] or 0),
        }

    return {"registros": 0, "facturas": 0, "total_pesos": 0, "total_usd": 0}


# =====================================================================
# ÚLTIMA FACTURA (POR ARTÍCULO O PROVEEDOR)
# =====================================================================

def get_ultima_factura_articulo(patron_articulo: str) -> pd.DataFrame:
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            "Cantidad",
            TRIM("Nro. Comprobante") AS NroFactura,
            "Moneda",
            "Monto Neto",
            {total_expr} AS Total,
            "Fecha"
        FROM chatbot_raw
        WHERE LOWER(TRIM("Articulo")) LIKE %s
          AND {_SQL_WHERE_TIPO_COMPRA}
        ORDER BY "Fecha" DESC
        LIMIT 1
    """
    return ejecutar_consulta(sql, (f"%{patron_articulo.lower()}%",))


def get_ultima_factura_proveedor(patron_proveedor: str) -> pd.DataFrame:
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            "Cantidad",
            TRIM("Nro. Comprobante") AS NroFactura,
            "Moneda",
            "Monto Neto",
            {total_expr} AS Total,
            "Fecha"
        FROM chatbot_raw
        WHERE LOWER(TRIM("Cliente / Proveedor")) LIKE %s
          AND {_SQL_WHERE_TIPO_COMPRA}
        ORDER BY "Fecha" DESC
        LIMIT 1
    """
    return ejecutar_consulta(sql, (f"%{patron_proveedor.lower()}%",))


def get_ultima_factura_inteligente(patron: str) -> pd.DataFrame:
    df = get_ultima_factura_articulo(patron)
    if df is not None and not df.empty:
        return df
    return get_ultima_factura_proveedor(patron)


# =====================================================================
# FACTURAS POR ARTÍCULO
# =====================================================================

def get_facturas_articulo(
    patron_articulo: str,
    solo_ultima: bool = False,
    limite: int = 50
) -> pd.DataFrame:
    total_expr = _sql_total_num_expr_general()
    limit_sql = "LIMIT 1" if solo_ultima else f"LIMIT {int(limite or 50)}"

    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            TRIM("Nro. Comprobante") AS NroFactura,
            "Fecha",
            "Cantidad",
            "Moneda",
            "Monto Neto",
            {total_expr} AS Total
        FROM chatbot_raw
        WHERE {_SQL_WHERE_TIPO_COMPRA}
          AND LOWER(TRIM("Articulo")) LIKE %s
        ORDER BY "Fecha" DESC
        {limit_sql}
    """
    return ejecutar_consulta(sql, (f"%{patron_articulo.lower()}%",))


# =====================================================================
# ALIASES COMPAT (para NO romper imports viejos)
# =====================================================================

# Algunas partes de tu app usan estos nombres
get_facturas_de_articulo = get_facturas_articulo
get_facturas_proveedor_detalle = get_facturas_proveedor
