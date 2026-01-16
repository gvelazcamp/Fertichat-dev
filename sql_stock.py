import pandas as pd
from typing import Tuple, Optional
from sql_core import ejecutar_consulta

def _stock_base_subquery() -> Tuple[str, str, str]:
    """
    Subconsulta base para stock con filtros comunes
    """
    base = """
        SELECT
            s."CODIGO",
            s."ARTICULO",
            s."FAMILIA",
            s."DEPOSITO",
            s."LOTE",
            s."VENCIMIENTO",
            s."STOCK",
            CASE
                WHEN s."VENCIMIENTO" IS NOT NULL THEN
                    EXTRACT(DAY FROM (s."VENCIMIENTO" - CURRENT_DATE))
                ELSE NULL
            END as "Dias_Para_Vencer"
        FROM public.stock s
        WHERE s."ARTICULO" NOT LIKE '%(INACTIVO)%'
          AND s."ARTICULO" NOT LIKE '%INACTIVO%'
          AND UPPER(TRIM(COALESCE(s."ARTICULO", ''))) <> 'SIN ARTICULO'
    """
    
    filtros_stock_positivo = 'AND s."STOCK" > 0'
    filtros_todos = ''
    
    return base, filtros_stock_positivo, filtros_todos

# =========================
# FUNCIONES DE STOCK
# =========================

def get_stock_total() -> pd.DataFrame:
    """Obtiene resumen total de stock"""
    try:
        base, _, _ = _stock_base_subquery()
        
        sql = f"""
            SELECT
                COUNT(*) as registros,
                COUNT(DISTINCT "ARTICULO") as articulos,
                COUNT(DISTINCT "LOTE") as lotes,
                SUM("STOCK") as stock_total
            FROM ({base}) s
        """
        
        df = ejecutar_consulta(sql, ())
        return df if df is not None else pd.DataFrame()
        
    except Exception as e:
        print(f"Error en get_stock_total: {e}")
        return pd.DataFrame()

def get_stock_por_familia() -> pd.DataFrame:
    """Obtiene stock agrupado por familia"""
    try:
        base, filtros_stock_positivo, _ = _stock_base_subquery()
        
        sql = f"""
            SELECT
                "FAMILIA",
                COUNT(*) as registros,
                COUNT(DISTINCT "ARTICULO") as articulos,
                SUM("STOCK") as stock_total
            FROM ({base}) s
            WHERE "FAMILIA" IS NOT NULL
              AND TRIM("FAMILIA") <> ''
              AND UPPER(TRIM("FAMILIA")) <> 'SIN FAMILIA'
            GROUP BY "FAMILIA"
            ORDER BY stock_total DESC
        """
        
        df = ejecutar_consulta(sql, ())
        return df if df is not None else pd.DataFrame()
        
    except Exception as e:
        print(f"Error en get_stock_por_familia: {e}")
        return pd.DataFrame()

