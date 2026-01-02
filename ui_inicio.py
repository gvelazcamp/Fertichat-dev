# =========================
# UI_INICIO.PY - PANTALLA DE INICIO CON ACCESOS RÁPIDOS
# =========================

import streamlit as st
from datetime import datetime


def mostrar_inicio():
    """Pantalla de inicio con accesos rápidos a los módulos"""
    
    # Obtener nombre del usuario
    user = st.session_state.get("user", {})
    nombre = user.get("nombre", "Usuario")
    
    # Saludo según hora del día
    hora = datetime.now().hour
    if hora < 12:
        saludo = "¡Buenos días"
    elif hora < 19:
        saludo = "¡Buenas tardes"
    else:
        saludo = "¡Buenas noches"
    
    # Header con saludo
    st.markdown(f"""
        <div style="
            text-align: center;
            padding: 20px 0 30px 0;
        ">
            <h2 style="
                color: #1e293b;
                font-size: 28px;
                font-weight: 700;
                margin: 0;
            ">
                {saludo}, {nombre.split()[0]}! 👋
            </h2>
            <p style="
                color: #64748b;
                font-size: 16px;
                margin: 8px 0 0 0;
            ">
                ¿Qué querés hacer hoy?
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # CSS para las tarjetas
    st.markdown("""
        <style>
        .acceso-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px;
            padding: 24px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            border: none;
            min-height: 140px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        .acceso-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 35px rgba(102, 126, 234, 0.4);
        }
        .acceso-card.compras {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .acceso-card.buscador {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        .acceso-card.stock {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }
        .acceso-card.pedidos {
            background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
        }
        .acceso-card.baja {
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        }
        .acceso-card.ordenes {
            background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
        }
        .acceso-card.dashboard {
            background: linear-gradient(135deg, #5ee7df 0%, #b490ca 100%);
        }
        .acceso-card.indicadores {
            background: linear-gradient(135deg, #d299c2 0%, #fef9d7 100%);
        }
        .acceso-icon {
            font-size: 42px;
            margin-bottom: 12px;
        }
        .acceso-title {
            color: white;
            font-size: 16px;
            font-weight: 700;
            margin: 0;
            text-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .acceso-desc {
            color: rgba(255,255,255,0.85);
            font-size: 12px;
            margin: 6px 0 0 0;
        }
        .acceso-card.ordenes .acceso-title,
        .acceso-card.ordenes .acceso-desc,
        .acceso-card.indicadores .acceso-title,
        .acceso-card.indicadores .acceso-desc {
            color: #1e293b;
            text-shadow: none;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Sección: Módulos Principales
    st.markdown("""
        <p style="
            color: #64748b;
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin: 10px 0 15px 5px;
        ">
            📌 Módulos Principales
        </p>
    """, unsafe_allow_html=True)
    
    # Primera fila - 4 columnas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🛒\n\n**Compras IA**\n\nConsultas inteligentes", key="btn_compras", use_container_width=True):
            st.session_state["menu_principal"] = "🛒 Compras IA"
            st.rerun()
    
    with col2:
        if st.button("🔎\n\n**Buscador IA**\n\nBuscar facturas/lotes", key="btn_buscador", use_container_width=True):
            st.session_state["menu_principal"] = "🔎 Buscador IA"
            st.rerun()
    
    with col3:
        if st.button("📦\n\n**Stock IA**\n\nConsultar inventario", key="btn_stock", use_container_width=True):
            st.session_state["menu_principal"] = "📦 Stock IA"
            st.rerun()
    
    with col4:
        if st.button("📊\n\n**Dashboard**\n\nVer estadísticas", key="btn_dashboard", use_container_width=True):
            st.session_state["menu_principal"] = "📊 Dashboard"
            st.rerun()
    
    st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)
    
    # Sección: Gestión
    st.markdown("""
        <p style="
            color: #64748b;
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin: 10px 0 15px 5px;
        ">
            📋 Gestión
        </p>
    """, unsafe_allow_html=True)
    
    # Segunda fila - 4 columnas
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        if st.button("📄\n\n**Pedidos Internos**\n\nGestionar pedidos", key="btn_pedidos", use_container_width=True):
            st.session_state["menu_principal"] = "📄 Pedidos internos"
            st.rerun()
    
    with col6:
        if st.button("🧾\n\n**Baja de Stock**\n\nRegistrar bajas", key="btn_baja", use_container_width=True):
            st.session_state["menu_principal"] = "🧾 Baja de stock"
            st.rerun()
    
    with col7:
        if st.button("📦\n\n**Órdenes de Compra**\n\nCrear órdenes", key="btn_ordenes", use_container_width=True):
            st.session_state["menu_principal"] = "📦 Órdenes de compra"
            st.rerun()
    
    with col8:
        if st.button("📈\n\n**Indicadores**\n\nPower BI", key="btn_indicadores", use_container_width=True):
            st.session_state["menu_principal"] = "📈 Indicadores (Power BI)"
            st.rerun()
    
    # Estilos para los botones
    st.markdown("""
        <style>
        /* Estilo base para todos los botones de acceso */
        div[data-testid="column"] button {
            height: 130px !important;
            border-radius: 16px !important;
            border: none !important;
            font-size: 14px !important;
            white-space: pre-wrap !important;
            line-height: 1.4 !important;
            transition: all 0.3s ease !important;
        }
        
        /* Colores por botón */
        button[key="btn_compras"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
        }
        button[key="btn_buscador"] {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%) !important;
            color: white !important;
        }
        button[key="btn_stock"] {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%) !important;
            color: white !important;
        }
        button[key="btn_dashboard"] {
            background: linear-gradient(135deg, #5ee7df 0%, #b490ca 100%) !important;
            color: white !important;
        }
        button[key="btn_pedidos"] {
            background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%) !important;
            color: white !important;
        }
        button[key="btn_baja"] {
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%) !important;
            color: white !important;
        }
        button[key="btn_ordenes"] {
            background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%) !important;
            color: #1e293b !important;
        }
        button[key="btn_indicadores"] {
            background: linear-gradient(135deg, #d299c2 0%, #fef9d7 100%) !important;
            color: #1e293b !important;
        }
        
        /* Hover effect */
        div[data-testid="column"] button:hover {
            transform: translateY(-3px) !important;
            box-shadow: 0 10px 25px rgba(0,0,0,0.15) !important;
        }
        
        /* Active state */
        div[data-testid="column"] button:active {
            transform: translateY(0px) !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<div style='height: 30px'></div>", unsafe_allow_html=True)
    
    # Tip del día
    tips = [
        "💡 Escribí 'compras roche 2025' para ver todas las compras a Roche este año",
        "💡 Usá 'lotes por vencer' en Stock IA para ver vencimientos próximos",
        "💡 Probá 'comparar roche 2024 2025' para ver la evolución de compras",
        "💡 En el Buscador podés filtrar por proveedor, artículo y fechas",
        "💡 Usá 'top 10 proveedores 2025' para ver el ranking de compras",
    ]
    import random
    tip = random.choice(tips)
    
    st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
            border-radius: 12px;
            padding: 16px 20px;
            border-left: 4px solid #0ea5e9;
        ">
            <p style="
                color: #0369a1;
                font-size: 14px;
                margin: 0;
            ">
                {tip}
            </p>
        </div>
    """, unsafe_allow_html=True)
