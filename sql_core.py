# =========================
# SQL CORE - CONEXIÓN Y HELPERS COMPARTIDOS
# =========================

import os
import re
import pandas as pd
from typing import Optional, List
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

def _safe_ident(col_name: str) -> str:
    """
    Escapa un nombre de columna para usar en SQL de forma segura.
    Envuelve el nombre en comillas dobles para Postgres.

    Parámetros:
    - col_name: str, nombre de la columna

    Retorna:
    - str con el nombre escapado entre comillas dobles
    """
    # Remover comillas existentes y espacios en blanco
    clean = str(col_name).strip().strip('"')
    # Envolver en comillas dobles para Postgres
    return f'"{clean}"'


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
# LISTADOS GENÉRICOS - CHATBOT_RAW
# =====================================================================

def get_valores_unicos(
    tabla: str,
    columna: str,
    incluir_todos: bool = True,
    label_todos: str = "Todos",
    limite: int = 500
) -> list:
    """
    Devuelve valores únicos (TRIM) de una columna en una tabla.
    Pensada para armar filtros/selector sin romper imports existentes.

    Parámetros:
    - tabla: nombre de la tabla (ej: 'chatbot_raw')
    - columna: nombre de la columna (ej: 'Cliente / Proveedor')
    - incluir_todos: si True, antepone label_todos al listado
    - label_todos: texto del primer item (por defecto 'Todos')
    - limite: máximo de valores

    Retorna:
    - list[str]
    """
    try:
        # Sanitización mínima del nombre de tabla (evita caracteres raros)
        t = str(tabla).strip().strip('"')
        if not re.fullmatch(r"[A-Za-z0-9_]+", t):
            print(f"⚠️ Tabla inválida para get_valores_unicos: {tabla}")
            return [label_todos] if incluir_todos else []

        col_sql = _safe_ident(columna)
        tabla_sql = f'"{t}"'

        sql = f"""
            SELECT DISTINCT TRIM({col_sql}) AS valor
            FROM {tabla_sql}
            WHERE {col_sql} IS NOT NULL AND TRIM({col_sql}) <> ''
            ORDER BY valor
            LIMIT %s
        """
        df = ejecutar_consulta(sql, (int(limite),))

        if df.empty:
            return [label_todos] if incluir_todos else []

        vals = df["valor"].dropna().astype(str).tolist()
        return ([label_todos] + vals) if incluir_todos else vals

    except Exception as e:
        print(f"❌ Error en get_valores_unicos: {e}")
        return [label_todos] if incluir_todos else []


def get_lista_proveedores() -> list:
    """Obtiene lista de proveedores únicos."""
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


def get_lista_articulos() -> list:
    """Obtiene lista de artículos únicos de chatbot_raw."""
    sql = """
        SELECT DISTINCT TRIM("Articulo") AS articulo
        FROM chatbot_raw
        WHERE "Articulo" IS NOT NULL AND TRIM("Articulo") <> ''
        ORDER BY articulo
        LIMIT 500
    """
    df = ejecutar_consulta(sql)
    if df.empty:
        print("⚠️ No se encontraron artículos en la base de datos.")
        return ["Todos"]
    return ["Todos"] + df['articulo'].tolist()


def get_lista_familias() -> list:
    """Obtiene lista de familias únicas de chatbot_raw."""
    sql = """
        SELECT DISTINCT TRIM("Familia") AS familia
        FROM chatbot_raw
        WHERE "Familia" IS NOT NULL AND TRIM("Familia") <> ''
        ORDER BY familia
        LIMIT 500
    """
    df = ejecutar_consulta(sql)
    if df.empty:
        print("⚠️ No se encontraron familias en la base de datos.")
        return ["Todos"]
    return ["Todos"] + df['familia'].tolist()


def get_lista_tipos_comprobante() -> list:
    """Obtiene lista de tipos de comprobante únicos."""
    sql = """
        SELECT DISTINCT TRIM("Tipo Comprobante") AS tipo
        FROM chatbot_raw
        WHERE "Tipo Comprobante" IS NOT NULL AND TRIM("Tipo Comprobante") <> ''
        ORDER BY tipo
        LIMIT 100
    """
    df = ejecutar_consulta(sql)
    if df.empty:
        print("⚠️ No se encontraron tipos de comprobante.")
        return ["Todos"]
    return ["Todos"] + df['tipo'].tolist()


def get_lista_monedas() -> list:
    """Obtiene lista de monedas únicas."""
    sql = """
        SELECT DISTINCT TRIM("Moneda") AS moneda
        FROM chatbot_raw
        WHERE "Moneda" IS NOT NULL AND TRIM("Moneda") <> ''
        ORDER BY moneda
    """
    df = ejecutar_consulta(sql)
    if df.empty:
        return ["Todas", "$", "U$S"]
    return ["Todas"] + df['moneda'].tolist()


def get_lista_anios() -> list:
    """Obtiene lista de años disponibles."""
    sql = """
        SELECT DISTINCT "Año"::int AS anio
        FROM chatbot_raw
        WHERE "Año" IS NOT NULL AND "Año" <> ''
        ORDER BY anio DESC
    """
    df = ejecutar_consulta(sql)
    if df.empty:
        print("⚠️ No se encontraron años en la base de datos.")
        return []
    return df['anio'].tolist()


