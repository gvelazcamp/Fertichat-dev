# =========================
# UI_COMPRAS.PY - CON TOTALES Y PESTAÑAS
# =========================

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import re
import difflib
import unicodedata
from typing import Optional, Dict, List, Tuple

import ia_compras as iaq_compras

# IMPORTS
from ia_router import interpretar_pregunta, obtener_info_tipo  # obtener_info_tipo queda por compat
from utils_openai import responder_con_openai

# IMPORTS DE SQL
import sql_compras as sqlq_compras
import sql_comparativas as sqlq_comparativas


# =========================
# DEBUG HELPERS (NO ROMPEN NADA)
# =========================
def _dbg_set_interpretacion(obj: dict):
    try:
        st.session_state["DBG_INT_LAST"] = obj or {}
    except Exception:
        pass


def _dbg_set_sql(tag: Optional[str], query: str, params, df: Optional[pd.DataFrame] = None):
    """
    Guarda info para el panel:
    - DBG_SQL_LAST_TAG
    - DBG_SQL_LAST_QUERY
    - DBG_SQL_LAST_PARAMS
    - DBG_SQL_ROWS
    - DBG_SQL_COLS
    """
    try:
        st.session_state["DBG_SQL_LAST_TAG"] = tag
        st.session_state["DBG_SQL_LAST_QUERY"] = query or ""
        st.session_state["DBG_SQL_LAST_PARAMS"] = params if params is not None else []
        if isinstance(df, pd.DataFrame):
            st.session_state["DBG_SQL_ROWS"] = int(len(df))
            st.session_state["DBG_SQL_COLS"] = list(df.columns)
        else:
            # no sabemos filas/cols
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
# INICIALIZAR HISTORIAL
# =========================
def inicializar_historial():
    if "historial_compras" not in st.session_state:
        st.session_state["historial_compras"] = []


# =========================
# SUGERENCIAS (SI/NO) - CORRECCIÓN RÁPIDA DE PROVEEDORES
# =========================

MESES_NOMBRE = {
    "01": "enero",
    "02": "febrero",
    "03": "marzo",
    "04": "abril",
    "05": "mayo",
    "06": "junio",
    "07": "julio",
    "08": "agosto",
    "09": "septiembre",
    "10": "octubre",
    "11": "noviembre",
    "12": "diciembre",
}

_STOPWORDS_PROV = {
    "compras", "compra", "comparar", "compara", "comparame", "comparame", "mes", "año", "anio",
    "del", "de", "la", "el", "y", "e", "en", "para", "por", "entre", "vs", "versus",
    "laboratorio", "lab", "s", "sa", "srl", "ltda", "lt", "inc", "ltd", "uruguay", "uy",
}

_MESES_TOKENS = {
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "setiembre",
    "octubre", "noviembre", "diciembre"
}


def _strip_accents_local(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s or "")
        if unicodedata.category(c) != "Mn"
    )


def _key_local(s: str) -> str:
    s = _strip_accents_local((s or "").lower().strip())
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _tiene_sep_multi_prov(texto: str) -> bool:
    t = (texto or "").lower()
    return ("," in t) or (" y " in t) or (" e " in t)


def _mes_yyyymm_a_nombre(mes_yyyymm: str) -> str:
    # "2025-11" -> "noviembre 2025"
    try:
        y, m = mes_yyyymm.split("-")
        return f"{MESES_NOMBRE.get(m.zfill(2), mes_yyyymm)} {y}"
    except Exception:
        return mes_yyyymm


def _anio_str_list(anios: List[int]) -> str:
    return " ".join([str(a) for a in anios if a])


def _extraer_anios_texto(texto: str) -> List[int]:
    out: List[int] = []
    for m in re.findall(r"\b(20\d{2})\b", (texto or "")):
        try:
            out.append(int(m))
        except Exception:
            continue
    # únicos preservando orden
    seen = set()
    uniq: List[int] = []
    for a in out:
        if a not in seen:
            uniq.append(a)
            seen.add(a)
    return uniq


def _short_from_proveedor(orig: str) -> str:
    # intenta devolver un "alias corto" útil (evita "laboratorio", "sa", etc.)
    tokens = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]+", (orig or "").lower())
    clean: List[str] = []
    for t in tokens:
        k = _key_local(t)
        if len(k) < 4:
            continue
        if k in _STOPWORDS_PROV:
            continue
        if k in _MESES_TOKENS:
            continue
        clean.append(t)
    if not clean:
        # fallback: primera palabra no vacía
        for t in tokens:
            if t.strip():
                return t.strip()
        return orig.strip()
    # prioriza la palabra más larga (suele ser el "nombre real")
    clean.sort(key=lambda x: len(_key_local(x)), reverse=True)
    return clean[0].strip()


