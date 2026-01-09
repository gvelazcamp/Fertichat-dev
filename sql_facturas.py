# =========================
# SQL_FACTURAS.PY - CONSULTAS DE FACTURAS
# =========================

import re
import pandas as pd
from typing import List, Optional, Any
from sql_core import (
    ejecutar_consulta,
    _sql_total_num_expr,
    _sql_total_num_expr_usd,
    _sql_total_num_expr_general,
)


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
        # A + zfill(8)
        if len(s) <= 8:
            variantes.append("A" + s.zfill(8))
        # zfill(8) sin A
        if len(s) < 8:
            variantes.append(s.zfill(8))
    else:
        # separar prefijo letras + parte numérica
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

    # dedup preservando orden
    out: List[str] = []
    seen = set()
    for v in variantes:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


# =====================================================================
# EXPRESIÓN CANÓNICA: MONTO NETO A NUMERIC (misma lógica que tu SQL)
# =====================================================================

def _sql_monto_neto_num_expr() -> str:
    return """
        (
          CASE
            WHEN TRIM("Monto Neto") LIKE '(%'
              THEN -1 * REPLACE(
                         REPLACE(
                           REPLACE(TRIM("Monto Neto"), '(', ''),
                           ')', ''),
                         '.', ''),
                       ',', '.'
                 )::numeric
            ELSE REPLACE(
                   REPLACE(TRIM("Monto Neto"), '.', ''),
                   ',', '.'
                 )::numeric
          END
        )
    """


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
            {total_expr} AS Total
        FROM chatbot_raw
        WHERE TRIM("Nro. Comprobante") = %s
          AND TRIM("Nro. Comprobante") <> 'A0000000'
          AND (
            "Tipo Comprobante" = 'Compra Contado'
            OR "Tipo Comprobante" ILIKE 'Compra%%'
            OR "Tipo Comprobante" ILIKE 'Factura%%'
          )
        ORDER BY TRIM("Articulo")
    """

    variantes = _factura_variantes(nro_factura)
    if not variantes:
        return ejecutar_consulta(sql, ("",))

    # 1) intento exacto
    df = ejecutar_consulta(sql, (variantes[0],))
    if df is not None and not df.empty:
        return df

    # 2) fallback por variantes
    for alt in variantes[1:]:
        df2 = ejecutar_consulta(sql, (alt,))
        if df2 is not None and not df2.empty:
            df2.attrs["nro_factura_fallback"] = alt
            return df2

    return df if df is not None else pd.DataFrame()


def get_total_factura_por_numero(nro_factura: str) -> dict:
    """Total de una factura."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT 
            COALESCE(SUM({total_expr}), 0) AS total_factura,
            COUNT(*) AS lineas,
            TRIM("Moneda") AS Moneda
        FROM chatbot_raw
        WHERE TRIM("Nro. Comprobante") = %s
          AND (
            "Tipo Comprobante" = 'Compra Contado'
            OR "Tipo Comprobante" ILIKE 'Compra%%'
            OR "Tipo Comprobante" ILIKE 'Factura%%'
          )
        GROUP BY TRIM("Moneda")
    """

    variantes = _factura_variantes(nro_factura)
    if not variantes:
        return {"total": 0, "lineas": 0, "moneda": ""}

    df = ejecutar_consulta(sql, (variantes[0],))
    if df is None or df.empty:
        # fallback
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
# FACTURAS POR PROVEEDOR (MISMA LÓGICA QUE TU SQL DE SUPABASE)
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
    Lista facturas por proveedor(es) con la misma lógica que el SQL que probaste:
    - Tipo Comprobante: Compra Contado OR ILIKE 'Compra%' OR ILIKE 'Factura%'
    - Año: "Año" = %s (sin casts raros)
    - Proveedor: LOWER("Cliente / Proveedor") LIKE %s
    - Monto: SUM(conversión de "Monto Neto")
    - Agrupado por (Proveedor, Fecha, Tipo, Nro, Moneda)
    """

    if not proveedores:
        return pd.DataFrame()

    limite = int(limite or 5000)
    if limite <= 0:
        limite = 5000

    where_parts = [
        """
        (
          "Tipo Comprobante" = 'Compra Contado'
          OR "Tipo Comprobante" ILIKE 'Compra%'
          OR "Tipo Comprobante" ILIKE 'Factura%'
        )
        """.strip()
    ]
    params: List[Any] = []

    # Proveedores (OR)
    prov_clauses: List[str] = []
    for p in [str(x).strip() for x in proveedores if str(x).strip()]:
        p_clean = p.lower().strip()
        prov_clauses.append('LOWER(TRIM("Cliente / Proveedor")) LIKE %s')
        params.append(f"%{p_clean}%")
    where_parts.append("(" + " OR ".join(prov_clauses) + ")")

    # Filtro artículo (opcional)
    if articulo and str(articulo).strip():
        where_parts.append('LOWER(TRIM("Articulo")) LIKE %s')
        params.append(f"%{str(articulo).lower().strip()}%")

    # Filtro moneda (opcional) - sin inventar reglas nuevas
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
        # Meses (tu formato tipo 11-06 / 20-05 / etc lo respeta tal cual venga en "Mes")
        if meses:
            meses_ok = [m for m in (meses or []) if m]
            if meses_ok:
                ph = ", ".join(["%s"] * len(meses_ok))
                where_parts.append(f'TRIM("Mes") IN ({ph})')
                params.extend(meses_ok)

        # Años (si NO hay meses)
        if (not meses) and anios:
            anios_ok = [int(a) for a in (anios or []) if a]
            if anios_ok:
                if len(anios_ok) == 1:
                    where_parts.append('"Año" = %s')
                    params.append(anios_ok[0])
                else:
                    ph = ", ".join(["%s"] * len(anios_ok))
                    where_parts.append(f'"Año" IN ({ph})')
                    params.extend(anios_ok)

    monto_expr = _sql_monto_neto_num_expr()

    query = f"""
        SELECT
          ROW_NUMBER() OVER (ORDER BY "Fecha"::date, "Nro. Comprobante") AS nro,
          TRIM("Cliente / Proveedor") AS proveedor,
          "Fecha",
          "Tipo Comprobante",
          "Nro. Comprobante",
          "Moneda",
          SUM({monto_expr}) AS monto_neto
        FROM chatbot_raw
        WHERE {" AND ".join(where_parts)}
        GROUP BY
          TRIM("Cliente / Proveedor"),
          "Fecha",
          "Tipo Comprobante",
          "Nro. Comprobante",
          "Moneda"
        ORDER BY
          nro
        LIMIT {limite};
    """

    # ✅ DEBUG POTENTE
    print("\n" + "="*80)
    print("🔍 DEBUG SQL_FACTURAS - get_facturas_proveedor")
    print("="*80)
    print(f"📋 Proveedores buscados: {proveedores}")
    print(f"📅 Años: {anios}")
    print(f"📅 Meses: {meses}")
    print(f"💰 Moneda: {moneda}")
    print(f"🔢 Límite: {limite}")
    print("\n📝 SQL generado:")
    print(query)
    print("\n🎯 Parámetros:")
    print(tuple(params))
    print("="*80)

    # DEBUG: Verificar total filas en tabla
    try:
        df_test = ejecutar_consulta("SELECT COUNT(*) as total FROM chatbot_raw", ())
        total_filas = df_test.iloc[0]['total'] if (df_test is not None and not df_test.empty) else 0
        print(f"\n📊 Total filas en chatbot_raw: {total_filas}")
    except Exception as e:
        print(f"\n❌ Error contando filas totales: {e}")

    # DEBUG: Verificar si existe el proveedor
    if proveedores:
        try:
            prov_test = proveedores[0].lower()
            sql_prov = f"SELECT COUNT(*) as total FROM chatbot_raw WHERE LOWER(\"Cliente / Proveedor\") LIKE '%{prov_test}%'"
            df_prov = ejecutar_consulta(sql_prov, ())
            total_prov = df_prov.iloc[0]['total'] if (df_prov is not None and not df_prov.empty) else 0
            print(f"🏢 Registros con proveedor '{proveedores[0]}': {total_prov}")
        except Exception as e:
            print(f"❌ Error verificando proveedor: {e}")

    # DEBUG: Verificar si existe el año
    if anios:
        try:
            sql_anio = f"SELECT COUNT(*) as total FROM chatbot_raw WHERE \"Año\" = {anios[0]}"
            df_anio = ejecutar_consulta(sql_anio, ())
            total_anio = df_anio.iloc[0]['total'] if (df_anio is not None and not df_anio.empty) else 0
            print(f"📅 Registros en año {anios[0]}: {total_anio}")
        except Exception as e:
            print(f"❌ Error verificando año: {e}")

    # DEBUG: Verificar proveedor + año combinados
    if proveedores and anios:
        try:
            prov_test = proveedores[0].lower()
            sql_combo = f"SELECT COUNT(*) as total FROM chatbot_raw WHERE LOWER(\"Cliente / Proveedor\") LIKE '%{prov_test}%' AND \"Año\" = {anios[0]}"
            df_combo = ejecutar_consulta(sql_combo, ())
            total_combo = df_combo.iloc[0]['total'] if (df_combo is not None and not df_combo.empty) else 0
            print(f"🎯 Registros con '{proveedores[0]}' en {anios[0]}: {total_combo}")
        except Exception as e:
            print(f"❌ Error verificando combo: {e}")

    print("\n🚀 Ejecutando consulta principal...")
    print("="*80 + "\n")

    # Ejecutar consulta
    df = ejecutar_consulta(query, tuple(params))

    # DEBUG resultado
    if df is not None and not df.empty:
        print(f"✅ Consulta exitosa: {len(df)} filas obtenidas\n")
    else:
        print(f"⚠️ Consulta NO trajo resultados\n")

    return df


