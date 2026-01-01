# =========================
# FERTI CHAT - BASE ADAPTATIVA
# =========================

import streamlit as st
import os


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
    # CONTENIDO PRINCIPAL
    # =========================
    st.subheader("🛒 Consultas")

    consulta = st.text_input(
        "Escribí tu consulta",
        placeholder="Ej: total compras noviembre 2025"
    )

    if st.button("Consultar"):
        if consulta:
            st.success(f"Consulta recibida: {consulta}")

            st.write("👉 Acá va tu lógica real (SQL / DB / IA)")

            if st.session_state.modo_avanzado:
                st.code("DEBUG: consulta parseada correctamente")
        else:
            st.warning("Escribí una consulta")

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
                "modo_avanzado": st.session_state.modo_avanzado
            })

    # =========================
    # FOOTER
    # =========================
    st.divider()
    st.caption("Ferti Chat • Hosted with Streamlit")


if __name__ == "__main__":
    main()







