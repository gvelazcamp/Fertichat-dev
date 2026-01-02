# =====================================================================
# 📚 MÓDULO ARTÍCULOS - FERTI CHAT
# Archivo: articulos.py
#
# Requiere:
# - supabase_client.py con objeto: supabase
# - Tablas (Supabase/Postgres): articulos, proveedores (id,nombre), articulo_archivos (opcional)
# - Bucket Storage (Supabase): "articulos" (para imágenes/manuales)
# =====================================================================

import streamlit as st
import pandas as pd
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import uuid

from supabase_client import supabase  # <-- NO cambiar si ya lo tenés así

# AgGrid opcional (si no está, cae a st.dataframe)
try:
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
except Exception:
    AgGrid = None


# =====================================================================
# CONSTANTES
# =====================================================================
BUCKET_ARTICULOS = "articulos"

TIPOS = {
    "Todos": None,          # ✅ AGREGADO (mostrar todos)
    "Ingreso": "ingreso",
    "Egreso": "egreso",
    "Gastos fijos": "gasto_fijo",
}

IVA_OPS = {
    "Exento (0%)": "exento",
    "Mínimo (10%)": "minimo_10",
    "Básico (22%)": "basico_22",
}

MONEDAS = ["UYU", "USD"]

PRECIO_POR_OPS = {
    "Por unidad base (stock)": "unidad_base",
    "Por unidad de compra": "unidad_compra",
}

UNIDAD_BASE_OPS = {
    "Unidad": "unidad",
    "Gramos": "gramos",
}

UNIDAD_COMPRA_OPS = {
    "Unidad": "unidad",
    "Caja": "caja",
    "Gramos": "gramos",
}

# Columnas exactas del maestro (lista)
ARTICULO_COLS = [
    "id",
    "tipo",
    "nombre",
    "descripcion",
    "codigo_interno",
    "codigo_barra",
    "familia",
    "subfamilia",
    "equipo",
    "proveedor_id",
    "fifo",
    "iva",
    "tiene_lote",
    "requiere_vencimiento",
    "unidad_base",
    "unidad_compra",
    "contenido_por_unidad_compra",
    "stock_min",
    "stock_max",
    "precio_actual",
    "moneda_actual",
    "precio_por_actual",
    "fecha_precio_actual",
    "precio_anterior",
    "moneda_anterior",
    "precio_por_anterior",
    "fecha_precio_anterior",
    "activo",
    "created_at",
    "updated_at",
]


# =====================================================================
# HELPERS SUPABASE (mínimos)
# =====================================================================
def _sb_select(
    table: str,
    columns: str = "*",
    filters: Optional[List[Tuple[str, str, Any]]] = None,
    order: Optional[Tuple[str, bool]] = None
) -> pd.DataFrame:
    """
    Select robusto:
    - Intenta con filtros + order.
    - Si falla por columna inexistente (42703), reintenta:
        1) mismos filtros sin order
        2) sin filtros y sin order
    """
    def _build_query(_filters: Optional[List[Tuple[str, str, Any]]], _order: Optional[Tuple[str, bool]]):
        q = supabase.table(table).select(columns)
        if _filters:
            for col, op, val in _filters:
                if op == "eq":
                    q = q.eq(col, val)
                elif op == "ilike":
                    q = q.ilike(col, val)
                elif op == "is":
                    q = q.is_(col, val)
        if _order:
            col, asc = _order
            q = q.order(col, desc=not asc)
        return q

    # 1) Intento normal
    try:
        res = _build_query(filters, order).execute()
        data = getattr(res, "data", None) or []
        return pd.DataFrame(data)
    except Exception as e:
        msg = str(e) or ""
        # 42703 = undefined_column (Postgres)
        if ("42703" in msg) or ("does not exist" in msg.lower()) or ("undefined_column" in msg.lower()):
            pass
        else:
            raise

    # 2) Reintento sin order (manteniendo filtros)
    try:
        res = _build_query(filters, None).execute()
        data = getattr(res, "data", None) or []
        return pd.DataFrame(data)
    except Exception as e2:
        msg2 = str(e2) or ""
        if ("42703" in msg2) or ("does not exist" in msg2.lower()) or ("undefined_column" in msg2.lower()):
            pass
        else:
            raise

    # 3) Reintento sin filtros y sin order
    res = _build_query(None, None).execute()
    data = getattr(res, "data", None) or []
    return pd.DataFrame(data)


