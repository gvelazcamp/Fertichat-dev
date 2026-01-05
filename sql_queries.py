# =========================
# SQL QUERIES - SOLO CONSULTAS (POSTGRES / SUPABASE)
# =========================
# VERSIÓN CORREGIDA - get_comparacion_proveedor_anios_like CON LIKE
# =========================

import os
import re
import pandas as pd
from typing import List, Tuple, Optional, Dict
from datetime import datetime
import streamlit as st

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None


# =====================================================================
# CONEXIÓN DB (SUPABASE / POSTGRES)
# =====================================================================

def get_db_connection():
    """Conexión a Postgres (Supabase) usando Secrets/Env vars."""
    if psycopg2 is None:
        print("psycopg2 no instalado")
        return None
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
    return '"Fecha"'


def _sql_mes_col() -> str:
    return 'TRIM(COALESCE("Mes", \'\'))'


def _sql_moneda_norm_expr() -> str:
    return 'TRIM(COALESCE("Moneda", \'\'))'


def _sql_num_from_text(text_expr: str) -> str:
    return f"CAST(NULLIF(TRIM({text_expr}), '') AS NUMERIC(15,2))"


def _sql_total_num_expr() -> str:
    """Convierte Monto Neto a número (pesos)."""
    limpio = """
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
    limpio = """
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
    limpio = """
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


def get_serie_compras_agregada(where_clause: str, params: tuple) -> pd.DataFrame:
    """Serie temporal agregada (SIN LIMIT). Se usa SOLO para gráficos."""
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

def get_comparacion_proveedor_meses(*args, **kwargs) -> pd.DataFrame:
    """
    Compatible con 2 firmas (para no romper nada):

    A) Nueva (canónica):
       get_comparacion_proveedor_meses(proveedor, mes1, mes2, label1, label2)

    B) Vieja (tu versión anterior):
       get_comparacion_proveedor_meses(mes1, mes2, label1, label2, proveedores=None)
       donde proveedores puede ser ["ROCHE"] o None
    """

    # Normalizar inputs
    proveedor = None
    mes1 = None
    mes2 = None
    label1 = None
    label2 = None

    # Caso kwargs (si alguien llama con nombres)
    if kwargs:
        proveedor = kwargs.get("proveedor", None)
        mes1 = kwargs.get("mes1", None)
        mes2 = kwargs.get("mes2", None)
        label1 = kwargs.get("label1", None)
        label2 = kwargs.get("label2", None)

        # compat vieja: proveedores=[...]
        provs = kwargs.get("proveedores", None)
        if (not proveedor) and isinstance(provs, (list, tuple)) and len(provs) > 0:
            proveedor = provs[0]

    # Caso args posicionales
    if args and (mes1 is None and mes2 is None):
        # Firma vieja: (mes1, mes2, label1, label2, proveedores?)
        if len(args) >= 4 and isinstance(args[0], str) and isinstance(args[1], str) and (
            args[0].startswith("202") and args[1].startswith("202")
        ):
            mes1 = args[0]
            mes2 = args[1]
            label1 = args[2]
            label2 = args[3]
            if len(args) >= 5 and isinstance(args[4], (list, tuple)) and len(args[4]) > 0:
                proveedor = args[4][0]
        else:
            # Firma nueva: (proveedor, mes1, mes2, label1?, label2?)
            if len(args) >= 3:
                proveedor = args[0]
                mes1 = args[1]
                mes2 = args[2]
            if len(args) >= 4:
                label1 = args[3]
            if len(args) >= 5:
                label2 = args[4]

    # Defaults de labels
    if mes1 is None or mes2 is None:
        return pd.DataFrame()

    if not label1:
        label1 = mes1
    if not label2:
        label2 = mes2

    # Sanitizar labels
    label1_sql = str(label1).replace('"', '').strip()
    label2_sql = str(label2).replace('"', '').strip()

    total_expr = _sql_total_num_expr_general()
    proveedor_norm = (proveedor or "").strip().lower()

    # WHERE dinámico (con o sin proveedor)
    prov_where = ""
    prov_param = []
    if proveedor_norm:
        prov_where = 'AND LOWER(TRIM("Cliente / Proveedor")) LIKE %s'
        prov_param = [f"%{proveedor_norm}%"]

    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) AS "{label1_sql}",
            SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) AS "{label2_sql}",
            SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) -
            SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) AS Diferencia
        FROM chatbot_raw
        WHERE TRIM("Mes") IN (%s, %s)
          {prov_where}
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        GROUP BY TRIM("Cliente / Proveedor")
        ORDER BY Diferencia DESC
    """

    params = (
        mes1, mes2,
        mes2, mes1,
        mes1, mes2,
        *prov_param
    )

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


