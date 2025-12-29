# =========================
# SQL QUERIES - SOLO CONSULTAS (POSTGRES / SUPABASE)
# =========================
import os
import re
import time
import psycopg2
import pandas as pd
from typing import List, Tuple, Optional, Dict
from datetime import datetime
from psycopg2.extras import RealDictCursor
import streamlit as st

# =====================================================================
# CONEXIÓN DB (SUPABASE / POSTGRES)
# =====================================================================

def get_db_connection():
    """Conexión a Postgres (Supabase) usando Secrets/Env vars."""
    try:
        host = st.secrets.get("DB_HOST", os.getenv("DB_HOST"))
        port = st.secrets.get("DB_PORT", os.getenv("DB_PORT", "5432"))
        dbname = st.secrets.get("DB_NAME", os.getenv("DB_NAME", "postgres"))
        user = st.secrets.get("DB_USER", os.getenv("DB_USER"))
        password = st.secrets.get("DB_PASSWORD", os.getenv("DB_PASSWORD"))

        if not host or not user or not password:
            return None

        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            sslmode="require"
        )
        return conn
        
    except Exception as e:
        print(f"Error de conexión: {e}")
        return None


# =====================================================================
# TABLAS + COLUMNAS REALES
# =====================================================================

TABLE_COMPRAS = "chatbot_raw"

COL_TIPO_COMP = '"Tipo Comprobante"'
COL_NRO_COMP  = '"Nro. Comprobante"'
COL_MONEDA    = '"Moneda"'
COL_PROV      = '"Cliente / Proveedor"'
COL_FAMILIA   = '"Familia"'
COL_ART       = '"Articulo"'
COL_ANIO      = '"Año"'
COL_MES       = '"Mes"'
COL_FECHA     = '"Fecha"'
COL_CANT      = '"Cantidad"'
COL_MONTO     = '"Monto Neto"'


# =====================================================================
# HELPERS SQL (POSTGRES)
# =====================================================================

def _sql_fecha_expr() -> str:
    return f'"Fecha"'


def _sql_mes_col() -> str:
    return f'TRIM(COALESCE("Mes", \'\'))'


def _sql_moneda_norm_expr() -> str:
    return f'TRIM(COALESCE("Moneda", \'\'))'


def _sql_num_from_text(text_expr: str) -> str:
    return f"CAST(NULLIF(TRIM({text_expr}), '') AS NUMERIC(15,2))"


def _sql_total_num_expr() -> str:
    """Convierte Monto Neto a número (pesos)."""
    limpio = f"""
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(TRIM(COALESCE("Monto Neto", '')), '.', ''),
                        ',', '.'
                    ),
                    '(', '-'
                ),
                ')', ''
            ),
            '$', ''
        )
    """
    return _sql_num_from_text(limpio)


def _sql_total_num_expr_usd() -> str:
    """Convierte Monto Neto a número (USD)."""
    limpio = f"""
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(TRIM(COALESCE("Monto Neto", '')), 'U$S', ''),
                                'U$$', ''
                            ),
                            '$', ''
                        ),
                        '.', ''
                    ),
                    ',', '.'
                ),
                '(', '-'
            ),
            ')', ''
        )
    """
    return _sql_num_from_text(limpio)


def _sql_total_num_expr_general() -> str:
    """Convierte Monto Neto a número (sirve para $ o U$S)."""
    limpio = f"""
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(
                                    REPLACE(TRIM(COALESCE("Monto Neto", '')), 'U$S', ''),
                                    'U$$', ''
                                ),
                                '$', ''
                            ),
                            '.', ''
                        ),
                        ',', '.'
                    ),
                    '(', '-'
                ),
                ')', ''
            ),
            ' ', ''
        )
    """
    return _sql_num_from_text(limpio)


# =====================================================================
# EJECUTOR SQL
# =====================================================================

def ejecutar_consulta(query: str, params: tuple = None) -> pd.DataFrame:
    """Ejecuta consulta SQL y retorna DataFrame."""
    try:
        conn = get_db_connection()
        if not conn:
            return pd.DataFrame()

        if params is None:
            params = ()

        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    except Exception as e:
        print(f"Error en consulta SQL: {e}")
        return pd.DataFrame()


