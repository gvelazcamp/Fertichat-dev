# =========================
# ORQUESTADOR.PY
# =========================

import streamlit as st

# =========================
# ESTADO / DEBUG DE CARGA (FORZADO)
# =========================
ORQUESTADOR_CARGADO = True
ORQUESTADOR_ERROR = None


def _init_orquestador_state():
    """
    Fuerza ORQUESTADOR_CARGADO en:
    - global (ORQUESTADOR_CARGADO)
    - session_state (st.session_state["ORQUESTADOR_CARGADO"])
    Así, en tu debug NO debería aparecer None.
    """
    global ORQUESTADOR_CARGADO, ORQUESTADOR_ERROR
    ORQUESTADOR_CARGADO = True
    ORQUESTADOR_ERROR = None
    try:
        st.session_state["ORQUESTADOR_CARGADO"] = True
        st.session_state["ORQUESTADOR_ERROR"] = None
    except Exception as e:
        ORQUESTADOR_ERROR = str(e)


# Ejecutar al importar (y también se vuelve a ejecutar por seguridad en cada pregunta)
_init_orquestador_state()

# =========================
# ORQUESTADOR V2 - USA IA INTERPRETADOR
# =========================

import pandas as pd
import re
from typing import Tuple, Optional, Any, List
from datetime import datetime

# Importar el interpretador
from ia_interpretador import interpretar_pregunta, obtener_info_tipo, es_tipo_valido

# =========================
# IMPORTAR FUNCIONES SQL
# =========================

# --- COMPRAS / FACTURAS ---
from sql_compras import (
    get_compras_anio,
    get_total_compras_anio,
    get_detalle_compras_proveedor_mes,
    get_total_compras_proveedor_anio,
    get_detalle_compras_articulo_mes,
    get_detalle_compras_articulo_anio,
    get_total_compras_articulo_anio,
    get_compras_por_mes_excel,
    # Facturas (fallback si NO existe sql_facturas)
    get_ultima_factura_inteligente,
    get_facturas_de_articulo,
    get_detalle_factura_por_numero,
    get_total_factura_por_numero,
    # Top
    get_top_10_proveedores_chatbot,
)

# --- COMPAT: algunas versiones tuyas tienen nombres distintos ---
try:
    from sql_compras import get_detalle_compras_proveedor_anio as _get_detalle_prov_anio
except Exception:
    _get_detalle_prov_anio = None

try:
    from sql_compras import get_detalle_facturas_proveedor_anio as _get_detalle_facturas_prov_anio
except Exception:
    _get_detalle_facturas_prov_anio = None


def get_detalle_compras_proveedor_anio(proveedor_like: str, anio: int, limite: int = 5000) -> pd.DataFrame:
    """
    Wrapper compat para NO romper:
    - Si existe get_detalle_compras_proveedor_anio(proveedor, anio, ...)
    - Si existe get_detalle_facturas_proveedor_anio(proveedores:list, anios:list, ...)
    """
    if _get_detalle_prov_anio is not None:
        try:
            return _get_detalle_prov_anio(proveedor_like, anio, limite)
        except TypeError:
            return _get_detalle_prov_anio(proveedor_like, anio)

    if _get_detalle_facturas_prov_anio is not None:
        try:
            return _get_detalle_facturas_prov_anio([proveedor_like], [anio], moneda=None, limite=limite)
        except TypeError:
            return _get_detalle_facturas_prov_anio([proveedor_like], [anio])

    return pd.DataFrame()


# Total facturas proveedor (fallback)
try:
    from sql_compras import get_total_factura_proveedor as get_total_factura_proveedor
except Exception:
    try:
        from sql_compras import get_total_facturas_proveedor as get_total_factura_proveedor
    except Exception:
        def get_total_factura_proveedor(*args, **kwargs) -> pd.DataFrame:
            return pd.DataFrame()


# Facturas por proveedor (detalle) - fallback
try:
    from sql_queries import get_facturas_proveedor_detalle as get_facturas_proveedor_detalle