# =========================
# REEMPLAZAR EN sql_queries.py
# Buscar get_comparacion_proveedor_anios_like (línea ~950-1000)
# =========================

def get_comparacion_proveedor_anios_like(proveedor_like: str, anios: list[int]) -> pd.DataFrame:
    """
    ✅ VERSIÓN LIMITADA: Trae solo el proveedor con más compras que matchee el LIKE.
    
    Comparación por proveedor usando LIKE (ej: tresul, biodiagnostico, roche)
    
    Args:
        proveedor_like: Texto a buscar en nombre del proveedor (ej: "tresul")
        anios: Lista de años a comparar (mínimo 2)
    
    Returns:
        DataFrame con 1 fila: Proveedor, {año1}, {año2}
    """
    # Normalizar proveedor
    proveedor_like = proveedor_like.strip().lower()
    
    # Validar años
    anios = sorted(anios)
    if len(anios) < 2:
        print(f"⚠️ get_comparacion_proveedor_anios_like: necesita al menos 2 años, recibió {len(anios)}")
        return pd.DataFrame()
    
    a1, a2 = anios[0], anios[1]
    
    # Expresión SQL para convertir montos
    total_expr = _sql_total_num_expr_general()
    
    # ✅ QUERY LIMITADA A 1 PROVEEDOR (el que más compras tiene)
    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            SUM(CASE WHEN "Año"::int = %s THEN {total_expr} ELSE 0 END) AS "{a1}",
            SUM(CASE WHEN "Año"::int = %s THEN {total_expr} ELSE 0 END) AS "{a2}",
            SUM({total_expr}) AS total_general
        FROM chatbot_raw
        WHERE LOWER(TRIM("Cliente / Proveedor")) LIKE %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año"::int IN (%s, %s)
        GROUP BY TRIM("Cliente / Proveedor")
        ORDER BY total_general DESC  -- Ordenar por el que más compras tiene
        LIMIT 1  -- Solo traer el principal
    """
    
    # Parámetros con % para LIKE
    params = (
        a1,                        # primer año en CASE
        a2,                        # segundo año en CASE
        f"%{proveedor_like}%",     # LIKE con wildcards
        a1,                        # primer año en IN
        a2,                        # segundo año en IN
    )
    
    df = ejecutar_consulta(sql, params)
    
    # Eliminar la columna auxiliar total_general antes de retornar
    if df is not None and not df.empty and 'total_general' in df.columns:
        df = df.drop(columns=['total_general'])
    
    return df


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


# =====================================================================
# HELPERS SQL - FALLBACK DE MES
# =====================================================================

def get_ultimo_mes_disponible_hasta(mes_key: str) -> Optional[str]:
    """
    Devuelve el último mes disponible (YYYY-MM) menor o igual al mes_key.
    """
    sql = """
        SELECT MAX(TRIM("Mes")) AS mes
        FROM chatbot_raw
        WHERE TRIM("Mes") <= %s
    """
    df = ejecutar_consulta(sql, (mes_key,))
    if df is None or df.empty:
        return None
    return df["mes"].iloc[0]


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


# =====================================================================
# STOCK (SUPABASE / POSTGRES)
# =====================================================================

_STOCK_TABLE_CANDIDATES = [
    "stock_raw",
    "stock",
    "stocks",
    "stock_lotes",
    "lotes_stock",
    "estado_stock",
    "estado_mercaderia_stock",
    "estado_mercaderia",
]


def _safe_ident(name: str) -> str:
    """Sanitiza identificadores simples (schema / table / column)."""
    if not name:
        return ""
    name = name.strip()
    return name if re.match(r"^[A-Za-z0-9_]+$", name) else ""


def _get_stock_schema_table() -> tuple:
    """Obtiene schema y tabla de stock."""
    schema = st.secrets.get("STOCK_SCHEMA", os.getenv("STOCK_SCHEMA", "public"))
    schema = _safe_ident(schema) or "public"

    table = st.secrets.get("STOCK_TABLE", os.getenv("STOCK_TABLE", "")).strip()
    table = _safe_ident(table)

    if table:
        return schema, table

    try:
        sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type = 'BASE TABLE'
        """
        df = ejecutar_consulta(sql, (schema,))
        existing = set()
        if df is not None and not df.empty and "table_name" in df.columns:
            existing = set([str(x) for x in df["table_name"].tolist()])

        for t in _STOCK_TABLE_CANDIDATES:
            if t in existing:
                return schema, t

        return schema, "stock_raw"
    except Exception:
        return schema, "stock_raw"


