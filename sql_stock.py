import os
import pandas as pd
import streamlit as st
from sql_core import ejecutar_consulta, _safe_ident


# =====================================================================
# CONSTANTES DE STOCK
# =====================================================================

_STOCK_TABLE_CANDIDATES = [
    "stock_rows",  # ✅ PRIORIDAD 1: según tu CSV importado
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
    """Hardcoded para usar public.stock"""
    return "public", "stock"


def _get_stock_columns(schema: str, table: str) -> list:
    """Obtiene columnas de la tabla con manejo de errores."""
    try:
        sql = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
        """
        df = ejecutar_consulta(sql, (schema, table))
        if df is None or df.empty or "column_name" not in df.columns:
            print(f"⚠️ DEBUG: No se encontraron columnas para {schema}.{table}")
            return []
        
        cols = [str(x) for x in df["column_name"].tolist()]
        print(f"🔍 DEBUG: Columnas encontradas en {schema}.{table}: {cols}")
        return cols
    except Exception as e:
        print(f"❌ DEBUG: Error obteniendo columnas: {e}")
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
            return f'"{real}"'
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
        WHEN TRIM({col_expr}::text) ~ '^\\d{{1,2}}/\\d{{1,2}}/\\d{{4}}$' THEN to_date(TRIM({col_expr}::text), 'DD/MM/YYYY')
        WHEN TRIM({col_expr}::text) ~ '^\\d{{1,2}}-\\d{{1,2}}-\\d{{4}}$' THEN to_date(TRIM({col_expr}::text), 'DD-MM-YYYY')
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
          replace(TRIM({col_expr}::text), ' ', ''),
          ',', '.'
        ),
        '[^0-9\\.]',
        '',
        'g'
      ),
      ''
    )::numeric
    """
def _stock_base_subquery() -> tuple:
    """Subquery hardcoded para evitar problemas de detección de columnas."""
    
    sub = """
        SELECT
            TRIM(COALESCE("CODIGO"::text,'')) AS "CODIGO",
            TRIM(COALESCE("ARTICULO"::text,'')) AS "ARTICULO",
            TRIM(COALESCE("FAMILIA"::text,'')) AS "FAMILIA",
            TRIM(COALESCE("DEPOSITO"::text,'')) AS "DEPOSITO",
            TRIM(COALESCE("LOTE"::text,'')) AS "LOTE",
            (
              CASE
                WHEN NULLIF(TRIM("VENCIMIENTO"::text), '') IS NULL THEN NULL::date
                WHEN TRIM("VENCIMIENTO"::text) ~ '^\\d{4}-\\d{2}-\\d{2}' THEN (TRIM("VENCIMIENTO"::text))::date
                WHEN TRIM("VENCIMIENTO"::text) ~ '^\\d{1,2}/\\d{1,2}/\\d{4}$' THEN to_date(TRIM("VENCIMIENTO"::text), 'DD/MM/YYYY')
                WHEN TRIM("VENCIMIENTO"::text) ~ '^\\d{1,2}-\\d{1,2}-\\d{4}$' THEN to_date(TRIM("VENCIMIENTO"::text), 'DD-MM-YYYY')
                ELSE NULL::date
              END
            ) AS "VENCIMIENTO",
            NULLIF(
              regexp_replace(
                replace(
                  replace(TRIM("STOCK"::text), ' ', ''),
                  ',', '.'
                ),
                '[^0-9\\.]',
                '',
                'g'
              ),
              ''
            )::numeric AS "STOCK",
            CASE
              WHEN (
                CASE
                  WHEN NULLIF(TRIM("VENCIMIENTO"::text), '') IS NULL THEN NULL::date
                  WHEN TRIM("VENCIMIENTO"::text) ~ '^\\d{4}-\\d{2}-\\d{2}' THEN (TRIM("VENCIMIENTO"::text))::date
                  WHEN TRIM("VENCIMIENTO"::text) ~ '^\\d{1,2}/\\d{1,2}/\\d{4}$' THEN to_date(TRIM("VENCIMIENTO"::text), 'DD/MM/YYYY')
                  WHEN TRIM("VENCIMIENTO"::text) ~ '^\\d{1,2}-\\d{1,2}-\\d{4}$' THEN to_date(TRIM("VENCIMIENTO"::text), 'DD-MM-YYYY')
                  ELSE NULL::date
                END
              ) IS NULL THEN NULL
              ELSE (
                (
                  CASE
                    WHEN NULLIF(TRIM("VENCIMIENTO"::text), '') IS NULL THEN NULL::date
                    WHEN TRIM("VENCIMIENTO"::text) ~ '^\\d{4}-\\d{2}-\\d{2}' THEN (TRIM("VENCIMIENTO"::text))::date
                    WHEN TRIM("VENCIMIENTO"::text) ~ '^\\d{1,2}/\\d{1,2}/\\d{4}$' THEN to_date(TRIM("VENCIMIENTO"::text), 'DD/MM/YYYY')
                    WHEN TRIM("VENCIMIENTO"::text) ~ '^\\d{1,2}-\\d{1,2}-\\d{4}$' THEN to_date(TRIM("VENCIMIENTO"::text), 'DD-MM-YYYY')
                    ELSE NULL::date
                  END
                ) - CURRENT_DATE
              )
            END AS "Dias_Para_Vencer"
        FROM "public"."stock" s
        WHERE UPPER(TRIM(COALESCE(s."ARTICULO", ''))) <> 'SIN ARTICULO'
    """
    
    return sub, "public", "stock"
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
              AND TRIM("ARTICULO") <> 'SIN ARTICULO'
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
              AND TRIM("FAMILIA") <> 'SIN FAMILIA'
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
              AND TRIM("DEPOSITO") <> 'SIN DEPOSITO'
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
        df = ejecutar_consulta(sql, tuple(params))
        return df if df is not None else pd.DataFrame()
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
        
        # 1. Obtener todos los datos
        sql = f"""
            SELECT
                "CODIGO","ARTICULO","FAMILIA","DEPOSITO","LOTE","VENCIMIENTO","Dias_Para_Vencer","STOCK"
            FROM ({base}) s
            WHERE UPPER(TRIM(COALESCE("FAMILIA", ''))) = %s
            ORDER BY 
                "ARTICULO" ASC,  -- ✅ ORDEN ALFABÉTICO
                CASE WHEN "VENCIMIENTO" IS NULL THEN 1 ELSE 0 END,
                "VENCIMIENTO" ASC NULLS LAST
        """
        df = ejecutar_consulta(sql, (familia.upper().strip(),))
        
        if df is None or df.empty:
            return pd.DataFrame()
        
        # ✅ FILTRAR INACTIVOS EN PYTHON (DESPUÉS DE LA QUERY)
        df = df[~df['ARTICULO'].str.contains('(INACTIVO)', case=False, na=False)]
        df = df[~df['ARTICULO'].str.contains('INACTIVO', case=False, na=False)]
        
        if df.empty:
            return pd.DataFrame()
        
        # 2. LÓGICA DE LIMPIEZA
        df['STOCK'] = df['STOCK'].fillna(0).astype(float)
        
        # Agrupar por artículo
        grouped = df.groupby('ARTICULO')
        cleaned_rows = []
        
        for articulo, group in grouped:
            stock_positive = group[group['STOCK'] > 0]
            if not stock_positive.empty:
                # ✅ Si hay lotes con stock >0, mostrar SOLO esos
                cleaned_rows.extend(stock_positive.to_dict('records'))
            else:
                # ✅ Si todos =0, mostrar 1 fila genérica para pedir
                row_dict = group.iloc[0].to_dict()
                row_dict['LOTE'] = None
                row_dict['VENCIMIENTO'] = None
                row_dict['Dias_Para_Vencer'] = None
                row_dict['STOCK'] = 0
                cleaned_rows.append(row_dict)
        
        df_cleaned = pd.DataFrame(cleaned_rows)
        
        # 3. ORDENAR ALFABÉTICAMENTE
        if not df_cleaned.empty:
            df_cleaned = df_cleaned.sort_values('ARTICULO', ascending=True)
        
        return df_cleaned
        
    except Exception as e:
        print(f"Error en get_stock_familia: {e}")
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
        df = ejecutar_consulta(sql, ())
        return df if df is not None else pd.DataFrame()
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
# ALERTAS Y VENCIMIENTOS - CORREGIDO PARA CAST DE TEXT A DATE/NUMERIC
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
        df = ejecutar_consulta(sql, (int(dias),))
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        print(f"Error en get_lotes_por_vencer: {e}")
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
        df = ejecutar_consulta(sql, ())
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        print(f"Error en get_lotes_vencidos: {e}")
        return pd.DataFrame()


def get_stock_bajo(minimo: int = 10) -> pd.DataFrame:
    """Devuelve registros con stock <= minimo (incluyendo 0)."""
    try:
        base, _, _ = _stock_base_subquery()
        sql = f"""
            SELECT
                "CODIGO","ARTICULO","FAMILIA","DEPOSITO","LOTE","VENCIMIENTO","Dias_Para_Vencer","STOCK"
            FROM ({base}) s
            WHERE "STOCK" IS NOT NULL
              AND "STOCK" <= %s  -- ✅ INCLUYE STOCK = 0
            ORDER BY "STOCK" ASC NULLS LAST, "ARTICULO" ASC
        """
        df = ejecutar_consulta(sql, (int(minimo),))
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        print(f"Error en get_stock_bajo: {e}")
        return pd.DataFrame()


def get_alertas_vencimiento_multiple(limite: int = 10, dias_filtro: int = 90) -> list:  # ✅ CAMBIADO A 90
    """Alertas rotativas de vencimiento para el módulo Stock IA."""
    try:
        df = get_lotes_por_vencer(dias=dias_filtro)
        
        if df is None or df.empty:
            return []

        df = df.head(int(limite))

        alertas = []
        for _, r in df.iterrows():
            alerta = {
                "articulo": str(r.get("ARTICULO", "") or ""),
                "lote": str(r.get("LOTE", "") or ""),
                "deposito": str(r.get("DEPOSITO", "") or ""),
                "vencimiento": str(r.get("VENCIMIENTO", "") or ""),
                "dias_restantes": int(r.get("Dias_Para_Vencer", 0) or 0),
                "stock": str(r.get("STOCK", "") or "")
            }
            alertas.append(alerta)
        return alertas
    except Exception as e:
        print(f"Error en get_alertas_vencimiento_multiple: {e}")
        return []


def get_alertas_stock_1(limite: int = 5) -> list:
    """Obtiene específicamente artículos con stock = 1."""
    try:
        base, _, _ = _stock_base_subquery()
        sql = f"""
            SELECT * FROM ({base}) s
            WHERE "STOCK" = 1
            ORDER BY "ARTICULO" ASC
            LIMIT {int(limite)}
        """
        df = ejecutar_consulta(sql, ())
        if df is None or df.empty: return []
        return df.to_dict('records')
    except Exception as e:
        print(f"Error en get_alertas_stock_1: {e}")
        return []


def get_alertas_combinadas(limite: int = 10, dias_filtro: int = 30) -> list:
    """✅ NUEVA FUNCIÓN: Combina alertas de stock = 1 y vencimientos en <30 días con stock > 0."""
    try:
        # Obtener alertas de stock = 1
        df_stock_1 = pd.DataFrame(get_alertas_stock_1(limite=limite))
        
        # Obtener alertas de vencimiento
        alertas_vto = get_alertas_vencimiento_multiple(limite=limite, dias_filtro=dias_filtro)
        df_vto = pd.DataFrame(alertas_vto)
        
        # Combinar sin duplicados (basado en ARTICULO + LOTE)
        df_combinado = pd.concat([df_stock_1, df_vto], ignore_index=True).drop_duplicates(subset=['ARTICULO', 'LOTE'])
        
        # Limitar y convertir a lista
        df_combinado = df_combinado.head(limite)
        return df_combinado.to_dict('records')
    except Exception as e:
        print(f"Error en get_alertas_combinadas: {e}")
        return []
