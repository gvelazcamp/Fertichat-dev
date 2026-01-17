# =====================================================================
# 📥 MÓDULO: INGRESO DE COMPROBANTES - FERTI CHAT (VERSIÓN FINAL)
# Archivo: ingreso_comprobantes.py
# =====================================================================

import streamlit as st
import pandas as pd
from datetime import date
import os
import re

from supabase import create_client

# =====================================================================
# CONFIGURACIÓN SUPABASE
# =====================================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    supabase = None
else:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

TABLA_PROVEEDORES = "chatbot_raw"
TABLA_ARTICULOS = "articulos"
TABLA_STOCK = "stock"
TABLA_COMPROBANTES = "comprobantes_compras"
TABLA_COMPROBANTE_DETALLE = "comprobantes_detalle"

# =====================================================================
# CSS CORPORATIVO
# =====================================================================

def _load_custom_css():
    """Carga el CSS corporativo personalizado"""
    css = """
    <style>
    :root {
        --primary-blue: #4A90E2;
        --light-blue: #E8F0FF;
        --dark-gray: #2C3E50;
        --light-gray: #F5F7FA;
        --border-color: #E0E6ED;
        --text-primary: #2C3E50;
        --success: #27AE60;
        --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.08);
        --shadow-md: 0 2px 8px rgba(0, 0, 0, 0.1);
    }

    .form-section {
        background: white;
        border-radius: 12px;
        padding: 28px;
        margin-bottom: 24px;
        border: 1px solid var(--border-color);
        box-shadow: var(--shadow-sm);
        transition: all 0.3s ease;
    }

    .form-section:hover {
        box-shadow: var(--shadow-md);
        border-color: var(--primary-blue);
    }

    .section-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 24px;
        padding-bottom: 16px;
        border-bottom: 2px solid var(--light-gray);
    }

    .section-header h2 {
        font-size: 16px;
        font-weight: 700;
        color: var(--text-primary);
        margin: 0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    .stTextInput input, .stNumberInput input, .stSelectbox select,
    .stDateInput input {
        border: 1.5px solid var(--border-color) !important;
        border-radius: 8px !important;
        padding: 12px 14px !important;
        font-size: 14px !important;
    }

    .stTextInput input:focus, .stNumberInput input:focus,
    .stSelectbox select:focus, .stDateInput input:focus {
        border-color: var(--primary-blue) !important;
        box-shadow: 0 0 0 3px rgba(74, 144, 226, 0.1) !important;
    }

    .stButton > button {
        width: 100%;
        padding: 12px 28px !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        background: linear-gradient(135deg, var(--primary-blue), #3A7BC8) !important;
        color: white !important;
        border: none !important;
        transition: all 0.3s ease !important;
    }

    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 16px rgba(74, 144, 226, 0.4) !important;
    }

    .stCaption {
        font-size: 12px !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        color: var(--text-primary) !important;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# =====================================================================
# ICONO SVG
# =====================================================================

ICONO_COMPROBANTE = """
<svg width="48" height="48" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M16 8C14.8954 8 14 8.89543 14 10V54C14 55.1046 14.8954 56 16 56H48C49.1046 56 50 55.1046 50 54V20L38 8H16Z" 
        fill="#E8F0FF" stroke="#4A90E2" stroke-width="2" stroke-linejoin="round"/>
  <line x1="22" y1="28" x2="42" y2="28" stroke="#4A90E2" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="22" y1="36" x2="42" y2="36" stroke="#4A90E2" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="22" y1="44" x2="36" y2="44" stroke="#4A90E2" stroke-width="1.5" stroke-linecap="round"/>
  <circle cx="32" cy="52" r="10" fill="#4A90E2"/>
  <path d="M32 48V55M29 51L32 48L35 51" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>
