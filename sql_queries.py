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
    """Conexión a Postgres (Supabase) usando Secrets/Env vars - CON DEBUG."""
    try:
        host = st.secrets.get("DB_HOST", os.getenv("DB_HOST"))
        port = st.secrets.get("DB_PORT", os.getenv("DB_PORT", "5432"))
        dbname = st.secrets.get("DB_NAME", os.getenv("DB_NAME", "postgres"))
        user = st.secrets.get("DB_USER", os.getenv("DB_USER"))
        password = st.secrets.get("DB_PASSWORD", os.getenv("DB_PASSWORD"))

        # 🔍 DEBUG - Ver qué valores tiene
        st.info(f"🔍 HOST: {host}")
        st.info(f"🔍 PORT: {port}")
        st.info(f"🔍 DBNAME: {dbname}")
        st.info(f"🔍 USER: {user}")
        st.info(f"🔍 PASS: {'****' if password else 'NONE'}")

        if not host or not user or not password:
            st.error("❌ Faltan credenciales de DB")
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
        
        st.success("✅ Conexión establecida")
        return conn
        
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None


# =====================================================================
# TABLAS + COLUMNAS REALES (según tu screenshot en Supabase)
# =====================================================================

TABLE_COMPRAS = "chatbot_raw"

# OJO: en Postgres, columnas con espacios/puntos van siempre entre comillas dobles.
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

# =========================
# LISTADOS (SIDEBAR)
# =========================
def get_lista_proveedores() -> list[str]:
    """Devuelve proveedores DISTINCT desde la tabla chatbot_raw."""
    conn = get_db_connection()
    if conn is None:
        return []

    try:
        with conn.cursor() as cur:
            sql = f"""
                SELECT DISTINCT TRIM({COL_PROV}) AS proveedor
                FROM {TABLE_COMPRAS}
                WHERE {COL_PROV} IS NOT NULL
                  AND TRIM({COL_PROV}) <> ''
                ORDER BY proveedor
            """
            cur.execute(sql)
            rows = cur.fetchall()
            return [r['proveedor'] for r in rows if r['proveedor']]

    except Exception as e:
        st.error(f"Error get_lista_proveedores: {e}")
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_lista_tipos_comprobante() -> list[str]:
    """Devuelve tipos de comprobante DISTINCT."""
    conn = get_db_connection()
    if conn is None:
        return ["Todos"]

    try:
        with conn.cursor() as cur:
            sql = f"""
                SELECT DISTINCT TRIM({COL_TIPO_COMP}) AS tipo
                FROM {TABLE_COMPRAS}
                WHERE {COL_TIPO_COMP} IS NOT NULL
                  AND TRIM({COL_TIPO_COMP}) <> ''
                ORDER BY tipo
            """
            cur.execute(sql)
            rows = cur.fetchall()
            tipos = [r['tipo'] for r in rows if r['tipo']]
            return ["Todos"] + tipos

    except Exception:
        return ["Todos"]
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_lista_articulos() -> list[str]:
    """Devuelve artículos DISTINCT."""
    conn = get_db_connection()
    if conn is None:
        return ["Todos"]

    try:
        with conn.cursor() as cur:
            sql = f"""
                SELECT DISTINCT TRIM({COL_ART}) AS articulo
                FROM {TABLE_COMPRAS}
                WHERE {COL_ART} IS NOT NULL
                  AND TRIM({COL_ART}) <> ''
                ORDER BY articulo
                LIMIT 500
            """
            cur.execute(sql)
            rows = cur.fetchall()
            arts = [r['articulo'] for r in rows if r['articulo']]
            return ["Todos"] + arts

    except Exception:
        return ["Todos"]
    finally:
        try:
            conn.close()
        except Exception:
            pass


# =====================================================================
# HELPERS SQL (POSTGRES)
# =====================================================================

def _sql_fecha_expr() -> str:
    """Convierte Fecha (texto) a DATE (YYYY-MM-DD o DD/MM/YYYY)."""
    return f"COALESCE(TO_DATE({COL_FECHA}, 'YYYY-MM-DD'), TO_DATE({COL_FECHA}, 'DD/MM/YYYY'))"


