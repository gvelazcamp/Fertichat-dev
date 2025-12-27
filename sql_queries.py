# =========================
# SQL QUERIES - SOLO CONSULTAS
# =========================
import os
import psycopg2
import pymysql
import pandas as pd
from typing import List, Tuple, Optional
import re
from datetime import datetime

# =====================================================================
# CONEXIÓN DB
# =====================================================================

def get_db_connection():
    """Establece conexión con MySQL"""
    try:
        conn = pymysql.connect(
            host='localhost',
            port=3307,
            user='root',
            password='',
            database='chatbot',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except pymysql.Error as e:
        print(f"Error de conexión a MySQL: {e}")
        return None


# =====================================================================
# HELPERS SQL
# =====================================================================

def _sql_fecha_expr() -> str:
    """Convierte fecha texto a DATE"""
    return "COALESCE(STR_TO_DATE(fecha, '%%Y-%%m-%%d'), STR_TO_DATE(fecha, '%%d/%%m/%%Y'))"


def _sql_mes_col() -> str:
    """Columna Mes normalizada"""
    return "TRIM(Mes)"


def _sql_total_num_expr() -> str:
    """Convierte Total $ a número"""
    return """CAST(
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(TRIM(Total), '.', ''),
                        ',', '.'
                    ),
                    '(', '-'
                ),
                ')', ''
            ),
            '$', ''
        ) AS DECIMAL(15,2)
    )"""


def _sql_total_num_expr_usd() -> str:
    """Convierte Total USD a número"""
    return """CAST(
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(
                            REPLACE(TRIM(Total), 'U$S', ''),
                            '.', ''
                        ),
                        ',', '.'
                    ),
                    '(', '-'
                ),
                ')', ''
            ),
            '$', ''
        ) AS DECIMAL(15,2)
    )"""


def _sql_total_num_expr_general() -> str:
    """Convierte Total ($ o USD) a número"""
    return """CAST(
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(
                                    REPLACE(TRIM(Total), 'U$S', ''),
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
        ) AS DECIMAL(15,2)
    )"""


def _sql_moneda_norm_expr() -> str:
    """Normaliza moneda"""
    return "TRIM(Moneda)"


def _sql_cantidad_num_expr() -> str:
    """Convierte cantidad a número"""
    return "CAST(REPLACE(TRIM(cantidad), ',', '.') AS DECIMAL(15,2))"


def _escape_percent_para_pymysql(query: str) -> str:
    """Escapa % literales para PyMySQL"""
    if not query or "%" not in query:
        return query

    out = []
    i = 0
    n = len(query)

    while i < n:
        ch = query[i]
        if ch == "%":
            if i + 1 < n:
                nxt = query[i + 1]
                if nxt == "s":
                    out.append("%s")
                    i += 2
                    continue
                if nxt == "%":
                    out.append("%%")
                    i += 2
                    continue
                out.append("%%")
                i += 1
                continue
            out.append("%%")
            i += 1
            continue
        out.append(ch)
        i += 1

    return "".join(out)


def _guardar_log(consulta: str, parametros: str, resultado: str, registros: int, error: str, tiempo_ms: int):
    """Guarda log de consulta en tabla query_log (silencioso si falla)"""
    try:
        conn = get_db_connection()
        if not conn:
            return
        
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO query_log (consulta, parametros, resultado, registros, error, tiempo_ms)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            # Truncar consulta si es muy larga
            consulta_corta = consulta[:2000] if consulta else ''
            error_corto = error[:500] if error else None
            
            cursor.execute(sql, (consulta_corta, parametros, resultado, registros, error_corto, tiempo_ms))
            conn.commit()
        conn.close()
    except:
        pass  # Si falla el log, no afecta la app


def guardar_chat_log(pregunta: str, intencion: str, respuesta: str, tuvo_datos: bool, registros: int = 0, debug: str = None):
    """Guarda log de pregunta/respuesta del chat (silencioso si falla)"""
    try:
        conn = get_db_connection()
        if not conn:
            return
        
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO chat_log (pregunta, intencion, respuesta, tuvo_datos, registros, debug)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            # Truncar si es muy largo
            pregunta_corta = pregunta[:1000] if pregunta else ''
            respuesta_corta = respuesta[:2000] if respuesta else ''
            debug_corto = debug[:500] if debug else None
            
            cursor.execute(sql, (pregunta_corta, intencion, respuesta_corta, tuvo_datos, registros, debug_corto))
            conn.commit()
        conn.close()
    except:
        pass  # Si falla el log, no afecta la app


def ejecutar_consulta(query: str, params: tuple = None) -> pd.DataFrame:
    """Ejecuta consulta SQL y retorna DataFrame (con logging)"""
    import time
    
    conn = get_db_connection()
    if not conn:
        _guardar_log(query, str(params), 'ERROR', 0, 'No se pudo conectar', 0)
        return pd.DataFrame()

    inicio = time.time()
    
    try:
        if params is None:
            params = ()

        query_safe = _escape_percent_para_pymysql(query)

        with conn.cursor() as cursor:
            cursor.execute(query_safe, params)
            data = cursor.fetchall()

        tiempo_ms = int((time.time() - inicio) * 1000)
        
        if not data:
            _guardar_log(query, str(params), 'OK', 0, None, tiempo_ms)
            return pd.DataFrame()

        df = pd.DataFrame(data)
        _guardar_log(query, str(params), 'OK', len(df), None, tiempo_ms)
        return df

    except Exception as e:
        tiempo_ms = int((time.time() - inicio) * 1000)
        _guardar_log(query, str(params), 'ERROR', 0, str(e), tiempo_ms)
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

# --- PRIORIDAD 1: FACTURAS POR NÚMERO (más específico) ---

# =========================
# FACTURA: DETALLE POR NÚMERO 
# =========================
def get_detalle_factura_por_numero(nro_factura: str) -> pd.DataFrame:
    query = """
        SELECT
            `N Factura` AS nro_factura,
            Proveedor,
            Articulo,
            cantidad,
            Total
        FROM chatbot
        WHERE `N Factura` = %s
          AND `N Factura` <> 'A0000000'
          AND (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%')
        ORDER BY Articulo
    """
    return ejecutar_consulta(query, (nro_factura,))



# --- PRIORIDAD 2: ÚLTIMA FACTURA DE ARTÍCULO ---

def get_ultima_factura_de_articulo(patron_articulo: str) -> pd.DataFrame:
    """Última factura donde vino un artículo"""
    total_expr = _sql_total_num_expr()
    fecha_expr = _sql_fecha_expr()

    query = f"""
        SELECT
            Proveedor,
            Articulo,
            cantidad,
            `N Factura` AS nro_factura,
            {total_expr} AS total_linea,
            fecha
        FROM chatbot
        WHERE LOWER(Articulo) LIKE %s
        ORDER BY {fecha_expr} DESC
        LIMIT 1
    """
    return ejecutar_consulta(query, (f"%{patron_articulo.lower()}%",))


def get_ultima_factura_numero_de_articulo(patron_articulo: str) -> Optional[str]:
    """Obtiene el número de la última factura de un artículo"""
    fecha_expr = _sql_fecha_expr()
    query = f"""
        SELECT `N Factura` AS nro_factura
        FROM chatbot
        WHERE LOWER(Articulo) LIKE %s
        ORDER BY {fecha_expr} DESC
        LIMIT 1
    """
    df = ejecutar_consulta(query, (f"%{patron_articulo.lower()}%",))
    if df.empty:
        return None
    nro = str(df["nro_factura"].iloc[0]).strip()
    return nro if nro else None


# --- PRIORIDAD 3: TODAS LAS FACTURAS DE ARTÍCULO ---

def get_facturas_de_articulo(patron_articulo: str, solo_ultima: bool = False) -> pd.DataFrame:
    """Lista todas las facturas donde apareció un artículo"""
    fecha_expr = _sql_fecha_expr()
    total_expr = _sql_total_num_expr_general()

    limit_sql = "LIMIT 1" if solo_ultima else "LIMIT 50"

    query = f"""
        SELECT
            Proveedor,
            Articulo,
            `N Factura` AS Nro_Factura,
            DATE_FORMAT({fecha_expr}, '%%d/%%m/%%Y') AS Fecha,
            cantidad AS Cantidad,
            {total_expr} AS Total
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
            AND LOWER(Articulo) LIKE %s
        ORDER BY {fecha_expr} DESC
        {limit_sql}
    """
    return ejecutar_consulta(query, (f"%{patron_articulo.lower()}%",))


# --- PRIORIDAD 4: COMPARACIONES (MESES) ---

def get_comparacion_familia_meses(mes1: str, mes2: str, label1: str, label2: str, familias: List[str] = None) -> pd.DataFrame:
    """Comparar familias entre 2 meses"""
    total_expr = _sql_total_num_expr()
    mes_col = _sql_mes_col()

    familia_where = ""
    familia_params = []
    if familias:
        parts = []
        for fam in familias:
            parts.append("TRIM(Familia) = %s")
            familia_params.append(fam)
        familia_where = f"AND ({' OR '.join(parts)})"

    query = f"""
        SELECT
            Familia,
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
        FROM chatbot
        WHERE {mes_col} IN (%s, %s)
        AND (
            LOWER(TRIM(COALESCE(Familia, ''))) IN ('servicio citometro', 'servicio citómetro')
            OR (
                UPPER(TRIM(COALESCE(Familia, ''))) NOT IN (
                    'GASTOS FIJOS',
                    'INGRESOS',
                    'GASTOS IMPORTACION',
                    'GASTOS IMPORTACIÓN',
                    '_RESGUARDOS',
                    'RESGUARDOS',
                    'DESCUENTOS'
                )
                AND UPPER(TRIM(COALESCE(Familia, ''))) NOT LIKE 'SERVICIO%%'
            )
        )
        {familia_where}
        GROUP BY Familia
        ORDER BY comparacion DESC
    """

    params = (mes1, mes2, mes2, mes1, mes1, mes2, mes1, mes1, mes1, mes2, *familia_params)
    df = ejecutar_consulta(query, params)

    if df.empty:
        return df

    df = df.rename(columns={"Mes1": label1, "Mes2": label2})
    return df


def get_comparacion_familia_meses_moneda(mes1: str, mes2: str, label1: str, label2: str, moneda: str = "$", familias: List[str] = None) -> pd.DataFrame:
    """
    Comparar familias entre 2 meses FILTRADO POR MONEDA
    moneda: "$" para pesos, "U$S" para dólares
    """
    mes_col = _sql_mes_col()
    mon_expr = _sql_moneda_norm_expr()
    
    # Seleccionar expresión de total según moneda
    if moneda == "U$S":
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
            parts.append("TRIM(Familia) = %s")
            familia_params.append(fam)
        familia_where = f"AND ({' OR '.join(parts)})"

    query = f"""
        SELECT
            Familia,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Mes1,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Mes2,
            (
                SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END)
                -
                SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END)
            ) AS Diferencia,
            CASE
                WHEN SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) = 0
                THEN NULL
                ELSE
                    ROUND((
                        (
                            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END)
                            -
                            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END)
                        )
                        /
                        SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END)
                    ) * 100, 1)
            END AS Variacion_Pct
        FROM chatbot
        WHERE {mes_col} IN (%s, %s)
        AND {mon_filter}
        AND (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
        AND (
            LOWER(TRIM(COALESCE(Familia, ''))) IN ('servicio citometro', 'servicio citómetro')
            OR (
                UPPER(TRIM(COALESCE(Familia, ''))) NOT IN (
                    'GASTOS FIJOS',
                    'INGRESOS',
                    'GASTOS IMPORTACION',
                    'GASTOS IMPORTACIÓN',
                    '_RESGUARDOS',
                    'RESGUARDOS',
                    'DESCUENTOS'
                )
                AND UPPER(TRIM(COALESCE(Familia, ''))) NOT LIKE 'SERVICIO%%'
            )
        )
        {familia_where}
        GROUP BY Familia
        HAVING Mes1 > 0 OR Mes2 > 0
        ORDER BY Diferencia DESC
    """

    params = (mes1, mes2, mes2, mes1, mes1, mes2, mes1, mes1, mes1, mes2, *familia_params)
    df = ejecutar_consulta(query, params)

    if df.empty:
        return df

    df = df.rename(columns={"Mes1": label1, "Mes2": label2})
    return df


def get_comparacion_proveedor_meses(mes1: str, mes2: str, label1: str, label2: str, proveedores: List[str] = None) -> pd.DataFrame:
    """Comparar proveedores entre 2 meses"""
    total_expr = _sql_total_num_expr()
    mes_col = _sql_mes_col()

    prov_where = ""
    prov_params = []
    if proveedores:
        parts = []
        for p in proveedores:
            parts.append("LOWER(Proveedor) LIKE %s")
            prov_params.append(f"%{p.lower()}%")
        prov_where = f"AND ({' OR '.join(parts)})"

    inner = f"""
        SELECT
            Proveedor AS Concepto,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Mes1,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Mes2
        FROM chatbot
        WHERE {mes_col} IN (%s, %s)
          AND (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
          {prov_where}
        GROUP BY Proveedor
    """

    query = f"""
        SELECT
            t.Concepto,
            t.Mes1 AS {label1},
            t.Mes2 AS {label2},
            (t.Mes2 - t.Mes1) AS Diferencia,
            CASE
                WHEN t.Mes1 = 0 THEN NULL
                ELSE ((t.Mes2 - t.Mes1) / t.Mes1) * 100
            END AS Variación_pct
        FROM ({inner}) t
        WHERE t.Mes1 <> 0 OR t.Mes2 <> 0
        ORDER BY Diferencia DESC
    """

    params = (mes1, mes2, mes1, mes2, *prov_params)
    return ejecutar_consulta(query, params)


def get_comparacion_articulo_meses(mes1: str, mes2: str, label1: str, label2: str, articulos: List[str] = None) -> pd.DataFrame:
    """Comparar artículos entre 2 meses"""
    total_expr = _sql_total_num_expr()
    mes_col = _sql_mes_col()

    art_where = ""
    art_params = []
    if articulos:
        parts = []
        for a in articulos:
            parts.append("LOWER(Articulo) LIKE %s")
            art_params.append(f"%{a.lower()}%")
        art_where = f"AND ({' OR '.join(parts)})"

    inner = f"""
        SELECT
            Articulo AS Concepto,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Mes1,
            SUM(CASE WHEN {mes_col} = %s THEN {total_expr} ELSE 0 END) AS Mes2
        FROM chatbot
        WHERE {mes_col} IN (%s, %s)
          AND (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
          {art_where}
        GROUP BY Articulo
    """

    query = f"""
        SELECT
            t.Concepto,
            t.Mes1 AS {label1},
            t.Mes2 AS {label2},
            (t.Mes2 - t.Mes1) AS Diferencia,
            CASE
                WHEN t.Mes1 = 0 THEN NULL
                ELSE ((t.Mes2 - t.Mes1) / t.Mes1) * 100
            END AS Variación_pct
        FROM ({inner}) t
        WHERE t.Mes1 <> 0 OR t.Mes2 <> 0
        ORDER BY Diferencia DESC
        LIMIT 200
    """

    params = (mes1, mes2, mes1, mes2, *art_params)
    return ejecutar_consulta(query, params)


# --- PRIORIDAD 5: COMPARACIONES POR AÑOS ---

def get_comparacion_proveedor_anios_monedas(anios: List[int], proveedores: List[str] = None) -> pd.DataFrame:
    """Comparar proveedores por años ($ y USD separados)"""
    fecha_expr = _sql_fecha_expr()
    mon_expr = _sql_moneda_norm_expr()
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()

    # Ordenar años ascendente
    anios = sorted(anios)

    prov_where = ""
    prov_params = []
    if proveedores:
        parts = []
        for p in proveedores:
            parts.append("LOWER(Proveedor) LIKE %s")
            prov_params.append(f"%{p.lower()}%")
        prov_where = f"AND ({' OR '.join(parts)})"

    cols = []
    for y in anios:
        cols.append(
            f"""SUM(CASE WHEN YEAR({fecha_expr}) = {y} AND {mon_expr} = '$'
                 THEN {total_pesos} ELSE 0 END) AS {y}_$"""
        )
        cols.append(
            f"""SUM(CASE WHEN YEAR({fecha_expr}) = {y} AND {mon_expr} = 'U$S'
                 THEN {total_usd} ELSE 0 END) AS {y}_USD"""
        )

    cols_sql = ",\n            ".join(cols)
    y_last = anios[-1]
    order_sql = f"{y_last}_$ DESC, {y_last}_USD DESC"

    query = f"""
        SELECT
            Proveedor,
            {cols_sql}
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
            AND YEAR({fecha_expr}) IN ({", ".join(str(y) for y in anios)})
            {prov_where}
        GROUP BY Proveedor
        ORDER BY {order_sql}
        LIMIT 300
    """

    return ejecutar_consulta(query, tuple(prov_params) if prov_params else None)


# =========================
# DETALLE COMPRAS PROVEEDOR + AÑO (CON MONEDA)
# =========================
def get_detalle_compras_proveedor_anio(proveedor_like: str, anio: int, moneda: str = None):
    fecha_expr = _sql_fecha_expr()
    mon_expr = _sql_moneda_norm_expr()

    proveedor_like = proveedor_like.split("(")[0].strip().lower()

    # 🔹 Total numérico según moneda
    if moneda and moneda.upper() in ("U$S", "USD", "U$$"):
        total_expr = _sql_total_num_expr_usd()
        moneda_sql = f"AND {mon_expr} IN ('U$S', 'U$$')"
    elif moneda and moneda in ("$", "UYU"):
        total_expr = _sql_total_num_expr()
        moneda_sql = f"AND {mon_expr} = '$'"
    else:
        # 🔴 COMPORTAMIENTO ORIGINAL (NO FILTRA MONEDA)
        total_expr = _sql_total_num_expr_general()
        moneda_sql = ""

    sql = f"""
        SELECT
            Proveedor,
            Articulo,
            `N Factura` AS Nro_Factura,
            DATE_FORMAT({fecha_expr}, '%%d/%%m/%%Y') AS Fecha,
            cantidad AS Cantidad,
            Moneda,
            {total_expr} AS Total
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
            AND LOWER(Proveedor) LIKE %s
            AND YEAR({fecha_expr}) = %s
            {moneda_sql}
        ORDER BY {fecha_expr} DESC
    """
    params = (f"%{proveedor_like}%", anio)
    return ejecutar_consulta(sql, params)

def get_comparacion_articulo_anios_monedas(anios: List[int], articulos: List[str] = None) -> pd.DataFrame:
    """Comparar artículos por años ($ y USD separados)"""
    fecha_expr = _sql_fecha_expr()
    mon_expr = _sql_moneda_norm_expr()
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()

    # Ordenar años ascendente
    anios = sorted(anios)

    art_where = ""
    art_params = []
    if articulos:
        parts = []
        for a in articulos:
            parts.append("LOWER(Articulo) LIKE %s")
            art_params.append(f"%{a.lower()}%")
        art_where = f"AND ({' OR '.join(parts)})"

    cols = []
    for y in anios:
        cols.append(
            f"""SUM(CASE WHEN YEAR({fecha_expr}) = {y} AND {mon_expr} = '$'
                 THEN {total_pesos} ELSE 0 END) AS {y}_$"""
        )
        cols.append(
            f"""SUM(CASE WHEN YEAR({fecha_expr}) = {y} AND {mon_expr} = 'U$S'
                 THEN {total_usd} ELSE 0 END) AS {y}_USD"""
        )

    cols_sql = ",\n            ".join(cols)
    y_last = anios[-1]
    order_sql = f"{y_last}_$ DESC, {y_last}_USD DESC"

    query = f"""
        SELECT
            Articulo,
            {cols_sql}
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
            AND YEAR({fecha_expr}) IN ({", ".join(str(y) for y in anios)})
            {art_where}
        GROUP BY Articulo
        ORDER BY {order_sql}
        LIMIT 300
    """

    return ejecutar_consulta(query, tuple(art_params) if art_params else None)


# --- PRIORIDAD 6: DETALLE COMPRAS POR MES/PROVEEDOR ---

def get_compras_por_mes_excel(mes_key: str) -> pd.DataFrame:
    """Detalle de compras de un mes (formato Excel)"""
    total_expr = _sql_total_num_expr()

    query = f"""
        SELECT
            tipo_comprobante AS Tipo_Comprobante,
            `N Factura` AS Nro_Comprobante,
            Proveedor AS Cliente_Proveedor,
            Familia,
            Tipo Articulo AS Tipo_Articulo,
            Articulo,
            DATE_FORMAT(COALESCE(STR_TO_DATE(fecha, '%%Y-%%m-%%d'), STR_TO_DATE(fecha, '%%d/%%m/%%Y')), '%%d/%%m/%%Y') AS Fecha,
            cantidad AS Cantidad,
            {total_expr} AS Monto_Neto
        FROM chatbot
        WHERE TRIM(Mes) = %s
        ORDER BY
            COALESCE(STR_TO_DATE(fecha, '%%Y-%%m-%%d'), STR_TO_DATE(fecha, '%%d/%%m/%%Y')) DESC,
            Proveedor,
            Articulo
    """
    return ejecutar_consulta(query, (mes_key,))


def get_detalle_compras_proveedor_mes(proveedor_like: str, mes_key: str) -> pd.DataFrame:
    """Detalle compras de un proveedor en un mes específico"""
    total_expr = _sql_total_num_expr()
    fecha_expr = _sql_fecha_expr()

    query = f"""
        SELECT
            Proveedor,
            Articulo,
            `N Factura` AS Nro_Factura,
            DATE_FORMAT({fecha_expr}, '%%d/%%m/%%Y') AS Fecha,
            cantidad AS Cantidad,
            {total_expr} AS Total
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
            AND LOWER(Proveedor) LIKE %s
            AND TRIM(Mes) = %s
        ORDER BY {fecha_expr} DESC
        LIMIT 200
    """
    return ejecutar_consulta(query, (f"%{proveedor_like.lower()}%", mes_key))


def get_detalle_compras_articulo_mes(articulo_like: str, mes_key: str) -> pd.DataFrame:
    """Detalle compras de un artículo en un mes específico"""
    total_expr = _sql_total_num_expr()
    fecha_expr = _sql_fecha_expr()

    query = f"""
        SELECT
            Proveedor,
            Articulo,
            `N Factura` AS Nro_Factura,
            DATE_FORMAT({fecha_expr}, '%%d/%%m/%%Y') AS Fecha,
            cantidad AS Cantidad,
            Moneda,
            {total_expr} AS Total
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
            AND LOWER(Articulo) LIKE %s
            AND TRIM(Mes) = %s
        ORDER BY {fecha_expr} DESC
        LIMIT 200
    """
    return ejecutar_consulta(query, (f"%{articulo_like.lower()}%", mes_key))


def get_comparacion_articulo_anios(anios: List[int], articulo_like: str) -> pd.DataFrame:
    """Comparar compras de un artículo entre múltiples años ($ y USD separados)"""
    fecha_expr = _sql_fecha_expr()
    mon_expr = _sql_moneda_norm_expr()
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()

    # Ordenar años ascendente
    anios = sorted(anios)

    # Generar columnas dinámicas para cada año
    cols = []
    for y in anios:
        cols.append(
            f"""SUM(CASE WHEN YEAR({fecha_expr}) = {y} AND {mon_expr} = '$'
                 THEN {total_pesos} ELSE 0 END) AS `{y}_$`"""
        )
        cols.append(
            f"""SUM(CASE WHEN YEAR({fecha_expr}) = {y} AND {mon_expr} = 'U$S'
                 THEN {total_usd} ELSE 0 END) AS `{y}_USD`"""
        )

    cols_sql = ",\n            ".join(cols)
    y_last = anios[-1]
    order_sql = f"`{y_last}_$` DESC, `{y_last}_USD` DESC"

    query = f"""
        SELECT
            Articulo,
            {cols_sql}
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
            AND YEAR({fecha_expr}) IN ({", ".join(str(y) for y in anios)})
            AND LOWER(Articulo) LIKE %s
        GROUP BY Articulo
        ORDER BY {order_sql}
        LIMIT 100
    """

    return ejecutar_consulta(query, (f"%{articulo_like.lower()}%",))


def get_detalle_compras_proveedor_anio(proveedor_like: str, anio: int) -> pd.DataFrame:
    """Detalle compras de un proveedor en un año específico"""
    total_expr = _sql_total_num_expr()
    fecha_expr = _sql_fecha_expr()

    query = f"""
        SELECT
            Proveedor,
            Articulo,
            `N Factura` AS Nro_Factura,
            DATE_FORMAT({fecha_expr}, '%%d/%%m/%%Y') AS Fecha,
            cantidad AS Cantidad,
            {total_expr} AS Total
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
            AND LOWER(Proveedor) LIKE %s
            AND YEAR({fecha_expr}) = %s
        ORDER BY {fecha_expr} DESC
        LIMIT 2000
    """
    return ejecutar_consulta(query, (f"%{proveedor_like.lower()}%", anio))


def get_detalle_compras_proveedor_anios(anios: List[int], proveedores: List[str] = None) -> pd.DataFrame:
    """
    Detalle de compras de proveedores en múltiples años.
    Para usar en comparaciones de proveedores por años.
    """
    total_expr = _sql_total_num_expr()
    fecha_expr = _sql_fecha_expr()
    mon_expr = _sql_moneda_norm_expr()
    
    # Construir filtro de años
    anios_ph = ", ".join(["%s"] * len(anios))
    params = list(anios)
    
    # Construir filtro de proveedores
    prov_where = ""
    if proveedores:
        prov_parts = []
        for p in proveedores:
            prov_parts.append("LOWER(Proveedor) LIKE %s")
            params.append(f"%{p.lower()}%")
        prov_where = f"AND ({' OR '.join(prov_parts)})"
    
    query = f"""
        SELECT
            Proveedor,
            YEAR({fecha_expr}) AS Anio,
            {mon_expr} AS Moneda,
            Articulo,
            `N Factura` AS Nro_Factura,
            DATE_FORMAT({fecha_expr}, '%%d/%%m/%%Y') AS Fecha,
            cantidad AS Cantidad,
            {total_expr} AS Total
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
            AND YEAR({fecha_expr}) IN ({anios_ph})
            {prov_where}
        ORDER BY {fecha_expr} DESC
        LIMIT 500
    """
    return ejecutar_consulta(query, tuple(params))


def get_total_compras_proveedor_anio(proveedor_like: str, anio: int) -> dict:
    """Obtiene el TOTAL real de compras de un proveedor en un año (sin límite)"""
    total_expr = _sql_total_num_expr()
    fecha_expr = _sql_fecha_expr()

    query = f"""
        SELECT
            COUNT(*) AS Registros,
            SUM({total_expr}) AS Total
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
            AND LOWER(Proveedor) LIKE %s
            AND YEAR({fecha_expr}) = %s
    """
    df = ejecutar_consulta(query, (f"%{proveedor_like.lower()}%", anio))
    if df is not None and not df.empty:
        return {
            'registros': int(df['Registros'].iloc[0]) if pd.notna(df['Registros'].iloc[0]) else 0,
            'total': float(df['Total'].iloc[0]) if pd.notna(df['Total'].iloc[0]) else 0
        }
    return {'registros': 0, 'total': 0}


def get_total_compras_proveedor_moneda_periodos(periodos: List[str], monedas: List[str] = None) -> pd.DataFrame:
    """Total compras por proveedor + moneda + múltiples períodos"""
    if not monedas:
        monedas = ["$", "U$$", "U$S"]

    total_expr = _sql_total_num_expr_general()
    ph_periodos = ", ".join(["%s"] * len(periodos))
    ph_monedas = ", ".join(["%s"] * len(monedas))

    query = f"""
        SELECT
            Proveedor,
            TRIM(Mes) AS Periodo,
            Moneda,
            COUNT(*) AS Registros,
            SUM({total_expr}) AS Total
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
            AND TRIM(Mes) IN ({ph_periodos})
            AND Moneda IN ({ph_monedas})
        GROUP BY Proveedor, TRIM(Mes), Moneda
        ORDER BY Periodo, Moneda, Total DESC
    """

    params = tuple(periodos) + tuple(monedas)
    return ejecutar_consulta(query, params)


# --- PRIORIDAD 7: GASTOS SECCIONES ---

def get_gastos_secciones_detalle(familias, mes_key):
    """
    Devuelve el gasto total por sección (familia) en un mes específico
    familias: lista ['G', 'FB', 'ID']
    mes_key: 'YYYY-MM'
    """
    if not familias or not mes_key:
        return pd.DataFrame()

    placeholders = ", ".join(["%s"] * len(familias))

    sql = f"""
        SELECT
            Familia AS Seccion,
            SUM(
                CAST(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(
                                    REPLACE(TRIM(Total), '.', ''),
                                ',', '.'),
                            '(', '-'),
                        ')', ''),
                    '$', '')
                AS DECIMAL(15,2))
            ) AS Total
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado'
             OR tipo_comprobante LIKE 'Compra%')
            AND TRIM(Mes) = %s
            AND (
                LOWER(TRIM(COALESCE(Familia, ''))) IN ('servicio citometro', 'servicio citómetro')
                OR (
                    UPPER(TRIM(COALESCE(Familia, ''))) NOT IN (
                        'GASTOS FIJOS',
                        'INGRESOS',
                        'GASTOS IMPORTACION',
                        'GASTOS IMPORTACIÓN',
                        '_RESGUARDOS',
                        'RESGUARDOS',
                        'DESCUENTOS'
                    )
                    AND UPPER(TRIM(COALESCE(Familia, ''))) NOT LIKE 'SERVICIO%%'
                )
            )

            AND Familia IN ({placeholders})
        GROUP BY Familia
        ORDER BY Total DESC
    """

    params = [mes_key] + familias

    return ejecutar_consulta(sql, params)


def get_gastos_secciones_detalle_completo(familias, mes_key):
    """
    Devuelve el detalle completo de gastos por secciones (familias) en un mes
    Columnas:
    Articulo | Familia | Tipo Articulo | Nro Comprobante | Cantidad | Monto
    """
    if not familias or not mes_key:
        return pd.DataFrame()

    placeholders = ", ".join(["%s"] * len(familias))
    total_expr = _sql_total_num_expr_general()
    fecha_expr = _sql_fecha_expr()

    sql = f"""
        SELECT
            Articulo,
            Familia,
            `Tipo Articulo` AS Tipo_Articulo,
            `N Factura` AS Nro_Comprobante,
            cantidad AS Cantidad,
            {total_expr} AS Monto
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado'
             OR tipo_comprobante LIKE 'Compra%%')
            AND TRIM(Mes) = %s
            AND (
                LOWER(TRIM(COALESCE(Familia, ''))) IN ('servicio citometro', 'servicio citómetro')
                OR (
                    UPPER(TRIM(COALESCE(Familia, ''))) NOT IN (
                        'GASTOS FIJOS',
                        'INGRESOS',
                        'GASTOS IMPORTACION',
                        'GASTOS IMPORTACIÓN',
                        '_RESGUARDOS',
                        'RESGUARDOS',
                        'DESCUENTOS'
                    )
                    AND UPPER(TRIM(COALESCE(Familia, ''))) NOT LIKE 'SERVICIO%%'
                )
            )

            AND Familia IN ({placeholders})
        ORDER BY Familia, {fecha_expr} DESC
        LIMIT 500
    """

    params = [mes_key] + familias
    return ejecutar_consulta(sql, tuple(params))

# --- PRIORIDAD 8: GASTOS POR FAMILIA ---

def get_gastos_por_familia(where_clause: str, params: tuple) -> pd.DataFrame:
    """Gastos totales por familia"""
    total_expr = _sql_total_num_expr()

    query = f"""
        SELECT
            Familia,
            SUM({total_expr}) as Total
        FROM chatbot
        WHERE {where_clause}
          AND (
              LOWER(TRIM(COALESCE(Familia, ''))) IN ('servicio citometro', 'servicio citómetro')
              OR (
                  UPPER(TRIM(COALESCE(Familia, ''))) NOT IN (
                      'GASTOS FIJOS',
                      'INGRESOS',
                      'GASTOS IMPORTACION',
                      'GASTOS IMPORTACIÓN',
                      '_RESGUARDOS',
                      'RESGUARDOS',
                      'DESCUENTOS'
                  )
                  AND UPPER(TRIM(COALESCE(Familia, ''))) NOT LIKE 'SERVICIO%%'
              )
          )

        GROUP BY Familia
        ORDER BY SUM({total_expr}) DESC
    """
    return ejecutar_consulta(query, params)


def get_gastos_todas_familias_mes(mes_key: str) -> pd.DataFrame:
    """Gastos de TODAS las familias para un mes específico (pesos y USD separados)"""
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()
    mon_expr = _sql_moneda_norm_expr()
    
    query = f"""
        SELECT
            COALESCE(Familia, 'SIN FAMILIA') as Familia,
            SUM(CASE WHEN {mon_expr} = '$' THEN {total_pesos} ELSE 0 END) as Total_Pesos,
            SUM(CASE WHEN {mon_expr} = 'U$S' THEN {total_usd} ELSE 0 END) as Total_USD
        FROM chatbot
        WHERE TRIM(Mes) = %s
          AND (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
          AND (
              LOWER(TRIM(COALESCE(Familia, ''))) IN ('servicio citometro', 'servicio citómetro')
              OR (
                  UPPER(TRIM(COALESCE(Familia, ''))) NOT IN (
                      'GASTOS FIJOS',
                      'INGRESOS',
                      'GASTOS IMPORTACION',
                      'GASTOS IMPORTACIÓN',
                      '_RESGUARDOS',
                      'RESGUARDOS',
                      'DESCUENTOS'
                  )
                  AND UPPER(TRIM(COALESCE(Familia, ''))) NOT LIKE 'SERVICIO%%'
              )
          )

        GROUP BY Familia
        ORDER BY SUM(CASE WHEN {mon_expr} = '$' THEN {total_pesos} ELSE 0 END) DESC
    """
    return ejecutar_consulta(query, (mes_key,))


def get_gastos_todas_familias_anio(anio: int) -> pd.DataFrame:
    """Gastos de TODAS las familias para un año específico (pesos y USD separados)"""
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()
    mon_expr = _sql_moneda_norm_expr()
    fecha_expr = _sql_fecha_expr()
    
    query = f"""
        SELECT
            COALESCE(Familia, 'SIN FAMILIA') as Familia,
            SUM(CASE WHEN {mon_expr} = '$' THEN {total_pesos} ELSE 0 END) as Total_Pesos,
            SUM(CASE WHEN {mon_expr} = 'U$S' THEN {total_usd} ELSE 0 END) as Total_USD
        FROM chatbot
        WHERE YEAR({fecha_expr}) = %s
          AND (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
          AND (
              LOWER(TRIM(COALESCE(Familia, ''))) IN ('servicio citometro', 'servicio citómetro')
              OR (
                  UPPER(TRIM(COALESCE(Familia, ''))) NOT IN (
                      'GASTOS FIJOS',
                      'INGRESOS',
                      'GASTOS IMPORTACION',
                      'GASTOS IMPORTACIÓN',
                      '_RESGUARDOS',
                      'RESGUARDOS',
                      'DESCUENTOS'
                  )
                  AND UPPER(TRIM(COALESCE(Familia, ''))) NOT LIKE 'SERVICIO%%'
              )
          )

        GROUP BY Familia
        ORDER BY SUM(CASE WHEN {mon_expr} = '$' THEN {total_pesos} ELSE 0 END) DESC
    """
    return ejecutar_consulta(query, (anio,))


# --- PRIORIDAD 9: LISTAR VALORES ---

def get_valores_unicos() -> dict:
    """Lista proveedores, familias y artículos únicos"""
    conn = get_db_connection()
    if not conn:
        return {}

    valores = {}

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT Proveedor FROM chatbot WHERE Proveedor IS NOT NULL ORDER BY Proveedor")
            valores['proveedores'] = [row['Proveedor'] for row in cursor.fetchall()]

            cursor.execute("SELECT DISTINCT Familia FROM chatbot WHERE Familia IS NOT NULL ORDER BY Familia")
            valores['familias'] = [row['Familia'] for row in cursor.fetchall()]

            cursor.execute("SELECT DISTINCT Articulo FROM chatbot WHERE Articulo IS NOT NULL ORDER BY Articulo LIMIT 50")
            valores['articulos'] = [row['Articulo'] for row in cursor.fetchall()]

    finally:
        try:
            conn.close()
        except Exception:
            pass

    return valores


# --- PRIORIDAD 10: DETALLE GENERAL ---

def get_detalle_compras(where_clause: str, params: tuple) -> pd.DataFrame:
    """Detalle general de compras"""
    fecha_expr = _sql_fecha_expr()
    query = f"""
        SELECT
            Proveedor,
            Familia,
            Articulo,
            `N Factura` as NumFactura,
            fecha as Fecha,
            cantidad as Cantidad,
            Total
        FROM chatbot
        WHERE {where_clause}
        ORDER BY {fecha_expr} DESC
        LIMIT 200
    """
    return ejecutar_consulta(query, params)


# --- PRIORIDAD 11: CONSULTA GENERAL (fallback) ---

def get_consulta_general(where_clause: str, params: tuple) -> pd.DataFrame:
    """Consulta general: total de compras"""
    total_expr = _sql_total_num_expr()
    query = f"""
        SELECT
            COUNT(*) as Registros,
            COALESCE(SUM({total_expr}), 0) as Total
        FROM chatbot
        WHERE {where_clause}
    """
    return ejecutar_consulta(query, params)

def get_ultima_factura_inteligente(patron: str) -> pd.DataFrame:
    """
    Busca última factura por patrón en ARTÍCULO o PROVEEDOR automáticamente
    """
    total_expr = _sql_total_num_expr()
    fecha_expr = _sql_fecha_expr()

    query = f"""
        SELECT
            Proveedor,
            Articulo,
            cantidad,
            `N Factura` AS nro_factura,
            {total_expr} AS total_linea,
            fecha
        FROM chatbot
        WHERE 
            (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
            AND (
                LOWER(Articulo) LIKE %s 
                OR LOWER(Proveedor) LIKE %s
            )
        ORDER BY {fecha_expr} DESC
        LIMIT 1
    """
    patron_like = f"%{patron.lower()}%"
    return ejecutar_consulta(query, (patron_like, patron_like))

def get_comparacion_familia_anios_monedas(anios: List[int], familias: List[str] = None) -> pd.DataFrame:
    """Comparar familias por años ($ y USD separados)"""
    fecha_expr = _sql_fecha_expr()
    mon_expr = _sql_moneda_norm_expr()
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()

    fam_where = ""
    fam_params = []
    if familias:
        parts = []
        for f in familias:
            parts.append("TRIM(Familia) = %s")
            fam_params.append(f.upper())
        fam_where = f"AND ({' OR '.join(parts)})"

    cols = []
    for y in anios:
        cols.append(
            f"""SUM(CASE WHEN YEAR({fecha_expr}) = {y} AND {mon_expr} = '$'
                 THEN {total_pesos} ELSE 0 END) AS {y}_$"""
        )
        cols.append(
            f"""SUM(CASE WHEN YEAR({fecha_expr}) = {y} AND {mon_expr} = 'U$S'
                 THEN {total_usd} ELSE 0 END) AS {y}_USD"""
        )

    cols_sql = ",\n            ".join(cols)
    y_last = anios[-1]
    order_sql = f"{y_last}_$ DESC, {y_last}_USD DESC"

    query = f"""
        SELECT
            Familia,
            {cols_sql}
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
            AND YEAR({fecha_expr}) IN ({", ".join(str(y) for y in anios)})
            AND (
                LOWER(TRIM(COALESCE(Familia, ''))) IN ('servicio citometro', 'servicio citómetro')
                OR (
                    UPPER(TRIM(COALESCE(Familia, ''))) NOT IN (
                        'GASTOS FIJOS',
                        'INGRESOS',
                        'GASTOS IMPORTACION',
                        'GASTOS IMPORTACIÓN',
                        '_RESGUARDOS',
                        'RESGUARDOS',
                        'DESCUENTOS'
                    )
                    AND UPPER(TRIM(COALESCE(Familia, ''))) NOT LIKE 'SERVICIO%%'
                )
            )

            {fam_where}
        GROUP BY Familia
        ORDER BY {order_sql}
        LIMIT 50
    """

    return ejecutar_consulta(query, tuple(fam_params) if fam_params else None)

# =====================================================================
# FUNCIONES PARA BUSCADOR DE COMPROBANTES
# =====================================================================

def get_lista_proveedores():
    """Obtiene lista única de proveedores"""
    sql = """
        SELECT DISTINCT TRIM(Proveedor) as proveedor
        FROM chatbot
        WHERE Proveedor IS NOT NULL AND TRIM(Proveedor) != ''
        ORDER BY proveedor
    """
    df = ejecutar_consulta(sql)
    if df is not None and not df.empty:
        return ["Todos"] + df['proveedor'].tolist()
    return ["Todos"]


def get_lista_tipos_comprobante():
    """Obtiene lista única de tipos de comprobante"""
    sql = """
        SELECT DISTINCT TRIM(tipo_comprobante) as tipo
        FROM chatbot
        WHERE tipo_comprobante IS NOT NULL AND TRIM(tipo_comprobante) != ''
        ORDER BY tipo
    """
    df = ejecutar_consulta(sql)
    if df is not None and not df.empty:
        return ["Todos"] + df['tipo'].tolist()
    return ["Todos"]


def get_lista_articulos():
    """Obtiene lista única de artículos (sin límite)"""
    sql = """
        SELECT DISTINCT TRIM(Articulo) as articulo
        FROM chatbot
        WHERE Articulo IS NOT NULL AND TRIM(Articulo) != ''
        ORDER BY articulo
    """
    df = ejecutar_consulta(sql)
    if df is not None and not df.empty:
        return ["Todos"] + df['articulo'].tolist()
    return ["Todos"]


def buscar_comprobantes(proveedor=None, tipo_comprobante=None, articulo=None, 
                        fecha_desde=None, fecha_hasta=None, texto_busqueda=None):
    """
    Búsqueda de comprobantes con filtros múltiples - CORREGIDA
    """
    
    # DEBUG - ver qué parámetros llegan
    print(f"="*50)
    print(f"BUSCAR_COMPROBANTES recibió:")
    print(f"  proveedor: '{proveedor}'")
    print(f"  tipo_comprobante: '{tipo_comprobante}'")
    print(f"  articulo: '{articulo}'")
    print(f"  fecha_desde: {fecha_desde}")
    print(f"  fecha_hasta: {fecha_hasta}")
    print(f"  texto_busqueda: '{texto_busqueda}'")
    print(f"="*50)
    
    # Usar helpers que ya funcionan en otras partes del código
    fecha_expr = _sql_fecha_expr()
    
    # Base de la consulta
    sql = f"""
        SELECT 
            tipo_comprobante AS Tipo,
            `N Factura` AS Nro_Factura,
            DATE_FORMAT({fecha_expr}, '%%d/%%m/%%Y') AS Fecha,
            Proveedor,
            Articulo,
            Familia,
            cantidad AS Cantidad,
            Total AS Monto
        FROM chatbot
        WHERE 1=1
    """
    
    params = []
    
    # Filtro proveedor (extraer parte principal antes del paréntesis)
    if proveedor and proveedor != "Todos":
        prov_clean = proveedor.split('(')[0].strip()
        sql += " AND LOWER(TRIM(Proveedor)) LIKE LOWER(%s)"
        params.append(f"%{prov_clean}%")
    
    # Filtro tipo comprobante
    if tipo_comprobante and tipo_comprobante != "Todos":
        tipo_clean = tipo_comprobante.split('(')[0].strip()
        sql += " AND LOWER(TRIM(tipo_comprobante)) LIKE LOWER(%s)"
        params.append(f"%{tipo_clean}%")
    
    # Filtro artículo - usar LIKE para mayor flexibilidad
    if articulo and articulo != "Todos":
        sql += " AND LOWER(TRIM(Articulo)) LIKE LOWER(%s)"
        params.append(f"%{articulo.strip()}%")
    
    # Filtro fecha desde (usando el helper que ya funciona)
    if fecha_desde:
        fecha_str = fecha_desde.strftime('%Y-%m-%d')
        sql += f" AND {fecha_expr} >= %s"
        params.append(fecha_str)
    
    # Filtro fecha hasta
    if fecha_hasta:
        fecha_str = fecha_hasta.strftime('%Y-%m-%d')
        sql += f" AND {fecha_expr} <= %s"
        params.append(fecha_str)
    
    # Búsqueda por texto libre
    if texto_busqueda and texto_busqueda.strip():
        sql += """ AND (
            `N Factura` LIKE %s 
            OR LOWER(Articulo) LIKE LOWER(%s)
            OR LOWER(Proveedor) LIKE LOWER(%s)
        )"""
        texto = f"%{texto_busqueda.strip()}%"
        params.extend([texto, texto, texto])
    
    sql += f" ORDER BY {fecha_expr} DESC LIMIT 200"
    
    # DEBUG - ver en consola qué se ejecuta
    print(f"DEBUG SQL: {sql}")
    print(f"DEBUG PARAMS: {params}")
    
    return ejecutar_consulta(sql, tuple(params) if params else None)


# =====================================================================
# FUNCIONES PARA BÚSQUEDA EN TABLA STOCK (LOTES)
# =====================================================================

def get_lista_articulos_stock():
    """Obtiene lista única de artículos de la tabla stock"""
    sql = """
        SELECT DISTINCT TRIM(ARTICULO) as articulo
        FROM stock
        WHERE ARTICULO IS NOT NULL 
          AND TRIM(ARTICULO) != '' 
          AND TRIM(ARTICULO) != 'ARTICULO'
        ORDER BY articulo
    """
    df = ejecutar_consulta(sql)
    if df is not None and not df.empty:
        return ["Todos"] + df['articulo'].tolist()
    return ["Todos"]


def get_lista_familias_stock():
    """Obtiene lista única de familias de la tabla stock"""
    sql = """
        SELECT DISTINCT TRIM(FAMILIA) as familia
        FROM stock
        WHERE FAMILIA IS NOT NULL 
          AND TRIM(FAMILIA) != ''
          AND FAMILIA NOT IN ('CONSULTA LOTES Y VENCIMIENTO', 'Stock Disponible', 'Documento generado por GNS Software', 'FAMILIA')
        ORDER BY familia
    """
    df = ejecutar_consulta(sql)
    if df is not None and not df.empty:
        return ["Todos"] + df['familia'].tolist()
    return ["Todos"]


def get_lista_depositos_stock():
    """Obtiene lista única de depósitos de la tabla stock"""
    sql = """
        SELECT DISTINCT TRIM(DEPOSITO) as deposito
        FROM stock
        WHERE DEPOSITO IS NOT NULL AND TRIM(DEPOSITO) != ''
        ORDER BY deposito
    """
    df = ejecutar_consulta(sql)
    if df is not None and not df.empty:
        return ["Todos"] + df['deposito'].tolist()
    return ["Todos"]


def buscar_stock_por_lote(articulo=None, lote=None, familia=None, deposito=None, texto_busqueda=None):
    """
    Búsqueda en tabla stock con filtros múltiples
    """
    
    # DEBUG
    print(f"="*50)
    print(f"BUSCAR_STOCK_POR_LOTE recibió:")
    print(f"  articulo: '{articulo}'")
    print(f"  lote: '{lote}'")
    print(f"  familia: '{familia}'")
    print(f"  deposito: '{deposito}'")
    print(f"  texto_busqueda: '{texto_busqueda}'")
    print(f"="*50)
    
    sql = """
        SELECT 
            FAMILIA,
            CODIGO,
            ARTICULO,
            DEPOSITO,
            LOTE,
            VENCIMIENTO,
            STOCK
        FROM stock
        WHERE 1=1
          AND (ARTICULO IS NOT NULL AND TRIM(ARTICULO) != '' AND TRIM(ARTICULO) != 'ARTICULO' AND TRIM(ARTICULO) != 'Proveedor:')
          AND (FAMILIA IS NULL OR (
               TRIM(FAMILIA) NOT IN ('CONSULTA LOTES Y VENCIMIENTO', 'Stock Disponible', 'Documento generado por GNS Software', 'FAMILIA', 'Empresa:')
               AND TRIM(FAMILIA) NOT LIKE 'FERTILAB%'
          ))
          AND (CODIGO IS NULL OR TRIM(CODIGO) NOT IN ('CODIGO', 'FERTILAB SA - (FERTILAB SA)'))
          AND (LOTE IS NULL OR TRIM(LOTE) NOT IN ('NRO.LOTE', 'Usuario:'))
          AND (DEPOSITO IS NULL OR TRIM(DEPOSITO) NOT IN ('DEPOSITO', 'Fecha Desde:'))
    """
    
    params = []
    
    # Filtro artículo
    if articulo and articulo != "Todos":
        sql += " AND LOWER(TRIM(ARTICULO)) LIKE LOWER(%s)"
        params.append(f"%{articulo}%")
    
    # Filtro lote
    if lote and lote.strip():
        sql += " AND TRIM(LOTE) LIKE %s"
        params.append(f"%{lote.strip()}%")
    
    # Filtro familia
    if familia and familia != "Todos":
        sql += " AND TRIM(FAMILIA) = %s"
        params.append(familia)
    
    # Filtro depósito
    if deposito and deposito != "Todos":
        sql += " AND TRIM(DEPOSITO) = %s"
        params.append(deposito)
    
    # Búsqueda por texto libre
    if texto_busqueda and texto_busqueda.strip():
        sql += """ AND (
            LOWER(ARTICULO) LIKE LOWER(%s)
            OR LOTE LIKE %s
            OR CODIGO LIKE %s
        )"""
        texto = f"%{texto_busqueda.strip()}%"
        params.extend([texto, texto, texto])
    
    sql += " ORDER BY STR_TO_DATE(VENCIMIENTO, '%d/%m/%Y') ASC LIMIT 200"
    
    # DEBUG
    print(f"DEBUG SQL STOCK: {sql}")
    print(f"DEBUG PARAMS: {params}")
    
    return ejecutar_consulta(sql, tuple(params) if params else None)


# =====================================================================
# FUNCIONES PARA STOCK IA (CHATBOT)
# =====================================================================

def _filtro_metadata_stock():
    """Filtro para excluir metadata/encabezados de la tabla stock"""
    return """
        (ARTICULO IS NOT NULL AND TRIM(ARTICULO) != '' AND TRIM(ARTICULO) != 'ARTICULO' AND TRIM(ARTICULO) != 'Proveedor:')
        AND (FAMILIA IS NULL OR (
             TRIM(FAMILIA) NOT IN ('CONSULTA LOTES Y VENCIMIENTO', 'Stock Disponible', 'Documento generado por GNS Software', 'FAMILIA', 'Empresa:')
             AND TRIM(FAMILIA) NOT LIKE 'FERTILAB%'
        ))
        AND (CODIGO IS NULL OR TRIM(CODIGO) NOT IN ('CODIGO', 'FERTILAB SA - (FERTILAB SA)'))
        AND (LOTE IS NULL OR TRIM(LOTE) NOT IN ('NRO.LOTE', 'Usuario:'))
        AND (DEPOSITO IS NULL OR TRIM(DEPOSITO) NOT IN ('DEPOSITO', 'Fecha Desde:'))
    """


def get_stock_total():
    """Total de stock disponible"""
    filtro = _filtro_metadata_stock()
    sql = f"""
        SELECT 
            COUNT(*) AS Registros,
            SUM(CAST(REPLACE(STOCK, ',', '.') AS DECIMAL(15,2))) AS Stock_Total
        FROM stock
        WHERE {filtro}
    """
    return ejecutar_consulta(sql)


def get_stock_por_familia():
    """Stock agrupado por familia"""
    filtro = _filtro_metadata_stock()
    sql = f"""
        SELECT 
            FAMILIA,
            COUNT(*) AS Articulos,
            SUM(CAST(REPLACE(STOCK, ',', '.') AS DECIMAL(15,2))) AS Stock_Total
        FROM stock
        WHERE {filtro}
        GROUP BY FAMILIA
        ORDER BY Stock_Total DESC
    """
    return ejecutar_consulta(sql)


def get_stock_por_deposito():
    """Stock agrupado por depósito"""
    filtro = _filtro_metadata_stock()
    sql = f"""
        SELECT 
            DEPOSITO,
            COUNT(*) AS Articulos,
            SUM(CAST(REPLACE(STOCK, ',', '.') AS DECIMAL(15,2))) AS Stock_Total
        FROM stock
        WHERE {filtro}
        GROUP BY DEPOSITO
        ORDER BY Stock_Total DESC
    """
    return ejecutar_consulta(sql)


def get_stock_articulo(patron_articulo: str):
    """Stock de un artículo específico"""
    filtro = _filtro_metadata_stock()
    sql = f"""
        SELECT 
            FAMILIA,
            CODIGO,
            ARTICULO,
            DEPOSITO,
            LOTE,
            VENCIMIENTO,
            STOCK
        FROM stock
        WHERE {filtro}
          AND LOWER(ARTICULO) LIKE LOWER(%s)
        ORDER BY STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') ASC
        LIMIT 50
    """
    return ejecutar_consulta(sql, (f"%{patron_articulo}%",))


def get_lotes_por_vencer(dias: int = 90):
    """Lotes que vencen en los próximos X días"""
    filtro = _filtro_metadata_stock()
    sql = f"""
        SELECT 
            FAMILIA,
            CODIGO,
            ARTICULO,
            DEPOSITO,
            LOTE,
            VENCIMIENTO,
            STOCK,
            DATEDIFF(STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y'), CURDATE()) AS Dias_Para_Vencer
        FROM stock
        WHERE {filtro}
          AND STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') IS NOT NULL
          AND STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') >= CURDATE()
          AND STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') <= DATE_ADD(CURDATE(), INTERVAL %s DAY)
        ORDER BY STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') ASC
        LIMIT 100
    """
    return ejecutar_consulta(sql, (dias,))


def get_alerta_proximo_vencimiento():
    """Obtiene el lote más próximo a vencer (para alerta)"""
    filtro = _filtro_metadata_stock()
    sql = f"""
        SELECT 
            ARTICULO,
            LOTE,
            VENCIMIENTO,
            STOCK,
            DATEDIFF(STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y'), CURDATE()) AS Dias_Para_Vencer
        FROM stock
        WHERE {filtro}
          AND STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') IS NOT NULL
          AND STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') >= CURDATE()
          AND CAST(REPLACE(STOCK, ',', '.') AS DECIMAL(15,2)) > 0
        ORDER BY STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') ASC
        LIMIT 1
    """
    df = ejecutar_consulta(sql)
    if df is not None and not df.empty:
        row = df.iloc[0]
        return {
            'articulo': row.get('ARTICULO', ''),
            'lote': row.get('LOTE', ''),
            'vencimiento': row.get('VENCIMIENTO', ''),
            'stock': row.get('STOCK', 0),
            'dias': int(row.get('Dias_Para_Vencer', 0)) if pd.notna(row.get('Dias_Para_Vencer')) else 0
        }
    return None


def get_alertas_vencimiento_multiple(limite: int = 10):
    """Obtiene múltiples lotes próximos a vencer (rojos y naranjas, hasta 60 días)"""
    filtro = _filtro_metadata_stock()
    sql = f"""
        SELECT 
            ARTICULO,
            LOTE,
            VENCIMIENTO,
            STOCK,
            DATEDIFF(STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y'), CURDATE()) AS Dias_Para_Vencer
        FROM stock
        WHERE {filtro}
          AND STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') IS NOT NULL
          AND STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') >= CURDATE()
          AND STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') <= DATE_ADD(CURDATE(), INTERVAL 60 DAY)
          AND CAST(REPLACE(STOCK, ',', '.') AS DECIMAL(15,2)) > 0
        ORDER BY STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') ASC
        LIMIT %s
    """
    df = ejecutar_consulta(sql, (limite,))
    alertas = []
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            alertas.append({
                'articulo': row.get('ARTICULO', ''),
                'lote': row.get('LOTE', ''),
                'vencimiento': row.get('VENCIMIENTO', ''),
                'stock': row.get('STOCK', 0),
                'dias': int(row.get('Dias_Para_Vencer', 0)) if pd.notna(row.get('Dias_Para_Vencer')) else 0
            })
    return alertas


def get_lotes_vencidos():
    """Lotes ya vencidos"""
    filtro = _filtro_metadata_stock()
    sql = f"""
        SELECT 
            FAMILIA,
            CODIGO,
            ARTICULO,
            DEPOSITO,
            LOTE,
            VENCIMIENTO,
            STOCK,
            DATEDIFF(CURDATE(), STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y')) AS Dias_Vencido
        FROM stock
        WHERE {filtro}
          AND STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') IS NOT NULL
          AND STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') < CURDATE()
        ORDER BY STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') DESC
        LIMIT 100
    """
    return ejecutar_consulta(sql)


def get_stock_bajo(limite: int = 10):
    """Artículos con stock bajo"""
    filtro = _filtro_metadata_stock()
    sql = f"""
        SELECT 
            FAMILIA,
            CODIGO,
            ARTICULO,
            DEPOSITO,
            LOTE,
            VENCIMIENTO,
            STOCK
        FROM stock
        WHERE {filtro}
          AND CAST(REPLACE(STOCK, ',', '.') AS DECIMAL(15,2)) <= %s
          AND CAST(REPLACE(STOCK, ',', '.') AS DECIMAL(15,2)) > 0
        ORDER BY CAST(REPLACE(STOCK, ',', '.') AS DECIMAL(15,2)) ASC
        LIMIT 100
    """
    return ejecutar_consulta(sql, (limite,))


def get_stock_lote_especifico(lote: str):
    """Buscar un lote específico"""
    filtro = _filtro_metadata_stock()
    sql = f"""
        SELECT 
            FAMILIA,
            CODIGO,
            ARTICULO,
            DEPOSITO,
            LOTE,
            VENCIMIENTO,
            STOCK
        FROM stock
        WHERE {filtro}
          AND TRIM(LOTE) LIKE %s
        ORDER BY STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') ASC
    """
    return ejecutar_consulta(sql, (f"%{lote}%",))


def get_stock_familia(familia: str):
    """Stock de una familia específica"""
    filtro = _filtro_metadata_stock()
    sql = f"""
        SELECT 
            FAMILIA,
            CODIGO,
            ARTICULO,
            DEPOSITO,
            LOTE,
            VENCIMIENTO,
            STOCK
        FROM stock
        WHERE {filtro}
          AND UPPER(TRIM(FAMILIA)) = UPPER(%s)
        ORDER BY ARTICULO, STR_TO_DATE(VENCIMIENTO, '%%d/%%m/%%Y') ASC
        LIMIT 100
    """
    return ejecutar_consulta(sql, (familia,))


# =====================================================================
# FUNCIONES PARA DASHBOARD
# =====================================================================

def get_dashboard_compras_por_mes(anio: int) -> pd.DataFrame:
    """Compras por mes para gráfico de barras"""
    total_expr = _sql_total_num_expr()
    fecha_expr = _sql_fecha_expr()
    
    query = f"""
        SELECT 
            MONTH({fecha_expr}) AS Mes_Num,
            CASE MONTH({fecha_expr})
                WHEN 1 THEN 'Ene'
                WHEN 2 THEN 'Feb'
                WHEN 3 THEN 'Mar'
                WHEN 4 THEN 'Abr'
                WHEN 5 THEN 'May'
                WHEN 6 THEN 'Jun'
                WHEN 7 THEN 'Jul'
                WHEN 8 THEN 'Ago'
                WHEN 9 THEN 'Sep'
                WHEN 10 THEN 'Oct'
                WHEN 11 THEN 'Nov'
                WHEN 12 THEN 'Dic'
            END AS Mes,
            SUM({total_expr}) AS Total
        FROM chatbot
        WHERE YEAR({fecha_expr}) = %s
          AND (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
        GROUP BY MONTH({fecha_expr})
        ORDER BY MONTH({fecha_expr})
    """
    return ejecutar_consulta(query, (anio,))


# =========================
# TOP 10 PROVEEDORES - CHATBOT COMPRAS IA (MONEDA + FECHA)
# =========================
def get_top_10_proveedores_chatbot(moneda: str = None, anio: int = None, mes: str = None):
    fecha_expr = _sql_fecha_expr()
    mon_expr = _sql_moneda_norm_expr()

    where_fecha = ""
    params = []

    # --- FILTRO AÑO ---
    if anio:
        where_fecha += f" AND YEAR({fecha_expr}) = %s"
        params.append(anio)

    # --- FILTRO MES (YYYY-MM) ---
    if mes:
        where_fecha += f" AND DATE_FORMAT({fecha_expr}, '%%Y-%%m') = %s"
        params.append(mes)

    # =========================
    # CASO 1: PESOS
    # =========================
    if moneda and moneda.upper() in ("$", "UYU", "PESOS"):
        total_expr = _sql_total_num_expr()

        sql = f"""
            SELECT
                Proveedor,
                '$' AS Moneda,
                SUM({total_expr}) AS Total,
                COUNT(DISTINCT `N Factura`) AS Facturas
            FROM chatbot
            WHERE
                (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
                AND Proveedor IS NOT NULL
                AND {mon_expr} = '$'
                {where_fecha}
            GROUP BY Proveedor
            ORDER BY Total DESC
            LIMIT 10
        """
        return ejecutar_consulta(sql, tuple(params))

    # =========================
    # CASO 2: USD
    # =========================
    if moneda and moneda.upper() in ("U$S", "USD", "U$$"):
        total_expr = _sql_total_num_expr_usd()

        sql = f"""
            SELECT
                Proveedor,
                'U$S' AS Moneda,
                SUM({total_expr}) AS Total,
                COUNT(DISTINCT `N Factura`) AS Facturas
            FROM chatbot
            WHERE
                (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
                AND Proveedor IS NOT NULL
                AND {mon_expr} IN ('U$S','U$$')
                {where_fecha}
            GROUP BY Proveedor
            ORDER BY Total DESC
            LIMIT 10
        """
        return ejecutar_consulta(sql, tuple(params))

    # =========================
    # CASO 3: SIN MONEDA → SEPARAR
    # =========================
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()

    sql = f"""
        SELECT
            Proveedor,
            {mon_expr} AS Moneda,
            SUM(
                CASE
                    WHEN {mon_expr} = '$' THEN {total_pesos}
                    WHEN {mon_expr} IN ('U$S','U$$') THEN {total_usd}
                    ELSE 0
                END
            ) AS Total,
            COUNT(DISTINCT `N Factura`) AS Facturas
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
            AND Proveedor IS NOT NULL
            AND {mon_expr} IN ('$', 'U$S', 'U$$')
            {where_fecha}
        GROUP BY Proveedor, {mon_expr}
        ORDER BY Total DESC
        LIMIT 10
    """
    return ejecutar_consulta(sql, tuple(params))


def get_dashboard_top_proveedores(anio: int, limite: int = 10, moneda: str = "$") -> pd.DataFrame:
    """Top proveedores por monto, discriminado por moneda ($ o U$S).
    - moneda: "$" (pesos) o "U$S" (dólares). También acepta "USD" o "U$$" como sinónimos.
    """
    fecha_expr = _sql_fecha_expr()
    mon_expr = _sql_moneda_norm_expr()

    mon = (moneda or "$").strip().upper()

    # ✅ Elegir expresión de total + filtro de moneda
    if mon in ("U$S", "USD", "U$$"):
        total_expr = _sql_total_num_expr_usd()
        moneda_where = f"{mon_expr} IN ('U$S', 'U$$')"
        label_m = "U$S"
    else:
        total_expr = _sql_total_num_expr()
        moneda_where = f"{mon_expr} = '$'"
        label_m = "$"

    query = f"""
        SELECT
            Proveedor,
            '{label_m}' AS Moneda,
            SUM({total_expr}) AS Total,
            COUNT(DISTINCT `N Factura`) AS Cantidad_Facturas
        FROM chatbot
        WHERE YEAR({fecha_expr}) = %s
          AND (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
          AND Proveedor IS NOT NULL
          AND {moneda_where}
        GROUP BY Proveedor
        ORDER BY SUM({total_expr}) DESC
        LIMIT %s
    """
    return ejecutar_consulta(query, (anio, limite))


def get_dashboard_gastos_familia(anio: int) -> pd.DataFrame:
    """Gastos por familia para gráfico de torta"""
    total_expr = _sql_total_num_expr()
    fecha_expr = _sql_fecha_expr()
    
    query = f"""
        SELECT 
            COALESCE(Familia, 'SIN FAMILIA') AS Familia,
            SUM({total_expr}) AS Total
        FROM chatbot
        WHERE YEAR({fecha_expr}) = %s
          AND (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
        GROUP BY Familia
        HAVING SUM({total_expr}) > 0
        ORDER BY SUM({total_expr}) DESC
        LIMIT 10
    """
    return ejecutar_consulta(query, (anio,))


def get_dashboard_totales(anio: int) -> dict:
    """Totales generales para métricas"""
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()
    fecha_expr = _sql_fecha_expr()
    mon_expr = _sql_moneda_norm_expr()
    
    query = f"""
        SELECT 
            SUM(CASE WHEN {mon_expr} = '$' THEN {total_pesos} ELSE 0 END) AS Total_Pesos,
            SUM(CASE WHEN {mon_expr} = 'U$S' THEN {total_usd} ELSE 0 END) AS Total_USD,
            COUNT(DISTINCT Proveedor) AS Proveedores,
            COUNT(DISTINCT `N Factura`) AS Facturas
        FROM chatbot
        WHERE YEAR({fecha_expr}) = %s
          AND (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
    """
    df = ejecutar_consulta(query, (anio,))
    if df is not None and not df.empty:
        row = df.iloc[0]
        return {
            'total_pesos': float(row['Total_Pesos']) if pd.notna(row['Total_Pesos']) else 0,
            'total_usd': float(row['Total_USD']) if pd.notna(row['Total_USD']) else 0,
            'proveedores': int(row['Proveedores']) if pd.notna(row['Proveedores']) else 0,
            'facturas': int(row['Facturas']) if pd.notna(row['Facturas']) else 0
        }
    return {'total_pesos': 0, 'total_usd': 0, 'proveedores': 0, 'facturas': 0}


def get_dashboard_ultimas_compras(limite: int = 5) -> pd.DataFrame:
    """Últimas compras realizadas"""
    total_expr = _sql_total_num_expr()
    fecha_expr = _sql_fecha_expr()
    
    query = f"""
        SELECT 
            DATE_FORMAT({fecha_expr}, '%%d/%%m/%%Y') AS Fecha,
            Proveedor,
            Articulo,
            {total_expr} AS Total
        FROM chatbot
        WHERE (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
          AND LOWER(Articulo) NOT LIKE '%%ajuste%%'
          AND LOWER(Articulo) NOT LIKE '%%redondeo%%'
          AND {total_expr} > 0
        ORDER BY {fecha_expr} DESC
        LIMIT %s
    """
    return ejecutar_consulta(query, (limite,))
# =========================
# COMPRAS: TOTAL POR ARTÍCULO + AÑO
# =========================

# =========================
# DETALLE COMPRAS: ARTÍCULO + AÑO (CON LÍMITE)
# =========================
def get_detalle_compras_articulo_anio(articulo_like: str, anio: int, limite: int = 200):
    fecha_expr = _sql_fecha_expr()
    total_expr = _sql_total_num_expr_general()

    sql = f"""
        SELECT
            Proveedor,
            Articulo,
            `N Factura` AS Nro_Factura,
            DATE_FORMAT({fecha_expr}, '%%d/%%m/%%Y') AS Fecha,
            cantidad AS Cantidad,
            Moneda,
            {total_expr} AS Total
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
            AND YEAR({fecha_expr}) = %s
            AND LOWER(Articulo) LIKE %s
        ORDER BY {fecha_expr} DESC
        LIMIT {int(limite)}
    """

    params = (anio, f"%{articulo_like.lower()}%")
    df = ejecutar_consulta(sql, params)

    # 🔥 Limpieza defensiva (por si en algún lado entra igual)
    if df is not None and not df.empty:
        cols_borrar = []
        for c in df.columns:
            cl = str(c).strip().lower()
            if cl in ("tipo_cfe", "anio", "año", "mes"):
                cols_borrar.append(c)
        if cols_borrar:
            df = df.drop(columns=cols_borrar, errors="ignore")

    return df


# =========================
# TOTAL COMPRAS: ARTÍCULO + AÑO (SIN LÍMITE)
# =========================
def get_total_compras_articulo_anio(articulo_like: str, anio: int) -> dict:
    fecha_expr = _sql_fecha_expr()
    total_expr = _sql_total_num_expr_general()

    sql = f"""
        SELECT
            COUNT(*) AS registros,
            COALESCE(SUM({total_expr}), 0) AS total
        FROM chatbot
        WHERE
            (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
            AND YEAR({fecha_expr}) = %s
            AND LOWER(Articulo) LIKE %s
    """

    params = (anio, f"%{articulo_like.lower()}%")
    df = ejecutar_consulta(sql, params)

    if df is not None and not df.empty:
        reg = df["registros"].iloc[0] if "registros" in df.columns else 0
        tot = df["total"].iloc[0] if "total" in df.columns else 0

        return {
            "registros": int(reg) if pd.notna(reg) else 0,
            "total": float(tot) if pd.notna(tot) else 0
        }

    return {"registros": 0, "total": 0}
