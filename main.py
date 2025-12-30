# =========================
# MAIN - ORQUESTADOR PRINCIPAL
# =========================
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Tuple, Optional
from supabase_client import supabase
import json
import re
import io
import plotly.express as px
import plotly.graph_objects as go

# =========================
# CONFIGURACIÓN DEBUG
# =========================
DEBUG_MODE = False  # Cambiar a True para ver debug

# =====================================================================
# 🔐 SISTEMA DE AUTENTICACIÓN
# =====================================================================
from auth import init_db
from login_page import (
    require_auth,
    show_user_info_sidebar,
    get_current_user,
    logout,
    LOGIN_CSS
)

# Inicializar base de datos de usuarios
init_db()

# ======================================================
# 🔔 CAMPANITA GLOBAL DE PEDIDOS INTERNOS
# ======================================================
from pedidos import contar_notificaciones_no_leidas

user = st.session_state.get("user", {})
usuario_actual = user.get("usuario", user.get("email", ""))

if usuario_actual:
    cant_pendientes = contar_notificaciones_no_leidas(usuario_actual)

    col_notif, col_space = st.columns([1, 9])

    with col_notif:
        if cant_pendientes > 0:
            if st.button(
                f"🔔 {cant_pendientes}",
                key="campanita_global",
                help="Tenés pedidos internos pendientes"
            ):
                st.session_state["ir_a_pedidos"] = True
                st.rerun()
        else:
            st.markdown("🔔")

    st.markdown("---")

# =========================
# IMPORTS DE SQL_QUERIES
# =========================
from sql_queries import (
    # Conexión y ejecución
    get_db_connection,
    ejecutar_consulta,
    
    # Helpers SQL
    _sql_fecha_expr,
    _sql_total_num_expr_general,
    
    # Listados
    get_lista_proveedores,
    get_lista_tipos_comprobante,
    get_lista_articulos,
    get_valores_unicos,
    
    # Facturas
    get_detalle_factura_por_numero,
    get_total_factura_por_numero,
    get_ultima_factura_de_articulo,
    get_ultima_factura_inteligente,
    get_ultima_factura_numero_de_articulo,
    get_facturas_de_articulo,
    
    # Detalle compras proveedor
    get_detalle_compras_proveedor_mes,
    get_detalle_compras_proveedor_anio,
    get_total_compras_proveedor_anio,
    get_detalle_compras_proveedor_anios,
    
    # Detalle compras artículo
    get_detalle_compras_articulo_mes,
    get_detalle_compras_articulo_anio,
    get_total_compras_articulo_anio,
    
    # Comparaciones meses
    get_comparacion_proveedor_meses,
    get_comparacion_articulo_meses,
    get_comparacion_familia_meses_moneda,
    
    # Comparaciones años
    get_comparacion_articulo_anios,
    get_comparacion_proveedor_anios_monedas,
    get_comparacion_familia_anios_monedas,
    
    # Gastos familias
    get_gastos_todas_familias_mes,
    get_gastos_todas_familias_anio,
    get_gastos_secciones_detalle_completo,
    get_gastos_por_familia,
    
    # Otros
    get_detalle_compras,
    get_compras_por_mes_excel,
    get_total_compras_proveedor_moneda_periodos,
    get_top_10_proveedores_chatbot,
    
    # Dashboard
    get_dashboard_totales,
    get_dashboard_compras_por_mes,
    get_dashboard_top_proveedores,
    get_dashboard_gastos_familia,
    get_dashboard_ultimas_compras,
    get_alertas_vencimiento_multiple,
    
    # Stock (placeholders)
    get_lista_articulos_stock,
    get_lista_familias_stock,
    get_lista_depositos_stock,
    get_stock_total,
    get_stock_por_familia,
    get_stock_por_deposito,
    get_stock_articulo,
    get_stock_familia,
    get_lotes_por_vencer,
    get_lotes_vencidos,
    get_stock_bajo,
    get_stock_lote_especifico,
    buscar_stock_por_lote
)

# =========================
# IMPORTS DE NUESTROS MÓDULOS
# =========================
from intent_detector import *
from intent_detector import (
    _extraer_patron_libre,
    _extraer_lista_familias,
    _extraer_mes_key
)

# OpenAI
from openai import OpenAI

# =========================
# UI - MANEJO DE RESPUESTAS ESPECIALES DEL ORQUESTADOR
# =========================
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
            dుఫ = info.get("df_usd")
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

# =====================================================================
# HELPER PARA EXPORTAR A EXCEL
# =====================================================================

def df_to_excel(df: pd.DataFrame) -> bytes:
    """Convierte un DataFrame a bytes de Excel (.xlsx)"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    output.seek(0)
    return output.getvalue()

# =====================================================================
# CONFIGURACIÓN OPENAI
# =====================================================================

import os
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o-mini"

client = OpenAI(api_key=OPENAI_API_KEY)


# =====================================================================
# FORMATEO DE NÚMEROS (LATAM)
# =====================================================================

def _fmt_num_latam(valor, decimales: int = 2) -> str:
    """Convierte números a formato LATAM (1.568.687,40)"""
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    prefijo = ""
    if isinstance(valor, str):
        v0 = valor.strip()
        if "U$S" in v0:
            prefijo = "U$S "
        elif "$" in v0:
            prefijo = "$ "

        s = v0.replace("U$S", "").replace("$", "").strip()
        s = s.replace("(", "-").replace(")", "").replace(" ", "")

        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        else:
            if "," in s and "." not in s:
                s = s.replace(".", "").replace(",", ".")

        try:
            num = float(s)
        except Exception:
            return str(valor).strip()
    else:
        try:
            num = float(valor)
        except Exception:
            return str(valor)

    base = f"{num:,.{decimales}f}"
    latam = base.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{prefijo}{latam}".strip()


def _es_col_importe_latam(nombre_col: str) -> bool:
    """Detecta si una columna es un importe"""
    n = normalizar_texto(nombre_col or "")

    if "cantidad" in n:
        return False
    if ("factura" in n) and ("total" not in n) and ("importe" not in n) and ("monto" not in n):
        return False

    if any(k in n for k in ["total", "monto", "importe", "diferencia", "comparacion"]):
        return True
    if n.endswith("_$") or n.endswith("_usd"):
        return True

    return False


def formatear_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Formatea DataFrame con números en formato LATAM"""
    if df is None or df.empty:
        return df

    d = df.copy()
    for c in d.columns:
        if _es_col_importe_latam(c):
            d[c] = d[c].apply(_fmt_num_latam)
        elif "variacion" in normalizar_texto(c) or "%" in c:
            d[c] = d[c].apply(lambda x: (f"{float(x):.2f}%" if pd.notna(x) else ""))
    return d


# =====================================================================
# OPENAI - RESPUESTAS CONVERSACIONALES
# =====================================================================

def es_saludo_o_conversacion(texto: str) -> bool:
    """Detecta si es un saludo o conversación casual (sin consulta de datos)"""
    texto_norm = normalizar_texto(texto)
    
    # Palabras que indican consulta de datos (NO es saludo si hay alguna de estas)
    palabras_consulta = [
        'compras', 'compra', 'compre', 'compramos', 'comprado',
        'comparar', 'comparame', 'compara', 'comparacion',
        'gastos', 'gasto', 'gastamos', 'gastado', 'gastar',
        'cuanto', 'cuanta', 'cuantos', 'cuantas',  # Preguntas de cantidad
        'proveedor', 'proveedores', 'articulo', 'articulos',
        'factura', 'facturas', 'familia', 'familias',
        'stock', 'lote', 'lotes', 'vencimiento', 'vencer',
        'total', 'detalle', 'ultima', 'ultimo', 'top', 'ranking',
        '2020', '2021', '2022', '2023', '2024', '2025', '2026',
        'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
        'ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'
    ]
    
    # Si hay palabras de consulta, NO es saludo (es una consulta con saludo incluido)
    for p in palabras_consulta:
        if p in texto_norm:
            print(f"🔍 es_saludo_o_conversacion: encontró '{p}' → NO es saludo")
            return False
    
    saludos = [
        'hola', 'buenos dias', 'buenas tardes', 'buenas noches',
        'hey', 'hi', 'hello', 'que tal', 'como estas', 'como andas',
        'gracias', 'muchas gracias', 'chau', 'adios', 'hasta luego',
        'buen dia', 'saludos'
    ]
    
    for saludo in saludos:
        if saludo in texto_norm:
            return True
    
    # Mensajes muy cortos sin palabras de datos
    if len(texto_norm.split()) <= 3:
        return True
    
    return False


def es_pregunta_conocimiento(texto: str) -> bool:
    """Detecta si es una pregunta de conocimiento general"""
    texto_norm = normalizar_texto(texto)
    
    patrones = [
        r'^que es\b',
        r'^que son\b', 
        r'^como funciona\b',
        r'^para que sirve\b',
        r'^cual es\b',
        r'^cuales son\b',
        r'^explicame\b',
        r'^que significa\b',
        r'^definicion de\b',
    ]
    
    for patron in patrones:
        if re.search(patron, texto_norm):
            palabras_datos = ['compras', 'gastos', 'proveedor', 'articulo', 'factura', 'familia']
            if not any(p in texto_norm for p in palabras_datos):
                return True
    
    return False


def responder_con_openai(pregunta: str, tipo: str) -> str:
    """Responde con OpenAI (conversación o conocimiento)"""
    if tipo == "conversacion":
        system_msg = """Eres un asistente amigable de un sistema de análisis de compras de laboratorio.
Responde de forma natural, cálida y breve a saludos y conversación casual.
Menciona que estás aquí para ayudar con consultas de compras, gastos, proveedores y facturas.
Responde en español."""
        max_tok = 200
    else:
        system_msg = """Eres un asistente experto que trabaja en un laboratorio clínico.
Responde preguntas de conocimiento general de forma clara, precisa y útil.
Si la pregunta es sobre términos médicos, científicos o de laboratorio, explícalos bien.
Responde en español de forma concisa pero completa."""
        max_tok = 500
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": pregunta}
            ],
            temperature=0.5,
            max_tokens=max_tok
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "No pude procesar tu pregunta."

def recomendar_como_preguntar(pregunta: str) -> str:
    system_prompt = """
Eres un Asistente Guía para un chatbot de laboratorio.
Tu tarea NO es devolver datos ni SQL.

Debes:
- Entender qué intenta preguntar el usuario
- Recomendar cómo formular la pregunta usando preguntas estándar del sistema
- Sugerir ejemplos claros y variantes humanas (errores de tipeo, abreviaturas)
- Si falta info, pedir solo UNA aclaración

Nunca devuelvas JSON.
Nunca devuelvas resultados.
Solo recomendaciones de cómo preguntar.

Usa frases como:
- "Probá con:"
- "También podés escribir:"
- "Una forma clara de preguntarlo es:"
"""

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pregunta}
            ],
            temperature=0.3,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "No pude ayudarte a reformular la pregunta."


def obtener_sugerencia_ejecutable(pregunta: str) -> dict:
    """
    Usa OpenAI para entender qué quiso decir el usuario
    y devolver UNA sugerencia que el sistema puede ejecutar.
    SISTEMA HÍBRIDO: Interpreta lenguaje humano → Sugiere formato estándar
    """
    system_prompt = """Eres un intérprete para un chatbot de compras de laboratorio.
Tu tarea es entender lo que el usuario quiere y traducirlo a un formato que el sistema entiende.

IMPORTANTE: Debes responder SOLO en JSON válido, sin markdown ni explicaciones.

FORMATOS QUE EL SISTEMA ENTIENDE (usa estos exactamente):

COMPRAS:
- "compras {proveedor} {año}" → compras roche 2025
- "compras {proveedor} {mes} {año}" → compras roche noviembre 2025
- "detalle compras {proveedor} {año}" → detalle compras roche 2025
- "total compras {mes} {año}" → total compras noviembre 2025

COMPARACIONES:
- "comparar {proveedor} {año1} {año2}" → comparar roche 2023 2024
- "comparar {proveedor} {mes} {año1} vs {mes} {año2}" → comparar roche noviembre 2023 vs noviembre 2024
- "comparar gastos familias {año1} {año2}" → comparar gastos familias 2023 2024
- "comparar gastos familias {mes1} {mes2}" → comparar gastos familias junio julio

FACTURAS:
- "última factura {proveedor/artículo}" → última factura vitek
- "detalle factura {número}" → detalle factura 275217
- "factura completa {artículo}" → factura completa vitek

GASTOS/FAMILIAS:
- "gastos familias {mes} {año}" → gastos familias noviembre 2025
- "gastos secciones {lista} {mes} {año}" → gastos secciones G,FB noviembre 2025
- "top proveedores {mes} {año}" → top proveedores noviembre 2025
- "top 10 proveedores {año}" → top 10 proveedores 2025

STOCK:
- "stock total"
- "stock {artículo}" → stock vitek
- "stock familia {sección}" → stock familia ID
- "lotes por vencer"
- "lotes vencidos"

EJEMPLOS DE TRADUCCIÓN:
- "cuanto le compramos a roche en 2024" → "compras roche 2024"
- "que compramos de biodiagnostico en noviembre" → "compras biodiagnostico noviembre 2025"
- "comparame roche del año pasado con este" → "comparar roche 2024 2025"
- "Comparame compras Roche Novimbr 2023 2024" → "comparar roche noviembre 2023 vs noviembre 2024"
- "cuanto gastamos en familias en junio y julio" → "comparar gastos familias junio julio"
- "cuando fue la ultima vez que vino vitek" → "última factura vitek"
- "cuanto hay en stock de reactivos" → "stock total"
- "quienes son los proveedores que mas compramos" → "top 10 proveedores 2025"

ERRORES COMUNES QUE DEBES ENTENDER:
- "novimbre", "novienbre", "novimbr" → noviembre
- "setiembre", "septirmbre" → septiembre  
- "oct", "nov", "dic" → octubre, noviembre, diciembre
- Sin tildes: "ultima", "cuanto", "deposito"
- "comparame", "comparar", "compara" → comparar

RESPONDE SOLO JSON (sin ```json ni nada más):
{"entendido": "Querés ver...", "sugerencia": "comando exacto", "alternativas": ["opción 1", "opción 2"]}
"""

    try:
        print(f"🤖 Llamando a IA con: {pregunta}")
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pregunta}
            ],
            temperature=0.2,
            max_tokens=250,
            timeout=15  # Timeout de 15 segundos
        )
        content = response.choices[0].message.content.strip()
        print(f"🤖 IA respondió: {content}")
        
        # Limpiar markdown si viene
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)
        content = content.strip()
        
        resultado = json.loads(content)
        print(f"🤖 JSON parseado: {resultado}")
        return resultado
        
    except json.JSONDecodeError as e:
        print(f"❌ Error parseando JSON: {e}")
        print(f"❌ Contenido recibido: {content if 'content' in dir() else 'N/A'}")
        return {'entendido': '', 'sugerencia': '', 'alternativas': []}
    except Exception as e:
        print(f"❌ Error en obtener_sugerencia_ejecutable: {e}")
        return {'entendido': '', 'sugerencia': '', 'alternativas': []}


