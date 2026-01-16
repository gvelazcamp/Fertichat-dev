import streamlit as st
import pandas as pd
import re
from typing import Tuple, Optional
import json

# =========================
# AGENTIC AI (fallback seguro)
# - Si existe agentic_decidir, lo usamos.
# - Si no existe, cae a interpretar_pregunta (compatibilidad).
# =========================
try:
    from ia_interpretador import agentic_decidir as _agentic_decidir
    _AGENTIC_SOURCE = "agentic_decidir"
except Exception:
    from ia_interpretador import interpretar_pregunta as _agentic_decidir
    _AGENTIC_SOURCE = "interpretar_pregunta"

from sql_facturas import get_facturas_proveedor as get_facturas_proveedor_detalle
from sql_compras import (  # Importar funciones de compras
    get_compras_proveedor_anio,
    get_detalle_compras_proveedor_mes,
    get_compras_multiples,
    get_compras_anio,
)
from sql_stock import (  # Importar funciones de stock
    get_lista_articulos_stock,
    get_lista_familias_stock,
    get_lista_depositos_stock,
    buscar_stock_por_lote,
    get_stock_articulo,
    get_stock_lote_especifico,
    get_stock_familia,
    get_stock_total,
    get_stock_por_familia,
    get_stock_por_deposito,
    get_lotes_por_vencer,
    get_lotes_vencidos,
    get_stock_bajo,
    get_alertas_vencimiento_multiple,
)
from utils_format import formatear_dataframe
from utils_openai import responder_con_openai

ORQUESTADOR_CARGADO = True
ORQUESTADOR_ERROR = None


def _init_orquestador_state():
    global ORQUESTADOR_CARGADO, ORQUESTADOR_ERROR
    ORQUESTADOR_CARGADO = True
    ORQUESTADOR_ERROR = None
    try:
        st.session_state["ORQUESTADOR_CARGADO"] = True
        st.session_state["ORQUESTADOR_ERROR"] = None
        # =========================
        # MARCA PARA VER SI ESTÁ USANDO AGENTIC O FALLBACK
        # =========================
        st.session_state["AGENTIC_SOURCE"] = _AGENTIC_SOURCE
    except Exception as e:  # Corregido: agregado 'as e'
        ORQUESTADOR_ERROR = str(e)


_init_orquestador_state()


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


# =========================
# NUEVO: INTERPRETACIÓN DE PREGUNTAS DE STOCK CON OPENAI
# =========================
import os
from openai import OpenAI

OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

def interpretar_pregunta_stock(pregunta: str) -> dict:
    """
    Usa OpenAI para clasificar la intención de la pregunta de stock
    """
    if not client:
        return {"tipo": "busqueda_libre", "parametros": {"texto": pregunta}}
    
    prompt = f"""
Analiza esta pregunta sobre stock: "{pregunta}"

Clasifica en UNO de estos tipos:
1. "stock_total" - Pregunta por stock total, cuántos artículos, cuántos lotes
2. "stock_por_familia" - Pregunta qué familias tienen más stock, stock por familia
3. "stock_por_deposito" - Pregunta qué depósitos tienen más stock
4. "stock_articulo" - Pregunta por un artículo específico (extraer nombre del artículo)
5. "stock_familia_especifica" - Pregunta por una familia específica (extraer nombre: ID, VITEK, LAB, etc)
6. "stock_lote" - Pregunta por un lote específico (extraer código de lote)
7. "vencimientos" - Pregunta qué vence, cuándo vence, días para vencer
8. "vencidos" - Pregunta por lotes vencidos
9. "stock_bajo" - Pregunta por stock bajo, stock crítico, qué pedir
10. "busqueda_libre" - Búsqueda con texto libre

Responde SOLO con JSON:
{{
  "tipo": "...",
  "parametros": {{
    "articulo": "...",
    "familia": "...",
    "lote": "...",
    "deposito": "...",
    "dias": 90,
    "texto": "..."
  }}
}}

Si un parámetro no aplica, déjalo en null.
"""
    
    try:
        respuesta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un clasificador de preguntas de inventario."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        content = respuesta.choices[0].message.content.strip()
        return json.loads(content)
    except Exception as e:
        print(f"Error interpretando pregunta de stock: {e}")
        return {"tipo": "busqueda_libre", "parametros": {"texto": pregunta}}