def _sql_mes_col() -> str:
    return f"TRIM(COALESCE({COL_MES}, ''))"


def _sql_moneda_norm_expr() -> str:
    return f"TRIM(COALESCE({COL_MONEDA}, ''))"


def _sql_year_expr() -> str:
    """Año robusto: usa columna Año si existe, sino lo extrae de Fecha."""
    return f"COALESCE({COL_ANIO}, EXTRACT(YEAR FROM {_sql_fecha_expr()})::int)"


def _sql_num_from_text(text_expr: str) -> str:
    """CAST defensivo: evita error si queda string vacío."""
    return f"CAST(NULLIF({text_expr}, '') AS NUMERIC(15,2))"


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
    """Convierte Monto Neto a número (USD: U$S / U$$)."""
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
    """Convierte Monto Neto a número (sirve para $ o U$S/U$$)."""
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
    """Convierte Cantidad (texto) a número."""
    limpio = f"REPLACE(TRIM(COALESCE({COL_CANT}, '')), ',', '.')"
    return _sql_num_from_text(limpio)


# =====================================================================
# ADAPTAR WHERE_CLAUSE (compatibilidad con orquestadores viejos)
# =====================================================================

def _adapt_where_clause(where_clause: str) -> str:
    if not where_clause or not str(where_clause).strip():
        return "1=1"

    m: Dict[str, str] = {
        "Proveedor": COL_PROV,
        "Articulo": COL_ART,
        "Familia": COL_FAMILIA,
        "Mes": COL_MES,
        "Moneda": COL_MONEDA,
        "tipo_comprobante": COL_TIPO_COMP,
        "Tipo_Comprobante": COL_TIPO_COMP,
        "nro_comprobante": COL_NRO_COMP,
        "Nro_Comprobante": COL_NRO_COMP,
        "Nro_Factura": COL_NRO_COMP,
        "fecha": COL_FECHA,
        "Fecha": COL_FECHA,
        "cantidad": COL_CANT,
        "Cantidad": COL_CANT,
        "anio": COL_ANIO,
        "Año": COL_ANIO,
        "Anio": COL_ANIO,
        "Monto Neto": COL_MONTO,
        "Monto_Neto": COL_MONTO,
    }

    out = str(where_clause)
    for k, v in m.items():
        out = re.sub(rf"(?i)\b{re.escape(k)}\b", v, out)
    return out


# =====================================================================
# LOGGING (si existen tablas query_log / chat_log)
# =====================================================================

def _guardar_log(consulta: str, parametros: str, resultado: str, registros: int, error: str, tiempo_ms: int):
    try:
        conn = get_db_connection()
        if not conn:
            return
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO query_log (consulta, parametros, resultado, registros, error, tiempo_ms)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            consulta_corta = (consulta or "")[:2000]
            error_corto = (error or "")[:500] if error else None
            cursor.execute(sql, (consulta_corta, parametros, resultado, registros, error_corto, tiempo_ms))
            conn.commit()
        conn.close()
    except Exception:
        pass


def guardar_chat_log(pregunta: str, intencion: str, respuesta: str, tuvo_datos: bool, registros: int = 0, debug: str = None):
    try:
        conn = get_db_connection()
        if not conn:
            return
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO chat_log (pregunta, intencion, respuesta, tuvo_datos, registros, debug)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            pregunta_corta = (pregunta or "")[:1000]
            respuesta_corta = (respuesta or "")[:2000]
            debug_corto = (debug or "")[:500] if debug else None
            cursor.execute(sql, (pregunta_corta, intencion, respuesta_corta, tuvo_datos, registros, debug_corto))
            conn.commit()
        conn.close()
    except Exception:
        pass


# =====================================================================
# EJECUTOR SQL (POSTGRES)
# =====================================================================