# =====================================================================
# LISTADOS
# =====================================================================

def get_lista_proveedores() -> list:
    sql = """
        SELECT DISTINCT TRIM("Cliente / Proveedor") AS proveedor
        FROM chatbot_raw
        WHERE "Cliente / Proveedor" IS NOT NULL AND TRIM("Cliente / Proveedor") <> ''
        ORDER BY proveedor
        LIMIT 500
    """
    df = ejecutar_consulta(sql)
    if df.empty:
        return ["Todos"]
    return ["Todos"] + df['proveedor'].tolist()


def get_lista_tipos_comprobante() -> list:
    sql = """
        SELECT DISTINCT TRIM("Tipo Comprobante") AS tipo
        FROM chatbot_raw
        WHERE "Tipo Comprobante" IS NOT NULL AND TRIM("Tipo Comprobante") <> ''
        ORDER BY tipo
    """
    df = ejecutar_consulta(sql)
    if df.empty:
        return ["Todos"]
    return ["Todos"] + df['tipo'].tolist()


def get_lista_articulos() -> list:
    sql = """
        SELECT DISTINCT TRIM("Articulo") AS articulo
        FROM chatbot_raw
        WHERE "Articulo" IS NOT NULL AND TRIM("Articulo") <> ''
        ORDER BY articulo
        LIMIT 500
    """
    df = ejecutar_consulta(sql)
    if df.empty:
        return ["Todos"]
    return ["Todos"] + df['articulo'].tolist()


def get_valores_unicos() -> dict:
    return {
        "proveedores": get_lista_proveedores()[1:],
        "familias": [],
        "articulos": get_lista_articulos()[1:]
    }


# =====================================================================
# DETALLE COMPRAS: PROVEEDOR + MES
# =====================================================================

def get_detalle_compras_proveedor_mes(proveedor_like: str, mes_key: str) -> pd.DataFrame:
    """Detalle de compras de un proveedor en un mes específico."""
    
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
        WHERE LOWER("Cliente / Proveedor") LIKE %s
          AND "Mes" = %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT 200
    """
    
    return ejecutar_consulta(sql, (f"%{proveedor_like}%", mes_key))


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
        LIMIT 200
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
        LIMIT 200
    """
    
    return ejecutar_consulta(sql, (f"%{articulo_like}%", mes_key))


# =====================================================================
# DETALLE COMPRAS: ARTÍCULO + AÑO
# =====================================================================

def get_detalle_compras_articulo_anio(articulo_like: str, anio: int, limite: int = 200) -> pd.DataFrame:
    """Detalle de compras de un artículo en un año."""
    
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
          AND LOWER(TRIM("Articulo")) LIKE %s
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT {int(limite)}
    """
    return ejecutar_consulta(sql, (anio, f"%{articulo_like.lower()}%"))


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
    return ejecutar_consulta(sql, (nro_factura,))


def get_total_factura_por_numero(nro_factura: str) -> pd.DataFrame:
    """Total de una factura."""
    
    total_expr = _sql_total_num_expr_general()
    
    sql = f"""
        SELECT COALESCE(SUM({total_expr}), 0) AS total_factura
        FROM chatbot_raw
        WHERE TRIM("Nro. Comprobante") = %s
    """
    return ejecutar_consulta(sql, (nro_factura,))


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
    
    # Primero como artículo
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
    
    # Si no encontró, buscar como proveedor
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


# =====================================================================
# COMPARACIONES POR MESES
# =====================================================================

def get_comparacion_proveedor_meses(mes1: str, mes2: str, label1: str, label2: str, proveedores: List[str] = None) -> pd.DataFrame:
    """Compara proveedores entre dos meses."""
    
    total_expr = _sql_total_num_expr_general()

    prov_where = ""
    prov_params = []
    if proveedores:
        parts = [f"LOWER(TRIM(\"Cliente / Proveedor\")) LIKE %s" for _ in proveedores]
        prov_params = [f"%{p.lower()}%" for p in proveedores]
        prov_where = f"AND ({' OR '.join(parts)})"

    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Concepto,
            SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) AS "{label1}",
            SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) AS "{label2}",
            SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) -
            SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) AS Diferencia
        FROM chatbot_raw
        WHERE TRIM("Mes") IN (%s, %s)
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          {prov_where}
        GROUP BY TRIM("Cliente / Proveedor")
        HAVING SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) > 0
            OR SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) > 0
        ORDER BY Diferencia DESC
    """

    params = (mes1, mes2, mes2, mes1, mes1, mes2, *prov_params, mes1, mes2)
    return ejecutar_consulta(sql, params)


