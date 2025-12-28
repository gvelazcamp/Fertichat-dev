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
            sslmode="require",
            cursor_factory=RealDictCursor
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
COL_TIPO_CFE  = '"Tipo CFE"'
COL_NRO_COMP  = '"Nro. Comprobante"'
COL_MONEDA    = '"Moneda"'
COL_PROV      = '"Cliente / Proveedor"'
COL_FAMILIA   = '"Familia"'
COL_TIPO_ART  = '"Tipo Articulo"'
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
    """Convierte Fecha (texto) a DATE."""
    return f"""
        CASE 
            WHEN {COL_FECHA} ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN TO_DATE({COL_FECHA}, 'YYYY-MM-DD')
            WHEN {COL_FECHA} ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$' THEN TO_DATE({COL_FECHA}, 'DD/MM/YYYY')
            ELSE NULL
        END
    """


def _sql_mes_col() -> str:
    return f"TRIM(COALESCE({COL_MES}, ''))"


def _sql_moneda_norm_expr() -> str:
    return f"TRIM(COALESCE({COL_MONEDA}, ''))"


def _sql_year_expr() -> str:
    return f"COALESCE({COL_ANIO}::int, EXTRACT(YEAR FROM ({_sql_fecha_expr()}))::int)"


def _sql_num_from_text(text_expr: str) -> str:
    return f"CAST(NULLIF(TRIM({text_expr}), '') AS NUMERIC(15,2))"


def _sql_total_num_expr() -> str:
    """Convierte Monto Neto a número (pesos)."""
    limpio = f"""
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(TRIM(COALESCE({COL_MONTO}, '')), '.', ''),
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
                                REPLACE(TRIM(COALESCE({COL_MONTO}, '')), 'U$S', ''),
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
                                    REPLACE(TRIM(COALESCE({COL_MONTO}, '')), 'U$S', ''),
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


def _sql_cantidad_num_expr() -> str:
    limpio = f"REPLACE(TRIM(COALESCE({COL_CANT}, '')), ',', '.')"
    return _sql_num_from_text(limpio)


# =====================================================================
# LOGGING
# =====================================================================

def _guardar_log(consulta: str, parametros: str, resultado: str, registros: int, error: str, tiempo_ms: int):
    pass  # Desactivado para producción


def guardar_chat_log(pregunta: str, intencion: str, respuesta: str, tuvo_datos: bool, registros: int = 0, debug: str = None):
    pass  # Desactivado para producción


# =====================================================================
# EJECUTOR SQL
# =====================================================================

def ejecutar_consulta(query: str, params: tuple = None) -> pd.DataFrame:
    """Ejecuta consulta SQL y retorna DataFrame."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()

    try:
        if params is None:
            params = ()

        df = pd.read_sql_query(query, conn, params=params)
        return df

    except Exception as e:
        print(f"Error en consulta SQL: {e}")
        return pd.DataFrame()

    finally:
        try:
            conn.close()
        except:
            pass


# =====================================================================
# LISTADOS
# =====================================================================

def get_lista_proveedores() -> list[str]:
    sql = f"""
        SELECT DISTINCT TRIM({COL_PROV}) AS proveedor
        FROM {TABLE_COMPRAS}
        WHERE {COL_PROV} IS NOT NULL AND TRIM({COL_PROV}) <> ''
        ORDER BY proveedor
        LIMIT 500
    """
    df = ejecutar_consulta(sql)
    if df.empty:
        return ["Todos"]
    return ["Todos"] + df['proveedor'].tolist()


def get_lista_tipos_comprobante() -> list[str]:
    sql = f"""
        SELECT DISTINCT TRIM({COL_TIPO_COMP}) AS tipo
        FROM {TABLE_COMPRAS}
        WHERE {COL_TIPO_COMP} IS NOT NULL AND TRIM({COL_TIPO_COMP}) <> ''
        ORDER BY tipo
    """
    df = ejecutar_consulta(sql)
    if df.empty:
        return ["Todos"]
    return ["Todos"] + df['tipo'].tolist()


def get_lista_articulos() -> list[str]:
    sql = f"""
        SELECT DISTINCT TRIM({COL_ART}) AS articulo
        FROM {TABLE_COMPRAS}
        WHERE {COL_ART} IS NOT NULL AND TRIM({COL_ART}) <> ''
        ORDER BY articulo
        LIMIT 500
    """
    df = ejecutar_consulta(sql)
    if df.empty:
        return ["Todos"]
    return ["Todos"] + df['articulo'].tolist()


# =====================================================================
# DETALLE COMPRAS: PROVEEDOR + MES
# =====================================================================