except Exception:
    try:
        from sql_compras import get_facturas_proveedor_detalle as get_facturas_proveedor_detalle
    except Exception:
        def get_facturas_proveedor_detalle(*args, **kwargs) -> pd.DataFrame:
            return pd.DataFrame()


# =========================
# OVERRIDE FACTURAS: USAR SQL_FACTURAS SI EXISTE (LO QUE PEDISTE)
# =========================
try:
    from sql_facturas import (
        get_facturas_proveedor as _sf_get_facturas_proveedor,
        get_total_facturas_proveedor as _sf_get_total_facturas_proveedor,
        get_detalle_factura_por_numero as _sf_get_detalle_factura_por_numero,
        get_total_factura_por_numero as _sf_get_total_factura_por_numero,
        get_ultima_factura_inteligente as _sf_get_ultima_factura_inteligente,
        get_facturas_articulo as _sf_get_facturas_articulo,
    )

    # Reemplazar SOLO las funciones de FACTURAS (sin tocar compras/comparativas/stock)
    get_facturas_proveedor_detalle = _sf_get_facturas_proveedor
    get_total_factura_proveedor = _sf_get_total_facturas_proveedor
    get_detalle_factura_por_numero = _sf_get_detalle_factura_por_numero
    get_total_factura_por_numero = _sf_get_total_factura_por_numero
    get_ultima_factura_inteligente = _sf_get_ultima_factura_inteligente

    # Compat: tu orquestador importa "get_facturas_de_articulo"
    get_facturas_de_articulo = _sf_get_facturas_articulo

    try:
        st.session_state["DBG_FACTURAS_ORIGEN"] = "sql_facturas"
    except Exception:
        pass

except Exception:
    # Si sql_facturas no existe todavía, queda todo como estaba.
    pass


# --- COMPARATIVAS + GASTOS ---
from sql_comparativas import (
    get_comparacion_proveedor_meses,
    get_comparacion_articulo_anios,
    get_comparacion_proveedor_anios_like,
    get_comparacion_proveedor_anios_monedas,
    get_comparacion_familia_anios_monedas,
    get_comparacion_proveedores_meses_multi,
    get_comparacion_proveedores_anios_multi,
    # Gastos
    get_gastos_todas_familias_mes,
    get_gastos_todas_familias_anio,
    get_gastos_secciones_detalle_completo,
)

try:
    from sql_comparativas import get_comparacion_articulo_meses
except Exception:
    def get_comparacion_articulo_meses(*args, **kwargs) -> pd.DataFrame:
        return pd.DataFrame()

try:
    from sql_comparativas import get_comparacion_familia_meses_moneda
except Exception:
    def get_comparacion_familia_meses_moneda(*args, **kwargs) -> pd.DataFrame:
        return pd.DataFrame()


# --- STOCK ---
from sql_stock import (
    get_stock_total,
    get_stock_articulo,
    get_stock_familia,
    get_stock_por_familia,
    get_stock_por_deposito,
    get_lotes_por_vencer,
    get_lotes_vencidos,
    get_stock_bajo,
    get_stock_lote_especifico,
)

# Importar utilidades
from utils_format import formatear_dataframe
from utils_openai import responder_con_openai


# =====================================================================
# FACTURAS - HELPERS (AGREGADO)
# =====================================================================

def _normalizar_nro_factura(nro: str) -> str:
    nro = str(nro or "").strip().upper()
    if not nro:
        return ""

    if re.fullmatch(r"\d+", nro):
        return "A" + nro.zfill(8)

    m = re.fullmatch(r"([A-Z])(\d+)", nro)
    if m:
        letra = m.group(1)
        dig = m.group(2)
        if len(dig) < 8:
            dig = dig.zfill(8)
        return letra + dig

    return nro


def _extraer_nro_factura_fallback(texto: str) -> Optional[str]:
    if not texto:
        return None

    t = str(texto).strip()

    if re.fullmatch(r"[A-Za-z]\d{5,}", t):
        return _normalizar_nro_factura(t)

    m = re.search(
        r"\b(?:detalle\s+)?(?:factura|comprobante|nro\.?\s*factura|nro\.?\s*comprobante)\b\s*[:#-]?\s*([A-Za-z]?\d{3,})\b",
        t,
        flags=re.IGNORECASE
    )
    if m:
        return _normalizar_nro_factura(m.group(1))

    return None