@st.cache_data(ttl=60 * 60)
def _catalogo_proveedores_cache() -> Dict[str, object]:
    listas = iaq_compras._cargar_listas_supabase()
    proveedores_full: List[str] = [p for p in (listas.get("proveedores") or []) if p]

    full_keys: List[str] = [_key_local(p) for p in proveedores_full]

    # mapping short_key -> short_text (si hay colisiones, dejamos el primero)
    short_key_to_short: Dict[str, str] = {}
    short_keys: List[str] = []

    for p in proveedores_full:
        short = _short_from_proveedor(p)
        sk = _key_local(short)
        if len(sk) < 4:
            continue
        if sk not in short_key_to_short:
            short_key_to_short[sk] = short
            short_keys.append(sk)

    return {
        "proveedores_full": proveedores_full,
        "full_keys": full_keys,
        "short_keys": short_keys,
        "short_key_to_short": short_key_to_short,
    }


def _proveedor_parece_valido(prov_input: str) -> bool:
    pkey = _key_local(prov_input or "")
    if len(pkey) < 4:
        return False
    cat = _catalogo_proveedores_cache()
    full_keys: List[str] = cat["full_keys"]  # type: ignore
    # si el input aparece como substring en algún proveedor real, lo consideramos válido (ej: "roche")
    for fk in full_keys:
        if pkey and pkey in fk:
            return True
    return False


def _match_proveedor_cercano(prov_input: str, cutoff: float = 0.72) -> Optional[str]:
    pkey = _key_local(prov_input or "")
    if len(pkey) < 4:
        return None

    cat = _catalogo_proveedores_cache()
    short_keys: List[str] = cat["short_keys"]  # type: ignore
    short_key_to_short: Dict[str, str] = cat["short_key_to_short"]  # type: ignore

    matches = difflib.get_close_matches(pkey, short_keys, n=1, cutoff=cutoff)
    if not matches:
        return None
    return short_key_to_short.get(matches[0])


def _infer_proveedores_desde_texto(texto: str, max_items: int = 3) -> List[str]:
    # busca "palabras" que parezcan proveedores, incluso con typos
    raw = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ]{3,}", (texto or "").lower())
    candidatos: List[str] = []
    for w in raw:
        kw = _key_local(w)
        if len(kw) < 4:
            continue
        if kw in _STOPWORDS_PROV or kw in _MESES_TOKENS:
            continue
        # intenta match cercano
        m = _match_proveedor_cercano(w, cutoff=0.75)
        if m:
            mk = _key_local(m)
            if mk not in [_key_local(x) for x in candidatos]:
                candidatos.append(m)
        if len(candidatos) >= max_items:
            break
    return candidatos


def _extraer_sugerencia_simple(sugerencia: str) -> Optional[str]:
    # toma la primera opción tipo "Probá: ... | ... | ..."
    if not sugerencia:
        return None
    s = sugerencia.strip()
    # si viene "Probá:" o "Sugerencia:" etc, recorta
    s = re.sub(r"^(probá|proba|sugerencia|tip)\s*:\s*", "", s, flags=re.IGNORECASE).strip()
    # primer segmento antes de "|"
    if "|" in s:
        s = s.split("|", 1)[0].strip()
    # limpieza final
    return s if s else None


