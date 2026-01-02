# =========================
# MAIN.PY - PC SIDEBAR NORMAL / MÓVIL: ☰ FIJO + CIERRE TOCANDO AFUERA
# =========================

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime

st.set_page_config(
    page_title="FertiChat",
    page_icon="🦋",
    layout="wide",
    initial_sidebar_state="auto"  # ✅ PC abierto / móvil colapsado (nativo)
)

# =========================
# IMPORTS
# =========================
from config import MENU_OPTIONS, DEBUG_MODE
from auth import init_db
from login_page import require_auth, get_current_user, logout
from pedidos import mostrar_pedidos_internos, contar_notificaciones_no_leidas
from bajastock import mostrar_baja_stock
from ordenes_compra import mostrar_ordenes_compra
from ui_compras import Compras_IA
from ui_buscador import mostrar_buscador_ia
from ui_stock import mostrar_stock_ia, mostrar_resumen_stock_rotativo
from ui_dashboard import mostrar_dashboard, mostrar_indicadores_ia, mostrar_resumen_compras_rotativo
from ingreso_comprobantes import mostrar_ingreso_comprobantes
from ui_inicio import mostrar_inicio
from ficha_stock import mostrar_ficha_stock
from articulos import mostrar_articulos
from depositos import mostrar_depositos
from familias import mostrar_familias

# =========================
# INICIALIZACIÓN
# =========================
init_db()
require_auth()

user = get_current_user() or {}

if "radio_menu" not in st.session_state:
    st.session_state["radio_menu"] = "🏠 Inicio"


# =========================
# CSS
# =========================
st.markdown(r"""
<style>
/* Ocultar UI de Streamlit */
div.stAppToolbar, div[data-testid="stToolbar"], div[data-testid="stToolbarActions"],
div[data-testid="stDecoration"], #MainMenu, footer {
  display: none !important;
}
/* NO colapsar el header a height:0 porque puede ocultar el control nativo */
header[data-testid="stHeader"] { background: transparent !important; }

/* Theme general */
:root {
    --fc-bg-1: #f6f4ef; --fc-bg-2: #f3f6fb;
    --fc-primary: #0b3b60; --fc-accent: #f59e0b;
}

html, body { font-family: Inter, system-ui, sans-serif; color: #0f172a; }
[data-testid="stAppViewContainer"] { background: linear-gradient(135deg, var(--fc-bg-1), var(--fc-bg-2)); }
.block-container { max-width: 1240px; padding-top: 1.25rem; padding-bottom: 2.25rem; }

/* Sidebar look */
section[data-testid="stSidebar"] { border-right: 1px solid rgba(15, 23, 42, 0.08); }
section[data-testid="stSidebar"] > div {
    background: rgba(255,255,255,0.70);
    backdrop-filter: blur(8px);
}

div[data-testid="stSidebar"] div[role="radiogroup"] label {
    border-radius: 12px; padding: 8px 10px; margin: 3px 0; border: 1px solid transparent;
}
div[data-testid="stSidebar"] div[role="radiogroup"] label:hover { background: rgba(37,99,235,0.06); }
div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
    background: rgba(245,158,11,0.10); border: 1px solid rgba(245,158,11,0.18);
}

/* Header móvil (visual) */
#mobile-header { display: none; }

/* ---------------------------------------------------------
   DESKTOP: SIN botón nativo ☰ (sidebar tradicional)
--------------------------------------------------------- */
@media (min-width: 768px) {
  div[data-testid="collapsedControl"] { display: none !important; }
  [data-testid="baseButton-header"],
  button[data-testid="stSidebarCollapseButton"],
  button[data-testid="stSidebarExpandButton"],
  button[title="Close sidebar"],
  button[title="Open sidebar"] {
    display: none !important;
  }
}

/* ---------------------------------------------------------
   MÓVIL: header fijo + sidebar arriba del overlay + ocultar flecha gris
--------------------------------------------------------- */
@media (max-width: 767px) {
  .block-container { padding-top: 70px !important; }

  #mobile-header {
    display: flex !important;
    position: fixed;
    top: 0; left: 0; right: 0;
    height: 60px;
    background: #0b3b60;
    z-index: 999998;
    align-items: center;
    padding: 0 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  }
  #mobile-header .logo {
    color: white;
    font-size: 20px;
    font-weight: 800;
    margin-left: 12px;
  }

  /* Sidebar por arriba del overlay */
  section[data-testid="stSidebar"] {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    height: 100vh !important;
    z-index: 999999 !important;
  }
  section[data-testid="stSidebar"] > div {
    height: 100% !important;
    overflow-y: auto !important;
  }

  /* Ocultar flecha gris + texto "Cerrar menú" */
  [data-testid="baseButton-header"] { display: none !important; }
}
</style>
""", unsafe_allow_html=True)


