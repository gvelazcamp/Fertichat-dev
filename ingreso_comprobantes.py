# =====================================================================
# 📥 MÓDULO: INGRESO DE COMPROBANTES - FERTI CHAT (REDISEÑO v2)
# Archivo: ingreso_comprobantes_redesign.py
# FIXES: Línea blanca, proveedor gigante, vencimiento, session_state
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

# Tablas base (candidatas para autodetección)
TABLAS_CABECERA_CANDIDATAS = [
    "comprobantes_compras",
    "comprobantes",
    "comprobantes_compra",
    "comprobantes_cabecera",
]

TABLAS_DETALLE_CANDIDATAS = [
    "comprobantes_detalle",
    "comprobante_detalle",
    "comprobantes_items",
    "comprobantes_lineas",
]

TABLA_STOCK = "stock"
TABLA_PROVEEDORES = "chatbot_raw"  # Cambiado a chatbot_raw
TABLA_ARTICULOS = "articulos"

# =====================================================================
# CSS CORPORATIVO
# =====================================================================

def _load_custom_css():
    """Carga el CSS corporativo personalizado"""
    css = """
    <style>
    /* ===== ESTILOS GENERALES ===== */
    :root {
        --primary-blue: #4A90E2;
        --light-blue: #E8F0FF;
        --dark-gray: #2C3E50;
        --medium-gray: #5A6C7D;
        --light-gray: #F5F7FA;
        --border-color: #E0E6ED;
        --text-primary: #2C3E50;
        --text-secondary: #5A6C7D;
        --success: #27AE60;
        --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.08);
        --shadow-md: 0 2px 8px rgba(0, 0, 0, 0.1);
    }

    /* Secciones */
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

    /* Inputs */
    .stTextInput input, .stNumberInput input, .stSelectbox select,
    .stDateInput input {
        border: 1.5px solid var(--border-color) !important;
        border-radius: 8px !important;
        padding: 12px 14px !important;
        font-size: 14px !important;
        transition: all 0.3s ease !important;
    }

    .stTextInput input:focus, .stNumberInput input:focus,
    .stSelectbox select:focus, .stDateInput input:focus {
        border-color: var(--primary-blue) !important;
        box-shadow: 0 0 0 3px rgba(74, 144, 226, 0.1) !important;
    }

    /* Botones */
    .stButton > button {
        width: 100%;
        padding: 12px 28px !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
        transition: all 0.3s ease !important;
        border: none !important;
    }

    .stButton > button {
        background: linear-gradient(135deg, var(--primary-blue), #3A7BC8) !important;
        color: white !important;
        box-shadow: 0 2px 8px rgba(74, 144, 226, 0.3) !important;
    }

    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 16px rgba(74, 144, 226, 0.4) !important;
    }

    /* Data editor */
    .stDataFrame {
        border-radius: 8px !important;
        border: 1px solid var(--border-color) !important;
    }

    /* Métricas */
    .stMetric {
        background: white;
        padding: 16px;
        border-radius: 8px;
        border: 1px solid var(--border-color);
    }

    h1, h2, h3 {
        color: var(--dark-gray) !important;
    }

    .stCaption {
        font-size: 12px !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
        color: var(--text-primary) !important;
    }

    .stSuccess {
        background-color: rgba(39, 174, 96, 0.1) !important;
        border-color: var(--success) !important;
    }

    /* Responsive */
    @media (max-width: 768px) {
        .form-section {
            padding: 20px;
        }

        .stButton > button {
            padding: 10px 20px !important;
        }
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
# HELPERS (SIN CAMBIOS)
# =====================================================================

def _safe_float(x, default=0.0) -> float:
    try:
        if x is None or x == "":
            return float(default)
        return float(x)
    except Exception:
        return float(default)

def _safe_int(x, default=0) -> int:
    try:
        if x is None or x == "":
            return int(default)
        return int(x)
    except Exception:
        return int(default)

def _iva_rate_from_tipo(iva_tipo: str) -> float:
    if iva_tipo == "Exento":
        return 0.0
    if iva_tipo == "10%":
        return 0.10
    if iva_tipo == "22%":
        return 0.22
    return 0.0

def _map_iva_tipo_from_articulo_row(row: dict) -> str:
    if not row:
        return "22%"

    candidates = [
        "Tipo Impuesto", "tipo impuesto", "tipo_impuesto",
        "iva_tipo", "IVA", "iva", "tasa_iva", "Tasa IVA"
    ]

    val = None
    for k in candidates:
        if k in row and row.get(k) not in (None, ""):
            val = row.get(k)
            break

    if val is None:
        return "22%"

    if isinstance(val, (int, float)):
        f = _safe_float(val, 0.0)
        if abs(f - 0.0) < 1e-9:
            return "Exento"
        if abs(f - 0.10) < 1e-6:
            return "10%"
        return "22%"

    v = str(val).strip().lower()

    if "exent" in v or "exento" in v or "0%" in v:
        return "Exento"
    if "10%" in v or re.search(r"\b10\b", v):
        return "10%"
    if "22%" in v or re.search(r"\b22\b", v):
        return "22%"

    if re.match(r"^\s*1\s*[-]", v):
        return "Exento"

    return "22%"

def _map_precio_sin_iva_from_articulo_row(row: dict) -> float:
    if not row:
        return 0.0

    candidates = [
        "precio_unit_sin_iva", "precio_unitario_sin_iva", "precio_sin_iva",
        "precio_unitario", "precio",
        "costo", "costo_unitario"
    ]

    for k in candidates:
        if k in row and row.get(k) not in (None, ""):
            return _safe_float(row.get(k), 0.0)

    return 0.0

def _articulo_desc_from_row(row: dict) -> str:
    if not row:
        return ""
    candidates = ["descripción", "Descripción", "descripcion", "nombre", "articulo", "Artículo", "detalle", "Detalle"]
    for k in candidates:
        if k in row and row.get(k) not in (None, ""):
            return str(row.get(k)).strip()
    return ""

def _articulo_label(row: dict) -> str:
    desc = _articulo_desc_from_row(row) or ""
    rid = str(row.get("id", "") or "")
    rid8 = rid[:8] if rid else ""
    return f"{desc} [{rid8}]" if rid8 else desc

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
        # Intenta obtener primer registro para ver columnas
        res_test = supabase.table(TABLA_PROVEEDORES).select("*").limit(1).execute()
        if not res_test.data:
            return []
        
        # Busca columna que contenga "proveedor" o "cliente"
        columnas = list(res_test.data[0].keys())
        prov_col = None
        for col in columnas:
            if "proveedor" in col.lower() or "cliente" in col.lower():
                prov_col = col
                break
        
        if not prov_col:
            # Si no encuentra, intenta con el nombre original
            prov_col = "Cliente / Proveedor"
        
        # Trae datos de esa columna
        res = supabase.table(TABLA_PROVEEDORES).select(f'"{prov_col}"').execute()
        data = [str(r.get(prov_col)).strip() for r in res.data if r.get(prov_col)]
        return sorted(list(set(data)))
    except Exception as e:
        return []

@st.cache_data(ttl=600)
def _cache_articulos() -> list:
    if not supabase:
        return []

    out = []
    start = 0
    page = 1000
    max_rows = 50000

    while start < max_rows:
        end = start + page - 1
        res = (
            supabase.table(TABLA_ARTICULOS)
            .select("*")
            .range(start, end)
            .execute()
        )
        batch = res.data or []
        out.extend(batch)
        if len(batch) < page:
            break
        start += page

    return out

def _get_proveedor_options() -> tuple[list, dict]:
    data = _cache_proveedores()
    name_to_id = {}
    options = [""]
    for nombre in data:
        nombre = str(nombre).strip()
        if nombre:
            options.append(nombre)
            name_to_id[nombre] = None  # No hay id en chatbot_raw
    return options, name_to_id

def _get_articulo_options() -> tuple[list, dict]:
    data = _cache_articulos()
    label_to_row = {}
    options = [""]
    for r in data:
        label = _articulo_label(r)
        if label:
            options.append(label)
            label_to_row[label] = r
    return options, label_to_row

# =====================================================================
# RESOLVER TABLAS
# =====================================================================

def _pick_table_name(candidates: list[str]) -> str | None:
    if not supabase:
        return None

    for name in candidates:
        try:
            supabase.table(name).select("*").limit(1).execute()
            return name
        except Exception as e:
            s = str(e)
            if ("PGRST205" in s) or ("schema cache" in s) or ("Could not find the table" in s):
                continue
            return name

    return None

def _resolver_tablas_o_stop() -> tuple[str, str]:
    if "tabla_comp_cab" not in st.session_state:
        st.session_state["tabla_comp_cab"] = _pick_table_name(TABLAS_CABECERA_CANDIDATAS)

    if "tabla_comp_det" not in st.session_state:
        st.session_state["tabla_comp_det"] = _pick_table_name(TABLAS_DETALLE_CANDIDATAS)

    cab = st.session_state.get("tabla_comp_cab")
    det = st.session_state.get("tabla_comp_det")

    if not cab or not det:
        st.error("No existe la tabla de comprobantes en Supabase (PGRST205).")
        st.markdown("Creá estas tablas (nombres exactos) o cambiá las candidatas en el código:")
        st.code(
            """