def _normalizar_articulos_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    ✅ CORREGIDO: Versión simplificada que asume que las columnas en Supabase
    ya tienen los nombres correctos (nombre, codigo_interno, etc.)
    Si tu tabla usa nombres diferentes, ajustá el mapeo aquí.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=ARTICULO_COLS)
    
    # Asegurar que existan todas las columnas esperadas (rellena con None las faltantes)
    for c in ARTICULO_COLS:
        if c not in df.columns:
            df[c] = None
    
    # Asegurar id como string si existe
    if "id" in df.columns:
        df["id"] = df["id"].astype(str)
    
    # Convertir tipos básicos
    if "activo" in df.columns:
        df["activo"] = df["activo"].fillna(True).astype(bool)
    
    if "fifo" in df.columns:
        df["fifo"] = df["fifo"].fillna(True).astype(bool)
        
    if "tiene_lote" in df.columns:
        df["tiene_lote"] = df["tiene_lote"].fillna(False).astype(bool)
        
    if "requiere_vencimiento" in df.columns:
        df["requiere_vencimiento"] = df["requiere_vencimiento"].fillna(False).astype(bool)
    
    # Reordenar a estructura esperada del módulo
    return df[ARTICULO_COLS].copy()


# =====================================================================
# CACHE FUNCTIONS
# =====================================================================
@st.cache_data(ttl=30)
def _cache_proveedores() -> pd.DataFrame:
    """
    Proveedores para selector.
    - Si NO existe la tabla public.proveedores, devuelve vacío y NO rompe el módulo.
    """
    try:
        df = _sb_select("proveedores", "id,nombre", order=("nombre", True))
    except Exception:
        return pd.DataFrame(columns=["id", "nombre"])

    if df.empty:
        return df

    df["id"] = df["id"].astype(str)
    df["nombre"] = df["nombre"].astype(str)
    return df


@st.cache_data(ttl=30)
def _cache_articulos_por_tipo(tipo: Optional[str]) -> pd.DataFrame:
    """
    ✅ CORREGIDO: Trae artículos y normaliza correctamente
    """
    # Intento traer datos de Supabase
    if tipo:
        df_raw = _sb_select("articulos", "*", filters=[("tipo", "eq", tipo)])
    else:
        df_raw = _sb_select("articulos", "*")

    # Debug temporal (comentá esto después de verificar)
    if df_raw is not None and not df_raw.empty:
        st.sidebar.write("🔍 DEBUG - Columnas en DB:", df_raw.columns.tolist())
        st.sidebar.write(f"🔍 DEBUG - Total filas: {len(df_raw)}")
    
    if df_raw is None or df_raw.empty:
        st.sidebar.warning("⚠️ No se encontraron artículos en la base de datos")
        return pd.DataFrame(columns=ARTICULO_COLS)

    # Normalizar columnas al formato del módulo
    df = _normalizar_articulos_df(df_raw)

    # Filtro adicional por tipo si no se pudo hacer server-side
    if tipo and df is not None and not df.empty and "tipo" in df.columns:
        try:
            # Caso 1: coincide texto directo
            df_tipo = df[df["tipo"].astype(str).str.strip().str.lower() == str(tipo).strip().lower()].copy()

            # Caso 2: si en tu tabla 'tipo' es numérico (1/2/3)
            if df_tipo.empty:
                map_num = {"ingreso": "1", "egreso": "2", "gasto_fijo": "3"}
                target = map_num.get(tipo)
                if target is not None:
                    df_tipo = df[df["tipo"].astype(str).str.strip() == target].copy()

            if not df_tipo.empty:
                df = df_tipo
        except Exception as e:
            st.sidebar.error(f"Error filtrando por tipo: {e}")

    # Orden local por nombre si existe
    try:
        if "nombre" in df.columns and not df.empty:
            df = df.sort_values("nombre", kind="stable")
    except Exception:
        pass

    return df


