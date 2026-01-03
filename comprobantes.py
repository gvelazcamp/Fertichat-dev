# =====================================================================
# 📑 MÓDULO COMPROBANTES - FERTI CHAT
# Archivo: comprobantes.py
# =====================================================================

import streamlit as st
import pandas as pd
from datetime import date
from typing import Optional, Dict, Any, List

from supabase_client import supabase

# =====================================================================
# CONFIG
# =====================================================================

DEPOSITOS = ["Casa Central", "ANDA", "Platinum"]


# =====================================================================
# HELPERS (NO ROMPEN LO EXISTENTE)
# =====================================================================

def _safe_float(x) -> float:
    try:
        if x is None:
            return 0.0
        s = str(x).strip().replace(".", "").replace(",", ".")
        if s == "":
            return 0.0
        return float(s)
    except Exception:
        try:
            return float(x)
        except Exception:
            return 0.0


def _to_date_safe(x) -> Optional[date]:
    if x is None:
        return None
    s = str(x).strip()
    if s == "":
        return None
    try:
        d = pd.to_datetime(s, dayfirst=True, errors="coerce")
        if pd.isna(d):
            return None
        return d.date()
    except Exception:
        return None


def _fmt_lote_row(lote: str, venc: str, stock: str) -> str:
    lote_s = (lote or "").strip()
    venc_s = (venc or "").strip()
    stk = _safe_float(stock)
    lote_txt = lote_s if lote_s else "(sin lote)"
    venc_txt = venc_s if venc_s else "(sin venc.)"
    return f"{lote_txt} | {venc_txt} | Stock: {stk:g}"


def _fetch_all_table(table_name: str, page_size: int = 1000, max_pages: int = 50) -> pd.DataFrame:
    """
    Trae todas las filas paginando con range().
    Evita depender de nombres raros de columnas (articulos tiene columnas con espacios/acentos).
    """
    rows: List[Dict[str, Any]] = []
    for i in range(max_pages):
        start = i * page_size
        end = start + page_size - 1
        resp = supabase.table(table_name).select("*").range(start, end).execute()
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def _cache_articulos() -> pd.DataFrame:
    return _fetch_all_table("articulos")


@st.cache_data(ttl=120)
def _cache_stock() -> pd.DataFrame:
    return _fetch_all_table("stock")


def _articulos_preparados() -> pd.DataFrame:
    """
    Devuelve df con columnas: _id, _codigo_int, _desc, _familia
    usando los nombres reales que existan en Supabase.
    """
    df = _cache_articulos()
    if df.empty:
        return df

    cols = list(df.columns)

    def pick_col(prefer: List[str]) -> Optional[str]:
        for c in prefer:
            if c in cols:
                return c
        return None

    col_id = pick_col(["Id", "id", "ID"])
    col_desc = pick_col(["Descripción", "Descripcion", "descripcion", "ARTICULO", "Articulo", "articulo", "Nombre", "nombre"])
    col_fam = pick_col(["Familia", "FAMILIA", "familia"])
    col_cod_int = pick_col(["Código Int.", "Codigo Int.", "Código Int", "Codigo Int", "codigo_int", "CODIGO_INT", "codigo interno", "CODIGO"])

    # Si no encuentra, igual intenta seguir con lo que haya
    if col_id is None:
        # fallback: primer columna
        col_id = cols[0]

    out = pd.DataFrame()
    out["_id"] = df[col_id].astype(str)

    out["_desc"] = df[col_desc].astype(str) if col_desc else ""
    out["_familia"] = df[col_fam].astype(str) if col_fam else ""
    out["_codigo_int"] = df[col_cod_int].astype(str) if col_cod_int else ""

    # limpieza
    out["_desc"] = out["_desc"].fillna("").astype(str)
    out["_familia"] = out["_familia"].fillna("").astype(str)
    out["_codigo_int"] = out["_codigo_int"].fillna("").astype(str)

    return out