def get_detalle_compras_proveedor_mes(proveedor_like: str, mes_key: str) -> pd.DataFrame:
    """Detalle de compras de un proveedor en un mes específico."""
    
    proveedor_like = (proveedor_like or "").strip().lower()
    
    sql = """
        SELECT 
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Articulo") AS Articulo,
            TRIM("Nro. Comprobante") AS Nro_Factura,
            "Fecha",
            "Cantidad",
            "Moneda",
            "Monto Neto" AS Total
        FROM chatbot_raw 
        WHERE LOWER("Cliente / Proveedor") LIKE %s
          AND "Mes" = %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        ORDER BY "Fecha" DESC NULLS LAST
        LIMIT 200
    """
    
    params = (f"%{proveedor_like}%", mes_key)
    
    # Usar pd.read_sql_query directamente (como cuando funcionó)
    try:
        conn = get_db_connection()
        if conn is None:
            return pd.DataFrame()
        
        df = pd.read_sql_query(sql, conn, params=params)
        conn.close()
        return df
        
    except Exception as e:
        print(f"Error: {e}")
        return pd.DataFrame()


# =====================================================================
# DETALLE COMPRAS: PROVEEDOR + AÑO
# =====================================================================

def get_detalle_compras_proveedor_anio(proveedor_like: str, anio: int, moneda: str = None) -> pd.DataFrame:
    """Detalle de compras de un proveedor en un año."""
    
    proveedor_like = (proveedor_like or "").split("(")[0].strip().lower()
    total_expr = _sql_total_num_expr_general()
    mon_expr = _sql_moneda_norm_expr()

    moneda_sql = ""
    if moneda and str(moneda).strip().upper() in ("U$S", "USD", "U$$"):
        total_expr = _sql_total_num_expr_usd()
        moneda_sql = f"AND {mon_expr} IN ('U$S','U$$')"
    elif moneda and str(moneda).strip() in ("$", "UYU"):
        total_expr = _sql_total_num_expr()
        moneda_sql = f"AND {mon_expr} = '$'"

    sql = f"""
        SELECT
            TRIM({COL_PROV}) AS Proveedor,
            TRIM({COL_ART}) AS Articulo,
            TRIM({COL_NRO_COMP}) AS Nro_Factura,
            {COL_FECHA} AS Fecha,
            {COL_CANT} AS Cantidad,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS Total
        FROM {TABLE_COMPRAS}
        WHERE ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
          AND LOWER(TRIM({COL_PROV})) LIKE %s
          AND {COL_ANIO}::int = %s
          {moneda_sql}
        ORDER BY {COL_FECHA} DESC NULLS LAST
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
        FROM {TABLE_COMPRAS}
        WHERE ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
          AND LOWER(TRIM({COL_PROV})) LIKE %s
          AND {COL_ANIO}::int = %s
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
    total_expr = _sql_total_num_expr_general()
    
    sql = f"""
        SELECT 
            TRIM({COL_PROV}) AS Proveedor,
            TRIM({COL_ART}) AS Articulo,
            TRIM({COL_NRO_COMP}) AS Nro_Factura,
            {COL_FECHA} AS Fecha,
            {COL_CANT} AS Cantidad,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS Total
        FROM {TABLE_COMPRAS}
        WHERE LOWER(TRIM({COL_ART})) LIKE %s
          AND TRIM({COL_MES}) = %s
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
        ORDER BY {COL_FECHA} DESC NULLS LAST
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
            TRIM({COL_PROV}) AS Proveedor,
            TRIM({COL_ART}) AS Articulo,
            TRIM({COL_NRO_COMP}) AS Nro_Factura,
            {COL_FECHA} AS Fecha,
            {COL_CANT} AS Cantidad,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS Total
        FROM {TABLE_COMPRAS}
        WHERE ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
          AND {COL_ANIO}::int = %s
          AND LOWER(TRIM({COL_ART})) LIKE %s
        ORDER BY {COL_FECHA} DESC NULLS LAST
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
        FROM {TABLE_COMPRAS}
        WHERE ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
          AND {COL_ANIO}::int = %s
          AND LOWER(TRIM({COL_ART})) LIKE %s
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
            TRIM({COL_NRO_COMP}) AS nro_factura,
            TRIM({COL_PROV}) AS Proveedor,
            TRIM({COL_ART}) AS Articulo,
            {COL_CANT} AS cantidad,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS Total
        FROM {TABLE_COMPRAS}
        WHERE TRIM({COL_NRO_COMP}) = %s
          AND TRIM({COL_NRO_COMP}) <> 'A0000000'
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
        ORDER BY TRIM({COL_ART})
    """
    return ejecutar_consulta(sql, (nro_factura,))


def get_ultima_factura_de_articulo(patron_articulo: str) -> pd.DataFrame:
    """Última factura de un artículo."""
    
    total_expr = _sql_total_num_expr_general()
    
    sql = f"""
        SELECT
            TRIM({COL_PROV}) AS Proveedor,
            TRIM({COL_ART}) AS Articulo,
            {COL_CANT} AS cantidad,
            TRIM({COL_NRO_COMP}) AS nro_factura,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS total_linea,
            {COL_FECHA} AS fecha
        FROM {TABLE_COMPRAS}
        WHERE LOWER(TRIM({COL_ART})) LIKE %s
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
        ORDER BY {COL_FECHA} DESC NULLS LAST
        LIMIT 1
    """
    return ejecutar_consulta(sql, (f"%{patron_articulo.lower()}%",))


def get_ultima_factura_inteligente(patron: str) -> pd.DataFrame:
    """Busca última factura por artículo O proveedor."""
    
    total_expr = _sql_total_num_expr_general()
    
    # Primero como artículo
    sql_art = f"""
        SELECT
            TRIM({COL_PROV}) AS Proveedor,
            TRIM({COL_ART}) AS Articulo,
            {COL_CANT} AS cantidad,
            TRIM({COL_NRO_COMP}) AS nro_factura,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS total_linea,
            {COL_FECHA} AS fecha
        FROM {TABLE_COMPRAS}
        WHERE LOWER(TRIM({COL_ART})) LIKE %s
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
        ORDER BY {COL_FECHA} DESC NULLS LAST
        LIMIT 1
    """
    df = ejecutar_consulta(sql_art, (f"%{patron.lower()}%",))
    
    if df is not None and not df.empty:
        return df
    
    # Si no, como proveedor
    sql_prov = f"""
        SELECT
            TRIM({COL_PROV}) AS Proveedor,
            TRIM({COL_ART}) AS Articulo,
            {COL_CANT} AS cantidad,
            TRIM({COL_NRO_COMP}) AS nro_factura,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS total_linea,
            {COL_FECHA} AS fecha
        FROM {TABLE_COMPRAS}
        WHERE LOWER(TRIM({COL_PROV})) LIKE %s
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
        ORDER BY {COL_FECHA} DESC NULLS LAST
        LIMIT 1
    """
    return ejecutar_consulta(sql_prov, (f"%{patron.lower()}%",))


def get_ultima_factura_numero_de_articulo(patron_articulo: str) -> Optional[str]:
    """Obtiene solo el número de la última factura."""
    
    sql = f"""
        SELECT TRIM({COL_NRO_COMP}) AS nro_factura
        FROM {TABLE_COMPRAS}
        WHERE LOWER(TRIM({COL_ART})) LIKE %s
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
        ORDER BY {COL_FECHA} DESC NULLS LAST
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
            TRIM({COL_PROV}) AS Proveedor,
            TRIM({COL_ART}) AS Articulo,
            TRIM({COL_NRO_COMP}) AS Nro_Factura,
            {COL_FECHA} AS Fecha,
            {COL_CANT} AS Cantidad,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS Total
        FROM {TABLE_COMPRAS}
        WHERE ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
          AND LOWER(TRIM({COL_ART})) LIKE %s
        ORDER BY {COL_FECHA} DESC NULLS LAST
        {limit_sql}
    """
    return ejecutar_consulta(sql, (f"%{patron_articulo.lower()}%",))


def get_total_factura_por_numero(nro_factura: str) -> pd.DataFrame:
    """Total de una factura."""
    
    total_expr = _sql_total_num_expr_general()
    
    sql = f"""
        SELECT COALESCE(SUM({total_expr}), 0) AS total_factura
        FROM {TABLE_COMPRAS}
        WHERE TRIM({COL_NRO_COMP}) = %s
    """
    return ejecutar_consulta(sql, (nro_factura,))


# =====================================================================
# COMPARACIONES POR MESES
# =====================================================================

def get_comparacion_proveedor_meses(mes1: str, mes2: str, label1: str, label2: str, proveedores: List[str] = None) -> pd.DataFrame:
    """Compara proveedores entre dos meses."""
    
    total_expr = _sql_total_num_expr_general()
    mes_col = _sql_mes_col()

    prov_where = ""
    prov_params = []
    if proveedores:
        parts = [f"LOWER(TRIM({COL_PROV})) LIKE %s" for _ in proveedores]
        prov_params = [f"%{p.lower()}%" for p in proveedores]
        prov_where = f"AND ({' OR '.join(parts)})"

    sql = f"""
        SELECT
            TRIM({COL_PROV}) AS Concepto,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS "{label1}",
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS "{label2}",
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) -
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Diferencia
        FROM {TABLE_COMPRAS}
        WHERE {mes_col} IN (%s, %s)
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
          {prov_where}
        GROUP BY TRIM({COL_PROV})
        HAVING SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) > 0
            OR SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) > 0
        ORDER BY Diferencia DESC
    """

    params = (mes1, mes2, mes2, mes1, mes1, mes2, *prov_params, mes1, mes2)
    return ejecutar_consulta(sql, params)


def get_comparacion_articulo_meses(mes1: str, mes2: str, label1: str, label2: str, articulos: List[str] = None) -> pd.DataFrame:
    """Compara artículos entre dos meses."""
    
    total_expr = _sql_total_num_expr_general()
    mes_col = _sql_mes_col()

    art_where = ""
    art_params = []
    if articulos:
        parts = [f"LOWER(TRIM({COL_ART})) LIKE %s" for _ in articulos]
        art_params = [f"%{a.lower()}%" for a in articulos]
        art_where = f"AND ({' OR '.join(parts)})"

    sql = f"""
        SELECT
            TRIM({COL_ART}) AS Concepto,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS "{label1}",
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS "{label2}",
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) -
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Diferencia
        FROM {TABLE_COMPRAS}
        WHERE {mes_col} IN (%s, %s)
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
          {art_where}
        GROUP BY TRIM({COL_ART})
        HAVING SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) > 0
            OR SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) > 0
        ORDER BY Diferencia DESC
        LIMIT 200
    """

    params = (mes1, mes2, mes2, mes1, mes1, mes2, *art_params, mes1, mes2)
    return ejecutar_consulta(sql, params)


def get_comparacion_familia_meses(mes1: str, mes2: str, label1: str, label2: str, familias: List[str] = None) -> pd.DataFrame:
    """Compara familias entre dos meses."""
    
    total_expr = _sql_total_num_expr_general()
    mes_col = _sql_mes_col()

    fam_where = ""
    fam_params = []
    if familias:
        parts = [f"TRIM(COALESCE({COL_FAMILIA}, '')) = %s" for _ in familias]
        fam_params = list(familias)
        fam_where = f"AND ({' OR '.join(parts)})"

    sql = f"""
        SELECT
            TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA')) AS Familia,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS "{label1}",
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS "{label2}",
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) -
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Diferencia
        FROM {TABLE_COMPRAS}
        WHERE {mes_col} IN (%s, %s)
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
          {fam_where}
        GROUP BY TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA'))
        HAVING SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) > 0
            OR SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) > 0
        ORDER BY Diferencia DESC
    """

    params = (mes1, mes2, mes2, mes1, mes1, mes2, *fam_params, mes1, mes2)
    return ejecutar_consulta(sql, params)


def get_comparacion_familia_meses_moneda(mes1: str, mes2: str, label1: str, label2: str, moneda: str = "$", familias: List[str] = None) -> pd.DataFrame:
    """Compara familias entre dos meses filtrado por moneda."""
    
    mes_col = _sql_mes_col()
    mon_expr = _sql_moneda_norm_expr()

    mon = (moneda or "$").strip().upper()
    if mon in ("U$S", "U$$", "USD"):
        total_expr = _sql_total_num_expr_usd()
        mon_filter = f"{mon_expr} IN ('U$S', 'U$$')"
    else:
        total_expr = _sql_total_num_expr()
        mon_filter = f"{mon_expr} = '$'"

    fam_where = ""
    fam_params = []
    if familias:
        parts = [f"TRIM(COALESCE({COL_FAMILIA}, '')) = %s" for _ in familias]
        fam_params = list(familias)
        fam_where = f"AND ({' OR '.join(parts)})"

    sql = f"""
        SELECT
            TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA')) AS Familia,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS "{label1}",
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS "{label2}",
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) -
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Diferencia
        FROM {TABLE_COMPRAS}
        WHERE {mes_col} IN (%s, %s)
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
          AND {mon_filter}
          {fam_where}
        GROUP BY TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA'))
        HAVING SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) > 0
            OR SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) > 0
        ORDER BY Diferencia DESC
    """

    params = (mes1, mes2, mes2, mes1, mes1, mes2, *fam_params, mes1, mes2)
    return ejecutar_consulta(sql, params)


# =====================================================================
# COMPARACIONES POR AÑOS
# =====================================================================

def get_comparacion_proveedor_anios_monedas(anios: List[int], proveedores: List[str] = None) -> pd.DataFrame:
    """Compara proveedores por años con separación de monedas."""
    
    mon_expr = _sql_moneda_norm_expr()
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()
    anios = sorted(anios)

    prov_where = ""
    prov_params = []
    if proveedores:
        parts = [f"LOWER(TRIM({COL_PROV})) LIKE %s" for _ in proveedores]
        prov_params = [f"%{p.lower()}%" for p in proveedores]
        prov_where = f"AND ({' OR '.join(parts)})"

    cols = []
    for y in anios:
        cols.append(f"""SUM(CASE WHEN {COL_ANIO}::int = {y} AND {mon_expr} = '$' THEN {total_pesos} ELSE 0 END) AS "{y}_$" """)
        cols.append(f"""SUM(CASE WHEN {COL_ANIO}::int = {y} AND {mon_expr} IN ('U$S','U$$') THEN {total_usd} ELSE 0 END) AS "{y}_USD" """)

    cols_sql = ",\n            ".join(cols)
    y_last = anios[-1]
    order_sql = f'"{y_last}_$" DESC, "{y_last}_USD" DESC'
    anios_sql = ", ".join(str(y) for y in anios)

    sql = f"""
        SELECT
            TRIM({COL_PROV}) AS Proveedor,
            {cols_sql}
        FROM {TABLE_COMPRAS}
        WHERE ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
          AND {COL_ANIO}::int IN ({anios_sql})
          {prov_where}
        GROUP BY TRIM({COL_PROV})
        ORDER BY {order_sql}
        LIMIT 300
    """

    return ejecutar_consulta(sql, tuple(prov_params) if prov_params else None)


def get_comparacion_articulo_anios_monedas(anios: List[int], articulos: List[str] = None) -> pd.DataFrame:
    """Compara artículos por años con separación de monedas."""
    
    mon_expr = _sql_moneda_norm_expr()
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()
    anios = sorted(anios)

    art_where = ""
    art_params = []
    if articulos:
        parts = [f"LOWER(TRIM({COL_ART})) LIKE %s" for _ in articulos]
        art_params = [f"%{a.lower()}%" for a in articulos]
        art_where = f"AND ({' OR '.join(parts)})"

    cols = []
    for y in anios:
        cols.append(f"""SUM(CASE WHEN {COL_ANIO}::int = {y} AND {mon_expr} = '$' THEN {total_pesos} ELSE 0 END) AS "{y}_$" """)
        cols.append(f"""SUM(CASE WHEN {COL_ANIO}::int = {y} AND {mon_expr} IN ('U$S','U$$') THEN {total_usd} ELSE 0 END) AS "{y}_USD" """)

    cols_sql = ",\n            ".join(cols)
    y_last = anios[-1]
    order_sql = f'"{y_last}_$" DESC, "{y_last}_USD" DESC'
    anios_sql = ", ".join(str(y) for y in anios)

    sql = f"""
        SELECT
            TRIM({COL_ART}) AS Articulo,
            {cols_sql}
        FROM {TABLE_COMPRAS}
        WHERE ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
          AND {COL_ANIO}::int IN ({anios_sql})
          {art_where}
        GROUP BY TRIM({COL_ART})
        ORDER BY {order_sql}
        LIMIT 300
    """

    return ejecutar_consulta(sql, tuple(art_params) if art_params else None)


def get_comparacion_articulo_anios(anios: List[int], articulo_like: str) -> pd.DataFrame:
    """Compara un artículo específico entre años."""
    return get_comparacion_articulo_anios_monedas(anios, [articulo_like] if articulo_like else None)


def get_comparacion_familia_anios_monedas(anios: List[int], familias: List[str] = None) -> pd.DataFrame:
    """Compara familias por años con separación de monedas."""
    
    mon_expr = _sql_moneda_norm_expr()
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()
    anios = sorted(anios)

    fam_where = ""
    fam_params = []
    if familias:
        parts = [f"TRIM(COALESCE({COL_FAMILIA}, '')) = %s" for _ in familias]
        fam_params = list(familias)
        fam_where = f"AND ({' OR '.join(parts)})"

    cols = []
    for y in anios:
        cols.append(f"""SUM(CASE WHEN {COL_ANIO}::int = {y} AND {mon_expr} = '$' THEN {total_pesos} ELSE 0 END) AS "{y}_$" """)
        cols.append(f"""SUM(CASE WHEN {COL_ANIO}::int = {y} AND {mon_expr} IN ('U$S','U$$') THEN {total_usd} ELSE 0 END) AS "{y}_USD" """)

    cols_sql = ",\n            ".join(cols)
    y_last = anios[-1]
    order_sql = f'"{y_last}_$" DESC, "{y_last}_USD" DESC'
    anios_sql = ", ".join(str(y) for y in anios)

    sql = f"""
        SELECT
            TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA')) AS Familia,
            {cols_sql}
        FROM {TABLE_COMPRAS}
        WHERE ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
          AND {COL_ANIO}::int IN ({anios_sql})
          {fam_where}
        GROUP BY TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA'))
        ORDER BY {order_sql}
        LIMIT 300
    """

    return ejecutar_consulta(sql, tuple(fam_params) if fam_params else None)


def get_detalle_compras_proveedor_anios(anios: List[int], proveedores: List[str] = None) -> pd.DataFrame:
    """Detalle de compras por proveedor en varios años."""
    
    total_expr = _sql_total_num_expr_general()
    anios = sorted(anios)
    anios_sql = ", ".join(str(y) for y in anios)

    prov_where = ""
    prov_params = []
    if proveedores:
        parts = [f"LOWER(TRIM({COL_PROV})) LIKE %s" for _ in proveedores]
        prov_params = [f"%{p.lower()}%" for p in proveedores]
        prov_where = f"AND ({' OR '.join(parts)})"

    sql = f"""
        SELECT
            TRIM({COL_PROV}) AS Proveedor,
            TRIM({COL_ART}) AS Articulo,
            {COL_ANIO} AS Año,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS Total
        FROM {TABLE_COMPRAS}
        WHERE ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
          AND {COL_ANIO}::int IN ({anios_sql})
          {prov_where}
        ORDER BY {COL_ANIO} DESC, TRIM({COL_PROV}), TRIM({COL_ART})
        LIMIT 500
    """

    return ejecutar_consulta(sql, tuple(prov_params) if prov_params else None)


# =====================================================================
# BUSCADOR DE COMPROBANTES
# =====================================================================

def buscar_comprobantes(proveedor: str = None, tipo_comprobante: str = None, 
                        articulo: str = None, fecha_desde=None, fecha_hasta=None,
                        texto_busqueda: str = None) -> pd.DataFrame:
    """Busca comprobantes con filtros múltiples."""
    
    total_expr = _sql_total_num_expr_general()
    
    condiciones = []
    params = []
    
    if proveedor:
        condiciones.append(f"LOWER(TRIM({COL_PROV})) LIKE %s")
        params.append(f"%{proveedor.lower()}%")
    
    if tipo_comprobante:
        condiciones.append(f"TRIM({COL_TIPO_COMP}) = %s")
        params.append(tipo_comprobante)
    
    if articulo:
        condiciones.append(f"LOWER(TRIM({COL_ART})) LIKE %s")
        params.append(f"%{articulo.lower()}%")
    
    if fecha_desde:
        condiciones.append(f"{COL_FECHA} >= %s")
        params.append(fecha_desde.strftime('%Y-%m-%d'))
    
    if fecha_hasta:
        condiciones.append(f"{COL_FECHA} <= %s")
        params.append(fecha_hasta.strftime('%Y-%m-%d'))
    
    if texto_busqueda:
        condiciones.append(f"""(
            LOWER(TRIM({COL_ART})) LIKE %s OR
            LOWER(TRIM({COL_PROV})) LIKE %s OR
            TRIM({COL_NRO_COMP}) LIKE %s
        )""")
        params.extend([f"%{texto_busqueda.lower()}%"] * 3)
    
    where_sql = " AND ".join(condiciones) if condiciones else "1=1"
    
    sql = f"""
        SELECT
            TRIM({COL_PROV}) AS Proveedor,
            TRIM({COL_ART}) AS Articulo,
            TRIM({COL_NRO_COMP}) AS Nro_Factura,
            {COL_FECHA} AS Fecha,
            {COL_CANT} AS Cantidad,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS Monto
        FROM {TABLE_COMPRAS}
        WHERE {where_sql}
        ORDER BY {COL_FECHA} DESC NULLS LAST
        LIMIT 200
    """
    
    return ejecutar_consulta(sql, tuple(params) if params else None)


# =====================================================================
# TOP PROVEEDORES
# =====================================================================

def get_top_10_proveedores_chatbot(moneda: str = None, anio: int = None, mes: str = None) -> pd.DataFrame:
    """Top 10 proveedores."""
    
    total_expr = _sql_total_num_expr_general()
    mon_expr = _sql_moneda_norm_expr()
    
    condiciones = [f"({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')"]
    params = []
    
    if moneda:
        mon = moneda.strip().upper()
        if mon in ("U$S", "U$$", "USD"):
            total_expr = _sql_total_num_expr_usd()
            condiciones.append(f"{mon_expr} IN ('U$S', 'U$$')")
        else:
            total_expr = _sql_total_num_expr()
            condiciones.append(f"{mon_expr} = '$'")
    
    if mes:
        condiciones.append(f"TRIM({COL_MES}) = %s")
        params.append(mes)
    elif anio:
        condiciones.append(f"{COL_ANIO}::int = %s")
        params.append(anio)
    
    where_sql = " AND ".join(condiciones)
    
    sql = f"""
        SELECT
            TRIM({COL_PROV}) AS Proveedor,
            SUM({total_expr}) AS Total,
            COUNT(*) AS Registros
        FROM {TABLE_COMPRAS}
        WHERE {where_sql}
          AND {COL_PROV} IS NOT NULL
          AND TRIM({COL_PROV}) <> ''
        GROUP BY TRIM({COL_PROV})
        ORDER BY Total DESC
        LIMIT 10
    """
    
    return ejecutar_consulta(sql, tuple(params) if params else None)


# =====================================================================
# GASTOS POR FAMILIAS / SECCIONES
# =====================================================================

def get_gastos_todas_familias_mes(mes_key: str) -> pd.DataFrame:
    """Gastos de todas las familias en un mes."""
    
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()
    mon_expr = _sql_moneda_norm_expr()
    
    sql = f"""
        SELECT
            TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA')) AS Familia,
            SUM(CASE WHEN {mon_expr} = '$' THEN {total_pesos} ELSE 0 END) AS Total_Pesos,
            SUM(CASE WHEN {mon_expr} IN ('U$S', 'U$$') THEN {total_usd} ELSE 0 END) AS Total_USD
        FROM {TABLE_COMPRAS}
        WHERE TRIM({COL_MES}) = %s
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
        GROUP BY TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA'))
        ORDER BY Total_Pesos DESC, Total_USD DESC
    """
    
    return ejecutar_consulta(sql, (mes_key,))


def get_gastos_todas_familias_anio(anio: int) -> pd.DataFrame:
    """Gastos de todas las familias en un año."""
    
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()
    mon_expr = _sql_moneda_norm_expr()
    
    sql = f"""
        SELECT
            TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA')) AS Familia,
            SUM(CASE WHEN {mon_expr} = '$' THEN {total_pesos} ELSE 0 END) AS Total_Pesos,
            SUM(CASE WHEN {mon_expr} IN ('U$S', 'U$$') THEN {total_usd} ELSE 0 END) AS Total_USD
        FROM {TABLE_COMPRAS}
        WHERE {COL_ANIO}::int = %s
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
        GROUP BY TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA'))
        ORDER BY Total_Pesos DESC, Total_USD DESC
    """
    
    return ejecutar_consulta(sql, (anio,))


def get_gastos_secciones_detalle_completo(familias: List[str], mes_key: str) -> pd.DataFrame:
    """Detalle de gastos de familias específicas en un mes."""
    
    total_expr = _sql_total_num_expr_general()
    
    fam_placeholders = ", ".join(["%s"] * len(familias))
    
    sql = f"""
        SELECT
            TRIM({COL_FAMILIA}) AS Familia,
            TRIM({COL_ART}) AS Articulo,
            TRIM({COL_PROV}) AS Proveedor,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS Total
        FROM {TABLE_COMPRAS}
        WHERE TRIM({COL_MES}) = %s
          AND UPPER(TRIM(COALESCE({COL_FAMILIA}, ''))) IN ({fam_placeholders})
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
        ORDER BY TRIM({COL_FAMILIA}), Total DESC
    """
    
    params = [mes_key] + [f.upper() for f in familias]
    return ejecutar_consulta(sql, tuple(params))


# =====================================================================
# DASHBOARD
# =====================================================================

def get_dashboard_totales(anio: int) -> dict:
    """Totales para dashboard."""
    
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()
    mon_expr = _sql_moneda_norm_expr()
    
    sql = f"""
        SELECT
            COALESCE(SUM(CASE WHEN {mon_expr} = '$' THEN {total_pesos} ELSE 0 END), 0) AS total_pesos,
            COALESCE(SUM(CASE WHEN {mon_expr} IN ('U$S', 'U$$') THEN {total_usd} ELSE 0 END), 0) AS total_usd,
            COUNT(DISTINCT {COL_PROV}) AS proveedores,
            COUNT(DISTINCT {COL_NRO_COMP}) AS facturas
        FROM {TABLE_COMPRAS}
        WHERE {COL_ANIO}::int = %s
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
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
            TRIM({COL_MES}) AS Mes,
            SUM({total_expr}) AS Total
        FROM {TABLE_COMPRAS}
        WHERE {COL_ANIO}::int = %s
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
        GROUP BY TRIM({COL_MES})
        ORDER BY TRIM({COL_MES})
    """
    
    return ejecutar_consulta(sql, (anio,))


def get_dashboard_top_proveedores(anio: int, top_n: int = 10, moneda: str = "$") -> pd.DataFrame:
    """Top proveedores para dashboard."""
    
    mon_expr = _sql_moneda_norm_expr()
    
    if moneda in ("U$S", "U$$", "USD"):
        total_expr = _sql_total_num_expr_usd()
        mon_filter = f"{mon_expr} IN ('U$S', 'U$$')"
    else:
        total_expr = _sql_total_num_expr()
        mon_filter = f"{mon_expr} = '$'"
    
    sql = f"""
        SELECT
            TRIM({COL_PROV}) AS Proveedor,
            SUM({total_expr}) AS Total
        FROM {TABLE_COMPRAS}
        WHERE {COL_ANIO}::int = %s
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
          AND {mon_filter}
          AND {COL_PROV} IS NOT NULL
          AND TRIM({COL_PROV}) <> ''
        GROUP BY TRIM({COL_PROV})
        ORDER BY Total DESC
        LIMIT %s
    """
    
    return ejecutar_consulta(sql, (anio, top_n))


def get_dashboard_gastos_familia(anio: int) -> pd.DataFrame:
    """Gastos por familia para dashboard."""
    
    total_expr = _sql_total_num_expr_general()
    
    sql = f"""
        SELECT
            TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA')) AS Familia,
            SUM({total_expr}) AS Total
        FROM {TABLE_COMPRAS}
        WHERE {COL_ANIO}::int = %s
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
        GROUP BY TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA'))
        ORDER BY Total DESC
        LIMIT 10
    """
    
    return ejecutar_consulta(sql, (anio,))


def get_dashboard_ultimas_compras(limite: int = 10) -> pd.DataFrame:
    """Últimas compras para dashboard."""
    
    total_expr = _sql_total_num_expr_general()
    
    sql = f"""
        SELECT
            {COL_FECHA} AS Fecha,
            TRIM({COL_ART}) AS Articulo,
            TRIM({COL_PROV}) AS Proveedor,
            {total_expr} AS Total
        FROM {TABLE_COMPRAS}
        WHERE ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
        ORDER BY {COL_FECHA} DESC NULLS LAST
        LIMIT %s
    """
    
    return ejecutar_consulta(sql, (limite,))


# =====================================================================
# ALERTAS DE VENCIMIENTO (PLACEHOLDER - NECESITA TABLA stock)
# =====================================================================

def get_alertas_vencimiento_multiple(limite: int = 10) -> list:
    """Placeholder para alertas de vencimiento."""
    return []


# =====================================================================
# OTRAS FUNCIONES DE SOPORTE
# =====================================================================

def get_valores_unicos() -> dict:
    """Obtiene valores únicos de proveedores, familias y artículos."""
    return {
        "proveedores": get_lista_proveedores()[1:],  # Sin "Todos"
        "familias": [],
        "articulos": get_lista_articulos()[1:]  # Sin "Todos"
    }


def get_gastos_por_familia(where_clause: str, params: tuple) -> pd.DataFrame:
    """Gastos por familia con where personalizado."""
    
    total_expr = _sql_total_num_expr_general()
    
    sql = f"""
        SELECT
            TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA')) AS Familia,
            SUM({total_expr}) AS Total
        FROM {TABLE_COMPRAS}
        WHERE {where_clause}
        GROUP BY TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA'))
        ORDER BY Total DESC
    """
    
    return ejecutar_consulta(sql, params)


def get_detalle_compras(where_clause: str, params: tuple) -> pd.DataFrame:
    """Detalle de compras con where personalizado."""
    
    total_expr = _sql_total_num_expr_general()
    
    sql = f"""
        SELECT
            TRIM({COL_PROV}) AS Proveedor,
            TRIM({COL_ART}) AS Articulo,
            TRIM({COL_NRO_COMP}) AS Nro_Factura,
            {COL_FECHA} AS Fecha,
            {COL_CANT} AS Cantidad,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS Total
        FROM {TABLE_COMPRAS}
        WHERE {where_clause}
        ORDER BY {COL_FECHA} DESC NULLS LAST
        LIMIT 200
    """
    
    return ejecutar_consulta(sql, params)


def get_compras_por_mes_excel(mes_key: str) -> pd.DataFrame:
    """Compras de un mes para exportar a Excel."""
    
    total_expr = _sql_total_num_expr_general()
    
    sql = f"""
        SELECT
            TRIM({COL_PROV}) AS Proveedor,
            TRIM({COL_ART}) AS Articulo,
            TRIM({COL_NRO_COMP}) AS Nro_Factura,
            {COL_FECHA} AS Fecha,
            {COL_CANT} AS Cantidad,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS Total
        FROM {TABLE_COMPRAS}
        WHERE TRIM({COL_MES}) = %s
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
        ORDER BY {COL_FECHA} DESC, TRIM({COL_PROV})
    """
    
    return ejecutar_consulta(sql, (mes_key,))


def get_total_compras_proveedor_moneda_periodos(periodos: List[str], monedas: List[str] = None) -> pd.DataFrame:
    """Total de compras por proveedor en múltiples períodos."""
    
    total_expr = _sql_total_num_expr_general()
    
    periodos_sql = ", ".join(["%s"] * len(periodos))
    
    sql = f"""
        SELECT
            TRIM({COL_PROV}) AS Proveedor,
            TRIM({COL_MES}) AS Mes,
            {COL_MONEDA} AS Moneda,
            SUM({total_expr}) AS Total
        FROM {TABLE_COMPRAS}
        WHERE TRIM({COL_MES}) IN ({periodos_sql})
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%%')
        GROUP BY TRIM({COL_PROV}), TRIM({COL_MES}), {COL_MONEDA}
        ORDER BY TRIM({COL_MES}), Total DESC
    """
    
    return ejecutar_consulta(sql, tuple(periodos))


# =====================================================================
# STOCK PLACEHOLDERS (necesitan tabla stock)
# =====================================================================

def get_lista_articulos_stock() -> list[str]:
    return ["Todos"]

def get_lista_familias_stock() -> list[str]:
    return ["Todos"]

def get_lista_depositos_stock() -> list[str]:
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