# =====================================================================
# OPENAI - FALLBACK SQL
# =====================================================================

def _extraer_json_de_texto(s: str) -> Optional[dict]:
    """Extrae JSON de respuesta de OpenAI"""
    if not s:
        return None
    s = s.strip()

    m = re.search(r"```json\s*(\{.*?\})\s*```", s, flags=re.DOTALL | re.IGNORECASE)
    if m:
        s = m.group(1).strip()

    m2 = re.search(r"```\s*(\{.*?\})\s*```", s, flags=re.DOTALL)
    if m2:
        s = m2.group(1).strip()

    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None
    return None


def _sql_es_seguro(sql: str) -> bool:
    """Verifica que el SQL sea solo SELECT y seguro"""
    if not sql:
        return False
    s = sql.strip().lower()

    if ";" in s:
        return False
    if not s.startswith("select"):
        return False
    if "from chatbot" not in s:
        return False

    bloqueos = [
        "insert ", "update ", "delete ", "drop ", "alter ", "create ",
        "truncate ", "grant ", "revoke ", "information_schema", "mysql.",
        "into outfile", "load_file(", "sleep(", "benchmark("
    ]
    for b in bloqueos:
        if b in s:
            return False

    return True


def fallback_openai_sql(pregunta: str, motivo: str) -> Tuple[Optional[str], Optional[pd.DataFrame], Optional[str]]:
    """FALLBACK: Genera SQL con OpenAI cuando las reglas no funcionan"""
    hoy = datetime.now()
    mes_actual = hoy.strftime('%Y-%m')
    
    schema_info = """
ESQUEMA DE LA BASE DE DATOS:
- Tabla: chatbot
- Columnas:
  * tipo_comprobante (texto) - Filtrar compras: tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%'
  * Proveedor (texto)
  * Familia (texto)
  * Tipo Articulo (texto)
  * Articulo (texto)
  * Mes (texto) - formato YYYY-MM
  * fecha (texto) - YYYY-MM-DD o DD/MM/YYYY
  * cantidad (texto) - número con coma decimal
  * Total (texto) - formato 78.160,33 (puntos miles, coma decimal)
  * N Factura (texto)

REGLAS:
1. SIEMPRE filtrar: (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%')
2. Para Total numérico: CAST(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(TRIM(Total), '.', ''), ',', '.'), '(', '-'), ')', ''), '$', '') AS DECIMAL(15,2))
3. Para Mes: TRIM(Mes) = 'YYYY-MM'
4. LIMIT 100 si es detalle
5. SOLO SELECT
"""

    system_prompt = f"""Eres un experto en SQL para MySQL. Convierte la pregunta a SQL.

{schema_info}

Fecha actual: {hoy.strftime('%Y-%m-%d')}, Mes actual: {mes_actual}

Responde SOLO con JSON:
{{"sql": "SELECT ...", "titulo": "descripción corta", "respuesta": "explicación breve de qué hace"}}
"""

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Motivo: {motivo}\n\nPregunta: {pregunta}"}
            ],
            temperature=0.1,
            max_tokens=800
        )
        
        content = response.choices[0].message.content.strip()
        obj = _extraer_json_de_texto(content)
        
        if not obj:
            return None, None, None
        
        sql = str(obj.get("sql", "")).strip()
        titulo = str(obj.get("titulo", "Resultado")).strip()
        respuesta = str(obj.get("respuesta", "")).strip()
        
        if not _sql_es_seguro(sql):
            return None, None, None
        
        df = ejecutar_consulta(sql)
        return titulo, df, respuesta
        
    except Exception as e:
        return None, None, None


# =====================================================================
# HELPERS - FACTURAS
# =====================================================================
# =====================================================================
# HELPERS - FACTURAS
# =====================================================================

def extraer_numero_factura(pregunta: str) -> str | None:
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


def normalizar_factura_para_db(nro_raw: str) -> tuple[str | None, str | None, str | None]:
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



# =====================================================================
# PROCESADOR PRINCIPAL - ORQUESTADOR
# =====================================================================

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
                    total = df['STOCK'].apply(lambda x: float(str(x).replace(',', '.').replace(' ', '')) if pd.notna(x) else 0).sum()
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
        
        texto_lower = normalizar_texto(pregunta)
        
        # Excluir saludos simples de la IA (ya se manejan arriba)
        saludos = ['hola', 'buenos dias', 'buenas tardes', 'buenas noches', 'gracias', 'chau', 'adios']
        es_saludo = any(s in texto_lower for s in saludos) and len(texto_lower.split()) <= 3
        
        if es_saludo:
            return "👋 ¡Hola! ¿En qué te puedo ayudar?", None
        
        # Para TODO lo demás → Mostrar sugerencia con IA
        return "__MOSTRAR_SUGERENCIA__", None


# =====================================================================
# MÓDULO BUSCADOR IA
# =====================================================================

def detectar_intencion_buscador(pregunta: str) -> str:
    """
    Detecta qué tipo de consulta quiere el usuario en el buscador.
    Devuelve: 'ultima_factura', 'total_compras', 'cuantas_facturas', 'detalle', 'general'
    """
    p = pregunta.lower().strip()
    
    # Última factura / cuándo llegó
    if any(k in p for k in ['ultimo', 'última', 'ultima', 'cuando llego', 'cuando vino', 'llegó', 'vino']):
        return 'ultima_factura'
    
    # Total / cuánto gastamos
    if any(k in p for k in ['total', 'cuanto', 'cuánto', 'gastamos', 'compramos', 'suma']):
        return 'total_compras'
    
    # Cuántas facturas
    if any(k in p for k in ['cuantas', 'cuántas', 'cantidad de', 'numero de']):
        return 'cuantas_facturas'
    
    # Detalle
    if any(k in p for k in ['detalle', 'todas', 'listado', 'lista']):
        return 'detalle'
    
    return 'general'


def ejecutar_consulta_buscador(intencion: str, proveedor: str, articulo: str, 
                                fecha_desde, fecha_hasta) -> Tuple[str, Optional[pd.DataFrame]]:
    """
    Ejecuta la consulta específica según la intención detectada.
    Usa directamente los filtros seleccionados.
    """
    
    # Limpiar valores
    prov_clean = proveedor.split('(')[0].strip() if proveedor and proveedor != "Todos" else None
    art_clean = articulo.strip() if articulo and articulo != "Todos" else None
    
    # =====================================================================
    # ÚLTIMA FACTURA
    # =====================================================================
    if intencion == 'ultima_factura':
        if art_clean:
            # Buscar última factura del artículo
            df = get_ultima_factura_de_articulo(art_clean)
            if df is not None and not df.empty:
                return f"🧾 Última factura del artículo '{art_clean}':", df
            return f"No encontré facturas del artículo '{art_clean}'.", None
        
        elif prov_clean:
            # Buscar última factura del proveedor
            df = get_ultima_factura_inteligente(prov_clean)
            if df is not None and not df.empty:
                return f"🧾 Última factura de '{prov_clean}':", df
            return f"No encontré facturas de '{prov_clean}'.", None
        
        return "Seleccioná un proveedor o artículo para ver la última factura.", None
    
    # =====================================================================
    # TOTAL COMPRAS
    # =====================================================================
    elif intencion == 'total_compras':
        fecha_expr = _sql_fecha_expr()
        total_expr = _sql_total_num_expr_general()
        
        sql = f"""
            SELECT 
                COUNT(*) AS Registros,
                SUM({total_expr}) AS Total
            FROM chatbot
            WHERE (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
        """
        params = []
        
        if prov_clean:
            sql += " AND LOWER(TRIM(Proveedor)) LIKE LOWER(%s)"
            params.append(f"%{prov_clean}%")
        
        if art_clean:
            sql += " AND LOWER(TRIM(Articulo)) LIKE LOWER(%s)"
            params.append(f"%{art_clean}%")
        
        if fecha_desde:
            sql += f" AND {fecha_expr} >= %s"
            params.append(fecha_desde.strftime('%Y-%m-%d'))
        
        if fecha_hasta:
            sql += f" AND {fecha_expr} <= %s"
            params.append(fecha_hasta.strftime('%Y-%m-%d'))
        
        df = ejecutar_consulta(sql, tuple(params) if params else None)
        
        if df is not None and not df.empty:
            registros = df['Registros'].iloc[0]
            total = df['Total'].iloc[0]
            
            # Construir contexto para el título
            contexto = []
            if prov_clean:
                contexto.append(f"proveedor '{prov_clean}'")
            if art_clean:
                contexto.append(f"artículo '{art_clean}'")
            if fecha_desde or fecha_hasta:
                if fecha_desde and fecha_hasta:
                    contexto.append(f"del {fecha_desde.strftime('%d/%m/%Y')} al {fecha_hasta.strftime('%d/%m/%Y')}")
                elif fecha_desde:
                    contexto.append(f"desde {fecha_desde.strftime('%d/%m/%Y')}")
                else:
                    contexto.append(f"hasta {fecha_hasta.strftime('%d/%m/%Y')}")
            
            titulo = "💰 Total de compras"
            if contexto:
                titulo += f" ({', '.join(contexto)})"
            
            total_fmt = f"${float(total):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if total else "$0"
            
            resultado = pd.DataFrame({
                'Concepto': [titulo],
                'Registros': [int(registros) if registros else 0],
                'Total': [total_fmt]
            })
            
            return f"✅ {titulo}:", resultado
        
        return "No encontré compras con esos filtros.", None
    
    # =====================================================================
    # CUÁNTAS FACTURAS
    # =====================================================================
    elif intencion == 'cuantas_facturas':
        fecha_expr = _sql_fecha_expr()
        
        sql = f"""
            SELECT 
                COUNT(DISTINCT `N Factura`) AS Facturas,
                COUNT(*) AS Lineas
            FROM chatbot
            WHERE (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
        """
        params = []
        
        if prov_clean:
            sql += " AND LOWER(TRIM(Proveedor)) LIKE LOWER(%s)"
            params.append(f"%{prov_clean}%")
        
        if art_clean:
            sql += " AND LOWER(TRIM(Articulo)) LIKE LOWER(%s)"
            params.append(f"%{art_clean}%")
        
        if fecha_desde:
            sql += f" AND {fecha_expr} >= %s"
            params.append(fecha_desde.strftime('%Y-%m-%d'))
        
        if fecha_hasta:
            sql += f" AND {fecha_expr} <= %s"
            params.append(fecha_hasta.strftime('%Y-%m-%d'))
        
        df = ejecutar_consulta(sql, tuple(params) if params else None)
        
        if df is not None and not df.empty:
            facturas = df['Facturas'].iloc[0]
            lineas = df['Lineas'].iloc[0]
            
            resultado = pd.DataFrame({
                'Concepto': ['Cantidad de facturas'],
                'Facturas únicas': [int(facturas) if facturas else 0],
                'Líneas totales': [int(lineas) if lineas else 0]
            })
            
            return "📊 Cantidad de facturas:", resultado
        
        return "No encontré facturas con esos filtros.", None
    
# =====================================================================
    # GENERAL (pasar al procesador principal)
    # =====================================================================
    return None, None


# =====================================================================
# FUNCIÓN BUSCAR COMPROBANTES (para Buscador IA)
# =====================================================================