def _stock_preparado() -> pd.DataFrame:
    """
    stock: columnas esperadas (según tu tabla): FAMILIA, CODIGO, ARTICULO, DEPOSITO, LOTE, VENCIMIENTO, STOCK
    """
    df = _cache_stock()
    if df.empty:
        return df

    # aseguramos columnas (por si vinieran en minúsculas)
    ren = {}
    for c in df.columns:
        cu = str(c).upper()
        if cu in ["FAMILIA", "CODIGO", "ARTICULO", "DEPOSITO", "LOTE", "VENCIMIENTO", "STOCK"]:
            ren[c] = cu
    df = df.rename(columns=ren)

    for need in ["FAMILIA", "CODIGO", "ARTICULO", "DEPOSITO", "LOTE", "VENCIMIENTO", "STOCK"]:
        if need not in df.columns:
            df[need] = ""

    # estandariza nulos
    for c in ["FAMILIA", "CODIGO", "ARTICULO", "DEPOSITO", "LOTE", "VENCIMIENTO", "STOCK"]:
        df[c] = df[c].fillna("").astype(str)

    return df


def _upsert_stock_row(
    deposito: str,
    familia: str,
    codigo: str,
    articulo: str,
    lote: str,
    vencimiento: str,
    delta_stock: float,
) -> None:
    """
    Inserta o actualiza en stock sumando delta_stock (puede ser + o -).
    Detecta nombres reales de columnas en Supabase (mayúsculas/acentos) para evitar APIError.
    """

    def _norm(s: str) -> str:
        if s is None:
            return ""
        s = str(s).strip().lower()
        # quitar acentos básico
        s = (s.replace("á", "a").replace("é", "e").replace("í", "i")
               .replace("ó", "o").replace("ú", "u").replace("ñ", "n"))
        # dejar solo alfanum
        out = []
        for ch in s:
            if ch.isalnum():
                out.append(ch)
        return "".join(out)

    # -------------------------
    # Resolver mapeo de columnas reales (una vez por sesión)
    # -------------------------
    if "_stock_colmap" not in st.session_state:
        keys: List[str] = []
        try:
            sample = supabase.table("stock").select("*").limit(1).execute().data or []
            if sample:
                keys = list(sample[0].keys())
        except Exception:
            keys = []

        nk = {_norm(k): k for k in keys}

        def resolve(logical: str, candidates: List[str]) -> str:
            # match exacto
            for c in candidates:
                if c in keys:
                    return c
            # match normalizado
            for c in candidates:
                nc = _norm(c)
                if nc in nk:
                    return nk[nc]
            # fallback: probar logical tal cual
            return logical

        st.session_state["_stock_colmap"] = {
            "FAMILIA": resolve("FAMILIA", ["FAMILIA", "familia", "Familia"]),
            "CODIGO": resolve("CODIGO", ["CODIGO", "codigo", "Código", "Codigo"]),
            "ARTICULO": resolve("ARTICULO", ["ARTICULO", "articulo", "Artículo", "Articulo"]),
            "DEPOSITO": resolve("DEPOSITO", ["DEPOSITO", "deposito", "Depósito", "Deposito"]),
            "LOTE": resolve("LOTE", ["LOTE", "lote", "Lote"]),
            "VENCIMIENTO": resolve("VENCIMIENTO", ["VENCIMIENTO", "vencimiento", "Vencimiento"]),
            "STOCK": resolve("STOCK", ["STOCK", "stock", "Stock"]),
        }

    colmap = st.session_state["_stock_colmap"]

    cFAM = colmap["FAMILIA"]
    cCOD = colmap["CODIGO"]
    cART = colmap["ARTICULO"]
    cDEP = colmap["DEPOSITO"]
    cLOT = colmap["LOTE"]
    cVEN = colmap["VENCIMIENTO"]
    cSTK = colmap["STOCK"]

    lote_val = (lote or "").strip()
    venc_val = (vencimiento or "").strip()

    # -------------------------
    # Buscar fila existente (si existe)
    # -------------------------
    try:
        q = (
            supabase.table("stock")
            .select("*")
            .eq(cDEP, deposito)
            .eq(cCOD, codigo)
            .eq(cLOT, lote_val)
            .eq(cVEN, venc_val)
        )
        resp = q.execute()
        rows = resp.data or []
    except Exception as e:
        raise Exception(
            "Error consultando 'stock' en Supabase. "
            "Probable: nombres de columnas distintos o RLS bloqueando SELECT. "
            f"Detalle: {e}"
        ) from e

    # -------------------------
    # Update o Insert
    # -------------------------
    if rows:
        try:
            current = _safe_float(rows[0].get(cSTK, "0"))
            new_val = current + float(delta_stock)
            if new_val < 0:
                new_val = 0.0

            supabase.table("stock").update(
                {
                    cFAM: familia,
                    cART: articulo,
                    cSTK: new_val,
                }
            ).eq(cDEP, deposito).eq(cCOD, codigo).eq(cLOT, lote_val).eq(cVEN, venc_val).execute()

        except Exception as e:
            raise Exception(
                "Error actualizando 'stock' en Supabase. "
                "Probable: RLS bloqueando UPDATE o tipos/columnas no coinciden. "
                f"Detalle: {e}"
            ) from e

    else:
        # si delta es negativo y no existe fila, no insertamos
        if float(delta_stock) <= 0:
            return

        try:
            supabase.table("stock").insert(
                {
                    cFAM: familia,
                    cCOD: codigo,
                    cART: articulo,
                    cDEP: deposito,
                    cLOT: lote_val,
                    cVEN: venc_val,
                    cSTK: float(delta_stock),
                }
            ).execute()
        except Exception as e:
            raise Exception(
                "Error insertando en 'stock' en Supabase. "
                "Probable: RLS bloqueando INSERT o columnas NOT NULL faltantes. "
                f"Detalle: {e}"
            ) from e

    # refresca cache
    _cache_stock.clear()


