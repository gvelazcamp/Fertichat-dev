import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional

from ia_interpretador import interpretar_pregunta, obtener_info_tipo
from utils_openai import responder_con_openai
import sql_compras as sqlq_compras
import sql_comparativas as sqlq_comparativas
import sql_facturas as sqlq_facturas
from sql_core import get_unique_proveedores, get_unique_articulos, ejecutar_consulta  # Agregado ejecutar_consulta

# Temporary fix for get_unique functions
def get_unique_proveedores():
    try:
        from sql_core import ejecutar_consulta
        sql = '''
            SELECT DISTINCT TRIM("Cliente / Proveedor") AS prov 
            FROM chatbot_raw 
            WHERE TRIM("Cliente / Proveedor") != '' 
            ORDER BY prov
        '''
        # ⚠️ SIN LIMIT - trae TODOS
        df = ejecutar_consulta(sql, ())
        if df is None or df.empty:
            return []
        provs = df['prov'].tolist()
        print(f"🐛 DEBUG: Cargados {len(provs)} proveedores únicos")  # Debug
        return provs
    except Exception as e:
        print(f"❌ Error cargando proveedores: {e}")
        return []

def get_unique_articulos():
    try:
        from sql_core import ejecutar_consulta
        sql = 'SELECT DISTINCT TRIM("Articulo") AS art FROM chatbot_raw WHERE TRIM("Articulo") != \'\' ORDER BY art'
        df = ejecutar_consulta(sql)
        return df['art'].tolist() if not df.empty else []
    except:
        return []

# =========================
# NUEVA FUNCIÓN PARA TOP 5 ARTÍCULOS EXCLUSIVA
# =========================
def get_top_5_articulos(anios, meses=None, proveedores=None):
    """
    ✅ MODIFICADO: Ahora acepta filtro por proveedores
    Devuelve Top 5 artículos por monto total para el período seleccionado.
    - anios: lista de int (ej: [2025] o [2024,2025])
    - meses: lista de str opcional (ej: ["2024-11", "2025-11"] o None)
    - proveedores: lista de str opcional (ej: ["PROVEEDOR A"] o None)
    """

    if not anios:
        return None

    # -------------------------
    # WHERE por período
    # -------------------------
    where_clauses = []
    params = []

    # ✅ FIX: Usar IN en lugar de ANY para compatibilidad, con casting a INT
    anios_str = ', '.join(str(int(a)) for a in anios)
    where_clauses.append(f'"Año"::int IN ({anios_str})')

    # ✅ FIX: Filtrar por meses usando las cadenas completas (ej. '2024-11')
    if meses and len(meses) > 0:
        meses_str = ', '.join(f"'{m}'" for m in meses)  # Cadenas con comillas simples
        where_clauses.append(f'"Mes" IN ({meses_str})')

    # ✅ Filtro de proveedores
    if proveedores and len(proveedores) > 0:
        prov_clauses = []
        for p in proveedores:
            p_norm = p.strip().lower()
            if not p_norm:
                continue
            prov_clauses.append('LOWER(TRIM("Cliente / Proveedor")) LIKE %s')
            params.append(f"%{p_norm}%")
        if prov_clauses:
            where_clauses.append("(" + " OR ".join(prov_clauses) + ")")

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # -------------------------
    # SQL TOP 5
    # -------------------------
    sql = f"""
        WITH montos AS (
            SELECT
                "Articulo",
                "Moneda",
                CASE
                    WHEN REPLACE("Monto Neto",' ','') LIKE '(%%)' THEN
                        -1 * CAST(
                            REPLACE(
                                REPLACE(
                                    SUBSTRING(
                                        REPLACE("Monto Neto",' ',''), 2,
                                        LENGTH(REPLACE("Monto Neto",' ','')) - 2
                                    ),
                                    '.',''
                                ),
                                ',','.'
                            ) AS NUMERIC
                        )
                    ELSE
                        CAST(
                            REPLACE(
                                REPLACE(
                                    REPLACE("Monto Neto",' ',''),'.',''
                                ),
                                ',','.'
                            ) AS NUMERIC
                        )
                END AS monto_num
            FROM chatbot_raw
            WHERE {where_sql}
                AND TRIM("Articulo") IS NOT NULL AND TRIM("Articulo") <> ''  -- Filtrar artículos vacíos
        )
        SELECT
            "Articulo",
            "Moneda",
            SUM(monto_num) AS total
        FROM montos
        WHERE monto_num IS NOT NULL AND monto_num > 0  -- Filtrar montos inválidos
        GROUP BY "Articulo", "Moneda"
        HAVING SUM(monto_num) > 0  -- Solo grupos con total > 0
        ORDER BY total DESC
        LIMIT 5
    """

    try:
        df = ejecutar_consulta(sql, tuple(params))
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        print("❌ Error Top 5 Artículos:", e)
        import traceback
        traceback.print_exc()
        return None

# =========================
# NUEVA FUNCIÓN PARA TOP 5 PERÍODOS POR ARTÍCULO
# =========================
def get_top_5_periodos_por_articulo(articulo, anios, meses=None, proveedores=None):
    """
    Devuelve top 5 períodos (meses) con más compras de un artículo específico.
    Siempre agrupa por mes cuando hay artículos seleccionados.
    """
    if not articulo or not anios:
        return pd.DataFrame()

    # Determinar si agrupar por mes o año - MODIFICADO: Siempre por mes
    group_by = "Mes"  # Siempre agrupar por mes cuando hay artículos seleccionados

    where_clauses = [f'"Año"::int IN ({", ".join(str(int(a)) for a in anios)})']
    params = []

    # Filtro por artículo específico
    where_clauses.append('LOWER(TRIM("Articulo")) LIKE %s')
    params.append(f"%{articulo.strip().lower()}%")

    # Filtro opcional de meses
    if meses and len(meses) > 0:
        meses_str = ', '.join(f"'{m}'" for m in meses)
        where_clauses.append(f'"Mes" IN ({meses_str})')

    # Filtro opcional de proveedores
    if proveedores and len(proveedores) > 0:
        prov_clauses = []
        for p in proveedores:
            prov_clauses.append('LOWER(TRIM("Cliente / Proveedor")) LIKE %s')
            params.append(f"%{p.strip().lower()}%")
        where_clauses.append("(" + " OR ".join(prov_clauses) + ")")

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    sql = f"""
        WITH montos AS (
            SELECT
                "{group_by}",
                SUM(
                    CASE
                        WHEN REPLACE("Monto Neto",' ','') LIKE '(%%)' THEN
                            -1 * CAST(REPLACE(REPLACE(SUBSTRING(REPLACE("Monto Neto",' ',''), 2, LENGTH(REPLACE("Monto Neto",' ','')) - 2), '.', ''), ',', '.') AS NUMERIC)
                        ELSE
                            CAST(REPLACE(REPLACE(REPLACE("Monto Neto",' ',''), '.', ''), ',', '.') AS NUMERIC)
                    END
                ) AS total
            FROM chatbot_raw
            WHERE {where_sql}
                AND TRIM("Articulo") IS NOT NULL AND TRIM("Articulo") <> ''
            GROUP BY "{group_by}"
        )
        SELECT "{group_by}" AS Periodo, total
        FROM montos
        WHERE total IS NOT NULL AND total > 0
        ORDER BY total DESC
        LIMIT 5
    """

    try:
        df = ejecutar_consulta(sql, tuple(params))
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        print(f"❌ Error Top 5 períodos por artículo: {e}")
        return pd.DataFrame()

# =========================
# CONVERSIÓN DE MESES A NOMBRES
# =========================
def convertir_mes_a_nombre(mes_str):
    if not mes_str or '-' not in mes_str:
        return mes_str
    try:
        year, month = mes_str.split('-')
        month_num = int(month)
        meses = {
            1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio',
            7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
        }
        return f"{meses.get(month_num, 'desconocido')} {year}"
    except:
        return mes_str


# =========================
# DEBUG HELPERS
# =========================
def _dbg_set_interpretacion(obj: dict):
    try:
        st.session_state["DBG_INT_LAST"] = obj or {}
    except Exception:
        pass


def _dbg_set_sql(tag: Optional[str], query: str, params, df: Optional[pd.DataFrame] = None):
    try:
        st.session_state["DBG_SQL_LAST_TAG"] = tag
        st.session_state["DBG_SQL_LAST_QUERY"] = query or ""
        st.session_state["DBG_SQL_LAST_PARAMS"] = params if params is not None else []
        if isinstance(df, pd.DataFrame):
            st.session_state["DBG_SQL_ROWS"] = int(len(df))
            st.session_state["DBG_SQL_COLS"] = list(df.columns)
        else:
            st.session_state["DBG_SQL_ROWS"] = None
            st.session_state["DBG_SQL_COLS"] = []
    except Exception:
        pass


def _dbg_set_result(df: Optional[pd.DataFrame]):
    try:
        if isinstance(df, pd.DataFrame):
            st.session_state["DBG_SQL_ROWS"] = int(len(df))
            st.session_state["DBG_SQL_COLS"] = list(df.columns)
    except Exception:
        pass


# =========================
# HISTORIAL
# =========================
def inicializar_historial():
    if "historial_compras" not in st.session_state:
        st.session_state["historial_compras"] = []


# =========================
# TOTALES
# =========================
def calcular_totales_por_moneda(df: pd.DataFrame) -> dict:
    """
    Devuelve totales por moneda (para el CHAT de compras normales):
    - Pesos: UYU / $ / pesos / ARS (pero excluye USD/U$S)
    - USD: USD / U$S / US$
    """
    if df is None or len(df) == 0:
        return {"Pesos": 0, "USD": 0}

    col_moneda = None
    for col in df.columns:
        if col.lower() in ["moneda", "currency"]:
            col_moneda = col
            break

    col_total = None
    for col in df.columns:
        if col.lower() in ["total", "monto", "importe", "valor", "monto_neto"]:
            col_total = col
            break

    if not col_moneda or not col_total:
        return None

    try:
        df_calc = df.copy()

        df_calc[col_total] = (
            df_calc[col_total]
            .astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.replace("$", "", regex=False)
            .str.strip()
        )
        df_calc[col_total] = pd.to_numeric(df_calc[col_total], errors="coerce").fillna(0)

        mon = df_calc[col_moneda].astype(str)

        # USD (incluye U$S)
        usd_mask = mon.str.contains(r"USD|U\$S|US\$|U\$|dolar|dólar", case=False, na=False)

        # Pesos (UYU/$/pesos) pero excluyendo USD (porque U$S contiene $)
        pesos_mask = mon.str.contains(r"UYU|\$|peso|ARS", case=False, na=False) & (~usd_mask)

        totales = {}
        totales["Pesos"] = df_calc.loc[pesos_mask, col_total].sum()
        totales["USD"] = df_calc.loc[usd_mask, col_total].sum()

        return totales

    except Exception as e:
        print(f"Error calculando totales: {e}")
        return None