def buscar_comprobantes(
    proveedor: str = None,
    tipo_comprobante: str = None,
    articulo: str = None,
    fecha_desde = None,
    fecha_hasta = None,
    texto_busqueda: str = None
) -> pd.DataFrame:
    """Busca comprobantes en chatbot_raw con filtros opcionales."""
    try:
        sql = """
            SELECT 
                "Fecha",
                "Tipo Comprobante" AS "Tipo",
                "Nro. Comprobante" AS "Nro Factura",
                "Cliente / Proveedor" AS "Proveedor",
                "Articulo",
                "Cantidad",
                "Monto Neto" AS "Monto"
            FROM chatbot_raw
            WHERE 1=1
        """
        params = []
        
        if tipo_comprobante:
            sql += ' AND "Tipo Comprobante" = %s'
            params.append(tipo_comprobante)
        else:
            sql += ' AND ("Tipo Comprobante" = \'Compra Contado\' OR "Tipo Comprobante" LIKE \'Compra%%\')'
        
        if proveedor:
            prov_clean = proveedor.split('(')[0].strip()
            sql += ' AND LOWER(TRIM("Cliente / Proveedor")) LIKE LOWER(%s)'
            params.append(f"%{prov_clean}%")
        
        if articulo:
            sql += ' AND LOWER(TRIM("Articulo")) LIKE LOWER(%s)'
            params.append(f"%{articulo}%")
        
        if fecha_desde:
            sql += ' AND "Fecha" >= %s'
            params.append(fecha_desde.strftime('%Y-%m-%d'))
        
        if fecha_hasta:
            sql += ' AND "Fecha" <= %s'
            params.append(fecha_hasta.strftime('%Y-%m-%d'))
        
        if texto_busqueda and texto_busqueda.strip():
            txt = texto_busqueda.strip()
            sql += """
                AND (
                    LOWER("Nro. Comprobante") LIKE LOWER(%s) OR
                    LOWER("Articulo") LIKE LOWER(%s) OR
                    LOWER("Cliente / Proveedor") LIKE LOWER(%s)
                )
            """
            params.extend([f"%{txt}%", f"%{txt}%", f"%{txt}%"])
        
        sql += ' ORDER BY "Fecha" DESC LIMIT 500'
        
        return ejecutar_consulta(sql, tuple(params) if params else None)
    
    except Exception as e:
        print(f"Error en buscar_comprobantes: {e}")
        return pd.DataFrame()
        