def ejecutar_consulta(query: str, params: tuple = None) -> pd.DataFrame:
    """Ejecuta consulta SQL y retorna DataFrame (con logging)."""
    conn = get_db_connection()
    if not conn:
        _guardar_log(query, str(params), "ERROR", 0, "No se pudo conectar", 0)
        return pd.DataFrame()

    inicio = time.time()
    try:
        if params is None:
            params = ()

        with conn.cursor() as cursor:
            cursor.execute(query, params)
            data = cursor.fetchall()

        tiempo_ms = int((time.time() - inicio) * 1000)

        if not data:
            _guardar_log(query, str(params), "OK", 0, None, tiempo_ms)
            return pd.DataFrame()

        df = pd.DataFrame(data)
        _guardar_log(query, str(params), "OK", len(df), None, tiempo_ms)
        return df

    except Exception as e:
        tiempo_ms = int((time.time() - inicio) * 1000)
        _guardar_log(query, str(params), "ERROR", 0, str(e), tiempo_ms)
        print(f"Error en consulta SQL: {e}")
        return pd.DataFrame()

    finally:
        try:
            conn.close()
        except Exception:
            pass


# =====================================================================
# CONSULTAS ESPECÍFICAS - ORDEN DE PRIORIDAD
# =====================================================================

# --- PRIORIDAD 1: FACTURA POR NÚMERO ---

def get_detalle_factura_por_numero(nro_factura: str) -> pd.DataFrame:
    total_expr = _sql_total_num_expr_general()
    query = f"""
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
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%')
        ORDER BY TRIM({COL_ART})
    """
    return ejecutar_consulta(query, (nro_factura,))


# --- PRIORIDAD 2: ÚLTIMA FACTURA DE ARTÍCULO ---

def get_ultima_factura_de_articulo(patron_articulo: str) -> pd.DataFrame:
    total_expr = _sql_total_num_expr_general()
    fecha_expr = _sql_fecha_expr()
    query = f"""
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
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%')
        ORDER BY {fecha_expr} DESC NULLS LAST
        LIMIT 1
    """
    return ejecutar_consulta(query, (f"%{patron_articulo.lower()}%",))


def get_ultima_factura_inteligente(patron: str) -> pd.DataFrame:
    """Busca última factura por artículo O proveedor."""
    total_expr = _sql_total_num_expr_general()
    fecha_expr = _sql_fecha_expr()
    
    # Primero intentar como artículo
    query_art = f"""
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
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%')
        ORDER BY {fecha_expr} DESC NULLS LAST
        LIMIT 1
    """
    df = ejecutar_consulta(query_art, (f"%{patron.lower()}%",))
    
    if df is not None and not df.empty:
        return df
    
    # Si no encontró como artículo, intentar como proveedor
    query_prov = f"""
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
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%')
        ORDER BY {fecha_expr} DESC NULLS LAST
        LIMIT 1
    """
    return ejecutar_consulta(query_prov, (f"%{patron.lower()}%",))


def get_ultima_factura_numero_de_articulo(patron_articulo: str) -> Optional[str]:
    fecha_expr = _sql_fecha_expr()
    query = f"""
        SELECT TRIM({COL_NRO_COMP}) AS nro_factura
        FROM {TABLE_COMPRAS}
        WHERE LOWER(TRIM({COL_ART})) LIKE %s
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%')
        ORDER BY {fecha_expr} DESC NULLS LAST
        LIMIT 1
    """
    df = ejecutar_consulta(query, (f"%{patron_articulo.lower()}%",))
    if df.empty:
        return None
    nro = str(df["nro_factura"].iloc[0]).strip()
    return nro if nro else None


# --- PRIORIDAD 3: FACTURAS DE ARTÍCULO ---