def calcular_totales_por_moneda_comparativas(df: pd.DataFrame) -> dict:
    """
    ✅ PARA COMPARATIVAS: Devuelve totales por moneda detectando correctamente USD vs UYU
    - Lee la columna "Moneda" fila por fila
    - Suma las columnas de períodos (ej: "2024", "2025", "2024-11")
    """
    if df is None or len(df) == 0:
        return {"Pesos": 0, "USD": 0}

    # Buscar columna de moneda
    col_moneda = None
    for col in df.columns:
        if col.lower() in ["moneda", "currency"]:
            col_moneda = col
            break

    # Buscar columnas de períodos (excluir columnas que NO son períodos)
    numeric_cols = []
    for col in df.columns:
        # Excluir columnas obvias que NO son períodos
        if col in [col_moneda, 'Articulo', 'Proveedor', 'Cliente / Proveedor', 'Diferencia']:
            continue
        
        # Si es numérica, incluirla
        if pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)
        # Si el nombre parece un año o período, incluirla
        elif isinstance(col, str) and (col.isdigit() or '-' in col):
            numeric_cols.append(col)
    
    # Si no hay columna moneda, asumir todo en UYU
    if not col_moneda:
        total_general = 0
        for col in numeric_cols:
            try:
                total_general += pd.to_numeric(df[col], errors='coerce').fillna(0).sum()
            except:
                pass
        return {"Pesos": float(total_general), "USD": 0}

    try:
        totales = {"Pesos": 0, "USD": 0}
        
        # Iterar por cada fila y sumar según su moneda
        for idx, row in df.iterrows():
            moneda_str = str(row[col_moneda]).strip().upper()
            
            # Detectar USD
            es_usd = any(x in moneda_str for x in ["USD", "U$S", "US$", "U$", "DOLAR", "DÓLAR"])
            
            # Sumar las columnas numéricas de esta fila
            suma_fila = 0
            for col in numeric_cols:
                try:
                    val = row[col]
                    if pd.notna(val):
                        suma_fila += float(val)
                except:
                    pass
            
            # Acumular en el total correcto
            if es_usd:
                totales["USD"] += suma_fila
            else:
                totales["Pesos"] += suma_fila
        
        return totales

    except Exception as e:
        print(f"❌ Error calculando totales comparativas: {e}")
        import traceback
        traceback.print_exc()
        return {"Pesos": 0, "USD": 0}


# =========================
# DASHBOARD VENDIBLE (UI) - NUEVO
# (NO TOCA SQL / NO ROMPE LO EXISTENTE)
# =========================
import io


def _find_col(df: pd.DataFrame, candidates_lower: list) -> Optional[str]:
    for c in df.columns:
        if str(c).lower() in candidates_lower:
            return c
    return None


def _norm_moneda_view(x: str) -> str:
    s = ("" if x is None else str(x)).strip().upper()
    if not s:
        return "OTRA"
    if "U$S" in s or "USD" in s or "US$" in s or s == "U$" or "DOLAR" in s or "DÓLAR" in s:
        return "USD"
    if s == "$" or "UYU" in s or "PESO" in s:
        return "UYU"
    return s


def _safe_to_float(v) -> float:
    try:
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if not s:
            return 0.0
        s = s.replace(" ", "")
        # soporta "1.234,56" (LATAM) y "1,234.56" (EN) de forma básica
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        else:
            if "," in s and "." not in s:
                s = s.replace(",", ".")
        return float(s)
    except Exception:
        return 0.0


def _fmt_compact_money(v: float, moneda: str) -> str:
    try:
        v = float(v or 0.0)
    except Exception:
        v = 0.0

    sign = "-" if v < 0 else ""
    a = abs(v)

    if moneda == "USD":
        prefix = "U$S "
        decimals = 2
    else:
        prefix = "$ "
        decimals = 0 if a >= 1000 else 2

    if a >= 1_000_000_000:
        return f"{sign}{prefix}{a/1_000_000_000:,.2f}B".replace(",", ".")
    if a >= 1_000_000:
        return f"{sign}{prefix}{a/1_000_000:,.2f}M".replace(",", ".")
    if a >= 1_000:
        return f"{sign}{prefix}{a/1_000:,.2f}K".replace(",", ".")
    return f"{sign}{prefix}{a:,.{decimals}f}".replace(",", ".")


def _shorten_text(x, max_len: int = 52) -> str:
    s = "" if x is None else str(x)
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _df_export_clean(df: pd.DataFrame) -> pd.DataFrame:
    # No exportar columnas internas __*
    cols = [c for c in df.columns if not str(c).startswith("__")]
    return df[cols].copy() if cols else df.copy()


def _df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    try:
        return df.to_csv(index=False).encode("utf-8")
    except Exception:
        return b""


def _df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    try:
        buff = io.BytesIO()
        with pd.ExcelWriter(buff, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="datos")
        return buff.getvalue()
    except Exception:
        return b""


def _init_saved_views():
    if "FC_SAVED_VIEWS" not in st.session_state:
        st.session_state["FC_SAVED_VIEWS"] = []


def _save_view(view_name: str, data: dict):
    _init_saved_views()
    name = (view_name or "").strip()
    if not name:
        return
    # Reemplaza si existe
    out = []
    for v in st.session_state["FC_SAVED_VIEWS"]:
        if str(v.get("name", "")).strip().lower() == name.lower():
            continue
        out.append({"name": name, "data": data})
    st.session_state["FC_SAVED_VIEWS"] = out


def _get_saved_view_names() -> list:
    _init_saved_views()
    names = [v.get("name") for v in st.session_state.get("FC_SAVED_VIEWS", []) if v.get("name")]
    return sorted(names, key=lambda s: str(s).lower())


def _load_view(name: str) -> Optional[dict]:
    _init_saved_views()
    for v in st.session_state.get("FC_SAVED_VIEWS", []):
        if str(v.get("name", "")).strip().lower() == str(name or "").strip().lower():
            return v.get("data") or {}
    return None


def _paginate(df_in: pd.DataFrame, page: int, page_size: int) -> pd.DataFrame:
    if df_in is None or df_in.empty:
        return df_in
    page_size = max(1, int(page_size or 25))
    page = max(1, int(page or 1))
    start = (page - 1) * page_size
    end = start + page_size
    return df_in.iloc[start:end]


# Agregado: Mapeo de meses para display amigable
month_names = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
month_num = {name: f"{i+1:02d}" for i, name in enumerate(month_names)}

MONTH_MAPPING = {}
for year in [2023, 2024, 2025, 2026]:
    for month, num in month_num.items():
        MONTH_MAPPING[f"{year}-{num}"] = f"{month} {year}"

def code_to_display(code: str) -> str:
    return MONTH_MAPPING.get(code, code)

def display_to_code(display: str) -> str:
    reverse_mapping = {v: k for k, v in MONTH_MAPPING.items()}
    return reverse_mapping.get(display, display)

def rename_month_columns(df: pd.DataFrame) -> pd.DataFrame:
    df_renamed = df.copy()
    df_renamed.rename(columns=MONTH_MAPPING, inplace=True)
    return df_renamed