def get_total_facturas_proveedor(
    proveedores: List[str],
    meses: Optional[List[str]] = None,
    anios: Optional[List[int]] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    articulo: Optional[str] = None,
    moneda: Optional[str] = None,
) -> dict:
    """
    Totales por proveedor(es) usando la misma conversión de Monto Neto.
    """
    if not proveedores:
        return {"registros": 0, "total_pesos": 0, "total_usd": 0, "facturas": 0}

    where_parts = [
        """
        (
          "Tipo Comprobante" = 'Compra Contado'
          OR "Tipo Comprobante" ILIKE 'Compra%'
          OR "Tipo Comprobante" ILIKE 'Factura%'
        )
        """.strip()
    ]
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
                    where_parts.append('"Año" = %s')
                    params.append(anios_ok[0])
                else:
                    ph = ", ".join(["%s"] * len(anios_ok))
                    where_parts.append(f'"Año" IN ({ph})')
                    params.extend(anios_ok)

    monto_expr = _sql_monto_neto_num_expr()

    sql = f"""
        SELECT
            COUNT(*) AS registros,
            COUNT(DISTINCT TRIM("Nro. Comprobante")) AS facturas,
            COALESCE(SUM(CASE WHEN TRIM("Moneda") = '$' THEN {monto_expr} ELSE 0 END), 0) AS total_pesos,
            COALESCE(SUM(CASE WHEN TRIM("Moneda") IN ('U$S', 'U$$', 'USD', 'US$') THEN {monto_expr} ELSE 0 END), 0) AS total_usd
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
    """Última factura de un artículo."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            "Cantidad",
            TRIM("Nro. Comprobante") AS NroFactura,
            "Moneda",
            {total_expr} AS Total,
            "Fecha"
        FROM chatbot_raw
        WHERE LOWER(TRIM("Articulo")) LIKE %s
          AND (
            "Tipo Comprobante" = 'Compra Contado'
            OR "Tipo Comprobante" ILIKE 'Compra%%'
            OR "Tipo Comprobante" ILIKE 'Factura%%'
          )
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT 1
    """
    return ejecutar_consulta(sql, (f"%{patron_articulo.lower()}%",))


def get_ultima_factura_proveedor(patron_proveedor: str) -> pd.DataFrame:
    """Última factura de un proveedor."""
    total_expr = _sql_total_num_expr_general()
    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            "Cantidad",
            TRIM("Nro. Comprobante") AS NroFactura,
            "Moneda",
            {total_expr} AS Total,
            "Fecha"
        FROM chatbot_raw
        WHERE LOWER(TRIM("Cliente / Proveedor")) LIKE %s
          AND (
            "Tipo Comprobante" = 'Compra Contado'
            OR "Tipo Comprobante" ILIKE 'Compra%%'
            OR "Tipo Comprobante" ILIKE 'Factura%%'
          )
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT 1
    """
    return ejecutar_consulta(sql, (f"%{patron_proveedor.lower()}%",))