# =========================
# HEADER MÓVIL (visual)
# =========================
st.markdown("""
<div id="mobile-header">
    <div class="logo">🦋 FertiChat</div>
</div>
""", unsafe_allow_html=True)


# =========================
# ☰ FIJO + OVERLAY (SOLO MÓVIL) - abre/cierra sidebar + cierra tocando afuera
# =========================
components.html(
    """
    <script>
    (function () {
      const doc = parent.document;
      const isMobile = parent.window.matchMedia("(max-width: 767px)").matches;

      const BTN_ID = "fc_mobile_hamburger_fixed";
      const OVERLAY_ID = "fc_sidebar_overlay_clickout";

      function qs(sel) { return doc.querySelector(sel); }

      function findOpenBtn() {
        return qs('div[data-testid="collapsedControl"] button')
            || qs('div[data-testid="collapsedControl"]')
            || qs('button[title="Open sidebar"]')
            || qs('button[data-testid="stSidebarExpandButton"]');
      }

      function findCloseBtn() {
        return qs('[data-testid="baseButton-header"]')
            || qs('button[title="Close sidebar"]')
            || qs('button[data-testid="stSidebarCollapseButton"]');
      }

      function sidebarIsOpen() {
        // Si existe botón de cerrar (aunque esté oculto), normalmente significa "open"
        const closeBtn = findCloseBtn();
        if (closeBtn) return true;

        // Fallback: si no hay closeBtn, asumimos "closed"
        return false;
      }

      function removeOverlay() {
        const ov = doc.getElementById(OVERLAY_ID);
        if (ov) ov.remove();
      }

      function ensureOverlay(show) {
        let ov = doc.getElementById(OVERLAY_ID);
        if (!show) { removeOverlay(); return; }

        if (!ov) {
          ov = doc.createElement("div");
          ov.id = OVERLAY_ID;
          ov.style.position = "fixed";
          ov.style.inset = "0";
          ov.style.width = "100vw";
          ov.style.height = "100vh";
          ov.style.background = "rgba(0,0,0,0.5)";
          ov.style.zIndex = "999998"; // debajo del sidebar (999999)
          ov.style.cursor = "pointer";

          ov.addEventListener("click", function () {
            const closeBtn = findCloseBtn();
            if (closeBtn) closeBtn.click();
            setTimeout(removeOverlay, 50);
          });

          doc.body.appendChild(ov);
        }
      }

      function toggleSidebar() {
        // Si está abierto: cerrar. Si está cerrado: abrir.
        const closeBtn = findCloseBtn();
        const openBtn = findOpenBtn();

        if (closeBtn) {
          closeBtn.click();
          setTimeout(removeOverlay, 80);
          return;
        }
        if (openBtn) {
          openBtn.click();
          // dar tiempo a que aparezca el sidebar antes de overlay
          setTimeout(function(){ ensureOverlay(true); }, 120);
        }
      }

      // Limpieza en desktop
      if (!isMobile) {
        const b = doc.getElementById(BTN_ID);
        if (b) b.remove();
        removeOverlay();
        return;
      }

      // Crear botón ☰ fijo si no existe
      if (!doc.getElementById(BTN_ID)) {
        const b = doc.createElement("button");
        b.id = BTN_ID;
        b.type = "button";
        b.textContent = "☰";

        b.style.position = "fixed";
        b.style.top = "12px";
        b.style.left = "12px";
        b.style.zIndex = "1000001";
        b.style.borderRadius = "12px";
        b.style.border = "1px solid rgba(255,255,255,0.35)";
        b.style.background = "rgba(11,59,96,0.92)";
        b.style.color = "#fff";
        b.style.fontSize = "18px";
        b.style.fontWeight = "800";
        b.style.padding = "10px 12px";
        b.style.lineHeight = "1";
        b.style.boxShadow = "0 6px 16px rgba(0,0,0,0.18)";

        b.addEventListener("click", toggleSidebar);
        doc.body.appendChild(b);
      }

      // Cada rerun: si está abierto, overlay; si está cerrado, sin overlay.
      // (No toca tu session_state, solo UI)
      setTimeout(function () {
        ensureOverlay(sidebarIsOpen());
      }, 80);

    })();
    </script>
    """,
    height=0,
    width=0,
)


