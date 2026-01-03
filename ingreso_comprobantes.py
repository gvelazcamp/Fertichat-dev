# =====================================================================
# 📥 MÓDULO: INGRESO DE COMPROBANTES - FERTI CHAT
# Archivo: ingreso_comprobantes.py
# =====================================================================

import streamlit as st
import pandas as pd
from datetime import date
import os
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

TABLA_COMPROBANTES = "comprobantes_compras"
TABLA_DETALLE = "comprobantes_detalle"
TABLA_STOCK = "stock"
TABLA_ARTICULOS = "articulos"  # Se usa para intentar autocargar precio/IVA (si existe)

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

    precio_unit_desc = precio_unit_sin_iva * (1.0 - (descuento_pct / 100.0))

    return {
        "base_sin_iva": base,
        "descuento_monto": desc_monto,
        "subtotal_sin_iva": subtotal,
        "iva_monto": iva_monto,
        "total_con_iva": total,
        "precio_unit_desc_sin_iva": precio_unit_desc,
    }

def _fmt_money(v: float, moneda: str) -> str:
    v = _safe_float(v, 0.0)
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{moneda} {s}"

def _fetch_articulo_info(articulo_texto: str) -> dict:
    """
    Intenta autocargar precio_unit_sin_iva e iva_tipo desde TABLA_ARTICULOS.
    Si no encuentra o la tabla/columnas no existen, devuelve {}.
    NO rompe: todo en try/except.
    """
    if not supabase:
        return {}

    a = (articulo_texto or "").strip()
    if not a:
        return {}

    candidates_search_cols = ["articulo", "descripcion", "detalle", "codigo"]
    candidates_price_cols = ["precio_sin_iva", "precio_unitario_sin_iva", "precio", "costo", "precio_unitario"]
    candidates_iva_cols = ["iva_tipo", "iva", "tasa_iva"]

    for search_col in candidates_search_cols:
        try:
            res = (
                supabase.table(TABLA_ARTICULOS)
                .select("*")
                .ilike(search_col, f"%{a}%")
                .limit(5)
                .execute()
            )
            if not res.data:
                continue

            row = res.data[0]
            out = {}

            for pc in candidates_price_cols:
                if pc in row and row.get(pc) not in (None, ""):
                    out["precio_unit_sin_iva"] = _safe_float(row.get(pc), 0.0)
                    break

            for ic in candidates_iva_cols:
                if ic in row and row.get(ic) not in (None, ""):
                    val = row.get(ic)
                    if isinstance(val, str):
                        v = val.strip()
                        if v in ("Exento", "0", "0%"):
                            out["iva_tipo"] = "Exento"
                        elif "10" in v:
                            out["iva_tipo"] = "10%"
                        elif "22" in v or "20" in v:
                            out["iva_tipo"] = "22%"
                        else:
                            out["iva_tipo"] = "22%"
                    else:
                        f = _safe_float(val, 0.0)
                        if abs(f - 0.0) < 1e-9:
                            out["iva_tipo"] = "Exento"
                        elif abs(f - 0.10) < 1e-6:
                            out["iva_tipo"] = "10%"
                        else:
                            out["iva_tipo"] = "22%"
                    break

            return out

        except Exception:
            continue

    return {}

# =====================================================================
# FUNCIÓN: IMPACTO STOCK
# =====================================================================

def _impactar_stock(articulo: str, cantidad: int) -> None:
    if not supabase:
        return

    articulo = (articulo or "").strip()
    if not articulo:
        return

    existe = (
        supabase.table(TABLA_STOCK)
        .select("id,cantidad")
        .eq("articulo", articulo)
        .execute()
    )

    if existe.data:
        stock_id = existe.data[0]["id"]
        cant_actual = existe.data[0].get("cantidad", 0) or 0
        nueva_cant = int(cant_actual) + int(cantidad)

        supabase.table(TABLA_STOCK).update(
            {"cantidad": nueva_cant}
        ).eq("id", stock_id).execute()
    else:
        supabase.table(TABLA_STOCK).insert({
            "articulo": articulo,
            "cantidad": int(cantidad)
        }).execute()