def get_comparacion_articulo_meses(mes1: str, mes2: str, label1: str, label2: str, articulos: List[str] = None) -> pd.DataFrame:
    """Compara artículos entre dos meses."""
    
    total_expr = _sql_total_num_expr_general()

    art_where = ""
    art_params = []
    if articulos:
        parts = [f"LOWER(TRIM(\"Articulo\")) LIKE %s" for _ in articulos]
        art_params = [f"%{a.lower()}%" for a in articulos]
        art_where = f"AND ({' OR '.join(parts)})"

    sql = f"""
        SELECT
            TRIM("Articulo") AS Concepto,
            SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) AS "{label1}",
            SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) AS "{label2}",
            SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) -
            SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) AS Diferencia
        FROM chatbot_raw
        WHERE TRIM("Mes") IN (%s, %s)
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          {art_where}
        GROUP BY TRIM("Articulo")
        HAVING SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) > 0
            OR SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) > 0
        ORDER BY Diferencia DESC
        LIMIT 200
    """

    params = (mes1, mes2, mes2, mes1, mes1, mes2, *art_params, mes1, mes2)
    return ejecutar_consulta(sql, params)


def get_comparacion_familia_meses_moneda(mes1: str, mes2: str, label1: str, label2: str, moneda: str = "$", familias: List[str] = None) -> pd.DataFrame:
    """Compara familias entre dos meses filtrado por moneda."""
    
    mon = (moneda or "$").strip().upper()
    if mon in ("U$S", "U$$", "USD"):
        total_expr = _sql_total_num_expr_usd()
        mon_filter = "TRIM(\"Moneda\") IN ('U$S', 'U$$')"
    else:
        total_expr = _sql_total_num_expr()
        mon_filter = "TRIM(\"Moneda\") = '$'"

    fam_where = ""
    fam_params = []
    if familias:
        parts = [f"TRIM(COALESCE(\"Familia\", '')) = %s" for _ in familias]
        fam_params = list(familias)
        fam_where = f"AND ({' OR '.join(parts)})"

    sql = f"""
        SELECT
            TRIM(COALESCE("Familia", 'SIN FAMILIA')) AS Familia,
            SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) AS "{label1}",
            SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) AS "{label2}",
            SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) -
            SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) AS Diferencia
        FROM chatbot_raw
        WHERE TRIM("Mes") IN (%s, %s)
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND {mon_filter}
          {fam_where}
        GROUP BY TRIM(COALESCE("Familia", 'SIN FAMILIA'))
        HAVING SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) > 0
            OR SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) > 0
        ORDER BY Diferencia DESC
    """

    params = (mes1, mes2, mes2, mes1, mes1, mes2, *fam_params, mes1, mes2)
    return ejecutar_consulta(sql, params)


# =====================================================================
# COMPARACIONES POR AÑOS
# =====================================================================

def get_comparacion_articulo_anios(anios: List[int], articulo_like: str) -> pd.DataFrame:
    """Compara un artículo específico entre años."""
    
    total_expr = _sql_total_num_expr_general()
    anios = sorted(anios)

    cols = []
    for y in anios:
        cols.append(f"""SUM(CASE WHEN "Año"::int = {y} THEN {total_expr} ELSE 0 END) AS "{y}" """)

    cols_sql = ",\n            ".join(cols)
    anios_sql = ", ".join(str(y) for y in anios)

    sql = f"""
        SELECT
            TRIM("Articulo") AS Articulo,
            {cols_sql}
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año"::int IN ({anios_sql})
          AND LOWER(TRIM("Articulo")) LIKE %s
        GROUP BY TRIM("Articulo")
        ORDER BY TRIM("Articulo")
        LIMIT 100
    """

    return ejecutar_consulta(sql, (f"%{articulo_like.lower()}%",))


