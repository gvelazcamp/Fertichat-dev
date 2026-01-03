# =====================================================================
# 📥 MÓDULO: INGRESO DE COMPROBANTES - FERTI CHAT
# Archivo: ingreso_comprobantes.py
# =====================================================================

import streamlit as st
import pandas as pd
from datetime import date
import os
import re
import io

from supabase import create_client

# PDF (ReportLab) - opcional (no rompe si no está instalado)
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    REPORTLAB_OK = True
except Exception:
    REPORTLAB_OK = False

# =====================================================================
# CONFIGURACIÓN SUPABASE
# =====================================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    supabase = None
else:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

TABLA_COMPROBANTES = "comprobantes_compras"
TABLA_DETALLE = "comprobantes_detalle"
TABLA_STOCK = "stock"
TABLA_PROVEEDORES = "proveedores"
TABLA_ARTICULOS = "articulos"

# =====================================================================
# HELPERS
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
    """
    Lee IVA desde la fila del artículo, especialmente desde:
    - "Tipo Impuesto" (ej: "1- Exento 0%", "IVA 10%", "IVA 22%")
    Devuelve: "Exento" / "10%" / "22%"
    """
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

    # fallback típico: "1- Exento 0%"
    if re.match(r"^\s*1\s*[-]", v):
        return "Exento"

    return "22%"

def _map_precio_sin_iva_from_articulo_row(row: dict) -> float:
    """
    Intenta leer precio unitario SIN IVA desde la fila del artículo.
    """
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

    out = []
    start = 0
    page = 1000
    max_rows = 50000

    while start < max_rows:
        end = start + page - 1
        res = (
            supabase.table(TABLA_PROVEEDORES)
            .select("*")
            .order("nombre")
            .range(start, end)
            .execute()
        )
        batch = res.data or []
        out.extend(batch)
        if len(batch) < page:
            break
        start += page

    return out


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
        # OJO: no ordeno por "descripción" porque puede no existir exactamente con ese nombre
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
    for r in data:
        nombre = str(r.get("nombre", "") or "").strip()
        if nombre:
            options.append(nombre)
            name_to_id[nombre] = r.get("id")
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
# INSERTS CON FALLBACK
# =====================================================================

def _insert_cabecera_con_fallback(cabecera_full: dict) -> dict:
    try:
        return supabase.table(TABLA_COMPROBANTES).insert(cabecera_full).execute()
    except Exception:
        cabecera_min = {
            "fecha": cabecera_full.get("fecha"),
            "proveedor": cabecera_full.get("proveedor"),
            "tipo_comprobante": cabecera_full.get("tipo_comprobante"),
            "nro_comprobante": cabecera_full.get("nro_comprobante"),
            "total": cabecera_full.get("total", 0.0),
            "usuario": cabecera_full.get("usuario"),
        }
        return supabase.table(TABLA_COMPROBANTES).insert(cabecera_min).execute()

def _insert_detalle_con_fallback(detalle_full: dict) -> None:
    try:
        supabase.table(TABLA_DETALLE).insert(detalle_full).execute()
    except Exception:
        detalle_min = {
            "comprobante_id": detalle_full.get("comprobante_id"),
            "articulo": detalle_full.get("articulo"),
            "cantidad": detalle_full.get("cantidad"),
            "lote": detalle_full.get("lote", ""),
            "vencimiento": detalle_full.get("vencimiento", ""),
            "usuario": detalle_full.get("usuario"),
        }
        supabase.table(TABLA_DETALLE).insert(detalle_min).execute()

# =====================================================================
# FUNCIÓN PRINCIPAL
# =====================================================================

