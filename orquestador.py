# =========================
# ORQUESTADOR.PY
# =========================

import streamlit as st
import pandas as pd
import re
from typing import Tuple, Optional

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
    except Exception:
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


def procesar_pregunta_v2(pregunta: str):
    # FORZAR PARA "comparar compras roche, tresul 2024 2025"
    if pregunta.lower().strip() == "comparar compras roche, tresul 2024 2025":
        print("🐛 FORZANDO SQL DIRECTO PARA LA CONSULTA")
        from sql_comparativas import get_comparacion_proveedores_anios_multi
        df = get_comparacion_proveedores_anios_multi(['roche', 'tresul'], [2024, 2025])
        print(f"🐛 FORZANDO: df filas={len(df) if df is not None and not df.empty else 0}")
        if df is not None and not df.empty:
            return (
                f"📊 Comparación forzada de compras entre ROCHE y TRESUL en 2024-2025:",
                formatear_dataframe(df),
                None,
            )
        else:
            return "⚠️ Forzado: No se encontraron resultados.", None, None

    print(f"🐛 DEBUG ORQUESTADOR: Procesando pregunta: '{pregunta}'")
    _init_orquestador_state()

    print(f"\n{'=' * 60}")
    print(f"📝 PREGUNTA: {pregunta}")
    print(f"{'=' * 60}")

    # =========================
    # MARCA EN LOG: QUÉ “CEREBRO” SE ESTÁ USANDO
    # =========================
    print(f"[ORQUESTADOR] AGENTIC_SOURCE = {_AGENTIC_SOURCE}")

    # =========================
    # NUEVO: BYPASS PARA COMPARACIONES MULTI PROVEEDORES AÑOS/MESES CON MONEDA
    # =========================
    print(f"🐛 DEBUG ORQUESTADOR: Verificando bypass para 'comparar compras'")
    if "comparar" in pregunta.lower() and "compras" in pregunta.lower():
        from sql_comparativas import get_comparacion_multi_proveedores_tiempo_monedas
        
        parts = [p.lower().strip() for p in pregunta.replace(",", "").split() if p.strip()]
        
        proveedores = []
        anios = []
        meses = []
        
        for p in parts:
            if p.isdigit() and len(p) == 4:  # Años como 2024
                anios.append(int(p))
            elif "-" in p and len(p) == 7:  # Meses como 2025-01
                meses.append(p)
            elif p not in ["comparar", "compras"] and not p.isdigit():
                proveedores.append(p)
        
        proveedores = list(set(proveedores))  # Eliminar duplicados
        anios = sorted(list(set(anios)))
        meses = sorted(list(set(meses)))
        
        if proveedores and (anios or meses):
            df = get_comparacion_multi_proveedores_tiempo_monedas(proveedores, anios=anios if anios else None, meses=meses if meses else None)
            if df is not None and not df.empty:
                tiempo_str = ", ".join(map(str, anios or meses))
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