def get_facturas_de_articulo(patron_articulo: str, solo_ultima: bool = False) -> pd.DataFrame:
    fecha_expr = _sql_fecha_expr()
    total_expr = _sql_total_num_expr_general()
    limit_sql = "LIMIT 1" if solo_ultima else "LIMIT 50"

    query = f"""
        SELECT
            TRIM({COL_PROV}) AS Proveedor,
            TRIM({COL_ART}) AS Articulo,
            TRIM({COL_NRO_COMP}) AS Nro_Factura,
            TO_CHAR({fecha_expr}, 'DD/MM/YYYY') AS Fecha,
            {COL_CANT} AS Cantidad,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS Total
        FROM {TABLE_COMPRAS}
        WHERE ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%')
          AND LOWER(TRIM({COL_ART})) LIKE %s
        ORDER BY {fecha_expr} DESC NULLS LAST
        {limit_sql}
    """
    return ejecutar_consulta(query, (f"%{patron_articulo.lower()}%",))


# --- PRIORIDAD 4: COMPARACIONES (MESES) ---

def get_comparacion_familia_meses(mes1: str, mes2: str, label1: str, label2: str, familias: List[str] = None) -> pd.DataFrame:
    total_expr = _sql_total_num_expr_general()
    mes_col = _sql_mes_col()

    familia_where = ""
    familia_params = []
    if familias:
        parts = []
        for fam in familias:
            parts.append(f"TRIM(COALESCE({COL_FAMILIA}, '')) = %s")
            familia_params.append(fam)
        familia_where = f"AND ({' OR '.join(parts)})"

    query = f"""
        SELECT
            TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA')) AS Familia,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Mes1,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Mes2,
            (
                SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END)
                -
                SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END)
            ) AS comparacion,
            CASE
                WHEN SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) = 0
                THEN NULL
                ELSE
                    (
                        (
                            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END)
                            -
                            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END)
                        )
                        /
                        SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END)
                    ) * 100
            END AS variacion_pct
        FROM {TABLE_COMPRAS}
        WHERE {mes_col} IN (%s, %s)
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%')
          {familia_where}
        GROUP BY TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA'))
        ORDER BY comparacion DESC
    """

    params = (
        mes1, mes2, mes2, mes1,
        mes1, mes2, mes1, mes1,
        mes1, mes2,
        *familia_params
    )
    df = ejecutar_consulta(query, params)
    if df.empty:
        return df
    return df.rename(columns={"Mes1": label1, "Mes2": label2})


def get_comparacion_familia_meses_moneda(mes1: str, mes2: str, label1: str, label2: str, moneda: str = "$", familias: List[str] = None) -> pd.DataFrame:
    mes_col = _sql_mes_col()
    mon_expr = _sql_moneda_norm_expr()

    mon = (moneda or "$").strip().upper()
    if mon in ("U$S", "U$$", "USD"):
        total_expr = _sql_total_num_expr_usd()
        mon_filter = f"{mon_expr} IN ('U$S', 'U$$')"
    else:
        total_expr = _sql_total_num_expr()
        mon_filter = f"{mon_expr} = '$'"

    familia_where = ""
    familia_params = []
    if familias:
        parts = []
        for fam in familias:
            parts.append(f"TRIM(COALESCE({COL_FAMILIA}, '')) = %s")
            familia_params.append(fam)
        familia_where = f"AND ({' OR '.join(parts)})"

    inner = f"""
        SELECT
            TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA')) AS Familia,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Mes1,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Mes2
        FROM {TABLE_COMPRAS}
        WHERE {mes_col} IN (%s, %s)
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%')
          AND {mon_filter}
          {familia_where}
        GROUP BY TRIM(COALESCE({COL_FAMILIA}, 'SIN FAMILIA'))
    """

    query = f"""
        SELECT
            t.Familia,
            t.Mes1,
            t.Mes2,
            (t.Mes2 - t.Mes1) AS Diferencia,
            CASE
                WHEN t.Mes1 = 0 THEN NULL
                ELSE ROUND(((t.Mes2 - t.Mes1) / t.Mes1) * 100, 1)
            END AS Variacion_Pct
        FROM ({inner}) t
        WHERE t.Mes1 > 0 OR t.Mes2 > 0
        ORDER BY Diferencia DESC
    """

    params = (mes1, mes2, mes1, mes2, *familia_params)
    df = ejecutar_consulta(query, params)
    if df.empty:
        return df
    return df.rename(columns={"Mes1": label1, "Mes2": label2})