def mostrar_buscador():
    """Pantalla del Buscador de Comprobantes - CON INTENCIONES IA"""
    
    st.title("🔍 Buscador de Comprobantes")
    st.markdown("Búsqueda con filtros + preguntas en lenguaje natural")
    
    # --- Selector principal: Factura o Lote ---
    tipo_busqueda = st.radio(
        "Buscar por:",
        ["📄 Factura", "📦 Lote"],
        horizontal=True,
        key="tipo_busqueda"
    )
    
    st.markdown("---")
    
      # =========================================================================
    # MODO FACTURA (tabla chatbot)
    # =========================================================================
    if tipo_busqueda == "📄 Factura":

        # ✅ CSS: Botón "🔎 Buscar" más chico (solo en Factura)
        st.markdown("""
        <style>
        div[data-testid="stButton"] button{
          padding: 0.25rem 0.65rem !important;
          font-size: 0.85rem !important;
          line-height: 1.1 !important;
          min-height: 32px !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # --- Cargar listas desde la DB ---
        lista_proveedores = get_lista_proveedores()
        lista_tipos = get_lista_tipos_comprobante()
        lista_articulos = get_lista_articulos()

        # --- Fila 1: Filtros principales ---
        col1, col2, col3, col4 = st.columns([2, 3, 3, 3])

        with col1:
            empresa = st.selectbox("Empresa", ["FERTILAB SA"], disabled=True)

        with col2:
            proveedor = st.selectbox(
                "Cliente / Proveedor",
                lista_proveedores,
                index=0
            )

        with col3:
            tipo_comprobante = st.selectbox(
                "Tipo de Comprobante",
                lista_tipos,
                index=0
            )

        with col4:
            articulo = st.selectbox(
                "Artículo",
                lista_articulos,
                index=0
            )

        # --- Fila 2: Fechas y búsqueda ---
        col5, col6, col7, col8, col9 = st.columns([2, 2, 3, 3, 1])

        with col5:
            fecha_desde = st.date_input(
                "Fecha desde",
                value=None,
                format="DD/MM/YYYY"
            )

        with col6:
            fecha_hasta = st.date_input(
                "Fecha hasta",
                value=None,
                format="DD/MM/YYYY"
            )

        with col7:
            texto_busqueda = st.text_input(
                "Buscar número o texto",
                placeholder="Ej: 275217 o VITEK"
            )

        with col8:
            pregunta_ia = st.text_input(
                "Preguntar IA (opcional)",
                placeholder="Ej: cuándo llegó el último?"
            )

        with col9:
            st.markdown("<br>", unsafe_allow_html=True)
            buscar = st.button("🔎 Buscar", use_container_width=True)


        # --- Ayuda contextual ---
        if proveedor != "Todos" or articulo != "Todos":
            contexto_actual = []
            if proveedor != "Todos":
                contexto_actual.append(f"**{proveedor.split('(')[0].strip()}**")
            if articulo != "Todos":
                contexto_actual.append(f"**{articulo}**")
            
            st.caption(f"💡 Contexto seleccionado: {', '.join(contexto_actual)} — Podés preguntar: 'cuánto compramos', 'última factura', 'total del mes'...")
        
        st.markdown("---")
        
        # --- Ejecutar búsqueda FACTURA ---
        if buscar:
            
            # OPCIÓN 1: PREGUNTA IA
            if pregunta_ia and pregunta_ia.strip():
                intencion = detectar_intencion_buscador(pregunta_ia)
                
                contexto_texto = []
                if proveedor != "Todos":
                    contexto_texto.append(f"proveedor: {proveedor.split('(')[0].strip()}")
                if articulo != "Todos":
                    contexto_texto.append(f"artículo: {articulo}")
                
                if contexto_texto:
                    st.info(f"🧠 Procesando: *\"{pregunta_ia}\"* con contexto: {', '.join(contexto_texto)}")
                else:
                    st.info(f"🧠 Procesando: *\"{pregunta_ia}\"*")
                
                with st.spinner("🧠 Analizando..."):
                    respuesta, df = ejecutar_consulta_buscador(
                        intencion,
                        proveedor if proveedor != "Todos" else None,
                        articulo if articulo != "Todos" else None,
                        fecha_desde,
                        fecha_hasta
                    )
                    
                    if respuesta is None:
                        pregunta_completa = pregunta_ia.strip()
                        if proveedor != "Todos":
                            pregunta_completa += f" {proveedor.split('(')[0].strip()}"
                        if articulo != "Todos":
                            pregunta_completa += f" {articulo}"
                        respuesta, df = procesar_pregunta(pregunta_completa)
                    
                    render_orquestador_output(pregunta_completa, respuesta, df)
                    
                    if df is not None and not df.empty:
                        st.dataframe(
                            formatear_dataframe(df), 
                            use_container_width=True, 
                            hide_index=True
                        )
            
            # OPCIÓN 2: BÚSQUEDA POR FILTROS
            else:
                with st.spinner("🔍 Buscando comprobantes..."):
                    df = buscar_comprobantes(
                        proveedor=proveedor if proveedor != "Todos" else None,
                        tipo_comprobante=tipo_comprobante if tipo_comprobante != "Todos" else None,
                        articulo=articulo if articulo != "Todos" else None,
                        fecha_desde=fecha_desde,
                        fecha_hasta=fecha_hasta,
                        texto_busqueda=texto_busqueda
                    )
                    
                    if df is not None and not df.empty:
                        st.success(f"✅ Se encontraron **{len(df)}** comprobantes")
                        
                        if 'Monto' in df.columns:
                            try:
                                montos = df['Monto'].apply(lambda x: float(
                                    str(x).replace('.', '').replace(',', '.').replace('$', '').replace(' ', '')
                                ) if pd.notna(x) else 0)
                                total = montos.sum()
                                st.info(f"💰 **Total:** ${total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
                            except:
                                pass
                        
                        st.dataframe(
                            formatear_dataframe(df),
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        excel_data = df_to_excel(df)
                        st.download_button(
                            label="📥 Descargar Excel",
                            data=excel_data,
                            file_name="comprobantes.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.warning("⚠️ No se encontraron resultados con esos filtros")
        
        else:
            st.info("👆 Seleccioná filtros y presioná **Buscar**, o escribí una pregunta en 'Preguntar IA'")
    
    # =========================================================================
    # MODO LOTE (tabla stock)
    # =========================================================================
    else:  # tipo_busqueda == "📦 Lote"
        
        # --- Cargar listas desde tabla stock ---
        lista_articulos_stock = get_lista_articulos_stock()
        lista_familias_stock = get_lista_familias_stock()
        lista_depositos_stock = get_lista_depositos_stock()
        
        # --- Fila 1: Filtros principales ---
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            articulo_stock = st.selectbox(
                "Artículo",
                lista_articulos_stock,
                index=0,
                key="articulo_stock"
            )
        
        with col2:
            familia_stock = st.selectbox(
                "Familia",
                lista_familias_stock,
                index=0,
                key="familia_stock"
            )
        
        with col3:
            deposito_stock = st.selectbox(
                "Depósito",
                lista_depositos_stock,
                index=0,
                key="deposito_stock"
            )
        
        with col4:
            lote_busqueda = st.text_input(
                "Número de Lote",
                placeholder="Ej: D250829AF",
                key="lote_busqueda"
            )
        
        # --- Fila 2: Búsqueda y botón ---
        col5, col6, col7 = st.columns([4, 4, 1])
        
        with col5:
            texto_busqueda_stock = st.text_input(
                "Buscar texto (artículo, código o lote)",
                placeholder="Ej: VITEK o 15625",
                key="texto_stock"
            )
        
        with col6:
            pregunta_ia_stock = st.text_input(
                "Preguntar IA (opcional)",
                placeholder="Ej: qué lotes vencen pronto?",
                key="pregunta_stock"
            )
        
        with col7:
            st.markdown("<br>", unsafe_allow_html=True)
            buscar_stock = st.button("🔎 Buscar", use_container_width=True, key="btn_stock")
        
        st.markdown("---")
        
        # --- Ejecutar búsqueda LOTE ---
        if buscar_stock:
            
            with st.spinner("🔍 Buscando en stock..."):
                df = buscar_stock_por_lote(
                    articulo=articulo_stock if articulo_stock != "Todos" else None,
                    lote=lote_busqueda,
                    familia=familia_stock if familia_stock != "Todos" else None,
                    deposito=deposito_stock if deposito_stock != "Todos" else None,
                    texto_busqueda=texto_busqueda_stock
                )
                
                if df is not None and not df.empty:
                    st.success(f"✅ Se encontraron **{len(df)}** registros de stock")
                    
                    # Calcular total de stock
                    if 'STOCK' in df.columns:
                        try:
                            total_stock = df['STOCK'].apply(lambda x: float(
                                str(x).replace(',', '.')
                            ) if pd.notna(x) else 0).sum()
                            st.info(f"📦 **Stock total:** {total_stock:,.0f} unidades".replace(',', '.'))
                        except:
                            pass
                    
                    st.dataframe(
                        df,
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # Descargar Excel
                    excel_data = df_to_excel(df)
                    st.download_button(
                        label="📥 Descargar Excel",
                        data=excel_data,
                        file_name="stock_lotes.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("⚠️ No se encontraron resultados con esos filtros")
        
        else:
            st.info("👆 Seleccioná filtros y presioná **Buscar** para buscar lotes en stock")

# =====================================================================
# MÓDULO STOCK IA (CHATBOT)
# =====================================================================

def detectar_intencion_stock(texto: str) -> dict:
    """Detecta la intención para consultas de stock"""
    texto_lower = texto.lower().strip()
    
    # Vencimientos
    if any(k in texto_lower for k in ['vencer', 'vencen', 'vencimiento', 'vence', 'por vencer', 'proximo a vencer']):
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
    
    # Stock por familia
    if any(k in texto_lower for k in ['familia', 'familias', 'por familia', 'seccion', 'secciones']):
        # Ver si menciona una familia específica
        familias_conocidas = ['id', 'fb', 'g', 'tr', 'xx', 'hm', 'mi']
        for fam in familias_conocidas:
            if fam in texto_lower.split():
                return {'tipo': 'stock_familia', 'familia': fam.upper(), 'debug': f'Stock familia {fam.upper()}'}
        return {'tipo': 'stock_por_familia', 'debug': 'Stock por familias'}
    
    # Stock por depósito
    if any(k in texto_lower for k in ['deposito', 'depósito', 'depositos', 'depósitos', 'almacen']):
        return {'tipo': 'stock_por_deposito', 'debug': 'Stock por depósito'}
    
    # Stock de artículo específico
    if any(k in texto_lower for k in ['stock', 'cuanto hay', 'cuánto hay', 'tenemos', 'disponible', 'hay']):
        # Extraer nombre del artículo
        palabras_excluir = ['stock', 'cuanto', 'cuánto', 'hay', 'de', 'del', 'tenemos', 'disponible', 'el', 'la', 'los', 'las', 'que']
        palabras = [p for p in texto_lower.split() if p not in palabras_excluir and len(p) > 2]
        if palabras:
            articulo = ' '.join(palabras)
            return {'tipo': 'stock_articulo', 'articulo': articulo, 'debug': f'Stock de artículo: {articulo}'}
    
    # Total general
    if any(k in texto_lower for k in ['total', 'resumen', 'general', 'todo el stock']):
        return {'tipo': 'stock_total', 'debug': 'Stock total'}
    
    # Por defecto, intentar buscar artículo
    return {'tipo': 'stock_articulo', 'articulo': texto, 'debug': f'Búsqueda general: {texto}'}


def procesar_pregunta_stock(pregunta: str) -> Tuple[str, Optional[pd.DataFrame]]:
    """Procesa una pregunta sobre stock"""
    
    intencion = detectar_intencion_stock(pregunta)
    tipo = intencion.get('tipo')
    
    print(f"🔍 STOCK IA - Intención: {tipo}")
    print(f"📋 Debug: {intencion.get('debug')}")
    
    # Stock total
    if tipo == 'stock_total':
        df = get_stock_total()
        if df is not None and not df.empty:
            return "📦 Resumen de stock total:", df
        return "No pude obtener el stock total.", None
    
    # Stock por familia
    if tipo == 'stock_por_familia':
        df = get_stock_por_familia()
        if df is not None and not df.empty:
            return "📊 Stock agrupado por familia:", df
        return "No encontré datos de stock por familia.", None
    
    # Stock de una familia específica
    if tipo == 'stock_familia':
        familia = intencion.get('familia', '')
        df = get_stock_familia(familia)
        if df is not None and not df.empty:
            return f"📦 Stock de familia {familia}:", df
        return f"No encontré stock para la familia {familia}.", None
    
    # Stock por depósito
    if tipo == 'stock_por_deposito':
        df = get_stock_por_deposito()
        if df is not None and not df.empty:
            return "🏢 Stock agrupado por depósito:", df
        return "No encontré datos de stock por depósito.", None
    
    # Lotes por vencer
    if tipo == 'lotes_por_vencer':
        dias = intencion.get('dias', 90)
        df = get_lotes_por_vencer(dias)
        if df is not None and not df.empty:
            return f"⚠️ Lotes que vencen en los próximos {dias} días:", df
        return f"No hay lotes que venzan en los próximos {dias} días.", None
    
    # Lotes vencidos
    if tipo == 'lotes_vencidos':
        df = get_lotes_vencidos()
        if df is not None and not df.empty:
            return "🚨 Lotes ya vencidos:", df
        return "No hay lotes vencidos registrados.", None
    
    # Stock bajo
    if tipo == 'stock_bajo':
        df = get_stock_bajo(10)
        if df is not None and not df.empty:
            return "📉 Artículos con stock bajo (≤10 unidades):", df
        return "No hay artículos con stock bajo.", None
    
    # Lote específico
    if tipo == 'lote_especifico':
        lote = intencion.get('lote', '')
        df = get_stock_lote_especifico(lote)
        if df is not None and not df.empty:
            return f"🔍 Información del lote {lote}:", df
        return f"No encontré el lote {lote}.", None
    
    # Stock de artículo
    if tipo == 'stock_articulo':
        articulo = intencion.get('articulo', pregunta)
        df = get_stock_articulo(articulo)
        if df is not None and not df.empty:
            return f"📦 Stock de '{articulo}':", df
        return f"No encontré stock para '{articulo}'.", None
    
    return "No entendí la consulta. Probá con: 'stock vitek', 'lotes por vencer', 'stock bajo'.", None

# =========================
# 📦 RESUMEN STOCK (ROTATIVO CADA 5s)
# =========================
def _stock_to_float(x) -> float:
    try:
        if x is None:
            return 0.0
        s = str(x).strip().replace(" ", "")
        s = s.replace(",", ".")
        return float(s)
    except Exception:
        return 0.0


@st.cache_data(ttl=300)
def _get_stock_cantidad_1(top_n: int = 200) -> pd.DataFrame:
    # Trae <= 1 y > 0 y filtramos a "≈ 1" exacto
    df = get_stock_bajo(1)
    if df is None or df.empty:
        return pd.DataFrame(columns=["FAMILIA", "CODIGO", "ARTICULO", "DEPOSITO", "LOTE", "VENCIMIENTO", "STOCK"])

    dfx = df.copy()
    dfx["__stock_num__"] = dfx["STOCK"].apply(_stock_to_float)

    eps = 0.0001
    dfx = dfx[(dfx["__stock_num__"] >= (1.0 - eps)) & (dfx["__stock_num__"] <= (1.0 + eps))]

    dfx = dfx.drop(columns=["__stock_num__"], errors="ignore")
    return dfx.head(int(top_n))


@st.cache_data(ttl=300)
def _get_lotes_proximos_a_vencer(dias: int = 30) -> pd.DataFrame:
    df = get_lotes_por_vencer(dias)
    if df is None or df.empty:
        return pd.DataFrame(columns=["FAMILIA", "CODIGO", "ARTICULO", "DEPOSITO", "LOTE", "VENCIMIENTO", "STOCK", "Dias_Para_Vencer"])
    return df


def mostrar_resumen_stock_rotativo(dias_vencer: int = 30):
    # ✅ No auto-refresh mientras el usuario está escribiendo en el input del Stock
    pregunta_actual = ""
    try:
        pregunta_actual = str(st.session_state.get("input_stock", "") or "")
    except Exception:
        pregunta_actual = ""

    tick = 0
    if not pregunta_actual.strip():
        try:
            from streamlit_autorefresh import st_autorefresh
            tick = st_autorefresh(interval=5000, key="__rotar_stock_5s__") or 0
        except Exception:
            tick = 0  # si no está instalado, queda fijo

    df_stock_1 = _get_stock_cantidad_1(top_n=200)
    df_vencer = _get_lotes_proximos_a_vencer(dias=int(dias_vencer))

    stock1_txt = "—"
    stock1_sub = "Sin registros con stock = 1"
    stock1_count = 0

    if df_stock_1 is not None and not df_stock_1.empty:
        stock1_count = len(df_stock_1)
        idx1 = int(tick) % stock1_count
        r1 = df_stock_1.iloc[idx1]

        art = str(r1.get("ARTICULO", "—"))
        lote = str(r1.get("LOTE", "—"))
        dep = str(r1.get("DEPOSITO", "—"))
        ven = str(r1.get("VENCIMIENTO", "—"))
        stk = str(r1.get("STOCK", "—"))

        stock1_txt = art
        stock1_sub = f"Lote {lote} | Depósito {dep} | Venc {ven} | Stock {stk}"

    vencer_txt = "—"
    vencer_sub = f"Sin lotes que venzan en {dias_vencer} días"
    vencer_count = 0

    if df_vencer is not None and not df_vencer.empty:
        vencer_count = len(df_vencer)
        idx2 = int(tick) % vencer_count
        r2 = df_vencer.iloc[idx2]

        art = str(r2.get("ARTICULO", "—"))
        lote = str(r2.get("LOTE", "—"))
        dep = str(r2.get("DEPOSITO", "—"))
        ven = str(r2.get("VENCIMIENTO", "—"))
        stk = str(r2.get("STOCK", "—"))
        dias = str(r2.get("Dias_Para_Vencer", "—"))

        vencer_txt = art
        vencer_sub = f"Lote {lote} | Depósito {dep} | Venc {ven} ({dias} días) | Stock {stk}"

    st.markdown("""
    <style>
      .mini-stock-wrap{
        display:flex;
        gap:12px;
        margin: 6px 0 10px 0;
      }
      .mini-stock-card{
        flex:1;
        border:1px solid #e5e7eb;
        border-radius:12px;
        padding:10px 12px;
        background: rgba(255,255,255,0.85);
      }
      .mini-stock-top{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:10px;
        margin:0;
      }
      .mini-stock-t{
        font-size:0.80rem;
        font-weight:600;
        opacity:0.85;
        margin:0;
      }
      .mini-stock-badge{
        font-size:0.75rem;
        opacity:0.75;
        border:1px solid #e5e7eb;
        padding:2px 8px;
        border-radius:999px;
        background: rgba(255,255,255,0.7);
        white-space:nowrap;
      }
      .mini-stock-v{
        font-size:1.00rem;
        font-weight:700;
        margin:4px 0 0 0;
        line-height:1.15;
      }
      .mini-stock-s{
        font-size:0.80rem;
        opacity:0.75;
        margin:4px 0 0 0;
        line-height:1.2;
      }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
      <div class="mini-stock-wrap">
        <div class="mini-stock-card">
          <div class="mini-stock-top">
            <p class="mini-stock-t">📉 Artículos con STOCK = 1</p>
            <span class="mini-stock-badge">{stock1_count} regs</span>
          </div>
          <p class="mini-stock-v">{stock1_txt}</p>
          <p class="mini-stock-s">{stock1_sub}</p>
        </div>

        <div class="mini-stock-card">
          <div class="mini-stock-top">
            <p class="mini-stock-t">⏳ Lotes próximos a vencer ({dias_vencer} días)</p>
            <span class="mini-stock-badge">{vencer_count} regs</span>
          </div>
          <p class="mini-stock-v">{vencer_txt}</p>
          <p class="mini-stock-s">{vencer_sub}</p>
        </div>
      </div>
    """, unsafe_allow_html=True)


# =========================
# 📦 STOCK IA (SIN TARJETAS ADENTRO)
# =========================
def mostrar_stock_ia():
    """Módulo Stock IA - Chat para consultas de stock"""

    st.title("📦 Stock IA")
    st.markdown("*Consultas de stock con lenguaje natural*")

    # ⛔ IMPORTANTE: NO LLAMAR mostrar_resumen_stock_rotativo() ACÁ
    # porque se renderiza arriba del menú desde main()

    st.markdown("---")

    if 'historial_stock' not in st.session_state:
        st.session_state.historial_stock = []

    with st.sidebar:
        st.header("📦 Stock IA - Ayuda")
        st.markdown("""
        **Este módulo entiende:**

        📊 **Consultas generales:**
        - "stock total"
        - "stock por familia"
        - "stock por depósito"

        🔍 **Búsquedas específicas:**
        - "stock vitek"
        - "lote D250829AF"
        - "stock familia ID"

        ⚠️ **Vencimientos:**
        - "lotes por vencer"
        - "vencen en 30 días"
        - "lotes vencidos"

        📉 **Alertas:**
        - "stock bajo"
        - "artículos a reponer"
        """)

        st.markdown("---")

        if st.button("🗑️ Limpiar historial", key="limpiar_stock", use_container_width=True):
            st.session_state.historial_stock = []
            st.rerun()

    pregunta = st.text_input(
        "Escribe tu consulta de stock:",
        placeholder="Ej: stock vitek / lotes por vencer / stock bajo",
        key="input_stock"
    )

    # 🔴 ALERTA DE VENCIMIENTO ROTATIVA (basada en tiempo)
    try:
        alertas = get_alertas_vencimiento_multiple(10)
        if alertas:
            import time
            # Cambiar cada 5 segundos basado en el tiempo actual
            indice = int(time.time() // 5) % len(alertas)
            alerta = alertas[indice]
            
            # ✅ CORREGIDO: usar 'dias_restantes' en vez de 'dias'
            dias = alerta['dias_restantes']
            articulo = alerta['articulo']
            lote = alerta['lote']
            venc = alerta['vencimiento']
            stock = alerta['stock']
            
            # Contador
            contador = f"<div style='text-align: center; font-size: 0.8em; color: #666; margin-top: 5px;'>{indice + 1} de {len(alertas)} alertas</div>"
            
            if dias <= 7:
                # Crítico - rojo
                st.markdown(f"""
                <div style="background-color: #fee2e2; border-left: 5px solid #dc2626; padding: 15px; border-radius: 5px; margin: 10px 0;">
                    <span style="color: #dc2626; font-weight: bold; font-size: 1.1em;">🚨 ¡ALERTA CRÍTICA!</span><br>
                    <span style="color: #7f1d1d;"><b>{articulo}</b> - Lote: <b>{lote}</b></span><br>
                    <span style="color: #7f1d1d;">Vence: <b>{venc}</b> ({dias} días) | Stock: {stock}</span>
                </div>
                {contador}
                """, unsafe_allow_html=True)
            elif dias <= 30:
                # Urgente - naranja
                st.markdown(f"""
                <div style="background-color: #fff7ed; border-left: 5px solid #ea580c; padding: 15px; border-radius: 5px; margin: 10px 0;">
                    <span style="color: #ea580c; font-weight: bold; font-size: 1.1em;">⚠️ PRÓXIMO A VENCER</span><br>
                    <span style="color: #9a3412;"><b>{articulo}</b> - Lote: <b>{lote}</b></span><br>
                    <span style="color: #9a3412;">Vence: <b>{venc}</b> ({dias} días) | Stock: {stock}</span>
                </div>
                {contador}
                """, unsafe_allow_html=True)
            else:
                # Atención - amarillo
                st.markdown(f"""
                <div style="background-color: #fefce8; border-left: 5px solid #ca8a04; padding: 15px; border-radius: 5px; margin: 10px 0;">
                    <span style="color: #ca8a04; font-weight: bold; font-size: 1.1em;">📋 Próximo vencimiento</span><br>
                    <span style="color: #854d0e;"><b>{articulo}</b> - Lote: <b>{lote}</b></span><br>
                    <span style="color: #854d0e;">Vence: <b>{venc}</b> ({dias} días) | Stock: {stock}</span>
                </div>
                {contador}
                """, unsafe_allow_html=True)
    except Exception as e:
        # ✅ AGREGADO: Mostrar error en debug para diagnosticar
        print(f"⚠️ Error en alertas de vencimiento: {e}")
        pass  # Si falla la alerta, no afecta el resto


    if pregunta:
        with st.spinner("🔍 Consultando stock."):
            respuesta, df = procesar_pregunta_stock(pregunta)

            st.session_state.historial_stock.append({
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'pregunta': pregunta,
                'respuesta': respuesta,
                'tiene_datos': df is not None and not df.empty
            })

            st.markdown(f"**{respuesta}**")

            if df is not None and not df.empty:
                if 'STOCK' in df.columns:
                    try:
                        total_stock = df['STOCK'].apply(lambda x: float(
                            str(x).replace(',', '.').replace(' ', '')
                        ) if pd.notna(x) else 0).sum()
                        st.info(f"📦 **Total stock:** {total_stock:,.0f} unidades".replace(',', '.'))
                    except Exception:
                        pass

                if 'Dias_Para_Vencer' in df.columns:
                    try:
                        criticos = len(df[df['Dias_Para_Vencer'] <= 30])
                        if criticos > 0:
                            st.warning(f"⚠️ **{criticos}** lotes vencen en menos de 30 días")
                    except Exception:
                        pass

                st.dataframe(df, use_container_width=True, hide_index=True)

                excel_data = df_to_excel(df)
                st.download_button(
                    label="📥 Descargar Excel",
                    data=excel_data,
                    file_name="consulta_stock.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    if st.session_state.historial_stock:
        st.markdown("---")
        st.subheader("📜 Historial")

        for i, item in enumerate(reversed(st.session_state.historial_stock[-5:])):
            with st.expander(f"🕐 {item['timestamp']} - {item['pregunta'][:40]}."):
                st.markdown(f"**Pregunta:** {item['pregunta']}")
                st.markdown(f"**Respuesta:** {item['respuesta']}")


# =========================
# 📊 DASHBOARD
# =========================

def mostrar_dashboard():
    """Dashboard con gráficos de compras y stock"""
    
    st.title("📊 Dashboard")
    
    # Selector de año
    anio_actual = datetime.now().year
    col_filtro, col_espacio = st.columns([1, 3])
    with col_filtro:
        anio = st.selectbox("Año:", [anio_actual, anio_actual - 1, anio_actual - 2], index=0)
    
    st.markdown("---")
    
    # =====================
    # MÉTRICAS PRINCIPALES
    # =====================
    try:
        totales = get_dashboard_totales(anio)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_fmt = f"${totales['total_pesos']:,.0f}".replace(',', '.')
            st.metric("💰 Total Compras $", total_fmt)
        
        with col2:
            usd_fmt = f"U$S {totales['total_usd']:,.0f}".replace(',', '.')
            st.metric("💵 Total USD", usd_fmt)
        
        with col3:
            st.metric("🏭 Proveedores", totales['proveedores'])
        
        with col4:
            st.metric("📄 Facturas", totales['facturas'])
    except Exception as e:
        st.error(f"Error cargando métricas: {e}")
    
    st.markdown("---")
    
    # =====================
    # GRÁFICOS EN 2 COLUMNAS
    # =====================
    col_izq, col_der = st.columns(2)

    # GRÁFICO 1: Compras por Mes (Barras)
    with col_izq:
        st.subheader("📈 Compras por Mes")
        try:
            df_meses = get_dashboard_compras_por_mes(anio)
            if df_meses is not None and not df_meses.empty:
                fig_meses = px.bar(
                    df_meses,
                    x='Mes',
                    y='Total',
                    color='Total',
                    color_continuous_scale='Blues',
                    labels={'Total': 'Monto ($)', 'Mes': ''}
                )
                fig_meses.update_layout(
                    showlegend=False,
                    coloraxis_showscale=False,
                    height=350,
                    margin=dict(l=20, r=20, t=30, b=20)
                )
                fig_meses.update_traces(
                    texttemplate='%{y:,.0f}',
                    textposition='outside',
                    textfont_size=10
                )
                st.plotly_chart(fig_meses, use_container_width=True)
            else:
                st.info("No hay datos para este año")
        except Exception as e:
            st.error(f"Error: {e}")

    # GRÁFICO 2: Top Proveedores (por moneda)
    with col_der:
        st.subheader("🏆 Top Proveedores (por moneda)")
        try:
            tabs = st.tabs(["$ Pesos", "U$S USD"])

            with tabs[0]:
                df_provs = get_dashboard_top_proveedores(anio, 10, moneda="$")
                if df_provs is not None and not df_provs.empty:
                    fig_provs = px.bar(
                        df_provs,
                        x='Total',
                        y='Proveedor',
                        orientation='h',
                        color='Total',
                        color_continuous_scale='Oranges',
                        labels={'Total': 'Monto ($)', 'Proveedor': ''}
                    )
                    fig_provs.update_layout(
                        showlegend=False,
                        coloraxis_showscale=False,
                        height=350,
                        margin=dict(l=20, r=20, t=30, b=20)
                    )
                    st.plotly_chart(fig_provs, use_container_width=True)
                else:
                    st.info("No hay datos en $ para este año")

            with tabs[1]:
                df_provs_usd = get_dashboard_top_proveedores(anio, 10, moneda="U$S")
                if df_provs_usd is not None and not df_provs_usd.empty:
                    fig_provs_usd = px.bar(
                        df_provs_usd,
                        x='Total',
                        y='Proveedor',
                        orientation='h',
                        color='Total',
                        color_continuous_scale='Oranges',
                        labels={'Total': 'Monto (U$S)', 'Proveedor': ''}
                    )
                    fig_provs_usd.update_layout(
                        showlegend=False,
                        coloraxis_showscale=False,
                        height=350,
                        margin=dict(l=20, r=20, t=30, b=20)
                    )
                    st.plotly_chart(fig_provs_usd, use_container_width=True)
                else:
                    st.info("No hay datos en U$S para este año")

        except Exception as e:
            st.error(f"Error: {e}")
    
    # SEGUNDA FILA DE GRÁFICOS
    col_izq2, col_der2 = st.columns(2)
    
    # GRÁFICO 3: Gastos por Familia (Torta)
    with col_izq2:
        st.subheader("🥧 Gastos por Familia")
        try:
            df_familias = get_dashboard_gastos_familia(anio)
            if df_familias is not None and not df_familias.empty:
                fig_torta = px.pie(
                    df_familias,
                    values='Total',
                    names='Familia',
                    color_discrete_sequence=px.colors.qualitative.Set3,
                    hole=0.4  # Donut chart
                )
                fig_torta.update_layout(
                    height=350,
                    margin=dict(l=20, r=20, t=30, b=20),
                    showlegend=True,
                    legend=dict(
                        orientation="v",
                        yanchor="middle",
                        y=0.5,
                        xanchor="left",
                        x=1.02
                    )
                )
                fig_torta.update_traces(
                    textposition='inside',
                    textinfo='percent',
                    textfont_size=11
                )
                st.plotly_chart(fig_torta, use_container_width=True)
            else:
                st.info("No hay datos para este año")
        except Exception as e:
            st.error(f"Error: {e}")
    
    # GRÁFICO 4: Alertas y Últimas Compras
    with col_der2:
        st.subheader("🚨 Alertas y Actividad")
        
        # Alertas de vencimiento
        try:
            alertas = get_alertas_vencimiento_multiple(5)
            if alertas:
                st.markdown("**⚠️ Próximos vencimientos:**")
                for alerta in alertas[:3]:
                    dias = alerta['dias']
                    if dias <= 7:
                        color = "🔴"
                    elif dias <= 30:
                        color = "🟠"
                    else:
                        color = "🟡"
                    st.markdown(f"{color} **{alerta['articulo'][:30]}** - {alerta['vencimiento']} ({dias} días)")
            else:
                st.success("✅ No hay vencimientos próximos")
        except:
            pass
        
        st.markdown("---")
        
        # Últimos artículos comprados
        try:
            st.markdown("**🛒 Últimos artículos comprados:**")
            df_ultimas = get_dashboard_ultimas_compras(5)
            if df_ultimas is not None and not df_ultimas.empty:
                for _, row in df_ultimas.iterrows():
                    total_fmt = f"${row['Total']:,.0f}".replace(',', '.') if pd.notna(row['Total']) else "$0"
                    articulo = str(row['Articulo'])[:25] + "..." if len(str(row['Articulo'])) > 25 else str(row['Articulo'])
                    proveedor = str(row['Proveedor'])[:15] if pd.notna(row['Proveedor']) else ""
                    st.markdown(f"• {row['Fecha']} - **{articulo}** - {proveedor} - {total_fmt}")
            else:
                st.info("No hay compras recientes")
        except Exception as e:
            st.error(f"Error: {e}")


# =========================
# 📈 INDICADORES IA (POWER BI)
# =========================

def mostrar_indicadores_ia():
    url = "https://app.powerbi.com/view?r=eyJrIjoiMTBhMGY0ZjktYmM1YS00OTM4LTg3ZjItMTEzYWVmZWNkMGIyIiwidCI6ImQxMzBmYmU3LTFiZjAtNDczNi1hM2Q5LTQ1YjBmYWUwMDVmYSIsImMiOjR9"

    scale = 0.50  # ✅ Zoom 65%

    st.markdown(
        f"""
        <style>
          .pbi-wrap {{
            width: 100%;
            height: 92vh;
            padding: 18px 24px;   /* aire alrededor */
            box-sizing: border-box;
            overflow: hidden;     /* evita scroll extra por el scale */
          }}

          .pbi-iframe {{
            width: calc(100% / {scale});
            height: calc(92vh / {scale});
            transform: scale({scale});
            transform-origin: top left;
            border: 0;
            border-radius: 14px;
          }}
        </style>

        <div class="pbi-wrap">
          <iframe class="pbi-iframe" src="{url}" allowfullscreen="true"></iframe>
        </div>
        """,
        unsafe_allow_html=True
    )

# =========================
# 📊 RESUMEN RÁPIDO
# =========================
def _safe_float(x) -> float:
    try:
        if x is None:
            return 0.0
        return float(x)
    except Exception:
        return 0.0


@st.cache_data(ttl=300)
def _get_totales_anio(anio: int) -> dict:
    total_expr = _sql_total_num_expr_general()

    query = f"""
        SELECT
            SUM(CASE WHEN TRIM(COALESCE("Moneda",'')) = '$'
                     THEN {total_expr} ELSE 0 END) AS total_pesos,
            SUM(CASE WHEN TRIM(COALESCE("Moneda",'')) IN ('U$S','U$$')
                     THEN {total_expr} ELSE 0 END) AS total_usd
        FROM chatbot_raw
        WHERE
            ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
            AND "Año"::int = %s
    """

    params = (anio,)

    # DEBUG (opcional)
    if DEBUG_MODE:
        st.session_state.debug = {
            "pregunta": "total compras por año",
            "proveedor": None,
            "mes": None,
            "anio": anio,
            "sql": query,
            "params": params,
            "ruta": "TOTAL_COMPRAS_ANIO",
        }

    df = ejecutar_consulta(query, params)
    if df is None or df.empty:
        return {"pesos": 0.0, "usd": 0.0}

    return {
        "pesos": _safe_float(df["total_pesos"].iloc[0]),
        "usd": _safe_float(df["total_usd"].iloc[0]),
    }


@st.cache_data(ttl=300)
def _get_totales_mes(mes_key: str) -> dict:
    total_expr = _sql_total_num_expr_general()

    query = f"""
        SELECT
            SUM(CASE WHEN TRIM(COALESCE("Moneda",'')) = '$'
                     THEN {total_expr} ELSE 0 END) AS total_pesos,
            SUM(CASE WHEN TRIM(COALESCE("Moneda",'')) IN ('U$S','U$$')
                     THEN {total_expr} ELSE 0 END) AS total_usd
        FROM chatbot_raw
        WHERE
            ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
            AND TRIM("Mes") = %s
    """
    df = ejecutar_consulta(query, (mes_key,))
    if df is None or df.empty:
        return {"pesos": 0.0, "usd": 0.0}

    return {
        "pesos": _safe_float(df["total_pesos"].iloc[0]),
        "usd": _safe_float(df["total_usd"].iloc[0]),
    }


@st.cache_data(ttl=300)
def _get_top_proveedores_anio(anio: int, top_n: int = 20) -> pd.DataFrame:
    total_expr = _sql_total_num_expr_general()

    query = f"""
        SELECT
            TRIM("Cliente / Proveedor") AS "Proveedor",
            SUM(CASE WHEN TRIM(COALESCE("Moneda",'')) = '$'
                     THEN {total_expr} ELSE 0 END) AS "Total_$",
            SUM(CASE WHEN TRIM(COALESCE("Moneda",'')) IN ('U$S','U$$')
                     THEN {total_expr} ELSE 0 END) AS "Total_USD"
        FROM chatbot_raw
        WHERE
            ("Tipo Comprobante" = 'Compra Contado' OR "Tipo Comprobante" LIKE 'Compra%%')
            AND "Año"::int = %s
            AND "Cliente / Proveedor" IS NOT NULL
            AND TRIM("Cliente / Proveedor") <> ''
        GROUP BY TRIM("Cliente / Proveedor")
        ORDER BY "Total_$" DESC, "Total_USD" DESC
        LIMIT {int(top_n)}
    """
    df = ejecutar_consulta(query, (anio,))
    if df is None:
        return pd.DataFrame(columns=["Proveedor", "Total_$", "Total_USD"])
    return df


def mostrar_resumen_compras_rotativo():
    # ✅ esto hace que el script se re-ejecute cada 5 segundos
    tick = 0
    try:
        from streamlit_autorefresh import st_autorefresh
        tick = st_autorefresh(interval=5000, key="__rotar_proveedor_5s__") or 0
    except Exception:
        tick = 0  # si no está instalado, queda fijo

    anio = datetime.now().year
    mes_key = datetime.now().strftime("%Y-%m")

    tot_anio = _get_totales_anio(anio)
    tot_mes = _get_totales_mes(mes_key)

    dfp = _get_top_proveedores_anio(anio, top_n=20)

    prov_nom = "—"
    prov_pesos = 0.0
    prov_usd = 0.0

    if dfp is not None and not dfp.empty:
        idx = int(tick) % len(dfp)
        row = dfp.iloc[idx]

        # Buscar columnas (PostgreSQL devuelve en minúsculas a veces según driver)
        for col in dfp.columns:
            if col.lower() == 'proveedor':
                prov_nom = str(row[col]) if pd.notna(row[col]) else "—"
            elif col.lower() == 'total_$':
                prov_pesos = _safe_float(row[col])
            elif col.lower() == 'total_usd':
                prov_usd = _safe_float(row[col])

    # ✅ estilo "mini" (chico y prolijo)
    st.markdown("""
    <style>
      .mini-resumen {
        display: flex;
        gap: 12px;
        margin: 6px 0 10px 0;
      }
      .mini-card {
        flex: 1;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 10px 12px;
        background: rgba(255,255,255,0.8);
      }
      .mini-t {
        font-size: 0.82rem;
        font-weight: 600;
        opacity: 0.85;
        margin: 0;
      }
      .mini-v {
        font-size: 1.05rem;
        font-weight: 700;
        margin: 4px 0 0 0;
      }
      .mini-s {
        font-size: 0.82rem;
        opacity: 0.75;
        margin: 4px 0 0 0;
      }
    </style>
    """, unsafe_allow_html=True)

    total_anio_txt = f"$ {_fmt_num_latam(tot_anio['pesos'], 0)}"
    total_anio_sub = f"U$S {_fmt_num_latam(tot_anio['usd'], 0)}"

    prov_sub = f"$ {_fmt_num_latam(prov_pesos, 0)} | U$S {_fmt_num_latam(prov_usd, 0)}"

    mes_txt = f"$ {_fmt_num_latam(tot_mes['pesos'], 0)}"
    mes_sub = f"U$S {_fmt_num_latam(tot_mes['usd'], 0)}"

    # ✅ IMPORTANTE: SOLO UNA VEZ (acá estaba duplicado)
    st.markdown(f"""
      <div class="mini-resumen">
        <div class="mini-card">
          <p class="mini-t">💰 Total {anio}</p>
          <p class="mini-v">{total_anio_txt}</p>
          <p class="mini-s">{total_anio_sub}</p>
        </div>
        <div class="mini-card">
          <p class="mini-t">🏭 Proveedor</p>
          <p class="mini-v">{prov_nom}</p>
          <p class="mini-s">{prov_sub}</p>
        </div>
        <div class="mini-card">
          <p class="mini-t">🗓️ Mes actual</p>
          <p class="mini-v">{mes_txt}</p>
          <p class="mini-s">{mes_sub}</p>
        </div>
      </div>
    """, unsafe_allow_html=True)

# =========================
# CSS RESPONSIVE (CELULAR)
# =========================
def inject_css_responsive():
    st.markdown(
        """
        <style>
        /* =========================================================
           RESPONSIVE MOBILE (solo tamaños/espaciado)
           ========================================================= */
        @media (max-width: 768px){

            /* Menos padding general */
            .block-container{
                padding-top: 0.9rem !important;
                padding-left: 0.8rem !important;
                padding-right: 0.8rem !important;
                padding-bottom: 4.5rem !important;
            }

            /* Títulos más chicos */
            h1 { font-size: 1.35rem !important; line-height: 1.2 !important; }
            h2 { font-size: 1.15rem !important; line-height: 1.2 !important; }
            h3 { font-size: 1.05rem !important; line-height: 1.2 !important; }

            /* Texto general más chico */
            .stMarkdown, .stText, .stCaption, p, li{
                font-size: 0.95rem !important;
                line-height: 1.25 !important;
            }

            /* Reduce padding interno de contenedores (tus “tarjetas” suelen ser containers) */
            div[data-testid="stContainer"]{
                padding: 0.55rem !important;
            }

            /* Radio/menu más compacto */
            div[role="radiogroup"] label{
                font-size: 0.95rem !important;
                margin-bottom: 0.25rem !important;
            }

            /* Inputs */
            input, textarea{
                font-size: 1rem !important;
            }

            /* Botones */
            .stButton > button{
                width: 100% !important;
                padding: 0.60rem 0.9rem !important;
                font-size: 1rem !important;
            }

            /* Dataframe: más chico + menos padding visual */
            div[data-testid="stDataFrame"]{
                font-size: 0.85rem !important;
            }
            div[data-testid="stDataFrame"] *{
                font-size: 0.85rem !important;
            }

            /* Expanders más compactos */
            details summary{
                font-size: 0.95rem !important;
            }

            /* Columnas: permitir wrap en mobile para que no quede 3 tarjetas apretadas */
            div[data-testid="stHorizontalBlock"]{
                flex-wrap: wrap !important;
                gap: 0.5rem !important;
            }
            div[data-testid="column"]{
                min-width: 280px !important;
                flex: 1 1 280px !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    )


# =========================
# UI - MOSTRAR DETALLE DF (+ gráfico + explicación)
# =========================

def _norm_colname(x: str) -> str:
    try:
        return normalizar_texto(str(x or ""))
    except Exception:
        return str(x or "").lower().strip()


def _pick_col(df: pd.DataFrame, posibles: list[str]) -> Optional[str]:
    if df is None or df.empty:
        return None
    cols = list(df.columns)
    cols_norm = {_norm_colname(c): c for c in cols}
    for p in posibles:
        pnorm = _norm_colname(p)
        # match exacto normalizado
        if pnorm in cols_norm:
            return cols_norm[pnorm]
        # match parcial
        for cnorm, corig in cols_norm.items():
            if pnorm in cnorm:
                return corig
    return None


def _latam_to_float(valor) -> float:
    """Convierte string LATAM/currency a float (robusto)."""
    if valor is None:
        return 0.0
    try:
        if pd.isna(valor):
            return 0.0
    except Exception:
        pass

    # Ya es numérico
    if isinstance(valor, (int, float)):
        try:
            return float(valor)
        except Exception:
            return 0.0

    s = str(valor).strip()
    if not s:
        return 0.0

    # Quitar símbolos y paréntesis
    s = s.replace("U$S", "").replace("USD", "").replace("$", "").strip()
    s = s.replace("(", "-").replace(")", "")
    s = s.replace(" ", "")

    # Normalizar separadores: casos con miles y decimales
    if "," in s and "." in s:
        # si la coma está al final → coma decimal, punto miles
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            # punto decimal, coma miles
            s = s.replace(",", "")
    else:
        # solo coma → decimal
        if "," in s and "." not in s:
            s = s.replace(".", "").replace(",", ".")
        # solo punto → puede ser decimal o miles; intentamos directo

    try:
        return float(s)
    except Exception:
        return 0.0


def _df_get_numeric(df: pd.DataFrame, col: str) -> pd.Series:
    if col is None or df is None or df.empty or col not in df.columns:
        return pd.Series([0.0] * (len(df) if df is not None else 0))
    ser = df[col]
    # si ya es numérico, usarlo
    if pd.api.types.is_numeric_dtype(ser):
        return pd.to_numeric(ser, errors="coerce").fillna(0.0)
    # si es string (por formatear_dataframe), parsear LATAM
    return ser.apply(_latam_to_float).fillna(0.0)


def _df_get_datetime(df: pd.DataFrame, col: str) -> Optional[pd.Series]:
    if df is None or df.empty or not col or col not in df.columns:
        return None
    try:
        # dayfirst=True por DD/MM/YYYY que aparece a veces
        return pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    except Exception:
        return None


def _es_df_compras(df: pd.DataFrame) -> bool:
    """Heurística: si parece detalle de compras (artículo/proveedor/total/fecha)."""
    if df is None or df.empty:
        return False
    c_art = _pick_col(df, ["articulo", "Artículo", "Articulo"])
    c_prov = _pick_col(df, ["proveedor", "Proveedor", "cliente / proveedor", "Cliente / Proveedor"])
    c_tot = _pick_col(df, ["total", "monto", "importe", "monto neto"])
    c_fec = _pick_col(df, ["fecha", "Fecha"])
    # basta con artículo + (total o cantidad) o proveedor + total
    c_cant = _pick_col(df, ["cantidad", "Cantidad"])
    return bool((c_art and (c_tot or c_cant)) or (c_prov and c_tot) or (c_fec and c_tot))


def _fmt_money_latam(valor: float, moneda: str = "$", dec: int = 2) -> str:
    if moneda and moneda.strip().upper() in ["U$S", "USD", "U$$"]:
        pref = "U$S "
    else:
        pref = "$ "
    return pref + _fmt_num_latam(valor, dec)


def _build_resumen_compras(df: pd.DataFrame) -> dict:
    """Devuelve métricas + top artículos."""
    if df is None or df.empty:
        return {}

    c_art = _pick_col(df, ["articulo", "Artículo", "Articulo"])
    c_prov = _pick_col(df, ["proveedor", "Proveedor", "cliente / proveedor", "Cliente / Proveedor"])
    c_fec = _pick_col(df, ["fecha", "Fecha"])
    c_mon = _pick_col(df, ["moneda", "Moneda"])
    c_fac = _pick_col(df, ["nro_factura", "N Factura", "Nro Factura", "Factura", "Nro. Comprobante", "Nro. Comprobante "])
    c_tot = _pick_col(df, ["total", "Total", "monto", "Monto", "importe", "Importe", "monto neto", "Monto Neto"])
    c_cant = _pick_col(df, ["cantidad", "Cantidad"])

    total_num = _df_get_numeric(df, c_tot) if c_tot else pd.Series([0.0] * len(df))
    cant_num = _df_get_numeric(df, c_cant) if c_cant else None

    # Totales por moneda (si existe)
    totales_por_moneda = {}
    if c_mon and c_tot:
        for m in df[c_mon].dropna().astype(str).unique():
            sub = df[df[c_mon].astype(str) == str(m)]
            sub_total = _df_get_numeric(sub, c_tot).sum()
            totales_por_moneda[str(m).strip()] = float(sub_total)

    # Fechas
    dt = _df_get_datetime(df, c_fec) if c_fec else None
    fecha_min = None
    fecha_max = None
    if dt is not None:
        try:
            fecha_min = dt.min()
            fecha_max = dt.max()
        except Exception:
            pass

    # Proveedor principal (si es casi único)
    prov_modo = None
    if c_prov:
        try:
            vc = df[c_prov].dropna().astype(str).value_counts()
            if not vc.empty:
                prov_modo = vc.index[0]
        except Exception:
            pass

    # Facturas únicas
    facturas_unicas = None
    if c_fac:
        try:
            facturas_unicas = int(df[c_fac].dropna().astype(str).nunique())
        except Exception:
            facturas_unicas = None

    # Artículos: top por total (o por cantidad si no hay total)
    top_items_df = pd.DataFrame()
    if c_art:
        if c_tot:
            tmp = df[[c_art]].copy()
            tmp["_total_"] = total_num.values
            top_items_df = (
                tmp.groupby(c_art, as_index=False)["_total_"]
                   .sum()
                   .sort_values("_total_", ascending=False)
                   .head(10)
            )
            top_items_df = top_items_df.rename(columns={c_art: "Artículo", "_total_": "Total"})
        elif c_cant:
            tmp = df[[c_art]].copy()
            tmp["_cant_"] = cant_num.values
            top_items_df = (
                tmp.groupby(c_art, as_index=False)["_cant_"]
                   .sum()
                   .sort_values("_cant_", ascending=False)
                   .head(10)
            )
            top_items_df = top_items_df.rename(columns={c_art: "Artículo", "_cant_": "Cantidad"})

    # Cantidad total (si existe)
    cantidad_total = None
    if c_cant:
        try:
            cantidad_total = float(_df_get_numeric(df, c_cant).sum())
        except Exception:
            cantidad_total = None

    return {
        "rows": int(len(df)),
        "col_total": c_tot,
        "col_moneda": c_mon,
        "col_fecha": c_fec,
        "col_factura": c_fac,
        "col_articulo": c_art,
        "col_proveedor": c_prov,
        "total_sum": float(total_num.sum()) if c_tot else None,
        "totales_por_moneda": totales_por_moneda,
        "fecha_min": fecha_min,
        "fecha_max": fecha_max,
        "proveedor_modo": prov_modo,
        "facturas_unicas": facturas_unicas,
        "cantidad_total": cantidad_total,
        "top_items_df": top_items_df
    }


# =========================
# GRÁFICOS COMPRAS (ROBUSTO)
# =========================
def _render_graficos_compras(df: pd.DataFrame, key_base: str = "detalle_df"):
    """
    Render de gráficos para compras:
    - Top artículos por total (barh)
    - Evolución por fecha (line)
    - Total por moneda (bar)

    Arregla el error típico de Plotly:
    cuando 'serie' queda como Series o DF sin reset_index().
    """
    if df is None:
        return

    if not hasattr(df, "columns"):
        return

    cols = list(df.columns)

    def _pick_col(candidates):
        for cand in candidates:
            for c in cols:
                if str(c).strip().lower() == str(cand).strip().lower():
                    return c
        return None

    col_fecha = _pick_col(["Fecha", "fecha"])
    col_total = _pick_col(["Total", "total", "Monto Neto", "monto neto", "monto_neto", "importe", "Importe"])
    col_articulo = _pick_col(["Articulo", "articulo", "Artículo", "artículo"])
    col_moneda = _pick_col(["Moneda", "moneda"])

    if col_total is None:
        st.warning("No pude armar gráficos: no encuentro la columna de total (Total/total/Monto Neto).")
        return

    # Copia local
    dfg = df.copy()

    # Limpieza numérica UY: "7.606,28" -> 7606.28 ; "(1.234,00)" -> -1234.00 ; "$" / "U$S" fuera
    def _to_number_uy(x):
        try:
            s = str(x).strip()
            if s == "" or s.lower() == "nan":
                return None
            s = s.replace("U$S", "").replace("US$", "").replace("$", "").strip()
            s = s.replace(" ", "")
            s = s.replace("\u00a0", "")
            s = s.replace("(", "-").replace(")", "")
            s = s.replace(".", "").replace(",", ".")
            return float(s)
        except Exception:
            return None

    # Total a numérico
    try:
        dfg[col_total] = dfg[col_total].apply(_to_number_uy)
        dfg[col_total] = pd.to_numeric(dfg[col_total], errors="coerce")
    except Exception:
        pass

    # Fecha a datetime si existe
    if col_fecha is not None:
        try:
            dfg[col_fecha] = pd.to_datetime(dfg[col_fecha], errors="coerce", dayfirst=True)
        except Exception:
            pass

    # Filtramos filas inválidas para graficar
    try:
        dfg = dfg.dropna(subset=[col_total])
    except Exception:
        pass

    if dfg.empty:
        st.warning("No hay datos numéricos válidos para graficar (Total vacío/no convertible).")
        return

    # Tabs
    tab1, tab2, tab3 = st.tabs(["🏷️ Top artículos", "📈 Evolución", "💱 Monedas"])

    # -------------------------
    # TOP ARTÍCULOS
    # -------------------------
    with tab1:
        if col_articulo is None:
            st.info("No encuentro columna de artículo (Articulo/articulo).")
        else:
            try:
                top = (
                    dfg.groupby(col_articulo, dropna=False)[col_total]
                    .sum()
                    .sort_values(ascending=False)
                    .head(10)
                    .reset_index()
                    .rename(columns={col_articulo: "Artículo", col_total: "Total"})
                )

                if top.empty:
                    st.info("No hay datos para Top artículos.")
                else:
                    fig1 = px.bar(top, x="Total", y="Artículo", orientation="h")
                    st.plotly_chart(fig1, use_container_width=True, key=f"{key_base}_bar_top")
            except Exception:
                st.info("No pude generar el gráfico de Top artículos (pero la app sigue).")

    # -------------------------
    # EVOLUCIÓN
    # -------------------------
    with tab2:
        if col_fecha is None:
            st.info("No encuentro columna de fecha (Fecha/fecha).")
        else:
            try:
                serie = (
                    dfg.dropna(subset=[col_fecha])
                    .groupby(col_fecha)[col_total]
                    .sum()
                    .reset_index()
                    .rename(columns={col_fecha: "Fecha", col_total: "Total"})
                    .sort_values("Fecha")
                )

                if serie.empty:
                    st.info("No hay datos para la evolución por fecha.")
                else:
                    fig2 = px.line(serie, x="Fecha", y="Total", markers=True)
                    st.plotly_chart(fig2, use_container_width=True, key=f"{key_base}_line_evo")
            except Exception:
                st.info("No pude generar el gráfico de evolución (pero la app sigue).")

    # -------------------------
    # MONEDAS
    # -------------------------
    with tab3:
        if col_moneda is None:
            st.info("No encuentro columna de moneda (Moneda/moneda).")
        else:
            try:
                mon = (
                    dfg.groupby(col_moneda, dropna=False)[col_total]
                    .sum()
                    .reset_index()
                    .rename(columns={col_moneda: "Moneda", col_total: "Total"})
                    .sort_values("Total", ascending=False)
                )

                if mon.empty:
                    st.info("No hay datos para monedas.")
                else:
                    fig3 = px.bar(mon, x="Moneda", y="Total")
                    st.plotly_chart(fig3, use_container_width=True, key=f"{key_base}_bar_mon")
            except Exception:
                st.info("No pude generar el gráfico por moneda (pero la app sigue).")


def _render_explicacion_compras(df: pd.DataFrame, contexto_respuesta: str = "") -> None:
    """Explicación simple y útil sin IA (100% determinística)."""
    info = _build_resumen_compras(df)
    if not info:
        st.info("No hay datos para explicar.")
        return

    rows = info["rows"]
    total_sum = info["total_sum"]
    totales_por_moneda = info["totales_por_moneda"] or {}
    prov = info["proveedor_modo"]
    facs = info["facturas_unicas"]
    cant_total = info["cantidad_total"]
    fmin = info["fecha_min"]
    fmax = info["fecha_max"]
    top_df = info["top_items_df"]

    st.markdown("### 🧠 Explicación")
    if contexto_respuesta:
        st.caption(contexto_respuesta)

    st.markdown(
        "- El **Total** se calcula como la **suma del importe de cada renglón** (cada renglón suele ser un artículo/línea dentro de una factura)."
    )
    st.markdown(f"- Se encontraron **{rows}** renglones (registros) en el detalle.")

    if facs is not None:
        st.markdown(f"- Facturas únicas detectadas: **{facs}**.")

    if prov:
        st.markdown(f"- Proveedor más frecuente en el detalle: **{prov}**.")

    if fmin is not None and fmax is not None:
        try:
            st.markdown(
                f"- Rango de fechas: **{fmin.date().strftime('%d/%m/%Y')}** → **{fmax.date().strftime('%d/%m/%Y')}**."
            )
        except Exception:
            pass

    # Totales por moneda si aplica
    if totales_por_moneda:
        st.markdown("#### 💰 Total por moneda")
        for mon, val in totales_por_moneda.items():
            mon_norm = str(mon).strip()
            if mon_norm.upper() in ["U$S", "USD", "U$$"]:
                st.markdown(f"- **{mon_norm}**: **{_fmt_money_latam(val, 'U$S')}**")
            else:
                st.markdown(f"- **{mon_norm or '$'}**: **{_fmt_money_latam(val, '$')}**")
    else:
        # Total general si no hay moneda
        if total_sum is not None:
            st.markdown(f"- Total (sumatoria): **{_fmt_money_latam(total_sum, '$')}**")

    if cant_total is not None and cant_total > 0:
        st.markdown(f"- Cantidad total (sumatoria de cantidades): **{_fmt_num_latam(cant_total, 2)}**")

    # Top artículos
    if top_df is not None and not top_df.empty:
        st.markdown("#### 🏷️ Artículos que más impactan")
        show = top_df.copy()
        if "Total" in show.columns:
            show["Total"] = show["Total"].apply(lambda x: _fmt_money_latam(float(x), "$"))
        st.dataframe(show, use_container_width=True, hide_index=True)

        st.markdown(
            "- Estos son los artículos con **mayor impacto** (por importe o por cantidad, según lo que tenga el detalle)."
        )


# =========================
# UI - MOSTRAR DETALLE DF
# =========================
def mostrar_detalle_df(
    df,
    titulo="Detalle",
    key="detalle",
    contexto_respuesta=None,
    max_rows=200,
    enable_chart=True,
    enable_explain=True,
):
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

    # ---------------------------------
    # DATASET COMPLETO PARA CÁLCULOS
    # ---------------------------------
    df_full = None

    if contexto_respuesta and "where_clause" in contexto_respuesta:
        try:
            df_full = get_dataset_completo(
                contexto_respuesta["where_clause"],
                contexto_respuesta.get("params", ())
            )
        except Exception:
            df_full = None

    # Fallback seguro
    if df_full is None or df_full.empty:
        df_full = df.copy()

    # ---------------------------------
    # DATASET RECORTADO SOLO PARA TABLA
    # ---------------------------------
    try:
        df_view = df_full.head(int(max_rows)).copy()
    except Exception:
        df_view = df_full.copy()

    # ---------------------------------
    # HEADER
    # ---------------------------------
    st.markdown(f"### {titulo}")

    # ---------------------------------
    # CHECKS UI
    # ---------------------------------
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        ver_tabla = st.checkbox(
            "📄 Ver tabla (detalle)",
            key=f"{key}_tabla",
            value=True
        )

    with col2:
        ver_grafico = False
        if enable_chart:
            ver_grafico = st.checkbox(
                "📈 Ver gráfico",
                key=f"{key}_grafico",
                value=False
            )

    with col3:
        ver_explicacion = False
        if enable_explain:
            ver_explicacion = st.checkbox(
                "🧠 Ver explicación",
                key=f"{key}_explica",
                value=False
            )

    # ---------------------------------
    # TABLA (LIMITADA)
    # ---------------------------------
    if ver_tabla:
        try:
            st.dataframe(
                df_view,
                use_container_width=True,
                hide_index=True
            )
        except Exception:
            st.dataframe(df_view)

        try:
            total_full = len(df_full)
            total_view = len(df_view)
            if total_full > total_view:
                st.caption(
                    f"Mostrando {total_view} de {total_full} registros. "
                    f"Gráficos y explicación se calculan sobre el total."
                )
        except Exception:
            pass

    # ---------------------------------
    # GRÁFICOS (DATASET COMPLETO)
    # ---------------------------------
    if ver_grafico:
        try:
            _render_graficos_compras(df_full, key_base=key)
        except Exception:
            st.warning("No se pudo generar el gráfico para este detalle.")

    # ---------------------------------
    # EXPLICACIÓN (DATASET COMPLETO)
    # ---------------------------------
    if ver_explicacion:
        try:
            _render_explicacion_compras(df_full)
        except Exception:
            st.warning("No se pudo generar la explicación para este detalle.")

        # =========================
        # DATASET COMPLETO PARA ANALISIS (SIN LIMIT)
        # =========================
        df_agregado = None
        if contexto_respuesta and "where_clause" in contexto_respuesta:
            try:
                df_agregado = get_serie_compras_agregada(
                    contexto_respuesta["where_clause"],
                    contexto_respuesta.get("params", ())
                )
            except Exception:
                df_agregado = None

        # =========================
        # GRAFICOS
        # =========================
        if enable_chart:
            if df_agregado is not None and not df_agregado.empty:
                _render_graficos_compras(df_agregado, key_base=key)
            else:
                _render_graficos_compras(df, key_base=key)

        # =========================
        # EXPLICACION
        # =========================
        if enable_explain:
            if df_agregado is not None and not df_agregado.empty:
                _render_explicacion_compras(df_agregado)
            else:
                _render_explicacion_compras(df)



# =====================================================================
# INTERFAZ STREAMLIT
# =====================================================================
def main():
    st.set_page_config(
        page_title="Ferti Chat - Gestión de Compras",
        page_icon="🦋",
        layout="wide"
    )

    # ✅ CSS responsive
    inject_css_responsive()

    # =====================================================================
    # 🔐 VERIFICAR AUTENTICACIÓN
    # =====================================================================
    if not require_auth():
        st.stop()

    # Si llegó acá, el usuario está autenticado
    user = get_current_user() or {}

    # =====================================================================
    # 🚪 SIDEBAR CON INFO DE USUARIO Y LOGOUT
    # =====================================================================
    with st.sidebar:
        st.markdown(f"""
            <div style='
                background: linear-gradient(135deg, #1e3a5f, #3d7ab5);
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
                color: white;
            '>
                <div style='font-size: 24px; text-align: center; margin-bottom: 5px;'>🦋</div>
                <div style='font-size: 18px; font-weight: bold; text-align: center;'>Ferti Chat</div>
                <div style='font-size: 12px; text-align: center; opacity: 0.8;'>Sistema de Gestión</div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(f"👤 **{user.get('nombre', 'Usuario')}**")
        if user.get('empresa'):
            st.markdown(f"🏢 {user.get('empresa')}")
        st.markdown(f"📧 _{user.get('Usuario', '')}_")

        st.markdown("---")

        if st.button("🚪 Cerrar sesión", use_container_width=True, type="secondary"):
            logout()
            st.rerun()

        st.markdown("---")

    # =========================
    # HEADER DINÁMICO (ARRIBA DEL MENÚ)
    # =========================
    header_slot = st.empty()

    # ======================================================
    # 🚦 REDIRECCIÓN DESDE CAMPANITA
    # ======================================================
    if st.session_state.get("ir_a_pedidos"):
        st.session_state["menu_ui"] = "📄 Pedidos Internos"
        st.session_state["menu_principal"] = "📄 Pedidos Internos"
        st.session_state.pop("ir_a_pedidos")

    # =========================
    # MENÚ ÚNICO (HORIZONTAL)
    # =========================
    menu = st.radio(
        "Menú:",
        [
            "🛒 Compras IA",
            "📦 Stock IA",
            "🔎 Buscador IA",
            "📊 Dashboard",
            "📈 Indicadores IA",
            "📄 Pedidos Internos",
            "📉 Baja de Stock"
        ],
        horizontal=True,
        key="menu_ui"
    )

    # 🔁 Sincronizar menú UI con menú lógico (evita crash de Streamlit)
    if "menu_principal" not in st.session_state:
        st.session_state.menu_principal = menu

    if menu != st.session_state.menu_principal:
        st.session_state.menu_principal = menu


    # DEBUG VISIBLE - QUÉ BUSCÓ LA APP
    if DEBUG_MODE:
        with st.expander("🐞 Debug – Última búsqueda", expanded=False):
            if "debug" in st.session_state:
                st.json(st.session_state.debug)

    # =========================
    # TARJETAS SEGÚN MENÚ
    # =========================
    if menu == "🛒 Compras IA":
        with header_slot.container():
            mostrar_resumen_compras_rotativo()

    elif menu == "📦 Stock IA":
        with header_slot.container():
            mostrar_resumen_stock_rotativo(dias_vencer=30)
            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    else:
        header_slot.empty()

    st.markdown("---")


    # =========================
    # ROUTER DE MÓDULOS
    # =========================
    if menu == "📦 Stock IA":
        mostrar_stock_ia()
        return

    elif menu == "🔎 Buscador IA":
        mostrar_buscador()
        return

    elif menu == "📊 Dashboard":
        mostrar_dashboard()
        return

    elif menu == "📈 Indicadores IA":
        mostrar_indicadores_ia()
        return
    
    elif menu == "📄 Pedidos Internos":
        try:
            from pedidos import mostrar_pedidos_internos
        except Exception:
            import traceback
            st.error("❌ Error cargando pedidos.py (abajo va el error REAL):")
            st.code(traceback.format_exc())
            return

        mostrar_pedidos_internos()
        return

    elif menu == "📉 Baja de Stock":
        from bajastock import mostrar_baja_stock
        mostrar_baja_stock()
        return

    # =========================
    # 🛒 COMPRAS IA
    # =========================
    st.title("🛒 Compras IA")
    st.markdown("*Integrado con OpenAI*")

    if 'historial' not in st.session_state:
        st.session_state.historial = []

    with st.sidebar:
        st.header("📊 Información")
        st.markdown("""
        **Este chatbot entiende:**

        💬 **Conversación:**
        - "Hola", "Buenos días", "Gracias"

        📚 **Conocimiento general:**
        - "¿Qué es HPV?"
        - "¿Para qué sirve un reactivo?"

        📊 **Consultas de datos:**
        - listar proveedores
        - compras roche 2025
        - ultima factura articulo vitek
        - comparar gastos familias junio julio
        - gastos secciones G,FB 2025-06
        """)

        st.markdown("---")

        if st.button("🗑️ Limpiar historial", use_container_width=True):
            st.session_state.historial = []
            st.rerun()

        st.markdown("---")

    if DEBUG_MODE:
        col1, col2 = st.columns(2)

        with col1:
            if st.button("🔌 Test DB", use_container_width=True):
                conn = get_db_connection()
                if conn:
                    st.success("✅ Postgres OK")
                    conn.close()
                else:
                    st.error("❌ Sin conexión")

        with col2:
            if st.button("🧠 Test AI", use_container_width=True):
                try:
                    response = client.chat.completions.create(
                        model=OPENAI_MODEL,
                        messages=[{"role": "user", "content": "Di OK"}],
                        max_tokens=10
                    )
                    st.success("✅ OpenAI OK")
                except Exception as e:
                    st.error(f"❌ {e}")

    # Input
    col1, col2 = st.columns([5, 1])

    with col1:
        pregunta = st.text_input(
            "Escribe tu pregunta:",
            placeholder="Ej: Hola / ¿Qué es HPV? / compras roche junio",
            key="input_pregunta"
        )

    with col2:
        enviar = st.button("Enviar", type="primary", use_container_width=True)

# =========================================================================
    # MANEJAR CLICK EN BOTÓN "SÍ" DE SUGERENCIA
    # =========================================================================
    if st.session_state.get('ejecutar_sugerencia'):
        sugerencia = st.session_state.get('sugerencia_pendiente', '')
        pregunta_orig = st.session_state.get('pregunta_original', '')
        
        # Limpiar estado ANTES de procesar
        st.session_state['ejecutar_sugerencia'] = False
        st.session_state['sugerencia_pendiente'] = None
        st.session_state['mostrar_sugerencia'] = False
        st.session_state['pregunta_original'] = None
        
        if sugerencia:
            with st.spinner("🧠 Ejecutando..."):
                respuesta, df = procesar_pregunta_router(sugerencia)  
                
                # Comparación de FAMILIAS con tabs de moneda
                if respuesta == "__COMPARACION_FAMILIA_TABS__" and 'comparacion_familia_tabs' in st.session_state:
                    tabs_data = st.session_state['comparacion_familia_tabs']
                    st.session_state.historial.append({
                        'pregunta': f"{pregunta_orig} → {sugerencia}",
                        'respuesta': tabs_data['titulo'],
                        'df_pesos': tabs_data['df_pesos'],
                        'df_usd': tabs_data['df_usd'],
                        'es_comparacion_familia': True,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                # Comparación de PROVEEDORES con tabs resumen/detalle
                elif respuesta == "__COMPARACION_TABS__" and 'comparacion_tabs' in st.session_state:
                    tabs_data = st.session_state['comparacion_tabs']
                    st.session_state.historial.append({
                        'pregunta': f"{pregunta_orig} → {sugerencia}",
                        'respuesta': tabs_data['titulo'],
                        'dataframe': tabs_data['resumen'],
                        'dataframe_detalle': tabs_data['detalle'],
                        'es_comparacion': True,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                else:
                    st.session_state.historial.append({
                        'pregunta': f"{pregunta_orig} → {sugerencia}",
                        'respuesta': respuesta,
                        'dataframe': df,
                        'es_comparacion': False,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
            
            # ✅ Mostrar resultado inmediato FUERA del spinner
            st.success("✅ Consulta ejecutada")
            if respuesta and respuesta not in ["__MOSTRAR_SUGERENCIA__", "__COMPARACION_TABS__", "__COMPARACION_FAMILIA_TABS__"]:
                st.markdown(f"**{respuesta}**")
                if df is not None and not df.empty:
                    st.dataframe(df, use_container_width=True, hide_index=True)
    # =========================================================================
    # PROCESAR NUEVA PREGUNTA
    # =========================================================================
    mostrar_sugerencia_ahora = False  # Flag para controlar rerun

    if enviar and pregunta:
        # Limpiar sugerencia anterior
        st.session_state['mostrar_sugerencia'] = False

        with st.spinner("🧠 Procesando..."):
            respuesta, df = procesar_pregunta_router(pregunta)
            render_orquestador_output(pregunta, respuesta, df)

            # Caso especial: Mostrar sugerencia con botones
            if respuesta == "__MOSTRAR_SUGERENCIA__":
                print(f"🎯 Entrando a __MOSTRAR_SUGERENCIA__ para: {pregunta}")
                resultado = obtener_sugerencia_ejecutable(pregunta)

                # Debug: mostrar qué devolvió la IA
                print(f"🤖 IA devolvió: {resultado}")

                if resultado and resultado.get('sugerencia'):
                    print(f"✅ Sugerencia encontrada: {resultado.get('sugerencia')}")
                    st.session_state['mostrar_sugerencia'] = True
                    st.session_state['sugerencia_pendiente'] = resultado['sugerencia']
                    st.session_state['sugerencia_entendido'] = resultado.get('entendido', 'Interpreté tu consulta')
                    st.session_state['sugerencia_alternativas'] = resultado.get('alternativas', [])
                    st.session_state['pregunta_original'] = pregunta
                    mostrar_sugerencia_ahora = True  # Marcar para rerun después del spinner
                    print(f"✅ mostrar_sugerencia_ahora = True, session_state['mostrar_sugerencia'] = True")
                else:
                    print(f"❌ IA no devolvió sugerencia válida")
                    # IA no pudo interpretar → mostrar ayuda en historial
                    st.session_state.historial.append({
                        'pregunta': pregunta,
                        'respuesta': "🤔 No pude interpretar tu consulta. Probá con:\n\n• **compras roche 2025**\n• **comparar roche 2023 2024**\n• **comparar roche noviembre 2023 vs noviembre 2024**\n• **gastos familias noviembre 2025**\n• **última factura vitek**",
                        'dataframe': None,
                        'es_comparacion': False,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })

            # Manejar comparación de FAMILIAS con tabs de moneda
            elif respuesta == "__COMPARACION_FAMILIA_TABS__" and 'comparacion_familia_tabs' in st.session_state:
                tabs_data = st.session_state['comparacion_familia_tabs']
                st.session_state.historial.append({
                    'pregunta': pregunta,
                    'respuesta': tabs_data['titulo'],
                    'df_pesos': tabs_data['df_pesos'],
                    'df_usd': tabs_data['df_usd'],
                    'es_comparacion_familia': True,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

            # Manejar comparación con tabs
            elif respuesta == "__COMPARACION_TABS__" and 'comparacion_tabs' in st.session_state:
                tabs_data = st.session_state['comparacion_tabs']
                st.session_state.historial.append({
                    'pregunta': pregunta,
                    'respuesta': tabs_data['titulo'],
                    'dataframe': tabs_data['resumen'],
                    'dataframe_detalle': tabs_data['detalle'],
                    'es_comparacion': True,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            else:
                st.session_state.historial.append({
                    'pregunta': pregunta,
                    'respuesta': respuesta,
                    'dataframe': df,
                    'es_comparacion': False,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

                # ✅ RENDER INMEDIATO (texto + tabla modo celular)
                if respuesta and respuesta not in ["__MOSTRAR_SUGERENCIA__", "__COMPARACION_TABS__", "__COMPARACION_FAMILIA_TABS__"]:
                    st.markdown("**Respuesta:**")
                    st.markdown(respuesta)
                    mostrar_detalle_df(
                        df,
                        titulo="📄 Ver detalle de compras",
                        key=f"curr_{len(st.session_state.historial)}",
                        contexto_respuesta=respuesta
                    )


    # Hacer rerun DESPUÉS del spinner si hay sugerencia pendiente
    if mostrar_sugerencia_ahora:
        print(f"🔄 Haciendo st.rerun() porque mostrar_sugerencia_ahora=True")
        st.rerun()

    # Mostrar sugerencia con botones (si está pendiente)
    if st.session_state.get('mostrar_sugerencia'):
        print(f"🎨 Renderizando sugerencia: {st.session_state.get('sugerencia_pendiente')}")
        sugerencia = st.session_state.get('sugerencia_pendiente', '')
        entendido = st.session_state.get('sugerencia_entendido', '')
        alternativas = st.session_state.get('sugerencia_alternativas', [])

        if sugerencia:  # Solo mostrar si hay sugerencia válida
            st.info(f"🤔 **{entendido}**")
            st.markdown(f"**¿Quisiste decir:** `{sugerencia}`?")

            col_si, col_no = st.columns(2)

            with col_si:
                if st.button("✅ Sí, ejecutar", key="btn_si_sugerencia", type="primary"):
                    st.session_state['ejecutar_sugerencia'] = True
                    st.rerun()

            with col_no:
                if st.button("❌ No", key="btn_no_sugerencia"):
                    st.session_state['mostrar_sugerencia'] = False
                    st.session_state['sugerencia_pendiente'] = None
                    st.rerun()

            # Alternativas
            if alternativas:
                st.caption("**Otras opciones:**")
                for i, alt in enumerate(alternativas[:2]):
                    if st.button(f"📝 {alt}", key=f"btn_alt_{i}"):
                        st.session_state['sugerencia_pendiente'] = alt
                        st.session_state['ejecutar_sugerencia'] = True
                        st.rerun()

    # =========================================================================
    # Historial (movido después de sugerencias)
    # =========================================================================
    if st.session_state.historial:
        st.markdown("---")
        st.subheader("📜 Historial")

        for i, item in enumerate(reversed(st.session_state.historial)):
            with st.expander(
                f"🕐 {item['timestamp']} - {item['pregunta'][:50]}...",
                expanded=(i == 0)
            ):
                st.markdown(f"**Pregunta:** {item['pregunta']}")
                st.markdown("**Respuesta:**")
                st.markdown(item['respuesta'])

                # Si es comparación de FAMILIA con tabs de moneda
                if item.get('es_comparacion_familia'):
                    tab_pesos, tab_usd = st.tabs(["💵 Pesos ($)", "💰 Dólares (U$S)"])

                    with tab_pesos:
                        if item.get('df_pesos') is not None and not item['df_pesos'].empty:
                            st.dataframe(
                                formatear_dataframe(item['df_pesos']),
                                use_container_width=True,
                                hide_index=True
                            )
                            excel_data_pesos = df_to_excel(item['df_pesos'])
                            st.download_button(
                                label="📥 Descargar Pesos",
                                data=excel_data_pesos,
                                file_name="comparacion_familia_pesos.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"dl_fam_pesos_{i}"
                            )
                        else:
                            st.info("No hay datos en pesos para este período")

                    with tab_usd:
                        if item.get('df_usd') is not None and not item['df_usd'].empty:
                            st.dataframe(
                                formatear_dataframe(item['df_usd']),
                                use_container_width=True,
                                hide_index=True
                            )
                            excel_data_usd = df_to_excel(item['df_usd'])
                            st.download_button(
                                label="📥 Descargar USD",
                                data=excel_data_usd,
                                file_name="comparacion_familia_usd.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"dl_fam_usd_{i}"
                            )
                        else:
                            st.info("No hay datos en dólares para este período")

                # Si es comparación proveedor, mostrar tabs resumen/detalle
                elif item.get('es_comparacion') and item.get('dataframe') is not None:
                    tab1, tab2 = st.tabs(["📊 Resumen", "📋 Detalle"])

                    with tab1:
                        st.dataframe(
                            item['dataframe'],
                            use_container_width=True,
                            hide_index=True
                        )
                        # Botón descargar resumen
                        excel_data = df_to_excel(item['dataframe'])
                        st.download_button(
                            label="📥 Descargar Resumen",
                            data=excel_data,
                            file_name="comparacion_resumen.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_resumen_{i}"
                        )

                    with tab2:
                        if item.get('dataframe_detalle') is not None and not item['dataframe_detalle'].empty:
                            st.dataframe(
                                item['dataframe_detalle'],
                                use_container_width=True,
                                hide_index=True
                            )
                            # Botón descargar detalle
                            excel_data_det = df_to_excel(item['dataframe_detalle'])
                            st.download_button(
                                label="📥 Descargar Detalle",
                                data=excel_data_det,
                                file_name="comparacion_detalle.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"dl_detalle_{i}"
                            )
                        else:
                            st.info("No hay detalle disponible")

                elif item.get('dataframe') is not None and not item['dataframe'].empty:
                    # ✅ ACÁ VA LO QUE PREGUNTABAS: render tabla modo celular dentro del historial
                    mostrar_detalle_df(
                        item.get('dataframe'),
                        titulo="📄 Ver tabla (detalle)",
                        key=f"hist_{i}"
                    )
    else:
        st.info("👋 ¡Hola! Escribime cualquier cosa: un saludo, una pregunta, o una consulta de datos.")


if __name__ == "__main__":
    main()