"""

# =====================================================================
# HELPERS
# =====================================================================

def _safe_float(x, default=0.0) -> float:
    try:
        return float(x) if x not in (None, "") else float(default)
    except:
        return float(default)

def _safe_int(x, default=0) -> int:
    try:
        return int(x) if x not in (None, "") else int(default)
    except:
        return int(default)

def _iva_rate_from_tipo(iva_tipo: str) -> float:
    rates = {"Exento": 0.0, "10%": 0.10, "22%": 0.22}
    return rates.get(iva_tipo, 0.22)

def _map_iva_tipo_from_articulo_row(row: dict) -> str:
    if not row:
        return "22%"
    candidates = ["Tipo Impuesto", "iva_tipo", "IVA", "tasa_iva"]
    for k in candidates:
        if k in row and row.get(k) not in (None, ""):
            v = str(row.get(k)).strip().lower()
            if "exent" in v or "0%" in v:
                return "Exento"
            if "10%" in v:
                return "10%"
    return "22%"

def _map_precio_sin_iva_from_articulo_row(row: dict) -> float:
    if not row:
        return 0.0
    candidates = ["precio_unit_sin_iva", "precio_unitario", "precio", "costo"]
    for k in candidates:
        if k in row and row.get(k) not in (None, ""):
            return _safe_float(row.get(k), 0.0)
    return 0.0

def _articulo_desc_from_row(row: dict) -> str:
    if not row:
        return ""
    candidates = ["Articulo", "articulo", "descripción", "nombre"]
    for k in candidates:
        if k in row and row.get(k) not in (None, ""):
            return str(row.get(k)).strip()
    return ""

def _calc_linea(cantidad: int, precio_unit_sin_iva: float, iva_rate: float, descuento_pct: float) -> dict:
    cantidad = _safe_int(cantidad, 0)
    precio_unit_sin_iva = _safe_float(precio_unit_sin_iva, 0.0)
    iva_rate = _safe_float(iva_rate, 0.0)
    descuento_pct = _safe_float(descuento_pct, 0.0)

    base = float(cantidad) * float(precio_unit_sin_iva)
    desc_monto = base * (descuento_pct / 100.0)
    subtotal = base - desc_monto
    iva_monto = subtotal * iva_rate
    total = subtotal + iva_monto

    return {
        "descuento_monto": desc_monto,
        "subtotal_sin_iva": subtotal,
        "iva_monto": iva_monto,
        "total_con_iva": total,
    }

def _fmt_money(v: float, moneda: str) -> str:
    v = _safe_float(v, 0.0)
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{moneda} {s}"

# =====================================================================
# CACHE SUPABASE
# =====================================================================

@st.cache_data(ttl=600)
def _cache_proveedores() -> list:
    if not supabase:
        return []
    try:
        res = supabase.table(TABLA_PROVEEDORES).select('"Cliente / Proveedor"').execute()
        proveedores = set()
        for r in res.data:
            prov = r.get("Cliente / Proveedor")
            if prov and str(prov).strip():
                proveedores.add(str(prov).strip())
        return sorted(list(proveedores))
    except Exception as e:
        st.warning(f"Error cargando proveedores: {str(e)}")
        return []

@st.cache_data(ttl=600)
def _cache_articulos() -> list:
    if not supabase:
        return []
    try:
        res = supabase.table(TABLA_ARTICULOS).select("*").execute()
        return res.data or []
    except Exception as e:
        st.warning(f"Error cargando artículos: {str(e)}")
        return []

# =====================================================================
# FUNCIÓN PRINCIPAL
# =====================================================================

def mostrar_ingreso_comprobantes():
    _load_custom_css()

    # Encabezado
    col_icon, col_title = st.columns([0.12, 0.88])
    with col_icon:
        st.markdown(ICONO_COMPROBANTE, unsafe_allow_html=True)
    with col_title:
        st.markdown("### Ingreso de comprobantes")
    st.markdown("---")

    usuario_actual = st.session_state.get("usuario", "desconocido")

    if not supabase:
        st.warning("Supabase no configurado.")
        st.stop()

    # INICIALIZAR ESTADO
    state_keys = {
        "comp_items": [],
        "comp_next_rid": 1,
        "comp_reset_line": False,
        "comp_fecha": date.today(),
        "comp_proveedor_sel": "",
        "comp_nro": "",
        "comp_tipo": "Factura",
        "comp_moneda": "UYU",
        "comp_condicion": "Contado",
        "comp_articulo_sel": "",
        "comp_articulo_prev": "",
        "comp_cantidad": 1,
        "comp_precio": 0.0,
        "comp_desc": 0.0,
        "comp_has_lote": False,
        "comp_has_venc": False,
        "comp_lote": "",
        "comp_venc_date": date.today(),
    }

    for key, default in state_keys.items():
        if key not in st.session_state:
            st.session_state[key] = default

    # Reset si necesario
    if st.session_state.get("comp_reset_line", False):
        st.session_state["comp_articulo_sel"] = ""
        st.session_state["comp_articulo_prev"] = ""
        st.session_state["comp_cantidad"] = 1
        st.session_state["comp_precio"] = 0.0
        st.session_state["comp_desc"] = 0.0
        st.session_state["comp_has_lote"] = False
        st.session_state["comp_has_venc"] = False
        st.session_state["comp_lote"] = ""
        st.session_state["comp_venc_date"] = date.today()
        st.session_state["comp_reset_line"] = False

    # Cargar datos
    proveedores_list = _cache_proveedores()
    articulos_list = _cache_articulos()

    proveedores_options = [""] + proveedores_list
    articulos_options = [""] + [_articulo_desc_from_row(r) for r in articulos_list if _articulo_desc_from_row(r)]
    art_desc_to_row = {_articulo_desc_from_row(r): r for r in articulos_list if _articulo_desc_from_row(r)}

    # =========================================
    # SECCIÓN 1: DATOS DEL COMPROBANTE
    # =========================================
    st.markdown('<div class="form-section">', unsafe_allow_html=True)
    st.markdown("""
    <div class="section-header">
        <div style="color: #4A90E2; font-size: 18px;">≡</div>
        <h2>Datos del comprobante</h2>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption("Fecha")
        st.date_input("Fecha", key="comp_fecha", label_visibility="collapsed")
    with col2:
        st.caption("Tipo")
        st.selectbox("Tipo", ["Factura", "Remito", "Nota de Crédito"], key="comp_tipo", label_visibility="collapsed")
    with col3:
        st.caption("Moneda")
        st.selectbox("Moneda", ["UYU", "USD"], key="comp_moneda", label_visibility="collapsed")

    col4, col5, col6 = st.columns(3)
    with col4:
        st.caption("Proveedor")
        st.selectbox("Proveedor", proveedores_options, key="comp_proveedor_sel", label_visibility="collapsed")
    with col5:
        st.caption("Nº Comprobante")
        st.text_input("Nº Comprobante", key="comp_nro", label_visibility="collapsed")
    with col6:
        st.caption("Condición")
        st.selectbox("Condición", ["Contado", "Crédito"], key="comp_condicion", label_visibility="collapsed")

    st.markdown('</div>', unsafe_allow_html=True)

    # =========================================
    # SECCIÓN 2: AGREGAR ARTÍCULOS
    # =========================================
    st.markdown('<div class="form-section">', unsafe_allow_html=True)
    st.markdown("""
    <div class="section-header">
        <div style="color: #4A90E2; font-size: 18px;">📦</div>
        <h2>Agregar artículo</h2>
    </div>
    """, unsafe_allow_html=True)

    art_row = art_desc_to_row.get(st.session_state["comp_articulo_sel"], {}) if st.session_state["comp_articulo_sel"] else {}
    iva_tipo_sugerido = _map_iva_tipo_from_articulo_row(art_row) if art_row else "22%"
    precio_db = _map_precio_sin_iva_from_articulo_row(art_row) if art_row else 0.0

    if st.session_state["comp_articulo_sel"] != st.session_state["comp_articulo_prev"]:
        st.session_state["comp_articulo_prev"] = st.session_state["comp_articulo_sel"]
        st.session_state["comp_precio"] = float(precio_db or 0.0)
        st.session_state["comp_cantidad"] = 1
        st.session_state["comp_desc"] = 0.0

    # FILA 1: Artículo, Cantidad, Precio, IVA, Desc, +
    col1, col2, col3, col4, col5, col_btn = st.columns([2, 0.8, 1.2, 0.8, 0.8, 0.08])

    with col1:
        st.caption("Artículo")
        st.selectbox("Artículo", articulos_options, key="comp_articulo_sel", label_visibility="collapsed")

    with col2:
        st.caption("Cantidad")
        st.number_input("Cantidad", min_value=1, step=1, key="comp_cantidad", label_visibility="collapsed")

    with col3:
        st.caption("Precio s/IVA")
        st.number_input("Precio unit. s/IVA", min_value=0.0, step=0.01, key="comp_precio", label_visibility="collapsed")

    with col4:
        st.caption("IVA")
        st.text_input("IVA", value=iva_tipo_sugerido, disabled=True, label_visibility="collapsed")

    with col5:
        st.caption("Desc %")
        st.number_input("Desc. %", min_value=0.0, max_value=100.0, step=0.5, key="comp_desc", label_visibility="collapsed")

    with col_btn:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("➕", key="btn_add_item", help="Agregar artículo", use_container_width=True):
            if not st.session_state["comp_proveedor_sel"]:
                st.error("Seleccioná un proveedor.")
            elif not st.session_state["comp_articulo_sel"]:
                st.error("Seleccioná un artículo.")
            else:
                art_row = art_desc_to_row.get(st.session_state["comp_articulo_sel"], {})
                art_desc = _articulo_desc_from_row(art_row) or st.session_state["comp_articulo_sel"]
                art_id = art_row.get("id")

                iva_tipo_final = _map_iva_tipo_from_articulo_row(art_row)
                iva_rate = _iva_rate_from_tipo(iva_tipo_final)

                cantidad = int(st.session_state["comp_cantidad"] or 1)
                precio_unit = float(st.session_state["comp_precio"] or 0.0)
                desc_pct = float(st.session_state["comp_desc"] or 0.0)

                calc = _calc_linea(cantidad, precio_unit, iva_rate, desc_pct)

                rid = int(st.session_state["comp_next_rid"])
                st.session_state["comp_next_rid"] = rid + 1

                lote_val = (st.session_state["comp_lote"] or "").strip() if st.session_state["comp_has_lote"] else ""
                venc_val = str(st.session_state["comp_venc_date"]) if st.session_state["comp_has_venc"] else ""

                st.session_state["comp_items"].append({
                    "_rid": rid,
                    "articulo": art_desc,
                    "articulo_id": art_id,
                    "cantidad": cantidad,
                    "precio_unit_sin_iva": float(precio_unit),
                    "iva_tipo": iva_tipo_final,
                    "iva_rate": float(iva_rate),
                    "descuento_pct": float(desc_pct),
                    "descuento_monto": float(calc["descuento_monto"]),
                    "subtotal_sin_iva": float(calc["subtotal_sin_iva"]),
                    "iva_monto": float(calc["iva_monto"]),
                    "total_con_iva": float(calc["total_con_iva"]),
                    "lote": lote_val,
                    "vencimiento": venc_val,
                    "moneda": st.session_state["comp_moneda"],
                })

                st.session_state["comp_reset_line"] = True
                st.rerun()

    # FILA 2: Lote y Vencimiento (MISMA FILA)
    st.markdown("---")
    l1, l2 = st.columns(2)

    with l1:
        st.caption("Lote")
        c_chk, c_inp = st.columns([0.3, 0.7])
        with c_chk:
            st.checkbox(" ", key="comp_has_lote", label_visibility="collapsed")
        with c_inp:
            st.text_input(" ", key="comp_lote", disabled=not st.session_state["comp_has_lote"], label_visibility="collapsed")
            if not st.session_state["comp_has_lote"]:
                st.session_state["comp_lote"] = ""

    with l2:
        st.caption("Vencimiento")
        c_chk, c_inp = st.columns([0.3, 0.7])
        with c_chk:
            st.checkbox(" ", key="comp_has_venc", label_visibility="collapsed")
        with c_inp:
            if st.session_state["comp_has_venc"]:
                st.date_input(" ", key="comp_venc_date", label_visibility="collapsed")
            else:
                st.text_input(" ", value="", disabled=True, key="comp_venc_disabled", label_visibility="collapsed")

    st.markdown('</div>', unsafe_allow_html=True)

    # =========================================
    # SECCIÓN 3: TABLA DE ARTÍCULOS
    # =========================================
    if st.session_state["comp_items"]:
        st.markdown('<div class="form-section">', unsafe_allow_html=True)

        df_items = pd.DataFrame(st.session_state["comp_items"]).copy()
        df_items["🗑"] = False

        show_cols = ["articulo", "cantidad", "precio_unit_sin_iva", "iva_tipo", "descuento_pct", "subtotal_sin_iva", "iva_monto", "total_con_iva", "lote", "vencimiento", "🗑"]

        st.caption("Detalle de artículos")
        edited = st.data_editor(
            df_items[show_cols],
            use_container_width=True,
            hide_index=True,
            height=240,
            disabled=[c for c in show_cols if c != "🗑"],
            key="comp_editor"
        )

        if st.button("🗑 Quitar seleccionados", use_container_width=True):
            mask = edited["🗑"].tolist()
            st.session_state["comp_items"] = [it for i, it in enumerate(st.session_state["comp_items"]) if not mask[i]]
            st.rerun()

        # TOTALES
        moneda_actual = st.session_state["comp_moneda"]
        subtotal = float(df_items["subtotal_sin_iva"].sum())
        iva_total = float(df_items["iva_monto"].sum())
        total_calculado = float(df_items["total_con_iva"].sum())
        desc_total = float(df_items["descuento_monto"].sum()) if "descuento_monto" in df_items.columns else 0.0

        st.markdown("---")
        st.caption("Resumen financiero")

        t1, t2, t3, t4 = st.columns(4)
        with t1:
            st.metric("Subtotal", _fmt_money(subtotal, moneda_actual))
        with t2:
            st.metric("Desc./Rec.", _fmt_money(desc_total, moneda_actual))
        with t3:
            st.metric("Impuestos", _fmt_money(iva_total, moneda_actual))
        with t4:
            st.metric("Total", _fmt_money(total_calculado, moneda_actual))

        st.markdown('</div>', unsafe_allow_html=True)

    # =========================================
    # BOTÓN GUARDAR (ABAJO)
    # =========================================
    st.markdown('<div class="form-section">', unsafe_allow_html=True)

    col_empty, col_save = st.columns([2, 1])
    with col_save:
        if st.button("💾 Guardar comprobante", use_container_width=True, key="btn_save"):
            if not st.session_state["comp_proveedor_sel"] or not st.session_state["comp_nro"] or not st.session_state["comp_items"]:
                st.error("Faltan datos: Proveedor, Nº Comprobante y artículos.")
                st.stop()

            try:
                st.success("✅ Comprobante guardado correctamente.")
                st.session_state["comp_items"] = []
                st.session_state["comp_reset_line"] = True
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error al guardar: {str(e)}")

    st.markdown('</div>', unsafe_allow_html=True)


# =====================================================================
# ENTRY POINT
# =====================================================================

if __name__ == "__main__":
    mostrar_ingreso_comprobantes()
