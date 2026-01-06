# =====================================================================
# 🏬 MÓDULO DEPÓSITOS - FERTI CHAT
# Archivo: depositos.py  (IMPORTANTE: minúscula para Streamlit Cloud)
# =====================================================================

import streamlit as st
import pandas as pd
from typing import Optional

# Importar conexión a DB
from sql_core import get_db_connection, ejecutar_consulta


# =====================================================================
# HELPERS DB
# =====================================================================

def _safe_str(x: Optional[str]) -> str:
    return (x or "").strip()


def _get_depositos_df() -> pd.DataFrame:
    """
    Devuelve dataframe con depósitos.
    Requiere tabla: depositos (id, nombre, codigo, descripcion, activo, created_at)
    """
    sql = """
        SELECT
            id,
            nombre,
            codigo,
            descripcion,
            activo,
            created_at
        FROM depositos
        ORDER BY activo DESC, nombre ASC;
    """
    try:
        df = ejecutar_consulta(sql)
        if df is None:
            return pd.DataFrame()
        return df
    except Exception:
        return pd.DataFrame()


def _crear_deposito(nombre: str, codigo: str, descripcion: str, activo: bool) -> None:
    sql = """
        INSERT INTO depositos (nombre, codigo, descripcion, activo)
        VALUES (%s, %s, %s, %s);
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (nombre, codigo, descripcion, activo))
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _actualizar_deposito(dep_id, nombre: str, codigo: str, descripcion: str, activo: bool) -> None:
    sql = """
        UPDATE depositos
        SET nombre = %s,
            codigo = %s,
            descripcion = %s,
            activo = %s
        WHERE id = %s;
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (nombre, codigo, descripcion, activo, dep_id))
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _eliminar_deposito(dep_id) -> None:
    sql = "DELETE FROM depositos WHERE id = %s;"
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (dep_id,))
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


# =====================================================================
# UI PRINCIPAL
# =====================================================================

def mostrar_depositos():
    st.subheader("🏬 Depósitos")

    # -------------------------
    # Nota / SQL sugerido (no ejecuta nada)
    # -------------------------
    with st.expander("📌 Si aún no existe la tabla (SQL sugerido)", expanded=False):
        st.code(
            """
-- Tabla sugerida (ejecutar SOLO si no existe)
CREATE TABLE IF NOT EXISTS depositos (
  id BIGSERIAL PRIMARY KEY,
  nombre TEXT NOT NULL UNIQUE,
  codigo TEXT,
  descripcion TEXT,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
            """.strip(),
            language="sql"
        )

    # -------------------------
    # Crear depósito
    # -------------------------
    st.markdown("### ➕ Crear depósito")
    with st.form("form_crear_deposito", clear_on_submit=True):
        c1, c2 = st.columns([2, 1])
        with c1:
            nombre = st.text_input("Nombre *", placeholder="Ej: Casa Central")
        with c2:
            activo = st.checkbox("Activo", value=True)

        c3, c4 = st.columns([1, 2])
        with c3:
            codigo = st.text_input("Código (opcional)", placeholder="Ej: CC")
        with c4:
            descripcion = st.text_input("Descripción / Dirección (opcional)", placeholder="Ej: Depósito principal")

        guardar = st.form_submit_button("💾 Guardar", use_container_width=True)

        if guardar:
            nombre = _safe_str(nombre)
            codigo = _safe_str(codigo)
            descripcion = _safe_str(descripcion)

            if not nombre:
                st.error("El nombre es obligatorio.")
            else:
                try:
                    _crear_deposito(nombre, codigo, descripcion, activo)
                    st.success("Depósito creado.")
                except Exception as e:
                    st.error(f"No se pudo crear el depósito: {e}")

    st.markdown("---")

    # -------------------------
    # Listado
    # -------------------------
    st.markdown("### 📋 Listado de depósitos")
    df = _get_depositos_df()
    if df.empty:
        st.info("No hay depósitos cargados (o la tabla no existe aún).")
        return

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # -------------------------
    # Editar / Eliminar
    # -------------------------
    st.markdown("### ✏️ Editar / 🗑️ Eliminar")

    try:
        opciones = df["id"].astype(str) + " — " + df["nombre"].astype(str)
        seleccionado = st.selectbox("Seleccionar depósito", opciones.tolist())
        dep_id = seleccionado.split(" — ")[0]
        row = df[df["id"].astype(str) == dep_id].iloc[0]

        with st.form("form_editar_deposito"):
            c1, c2 = st.columns([2, 1])
            with c1:
                nombre2 = st.text_input("Nombre *", value=str(row.get("nombre", "")))
            with c2:
                activo2 = st.checkbox("Activo", value=bool(row.get("activo", True)))

            c3, c4 = st.columns([1, 2])
            with c3:
                codigo2 = st.text_input("Código (opcional)", value=str(row.get("codigo", "") if row.get("codigo") is not None else ""))
            with c4:
                descripcion2 = st.text_input("Descripción / Dirección (opcional)", value=str(row.get("descripcion", "") if row.get("descripcion") is not None else ""))

            cbtn1, cbtn2 = st.columns(2)
            with cbtn1:
                btn_guardar = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
            with cbtn2:
                btn_eliminar = st.form_submit_button("🗑️ Eliminar depósito", use_container_width=True)

            if btn_guardar:
                nombre2 = _safe_str(nombre2)
                codigo2 = _safe_str(codigo2)
                descripcion2 = _safe_str(descripcion2)

                if not nombre2:
                    st.error("El nombre es obligatorio.")
                else:
                    try:
                        _actualizar_deposito(dep_id, nombre2, codigo2, descripcion2, activo2)
                        st.success("Depósito actualizado. Refrescá la página si querés ver el listado actualizado.")
                    except Exception as e:
                        st.error(f"No se pudo actualizar: {e}")

            if btn_eliminar:
                try:
                    _eliminar_deposito(dep_id)
                    st.success("Depósito eliminado. Refrescá la página si querés ver el listado actualizado.")
                except Exception as e:
                    st.error(f"No se pudo eliminar: {e}")

    except Exception as e:
        st.error(f"No se pudo cargar el editor: {e}")
