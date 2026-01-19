# =========================
# SUGERENCIAS.PY - VERSIÓN DE PRUEBA ULTRA-SIMPLE
# =========================

import streamlit as st

def main():
    st.title("📋 Sugerencia de pedidos - PRUEBA")
    st.write("¡Hola! Si ves esto, la función main() se está ejecutando correctamente.")
    st.write("Parámetro go en URL:", st.query_params.get("go"))
    
    # Prueba de importación
    try:
        from ui.ui_sugerencias import apply_css_sugerencias
        st.success("✅ Importación de ui_sugerencias OK")
        apply_css_sugerencias()
        st.write("✅ CSS aplicado")
    except Exception as e:
        st.error(f"❌ Error en importación: {str(e)}")
    
    # Prueba de datos
    try:
        from sql_compras import get_compras_anio
        df = get_compras_anio(2025, limite=10)
        if df is not None and not df.empty:
            st.success(f"✅ Datos obtenidos: {len(df)} filas")
            st.dataframe(df.head(3))
        else:
            st.warning("⚠️ No hay datos o df vacío")
    except Exception as e:
        st.error(f"❌ Error en consulta SQL: {str(e)}")

if __name__ == "__main__":
    main()
