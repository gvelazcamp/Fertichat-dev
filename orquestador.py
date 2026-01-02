# =========================
# ORQUESTADOR.PY - LÓGICA DE PROCESAMIENTO
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
    guardar_chat_log,
)

from intent_detector import (
    detectar_intencion,
    extraer_valores_multiples,
    extraer_meses_para_comparacion,
    normalizar_texto,
    _extraer_patron_libre,
    _extraer_lista_familias,
    _extraer_mes_key,
)

def extraer_numero_factura(pregunta: str) -> Optional[str]:
    """Extrae número de factura desde texto.
    - Soporta: 'detalle factura 275217', 'factura A00275217', 'A00 275217', etc.
    - Devuelve SOLO dígitos (sin 'A', sin ceros a la izquierda).
    """
    if not pregunta:
        return None

    txt = (pregunta or "").upper()

    # Caso: viene con letra A + ceros opcionales + número (con o sin espacios)
    m = re.search(r"A0*\s*(\d{5,})", txt)
    if m:
        num = m.group(1)
        num = num.lstrip("0") or num
        return num

    # Caso: número suelto (mínimo 5 dígitos) separado por espacios/puntuación
    m = re.search(r"\b(\d{5,})\b", txt)
    if m:
        num = m.group(1)
        num = num.lstrip("0") or num
        return num

    return None


