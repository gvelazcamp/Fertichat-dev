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

try:
    from supabase_client import supabase
except ImportError:
    st.error("❌ No se pudo importar supabase_client. Verificá que el archivo exista.")
    supabase = None

# AgGrid opcional (si no está, cae a st.dataframe)
try:
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
    AGGRID_AVAILABLE = True
except ImportError:
    AGGRID_AVAILABLE = False
    AgGrid = None


# =====================================================================
# CONSTANTES
# =====================================================================
BUCKET_ARTICULOS = "articulos"

TIPOS = {
    "Todos": None,
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
# HELPERS SUPABASE
# =====================================================================
def _sb_select(
    table: str,
    columns: str = "*",
    filters: Optional[List[Tuple[str, str, Any]]] = None,
    order: Optional[Tuple[str, bool]] = None
) -> pd.DataFrame:
    """
    Select robusto con manejo de errores mejorado
    """
    if supabase is None:
        return pd.DataFrame()
    
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
        if ("42703" in msg) or ("does not exist" in msg.lower()) or ("undefined_column" in msg.lower()):
            pass
        else:
            return pd.DataFrame()

    # 2) Reintento sin order
    try:
        res = _build_query(filters, None).execute()
        data = getattr(res, "data", None) or []
        return pd.DataFrame(data)
    except Exception as e2:
        msg2 = str(e2) or ""
        if ("42703" in msg2) or ("does not exist" in msg2.lower()) or ("undefined_column" in msg2.lower()):
            pass
        else:
            return pd.DataFrame()

    # 3) Reintento sin filtros ni order
    try:
        res = _build_query(None, None).execute()
        data = getattr(res, "data", None) or []
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()


def _normalizar_articulos_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    ✅ MAPEO SIMPLIFICADO - Versión que funciona con tu estructura
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=ARTICULO_COLS)
    
    # Mapeo directo de columnas que sabemos que existen
    if "Id" in df.columns:
        df["id"] = df["Id"].astype(str)
    
    if "Descripción" in df.columns:
        df["nombre"] = df["Descripción"].fillna("").astype(str)
    else:
        df["nombre"] = ""
    
    if "Familia" in df.columns:
        df["familia"] = df["Familia"].fillna("").astype(str)
    else:
        df["familia"] = ""
    
    if "Código Int." in df.columns:
        df["codigo_interno"] = df["Código Int."].fillna("").astype(str)
    else:
        df["codigo_interno"] = ""
    
    if "Código Ext." in df.columns:
        df["codigo_barra"] = df["Código Ext."].fillna("").astype(str)
    else:
        df["codigo_barra"] = ""
    
    if "Unidad" in df.columns:
        df["unidad_base"] = df["Unidad"].fillna("unidad").astype(str)
    else:
        df["unidad_base"] = "unidad"
    
    if "Tipo Articulo" in df.columns:
        df["tipo"] = df["Tipo Articulo"].fillna("").astype(str)
    else:
        df["tipo"] = ""
    
    if "Activo" in df.columns:
        df["activo"] = df["Activo"].fillna(True).astype(bool)
    else:
        df["activo"] = True
    
    # Agregar resto de columnas que faltan con valores por defecto
    columnas_faltantes = {
        "descripcion": None,
        "subfamilia": None,
        "equipo": None,
        "proveedor_id": None,
        "fifo": True,
        "iva": "basico_22",
        "tiene_lote": False,
        "requiere_vencimiento": False,
        "unidad_compra": "unidad",
        "contenido_por_unidad_compra": 1.0,
        "stock_min": 0.0,
        "stock_max": 0.0,
        "precio_actual": None,
        "moneda_actual": None,
        "precio_por_actual": None,
        "fecha_precio_actual": None,
        "precio_anterior": None,
        "moneda_anterior": None,
        "precio_por_anterior": None,
        "fecha_precio_anterior": None,
        "created_at": None,
        "updated_at": None,
    }
    
    for col, valor_default in columnas_faltantes.items():
        if col not in df.columns:
            df[col] = valor_default
    
    # Retornar solo las columnas esperadas
    return df[ARTICULO_COLS].copy()
    
    # ========================================
    # CONVERSIÓN DE TIPOS
    # ========================================
    
    # ID como string
    if "id" in df.columns:
        df["id"] = df["id"].astype(str)
    
    # Booleanos con valores por defecto
    if "activo" in df.columns:
        df["activo"] = df["activo"].fillna(True).astype(bool)
    else:
        df["activo"] = True
    
    if "fifo" in df.columns:
        df["fifo"] = df["fifo"].fillna(True).astype(bool)
    else:
        df["fifo"] = True
        
    if "tiene_lote" in df.columns:
        df["tiene_lote"] = df["tiene_lote"].fillna(False).astype(bool)
    else:
        df["tiene_lote"] = False
        
    if "requiere_vencimiento" in df.columns:
        df["requiere_vencimiento"] = df["requiere_vencimiento"].fillna(False).astype(bool)
    else:
        df["requiere_vencimiento"] = False
    
    # Normalizar strings
    for col in ["nombre", "codigo_interno", "codigo_barra", "familia", "subfamilia", "equipo"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)
    
    # Normalizar tipo (puede venir como número o texto)
    if "tipo" in df.columns:
        df["tipo"] = df["tipo"].fillna("").astype(str).str.strip()
    
    # Valores por defecto para campos opcionales
    if df["unidad_base"].isna().all():
        df["unidad_base"] = "unidad"
    
    if df["unidad_compra"].isna().all():
        df["unidad_compra"] = "unidad"
    
    if df["contenido_por_unidad_compra"].isna().all():
        df["contenido_por_unidad_compra"] = 1.0
    
    if df["iva"].isna().all():
        df["iva"] = "basico_22"
    
    # Retornar solo las columnas esperadas
    return df[ARTICULO_COLS].copy()