def mostrar_ingreso_comprobantes():
    st.title("📥 Ingreso de comprobantes")

    usuario_actual = st.session_state.get("usuario", st.session_state.get("user", "desconocido"))

    if not supabase:
        st.warning("Supabase no configurado.")
        st.stop()

    # -------------------------
    # Estado inicial (defaults)
    # -------------------------
    if "comp_items" not in st.session_state:
        st.session_state["comp_items"] = []

    if "comp_next_rid" not in st.session_state:
        st.session_state["comp_next_rid"] = 1

    if "comp_reset_line" not in st.session_state:
        st.session_state["comp_reset_line"] = False

    # Defaults de widgets (solo si no existen)
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
    if "comp_lote" not in st.session_state:
        st.session_state["comp_lote"] = ""
    if "comp_venc" not in st.session_state:
        st.session_state["comp_venc"] = date.today()

    # Reset del renglón (se ejecuta ANTES de crear widgets)
    if st.session_state["comp_reset_line"]:
        st.session_state["comp_articulo_sel"] = ""
        st.session_state["comp_articulo_prev"] = ""
        st.session_state["comp_cantidad"] = 1
        st.session_state["comp_precio"] = 0.0
        st.session_state["comp_desc"] = 0.0
        st.session_state["comp_lote"] = ""
        st.session_state["comp_venc"] = date.today()
        st.session_state["comp_reset_line"] = False

    # -------------------------
    # Datos Supabase
    # -------------------------
    proveedores_options, prov_name_to_id = _get_proveedor_options()
    articulos_options, art_label_to_row = _get_articulo_options()

    # Sanitizar selectbox si quedó un valor viejo
    if st.session_state["comp_proveedor_sel"] not in proveedores_options:
        st.session_state["comp_proveedor_sel"] = ""
    if st.session_state["comp_articulo_sel"] not in articulos_options:
        st.session_state["comp_articulo_sel"] = ""

    # =========================
    # CABECERA
    # =========================
    c1, c2, c3 = st.columns(3)

    with c1:
        st.date_input("Fecha", key="comp_fecha")

        cprov, cnro = st.columns([2, 1])
        with cprov:
            st.selectbox("Proveedor", proveedores_options, key="comp_proveedor_sel")
        with cnro:
            st.text_input("Nº Comprobante", key="comp_nro")

    with c2:
        st.selectbox("Tipo", ["Factura", "Remito", "Nota de Crédito"], key="comp_tipo")
        st.selectbox("Condición", ["Contado", "Crédito"], key="comp_condicion")

    with c3:
        st.selectbox("Moneda", ["UYU", "USD"], key="comp_moneda")

    st.markdown("### 📦 Artículos")

    # =========================
    # RENGLÓN DE CARGA
    # =========================
    i1, i2, i3, i4, i5, i6, i7 = st.columns([2.6, 1, 1.2, 1.1, 1.1, 1.2, 1.4])

    with i1:
        st.selectbox("Artículo", articulos_options, key="comp_articulo_sel")

    # Autocargar precio/IVA cuando cambia el artículo (ANTES de crear los otros widgets)
    art_row = art_label_to_row.get(st.session_state["comp_articulo_sel"], {}) if st.session_state["comp_articulo_sel"] else {}
    iva_tipo_sugerido = _map_iva_tipo_from_articulo_row(art_row) if art_row else "22%"
    precio_db = _map_precio_sin_iva_from_articulo_row(art_row) if art_row else 0.0

    if st.session_state["comp_articulo_sel"] != st.session_state["comp_articulo_prev"]:
        st.session_state["comp_articulo_prev"] = st.session_state["comp_articulo_sel"]
        st.session_state["comp_precio"] = float(precio_db or 0.0)
        st.session_state["comp_cantidad"] = 1
        st.session_state["comp_desc"] = 0.0
        st.session_state["comp_lote"] = ""
        st.session_state["comp_venc"] = date.today()

    with i2:
        st.number_input("Cantidad", min_value=1, step=1, key="comp_cantidad")
    with i3:
        st.number_input("Precio unit. s/IVA", min_value=0.0, step=0.01, key="comp_precio")
    with i4:
        st.text_input("IVA", value=iva_tipo_sugerido, disabled=True)
    with i5:
        st.number_input("Desc. %", min_value=0.0, max_value=100.0, step=0.5, key="comp_desc")
    with i6:
        st.text_input("Lote", key="comp_lote")
    with i7:
        st.date_input("Vencimiento", key="comp_venc")

    badd, bsave = st.columns([1, 1])

    # =========================
    # ➕ AGREGAR ARTÍCULO
    # =========================
    if badd.button("➕ Agregar artículo", use_container_width=True):
        if not st.session_state["comp_proveedor_sel"]:
            st.error("Seleccioná un proveedor.")
        elif not st.session_state["comp_articulo_sel"]:
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
                "lote": (st.session_state["comp_lote"] or "").strip(),
                "vencimiento": str(st.session_state["comp_venc"]),
                "moneda": st.session_state["comp_moneda"],
            })

            # Pediste: al agregar, que quede listo para una nueva línea
            st.session_state["comp_reset_line"] = True
            st.rerun()

    # =========================
    # TABLA ÚNICA + BORRAR
    # =========================
    if st.session_state["comp_items"]:
        df_items = pd.DataFrame(st.session_state["comp_items"]).copy()

        if "🗑 Eliminar" not in df_items.columns:
            df_items["🗑 Eliminar"] = False

        show_cols = [
            "_rid",
            "articulo",
            "cantidad",
            "precio_unit_sin_iva",
            "iva_tipo",
            "descuento_pct",
            "subtotal_sin_iva",
            "iva_monto",
            "total_con_iva",
            "lote",
            "vencimiento",
            "🗑 Eliminar",
        ]

        edited = st.data_editor(
            df_items[show_cols],
            use_container_width=True,
            hide_index=True,
            height=240,
            disabled=[c for c in show_cols if c != "🗑 Eliminar"],
            key="comp_editor"
        )

        cdel1, _ = st.columns([1, 3])
        if cdel1.button("🗑 Quitar seleccionados", use_container_width=True):
            to_del = set(edited.loc[edited["🗑 Eliminar"] == True, "_rid"].tolist())
            st.session_state["comp_items"] = [it for it in st.session_state["comp_items"] if it.get("_rid") not in to_del]
            st.rerun()

        # Totales
        moneda_actual = st.session_state["comp_moneda"]
        subtotal = float(df_items["subtotal_sin_iva"].sum())
        iva_total = float(df_items["iva_monto"].sum())
        total_calculado = float(df_items["total_con_iva"].sum())
        desc_total = float(df_items["descuento_monto"].sum()) if "descuento_monto" in df_items.columns else 0.0

        t1, t2, t3, t4 = st.columns([2.2, 2.2, 2.2, 2.4])
        with t1:
            st.caption("SUB TOTAL")
            st.text_input("SUB TOTAL", value=_fmt_money(subtotal, moneda_actual), disabled=True, label_visibility="collapsed")
        with t2:
            st.caption("DESC./REC.")
            st.text_input("DESC./REC.", value=_fmt_money(desc_total, moneda_actual), disabled=True, label_visibility="collapsed")
        with t3:
            st.caption("IMPUESTOS")
            st.text_input("IMPUESTOS", value=_fmt_money(iva_total, moneda_actual), disabled=True, label_visibility="collapsed")
        with t4:
            st.caption("TOTAL")
            st.text_input("TOTAL", value=_fmt_money(total_calculado, moneda_actual), disabled=True, label_visibility="collapsed")

    # =========================
    # 💾 GUARDAR COMPROBANTE
    # =========================
    if bsave.button("💾 Guardar comprobante", use_container_width=True):
        if not st.session_state["comp_proveedor_sel"] or not st.session_state["comp_nro"] or not st.session_state["comp_items"]:
            st.error("Faltan datos obligatorios (Proveedor, Nº Comprobante y al menos 1 artículo).")
            st.stop()

        proveedor_nombre = str(st.session_state["comp_proveedor_sel"]).strip()
        proveedor_id = prov_name_to_id.get(proveedor_nombre)
        nro_norm = str(st.session_state["comp_nro"]).strip()

        try:
            df_items = pd.DataFrame(st.session_state["comp_items"])
            subtotal = float(df_items["subtotal_sin_iva"].sum())
            iva_total = float(df_items["iva_monto"].sum())
            total_calculado = float(df_items["total_con_iva"].sum())

            cabecera_full = {
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

            res = _insert_cabecera_con_fallback(cabecera_full)
            comprobante_id = res.data[0]["id"]

            for item in st.session_state["comp_items"]:
                detalle_full = {
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

                _insert_detalle_con_fallback(detalle_full)
                _impactar_stock(detalle_full["articulo"], detalle_full["cantidad"])

            st.success("Comprobante guardado correctamente.")
            st.session_state["comp_items"] = []
            st.rerun()

        except Exception as e:
            st.error("No se pudo guardar en Supabase (RLS / columnas / permisos).")
            st.write(str(e))
            st.stop()