def detectar_intencion_stock(texto: str) -> dict:
    """Detecta la intención para consultas de stock"""
    texto_lower = texto.lower().strip()

    # ✅ PRIORIZAR STOCK TOTAL ANTES DE ARTÍCULO ESPECÍFICO
    if 'total' in texto_lower and 'stock' in texto_lower:
        return {'tipo': 'stock_total', 'debug': 'Stock total'}
    
    # ✅ NUEVO: Artículos totales
    if 'artículos' in texto_lower or 'articulos' in texto_lower:
        return {'tipo': 'stock_total', 'debug': 'Artículos totales'}
    
    # ✅ NUEVO: Lotes totales
    if 'lotes' in texto_lower and ('registrados' in texto_lower or 'tengo' in texto_lower):
        return {'tipo': 'stock_total', 'debug': 'Lotes totales'}

    # ✅ DETECTAR FAMILIAS CONOCIDAS (antes de artículos)
    familias_conocidas = ['id', 'fb', 'g', 'tr', 'xx', 'hm', 'mi']
    for fam in familias_conocidas:
        if fam in texto_lower.split():
            return {'tipo': 'stock_familia_especifica', 'familia': fam.upper(), 'debug': f'Stock familia {fam.upper()}'}

    # ✅ MOVER ANTES DE ARTÍCULO: Stock por familia general
    if 'por familia' in texto_lower or 'familias' in texto_lower or 'familia' in texto_lower:
        # Si no específica, stock por familia general
        if 'por familia' in texto_lower or 'familias' in texto_lower:
            return {'tipo': 'stock_por_familia', 'debug': 'Stock por familia general'}

    # ✅ MOVER STOCK_ARTICULO ANTES DE VENCIMIENTOS PARA PRIORIZAR ARTÍCULO ESPECÍFICO
    # Stock de artículo específico (casos 1 y 4)
    if any(k in texto_lower for k in ['stock', 'cuanto hay', 'cuánto hay', 'tenemos', 'disponible', 'hay']):
        # Extraer nombre del artículo
        palabras_excluir = ['stock', 'cuanto', 'cuánto', 'hay', 'de', 'del', 'tenemos', 'disponible', 'el', 'la', 'los', 'las', 'que', 'es', 'un', 'una', 'cual']
        palabras = [p for p in texto_lower.split() if p not in palabras_excluir and len(p) > 2]
        if palabras:
            articulo = ' '.join(palabras)
            return {'tipo': 'stock_articulo', 'articulo': articulo, 'debug': f'Stock de artículo: {articulo}'}

    # Vencimientos
    if any(k in texto_lower for k in ['vencer', 'vencen', 'vencimiento', 'vence', 'por vencer']):
        if 'vencido' in texto_lower or 'ya vencio' in texto_lower:
            return {'tipo': 'lotes_vencidos', 'debug': 'Lotes vencidos'}
        # Extraer días si se menciona
        import re
        match = re.search(r'(\d+)\s*(dias|día|dia|días)', texto_lower)
        dias = int(match.group(1)) if match else 90
        return {'tipo': 'lotes_por_vencer', 'dias': dias, 'debug': f'Lotes por vencer en {dias} días'}

    # Vencidos
    if any(k in texto_lower for k in ['vencido', 'vencidos', 'ya vencio', 'caducado']):
        return {'tipo': 'lotes_vencidos', 'debug': 'Lotes vencidos'}

    # Stock bajo
    if any(k in texto_lower for k in ['stock bajo', 'poco stock', 'bajo stock', 'quedan pocos', 'se acaba', 'reponer']):
        return {'tipo': 'stock_bajo', 'debug': 'Stock bajo'}

    # Lote específico
    if any(k in texto_lower for k in ['lote', 'nro lote', 'numero de lote']):
        # Buscar patrón de lote (alfanumérico)
        import re
        match = re.search(r'lote\s+(\w+)', texto_lower)
        if match:
            return {'tipo': 'lote_especifico', 'lote': match.group(1), 'debug': f'Lote específico: {match.group(1)}'}

    # Stock por familia (ya cubierto arriba, pero dejar por si acaso)
    if any(k in texto_lower for k in ['familia', 'familias', 'por familia', 'seccion', 'secciones']):
        return {'tipo': 'stock_por_familia', 'debug': 'Stock por familias'}

    # ✅ NUEVO: Lista de artículos
    if any(k in texto_lower for k in ['listado', 'lista', 'todos los artículos', 'artículos disponibles', 'qué artículos hay']):
        return {'tipo': 'lista_articulos', 'debug': 'Lista de artículos'}

    # ✅ NUEVO: Preguntas comparativas
    if any(k in texto_lower for k in ['qué artículo tiene más stock', 'cuál tiene más stock', 'artículo con más stock']):
        return {'tipo': 'stock_comparativo', 'subtipo': 'mas_stock', 'debug': 'Artículo con más stock'}
    if any(k in texto_lower for k in ['qué artículo tiene menos stock', 'cuál tiene menos stock', 'artículo con menos stock']):
        return {'tipo': 'stock_comparativo', 'subtipo': 'menos_stock', 'debug': 'Artículo con menos stock'}
    if any(k in texto_lower for k in ['qué artículos están bajos', 'artículos bajos de stock']):
        return {'tipo': 'stock_bajo', 'debug': 'Artículos bajos de stock'}

    # Stock por depósito
    if any(k in texto_lower for k in ['deposito', 'depósito', 'depositos', 'depósitos', 'almacen']):
        return {'tipo': 'stock_por_deposito', 'debug': 'Stock por depósito'}

    # Al final, por defecto buscar artículo
    return {'tipo': 'stock_articulo', 'articulo': texto, 'debug': f'Búsqueda general: {texto}'}


