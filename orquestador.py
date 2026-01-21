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

from sql_facturas import (
    get_facturas_proveedor as get_facturas_proveedor_detalle,
    get_detalle_factura_por_numero,
    buscar_facturas_similares,
)
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

# NUEVO: Importar el interpretador dedicado de stock
from interpretador_stock import interpretar_pregunta_stock

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


def responder_pregunta_stock(pregunta: str) -> tuple:
    """
    Procesa preguntas de stock usando el interpretador dedicado
    """
    # 1. Interpretar con el módulo dedicado
    resultado = interpretar_pregunta_stock(pregunta)
    
    tipo = resultado["tipo"]
    params = resultado["parametros"]
    
    # Debug
    print(f"\n🔍 INTERPRETADOR STOCK:")
    print(f"  Pregunta: {pregunta}")
    print(f"  Tipo: {tipo}")
    print(f"  Params: {params}")
    
    # 2. Si no es stock, retornar None para que siga con compras
    if tipo == "no_stock":
        return None, None
    
    # 3. Ejecutar según tipo
    if tipo == "familia_especifica":
        familia = params.get("familia")
        if not familia:
            return "❌ No se detectó la familia", None
        
        df = get_stock_familia(familia)
        if df is None or df.empty:
            return f"❌ No se encontró stock de la familia '{familia}' en Casa Central", None
        else:
            articulos = df['ARTICULO'].nunique()
            total = df['STOCK'].sum()
            return f"📦 Familia {familia.upper()} (Casa Central): {articulos} artículos, {int(total)} unidades", df
    
    elif tipo == "por_familia":
        df = get_stock_por_familia()
        if df is not None and not df.empty:
            mensaje = f"📊 Stock por familia ({len(df)} familias):\n\n"
            for _, row in df.head(10).iterrows():
                mensaje += f"- {row['familia']}: {int(row['stock_total']):,} unidades ({int(row['articulos'])} artículos)\n"
            return mensaje.strip(), df
        return "⚠️ No se pudo obtener el stock por familia.", None
    
    elif tipo == "por_deposito":
        df = get_stock_por_deposito()
        if df is not None and not df.empty:
            mensaje = f"🏢 Stock por depósito ({len(df)} depósitos):\n\n"
            for _, row in df.head(10).iterrows():
                mensaje += f"- {row['deposito']}: {int(row['stock_total']):,} unidades ({int(row['articulos'])} artículos)\n"
            return mensaje.strip(), df
        return "⚠️ No se pudo obtener el stock por depósito.", None
    
    elif tipo == "total":
        df = get_stock_total()
        if df is not None and not df.empty:
            row = df.iloc[0]
            mensaje = f"📊 Stock total general:\n"
            mensaje += f"- Registros: {int(row['registros']):,}\n"
            mensaje += f"- Artículos: {int(row['articulos']):,}\n"
            mensaje += f"- Lotes: {int(row['lotes']):,}\n"
            mensaje += f"- Stock total: {int(row['stock_total']):,} unidades"
            return mensaje, None
        return "⚠️ No se pudo obtener el resumen de stock.", None
    
    elif tipo == "vencimientos":
        dias = params.get("dias", 90)
        df = get_lotes_por_vencer(dias=dias)
        if df is None or df.empty:
            return f"✅ No hay lotes que venzan en los próximos {dias} días", None
        else:
            return f"⚠️ Hay {len(df)} lote(s) que vencen en los próximos {dias} días", df
    
    elif tipo == "vencidos":
        df = get_lotes_vencidos()
        if df is None or df.empty:
            return "✅ No hay lotes vencidos con stock", None
        else:
            return f"⚠️ Hay {len(df)} lote(s) vencido(s) con stock", df
    
    elif tipo == "stock_bajo":
        df = get_stock_bajo(minimo=10)
        if df is None or df.empty:
            return "✅ No hay artículos con stock bajo", None
        else:
            articulos = df.groupby('ARTICULO')['STOCK'].sum().sort_values().head(10)
            mensaje = "⚠️ Artículos con stock bajo:\n\n"
            for art, stock in articulos.items():
                mensaje += f"- {art}: {int(stock)} unidades\n"
            return mensaje.strip(), df
    
    elif tipo == "articulo":
        articulo = params.get("articulo")
        if not articulo:
            return "❌ No se detectó el artículo", None
        
        df = get_stock_articulo(articulo)
        if df is None or df.empty:
            return f"❌ No se encontró stock para '{articulo}'", None
        else:
            total = df['STOCK'].sum()
            lotes = df['LOTE'].nunique()
            return f"📦 {articulo}: {int(total)} unidades en {lotes} lote(s)", df
    
    elif tipo == "lote":
        lote = params.get("lote")
        if not lote:
            return "❌ No se detectó el lote", None
        
        df = get_stock_lote_especifico(lote)
        if df is None or df.empty:
            return f"❌ No se encontró el lote '{lote}'", None
        else:
            r = df.iloc[0]
            mensaje = f"📦 Lote {lote}:\n- Artículo: {r['ARTICULO']}\n- Depósito: {r['DEPOSITO']}\n- Stock: {int(r['STOCK'])} unidades\n- Vence: {r['VENCIMIENTO']}"
            return mensaje, df
    
    else:
        # Búsqueda libre como fallback
        df = buscar_stock_por_lote(texto_busqueda=pregunta)
        if df is None or df.empty:
            return f"❌ No se encontraron resultados para '{pregunta}'", None
        else:
            return f"✅ Encontré {len(df)} registro(s) relacionados con '{pregunta}'", df