def _sb_upsert_articulo(payload: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict]]:
    """
    Inserta o actualiza un artículo
    MAPEO INVERSO: columnas del módulo -> columnas de Supabase
    """
    if supabase is None:
        return False, "Supabase no disponible", None
    
    # ========================================
    # MAPEO INVERSO PARA GUARDAR
    # ========================================
    payload_db = {
        "Descripción": payload.get("nombre"),
        "Familia": payload.get("familia"),
        "Código Int.": payload.get("codigo_interno"),
        "Código Ext.": payload.get("codigo_barra"),
        "Unidad": payload.get("unidad_base"),
        "Tipo Articulo": payload.get("tipo"),
        "Activo": payload.get("activo"),
        "Stock Minimo": payload.get("stock_min"),
        "Stock Maximo": payload.get("stock_max"),
    }
    
    # Eliminar None values
    payload_db = {k: v for k, v in payload_db.items() if v is not None}
    
    try:
        if payload.get("id"):
            # UPDATE
            art_id = payload.get("id")
            
            res = supabase.table("articulos").update(payload_db).eq("Id", art_id).execute()
            data = getattr(res, "data", None) or []
            if data:
                return True, "Actualizado correctamente", data[0]
            return False, "No se encontró el artículo", None
        else:
            # INSERT
            res = supabase.table("articulos").insert(payload_db).execute()
            data = getattr(res, "data", None) or []
            if data:
                return True, "Creado correctamente", data[0]
            return False, "Error al crear", None
            
    except Exception as e:
        return False, f"Error: {str(e)}", None


def _sb_insert_archivo(payload: Dict[str, Any]) -> bool:
    """
    Inserta registro en articulo_archivos (opcional)
    """
    if supabase is None:
        return False
    
    try:
        supabase.table("articulo_archivos").insert(payload).execute()
        return True
    except Exception:
        return False


def _sb_upload_storage(bucket: str, path: str, data: bytes, mime_type: str) -> Tuple[bool, str]:
    """
    Sube archivo a Supabase Storage
    """
    if supabase is None:
        return False, "Supabase no disponible"
    
    try:
        supabase.storage.from_(bucket).upload(path, data, {"content-type": mime_type})
        return True, ""
    except Exception as e:
        return False, str(e)


# =====================================================================
# CACHE FUNCTIONS
# =====================================================================
@st.cache_data(ttl=30, show_spinner=False)
def _cache_proveedores() -> pd.DataFrame:
    """
    Cache de proveedores
    """
    try:
        df = _sb_select("proveedores", "id,nombre")
    except Exception:
        return pd.DataFrame(columns=["id", "nombre"])

    if df.empty:
        return df

    df["id"] = df["id"].astype(str)
    df["nombre"] = df["nombre"].astype(str)
    return df


