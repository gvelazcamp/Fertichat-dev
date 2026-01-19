# =========================
# SQL COMPARATIVAS - ANÁLISIS Y COMPARACIONES
# =========================

import pandas as pd
from typing import List, Optional

from sql_core import (
    ejecutar_consulta,
    _sql_total_num_expr,
    _sql_total_num_expr_usd,
    _sql_total_num_expr_general
)

# =====================================================================
# EXPRESIÓN TOTAL NUMÉRICA GENERAL (ACTUALIZADA PARA "Monto Neto")
# =====================================================================
def _sql_total_num_expr_general() -> str:
    """
    Expresión SQL para calcular el total numérico desde "Monto Neto".
    Maneja formatos LATAM (coma como decimal), negativos en paréntesis, y limpia espacios/dólares.
    """
    return '''
        CASE 
            WHEN TRIM(REPLACE("Monto Neto", ' ', '')) LIKE '(%%)' THEN 
                -1 * COALESCE(CAST(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                SUBSTRING(TRIM(REPLACE("Monto Neto", ' ', '')), 2, LENGTH(TRIM(REPLACE("Monto Neto", ' ', ''))) - 2), 
                                '.', ''
                            ), 
                            ',', '.'
                        ), 
                        '$', ''
                    ) AS NUMERIC
                ), 0)
            ELSE 
                COALESCE(CAST(
                    REPLACE(
                        REPLACE(
                            REPLACE(TRIM(REPLACE("Monto Neto", ' ', '')), '.', ''), 
                            ',', '.'
                        ), 
                        '$', ''
                    ) AS NUMERIC
                ), 0)
        END
    '''

# =====================================================================
# 🆕 FUNCIÓN PRINCIPAL PARA MENÚ DE COMPARATIVAS
# =====================================================================

