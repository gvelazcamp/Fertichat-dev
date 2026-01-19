# =========================
# SUGERENCIAS.PY - VERSIÓN DE PRUEBA ULTRA-SIMPLE
# =========================

import streamlit as st

def main():
    st.title("Sugerencia de pedidos")
    st.write("¡Hola! La página funciona.")
    st.write("Si ves esto, el import y la ejecución funcionan correctamente.")
    
    # Prueba de datos
    try:
        from sql_compras import get_compras_anio
        df = get_compras_anio(2025, limite=5)
        if df is not None and not df.empty:
            st.success(f"Datos obtenidos: {len(df)} filas")
            st.dataframe(df)
        else:
            st.warning("No hay datos")
    except Exception as e:
        st.error(f"Error en datos: {str(e)}")

if __name__ == "__main__":
    main()