# =====================================================================
# UI: COMPONENTE FILTRO ARTÍCULOS (DESDE TABLA ARTICULOS)
# =====================================================================

def _selector_articulo_articulos(row_idx: int, df_art: pd.DataFrame) -> Optional[Dict[str, str]]:
    """
    Selector por Id desde 'articulos' con búsqueda por código interno o descripción.
    Devuelve dict: {id, codigo_int, desc, familia} o None.
    """
    if df_art.empty:
        st.warning("No hay artículos en Supabase (tabla articulos vacía).")
        return None

    buscar = st.text_input(
        "Buscar (código interno o descripción)",
        key=f"alta_buscar_{row_idx}",
        placeholder="Ej: 12345 o 'tubo'...",
    ).strip().lower()

    tmp = df_art.copy()
    if buscar:
        tmp = tmp[
            tmp["_codigo_int"].str.lower().str.contains(buscar, na=False)
            | tmp["_desc"].str.lower().str.contains(buscar, na=False)
        ].head(50)
    else:
        tmp = tmp.head(50)

    # Siempre incluir el seleccionado actual si existe, para no romper el selectbox
    current_id = st.session_state.get(f"alta_art_id_{row_idx}", "")
    if current_id:
        if not (tmp["_id"] == str(current_id)).any():
            cur_row = df_art[df_art["_id"] == str(current_id)]
            if not cur_row.empty:
                tmp = pd.concat([cur_row, tmp], ignore_index=True)

    options = tmp["_id"].astype(str).tolist()
    if not options:
        st.info("Sin resultados para esa búsqueda.")
        return None

    label_map = {}
    for _, r in tmp.iterrows():
        cod = (r["_codigo_int"] or "").strip()
        desc = (r["_desc"] or "").strip()
        fam = (r["_familia"] or "").strip()
        cod_txt = cod if cod else "(sin código int.)"
        fam_txt = f" | {fam}" if fam else ""
        label_map[str(r["_id"])] = f"{cod_txt} - {desc}{fam_txt}"

    sel = st.selectbox(
        "Artículo",
        options=options,
        index=options.index(str(current_id)) if str(current_id) in options else 0,
        format_func=lambda x: label_map.get(str(x), str(x)),
        key=f"alta_art_id_{row_idx}",
    )

    row = df_art[df_art["_id"] == str(sel)]
    if row.empty:
        return None

    r0 = row.iloc[0]
    return {
        "id": str(r0["_id"]),
        "codigo_int": str(r0["_codigo_int"] or "").strip(),
        "desc": str(r0["_desc"] or "").strip(),
        "familia": str(r0["_familia"] or "").strip(),
    }


