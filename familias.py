# =====================================================================
# 🧩 MÓDULO: CREAR / GESTIONAR FAMILIAS - FERTI CHAT
# Archivo: familias.py  (IMPORTANTE: minúscula para Streamlit Cloud)
# =====================================================================

import streamlit as st
import pandas as pd
from datetime import datetime

# Importar conexión a DB (Supabase / Postgres)
# (No cambiar: se asume que ya existe en tu proyecto)
from sql_core import get_db_connection


# =====================================================================
# DB HELPERS
# =====================================================================

def _ensure_table_familias() -> None:
    """
    Crea la tabla si no existe. No rompe nada si ya existe.
    """
    sql = """
    CREATE TABLE IF NOT EXISTS public.familias (
        id BIGSERIAL PRIMARY KEY,
        nombre TEXT NOT NULL UNIQUE,
        descripcion TEXT,
        activo BOOLEAN NOT NULL DEFAULT TRUE,
        creado_por TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ
    );
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    except Exception as e:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        st.error(f"No pude asegurar la tabla 'familias'. Detalle: {e}")
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def _read_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = None
    try:
        conn = get_db_connection()
        df = pd.read_sql_query(sql, conn, params=params)
        return df
    except Exception as e:
        st.error(f"Error leyendo DB: {e}")
        return pd.DataFrame()
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def _exec(sql: str, params: tuple = ()) -> bool:
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
        return True
    except Exception as e:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        st.error(f"Error ejecutando SQL: {e}")
        return False
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


# =====================================================================
# QUERIES
# =====================================================================

def _get_familias(buscar: str = "") -> pd.DataFrame:
    if buscar:
        sql = """
        SELECT id, nombre, descripcion, activo, creado_por, created_at, updated_at
        FROM public.familias
        WHERE (LOWER(nombre) LIKE LOWER(%s) OR LOWER(COALESCE(descripcion,'')) LIKE LOWER(%s))
        ORDER BY LOWER(nombre) ASC;
        """
        like = f"%{buscar.strip()}%"
        return _read_df(sql, (like, like))
    else:
        sql = """
        SELECT id, nombre, descripcion, activo, creado_por, created_at, updated_at
        FROM public.familias
        ORDER BY LOWER(nombre) ASC;
        """
        return _read_df(sql)


def _insert_familia(nombre: str, descripcion: str, activo: bool, creado_por: str) -> bool:
    sql = """
    INSERT INTO public.familias (nombre, descripcion, activo, creado_por)
    VALUES (%s, %s, %s, %s);
    """
    return _exec(sql, (nombre.strip(), (descripcion or "").strip(), bool(activo), (creado_por or "").strip()))


def _update_familia(fid: int, nombre: str, descripcion: str, activo: bool) -> bool:
    sql = """
    UPDATE public.familias
    SET nombre = %s,
        descripcion = %s,
        activo = %s,
        updated_at = NOW()
    WHERE id = %s;
    """
    return _exec(sql, (nombre.strip(), (descripcion or "").strip(), bool(activo), int(fid)))


def _delete_familia(fid: int) -> bool:
    # Borrado físico (simple). Si preferís soft delete, avisame y lo cambiamos.
    sql = "DELETE FROM public.familias WHERE id = %s;"
    return _exec(sql, (int(fid),))


# =====================================================================
# UI
# =====================================================================

def mostrar_familias():
    # 1) Asegurar tabla (no rompe si ya existe)
    _ensure_table_familias()

    st.header("🧩 Crear Familias")

    # Usuario (si existe en tu login)
    usuario = st.session_state.get("usuario") or st.session_state.get("user") or st.session_state.get("username") or ""

    tab1, tab2 = st.tabs(["📋 Listado / Editar", "➕ Nueva familia"])

    # -------------------------
    # TAB 1: Listado / Editar
    # -------------------------
    with tab1:
        colA, colB = st.columns([2, 1])
        with colA:
            buscar = st.text_input("Buscar (nombre o descripción):", value="", placeholder="Ej: reactivos, limpieza...")
        with colB:
            st.write("")
            st.write("")
            if st.button("🔄 Refrescar", use_container_width=True):
                st.rerun()

        df = _get_familias(buscar)

        if df.empty:
            st.info("No hay familias cargadas (o no coincide la búsqueda).")
        else:
            # Normalizar fechas a string para visualización
            for c in ["created_at", "updated_at"]:
                if c in df.columns:
                    df[c] = df[c].astype(str)

            st.dataframe(df, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.subheader("✏️ Editar / Eliminar")

            opciones = df[["id", "nombre"]].copy()
            opciones["label"] = opciones["id"].astype(str) + " — " + opciones["nombre"].astype(str)

            selected_label = st.selectbox(
                "Seleccionar familia:",
                opciones["label"].tolist(),
                index=0
            )
            fid = int(selected_label.split("—")[0].strip())
            fila = df[df["id"] == fid].iloc[0]

            col1, col2 = st.columns(2)
            with col1:
                nuevo_nombre = st.text_input("Nombre:", value=str(fila.get("nombre", "")))
                nuevo_desc = st.text_area("Descripción:", value=str(fila.get("descripcion", "") or ""), height=90)
            with col2:
                nuevo_activo = st.checkbox("Activo", value=bool(fila.get("activo", True)))
                st.caption("Tip: si no querés borrar, podés desactivar la familia.")

            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                if st.button("💾 Guardar cambios", use_container_width=True):
                    if not nuevo_nombre.strip():
                        st.warning("El nombre no puede estar vacío.")
                    else:
                        ok = _update_familia(fid, nuevo_nombre, nuevo_desc, nuevo_activo)
                        if ok:
                            st.success("Familia actualizada.")
                            st.rerun()

            with c2:
                if st.button("🗑️ Eliminar", use_container_width=True):
                    st.session_state["_confirm_delete_familia_id"] = fid

            with c3:
                fid_conf = st.session_state.get("_confirm_delete_familia_id")
                if fid_conf == fid:
                    st.warning("Confirmá eliminación: esta acción borra la familia de la tabla.")
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("✅ Confirmar borrar", use_container_width=True):
                            ok = _delete_familia(fid)
                            st.session_state.pop("_confirm_delete_familia_id", None)
                            if ok:
                                st.success("Familia eliminada.")
                                st.rerun()
                    with cc2:
                        if st.button("❌ Cancelar", use_container_width=True):
                            st.session_state.pop("_confirm_delete_familia_id", None)
                            st.rerun()

    # -------------------------
    # TAB 2: Nueva familia
    # -------------------------
    with tab2:
        st.subheader("➕ Crear nueva familia")

        nombre = st.text_input("Nombre de la familia:", value="", placeholder="Ej: Reactivos")
        descripcion = st.text_area("Descripción (opcional):", value="", height=110, placeholder="Ej: Reactivos para inmunoquímica...")
        activo = st.checkbox("Activo", value=True)

        colX, colY = st.columns([1, 2])
        with colX:
            if st.button("✅ Crear", use_container_width=True):
                if not nombre.strip():
                    st.warning("El nombre es obligatorio.")
                else:
                    ok = _insert_familia(nombre, descripcion, activo, usuario)
                    if ok:
                        st.success("Familia creada.")
                        st.rerun()
        with colY:
            st.caption("Se guarda en Postgres/Supabase. El nombre es único (no permite duplicados).")