def get_stock_por_deposito() -> pd.DataFrame:
    """Obtiene stock agrupado por depósito"""
    try:
        base, filtros_stock_positivo, _ = _stock_base_subquery()
        
        sql = f"""
            SELECT
                "DEPOSITO",
                COUNT(*) as registros,
                COUNT(DISTINCT "ARTICULO") as articulos,
                SUM("STOCK") as stock_total
            FROM ({base}) s
            GROUP BY "DEPOSITO"
            ORDER BY stock_total DESC
        """
        
        df = ejecutar_consulta(sql, ())
        return df if df is not None else pd.DataFrame()
        
    except Exception as e:
        print(f"Error en get_stock_por_deposito: {e}")
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
              AND UPPER(TRIM(COALESCE("DEPOSITO", ''))) = 'CASA CENTRAL'
            ORDER BY 
                "ARTICULO" ASC,  -- ✅ ORDEN ALFABÉTICO
                CASE WHEN "VENCIMIENTO" IS NULL THEN 1 ELSE 0 END,
                "VENCIMIENTO" ASC NULLS LAST
        """
        df = ejecutar_consulta(sql, (familia.upper().strip(),))
        
        if df is None or df.empty:
            return pd.DataFrame()
        
        # 2. LÓGICA DE LIMPIEZA
        df['STOCK'] = df['STOCK'].fillna(0).astype(float)
        
        # Agrupar por artículo
        grouped = df.groupby('ARTICULO')
        cleaned_rows = []
        
        for articulo, group in grouped:
            # Ver si hay stock > 0
            stock_positive = group[group['STOCK'] > 0]
            
            if not stock_positive.empty:
                # ✅ CASO 1: Hay lotes con stock > 0 → Mostrar SOLO esos
                cleaned_rows.extend(stock_positive.to_dict('records'))
            else:
                # ✅ CASO 2: TODO en 0 → Mostrar 1 fila genérica SIN lote/vencimiento
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

def get_stock_articulo(articulo: str) -> pd.DataFrame:
    """Obtiene stock de un artículo específico"""
    try:
        base, filtros_stock_positivo, _ = _stock_base_subquery()
        
        # Buscar por nombre aproximado
        sql = f"""
            SELECT
                "CODIGO","ARTICULO","FAMILIA","DEPOSITO","LOTE","VENCIMIENTO","Dias_Para_Vencer","STOCK"
            FROM ({base}) s
            WHERE UPPER("ARTICULO") LIKE UPPER(%s)
            ORDER BY "STOCK" DESC, "VENCIMIENTO" ASC
        """
        
        df = ejecutar_consulta(sql, (f'%{articulo.upper()}%',))
        return df if df is not None else pd.DataFrame()
        
    except Exception as e:
        print(f"Error en get_stock_articulo: {e}")
        return pd.DataFrame()

def get_stock_lote_especifico(lote: str) -> pd.DataFrame:
    """Obtiene información de un lote específico"""
    try:
        base, _, _ = _stock_base_subquery()
        
        sql = f"""
            SELECT
                "CODIGO","ARTICULO","FAMILIA","DEPOSITO","LOTE","VENCIMIENTO","Dias_Para_Vencer","STOCK"
            FROM ({base}) s
            WHERE UPPER("LOTE") = UPPER(%s)
        """
        
        df = ejecutar_consulta(sql, (lote.strip(),))
        return df if df is not None else pd.DataFrame()
        
    except Exception as e:
        print(f"Error en get_stock_lote_especifico: {e}")
        return pd.DataFrame()

def get_lotes_por_vencer(dias: int = 90) -> pd.DataFrame:
    """Obtiene lotes que vencen en los próximos N días"""
    try:
        base, filtros_stock_positivo, _ = _stock_base_subquery()
        
        sql = f"""
            SELECT
                "CODIGO","ARTICULO","FAMILIA","DEPOSITO","LOTE","VENCIMIENTO","Dias_Para_Vencer","STOCK"
            FROM ({base}) s
            WHERE "Dias_Para_Vencer" >= 0
              AND "Dias_Para_Vencer" <= %s
              {filtros_stock_positivo}
            ORDER BY "Dias_Para_Vencer" ASC, "ARTICULO" ASC
        """
        
        df = ejecutar_consulta(sql, (dias,))
        return df if df is not None else pd.DataFrame()
        
    except Exception as e:
        print(f"Error en get_lotes_por_vencer: {e}")
        return pd.DataFrame()

def get_lotes_vencidos() -> pd.DataFrame:
    """Obtiene lotes ya vencidos con stock"""
    try:
        base, filtros_stock_positivo, _ = _stock_base_subquery()
        
        sql = f"""
            SELECT
                "CODIGO","ARTICULO","FAMILIA","DEPOSITO","LOTE","VENCIMIENTO","Dias_Para_Vencer","STOCK"
            FROM ({base}) s
            WHERE "Dias_Para_Vencer" < 0
              {filtros_stock_positivo}
            ORDER BY "Dias_Para_Vencer" ASC, "ARTICULO" ASC
        """
        
        df = ejecutar_consulta(sql, ())
        return df if df is not None else pd.DataFrame()
        
    except Exception as e:
        print(f"Error en get_lotes_vencidos: {e}")
        return pd.DataFrame()

def get_stock_bajo(minimo: int = 10) -> pd.DataFrame:
    """Obtiene artículos con stock bajo o igual a mínimo"""
    try:
        base, _, _ = _stock_base_subquery()
        
        # Agrupar por artículo y sumar stock
        sql = f"""
            SELECT
                "CODIGO","ARTICULO","FAMILIA","DEPOSITO","LOTE","VENCIMIENTO","Dias_Para_Vencer","STOCK"
            FROM ({base}) s
            WHERE "ARTICULO" IN (
                SELECT sub."ARTICULO"
                FROM ({base}) sub
                GROUP BY sub."ARTICULO"
                HAVING SUM(sub."STOCK") <= %s
            )
            ORDER BY "ARTICULO" ASC, "STOCK" DESC
        """
        
        df = ejecutar_consulta(sql, (minimo,))
        return df if df is not None else pd.DataFrame()
        
    except Exception as e:
        print(f"Error en get_stock_bajo: {e}")
        return pd.DataFrame()

def get_alertas_vencimiento_multiple(dias_urgente: int = 30) -> list:
    """Obtiene alertas de vencimiento múltiple para UI"""
    try:
        df = get_lotes_por_vencer(dias_urgente)
        
        if df is None or df.empty:
            return []
        
        alertas = []
        for _, row in df.iterrows():
            alertas.append({
                'articulo': str(row.get('ARTICULO', '-')),
                'lote': str(row.get('LOTE', '-')),
                'vencimiento': str(row.get('VENCIMIENTO', '-')),
                'dias_restantes': int(row.get('Dias_Para_Vencer', 0)),
                'stock': int(row.get('STOCK', 0))
            })
        
        return alertas
        
    except Exception as e:
        print(f"Error en get_alertas_vencimiento_multiple: {e}")
        return []

def get_alertas_stock_1(maximo: int = 20) -> list:
    """Obtiene artículos con stock = 1"""
    try:
        df = get_stock_bajo(1)
        
        if df is None or df.empty:
            return []
        
        # Filtrar solo stock = 1
        df_uno = df[df['STOCK'] == 1]
        
        alertas = []
        for _, row in df_uno.iterrows():
            alertas.append({
                'ARTICULO': str(row.get('ARTICULO', '-')),
                'LOTE': str(row.get('LOTE', '-')),
                'DEPOSITO': str(row.get('DEPOSITO', '-')),
                'STOCK': int(row.get('STOCK', 0))
            })
        
        return alertas
        
    except Exception as e:
        print(f"Error en get_alertas_stock_1: {e}")
        return []

def get_lista_articulos_stock() -> list:
    """Obtiene lista de artículos disponibles"""
    try:
        sql = """
            SELECT DISTINCT "ARTICULO"
            FROM public.stock
            WHERE "ARTICULO" NOT LIKE '%(INACTIVO)%'
              AND "ARTICULO" NOT LIKE '%INACTIVO%'
              AND UPPER(TRIM(COALESCE("ARTICULO", ''))) <> 'SIN ARTICULO'
              AND "ARTICULO" IS NOT NULL
            ORDER BY "ARTICULO" ASC
        """
        
        df = ejecutar_consulta(sql, ())
        
        if df is not None and not df.empty:
            articulos = df['ARTICULO'].tolist()
            return ["Todos"] + articulos
        
        return ["Todos"]
        
    except Exception as e:
        print(f"Error en get_lista_articulos_stock: {e}")
        return ["Todos"]

def get_lista_familias_stock() -> list:
    """Obtiene lista de familias disponibles"""
    try:
        sql = """
            SELECT DISTINCT "FAMILIA"
            FROM public.stock
            WHERE "FAMILIA" IS NOT NULL
              AND TRIM("FAMILIA") <> ''
              AND UPPER(TRIM("FAMILIA")) <> 'SIN FAMILIA'
            ORDER BY "FAMILIA" ASC
        """
        
        df = ejecutar_consulta(sql, ())
        
        if df is not None and not df.empty:
            familias = df['FAMILIA'].tolist()
            return ["Todas"] + familias
        
        return ["Todas"]
        
    except Exception as e:
        print(f"Error en get_lista_familias_stock: {e}")
        return ["Todas"]

def get_lista_depositos_stock() -> list:
    """Obtiene lista de depósitos disponibles"""
    try:
        sql = """
            SELECT DISTINCT "DEPOSITO"
            FROM public.stock
            WHERE "DEPOSITO" IS NOT NULL
              AND TRIM("DEPOSITO") <> ''
            ORDER BY "DEPOSITO" ASC
        """
        
        df = ejecutar_consulta(sql, ())
        
        if df is not None and not df.empty:
            depositos = df['DEPOSITO'].tolist()
            return ["Todos"] + depositos
        
        return ["Todos"]
        
    except Exception as e:
        print(f"Error en get_lista_depositos_stock: {e}")
        return ["Todos"]

def buscar_stock_por_lote(texto_busqueda: str = None, deposito: str = None, articulo: str = None) -> pd.DataFrame:
    """Búsqueda avanzada de stock"""
    try:
        base, filtros_stock_positivo, _ = _stock_base_subquery()
        
        condiciones = []
        params = []
        
        if texto_busqueda:
            condiciones.append("""
                (UPPER("ARTICULO") LIKE UPPER(%s) 
                 OR UPPER("LOTE") LIKE UPPER(%s)
                 OR UPPER("CODIGO") LIKE UPPER(%s))
            """)
            params.extend([f'%{texto_busqueda}%'] * 3)
        
        if deposito and deposito != "Todos":
            condiciones.append('UPPER("DEPOSITO") = UPPER(%s)')
            params.append(deposito.upper())
        
        if articulo and articulo != "Todos":
            condiciones.append('UPPER("ARTICULO") LIKE UPPER(%s)')
            params.append(f'%{articulo.upper()}%')
        
        where_clause = " AND ".join(condiciones) if condiciones else "1=1"
        
        sql = f"""
            SELECT
                "CODIGO","ARTICULO","FAMILIA","DEPOSITO","LOTE","VENCIMIENTO","Dias_Para_Vencer","STOCK"
            FROM ({base}) s
            WHERE {where_clause}
            ORDER BY "ARTICULO" ASC, "STOCK" DESC
        """
        
        df = ejecutar_consulta(sql, tuple(params))
        return df if df is not None else pd.DataFrame()
        
    except Exception as e:
        print(f"Error en buscar_stock_por_lote: {e}")
        return pd.DataFrame()
        
# Agregar al final de sql_stock.py, antes del último return o después de get_alertas_stock_1

def get_alertas_combinadas(dias_urgente: int = 30) -> list:
    """Alias para get_alertas_vencimiento_multiple"""
    return get_alertas_vencimiento_multiple(dias_urgente)
