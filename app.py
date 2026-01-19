# =========================
# FERTI CHAT - BASE ADAPTATIVA
# =========================

import streamlit as st
import os
from ui_inicio import mostrar_inicio  # Importa la función de inicio


def main():

    # =========================
    # CONFIGURACIÓN GENERAL
    # =========================
    st.set_page_config(
        page_title="Ferti Chat",
        page_icon="🦋",
        layout="wide"
    )

    # =========================
    # ESTADO INICIAL
    # =========================
    if "rol" not in st.session_state:
        st.session_state.rol = "user"
        
    if "modo_avanzado" not in st.session_state:
        st.session_state.modo_avanzado = False    

    if "logueado" not in st.session_state:
        st.session_state.logueado = False

    # =========================
    # DETECTAR ENTORNO
    # =========================
    ENTORNO = "cloud" if os.getenv("STREAMLIT_SERVER") else "local"

    # =========================
    # CSS RESPONSIVE (CLAVE)
    # =========================
    st.markdown("""
    <style>
    .block-container {
        padding-top: 2rem;
        padding-left: 2rem;
        padding-right: 2rem;
        max-width: 100%;
    }

    input, button {
        width: 100% !important;
    }

    .stButton>button {
        background-color: #ff6a00;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        height: 3rem;
    }

    @media (max-width: 900px) {
        h1 { font-size: 1.5rem; }
        h2 { font-size: 1.2rem; }
    }
    </style>
    """, unsafe_allow_html=True)

    # =========================
    # HEADER
    # =========================
    st.markdown("<h1 style='text-align:center;'>🦋 Ferti Chat</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>Sistema de Gestión de Compras</p>", unsafe_allow_html=True)
    st.divider()

    # =========================
    # LOGIN
    # =========================
    if not st.session_state.logueado:

        with st.container():
            empresa = st.text_input("Empresa")
            usuario = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Ingresar"):
                    if empresa and usuario and password:
                        st.session_state.logueado = True
                        if usuario.lower() == "admin":
                            st.session_state.rol = "admin"
                        st.rerun()
                    else:
                        st.warning("Completar todos los campos")

            with col2:
                st.button("Cambiar clave")

        st.stop()

    # =========================
    # BARRA SUPERIOR
    # =========================
    colA, colB, colC = st.columns([2, 2, 1])

    with colA:
        st.write(f"👤 Rol: **{st.session_state.rol}**")

    with colB:
        st.session_state.modo_avanzado = st.toggle(
            "Modo avanzado",
            value=st.session_state.modo_avanzado
        )

    with colC:
        if st.button("Salir"):
            st.session_state.logueado = False
            st.rerun()

    st.divider()

    # =========================
    # NAVEGACIÓN POR MÓDULOS
    # =========================
    go = st.query_params.get("go")
    
    # DEBUG GENERAL: Mostrar el valor de 'go' para verificar navegación
    if st.session_state.get("modo_avanzado"):
        st.write(f"🔍 DEBUG: Valor de 'go' = {go}")
    
    if go == "compras":
        # Módulo Compras IA
        st.subheader("🛒 Compras IA")
        st.write("Consultas inteligentes sobre compras.")
        consulta = st.text_input(
            "Escribí tu consulta de compras",
            placeholder="Ej: total compras noviembre 2025"
        )
        if st.button("Consultar Compras"):
            if consulta:
                st.success(f"Consulta de compras: {consulta}")
                st.write("👉 Acá va tu lógica real (SQL / DB / IA para compras)")
                if st.session_state.modo_avanzado:
                    st.code("DEBUG: consulta de compras parseada")
            else:
                st.warning("Escribí una consulta")

    elif go == "buscador":
        # Módulo Buscador IA
        st.subheader("🔎 Buscador IA")
        st.write("Buscar facturas / lotes.")
        # Agrega lógica específica

    elif go == "stock":
        # Módulo Stock IA
        st.subheader("📦 Stock IA")
        st.write("Consultar inventario.")
        # Agrega lógica específica

    elif go == "dashboard":
        # Módulo Dashboard
        st.subheader("📊 Dashboard")
        st.write("Ver estadísticas.")
        # Agrega lógica específica

    elif go == "pedidos":
        # Módulo Pedidos internos
        st.subheader("📄 Pedidos internos")
        st.write("Gestionar pedidos.")
        # Agrega lógica específica

    elif go == "baja":
        # Módulo Baja de stock
        st.subheader("🧾 Baja de stock")
        st.write("Registrar bajas.")
        # Agrega lógica específica

    elif go == "ordenes":
        # Módulo Órdenes de compra
        st.subheader("📦 Órdenes de compra")
        st.write("Crear órdenes.")
        # Agrega lógica específica

    elif go == "indicadores":
        # Módulo Indicadores
        st.subheader("📈 Indicadores")
        st.write("Power BI.")
        # Agrega lógica específica

    # ← CONDICIÓN PARA SUGERENCIAS CON DEBUG DETALLADO
    elif go == "sugerencias":
        st.write("🔍 DEBUG: Entrando a sección sugerencias")
        
        # Módulo Sugerencia de pedidos
        st.subheader("📋 Sugerencia de pedidos")
        st.write("Sistema inteligente de recomendaciones de compra.")
        
        try:
            st.write("🔍 DEBUG: Intentando importar pages.sugerencias...")
            import pages.sugerencias
            st.write("✅ DEBUG: Módulo importado correctamente")
            
            st.write("🔍 DEBUG: Intentando ejecutar main()...")
            pages.sugerencias.main()
            st.write("✅ DEBUG: main() ejecutado sin errores")
            
        except ImportError as e:
            st.error(f"❌ ERROR de Importación: {str(e)}")
            st.write("Posibles causas:")
            st.write("- El archivo pages/sugerencias.py no existe")
            st.write("- Error de sintaxis en sugerencias.py")
            st.write("- Ruta incorrecta (verifica carpeta pages/)")
            st.write("- Módulos faltantes (ui_sugerencias, config, etc.)")
            
        except Exception as e:
            st.error(f"❌ ERROR al ejecutar sugerencias: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    else:
        # Pantalla de inicio con tarjetas
        mostrar_inicio()

    # =========================
    # SECCIÓN AVANZADA (ADMIN)
    # =========================
    if st.session_state.rol == "admin":

        st.divider()
        st.subheader("⚙️ Administración")

        if st.session_state.modo_avanzado:
            st.write("📊 Debug / logs / tablas completas")
            st.json({
                "entorno": ENTORNO,
                "rol": st.session_state.rol,
                "modo_avanzado": st.session_state.modo_avanzado,
                "go": go
            })

    # =========================
    # FOOTER
    # =========================
    st.divider()
    st.caption("Ferti Chat • Hosted with Streamlit")


if __name__ == "__main__":
    main()