def get_comparacion_proveedor_meses(mes1: str, mes2: str, label1: str, label2: str, proveedores: List[str] = None) -> pd.DataFrame:
    total_expr = _sql_total_num_expr_general()
    mes_col = _sql_mes_col()

    prov_where = ""
    prov_params: List[str] = []
    if proveedores:
        parts = []
        for p in proveedores:
            parts.append(f"LOWER(TRIM({COL_PROV})) LIKE %s")
            prov_params.append(f"%{p.lower()}%")
        prov_where = f"AND ({' OR '.join(parts)})"

    inner = f"""
        SELECT
            TRIM({COL_PROV}) AS Concepto,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Mes1,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Mes2
        FROM {TABLE_COMPRAS}
        WHERE {mes_col} IN (%s, %s)
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%')
          {prov_where}
        GROUP BY TRIM({COL_PROV})
    """

    query = f"""
        SELECT
            t.Concepto,
            t.Mes1 AS "{label1}",
            t.Mes2 AS "{label2}",
            (t.Mes2 - t.Mes1) AS Diferencia,
            CASE
                WHEN t.Mes1 = 0 THEN NULL
                ELSE ((t.Mes2 - t.Mes1) / t.Mes1) * 100
            END AS Variacion_pct
        FROM ({inner}) t
        WHERE t.Mes1 <> 0 OR t.Mes2 <> 0
        ORDER BY Diferencia DESC
    """

    params = (mes1, mes2, mes1, mes2, *prov_params)
    return ejecutar_consulta(query, tuple(params))


def get_comparacion_articulo_meses(mes1: str, mes2: str, label1: str, label2: str, articulos: List[str] = None) -> pd.DataFrame:
    total_expr = _sql_total_num_expr_general()
    mes_col = _sql_mes_col()

    art_where = ""
    art_params: List[str] = []
    if articulos:
        parts = []
        for a in articulos:
            parts.append(f"LOWER(TRIM({COL_ART})) LIKE %s")
            art_params.append(f"%{a.lower()}%")
        art_where = f"AND ({' OR '.join(parts)})"

    inner = f"""
        SELECT
            TRIM({COL_ART}) AS Concepto,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Mes1,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Mes2
        FROM {TABLE_COMPRAS}
        WHERE {mes_col} IN (%s, %s)
          AND ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%')
          {art_where}
        GROUP BY TRIM({COL_ART})
    """

    query = f"""
        SELECT
            t.Concepto,
            t.Mes1 AS "{label1}",
            t.Mes2 AS "{label2}",
            (t.Mes2 - t.Mes1) AS Diferencia,
            CASE
                WHEN t.Mes1 = 0 THEN NULL
                ELSE ((t.Mes2 - t.Mes1) / t.Mes1) * 100
            END AS Variacion_pct
        FROM ({inner}) t
        WHERE t.Mes1 <> 0 OR t.Mes2 <> 0
        ORDER BY Diferencia DESC
        LIMIT 200
    """

    params = (mes1, mes2, mes1, mes2, *art_params)
    return ejecutar_consulta(query, tuple(params))


# --- PRIORIDAD 5: COMPARACIONES POR AÑOS ---

