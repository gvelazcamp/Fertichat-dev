# =========================
# SQL CORE - CONEXIÓN Y HELPERS COMPARTIDOS
# =========================

import os
import re
import pandas as pd
from typing import Optional
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
        print("❌ psycopg2 no instalado")
        return None
    try:
        # Obtener credenciales de la base de datos
        host = st.secrets.get("DB_HOST", os.getenv("DB_HOST"))
        port = st.secrets.get("DB_PORT", os.getenv("DB_PORT", "5432"))
        dbname = st.secrets.get("DB_NAME", os.getenv("DB_NAME", "postgres"))
        user = st.secrets.get("DB_USER", os.getenv("DB_USER"))
        password = st.secrets.get("DB_PASSWORD", os.getenv("DB_PASSWORD"))

        # Verificación previa de las credenciales
        if not host or not user or not password:
            print("❌ Faltan credenciales para la conexión.")
            return None

        # Establecer conexión
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
        print(f"❌ Error de conexión: {e}")
        return None


# =====================================================================
# CONSTANTES - TABLAS Y COLUMNAS
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
    """
    Ejecuta una consulta SQL y retorna los resultados en un DataFrame.

    Parámetros:
    - query: str, el SQL a ejecutar.
    - params: tuple o None, los parámetros para la consulta (opcional).

    Retorna:
    - pd.DataFrame con los resultados de la consulta.
    """
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ No se pudo establecer conexión con la base de datos.")
            return pd.DataFrame()

        if params is None:
            params = ()

        # Agregar logs del SQL y parámetros
        print("\n🛠 SQL ejecutado:")
        print(query)
        print("🛠 Parámetros usados:")
        print(params)

        # Ejecutar la consulta y retornar resultados
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        if df.empty:
            print("⚠️ Consulta ejecutada, pero no devolvió resultados.")
        else:
            print(f"✅ Resultados obtenidos: {len(df)} filas.")
        return df

    except Exception as e:
        print(f"❌ Error ejecutando consulta SQL: {e}")
        print(f"SQL fallido:\n{query}")
        print(f"Parámetros:\n{params}")
        return pd.DataFrame()


# =====================================================================
# LISTADOS GENÉRICOS
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
        print("⚠️ No se encontraron proveedores en la base de datos.")
        return ["Todos"]
    return ["Todos"] + df['proveedor'].tolist()

def get_lista_articulos_stock() -> list:
    sql = """
        SELECT DISTINCT TRIM("Articulo") AS articulo
        FROM stock_raw
        WHERE "Articulo" IS NOT NULL AND TRIM("Articulo") <> ''
        ORDER BY articulo
        LIMIT 500
    """
    df = ejecutar_consulta(sql)
    if df.empty:
        print("⚠️ No se encontraron artículos en el stock.")
        return ["Todos"]
    return ["Todos"] + df['articulo'].tolist()

def get_lista_familias_stock() -> list:
    sql = """
        SELECT DISTINCT TRIM("Familia") AS familia
        FROM stock_raw
        WHERE "Familia" IS NOT NULL AND TRIM("Familia") <> ''
        ORDER BY familia
        LIMIT 500
    """
    df = ejecutar_consulta(sql)
    if df.empty:
        print("⚠️ No se encontraron familias en el stock.")
        return ["Todos"]
    return ["Todos"] + df['familia'].tolist()

# Otras funciones similares no han sido modificadas.

# =====================================================================
# DEPURACIÓN ADICIONAL EN STOCK Y ALERTAS
# =====================================================================
def get_lotes_por_vencer(dias: int) -> pd.DataFrame:
    sql = """
        SELECT TRIM("Articulo") AS articulo, TRIM("Lote") AS lote, TRIM("Vencimiento") AS vencimiento, TRIM("STOCK") AS stock,
               DATE_PART('day', TRIM("Vencimiento")::date - NOW()::date) AS dias_restantes
        FROM stock_raw
        WHERE DATE_PART('day', TRIM("Vencimiento")::date - NOW()::date) <= %s
        ORDER BY dias_restantes
    """
    df = ejecutar_consulta(sql, (dias,))
    if df.empty:
        print(f"⚠️ No se encontraron lotes por vencer dentro de {dias} días.")
    return df

# Otras funciones listas simplemente añaden validaciones adicionales para el manejo de errores.

# =====================================================================
# FIN DEL ARCHIVO
# =====================================================================