def get_comparacion_proveedor_anios_monedas(anios: List[int], proveedores: List[str] = None) -> pd.DataFrame:
    """Compara proveedores por años con separación de monedas."""
    
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()
    anios = sorted(anios)

    prov_where = ""
    prov_params = []
    if proveedores:
        parts = [f"LOWER(TRIM(\"Cliente / Proveedor\")) LIKE %s" for _ in proveedores]
        prov_params = [f"%{p.lower()}%" for p in proveedores]
        prov_where = f"AND ({' OR '.join(parts)})"

    cols = []
    for y in anios:
        cols.append(f"""SUM(CASE WHEN "Año"::int = {y} AND TRIM("Moneda") = '$' THEN {total_pesos} ELSE 0 END) AS "{y}_$" """)
        cols.append(f"""SUM(CASE WHEN "Año"::int = {y} AND TRIM("Moneda") IN ('U$S','U$$') THEN {total_usd} ELSE 0 END) AS "{y}_USD" """)

    cols_sql = ",\n            ".join(cols)
    y_last = anios[-1]
    order_sql = f'"{y_last}_$" DESC, "{y_last}_USD" DESC'
    anios_sql = ", ".join(str(y) for y in anios)

    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            {cols_sql}
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año"::int IN ({anios_sql})
          {prov_where}
        GROUP BY TRIM("Cliente / Proveedor")
        ORDER BY {order_sql}
        LIMIT 300
    """

    return ejecutar_consulta(sql, tuple(prov_params) if prov_params else None)


def get_comparacion_familia_anios_monedas(anios: List[int], familias: List[str] = None) -> pd.DataFrame:
    """Compara familias por años con separación de monedas."""
    
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()
    anios = sorted(anios)

    fam_where = ""
    fam_params = []
    if familias:
        parts = [f"TRIM(COALESCE(\"Familia\", '')) = %s" for _ in familias]
        fam_params = list(familias)
        fam_where = f"AND ({' OR '.join(parts)})"

    cols = []
    for y in anios:
        cols.append(f"""SUM(CASE WHEN "Año"::int = {y} AND TRIM("Moneda") = '$' THEN {total_pesos} ELSE 0 END) AS "{y}_$" """)
        cols.append(f"""SUM(CASE WHEN "Año"::int = {y} AND TRIM("Moneda") IN ('U$S','U$$') THEN {total_usd} ELSE 0 END) AS "{y}_USD" """)

    cols_sql = ",\n            ".join(cols)
    y_last = anios[-1]
    order_sql = f'"{y_last}_$" DESC, "{y_last}_USD" DESC'
    anios_sql = ", ".join(str(y) for y in anios)

    sql = f"""
        SELECT
            TRIM(COALESCE("Familia", 'SIN FAMILIA')) AS Familia,
            {cols_sql}
        FROM chatbot_raw
        WHERE ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año"::int IN ({anios_sql})
          {fam_where}
        GROUP BY TRIM(COALESCE("Familia", 'SIN FAMILIA'))
        ORDER BY {order_sql}
        LIMIT 300
    """

    return ejecutar_consulta(sql, tuple(fam_params) if fam_params else None)


# =====================================================================
# GASTOS POR FAMILIAS
# =====================================================================

def get_gastos_todas_familias_mes(mes_key: str) -> pd.DataFrame:
    """Gastos de todas las familias en un mes."""
    
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()
    
    sql = f"""
        SELECT
            TRIM(COALESCE("Familia", 'SIN FAMILIA')) AS Familia,
            SUM(CASE WHEN TRIM("Moneda") = '$' THEN {total_pesos} ELSE 0 END) AS Total_Pesos,
            SUM(CASE WHEN TRIM("Moneda") IN ('U$S', 'U$$') THEN {total_usd} ELSE 0 END) AS Total_USD
        FROM chatbot_raw
        WHERE TRIM("Mes") = %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        GROUP BY TRIM(COALESCE("Familia", 'SIN FAMILIA'))
        ORDER BY Total_Pesos DESC, Total_USD DESC
    """
    
    return ejecutar_consulta(sql, (mes_key,))


def get_gastos_todas_familias_anio(anio: int) -> pd.DataFrame:
    """Gastos de todas las familias en un año."""
    
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()
    
    sql = f"""
        SELECT
            TRIM(COALESCE("Familia", 'SIN FAMILIA')) AS Familia,
            SUM(CASE WHEN TRIM("Moneda") = '$' THEN {total_pesos} ELSE 0 END) AS Total_Pesos,
            SUM(CASE WHEN TRIM("Moneda") IN ('U$S', 'U$$') THEN {total_usd} ELSE 0 END) AS Total_USD
        FROM chatbot_raw
        WHERE "Año"::int = %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        GROUP BY TRIM(COALESCE("Familia", 'SIN FAMILIA'))
        ORDER BY Total_Pesos DESC, Total_USD DESC
    """
    
    return ejecutar_consulta(sql, (anio,))


def get_gastos_secciones_detalle_completo(familias: List[str], mes_key: str) -> pd.DataFrame:
    """Detalle de gastos de familias específicas en un mes."""
    
    total_expr = _sql_total_num_expr_general()
    
    fam_placeholders = ", ".join(["%s"] * len(familias))
    
    sql = f"""
        SELECT
            TRIM("Familia") AS Familia,
            TRIM("Articulo") AS Articulo,
            TRIM("Cliente / Proveedor") AS Proveedor,
            "Moneda",
            {total_expr} AS Total
        FROM chatbot_raw
        WHERE TRIM("Mes") = %s
          AND UPPER(TRIM(COALESCE("Familia", ''))) IN ({fam_placeholders})
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        ORDER BY TRIM("Familia"), Total DESC
    """
    
    params = [mes_key] + [f.upper() for f in familias]
    return ejecutar_consulta(sql, tuple(params))


def get_gastos_por_familia(where_clause: str, params: tuple) -> pd.DataFrame:
    """Gastos por familia con where personalizado."""
    
    total_expr = _sql_total_num_expr_general()
    
    sql = f"""
        SELECT
            TRIM(COALESCE("Familia", 'SIN FAMILIA')) AS Familia,
            SUM({total_expr}) AS Total
        FROM chatbot_raw
        WHERE {where_clause}
        GROUP BY TRIM(COALESCE("Familia", 'SIN FAMILIA'))
        ORDER BY Total DESC
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
        LIMIT 200
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


