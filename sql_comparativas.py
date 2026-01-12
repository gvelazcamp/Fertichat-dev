# =========================
# SQL COMPARATIVAS - ANÁLISIS Y COMPARACIONES
# =========================

import pandas as pd
from typing import List

from sql_core import (
    ejecutar_consulta,
    _sql_total_num_expr,
    _sql_total_num_expr_usd,
    _sql_total_num_expr_general
)


# =====================================================================
# COMPARACIONES POR MESES
# =====================================================================

def get_comparacion_proveedor_meses(*args, **kwargs) -> pd.DataFrame:
    """
    Compatible con 2 firmas (para no romper nada):

    A) Nueva (canónica):
       get_comparacion_proveedor_meses(proveedor, mes1, mes2, label1, label2)

    B) Vieja (versión anterior):
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
    label1_sql = str(label1).replace('"', "").strip()
    label2_sql = str(label2).replace('"', "").strip()

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


def get_comparacion_proveedor_anios_like(proveedor_like: str, anios: list[int]) -> pd.DataFrame:
    """
    ✅ VERSIÓN LIMITADA: Trae solo el proveedor con más compras que matchee el LIKE.
    """
    proveedor_like = proveedor_like.strip().lower()

    anios = sorted(anios)
    if len(anios) < 2:
        print(f"⚠️ get_comparacion_proveedor_anios_like: necesita al menos 2 años, recibió {len(anios)}")
        return pd.DataFrame()

    a1, a2 = anios[0], anios[1]
    total_expr = _sql_total_num_expr_general()

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
        ORDER BY total_general DESC
        LIMIT 1
    """

    params = (
        a1,
        a2,
        f"%{proveedor_like}%",
        a1,
        a2,
    )

    df = ejecutar_consulta(sql, params)

    if df is not None and not df.empty and "total_general" in df.columns:
        df = df.drop(columns=["total_general"])

    return df


def get_comparacion_proveedor_anios(proveedor: str, anios: List[int]) -> pd.DataFrame:
    """
    Compara un proveedor específico entre años (coincidencia exacta, no LIKE).
    Ej:
      get_comparacion_proveedor_anios("roche", [2024, 2025])
    Devuelve filas con el proveedor y columnas por año (y Diferencia si hay 2 años).
    """
    if not proveedor or not anios:
        return pd.DataFrame()
    
    # Normalizar años a int
    anios_ok: List[int] = []
    for y in anios:
        try:
            anios_ok.append(int(y))
        except Exception:
            pass
    
    anios_ok = sorted(list(set(anios_ok)))
    if len(anios_ok) < 2:
        return pd.DataFrame()
    
    total_expr = _sql_total_num_expr_general()
    
    # Columnas por año
    cols = []
    for y in anios_ok:
        cols.append(
            f"""SUM(CASE WHEN "Año"::int = {y} THEN {total_expr} ELSE 0 END) AS "{y}" """
        )
    cols_sql = ",\n            ".join(cols)
    
    # Diferencia solo si hay exactamente 2 años
    diff_sql = ""
    if len(anios_ok) == 2:
        y1, y2 = anios_ok[0], anios_ok[1]
        diff_sql = f""",
            (SUM(CASE WHEN "Año"::int = {y2} THEN {total_expr} ELSE 0 END) -
             SUM(CASE WHEN "Año"::int = {y1} THEN {total_expr} ELSE 0 END)) AS Diferencia
        """
    
    anios_sql = ", ".join(str(y) for y in anios_ok)
    
    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            {cols_sql}
            {diff_sql}
        FROM chatbot_raw
        WHERE LOWER(TRIM("Cliente / Proveedor")) = %s
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año"::int IN ({anios_sql})
        GROUP BY TRIM("Cliente / Proveedor")
        ORDER BY Proveedor
        LIMIT 300
    """
    
    return ejecutar_consulta(sql, (proveedor.strip().lower(),))


def get_comparacion_proveedor_anios_monedas(anios: List[int], proveedores: List[str] = None) -> pd.DataFrame:
    """Compara proveedores por años con separación de monedas."""
    total_pesos = _sql_total_num_expr()
    total_usd = _sql_total_num_expr_usd()
    anios = sorted(anios)

    prov_where = ""
    prov_params = []
    if proveedores:
        parts = [f'LOWER(TRIM("Cliente / Proveedor")) LIKE %s' for _ in proveedores]
        prov_params = [f"%{p.lower()}%" for p in proveedores]
        prov_where = f"AND ({' OR '.join(parts)})"

    cols = []
    for y in anios:
        cols.append(
            f"""SUM(CASE WHEN "Año"::int = {y} AND TRIM("Moneda") = '$' THEN {total_pesos} ELSE 0 END) AS "{y}_$" """
        )
        cols.append(
            f"""SUM(CASE WHEN "Año"::int = {y} AND TRIM("Moneda") IN ('U$S','U$$') THEN {total_usd} ELSE 0 END) AS "{y}_USD" """
        )

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
        parts = [f'TRIM(COALESCE("Familia", \'\')) = %s' for _ in familias]
        fam_params = list(familias)
        fam_where = f"AND ({' OR '.join(parts)})"

    cols = []
    for y in anios:
        cols.append(
            f"""SUM(CASE WHEN "Año"::int = {y} AND TRIM("Moneda") = '$' THEN {total_pesos} ELSE 0 END) AS "{y}_$" """
        )
        cols.append(
            f"""SUM(CASE WHEN "Año"::int = {y} AND TRIM("Moneda") IN ('U$S','U$$') THEN {total_usd} ELSE 0 END) AS "{y}_USD" """
        )

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
# COMPARACIÓN MULTI PROVEEDORES - MULTI MESES (FIX)
# =====================================================================

def get_comparacion_proveedores_meses_multi(
    proveedores: List[str],
    meses: List[str]
) -> pd.DataFrame:
    """
    Compara múltiples proveedores en múltiples meses.
    Ej:
      proveedores = ["roche", "biodiagnostico", "tresul"]
      meses = ["2025-06", "2025-07"]
    """

    if not proveedores or not meses:
        return pd.DataFrame()

    total_expr = _sql_total_num_expr_general()

    # 1) Columnas dinámicas por mes (sus %s van PRIMERO en params)
    cols = []
    params: List = []
    for m in meses:
        cols.append(
            f"""SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) AS "{m}" """
        )
        params.append(m)

    cols_sql = ",\n            ".join(cols)

    # 2) WHERE proveedores (sus %s van DESPUÉS)
    prov_clauses = []
    for p in proveedores:
        p_norm = p.strip().lower()
        if not p_norm:
            continue
        prov_clauses.append('LOWER(TRIM("Cliente / Proveedor")) LIKE %s')
        params.append(f"%{p_norm}%")

    if not prov_clauses:
        return pd.DataFrame()

    prov_where = " OR ".join(prov_clauses)

    # 3) IN meses (sus %s van AL FINAL)
    meses_placeholders = ", ".join(["%s"] * len(meses))
    params.extend(meses)

    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            {cols_sql}
        FROM chatbot_raw
        WHERE ({prov_where})
          AND TRIM("Mes") IN ({meses_placeholders})
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
        GROUP BY TRIM("Cliente / Proveedor")
        ORDER BY Proveedor
        LIMIT 300
    """

    return ejecutar_consulta(sql, tuple(params))


