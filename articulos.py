# =====================================================================
# 📚 MÓDULO ARTÍCULOS - FERTI CHAT
# Archivo: articulos.py
#
# Objetivo:
# - LISTAR artículos ya creados desde tabla Supabase: public.articulos (estructura GNS)
# - Permite buscar, seleccionar y adjuntar imágenes/manuales (Storage)
#
# Requiere:
# - supabase_client.py con objeto: supabase
# - Tabla (Supabase/Postgres): articulos  (GNS)
# - Bucket Storage (Supabase): "articulos" (para imágenes/manuales)
# - Tabla articulo_archivos (opcional)
# =====================================================================

import streamlit as st
import pandas as pd
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import uuid

from supabase_client import supabase  # <-- NO cambiar

# AgGrid opcional (si no está, cae a st.dataframe)
try:
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
except Exception:
    AgGrid = None


# =====================================================================
# CONFIG
# =====================================================================
BUCKET_ARTICULOS = "articulos"
TABLE_ARTICULOS_GNS = "articulos"  # <- TU TABLA GNS (la creaste con ese nombre)

# Mapeo "posibles nombres" -> "columna normalizada"
# (Soporta nombres con espacios, guiones, puntos, etc)
COL_ALIASES = {
    "id": ["id", "Id", "ID"],
    "descripcion": ["descripcion", "Descripcion", "Descripción", "DESCRIPCION", "DESCRIPCIÓN"],
    "familia": ["familia", "Familia", "FAMILIA"],
    "codigo_int": ["codigo_int", "Codigo Int.", "Código Int.", "Codigo Int", "Código Int", "Código Int.", "Codigo Int."],
    "codigo_ext": ["codigo_ext", "Codigo Ext.", "Código Ext.", "Codigo Ext", "Código Ext", "Código Ext.", "Codigo Ext."],
    "unidad": ["unidad", "Unidad", "UNIDAD"],
    "tipo_articulo": ["tipo_articulo", "Tipo Articulo", "Tipo Artículo", "TIPO ARTICULO", "TIPO ARTÍCULO"],
    "tipo_impuesto": ["tipo_impuesto", "Tipo Impuesto", "TIPO IMPUESTO"],
    "tipo_concepto": ["tipo_concepto", "Tipo Concepto", "TIPO CONCEPTO"],
    "cuenta_compra": ["cuenta_compra", "Cuenta Compra", "CUENTA COMPRA"],
    "cuenta_venta": ["cuenta_venta", "Cuenta Venta", "CUENTA VENTA"],
    "cuenta_venta_exe": ["cuenta_venta_exe", "Cuenta Venta Exe.", "Cuenta Venta Exe", "CUENTA VENTA EXE", "Cuenta Venta Exe."],
    "cuenta_costo_venta": ["cuenta_costo_venta", "Cuenta Costo Venta", "CUENTA COSTO VENTA"],
    "proveedor": ["proveedor", "Proveedor", "PROVEEDOR"],
    "activo": ["activo", "Activo", "ACTIVO"],
    "mueve_stock": ["mueve_stock", "Mueve Stock", "MueveStock", "MUEVE STOCK"],
    "ecommerce": ["ecommerce", "e-Commerce", "ecommerce", "E-Commerce", "e_commerce", "E-COMMERCE"],
    "stock_minimo": ["stock_minimo", "Stock Minimo", "Stock Mínimo", "STOCK MINIMO", "STOCK MÍNIMO"],
    "stock_maximo": ["stock_maximo", "Stock Maximo", "Stock Máximo", "STOCK MAXIMO", "STOCK MÁXIMO"],
    "costo_fijo": ["costo_fijo", "Costo Fijo", "COSTO FIJO"],
}


# =====================================================================
# HELPERS SUPABASE
# =====================================================================
def _sb_select(
    table: str,
    columns: str = "*",
    filters: Optional[List[Tuple[str, str, Any]]] = None,
    order: Optional[Tuple[str, bool]] = None,
) -> pd.DataFrame:
    q = supabase.table(table).select(columns)

    if filters:
        for col, op, val in filters:
            if op == "eq":
                q = q.eq(col, val)
            elif op == "ilike":
                q = q.ilike(col, val)
            elif op == "is":
                q = q.is_(col, val)

    # Nota: para columnas con espacios/nombres raros, evitamos order server-side.
    if order:
        col, asc = order
        q = q.order(col, desc=not asc)

    res = q.execute()
    data = getattr(res, "data", None) or []
    return pd.DataFrame(data)


