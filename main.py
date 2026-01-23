import streamlit as st

st.set_page_config(
    page_title="FertiChat",
    page_icon="🦋",
    layout="wide",
    initial_sidebar_state="auto",
)

from ui_css import CSS_GLOBAL
from login_page import require_auth, get_current_user, logout
from imports_globales import *

from config import MENU_OPTIONS, DEBUG_MODE
from auth import init_db
from pedidos import mostrar_pedidos_internos, contar_notificaciones_no_leidas
from bajastock import mostrar_baja_stock
from ordenes_compra import mostrar_ordenes_compra
from ui_compras import Compras_IA
from ui_buscador import mostrar_buscador_ia
from ui_stock import mostrar_stock_ia, mostrar_resumen_stock_rotativo
from ui_dashboard import (
    mostrar_dashboard,
    mostrar_indicadores_ia,
    mostrar_resumen_compras_rotativo,
)
from ingreso_comprobantes import mostrar_ingreso_comprobantes
from ui_inicio import mostrar_inicio
from ficha_stock import mostrar_ficha_stock
from articulos import mostrar_articulos
from depositos import mostrar_depositos
from familias import mostrar_familias
from comprobantes import mostrar_menu_comprobantes
from ui_chat_chainlit import mostrar_chat_chainlit
from sql_core import ejecutar_consulta

from ia_router import interpretar_pregunta

print(">>> 🚀 USANDO IA_ROUTER: ia_router.interpretar_pregunta")

from sql_facturas import (
    get_facturas_proveedor as get_facturas_proveedor_detalle,
    get_detalle_factura_por_numero,
    buscar_facturas_similares,
)
from sql_compras import (
    get_compras_proveedor_anio,
    get_detalle_compras_proveedor_mes,
    get_compras_multiples,
    get_compras_anio,
    get_top_proveedores_por_anios,
)
from utils_format import formatear_dataframe
from utils_openai import responder_con_openai

from sql_facturas import (
    get_facturas_proveedor as get_facturas_proveedor_detalle,
    get_detalle_factura_por_numero,
    buscar_facturas_similares,
)
from sql_compras import (
    get_compras_proveedor_anio,
    get_detalle_compras_proveedor_mes,
    get_compras_multiples,
    get_compras_anio,
    get_top_proveedores_por_anios,  # 🔥 AGREGADO: Función para top proveedores por año
)
from utils_format import formatear_dataframe
from utils_openai import responder_con_openai

# =========================
# IMPORT ORQUESTADOR PARA INTEGRACIÓN (con try-except para evitar errores)
# =========================
try:
    from orquestador import procesar_pregunta_v2
except ImportError:
    def procesar_pregunta_v2(*args, **kwargs):
        return "Orquestador no disponible", None, None

# =========================
# DETECCIÓN DE DISPOSITIVO
# =========================
def inicializar_deteccion_dispositivo():
    """
    Inicializa la detección de dispositivo usando JavaScript.
    Se ejecuta una sola vez al inicio.
    """
    if "device_detected" not in st.session_state:
        st.session_state["device_detected"] = False
        st.session_state["is_mobile"] = False  # Default a desktop
        
        # JavaScript para detectar ancho de pantalla
        js_detect = """
        <script>
        const width = window.innerWidth || document.documentElement.clientWidth;
        const isMobile = width < 768;
        
        // Guardar en localStorage para persistencia
        if (typeof(Storage) !== "undefined") {
            localStorage.setItem('viewport_width', width);
            localStorage.setItem('is_mobile', isMobile);
        }
        </script>
        """
        
        st.components.v1.html(js_detect, height=0)
        
        # Marcar como detectado
        st.session_state["device_detected"] = True


def agregar_selector_manual_dispositivo():
    """
    Agrega un selector manual en el sidebar para cambiar entre mobile/desktop.
    Útil para testing y para usuarios que quieran forzar una vista.
    """
    with st.sidebar:
        st.markdown("---")
        
        # Obtener estado actual
        es_mobile_actual = st.session_state.get("is_mobile", False)
        
        dispositivo = st.radio(
            "🖥️ Vista",
            options=["💻 Desktop", "📱 Mobile"],
            index=1 if es_mobile_actual else 0,
            horizontal=True,
            key="selector_dispositivo_manual",
            help="Cambia la vista between desktop and mobile"
        )
        
        # Actualizar session_state
        st.session_state["is_mobile"] = (dispositivo == "📱 Mobile")