def responder_pregunta_stock(pregunta: str) -> tuple:
    """
    Orquestador principal que interpreta y ejecuta consultas de stock
    Devuelve: (mensaje, df) donde df puede ser None
    """
    # 1. Interpretar la pregunta
    intencion = detectar_intencion_stock(pregunta)  # ✅ USAR LA FUNCIÓN LOCAL EN LUGAR DE OPENAI
    tipo = intencion["tipo"]
    params = intencion.get("parametros", {})  # ✅ AGREGAR .get() POR SI NO HAY PARAMETROS
    
    # 2. Ejecutar la función SQL correcta según el tipo
    if tipo == "stock_total":
        df = get_stock_total()
        if df is not None and not df.empty:
            mensaje = f"""
            📊 Stock total:
            - Registros: {int(df['registros'].iloc[0]):,}
            - Artículos: {int(df['articulos'].iloc[0]):,}
            - Lotes: {int(df['lotes'].iloc[0]):,}
            - Stock total: {int(df['stock_total'].iloc[0]):,} unidades
            """
            return mensaje.strip(), None  # No tabla, solo mensaje
        return "⚠️ No se pudo obtener el resumen de stock.", None
    
    elif tipo == "stock_por_familia":
        df = get_stock_por_familia()
        if df is not None and not df.empty:
            return "📊 Stock por familia:", df  # Devuelve tabla
        return "⚠️ No se pudo obtener el stock por familia.", None
    
    elif tipo == "stock_por_deposito":
        df = get_stock_por_deposito()
        if df is not None and not df.empty:
            return "🏢 Stock por depósito:", df  # Devuelve tabla
        return "⚠️ No se pudo obtener el stock por depósito.", None
    
    elif tipo == "stock_articulo":
        articulo = params.get("articulo")
        if articulo:
            df = get_stock_articulo(articulo)
            if df is None or df.empty:
                return f"❌ No se encontró stock para '{articulo}'", None
            else:
                return f"📦 {articulo}: {int(df['STOCK'].sum())} unidades en {df['LOTE'].nunique()} lote(s)", df  # Devuelve tabla
        return "❌ Indicá el artículo.", None
    
    elif tipo == "stock_familia_especifica":
        familia = params.get("familia")
        if familia:
            df = get_stock_familia(familia)
            if df is None or df.empty:
                return f"❌ No se encontró stock de la familia '{familia}' en Casa Central", None
            else:
                return f"📦 Stock de familia {familia.upper()} (Casa Central, {len(df)} registros):", df  # Devuelve tabla
        return "❌ Indicá la familia.", None
    
    elif tipo == "stock_lote":
        lote = params.get("lote")
        if lote:
            df = get_stock_lote_especifico(lote)
            if df is None or df.empty:
                return f"❌ No se encontró el lote '{lote}'", None
            else:
                r = df.iloc[0]
                mensaje = f"📦 Lote {lote}:\n- Artículo: {r['ARTICULO']}\n- Depósito: {r['DEPOSITO']}\n- Stock: {int(r['STOCK'])} unidades\n- Vence: {r['VENCIMIENTO']}"
                return mensaje, df  # Devuelve tabla
        return "❌ Indicá el lote.", None
    
    elif tipo == "vencimientos":
        dias = params.get("dias", 90)
        df = get_lotes_por_vencer(dias=dias)
        if df is None or df.empty:
            return f"✅ No hay lotes que venzan en los próximos {dias} días", None
        else:
            return f"⚠️ Hay {len(df)} lote(s) que vencen en los próximos {dias} días", df  # Devuelve tabla
    
    elif tipo == "vencidos":
        df = get_lotes_vencidos()
        if df is None or df.empty:
            return "✅ No hay lotes vencidos con stock", None
        else:
            return f"⚠️ Hay {len(df)} lote(s) vencido(s) con stock", df  # Devuelve tabla
    
    elif tipo == "stock_bajo":
        df = get_stock_bajo(minimo=10)
        if df is None or df.empty:
            return "✅ No hay artículos con stock bajo", None
        else:
            articulos = df.groupby('ARTICULO')['STOCK'].sum().sort_values().head(10)
            mensaje = "⚠️ Artículos con stock bajo:\n\n"
            for art, stock in articulos.items():
                mensaje += f"- {art}: {int(stock)} unidades\n"
            return mensaje.strip(), df  # Devuelve tabla
    
    elif tipo == "busqueda_libre":
        texto = params.get("texto")
        if texto:
            df = buscar_stock_por_lote(texto_busqueda=texto)
            if df is None or df.empty:
                return f"❌ No se encontraron resultados para '{texto}'", None
            else:
                return f"✅ Encontré {len(df)} registro(s) relacionados con '{texto}'", df  # Devuelve tabla
        return "❌ Indicá qué buscar.", None
    
    return "❌ No pude interpretar la pregunta", None


