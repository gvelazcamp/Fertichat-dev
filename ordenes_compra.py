# =====================================================================
# 📦 MÓDULO ÓRDENES DE COMPRA
# Archivo: ordenes_compra.py
# =====================================================================

import streamlit as st
from datetime import datetime, date

# =====================================================================
# CONSTANTES
# =====================================================================

TIPOS_OC = [
    "Normal" 
    "Inmediata"
    "Programada"
]

ESTADOS_OC = [
    "INGRESADA",
    "ENVIADA",
    "RECIBIDA",
    "FACTURADA",
    "CERRADA"
]

# =====================================================================
# FUNCIÓN PRINCIPAL (LLAMADA DESDE MAIN)
# =====================================================================

def mostrar_ordenes_compra():
    """
    Punto de entrada del módulo Órdenes de Compra
    Se llama desde el menú principal.
    """

    st.subheader("📦 Órdenes de Compra")

    opcion = st.radio(
        "Acción",
        [
            "🔎 Buscar órdenes",
            "➕ Nueva orden de compra"
        ],
        horizontal=True
    )

    if opcion == "🔎 Buscar órdenes":
        _vista_buscar_oc()

    elif opcion == "➕ Nueva orden de compra":
        _vista_nueva_oc()

# =====================================================================
# 🔎 BUSCAR ÓRDENES DE COMPRA
# =====================================================================

def _vista_buscar_oc():
    st.markdown("### 🔎 Buscar órdenes de compra")

    col1, col2, col3 = st.columns(3)

    with col1:
        filtro_proveedor = st.text_input("Proveedor")

    with col2:
        filtro_estado = st.selectbox(
            "Estado",
            ["Todos"] + ESTADOS_OC
        )

    with col3:
        filtro_tipo = st.selectbox(
            "Tipo",
            ["Todos"] + TIPOS_OC
        )

    st.info(
        "Aquí irá el listado de órdenes de compra filtradas "
        "(DB / Supabase / Excel, según tu implementación)."
    )

    st.dataframe(
        [],
        use_container_width=True
    )

# =====================================================================
# ➕ NUEVA ORDEN DE COMPRA
# =====================================================================

def _vista_nueva_oc():
    st.markdown("### ➕ Nueva Orden de Compra")

    col1, col2 = st.columns(2)

    with col1:
        proveedor = st.text_input("Proveedor")
        email_proveedor = st.text_input(
            "Email proveedor (opcional)"
        )

    with col2:
        responsable = st.text_input(
            "Responsable (quien pidió)"
        )
        contacto_responsable = st.text_input(
            "Mail / WhatsApp responsable"
        )

    tipo_oc = st.selectbox(
        "Tipo de orden de compra",
        TIPOS_OC
    )

    fecha_oc = st.date_input(
        "Fecha de la OC",
        value=date.today()
    )

    fecha_envio_programada = None

    if tipo_oc == "Programada":
        st.markdown("#### ⏰ Programación de envío")

        colf1, colf2 = st.columns(2)

        with colf1:
            fecha_programada = st.date_input(
                "Fecha de envío"
            )

        with colf2:
            hora_programada = st.time_input(
                "Hora de envío"
            )

        fecha_envio_programada = datetime.combine(
            fecha_programada,
            hora_programada
        )

    st.markdown("### 📦 Ítems de la orden")

    st.info(
        "Aquí irá la grilla de ítems:\n"
        "- Artículo\n"
        "- Cantidad\n"
        "- Precio unitario\n\n"
        "Editable mientras la OC esté INGRESADA."
    )

    st.markdown("---")

    colb1, colb2 = st.columns(2)

    with colb1:
        if st.button("💾 Guardar OC"):
            st.success(
                "OC guardada en estado INGRESADA "
                "(lógica de guardado pendiente)."
            )

    with colb2:
        st.button(
            "📤 Enviar OC",
            help="Pasa a ENVIADA y dispara mails / PDF"
        )

# =====================================================================
# FIN DEL ARCHIVO
# =====================================================================