def _generar_sugerencia_ejecutable(pregunta: str, tipo: str, parametros: Dict) -> Optional[Dict[str, str]]:
    # 1) Si falta separador multi-proveedor (ej: "roche biodiagnostico 2024 2025"), sugerimos con coma.
    if ("compar" in (pregunta or "").lower()) and ("compra" in (pregunta or "").lower()):
        if not _tiene_sep_multi_prov(pregunta):
            provs_inferidos = _infer_proveedores_desde_texto(pregunta, max_items=3)
            anios = parametros.get("anios") or _extraer_anios_texto(pregunta)
            if len(provs_inferidos) >= 2 and len(anios) >= 2:
                sugerida = f"comparar compras {provs_inferidos[0]}, {provs_inferidos[1]} {_anio_str_list(anios[:2])}"
                return {"pregunta": sugerida, "motivo": "Faltaba separador entre proveedores (usar coma o 'y')."}

    # 2) Corrección de proveedor en consultas proveedor/mes/año y comparativas
    proveedores: List[str] = []

    if isinstance(parametros.get("proveedores"), list) and parametros.get("proveedores"):
        proveedores = [str(x) for x in parametros.get("proveedores") if x]
    elif parametros.get("proveedor"):
        proveedores = [str(parametros.get("proveedor"))]

    if not proveedores:
        return None

    # si todos parecen válidos, no sugerimos
    if all(_proveedor_parece_valido(p) for p in proveedores):
        return None

    # intentamos corregir el primero inválido
    for p in proveedores:
        if _proveedor_parece_valido(p):
            continue
        m = _match_proveedor_cercano(p, cutoff=0.72)
        if not m:
            continue

        # reconstrucción mínima de la pregunta sugerida (sin tocar tu lógica, solo propone texto)
        p_sug = m

        # compras proveedor mes
        if tipo == "compras_proveedor_mes" and parametros.get("mes"):
            mes_str = _mes_yyyymm_a_nombre(str(parametros.get("mes")))
            return {
                "pregunta": f"compras {p_sug} {mes_str}",
                "motivo": f"Proveedor no reconocido: '{p}' → '{p_sug}'."
            }

        # compras proveedor año
        if tipo == "compras_proveedor_anio" and parametros.get("anio"):
            return {
                "pregunta": f"compras {p_sug} {int(parametros.get('anio'))}",
                "motivo": f"Proveedor no reconocido: '{p}' → '{p_sug}'."
            }

        # comparar proveedor años (single)
        if tipo == "comparar_proveedor_anios" and parametros.get("anios"):
            anios = parametros.get("anios") or []
            return {
                "pregunta": f"comparar compras {p_sug} {_anio_str_list(anios)}",
                "motivo": f"Proveedor no reconocido: '{p}' → '{p_sug}'."
            }

        # comparar proveedor meses (single)
        if tipo == "comparar_proveedor_meses" and parametros.get("mes1") and parametros.get("mes2"):
            mes1 = _mes_yyyymm_a_nombre(str(parametros.get("mes1")))
            mes2 = _mes_yyyymm_a_nombre(str(parametros.get("mes2")))
            return {
                "pregunta": f"comparar compras {p_sug} {mes1} {mes2}",
                "motivo": f"Proveedor no reconocido: '{p}' → '{p_sug}'."
            }

        # multi proveedores años
        if tipo in ("comparar_proveedores_anios", "comparar_proveedores_anios_multi") and parametros.get("anios"):
            anios = parametros.get("anios") or []
            # reemplaza el inválido por el sugerido
            provs_corr = []
            for pp in proveedores:
                if _proveedor_parece_valido(pp):
                    provs_corr.append(pp)
                else:
                    provs_corr.append(p_sug)
            sugerida = f"comparar compras {', '.join(provs_corr)} {_anio_str_list(anios)}"
            return {"pregunta": sugerida, "motivo": f"Corrigiendo proveedor: '{p}' → '{p_sug}'."}

        # multi proveedores meses
        if tipo in ("comparar_proveedores_meses", "comparar_proveedores_meses_multi"):
            meses = parametros.get("meses") or []
            if not meses:
                m1 = parametros.get("mes1")
                m2 = parametros.get("mes2")
                if m1 and m2:
                    meses = [m1, m2]
            meses_txt = " ".join([_mes_yyyymm_a_nombre(str(x)) for x in (meses or [])])
            if meses_txt:
                provs_corr = []
                for pp in proveedores:
                    if _proveedor_parece_valido(pp):
                        provs_corr.append(pp)
                    else:
                        provs_corr.append(p_sug)
                sugerida = f"comparar compras {', '.join(provs_corr)} {meses_txt}"
                return {"pregunta": sugerida, "motivo": f"Corrigiendo proveedor: '{p}' → '{p_sug}'."}

        # fallback genérico
        return {"pregunta": f"compras {p_sug}", "motivo": f"Proveedor no reconocido: '{p}' → '{p_sug}'."}

    return None


# =========================
# CALCULAR TOTALES POR MONEDA
# =========================
def calcular_totales_por_moneda(df: pd.DataFrame) -> dict:
    """
    Calcula totales separados por moneda si la columna 'Moneda' existe
    """
    if df is None or len(df) == 0:
        return {"Pesos": 0, "USD": 0}

    # Verificar si existe columna de moneda
    col_moneda = None
    for col in df.columns:
        if col.lower() in ["moneda", "currency"]:
            col_moneda = col
            break

    # Verificar si existe columna de total
    col_total = None
    for col in df.columns:
        if col.lower() in ["total", "monto", "importe", "valor"]:
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

        totales = {}

        pesos_df = df_calc[df_calc[col_moneda].astype(str).str.contains(r"\$|peso|ARS|ars", case=False, na=False)]
        totales["Pesos"] = pesos_df[col_total].sum()

        usd_df = df_calc[df_calc[col_moneda].astype(str).str.contains(r"USD|US|dolar|dólar", case=False, na=False)]
        totales["USD"] = usd_df[col_total].sum()

        return totales

    except Exception as e:
        print(f"Error calculando totales: {e}")
        return None