def get_ultima_factura_inteligente(patron: str) -> pd.DataFrame:
    """Busca última factura por artículo O proveedor (inteligente)."""
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
    """Lista de facturas de un artículo."""
    total_expr = _sql_total_num_expr_general()
    limit_sql = "LIMIT 1" if solo_ultima else f"LIMIT {limite}"

    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            TRIM("Nro. Comprobante") AS NroFactura,
            "Fecha",
            "Cantidad",
            "Moneda",
            {total_expr} AS Total
        FROM chatbot_raw
        WHERE (
            "Tipo Comprobante" = 'Compra Contado'
            OR "Tipo Comprobante" ILIKE 'Compra%%'
            OR "Tipo Comprobante" ILIKE 'Factura%%'
        )
          AND LOWER(TRIM("Articulo")) LIKE %s
        ORDER BY "Fecha" DESC NULLS LAST
        {limit_sql}
    """
    return ejecutar_consulta(sql, (f"%{patron_articulo.lower()}%",))


# =====================================================================
# RESUMEN DE FACTURAS (AGRUPADO)
# =====================================================================

def get_resumen_facturas_por_proveedor(
    meses: Optional[List[str]] = None,
    anios: Optional[List[int]] = None,
    moneda: Optional[str] = None,
) -> pd.DataFrame:
    """
    Resumen agrupado: total por proveedor + cantidad de facturas.
    """
    where_parts = [
        """
        (
          "Tipo Comprobante" = 'Compra Contado'
          OR "Tipo Comprobante" ILIKE 'Compra%'
          OR "Tipo Comprobante" ILIKE 'Factura%'
        )
        """.strip()
    ]
    params: List[Any] = []

    if moneda and str(moneda).strip():
        m = str(moneda).strip().upper()
        if m in ("USD", "U$S", "U$$", "US$"):
            where_parts.append('TRIM("Moneda") IN (\'U$S\', \'U$$\', \'USD\', \'US$\')')
        elif m in ("$", "PESOS", "UYU", "URU"):
            where_parts.append('TRIM("Moneda") = \'$\'')

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
                where_parts.append('"Año" = %s')
                params.append(anios_ok[0])
            else:
                ph = ", ".join(["%s"] * len(anios_ok))
                where_parts.append(f'"Año" IN ({ph})')
                params.extend(anios_ok)

    monto_expr = _sql_monto_neto_num_expr()

    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            COUNT(DISTINCT TRIM("Nro. Comprobante")) AS CantidadFacturas,
            COUNT(*) AS Lineas,
            SUM({monto_expr}) AS Total
        FROM chatbot_raw
        WHERE {" AND ".join(where_parts)}
          AND "Cliente / Proveedor" IS NOT NULL
          AND TRIM("Cliente / Proveedor") <> ''
        GROUP BY TRIM("Cliente / Proveedor")
        ORDER BY Total DESC
        LIMIT 50
    """

    return ejecutar_consulta(sql, tuple(params) if params else None)