# =====================================================================
# ALTA DE STOCK (DESDE ARTICULOS)
# =====================================================================

def mostrar_comprobante_alta_stock():
    st.subheader("⬆️ Alta de stock")

    deposito_destino = st.selectbox(
        "Depósito destino",
        DEPOSITOS,
        key="alta_deposito_destino",
    )

    df_art = _articulos_preparados()

    if "alta_items_count" not in st.session_state:
        st.session_state.alta_items_count = 1

    col_add, col_clear = st.columns([1, 1])
    with col_add:
        if st.button("➕ Agregar línea", use_container_width=True, key="alta_add_line"):
            st.session_state.alta_items_count += 1
    with col_clear:
        if st.button("🧹 Limpiar líneas", use_container_width=True, key="alta_clear_lines"):
            st.session_state.alta_items_count = 1
            # No borramos keys a la fuerza para no romper Streamlit; solo reducimos count

    st.markdown("### Artículos")

    items_to_process: List[Dict[str, Any]] = []

    for i in range(int(st.session_state.alta_items_count)):
        with st.container(border=True):
            top = st.columns([5, 1])
            with top[0]:
                st.markdown(f"**Línea #{i + 1}**")
            with top[1]:
                if st.button("🗑️", key=f"alta_del_{i}", help="Eliminar esta línea"):
                    # Re-armado simple: decrementa count y mueve el último sobre este
                    if st.session_state.alta_items_count > 1:
                        st.session_state.alta_items_count -= 1
                        st.rerun()

            art = _selector_articulo_articulos(i, df_art)

            usa_lote = st.checkbox(
                "Este artículo usa Lote y Vencimiento",
                value=bool(st.session_state.get(f"alta_usa_lote_{i}", False)),
                key=f"alta_usa_lote_{i}",
            )

            c1, c2, c3 = st.columns(3)
            with c1:
                cantidad = st.number_input(
                    "Cantidad",
                    min_value=0.0,
                    step=1.0,
                    value=float(st.session_state.get(f"alta_cant_{i}", 0.0)),
                    key=f"alta_cant_{i}",
                )
            with c2:
                precio = st.number_input(
                    "Precio unitario (obligatorio para FIFO)",
                    min_value=0.0,
                    step=0.01,
                    value=float(st.session_state.get(f"alta_precio_{i}", 0.0)),
                    key=f"alta_precio_{i}",
                )
            with c3:
                st.caption("")

            lote_val = ""
            venc_val = ""

            if usa_lote:
                c4, c5 = st.columns(2)
                with c4:
                    lote_val = st.text_input(
                        "Lote",
                        value=str(st.session_state.get(f"alta_lote_{i}", "")),
                        key=f"alta_lote_{i}",
                    ).strip()
                with c5:
                    venc_date = st.date_input(
                        "Vencimiento",
                        value=st.session_state.get(f"alta_venc_{i}", None),
                        key=f"alta_venc_{i}",
                    )
                    if venc_date:
                        venc_val = venc_date.isoformat()

            items_to_process.append(
                {
                    "art": art,
                    "cantidad": float(cantidad),
                    "precio": float(precio),
                    "usa_lote": bool(usa_lote),
                    "lote": lote_val,
                    "venc": venc_val,
                }
            )

    st.markdown("---")

    if st.button("✅ Confirmar alta", use_container_width=True, key="alta_confirmar"):
        errores = []
        for idx, it in enumerate(items_to_process, start=1):
            if not it["art"]:
                errores.append(f"Línea #{idx}: falta seleccionar artículo.")
                continue
            if it["cantidad"] <= 0:
                errores.append(f"Línea #{idx}: cantidad debe ser > 0.")
            # Precio “siempre”: dejo pasar 0 pero avisamos (por si querés cargar sin costo)
            if it["precio"] <= 0:
                errores.append(f"Línea #{idx}: precio debe ser > 0 (lo pediste como obligatorio para FIFO).")
            if it["usa_lote"]:
                if (it["lote"] or "").strip() == "":
                    errores.append(f"Línea #{idx}: marcaste lote/vencimiento pero falta Lote.")
                if (it["venc"] or "").strip() == "":
                    errores.append(f"Línea #{idx}: marcaste lote/vencimiento pero falta Vencimiento.")

        if errores:
            st.error("No se puede confirmar:\n- " + "\n- ".join(errores))
            return

        ok = 0
        for it in items_to_process:
            art = it["art"]
            if not art:
                continue

            codigo = art.get("codigo_int", "").strip()
            desc = art.get("desc", "").strip()
            fam = art.get("familia", "").strip()

            if codigo == "":
                # si no hay código interno, usamos el Id como código “de sistema”
                codigo = f"ID:{art.get('id', '')}"

            lote = it["lote"] if it["usa_lote"] else ""
            venc = it["venc"] if it["usa_lote"] else ""

            # Alta impacta en stock (cantidad)
            _upsert_stock_row(
                deposito=deposito_destino,
                familia=fam,
                codigo=codigo,
                articulo=desc,
                lote=lote,
                vencimiento=venc,
                delta_stock=float(it["cantidad"]),
            )

            ok += 1

        st.success(f"Alta confirmada. Líneas procesadas: {ok}")
        st.info("Nota: el precio se está capturando en la UI (obligatorio), pero tu tabla 'stock' no tiene columna de precio. "
                "Cuando definas dónde persistir el precio (tabla de movimientos / comprobantes / costo por lote), lo conectamos sin cambiar esta lógica.")