-- CABECERA
create table if not exists public.comprobantes_compras (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz default now(),
  fecha date,
  proveedor text,
  proveedor_id uuid,
  tipo_comprobante text,
  nro_comprobante text,
  condicion_pago text,
  usuario text,
  moneda text,
  subtotal numeric,
  iva_total numeric,
  total numeric
);

-- DETALLE
create table if not exists public.comprobantes_detalle (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz default now(),
  comprobante_id uuid references public.comprobantes_compras(id) on delete cascade,
  articulo text,
  articulo_id uuid,
  cantidad integer,
  moneda text,
  precio_unit_sin_iva numeric,
  iva_tipo text,
  iva_rate numeric,
  descuento_pct numeric,
  descuento_monto numeric,
  subtotal_sin_iva numeric,
  iva_monto numeric,
  total_con_iva numeric,
  lote text,
  vencimiento date,
  usuario text
);
            """.strip(),
            language="sql"
        )
        st.stop()

    return cab, det

# =====================================================================
# STOCK
# =====================================================================

def _impactar_stock(articulo: str, cantidad: int) -> None:
    if not supabase:
        return

    articulo = (articulo or "").strip()
    if not articulo:
        return

    existe = supabase.table(TABLA_STOCK).select("id,cantidad").eq("articulo", articulo).execute()

    if existe.data:
        stock_id = existe.data[0]["id"]
        cant_actual = existe.data[0].get("cantidad", 0) or 0
        nueva_cant = int(cant_actual) + int(cantidad)
        supabase.table(TABLA_STOCK).update({"cantidad": nueva_cant}).eq("id", stock_id).execute()
    else:
        supabase.table(TABLA_STOCK).insert({"articulo": articulo, "cantidad": int(cantidad)}).execute()

# =====================================================================
# INSERTS
# =====================================================================

def _insert_cabecera(tabla_cab: str, cabecera: dict) -> dict:
    return supabase.table(tabla_cab).insert(cabecera).execute()

def _insert_detalle(tabla_det: str, detalle: dict) -> None:
    supabase.table(tabla_det).insert(detalle).execute()

# =====================================================================
# FUNCIÓN PRINCIPAL - REDISEÑADA v2 (FIXED)
# =====================================================================

def mostrar_ingreso_comprobantes():
    # Cargar CSS
    _load_custom_css()

    # Encabezado - SIN LÍNEA BLANCA
    col_icon, col_title = st.columns([0.12, 0.88])
    with col_icon:
        st.markdown(ICONO_COMPROBANTE, unsafe_allow_html=True)
    with col_title:
        st.markdown("### Ingreso de comprobantes")

    st.markdown("---")

    usuario_actual = st.session_state.get("usuario", st.session_state.get("user", "desconocido"))

    if not supabase:
        st.warning("Supabase no configurado.")
        st.stop()

    tabla_cab, tabla_det = _resolver_tablas_o_stop()

    # ===== INICIALIZAR ESTADO =====
    if "comp_items" not in st.session_state:
        st.session_state["comp_items"] = []
    
    if "comp_next_rid" not in st.session_state:
        st.session_state["comp_next_rid"] = 1
    
    if "comp_reset_line" not in st.session_state:
        st.session_state["comp_reset_line"] = False
    
    if "comp_fecha" not in st.session_state:
        st.session_state["comp_fecha"] = date.today()
    
    if "comp_proveedor_sel" not in st.session_state:
        st.session_state["comp_proveedor_sel"] = ""
    
    if "comp_nro" not in st.session_state:
        st.session_state["comp_nro"] = ""
    
    if "comp_tipo" not in st.session_state:
        st.session_state["comp_tipo"] = "Factura"
    
    if "comp_moneda" not in st.session_state:
        st.session_state["comp_moneda"] = "UYU"
    
    if "comp_condicion" not in st.session_state:
        st.session_state["comp_condicion"] = "Contado"
    
    if "comp_articulo_sel" not in st.session_state:
        st.session_state["comp_articulo_sel"] = ""
    
    if "comp_articulo_prev" not in st.session_state:
        st.session_state["comp_articulo_prev"] = ""
    
    if "comp_cantidad" not in st.session_state:
        st.session_state["comp_cantidad"] = 1
    
    if "comp_precio" not in st.session_state:
        st.session_state["comp_precio"] = 0.0
    
    if "comp_desc" not in st.session_state:
        st.session_state["comp_desc"] = 0.0
    
    if "comp_has_lote" not in st.session_state:
        st.session_state["comp_has_lote"] = False
    
    if "comp_has_venc" not in st.session_state:
        st.session_state["comp_has_venc"] = False
    
    if "comp_lote" not in st.session_state:
        st.session_state["comp_lote"] = ""
    
    if "comp_venc_date" not in st.session_state:
        st.session_state["comp_venc_date"] = date.today()

    # ===== RESET DESPUÉS DE INICIALIZAR =====
    if st.session_state.get("comp_reset_line", False):
        st.session_state["comp_articulo_sel"] = ""
        st.session_state["comp_articulo_prev"] = ""
        st.session_state["comp_cantidad"] = 1
        st.session_state["comp_precio"] = 0.0
        st.session_state["comp_desc"] = 0.0
        st.session_state["comp_has_lote"] = False
        st.session_state["comp_has_venc"] = False
        st.session_state["comp_reset_line"] = False

    proveedores_options, prov_name_to_id = _get_proveedor_options()
    articulos_options, art_label_to_row = _get_articulo_options()

    if st.session_state["comp_proveedor_sel"] not in proveedores_options:
        st.session_state["comp_proveedor_sel"] = ""
    if st.session_state["comp_articulo_sel"] not in articulos_options:
        st.session_state["comp_articulo_sel"] = ""

    # =========================================
    # SECCIÓN 1: DATOS DEL COMPROBANTE
    # =========================================

    st.markdown("""
    <div class="section-header">
        <div style="color: #4A90E2; font-size: 18px;">≡</div>
        <h2>Datos del comprobante</h2>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.date_input("Fecha", key="comp_fecha")

    with col2:
        st.selectbox("Tipo", ["Factura", "Remito", "Nota de Crédito"], key="comp_tipo")

    with col3:
        st.selectbox("Moneda", ["UYU", "USD"], key="comp_moneda")

    col4, col5, col6 = st.columns(3)

    with col4:
        st.selectbox("Proveedor", proveedores_options, key="comp_proveedor_sel")

    with col5:
        st.text_input("Nº Comprobante", key="comp_nro")

    with col6:
        st.selectbox("Condición", ["Contado", "Crédito"], key="comp_condicion")


    # =========================================
    # ARTÍCULOS - LAYOUT COMPACTO TIPO TABLA
    # =========================================

    st.markdown("---")
    st.caption("Agregar artículo")

    # Fila compacta: Artículo | Cantidad | Precio | IVA | Desc | Lote | Vencimiento | +
    art, cant, prec, iva, desc, lote, venc, btn = st.columns([2, 1, 1, 1, 1, 1.5, 1.5, 0.5])

    with art:
        st.selectbox("Artículo", articulos_options, key="comp_articulo_sel")

    with cant:
        st.number_input("Cant.", min_value=1, step=1, key="comp_cantidad")

    with prec:
        st.number_input("P.Unit.", min_value=0.0, step=0.01, key="comp_precio")

    with iva:
        art_row = art_label_to_row.get(st.session_state["comp_articulo_sel"], {}) if st.session_state["comp_articulo_sel"] else {}
        iva_tipo_sugerido = _map_iva_tipo_from_articulo_row(art_row) if art_row else "22%"
        st.text_input("IVA", value=iva_tipo_sugerido, disabled=True, key="comp_iva_display")

    with desc:
        st.number_input("Desc.%", min_value=0.0, max_value=100.0, step=0.5, key="comp_desc")

    with lote:
        c_chk, c_inp = st.columns([0.4, 0.6])
        with c_chk:
            st.checkbox("Lote", key="comp_has_lote")
        with c_inp:
            lote_value = "" if not st.session_state["comp_has_lote"] else st.session_state.get("comp_lote", "")
            st.text_input(" ", value=lote_value, key="comp_lote", disabled=not st.session_state["comp_has_lote"])

    with venc:
        c_chk, c_inp = st.columns([0.4, 0.6])
        with c_chk:
            st.checkbox("Venc.", key="comp_has_venc")
        with c_inp:
            if st.session_state["comp_has_venc"]:
                venc_value = st.session_state.get("comp_venc_date", date.today())
                st.date_input(" ", value=venc_value, key="comp_venc_date")
            else:
                st.text_input(" ", value="", disabled=True, key="comp_venc_disabled")

    with btn:
        col_p, col_m = st.columns(2)
        with col_p:
            if st.button("+", key="btn_add_art", help="Agregar"):
                if not st.session_state["comp_articulo_sel"]:
                    st.error("Seleccioná un artículo.")
                else:
                    art_row = art_label_to_row.get(st.session_state["comp_articulo_sel"], {})
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
        
        with col_m:
            if st.button("-", key="btn_remove_art", help="Quitar"):
                if st.session_state["comp_items"]:
                    st.session_state["comp_items"].pop()
                    st.rerun()

    # Autocargar precio/IVA al cambiar artículo
    if st.session_state["comp_articulo_sel"] != st.session_state["comp_articulo_prev"]:
        st.session_state["comp_articulo_prev"] = st.session_state["comp_articulo_sel"]
        precio_db = _map_precio_sin_iva_from_articulo_row(art_row) if art_row else 0.0
        st.session_state["comp_precio"] = float(precio_db or 0.0)
        st.session_state["comp_cantidad"] = 1
        st.session_state["comp_desc"] = 0.0
        st.session_state["comp_has_lote"] = False
        st.session_state["comp_has_venc"] = False
        st.session_state["comp_lote"] = ""
        st.session_state["comp_venc_date"] = date.today()

    # =========================================
    # SECCIÓN 3: TABLA DE ARTÍCULOS
    # =========================================
    if st.session_state["comp_items"]:

        df_items = pd.DataFrame(st.session_state["comp_items"]).copy()

        # Crear dataframe de display con columnas nuevas
        df_display = pd.DataFrame()
        df_display["CÓDIGO"] = df_items["articulo_id"].apply(lambda x: str(x)[:8] if x else "")
        df_display["UNIDAD"] = df_items["moneda"]
        df_display["CANTIDAD"] = df_items["cantidad"]
        df_display["CONCEPTO"] = df_items["articulo"]
        df_display["P.UNITARIO"] = df_items["precio_unit_sin_iva"]
        df_display["DESCUENTO"] = df_items["descuento_monto"]
        df_display["SUB-TOTAL"] = df_items["subtotal_sin_iva"]
        df_display["I.V.A."] = df_items["iva_monto"]
        df_display["IMPUESTOS"] = df_items["iva_monto"]
        df_display["TOTAL"] = df_items["total_con_iva"]
        df_display["CHECK"] = df_items["🗑"] if "🗑" in df_items.columns else False
        df_display["LOTE"] = df_items["lote"]
        df_display["VENCIMIENTO"] = df_items["vencimiento"]
        df_display["+"] = False  # Placeholder

        show_cols = [
            "CÓDIGO",
            "UNIDAD",
            "CANTIDAD",
            "CONCEPTO",
            "P.UNITARIO",
            "DESCUENTO",
            "SUB-TOTAL",
            "I.V.A.",
            "IMPUESTOS",
            "TOTAL",
            "CHECK",
            "LOTE",
            "VENCIMIENTO",
            "+"
        ]

        st.caption("Detalle de artículos")
        edited = st.data_editor(
            df_display[show_cols],
            use_container_width=True,
            hide_index=True,
            height=240,
            disabled=[c for c in show_cols if c != "CHECK"],
            key="comp_editor"
        )

        if st.button("🗑 Quitar seleccionados", use_container_width=True):
            # Obtener índices donde está marcado el checkbox
            mask = edited["CHECK"].tolist()
            st.session_state["comp_items"] = [it for i, it in enumerate(st.session_state["comp_items"]) if not mask[i]]
            st.rerun()

        # Métricas y guardar en la misma fila
        st.markdown("---")
        col_metrics, col_save = st.columns([3, 1])

        with col_metrics:
            st.caption("Resumen financiero")

            t1, t2, t3, t4 = st.columns(4)
            with t1:
                subtotal = float(df_items["subtotal_sin_iva"].sum())
                st.metric("Subtotal", _fmt_money(subtotal, st.session_state["comp_moneda"]))
            with t2:
                desc_total = float(df_items["descuento_monto"].sum()) if "descuento_monto" in df_items.columns else 0.0
                st.metric("Desc./Rec.", _fmt_money(desc_total, st.session_state["comp_moneda"]))
            with t3:
                iva_total = float(df_items["iva_monto"].sum())
                st.metric("Impuestos", _fmt_money(iva_total, st.session_state["comp_moneda"]))
            with t4:
                total_calculado = float(df_items["total_con_iva"].sum())
                st.metric("Total", _fmt_money(total_calculado, st.session_state["comp_moneda"]))

        with col_save:
            if st.button("💾 Guardar comprobante", use_container_width=True, key="btn_save"):
                if not st.session_state["comp_proveedor_sel"] or not st.session_state["comp_nro"] or not st.session_state["comp_items"]:
                    st.error("Faltan datos obligatorios (Proveedor, Nº Comprobante y al menos 1 artículo).")
                    st.stop()

                proveedor_nombre = str(st.session_state["comp_proveedor_sel"]).strip()
                proveedor_id = prov_name_to_id.get(proveedor_nombre)
                nro_norm = str(st.session_state["comp_nro"]).strip()

                try:
                    cabecera = {
                        "fecha": str(st.session_state["comp_fecha"]),
                        "proveedor": proveedor_nombre,
                        "proveedor_id": proveedor_id,
                        "tipo_comprobante": st.session_state["comp_tipo"],
                        "nro_comprobante": nro_norm,
                        "condicion_pago": st.session_state["comp_condicion"],
                        "usuario": str(usuario_actual),
                        "moneda": st.session_state["comp_moneda"],
                        "subtotal": subtotal,
                        "iva_total": iva_total,
                        "total": total_calculado,
                    }

                    res = _insert_cabecera(tabla_cab, cabecera)
                    comprobante_id = res.data[0]["id"]

                    for item in st.session_state["comp_items"]:
                        detalle = {
                            "comprobante_id": comprobante_id,
                            "articulo": item["articulo"],
                            "articulo_id": item.get("articulo_id"),
                            "cantidad": int(item["cantidad"]),
                            "lote": item.get("lote", ""),
                            "vencimiento": item.get("vencimiento", ""),
                            "usuario": str(usuario_actual),
                            "moneda": st.session_state["comp_moneda"],
                            "precio_unit_sin_iva": float(item.get("precio_unit_sin_iva", 0.0)),
                            "iva_tipo": item.get("iva_tipo", "22%"),
                            "iva_rate": float(item.get("iva_rate", 0.22)),
                            "descuento_pct": float(item.get("descuento_pct", 0.0)),
                            "descuento_monto": float(item.get("descuento_monto", 0.0)),
                            "subtotal_sin_iva": float(item.get("subtotal_sin_iva", 0.0)),
                            "iva_monto": float(item.get("iva_monto", 0.0)),
                            "total_con_iva": float(item.get("total_con_iva", 0.0)),
                        }

                        _insert_detalle(tabla_det, detalle)
                        _impactar_stock(detalle["articulo"], detalle["cantidad"])

                    st.success("✅ Comprobante guardado correctamente.")
                    st.session_state["comp_items"] = []
                    st.session_state["comp_reset_line"] = True
                    st.rerun()

                except Exception as e:
                    st.error("❌ No se pudo guardar en Supabase.")
                    st.write(str(e))
                    st.stop()



# =====================================================================
# ENTRY POINT
# =====================================================================

if __name__ == "__main__":
    mostrar_ingreso_comprobantes()