# =====================================================================
# BÚSQUEDA DE FACTURAS POR RANGO DE MONTOS
# =====================================================================

def get_facturas_por_rango_monto(
    monto_min: float,
    monto_max: float,
    proveedores: Optional[List[str]] = None,
    meses: Optional[List[str]] = None,
    anios: Optional[List[int]] = None,
    moneda: Optional[str] = None,
    limite: int = 100
) -> pd.DataFrame:
    """
    Busca facturas dentro de un rango de montos.
    """
    where_parts = [
        """
        (
          "Tipo Comprobante" = 'Compra Contado'
          OR "Tipo Comprobante" ILIKE 'Compra%'
          OR "Tipo Comprobante" ILIKE 'Factura%'
        )
        """.strip()
    ]
    params: List[Any] = []

    if proveedores:
        prov_clauses = []
        for p in proveedores:
            prov_clauses.append('LOWER(TRIM("Cliente / Proveedor")) LIKE %s')
            params.append(f"%{str(p).lower().strip()}%")
        where_parts.append("(" + " OR ".join(prov_clauses) + ")")

    if moneda:
        m = str(moneda).strip().upper()
        if m in ("USD", "U$S", "U$$", "US$"):
            where_parts.append('TRIM("Moneda") IN (\'U$S\', \'U$$\', \'USD\', \'US$\')')
        elif m in ("$", "PESOS", "UYU", "URU"):
            where_parts.append('TRIM("Moneda") = \'$\'')

    if meses:
        ph = ", ".join(["%s"] * len(meses))
        where_parts.append(f'TRIM("Mes") IN ({ph})')
        params.extend(meses)

    if (not meses) and anios:
        anios_ok = [int(a) for a in (anios or []) if a]
        if anios_ok:
            if len(anios_ok) == 1:
                where_parts.append('"Año" = %s')
                params.append(anios_ok[0])
            else:
                ph = ", ".join(["%s"] * len(anios_ok))
                where_parts.append(f'"Año" IN ({ph})')
                params.extend(anios_ok)

    monto_expr = _sql_monto_neto_num_expr()

    sql = f"""
        SELECT
            TRIM("Nro. Comprobante") AS NroFactura,
            TRIM("Cliente / Proveedor") AS Proveedor,
            "Fecha",
            "Moneda",
            SUM({monto_expr}) AS Total
        FROM chatbot_raw
        WHERE {" AND ".join(where_parts)}
        GROUP BY TRIM("Nro. Comprobante"), TRIM("Cliente / Proveedor"), "Fecha", "Moneda"
        HAVING SUM({monto_expr}) BETWEEN %s AND %s
        ORDER BY "Fecha" DESC
        LIMIT {limite}
    """

    params.extend([monto_min, monto_max])
    return ejecutar_consulta(sql, tuple(params))