@st.cache_data(ttl=30, show_spinner=False)
def _cache_articulos_por_tipo(tipo: Optional[str]) -> pd.DataFrame:
    """
    Cache de artículos filtrados por tipo
    """
    # Traer TODOS los datos
    df_raw = _sb_select("articulos", "*")

    # ========================================
    # 🔍 DEBUG TEMPORAL - Ver estructura real de la tabla
    # ========================================
    if df_raw is not None and not df_raw.empty:
        with st.sidebar:
            with st.expander("🔍 DEBUG - Estructura de tabla", expanded=False):
                st.write(f"**📊 Total registros:** {len(df_raw)}")
                st.write("**📋 Columnas en Supabase:**")
                st.code("\n".join(df_raw.columns.tolist()))
                st.write("**📄 Primer registro:**")
                st.json(df_raw.iloc[0].to_dict())
    # ========================================
    
    if df_raw is None or df_raw.empty:
        return pd.DataFrame(columns=ARTICULO_COLS)

    # Normalizar (mapea Descripción->nombre, etc)
    df = _normalizar_articulos_df(df_raw)
    
    # Filtro local por tipo si es necesario
    if tipo and not df.empty and "tipo" in df.columns:
        try:
            # Limpiar y normalizar valores
            df_copy = df.copy()
            df_copy["tipo_norm"] = df_copy["tipo"].fillna("").astype(str).str.strip().str.lower()
            
            # Caso 1: coincide texto directo
            df_tipo = df_copy[df_copy["tipo_norm"] == str(tipo).strip().lower()].copy()
            
            # Caso 2: mapeo numérico (si tu DB usa 1/2/3)
            if df_tipo.empty:
                map_num = {"ingreso": "1", "egreso": "2", "gasto_fijo": "3"}
                target = map_num.get(tipo)
                if target:
                    df_tipo = df_copy[df_copy["tipo_norm"] == target].copy()
            
            # Si encontró matches, usarlo
            if not df_tipo.empty:
                df = df_tipo.drop(columns=["tipo_norm"])
            
        except Exception:
            pass
    
    # Ordenar por nombre
    try:
        if "nombre" in df.columns and not df.empty:
            df = df.sort_values("nombre", kind="stable")
    except Exception:
        pass
    
    return df


def _invalidate_caches():
    """
    Invalida todos los caches
    """
    _cache_proveedores.clear()
    _cache_articulos_por_tipo.clear()