def _to_like(p: str) -> str:
    p = str(p or "").strip().lower()
    if not p:
        return ""
    if "%" in p:
        return p
    return f"%{p}%"


# =====================================================================
# FUNCIÓN PRINCIPAL
# =====================================================================

def procesar_pregunta_v2(pregunta: str) -> Tuple[str, Optional[pd.DataFrame], Optional[dict]]:
    """
    Retorna:
    - mensaje: str
    - df: DataFrame o None
    - sugerencia_info: dict o None
    """

    # Forzar estado en cada pregunta (para que NO quede None)
    _init_orquestador_state()

    print(f"\n{'='*60}")
    print(f"📝 PREGUNTA: {pregunta}")
    print(f"{'='*60}")

    interpretacion = interpretar_pregunta(pregunta)

    tipo = interpretacion.get("tipo", "no_entendido")
    params = interpretacion.get("parametros", {})
    debug = interpretacion.get("debug", "")

    print(f"🎯 TIPO: {tipo}")
    print(f"📦 PARAMS: {params}")
    print(f"🔍 DEBUG: {debug}")

    try:
        if st.session_state.get("DEBUG_SQL", False):
            st.session_state["DBG_INT_LAST"] = {
                "pregunta": pregunta,
                "tipo": tipo,
                "parametros": params,
                "debug": debug,
            }
    except Exception:
        pass

    if tipo == "conversacion":
        respuesta = responder_con_openai(pregunta, "conversacion")
        return f"💬 {respuesta}", None, None

    if tipo == "conocimiento":
        respuesta = responder_con_openai(pregunta, "conocimiento")
        return f"📚 {respuesta}", None, None

    if tipo == "no_entendido":
        nro_fb = _extraer_nro_factura_fallback(pregunta)
        if nro_fb:
            return _ejecutar_consulta("detalle_factura_numero", {"nro_factura": nro_fb}, pregunta)

    if tipo == "no_entendido":
        sugerencia = interpretacion.get("sugerencia", "No entendí tu pregunta.")
        alternativas = interpretacion.get("alternativas", [])
        return (
            f"🤔 {sugerencia}",
            None,
            {
                "sugerencia": sugerencia,
                "alternativas": alternativas,
                "pregunta_original": pregunta
            }
        )

    return _ejecutar_consulta(tipo, params, pregunta)


# =====================================================================
# EJECUTOR DE CONSULTAS
# =====================================================================