# =========================
# FUNCIÓN PARA EJECUTAR CONSULTAS POR TIPO (AGREGADA)
# =========================
def ejecutar_consulta_por_tipo(tipo: str, params: dict, pregunta_original: str):
    try:
        # =========================================================
        # FACTURAS (LISTADO) - usa sql_facturas
        # =========================================================
        if tipo in ("facturas_proveedor", "facturas_proveedor_detalle"):
            proveedores = params.get("proveedores", [])
            if isinstance(proveedores, str):
                proveedores = [proveedores]

            proveedores_raw = [str(p).strip() for p in proveedores if str(p).strip()]
            if not proveedores_raw:
                return "❌ Indicá el proveedor. Ej: todas las facturas roche 2025", None, None

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
                debug_msg = f"⚠️ No se encontraron resultados para '{pregunta_original}'.\n\n"
                debug_msg += "Revisá la consola del servidor para ver el SQL impreso."
                return debug_msg, None, None

            prov_lbl = ", ".join([p.upper() for p in proveedores_raw[:3]])
            return (
                f"🧾 Facturas de **{prov_lbl}** ({len(df)} registros):",
                formatear_dataframe(df),
                None,
            )

        # =========================================================
        # COMPRAS (NUEVO)
        # =========================================================
        elif tipo == "compras_proveedor_anio":
            proveedor = params.get("proveedor", "").strip()
            anio = params.get("anio", 2025)
            if not proveedor:
                return "❌ Indicá el proveedor. Ej: compras roche 2025", None, None

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
            anio = params.get("anio")

            if not proveedor or not mes:
                return "❌ Indicá proveedor y mes. Ej: compras roche noviembre 2025", None, None

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
            limite = params.get("limite", 10)

            # =========================
            # DEBUG – INTERPRETACIÓN
            # =========================
            st.session_state["DBG_INT_LAST"] = {
                "tipo": tipo,
                "parametros": params,
                "pregunta": pregunta_original,
            }

            # =========================
            # DEBUG – ROUTER
            # =========================
            st.session_state["DBG_ROUTER_LAST"] = {
                "tipo": tipo,
                "parametros": params,
            }

            # =========================
            # EJECUCIÓN SQL
            # =========================
            df = get_top_proveedores_por_anios(anios=[anio], limite=limite)

            # =========================
            # DEBUG – SQL
            # =========================
            st.session_state["DBG_SQL_LAST_TAG"] = "sql_compras.get_top_proveedores_por_anios"
            st.session_state["DBG_SQL_PARAMS"] = {"anios": [anio], "limite": limite}

            if df is None or df.empty:
                st.session_state["DBG_SQL_ROWS"] = 0
                st.session_state["DBG_SQL_COLS"] = []
                return f"⚠️ No se encontraron compras en {anio}.", None, None

            st.session_state["DBG_SQL_ROWS"] = len(df)
            st.session_state["DBG_SQL_COLS"] = list(df.columns)

            total_general = df["Total"].sum() if "Total" in df.columns else 0

            return (
                f"📊 **Top {len(df)} Proveedores - Compras {anio}**\n\n"
                f"💰 Total: ${total_general:,.2f}",
                formatear_dataframe(df),
                None,
            )

        # =========================================================
        # DASHBOARD – TOP PROVEEDORES POR AÑO
        # =========================================================
        elif tipo == "dashboard_top_proveedores":
            from sql_compras import get_dashboard_top_proveedores

            anio = params.get("anio")
            top_n = params.get("top_n", 10)
            moneda = params.get("moneda", "$")

            if not anio:
                return "❌ Indic�� el año. Ej: top proveedores 2025", None, None

            df = get_dashboard_top_proveedores(anio=anio, top_n=top_n, moneda=moneda)

            if df is None or df.empty:
                return f"⚠️ No se encontraron proveedores para {anio}.", None, None

            moneda_label = "USD" if moneda == "U$S" else "pesos"
            return (
                f"🏭 Top {top_n} proveedores {anio} en {moneda_label}:",
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
            
            df = get_detalle_factura_por_numero(nro_factura)
            
            # Si no se encuentra la factura, buscar similares
            if df is None or df.empty:
                print(f"⚠️ No se encontró factura exacta, buscando similares a '{nro_factura}'...")
                similares = buscar_facturas_similares(nro_factura, limite=20)
                
                if similares is not None and not similares.empty:
                    mensaje = f"⚠️ No se encontró la factura **{nro_factura}** exactamente.\n\n"
                    mensaje += f"📋 Encontré **{len(similares)}** factura(s) similar(es):\n"
                    return (
                        mensaje,
                        formatear_dataframe(similares),
                        None,
                    )
                else:
                    return f"❌ No se encontró la factura {nro_factura} ni facturas similares.", None, None
            
            # Obtener info del encabezado
            proveedor = df["Proveedor"].iloc[0] if "Proveedor" in df.columns else "N/A"
            fecha = df["Fecha"].iloc[0] if "Fecha" in df.columns else "N/A"
            moneda = df["Moneda"].iloc[0] if "Moneda" in df.columns else ""
            nro_factura_encontrado = df["nro_factura"].iloc[0] if "nro_factura" in df.columns else nro_factura
            
            # Calcular totales
            total_lineas = len(df)
            total_monto = df["Total"].sum() if "Total" in df.columns else 0
            
            mensaje = f"📄 **Factura {nro_factura_encontrado}**\n"
            mensaje += f"🏢 Proveedor: **{proveedor}**\n"
            mensaje += f"📅 Fecha: {fecha}\n"
            mensaje += f"💰 Total: {moneda} {total_monto:,.2f}\n"
            mensaje += f"📦 {total_lineas} artículo(s)\n"
            
            return (
                mensaje,
                formatear_dataframe(df),
                None,
            )

        # =========================================================
        # OTROS TIPOS
        # =========================================================
        return f"❌ Tipo de consulta '{tipo}' no implementado.", None, None

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Error: {str(e)[:150]}", None, None

# =========================
# ESTILO GLOBAL E INICIO DE SESIÓN
# =========================
st.markdown(CSS_GLOBAL, unsafe_allow_html=True)

# =========================
# CSS PARA ELIMINAR TODO PADDING SUPERIOR (más específico)
# =========================
st.markdown("""
<style>
/* ====== ELIMINAR TODO PADDING SUPERIOR ====== */

/* Contenedor principal de la app */
.main > div:first-child {
    padding-top: 0rem !important;
}

/* Bloque principal */
.main .block-container {
    padding-top: 0rem !important;
    padding-bottom: 0rem !important;
    margin-top: 0rem !important;
}

/* Todos los bloques verticales (el que ves en violeta) */
div.stVerticalBlock,
div[data-testid="stVerticalBlock"],
div[class*="stVerticalBlock"] {
    padding-top: 0rem !important;
    margin-top: 0rem !important;
    gap: 0rem !important;
}

/* Contenedor de la vista */
div[data-testid="stAppViewContainer"] {
    padding-top: 0rem !important;
}

/* Primer elemento de cada sección */
.main > div:first-child > div:first-child {
    padding-top: 0rem !important;
}

/* Si tenés header fijo */
header[data-testid="stHeader"] {
    background-color: transparent;
    height: 0rem;
}

/* Ajuste fino - solo dejá un mínimo para que no se solape con el header del navegador */
.main .block-container {
    padding-top: 0.5rem !important;
}
</style>
""", unsafe_allow_html=True)

# =========================
# CSS PARA OCULTAR KEEPALIVE / AUTOREFRESH
# =========================
st.markdown("""
<style>
/* ====== OCULTAR KEEPALIVE / AUTOREFRESH ====== */

/* Ocultar componente keepalive por su key única */
div[class*="st-key-fc_keepalive"],
div.st-key-fc_keepalive,
[data-testid="stElementContainer"].st-key-fc_keepalive {
    display: none !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    visibility: hidden !important;
}

/* Ocultar cualquier iframe de autorefresh */
iframe[src*="streamlit_autorefresh"] {
    display: none !important;
    height: 0 !important;
}

/* Ocultar contenedor padre del autorefresh */
div.stElementContainer:has(iframe[src*="streamlit_autorefresh"]) {
    display: none !important;
    height: 0 !important;
}
</style>
""", unsafe_allow_html=True)

# =========================
# CSS PARA SUAVIZAR RERUN (quitar animaciones y loaders)
# =========================
st.markdown("""
<style>
/* Quitar animaciones de rerun */
.stApp {
    transition: none !important;
}

/* Quitar fade-in */
section[data-testid="stMain"] {
    animation: none !important;
}

/* Quitar shimmer / placeholders */
[data-testid="stSkeleton"] {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)

# =========================
# FIX UI: BOTONES DEL SIDEBAR (evita texto vertical en "Cerrar sesión")
# =========================
CSS_SIDEBAR_BUTTON_FIX = """
<style>
/* Si en Home tenés CSS que transforma .stButton en "tarjeta", puede pegarle al sidebar.
   Esto lo pisa SOLO en el sidebar para evitar quiebres por char (texto vertical). */
section[data-testid="stSidebar"] .stButton > button,
div[data-testid="stSidebar"] .stButton > button{
    height: auto !important;
    min-height: unset !important;
    padding: 0.55rem 0.85rem !important;
    border-radius: 12px !important;
    width: auto !important;
    white-space: nowrap !important;
}
section[data-testid="stSidebar"] .stButton > button * ,
div[data-testid="stSidebar"] .stButton > button *{
    white-space: nowrap !important;
}
</style>
"""
st.markdown(CSS_SIDEBAR_BUTTON_FIX, unsafe_allow_html=True)

require_auth()
st.title("Inicio")

# =========================
# CONTAINER FIJO PARA EVITAR DESPLAZAMIENTO VISUAL
# =========================
main_container = st.container()

# =========================
# INICIALIZACIÓN
# =========================
init_db()
user = get_current_user() or {}

# Grupos del menú - SIN EMOJIS
groups = {
    "PRINCIPAL": ["Inicio", "Compras IA", "Buscador IA", "Stock IA"],
    "GESTIÓN": ["Pedidos internos", "Baja de stock", "Órdenes de compra", "Ingreso de comprobantes", "Sugerencia de pedidos"],
    "CATÁLOGO": ["Artículos", "Familias", "Depósitos", "Comprobantes"],
    "ANÁLISIS": ["Dashboard", "Indicadores (Power BI)"],
}

# Inicializar página
if "pagina" not in st.session_state:
    st.session_state.pagina = "Inicio"

# Inicializar radios
for group in groups:
    key = f"radio_{group.lower()}"
    if key not in st.session_state:
        if group == "PRINCIPAL":
            st.session_state[key] = "Inicio"
        else:
            st.session_state[key] = None

# Forzar flag del orquestador
st.session_state["ORQUESTADOR_CARGADO"] = True

# Reaplicar CSS (por compatibilidad con versiones anteriores)
st.markdown(f"<style>{CSS_GLOBAL}</style>", unsafe_allow_html=True)

# =========================
# INICIALIZACIÓN
# =========================
inicializar_deteccion_dispositivo()

# =========================
# NOTIFICACIONES
# =========================
usuario_actual = user.get("usuario", user.get("email", ""))
cant_pendientes = 0
if usuario_actual:
    cant_pendientes = contar_notificaciones_no_leidas(usuario_actual)

# =========================
# HEADER MÓVIL
# =========================
badge_html = ""
if cant_pendientes > 0:
    badge_html = f'<span class="notif-badge">{cant_pendientes}</span>'

st.markdown(
    f"""
<div id="mobile-header">
    <div class="logo">🦋 FertiChat</div>
</div>
<a id="campana-mobile" href="?ir_notif=1">
    🔔
    {badge_html}
</a>
""",
    unsafe_allow_html=True,
)

# =========================
# HEADER ESCRITORIO
# =========================
campana_html = '<span style="font-size:26px;">🔔</span>'
if cant_pendientes > 0:
    campana_html = (
        '<a href="?ir_notif=1" '
        'style="text-decoration:none;font-size:18px;'
        "background:#0b3b60;color:white;padding:6px 12px;"
        'border-radius:8px;">'
        f"🔔 {cant_pendientes}</a>"
    )

st.markdown(
    """
<style>
@media (max-width: 768px) {
  .header-desktop-wrapper { display: none !important; }
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    f"""
<div class="header-desktop-wrapper" style="display: none;">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
            <h1 style="margin:0; font-size:38px; font-weight:900; color:#0f172a;">FertiChat</h1>
            <p style="margin:4px 0 0 0; font-size:15px; color:#64748b;">
                Sistema de Gestión de Compras
            </p>
        </div>
        <div>{campana_html}</div>
    </div>
    <hr style="margin-top:16px; border:none; border-top:1px solid #e2e8f0;">
</div>
""",
    unsafe_allow_html=True,
)

# =========================
# NAVEGACIÓN POR QUERY PARAMS (tarjetas / campana)
# =========================
def _get_qp_first(key: str):
    try:
        v = st.query_params.get(key)
        if isinstance(v, list):
            return v[0] if v else None
        return v
    except Exception:
        qp = st.experimental_get_query_params()
        lst = qp.get(key)
        return lst[0] if isinstance(lst, list) and lst else None


def _clear_qp():
    try:
        st.query_params.clear()
    except Exception:
        st.experimental_set_query_params()


# Desde tarjetas (go=?)
_go = _get_qp_first("go")
if _go == "compras":
    with st.spinner("⏳ Cargando Compras..."):
        st.session_state["radio_principal"] = "Compras IA"
        st.session_state.pagina = "Compras IA"
        for g in groups:
            if g != "PRINCIPAL":
                st.session_state[f"radio_{g.lower()}"] = None
    _clear_qp()
    st.rerun()

elif _go == "buscador":
    with st.spinner("🔍 Cargando Buscador..."):
        st.session_state["radio_principal"] = "Buscador IA"
        st.session_state.pagina = "Buscador IA"
        for g in groups:
            if g != "PRINCIPAL":
                st.session_state[f"radio_{g.lower()}"] = None
    _clear_qp()
    st.rerun()

elif _go == "stock":
    with st.spinner("📦 Cargando Stock..."):
        st.session_state["radio_principal"] = "Stock IA"
        st.session_state.pagina = "Stock IA"
        for g in groups:
            if g != "PRINCIPAL":
                st.session_state[f"radio_{g.lower()}"] = None
    _clear_qp()
    st.rerun()

elif _go == "dashboard":
    with st.spinner("📊 Cargando Dashboard..."):
        st.session_state["radio_analisis"] = "Dashboard"
        st.session_state.pagina = "Dashboard"
        for g in groups:
            if g != "ANÁLISIS":
                st.session_state[f"radio_{g.lower()}"] = None
    _clear_qp()
    st.rerun()

elif _go == "pedidos":
    with st.spinner("📄 Cargando Pedidos..."):
        st.session_state["radio_gestion"] = "Pedidos internos"
        st.session_state.pagina = "Pedidos internos"
        for g in groups:
            if g != "GESTIÓN":
                st.session_state[f"radio_{g.lower()}"] = None
    _clear_qp()
    st.rerun()

elif _go == "baja":
    with st.spinner("🧾 Cargando Baja de Stock..."):
        st.session_state["radio_gestion"] = "Baja de stock"
        st.session_state.pagina = "Baja de stock"
        for g in groups:
            if g != "GESTIÓN":
                st.session_state[f"radio_{g.lower()}"] = None
    _clear_qp()
    st.rerun()

elif _go == "ordenes":
    with st.spinner("📦 Cargando Órdenes..."):
        st.session_state["radio_gestion"] = "Órdenes de compra"
        st.session_state.pagina = "Órdenes de compra"
        for g in groups:
            if g != "GESTIÓN":
                st.session_state[f"radio_{g.lower()}"] = None
    _clear_qp()
    st.rerun()

elif _go == "indicadores":
    with st.spinner("📈 Cargando Indicadores..."):
        st.session_state["radio_analisis"] = "Indicadores (Power BI)"
        st.session_state.pagina = "Indicadores (Power BI)"
        for g in groups:
            if g != "ANÁLISIS":
                st.session_state[f"radio_{g.lower()}"] = None
    _clear_qp()
    st.rerun()

# Desde campana (ir_notif=1)
try:
    if st.query_params.get("ir_notif") == "1":
        with st.spinner("🔔 Cargando Notificaciones..."):
            st.session_state["radio_gestion"] = "Pedidos internos"
            st.session_state.pagina = "Pedidos internos"
            for g in groups:
                if g != "GESTIÓN":
                    st.session_state[f"radio_{g.lower()}"] = None
        _clear_qp()
        st.rerun()
except Exception:
    pass

# =========================
# SIDEBAR
# =========================
def update_pagina(group):
    selected = st.session_state[f"radio_{group.lower()}"]
    if selected:
        st.session_state.pagina = selected
        for g in groups:
            if g != group:
                st.session_state[f"radio_{g.lower()}"] = None

with st.sidebar:
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] {
        background: #ffffff !important;
        border-right: 1px solid rgba(148, 163, 184, 0.15);
    }
    
    section[data-testid="stSidebar"] > div {
        background: #ffffff !important;
    }
    
    .fc-sidebar-header {
        background: rgba(255,255,255,0.85);
        padding: 16px;
        border-radius: 18px;
        margin-bottom: 14px;
        border: 1px solid rgba(15, 23, 42, 0.10);
        box-shadow: 0 10px 26px rgba(2, 6, 23, 0.06);
    }
    
    .fc-section-header {
        font-size: 16px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #94a3b8;
        padding: 12px 16px 8px 16px;
        margin: 16px 0 2px 0;
        display: block !important;
        width: 100%;
        overflow: visible !important;
        white-space: nowrap !important;
    }
    
    /* Ocultar TODOS los labels de widgets en el sidebar */
    section[data-testid="stSidebar"] label[data-testid="stWidgetLabel"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* Hacer círculos MUCHO MÁS CHICOS */
    section[data-testid="stSidebar"] input[type="radio"] {
        width: 12px !important;
        height: 12px !important;
        min-width: 12px !important;
        margin-right: 8px !important;
        flex-shrink: 0 !important;
        accent-color: #3b82f6 !important;
    }
    
    /* Contenedor MÁS COMPACTO */
    section[data-testid="stSidebar"] .stRadio > div {
        gap: 0 !important;
    }
    
    /* Labels SÚPER COMPACTOS */
    section[data-testid="stSidebar"] .stRadio label {
        padding: 4px 12px 4px 8px !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        color: #475569 !important;
        border-left: 3px solid transparent !important;
        transition: all 120ms ease !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        margin: 0 !important;
        background: transparent !important;
        position: relative !important;
        min-height: 28px !important;
        line-height: 1.2 !important;
    }
    
    /* Flechita azul ANTES del círculo */
    section[data-testid="stSidebar"] .stRadio label::before {
        content: '▸' !important;
        position: absolute !important;
        left: -12px !important;
        top: 50% !important;
        transform: translateY(-50%) !important;
        color: #3b82f6 !important;
        font-size: 14px !important;
        font-weight: 400 !important;
        line-height: 1 !important;
    }
    
    /* Flechita más bold cuando está seleccionado */
    section[data-testid="stSidebar"] .stRadio input:checked + div label::before {
        font-weight: 900 !important;
    }
    
    section[data-testid="stSidebar"] .stRadio label:hover {
        background: #f8fafc !important;
    }
    
    section[data-testid="stSidebar"] .stRadio input:checked + div label {
        background: #ebf5ff !important;
        border-left-color: #3b82f6 !important;
        font-weight: 600 !important;
        color: #1e293b !important;
    }
    
    .fc-divider {
        height: 1px;
        background: rgba(148, 163, 184, 0.15);
        margin: 16px 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header con logo
    st.markdown("""
    <div class='fc-sidebar-header'>
        <div style='display:flex; align-items:center; gap:10px; justify-content:center;'>
            <div style='font-size: 26px;'>🦋</div>
            <div style='font-size: 20px; font-weight: 800; color:#0f172a;'>FertiChat</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Buscador
    st.text_input(
        "Buscar...",
        key="sidebar_search",
        label_visibility="collapsed",
        placeholder="Buscar...",
    )
    
    # Info usuario
    st.markdown(f"👤 **{user.get('nombre', 'Usuario')}**")
    if user.get("empresa"):
        st.markdown(f"🏢 {user.get('empresa')}")
    st.markdown(f"📧 _{user.get('Usuario', user.get('usuario', ''))}_")
    
    st.markdown('<div class="fc-divider"></div>', unsafe_allow_html=True)
    
    # Botón cerrar sesión
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚪 Cerrar sesión", key="btn_logout_sidebar"):
            logout()
            st.rerun()
    
    st.markdown('<div class="fc-divider"></div>', unsafe_allow_html=True)
    
    # Debug SQL
    st.session_state["DEBUG_SQL"] = st.checkbox(
        "Debug SQL", value=False, key="debug_sql"
    )
    
    st.markdown('<div class="fc-divider"></div>', unsafe_allow_html=True)
    
    # =========================
    # Menu agrupado (PRINCIPAL con Compras IA como grupo)
    # =========================
    for group, options in groups.items():
        st.markdown(
            f'<div class="fc-section-header">{group}</div>',
            unsafe_allow_html=True
        )

        # ===== PRINCIPAL =====
        if group == "PRINCIPAL":
            # Opciones SIN "Compras IA"
            opciones_principal = [o for o in options if o != "Compras IA"]

            # Grupo Compras IA (visual)
            st.markdown(
                "<div style='font-weight:600; padding:4px 12px; color:#475569;'>▶ Compras IA</div>",
                unsafe_allow_html=True
            )

            # Submenú real
            sub = st.radio(
                "",
                ["Compras", "Comparar"],
                key="submenu_compras_ia",
                label_visibility="collapsed",
            )

            # Página real (NO cambia lógica todavía)
            st.session_state.pagina = "Compras IA"

            # Resto de opciones normales
            st.radio(
                "Opciones",
                opciones_principal,
                key=f"radio_{group.lower()}",
                label_visibility="collapsed",
                on_change=update_pagina,
                args=(group,),
            )

        # ===== RESTO DE LOS GRUPOS =====
        else:
            st.radio(
                "Opciones",
                options,
                key=f"radio_{group.lower()}",
                label_visibility="collapsed",
                on_change=update_pagina,
                args=(group,),
            )

    st.components.v1.html(r"""
    <script>
    (function() {
        const interval = setInterval(() => {
            const labels = parent.document.querySelectorAll(
                'section[data-testid="stSidebar"] .stRadio label p'
            );
            if (labels.length > 0) {
                labels.forEach(label => {
                    label.textContent = label.textContent
                        .replace(/[\u{1F000}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '')
                        .trim();
                });
                clearInterval(interval);
            }
        }, 50);
    })();
    </script>
    """, height=0)


# =========================
# FUNCIÓN DEBUG SQL FACTURA (pestaña aparte)
# =========================
def mostrar_debug_sql_factura():
    st.header("🔍 Debug SQL Factura")

    # Probar conexión
    try:
        test_df = ejecutar_consulta("SELECT 1 as test", ())
        if test_df is not None and not test_df.empty:
            st.success("✅ Base de datos conectada ok")
        else:
            st.error("❌ Base de datos no responde")
    except Exception as e:
        st.error(f"❌ Error en base de datos: {str(e)[:100]}")

    # Estado orquestador
    if st.session_state.get("ORQUESTADOR_CARGADO"):
        st.success("✅ Orquestador funcionando ok")
    else:
        st.warning("⚠️ Orquestador no cargado")

    # Params últimos de facturas (si los usás desde sql_facturas)
    if "DEBUG_SQL_FACTURA_PARAMS" in st.session_state:
        st.subheader("🎯 Interpretador trata de traer esto:")
        params = st.session_state["DEBUG_SQL_FACTURA_PARAMS"]
        st.json(params)
        st.write("Proveedores:", params.get("proveedores", []))
        st.write("Años:", params.get("anios", []))
        st.write("Meses:", params.get("meses", []))
        st.write("Moneda:", params.get("moneda", "Ninguna"))
        st.write("Límite:", params.get("limite", 5000))
    else:
        st.info(
            "ℹ️ No hay params de consulta reciente. "
            "Hacé una consulta como 'todas las facturas roche 2025' primero."
        )

    # SQL último de facturas
    if "DEBUG_SQL_FACTURA_QUERY" in st.session_state:
        st.subheader("🛠 SQL trata de traer:")
        query = st.session_state["DEBUG_SQL_FACTURA_QUERY"]
        st.code(query, language="sql")
        st.write("**Tabla objetivo:** chatbot_raw")
    else:
        st.info("ℹ️ No hay SQL reciente. Hacé una consulta primero.")


# =========================
# ROUTER PRINCIPAL CON CONTAINER FIJO
# =========================
with main_container:
    if st.session_state.pagina == "Inicio":
        mostrar_inicio()

    elif "Chat (Chainlit)" in st.session_state.pagina:
        mostrar_chat_chainlit()

    elif st.session_state.pagina == "Compras IA":
        mostrar_resumen_compras_rotativo()
        Compras_IA()

        # Panel de debug general (última consulta)
        if st.session_state.get("DEBUG_SQL", False):
            with st.expander("🛠 Debug (última consulta)", expanded=True):
                st.subheader("Interpretación")
                st.json(st.session_state.get("DBG_INT_LAST", {}))
                st.subheader("SQL ejecutado")
                st.write("Origen:", st.session_state.get("DBG_SQL_LAST_TAG"))
                st.subheader("Resultado")
                st.write("Filas:", st.session_state.get("DBG_SQL_ROWS"))
                st.write("Columnas:", st.session_state.get("DBG_SQL_COLS", []))

    elif st.session_state.pagina == "🔍 Debug SQL factura":
        mostrar_debug_sql_factura()

    elif st.session_state.pagina == "Stock IA":
        mostrar_resumen_stock_rotativo(dias_vencer=30)  # Cambiado a 30 días
        mostrar_stock_ia()

    elif st.session_state.pagina == "Buscador IA":
        mostrar_buscador_ia()

    elif st.session_state.pagina == "Ingreso de comprobantes":
        mostrar_ingreso_comprobantes()

    elif st.session_state.pagina == "Dashboard":
        mostrar_dashboard()

    elif st.session_state.pagina == "Pedidos internos":
        mostrar_pedidos_internos()

    elif st.session_state.pagina == "Baja de stock":
        mostrar_baja_stock()

    elif st.session_state.pagina == "Indicadores (Power BI)":
        mostrar_indicadores_ia()

    elif st.session_state.pagina == "Órdenes de compra":
        mostrar_ordenes_compra()

    elif st.session_state.pagina == "📒 Ficha de stock":
        mostrar_ficha_stock()

    elif st.session_state.pagina == "Artículos":
        mostrar_articulos()

    elif st.session_state.pagina == "Depósitos":
        mostrar_depositos()

    elif st.session_state.pagina == "Familias":
        mostrar_familias()

    elif st.session_state.pagina == "Comprobantes":
        mostrar_menu_comprobantes()

    # ← CONDICIÓN PARA SUGERENCIAS - CAMBIADO A "Sugerencia de pedidos"
    elif st.session_state.pagina == "Sugerencia de pedidos":
        try:
            import sugerencias  # ← CAMBIADO
            sugerencias.main()  # ← CAMBIADO
        except ImportError:
            st.error("Página 'Sugerencias' no encontrada. Verifica que sugerencias.py exista en la raíz.")
        except Exception as e:
            st.error(f"Error al cargar sugerencias: {str(e)}")

# Marca visual para saber que el orquestador está cargado
# st.markdown("<div style='margin-top:30px;'></div>", unsafe_allow_html=True)
# st.write("ORQUESTADOR_CARGADO = True")