# =====================================================================
# BAJA DE STOCK (DESDE STOCK)
# =====================================================================

def mostrar_comprobante_baja_stock():
    st.subheader("⬇️ Baja de stock")

    deposito_origen = st.selectbox(
        "Depósito origen",
        DEPOSITOS,
        key="baja_deposito_origen",
    )

    motivo = st.selectbox(
        "Motivo de baja",
        ["Salida no declarada", "Rotura", "Pérdida", "Recuento", "Otro"],
        key="baja_motivo",
    )

    df_stock = _stock_preparado()
    df_dep = df_stock[df_stock["DEPOSITO"] == deposito_origen].copy()

    if df_dep.empty:
        st.info("No hay stock para ese depósito.")
        return

    # Selector de artículo por CODIGO / ARTICULO
    buscar = st.text_input(
        "Buscar (código interno o artículo)",
        key="baja_buscar",
        placeholder="Ej: 12345 o 'tubo'...",
    ).strip().lower()

    df_art = df_dep[["CODIGO", "ARTICULO", "FAMILIA"]].drop_duplicates().copy()
    if buscar:
        df_art = df_art[
            df_art["CODIGO"].str.lower().str.contains(buscar, na=False)
            | df_art["ARTICULO"].str.lower().str.contains(buscar, na=False)
        ].head(50)
    else:
        df_art = df_art.head(50)

    if df_art.empty:
        st.info("Sin resultados para esa búsqueda.")
        return

    options = df_art["CODIGO"].astype(str).tolist()
    label_map = {r["CODIGO"]: f'{r["CODIGO"]} - {r["ARTICULO"]} | {r["FAMILIA"]}' for _, r in df_art.iterrows()}

    cod_sel = st.selectbox(
        "Artículo (desde stock)",
        options=options,
        format_func=lambda x: label_map.get(str(x), str(x)),
        key="baja_codigo_sel",
    )

    df_lotes = df_dep[df_dep["CODIGO"].astype(str) == str(cod_sel)].copy()
    if df_lotes.empty:
        st.warning("No se encontró stock para ese código en este depósito.")
        return

    # Determina si tiene lote/venc
    has_lote = ((df_lotes["LOTE"].astype(str).str.strip() != "") | (df_lotes["VENCIMIENTO"].astype(str).str.strip() != "")).any()

    # Orden FIFO por vencimiento (más viejo = vencimiento más cercano / menor fecha)
    df_lotes["_vdate"] = df_lotes["VENCIMIENTO"].apply(_to_date_safe)
    df_lotes["_v_sort"] = df_lotes["_vdate"].apply(lambda d: d if d else date(2100, 1, 1))
    df_lotes = df_lotes.sort_values(by=["_v_sort", "LOTE"], ascending=[True, True]).reset_index(drop=True)

    modo = st.radio(
        "Selección de lote",
        ["FIFO (más viejo)", "Más nuevo", "Elegir manual"],
        horizontal=True,
        key="baja_modo_lote",
    )

    chosen_idx = 0
    if modo == "FIFO (más viejo)":
        chosen_idx = 0
    elif modo == "Más nuevo":
        chosen_idx = len(df_lotes) - 1
    else:
        # manual
        idx_opt = list(range(len(df_lotes)))
        chosen_idx = st.selectbox(
            "Elegir lote",
            options=idx_opt,
            format_func=lambda ix: _fmt_lote_row(
                df_lotes.loc[ix, "LOTE"],
                df_lotes.loc[ix, "VENCIMIENTO"],
                df_lotes.loc[ix, "STOCK"],
            ),
            key="baja_lote_manual_idx",
        )

    chosen = df_lotes.loc[int(chosen_idx)]
    stock_actual = _safe_float(chosen.get("STOCK", "0"))

    st.markdown("#### Lote seleccionado")
    if has_lote:
        st.write(_fmt_lote_row(chosen.get("LOTE", ""), chosen.get("VENCIMIENTO", ""), chosen.get("STOCK", "")))
    else:
        st.write(f'Stock disponible: {stock_actual:g} (sin lote/vencimiento)')

    # Alerta si elige "más nuevo" y existe uno más viejo
    requiere_confirm = False
    if modo == "Más nuevo" and len(df_lotes) > 1:
        requiere_confirm = True
        st.warning("Estás eligiendo el lote MÁS NUEVO, pero existe un lote más viejo (FIFO).")
        confirmar = st.checkbox(
            "Sí, estoy seguro: quiero bajar el lote más nuevo",
            key="baja_confirm_no_fifo",
        )
        if not confirmar:
            st.info("Para continuar, confirmá la excepción FIFO.")
            st.stop()

    cant = st.number_input(
        "Cantidad a dar de baja",
        min_value=0.0,
        max_value=float(stock_actual) if stock_actual > 0 else 0.0,
        step=1.0,
        value=0.0,
        key="baja_cantidad",
    )

    if st.button("✅ Confirmar baja", use_container_width=True, key="baja_confirmar"):
        if cant <= 0:
            st.error("La cantidad debe ser > 0.")
            return
        if cant > stock_actual:
            st.error("No podés bajar más que el stock disponible.")
            return

        delta = -float(cant)

        _upsert_stock_row(
            deposito=deposito_origen,
            familia=str(chosen.get("FAMILIA", "") or ""),
            codigo=str(chosen.get("CODIGO", "") or ""),
            articulo=str(chosen.get("ARTICULO", "") or ""),
            lote=str(chosen.get("LOTE", "") or ""),
            vencimiento=str(chosen.get("VENCIMIENTO", "") or ""),
            delta_stock=delta,
        )

        st.success("Baja confirmada y aplicada a stock.")