# =====================================================================
# INSERTS CON FALLBACK
# =====================================================================

def _insert_cabecera_con_fallback(cabecera_full: dict) -> dict:
    try:
        return supabase.table(TABLA_COMPROBANTES).insert(cabecera_full).execute()
    except Exception:
        pass

    cabecera_min = {
        "fecha": cabecera_full.get("fecha"),
        "proveedor": cabecera_full.get("proveedor"),
        "tipo_comprobante": cabecera_full.get("tipo_comprobante"),
        "nro_comprobante": cabecera_full.get("nro_comprobante"),
        "total": cabecera_full.get("total_calculado", cabecera_full.get("total", 0.0)),
        "usuario": cabecera_full.get("usuario"),
    }
    return supabase.table(TABLA_COMPROBANTES).insert(cabecera_min).execute()

def _insert_detalle_con_fallback(detalle_full: dict) -> None:
    try:
        supabase.table(TABLA_DETALLE).insert(detalle_full).execute()
        return
    except Exception:
        pass

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
# FUNCIÓN PRINCIPAL DEL MÓDULO
# =====================================================================

def mostrar_ingreso_comprobantes():
    st.title("📥 Ingreso de comprobantes")

    usuario_actual = st.session_state.get(
        "usuario",
        st.session_state.get("user", "desconocido")
    )

    if not supabase:
        st.warning("Supabase no configurado.")
        st.stop()

    if "comp_items" not in st.session_state:
        st.session_state.comp_items = []

    if "comp_moneda" not in st.session_state:
        st.session_state.comp_moneda = "UYU"

    menu = st.radio(
        "Modo:",
        ["🧾 Ingreso manual", "📄 Carga por archivo (CSV/PDF)"],
        horizontal=True
    )

    # =========================
    # INGRESO MANUAL
    # =========================
    if menu == "🧾 Ingreso manual":

        with st.form("form_comprobante"):

            # Cabecera: Moneda al lado de Tipo + N° Comprobante al lado de Proveedor
            col1, col2, col3 = st.columns(3)

            with col1:
                fecha = st.date_input("Fecha", value=date.today())

                cprov, cnro = st.columns([2, 1])
                with cprov:
                    proveedor = st.text_input("Proveedor")
                with cnro:
                    nro_comprobante = st.text_input("Nº Comprobante")

            with col2:
                tipo_comprobante = st.selectbox(
                    "Tipo",
                    ["Factura", "Remito", "Nota de Crédito"]
                )

            with col3:
                moneda = st.selectbox(
                    "Moneda",
                    ["UYU", "USD"],
                    index=0 if st.session_state.comp_moneda == "UYU" else 1,
                    key="comp_moneda"
                )

            st.markdown("### 📦 Artículos")

            c1, c2, c3, c4, c5, c6, c7 = st.columns([2.3, 1, 1.2, 1.1, 1.1, 1.2, 1.4])
            with c1:
                articulo = st.text_input("Artículo")
            with c2:
                cantidad = st.number_input("Cantidad", min_value=1, step=1)
            with c3:
                precio_unit_sin_iva = st.number_input("Precio unit. s/IVA", min_value=0.0, step=0.01)
            with c4:
                iva_tipo = st.selectbox("IVA", ["Exento", "10%", "22%"], index=2)
            with c5:
                descuento_pct = st.number_input("Desc. %", min_value=0.0, max_value=100.0, step=0.5)
            with c6:
                lote = st.text_input("Lote")
            with c7:
                vencimiento = st.date_input("Vencimiento")

            btn_add = st.form_submit_button("➕ Agregar artículo")
            guardar = st.form_submit_button("💾 Guardar comprobante")


        # ----------------------------------
        # Agregar artículo
        # ----------------------------------
        if btn_add:
            if not (articulo or "").strip():
                st.error("El artículo no puede estar vacío.")
            else:
                art = articulo.strip()

                # Autocarga silenciosa (sin checkbox)
                info = _fetch_articulo_info(art)

                if "precio_unit_sin_iva" in info and _safe_float(precio_unit_sin_iva, 0.0) <= 0.0:
                    precio_unit_sin_iva = float(info["precio_unit_sin_iva"])

                if "iva_tipo" in info:
                    iva_tipo = info["iva_tipo"]

                iva_rate = _iva_rate_from_tipo(iva_tipo)
                calc = _calc_linea(int(cantidad), float(precio_unit_sin_iva), float(iva_rate), float(descuento_pct))

                st.session_state.comp_items.append({
                    "articulo": art,
                    "cantidad": int(cantidad),
                    "precio_unit_sin_iva": float(precio_unit_sin_iva),
                    "iva_tipo": iva_tipo,
                    "iva_rate": float(iva_rate),
                    "descuento_pct": float(descuento_pct),
                    "descuento_monto": float(calc["descuento_monto"]),
                    "subtotal_sin_iva": float(calc["subtotal_sin_iva"]),
                    "iva_monto": float(calc["iva_monto"]),
                    "total_con_iva": float(calc["total_con_iva"]),
                    "lote": (lote or "").strip(),
                    "vencimiento": str(vencimiento),
                    "moneda": st.session_state.comp_moneda,
                })

        # ----------------------------------
        # Vista items + totales (abajo)
        # ----------------------------------
        if st.session_state.comp_items:
            df_items = pd.DataFrame(st.session_state.comp_items)

            show_cols = [
                "articulo", "cantidad",
                "precio_unit_sin_iva", "iva_tipo", "descuento_pct",
                "subtotal_sin_iva", "iva_monto", "total_con_iva",
                "lote", "vencimiento"
            ]
            for c in show_cols:
                if c not in df_items.columns:
                    df_items[c] = ""

            st.dataframe(df_items[show_cols], use_container_width=True)

            moneda_actual = st.session_state.comp_moneda
            subtotal = float(df_items["subtotal_sin_iva"].sum()) if "subtotal_sin_iva" in df_items.columns else 0.0
            iva_total = float(df_items["iva_monto"].sum()) if "iva_monto" in df_items.columns else 0.0
            total_calculado = float(df_items["total_con_iva"].sum()) if "total_con_iva" in df_items.columns else 0.0

            ctot1, ctot2, ctot3 = st.columns(3)
            with ctot1:
                st.metric("Subtotal", _fmt_money(subtotal, moneda_actual))
            with ctot2:
                st.metric("IVA", _fmt_money(iva_total, moneda_actual))
            with ctot3:
                st.metric("Total", _fmt_money(total_calculado, moneda_actual))

        # ----------------------------------
        # Guardar comprobante
        # ----------------------------------
        if guardar:
            if not proveedor or not nro_comprobante or not st.session_state.comp_items:
                st.error("Faltan datos obligatorios.")
                st.stop()

            proveedor_norm = proveedor.strip().upper()
            nro_norm = nro_comprobante.strip()

            existe = (
                supabase.table(TABLA_COMPROBANTES)
                .select("id")
                .eq("proveedor", proveedor_norm)
                .eq("nro_comprobante", nro_norm)
                .execute()
            )

            if existe.data:
                st.warning("Comprobante duplicado.")
                st.stop()

            df_items = pd.DataFrame(st.session_state.comp_items)
            subtotal = float(df_items["subtotal_sin_iva"].sum()) if "subtotal_sin_iva" in df_items.columns else 0.0
            iva_total = float(df_items["iva_monto"].sum()) if "iva_monto" in df_items.columns else 0.0
            total_calculado = float(df_items["total_con_iva"].sum()) if "total_con_iva" in df_items.columns else 0.0

            moneda_actual = st.session_state.comp_moneda

            cabecera_full = {
                "fecha": str(fecha),
                "proveedor": proveedor_norm,
                "tipo_comprobante": tipo_comprobante,
                "nro_comprobante": nro_norm,
                "usuario": str(usuario_actual),
                "moneda": moneda_actual,
                "subtotal": subtotal,
                "iva_total": iva_total,
                "total_calculado": total_calculado,
                "total": total_calculado,
            }

            res = _insert_cabecera_con_fallback(cabecera_full)
            comprobante_id = res.data[0]["id"]

            for item in st.session_state.comp_items:
                detalle_full = {
                    "comprobante_id": comprobante_id,
                    "articulo": item["articulo"],
                    "cantidad": int(item["cantidad"]),
                    "lote": item.get("lote", ""),
                    "vencimiento": item.get("vencimiento", ""),
                    "usuario": str(usuario_actual),

                    "moneda": moneda_actual,
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
            st.session_state.comp_items = []

    # =========================
    # CARGA POR ARCHIVO
    # =========================
    else:
        archivo = st.file_uploader("Subir CSV o PDF", type=["csv", "pdf"])

        if archivo and archivo.name.lower().endswith(".csv"):
            df = pd.read_csv(archivo)
            st.dataframe(df, use_container_width=True)

            if st.button("Importar CSV"):
                for _, row in df.iterrows():
                    proveedor_norm = str(row.get("proveedor", "")).strip().upper()
                    nro_norm = str(row.get("nro_comprobante", "")).strip()

                    moneda_row = str(row.get("moneda", st.session_state.comp_moneda)).strip().upper()
                    if moneda_row not in ("UYU", "USD"):
                        moneda_row = st.session_state.comp_moneda

                    iva_tipo_row = str(row.get("iva_tipo", "22%")).strip()
                    iva_rate_row = _safe_float(row.get("iva_rate", _iva_rate_from_tipo(iva_tipo_row)), 0.0)
                    if iva_rate_row not in (0.0, 0.1, 0.22):
                        iva_rate_row = _iva_rate_from_tipo(iva_tipo_row)

                    cantidad_row = _safe_int(row.get("cantidad", 0), 0)
                    precio_row = _safe_float(row.get("precio_unit_sin_iva", 0.0), 0.0)
                    desc_pct_row = _safe_float(row.get("descuento_pct", 0.0), 0.0)

                    calc = _calc_linea(cantidad_row, precio_row, iva_rate_row, desc_pct_row)

                    cabecera_full = {
                        "fecha": str(row.get("fecha", "")),
                        "proveedor": proveedor_norm,
                        "tipo_comprobante": str(row.get("tipo", "")),
                        "nro_comprobante": nro_norm,
                        "usuario": str(usuario_actual),
                        "moneda": moneda_row,
                        "subtotal": float(calc["subtotal_sin_iva"]),
                        "iva_total": float(calc["iva_monto"]),
                        "total_calculado": float(calc["total_con_iva"]),
                        "total": float(calc["total_con_iva"]),
                    }

                    res = _insert_cabecera_con_fallback(cabecera_full)
                    comprobante_id = res.data[0]["id"]

                    detalle_full = {
                        "comprobante_id": comprobante_id,
                        "articulo": str(row.get("articulo", "")).strip(),
                        "cantidad": int(cantidad_row),
                        "lote": str(row.get("lote", "")).strip(),
                        "vencimiento": str(row.get("vencimiento", "")).strip(),
                        "usuario": str(usuario_actual),
                        "moneda": moneda_row,
                        "precio_unit_sin_iva": float(precio_row),
                        "iva_tipo": iva_tipo_row,
                        "iva_rate": float(iva_rate_row),
                        "descuento_pct": float(desc_pct_row),
                        "descuento_monto": float(calc["descuento_monto"]),
                        "subtotal_sin_iva": float(calc["subtotal_sin_iva"]),
                        "iva_monto": float(calc["iva_monto"]),
                        "total_con_iva": float(calc["total_con_iva"]),
                    }

                    _insert_detalle_con_fallback(detalle_full)
                    _impactar_stock(detalle_full["articulo"], detalle_full["cantidad"])

                st.success("CSV importado correctamente.")

        elif archivo:
            st.info("PDF cargado (no parseado).")