# =====================================================================
# COMPARACIÓN MULTI PROVEEDORES - MULTI AÑOS (NUEVO)
# =====================================================================

def get_comparacion_proveedores_anios_multi(
    proveedores: List[str],
    anios: List[int]
) -> pd.DataFrame:
    """
    Compara múltiples proveedores en múltiples años.
    Ej:
      proveedores = ["roche", "tresul"]
      anios = [2024, 2025]
    Devuelve filas por Proveedor y columnas por año (y Diferencia si hay 2 años).
    """

    if not proveedores or not anios:
        return pd.DataFrame()

    # Normalizar años a int
    anios_ok: List[int] = []
    for y in anios:
        try:
            anios_ok.append(int(y))
        except Exception:
            pass

    anios_ok = sorted(list(set(anios_ok)))
    if len(anios_ok) < 2:
        return pd.DataFrame()

    total_expr = _sql_total_num_expr_general()

    # Columnas por año (embebidas como int seguro)
    cols = []
    for y in anios_ok:
        cols.append(
            f"""SUM(CASE WHEN "Año"::int = {y} THEN {total_expr} ELSE 0 END) AS "{y}" """
        )
    cols_sql = ",\n            ".join(cols)

    # Diferencia solo si hay exactamente 2 años
    diff_sql = ""
    if len(anios_ok) == 2:
        y1, y2 = anios_ok[0], anios_ok[1]
        diff_sql = f""",
            (SUM(CASE WHEN "Año"::int = {y2} THEN {total_expr} ELSE 0 END) -
             SUM(CASE WHEN "Año"::int = {y1} THEN {total_expr} ELSE 0 END)) AS Diferencia
        """

    anios_sql = ", ".join(str(y) for y in anios_ok)

    # WHERE proveedores
    prov_clauses = []
    params: List = []
    for p in proveedores:
        p_norm = p.strip().lower()
        if not p_norm:
            continue
        prov_clauses.append('LOWER(TRIM("Cliente / Proveedor")) LIKE %s')
        params.append(f"%{p_norm}%")

    if not prov_clauses:
        return pd.DataFrame()

    prov_where = " OR ".join(prov_clauses)

    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            {cols_sql}
            {diff_sql}
        FROM chatbot_raw
        WHERE ({prov_where})
          AND ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
          AND "Año"::int IN ({anios_sql})
        GROUP BY TRIM("Cliente / Proveedor")
        ORDER BY Proveedor
        LIMIT 300
    """

    return ejecutar_consulta(sql, tuple(params))


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