def _sb_insert_archivo(payload: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        supabase.table("articulo_archivos").insert(payload).execute()
        return True, "OK"
    except Exception as e:
        return False, str(e)


def _sb_upload_storage(bucket: str, path: str, content_bytes: bytes, mime: str) -> Tuple[bool, str]:
    try:
        supabase.storage.from_(bucket).upload(
            path,
            content_bytes,
            file_options={"content-type": mime or "application/octet-stream"},
        )
        return True, "OK"
    except Exception as e:
        return False, str(e)


# =====================================================================
# NORMALIZACIÓN (para que SIEMPRE encontremos columnas)
# =====================================================================
def _find_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    cols = list(df.columns)
    # match exacto primero
    for c in candidates:
        if c in cols:
            return c
    # match por lower/strip (por si hay diferencias mínimas)
    cols_norm = {str(c).strip().lower(): c for c in cols}
    for c in candidates:
        key = str(c).strip().lower()
        if key in cols_norm:
            return cols_norm[key]
    return None


def _normalize_articulos_gns(df_raw: pd.DataFrame) -> pd.DataFrame:
    if df_raw is None or df_raw.empty:
        return pd.DataFrame(
            columns=[
                "id",
                "descripcion",
                "familia",
                "codigo_int",
                "codigo_ext",
                "unidad",
                "tipo_articulo",
                "tipo_impuesto",
                "tipo_concepto",
                "cuenta_compra",
                "cuenta_venta",
                "cuenta_venta_exe",
                "cuenta_costo_venta",
                "proveedor",
                "activo",
                "mueve_stock",
                "ecommerce",
                "stock_minimo",
                "stock_maximo",
                "costo_fijo",
            ]
        )

    out = pd.DataFrame()

    for key, aliases in COL_ALIASES.items():
        col = _find_col(df_raw, aliases)
        if col is None:
            out[key] = None
        else:
            out[key] = df_raw[col]

    # Normalizar types a texto para búsqueda/visual (sin romper)
    for c in out.columns:
        if c in ["activo", "mueve_stock", "ecommerce"]:
            # boolean friendly (si viene 'x', '1', 'true', etc)
            def _to_bool(v):
                s = str(v or "").strip().lower()
                if s in ["true", "t", "1", "x", "si", "sí", "y", "yes"]:
                    return True
                if s in ["false", "f", "0", "no", "n", ""]:
                    return False
                # si ya es bool
                if isinstance(v, bool):
                    return bool(v)
                return False

            out[c] = out[c].apply(_to_bool)

    # Orden local por descripción
    if "descripcion" in out.columns:
        out["descripcion"] = out["descripcion"].astype(str).fillna("").str.strip()
        out = out.sort_values("descripcion", ascending=True)

    # id a str para selección/archivos
    out["id"] = out["id"].astype(str).fillna("").str.strip()

    return out.reset_index(drop=True)


# =====================================================================
# CACHES
# =====================================================================
@st.cache_data(ttl=30)
def _cache_articulos_gns() -> pd.DataFrame:
    df_raw = _sb_select(TABLE_ARTICULOS_GNS, "*")
    return _normalize_articulos_gns(df_raw)


def _invalidate_caches():
    _cache_articulos_gns.clear()


# =====================================================================
# UI: GRID
# =====================================================================
def _grid_listado(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    if df is None or df.empty:
        st.info("Sin artículos para mostrar. (Si sabés que hay datos, revisá RLS/Policies de la tabla en Supabase).")
        return None

    view_cols = [
        "id",
        "descripcion",
        "familia",
        "codigo_int",
        "codigo_ext",
        "unidad",
        "proveedor",
        "activo",
        "mueve_stock",
        "ecommerce",
        "stock_minimo",
        "stock_maximo",
        "costo_fijo",
    ]

    for c in view_cols:
        if c not in df.columns:
            df[c] = None

    vdf = df[view_cols].copy()
    st.caption(f"Mostrando {len(vdf)} artículo(s).")

    if AgGrid is None:
        st.dataframe(vdf, use_container_width=True, height=420)
        return None

    gb = GridOptionsBuilder.from_dataframe(vdf)
    gb.configure_default_column(filter=True, sortable=True, resizable=True)
    gb.configure_selection("single", use_checkbox=True)
    grid_options = gb.build()

    resp = AgGrid(
        vdf,
        gridOptions=grid_options,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        fit_columns_on_grid_load=True,
        height=420,
    )

    sel = resp.get("selected_rows") or []
    if not sel:
        return None
    return sel[0]


def _ui_detalle(row: Dict[str, Any]):
    st.subheader("Detalle")
    # Mostrar en formato “limpio”
    show = {
        "Id": row.get("id"),
        "Descripción": row.get("descripcion"),
        "Familia": row.get("familia"),
        "Código Int.": row.get("codigo_int"),
        "Código Ext.": row.get("codigo_ext"),
        "Unidad": row.get("unidad"),
        "Tipo Artículo": row.get("tipo_articulo"),
        "Tipo Impuesto": row.get("tipo_impuesto"),
        "Tipo Concepto": row.get("tipo_concepto"),
        "Cuenta Compra": row.get("cuenta_compra"),
        "Cuenta Venta": row.get("cuenta_venta"),
        "Cuenta Venta Exe.": row.get("cuenta_venta_exe"),
        "Cuenta Costo Venta": row.get("cuenta_costo_venta"),
        "Proveedor": row.get("proveedor"),
        "Activo": row.get("activo"),
        "Mueve Stock": row.get("mueve_stock"),
        "e-Commerce": row.get("ecommerce"),
        "Stock Mínimo": row.get("stock_minimo"),
        "Stock Máximo": row.get("stock_maximo"),
        "Costo Fijo": row.get("costo_fijo"),
    }
    st.write(show)


# =====================================================================
# ARCHIVOS (Storage)
# =====================================================================
def _ui_archivos(articulo_id: str):
    st.markdown("### Archivos (imágenes / manuales)")

    col1, col2 = st.columns(2)

    with col1:
        img = st.file_uploader("Subir imagen", type=["png", "jpg", "jpeg", "webp"], key=f"up_img_{articulo_id}")
        if st.button("⬆️ Subir imagen", key=f"btn_img_{articulo_id}", use_container_width=True):
            if img is None:
                st.error("Seleccioná una imagen.")
            else:
                raw = img.getvalue()
                ext = ""
                if "." in img.name:
                    ext = "." + img.name.split(".")[-1].lower().strip()
                path = f"{articulo_id}/imagen_{uuid.uuid4().hex}{ext}"
                ok, err = _sb_upload_storage(BUCKET_ARTICULOS, path, raw, getattr(img, "type", "") or "")
                if not ok:
                    st.error(f"Error storage: {err}")
                else:
                    payload = {
                        "articulo_id": str(articulo_id),
                        "tipo": "imagen",
                        "nombre_archivo": img.name,
                        "storage_bucket": BUCKET_ARTICULOS,
                        "storage_path": path,
                        "mime_type": getattr(img, "type", None),
                        "size_bytes": len(raw),
                        "created_at": datetime.utcnow().isoformat(),
                    }
                    _sb_insert_archivo(payload)
                    st.success("Imagen subida.")

    with col2:
        pdf = st.file_uploader("Subir manual (PDF)", type=["pdf"], key=f"up_pdf_{articulo_id}")
        if st.button("⬆️ Subir manual", key=f"btn_pdf_{articulo_id}", use_container_width=True):
            if pdf is None:
                st.error("Seleccioná un PDF.")
            else:
                raw = pdf.getvalue()
                path = f"{articulo_id}/manual_{uuid.uuid4().hex}.pdf"
                ok, err = _sb_upload_storage(BUCKET_ARTICULOS, path, raw, getattr(pdf, "type", "") or "application/pdf")
                if not ok:
                    st.error(f"Error storage: {err}")
                else:
                    payload = {
                        "articulo_id": str(articulo_id),
                        "tipo": "manual",
                        "nombre_archivo": pdf.name,
                        "storage_bucket": BUCKET_ARTICULOS,
                        "storage_path": path,
                        "mime_type": getattr(pdf, "type", None),
                        "size_bytes": len(raw),
                        "created_at": datetime.utcnow().isoformat(),
                    }
                    _sb_insert_archivo(payload)
                    st.success("Manual subido.")

    # Listado si existe tabla articulo_archivos
    try:
        df = _sb_select("articulo_archivos", "*", filters=[("articulo_id", "eq", str(articulo_id))])
        if df is not None and not df.empty:
            cols_show = [c for c in ["tipo", "nombre_archivo", "storage_path", "created_at"] if c in df.columns]
            if cols_show:
                st.dataframe(df[cols_show], use_container_width=True)
            else:
                st.dataframe(df, use_container_width=True)
        else:
            st.caption("Sin registros en articulo_archivos (o tabla vacía).")
    except Exception:
        st.caption("Tabla articulo_archivos no disponible (opcional).")


# =====================================================================
# FUNCIÓN PRINCIPAL
# =====================================================================
def mostrar_articulos():
    st.title("📚 Artículos (GNS)")

    if "articulos_sel" not in st.session_state:
        st.session_state["articulos_sel"] = None

    if "articulos_busqueda" not in st.session_state:
        st.session_state["articulos_busqueda"] = ""

    tab_listado, tab_detalle = st.tabs(["📋 Listado", "🧾 Detalle / Archivos"])

    # -------------------------
    # TAB LISTADO
    # -------------------------
    with tab_listado:
        c1, c2, c3 = st.columns([0.72, 0.14, 0.14])

        with c1:
            filtro = st.text_input(
                "Buscar (Descripción / Familia / Códigos / Proveedor)",
                key="articulos_busqueda",
                placeholder="Vacío = muestra todos",
            )

        with c2:
            if st.button("🧹 Limpiar", use_container_width=True, key="art_list_clear"):
                st.session_state["articulos_busqueda"] = ""
                st.rerun()

        with c3:
            if st.button("🔄 Recargar", use_container_width=True, key="art_list_reload"):
                _invalidate_caches()
                st.rerun()

        df = _cache_articulos_gns()

        # Filtro local literal (no regex)
        if df is not None and not df.empty and (filtro or "").strip():
            t = (filtro or "").strip().lower()

            def _col_as_str(s: pd.Series) -> pd.Series:
                return s.fillna("").astype(str).str.lower()

            cols_busqueda = [
                "id",
                "descripcion",
                "familia",
                "codigo_int",
                "codigo_ext",
                "unidad",
                "proveedor",
                "tipo_articulo",
                "tipo_impuesto",
                "tipo_concepto",
                "cuenta_compra",
                "cuenta_venta",
                "cuenta_venta_exe",
                "cuenta_costo_venta",
            ]

            for c in cols_busqueda:
                if c not in df.columns:
                    df[c] = ""

            mask = False
            for c in cols_busqueda:
                mask = mask | _col_as_str(df[c]).str.contains(t, na=False, regex=False)

            df = df[mask].copy()

        selected_row = _grid_listado(df)
        if selected_row and selected_row.get("id"):
            st.session_state["articulos_sel"] = {"id": str(selected_row["id"])}
            st.info("Artículo seleccionado. Abrí la pestaña “Detalle / Archivos”.")

        # Mini diagnóstico si sigue vacío
        if df is None or df.empty:
            with st.expander("🔎 Diagnóstico (si sabés que hay datos)", expanded=False):
                st.write(
                    "Si tu tabla tiene filas y acá sale vacío, casi seguro es RLS/Policies.\n\n"
                    "En Supabase: Table Editor → articulos → RLS.\n"
                    "Si está ENABLED, necesitás una policy SELECT para anon/authenticated."
                )

    # -------------------------
    # TAB DETALLE / ARCHIVOS
    # -------------------------
    with tab_detalle:
        sel = st.session_state.get("articulos_sel")
        if not sel or not sel.get("id"):
            st.info("Seleccioná un artículo en la pestaña “Listado”.")
            return

        articulo_id = str(sel["id"]).strip()
        df_all = _cache_articulos_gns()
        row = None
        if df_all is not None and not df_all.empty:
            m = df_all[df_all["id"].astype(str) == articulo_id]
            if not m.empty:
                row = m.iloc[0].to_dict()

        if not row:
            st.warning("No se encontró el artículo seleccionado (probá Recargar).")
            if st.button("🔄 Recargar", use_container_width=True, key="art_det_reload"):
                _invalidate_caches()
                st.rerun()
            return

        _ui_detalle(row)
        st.markdown("---")
        _ui_archivos(articulo_id)

