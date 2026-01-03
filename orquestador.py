# =========================
# ORQUESTADOR.PY - LÓGICA DE PROCESAMIENTO (COMPLETO)
# =========================

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Tuple, Optional
import re

from config import DEBUG_MODE
from utils_format import formatear_dataframe, df_to_excel, _latam_to_float
from utils_openai import (
    es_saludo_o_conversacion,
    es_pregunta_conocimiento,
    responder_con_openai,
    recomendar_como_preguntar,
    obtener_sugerencia_ejecutable,
    fallback_openai_sql,
)

# Imports de sql_queries
from sql_queries import (
    ejecutar_consulta,
    _sql_fecha_expr,
    _sql_total_num_expr_general,
    get_valores_unicos,
    get_detalle_factura_por_numero,
    get_total_factura_por_numero,
    get_ultima_factura_inteligente,
    get_ultima_factura_numero_de_articulo,
    get_detalle_compras_proveedor_mes,
    get_detalle_compras_proveedor_anio,
    get_total_compras_proveedor_anio,
    get_detalle_compras_proveedor_anios,
    get_detalle_compras_articulo_mes,
    get_detalle_compras_articulo_anio,
    get_total_compras_articulo_anio,
    get_comparacion_articulo_anios,
    get_comparacion_proveedor_meses,
    get_comparacion_articulo_meses,
    get_comparacion_familia_meses_moneda,
    get_comparacion_proveedor_anios_monedas,
    get_comparacion_familia_anios_monedas,
    get_gastos_todas_familias_mes,
    get_gastos_todas_familias_anio,
    get_gastos_secciones_detalle_completo,
    get_gastos_por_familia,
    get_compras_por_mes_excel,
    get_total_compras_proveedor_moneda_periodos,
    get_top_10_proveedores_chatbot,
    get_facturas_de_articulo,
    get_stock_total,
    get_stock_por_familia,
    get_stock_por_deposito,
    get_stock_articulo,
    get_stock_familia,
    get_lotes_por_vencer,
    get_lotes_vencidos,
    get_stock_bajo,
    get_stock_lote_especifico,
    get_detalle_compras,
)

# Placeholder para guardar_chat_log si no existe
def guardar_chat_log(**kwargs):
    """Placeholder - implementar en sql_queries si se necesita logging"""
    pass

from intent_detector import (
    detectar_intencion,
    extraer_valores_multiples,
    extraer_meses_para_comparacion,
    extraer_anios,
    normalizar_texto,
    _extraer_patron_libre,
    _extraer_lista_familias,
    _extraer_mes_key,
    construir_where_clause,
)


def extraer_numero_factura(pregunta: str) -> Optional[str]:
    """Extrae número de factura desde texto."""
    if not pregunta:
        return None

    txt = (pregunta or "").upper()

    # Caso: viene con letra A + ceros opcionales + número
    m = re.search(r"A0*\s*(\d{5,})", txt)
    if m:
        num = m.group(1)
        num = num.lstrip("0") or num
        return num

    # Caso: número suelto (mínimo 5 dígitos)
    m = re.search(r"\b(\d{5,})\b", txt)
    if m:
        num = m.group(1)
        num = num.lstrip("0") or num
        return num

    return None