@st.cache_data(ttl=60)
def _cache_sugerencias_desde_chatbot_raw() -> pd.DataFrame:
    """
    Sugerencias: valores únicos de chatbot_raw.Articulo
    (y trae Familia / Tipo Articulo si existen).
    """
    try:
        df = _sb_select("chatbot_raw", '"Articulo","Familia","Tipo Articulo"')
    except Exception:
        return pd.DataFrame(columns=["Articulo", "Familia", "Tipo Articulo"])

    if df.empty:
        return df

    # Normalizar
    for c in ["Articulo", "Familia", "Tipo Articulo"]:
        if c in df.columns:
            df[c] = df[c].astype(str).fillna("").str.strip()

    df = df[df["Articulo"].astype(str).str.strip() != ""].copy()
    if df.empty:
        return pd.DataFrame(columns=["Articulo", "Familia", "Tipo Articulo"])

    # Unificar por Articulo (primera ocurrencia)
    df = df.drop_duplicates(subset=["Articulo"], keep="first").reset_index(drop=True)
    return df


def _invalidate_caches():
    _cache_proveedores.clear()
    _cache_articulos_por_tipo.clear()
    _cache_sugerencias_desde_chatbot_raw.clear()


# =====================================================================
# SUPABASE UPSERT/INSERT HELPERS
# =====================================================================
def _sb_upsert_articulo(payload: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict]]:
    """
    Inserta o actualiza un artículo.
    Retorna: (success, mensaje, row)
    """
    try:
        # Si tiene id, es UPDATE
        if payload.get("id"):
            art_id = payload.pop("id")
            payload["updated_at"] = datetime.utcnow().isoformat()
            
            res = supabase.table("articulos").update(payload).eq("id", art_id).execute()
            data = getattr(res, "data", None) or []
            if data:
                return True, "Actualizado correctamente", data[0]
            return False, "No se encontró el artículo", None
        else:
            # INSERT
            payload["created_at"] = datetime.utcnow().isoformat()
            payload["updated_at"] = datetime.utcnow().isoformat()
            
            res = supabase.table("articulos").insert(payload).execute()
            data = getattr(res, "data", None) or []
            if data:
                return True, "Creado correctamente", data[0]
            return False, "Error al crear", None
            
    except Exception as e:
        return False, f"Error: {str(e)}", None


def _sb_insert_archivo(payload: Dict[str, Any]) -> bool:
    """
    Inserta registro en articulo_archivos (opcional).
    Si la tabla no existe, no hace nada.
    """
    try:
        supabase.table("articulo_archivos").insert(payload).execute()
        return True
    except Exception:
        return False


def _sb_upload_storage(bucket: str, path: str, data: bytes, mime_type: str) -> Tuple[bool, str]:
    """
    Sube archivo a Supabase Storage.
    """
    try:
        supabase.storage.from_(bucket).upload(path, data, {"content-type": mime_type})
        return True, ""
    except Exception as e:
        return False, str(e)


# =====================================================================
# LÓGICA PRECIO: 2 niveles (actual + anterior)
# =====================================================================
def _aplicar_historial_precio_minimo(payload: Dict[str, Any], current_row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Si cambia el precio_actual (o moneda/por), mueve lo actual a 'anterior' y guarda el nuevo como actual.
    Solo opera cuando hay edición (current_row) y detecta cambio real.
    """
    if not current_row:
        # Nuevo artículo: si viene precio_actual, setea fecha_precio_actual
        if payload.get("precio_actual") is not None and payload.get("moneda_actual") and payload.get("precio_por_actual"):
            payload["fecha_precio_actual"] = datetime.utcnow().isoformat()
        return payload

    # Valores actuales (DB)
    cur_precio = current_row.get("precio_actual")
    cur_mon = current_row.get("moneda_actual")
    cur_por = current_row.get("precio_por_actual")
    cur_fecha = current_row.get("fecha_precio_actual")

    # Nuevos (form)
    new_precio = payload.get("precio_actual")
    new_mon = payload.get("moneda_actual")
    new_por = payload.get("precio_por_actual")

    def _norm_num(x):
        try:
            if x is None or x == "":
                return None
            return float(x)
        except Exception:
            return None

    cur_precio_n = _norm_num(cur_precio)
    new_precio_n = _norm_num(new_precio)

    changed = False
    if cur_precio_n != new_precio_n:
        changed = True
    if (cur_mon or "") != (new_mon or ""):
        changed = True
    if (cur_por or "") != (new_por or ""):
        changed = True

    if changed and (new_precio_n is not None) and new_mon and new_por:
        # Mover actual -> anterior
        payload["precio_anterior"] = cur_precio_n
        payload["moneda_anterior"] = cur_mon
        payload["precio_por_anterior"] = cur_por
        payload["fecha_precio_anterior"] = cur_fecha

        # Setear fecha del nuevo actual
        payload["fecha_precio_actual"] = datetime.utcnow().isoformat()

    return payload


# =====================================================================
# UI COMPONENTS
# =====================================================================
def _grid(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    ✅ CORREGIDO: Muestra grid con validación mejorada
    """
    if df is None or df.empty:
        st.info("📭 Sin artículos para mostrar")
        return None

    # Vista para listado (columna id solo para selección)
    view_cols = [
        "nombre",
        "codigo_interno",
        "codigo_barra",
        "familia",
        "subfamilia",
        "equipo",
        "unidad_compra",
        "unidad_base",
        "precio_actual",
        "moneda_actual",
        "activo",
        "updated_at",
        "id",
    ]
    
    # Asegurar que existen todas las columnas
    for c in view_cols:
        if c not in df.columns:
            df[c] = None

    vdf = df[view_cols].copy()

    # Mostrar cantidad
    st.caption(f"📊 Mostrando {len(vdf)} artículo(s)")

    # Sin AgGrid: solo tabla (sin selección)
    if AgGrid is None:
        st.dataframe(vdf.drop(columns=["id"], errors="ignore"), use_container_width=True, height=350)
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
        height=350,
    )

    sel = resp.get("selected_rows") or []
    if not sel:
        return None
    return sel[0]