def procesar_pregunta_v2(pregunta: str):
    print(f"🐛 DEBUG ORQUESTADOR: Procesando pregunta: '{pregunta}'")
    _init_orquestador_state()

    print(f"\n{'=' * 60}")
    print(f"📝 PREGUNTA: {pregunta}")
    print(f"{'=' * 60}")

    # =========================
    # MARCA EN LOG: QUÉ "CEREBRO" SE ESTÁ USANDO
    # =========================
    print(f"[ORQUESTADOR] AGENTIC_SOURCE = {_AGENTIC_SOURCE}")

    # =========================
    # NUEVO: BYPASS PARA COMPARACIONES MULTI PROVEEDORES AÑOS/MESES CON MONEDA
    # =========================
    print(f"🐛 DEBUG ORQUESTADOR: Verificando bypass para 'comparar compras'")
    if "comparar" in pregunta.lower() and "compras" in pregunta.lower():
        from sql_comparativas import get_comparacion_multi_proveedores_tiempo_monedas
        
        parts = [p.lower().strip().replace(',', '') for p in pregunta.split() if p.strip()]
        
        proveedores = []
        months_list = []
        years_list = []
        
        month_names = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        
        for p in parts:
            if p in month_names:
                months_list.append(p)
            elif p.isdigit() and len(p) == 4:
                years_list.append(int(p))
            elif p not in ["comparar", "compras"]:
                proveedores.append(p)
        
        proveedores = list(set(proveedores))  # Eliminar duplicados
        anios = []
        meses = []
        
        if months_list:
            if len(months_list) == len(years_list):
                for m, y in zip(months_list, years_list):
                    mes_num = month_names.index(m) + 1
                    mes_str = f"{y:04d}-{mes_num:02d}"
                    meses.append(mes_str)
                    anios.append(y)
            else:
                # Si no coinciden, usar solo años
                anios = years_list
        else:
            anios = years_list
        
        anios = sorted(list(set(anios)))
        meses = sorted(list(set(meses)))
        
        if proveedores and (anios or meses):
            df = get_comparacion_multi_proveedores_tiempo_monedas(proveedores, anios=anios if not meses else None, meses=meses if meses else None)
            if df is not None and not df.empty:
                tiempo_str = ", ".join(meses) if meses else ", ".join(map(str, anios))
                mensaje = f"📊 Comparación de compras para {', '.join(proveedores).upper()} en {tiempo_str} (agrupado por moneda)."
                return mensaje, formatear_dataframe(df), None
            else:
                return "⚠️ No se encontraron resultados para la comparación.", None, None
        else:
            # Si no parsea, seguir con agentic
            pass

    # =========================
    # AGENTIC AI: decisión (tipo + parametros), no ejecuta SQL
    # =========================
    interpretacion = _agentic_decidir(pregunta)

    tipo = interpretacion.get("tipo", "no_entendido")
    params = interpretacion.get("parametros", {})
    debug = interpretacion.get("debug", "")

    print("\n[ORQUESTADOR] DECISIÓN")
    print(f"  Tipo   : {tipo}")
    print(f"  Params : {params}")
    print(f"  Debug  : {debug}")

    try:
        if st.session_state.get("DEBUG_SQL", False):
            st.session_state["DBG_INT_LAST"] = {
                "pregunta": pregunta,
                "tipo": tipo,
                "parametros": params,
                "debug": debug,
                "agentic_source": _AGENTIC_SOURCE,
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
            # Aquí podrías derivar a detalle_factura_numero si quieres
            pass

    if tipo == "no_entendido":
        # NUEVO: INTENTAR INTERPRETAR COMO PREGUNTA DE STOCK
        if any(word in pregunta.lower() for word in ["stock", "artículo", "articulo", "lote", "familia", "depósito", "deposito", "vence", "vencimiento"]):
            respuesta, df_extra = responder_pregunta_stock(pregunta)
            return respuesta, formatear_dataframe(df_extra) if df_extra is not None else None, None
        
        sugerencia = interpretacion.get("sugerencia", "No entendí tu pregunta.")
        alternativas = interpretacion.get("alternativas", [])
        return (
            f"🤔 {sugerencia}",
            None,
            {
                "sugerencia": sugerencia,
                "alternativas": alternativas,
                "pregunta_original": pregunta,
            },
        )

    return _ejecutar_consulta(tipo, params, pregunta)


def _ejecutar_consulta(tipo: str, params: dict, pregunta_original: str):
    try:
        # =========================================================
        # COMPARACIÓN PROVEEDORES AÑOS (AGREGADO PARA FORZAR)
        # =========================================================
        if tipo == "comparar_proveedor_anios":
            print(f"🐛 DEBUG ORQUESTADOR: Ejecutando tipo comparar_proveedor_anios")
            proveedores = params.get("proveedores", [])
            if isinstance(proveedores, str):
                proveedores = [p.strip() for p in proveedores.split(",") if p.strip()]
            if not proveedores:
                proveedor = params.get("proveedor", "").strip()
                if proveedor:
                    proveedores = [proveedor]
            anios = params.get("anios", [])
            if len(proveedores) < 1 or len(anios) < 2:
                return "❌ Indicá proveedores y años. Ej: comparar compras roche, tresul 2024 2025", None, None

            st.session_state["DBG_SQL_LAST_TAG"] = "comparar_proveedor_anios (sql_comparativas)"

            print("\n[ORQUESTADOR] Llamando get_comparacion_proveedor_anios()")
            print(f"  proveedores = {proveedores}")
            print(f"  anios       = {anios}")

            from sql_comparativas import get_comparacion_proveedor_anios
            df = get_comparacion_proveedor_anios(proveedores, anios)

            if df is None or df.empty:
                return "⚠️ No se encontraron resultados para la comparación.", None, None

            prov_lbl = ", ".join([p.upper() for p in proveedores[:3]])
            return (
                f"📊 Comparación de compras de **{prov_lbl}** en {anios[0]}-{anios[1]} ({len(df)} registros):",
                formatear_dataframe(df),
                None,
            )

        # =========================================================
        # FACTURAS (LISTADO) - usa SIEMPRE sql_facturas.get_facturas_proveedor
        # =========================================================
        if tipo in ("facturas_proveedor", "facturas_proveedor_detalle"):
            proveedores = params.get("proveedores", [])
            if isinstance(proveedores, str):
                proveedores = [proveedores]

            proveedores_raw = [str(p).strip() for p in proveedores if str(p).strip()]
            if not proveedores_raw:
                return "❌ Indicá el proveedor. Ej: todas las facturas roche 2025", None, None

            st.session_state["DBG_SQL_LAST_TAG"] = "facturas_proveedor (sql_facturas)"

            print("\n[ORQUESTADOR] Llamando get_facturas_proveedor_detalle()")
            print(f"  proveedores = {proveedores_raw}")
            print(f"  meses       = {params.get('meses')}")
            print(f"  anios       = {params.get('anios')}")
            print(f"  desde       = {params.get('desde')}")
            print(f"  hasta       = {params.get('hasta')}")
            print(f"  articulo    = {params.get('articulo')}")
            print(f"  moneda      = {params.get('moneda')}")
            print(f"  limite      = {params.get('limite', 5000)}")

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

            try:
                if st.session_state.get("DEBUG_SQL", False):
                    st.session_state["DBG_SQL_ROWS"] = 0 if df is None else len(df)
                    st.session_state["DBG_SQL_COLS"] = (
                        [] if df is None or df.empty else list(df.columns)
                    )
            except Exception:
                pass

            if df is None or df.empty:
                debug_msg = f"⚠️ No se encontraron resultados para '{pregunta_original}'.\n\n"
                debug_msg += f"**Tipo detectado:** {tipo}\n"
                debug_msg += f"**Parámetros extraídos:**\n"
                for k, v in params.items():
                    debug_msg += f"- {k}: {v}\n"
                debug_msg += "\nRevisá la consola del servidor para ver el SQL impreso."
                return debug_msg, None, None

            prov_lbl = ", ".join([p.upper() for p in proveedores_raw[:3]])
            return (
                f"🧾 Facturas de **{prov_lbl}** ({len(df)} registros):",
                formatear_dataframe(df),
                None,
            )

        # =========================================================
        # COMPRAS (LISTADO) - usa sql_compras
        # =========================================================
        elif tipo == "compras_proveedor_anio":
            proveedor = params.get("proveedor", "").strip()
            anio = params.get("anio", 2025)
            if not proveedor:
                return "❌ Indicá el proveedor. Ej: compras roche 2025", None, None

            st.session_state["DBG_SQL_LAST_TAG"] = "compras_proveedor_anio (sql_compras)"

            print("\n[ORQUESTADOR] Llamando get_compras_proveedor_anio()")
            print(f"  proveedor = {proveedor}")
            print(f"  anio      = {anio}")

            df = get_compras_proveedor_anio(proveedor, anio)

            if df is None or df.empty:
                return f"⚠️ No se encontraron compras para '{proveedor}' en {anio}.", None, None

            return (
                f"🛒 Compras de **{proveedor.upper()}** en {anio} ({len(df)} registros):",
                formatear_dataframe(df),
                None,
            )

        elif tipo == "compras_proveedor_mes":
            proveedor = params.get("proveedor", "").strip()
            mes = params.get("mes", "").strip()
            anio = params.get("anio")  # Opcional, puede ser None

            if not proveedor or not mes:
                return "❌ Indicá proveedor y mes. Ej: compras roche noviembre 2025", None, None

            st.session_state["DBG_SQL_LAST_TAG"] = "compras_proveedor_mes (sql_compras)"

            print("\n[ORQUESTADOR] Llamando get_detalle_compras_proveedor_mes()")
            print(f"  proveedor = {proveedor}")
            print(f"  mes       = {mes}")
            print(f"  anio      = {anio}")

            df = get_detalle_compras_proveedor_mes(proveedor, mes, anio)

            if df is None or df.empty:
                return f"⚠️ No se encontraron compras para '{proveedor}' en {mes} {anio or ''}.", None, None

            return (
                f"🛒 Compras de **{proveedor.upper()}** en {mes} {anio or ''} ({len(df)} registros):",
                formatear_dataframe(df),
                None,
            )

        elif tipo == "compras_multiples":
            proveedores = params.get("proveedores", [])
            if isinstance(proveedores, str):
                if "," in proveedores:
                    proveedores = [p.strip() for p in proveedores.split(",") if p.strip()]
                else:
                    proveedores = [proveedores]

            proveedores_raw = [str(p).strip() for p in proveedores if str(p).strip()]
            if not proveedores_raw:
                return "❌ Indicá los proveedores. Ej: compras roche, biodiagnostico noviembre 2025", None, None

            meses = params.get("meses", [])
            anios = params.get("anios", [])
            limite = params.get("limite", 5000)

            st.session_state["DBG_SQL_LAST_TAG"] = "compras_multiples (sql_compras)"

            print("\n[ORQUESTADOR] Llamando get_compras_multiples()")
            print(f"  proveedores = {proveedores_raw}")
            print(f"  meses       = {meses}")
            print(f"  anios       = {anios}")
            print(f"  limite      = {limite}")

            df = get_compras_multiples(proveedores_raw, meses, anios, limite)

            if df is None or df.empty:
                return f"⚠️ No se encontraron compras para {', '.join(proveedores_raw)}.", None, None

            prov_lbl = ", ".join([p.upper() for p in proveedores_raw[:3]])
            mes_lbl = ", ".join(meses) if meses else ""
            anio_lbl = ", ".join(map(str, anios)) if anios else ""
            filtro = f" {mes_lbl} {anio_lbl}".strip()
            return (
                f"🛒 Compras de **{prov_lbl}**{filtro} ({len(df)} registros):",
                formatear_dataframe(df),
                None,
            )

        elif tipo == "compras_anio":
            anio = params.get("anio", 2025)
            limite = params.get("limite", 5000)

            st.session_state["DBG_SQL_LAST_TAG"] = "compras_anio (sql_compras)"

            print("\n[ORQUESTADOR] Llamando get_compras_anio()")
            print(f"  anio   = {anio}")
            print(f"  limite = {limite}")

            df = get_compras_anio(anio, limite)

            if df is None or df.empty:
                return f"⚠️ No se encontraron compras en {anio}.", None, None

            return (
                f"🛒 Todas las compras en {anio} ({len(df)} registros):",
                formatear_dataframe(df),
                None,
            )

        return f"❌ Tipo de consulta '{tipo}' no implementado.", None, None

    except Exception as e:
        print(f"❌ Error ejecutando consulta: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ Error: {str(e)[:150]}", None, None


def procesar_pregunta(pregunta: str) -> Tuple[str, Optional[pd.DataFrame]]:
    mensaje, df, sugerencia = procesar_pregunta_v2(pregunta)

    if sugerencia:
        alternativas = sugerencia.get("alternativas", [])
        if alternativas:
            mensaje += "\n\n**Alternativas:**\n" + "\n".join(
                f"• {a}" for a in alternativas[:3]
            )

    return mensaje, df


def procesar_pregunta_router(pregunta: str) -> Tuple[str, Optional[pd.DataFrame]]:
    return procesar_pregunta(pregunta)


if __name__ == "__main__":
    print("=" * 60)
    print("🛠 Verificando estado del orquestador...")
    try:
        print(
            f"ORQUESTADOR_CARGADO (session): {st.session_state.get('ORQUESTADOR_CARGADO', None)}"
        )
        print(
            f"AGENTIC_SOURCE (session): {st.session_state.get('AGENTIC_SOURCE', None)}"
        )
    except Exception:
        print("ORQUESTADOR_CARGADO (session): n/a")
    print("=" * 60)