# =====================================================================
# LÓGICA DE PRECIO
# =====================================================================
def _aplicar_historial_precio_minimo(payload: Dict[str, Any], current_row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Maneja el historial de precios (actual -> anterior)
    """
    if not current_row:
        if payload.get("precio_actual") is not None and payload.get("moneda_actual") and payload.get("precio_por_actual"):
            payload["fecha_precio_actual"] = datetime.utcnow().isoformat()
        return payload

    cur_precio = current_row.get("precio_actual")
    cur_mon = current_row.get("moneda_actual")
    cur_por = current_row.get("precio_por_actual")
    cur_fecha = current_row.get("fecha_precio_actual")

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
        payload["precio_anterior"] = cur_precio_n
        payload["moneda_anterior"] = cur_mon
        payload["precio_por_anterior"] = cur_por
        payload["fecha_precio_anterior"] = cur_fecha
        payload["fecha_precio_actual"] = datetime.utcnow().isoformat()

    return payload


# =====================================================================
# UI COMPONENTS
# =====================================================================
def _grid(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Muestra grid de artículos
    """
    if df is None or df.empty:
        st.info("📭 Sin artículos para mostrar")
        return None

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
    
    for c in view_cols:
        if c not in df.columns:
            df[c] = None

    vdf = df[view_cols].copy()
    st.caption(f"📊 Mostrando {len(vdf)} artículo(s)")

    if not AGGRID_AVAILABLE:
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
    """
    Selector de proveedor
    """
    dfp = _cache_proveedores()
    if dfp.empty:
        st.caption("⚠️ Sin proveedores disponibles")
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
    Formulario de artículo
    """
    is_edit = bool(selected and selected.get("id"))
    st.subheader("✏️ Editar artículo" if is_edit else "➕ Nuevo artículo")

    current_row = None
    if is_edit:
        df_all = _cache_articulos_por_tipo(None)  # Traer todos para buscar por ID
        match = df_all[df_all["id"].astype(str) == str(selected["id"])]
        if not match.empty:
            current_row = match.iloc[0].to_dict()

    prefill = st.session_state.get("articulos_prefill") if not is_edit else None
    base = current_row or prefill or {}

    # Botones
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

    # Datos generales
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

            inv_iva = {v: k for k, v in IVA_OPS.items()}
            iva_default = inv_iva.get(base.get("iva") or "basico_22", "Básico (22%)")
            iva_label = st.selectbox("IVA", list(IVA_OPS.keys()), index=list(IVA_OPS.keys()).index(iva_default))
            iva = IVA_OPS[iva_label]

            tiene_lote = st.checkbox("Tiene lote", value=bool(base.get("tiene_lote", False)))
            requiere_vencimiento = st.checkbox("Requiere vencimiento", value=bool(base.get("requiere_vencimiento", False)))

    # Unidades y stock
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
                "Contenido por unidad de compra",
                min_value=1.0,
                value=max(contenido_default, 1.0),
                step=1.0,
            )

    # Precio
    with st.expander("💲 Precio", expanded=True):
        colP1, colP2 = st.columns(2)

        with colP1:
            moneda_actual = st.selectbox(
                "Moneda",
                MONEDAS,
                index=MONEDAS.index(base.get("moneda_actual") or "UYU"),
            )

            try:
                precio_actual_val = float(base.get("precio_actual") or 0)
            except Exception:
                precio_actual_val = 0.0

            precio_actual = st.number_input("Precio actual", min_value=0.0, value=precio_actual_val, step=1.0)

            inv_pp = {v: k for k, v in PRECIO_POR_OPS.items()}
            pp_default = inv_pp.get(base.get("precio_por_actual") or "unidad_compra", "Por unidad de compra")
            precio_por_label = st.selectbox(
                "Precio es por",
                list(PRECIO_POR_OPS.keys()),
                index=list(PRECIO_POR_OPS.keys()).index(pp_default),
            )
            precio_por_actual = PRECIO_POR_OPS[precio_por_label]

            st.caption(f"Fecha: {base.get('fecha_precio_actual') or '—'}")

        with colP2:
            st.markdown("**Precio anterior**")
            st.write(f"Precio: {base.get('precio_anterior') or '—'}")
            st.write(f"Moneda: {base.get('moneda_anterior') or '—'}")
            st.write(f"Por: {base.get('precio_por_anterior') or '—'}")
            st.write(f"Fecha: {base.get('fecha_precio_anterior') or '—'}")

    # Guardar
    if not btn_save:
        return None

    if not nombre.strip():
        st.error("❌ Nombre es obligatorio")
        return None

    payload = {
        "tipo": tipo,
        "nombre": nombre.strip(),
        "descripcion": descripcion.strip() or None,
        "codigo_interno": codigo_interno.strip() or None,
        "codigo_barra": codigo_barra.strip() or None,
        "familia": familia.strip() or None,
        "subfamilia": subfamilia.strip() or None,
        "equipo": equipo.strip() or None,
        "proveedor_id": proveedor_id,
        "fifo": fifo,
        "iva": iva,
        "tiene_lote": tiene_lote,
        "requiere_vencimiento": requiere_vencimiento,
        "unidad_base": unidad_base,
        "unidad_compra": unidad_compra,
        "contenido_por_unidad_compra": float(contenido_por_unidad_compra),
        "stock_min": float(stock_min),
        "stock_max": float(stock_max),
        "precio_actual": float(precio_actual),
        "moneda_actual": moneda_actual,
        "precio_por_actual": precio_por_actual,
        "activo": activo,
    }

    if is_edit:
        payload["id"] = str(selected["id"])

    payload = _aplicar_historial_precio_minimo(payload, current_row)

    ok, msg, row = _sb_upsert_articulo(payload)
    if not ok:
        st.error(f"❌ {msg}")
        return None

    _invalidate_caches()
    st.success(f"✅ {msg}")
    st.session_state["articulos_prefill"] = None

    if row and row.get("Id"):
        return str(row["Id"])
    if is_edit:
        return str(selected["id"])
    return None


def _ui_archivos(articulo_id: str):
    """
    UI para archivos
    """
    st.markdown("### 📎 Archivos")

    col1, col2 = st.columns(2)

    with col1:
        img = st.file_uploader("Imagen", type=["png", "jpg", "jpeg", "webp"], key=f"up_img_{articulo_id}")
        if st.button("⬆️ Subir imagen", key=f"btn_img_{articulo_id}", use_container_width=True):
            if not img:
                st.error("❌ Seleccioná una imagen")
            else:
                raw = img.getvalue()
                ext = "." + img.name.split(".")[-1].lower() if "." in img.name else ""
                path = f"{articulo_id}/imagen_{uuid.uuid4().hex}{ext}"
                ok, err = _sb_upload_storage(BUCKET_ARTICULOS, path, raw, getattr(img, "type", "") or "")
                if not ok:
                    st.error(f"❌ {err}")
                else:
                    _sb_insert_archivo({
                        "articulo_id": articulo_id,
                        "tipo": "imagen",
                        "nombre_archivo": img.name,
                        "storage_bucket": BUCKET_ARTICULOS,
                        "storage_path": path,
                        "mime_type": getattr(img, "type", None),
                        "size_bytes": len(raw),
                        "created_at": datetime.utcnow().isoformat(),
                    })
                    st.success("✅ Subida")

    with col2:
        pdf = st.file_uploader("Manual PDF", type=["pdf"], key=f"up_pdf_{articulo_id}")
        if st.button("⬆️ Subir manual", key=f"btn_pdf_{articulo_id}", use_container_width=True):
            if not pdf:
                st.error("❌ Seleccioná un PDF")
            else:
                raw = pdf.getvalue()
                path = f"{articulo_id}/manual_{uuid.uuid4().hex}.pdf"
                ok, err = _sb_upload_storage(BUCKET_ARTICULOS, path, raw, "application/pdf")
                if not ok:
                    st.error(f"❌ {err}")
                else:
                    _sb_insert_archivo({
                        "articulo_id": articulo_id,
                        "tipo": "manual",
                        "nombre_archivo": pdf.name,
                        "storage_bucket": BUCKET_ARTICULOS,
                        "storage_path": path,
                        "mime_type": "application/pdf",
                        "size_bytes": len(raw),
                        "created_at": datetime.utcnow().isoformat(),
                    })
                    st.success("✅ Subido")

    try:
        df = _sb_select("articulo_archivos", "*", filters=[("articulo_id", "eq", articulo_id)])
        if not df.empty:
            st.dataframe(df[["tipo", "nombre_archivo", "created_at"]], use_container_width=True)
    except Exception:
        pass


# =====================================================================
# FUNCIÓN PRINCIPAL
# =====================================================================
def mostrar_articulos():
    """
    Función principal del módulo
    """
    st.title("📚 Artículos")

    if "articulos_sel" not in st.session_state:
        st.session_state["articulos_sel"] = None

    if "articulos_busqueda" not in st.session_state:
        st.session_state["articulos_busqueda"] = ""

    tipo_label = st.radio("Categoría", list(TIPOS.keys()), horizontal=True)
    tipo = TIPOS[tipo_label]
    tipo_key = tipo if tipo else "todos"

    tab_listado, tab_form = st.tabs(["📋 Listado", "📝 Nuevo / Editar"])

    with tab_listado:
        c1, c2 = st.columns([0.86, 0.14])
        with c1:
            filtro = st.text_input(
                "🔍 Buscar",
                key="articulos_busqueda",
                placeholder="nombre, códigos, familia...",
            )
        with c2:
            if st.button("🧹", use_container_width=True, key=f"clear_{tipo_key}"):
                st.session_state["articulos_busqueda"] = ""
                st.rerun()

        if st.button("🔄 Recargar", use_container_width=True, key=f"reload_{tipo_key}"):
            _invalidate_caches()
            st.rerun()

        df = _cache_articulos_por_tipo(tipo)

        if df is not None and not df.empty and filtro.strip():
            t = filtro.strip().lower()
            cols = ["nombre", "codigo_interno", "codigo_barra", "familia", "subfamilia", "equipo"]
            mask = False
            for c in cols:
                if c in df.columns:
                    mask = mask | df[c].fillna("").astype(str).str.lower().str.contains(t, na=False, regex=False)
            df = df[mask].copy()

        selected_row = _grid(df)

        if selected_row and selected_row.get("id"):
            st.session_state["articulos_sel"] = {"id": selected_row["id"]}
            st.info("✅ Seleccionado. Abrí la pestaña 'Nuevo / Editar'")

    with tab_form:
        cA, cB = st.columns(2)
        with cA:
            if st.button("➕ Nuevo", use_container_width=True, key=f"new_{tipo_key}"):
                st.session_state["articulos_sel"] = None
                st.rerun()
        with cB:
            if st.button("🔄 Recargar", use_container_width=True, key=f"reload2_{tipo_key}"):
                _invalidate_caches()
                st.rerun()

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