def _selector_proveedor(current_id: Optional[str]) -> Optional[str]:
    dfp = _cache_proveedores()
    if dfp.empty:
        st.caption("⚠️ Sin proveedores (tabla proveedores vacía o no existe)")
        return current_id

    options = ["(sin proveedor)"] + dfp["nombre"].tolist()
    name_by_id = {row["id"]: row["nombre"] for _, row in dfp.iterrows()}
    id_by_name = {row["nombre"]: row["id"] for _, row in dfp.iterrows()}

    default_name = "(sin proveedor)"
    if current_id and str(current_id) in name_by_id:
        default_name = name_by_id[str(current_id)]

    idx = options.index(default_name) if default_name in options else 0
    choice = st.selectbox("Proveedor principal", options, index=idx)
    if choice == "(sin proveedor)":
        return None
    return str(id_by_name.get(choice))


def _form_articulo(tipo: str, selected: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    ✅ CORREGIDO: Form mejorado con mejor manejo de datos
    """
    is_edit = bool(selected and selected.get("id"))
    st.subheader("✏️ Editar artículo" if is_edit else "➕ Nuevo artículo")

    # Valores actuales (si edita): traemos fila completa desde df cache para comparar precio
    current_row = None
    if is_edit:
        df_all = _cache_articulos_por_tipo(tipo)
        match = df_all[df_all["id"].astype(str) == str(selected["id"])]
        if not match.empty:
            current_row = match.iloc[0].to_dict()

    prefill = None
    if (not is_edit) and ("articulos_prefill" in st.session_state):
        prefill = st.session_state.get("articulos_prefill") or None

    base = current_row or prefill or {}

    # Botones arriba (mejor UX)
    b1, b2, b3 = st.columns(3)
    with b1:
        btn_save = st.button("💾 Guardar", type="primary", use_container_width=True)
    with b2:
        btn_new = st.button("➕ Nuevo", use_container_width=True)
    with b3:
        btn_reload = st.button("🔄 Recargar", use_container_width=True)

    if btn_reload:
        _invalidate_caches()
        st.rerun()

    if btn_new:
        st.session_state["articulos_sel"] = None
        st.rerun()

    # -------------------------
    # General
    # -------------------------
    with st.expander("🧾 Datos generales", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            nombre = st.text_input("Nombre *", value=str(base.get("nombre") or ""))
            descripcion = st.text_area("Descripción", value=str(base.get("descripcion") or ""), height=90)

            codigo_interno = st.text_input("Código interno", value=str(base.get("codigo_interno") or ""))
            codigo_barra = st.text_input("Código de barra", value=str(base.get("codigo_barra") or ""))

            familia = st.text_input("Familia", value=str(base.get("familia") or ""))
            subfamilia = st.text_input("Subfamilia", value=str(base.get("subfamilia") or ""))
            equipo = st.text_input("Equipo", value=str(base.get("equipo") or ""))

            proveedor_id = _selector_proveedor(str(base.get("proveedor_id") or "") or None)

        with col2:
            fifo = st.checkbox("FIFO", value=bool(base.get("fifo", True)))
            activo = st.checkbox("Activo", value=bool(base.get("activo", True)))

            # IVA
            inv_iva = {v: k for k, v in IVA_OPS.items()}
            iva_default = inv_iva.get(base.get("iva") or "basico_22", "Básico (22%)")
            iva_label = st.selectbox("IVA", list(IVA_OPS.keys()), index=list(IVA_OPS.keys()).index(iva_default))
            iva = IVA_OPS[iva_label]

            tiene_lote = st.checkbox("Tiene lote", value=bool(base.get("tiene_lote", False)))
            requiere_vencimiento = st.checkbox("Requiere vencimiento", value=bool(base.get("requiere_vencimiento", False)))

    # -------------------------
    # Unidades / Stock
    # -------------------------
    with st.expander("📦 Unidades y stock", expanded=True):
        colU1, colU2 = st.columns(2)

        with colU1:
            inv_ub = {v: k for k, v in UNIDAD_BASE_OPS.items()}
            ub_default = inv_ub.get(base.get("unidad_base") or "unidad", "Unidad")
            unidad_base_label = st.selectbox(
                "Unidad base (stock)",
                list(UNIDAD_BASE_OPS.keys()),
                index=list(UNIDAD_BASE_OPS.keys()).index(ub_default),
            )
            unidad_base = UNIDAD_BASE_OPS[unidad_base_label]

            stock_min = st.number_input("Stock mínimo", min_value=0.0, value=float(base.get("stock_min") or 0), step=1.0)
            stock_max = st.number_input("Stock máximo", min_value=0.0, value=float(base.get("stock_max") or 0), step=1.0)

        with colU2:
            inv_uc = {v: k for k, v in UNIDAD_COMPRA_OPS.items()}
            uc_default = inv_uc.get(base.get("unidad_compra") or "unidad", "Unidad")
            unidad_compra_label = st.selectbox(
                "Unidad de compra",
                list(UNIDAD_COMPRA_OPS.keys()),
                index=list(UNIDAD_COMPRA_OPS.keys()).index(uc_default),
            )
            unidad_compra = UNIDAD_COMPRA_OPS[unidad_compra_label]

            contenido_default = float(base.get("contenido_por_unidad_compra") or 1)
            contenido_por_unidad_compra = st.number_input(
                "Contenido por unidad de compra (ej: 1 caja = 100 unidades)",
                min_value=1.0,
                value=contenido_default if contenido_default >= 1 else 1.0,
                step=1.0,
            )

    # -------------------------
    # Precio
    # -------------------------
    with st.expander("💲 Precio", expanded=True):
        colP1, colP2 = st.columns(2)

        with colP1:
            moneda_actual = st.selectbox(
                "Moneda (precio actual)",
                MONEDAS,
                index=MONEDAS.index((base.get("moneda_actual") or "UYU")),
            )

            precio_actual_val = base.get("precio_actual")
            try:
                precio_actual_val = float(precio_actual_val) if precio_actual_val is not None else 0.0
            except Exception:
                precio_actual_val = 0.0

            precio_actual = st.number_input("Precio actual (referencia)", min_value=0.0, value=float(precio_actual_val), step=1.0)

            inv_pp = {v: k for k, v in PRECIO_POR_OPS.items()}
            pp_default = inv_pp.get(base.get("precio_por_actual") or "unidad_compra", "Por unidad de compra")
            precio_por_label = st.selectbox(
                "Precio actual es por",
                list(PRECIO_POR_OPS.keys()),
                index=list(PRECIO_POR_OPS.keys()).index(pp_default),
            )
            precio_por_actual = PRECIO_POR_OPS[precio_por_label]

            st.caption(f"Fecha último precio: {base.get('fecha_precio_actual') or '—'}")

        with colP2:
            st.markdown("**Último precio anterior (historial mínimo)**")
            st.write(f"Precio anterior: {base.get('precio_anterior') or '—'}")
            st.write(f"Moneda anterior: {base.get('moneda_anterior') or '—'}")
            st.write(f"Por anterior: {base.get('precio_por_anterior') or '—'}")
            st.write(f"Fecha anterior: {base.get('fecha_precio_anterior') or '—'}")

    # -------------------------
    # Guardar
    # -------------------------
    if not btn_save:
        return None

    if not nombre.strip():
        st.error("❌ Nombre es obligatorio")
        return None

    payload: Dict[str, Any] = {
        "tipo": tipo,
        "nombre": nombre.strip(),
        "descripcion": descripcion.strip() if descripcion else None,
        "codigo_interno": codigo_interno.strip() if codigo_interno else None,
        "codigo_barra": codigo_barra.strip() if codigo_barra else None,
        "familia": familia.strip() if familia else None,
        "subfamilia": subfamilia.strip() if subfamilia else None,
        "equipo": equipo.strip() if equipo else None,
        "proveedor_id": proveedor_id,

        "fifo": bool(fifo),
        "iva": iva,
        "tiene_lote": bool(tiene_lote),
        "requiere_vencimiento": bool(requiere_vencimiento),

        "unidad_base": unidad_base,
        "unidad_compra": unidad_compra,
        "contenido_por_unidad_compra": float(contenido_por_unidad_compra),

        "stock_min": float(stock_min),
        "stock_max": float(stock_max),

        "precio_actual": float(precio_actual),
        "moneda_actual": moneda_actual,
        "precio_por_actual": precio_por_actual,

        "activo": bool(activo),
    }

    if is_edit:
        payload["id"] = str(selected["id"])

    # Aplicar historial mínimo de precio (actual -> anterior) SOLO si cambia
    payload = _aplicar_historial_precio_minimo(payload, current_row)

    ok, msg, row = _sb_upsert_articulo(payload)
    if not ok:
        st.error(f"❌ No se pudo guardar: {msg}")
        return None

    _invalidate_caches()
    st.success(f"✅ {msg}")
    st.session_state["articulos_prefill"] = None

    # Devolver ID guardado
    if row and row.get("id"):
        return str(row["id"])
    if is_edit:
        return str(selected["id"])
    return None


def _ui_archivos(articulo_id: str):
    """
    UI para subir archivos (imágenes/manuales)
    """
    st.markdown("### 📎 Archivos (imágenes / manuales)")

    col1, col2 = st.columns(2)

    with col1:
        img = st.file_uploader("Subir imagen", type=["png", "jpg", "jpeg", "webp"], key=f"up_img_{articulo_id}")
        if st.button("⬆️ Subir imagen", key=f"btn_img_{articulo_id}", use_container_width=True):
            if img is None:
                st.error("❌ Seleccioná una imagen")
            else:
                raw = img.getvalue()
                ext = ""
                if "." in img.name:
                    ext = "." + img.name.split(".")[-1].lower().strip()
                path = f"{articulo_id}/imagen_{uuid.uuid4().hex}{ext}"
                ok, err = _sb_upload_storage(BUCKET_ARTICULOS, path, raw, getattr(img, "type", "") or "")
                if not ok:
                    st.error(f"❌ Error storage: {err}")
                else:
                    payload = {
                        "articulo_id": articulo_id,
                        "tipo": "imagen",
                        "nombre_archivo": img.name,
                        "storage_bucket": BUCKET_ARTICULOS,
                        "storage_path": path,
                        "mime_type": getattr(img, "type", None),
                        "size_bytes": len(raw),
                        "created_at": datetime.utcnow().isoformat(),
                    }
                    _sb_insert_archivo(payload)
                    st.success("✅ Imagen subida")

    with col2:
        pdf = st.file_uploader("Subir manual (PDF)", type=["pdf"], key=f"up_pdf_{articulo_id}")
        if st.button("⬆️ Subir manual", key=f"btn_pdf_{articulo_id}", use_container_width=True):
            if pdf is None:
                st.error("❌ Seleccioná un PDF")
            else:
                raw = pdf.getvalue()
                path = f"{articulo_id}/manual_{uuid.uuid4().hex}.pdf"
                ok, err = _sb_upload_storage(BUCKET_ARTICULOS, path, raw, getattr(pdf, "type", "") or "application/pdf")
                if not ok:
                    st.error(f"❌ Error storage: {err}")
                else:
                    payload = {
                        "articulo_id": articulo_id,
                        "tipo": "manual",
                        "nombre_archivo": pdf.name,
                        "storage_bucket": BUCKET_ARTICULOS,
                        "storage_path": path,
                        "mime_type": getattr(pdf, "type", None),
                        "size_bytes": len(raw),
                        "created_at": datetime.utcnow().isoformat(),
                    }
                    _sb_insert_archivo(payload)
                    st.success("✅ Manual subido")

    # Listado si existe tabla articulo_archivos
    try:
        df = _sb_select("articulo_archivos", "*", filters=[("articulo_id", "eq", articulo_id)])
        if not df.empty:
            st.dataframe(df[["tipo", "nombre_archivo", "storage_path", "created_at"]], use_container_width=True)
        else:
            st.caption("📭 Sin registros en articulo_archivos")
    except Exception:
        st.caption("⚠️ Tabla articulo_archivos no disponible (opcional)")


# =====================================================================
# FUNCIÓN PRINCIPAL DEL MÓDULO
# =====================================================================
def mostrar_articulos():
    """
    ✅ FUNCIÓN PRINCIPAL - Mejorada con mejor debugging
    """
    st.title("📚 Artículos")

    if "articulos_sel" not in st.session_state:
        st.session_state["articulos_sel"] = None

    if "articulos_busqueda" not in st.session_state:
        st.session_state["articulos_busqueda"] = ""

    # Selector de tipo (submenú)
    tipo_label = st.radio("Categoría", list(TIPOS.keys()), horizontal=True)
    tipo = TIPOS[tipo_label]

    # ✅ Clave segura para keys cuando tipo es None
    tipo_key = tipo if tipo else "todos"

    # Tabs para que no quede "desparramado"
    tab_listado, tab_form = st.tabs(["📋 Listado", "📝 Nuevo / Editar"])

    # -------------------------
    # TAB LISTADO
    # -------------------------
    with tab_listado:
        c1, c2 = st.columns([0.86, 0.14])
        with c1:
            filtro = st.text_input(
                "🔍 Buscar (nombre / códigos / familia / subfamilia / equipo)",
                key="articulos_busqueda",
                placeholder="Vacío = muestra todos",
            )
        with c2:
            if st.button("🧹 Limpiar", use_container_width=True, key=f"art_list_clear_{tipo_key}"):
                st.session_state["articulos_busqueda"] = ""
                st.rerun()

        if st.button("🔄 Recargar listado", use_container_width=True, key=f"art_list_reload_{tipo_key}"):
            _invalidate_caches()
            st.rerun()

        df = _cache_articulos_por_tipo(tipo)

        # Filtro local robusto (literal, no regex)
        if df is not None and not df.empty and (filtro or "").strip():
            t = (filtro or "").strip().lower()

            def _col_as_str(s: pd.Series) -> pd.Series:
                return s.fillna("").astype(str).str.lower()

            cols_busqueda = [
                "nombre",
                "codigo_interno",
                "codigo_barra",
                "familia",
                "subfamilia",
                "equipo",
                "unidad_base",
                "unidad_compra",
                "iva",
                "moneda_actual",
            ]

            mask = False
            for c in cols_busqueda:
                if c in df.columns:
                    mask = mask | _col_as_str(df[c]).str.contains(t, na=False, regex=False)

            df = df[mask].copy()

        selected_row = _grid(df)

        if selected_row and selected_row.get("id"):
            st.session_state["articulos_sel"] = {"id": selected_row["id"]}
            st.info("✅ Artículo seleccionado. Abrí la pestaña "Nuevo / Editar" para modificarlo.")

    # -------------------------
    # TAB FORM
    # -------------------------
    with tab_form:
        cA, cB = st.columns(2)
        with cA:
            if st.button("➕ Nuevo artículo", use_container_width=True, key=f"art_form_new_{tipo_key}"):
                st.session_state["articulos_sel"] = None
                st.rerun()
        with cB:
            if st.button("🔄 Recargar", use_container_width=True, key=f"art_form_reload_{tipo_key}"):
                _invalidate_caches()
                st.rerun()

        # Si estás en "Todos", el form necesita un tipo real para crear/editar
        tipo_form = tipo if tipo else "ingreso"

        saved_id = _form_articulo(tipo_form, st.session_state.get("articulos_sel"))

        if saved_id:
            st.session_state["articulos_sel"] = {"id": saved_id}
            st.markdown("---")
            _ui_archivos(saved_id)
        else:
            sel = st.session_state.get("articulos_sel")
            if sel and sel.get("id"):
                st.markdown("---")
                _ui_archivos(str(sel["id"]))