# =========================
# GENERAR EXPLICACIÓN
# =========================
def generar_explicacion_ia(df: pd.DataFrame, pregunta: str, tipo: str) -> str:
    """
    Genera una explicación natural y completa de los resultados
    """
    try:
        if df is None or len(df) == 0:
            return "No se encontraron datos para esta consulta."

        explicacion = []

        explicacion.append("### 📊 Análisis de la consulta\n")
        explicacion.append(f"Se encontraron **{len(df)} registros** que coinciden con tu búsqueda.\n")

        totales = calcular_totales_por_moneda(df)
        if totales:
            explicacion.append("#### 💰 Totales\n")

            pesos = totales.get("Pesos", 0)
            usd = totales.get("USD", 0)

            if pesos > 0 and usd > 0:
                explicacion.append(f"El gasto total fue de **${pesos:,.2f} pesos** y **${usd:,.2f} dólares**.\n")
            elif pesos > 0:
                explicacion.append(f"El gasto total fue de **${pesos:,.2f} pesos**.\n")
            elif usd > 0:
                explicacion.append(f"El gasto total fue de **${usd:,.2f} dólares**.\n")

        # Detectar columna proveedor/articulo (case-insensitive)
        col_prov = None
        col_art = None
        for c in df.columns:
            if c.lower() == "proveedor":
                col_prov = c
            if c.lower() == "articulo":
                col_art = c

        # Top proveedores (si existe columna proveedor)
        if col_prov:
            top_proveedores = df.groupby(col_prov).size().sort_values(ascending=False).head(3)

            explicacion.append("\n#### 🏢 Proveedores principales\n")
            explicacion.append("Los proveedores con más movimientos fueron:\n")

            # Detectar columna total si existe
            col_total = None
            for c in df.columns:
                if c.lower() in ["total", "monto", "importe", "valor"]:
                    col_total = c
                    break

            for i, (prov, cant) in enumerate(top_proveedores.items(), 1):
                if col_total:
                    df_prov = df[df[col_prov] == prov].copy()
                    df_prov[col_total] = (
                        df_prov[col_total]
                        .astype(str)
                        .str.replace(".", "", regex=False)
                        .str.replace(",", ".", regex=False)
                        .str.replace("$", "", regex=False)
                        .str.strip()
                    )
                    df_prov[col_total] = pd.to_numeric(df_prov[col_total], errors="coerce").fillna(0)
                    total_prov = df_prov[col_total].sum()
                    explicacion.append(f"{i}. **{prov}**: {cant} registros por un total de ${total_prov:,.2f}\n")
                else:
                    explicacion.append(f"{i}. **{prov}**: {cant} registros\n")

        # Top artículos
        elif col_art:
            top_articulos = df.groupby(col_art).size().sort_values(ascending=False).head(3)

            explicacion.append("\n#### 📦 Artículos principales\n")
            explicacion.append("Los artículos más comprados fueron:\n")

            for i, (art, cant) in enumerate(top_articulos.items(), 1):
                explicacion.append(f"{i}. **{art}**: {cant} registros\n")

        # Rango de fechas
        if "Fecha" in df.columns or "fecha" in df.columns:
            col_fecha = "Fecha" if "Fecha" in df.columns else "fecha"
            df_temp = df.copy()
            df_temp[col_fecha] = pd.to_datetime(df_temp[col_fecha], errors="coerce")
            df_temp = df_temp.dropna(subset=[col_fecha])

            if len(df_temp) > 0:
                fecha_min = df_temp[col_fecha].min()
                fecha_max = df_temp[col_fecha].max()
                explicacion.append("\n#### 📅 Período\n")
                explicacion.append(
                    f"Los datos abarcan desde **{fecha_min.strftime('%d/%m/%Y')}** hasta **{fecha_max.strftime('%d/%m/%Y')}**.\n"
                )

        explicacion.append("\n---\n")
        explicacion.append("💡 *Tip: Podés descargar estos datos en Excel usando el botón en la pestaña 'Tabla'.*")

        return "".join(explicacion)

    except Exception as e:
        print(f"Error generando explicación: {e}")
        return f"Se encontraron {len(df)} resultados. Los datos están disponibles en la pestaña 'Tabla'."


