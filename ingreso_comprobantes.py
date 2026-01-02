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

    menu = st.radio(
        "Modo:",
        ["🧾 Ingreso manual", "📄 Carga por archivo (CSV/PDF)"],
        horizontal=True
    )

    # =========================
    # INGRESO MANUAL
    # =========================
    if menu == "🧾 Ingreso manual":

        if "comp_items" not in st.session_state:
            st.session_state.comp_items = []

        with st.form("form_comprobante"):

            col1, col2, col3 = st.columns(3)

            with col1:
                fecha = st.date_input("Fecha", value=date.today())
                proveedor = st.text_input("Proveedor")

            with col2:
                tipo_comprobante = st.selectbox(
                    "Tipo",
                    ["Factura", "Remito", "Nota de Crédito"]
                )
                nro_comprobante = st.text_input("Nº Comprobante")

            with col3:
                total = st.number_input(
                    "Total",
                    min_value=0.0,
                    step=0.01
                )

            st.markdown("### 📦 Artículos")

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                articulo = st.text_input("Artículo")
            with c2:
                cantidad = st.number_input("Cantidad", min_value=1, step=1)
            with c3:
                lote = st.text_input("Lote")
            with c4:
                vencimiento = st.date_input("Vencimiento")

            if st.form_submit_button("➕ Agregar artículo"):
                if articulo.strip():
                    st.session_state.comp_items.append({
                        "articulo": articulo.strip(),
                        "cantidad": int(cantidad),
                        "lote": lote.strip(),
                        "vencimiento": str(vencimiento)
                    })

            if st.session_state.comp_items:
                st.dataframe(
                    pd.DataFrame(st.session_state.comp_items),
                    use_container_width=True
                )

            guardar = st.form_submit_button("💾 Guardar comprobante")

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

            cabecera = {
                "fecha": str(fecha),
                "proveedor": proveedor_norm,
                "tipo_comprobante": tipo_comprobante,
                "nro_comprobante": nro_norm,
                "total": float(total),
                "usuario": str(usuario_actual)
            }

            res = supabase.table(TABLA_COMPROBANTES).insert(cabecera).execute()
            comprobante_id = res.data[0]["id"]

            for item in st.session_state.comp_items:
                detalle = {
                    "comprobante_id": comprobante_id,
                    "articulo": item["articulo"],
                    "cantidad": int(item["cantidad"]),
                    "lote": item.get("lote", ""),
                    "vencimiento": item.get("vencimiento", ""),
                    "usuario": str(usuario_actual)
                }
                supabase.table(TABLA_DETALLE).insert(detalle).execute()
                _impactar_stock(detalle["articulo"], detalle["cantidad"])

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
                    cabecera = {
                        "fecha": str(row["fecha"]),
                        "proveedor": str(row["proveedor"]).upper(),
                        "tipo_comprobante": str(row["tipo"]),
                        "nro_comprobante": str(row["nro_comprobante"]),
                        "total": float(row["total"]),
                        "usuario": str(usuario_actual)
                    }

                    res = supabase.table(TABLA_COMPROBANTES).insert(cabecera).execute()
                    comprobante_id = res.data[0]["id"]

                    detalle = {
                        "comprobante_id": comprobante_id,
                        "articulo": str(row["articulo"]),
                        "cantidad": int(row["cantidad"]),
                        "lote": str(row.get("lote", "")),
                        "vencimiento": str(row.get("vencimiento", "")),
                        "usuario": str(usuario_actual)
                    }

                    supabase.table(TABLA_DETALLE).insert(detalle).execute()
                    _impactar_stock(detalle["articulo"], detalle["cantidad"])

                st.success("CSV importado correctamente.")

        elif archivo:
            st.info("PDF cargado (no parseado).")