def get_lista_meses() -> list:
    """Obtiene lista de meses disponibles ordenados."""
    sql = """
        SELECT DISTINCT TRIM("Mes") AS mes
        FROM chatbot_raw
        WHERE "Mes" IS NOT NULL AND TRIM("Mes") <> ''
        ORDER BY mes
    """
    df = ejecutar_consulta(sql)
    if df.empty:
        print("⚠️ No se encontraron meses en la base de datos.")
        return []
    return df['mes'].tolist()


# =====================================================================
# LISTADOS GENÉRICOS - STOCK_RAW
# =====================================================================

def get_lista_articulos_stock() -> list:
    """Obtiene lista de artículos únicos de stock_raw."""
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
    """Obtiene lista de familias únicas de stock_raw."""
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


def get_lista_depositos_stock() -> list:
    """Obtiene lista de depósitos únicos de stock_raw."""
    sql = """
        SELECT DISTINCT TRIM("Deposito") AS deposito
        FROM stock_raw
        WHERE "Deposito" IS NOT NULL AND TRIM("Deposito") <> ''
        ORDER BY deposito
        LIMIT 100
    """
    df = ejecutar_consulta(sql)
    if df.empty:
        print("⚠️ No se encontraron depósitos en el stock.")
        return ["Todos"]
    return ["Todos"] + df['deposito'].tolist()


# =====================================================================
# BÚSQUEDA EN STOCK POR LOTE
# =====================================================================

def buscar_stock_por_lote(
    articulo: str = None,
    lote: str = None,
    familia: str = None,
    deposito: str = None,
    texto_busqueda: str = None
) -> pd.DataFrame:
    """Busca registros en stock_raw por lote y otros filtros."""
    try:
        sql = """
            SELECT 
                TRIM("Articulo") AS "Artículo",
                TRIM("Lote") AS "Lote",
                TRIM("Vencimiento") AS "Vencimiento",
                TRIM("STOCK") AS "STOCK",
                TRIM("Familia") AS "Familia",
                TRIM("Deposito") AS "Depósito"
            FROM stock_raw
            WHERE 1=1
        """
        params = []

        if articulo:
            sql += ' AND LOWER(TRIM("Articulo")) LIKE LOWER(%s)'
            params.append(f"%{articulo}%")

        if lote and lote.strip():
            sql += ' AND LOWER(TRIM("Lote")) LIKE LOWER(%s)'
            params.append(f"%{lote.strip()}%")

        if familia:
            sql += ' AND LOWER(TRIM("Familia")) LIKE LOWER(%s)'
            params.append(f"%{familia}%")

        if deposito:
            sql += ' AND LOWER(TRIM("Deposito")) LIKE LOWER(%s)'
            params.append(f"%{deposito}%")

        if texto_busqueda and texto_busqueda.strip():
            txt = texto_busqueda.strip()
            sql += """
                AND (
                    LOWER("Articulo") LIKE LOWER(%s) OR
                    LOWER("Lote") LIKE LOWER(%s) OR
                    LOWER("Familia") LIKE LOWER(%s)
                )
            """
            params.extend([f"%{txt}%", f"%{txt}%", f"%{txt}%"])

        sql += ' ORDER BY "Vencimiento" ASC LIMIT 500'

        return ejecutar_consulta(sql, tuple(params) if params else None)

    except Exception as e:
        print(f"❌ Error en buscar_stock_por_lote: {e}")
        return pd.DataFrame()


# =====================================================================
# FUNCIÓN PARA OBTENER ÚLTIMO MES DISPONIBLE
# =====================================================================

def get_ultimo_mes_disponible_hasta(mes_key: str) -> Optional[str]:
    """
    Busca el último mes disponible en la tabla chatbot_raw hasta el mes indicado.

    Parámetros:
    - mes_key: str, formato esperado "YYYY-MM" o "Mes YYYY"

    Retorna:
    - str con el mes anterior disponible o None si no hay datos
    """
    try:
        sql = """
            SELECT DISTINCT TRIM("Mes") AS mes
            FROM chatbot_raw
            WHERE TRIM("Mes") IS NOT NULL 
              AND TRIM("Mes") <> ''
              AND TRIM("Mes") <= %s
            ORDER BY TRIM("Mes") DESC
            LIMIT 1
        """
        df = ejecutar_consulta(sql, (mes_key,))

        if df.empty:
            print(f"⚠️ No se encontró mes disponible hasta {mes_key}")
            return None

        mes_encontrado = df['mes'].iloc[0]
        print(f"✅ Último mes disponible hasta {mes_key}: {mes_encontrado}")
        return mes_encontrado

    except Exception as e:
        print(f"❌ Error buscando último mes disponible: {e}")
        return None


# =====================================================================
# DEPURACIÓN ADICIONAL EN STOCK Y ALERTAS
# =====================================================================

def get_lotes_por_vencer(dias: int) -> pd.DataFrame:
    """Obtiene lotes que vencen dentro de X días."""
    sql = """
        SELECT TRIM("Articulo") AS articulo, 
               TRIM("Lote") AS lote, 
               TRIM("Vencimiento") AS vencimiento, 
               TRIM("STOCK") AS stock,
               DATE_PART('day', TRIM("Vencimiento")::date - NOW()::date) AS dias_restantes
        FROM stock_raw
        WHERE DATE_PART('day', TRIM("Vencimiento")::date - NOW()::date) <= %s
        ORDER BY dias_restantes
    """
    df = ejecutar_consulta(sql, (dias,))
    if df.empty:
        print(f"⚠️ No se encontraron lotes por vencer dentro de {dias} días.")
    return df


# =====================================================================
# FIN DEL ARCHIVO
# =====================================================================
