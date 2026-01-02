# =========================
# UI_COMPRAS.PY - INTERFAZ COMPRAS IA
# =========================

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional

from utils_format import formatear_dataframe, df_to_excel
from utils_graphs import _render_graficos_compras, _render_explicacion_compras

# Importar del orquestador
from orquestador import (
    procesar_pregunta,
    procesar_pregunta_router,
)

# Importar de utils_openai
from utils_openai import (
    obtener_sugerencia_ejecutable,
    recomendar_como_preguntar,
)

# Importar de intent_detector
from intent_detector import normalizar_texto


def render_orquestador_output(pregunta_original: str, respuesta: str, df: Optional[pd.DataFrame]):
    """
    Intercepta marcadores especiales del orquestador y los renderiza en la UI.
    """
    # UID para keys (evita choques de botones en reruns)
    uid = str(abs(hash((pregunta_original or "", respuesta or ""))) % 10**8)

    # -------------------------------------------------
    # 1) SUGERENCIA IA (cuando intent_detector no entiende)
    # -------------------------------------------------
    if respuesta == "__MOSTRAR_SUGERENCIA__":
        st.warning("No entendí esa pregunta tal cual. Te propongo una forma ejecutable 👇")

        with st.spinner("🧠 Generando sugerencia..."):
            sug = obtener_sugerencia_ejecutable(pregunta_original)

        entendido = (sug.get("entendido") or "").strip()
        comando = (sug.get("sugerencia") or "").strip()
        alternativas = sug.get("alternativas") or []

        if entendido:
            st.caption(entendido)

        if comando:
            st.markdown(f"✅ **Sugerencia ejecutable:** `{comando}`")

            if st.button(f"▶️ Ejecutar: {comando}", key=f"btn_exec_{uid}", use_container_width=True):
                with st.spinner("🔎 Ejecutando..."):
                    resp2, df2 = procesar_pregunta(comando)

                # Render normal
                st.markdown(f"**{resp2}**")
                if df2 is not None and not df2.empty:
                    st.dataframe(formatear_dataframe(df2), use_container_width=True, hide_index=True)
        else:
            st.info("No pude generar un comando ejecutable. Probá reformular.")
            st.markdown(recomendar_como_preguntar(pregunta_original))

        if alternativas:
            st.markdown("**Alternativas:**")
            for i, alt in enumerate(alternativas[:5]):
                alt = str(alt).strip()
                if not alt:
                    continue
                if st.button(f"➡️ {alt}", key=f"btn_alt_{uid}_{i}", use_container_width=True):
                    with st.spinner("🔎 Ejecutando alternativa..."):
                        resp3, df3 = procesar_pregunta(alt)

                    st.markdown(f"**{resp3}**")
                    if df3 is not None and not df3.empty:
                        st.dataframe(formatear_dataframe(df3), use_container_width=True, hide_index=True)

        return  # 👈 importante

    # -------------------------------------------------
    # 2) COMPARACIÓN (tabs proveedor/años)
    # -------------------------------------------------
    if respuesta == "__COMPARACION_TABS__":
        info = st.session_state.get("comparacion_tabs", {}) or {}
        st.markdown(f"**{info.get('titulo','📊 Comparación')}**")

        tabs = st.tabs(["📌 Resumen", "📋 Detalle"])
        with tabs[0]:
            df_res = info.get("resumen")
            if df_res is not None and not df_res.empty:
                st.dataframe(df_res, use_container_width=True, hide_index=True)
            else:
                st.info("Sin resumen.")

        with tabs[1]:
            df_det = info.get("detalle")
            if df_det is not None and not df_det.empty:
                st.dataframe(df_det, use_container_width=True, hide_index=True)
            else:
                st.info("Sin detalle.")

        return

    # -------------------------------------------------
    # 3) COMPARACIÓN FAMILIAS (tabs pesos/usd)
    # -------------------------------------------------
    if respuesta == "__COMPARACION_FAMILIA_TABS__":
        info = st.session_state.get("comparacion_familia_tabs", {}) or {}
        st.markdown(f"**{info.get('titulo','📊 Comparación de familias')}**")

        tabs = st.tabs(["$ Pesos", "U$S USD"])
        with tabs[0]:
            dfp = info.get("df_pesos")
            if dfp is not None and not dfp.empty:
                st.dataframe(formatear_dataframe(dfp), use_container_width=True, hide_index=True)
            else:
                st.info("Sin datos en pesos.")

        with tabs[1]:
            duf = info.get("df_usd")
            if duf is not None and not duf.empty:
                st.dataframe(formatear_dataframe(duf), use_container_width=True, hide_index=True)
            else:
                st.info("Sin datos en USD.")

        return

    # -------------------------------------------------
    # 4) RESPUESTA NORMAL
    # -------------------------------------------------
    st.markdown(f"**{respuesta}**")
    if df is not None and not df.empty:
        st.dataframe(formatear_dataframe(df), use_container_width=True, hide_index=True)