def get_alertas_vencimiento_multiple(limite: int = 10) -> list:
    """Placeholder para alertas de vencimiento."""
    return []


# =====================================================================
# STOCK PLACEHOLDERS
# =====================================================================

def get_lista_articulos_stock() -> list:
    return ["Todos"]

def get_lista_familias_stock() -> list:
    return ["Todos"]

def get_lista_depositos_stock() -> list:
    return ["Todos"]

def buscar_stock_por_lote(**kwargs) -> pd.DataFrame:
    return pd.DataFrame()

def get_stock_total() -> pd.DataFrame:
    return pd.DataFrame()

def get_stock_por_familia() -> pd.DataFrame:
    return pd.DataFrame()

def get_stock_por_deposito() -> pd.DataFrame:
    return pd.DataFrame()

def get_stock_articulo(articulo: str) -> pd.DataFrame:
    return pd.DataFrame()

def get_lotes_por_vencer(dias: int = 90) -> pd.DataFrame:
    return pd.DataFrame()

def get_lotes_vencidos() -> pd.DataFrame:
    return pd.DataFrame()

def get_stock_bajo(minimo: int = 10) -> pd.DataFrame:
    return pd.DataFrame()

def get_stock_lote_especifico(lote: str) -> pd.DataFrame:
    return pd.DataFrame()

def get_stock_familia(familia: str) -> pd.DataFrame:
    return pd.DataFrame()


# FIN DEL ARCHIVO