def procesar_pregunta_v2(pregunta: str):
    print(f"🐛 DEBUG ORQUESTADOR: Procesando pregunta: '{pregunta}'")
    _init_orquestador_state()

    print(f"\n{'=' * 60}")
    print(f"📝 PREGUNTA: {pregunta}")
    print(f"{'=' * 60}")

    # =========================
    # 🆕 PRIMERO: INTENTAR CON STOCK
    # =========================
    if any(word in pregunta.lower() for word in ["stock", "familia", "lote", "venc", "deposito", "depósito", "bajo", "crítico"]):
        print("🔍 Detectada palabra clave de STOCK, intentando interpretador...")
        respuesta, df_extra = responder_pregunta_stock(pregunta)
        
        # Si el interpretador manejó la pregunta (no retornó None)
        if respuesta is not None:
            print(f"✅ Pregunta manejada por interpretador de STOCK")
            return respuesta, formatear_dataframe(df_extra) if df_extra is not None else None, None
        else:
            print("⚠️ Interpretador de stock retornó None, continuando con compras...")

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

        # =========================================================
        # DETALLE DE FACTURA POR NÚMERO
        # =========================================================
        elif tipo == "detalle_factura_numero":
            nro_factura = params.get("nro_factura", "").strip()
            
            if not nro_factura:
                return "❌ Indicá el número de factura. Ej: detalle factura 60907", None, None
            
            st.session_state["DBG_SQL_LAST_TAG"] = "detalle_factura_numero"
            
            print("\n[ORQUESTADOR] Llamando get_detalle_factura_por_numero()")
            print(f"  nro_factura = {nro_factura}")
            
            df = get_detalle_factura_por_numero(nro_factura)
            
            try:
                if st.session_state.get("DEBUG_SQL", False):
                    st.session_state["DBG_SQL_ROWS"] = 0 if df is None else len(df)
                    st.session_state["DBG_SQL_COLS"] = [] if df is None or df.empty else list(df.columns)
            except Exception:
                pass
            
            # Si no se encuentra, buscar similares
            if df is None or df.empty:
                print(f"⚠️ No se encontró factura exacta, buscando similares a '{nro_factura}'...")
                similares = buscar_facturas_similares(nro_factura, limite=20)
                
                if similares is not None and not similares.empty:
                    mensaje = f"⚠️ No se encontró la factura **{nro_factura}** exactamente.\n\n"
                    mensaje += f"📋 Encontré **{len(similares)}** factura(s) similar(es):"
                    return mensaje, formatear_dataframe(similares), None
                else:
                    return f"❌ No se encontró la factura {nro_factura} ni facturas similares.", None, None
            
            # Obtener info
            proveedor = df["Proveedor"].iloc[0] if "Proveedor" in df.columns else "N/A"
            fecha = df["Fecha"].iloc[0] if "Fecha" in df.columns else "N/A"
            moneda = df["Moneda"].iloc[0] if "Moneda" in df.columns else ""
            nro_real = df["nro_factura"].iloc[0] if "nro_factura" in df.columns else nro_factura
            total_lineas = len(df)
            total_monto = df["Total"].sum() if "Total" in df.columns else 0
            
            mensaje = f"📄 **Factura {nro_real}**\n"
            mensaje += f"🏢 Proveedor: **{proveedor}**\n"
            mensaje += f"📅 Fecha: {fecha}\n"
            mensaje += f"💰 Total: {moneda} {total_monto:,.2f}\n"
            mensaje += f"📦 {total_lineas} artículo(s)\n"
            
            return mensaje, formatear_dataframe(df), None

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
