# =========================
# ORQUESTADOR V2 - USA IA INTERPRETADOR
# =========================
# Flujo:
# 1. Usuario pregunta
# 2. IA interpreta → tipo + parámetros
# 3. Si no entiende → sugerencia con botones
# 4. Si entiende → llama función SQL
# 5. Formatea y devuelve resultado
# =========================

import streamlit as st
import pandas as pd
import re
from typing import Tuple, Optional
from datetime import datetime

# Importar el interpretador
from ia_interpretador import interpretar_pregunta, obtener_info_tipo, es_tipo_valido

# Importar funciones SQL
from sql_queries import (
    # Compras
    get_compras_anio,
    get_total_compras_anio,
    get_detalle_compras_proveedor_mes,
    get_detalle_compras_proveedor_anio,
    get_total_compras_proveedor_anio,
    get_detalle_compras_articulo_mes,
    get_detalle_compras_articulo_anio,
    get_total_compras_articulo_anio,
    get_compras_por_mes_excel,

    # Facturas
    get_ultima_factura_inteligente,
    get_facturas_de_articulo,
    get_detalle_factura_por_numero,
    get_total_factura_por_numero,

    # ✅ NUEVO: TODAS LAS FACTURAS POR PROVEEDOR (DETALLE)
    get_facturas_proveedor_detalle,

    # Comparaciones
    get_comparacion_proveedor_meses,
    get_comparacion_proveedor_anios_monedas,
    get_comparacion_articulo_meses,
    get_comparacion_articulo_anios,
    get_comparacion_familia_meses_moneda,
    get_comparacion_familia_anios_monedas,

    # Gastos
    get_gastos_todas_familias_mes,
    get_gastos_todas_familias_anio,
    get_gastos_secciones_detalle_completo,

    # Top
    get_top_10_proveedores_chatbot,

    # Stock
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

    # Solo números -> A + 8 dígitos (ej: 273279 -> A00273279)
    if re.fullmatch(r"\d+", nro):
        return "A" + nro.zfill(8)

    # Letra + números -> asegurar 8 dígitos si es A#####
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

    # Caso: el texto ES solo el nro (A00273279)
    if re.fullmatch(r"[A-Za-z]\d{5,}", t):
        return _normalizar_nro_factura(t)

    # Caso: "detalle factura 273279" / "factura A00273279" / "comprobante 273279"
    m = re.search(
        r"\b(?:detalle\s+)?(?:factura|comprobante|nro\.?\s*factura|nro\.?\s*comprobante)\b\s*[:#-]?\s*([A-Za-z]?\d{3,})\b",
        t,
        flags=re.IGNORECASE
    )
    if m:
        return _normalizar_nro_factura(m.group(1))

    return None


# =====================================================================
# FUNCIÓN PRINCIPAL
# =====================================================================

def procesar_pregunta_v2(pregunta: str) -> Tuple[str, Optional[pd.DataFrame], Optional[dict]]:
    """
    Procesa la pregunta del usuario usando el nuevo sistema IA.

    Retorna:
    - mensaje: str con la respuesta o título
    - df: DataFrame con datos (o None)
    - sugerencia_info: dict con info de sugerencia si no entendió (o None)
    """

    print(f"\n{'='*60}")
    print(f"📝 PREGUNTA: {pregunta}")
    print(f"{'='*60}")

    # PASO 1: Interpretar con IA
    interpretacion = interpretar_pregunta(pregunta)

    tipo = interpretacion.get("tipo", "no_entendido")
    params = interpretacion.get("parametros", {})
    debug = interpretacion.get("debug", "")

    print(f"🎯 TIPO: {tipo}")
    print(f"📦 PARAMS: {params}")
    print(f"🔍 DEBUG: {debug}")

    # PASO 2: Manejar casos especiales

    # Conversación
    if tipo == "conversacion":
        respuesta = responder_con_openai(pregunta, "conversacion")
        return f"💬 {respuesta}", None, None

    # Conocimiento general
    if tipo == "conocimiento":
        respuesta = responder_con_openai(pregunta, "conocimiento")
        return f"📚 {respuesta}", None, None

    # ✅ FALLBACK FACTURA (AGREGADO):
    # Si la IA no entiende pero el texto claramente pide "detalle factura ..."
    if tipo == "no_entendido":
        nro_fb = _extraer_nro_factura_fallback(pregunta)
        if nro_fb:
            return _ejecutar_consulta(
                "detalle_factura_numero",
                {"nro_factura": nro_fb},
                pregunta
            )

    # No entendido → devolver sugerencia
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

    # PASO 3: Ejecutar consulta según tipo
    return _ejecutar_consulta(tipo, params, pregunta)


# =====================================================================
# EJECUTOR DE CONSULTAS
# =====================================================================

def _ejecutar_consulta(tipo: str, params: dict, pregunta_original: str) -> Tuple[str, Optional[pd.DataFrame], None]:
    """Ejecuta la consulta SQL según el tipo"""

    try:
        # =========================================================
        # COMPRAS
        # =========================================================

        if tipo == "compras_anio":
            anio = params.get("anio")
            if not anio:
                return "❌ Falta especificar el año.", None, None

            # Obtener resumen
            resumen = get_total_compras_anio(anio)
            df = get_compras_anio(anio)

            if df is None or df.empty:
                return f"No encontré compras en {anio}.", None, None

            # Formatear totales
            total_pesos = resumen.get('total_pesos', 0)
            total_usd = resumen.get('total_usd', 0)
            registros = resumen.get('registros', 0)
            proveedores = resumen.get('proveedores', 0)
            articulos = resumen.get('articulos', 0)

            total_pesos_fmt = f"${total_pesos:,.0f}".replace(',', '.')
            total_usd_fmt = f"U$S {total_usd:,.0f}".replace(',', '.')

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
                return f"No encontré compras de {proveedor.upper()} en {mes}.", None, None

            total = df['Total'].sum() if 'Total' in df.columns else 0
            total_fmt = f"${total:,.0f}".replace(',', '.')

            return (
                f"📋 Compras de **{proveedor.upper()}** en {mes} | 💰 **{total_fmt}** | {len(df)} registros:",
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
                return f"No encontré compras de {proveedor.upper()} en {anio}.", None, None

            total = resumen.get('total', 0)
            total_fmt = f"${total:,.0f}".replace(',', '.')
            registros = resumen.get('registros', 0)

            msg = f"📋 Compras de **{proveedor.upper()}** en {anio} | 💰 **{total_fmt}** | {registros} registros"
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
                return f"No encontré compras de {articulo.upper()} en {mes}.", None, None

            total = df['Total'].sum() if 'Total' in df.columns else 0
            total_fmt = f"${total:,.0f}".replace(',', '.')

            return (
                f"📦 Compras de **{articulo.upper()}** en {mes} | 💰 **{total_fmt}** | {len(df)} registros:",
                formatear_dataframe(df),
                None
            )


        if tipo == "compras_articulo_anio":
            articulo = params.get("articulo")
            anio = params.get("anio")

            if not articulo or not anio:
                return "❌ Falta artículo o año.", None, None

            resumen = get_total_compras_articulo_anio(articulo, anio)
            df = get_detalle_compras_articulo_anio(articulo, anio)

            if df is None or df.empty:
                return f"No encontré compras de {articulo.upper()} en {anio}.", None, None

            total = resumen.get('total', 0)
            total_fmt = f"${total:,.0f}".replace(',', '.')

            return (
                f"📦 Compras de **{articulo.upper()}** en {anio} | 💰 **{total_fmt}** | {len(df)} registros:",
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
        # FACTURAS
        # =========================================================

        if tipo == "ultima_factura":
            patron = params.get("patron")

            if not patron:
                return "❌ ¿De qué artículo o proveedor querés la última factura?", None, None

            df = get_ultima_factura_inteligente(patron)

            if df is None or df.empty:
                return f"No encontré facturas de '{patron}'.", None, None

            return f"🧾 Última factura de **{patron.upper()}**:", formatear_dataframe(df), None


        if tipo == "facturas_articulo":
            articulo = params.get("articulo")

            if not articulo:
                return "❌ ¿De qué artículo querés ver las facturas?", None, None

            df = get_facturas_de_articulo(articulo, solo_ultima=False)

            if df is None or df.empty:
                return f"No encontré facturas de '{articulo}'.", None, None

            return f"🧾 Facturas de **{articulo.upper()}** ({len(df)} registros):", formatear_dataframe(df), None


        # ✅ NUEVO: FACTURAS POR PROVEEDOR (DETALLE)
        # Soporta tipo canónico "facturas_proveedor"
        # y también el tipo viejo que tenías en el interpretador.
        if tipo in ("facturas_proveedor", "compras_Todas las facturas de un Proveedor"):
            proveedores = params.get("proveedores") or []
            if isinstance(proveedores, str) and proveedores.strip():
                proveedores = [proveedores.strip()]

            # compat: por si viene "proveedor" singular
            prov_singular = params.get("proveedor")
            if (not proveedores) and prov_singular:
                proveedores = [str(prov_singular).strip()]

            meses = params.get("meses")
            anios = params.get("anios")
            desde = params.get("desde")
            hasta = params.get("hasta")
            articulo = params.get("articulo")
            moneda = params.get("moneda")
            limite = params.get("limite", 5000)

            if not proveedores:
                return "❌ Falta proveedor para listar facturas. Ej: todas las facturas roche 2025", None, None

            df = get_facturas_proveedor_detalle(
                proveedores=proveedores,
                meses=meses,
                anios=anios,
                desde=desde,
                hasta=hasta,
                articulo=articulo,
                moneda=moneda,
                limite=limite,
            )

            if df is None or df.empty:
                prov_txt = ", ".join([p.upper() for p in proveedores[:3]])
                return f"No encontré facturas de {prov_txt} para ese período.", None, None

            total = df["Total"].sum() if "Total" in df.columns else 0
            total_fmt = f"${total:,.0f}".replace(",", ".")
            prov_txt = ", ".join([p.upper() for p in proveedores[:3]])

            # título “humano” según tiempo
            tiempo_txt = ""
            if meses and isinstance(meses, list) and meses:
                tiempo_txt = f" en {meses[0]}"
            elif anios and isinstance(anios, list) and anios:
                tiempo_txt = f" en {anios[0]}"
            elif desde and hasta:
                tiempo_txt = f" del {desde} al {hasta}"

            return (
                f"🧾 Facturas de **{prov_txt}**{tiempo_txt} | 💰 **{total_fmt}** | {len(df)} registros:",
                formatear_dataframe(df),
                None
            )


        # ✅ SOPORTE NUEVO (AGREGADO): detalle_factura_numero
        if tipo in ("detalle_factura", "detalle_factura_numero"):
            nro = params.get("nro_factura") or params.get("nro")

            if not nro:
                return "❌ Falta el número de factura.", None, None

            nro_clean = _normalizar_nro_factura(nro)
            if not nro_clean:
                return "❌ Número de factura inválido.", None, None

            df = get_detalle_factura_por_numero(nro_clean)

            if df is None or df.empty:
                return f"No encontré la factura {nro_clean}.", None, None

            return f"🧾 Detalle de factura {nro_clean}:", formatear_dataframe(df), None


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

            df = get_comparacion_proveedor_meses(
                proveedor,
                mes1,
                mes2,
                label1,
                label2
            )

            if df is None or df.empty:
                return f"No encontré datos para comparar {proveedor.upper()} entre {label1} y {label2}.", None, None

            return (
                f"📊 Comparación {proveedor.upper()}: {label1} vs {label2}",
                formatear_dataframe(df),
                None
            )


        if tipo == "comparar_proveedor_anios":
            proveedor = params.get("proveedor")
            anios = sorted(params.get("anios", []))

            if not proveedor or len(anios) < 2:
                return "❌ Necesito proveedor y al menos dos años para comparar.", None, None

            df = get_comparacion_proveedor_anios_like(
                proveedor,
                anios
            )

            if df is None or df.empty:
                return f"No encontré datos para comparar {proveedor.upper()}.", None, None

            anios_str = " vs ".join(map(str, anios))
            return (
                f"📊 Comparación {proveedor.upper()}: {anios_str}",
                formatear_dataframe(df),
                None
            )


        if tipo == "comparar_articulo_meses":
            articulo = params.get("articulo")
            mes1 = params.get("mes1")
            mes2 = params.get("mes2")

            if not articulo or not mes1 or not mes2:
                return "❌ Falta artículo o meses.", None, None

            label1 = params.get("label1", mes1)
            label2 = params.get("label2", mes2)

            df = get_comparacion_articulo_meses(
                mes1,
                mes2,
                label1,
                label2,
                [articulo]
            )

            if df is None or df.empty:
                return f"No encontré datos para comparar {articulo}.", None, None

            return (
                f"📊 Comparación {articulo.upper()}: {label1} vs {label2}",
                formatear_dataframe(df),
                None
            )


        if tipo == "comparar_articulo_anios":
            articulo = params.get("articulo")
            anios = sorted(params.get("anios", []))

            if not articulo or len(anios) < 2:
                return "❌ Falta artículo o años.", None, None

            df = get_comparacion_articulo_anios(anios, articulo)

            if df is None or df.empty:
                return f"No encontré datos para comparar {articulo}.", None, None

            anios_str = " vs ".join(map(str, anios))
            return (
                f"📊 Comparación {articulo.upper()}: {anios_str}",
                formatear_dataframe(df),
                None
            )


        if tipo == "comparar_familia_meses":
            mes1 = params.get("mes1")
            mes2 = params.get("mes2")
            moneda = params.get("moneda", "$")

            if not mes1 or not mes2:
                return "❌ Necesito dos meses para comparar.", None, None

            label1 = params.get("label1", mes1)
            label2 = params.get("label2", mes2)

            df = get_comparacion_familia_meses_moneda(
                mes1,
                mes2,
                label1,
                label2,
                moneda
            )

            if df is None or df.empty:
                return "No encontré datos para comparar.", None, None

            return (
                f"📊 Comparación familias: {label1} vs {label2} ({moneda})",
                formatear_dataframe(df),
                None
            )


        if tipo == "comparar_familia_anios":
            anios = sorted(params.get("anios", []))

            if len(anios) < 2:
                return "❌ Necesito al menos dos años para comparar.", None, None

            df = get_comparacion_familia_anios_monedas(anios)

            if df is None or df.empty:
                return "No encontré datos para comparar.", None, None

            anios_str = " vs ".join(map(str, anios))
            return (
                f"📊 Comparación familias: {anios_str}",
                formatear_dataframe(df),
                None
            )


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

            # Calcular totales
            total_pesos = df['Total_Pesos'].sum() if 'Total_Pesos' in df.columns else 0
            total_usd = df['Total_USD'].sum() if 'Total_USD' in df.columns else 0

            total_pesos_fmt = f"${total_pesos:,.0f}".replace(',', '.')
            total_usd_fmt = f"U$S {total_usd:,.0f}".replace(',', '.')

            msg = f"📊 Gastos por familia en {mes} | 💰 **{total_pesos_fmt}**"
            if total_usd > 0:
                msg += f" | 💵 **{total_usd_fmt}**"

            return msg + ":", formatear_dataframe(df), None


        if tipo == "gastos_familias_anio":
            anio = params.get("anio")

            if not anio:
                return "❌ Falta especificar el año.", None, None

            df = get_gastos_todas_familias_anio(anio)

            if df is None or df.empty:
                return f"No encontré gastos en {anio}.", None, None

            total_pesos = df['Total_Pesos'].sum() if 'Total_Pesos' in df.columns else 0
            total_usd = df['Total_USD'].sum() if 'Total_USD' in df.columns else 0

            total_pesos_fmt = f"${total_pesos:,.0f}".replace(',', '.')
            total_usd_fmt = f"U$S {total_usd:,.0f}".replace(',', '.')

            msg = f"📊 Gastos por familia en {anio} | 💰 **{total_pesos_fmt}**"
            if total_usd > 0:
                msg += f" | 💵 **{total_usd_fmt}**"

            return msg + ":", formatear_dataframe(df), None


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

            total = 0
            if 'STOCK' in df.columns:
                try:
                    total = df['STOCK'].apply(
                        lambda x: float(str(x).replace(',', '.').replace(' ', '')) if pd.notna(x) else 0
                    ).sum()
                except:
                    pass

            msg = f"📦 **Stock de '{articulo.upper()}'**"
            if total > 0:
                msg += f" (Total: {total:,.0f} unidades)".replace(',', '.')

            return msg + ":", formatear_dataframe(df), None


        if tipo == "stock_familia":
            familia = params.get("familia")
            if not familia:
                return "❌ ¿De qué familia querés ver el stock?", None, None

            df = get_stock_familia(familia)

            if df is None or df.empty:
                return f"No encontré stock de la familia '{familia}'.", None, None

            return f"📦 **Stock de familia {familia.upper()}:**", formatear_dataframe(df), None


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

            return f"📦 **Lote {lote.upper()}:**", formatear_dataframe(df), None


        # =========================================================
        # TIPO NO RECONOCIDO
        # =========================================================

        return f"❌ Tipo de consulta '{tipo}' no implementado.", None, None

    except Exception as e:
        print(f"❌ Error ejecutando consulta: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ Error: {str(e)[:100]}", None, None


# =====================================================================
# FUNCIÓN DE COMPATIBILIDAD CON SISTEMA ANTERIOR
# =====================================================================

def procesar_pregunta(pregunta: str) -> Tuple[str, Optional[pd.DataFrame]]:
    """
    Función de compatibilidad con el sistema anterior.
    Ignora las sugerencias y solo devuelve mensaje + df.
    """
    mensaje, df, sugerencia = procesar_pregunta_v2(pregunta)

    # Si hay sugerencia, la incluimos en el mensaje
    if sugerencia:
        alternativas = sugerencia.get("alternativas", [])
        if alternativas:
            mensaje += "\n\n**Alternativas:**\n" + "\n".join(f"• {a}" for a in alternativas[:3])

    return mensaje, df


def procesar_pregunta_router(pregunta: str) -> Tuple[str, Optional[pd.DataFrame]]:
    """
    Alias de procesar_pregunta para compatibilidad con ui_compras.py
    """
    return procesar_pregunta(pregunta)


# =====================================================================
# TEST
# =====================================================================

if __name__ == "__main__":
    pruebas = [
        "compras 2025",
        "compras roche enero 2026",
        "ultimo vitek",
        "cuando vino vitek",
        "comparar roche 2024 2025",
        "stock vitek",
        "cuanto gastamos",
        "detalle factura 273279",
        "detalle factura A00273279",
        "todas las facturas roche 2025",
        "todas las facturas roche noviembre 2025",
    ]

    print("=" * 60)
    print("PRUEBAS DEL ORQUESTADOR V2")
    print("=" * 60)

    for p in pruebas:
        print(f"\n📝 Pregunta: {p}")
        msg, df, sug = procesar_pregunta_v2(p)
        print(f"   Mensaje: {msg[:100]}...")
        if df is not None:
            print(f"   DataFrame: {len(df)} filas")
        if sug:
            print(f"   Sugerencia: {sug.get('sugerencia')}")