# =========================
# GENERAR GRÁFICO
# =========================
def generar_grafico(df: pd.DataFrame, tipo: str):
    """
    Genera un gráfico según el tipo de consulta
    """
    try:
        if df is None or len(df) == 0:
            return None

        df_clean = df.copy()

        col_total = None
        for col in df_clean.columns:
            if col.lower() in ["total", "monto", "importe", "valor"]:
                col_total = col
                break

        if col_total:
            df_clean[col_total] = (
                df_clean[col_total]
                .astype(str)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
                .str.replace("$", "", regex=False)
                .str.strip()
            )
            df_clean[col_total] = pd.to_numeric(df_clean[col_total], errors="coerce").fillna(0)

        # Detectar columnas proveedor/articulo (case-insensitive)
        col_prov = None
        col_art = None
        for c in df_clean.columns:
            if c.lower() == "proveedor":
                col_prov = c
            if c.lower() == "articulo":
                col_art = c

        # Top 10 proveedores por total
        if col_prov and col_total:
            df_grouped = df_clean.groupby(col_prov)[col_total].sum().sort_values(ascending=False).head(10)

            fig = px.bar(
                x=df_grouped.values,
                y=df_grouped.index,
                orientation="h",
                title="Top 10 Proveedores por Total",
                labels={"x": "Total ($)", "y": "Proveedor"},
                text=df_grouped.values,
            )

            fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
            fig.update_layout(
                height=500,
                xaxis_title="Total",
                yaxis_title="Proveedor",
                showlegend=False,
                xaxis={"tickformat": "$,.0f"},
            )
            return fig

        # Top 10 artículos por total
        if col_art and col_total:
            df_grouped = df_clean.groupby(col_art)[col_total].sum().sort_values(ascending=False).head(10)

            fig = px.bar(
                x=df_grouped.values,
                y=df_grouped.index,
                orientation="h",
                title="Top 10 Artículos por Total",
                labels={"x": "Total ($)", "y": "Artículo"},
                text=df_grouped.values,
            )

            fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
            fig.update_layout(
                height=500,
                xaxis_title="Total",
                yaxis_title="Artículo",
                showlegend=False,
                xaxis={"tickformat": "$,.0f"},
            )
            return fig

        # Línea temporal si hay fecha
        if "Fecha" in df_clean.columns or "fecha" in df_clean.columns:
            col_fecha = "Fecha" if "Fecha" in df_clean.columns else "fecha"
            df_temp = df_clean.copy()
            df_temp[col_fecha] = pd.to_datetime(df_temp[col_fecha], errors="coerce")
            df_temp = df_temp.dropna(subset=[col_fecha])

            if len(df_temp) > 0:
                df_grouped = df_temp.groupby(df_temp[col_fecha].dt.to_period("M")).size()
                fig = px.line(
                    x=[str(p) for p in df_grouped.index],
                    y=df_grouped.values,
                    title="Cantidad de Registros por Mes",
                    labels={"x": "Mes", "y": "Cantidad"},
                    markers=True,
                )
                fig.update_layout(height=400)
                return fig

        return None

    except Exception as e:
        print(f"Error generando gráfico: {e}")
        return None


