# =====================================================================
# 📉 MÓDULO BAJA DE STOCK - USO OPERATIVO
# Archivo: baja_stock.py
# =====================================================================

import streamlit as st
import pandas as pd
from datetime import datetime

from sql_queries import ejecutar_consulta, get_db_connection

# =====================================================================
# CONFIG
# =====================================================================

CANTIDAD_FIJA = 1

# =====================================================================
# DB HELPERS
# =====================================================================

def buscar_articulo(texto: str) -> pd.DataFrame:
    """
    Busca por código exacto o por nombre parcial
    """
    query = """
        SELECT
            "CODIGO"   AS codigo,
            "ARTICULO" AS articulo,
            "FAMILIA"  AS familia,
            "STOCK"    AS stock
        FROM stock
        WHERE
            "CODIGO" = %s
            OR UPPER("ARTICULO") LIKE %s
        LIMIT 5
    """
    return ejecutar_consulta(
        query,
        (texto.strip(), f"%{texto.upper().strip()}%")
    )


def bajar_stock(codigo: str, usuario: str) -> tuple[bool, str]:
    """
    Resta 1 unidad de stock y registra movimiento
    """
    conn = get_db_connection()
    if not conn:
        return False, "Error de conexión"

    try:
        cursor = conn.cursor()

        # Ver stock actual
        cursor.execute("""
            SELECT "STOCK", "ARTICULO"
            FROM stock
            WHERE "CODIGO" = %s
            FOR UPDATE
        """, (codigo,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False, "Artículo no encontrado"

        stock_actual, articulo = row

        if stock_actual is None or stock_actual <= 0:
            conn.close()
            return False, "Stock en cero"

        # Actualizar stock
        cursor.execute("""
            UPDATE stock
            SET "STOCK" = "STOCK" - 1
            WHERE "CODIGO" = %s
        """, (codigo,))

        # Registrar historial
        cursor.execute("""
            INSERT INTO stock_movimientos
            (codigo, articulo, usuario, cantidad, fecha)
            VALUES (%s, %s, %s, %s, NOW())
        """, (codigo, articulo, usuario, -1))

        conn.commit()
        conn.close()

        return True, f"✔️ Bajado: {articulo}"

    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except:
            pass
        return False, str(e)


def obtener_historial(limit: int = 50) -> pd.DataFrame:
    """
    Últimos movimientos de stock
    """
    query = """
        SELECT
            fecha        AS "Fecha",
            usuario      AS "Usuario",
            codigo       AS "Código",
            articulo     AS "Artículo",
            cantidad     AS "Cantidad"
        FROM stock_movimientos
        ORDER BY fecha DESC
        LIMIT %s
    """
    return ejecutar_consulta(query, (limit,))


# =====================================================================
# UI STREAMLIT
# =====================================================================

def mostrar_baja_stock():
    st.title("📉 Baja de Stock")

    # Usuario actual
    user = st.session_state.get("user", {})
    usuario = user.get("usuario", user.get("email", "anonimo"))

    st.markdown("### 🔎 Escaneá o escribí el artículo")
    st.caption("Cantidad fija = 1 · Uso rápido · Sin vueltas")

    texto = st.text_input(
        "Código de barras o nombre",
        key="input_baja_stock",
        placeholder="Escanear código o escribir nombre"
    )

    if texto:
        df = buscar_articulo(texto)

        if df is None or df.empty:
            st.warning("No se encontró el artículo")
        else:
            for _, row in df.iterrows():
                col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 1, 2])

                with col1:
                    st.markdown(f"**{row['articulo']}**")
                    st.caption(f"Código: {row['codigo']}")

                with col2:
                    st.markdown(f"Familia: `{row['familia']}`")

                with col3:
                    st.markdown(f"Stock: **{row['stock']}**")

                with col5:
                    if st.button("➖ Bajar 1", key=f"bajar_{row['codigo']}"):
                        ok, msg = bajar_stock(row["codigo"], usuario)
                        if ok:
                            st.success(msg)
                            st.session_state["input_baja_stock"] = ""
                            st.rerun()
                        else:
                            st.error(msg)

    st.markdown("---")

    # =========================
    # HISTORIAL
    # =========================
    st.subheader("🧾 Historial de bajas")

    df_hist = obtener_historial()

    if df_hist is not None and not df_hist.empty:
        st.dataframe(
            df_hist,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Todavía no hay movimientos registrados")
