import streamlit as st

st.set_page_config(
    page_title="FertiChat",
    page_icon="🦋",
    layout="wide",
    initial_sidebar_state="auto",
)

from ui_css import CSS_GLOBAL
from login_page import require_auth, get_current_user, logout

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

# NUEVOS IMPORTS PARA SOPORTE DE COMPRAS
from ia_interpretador import interpretar_pregunta
from sql_facturas import get_facturas_proveedor as get_facturas_proveedor_detalle
from sql_compras import (
    get_compras_proveedor_anio,
    get_detalle_compras_proveedor_mes,
    get_compras_multiples,
    get_compras_anio,
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
            help="Cambia la vista entre desktop and mobile"
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
            limite = params.get("limite", 5000)

            df = get_compras_anio(anio, limite)

            if df is None or df.empty:
                return f"⚠️ No se encontraron compras en {anio}.", None, None

            return (
                f"🛒 Todas las compras en {anio} ({len(df)} registros):",
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
# INICIALIZACIÓN
# =========================
init_db()
user = get_current_user() or {}

if "radio_menu" not in st.session_state:
    st.session_state["radio_menu"] = "🏠 Inicio"

# Forzar flag del orquestador
st.session_state["ORQUESTADOR_CARGADO"] = True

# Reaplicar CSS (por compatibilidad con versiones anteriores)
st.markdown(f"<style>{CSS_GLOBAL}</style>", unsafe_allow_html=True)

# =========================
# INICIALIZAR DETECCIÓN DE DISPOSITIVO
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
    _target = None
    for _opt in MENU_OPTIONS:
        if "compras" in (_opt or "").lower():
            _target = _opt
            break

    if _target:
        st.session_state["radio_menu"] = _target

    _clear_qp()
    st.rerun()

elif _go == "buscador":
    st.session_state["radio_menu"] = "🔎 Buscador IA"
    _clear_qp()
    st.rerun()

elif _go == "stock":
    st.session_state["radio_menu"] = "📦 Stock IA"
    _clear_qp()
    st.rerun()

elif _go == "dashboard":
    st.session_state["radio_menu"] = "📊 Dashboard"
    _clear_qp()
    st.rerun()

elif _go == "pedidos":
    st.session_state["radio_menu"] = "📄 Pedidos internos"
    _clear_qp()
    st.rerun()

elif _go == "baja":
    st.session_state["radio_menu"] = "🧾 Baja de stock"
    _clear_qp()
    st.rerun()

elif _go == "ordenes":
    st.session_state["radio_menu"] = "📦 Órdenes de compra"
    _clear_qp()
    st.rerun()

elif _go == "indicadores":
    st.session_state["radio_menu"] = "📈 Indicadores (Power BI)"
    _clear_qp()
    st.rerun()

# Desde campana (ir_notif=1)
try:
    if st.query_params.get("ir_notif") == "1":
        st.session_state["radio_menu"] = "📄 Pedidos internos"
        _clear_qp()
        st.rerun()
except Exception:
    pass

# =========================
# SIDEBAR
# =========================
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
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #94a3b8;
        padding: 8px 16px;
        margin: 16px 0 4px 0;
        display: block !important;
        width: 100%;
    }
    
    /* Ocultar "Ir a:" - TODOS los selectores posibles */
    section[data-testid="stSidebar"] .stRadio > label,
    section[data-testid="stSidebar"] .stRadio > div > label:first-child,
    section[data-testid="stSidebar"] div[role="radiogroup"] > label {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* OCULTAR círculos A LA FUERZA */
    section[data-testid="stSidebar"] input[type="radio"],
    section[data-testid="stSidebar"] div[role="radiogroup"] input[type="radio"],
    section[data-testid="stSidebar"] .stRadio input {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        width: 0 !important;
        height: 0 !important;
        position: absolute !important;
        left: -9999px !important;
    }
    
    /* Contenedor más compacto */
    section[data-testid="stSidebar"] .stRadio > div,
    section[data-testid="stSidebar"] div[role="radiogroup"] {
        gap: 0 !important;
        display: flex !important;
        flex-direction: column !important;
    }
    
    /* Labels MÁS COMPACTOS */
    section[data-testid="stSidebar"] .stRadio label,
    section[data-testid="stSidebar"] div[role="radiogroup"] label {
        padding: 6px 16px 6px 32px !important;
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
        min-height: 32px !important;
        line-height: 1.2 !important;
    }
    
    /* Flechita SVG azul */
    section[data-testid="stSidebar"] .stRadio label::before,
    section[data-testid="stSidebar"] div[role="radiogroup"] label::before {
        content: '' !important;
        position: absolute !important;
        left: 12px !important;
        top: 50% !important;
        transform: translateY(-50%) !important;
        width: 14px !important;
        height: 14px !important;
        background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="%233b82f6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>') !important;
        background-repeat: no-repeat !important;
        background-position: center !important;
        background-size: 14px 14px !important;
    }
    
    /* Flechita más gruesa cuando está seleccionado */
    section[data-testid="stSidebar"] .stRadio input:checked + div label::before,
    section[data-testid="stSidebar"] div[role="radiogroup"] input:checked + div label::before {
        background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="%233b82f6" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>') !important;
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
    st.markdown('<div class="fc-section-header">PRINCIPAL</div>', unsafe_allow_html=True)
    
    st.radio("Ir a:", MENU_OPTIONS, key="radio_menu", label_visibility="collapsed")
    
    st.components.v1.html("""
    <script>
    (function() {
        const interval = setInterval(() => {
            const labels = parent.document.querySelectorAll('section[data-testid="stSidebar"] .stRadio label p');
            if (labels.length > 0) {
                labels.forEach(label => {
                    label.textContent = label.textContent.replace(/[\\u{1F000}-\\u{1F9FF}\\u{2600}-\\u{26FF}\\u{2700}-\\u{27BF}]/gu, '').trim();
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
# ROUTER PRINCIPAL
# =========================
menu_actual = st.session_state["radio_menu"]

if menu_actual == "🏠 Inicio":
    mostrar_inicio()

elif "Chat (Chainlit)" in menu_actual:
    mostrar_chat_chainlit()

elif menu_actual == "🛒 Compras IA":
    mostrar_resumen_compras_rotativo()
    Compras_IA()

    # Panel de debug general (última consulta)
    if st.session_state.get("DEBUG_SQL", False):
        with st.expander("🛠 Debug (última consulta)", expanded=True):
            st.subheader("Interpretación")
            st.json(st.session_state.get("DBG_INT_LAST", {}))

            st.subheader("SQL ejecutado")
            st.write("Origen:", st.session_state.get("DBG_SQL_LAST_TAG"))
            st.write("Params:", st.session_state.get("DBG_SQL_LAST_PARAMS", []))

            st.subheader("Resultado")
            st.write("Filas:", st.session_state.get("DBG_SQL_ROWS"))
            st.write("Columnas:", st.session_state.get("DBG_SQL_COLS", []))

elif menu_actual == "🔍 Debug SQL factura":
    mostrar_debug_sql_factura()

elif menu_actual == "📦 Stock IA":
    mostrar_resumen_stock_rotativo(dias_vencer=30)  # Cambiado a 30 días
    mostrar_stock_ia()

elif menu_actual == "🔎 Buscador IA":
    mostrar_buscador_ia()

elif menu_actual == "📥 Ingreso de comprobantes":
    mostrar_ingreso_comprobantes()

elif menu_actual == "📊 Dashboard":
    mostrar_dashboard()

elif menu_actual == "📄 Pedidos internos":
    mostrar_pedidos_internos()

elif menu_actual == "🧾 Baja de stock":
    mostrar_baja_stock()

elif menu_actual == "📈 Indicadores (Power BI)":
    mostrar_indicadores_ia()

elif menu_actual == "📦 Órdenes de compra":
    mostrar_ordenes_compra()

elif menu_actual == "📒 Ficha de stock":
    mostrar_ficha_stock()

elif menu_actual == "📚 Artículos":
    mostrar_articulos()

elif menu_actual == "���� Depósitos":
    mostrar_depositos()

elif menu_actual == "🧩 Familias":
    mostrar_familias()

elif menu_actual == "📑 Comprobantes":
    mostrar_menu_comprobantes()

# Marca visual para saber que el orquestador está cargado
# st.markdown("<div style='margin-top:30px;'></div>", unsafe_allow_html=True)
# st.write("ORQUESTADOR_CARGADO = True")