def get_comparacion_proveedor_anios_monedas(anios: List[int], proveedores: List[str] = None) -> pd.DataFrame:
    mon_expr = _sql_moneda_norm_expr()
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()

    anios = sorted(anios)

    prov_where = ""
    prov_params: List[str] = []
    if proveedores:
        parts = []
        for p in proveedores:
            parts.append(f"LOWER(TRIM({COL_PROV})) LIKE %s")
            prov_params.append(f"%{p.lower()}%")
        prov_where = f"AND ({' OR '.join(parts)})"

    cols = []
    for y in anios:
        cols.append(f"""SUM(CASE WHEN {_sql_year_expr()} = {y} AND {mon_expr} = '$' THEN {total_pesos} ELSE 0 END) AS "{y}_$" """)
        cols.append(f"""SUM(CASE WHEN {_sql_year_expr()} = {y} AND {mon_expr} IN ('U$S','U$$') THEN {total_usd} ELSE 0 END) AS "{y}_USD" """)

    cols_sql = ",\n            ".join(cols)
    y_last = anios[-1]
    order_sql = f"\"{y_last}_$\" DESC, \"{y_last}_USD\" DESC"

    query = f"""
        SELECT
            TRIM({COL_PROV}) AS Proveedor,
            {cols_sql}
        FROM {TABLE_COMPRAS}
        WHERE ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%')
          AND {_sql_year_expr()} IN ({", ".join(str(y) for y in anios)})
          {prov_where}
        GROUP BY TRIM({COL_PROV})
        ORDER BY {order_sql}
        LIMIT 300
    """

    return ejecutar_consulta(query, tuple(prov_params) if prov_params else None)


def get_comparacion_articulo_anios_monedas(anios: List[int], articulos: List[str] = None) -> pd.DataFrame:
    mon_expr = _sql_moneda_norm_expr()
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()

    anios = sorted(anios)

    art_where = ""
    art_params: List[str] = []
    if articulos:
        parts = []
        for a in articulos:
            parts.append(f"LOWER(TRIM({COL_ART})) LIKE %s")
            art_params.append(f"%{a.lower()}%")
        art_where = f"AND ({' OR '.join(parts)})"

    cols = []
    for y in anios:
        cols.append(f"""SUM(CASE WHEN {_sql_year_expr()} = {y} AND {mon_expr} = '$' THEN {total_pesos} ELSE 0 END) AS "{y}_$" """)
        cols.append(f"""SUM(CASE WHEN {_sql_year_expr()} = {y} AND {mon_expr} IN ('U$S','U$$') THEN {total_usd} ELSE 0 END) AS "{y}_USD" """)

    cols_sql = ",\n            ".join(cols)
    y_last = anios[-1]
    order_sql = f"\"{y_last}_$\" DESC, \"{y_last}_USD\" DESC"

    query = f"""
        SELECT
            TRIM({COL_ART}) AS Articulo,
            {cols_sql}
        FROM {TABLE_COMPRAS}
        WHERE ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%')
          AND {_sql_year_expr()} IN ({", ".join(str(y) for y in anios)})
          {art_where}
        GROUP BY TRIM({COL_ART})
        ORDER BY {order_sql}
        LIMIT 300
    """

    return ejecutar_consulta(query, tuple(art_params) if art_params else None)


# =========================
# DETALLE COMPRAS: PROVEEDOR + AÑO (MONEDA opcional)
# =========================

def get_detalle_compras_proveedor_anio(proveedor_like: str, anio: int, moneda: str = None) -> pd.DataFrame:
    fecha_expr = _sql_fecha_expr()
    mon_expr = _sql_moneda_norm_expr()

    proveedor_like = (proveedor_like or "").split("(")[0].strip().lower()

    if moneda and str(moneda).strip().upper() in ("U$S", "USD", "U$$"):
        total_expr = _sql_total_num_expr_usd()
        moneda_sql = f"AND {mon_expr} IN ('U$S','U$$')"
    elif moneda and str(moneda).strip() in ("$", "UYU"):
        total_expr = _sql_total_num_expr()
        moneda_sql = f"AND {mon_expr} = '$'"
    else:
        total_expr = _sql_total_num_expr_general()
        moneda_sql = ""

    sql = f"""
        SELECT
            TRIM({COL_PROV}) AS Proveedor,
            TRIM({COL_ART}) AS Articulo,
            TRIM({COL_NRO_COMP}) AS Nro_Factura,
            TO_CHAR({fecha_expr}, 'DD/MM/YYYY') AS Fecha,
            {COL_CANT} AS Cantidad,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS Total
        FROM {TABLE_COMPRAS}
        WHERE ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%')
          AND LOWER(TRIM({COL_PROV})) LIKE %s
          AND {_sql_year_expr()} = %s
          {moneda_sql}
        ORDER BY {fecha_expr} DESC NULLS LAST
    """
    return ejecutar_consulta(sql, (f"%{proveedor_like}%", anio))