# =====================================================================
# MOVIMIENTO ENTRE DEPÓSITOS (DESDE STOCK)
# =====================================================================

def mostrar_comprobante_movimiento():
    st.subheader("🔁 Movimiento entre depósitos")

    col1, col2 = st.columns(2)

    with col1:
        deposito_origen = st.selectbox(
            "Depósito origen",
            DEPOSITOS,
            key="mov_deposito_origen",
        )

    with col2:
        deposito_destino = st.selectbox(
            "Depósito destino",
            DEPOSITOS,
            key="mov_deposito_destino",
        )

    if deposito_origen == deposito_destino:
        st.warning("El depósito destino debe ser distinto al origen.")
        return

    df_stock = _stock_preparado()
    df_dep = df_stock[df_stock["DEPOSITO"] == deposito_origen].copy()

    if df_dep.empty:
        st.info("No hay stock para el depósito origen.")
        return

    buscar = st.text_input(
        "Buscar (código interno o artículo)",
        key="mov_buscar",
        placeholder="Ej: 12345 o 'tubo'...",
    ).strip().lower()

    df_art = df_dep[["CODIGO", "ARTICULO", "FAMILIA"]].drop_duplicates().copy()
    if buscar:
        df_art = df_art[
            df_art["CODIGO"].str.lower().str.contains(buscar, na=False)
            | df_art["ARTICULO"].str.lower().str.contains(buscar, na=False)
        ].head(50)
    else:
        df_art = df_art.head(50)

    if df_art.empty:
        st.info("Sin resultados para esa búsqueda.")
        return

    options = df_art["CODIGO"].astype(str).tolist()
    label_map = {r["CODIGO"]: f'{r["CODIGO"]} - {r["ARTICULO"]} | {r["FAMILIA"]}' for _, r in df_art.iterrows()}

    cod_sel = st.selectbox(
        "Artículo (desde stock origen)",
        options=options,
        format_func=lambda x: label_map.get(str(x), str(x)),
        key="mov_codigo_sel",
    )

    df_lotes = df_dep[df_dep["CODIGO"].astype(str) == str(cod_sel)].copy()
    if df_lotes.empty:
        st.warning("No se encontró stock para ese código en el depósito origen.")
        return

    has_lote = ((df_lotes["LOTE"].astype(str).str.strip() != "") | (df_lotes["VENCIMIENTO"].astype(str).str.strip() != "")).any()

    df_lotes["_vdate"] = df_lotes["VENCIMIENTO"].apply(_to_date_safe)
    df_lotes["_v_sort"] = df_lotes["_vdate"].apply(lambda d: d if d else date(2100, 1, 1))
    df_lotes = df_lotes.sort_values(by=["_v_sort", "LOTE"], ascending=[True, True]).reset_index(drop=True)

    modo = st.radio(
        "Selección de lote a mover",
        ["FIFO (más viejo)", "Más nuevo", "Elegir manual"],
        horizontal=True,
        key="mov_modo_lote",
    )

    chosen_idx = 0
    if modo == "FIFO (más viejo)":
        chosen_idx = 0
    elif modo == "Más nuevo":
        chosen_idx = len(df_lotes) - 1
    else:
        idx_opt = list(range(len(df_lotes)))
        chosen_idx = st.selectbox(
            "Elegir lote",
            options=idx_opt,
            format_func=lambda ix: _fmt_lote_row(
                df_lotes.loc[ix, "LOTE"],
                df_lotes.loc[ix, "VENCIMIENTO"],
                df_lotes.loc[ix, "STOCK"],
            ),
            key="mov_lote_manual_idx",
        )

    chosen = df_lotes.loc[int(chosen_idx)]
    stock_actual = _safe_float(chosen.get("STOCK", "0"))

    st.markdown("#### Lote seleccionado (origen)")
    if has_lote:
        st.write(_fmt_lote_row(chosen.get("LOTE", ""), chosen.get("VENCIMIENTO", ""), chosen.get("STOCK", "")))
    else:
        st.write(f'Stock disponible: {stock_actual:g} (sin lote/vencimiento)')

    # Alerta FIFO si elige más nuevo
    if modo == "Más nuevo" and len(df_lotes) > 1:
        st.warning("Estás eligiendo el lote MÁS NUEVO, pero existe un lote más viejo (FIFO).")
        confirmar = st.checkbox(
            "Sí, estoy seguro: quiero mover el lote más nuevo",
            key="mov_confirm_no_fifo",
        )
        if not confirmar:
            st.info("Para continuar, confirmá la excepción FIFO.")
            st.stop()

    cant = st.number_input(
        "Cantidad a mover",
        min_value=0.0,
        max_value=float(stock_actual) if stock_actual > 0 else 0.0,
        step=1.0,
        value=0.0,
        key="mov_cantidad",
    )

    if st.button("✅ Confirmar movimiento", use_container_width=True, key="mov_confirmar"):
        if cant <= 0:
            st.error("La cantidad debe ser > 0.")
            return
        if cant > stock_actual:
            st.error("No podés mover más que el stock disponible.")
            return

        # resta origen
        _upsert_stock_row(
            deposito=deposito_origen,
            familia=str(chosen.get("FAMILIA", "") or ""),
            codigo=str(chosen.get("CODIGO", "") or ""),
            articulo=str(chosen.get("ARTICULO", "") or ""),
            lote=str(chosen.get("LOTE", "") or ""),
            vencimiento=str(chosen.get("VENCIMIENTO", "") or ""),
            delta_stock=-float(cant),
        )

        # suma destino (mismo lote/venc)
        _upsert_stock_row(
            deposito=deposito_destino,
            familia=str(chosen.get("FAMILIA", "") or ""),
            codigo=str(chosen.get("CODIGO", "") or ""),
            articulo=str(chosen.get("ARTICULO", "") or ""),
            lote=str(chosen.get("LOTE", "") or ""),
            vencimiento=str(chosen.get("VENCIMIENTO", "") or ""),
            delta_stock=float(cant),
        )

        st.success("Movimiento confirmado y aplicado a stock.")