def normalizar_factura_para_db(nro_raw: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Devuelve:
    - nro_db: formato para buscar en DB (ej: A00275217)
    - nro_alt: formato alternativo (ej: A0275217) por si hay otra carga histórica
    - nro_mostrar: número limpio para mostrar al usuario (ej: 275217)
    """
    if not nro_raw:
        return None, None, None

    s = str(nro_raw).strip().upper()

    # Extraer sólo dígitos (por si viene 'A00275217' o con guiones)
    digits = re.sub(r"\D", "", s)
    if not digits or len(digits) < 5:
        return None, None, None

    nro_mostrar = digits.lstrip("0") or digits

    # Formato principal: A + 8 dígitos (lo que tenés en tu DB: A00xxxxxx)
    if len(digits) <= 8:
        nro_db = "A" + digits.zfill(8)
        # Alternativo (viejo): A + 7 dígitos
        nro_alt = "A" + digits.zfill(7)
    else:
        nro_db = "A" + digits
        nro_alt = None

    return nro_db, nro_alt, nro_mostrar


def _formatear_detalle_factura_df(df: pd.DataFrame) -> pd.DataFrame:
    """Para que no muestre 'A00...' y devuelva tabla prolija."""
    if df is None or df.empty:
        return df

    dfx = df.copy()

    # Reemplazar nro_factura por número limpio
    if "nro_factura" in dfx.columns:
        dfx["Factura"] = dfx["nro_factura"].astype(str).apply(
            lambda x: (re.sub(r"\D", "", x).lstrip("0") or re.sub(r"\D", "", x) or x)
        )
        dfx = dfx.drop(columns=["nro_factura"])

        # Poner 'Factura' primera
        cols = ["Factura"] + [c for c in dfx.columns if c != "Factura"]
        dfx = dfx[cols]

    # Mantener tu formateo actual (monto, etc.)
    try:
        dfx = formatear_dataframe(dfx)
    except Exception:
        pass

    return dfx

def es_conocimiento_general(pregunta: str) -> bool:
    """
    Devuelve True si la pregunta es de conocimiento general
    y NO debería ir a SQL.
    """
    txt = (pregunta or "").lower()

    # Palabras típicas de conocimiento general
    claves = [
        "que es", "qué es", "para que sirve", "para qué sirve",
        "definicion", "definición", "explicame", "explica",
        "que significa", "significa"
    ]

    return any(k in txt for k in claves)

# =========================
# COMPATIBILIDAD: ROUTER (nombre antiguo) → ORQUESTADOR
# =========================

def procesar_pregunta_router(pregunta: str) -> Tuple[str, Optional[pd.DataFrame]]:
    """
    Alias para mantener compatibilidad con el menú/UI.
    Antes el código llamaba a `procesar_pregunta_router()`,
    pero el orquestador real se llama `procesar_pregunta()`.
    Ahora también guarda log de cada pregunta/respuesta.
    """
    # Detectar intención para el log
    intencion_info = detectar_intencion(pregunta)
    tipo = intencion_info.get('tipo', 'desconocido')
    debug = intencion_info.get('debug', '')

    # Procesar la pregunta
    respuesta, df = procesar_pregunta(pregunta)

    # Guardar log
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
        pass  # Si falla el log, no afecta la app

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
        # ...

        # Normalizar a A00XXXXXX (7 dígitos)
        if nro_sql.isdigit():
            nro_sql = "A" + nro_sql.zfill(7)
        else:
            # Si vino tipo A00275217, extraemos los dígitos y normalizamos igual
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

            return (
                titulo,
                formatear_dataframe(df)
            )

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
    # ✅ NUEVO: MANEJO DE INTENCIONES DE STOCK
    # =====================================================================

    # --- STOCK TOTAL ---
    if tipo == 'stock_total':
        df = get_stock_total()
        if df is not None and not df.empty:
            return "📦 **Resumen de stock total:**", formatear_dataframe(df)
        return "No pude obtener el stock total. Verificá la conexión a la tabla de stock.", None

    # --- STOCK POR FAMILIA ---
    if tipo == 'stock_por_familia':
        df = get_stock_por_familia()
        if df is not None and not df.empty:
            return "📦 **Stock por familia/sección:**", formatear_dataframe(df)
        return "No encontré datos de stock por familia.", None

    # --- STOCK FAMILIA ESPECÍFICA ---
    if tipo == 'stock_familia':
        familia = params.get('familia', '')
        df = get_stock_familia(familia)
        if df is not None and not df.empty:
            return f"📦 **Stock de la familia {familia}:**", formatear_dataframe(df)
        return f"No encontré stock para la familia {familia}.", None

    # --- STOCK POR DEPÓSITO ---
    if tipo == 'stock_por_deposito':
        df = get_stock_por_deposito()
        if df is not None and not df.empty:
            return "📦 **Stock por depósito:**", formatear_dataframe(df)
        return "No encontré datos de stock por depósito.", None

    # --- STOCK DE ARTÍCULO ---
    if tipo == 'stock_articulo':
        articulo = params.get('articulo', '')
        df = get_stock_articulo(articulo)
        if df is not None and not df.empty:
            # Calcular total
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
        return f"No encontré stock para '{articulo}'. Probá con otro término.", None

    # --- LOTES POR VENCER ---
    if tipo == 'stock_lotes_por_vencer':
        dias = params.get('dias', 90)
        df = get_lotes_por_vencer(dias)
        if df is not None and not df.empty:
            return f"⚠️ **Lotes que vencen en los próximos {dias} días:**", formatear_dataframe(df)
        return f"No hay lotes que venzan en los próximos {dias} días.", None

    # --- LOTES VENCIDOS ---
    if tipo == 'stock_lotes_vencidos':
        df = get_lotes_vencidos()
        if df is not None and not df.empty:
            return "🚨 **Lotes VENCIDOS:**", formatear_dataframe(df)
        return "No hay lotes vencidos con stock.", None

    # --- STOCK BAJO ---
    if tipo == 'stock_bajo':
        df = get_stock_bajo(10)
        if df is not None and not df.empty:
            return "📉 **Artículos con stock bajo (≤10 unidades):**", formatear_dataframe(df)
        return "No hay artículos con stock bajo.", None

    # --- LOTE ESPECÍFICO ---
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
    # PASO 4: Ejecutar SQL según intención (ORDEN DE PRIORIDAD)
    # =====================================================================

    df = None
    titulo = "Resultado"

    # --- PRIORIDAD 1: LISTAR VALORES ---
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

    # --- PRIORIDAD 2: FACTURA POR NÚMERO ---
    elif tipo == 'detalle_factura_numero':
        nro_raw = params.get("nro_factura", "")

        nro_db, nro_alt, nro_mostrar = normalizar_factura_para_db(nro_raw)
        if not nro_db:
            return ("No pude identificar el número de factura.", None)

        print(f"✅ TIPO: Detalle Factura → SQL (Factura {nro_mostrar})")

        df = get_detalle_factura_por_numero(nro_db)

        # Fallback por si existe otra carga histórica (A + 7 dígitos)
        if (df is None or df.empty) and nro_alt and (nro_alt != nro_db):
            df = get_detalle_factura_por_numero(nro_alt)

        if df is None or df.empty:
            return (f"No encontré detalle para la factura {nro_mostrar}.", None)

        return (f"🧾 Detalle de la factura {nro_mostrar}", _formatear_detalle_factura_df(df))

        # =========================
        # DETALLE COMPLETO
        # =========================
        df = get_detalle_factura_por_numero(nro)

        if df.empty:
            return (
                f"No encontré detalle para la factura {nro}.",
                None
            )

        return (
            f"🧾 Detalle completo de la factura {nro}:",
            formatear_dataframe(df)
        )

    # --- PRIORIDAD 3: FACTURA COMPLETA ARTÍCULO ---
    elif tipo == 'factura_completa_articulo':
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

    # --- PRIORIDAD 4: ÚLTIMA FACTURA (ARTÍCULO O PROVEEDOR) ---
    elif tipo == 'ultima_factura_articulo':

        # Extraer patrón (puede ser artículo o proveedor)
        articulos = extraer_valores_multiples(pregunta, 'articulo')
        proveedores = extraer_valores_multiples(pregunta, 'proveedor')

        if articulos:
            patron = articulos[0]
        elif proveedores:
            patron = proveedores[0]
        else:
            # Lista COMPLETA de palabras a ignorar
            patron = _extraer_patron_libre(
                pregunta,
                [
                    # Palabras de intención
                    'ultima', 'ultimo', 'ultim', 'factura', 'facturas',
                    'articulo', 'articulos', 'proveedor', 'proveedores',

                    # Verbos comunes
                    'compras', 'compra', 'compre', 'compramos', 'comprado',
                    'traer', 'mostrar', 'ver', 'dame', 'pasame', 'mostrame',
                    'necesito', 'quiero', 'buscar', 'busco',

                    # Palabras de tiempo
                    'cuando', 'vino', 'llego', 'entro', 'fue', 'paso',

                    # Cualificadores
                    'completa', 'toda', 'todo', 'todos', 'todas', 'entera',

                    # Artículos / preposiciones
                    'de', 'del', 'la', 'el', 'los', 'las', 'un', 'una',
                    'por', 'para', 'en', 'a', 'con', 'sin'
                ]
            )

        if not patron:
            return "¿De qué artículo o proveedor querés la última factura?", None

        df = get_ultima_factura_inteligente(patron)

        if df.empty:
            titulo, df2, resp2 = fallback_openai_sql(
                pregunta,
                "No encontró última factura"
            )
            if df2 is not None and not df2.empty:
                return f"🧾 {resp2 or titulo}", formatear_dataframe(df2)
            return f"No encontré facturas con '{patron}' en artículos ni proveedores.", None

        return "🧾 Última factura encontrada:", formatear_dataframe(df)

    # --- PRIORIDAD 6: GASTOS SECCIONES ---
    elif tipo == 'gastos_secciones':
        familias = _extraer_lista_familias(pregunta)
        mes_key = _extraer_mes_key(pregunta)

        # Si no hay mes_key, intentar buscar solo año
        anio = None
        if not mes_key:
            import re
            match = re.search(r'(202[3-9]|2030)', pregunta)
            if match:
                anio = int(match.group(1))

        # Si no hay ni mes ni año, pedir más info
        if not mes_key and not anio:
            return "Especificá el mes o año (ej: 'gastos familias noviembre 2025' o 'gastos familias 2025').", None

        # Si no hay familias específicas, traer TODAS
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

            # ✅ CORREGIDO: Función para convertir formato LATAM a número
            def latam_to_float(valor):
                if pd.isna(valor):
                    return 0.0
                try:
                    s = str(valor).strip()
                    # Quitar puntos de miles y cambiar coma por punto decimal
                    s = s.replace('.', '').replace(',', '.')
                    return float(s)
                except:
                    return 0.0

            # Buscar columna de pesos (flexible)
            col_pesos = None
            col_usd = None
            for col in df.columns:
                col_lower = col.lower()
                if 'pesos' in col_lower:
                    col_pesos = col
                if 'usd' in col_lower:
                    col_usd = col

            # Calcular totales
            total_pesos = 0
            total_usd = 0

            if col_pesos:
                total_pesos = df[col_pesos].apply(latam_to_float).sum()

            if col_usd:
                total_usd = df[col_usd].apply(latam_to_float).sum()

            # Formatear para mostrar
            total_pesos_fmt = f"${total_pesos:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            total_usd_fmt = f"U$S {total_usd:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

            return f"📊 Gastos por familia en {periodo} | 💰 **{total_pesos_fmt}** | 💵 **{total_usd_fmt}**:", formatear_dataframe(df)

        # Si hay familias específicas
        if not mes_key:
            return "Para familias específicas necesito el mes (ej: 'gastos familia ID noviembre 2025').", None

        df = get_gastos_secciones_detalle_completo(familias, mes_key)
        if df.empty:
            titulo, df2, resp2 = fallback_openai_sql(pregunta, "No encontró gastos secciones")
            if df2 is not None and not df2.empty:
                return f"📌 {resp2 or titulo}", formatear_dataframe(df2)
            return "No encontré gastos para esas secciones.", None

        return f"📌 Gastos de familias {', '.join(familias)} en {mes_key}:", formatear_dataframe(df)

    # --- PRIORIDAD 7: COMPRAS POR MES ---
    elif tipo == 'compras_por_mes':
        mes_key = _extraer_mes_key(pregunta)
        if not mes_key:
            return "Especificá el mes (ej: 'compras por mes 2025-06' o 'compras junio 2025').", None

        df = get_compras_por_mes_excel(mes_key)
        if df.empty:
            titulo, df2, resp2 = fallback_openai_sql(pregunta, "No encontró compras por mes")
            if df2 is not None and not df2.empty:
                return f"📦 {resp2 or titulo}", formatear_dataframe(df2)
            return "No encontré compras para ese mes.", None

        return "📦 Compras por mes:", formatear_dataframe(df)

    # --- PRIORIDAD 8: DETALLE COMPRAS PROVEEDOR + MES ---
    elif tipo == 'detalle_compras_proveedor_mes':
        mes_key = params.get('mes_key')
        proveedor_like = params.get('proveedor_like')

        df = get_detalle_compras_proveedor_mes(proveedor_like, mes_key)

        if df.empty:
            titulo, df2, resp2 = fallback_openai_sql(
                pregunta,
                "No encontró detalle proveedor + mes"
            )
            if df2 is not None and not df2.empty:
                return f"📋 {resp2 or titulo}", formatear_dataframe(df2)
            return "No encontré compras para ese proveedor y mes.", None

        # Calcular total - la columna viene como 'total' (minúscula)
        total = 0
        if 'total' in df.columns:
            total = pd.to_numeric(df['total'], errors='coerce').fillna(0).sum()

        total_fmt = f"${total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

        return (
            f"📋 Compras de {proveedor_like.upper()} en {mes_key} "
            f"| 💰 **Total: {total_fmt}** | {len(df)} registros:",
            formatear_dataframe(df)
        )

    # --- PRIORIDAD 8: DETALLE COMPRAS ARTÍCULO + MES ---
    elif tipo == "detalle_compras_articulo_mes":
        mes_key = params.get("mes_key")
        articulo_like = params.get("articulo_like")

        df = get_detalle_compras_articulo_mes(articulo_like, mes_key)

        if df is None or df.empty:
            titulo, df2, resp2 = fallback_openai_sql(
                pregunta,
                "No encontró compras por artículo + mes"
            )
            if df2 is not None and not df2.empty:
                return f"📋 {resp2 or titulo}", formatear_dataframe(df2)

            return f"No encontré compras del artículo '{articulo_like}' en {mes_key}.", None

        # Calcular totales por moneda
        totales_str = ""
        if 'Total' in df.columns and 'Moneda' in df.columns:
            # Agrupar por moneda
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

    # --- PRIORIDAD 8a: COMPARAR ARTÍCULO ENTRE AÑOS ---
    elif tipo == "comparar_articulo_anios":
        anios = params.get("anios", [])
        articulo_like = params.get("articulo_like", "")

        df = get_comparacion_articulo_anios(anios, articulo_like)

        if df is None or df.empty:
            return f"No encontré compras del artículo '{articulo_like}' en los años {anios}.", None

        # Calcular totales por año
        totales_por_anio = []
        for anio in sorted(anios):
            col_pesos = f"{anio}_$"
            col_usd = f"{anio}_USD"

            total_pesos = df[col_pesos].sum() if col_pesos in df.columns else 0
            total_usd = df[col_usd].sum() if col_usd in df.columns else 0

            # Formatear números
            pesos_fmt = f"${total_pesos:,.0f}".replace(',', '.')
            usd_fmt = f"U$S {total_usd:,.0f}".replace(',', '.')

            if total_pesos > 0 and total_usd > 0:
                totales_por_anio.append(f"**{anio}**: {pesos_fmt} + {usd_fmt}")
            elif total_usd > 0:
                totales_por_anio.append(f"**{anio}**: {usd_fmt}")
            elif total_pesos > 0:
                totales_por_anio.append(f"**{anio}**: {pesos_fmt}")
            else:
                totales_por_anio.append(f"**{anio}**: $0")

        totales_str = " | ".join(totales_por_anio)

        return (
            f"📊 Comparación del artículo **{articulo_like.upper()}** | {totales_str}:",
            formatear_dataframe(df)
        )

    # --- PRIORIDAD 8b: DETALLE COMPRAS ARTÍCULO + AÑO ---
    elif tipo == "detalle_compras_articulo_anio":
        anio = params.get("anio")
        articulo_like = params.get("articulo_like")

        df = get_detalle_compras_articulo_anio(articulo_like, anio)

        if df is None or df.empty:
            titulo, df2, resp2 = fallback_openai_sql(
                pregunta,
                "No encontró compras por artículo + año"
            )
            if df2 is not None and not df2.empty:
                return f"📋 {resp2 or titulo}", formatear_dataframe(df2)

            return f"No encontré compras para el artículo '{articulo_like}' en {anio}.", None

        # Calcular totales por moneda
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

    # --- PRIORIDAD 8b: DETALLE COMPRAS PROVEEDOR + AÑO ---
    elif tipo == "detalle_compras_proveedor_anio":
        anio = params.get('anio')
        proveedor_like = params.get('proveedor_like')

        # Obtener TOTAL REAL primero (sin límite)
        totales = get_total_compras_proveedor_anio(proveedor_like, anio)
        total_real = totales.get('total', 0)
        registros_total = totales.get('registros', 0)

        df = get_detalle_compras_proveedor_anio(proveedor_like, anio)
        if df is None or df.empty:
            # 🔁 Si no hubo resultados como PROVEEDOR, reintentar como ARTÍCULO
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

            # Si tampoco fue artículo → fallback IA/SQL
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
# --- PRIORIDAD 9: TOTAL PROVEEDOR + MONEDA + PERÍODOS ---
    elif tipo == 'total_proveedor_moneda_periodos':
        periodos = params.get('periodos', [])
        monedas = params.get('monedas')

        df = get_total_compras_proveedor_moneda_periodos(periodos, monedas)
        if df is None or df.empty:
            titulo, df2, resp2 = fallback_openai_sql(pregunta, "No encontró total por proveedor + moneda")
            if df2 is not None and not df2.empty:
                return f"📌 {resp2 or titulo}", formatear_dataframe(df2)
            return "No encontré compras por proveedor para esos períodos/monedas.", None

        return "🏭 Total compras por proveedor (por período y moneda):", formatear_dataframe(df)

    # =========================
    # TOP 10 PROVEEDORES (COMPRAS IA)
    # =========================
    elif tipo == "top_10_proveedores":
        moneda = params.get("moneda")  # puede venir None
        anio = params.get("anio")      # puede venir None
        mes = params.get("mes")        # formato YYYY-MM o None

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

    # --- PRIORIDAD 10: COMPARACIONES (MESES) ---
    elif tipo == 'comparar_familia_meses':
        # ✅ CORREGIDO: Primero intentar obtener de params['meses']
        meses_params = params.get("meses", [])
        familias = params.get("familias")

        mes1 = None
        mes2 = None

        # Si vienen meses en params (lista de tuplas)
        if meses_params and len(meses_params) >= 2:
            try:
                ini1, _, _ = meses_params[0]
                ini2, _, _ = meses_params[1]
                mes1 = ini1.strftime("%Y-%m")
                mes2 = ini2.strftime("%Y-%m")
            except:
                pass

        # Fallback: extraer de la pregunta
        if not mes1 or not mes2:
            meses_detectados = extraer_meses_para_comparacion(pregunta)

            if len(meses_detectados) >= 2:
                ini1, _, _ = meses_detectados[0]
                ini2, _, _ = meses_detectados[1]
                mes1 = ini1.strftime("%Y-%m")
                mes2 = ini2.strftime("%Y-%m")

        if not mes1 or not mes2:
            return (
                "No pude identificar los dos meses a comparar. Probá con: 'comparar gastos familias junio julio 2025'",
                None
            )

        # Obtener datos en PESOS
        df_pesos = get_comparacion_familia_meses_moneda(
            mes1, mes2, mes1, mes2, "$", familias if familias else None
        )

        # Obtener datos en USD
        df_usd = get_comparacion_familia_meses_moneda(
            mes1, mes2, mes1, mes2, "U$S", familias if familias else None
        )

        if (df_pesos is None or df_pesos.empty) and (df_usd is None or df_usd.empty):
            return (
                f"No hay datos para comparar familias entre {mes1} y {mes2}.",
                None
            )

        # Guardar en session_state para mostrar con tabs
        st.session_state['comparacion_familia_tabs'] = {
            'titulo': f"📊 Comparación de gastos por familia: {mes1} vs {mes2}",
            'df_pesos': df_pesos,
            'df_usd': df_usd,
            'mes1': mes1,
            'mes2': mes2
        }

        return "__COMPARACION_FAMILIA_TABS__", None

    # --- PRIORIDAD 11: COMPARACIONES (AÑOS) ---
    elif tipo == 'comparar_proveedor_anios_monedas':
        anios = params.get('anios') or extraer_anios(pregunta)

        # ✅ Tomar proveedores desde params (intent_detector) o desde "proveedor ..."
        proveedores = params.get('proveedores') or extraer_valores_multiples(pregunta, 'proveedor')

        # ✅ Normalizar a lista
        if isinstance(proveedores, str):
            proveedores = [proveedores]

        # ✅ Limpiar vacíos (por si viene [''] cuando no se especifica proveedor)
        if proveedores:
            proveedores = [p.strip() for p in proveedores if p and str(p).strip()]

        # ✅ Fallback libre: "comparar compras roche 2023 2024 2025" -> proveedores=['roche']
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

        # Obtener detalle también
        df_detalle = get_detalle_compras_proveedor_anios(anios, proveedores if proveedores else None)

        # Guardar en session_state para mostrar tabs
        st.session_state['comparacion_tabs'] = {
            'resumen': formatear_dataframe(df_resumen),
            'detalle': formatear_dataframe(df_detalle) if df_detalle is not None and not df_detalle.empty else None,
            'titulo': f"🏭 Comparación {', '.join(proveedores) if proveedores else 'proveedores'} ({', '.join(map(str, sorted(anios)))})"
        }

        # Devolver marcador especial
        return "__COMPARACION_TABS__", None

    # --- PRIORIDAD 12: GASTOS POR FAMILIA ---
    elif tipo == 'gastos_familia':
        where_clause, params_sql = construir_where_clause(pregunta)
        df = get_gastos_por_familia(where_clause, params_sql)

        if df.empty:
            titulo, df2, resp2 = fallback_openai_sql(pregunta, "No encontró gastos por familia")
            if df2 is not None and not df2.empty:
                return f"📊 {resp2 or titulo}", formatear_dataframe(df2)
            return "No encontré gastos por familia.", None

        return "📊 Gastos por familia:", formatear_dataframe(df)

    # --- PRIORIDAD 13: DETALLE GENERAL ---
    elif tipo == 'detalle':
        where_clause, params_sql = construir_where_clause(pregunta)
        df = get_detalle_compras(where_clause, params_sql)

        if df.empty:
            titulo, df2, resp2 = fallback_openai_sql(pregunta, "No encontró detalle")
            if df2 is not None and not df2.empty:
                return f"📋 {resp2 or titulo}", formatear_dataframe(df2)
            return "No encontré detalle para esa consulta.", None

        return "📋 Detalle de compras:", formatear_dataframe(df)

    # --- PRIORIDAD 14: CONSULTA GENERAL (HÍBRIDO CON IA) ---
    else:
        # 🤖 SISTEMA HÍBRIDO: Si llegó hasta acá, el intent_detector no entendió
        # → Usamos IA para interpretar y sugerir