# =========================
# DETALLE COMPRAS: PROVEEDOR + MES
# =========================

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
        LIMIT 100
    """
    
    return ejecutar_consulta(sql, (f"%{proveedor_like}%", mes_key))


# =========================
# DETALLE COMPRAS: ARTÍCULO + AÑO (CON LÍMITE)
# =========================

def get_detalle_compras_articulo_anio(articulo_like: str, anio: int, limite: int = 200) -> pd.DataFrame:
    fecha_expr = _sql_fecha_expr()
    total_expr = _sql_total_num_expr_general()

    sql = f"""
        SELECT
            TRIM({COL_PROV}) AS Proveedor,
            TRIM({COL_ART}) AS Articulo,
            TRIM({COL_NRO_COMP}) AS Nro_Factura,
            TO_CHAR({fecha_expr}, 'DD/MM/YYYY') AS Fecha,
            {COL_CANT} AS Cantidad,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS Total
        FROM {TABLE_COMPRAS}
        WHERE ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%')
          AND {_sql_year_expr()} = %s
          AND LOWER(TRIM({COL_ART})) LIKE %s
        ORDER BY {fecha_expr} DESC NULLS LAST
        LIMIT {int(limite)}
    """
    return ejecutar_consulta(sql, (anio, f"%{articulo_like.lower()}%"))


# =========================
# TOTAL COMPRAS: ARTÍCULO + AÑO (SIN LÍMITE)
# =========================

def get_total_compras_articulo_anio(articulo_like: str, anio: int) -> dict:
    total_expr = _sql_total_num_expr_general()

    sql = f"""
        SELECT
            COUNT(*) AS registros,
            COALESCE(SUM({total_expr}), 0) AS total
        FROM {TABLE_COMPRAS}
        WHERE ({COL_TIPO_COMP} = 'Compra Contado' OR {COL_TIPO_COMP} LIKE 'Compra%')
          AND {_sql_year_expr()} = %s
          AND LOWER(TRIM({COL_ART})) LIKE %s
    """
    df = ejecutar_consulta(sql, (anio, f"%{articulo_like.lower()}%"))
    if df is not None and not df.empty:
        reg = df["registros"].iloc[0] if "registros" in df.columns else 0
        tot = df["total"].iloc[0] if "total" in df.columns else 0
        return {
            "registros": int(reg) if pd.notna(reg) else 0,
            "total": float(tot) if pd.notna(tot) else 0.0
        }
    return {"registros": 0, "total": 0.0}


# =========================
# BUSCADOR DE COMPROBANTES
# =========================

def buscar_comprobantes(proveedor: str = None, tipo_comprobante: str = None, 
                        articulo: str = None, fecha_desde=None, fecha_hasta=None,
                        texto_busqueda: str = None) -> pd.DataFrame:
    """Busca comprobantes con filtros múltiples."""
    fecha_expr = _sql_fecha_expr()
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
        condiciones.append(f"{fecha_expr} >= %s")
        params.append(fecha_desde.strftime('%Y-%m-%d'))
    
    if fecha_hasta:
        condiciones.append(f"{fecha_expr} <= %s")
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
            TO_CHAR({fecha_expr}, 'DD/MM/YYYY') AS Fecha,
            {COL_CANT} AS Cantidad,
            {COL_MONEDA} AS Moneda,
            {total_expr} AS Monto
        FROM {TABLE_COMPRAS}
        WHERE {where_sql}
        ORDER BY {fecha_expr} DESC NULLS LAST
        LIMIT 200
    """
    
    return ejecutar_consulta(sql, tuple(params) if params else None)


# =========================
# STOCK FUNCTIONS (PLACEHOLDERS)
# =========================

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

def get_top_10_proveedores_chatbot(moneda: str = None, anio: int = None, mes: str = None) -> pd.DataFrame:
    return pd.DataFrame()


# FIN DEL ARCHIVO
