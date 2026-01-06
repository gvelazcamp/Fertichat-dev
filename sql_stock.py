# =========================
# SQL STOCK - INVENTARIO Y LOTES
# =========================

import os
import pandas as pd
import streamlit as st
from sql_core import ejecutar_consulta, _safe_ident


# =====================================================================
# CONSTANTES DE STOCK
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


# =====================================================================
# HELPERS INTERNOS DE STOCK
# =====================================================================

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


# =====================================================================
# LISTADOS DE STOCK
# =====================================================================

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


# =====================================================================
# BÚSQUEDAS DE STOCK
# =====================================================================

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


# =====================================================================
# RESÚMENES Y AGREGACIONES
# =====================================================================

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


# =====================================================================
# ALERTAS Y VENCIMIENTOS
# =====================================================================

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