def comparar_compras(
    anios: Optional[List[int]] = None,
    meses: Optional[List[str]] = None,
    proveedores: Optional[List[str]] = None,
    articulos: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    🎯 FUNCIÓN UNIVERSAL DE COMPARATIVAS
    Compara proveedores o artículos entre años o meses.
    """
    if not anios and not meses:
        print("⚠️ comparar_compras: Se requiere anios o meses")
        return pd.DataFrame()

    usar_meses = bool(meses)
    tiempos = meses if usar_meses else anios

    if not tiempos or len(tiempos) < 2:
        print(f"⚠️ comparar_compras: Se requieren al menos 2 tiempos, recibió {len(tiempos) if tiempos else 0}")
        return pd.DataFrame()

    tiempos_sorted = sorted(list(set(tiempos)))

    total_expr = _sql_total_num_expr_general()

    # ✅ USAR FILTER en lugar de CASE WHEN para mejor performance
    cols = []
    for t in tiempos_sorted:
        if usar_meses:
            cols.append(f"""SUM({total_expr}) FILTER (WHERE TRIM("Mes") = '{t}') AS "{t}" """)
        else:
            # ✅ Año es INTEGER en la BD
            cols.append(f"""SUM({total_expr}) FILTER (WHERE "Año" = {int(t)}) AS "{t}" """)

    cols_sql = ",\n            ".join(cols)
    
    diff_sql = ""
    if len(tiempos_sorted) == 2:
        t1, t2 = tiempos_sorted[0], tiempos_sorted[1]
        if usar_meses:
            diff_sql = f""",
                (SUM({total_expr}) FILTER (WHERE TRIM("Mes") = '{t2}') -
                 SUM({total_expr}) FILTER (WHERE TRIM("Mes") = '{t1}')) AS Diferencia
            """
        else:
            diff_sql = f""",
                (SUM({total_expr}) FILTER (WHERE "Año" = {int(t2)}) -
                 SUM({total_expr}) FILTER (WHERE "Año" = {int(t1)})) AS Diferencia
            """

    # ✅ CONSTRUIR FILTROS
    params: List = []
    
    prov_where = ""
    if proveedores:
        prov_clauses = []
        for p in proveedores:
            p_norm = p.strip().lower()
            if not p_norm:
                continue
            prov_clauses.append('LOWER(TRIM("Cliente / Proveedor")) LIKE %s')
            params.append(f"%{p_norm}%")
        if prov_clauses:
            prov_where = "AND (" + " OR ".join(prov_clauses) + ")"

    art_where = ""
    if articulos:
        art_clauses = []
        for a in articulos:
            a_norm = a.strip().lower()
            if a_norm:
                art_clauses.append('LOWER(TRIM("Articulo")) ILIKE %s')
                params.append(f"%{a_norm}%")
        if art_clauses:
            art_where = "AND (" + " OR ".join(art_clauses) + ")"

    # ✅ WHERE tiempo
    if usar_meses:
        meses_str = "', '".join(tiempos_sorted)
        tiempo_where = f"TRIM(\"Mes\") IN ('{meses_str}')"
    else:
        anios_str = ", ".join(str(int(a)) for a in tiempos_sorted)
        tiempo_where = f'"Año" IN ({anios_str})'

    # ✅ Determinar si comparar por artículos o proveedores
    modo_articulos = articulos is not None and len(articulos) > 0
    group_by_col = "Articulo" if modo_articulos else "Proveedor"
    select_col = 'TRIM("Articulo")' if modo_articulos else 'TRIM("Cliente / Proveedor")'

    # ✅ Límite
    if modo_articulos:
        limite = 1000
    elif proveedores is None or len(proveedores) == 0:
        limite = 5000
    else:
        limite = 1000

    # ✅ SQL FINAL
    sql = f"""
        SELECT
            {select_col} AS "{group_by_col}",
            TRIM("Moneda") AS Moneda,
            {cols_sql}
            {diff_sql}
        FROM chatbot_raw
        WHERE {tiempo_where}
          {prov_where}
          {art_where}
        GROUP BY {select_col}, TRIM("Moneda")
        ORDER BY "{group_by_col}", Moneda
        LIMIT {limite}
    """

    print(f"🐛 DEBUG comparar_compras: Ejecutando con {len(params)} params")
    print(f"🐛 DEBUG SQL (primeros 500 chars): {sql[:500]}...")

    df = ejecutar_consulta(sql, tuple(params))
    print(f"🐛 Resultado: {len(df) if df is not None and not df.empty else 0} filas")
    return df

# =====================================================================
# COMPARACIONES POR MESES (LEGACY)
# =====================================================================

def get_comparacion_proveedor_meses(*args, **kwargs) -> pd.DataFrame:
    """
    Compatible con múltiples firmas (para no romper nada)
    """
    proveedor = None
    mes1 = None
    mes2 = None
    label1 = None
    label2 = None

    if kwargs:
        proveedor = kwargs.get("proveedor", None) or kwargs.get("proveedores", None)
        mes1 = kwargs.get("mes1", None)
        mes2 = kwargs.get("mes2", None)
        label1 = kwargs.get("label1", None)
        label2 = kwargs.get("label2", None)

    if args and (mes1 is None and mes2 is None):
        if len(args) >= 4 and isinstance(args[0], str) and isinstance(args[1], str) and (
            args[0].startswith("202") and args[1].startswith("202")
        ):
            mes1 = args[0]
            mes2 = args[1]
            label1 = args[2]
            label2 = args[3]
            if len(args) >= 5:
                proveedor = args[4]
        else:
            if len(args) >= 3:
                proveedor = args[0]
                mes1 = args[1]
                mes2 = args[2]
            if len(args) >= 4:
                label1 = args[3]
            if len(args) >= 5:
                label2 = args[4]

    if mes1 is None or mes2 is None:
        return pd.DataFrame()

    if not label1:
        label1 = mes1
    if not label2:
        label2 = mes2

    label1_sql = str(label1).replace('"', "").strip()
    label2_sql = str(label2).replace('"', "").strip()

    total_expr = _sql_total_num_expr_general()

    prov_where = ""
    prov_param = []
    if proveedor:
        if isinstance(proveedor, (list, tuple)):
            if len(proveedor) > 0:
                prov_clauses = ['LOWER(TRIM("Cliente / Proveedor")) LIKE %s' for _ in proveedor]
                prov_where = "AND (" + " OR ".join(prov_clauses) + ")"
                prov_param = [f"%{p.strip().lower()}%" for p in proveedor if p.strip()]
        else:
            prov_norm = str(proveedor).strip().lower()
            if prov_norm:
                prov_where = 'AND LOWER(TRIM("Cliente / Proveedor")) LIKE %s'
                prov_param = [f"%{prov_norm}%"]

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
# COMPARACIONES POR AÑOS (LEGACY)
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
        WHERE "Año"::int IN ({anios_sql})
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

def get_comparacion_proveedor_anios(*args, **kwargs) -> pd.DataFrame:
    """
    Compara proveedores entre años. Compatible con firmas flexibles:
    """
    print(f"🐛 DEBUG SQL_COMPARATIVAS: Llamando get_comparacion_proveedor_anios con args={args}, kwargs={kwargs}")

    proveedores = None
    anios = None

    if len(args) == 2:
        first, second = args
        if isinstance(first, str) and isinstance(second, list):
            proveedores = [first]
            anios = second
        elif isinstance(first, list) and isinstance(second, list):
            proveedores = first
            anios = second
        else:
            return pd.DataFrame()

    elif len(args) == 4:
        prov1, prov2, anio1, anio2 = args
        if isinstance(prov1, str) and isinstance(prov2, str):
            try:
                proveedores = [prov1, prov2]
                anios = [int(anio1), int(anio2)]
            except ValueError:
                return pd.DataFrame()
        else:
            return pd.DataFrame()

    else:
        return pd.DataFrame()

    if not proveedores or not anios:
        return pd.DataFrame()

    if isinstance(proveedores, str):
        proveedores = [proveedores]

    print(f"🐛 DEBUG SQL_COMPARATIVAS: Detectado proveedores={proveedores}, anios={anios}")

    df = get_comparacion_proveedores_anios_multi(proveedores, anios)
    print(f"🐛 DEBUG SQL_COMPARATIVAS: Resultado - filas={len(df) if df is not None else 0}")
    return df

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
        WHERE "Año"::int IN ({anios_sql})
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
        WHERE "Año"::int IN ({anios_sql})
          {fam_where}
        GROUP BY TRIM(COALESCE("Familia", 'SIN FAMILIA'))
        ORDER BY {order_sql}
        LIMIT 300
    """
    return ejecutar_consulta(sql, tuple(fam_params) if fam_params else None)

# =====================================================================
# COMPARACIÓN MULTI PROVEEDORES - MULTI MESES
# =====================================================================

def get_comparacion_proveedores_meses_multi(
    proveedores: List[str],
    meses: List[str],
    articulos: List[str] = None
) -> pd.DataFrame:
    """
    Compara múltiples proveedores en múltiples meses.
    Si proveedores está vacío, incluye TODOS los proveedores.
    """

    if not meses:
        return pd.DataFrame()

    total_expr = _sql_total_num_expr_general()

    cols = []
    params: List = []
    for m in meses:
        cols.append(
            f"""SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) AS "{m}" """
        )
        params.append(m)

    cols_sql = ",\n            ".join(cols)

    prov_where = ""
    if proveedores:
        prov_clauses = []
        for p in proveedores:
            p_norm = p.strip().lower()
            if not p_norm:
                continue
            prov_clauses.append('LOWER(TRIM("Cliente / Proveedor")) LIKE %s')
            params.append(f"%{p_norm}%")
        if prov_clauses:
            prov_where = "AND (" + " OR ".join(prov_clauses) + ")"

    art_where = ""
    art_params = []
    if articulos:
        art_clauses = ['LOWER(TRIM("Articulo")) LIKE %s' for _ in articulos]
        art_where = " AND (" + " OR ".join(art_clauses) + ")"
        art_params = [f"%{a.strip().lower()}%" for a in articulos if a.strip()]

    meses_placeholders = ", ".join(["%s"] * len(meses))
    params.extend(meses)
    params.extend(art_params)

    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Moneda") AS Moneda,
            {cols_sql}
        FROM chatbot_raw
        WHERE TRIM("Mes") IN ({meses_placeholders})
          {prov_where}
          {art_where}
        GROUP BY TRIM("Cliente / Proveedor"), TRIM("Moneda")
        ORDER BY Proveedor, Moneda
        LIMIT 300
    """

    return ejecutar_consulta(sql, tuple(params))

# =====================================================================
# COMPARACIÓN MULTI PROVEEDORES - MULTI AÑOS
# =====================================================================

def get_comparacion_proveedores_anios_multi(
    proveedores: List[str],
    anios: List[int]
) -> pd.DataFrame:
    """
    Compara múltiples proveedores en múltiples años, separado por moneda.
    Si proveedores está vacío, incluye TODOS los proveedores.
    """
    print(f"🐛 DEBUG SQL_COMPARATIVAS: Ejecutando comparación multi-proveedores-años con moneda")
    print(f"🐛 DEBUG SQL_COMPARATIVAS: Proveedores={proveedores}, Años={anios}")

    if not anios:
        return pd.DataFrame()

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

    cols = []
    for y in anios_ok:
        cols.append(
            f"""SUM(CASE WHEN "Año"::int = {y} THEN {total_expr} ELSE 0 END) AS "{y}" """
        )
    cols_sql = ",\n            ".join(cols)

    diff_sql = ""
    if len(anios_ok) == 2:
        y1, y2 = anios_ok[0], anios_ok[1]
        diff_sql = f""",
            (SUM(CASE WHEN "Año"::int = {y2} THEN {total_expr} ELSE 0 END) -
             SUM(CASE WHEN "Año"::int = {y1} THEN {total_expr} ELSE 0 END)) AS Diferencia
        """

    anios_sql = ", ".join(str(y) for y in anios_ok)

    prov_where = ""
    params: List = []
    if proveedores:
        prov_clauses = []
        for p in proveedores:
            p_norm = p.strip().lower()
            if not p_norm:
                continue
            prov_clauses.append('LOWER(TRIM("Cliente / Proveedor")) LIKE %s')
            params.append(f"%{p_norm}%")
        if prov_clauses:
            prov_where = "AND (" + " OR ".join(prov_clauses) + ")"

    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Moneda") AS Moneda,
            {cols_sql}
            {diff_sql}
        FROM chatbot_raw
        WHERE "Año"::int IN ({anios_sql})
          {prov_where}
        GROUP BY TRIM("Cliente / Proveedor"), TRIM("Moneda")
        ORDER BY Proveedor, Moneda
        LIMIT 300
    """

    print(f"🐛 DEBUG SQL_COMPARATIVAS: SQL construido (primeros 200 chars): {sql[:200]}...")
    print(f"🐛 DEBUG SQL_COMPARATIVAS: Params={params}")
    df = ejecutar_consulta(sql, tuple(params))
    print(f"🐛 DEBUG SQL_COMPARATIVAS: SQL ejecutado, resultado filas={len(df) if not df.empty else 0}")
    return df

# =====================================================================
# COMPARACIÓN MULTI (AÑOS O MESES) CON MONEDAS
# =====================================================================

def get_comparacion_multi_proveedores_tiempo_monedas(
    proveedores: List[str], 
    anios: List[int] = None, 
    meses: List[str] = None
) -> pd.DataFrame:
    """
    Compara múltiples proveedores en múltiples años O meses, separado por moneda.
    """
    if not proveedores:
        return pd.DataFrame()

    usar_meses = bool(meses)
    tiempos = meses if usar_meses else anios

    if not tiempos:
        return pd.DataFrame()

    tiempos_ok = sorted(list(set(tiempos)))
    if len(tiempos_ok) < 2:
        return pd.DataFrame()

    total_expr = _sql_total_num_expr_general()

    cols = []
    params: List = []
    for t in tiempos_ok:
        if usar_meses:
            cols.append(
                f"""SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) AS "{t}" """
            )
            params.append(t)
        else:
            cols.append(
                f"""SUM(CASE WHEN "Año"::int = {int(t)} THEN {total_expr} ELSE 0 END) AS "{t}" """
            )
    cols_sql = ",\n            ".join(cols)

    diff_sql = ""
    if len(tiempos_ok) == 2:
        t1, t2 = tiempos_ok[0], tiempos_ok[1]
        if usar_meses:
            diff_sql = f""",
                (SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END) -
                 SUM(CASE WHEN TRIM("Mes") = %s THEN {total_expr} ELSE 0 END)) AS Diferencia
            """
            params.extend([t2, t1])
        else:
            diff_sql = f""",
                (SUM(CASE WHEN "Año"::int = {int(t2)} THEN {total_expr} ELSE 0 END) -
                 SUM(CASE WHEN "Año"::int = {int(t1)} THEN {total_expr} ELSE 0 END)) AS Diferencia
            """

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

    tiempo_col = "Mes" if usar_meses else "Año"
    if usar_meses:
        tiempo_placeholders = ", ".join(["%s"] * len(tiempos_ok))
        params.extend(tiempos_ok)
    else:
        tiempo_placeholders = ", ".join(str(int(y)) for y in tiempos_ok)

    sql = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS Proveedor,
            TRIM("Moneda") AS Moneda,
            {cols_sql}
            {diff_sql}
        FROM chatbot_raw
        WHERE ({prov_where})
          AND {"TRIM(\"" + tiempo_col + "\")" if usar_meses else "\"" + tiempo_col + "\"::int"} IN ({tiempo_placeholders})
        GROUP BY TRIM("Cliente / Proveedor"), TRIM("Moneda")
        ORDER BY Proveedor, Moneda
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

# =====================================================================
# HISTÓRICO DE PRECIOS UNITARIOS POR ARTÍCULO
# =====================================================================

def get_historico_precios_unitarios(articulo_like: str) -> pd.DataFrame:
    """
    Devuelve el histórico con Total (monto_num) en lugar de precio unitario.
    """
    sql = """
        SELECT
            "Fecha",
            "Cliente / Proveedor" AS Proveedor,
            "Nro. Comprobante",
            "Cantidad",
            -- Usa monto_num directamente como Total (sin dividir)
            CASE
                WHEN REPLACE("Monto Neto", ' ', '') LIKE '(%%)' THEN
                    -1 * CAST(REPLACE(REPLACE(REPLACE("Monto Neto", ' ', ''), '.', ''), ',', '.') AS NUMERIC)
                ELSE
                    CAST(REPLACE(REPLACE(REPLACE("Monto Neto", ' ', ''), '.', ''), ',', '.') AS NUMERIC)
            END AS Total,
            "Moneda"
        FROM chatbot_raw
        WHERE
            LOWER(TRIM("Articulo")) = LOWER(TRIM(%s))  -- Cambia LIKE por = para match exacto
            AND "Cantidad" IS NOT NULL
            AND TRIM("Cantidad") <> ''
            AND TRIM("Articulo") IS NOT NULL AND TRIM("Articulo") <> ''
            AND CAST(REPLACE(REPLACE(REPLACE("Monto Neto", ' ', ''), '.', ''), ',', '.') AS NUMERIC) > 0
        ORDER BY "Fecha" ASC;
    """
    return ejecutar_consulta(sql, (articulo_like.strip(),))

# =====================================================================
# ANÁLISIS DE VARIACIÓN POR ARTÍCULO/MONEDA
# =====================================================================

with tabs[4]:
    # ✅ MODIFICACIÓN AQUÍ: LOGIC FOR HISTORICAL PRICES IF ONE ARTICLE SELECTED
    articulos_sel = st.session_state.get("art_multi", [])
    
    if articulos_sel and len(articulos_sel) == 1:
        articulo = articulos_sel[0]
        
        try:
            df_hist = sqlq_comparativas.get_historico_precios_unitarios(articulo)
            
            if df_hist is not None and not df_hist.empty:
                st.subheader(f"Histórico de precios – {articulo}")
                
                st.dataframe(
                    df_hist,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning(f"⚠️ No hay datos históricos para '{articulo}'")
                
                # Debug rápido: contar registros
                debug_sql = '''
                    SELECT COUNT(*) as total
                    FROM chatbot_raw 
                    WHERE LOWER(TRIM("Articulo")) LIKE LOWER(%s)
                      AND "Cantidad" IS NOT NULL AND TRIM("Cantidad") <> ''
                      AND TRIM("Articulo") IS NOT NULL AND TRIM("Articulo") <> ''
                '''
                debug_df = ejecutar_consulta(debug_sql, (f"%{articulo.strip().lower()}%",))
                if debug_df is not None and not debug_df.empty:
                    total = int(debug_df.iloc[0]['total'])
                    st.info(f"Registros encontrados para '{articulo}': {total}")
                    if total == 0:
                        st.info("El artículo no existe o no tiene datos válidos.")
                    else:
                        st.info("Datos existen, pero no se pudieron parsear (revisa Monto Neto).")
        except Exception as e:
            st.error(f"Error: {e}")
    else:
        # ✅ NUEVA LÓGICA: Si 1 proveedor y 2 períodos → Mostrar análisis de variación
        proveedores_sel = st.session_state.get("comparativas_proveedores_multi", [])
        if proveedores_sel and len(proveedores_sel) == 1 and len(periodos_validos) == 2:
            proveedor_sel = proveedores_sel[0]
            
            df_variacion = sqlq_comparativas.get_analisis_variacion_articulos(proveedor_sel, periodos_validos)
            
            if df_variacion is not None and not df_variacion.empty:
                st.markdown("#### 📊 ¿Por qué bajó/subió el gasto?")
                st.dataframe(
                    df_variacion[['Articulo', 'Moneda', f'Total {periodos_validos[0]}', f'Total {periodos_validos[1]}', 'Variación', 'Tipo de Variación', 'Impacto']],
                    use_container_width=True,
                    hide_index=True,
                    height=600
                )
            else:
                st.info("No hay datos de variación para este proveedor")
        else:
            # ⬇️ TABLA COMPARATIVA ORIGINAL (NO TOCAR)
            st.dataframe(df, use_container_width=True, height=600)