# =====================================================================
# BAJA POR VENCIMIENTO (SE DEJA COMO PLACEHOLDER + REGLA)
# =====================================================================

def mostrar_comprobante_baja_vencimiento():
    st.subheader("⏰ Baja por vencimiento")

    deposito_origen = st.selectbox(
        "Depósito",
        DEPOSITOS,
        key="venc_deposito_origen",
    )

    st.warning("Solo se permiten artículos vencidos (pendiente de completar lógica).")


# =====================================================================
# AJUSTE POR RECUENTO (SE DEJA COMO PLACEHOLDER)
# =====================================================================

def mostrar_comprobante_ajuste_recuento():
    st.subheader("⚖️ Ajuste por recuento")

    deposito = st.selectbox(
        "Depósito",
        DEPOSITOS,
        key="recuento_deposito",
    )

    tipo_ajuste = st.radio(
        "Tipo de ajuste",
        ["Alta", "Baja"],
        horizontal=True,
        key="recuento_tipo",
    )

    st.markdown("### Artículos")
    st.info("Permite ajustar stock real contra sistema (pendiente de completar lógica).")


# =====================================================================
# MENÚ PRINCIPAL COMPROBANTES
# =====================================================================

def mostrar_menu_comprobantes():

    st.title("📑 Comprobantes")

    opcion = st.radio(
        "Tipo de comprobante",
        [
            "⬆️ Alta de stock",
            "⬇️ Baja de stock",
            "🔁 Movimiento entre depósitos",
            "⏰ Baja por vencimiento",
            "⚖️ Ajuste por recuento"
        ],
        key="menu_comprobantes_opcion",
    )

    if opcion == "⬆️ Alta de stock":
        mostrar_comprobante_alta_stock()

    elif opcion == "⬇️ Baja de stock":
        mostrar_comprobante_baja_stock()

    elif opcion == "🔁 Movimiento entre depósitos":
        mostrar_comprobante_movimiento()

    elif opcion == "⏰ Baja por vencimiento":
        mostrar_comprobante_baja_vencimiento()

    elif opcion == "⚖️ Ajuste por recuento":
        mostrar_comprobante_ajuste_recuento()