def _ejecutar_consulta(tipo: str, params: dict, pregunta_original: str) -> Tuple[str, Optional[pd.DataFrame], None]:
    """Ejecuta la consulta SQL según el tipo de consulta."""
    try:
        # =========================================================
        # COMPRAS
        # =========================================================
        if tipo == "compras_anio":
            anio = params.get("anio")
            if not anio:
                return "❌ Falta especificar el año.", None, None

            resumen = get_total_compras_anio(anio)
            df = get_compras_anio(anio)

            if df is None or df.empty:
                return f"No encontré compras en {anio}.", None, None

            total_pesos = resumen.get("total_pesos", 0)
            total_usd = resumen.get("total_usd", 0)
            registros = resumen.get("registros", 0)
            proveedores = resumen.get("proveedores", 0)
            articulos = resumen.get("articulos", 0)

            total_pesos_fmt = f"${total_pesos:,.0f}".replace(",", ".")
            total_usd_fmt = f"U$S {total_usd:,.0f}".replace(",", ".")

            msg = f"📦 **Compras {anio}** | 💰 **{total_pesos_fmt}**"
            if total_usd > 0:
                msg += f" | 💵 **{total_usd_fmt}**"
            msg += f" | {registros} registros | {proveedores} proveedores | {articulos} artículos"

            if registros > len(df):
                msg += f" (mostrando {len(df)})"

            return msg + ":", formatear_dataframe(df), None

        if tipo == "compras_proveedor_mes":
            proveedor = params.get("proveedor")
            mes = params.get("mes")

            if not proveedor or not mes:
                return "❌ Falta proveedor o mes.", None, None

            df = get_detalle_compras_proveedor_mes(proveedor, mes)

            if df is None or df.empty:
                return f"No encontré compras de {str(proveedor).upper()} en {mes}.", None, None

            total = df["Total"].sum() if "Total" in df.columns else 0
            total_fmt = f"${total:,.0f}".replace(",", ".")

            return (
                f"📋 Compras de **{str(proveedor).upper()}** en {mes} | 💰 **{total_fmt}** | {len(df)} registros:",
                formatear_dataframe(df),
                None
            )

        if tipo == "compras_proveedor_anio":
            proveedor = params.get("proveedor")
            anio = params.get("anio")

            if not proveedor or not anio:
                return "❌ Falta proveedor o año.", None, None

            resumen = get_total_compras_proveedor_anio(proveedor, anio)
            df = get_detalle_compras_proveedor_anio(proveedor, anio)

            if df is None or df.empty:
                return f"No encontré compras de {str(proveedor).upper()} en {anio}.", None, None

            total = resumen.get("total", 0)
            total_fmt = f"${total:,.0f}".replace(",", ".")
            registros = resumen.get("registros", 0)

            msg = f"📋 Compras de **{str(proveedor).upper()}** en {anio} | 💰 **{total_fmt}** | {registros} registros"
            if registros > len(df):
                msg += f" (mostrando {len(df)})"

            return msg + ":", formatear_dataframe(df), None

        if tipo == "compras_articulo_mes":
            articulo = params.get("articulo")
            mes = params.get("mes")

            if not articulo or not mes:
                return "❌ Falta artículo o mes.", None, None

            df = get_detalle_compras_articulo_mes(articulo, mes)

            if df is None or df.empty:
                return f"No encontré compras de {str(articulo).upper()} en {mes}.", None, None

            total = df["Total"].sum() if "Total" in df.columns else 0
            total_fmt = f"${total:,.0f}".replace(",", ".")

            return (
                f"📦 Compras de **{str(articulo).upper()}** en {mes} | 💰 **{total_fmt}** | {len(df)} registros:",
                formatear_dataframe(df),
                None
            )

        if tipo == "compras_articulo_anio":
            articulo = params.get("articulo")
            anio = params.get("anio")

            if not articulo or not anio:
                return "❌ Falta artículo o mes.", None, None

            resumen = get_total_compras_articulo_anio(articulo, anio)
            df = get_detalle_compras_articulo_anio(articulo, anio)

            if df is None or df.empty:
                return f"No encontré compras de {str(articulo).upper()} en {anio}.", None, None

            total = resumen.get("total", 0)
            total_fmt = f"${total:,.0f}".replace(",", ".")

            return (
                f"📦 Compras de **{str(articulo).upper()}** en {anio} | 💰 **{total_fmt}** | {len(df)} registros:",
                formatear_dataframe(df),
                None
            )

        if tipo == "compras_mes":
            mes = params.get("mes")
            if not mes:
                return "❌ Falta especificar el mes.", None, None

            df = get_compras_por_mes_excel(mes)
            if df is None or df.empty:
                return f"No encontré compras en {mes}.", None, None

            return f"📦 Compras de {mes} ({len(df)} registros):", formatear_dataframe(df), None

        # =========================================================
        # DETALLE FACTURA POR NÚMERO
        # =========================================================
        if tipo == "detalle_factura_numero":
            nro = params.get("nro_factura")
            if not nro:
                return "❌ Falta número de factura.", None, None

            df = get_detalle_factura_por_numero(nro)
            if df is None or df.empty:
                return f"No encontré detalle para la factura {nro}.", None, None

            total_info = get_total_factura_por_numero(nro)

            # Compat: puede venir dict (sql_facturas) o DataFrame (sql_compras viejo)
            total_fact = 0.0
            try:
                if isinstance(total_info, dict):
                    total_fact = float(total_info.get("total", 0) or total_info.get("total_factura", 0) or 0)
                elif isinstance(total_info, pd.DataFrame) and (not total_info.empty):
                    if "total_factura" in total_info.columns:
                        total_fact = float(total_info["total_factura"].iloc[0] or 0)
            except Exception:
                total_fact = 0.0

            total_fmt = f"${total_fact:,.0f}".replace(",", ".") if total_fact else ""
            titulo = f"🧾 Detalle factura **{nro}**"
            if total_fmt:
                titulo += f" | Total: **{total_fmt}**"

            return titulo + ":", formatear_dataframe(df), None

        # =========================================================
        # FACTURAS (LISTADO)  <-- AHORA SALE DESDE sql_facturas SI EXISTE
        # =========================================================
        if tipo in ("facturas_proveedor", "facturas_proveedor_detalle"):
            proveedores = params.get("proveedores", [])
            if isinstance(proveedores, str):
                proveedores = [proveedores]

            proveedores_raw = [str(p).strip() for p in proveedores if str(p).strip()]
            if not proveedores_raw:
                return "❌ Indicá el proveedor. Ej: todas las facturas roche 2025", None, None

            # Default a 2025 si no se especifica año (para coincidir con el SQL de Supabase)
            if not params.get("anios"):
                params["anios"] = [2025]

            df = get_facturas_proveedor_detalle(
                proveedores=proveedores_raw,
                meses=params.get("meses"),
                anios=params.get("anios"),
                desde=params.get("desde"),
                hasta=params.get("hasta"),
                articulo=params.get("articulo"),
                moneda=params.get("moneda"),
                limite=params.get("limite", 5000),
            )

            if df is None or df.empty:
                tiempo_lbl = ""
                if params.get("meses"):
                    tiempo_lbl = f" en {', '.join(params.get('meses'))}"
                elif params.get("anios"):
                    tiempo_lbl = f" en {', '.join(map(str, params.get('anios')))}"
                return f"No encontré facturas de **{', '.join([p.upper() for p in proveedores_raw])}**{tiempo_lbl}.", None, None

            prov_lbl = ", ".join([p.upper() for p in proveedores_raw[:3]])
            return f"🧾 Facturas de **{prov_lbl}** ({len(df)} registros):", formatear_dataframe(df), None

        # =========================================================
        # COMPARACIONES
        # =========================================================
        if tipo == "comparar_proveedor_meses":
            proveedor = params.get("proveedor")
            mes1 = params.get("mes1")
            mes2 = params.get("mes2")
            label1 = params.get("label1", mes1)
            label2 = params.get("label2", mes2)

            if not proveedor or not mes1 or not mes2:
                return "❌ Necesito proveedor y dos meses para comparar.", None, None

            df = get_comparacion_proveedor_meses(proveedor, mes1, mes2, label1, label2)
            if df is None or df.empty:
                return f"No encontré datos para comparar {str(proveedor).upper()} entre {label1} y {label2}.", None, None

            return (f"📊 Comparación {str(proveedor).upper()}: {label1} vs {label2}", formatear_dataframe(df), None)

        if tipo == "comparar_proveedor_anios":
            proveedor = params.get("proveedor")
            anios = sorted(params.get("anios", []))

            if not proveedor or len(anios) < 2:
                return "❌ Necesito proveedor y al menos dos años para comparar.", None, None

            df = get_comparacion_proveedor_anios_like(proveedor, anios)
            if df is None or df.empty:
                return f"No encontré datos para comparar {str(proveedor).upper()}.", None, None

            anios_str = " vs ".join(map(str, anios))
            return (f"📊 Comparación {str(proveedor).upper()}: {anios_str}", formatear_dataframe(df), None)

        if tipo == "comparar_articulo_meses":
            articulo = params.get("articulo")
            mes1 = params.get("mes1")
            mes2 = params.get("mes2")

            if not articulo or not mes1 or not mes2:
                return "❌ Falta artículo o meses.", None, None

            label1 = params.get("label1", mes1)
            label2 = params.get("label2", mes2)

            df = get_comparacion_articulo_meses(mes1, mes2, label1, label2, [articulo])
            if df is None or df.empty:
                return f"No encontré datos para comparar {articulo}.", None, None

            return (f"📊 Comparación {str(articulo).upper()}: {label1} vs {label2}", formatear_dataframe(df), None)

        if tipo == "comparar_articulo_anios":
            articulo = params.get("articulo")
            anios = sorted(params.get("anios", []))

            if not articulo or len(anios) < 2:
                return "❌ Falta artículo o años.", None, None

            df = get_comparacion_articulo_anios(anios, articulo)
            if df is None or df.empty:
                return f"No encontré datos para comparar {articulo}.", None, None

            anios_str = " vs ".join(map(str, anios))
            return (f"📊 Comparación {str(articulo).upper()}: {anios_str}", formatear_dataframe(df), None)

        if tipo == "comparar_familia_meses":
            mes1 = params.get("mes1")
            mes2 = params.get("mes2")
            moneda = params.get("moneda", "$")

            if not mes1 or not mes2:
                return "❌ Necesito dos meses para comparar.", None, None

            label1 = params.get("label1", mes1)
            label2 = params.get("label2", mes2)

            df = get_comparacion_familia_meses_moneda(mes1, mes2, label1, label2, moneda)
            if df is None or df.empty:
                return "No encontré datos para comparar.", None, None

            return (f"📊 Comparación familias: {label1} vs {label2} ({moneda})", formatear_dataframe(df), None)

        if tipo == "comparar_familia_anios":
            anios = sorted(params.get("anios", []))
            if len(anios) < 2:
                return "❌ Necesito al menos dos años para comparar.", None, None

            df = get_comparacion_familia_anios_monedas(anios)
            if df is None or df.empty:
                return "No encontré datos para comparar.", None, None

            anios_str = " vs ".join(map(str, anios))
            return (f"📊 Comparación familias: {anios_str}", formatear_dataframe(df), None)

        # =========================================================
        # GASTOS
        # =========================================================
        if tipo == "gastos_familias_mes":
            mes = params.get("mes")
            if not mes:
                return "❌ Falta especificar el mes.", None, None

            df = get_gastos_todas_familias_mes(mes)
            if df is None or df.empty:
                return f"No encontré gastos en {mes}.", None, None

            return f"📊 Gastos por familia en {mes}:", formatear_dataframe(df), None

        if tipo == "gastos_familias_anio":
            anio = params.get("anio")
            if not anio:
                return "❌ Falta especificar el año.", None, None

            df = get_gastos_todas_familias_anio(anio)
            if df is None or df.empty:
                return f"No encontré gastos en {anio}.", None, None

            return f"📊 Gastos por familia en {anio}:", formatear_dataframe(df), None

        if tipo == "gastos_secciones":
            familias = params.get("familias", [])
            mes = params.get("mes")

            if not familias or not mes:
                return "❌ Falta especificar familias o mes.", None, None

            df = get_gastos_secciones_detalle_completo(familias, mes)
            if df is None or df.empty:
                return f"No encontré gastos para esas familias en {mes}.", None, None

            return f"📊 Gastos de familias {', '.join(familias)} en {mes}:", formatear_dataframe(df), None

        # =========================================================
        # TOP PROVEEDORES
        # =========================================================
        if tipo == "top_proveedores":
            moneda = params.get("moneda")
            anio = params.get("anio")
            mes = params.get("mes")

            df = get_top_10_proveedores_chatbot(moneda, anio, mes)
            if df is None or df.empty:
                return "No encontré datos de proveedores.", None, None

            titulo = "🏆 Top 10 Proveedores"
            if moneda:
                titulo += f" ({moneda})"
            if mes:
                titulo += f" {mes}"
            elif anio:
                titulo += f" {anio}"

            return titulo + ":", formatear_dataframe(df), None

        # =========================================================
        # STOCK
        # =========================================================
        if tipo == "stock_total":
            df = get_stock_total()
            if df is not None and not df.empty:
                return "📦 **Resumen de stock total:**", formatear_dataframe(df), None
            return "No pude obtener el stock total.", None, None

        if tipo == "stock_articulo":
            articulo = params.get("articulo")
            if not articulo:
                return "❌ ¿De qué artículo querés ver el stock?", None, None

            df = get_stock_articulo(articulo)
            if df is None or df.empty:
                return f"No encontré stock de '{articulo}'.", None, None

            return f"📦 **Stock de '{str(articulo).upper()}':**", formatear_dataframe(df), None

        if tipo == "stock_familia":
            familia = params.get("familia")
            if not familia:
                return "❌ ¿De qué familia querés ver el stock?", None, None

            df = get_stock_familia(familia)
            if df is None or df.empty:
                return f"No encontré stock de la familia '{familia}'.", None, None

            return f"📦 **Stock de familia {str(familia).upper()}:**", formatear_dataframe(df), None

        if tipo == "stock_por_familia":
            df = get_stock_por_familia()
            if df is not None and not df.empty:
                return "📦 **Stock por familia:**", formatear_dataframe(df), None
            return "No encontré datos de stock por familia.", None, None

        if tipo == "stock_por_deposito":
            df = get_stock_por_deposito()
            if df is not None and not df.empty:
                return "📦 **Stock por depósito:**", formatear_dataframe(df), None
            return "No encontré datos de stock por depósito.", None, None

        if tipo == "stock_lotes_vencer":
            dias = params.get("dias", 90)
            df = get_lotes_por_vencer(dias)
            if df is not None and not df.empty:
                return f"⚠️ **Lotes que vencen en los próximos {dias} días:**", formatear_dataframe(df), None
            return f"No hay lotes que venzan en los próximos {dias} días.", None, None

        if tipo == "stock_lotes_vencidos":
            df = get_lotes_vencidos()
            if df is not None and not df.empty:
                return "🚨 **Lotes VENCIDOS:**", formatear_dataframe(df), None
            return "No hay lotes vencidos con stock.", None, None

        if tipo == "stock_bajo":
            minimo = params.get("minimo", 10)
            df = get_stock_bajo(minimo)
            if df is not None and not df.empty:
                return f"📉 **Artículos con stock bajo (≤{minimo}):**", formatear_dataframe(df), None
            return "No hay artículos con stock bajo.", None, None

        if tipo == "stock_lote":
            lote = params.get("lote")
            if not lote:
                return "❌ ¿Qué lote querés buscar?", None, None

            df = get_stock_lote_especifico(lote)
            if df is None or df.empty:
                return f"No encontré el lote '{lote}'.", None, None

            return f"📦 **Lote {str(lote).upper()}:**", formatear_dataframe(df), None

        return f"❌ Tipo de consulta '{tipo}' no implementado.", None, None

    except Exception as e:
        print(f"❌ Error ejecutando consulta: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ Error: {str(e)[:150]}", None, None


# =====================================================================
# COMPAT CON SISTEMA ANTERIOR
# =====================================================================

def procesar_pregunta(pregunta: str) -> Tuple[str, Optional[pd.DataFrame]]:
    mensaje, df, sugerencia = procesar_pregunta_v2(pregunta)

    if sugerencia:
        alternativas = sugerencia.get("alternativas", [])
        if alternativas:
            mensaje += "\n\n**Alternativas:**\n" + "\n".join(f"• {a}" for a in alternativas[:3])

    return mensaje, df


def procesar_pregunta_router(pregunta: str) -> Tuple[str, Optional[pd.DataFrame]]:
    return procesar_pregunta(pregunta)


# =====================================================================
# TEST
# =====================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🛠 Verificando estado del orquestador...")
    try:
        print(f"ORQUESTADOR_CARGADO (session): {st.session_state.get('ORQUESTADOR_CARGADO', None)}")
    except Exception:
        print("ORQUESTADOR_CARGADO (session): n/a")
    print("=" * 60)