def normalizar_factura_para_db(nro_raw: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Normaliza número de factura para búsqueda en DB."""
    if not nro_raw:
        return None, None, None

    s = str(nro_raw).strip().upper()
    digits = re.sub(r"\D", "", s)
    if not digits or len(digits) < 5:
        return None, None, None

    nro_mostrar = digits.lstrip("0") or digits

    if len(digits) <= 8:
        nro_db = "A" + digits.zfill(8)
        nro_alt = "A" + digits.zfill(7)
    else:
        nro_db = "A" + digits
        nro_alt = None

    return nro_db, nro_alt, nro_mostrar


def _formatear_detalle_factura_df(df: pd.DataFrame) -> pd.DataFrame:
    """Formatea DataFrame de detalle de factura."""
    if df is None or df.empty:
        return df

    dfx = df.copy()

    if "nro_factura" in dfx.columns:
        dfx["Factura"] = dfx["nro_factura"].astype(str).apply(
            lambda x: (re.sub(r"\D", "", x).lstrip("0") or re.sub(r"\D", "", x) or x)
        )
        dfx = dfx.drop(columns=["nro_factura"])
        cols = ["Factura"] + [c for c in dfx.columns if c != "Factura"]
        dfx = dfx[cols]

    try:
        dfx = formatear_dataframe(dfx)
    except Exception:
        pass

    return dfx


def es_conocimiento_general(pregunta: str) -> bool:
    """Detecta si es pregunta de conocimiento general."""
    txt = (pregunta or "").lower()
    claves = [
        "que es", "qué es", "para que sirve", "para qué sirve",
        "definicion", "definición", "explicame", "explica",
        "que significa", "significa"
    ]
    return any(k in txt for k in claves)


# =========================
# COMPATIBILIDAD: ROUTER → ORQUESTADOR
# =========================

def procesar_pregunta_router(pregunta: str) -> Tuple[str, Optional[pd.DataFrame]]:
    """Alias para compatibilidad."""
    intencion_info = detectar_intencion(pregunta)
    tipo = intencion_info.get('tipo', 'desconocido')
    debug = intencion_info.get('debug', '')

    respuesta, df = procesar_pregunta(pregunta)

    tuvo_datos = df is not None and not df.empty
    registros = len(df) if tuvo_datos else 0

    try:
        guardar_chat_log(
            pregunta=pregunta,
            intencion=tipo,
            respuesta=respuesta[:2000] if respuesta else '',
            tuvo_datos=tuvo_datos,
            registros=registros,
            debug=debug
        )
    except:
        pass

    return respuesta, df


def procesar_pregunta(pregunta: str) -> Tuple[str, Optional[pd.DataFrame]]:
    """
    🎯 ORQUESTADOR PRINCIPAL
    Recibe pregunta → detecta intención → llama SQL → formatea respuesta
    """

    if not pregunta or not pregunta.strip():
        return "Por favor, escribe una pregunta.", None

    print(f"\n{'='*60}")
    print(f"PREGUNTA: {pregunta}")
    print(f"{'='*60}")

    # =====================================================================
    # DETALLE FACTURA (ROBUSTO Y EXACTO)
    # =====================================================================
    nro_raw = extraer_numero_factura(pregunta)

    if nro_raw:
        nro_mostrar = str(nro_raw).strip()
        nro_sql = nro_mostrar

        if nro_sql.isdigit():
            nro_sql = "A" + nro_sql.zfill(7)
        else:
            txt = str(nro_sql).upper().replace(" ", "")
            m = re.search(r"A0*(\d{5,})", txt)
            if m:
                nro_mostrar = m.group(1)
                nro_sql = "A" + m.group(1).zfill(7)

        df = get_detalle_factura_por_numero(nro_sql)

        if df is not None and not df.empty:
            prov = ""
            if "Proveedor" in df.columns:
                try:
                    prov = str(df["Proveedor"].dropna().iloc[0]).strip()
                except Exception:
                    prov = ""

            print(f"🧾 FACTURA EXACTA: {nro_sql}")

            titulo = f"🧾 Detalle de la factura {nro_mostrar}"
            if prov:
                titulo += f" — Proveedor: {prov}"

            return titulo, formatear_dataframe(df)

    # =====================================================================
    # PASO 1: ¿Es saludo/conversación?
    # =====================================================================
    if es_saludo_o_conversacion(pregunta):
        respuesta = responder_con_openai(pregunta, "conversacion")
        print(f"✅ TIPO: Conversación → OpenAI")
        return f"💬 {respuesta}", None

    # =====================================================================
    # PASO 2: ¿Es pregunta de conocimiento?
    # =====================================================================
    if es_pregunta_conocimiento(pregunta):
        respuesta = responder_con_openai(pregunta, "conocimiento")
        print(f"✅ TIPO: Conocimiento → OpenAI")
        return f"📚 {respuesta}", None

    # =====================================================================
    # PASO 3: Detectar intención (REGLAS)
    # =====================================================================
    intencion = detectar_intencion(pregunta)
    tipo = intencion.get('tipo', 'consulta_general')
    params = intencion.get('parametros', {})
    debug = intencion.get('debug', '')

    print(f"🎯 INTENCIÓN: {tipo}")
    print(f"📦 PARÁMETROS: {params}")
    print(f"🔍 DEBUG: {debug}")

    # =====================================================================
    # MANEJO DE INTENCIONES DE STOCK
    # =====================================================================

    if tipo == 'stock_total':
        df = get_stock_total()
        if df is not None and not df.empty:
            return "📦 **Resumen de stock total:**", formatear_dataframe(df)
        return "No pude obtener el stock total.", None

    if tipo == 'stock_por_familia':
        df = get_stock_por_familia()
        if df is not None and not df.empty:
            return "📦 **Stock por familia/sección:**", formatear_dataframe(df)
        return "No encontré datos de stock por familia.", None

    if tipo == 'stock_familia':
        familia = params.get('familia', '')
        df = get_stock_familia(familia)
        if df is not None and not df.empty:
            return f"📦 **Stock de la familia {familia}:**", formatear_dataframe(df)
        return f"No encontré stock para la familia {familia}.", None

    if tipo == 'stock_por_deposito':
        df = get_stock_por_deposito()
        if df is not None and not df.empty:
            return "📦 **Stock por depósito:**", formatear_dataframe(df)
        return "No encontré datos de stock por depósito.", None

    if tipo == 'stock_articulo':
        articulo = params.get('articulo', '')
        df = get_stock_articulo(articulo)
        if df is not None and not df.empty:
            total = 0
            if 'STOCK' in df.columns:
                try:
                    total = df['STOCK'].apply(
                        lambda x: float(str(x).replace(',', '.').replace(' ', '')) if pd.notna(x) else 0
                    ).sum()
                except:
                    pass
            msg = f"📦 **Stock de '{articulo}':**"
            if total > 0:
                msg += f" (Total: {total:,.0f} unidades)".replace(',', '.')
            return msg, formatear_dataframe(df)
        return f"No encontré stock para '{articulo}'.", None

    if tipo == 'stock_lotes_por_vencer':
        dias = params.get('dias', 90)
        df = get_lotes_por_vencer(dias)
        if df is not None and not df.empty:
            return f"⚠️ **Lotes que vencen en los próximos {dias} días:**", formatear_dataframe(df)
        return f"No hay lotes que venzan en los próximos {dias} días.", None

    if tipo == 'stock_lotes_vencidos':
        df = get_lotes_vencidos()
        if df is not None and not df.empty:
            return "🚨 **Lotes VENCIDOS:**", formatear_dataframe(df)
        return "No hay lotes vencidos con stock.", None

    if tipo == 'stock_bajo':
        df = get_stock_bajo(10)
        if df is not None and not df.empty:
            return "📉 **Artículos con stock bajo (≤10 unidades):**", formatear_dataframe(df)
        return "No hay artículos con stock bajo.", None

    if tipo == 'stock_lote_especifico':
        lote = params.get('lote', '')
        df = get_stock_lote_especifico(lote)
        if df is not None and not df.empty:
            return f"📦 **Información del lote {lote}:**", formatear_dataframe(df)
        return f"No encontré el lote {lote}.", None

    # =====================================================================
    # CONOCIMIENTO GENERAL (NO SQL)
    # =====================================================================
    if es_conocimiento_general(pregunta):
        respuesta = responder_con_openai(pregunta, tipo="conocimiento")
        return respuesta, None

    # =====================================================================
    # LISTAR VALORES
    # =====================================================================
    if tipo == 'listar_valores':
        valores = get_valores_unicos()
        if valores:
            texto_resp = "**Valores disponibles en la base de datos:**\n\n"

            if valores.get('proveedores'):
                texto_resp += f"**Proveedores ({len(valores['proveedores'])}):**\n"
                texto_resp += ", ".join(valores['proveedores'][:20])
                if len(valores['proveedores']) > 20:
                    texto_resp += f" ... y {len(valores['proveedores']) - 20} más"
                texto_resp += "\n\n"

            if valores.get('familias'):
                texto_resp += f"**Familias ({len(valores['familias'])}):**\n"
                texto_resp += ", ".join(valores['familias'])
                texto_resp += "\n\n"

            if valores.get('articulos'):
                texto_resp += "**Artículos (primeros 50):**\n"
                texto_resp += ", ".join(valores['articulos'])

            return texto_resp, None
        return "No se pudo obtener la lista de valores.", None

    # =====================================================================
    # FACTURA POR NÚMERO
    # =====================================================================
    if tipo == 'detalle_factura_numero':
        nro_raw = params.get("nro_factura", "")
        nro_db, nro_alt, nro_mostrar = normalizar_factura_para_db(nro_raw)
        if not nro_db:
            return "No pude identificar el número de factura.", None

        print(f"✅ TIPO: Detalle Factura → SQL (Factura {nro_mostrar})")

        df = get_detalle_factura_por_numero(nro_db)

        if (df is None or df.empty) and nro_alt and (nro_alt != nro_db):
            df = get_detalle_factura_por_numero(nro_alt)

        if df is None or df.empty:
            return f"No encontré detalle para la factura {nro_mostrar}.", None

        return f"🧾 Detalle de la factura {nro_mostrar}", _formatear_detalle_factura_df(df)

    # =====================================================================
    # FACTURA COMPLETA ARTÍCULO
    # =====================================================================
    if tipo == 'factura_completa_articulo':
        articulos = extraer_valores_multiples(pregunta, 'articulo')
        patron = articulos[0] if articulos else _extraer_patron_libre(
            pregunta,
            ['ultima', 'factura', 'articulo', 'completa', 'toda', 'todo', 'traer', 'mostrar', 'ver', 'detalle', 'de', 'del', 'la', 'el', 'por', 'para']
        )

        if not patron:
            return "¿De qué artículo querés la factura completa?", None

        nro = get_ultima_factura_numero_de_articulo(patron)
        if not nro:
            titulo, df2, resp2 = fallback_openai_sql(pregunta, "No pudo obtener factura completa")
            if df2 is not None and not df2.empty:
                return f"🧾 {resp2 or titulo}", formatear_dataframe(df2)
            return "No pude obtener la factura completa.", None

        df = get_detalle_factura_por_numero(nro)
        df_tot = get_total_factura_por_numero(nro)

        if not df_tot.empty and 'total_factura' in df_tot.columns:
            try:
                total = float(df_tot['total_factura'].iloc[0])
                return f"🧾 Factura completa (nro {nro}) — Total: ${total:,.2f}", formatear_dataframe(df)
            except Exception:
                pass

        return f"🧾 Factura completa (nro {nro}):", formatear_dataframe(df)

    # =====================================================================
    # ÚLTIMA FACTURA (ARTÍCULO O PROVEEDOR)
    # =====================================================================
    if tipo == 'ultima_factura_articulo':
        articulos = extraer_valores_multiples(pregunta, 'articulo')
        proveedores = extraer_valores_multiples(pregunta, 'proveedor')

        if articulos:
            patron = articulos[0]
        elif proveedores:
            patron = proveedores[0]
        else:
            patron = _extraer_patron_libre(
                pregunta,
                [
                    'ultima', 'ultimo', 'ultim', 'factura', 'facturas',
                    'articulo', 'articulos', 'proveedor', 'proveedores',
                    'compras', 'compra', 'compre', 'compramos', 'comprado',
                    'traer', 'mostrar', 'ver', 'dame', 'pasame', 'mostrame',
                    'necesito', 'quiero', 'buscar', 'busco',
                    'cuando', 'vino', 'llego', 'entro', 'fue', 'paso',
                    'completa', 'toda', 'todo', 'todos', 'todas', 'entera',
                    'de', 'del', 'la', 'el', 'los', 'las', 'un', 'una',
                    'por', 'para', 'en', 'a', 'con', 'sin'
                ]
            )

        if not patron:
            return "¿De qué artículo o proveedor querés la última factura?", None

        df = get_ultima_factura_inteligente(patron)

        if df.empty:
            titulo, df2, resp2 = fallback_openai_sql(pregunta, "No encontró última factura")
            if df2 is not None and not df2.empty:
                return f"🧾 {resp2 or titulo}", formatear_dataframe(df2)
            return f"No encontré facturas con '{patron}' en artículos ni proveedores.", None

        return "🧾 Última factura encontrada:", formatear_dataframe(df)

    # =====================================================================
    # ✅ NUEVO: TODAS LAS FACTURAS DE UN ARTÍCULO
    # =====================================================================
    if tipo == 'facturas_articulo':
        articulos = extraer_valores_multiples(pregunta, 'articulo')
        patron = articulos[0] if articulos else _extraer_patron_libre(
            pregunta,
            ['facturas', 'factura', 'listar', 'todas', 'articulo', 'de', 'del', 'la', 'el', 'cuando', 'vino']
        )

        if not patron:
            return "¿De qué artículo querés ver las facturas?", None

        df = get_facturas_de_articulo(patron, solo_ultima=False)

        if df is None or df.empty:
            return f"No encontré facturas para '{patron}'.", None

        return f"🧾 Facturas del artículo '{patron}' ({len(df)} registros):", formatear_dataframe(df)

    # =====================================================================
    # GASTOS SECCIONES
    # =====================================================================
    if tipo == 'gastos_secciones':
        familias = _extraer_lista_familias(pregunta)
        mes_key = _extraer_mes_key(pregunta)

        anio = None
        if not mes_key:
            match = re.search(r'(202[3-9]|2030)', pregunta)
            if match:
                anio = int(match.group(1))

        if not mes_key and not anio:
            return "Especificá el mes o año (ej: 'gastos familias noviembre 2025').", None

        if not familias:
            if mes_key:
                df = get_gastos_todas_familias_mes(mes_key)
                periodo = mes_key
            else:
                df = get_gastos_todas_familias_anio(anio)
                periodo = str(anio)

            if df is None or df.empty:
                titulo, df2, resp2 = fallback_openai_sql(pregunta, "No encontró gastos por familias")
                if df2 is not None and not df2.empty:
                    return f"📌 {resp2 or titulo}", formatear_dataframe(df2)
                return f"No encontré gastos para {periodo}.", None

            def latam_to_float(valor):
                if pd.isna(valor):
                    return 0.0
                try:
                    s = str(valor).strip()
                    s = s.replace('.', '').replace(',', '.')
                    return float(s)
                except:
                    return 0.0

            col_pesos = None
            col_usd = None
            for col in df.columns:
                col_lower = col.lower()
                if 'pesos' in col_lower:
                    col_pesos = col
                if 'usd' in col_lower:
                    col_usd = col

            total_pesos = 0
            total_usd = 0

            if col_pesos:
                total_pesos = df[col_pesos].apply(latam_to_float).sum()
            if col_usd:
                total_usd = df[col_usd].apply(latam_to_float).sum()

            total_pesos_fmt = f"${total_pesos:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            total_usd_fmt = f"U$S {total_usd:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

            return f"📊 Gastos por familia en {periodo} | 💰 **{total_pesos_fmt}** | 💵 **{total_usd_fmt}**:", formatear_dataframe(df)

        if not mes_key:
            return "Para familias específicas necesito el mes.", None

        df = get_gastos_secciones_detalle_completo(familias, mes_key)
        if df.empty:
            return "No encontré gastos para esas secciones.", None

        return f"📌 Gastos de familias {', '.join(familias)} en {mes_key}:", formatear_dataframe(df)

    # =====================================================================
    # ✅ NUEVO: COMPARAR PROVEEDOR MESES
    # =====================================================================
    if tipo == 'comparar_proveedor_meses':
        meses = params.get('meses', [])
        proveedores = params.get('proveedores', [])

        # Si no hay meses en params, extraer de pregunta
        if len(meses) < 2:
            meses_detectados = extraer_meses_para_comparacion(pregunta)
            meses = [m[2] for m in meses_detectados]  # m[2] es el mes_key

        if len(meses) < 2:
            return "Necesito dos meses para comparar (ej: 'comparar roche junio julio 2025').", None

        mes1, mes2 = meses[0], meses[1]

        # Si no hay proveedores, extraer de pregunta
        if not proveedores:
            proveedores = extraer_valores_multiples(pregunta, 'proveedor')
        if not proveedores:
            prov_libre = _extraer_patron_libre(pregunta, [
                'comparar', 'comparame', 'compara', 'comparacion', 'vs',
                'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
                '2023', '2024', '2025', '2026', 'compras', 'proveedor', 'proveedores'
            ])
            if prov_libre:
                proveedores = [prov_libre]

        df = get_comparacion_proveedor_meses(mes1, mes2, mes1, mes2, proveedores if proveedores else None)

        if df is None or df.empty:
            prov_str = ', '.join(proveedores) if proveedores else 'proveedores'
            return f"No encontré datos para comparar {prov_str} entre {mes1} y {mes2}.", None

        prov_str = ', '.join(proveedores).upper() if proveedores else 'Proveedores'
        return f"📊 Comparación de {prov_str}: {mes1} vs {mes2}:", formatear_dataframe(df)

    # =====================================================================
    # ✅ NUEVO: COMPARAR ARTÍCULO MESES
    # =====================================================================
    if tipo == 'comparar_articulo_meses':
        meses = params.get('meses', [])
        articulo = params.get('articulo_like', '')

        if len(meses) < 2:
            meses_detectados = extraer_meses_para_comparacion(pregunta)
            meses = [m[2] for m in meses_detectados]

        if len(meses) < 2:
            return "Necesito dos meses para comparar.", None

        mes1, mes2 = meses[0], meses[1]

        if not articulo:
            articulos = extraer_valores_multiples(pregunta, 'articulo')
            articulo = articulos[0] if articulos else _extraer_patron_libre(pregunta, [
                'comparar', 'comparame', 'vs', 'enero', 'febrero', 'marzo', 'abril',
                'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
                'noviembre', 'diciembre', '2023', '2024', '2025', '2026'
            ])

        df = get_comparacion_articulo_meses(mes1, mes2, mes1, mes2, [articulo] if articulo else None)

        if df is None or df.empty:
            return f"No encontré datos para comparar '{articulo}' entre {mes1} y {mes2}.", None

        return f"📊 Comparación de {articulo.upper()}: {mes1} vs {mes2}:", formatear_dataframe(df)

    # =====================================================================
    # COMPARAR FAMILIA MESES
    # =====================================================================
    if tipo == 'comparar_familia_meses':
        meses_params = params.get("meses", [])
        familias = params.get("familias")

        mes1 = None
        mes2 = None

        if meses_params and len(meses_params) >= 2:
            mes1, mes2 = meses_params[0], meses_params[1]

        if not mes1 or not mes2:
            meses_detectados = extraer_meses_para_comparacion(pregunta)
            if len(meses_detectados) >= 2:
                mes1 = meses_detectados[0][2]
                mes2 = meses_detectados[1][2]

        if not mes1 or not mes2:
            return "No pude identificar los dos meses a comparar.", None

        df_pesos = get_comparacion_familia_meses_moneda(mes1, mes2, mes1, mes2, "$", familias)
        df_usd = get_comparacion_familia_meses_moneda(mes1, mes2, mes1, mes2, "U$S", familias)

        if (df_pesos is None or df_pesos.empty) and (df_usd is None or df_usd.empty):
            return f"No hay datos para comparar familias entre {mes1} y {mes2}.", None

        st.session_state['comparacion_familia_tabs'] = {
            'titulo': f"📊 Comparación de gastos por familia: {mes1} vs {mes2}",
            'df_pesos': df_pesos,
            'df_usd': df_usd,
            'mes1': mes1,
            'mes2': mes2
        }

        return "__COMPARACION_FAMILIA_TABS__", None

    # =====================================================================
    # ✅ NUEVO: COMPARAR PROVEEDOR AÑOS
    # =====================================================================
    if tipo == 'comparar_proveedor_anios':
        anios = params.get('anios', [])
        proveedores = params.get('proveedores', [])

        if not anios:
            anios = extraer_anios(pregunta)

        if len(anios) < 2:
            return "Necesito al menos dos años para comparar.", None

        if not proveedores:
            proveedores = extraer_valores_multiples(pregunta, 'proveedor')
        if not proveedores:
            prov_libre = _extraer_patron_libre(pregunta, [
                'comparar', 'comparame', 'compara', 'vs', 'compras',
                '2023', '2024', '2025', '2026', 'proveedor', 'proveedores', 'años', 'anios'
            ])
            if prov_libre:
                proveedores = [prov_libre]

        df_resumen = get_comparacion_proveedor_anios_monedas(anios, proveedores if proveedores else None)

        if df_resumen is None or df_resumen.empty:
            return f"No encontré datos para comparar proveedores en años {anios}.", None

        df_detalle = get_detalle_compras_proveedor_anios(anios, proveedores if proveedores else None)

        st.session_state['comparacion_tabs'] = {
            'resumen': formatear_dataframe(df_resumen),
            'detalle': formatear_dataframe(df_detalle) if df_detalle is not None and not df_detalle.empty else None,
            'titulo': f"🏭 Comparación {', '.join(proveedores) if proveedores else 'proveedores'} ({', '.join(map(str, sorted(anios)))})"
        }

        return "__COMPARACION_TABS__", None

    # =====================================================================
    # ✅ NUEVO: COMPARAR FAMILIA AÑOS
    # =====================================================================
    if tipo == 'comparar_familia_anios':
        anios = params.get('anios', [])
        familias = params.get('familias')
        moneda = params.get('moneda')

        if not anios:
            anios = extraer_anios(pregunta)

        if len(anios) < 2:
            return "Necesito al menos dos años para comparar.", None

        df = get_comparacion_familia_anios_monedas(anios, familias if familias else None)

        if df is None or df.empty:
            return f"No encontré datos para comparar familias en años {anios}.", None

        return f"📊 Comparación de familias ({', '.join(map(str, sorted(anios)))}):", formatear_dataframe(df)

    # =====================================================================
    # COMPARAR PROVEEDOR AÑOS MONEDAS (existente)
    # =====================================================================
    if tipo == 'comparar_proveedor_anios_monedas':
        anios = params.get('anios') or extraer_anios(pregunta)
        proveedores = params.get('proveedores') or extraer_valores_multiples(pregunta, 'proveedor')

        if isinstance(proveedores, str):
            proveedores = [proveedores]

        if proveedores:
            proveedores = [p.strip() for p in proveedores if p and str(p).strip()]

        if not proveedores:
            txt = normalizar_texto(pregunta or "")
            txt = re.sub(r"\b20\d{2}\b", " ", txt)
            for w in ["comparar", "comparacion", "compras", "compra", "vs", "proveedor", "proveedores", "por"]:
                txt = txt.replace(w, " ")
            prov_libre = " ".join([t for t in txt.split() if t]).strip()
            if prov_libre:
                proveedores = [prov_libre]

        df_resumen = get_comparacion_proveedor_anios_monedas(anios, proveedores if proveedores else None)
        if df_resumen.empty:
            titulo, df2, resp2 = fallback_openai_sql(pregunta, "No encontró comparación proveedor por años")
            if df2 is not None and not df2.empty:
                return f"📊 {resp2 or titulo}", formatear_dataframe(df2)
            return "No encontré datos para comparar proveedores por años.", None

        df_detalle = get_detalle_compras_proveedor_anios(anios, proveedores if proveedores else None)

        st.session_state['comparacion_tabs'] = {
            'resumen': formatear_dataframe(df_resumen),
            'detalle': formatear_dataframe(df_detalle) if df_detalle is not None and not df_detalle.empty else None,
            'titulo': f"🏭 Comparación {', '.join(proveedores) if proveedores else 'proveedores'} ({', '.join(map(str, sorted(anios)))})"
        }

        return "__COMPARACION_TABS__", None

    # =====================================================================
    # COMPARAR ARTÍCULO AÑOS
    # =====================================================================
    if tipo == 'comparar_articulo_anios':
        anios = params.get("anios", [])
        articulo_like = params.get("articulo_like", "")

        if not anios:
            anios = extraer_anios(pregunta)

        if not articulo_like:
            articulos = extraer_valores_multiples(pregunta, 'articulo')
            articulo_like = articulos[0] if articulos else _extraer_patron_libre(pregunta, [
                'comparar', 'comparame', 'vs', '2023', '2024', '2025', '2026', 'compras', 'articulo'
            ])

        df = get_comparacion_articulo_anios(anios, articulo_like)

        if df is None or df.empty:
            return f"No encontré compras del artículo '{articulo_like}' en los años {anios}.", None

        totales_por_anio = []
        for anio in sorted(anios):
            col_anio = str(anio)
            if col_anio in df.columns:
                total = df[col_anio].sum()
                total_fmt = f"${total:,.0f}".replace(',', '.')
                totales_por_anio.append(f"**{anio}**: {total_fmt}")

        totales_str = " | ".join(totales_por_anio) if totales_por_anio else ""

        return f"📊 Comparación del artículo **{articulo_like.upper()}** | {totales_str}:", formatear_dataframe(df)

    # =====================================================================
    # COMPRAS POR MES
    # =====================================================================
    if tipo == 'compras_por_mes':
        mes_key = _extraer_mes_key(pregunta)
        if not mes_key:
            return "Especificá el mes (ej: 'compras junio 2025').", None

        df = get_compras_por_mes_excel(mes_key)
        if df.empty:
            return "No encontré compras para ese mes.", None

        return "📦 Compras por mes:", formatear_dataframe(df)

    # =====================================================================
    # DETALLE COMPRAS PROVEEDOR + MES
    # =====================================================================
    if tipo == 'detalle_compras_proveedor_mes':
        mes_key = params.get('mes_key')
        proveedor_like = params.get('proveedor_like')

        df = get_detalle_compras_proveedor_mes(proveedor_like, mes_key)

        if df.empty:
            titulo, df2, resp2 = fallback_openai_sql(pregunta, "No encontró detalle proveedor + mes")
            if df2 is not None and not df2.empty:
                return f"📋 {resp2 or titulo}", formatear_dataframe(df2)
            return "No encontré compras para ese proveedor y mes.", None

        total = 0
        if 'total' in df.columns:
            total = pd.to_numeric(df['total'], errors='coerce').fillna(0).sum()

        total_fmt = f"${total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

        return (
            f"📋 Compras de {proveedor_like.upper()} en {mes_key} "
            f"| 💰 **Total: {total_fmt}** | {len(df)} registros:",
            formatear_dataframe(df)
        )

    # =====================================================================
    # DETALLE COMPRAS ARTÍCULO + MES
    # =====================================================================
    if tipo == 'detalle_compras_articulo_mes':
        mes_key = params.get("mes_key")
        articulo_like = params.get("articulo_like")

        df = get_detalle_compras_articulo_mes(articulo_like, mes_key)

        if df is None or df.empty:
            titulo, df2, resp2 = fallback_openai_sql(pregunta, "No encontró compras por artículo + mes")
            if df2 is not None and not df2.empty:
                return f"📋 {resp2 or titulo}", formatear_dataframe(df2)
            return f"No encontré compras del artículo '{articulo_like}' en {mes_key}.", None

        totales_str = ""
        if 'Total' in df.columns and 'Moneda' in df.columns:
            for moneda in df['Moneda'].unique():
                df_moneda = df[df['Moneda'] == moneda]
                total_moneda = df_moneda['Total'].sum()
                if moneda in ['U$S', 'USD', 'Dólares', 'Dolares']:
                    totales_str += f"💵 **U$S {total_moneda:,.2f}** ".replace(',', 'X').replace('.', ',').replace('X', '.')
                else:
                    totales_str += f"💰 **${total_moneda:,.2f}** ".replace(',', 'X').replace('.', ',').replace('X', '.')
        else:
            total = df['Total'].sum() if 'Total' in df.columns else 0
            totales_str = f"💰 **${total:,.2f}**".replace(',', 'X').replace('.', ',').replace('X', '.')

        return (
            f"📦 Compras del artículo **{articulo_like.upper()}** en {mes_key} "
            f"| {totales_str}| {len(df)} registros:",
            formatear_dataframe(df)
        )

    # =====================================================================
    # DETALLE COMPRAS ARTÍCULO + AÑO
    # =====================================================================
    if tipo == 'detalle_compras_articulo_anio':
        anio = params.get("anio")
        articulo_like = params.get("articulo_like")

        df = get_detalle_compras_articulo_anio(articulo_like, anio)

        if df is None or df.empty:
            titulo, df2, resp2 = fallback_openai_sql(pregunta, "No encontró compras por artículo + año")
            if df2 is not None and not df2.empty:
                return f"📋 {resp2 or titulo}", formatear_dataframe(df2)
            return f"No encontré compras para el artículo '{articulo_like}' en {anio}.", None

        totales_str = ""
        if 'Total' in df.columns and 'Moneda' in df.columns:
            for moneda in df['Moneda'].unique():
                df_moneda = df[df['Moneda'] == moneda]
                total_moneda = df_moneda['Total'].sum()
                if moneda in ['U$S', 'USD', 'Dólares', 'Dolares']:
                    totales_str += f"💵 **U$S {total_moneda:,.0f}** ".replace(',', '.')
                else:
                    totales_str += f"💰 **${total_moneda:,.0f}** ".replace(',', '.')
        else:
            total = df['Total'].sum() if 'Total' in df.columns else 0
            totales_str = f"💰 **${total:,.0f}**".replace(',', '.')

        return (
            f"📦 Compras del artículo **{articulo_like.upper()}** en {anio} "
            f"| {totales_str}| {len(df)} registros:",
            formatear_dataframe(df)
        )

    # =====================================================================
    # DETALLE COMPRAS PROVEEDOR + AÑO
    # =====================================================================
    if tipo == 'detalle_compras_proveedor_anio':
        anio = params.get('anio')
        proveedor_like = params.get('proveedor_like')

        totales = get_total_compras_proveedor_anio(proveedor_like, anio)
        total_real = totales.get('total', 0)
        registros_total = totales.get('registros', 0)

        df = get_detalle_compras_proveedor_anio(proveedor_like, anio)
        if df is None or df.empty:
            # Reintentar como ARTÍCULO
            totales_alt = get_total_compras_articulo_anio(proveedor_like, anio)
            total_real_alt = totales_alt.get('total', 0)
            registros_total_alt = totales_alt.get('registros', 0)

            df_alt = get_detalle_compras_articulo_anio(proveedor_like, anio)
            if df_alt is not None and not df_alt.empty:
                total_fmt_alt = f"${total_real_alt:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                if registros_total_alt > len(df_alt):
                    return (
                        f"📦 Compras del artículo **{proveedor_like.upper()}** en {anio} "
                        f"| 💰 **Total: {total_fmt_alt}** | {registros_total_alt} registros "
                        f"(mostrando {len(df_alt)}):",
                        formatear_dataframe(df_alt)
                    )
                return (
                    f"📦 Compras del artículo **{proveedor_like.upper()}** en {anio} "
                    f"| 💰 **Total: {total_fmt_alt}** | {len(df_alt)} registros:",
                    formatear_dataframe(df_alt)
                )

            titulo, df2, resp2 = fallback_openai_sql(pregunta, "No encontró detalle proveedor + año")
            if df2 is not None and not df2.empty:
                return f"📋 {resp2 or titulo}", formatear_dataframe(df2)
            return "No encontré compras para ese proveedor y año.", None

        total_fmt = f"${total_real:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

        if registros_total > len(df):
            return (
                f"📋 Compras de {proveedor_like.upper()} en {anio} | 💰 **Total: {total_fmt}** "
                f"| {registros_total} registros (mostrando {len(df)}):",
                formatear_dataframe(df)
            )

        return (
            f"📋 Compras de {proveedor_like.upper()} en {anio} | 💰 **Total: {total_fmt}** | {len(df)} registros:",
            formatear_dataframe(df)
        )

    # =====================================================================
    # TOTAL PROVEEDOR + MONEDA + PERÍODOS
    # =====================================================================
    if tipo == 'total_proveedor_moneda_periodos':
        periodos = params.get('periodos', [])
        monedas = params.get('monedas')

        df = get_total_compras_proveedor_moneda_periodos(periodos, monedas)
        if df is None or df.empty:
            return "No encontré compras por proveedor para esos períodos.", None

        return "🏭 Total compras por proveedor (por período y moneda):", formatear_dataframe(df)

    # =====================================================================
    # TOP 10 PROVEEDORES
    # =====================================================================
    if tipo == 'top_10_proveedores':
        moneda = params.get("moneda")
        anio = params.get("anio")
        mes = params.get("mes")

        df = get_top_10_proveedores_chatbot(moneda, anio, mes)

        if df is None or df.empty:
            return "No encontré proveedores con compras registradas.", None

        titulo = "🏆 Top 10 Proveedores"
        if moneda:
            titulo += f" ({moneda})"
        if mes:
            titulo += f" {mes}"
        elif anio:
            titulo += f" {anio}"

        return titulo + ":", formatear_dataframe(df)

    # =====================================================================
    # GASTOS POR FAMILIA
    # =====================================================================
    if tipo == 'gastos_familia':
        where_clause, params_sql = construir_where_clause(pregunta)
        df = get_gastos_por_familia(where_clause, params_sql)

        if df.empty:
            return "No encontré gastos por familia.", None

        return "📊 Gastos por familia:", formatear_dataframe(df)

    # =====================================================================
    # DETALLE GENERAL
    # =====================================================================
    if tipo == 'detalle':
        where_clause, params_sql = construir_where_clause(pregunta)
        df = get_detalle_compras(where_clause, params_sql)

        if df.empty:
            return "No encontré detalle para esa consulta.", None

        return "📋 Detalle de compras:", formatear_dataframe(df)

    # =====================================================================
    # CONSULTA GENERAL (FALLBACK)
    # =====================================================================
    texto_lower = normalizar_texto(pregunta)

    saludos = ['hola', 'buenos dias', 'buenas tardes', 'buenas noches', 'gracias', 'chau', 'adios']
    es_saludo = any(s in texto_lower for s in saludos) and len(texto_lower.split()) <= 3

    if es_saludo:
        return "👋 ¡Hola! ¿En qué te puedo ayudar?", None

    return "__MOSTRAR_SUGERENCIA__", None