# =========================
# TÍTULO Y CAMPANITA
# =========================
usuario_actual = user.get("usuario", user.get("email", ""))
cant_pendientes = 0
if usuario_actual:
    cant_pendientes = contar_notificaciones_no_leidas(usuario_actual)

col_logo, col_spacer, col_notif = st.columns([7, 2, 1])

with col_logo:
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 12px;">
            <div>
                <h1 style="margin: 0; font-size: 38px; font-weight: 900; color: #0f172a;">
                    FertiChat
                </h1>
                <p style="margin: 4px 0 0 0; font-size: 15px; color: #64748b;">
                    Sistema de Gestión de Compras
                </p>
            </div>
        </div>
    """, unsafe_allow_html=True)

with col_notif:
    if cant_pendientes > 0:
        if st.button(f"🔔 {cant_pendientes}", key="campanita_global"):
            st.session_state["radio_menu"] = "📄 Pedidos internos"
            st.rerun()
    else:
        st.markdown("<div style='text-align:right; font-size:26px;'>🔔</div>", unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)


# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.markdown(f"""
        <div style='
            background: rgba(255,255,255,0.85);
            padding: 16px;
            border-radius: 18px;
            margin-bottom: 14px;
            border: 1px solid rgba(15, 23, 42, 0.10);
            box-shadow: 0 10px 26px rgba(2, 6, 23, 0.06);
        '>
            <div style='display:flex; align-items:center; gap:10px; justify-content:center;'>
                <div style='font-size: 26px;'>🦋</div>
                <div style='font-size: 20px; font-weight: 800; color:#0f172a;'>FertiChat</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.text_input("Buscar...", key="sidebar_search", label_visibility="collapsed", placeholder="Buscar...")

    st.markdown(f"👤 **{user.get('nombre', 'Usuario')}**")
    if user.get('empresa'):
        st.markdown(f"🏢 {user.get('empresa')}")
    st.markdown(f"📧 _{user.get('Usuario', user.get('usuario', ''))}_")

    st.markdown("---")

    if st.button("🚪 Cerrar sesión", key="btn_logout_sidebar", use_container_width=True):
        logout()
        st.rerun()

    st.markdown("---")
    st.markdown("## 📌 Menú")

    st.radio("Ir a:", MENU_OPTIONS, key="radio_menu")


# =========================
# ROUTER
# =========================
menu_actual = st.session_state["radio_menu"]

if menu_actual == "🏠 Inicio":
    mostrar_inicio()
elif menu_actual == "🛒 Compras IA":
    mostrar_resumen_compras_rotativo()
    Compras_IA()
elif menu_actual == "📦 Stock IA":
    mostrar_resumen_stock_rotativo()
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
elif menu_actual == "🏬 Depósitos":
    mostrar_depositos()
elif menu_actual == "🧩 Familias":
    mostrar_familias()