def mostrar_detalle_df(
    df,
    titulo="Detalle",
    key="detalle",
    contexto_respuesta=None,
    max_rows=None,  # ✅ Sin límite por defecto
    enable_chart=True,
    enable_explain=True,
):
    """
    ✅ VERSIÓN CON ESTADO PERSISTENTE
    El detalle NO desaparece al hacer refresh/rerun
    """
    # ---------------------------------
    # Validaciones básicas
    # ---------------------------------
    if df is None:
        return

    try:
        if hasattr(df, "empty") and df.empty:
            return
    except Exception:
        pass

    # ✅ GUARDAR EN SESSION STATE (persiste entre reruns)
    estado_key = f"detalle_{key}_estado"
    if estado_key not in st.session_state:
        st.session_state[estado_key] = {
            "df": df.copy(),
            "titulo": titulo,
            "contexto": contexto_respuesta,
            "ver_tabla": True,
            "ver_grafico": False,
            "ver_explicacion": False,
        }
    else:
        # Actualizar solo si cambió el DF
        if not df.equals(st.session_state[estado_key]["df"]):
            st.session_state[estado_key]["df"] = df.copy()
            st.session_state[estado_key]["titulo"] = titulo
            st.session_state[estado_key]["contexto"] = contexto_respuesta

    # Usar datos del estado
    estado = st.session_state[estado_key]
    df_guardado = estado["df"]
    titulo_guardado = estado["titulo"]
    contexto_guardado = estado["contexto"]

    # ---------------------------------
    # DATASET COMPLETO PARA CÁLCULOS
    # ---------------------------------
    df_full = df_guardado.copy()

    # ---------------------------------
    # DATASET RECORTADO PARA TABLA
    # ---------------------------------
    if max_rows is not None:
        try:
            df_view = df_full.head(int(max_rows)).copy()
        except Exception:
            df_view = df_full.copy()
    else:
        df_view = df_full.copy()

    # ---------------------------------
    # HEADER
    # ---------------------------------
    st.markdown(f"### {titulo_guardado}")

    # ---------------------------------
    # CHECKS UI (con estado persistente)
    # ---------------------------------
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        ver_tabla = st.checkbox(
            "📄 Ver tabla (detalle)",
            key=f"{key}_tabla",
            value=estado["ver_tabla"]
        )
        if ver_tabla != estado["ver_tabla"]:
            st.session_state[estado_key]["ver_tabla"] = ver_tabla

    with col2:
        ver_grafico = False
        if enable_chart:
            ver_grafico = st.checkbox(
                "📈 Ver gráfico",
                key=f"{key}_grafico",
                value=estado["ver_grafico"]
            )
            if ver_grafico != estado["ver_grafico"]:
                st.session_state[estado_key]["ver_grafico"] = ver_grafico

    with col3:
        ver_explicacion = False
        if enable_explain:
            ver_explicacion = st.checkbox(
                "🧠 Ver explicación",
                key=f"{key}_explica",
                value=estado["ver_explicacion"]
            )
            if ver_explicacion != estado["ver_explicacion"]:
                st.session_state[estado_key]["ver_explicacion"] = ver_explicacion

    # ---------------------------------
    # TABLA (LIMITADA O COMPLETA)
    # ---------------------------------
    if ver_tabla:
        try:
            st.dataframe(
                df_view,
                use_container_width=True,
                hide_index=True,
                height=400
            )
        except Exception:
            st.dataframe(df_view)

        try:
            total_full = len(df_full)
            total_view = len(df_view)
            if max_rows is not None and total_full > total_view:
                st.caption(
                    f"📊 Mostrando {total_view:,} de {total_full:,} registros. "
                    f"Gráficos y explicación usan el dataset completo."
                )
            else:
                st.caption(f"📊 Mostrando {total_full:,} registros")
        except Exception:
            pass

    # ---------------------------------
    # GRÁFICOS (DATASET COMPLETO)
    # ---------------------------------
    if ver_grafico:
        try:
            _render_graficos_compras(df_full, key_base=key)
        except Exception as e:
            st.warning(f"No se pudo generar el gráfico: {str(e)}")

    # ---------------------------------
    # EXPLICACIÓN (DATASET COMPLETO)
    # ---------------------------------
    if ver_explicacion:
        try:
            _render_explicacion_compras(df_full)
        except Exception as e:
            st.warning(f"No se pudo generar la explicación: {str(e)}")


def Compras_IA():
    """
    ✅ Chat mejorado con estado persistente del detalle
    """
    st.subheader("🛒 Compras IA")
    st.markdown("*Integrado con OpenAI*")

    # Inicializar historial
    if "chat_historial" not in st.session_state:
        st.session_state.chat_historial = []

    # Mostrar historial (últimos 15 mensajes)
    for msg in st.session_state.chat_historial[-15:]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input del usuario
    prompt = st.chat_input("Escribí tu consulta… (ej: compras roche noviembre 2025)")

    if prompt:
        # Agregar mensaje del usuario
        st.session_state.chat_historial.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("🔎 Procesando..."):
                resp, df = procesar_pregunta_router(prompt)
                
                # ✅ Guardar respuesta en session_state ANTES de renderizar
                st.session_state["ultima_respuesta"] = resp
                st.session_state["ultimo_df"] = df
                st.session_state["ultima_pregunta"] = prompt
                
                # Render especial (tabs/sugerencias/etc)
                render_orquestador_output(prompt, resp, df)

        # Guardar en historial
        st.session_state.chat_historial.append({"role": "assistant", "content": resp})

    # ✅ MOSTRAR DETALLE PERSISTENTE (si existe)
    if "ultimo_df" in st.session_state and st.session_state["ultimo_df"] is not None:
        if not st.session_state["ultimo_df"].empty:
            mostrar_detalle_df(
                df=st.session_state["ultimo_df"],
                titulo=st.session_state.get("ultima_respuesta", "Detalle"),
                key="compras_detalle_principal",
                max_rows=None,  # Sin límite
                enable_chart=True,
                enable_explain=True
            )