def render_dashboard_compras_vendible(df: pd.DataFrame, titulo: str = "Resultado", key_prefix: str = "", hide_metrics: bool = False):
    if df is None or df.empty:
        st.warning("⚠️ No hay resultados para mostrar.")
        return

    # CSS MODERNO (header gradiente + tarjetas)
    st.markdown(
        """
        <style>
        /* ==========================================
           HEADER CON TÍTULO Y METADATA
           ========================================== */
        .fc-header-modern {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px;
            padding: 20px 24px;
            margin-bottom: 20px;
            color: white;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
        }
        
        .fc-title-modern {
            font-size: 1.3rem;
            font-weight: 700;
            margin: 0 0 8px 0;
            color: white;
        }
        
        .fc-badge-modern {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.85rem;
            color: white;
        }
        
        .fc-meta-modern {
            font-size: 0.85rem;
            opacity: 0.9;
            margin: 0;
            color: rgba(255,255,255,0.9);
        }
        
        /* ==========================================
           TARJETAS DE MÉTRICAS (4 columnas)
           ========================================== */
        .fc-metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 32px;  /* ← Aumentado de 16px a 32px para más separación */
            margin-bottom: 20px;
        }
        
        .fc-metric-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 18px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            transition: all 0.2s ease;
        }
        
        .fc-metric-card:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            transform: translateY(-2px);
        }
        
        .fc-metric-label {
            font-size: 0.85rem;
            color: #6b7280;
            margin: 0 0 6px 0;
            font-weight: 500;
        }
        
        .fc-metric-value {
            font-size: 1.6rem;
            font-weight: 700;
            color: #111827;
            margin: 0;
        }
        
        .fc-metric-help {
            font-size: 0.75rem;
            color: #9ca3af;
            margin: 4px 0 0 0;
        }
        
        /* ==========================================
           CARD TOTAL GRANDE
           ========================================== */
        .total-summary-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px;
            padding: 40px 32px;
            margin-bottom: 24px;
            color: white;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
            text-align: center;
        }
        
        .total-summary-value {
            font-size: 3rem;
            font-weight: 700;
            margin: 0 0 8px 0;
        }
        
        .total-summary-label {
            font-size: 1.2rem;
            opacity: 0.9;
            margin: 0;
        }
        
        /* ==========================================
           CARD RESUMEN EJECUTIVO
           ========================================== */
        .resumen-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 14px 18px !important;
            margin-bottom: 24px !important;  /* ← MÁS ESPACIO ENTRE CARDS (antes 12px) */
            min-height: 120px !important;  /* ← MÁS BAJA (antes 140px) */
            display: flex !important;
            flex-direction: column !important;
            box-sizing: border-box !important;
        }
        
        .resumen-title {
            font-size: 0.8rem !important;  /* Un poco más pequeño */
            font-weight: 700 !important;
            margin: 0 0 6px 0 !important;
            color: #374151;
        }
        
        .resumen-text {
            font-size: 0.7rem !important;  /* Un poco más pequeño */
            color: #6b7280;
            margin: 0 !important;
            line-height: 1.3 !important;  /* Menos interlineado */
        }
        
        /* ==========================================
           PROVIDER CARD
           ========================================== */
        .provider-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 16px !important;
            margin-bottom: 24px !important;  /* ← MÁS ESPACIO */
            min-height: 120px !important;  /* ← MÁS BAJA */
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            display: flex !important;
            flex-direction: column !important;
        }
        
        .provider-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }
        
        .provider-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
            color: white;
            font-weight: 700;
        }
        
        .provider-info {
            flex: 1;
        }
        
        .provider-name {
            font-size: 0.95rem;
            font-weight: 700;
            color: #111827;
            margin: 0 0 2px 0;
        }
        
        .provider-subtitle {
            font-size: 0.8rem;
            color: #6b7280;
            margin: 0;
        }
        
        .provider-amount {
            font-size: 1.2rem;
            font-weight: 700;
            color: #111827;
            text-align: right;
        }
        
        .provider-amount-sub {
            font-size: 0.8rem;
            color: #6b7280;
            text-align: right;
            margin-top: 2px;
        }
        
        .progress-bar {
            width: 100%;
            height: 6px;
            background: #e5e7eb;
            border-radius: 3px;
            overflow: hidden;
            margin: 8px 0;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 3px;
        }
        
        /* ==========================================
           RESPONSIVE (MOBILE)
           ========================================== */
        @media (max-width: 768px) {
            .fc-metrics-grid {
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
            }
            .fc-metric-value {
                font-size: 1.3rem;
            }
            .total-summary-value {
                font-size: 2.5rem;
            }
        }
        
        /* Legacy (mantener compatibilidad) */
        .fc-subtle { color: rgba(49,51,63,0.65); font-size: 0.9rem; }
        .fc-title { font-size: 1.05rem; font-weight: 700; margin: 0 0 4px 0; }
        
        /* ==========================================
           OCULTAR BOTÓN NATIVO DE STREAMLIT
           ========================================== */
        [data-testid="stDataFrameToolbar"] {
            display: none !important;
        }
        
        /* ==========================================
           OCULTAR LÍNEAS HORIZONTALES (hr) GENERADAS POR st.markdown("---")
           ========================================== */
        hr {
            display: none !important;
        }
        
        /* Botón de exportación arriba */
        .fc-export-btn {
            text-align: right;
            margin-bottom: 8px;
        }
        
        /* Ajuste para Top 5 Artículos más largo */
        .top5-card {
            min-height: 260px !important;  /* Hacerlo más largo para alinear con Actividad */
        }
        """ + (".fc-metrics-grid { display: none !important; }" if hide_metrics else "") + """
        </style>
        """,
        unsafe_allow_html=True
    )

    df_view = rename_month_columns(df.copy())  # Renombra columnas de meses para display

    col_proveedor = _find_col(df_view, ["proveedor", "cliente / proveedor"])
    col_articulo = _find_col(df_view, ["articulo", "artículo"])
    col_fecha = _find_col(df_view, ["fecha"])
    col_moneda = _find_col(df_view, ["moneda", "currency"])
    col_total = _find_col(df_view, ["total", "monto", "importe", "valor", "monto_neto"])
    col_nro = _find_col(df_view, ["nro_factura", "nro. comprobante", "nro comprobante", "nro_comprobante"])
    col_cantidad = _find_col(df_view, ["cantidad"])

    if col_moneda:
        df_view["__moneda_view__"] = df_view[col_moneda].apply(_norm_moneda_view)
    else:
        df_view["__moneda_view__"] = "OTRA"

    if col_fecha:
        df_view["__fecha_view__"] = pd.to_datetime(df_view[col_fecha], errors="coerce")
    else:
        df_view["__fecha_view__"] = pd.NaT

    # FIX: Calcular __total_num__ correctamente para comparaciones
    if col_total:
        df_view["__total_num__"] = df_view[col_total].apply(_safe_to_float)
    else:
        numeric_cols = [c for c in df_view.columns if c != col_proveedor and pd.api.types.is_numeric_dtype(df_view[c])]
        if numeric_cols:
            # Para comparaciones: suma las columnas numéricas (ej: "2024-11" + "2025-11")
            df_view["__total_num__"] = df_view[numeric_cols].sum(axis=1)
        else:
            df_view["__total_num__"] = 0.0

    # Contexto
    filas_total = int(len(df_view))
    facturas = int(df_view[col_nro].nunique()) if col_nro else 0
    proveedores = int(df_view[col_proveedor].nunique()) if col_proveedor else 0
    articulos = int(df_view[col_articulo].nunique()) if col_articulo else 0

    # Rango fechas
    rango_txt = ""
    if df_view["__fecha_view__"].notna().any():
        dmin = df_view["__fecha_view__"].min()
        dmax = df_view["__fecha_view__"].max()
        try:
            rango_txt = f" · {dmin.date()} → {dmax.date()}"
        except Exception:
            rango_txt = ""

    # ==========================================
    # HEADER MODERNO CON GRADIENTE
    # ==========================================
    st.markdown(f"""
    <div class="fc-header-modern">
        <h2 class="fc-title-modern">📊 {titulo}</h2>
        <div class="fc-badge-modern">
            ✅ {filas_total} registros encontrados
        </div>
        <p class="fc-meta-modern">
            Facturas: {facturas} · Proveedores: {proveedores} · Artículos: {articulos}{rango_txt}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ==========================================
    # MÉTRICAS CON TARJETAS MODERNAS (ocultas si hide_metrics)
    # ==========================================
    tot_uyu = float(df_view.loc[df_view["__moneda_view__"] == "UYU", "__total_num__"].sum())
    tot_usd = float(df_view.loc[df_view["__moneda_view__"] == "USD", "__total_num__"].sum())
    # FIX: Si no hay columna moneda (como en comparaciones), mostrar total general en UYU
    if not col_moneda:
        tot_uyu = float(df_view["__total_num__"].sum())
        tot_usd = 0.0

    st.markdown(f"""
    <div class="fc-metrics-grid">
        <div class="fc-metric-card">
            <p class="fc-metric-label">Total UYU 💰</p>
            <p class="fc-metric-value">{_fmt_compact_money(tot_uyu, "UYU")}</p>
            <p class="fc-metric-help">Valor exacto: $ {tot_uyu:,.2f}</p>
        </div>
        <div class="fc-metric-card">
            <p class="fc-metric-label">Total USD 💵</p>
            <p class="fc-metric-value">{_fmt_compact_money(tot_usd, "USD")}</p>
            <p class="fc-metric-help">Valor exacto: U$S {tot_usd:,.2f}</p>
        </div>
        <div class="fc-metric-card">
            <p class="fc-metric-label">{"Facturas 📄" if col_nro else "Registros 📄"}</p>
            <p class="fc-metric-value">{facturas if col_nro else filas_total}</p>
        </div>
        <div class="fc-metric-card">
            <p class="fc-metric-label">Proveedores 🏭</p>
            <p class="fc-metric-value">{proveedores}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ============================================================
    # SIN FILTROS (mostrar todo)
    # ============================================================
    df_f = df_view.copy()

    # ============================================================
    # TABS
    # ============================================================
    tab_all, tab_uyu, tab_usd, tab_graf, tab_tabla = st.tabs(
        ["Vista general", "Pesos (UYU)", "Dólares (USD)", "Gráfico (Top 10 artículos)", "Tabla"]
    )

    with tab_all:
        # 📊 GRID 2x2 DE CARDS
        col1, col2 = st.columns(2)
        
        with col1:
            # CARD 1: PERÍODO ANALIZADO
            st.markdown(f"""
            <div class="resumen-card">
                <h4 class="resumen-title">📅 Período Analizado</h4>
                <p class="resumen-text">{rango_txt if rango_txt else 'Sin datos de fecha'}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # CARD 3: ACTIVIDAD EN EL TIEMPO
            if col_fecha and not df_f.empty:
                df_f['fecha_dt'] = pd.to_datetime(df_f[col_fecha], errors='coerce')
                df_f['fecha_str'] = df_f['fecha_dt'].dt.strftime('%d/%m')
                gasto_diario = df_f.groupby('fecha_str')['__total_num__'].sum()
                if col_nro:
                    facturas_diario = df_f.groupby('fecha_str')[col_nro].nunique()
                else:
                    facturas_diario = df_f.groupby('fecha_str').size()
                
                if not gasto_diario.empty:
                    dia_mayor_gasto = gasto_diario.idxmax()
                    mayor_gasto = gasto_diario.max()
                    
                    dia_mas_facturas = facturas_diario.idxmax()
                    mas_facturas = facturas_diario.max()
                    
                    promedio_diario = gasto_diario.mean()
                    
                    st.markdown(f"""
                    <div class="resumen-card">
                        <h4 class="resumen-title">⏰ Actividad en el Tiempo</h4>
                        <p class="resumen-text">
                            Día con mayor gasto: {dia_mayor_gasto} — {_fmt_compact_money(mayor_gasto, "UYU")}<br>
                            Día con más facturas: {dia_mas_facturas} — {mas_facturas} facturas<br>
                            Promedio diario: {_fmt_compact_money(promedio_diario, "UYU")}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
        
        with col2:
            # CARD 2: TOP 5 ARTÍCULOS
            if col_articulo:
                top_art = (
                    df_f.groupby(col_articulo)["__total_num__"]
                    .sum()
                    .sort_values(ascending=False)
                ).head(5)
                
                if len(top_art) > 0:
                    items_html = ""
                    for idx, (art, monto) in enumerate(top_art.items(), 1):
                        art_short = _shorten_text(art, 40)
                        monto_fmt = _fmt_compact_money(monto, "UYU")
                        items_html += f'<span class="numero-badge">{idx}</span>{art_short} — {monto_fmt}<br>'
                    
                    st.markdown(f"""
                    <div class="resumen-card top5-card">
                        <h4 class="resumen-title">📊 Top 5 Artículos</h4>
                        <p class="resumen-text">{items_html}</p>
                    </div>
                    """, unsafe_allow_html=True)

    with tab_uyu:
        # Calcular total UYU
        total_uyu_tab = df_f[df_f["__moneda_view__"] == "UYU"]["__total_num__"].sum()
        
        st.markdown(f"""
        <div class="total-summary-card">
            <p class="total-summary-value">{_fmt_compact_money(total_uyu_tab, "UYU")}</p>
            <p class="total-summary-label">Total Pesos (UYU)</p>
        </div>
        """, unsafe_allow_html=True)

    with tab_usd:
        # Calcular total USD
        total_usd_tab = df_f[df_f["__moneda_view__"] == "USD"]["__total_num__"].sum()
        
        st.markdown(f"""
        <div class="total-summary-card">
            <p class="total-summary-value">{_fmt_compact_money(total_usd_tab, "USD")}</p>
            <p class="total-summary-label">Total Dólares (USD)</p>
        </div>
        """, unsafe_allow_html=True)

    with tab_graf:
        if df_f is None or df_f.empty or not col_articulo:
            st.info("Sin datos suficientes para gráfico.")
        else:
            g_mon = st.selectbox(
                "Moneda del gráfico",
                options=["TODAS", "UYU", "USD"],
                index=0,
                key=f"{key_prefix}g_mon"
            )
            df_g = df_f.copy()
            if g_mon != "TODAS":
                df_g = df_g[df_g["__moneda_view__"] == g_mon]

            top_art = (
                df_g.groupby(col_articulo)["__total_num__"]
                .sum()
                .sort_values(ascending=False)
            ).head(10)

            if len(top_art) == 0:
                st.info("Sin resultados para ese filtro.")
            else:
                df_top_art = top_art.reset_index()
                df_top_art.columns = [col_articulo, "Total"]
                df_top_art[col_articulo] = df_top_art[col_articulo].apply(lambda x: _shorten_text(x, 60))

                st.dataframe(df_top_art, use_container_width=True, hide_index=True, height=320)

                try:
                    chart_df = df_top_art.set_index(col_articulo)["Total"]
                    st.bar_chart(chart_df)
                except Exception:
                    pass

    with tab_tabla:
        if df_f is None or df_f.empty:
            st.info("Sin resultados para mostrar.")
        else:
            # Orden preferido (mantiene columnas originales)
            pref = []
            for c in [col_proveedor, col_articulo, col_nro, col_fecha, col_cantidad, col_moneda, col_total]:
                if c and c in df_f.columns:
                    pref.append(c)
            resto = [c for c in df_f.columns if c not in pref and not str(c).startswith("__")]
            show_cols = pref + resto

            # Paginación
            t1, t2, t3 = st.columns([1.2, 1.0, 1.8])
            with t1:
                page_size = st.selectbox(
                    "Filas por página",
                    options=[25, 50, 100, 250],
                    index=0,
                    key=f"{key_prefix}page_size"
                )
            max_pages = max(1, int((len(df_f) + int(page_size) - 1) / int(page_size)))
            with t2:
                page = st.number_input(
                    "Página",
                    min_value=1,
                    max_value=max_pages,
                    value=min(st.session_state.get(f"{key_prefix}page", 1), max_pages),
                    step=1,
                    key=f"{key_prefix}page"
                )
            with t3:
                st.caption(f"Página {int(page)} de {max_pages} · Total filas: {len(df_f)}")

            df_page = _paginate(df_f[show_cols], int(page), int(page_size)).copy()

            # Recortar textos para vista limpia
            if col_proveedor and col_proveedor in df_page.columns:
                df_page[col_proveedor] = df_page[col_proveedor].apply(lambda x: _shorten_text(x, 60))
            if col_articulo and col_articulo in df_page.columns:
                df_page[col_articulo] = df_page[col_articulo].apply(lambda x: _shorten_text(x, 60))

            st.dataframe(df_page, use_container_width=True, height=460)

            # Drill-down por factura
            if col_nro and col_nro in df_f.columns:
                st.markdown("#### Detalle por factura")
                nros = [n for n in df_f[col_nro].dropna().astype(str).unique().tolist() if str(n).strip()]
                nros = sorted(nros)[:5000]

                det_col1, det_col2 = st.columns([1.2, 2.8])
                with det_col1:
                    det_search = st.text_input(
                        "Buscar nro factura",
                        value="",
                        key=f"{key_prefix}det_search",
                        placeholder="Ej: A00060907"
                    ).strip()

                nro_opts = nros
                if det_search:
                    nro_opts = [n for n in nros if det_search.lower() in str(n).lower()]
                    nro_opts = nro_opts[:200]

                with det_col2:
                    nro_sel = st.selectbox(
                        "Seleccionar factura",
                        options=["(ninguna)"] + nro_opts,
                        index=0,
                        key=f"{key_prefix}det_nro_sel"
                    )

                if nro_sel and nro_sel != "(ninguna)":
                    df_fac = df_f[df_f[col_nro].astype(str) == str(nro_sel)].copy()

                    tot_fac = float(df_fac["__total_num__"].sum())
                    mon_fac = "USD" if (df_fac["__moneda_view__"] == "USD").any() and not (df_fac["__moneda_view__"] == "UYU").any() else "UYU"
                    st.markdown(
                        f"**Factura:** `{nro_sel}` · **Items:** {len(df_fac)} · **Total:** {_fmt_compact_money(tot_fac, mon_fac)}"
                    )

                    pref_fac = []
                    for c in [col_articulo, col_cantidad, col_total, col_fecha, col_moneda]:
                        if c and c in df_fac.columns:
                            pref_fac.append(c)
                    resto_fac = [c for c in df_fac.columns if c not in pref_fac and not str(c).startswith("__")]
                    show_cols_fac = pref_fac + resto_fac

                    df_fac_disp = df_fac[show_cols_fac].copy()
                    if col_articulo and col_articulo in df_fac_disp.columns:
                        df_fac_disp[col_articulo] = df_fac_disp[col_articulo].apply(lambda x: _shorten_text(x, 70))

                    st.dataframe(df_fac_disp, use_container_width=True, height=320)


# =========================
# DASHBOARD COMPARATIVAS MODERNO
# =========================
def render_dashboard_comparativas_moderno(df: pd.DataFrame, titulo: str = "Comparativas"):
    """
    Dashboard con diseño moderno tipo card (similar a la imagen)
    """
    
    if df is None or df.empty:
        st.warning("⚠️ No hay datos para mostrar")
        return
    
    # ==========================================
    # CALCULAR MÉTRICAS CORRECTAMENTE
    # ==========================================
    
    print(f"🐛 DEBUG: Columnas del DataFrame: {df.columns.tolist()}")
    
    # Identificar columnas de períodos (años como 2024, 2025 o meses como 2024-11)
    # Excluir 'Proveedor', 'Articulo', 'Moneda', 'Diferencia'
    cols_periodos = []
    for c in df.columns:
        # Es un período si es numérica o tiene guión y no es excluida
        if pd.api.types.is_numeric_dtype(df[c]) and c not in ['Diferencia']:
            cols_periodos.append(c)
        elif isinstance(c, str) and ('-' in c or c.isdigit()) and c not in ['Proveedor', 'Articulo', 'Moneda', 'Cliente / Proveedor']:
            cols_periodos.append(c)
    
    # ✅ AGREGADO: Convertir columnas de períodos a numérico
    for col in cols_periodos:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    print(f"🐛 DEBUG: Columnas de períodos detectadas: {cols_periodos}")
    
    # Calcular totales por moneda - SEPARAR CORRECTAMENTE SIN FALLBACK
    total_uyu = 0
    total_usd = 0
    
    # ✅ FIX: Buscar columna "Moneda" o "moneda" (case insensitive)
    col_moneda = None
    for col in df.columns:
        if col.lower() == 'moneda':
            col_moneda = col
            break
    
    if col_moneda and cols_periodos:
        # ✅ FIX: Buscar TODAS las variaciones de pesos y dólares
        df['Moneda_norm'] = df[col_moneda].astype(str).str.strip().str.upper()
        
        # Pesos: $, UYU, PESO
        df_pesos = df[df['Moneda_norm'].str.contains(r'^\$|UYU|PESO', regex=True, na=False) & 
                      ~df['Moneda_norm'].str.contains(r'U\$S|USD|U\$|US\$', regex=True, na=False)]
        
        # Dólares: U$S, USD, US$, U$
        df_usd = df[df['Moneda_norm'].str.contains(r'U\$S|USD|U\$|US\$', regex=True, na=False)]
        
        if not df_pesos.empty:
            for col in cols_periodos:
                try:
                    total_uyu += pd.to_numeric(df_pesos[col], errors='coerce').fillna(0).sum()
                except:
                    pass
        
        if not df_usd.empty:
            for col in cols_periodos:
                try:
                    total_usd += pd.to_numeric(df_usd[col], errors='coerce').fillna(0).sum()
                except:
                    pass
        
        print(f"🐛 DEBUG: Total UYU: {total_uyu}, Total USD: {total_usd}")
    
    # Determinar si es comparación de artículos (basado en entrada)
    # Nota: Aquí asumimos que si 'articulos' fue seleccionado en la UI, es artículos
    # Pero como no tenemos acceso directo, usamos la estructura del DF
    es_articulos = 'Articulo' in df.columns and 'Proveedor' not in df.columns
    entidad = 'Artículos' if es_articulos else 'Proveedores'
    entidad_singular = 'Artículo' if es_articulos else 'Proveedor'
    todos_entidad = f"Todos los {entidad.lower()}"
    
    # Número de entidades y registros
    num_entidades = df['Articulo'].nunique() if es_articulos else df['Proveedor'].nunique() if 'Proveedor' in df.columns else 0
    num_registros = len(df)
    
    # Identificar qué años/meses se están comparando
    periodos = cols_periodos
    num_periodos = len(periodos)
    
    # ==========================================
    # CSS Moderno (restante) - AGREGAR ESPACIADO Y ALTURA UNIFORME
    # ==========================================
    st.markdown("""
    <style>
        /* ==========================================
           HEADER CON TÍTULO Y METADATA
           ========================================== */
        .dash-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px;
            padding: 24px 28px;
            margin-bottom: 24px;
            color: white;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
        }
        
        .dash-title {
            font-size: 1.5rem;
            font-weight: 700;
            margin: 0 0 12px 0;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .dash-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9rem;
            margin-bottom: 8px;
        }
        
        .dash-meta {
            font-size: 0.85rem;
            opacity: 0.9;
            margin: 0;
        }
        
        /* ==========================================
           TARJETAS DE MÉTRICAS (4 columnas)
           ========================================== */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 32px;  /* ← Aumentado de 16px a 32px para más separación */
            margin-bottom: 24px;
        }
        
        .metric-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            transition: all 0.2s ease;
        }
        
        .metric-card:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            transform: translateY(-2px);
        }
        
        .metric-label {
            font-size: 0.85rem;
            color: #6b7280;
            margin: 0 0 8px 0;
            font-weight: 500;
        }
        
        .metric-value {
            font-size: 1.75rem;
            font-weight: 700;
            color: #111827;
            margin: 0;
        }
        
        /* ==========================================
           CARD PROVEEDOR DESTACADO (para 1 proveedor)
           ========================================== */
        .single-provider-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px;
            padding: 32px 28px;
            margin-bottom: 24px;
            color: white;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
            text-align: center;
        }
        
        .single-provider-icon {
            width: 64px;
            height: 64px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 16px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 16px;
        }
        
        .single-provider-name {
            font-size: 1.5rem;
            font-weight: 700;
            margin: 0 0 8px 0;
        }
        
        .single-provider-detail {
            font-size: 0.9rem;
            opacity: 0.9;
            margin: 0;
        }
        
        /* ==========================================
           CARD PROVEEDOR PRINCIPAL
           ========================================== */
        .provider-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }
        
        .provider-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }
        
        .provider-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
            color: white;
            font-weight: 700;
        }
        
        .provider-info {
            flex: 1;
        }
        
        .provider-name {
            font-size: 0.95rem;
            font-weight: 700;
            color: #111827;
            margin: 0 0 2px 0;
        }
        
        .provider-subtitle {
            font-size: 0.8rem;
            color: #6b7280;
            margin: 0;
        }
        
        .provider-amount {
            font-size: 1.2rem;
            font-weight: 700;
            color: #111827;
            text-align: right;
        }
        
        .provider-amount-sub {
            font-size: 0.8rem;
            color: #6b7280;
            text-align: right;
            margin-top: 2px;
        }
        
        .progress-bar {
            width: 100%;
            height: 6px;
            background: #e5e7eb;
            border-radius: 3px;
            overflow: hidden;
            margin: 8px 0;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 3px;
        }
        
        /* ==========================================
           TABS Y BOTONES
           ========================================== */
        .btn-export {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: white;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            padding: 8px 16px;
            font-size: 0.9rem;
            font-weight: 500;
            color: #374151;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .btn-export:hover {
            background: #f9fafb;
            border-color: #9ca3af;
        }
        
        /* ==========================================
           RESPONSIVE (MOBILE)
           ========================================== */
        @media (max-width: 768px) {
            .metrics-grid {
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
            }
            
            .metric-value {
                font-size: 1.4rem;
            }
            
            .provider-header {
                flex-direction: column;
                align-items: flex-start;
            }
            
            .provider-amount {
                text-align: left;
                margin-top: 8px;
            }
            
            .dash-title {
                font-size: 1.2rem;
            }
            
            .action-bar {
                flex-wrap: nowrap !important;
                height: 48px !important;  /* Altura máxima de la barra */
                gap: 8px !important;  /* Separación uniforme */
            }
            
            .action-left, .action-right {
                justify-content: center;
            }
        }
        
        /* Espaciado consistente */
        .action-bar {
            margin-bottom: 20px !important;  /* Espacio entre barra y tarjetas */
        }
        
        .metrics-grid {
            margin-bottom: 20px !important;  /* Espacio entre tarjetas y gráfico */
        }
        
        /* INTERLINEADO ENTRE BOTONES Y TARJETAS */
        .comparison-wrapper {
            margin-top: 40px !important;  /* Más espacio arriba */
            margin-bottom: 20px !important;  /* Espacio entre gráfico y siguiente */
        }
        
        /* ALTURA UNIFORME ENTRE GRÁFICA Y TOP 5 */
        .comparison-wrapper .stColumns {
            display: flex !important;
            align-items: stretch !important;  /* Hace que las columnas tengan la misma altura */
        }
    </style>
    """, unsafe_allow_html=True)
    
    # ==========================================
    # HTML ESTRUCTURA
    # ==========================================
    
    # HEADER
    st.markdown(f"""
    <div class="dash-header">
        <h2 class="dash-title">📊 {titulo}</h2>
        <div class="dash-badge">
            ✅ Resultado: Se encontraron {len(df)} registros
        </div>
        <p class="dash-meta">
            📅 Última actualización: {datetime.now().strftime("%d/%m/%Y %H:%M")}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # MÉTRICAS
    # Formatear totales
    total_uyu_fmt = f"$ {total_uyu/1_000_000:.2f}M" if total_uyu >= 1_000_000 else f"$ {total_uyu:,.0f}".replace(",", ".")
    total_usd_fmt = f"U$S {total_usd/1_000:.0f}K" if total_usd >= 1_000 else f"U$S {total_usd:,.0f}"
    
    st.markdown(f"""
    <div class="metrics-grid">
        <div class="metric-card">
            <p class="metric-label">Total UYU 💰</p>
            <p class="metric-value">{total_uyu_fmt}</p>
            <p style="font-size: 0.75rem; color: #9ca3af; margin-top: 4px;">
                Suma de {len(periodos)} período(s)
            </p>
        </div>
        <div class="metric-card">
            <p class="metric-label">Total USD 💵</p>
            <p class="metric-value">{total_usd_fmt}</p>
            <p style="font-size: 0.75rem; color: #9ca3af; margin-top: 4px;">
                Suma de {len(periodos)} período(s)
            </p>
        </div>
        <div class="metric-card">
            <p class="metric-label">Registros 📄</p>
            <p class="metric-value">{num_registros}</p>
            <p style="font-size: 0.75rem; color: #9ca3af; margin-top: 4px;">
                {len(df_pesos) if 'Moneda' in df.columns and not df_pesos.empty else 0} en pesos, {len(df_usd) if 'Moneda' in df.columns and not df_usd.empty else 0} en USD
            </p>
        </div>
        <div class="metric-card">
            <p class="metric-label">{entidad} 🏭</p>
            <p class="metric-value">{num_entidades}</p>
            <p style="font-size: 0.75rem; color: #9ca3af; margin-top: 4px;">
                Comparando {', '.join(map(str, periodos[:3]))}{"..." if len(periodos) > 3 else ""}
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ==========================================
    # ❌ TARJETAS DUPLICADAS ELIMINADAS
    # ==========================================
    
    # TABS CON DATOS
    tabs = st.tabs(["📊 Vista General", "💵 Pesos (UYU)", "💰 Dólares (USD)", "📈 Gráfico", "📋 Tabla"])
    
    # ==========================================
    # TAB 1: VISTA GENERAL - DASHBOARD EJECUTIVO IMPACTANTE
    # ==========================================
    with tabs[0]:
        # Validar que tengamos al menos 2 períodos
        periodos_validos = [p for p in periodos if p in df.columns]
        
        if len(periodos_validos) >= 2:
            # 🎯 CALCULAR MÉTRICAS PRINCIPALES
            p1 = periodos_validos[0]
            p2 = periodos_validos[1]
            
            total_p1 = df[p1].sum()
            total_p2 = df[p2].sum()
            diferencia = total_p2 - total_p1
            variacion_pct = ((total_p2 / total_p1 - 1) * 100) if total_p1 != 0 else 0
            
            # 🎨 DETERMINAR COLOR Y ESTILO
            if variacion_pct > 0:
                color_bg = "linear-gradient(135deg, #10b981 0%, #059669 100%)"
                icono = "🚀"
                color_texto = "#10b981"
            else:
                color_bg = "linear-gradient(135deg, #ef4444 0%, #dc2626 100%)"
                icono = "📉"
                color_texto = "#ef4444"
            
            # Formatear diferencia
            dif_fmt = f"${abs(diferencia)/1_000_000:.1f}M" if abs(diferencia) >= 1_000_000 else f"${abs(diferencia):,.0f}".replace(",", ".")
            signo = "+" if diferencia > 0 else "-"
            
            # 📊 FIX 3: WRAPPER PARA BLOQUE KPIs (forzar flujo vertical)
            st.markdown('<div style="margin-bottom:20px;">', unsafe_allow_html=True)  # Espacio
            
            # 📊 FILA 1: 2 CARDS ARRIBA (CRECIMIENTO EN $ + VARIACIÓN EN %)
            col_crec, col_var = st.columns(2)
            
            with col_crec:
                card_html = f'<div style="background: {color_bg}; border-radius: 8px; padding: 12px 16px; text-align: center; color: white; box-shadow: 0 2px 8px rgba(0,0,0,0.08); display: flex; flex-direction: column; justify-content: center;"><h3 style="margin: 0; font-size: 0.75rem; font-weight: 600; opacity: 0.95; letter-spacing: 1px;">CRECIMIENTO</h3><h1 style="margin: 6px 0 2px 0; font-size: 1.5rem; font-weight: 800; line-height: 1;">{signo}{dif_fmt}</h1><p style="margin: 0; font-size: 0.7rem; font-weight: 500; opacity: 0.9;">vs {p1}</p></div>'
                st.markdown(card_html, unsafe_allow_html=True)
            
            with col_var:
                card_html = f'<div style="background: white; border: 2px solid {color_texto}; border-radius: 8px; padding: 12px 16px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.08); display: flex; flex-direction: column; justify-content: center;"><h3 style="margin: 0; font-size: 0.75rem; font-weight: 600; color: #6b7280; letter-spacing: 1px;">VARIACIÓN</h3><h1 style="margin: 6px 0 2px 0; font-size: 1.5rem; font-weight: 800; line-height: 1; color: {color_texto};">{variacion_pct:+.1f}%</h1><p style="margin: 0; font-size: 0.7rem; font-weight: 500; color: #6b7280;">Cambio total</p></div>'
                st.markdown(card_html, unsafe_allow_html=True)
            
            # Cerrar wrapper KPIs
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # 📊 FIX 3: WRAPPER PARA BLOQUE GRÁFICO + TOP5
            st.markdown('<div class="comparison-wrapper" style="margin-bottom:20px;">', unsafe_allow_html=True)  # Espacio
            
            # 📊 FILA 2: GRÁFICO (50%) + TOP 5 (50%) - ✅ Alineado con 2 columnas arriba
            col_graph, col_top5 = st.columns(2)  # ✅ Cambiado a st.columns(2) para igual ancho
            
            with col_graph:
                # ✅ FIX #3: GRÁFICO INTELIGENTE SEGÚN CANTIDAD DE ENTIDADES
                if len(df) == 1:
                    st.markdown("#### 📊 Comparación de Períodos")
                else:
                    st.markdown("#### 📊 Comparación")
                
                try:
                    import plotly.graph_objects as go
                    
                    entity_col = 'Articulo' if es_articulos else 'Proveedor' if 'Proveedor' in df.columns else 'Articulo'
                    
                    if len(df) == 1:
                        # ✅ 1 SOLO ARTÍCULO/PROVEEDOR: Gráfico simple de períodos
                        fig = go.Figure()
                        fig.add_trace(go.Bar(
                            name=str(p1),
                            x=['Período 1'],
                            y=[total_p1],
                            marker_color='#667eea',
                            text=[f'${total_p1/1_000_000:.1f}M' if total_p1 >= 1_000_000 else f'${total_p1:,.0f}'.replace(",", ".")],
                            textposition='outside'
                        ))
                        fig.add_trace(go.Bar(
                            name=str(p2),
                            x=['Período 2'],
                            y=[total_p2],
                            marker_color='#764ba2',
                            text=[f'${total_p2/1_000_000:.1f}M' if total_p2 >= 1_000_000 else f'${total_p2:,.0f}'.replace(",", ".")],
                            textposition='outside'
                        ))
                        
                        fig.update_layout(
                            xaxis_title="",
                            yaxis_title="Monto",
                            template="plotly_white",
                            showlegend=True,
                            barmode='group',
                            margin=dict(t=20, b=30, l=50, r=20)
                        )
                    else:
                        # ✅ MÚLTIPLES ENTIDADES: Top 8 con barras agrupadas
                        df_graph = df.copy()
                        df_graph['Total'] = df_graph[periodos_validos].sum(axis=1)
                        df_graph = df_graph.nlargest(8, 'Total')
                        
                        fig = go.Figure()
                        fig.add_trace(go.Bar(
                            name=str(p1),
                            x=df_graph[entity_col],
                            y=df_graph[p1].astype(float),
                            marker_color='#667eea',
                            text=df_graph[p1].apply(lambda x: f'${float(x)/1_000_000:.1f}M' if x >= 1_000_000 else f'${float(x):,.0f}'.replace(",", ".") if pd.notna(x) else "0"),
                            textposition='outside',
                            textfont=dict(size=10)
                        ))
                        fig.add_trace(go.Bar(
                            name=str(p2),
                            x=df_graph[entity_col],
                            y=df_graph[p2].astype(float),
                            marker_color='#764ba2',
                            text=df_graph[p2].apply(lambda x: f'${float(x)/1_000_000:.1f}M' if x >= 1_000_000 else f'${float(x):,.0f}'.replace(",", ".") if pd.notna(x) else "0"),
                            textposition='outside',
                            textfont=dict(size=10)
                        ))
                        
                        fig.update_layout(
                            xaxis_title="",
                            yaxis_title="Monto",
                            template="plotly_white",
                            showlegend=True,
                            barmode='group',
                            xaxis={'tickangle': -45, 'tickfont': {'size': 9}},
                            margin=dict(t=20, b=50, l=50, r=20)
                        )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
            
            with col_top5:
                st.markdown("#### 📊 Top 5 Períodos Más Comprados")
                
                # ✅ TOP 5 PERÍODOS: Si hay artículos seleccionados, mostrar top períodos para ese artículo
                articulos_sel = st.session_state.get("art_multi", [])
                
                if articulos_sel and len(articulos_sel) > 0:
                    # Mostrar top períodos para el primer artículo seleccionado
                    articulo_seleccionado = articulos_sel[0]  # Asumir uno; ajusta si múltiples
                    try:
                        # Obtener contexto de session_state
                        anios_ctx = st.session_state.get("anios_sel", [2024, 2025])
                        meses_ctx = st.session_state.get("meses_multi", [])
                        proveedores_ctx = st.session_state.get("comparativas_proveedores_multi", [])
                        
                        meses_param = meses_ctx if meses_ctx and len(meses_ctx) > 0 else None
                        proveedores_param = proveedores_ctx if proveedores_ctx and len(proveedores_ctx) > 0 else None
                        
                        df_top_periodos = get_top_5_periodos_por_articulo(
                            articulo=articulo_seleccionado,
                            anios=anios_ctx,
                            meses=meses_param,
                            proveedores=proveedores_param
                        )
                        
                        if df_top_periodos is None or df_top_periodos.empty:
                            st.info("No hay datos para los períodos seleccionados")
                        else:
                            # Formatear totales
                            df_display = df_top_periodos.copy()
                            df_display['total'] = df_display['total'].apply(lambda x: f"${float(x):,.0f}".replace(",", "."))
                            df_display.columns = ['Período', 'Total Comprado']
                            st.dataframe(df_display, use_container_width=True, hide_index=True, height=300)
                            st.caption(f"Top períodos para el artículo: **{articulo_seleccionado}**")
                    except Exception as e:
                        st.error(f"Error cargando top períodos: {str(e)}")
                else:
                    # Mantener el Top 5 artículos global original
                    try:
                        # Obtener contexto de session_state
                        anios_ctx = st.session_state.get("anios_sel", [2024, 2025])
                        meses_ctx = st.session_state.get("meses_multi", [])
                        proveedores_ctx = st.session_state.get("comparativas_proveedores_multi", [])
                        
                        # ✅ FIX: Si hay meses, usar SOLO los años únicos de esos meses
                        if meses_ctx and len(meses_ctx) > 0:
                            # Extraer años únicos de los meses (ej: ["2024-11", "2025-11"] -> [2024, 2025])
                            anios_unicos = list(set([int(m.split('-')[0]) for m in meses_ctx if '-' in m]))
                            anios_ctx = anios_unicos if anios_unicos else anios_ctx
                        
                        # ✅ Pasar meses SOLO si hay selección explícita
                        meses_param = meses_ctx if meses_ctx and len(meses_ctx) > 0 else None
                        
                        # ✅ Pasar proveedores correctamente
                        proveedores_param = proveedores_ctx if proveedores_ctx and len(proveedores_ctx) > 0 else None
                        
                        # --- NORMALIZAR PROVEEDORES PARA TOP 5 ---
                        if proveedores_param:
                            if isinstance(proveedores_param, str):
                                proveedores_param = [proveedores_param]
                            elif not isinstance(proveedores_param, (list, tuple)):
                                proveedores_param = []
                        
                        print(f"🛠 DEBUG Top5: años={anios_ctx}, meses={meses_param}, provs={proveedores_param}")
                        
                        df_top5 = get_top_5_articulos(
                            anios=anios_ctx,
                            meses=meses_param,
                            proveedores=proveedores_param
                        )
                        
                        if df_top5 is None or df_top5.empty:
                            st.info("No hay datos para el período seleccionado")
                        else:
                            # Mostrar tabla con Moneda incluida
                            df_display = df_top5[['Articulo', 'Moneda', 'total']].copy()
                            df_display['total'] = df_display['total'].apply(
                                lambda x: f"${float(x):,.0f}".replace(",", ".")
                            )
                            df_display.columns = ['Artículo', 'Moneda', 'Total']
                            st.dataframe(df_display, use_container_width=True, hide_index=True, height=300)
                    except Exception as e:
                        st.error(f"Error Top 5: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())
            
            # Cerrar wrapper gráfico + top5
            st.markdown('</div>', unsafe_allow_html=True)
        
        else:
            st.info("⚠️ Se requieren al menos 2 períodos para generar el análisis comparativo.")
    
    with tabs[1]:
        # ✅ FIX: Usar col_moneda encontrada antes (case insensitive)
        if col_moneda:
            df['Moneda_norm'] = df[col_moneda].astype(str).str.strip().str.upper()
            df_pesos = df[df['Moneda_norm'].str.contains(r'^\$|UYU|PESO', regex=True, na=False) & 
                          ~df['Moneda_norm'].str.contains(r'U\$S|USD|U\$|US\$', regex=True, na=False)]
        else:
            df_pesos = df
        st.dataframe(df_pesos, use_container_width=True, height=400)
    
    with tabs[2]:
        # ✅ FIX: Usar col_moneda encontrada antes (case insensitive)
        if col_moneda:
            df['Moneda_norm'] = df[col_moneda].astype(str).str.strip().str.upper()
            df_usd = df[df['Moneda_norm'].str.contains(r'U\$S|USD|U\$|US\$', regex=True, na=False)]
        else:
            df_usd = pd.DataFrame()
        
        if not df_usd.empty:
            st.dataframe(df_usd, use_container_width=True, height=400)
        else:
            st.info("No hay datos en dólares")
    
    with tabs[3]:
        # Gráfico de barras por proveedor
        if 'Proveedor' in df.columns:
            try:
                import plotly.express as px
                fig = px.bar(
                    df.groupby('Proveedor').sum(numeric_only=True).reset_index(),
                    x='Proveedor',
                    y=df.select_dtypes(include='number').columns[0],
                    title="Distribución por Proveedor"
                )
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                st.info("Plotly no disponible")
            except Exception:
                st.info("No se pudo generar el gráfico")
    
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
        
        # ⬇️ TABLA COMPARATIVA ORIGINAL (NO TOCAR) - Solo si NO aplica CASO 2
        if not (
            proveedores_sel
            and len(proveedores_sel) == 1
            and len(periodos_validos) == 2
        ):
            st.dataframe(df, use_container_width=True, height=600)

# =========================
# ROUTER SQL (ahora incluye compras, comparativas y stock)
# =========================
def ejecutar_consulta_por_tipo(tipo: str, parametros: dict):

    _dbg_set_sql(
        tag=tipo,
        query=f"-- Ejecutando tipo: {tipo}\n-- (SQL real en sql_compras/sql_comparativas/sql_facturas)\n",
        params=parametros,
        df=None,
    )

    # ===== FACTURAS =====
    if tipo == "detalle_factura":
        df = sqlq_facturas.get_detalle_factura_por_numero(parametros["nro_factura"])
        _dbg_set_result(df)
        return df

    elif tipo == "facturas_proveedor":
        # ✅ Usa la función corregida de sql_facturas.py
        df = sqlq_facturas.get_facturas_proveedor(
            proveedores=parametros.get("proveedores", []),
            meses=parametros.get("meses"),
            anios=parametros.get("anios"),
            desde=parametros.get("desde"),
            hasta=parametros.get("hasta"),
            articulo=parametros.get("articulo"),
            moneda=parametros.get("moneda"),
            limite=parametros.get("limite", 5000),
        )
        _dbg_set_result(df)
        return df

    elif tipo == "ultima_factura":
        df = sqlq_facturas.get_ultima_factura_inteligente(parametros["patron"])
        _dbg_set_result(df)
        return df

    elif tipo == "resumen_facturas":
        df = sqlq_facturas.get_resumen_facturas_por_proveedor(
            meses=parametros.get("meses"),
            anios=parametros.get("anios"),
            moneda=parametros.get("moneda"),
        )
        _dbg_set_result(df)
        return df

    elif tipo == "facturas_rango_monto":
        df = sqlq_facturas.get_facturas_por_rango_monto(
            monto_min=parametros.get("monto_min", 0),
            monto_max=parametros.get("monto_max", 999999999),
            proveedores=parametros.get("proveedores"),
            meses=parametros.get("meses"),
            anios=parametros.get("anios"),
            moneda=parametros.get("moneda"),
            limite=parametros.get("limite", 100),
        )
        _dbg_set_result(df)
        return df

    # ===== COMPRAS =====
    elif tipo == "compras_anio":
        df = sqlq_compras.get_compras_anio(parametros["anio"])
        _dbg_set_result(df)
        return df

    elif tipo == "compras_mes":
        df = sqlq_compras.get_compras_por_mes_excel(parametros["mes"])
        _dbg_set_result(df)
        return df

    elif tipo == "compras_proveedor_mes":
        df = sqlq_compras.get_detalle_compras_proveedor_mes(parametros["proveedor"], parametros["mes"])
        _dbg_set_result(df)
        return df

    # AGREGADO: COMPRAS MÚLTIPLES
    elif tipo == "compras_multiples":
        df = sqlq_compras.get_compras_multiples(
            proveedores=parametros.get("proveedores", []),
            meses=parametros.get("meses", []),
            anios=parametros.get("anios", []),
            limite=parametros.get("limite", 5000)
        )
        _dbg_set_result(df)
        return df

    # ===== COMPARATIVAS =====
    elif tipo == "comparar_proveedor_meses":
        df = sqlq_comparativas.get_comparacion_proveedor_meses(
            parametros["proveedor"], parametros["mes1"], parametros["mes2"], parametros["label1"], parametros["label2"]
        )
        _dbg_set_result(df)
        return df

    elif tipo == "comparar_proveedor_anios":
        df = sqlq_comparativas.get_comparacion_proveedor_anios(
            parametros["proveedor"], parametros["anios"], parametros["label1"], parametros["label2"]
        )
        _dbg_set_result(df)
        return df

    elif tipo == "comparar_proveedores_meses":
        df = sqlq_comparativas.get_comparacion_proveedores_meses(
            parametros["proveedores"], parametros["mes1"], parametros["mes2"], parametros["label1"], parametros["label2"]
        )
        _dbg_set_result(df)
        return df

    elif tipo == "comparar_proveedores_anios":
        df = sqlq_comparativas.get_comparacion_proveedores_anios(
            parametros["proveedores"], parametros["anios"], parametros["label1"], parametros["label2"]
        )
        _dbg_set_result(df)
        return df

    # AGREGADO: Comparación multi proveedores multi meses
    elif tipo == "comparar_proveedores_meses_multi":
        df = sqlq_comparativas.get_comparacion_proveedores_meses_multi(
            proveedores=parametros.get("proveedores", []),
            meses=parametros.get("meses", []),
            articulos=parametros.get("articulos", [])  # Agregado articulos
        )
        _dbg_set_result(df)
        return df
        
    # ===== COMPARATIVAS MULTI (NUEVO - TODOS LOS PROVEEDORES) =====
    elif tipo == "comparar_proveedores_anios_multi":
        proveedores = parametros.get("proveedores", [])
        anios = parametros.get("anios", [])
        
        # Si proveedores está vacío, significa TODOS
        if not proveedores:
            proveedores = None
        
        print(f"🐛 DEBUG ejecutar_consulta: comparar_proveedores_anios_multi")
        print(f"   Proveedores: {proveedores or 'TODOS'}")
        print(f"   Años: {anios}")
        
        df = sqlq_comparativas.get_comparacion_proveedores_anios_multi(
            proveedores=proveedores,
            anios=anios
        )
        _dbg_set_result(df)
        return df

    # ===== STOCK =====
    elif tipo == "stock_total":
        df = sqlq_compras.get_stock_total()  # Ajusta si es otro módulo
        _dbg_set_result(df)
        return df

    elif tipo == "stock_articulo":
        df = sqlq_compras.get_stock_articulo(parametros["articulo"])  # Ajusta si es otro módulo
        _dbg_set_result(df)
        return df

    # ===== LISTADO FACTURAS AÑO =====
    elif tipo == "listado_facturas_anio":
        df = sqlq_compras.get_listado_facturas_por_anio(parametros["anio"])
        _dbg_set_result(df)
        return df

    # ===== TOTAL FACTURAS POR MONEDA AÑO =====
    elif tipo == "total_facturas_por_moneda_anio":
        df = sqlq_compras.get_total_facturas_por_moneda_anio(parametros["anio"])
        _dbg_set_result(df)
        return df

    # ===== TOTAL FACTURAS POR MONEDA GENÉRICO (TODOS LOS AÑOS) =====
    elif tipo == "total_facturas_por_moneda_generico":
        df = sqlq_facturas.get_total_facturas_por_moneda_todos_anios()
        _dbg_set_result(df)
        return df

    # ===== TOTAL COMPRAS POR MONEDA GENÉRICO (TODOS LOS AÑOS) =====
    elif tipo == "total_compras_por_moneda_generico":
        df = sqlq_compras.get_total_compras_por_moneda_todos_anios()
        _dbg_set_result(df)
        return df

    raise ValueError(f"Tipo '{tipo}' no implementado en ejecutar_consulta_por_tipo")


# =========================
# UI PRINCIPAL
# =========================
def Compras_IA():

    # =========================
    # DISEÑO MÁS COMPACTO Y VISIBLE
    # =========================
    st.markdown("""
    <style>
    /* ========================================
       HEADER MÁS COMPACTO
       ======================================== */
    .fc-header-modern,
    .dash-header {
        padding: 12px 16px !important;  /* Más pequeño */
        margin-bottom: 16px !important;
        border-radius: 10px !important;
    }
    
    .fc-title-modern,
    .dash-title {
        font-size: 1rem !important;  /* Más pequeño */
        margin-bottom: 4px !important;
        font-weight: 700 !important;
    }
    
    .fc-badge-modern,
    .dash-badge {
        font-size: 0.7rem !important;  /* Más pequeño */
        padding: 3px 8px !important;
        border-radius: 10px !important;
        margin-bottom: 4px !important;
    }
    
    .fc-meta-modern,
    .dash-meta {
        font-size: 0.7rem !important;  /* Más pequeño */
        margin: 0 !important;
        line-height: 1.2 !important;
    }
    
    /* ========================================
       TARJETAS MÉTRICAS MÁS CHICAS
       ======================================== */
    .fc-metrics-grid,
    .metrics-grid {
        gap: 16px !important;  /* Más pequeño para más tarjetas visibles */
        margin-bottom: 24px !important;
    }
    
    .fc-metric-card,
    .metric-card {
        padding: 12px 16px !important;  /* Más pequeño */
        border-radius: 10px !important;
    }
    
    .fc-metric-label,
    .metric-label {
        font-size: 0.75rem !important;  /* Más pequeño */
        margin-bottom: 4px !important;
    }
    
    .fc-metric-value,
    .metric-value {
        font-size: 1.2rem !important;  /* Más pequeño pero legible */
        font-weight: 700 !important;
    }
    
    .fc-metric-help {
        font-size: 0.65rem !important;  /* Más pequeño */
    }
    
    /* ========================================
       CARDS DE RESUMEN CON MISMO ALTO + MÁS ESPACIO
       ======================================== */
    
    /* Todas las cards de resumen con altura uniforme */
    .resumen-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 14px 18px !important;
        margin-bottom: 24px !important;  /* ← MÁS ESPACIO ENTRE CARDS (antes 12px) */
        min-height: 120px !important;  /* ← MÁS BAJA (antes 140px) */
        display: flex !important;
        flex-direction: column !important;
        box-sizing: border-box !important;
    }
    
    /* Título de la card */
    .resumen-title {
        font-size: 0.8rem !important;  /* Un poco más pequeño */
        font-weight: 700 !important;
        margin: 0 0 6px 0 !important;
        color: #374151;
    }
    
    /* Texto de la card */
    .resumen-text {
        font-size: 0.7rem !important;  /* Un poco más pequeño */
        color: #6b7280;
        margin: 0 !important;
        line-height: 1.3 !important;  /* Menos interlineado */
    }
    
    /* Badge para números en lista */
    .numero-badge {
        display: inline-block;
        background: #667eea;  /* Violeta */
        color: white;
        border-radius: 50%;
        padding: 1px 5px;
        font-size: 0.7rem;
        font-weight: bold;
        margin-right: 4px;
        width: 18px;
        height: 18px;
        text-align: center;
        line-height: 16px;
    }
    
    /* Provider card también con mismo alto */
    .provider-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 16px !important;
        margin-bottom: 24px !important;  /* ← MÁS ESPACIO */
        min-height: 120px !important;  /* ← MÁS BAJA */
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        display: flex !important;
        flex-direction: column !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px !important;  /* Más pequeño */
        margin-bottom: 16px !important;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-size: 0.8rem !important;  /* Más pequeño */
        padding: 5px 10px !important;
    }
    
    /* Total summary card */
    .total-summary-card {
        padding: 16px 14px !important;  /* Más pequeño */
        margin-bottom: 16px !important;
    }
    
    .total-summary-value {
        font-size: 1.6rem !important;  /* Más pequeño */
    }
    
    .total-summary-label {
        font-size: 0.85rem !important;
    }
    
    /* Provider card destacado */
    .single-provider-card {
        padding: 16px 14px !important;  /* Más pequeño */
        margin-bottom: 16px !important;
    }
    
    .single-provider-icon {
        width: 40px !important;  /* Más pequeño */
        height: 40px !important;
        font-size: 1.3rem !important;
    }
    
    .single-provider-name {
        font-size: 1rem !important;
    }
    
    /* Responsive - Mobile */
    @media (max-width: 768px) {
        .main .block-container {
            padding: 0.5rem 1rem !important;
        }
        
        .fc-metrics-grid,
        .metrics-grid {
            gap: 8px !important;
            grid-template-columns: repeat(2, 1fr) !important;
        }
        
        .fc-metric-value,
        .metric-value {
            font-size: 1rem !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    inicializar_historial()

    # ✅ INICIALIZAR FLAG PARA PAUSAR AUTOREFRESH
    if "pause_autorefresh" not in st.session_state:
        st.session_state["pause_autorefresh"] = False

    st.markdown("### 🤖 Asistente de Compras y Facturas")

    # Persistencia de selecciones en Comparativas
    if "prov_multi" not in st.session_state:
        st.session_state["prov_multi"] = []
    if "meses_multi" not in st.session_state:
        st.session_state["meses_multi"] = ["2024-11", "2025-11"]
    if "art_multi" not in st.session_state:
        st.session_state["art_multi"] = []

    # Fetch opciones dinámicas - TODOS sin límite
    prov_options = get_unique_proveedores()  # ✅ Sin límite
    print(f"🐛 Proveedores disponibles: {len(prov_options)}")  # Debug

    art_options = get_unique_articulos()  # ✅ CAMBIO: TODOS LOS ARTÍCULOS (sin [:100])

    # TABS PRINCIPALES: Chat IA + Comparativas
    tab_chat, tab_comparativas = st.tabs(["💬Compras", "📊 Comparativas"])

    with tab_chat:
        # BOTÓN LIMPIAR (solo en chat)
        if st.button("🗑️ Limpiar chat"):
            st.session_state["historial_compras"] = []
            _dbg_set_interpretacion({})
            _dbg_set_sql(None, "", [], None)
            st.session_state["pause_autorefresh"] = False  # ✅ REACTIVAR AUTOREFRESH
            st.rerun()

        # st.markdown("---")  # ← COMENTADA - ocupaba espacio al pedo

        # Mostrar historial
        for idx, msg in enumerate(st.session_state["historial_compras"]):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

                if "df" in msg and msg["df"] is not None:
                    df = msg["df"]

                    # Dashboard vendible compacto
                    try:
                        st.markdown("---")
                        render_dashboard_compras_vendible(
                            df,
                            titulo="Datos",
                            key_prefix=f"hist_{idx}_"
                        )
                    except Exception as e:
                        # Fallback viejo (no romper nada)
                        totales = calcular_totales_por_moneda(df)
                        if totales:
                            col1, col2, col3 = st.columns([2, 2, 3])

                            with col1:
                                pesos = totales.get("Pesos", 0)
                                pesos_str = (
                                    f"${pesos/1_000_000:,.2f}M"
                                    if pesos >= 1_000_000
                                    else f"${pesos:,.2f}"
                                )
                                st.metric(
                                    "💵 Total Pesos",
                                    pesos_str,
                                    help=f"Valor exacto: ${pesos:,.2f}",
                                )

                            with col2:
                                usd = totales.get("USD", 0)
                                usd_str = (
                                    f"${usd/1_000_000:,.2f}M"
                                    if usd >= 1_000_000
                                    else f"${usd:,.2f}"
                                )
                                st.metric(
                                    "💵 Total USD",
                                    usd_str,
                                    help=f"Valor exacto: ${usd:,.2f}",
                                )

                        st.markdown("---")
                        st.dataframe(df, use_container_width=True, height=400)
                        st.caption(f"⚠️ Dashboard vendible falló: {e}")

        # =========================
        # TIPS / EJEMPLOS (CAJA AMARILLA ANTES DEL INPUT)
        # =========================
        tips_html = """
        <div style="
            background: rgba(255, 243, 205, 0.85);
            border: 1px solid rgba(245, 158, 11, 0.30);
            border-left: 4px solid rgba(245, 158, 11, 0.75);
            border-radius: 12px;
            padding: 12px 16px;
            margin: 16px 0 12px 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        ">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                <span style="font-size: 18px;">💡</span>
                <span style="font-size: 14px; font-weight: 700; color: rgb(234, 88, 12);">Ejemplos de preguntas:</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px 20px; font-size: 12px; color: rgb(154, 52, 18);">
                <div>• Compras roche 2024</div>
                <div>• Facturas roche noviembre 2025</div>
                <div>• Compras roche, tresul 2024 2025</div>
                <div>• Detalle factura A00060907</div>
                <div>• Total facturas por moneda</div>
                <div>• Top proveedores 2025</div>
                <div>• Compras 2025</div>
                <div>• Compras vitek 2024</div>
                <div>• Comparar roche 2024 2025</div>
                <div>• Total compras octubre 2025</div>
            </div>
        </div>
        """
        st.markdown(tips_html, unsafe_allow_html=True)

    # Input
    pregunta = st.chat_input("Escribí tu consulta sobre compras o facturas...")

    if pregunta:
        # ✅ PAUSAR AUTOREFRESH AL HACER UNA PREGUNTA
        st.session_state["pause_autorefresh"] = True

        st_session_state = st.session_state  # Typo fix, but assuming it's st.session_state

        st.session_state["historial_compras"].append(
            {
                "role": "user",
                "content": pregunta,
                "timestamp": datetime.now().timestamp(),
            }
        )

        resultado = interpretar_pregunta(pregunta)
        _dbg_set_interpretacion(resultado)

        tipo = resultado.get("tipo", "")
        parametros = resultado.get("parametros", {})

        respuesta_content = ""
        respuesta_df = None

        if tipo == "conversacion":
            respuesta_content = responder_con_openai(pregunta, tipo="conversacion")

        elif tipo == "conocimiento":
            respuesta_content = responder_con_openai(pregunta, tipo="conocimiento")

        elif tipo == "no_entendido":
            respuesta_content = "🤔 No entendí bien tu pregunta."
            sugerencia = resultado.get("sugerencia", "")
            if sugerencia:
                respuesta_content += f"\n\n**Sugerencia:** {sugerencia}"

        else:
            try:
                resultado_sql = ejecutar_consulta_por_tipo(tipo, parametros)

                # Convertir "Mes" a nombres antes de mostrar
                if isinstance(resultado_sql, pd.DataFrame) and 'Mes' in resultado_sql.columns:
                    resultado_sql['Mes'] = resultado_sql['Mes'].apply(convertir_mes_a_nombre)

                if isinstance(resultado_sql, pd.DataFrame):
                    if len(resultado_sql) == 0:
                        respuesta_content = "⚠️ No se encontraron resultados"
                    else:
                        if tipo == "detalle_factura":
                            nro = parametros.get("nro_factura", "")
                            respuesta_content = f"✅ **Factura {nro}** - {len(resultado_sql)} artículos"
                        elif tipo.startswith("facturas_"):
                            respuesta_content = f"✅ Encontré **{len(resultado_sql)}** facturas"
                        elif tipo.startswith("compras_"):
                            respuesta_content = f"✅ Encontré **{len(resultado_sql)}** compras"
                        elif tipo.startswith("comparar_"):
                            respuesta_content = f"✅ Comparación lista - {len(resultado_sql)} filas"
                        elif tipo.startswith("stock_"):
                            respuesta_content = f"✅ Stock encontrado - {len(resultado_sql)} filas"
                        elif tipo == "listado_facturas_anio":
                            anio = parametros.get("anio", "")
                            respuesta_content = f"✅ **Listado de Facturas {anio}** - {len(resultado_sql)} proveedores"
                        elif tipo == "total_facturas_por_moneda_anio":
                            anio = parametros.get("anio", "")
                            respuesta_content = f"✅ **Totales de Facturas {anio} por Moneda** - {len(resultado_sql)} monedas"
                        elif tipo == "total_facturas_por_moneda_generico":
                            respuesta_content = f"✅ **Totales de Facturas por Moneda (Todos los años)** - {len(resultado_sql)} monedas"
                        elif tipo == "total_compras_por_moneda_generico":
                            respuesta_content = f"✅ **Totales de Compras por Moneda (Todos los años)** - {len(resultado_sql)} monedas"
                        else:
                            respuesta_content = f"✅ Encontré **{len(resultado_sql)}** resultados"

                        respuesta_df = resultado_sql
                else:
                    respuesta_content = str(resultado_sql)

            except Exception as e:
                _dbg_set_sql(
                    tipo,
                    f"-- Error ejecutando consulta_por_tipo: {str(e)}",
                    parametros,
                    None,
                )
                respuesta_content = f"❌ Error: {str(e)}"

        st.session_state["historial_compras"].append(
            {
                "role": "assistant",
                "content": respuesta_content,
                "df": respuesta_df,
                "tipo": tipo,
                "pregunta": pregunta,
            }
        )

        st.rerun()

    with tab_comparativas:
        st.markdown("### 📊 Menú Comparativas Fáciles")
        st.markdown("Selecciona opciones y compara proveedores/meses/años directamente (sin chat).")

        # Agregado: Submenús Compras y Comparativas
        tipo_consulta = st.selectbox("Tipo de consulta", options=["Compras", "Comparativas"], index=0, key="tipo_consulta")

        if tipo_consulta == "Compras":
            st.markdown("#### 🛒 Consultas de Compras")
            
            anio_compras = st.selectbox("Año", options=[2023, 2024, 2025, 2026], index=2, key="anio_compras")
            mes_compras = st.selectbox("Mes", options=month_names + ["Todos"], index=len(month_names), key="mes_compras")
            proveedor_compras = st.selectbox("Proveedor", options=["Todos"] + prov_options[:50], index=0, key="proveedor_compras")
            
            # ✅ MOSTRAR RESULTADO GUARDADO PARA COMPRAS
            if "compras_resultado" in st.session_state:
                df_guardado = st.session_state["compras_resultado"]
                titulo_guardado = st.session_state.get("compras_titulo", "Compras")
                
                render_dashboard_compras_vendible(df_guardado, titulo=titulo_guardado)
                
                # Botón para limpiar
                if st.button("🗑️ Limpiar resultados compras", key="btn_limpiar_compras"):
                    del st.session_state["compras_resultado"]
                    del st.session_state["compras_titulo"]
                    st.rerun()
            
            if st.button("🔍 Buscar Compras", key="btn_buscar_compras"):
                # ✅ PAUSAR AUTOREFRESH AL PRESIONAR BOTÓN DE BÚSQUEDA
                st.session_state["pause_autorefresh"] = True

                try:
                    if mes_compras == "Todos":
                        if proveedor_compras == "Todos":
                            df = sqlq_compras.get_compras_anio(anio_compras)
                        else:
                            df = sqlq_facturas.get_facturas_proveedor(proveedores=[proveedor_compras], anios=[anio_compras])
                    else:
                        mes_code = f"{anio_compras}-{month_num[mes_compras]}"
                        if proveedor_compras == "Todos":
                            df = sqlq_compras.get_compras_por_mes_excel(mes_code)
                        else:
                            df = sqlq_compras.get_detalle_compras_proveedor_mes(proveedor_compras, mes_code)
                    
                    if df is not None and not df.empty:
                        # ✅ GUARDAR EN SESSION_STATE PARA PERSISTIR
                        st.session_state["compras_resultado"] = df
                        st.session_state["compras_titulo"] = "Compras"
                        
                        render_dashboard_compras_vendible(df, titulo="Compras")
                    elif df is not None:
                        st.warning("⚠️ No se encontraron resultados para esa búsqueda.")
                except Exception as e:
                    st.error(f"❌ Error en búsqueda: {e}")

        elif tipo_consulta == "Comparativas":
            # ✅ PAUSAR AUTOREFRESH EN COMPARATIVAS
            st.session_state["pause_autorefresh"] = True

            st.markdown("#### 📊 Comparativas")
            
            # ✅ PROVEEDORES (ancho completo, sin columnas)
            proveedores_disponibles = prov_options  # Ya tiene todos los proveedores
            proveedores_sel = st.multiselect(
                "Proveedores",
                options=proveedores_disponibles,
                default=[],
                key="comparativas_proveedores_multi",
                help="Dejá vacío para comparar TODOS. Escribí para filtrar y seleccioná con Enter."
            )
            
            if proveedores_sel:
                proveedores = proveedores_sel
            else:
                proveedores = None
            
            meses_sel = st.multiselect("Meses", options=month_names, default=[], key="meses_sel")
            anios = st.multiselect("Años", options=[2023, 2024, 2025, 2026], default=[2024, 2025], key="anios_sel")
            # Generar combinaciones
            meses = []
            for a in anios:
                for m in meses_sel:
                    meses.append(f"{a}-{month_num[m]}")
            st.session_state["meses_multi"] = meses
            articulos = st.multiselect("Artículos", options=art_options, default=[x for x in st.session_state.get("art_multi", []) if x in art_options], key="art_multi")

            # Separar la barra del formulario
            st.markdown('<div style="margin-top: 20px; border-top: 1px solid #e5e7eb; padding-top: 16px;"></div>', unsafe_allow_html=True)

            # Barra de acciones en una sola fila horizontal - MODIFICADA
            col_cmp, col_clr, col_csv, col_xls = st.columns(4)  # Equal size for all buttons
            
            with col_cmp:
                btn_compare = st.button("🔍 Comparar", key="btn_comparar_horizontal", use_container_width=True)
            
            with col_clr:
                btn_clear = st.button("🗑️ Limpiar resultados", key="btn_limpiar_horizontal", use_container_width=True)
            
            with col_csv:
                btn_csv = st.button("📊 CSV", key="btn_csv_horizontal", use_container_width=True)
            
            with col_xls:
                btn_excel = st.button("📥 Excel", key="btn_excel_horizontal", use_container_width=True)

            # CSS adicional para ajustar botones
            st.markdown("""
            <style>
            /* Barra de acciones compacta */
            .action-bar {
                flex-wrap: nowrap !important;
                height: 48px !important;  /* Altura máxima de la barra */
                gap: 8px !important;  /* Separación uniforme */
            }
            
            /* Botones compactos */
            .stButton button {
                height: 36px !important;  /* Altura objetivo */
                padding: 6px 12px !important;  /* Padding vertical y horizontal reducido */
                font-size: 0.85rem !important;  /* Tamaño de fuente */
                white-space: nowrap !important;  /* Texto en una línea */
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                border-radius: 6px !important;
            }
            
            /* Íconos más pequeños */
            .stButton button span {
                font-size: 14px !important;  /* Tamaño de íconos reducido */
            }
            
            /* Botón primario "Comparar" menos prominente */
            .stButton button[data-testid*="btn_comparar_horizontal"] {
                font-weight: 600 !important;  /* Menos bold */
                padding: 6px 14px !important;  /* Un poco más padding horizontal pero no vertical */
            }
            
            /* Asegurar que todos los botones tengan el mismo ancho si es necesario */
            .stButton {
                flex: 1 !important;
            }
            </style>
            """, unsafe_allow_html=True)

            # Botón comparar (oculto, pero funcionalidad en el botón de arriba)
            if btn_compare:
                # ✅ VALIDAR: necesitamos al menos 2 períodos (años O meses)
                tiene_anios = len(anios) >= 2
                tiene_meses = len(meses) >= 2
                
                if not tiene_anios and not tiene_meses:
                    st.error("Seleccioná al menos 2 años O al menos 2 combinaciones de mes-año para comparar")
                else:
                    # ✅ PAUSAR AUTOREFRESH
                    st.session_state["comparativa_activa"] = True
                    
                    with st.spinner("Comparando..."):
                        try:
                            # ✅ PASAR TODOS LOS PARÁMETROS RELEVANTES
                            df = sqlq_comparativas.comparar_compras(
                                anios=anios if not meses else None,  # Si hay meses, no usar años
                                meses=meses if meses else None,       # Pasar meses si hay
                                proveedores=proveedores,
                                articulos=articulos if articulos else None  # Pasar artículos si hay
                            )
                            
                            if df is not None and not df.empty:
                                # ✅ CONSTRUIR TÍTULO CON ENTIDAD CORRECTA
                                if articulos:
                                    entidad_titulo = 'Artículos'
                                    todos_entidad_titulo = "Todos los artículos"
                                else:
                                    entidad_titulo = 'Proveedores'
                                    todos_entidad_titulo = "Todos los proveedores"
                                
                                titulo_provs = ""
                                if proveedores_sel:
                                    if len(proveedores_sel) == 1:
                                        # Un solo proveedor: mostrar nombre completo
                                        titulo_provs = f"{proveedores_sel[0]} - "
                                    elif len(proveedores_sel) <= 3:
                                        # 2-3 proveedores: mostrar todos
                                        titulo_provs = f"{', '.join(proveedores_sel)} - "
                                    else:
                                        # Más de 3: mostrar cantidad
                                        titulo_provs = f"{len(proveedores_sel)} proveedores - "
                                else:
                                    titulo_provs = f"{todos_entidad_titulo} - "
                                
                                # ✅ GUARDAR EN SESSION_STATE
                                st.session_state["comparativa_resultado"] = df
                                st.session_state["comparativa_titulo"] = f"{titulo_provs}Comparación {' vs '.join(map(str, anios))}"
                                st.session_state["comparativa_activa"] = True
                                
                                st.success(f"✅ Comparación lista - {len(df)} filas")
                            else:
                                st.warning("No se encontraron datos")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
                            st.exception(e)
            
            # ✅ MOSTRAR RESULTADO GUARDADO (persiste entre refreshes)
            if "comparativa_resultado" in st.session_state:
                df_guardado = st.session_state["comparativa_resultado"]
                titulo_guardado = st.session_state.get("comparativa_titulo", "Comparación")
                
                # Botón para limpiar (oculto, funcionalidad en botón de arriba)
                if btn_clear:
                    del st.session_state["comparativa_resultado"]
                    del st.session_state["comparativa_titulo"]
                    st.session_state["comparativa_activa"] = False  # Reactivar auto-refresh
                    st.rerun()
                
                # Mostrar dashboard con datos guardados
                render_dashboard_comparativas_moderno(
                    df_guardado,
                    titulo=titulo_guardado
                )

        # Botón para reanudar auto-refresh (opcional, si se pausa)
        if st.session_state.get("pause_autorefresh", False):
            st.markdown("---")
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("▶️ Reanudar auto-refresh", help="Reactivar auto-refresh automático"):
                    st.session_state["pause_autorefresh"] = False
                    st.rerun()

    # ✅ AUTOREFRESH CONDICIONAL: SOLO SI NO ESTÁ PAUSADO
    if not st.session_state.get("pause_autorefresh", False):
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=5000, key="fc_keepalive")
        except Exception:
            pass