# =========================
# ROUTER SQL
# =========================
def ejecutar_consulta_por_tipo(tipo: str, parametros: dict):

    # Debug base: deja de estar vacío aunque la query viva en sql_compras/sql_comparativas
    _dbg_set_sql(
        tag=tipo,
        query=f"-- Ejecutando tipo: {tipo}\n-- (SQL real se arma dentro de sql_compras/sql_comparativas)\n",
        params=parametros,
        df=None
    )

    if tipo == "compras_anio":
        df = sqlq_compras.get_compras_anio(parametros["anio"])
        _dbg_set_result(df)
        return df

    elif tipo == "compras_proveedor_mes":
        df = sqlq_compras.get_detalle_compras_proveedor_mes(parametros["proveedor"], parametros["mes"])
        _dbg_set_result(df)
        return df

    elif tipo == "compras_proveedor_anio":
        df = sqlq_compras.get_detalle_compras_proveedor_anio(parametros["proveedor"], parametros["anio"])
        _dbg_set_result(df)
        return df

    elif tipo == "compras_articulo_mes":
        df = sqlq_compras.get_detalle_compras_articulo_mes(parametros["articulo"], parametros["mes"])
        _dbg_set_result(df)
        return df

    elif tipo == "compras_articulo_anio":
        df = sqlq_compras.get_detalle_compras_articulo_anio(parametros["articulo"], parametros["anio"])
        _dbg_set_result(df)
        return df

    elif tipo == "compras_mes":
        df = sqlq_compras.get_compras_por_mes_excel(parametros["mes"])
        _dbg_set_result(df)
        return df

    elif tipo == "ultima_factura":
        df = sqlq_compras.get_ultima_factura_inteligente(parametros["patron"])
        _dbg_set_result(df)
        return df

    elif tipo == "facturas_articulo":
        df = sqlq_compras.get_facturas_de_articulo(parametros["articulo"])
        _dbg_set_result(df)
        return df

    # =========================
    # FACTURAS
    # =========================
    elif tipo in ("detalle_factura", "detalle_factura_numero"):
        df = sqlq_compras.get_detalle_factura_por_numero(parametros["nro_factura"])
        _dbg_set_result(df)
        return df

    # =========================
    # ✅ FIX: FACTURAS POR PROVEEDOR (NUEVO SOPORTE)
    # =========================
    elif tipo in (
        "facturas_proveedor",
        "facturas_por_proveedor",
        "todas_facturas_proveedor",
        "todas_las_facturas_proveedor",
        "facturas_proveedor_anio",
        "facturas_proveedor_mes",
    ):
        proveedores = parametros.get("proveedores", [])
        if (not proveedores) and parametros.get("proveedor"):
            proveedores = [parametros.get("proveedor")]

        # soportar mes singular -> meses
        meses = parametros.get("meses")
        if not meses and parametros.get("mes"):
            meses = [parametros.get("mes")]

        # soportar anio singular -> anios
        anios = parametros.get("anios")
        if not anios and parametros.get("anio"):
            try:
                anios = [int(parametros.get("anio"))]
            except Exception:
                anios = parametros.get("anios")

        df = sqlq_compras.get_facturas_proveedor_detalle(
            proveedores=proveedores or [],
            meses=meses,
            anios=anios,
            desde=parametros.get("desde"),
            hasta=parametros.get("hasta"),
            articulo=parametros.get("articulo"),
            moneda=parametros.get("moneda"),
            limite=parametros.get("limite", 5000),
        )
        _dbg_set_result(df)
        return df

    # =========================
    # COMPARATIVAS
    # =========================
    elif tipo == "comparar_proveedor_meses":
        proveedor = parametros.get("proveedor")
        mes1 = parametros.get("mes1")
        mes2 = parametros.get("mes2")
        label1 = parametros.get("label1", mes1)
        label2 = parametros.get("label2", mes2)

        df = sqlq_comparativas.get_comparacion_proveedor_meses(
            proveedor,
            mes1,
            mes2,
            label1,
            label2,
        )
        _dbg_set_result(df)
        return df

    elif tipo == "comparar_proveedor_anios":
        proveedor = parametros.get("proveedor")
        anios = parametros.get("anios", [])
        df = sqlq_comparativas.get_comparacion_proveedor_anios_like(proveedor, anios)
        _dbg_set_result(df)
        return df

    elif tipo == "comparar_articulo_anios":
        df = sqlq_comparativas.get_comparacion_articulo_anios(
            parametros["anios"],
            parametros["articulo"]
        )
        _dbg_set_result(df)
        return df

    elif tipo == "comparar_familia_anios":
        df = sqlq_comparativas.get_comparacion_familia_anios_monedas(
            parametros["anios"]
        )
        _dbg_set_result(df)
        return df

    # =========================
    # TODAS LAS FACTURAS DE PROVEEDOR (DETALLE) - COMPAT VIEJA
    # =========================
    elif tipo in (
        "compras_Todas las facturas de un Proveedor",
        "compras_Todoas las facturas de un Proveedor_________",  # compat typo viejo
    ):
        proveedores = parametros.get("proveedores", [])
        if (not proveedores) and parametros.get("proveedor"):
            proveedores = [parametros.get("proveedor")]

        df = sqlq_compras.get_facturas_proveedor_detalle(
            proveedores=proveedores or [],
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

    # =========================
    # COMPARATIVAS (MULTI-PROVEEDOR) - FIX + COMPAT
    # =========================
    elif tipo in ("comparar_proveedores_meses", "comparar_proveedores_meses_multi"):
        proveedores = parametros.get("proveedores", [])
        if (not proveedores) and parametros.get("proveedor"):
            proveedores = [parametros.get("proveedor")]

        meses = parametros.get("meses")
        if not meses:
            mes1 = parametros.get("mes1")
            mes2 = parametros.get("mes2")
            if mes1 and mes2:
                meses = [mes1, mes2]
            elif mes1:
                meses = [mes1]

        df = sqlq_comparativas.get_comparacion_proveedores_meses_multi(
            proveedores,
            meses or []
        )
        _dbg_set_result(df)
        return df

    elif tipo in ("comparar_proveedores_anios", "comparar_proveedores_anios_multi"):
        proveedores = parametros.get("proveedores", [])
        if (not proveedores) and parametros.get("proveedor"):
            proveedores = [parametros.get("proveedor")]

        anios = parametros.get("anios", [])
        df = sqlq_comparativas.get_comparacion_proveedores_anios_multi(
            proveedores,
            anios
        )
        _dbg_set_result(df)
        return df

    # =========================
    # GASTOS
    # =========================
    elif tipo == "gastos_familias_mes":
        df = sqlq_compras.get_gastos_todas_familias_mes(parametros["mes"])
        _dbg_set_result(df)
        return df

    elif tipo == "gastos_familias_anio":
        df = sqlq_compras.get_gastos_todas_familias_anio(parametros["anio"])
        _dbg_set_result(df)
        return df

    elif tipo == "gastos_secciones":
        df = sqlq_compras.get_gastos_secciones_detalle_completo(parametros["familias"], parametros["mes"])
        _dbg_set_result(df)
        return df

    elif tipo == "top_proveedores":
        moneda = parametros.get("moneda", "pesos")
        anio = parametros.get("anio")
        mes = parametros.get("mes")
        df = sqlq_compras.get_top_10_proveedores_chatbot(moneda, anio, mes)
        _dbg_set_result(df)
        return df

    # =========================
    # STOCK
    # =========================
    elif tipo == "stock_total":
        df = sqlq_compras.get_stock_total()
        _dbg_set_result(df)
        return df

    elif tipo == "stock_articulo":
        df = sqlq_compras.get_stock_articulo(parametros["articulo"])
        _dbg_set_result(df)
        return df

    elif tipo == "stock_familia":
        df = sqlq_compras.get_stock_familia(parametros["familia"])
        _dbg_set_result(df)
        return df

    elif tipo == "stock_por_familia":
        df = sqlq_compras.get_stock_por_familia()
        _dbg_set_result(df)
        return df

    elif tipo == "stock_por_deposito":
        df = sqlq_compras.get_stock_por_deposito()
        _dbg_set_result(df)
        return df

    elif tipo == "stock_lotes_vencer":
        dias = parametros.get("dias", 90)
        df = sqlq_compras.get_lotes_por_vencer(dias)
        _dbg_set_result(df)
        return df

    elif tipo == "stock_lotes_vencidos":
        df = sqlq_compras.get_lotes_vencidos()
        _dbg_set_result(df)
        return df

    elif tipo == "stock_bajo":
        minimo = parametros.get("minimo", 10)
        df = sqlq_compras.get_stock_bajo(minimo)
        _dbg_set_result(df)
        return df

    elif tipo == "stock_lote":
        df = sqlq_compras.get_stock_lote_especifico(parametros["lote"])
        _dbg_set_result(df)
        return df

    else:
        raise ValueError(f"Tipo '{tipo}' no implementado")


# =========================
# UI PRINCIPAL
# =========================
def Compras_IA():

    inicializar_historial()

    st.markdown("### 🤖 Asistente de Compras IA")

    if st.button("🗑️ Limpiar chat"):
        st.session_state["historial_compras"] = []
        # limpiar debug también
        _dbg_set_interpretacion({})
        _dbg_set_sql(None, "", [], None)
        st.rerun()

    st.markdown("---")

    # MOSTRAR HISTORIAL
    for idx, msg in enumerate(st.session_state["historial_compras"]):
        with st.chat_message(msg["role"]):

            st.markdown(msg["content"])

            # =========================
            # SUGERENCIA (SI/NO) - EJECUTAR CONSULTA CORREGIDA
            # =========================
            suger = msg.get("sugerencia_ejecutable")
            if suger and isinstance(suger, dict):
                suger_preg = suger.get("pregunta")
                suger_motivo = suger.get("motivo", "")
                if suger_preg:
                    sug_id = f"sug_{int(msg.get('timestamp', 0)*1000)}_{idx}"
                    done_key = f"{sug_id}_done"
                    if not st.session_state.get(done_key, False):
                        if suger_motivo:
                            st.info(suger_motivo)
                        st.markdown(f"**¿Quisiste decir:** `{suger_preg}` ?")

                        col_s1, col_s2 = st.columns([2, 1])
                        with col_s1:
                            opt = st.radio(
                                "Confirmación",
                                ["No", "Sí"],
                                horizontal=True,
                                index=0,
                                key=f"{sug_id}_radio",
                                label_visibility="collapsed",
                            )
                        with col_s2:
                            ejecutar_btn = st.button(
                                "▶ Ejecutar",
                                key=f"{sug_id}_btn",
                                disabled=(opt != "Sí"),
                                use_container_width=True,
                            )

                        if ejecutar_btn:
                            st.session_state[done_key] = True

                            # Agregar al historial como "confirmación" del usuario
                            st.session_state["historial_compras"].append(
                                {
                                    "role": "user",
                                    "content": f"✅ Sí: {suger_preg}",
                                    "timestamp": datetime.now().timestamp(),
                                }
                            )

                            # Ejecutar sugerencia (misma lógica del input principal)
                            res2 = interpretar_pregunta(suger_preg)
                            _dbg_set_interpretacion(res2)

                            tipo2 = res2.get("tipo", "")
                            params2 = res2.get("parametros", {})

                            resp2_content = ""
                            resp2_df = None

                            try:
                                if tipo2 == "conversacion":
                                    resp2_content = responder_con_openai(suger_preg, tipo="conversacion")
                                elif tipo2 == "conocimiento":
                                    resp2_content = responder_con_openai(suger_preg, tipo="conocimiento")
                                elif tipo2 == "no_entendido":
                                    resp2_content = "🤔 No entendí bien tu pregunta."
                                    sug_txt2 = _extraer_sugerencia_simple(res2.get("sugerencia", ""))
                                    if sug_txt2:
                                        resp2_content += f"\n\n**Sugerencia:** {sug_txt2}"
                                else:
                                    resultado_sql2 = ejecutar_consulta_por_tipo(tipo2, params2)
                                    if isinstance(resultado_sql2, pd.DataFrame):
                                        if len(resultado_sql2) == 0:
                                            resp2_content = "⚠️ No se encontraron resultados"
                                            sug_obj2 = _generar_sugerencia_ejecutable(suger_preg, tipo2, params2)
                                            # si hay otra sugerencia, la guardamos para permitir corrección en cadena
                                            if sug_obj2:
                                                st.session_state["historial_compras"].append(
                                                    {
                                                        "role": "assistant",
                                                        "content": resp2_content,
                                                        "df": None,
                                                        "tipo": tipo2,
                                                        "pregunta": suger_preg,
                                                        "sugerencia_ejecutable": sug_obj2,
                                                        "timestamp": datetime.now().timestamp(),
                                                    }
                                                )
                                                st.rerun()
                                        else:
                                            resp2_content = f"✅ Encontré **{len(resultado_sql2)}** resultados"
                                            resp2_df = resultado_sql2
                                    else:
                                        resp2_content = str(resultado_sql2)

                            except Exception as e:
                                # dejar debug visible aunque haya error
                                _dbg_set_sql(tipo2, f"-- Error ejecutando tipo: {tipo2}", params2, None)
                                resp2_content = f"❌ Error: {str(e)}"

                            st.session_state["historial_compras"].append(
                                {
                                    "role": "assistant",
                                    "content": resp2_content,
                                    "df": resp2_df,
                                    "tipo": tipo2,
                                    "pregunta": suger_preg,
                                    "timestamp": datetime.now().timestamp(),
                                }
                            )

                            st.rerun()

            if "df" in msg and msg["df"] is not None:
                df = msg["df"]

                totales = calcular_totales_por_moneda(df)
                if totales:
                    col1, col2, col3 = st.columns([2, 2, 3])

                    with col1:
                        pesos = totales.get("Pesos", 0)
                        pesos_str = f"${pesos/1_000_000:,.2f}M" if pesos >= 1_000_000 else f"${pesos:,.2f}"
                        st.metric("💵 Total Pesos", pesos_str, help=f"Valor exacto: ${pesos:,.2f}")

                    with col2:
                        usd = totales.get("USD", 0)
                        usd_str = f"${usd/1_000_000:,.2f}M" if usd >= 1_000_000 else f"${usd:,.2f}"
                        st.metric("💵 Total USD", usd_str, help=f"Valor exacto: ${usd:,.2f}")

                st.markdown("---")

                tab1, tab2, tab3 = st.tabs(["📊 Tabla", "📈 Gráfico", "💡 Explicación"])

                with tab1:
                    st.dataframe(df, use_container_width=True, height=400)

                    from io import BytesIO
                    buffer = BytesIO()
                    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                        df.to_excel(writer, index=False, sheet_name="Resultados")
                    buffer.seek(0)

                    st.download_button(
                        "📥 Descargar Excel",
                        buffer,
                        f"resultado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"dl_{msg.get('timestamp', 0)}_{idx}",
                    )

                with tab2:
                    fig = generar_grafico(df, msg.get("tipo", ""))
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No se puede generar gráfico para este tipo de datos")

                with tab3:
                    explicacion = generar_explicacion_ia(df, msg.get("pregunta", ""), msg.get("tipo", ""))
                    st.markdown(explicacion)

    # INPUT
    pregunta = st.chat_input("Escribí tu consulta...")

    if pregunta:
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
        sugerencia_ejecutable = None

        if tipo == "conversacion":
            respuesta_content = responder_con_openai(pregunta, tipo="conversacion")

        elif tipo == "conocimiento":
            respuesta_content = responder_con_openai(pregunta, tipo="conocimiento")

        elif tipo == "no_entendido":
            respuesta_content = "🤔 No entendí bien tu pregunta."
            sug_txt = _extraer_sugerencia_simple(resultado.get("sugerencia", ""))
            if sug_txt:
                respuesta_content += f"\n\n**Sugerencia:** {sug_txt}"
                sugerencia_ejecutable = {
                    "pregunta": sug_txt,
                    "motivo": "Sugerencia detectada (si confirmás, la ejecuto)."
                }

        else:
            try:
                resultado_sql = ejecutar_consulta_por_tipo(tipo, parametros)

                if isinstance(resultado_sql, pd.DataFrame):
                    if len(resultado_sql) == 0:
                        respuesta_content = "⚠️ No se encontraron resultados"
                        sugerencia_ejecutable = _generar_sugerencia_ejecutable(pregunta, tipo, parametros)
                    else:
                        respuesta_content = f"✅ Encontré **{len(resultado_sql)}** resultados"
                        respuesta_df = resultado_sql
                else:
                    respuesta_content = str(resultado_sql)

            except Exception as e:
                # dejar debug visible aunque haya error
                _dbg_set_sql(tipo, f"-- Error ejecutando tipo: {tipo}", parametros, None)
                respuesta_content = f"❌ Error: {str(e)}"

        st.session_state["historial_compras"].append(
            {
                "role": "assistant",
                "content": respuesta_content,
                "df": respuesta_df,
                "tipo": tipo,
                "pregunta": pregunta,
                "sugerencia_ejecutable": sugerencia_ejecutable,
                "timestamp": datetime.now().timestamp(),
            }
        )

        st.rerun()