def _get_stock_columns(schema: str, table: str) -> list:
    try:
        sql = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
        """
        df = ejecutar_consulta(sql, (schema, table))
        if df is None or df.empty or "column_name" not in df.columns:
            return []
        return [str(x) for x in df["column_name"].tolist()]
    except Exception:
        return []


def _pick_col(cols: list, candidates: list) -> str:
    """Devuelve el nombre REAL de la columna (con comillas) si existe."""
    if not cols:
        return ""

    col_map = {c.lower(): c for c in cols}
    for cand in candidates:
        key = str(cand).lower()
        if key in col_map:
            real = col_map[key]
            return f"\"{real}\""
    return ""


def _sql_date_expr_stock(col_expr: str) -> str:
    """Convierte una columna (texto/date) a DATE de forma robusta."""
    if not col_expr:
        return "NULL::date"

    return f"""
    (
      CASE
        WHEN NULLIF(TRIM({col_expr}::text), '') IS NULL THEN NULL::date
        WHEN TRIM({col_expr}::text) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}' THEN (TRIM({col_expr}::text))::date
        WHEN TRIM({col_expr}::text) ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$' THEN to_date(TRIM({col_expr}::text), 'DD/MM/YYYY')
        WHEN TRIM({col_expr}::text) ~ '^\\d{{2}}-\\d{{2}}-\\d{{4}}$' THEN to_date(TRIM({col_expr}::text), 'DD-MM-YYYY')
        ELSE NULL::date
      END
    )
    """


def _sql_num_expr_stock(col_expr: str) -> str:
    """Convierte una columna (texto/num) a numeric."""
    if not col_expr:
        return "NULL::numeric"

    return f"""
    NULLIF(
      regexp_replace(
        replace(
          replace(TRIM({col_expr}::text), '.', ''),
          ',', '.'
        ),
        '[^0-9\\.-]',
        '',
        'g'
      ),
      ''
    )::numeric
    """


def _stock_base_subquery() -> tuple:
    """Construye un subquery estándar con aliases esperados."""
    schema, table = _get_stock_schema_table()
    schema_s = _safe_ident(schema) or "public"
    table_s = _safe_ident(table) or "stock_raw"

    cols = _get_stock_columns(schema_s, table_s)

    c_art = _pick_col(cols, ["articulo", "Artículo", "ARTICULO", "insumo", "descripcion", "descripcion_articulo", "item"])
    c_fam = _pick_col(cols, ["familia", "FAMILIA", "sector", "seccion", "sección", "rubro"])
    c_dep = _pick_col(cols, ["deposito", "Depósito", "DEPOSITO", "ubicacion", "ubicación", "boca", "almacen", "almacén"])
    c_lot = _pick_col(cols, ["lote", "LOTE", "batch", "nro_lote", "numero_lote", "número_lote"])
    c_vto = _pick_col(cols, ["vencimiento", "VENCIMIENTO", "vto", "vence", "fecha_vencimiento", "fecha_vto", "fec_vto"])
    c_stk = _pick_col(cols, ["stock", "STOCK", "cantidad", "existencia", "saldo", "unidades"])
    c_cod = _pick_col(cols, ["codigo", "CODIGO", "id", "ID", "cod_articulo", "cod", "codigo_articulo"])

    art_expr = f"TRIM(COALESCE({c_art}::text,''))" if c_art else "''"
    fam_expr = f"TRIM(COALESCE({c_fam}::text,''))" if c_fam else "''"
    dep_expr = f"TRIM(COALESCE({c_dep}::text,''))" if c_dep else "''"
    lot_expr = f"TRIM(COALESCE({c_lot}::text,''))" if c_lot else "''"
    cod_expr = f"TRIM(COALESCE({c_cod}::text,''))" if c_cod else "''"

    vto_expr = _sql_date_expr_stock(c_vto)
    stk_expr = _sql_num_expr_stock(c_stk)

    full_table = f"\"{schema_s}\".\"{table_s}\""

    sub = f"""
        SELECT
            {cod_expr} AS "CODIGO",
            {art_expr} AS "ARTICULO",
            {fam_expr} AS "FAMILIA",
            {dep_expr} AS "DEPOSITO",
            {lot_expr} AS "LOTE",
            {vto_expr} AS "VENCIMIENTO",
            {stk_expr} AS "STOCK",
            CASE
              WHEN {vto_expr} IS NULL THEN NULL
              ELSE ({vto_expr} - CURRENT_DATE)
            END AS "Dias_Para_Vencer"
        FROM {full_table}
    """
    return sub, schema_s, table_s


def get_lista_articulos_stock() -> list:
    try:
        base, _, _ = _stock_base_subquery()
        sql = f"""
            SELECT DISTINCT "ARTICULO"
            FROM ({base}) s
            WHERE "ARTICULO" IS NOT NULL
              AND TRIM("ARTICULO") <> ''
            ORDER BY "ARTICULO"
            LIMIT 5000
        """
        df = ejecutar_consulta(sql, ())
        items = ["Todos"]
        if df is not None and not df.empty and "ARTICULO" in df.columns:
            items += [str(x) for x in df["ARTICULO"].tolist()]
        return items
    except Exception:
        return ["Todos"]


def get_lista_familias_stock() -> list:
    try:
        base, _, _ = _stock_base_subquery()
        sql = f"""
            SELECT DISTINCT "FAMILIA"
            FROM ({base}) s
            WHERE "FAMILIA" IS NOT NULL
              AND TRIM("FAMILIA") <> ''
            ORDER BY "FAMILIA"
            LIMIT 5000
        """
        df = ejecutar_consulta(sql, ())
        items = ["Todos"]
        if df is not None and not df.empty and "FAMILIA" in df.columns:
            items += [str(x) for x in df["FAMILIA"].tolist()]
        return items
    except Exception:
        return ["Todos"]


def get_lista_depositos_stock() -> list:
    try:
        base, _, _ = _stock_base_subquery()
        sql = f"""
            SELECT DISTINCT "DEPOSITO"
            FROM ({base}) s
            WHERE "DEPOSITO" IS NOT NULL
              AND TRIM("DEPOSITO") <> ''
            ORDER BY "DEPOSITO"
            LIMIT 5000
        """
        df = ejecutar_consulta(sql, ())
        items = ["Todos"]
        if df is not None and not df.empty and "DEPOSITO" in df.columns:
            items += [str(x) for x in df["DEPOSITO"].tolist()]
        return items
    except Exception:
        return ["Todos"]


def buscar_stock_por_lote(
    articulo: str = None,
    lote: str = None,
    familia: str = None,
    deposito: str = None,
    texto_busqueda: str = None
) -> pd.DataFrame:
    try:
        base, _, _ = _stock_base_subquery()

        where = []
        params = []

        if articulo:
            where.append("LOWER(COALESCE(\"ARTICULO\", '')) LIKE %s")
            params.append(f"%{articulo.lower().strip()}%")

        if familia:
            where.append("LOWER(COALESCE(\"FAMILIA\", '')) LIKE %s")
            params.append(f"%{familia.lower().strip()}%")

        if deposito:
            where.append("LOWER(COALESCE(\"DEPOSITO\", '')) LIKE %s")
            params.append(f"%{deposito.lower().strip()}%")

        if lote:
            where.append("LOWER(COALESCE(\"LOTE\", '')) LIKE %s")
            params.append(f"%{lote.lower().strip()}%")

        if texto_busqueda:
            t = texto_busqueda.lower().strip()
            where.append("""
                (
                  LOWER(COALESCE("ARTICULO", '')) LIKE %s OR
                  LOWER(COALESCE("LOTE", '')) LIKE %s OR
                  LOWER(COALESCE("CODIGO", '')) LIKE %s OR
                  LOWER(COALESCE("FAMILIA", '')) LIKE %s OR
                  LOWER(COALESCE("DEPOSITO", '')) LIKE %s
                )
            """)
            params.extend([f"%{t}%"] * 5)

        where_sql = "WHERE " + " AND ".join(where) if where else ""

        sql = f"""
            SELECT
                "CODIGO",
                "ARTICULO",
                "FAMILIA",
                "DEPOSITO",
                "LOTE",
                "VENCIMIENTO",
                "Dias_Para_Vencer",
                "STOCK"
            FROM ({base}) s
            {where_sql}
            ORDER BY "VENCIMIENTO" ASC NULLS LAST, "ARTICULO" ASC
            LIMIT 5000
        """
        return ejecutar_consulta(sql, tuple(params))
    except Exception:
        return pd.DataFrame()


def get_stock_total() -> pd.DataFrame:
    try:
        base, _, _ = _stock_base_subquery()
        sql = f"""
            SELECT
                COUNT(*) AS registros,
                COUNT(DISTINCT NULLIF(TRIM("ARTICULO"), '')) AS articulos,
                COUNT(DISTINCT NULLIF(TRIM("LOTE"), '')) AS lotes,
                COALESCE(SUM("STOCK"), 0) AS stock_total
            FROM ({base}) s
        """
        return ejecutar_consulta(sql, ())
    except Exception:
        return pd.DataFrame()


def get_stock_por_familia() -> pd.DataFrame:
    try:
        base, _, _ = _stock_base_subquery()
        sql = f"""
            SELECT
                COALESCE(NULLIF(TRIM("FAMILIA"), ''), 'SIN FAMILIA') AS familia,
                COUNT(*) AS registros,
                COUNT(DISTINCT NULLIF(TRIM("ARTICULO"), '')) AS articulos,
                COALESCE(SUM("STOCK"), 0) AS stock_total
            FROM ({base}) s
            GROUP BY COALESCE(NULLIF(TRIM("FAMILIA"), ''), 'SIN FAMILIA')
            ORDER BY stock_total DESC
        """
        return ejecutar_consulta(sql, ())
    except Exception:
        return pd.DataFrame()


def get_stock_por_deposito() -> pd.DataFrame:
    try:
        base, _, _ = _stock_base_subquery()
        sql = f"""
            SELECT
                COALESCE(NULLIF(TRIM("DEPOSITO"), ''), 'SIN DEPÓSITO') AS deposito,
                COUNT(*) AS registros,
                COUNT(DISTINCT NULLIF(TRIM("ARTICULO"), '')) AS articulos,
                COALESCE(SUM("STOCK"), 0) AS stock_total
            FROM ({base}) s
            GROUP BY COALESCE(NULLIF(TRIM("DEPOSITO"), ''), 'SIN DEPÓSITO')
            ORDER BY stock_total DESC
        """
        return ejecutar_consulta(sql, ())
    except Exception:
        return pd.DataFrame()


def get_stock_articulo(articulo: str) -> pd.DataFrame:
    try:
        base, _, _ = _stock_base_subquery()
        sql = f"""
            SELECT
                "CODIGO","ARTICULO","FAMILIA","DEPOSITO","LOTE","VENCIMIENTO","Dias_Para_Vencer","STOCK"
            FROM ({base}) s
            WHERE LOWER(COALESCE("ARTICULO", '')) LIKE %s
            ORDER BY "VENCIMIENTO" ASC NULLS LAST, "LOTE" ASC
        """
        return ejecutar_consulta(sql, (f"%{articulo.lower().strip()}%",))
    except Exception:
        return pd.DataFrame()


def get_lotes_por_vencer(dias: int = 90) -> pd.DataFrame:
    try:
        base, _, _ = _stock_base_subquery()
        sql = f"""
            SELECT
                "CODIGO","ARTICULO","FAMILIA","DEPOSITO","LOTE","VENCIMIENTO","Dias_Para_Vencer","STOCK"
            FROM ({base}) s
            WHERE "VENCIMIENTO" IS NOT NULL
              AND "VENCIMIENTO" >= CURRENT_DATE
              AND "VENCIMIENTO" <= (CURRENT_DATE + (%s || ' days')::interval)
              AND COALESCE("STOCK", 0) > 0
            ORDER BY "VENCIMIENTO" ASC
        """
        return ejecutar_consulta(sql, (int(dias),))
    except Exception:
        return pd.DataFrame()


def get_lotes_vencidos() -> pd.DataFrame:
    try:
        base, _, _ = _stock_base_subquery()
        sql = f"""
            SELECT
                "CODIGO","ARTICULO","FAMILIA","DEPOSITO","LOTE","VENCIMIENTO","Dias_Para_Vencer","STOCK"
            FROM ({base}) s
            WHERE "VENCIMIENTO" IS NOT NULL
              AND "VENCIMIENTO" < CURRENT_DATE
              AND COALESCE("STOCK", 0) > 0
            ORDER BY "VENCIMIENTO" DESC
        """
        return ejecutar_consulta(sql, ())
    except Exception:
        return pd.DataFrame()


def get_stock_bajo(minimo: int = 10) -> pd.DataFrame:
    """Devuelve registros con stock <= minimo (por defecto 10)."""
    try:
        base, _, _ = _stock_base_subquery()
        sql = f"""
            SELECT
                "CODIGO","ARTICULO","FAMILIA","DEPOSITO","LOTE","VENCIMIENTO","Dias_Para_Vencer","STOCK"
            FROM ({base}) s
            WHERE "STOCK" IS NOT NULL
              AND "STOCK" <= %s
            ORDER BY "STOCK" ASC NULLS LAST, "ARTICULO" ASC
        """
        return ejecutar_consulta(sql, (int(minimo),))
    except Exception:
        return pd.DataFrame()


def resolver_mes_existente(mes_key: str) -> str:
    """
    Si el mes existe, lo devuelve.
    Si no existe, devuelve el último mes disponible menor.
    """
    sql = """
        SELECT MAX(TRIM("Mes")) AS mes
        FROM chatbot_raw
        WHERE TRIM("Mes") <= %s
    """
    df = ejecutar_consulta(sql, (mes_key,))
    if df is None or df.empty or not df.iloc[0]["mes"]:
        return mes_key
    return df.iloc[0]["mes"]


def get_stock_lote_especifico(lote: str) -> pd.DataFrame:
    try:
        base, _, _ = _stock_base_subquery()
        sql = f"""
            SELECT
                "CODIGO","ARTICULO","FAMILIA","DEPOSITO","LOTE","VENCIMIENTO","Dias_Para_Vencer","STOCK"
            FROM ({base}) s
            WHERE LOWER(COALESCE("LOTE", '')) LIKE %s
            ORDER BY "VENCIMIENTO" ASC NULLS LAST, "ARTICULO" ASC
        """
        return ejecutar_consulta(sql, (f"%{lote.lower().strip()}%",))
    except Exception:
        return pd.DataFrame()


def get_stock_familia(familia: str) -> pd.DataFrame:
    try:
        base, _, _ = _stock_base_subquery()
        sql = f"""
            SELECT
                "CODIGO","ARTICULO","FAMILIA","DEPOSITO","LOTE","VENCIMIENTO","Dias_Para_Vencer","STOCK"
            FROM ({base}) s
            WHERE LOWER(COALESCE("FAMILIA", '')) LIKE %s
            ORDER BY "ARTICULO" ASC, "VENCIMIENTO" ASC NULLS LAST
        """
        return ejecutar_consulta(sql, (f"%{familia.lower().strip()}%",))
    except Exception:
        return pd.DataFrame()


def get_alertas_vencimiento_multiple(limite: int = 10) -> list:
    """Alertas rotativas de vencimiento para el módulo Stock IA."""
    try:
        df = get_lotes_por_vencer(dias=90)
        if df is None or df.empty:
            return []

        if "VENCIMIENTO" in df.columns:
            df = df.sort_values(by="VENCIMIENTO", ascending=True, na_position="last")

        df = df.head(int(limite))

        alertas = []
        for _, r in df.iterrows():
            alertas.append({
                "articulo": str(r.get("ARTICULO", "") or ""),
                "lote": str(r.get("LOTE", "") or ""),
                "deposito": str(r.get("DEPOSITO", "") or ""),
                "vencimiento": str(r.get("VENCIMIENTO", "") or ""),
                "dias_restantes": int(r.get("Dias_Para_Vencer", 0) or 0),
                "stock": str(r.get("STOCK", "") or "")
            })
        return alertas
    except Exception:
        return []


# FIN DEL ARCHIVO
