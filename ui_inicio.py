# =========================
# UI_INICIO.    PY - PANTALLA DE INICIO CON ACCESOS RÁPIDOS (CORPORATIVO)
# =========================

import streamlit as st
from datetime import datetime
import random


def mostrar_inicio():
    """Pantalla de inicio con accesos rápidos a los módulos (look corporativo)"""

    # =========================
    # Datos usuario / saludo
    # =========================
    user = st.session_state.get("user", {})
    nombre = user.get("nombre", "Usuario")

    hora = datetime.now().hour
    if hora < 12:
        saludo = "¡Buenos días"
    elif hora < 19:
        saludo = "¡Buenas tardes"
    else:
        saludo = "¡Buenas noches"

    # =========================
    # Header (saludo)
    # =========================
    st.markdown(
        f"""
        <div style="max-width:1100px;margin:  0 auto;text-align:  center;padding:  10px 0 18px 0;">
            <h2 style="margin:0;color:#0f172a;font-size:34px;font-weight:800;letter-spacing:-0.02em;">
                {saludo}, {nombre.    split()[0]}!     👋
            </h2>
            <p style="margin:8px 0 0 0;color:#64748b;font-size:16px;">
                ¿Qué querés hacer hoy?   
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # =========================
    # MARCADOR (para aplicar CSS SOLO en esta pantalla)
    # =========================
    st.markdown('<div id="fc-home-marker" style="display:none;"></div>', unsafe_allow_html=True)

    # =========================
    # CSS para HOME (PC + MÓVIL)
    # =========================
    st.markdown("""
    <style>
    /* =========================================================
       SOLO HOME (scoped)
       ========================================================= */
    div[data-testid="stAppViewContainer"]:  has(#fc-home-marker) div[data-testid="column"]{
        position: relative;
    }

    /* =========================
       DESKTOP (tu grilla actual)
       ========================= */
    div[data-testid="stAppViewContainer"]: has(#fc-home-marker) . fc-home-desktop{
        display: block;
    }
    div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .fc-home-mobile{
        display:    none;
    }

    /* Asegurar full width del wrapper del botón */
    div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .stButton{
        width: 100%;
    }

    /* Botón como tarjeta (DESKTOP) */
    div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .fc-home-desktop .stButton > button{
        border:    1px solid rgba(15,23,42,0.10);
        background: rgba(255,255,255,0.82);
        border-radius: 20px;

        height:     96px;
        min-height:    96px;

        padding:16px 16px 16px 92px;

        box-shadow: 0 10px 24px rgba(2,6,23,0.06);
        cursor:  pointer;
        transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease, background 140ms ease;

        width:100%;
        text-align: left;

        white-space:    pre-line;
        font-size:13.    5px;
        font-weight:   600;
        color:#334155;
        line-height:1.22;

        display:block;
        position:    relative;
        margin:    0;
        box-sizing:  border-box;
    }

    div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .fc-home-desktop .stButton > button::    first-line{
        font-size:16px;
        font-weight:   900;
        color:#0f172a;
        letter-spacing:-0.01em;
    }

    div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .fc-home-desktop .stButton > button:  hover{
        transform:  translateY(-2px);
        box-shadow: 0 14px 34px rgba(2,6,23,0.09);
        border-color: rgba(37,99,235,0.22);
        background: rgba(255,255,255,0.90);
    }
    div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .fc-home-desktop .stButton > button: active{
        transform:  translateY(0);
        box-shadow: 0 10px 24px rgba(2,6,23,0.06);
    }
    div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .fc-home-desktop .stButton > button: focus{
        outline:  none;
        box-shadow: 0 0 0 3px rgba(37,99,235,0.12), 0 10px 24px rgba(2,6,23,0.06);
    }

    /* Tile (ícono) - DESKTOP */
    div[data-testid="stAppViewContainer"]:  has(#fc-home-marker) .fc-home-desktop .fc-home-tile{
        width:54px;
        height:54px;
        border-radius:16px;
        display:flex;
        align-items:center;
        justify-content:center;

        border:  1px solid rgba(15,23,42,0.08);
        background: rgba(255,255,255,0.86);
        font-size:26px;

        position:absolute;
        left:   16px;
        top:   50%;
        transform:   translateY(-50%);
        z-index:    5;

        pointer-events:none;
        box-shadow: 0 10px 18px rgba(2,6,23,0.07);
        user-select:none;
    }

    /* Colores tiles */
    .    tile-compras { background: rgba(16,185,129,0.10); border-color: rgba(16,185,129,0.18); }
    .tile-buscador { background: rgba(59,130,246,0.10); border-color: rgba(59,130,246,0.18); }
    .tile-stock { background: rgba(245,158,11,0.12); border-color:rgba(245,158,11,0.22); }
    .tile-dashboard { background:rgba(139,92,246,0.10); border-color:rgba(139,92,246,0.18); }
    .tile-pedidos { background:rgba(2,132,199,0.10); border-color:rgba(2,132,199,0.18); }
    .tile-baja { background:rgba(244,63,94,0.10); border-color:rgba(244,63,94,0.18); }
    .tile-ordenes { background:rgba(100,116,139,0.10); border-color:rgba(100,116,139,0.18); }
    .tile-indicadores { background:rgba(34,197,94,0.10); border-color:rgba(34,197,94,0.18); }

    /* =========================
       MÓVIL:     OCULTAR DESKTOP, MOSTRAR MOBILE
       ========================= */
    @media (max-width: 768px){
        /* OCULTAR layout desktop */
        div[data-testid="stAppViewContainer"]: has(#fc-home-marker) .fc-home-desktop{
            display:none !    important;
        }
        
        /* MOSTRAR layout móvil */
        div[data-testid="stAppViewContainer"]:  has(#fc-home-marker) .fc-home-mobile{
            display:  block !   important;
        }

        /* más ancho útil */
        div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .block-container{
            padding-left:0.   65rem ! important;
            padding-right: 0.65rem !important;
        }

        /* Tarjeta móvil (BUTTON clickeable - COMPLETAMENTE INVISIBLE AL CLICK) */
        div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .fc-mcard{
            display:flex;
            align-items:center;
            gap:14px;

            width:100%;
            box-sizing:border-box;

            height:   104px;
            min-height:     104px;
            max-height:   104px;

            border-radius:24px;
            border:  1px solid rgba(15,23,42,0.10);
            background: linear-gradient(135deg, rgba(255,255,255,0.95), rgba(255,255,255,0.85));
            box-shadow: 0 12px 28px rgba(2,6,23,0.08);

            padding:14px 14px;
            cursor:pointer;

            /* Estilos de button - SIN NINGÚN EFECTO VISUAL */
            outline: none;
            -webkit-tap-highlight-color: rgba(0,0,0,0);
            -webkit-touch-callout: none;
            -webkit-user-select: none;
            -webkit-focus-ring-color: transparent;
            user-select: none;
            transition: none;
        }

        /* NINGÚN CAMBIO AL PRESIONAR, FOCUS O HOVER */
        div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .fc-mcard:active,
        div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .fc-mcard:focus,
        div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .fc-mcard:hover{
            transform: none;
            box-shadow: 0 12px 28px rgba(2,6,23,0.08);
            background: linear-gradient(135deg, rgba(255,255,255,0.95), rgba(255,255,255,0.85));
            outline: none;
            -webkit-tap-highlight-color: rgba(0,0,0,0);
        }

        /* icon */
        div[data-testid="stAppViewContainer"]: has(#fc-home-marker) .fc-micon{
            width:54px;
            height:54px;
            border-radius:18px;
            display:flex;
            align-items:center;
            justify-content:center;
            font-size:26px;

            border:  1px solid rgba(15,23,42,0.08);
            background: linear-gradient(135deg, rgba(255,255,255,0.92), rgba(255,255,255,0.80));
            box-shadow:0 8px 16px rgba(2,6,23,0.06);

            flex:     0 0 54px;
        }

        /* text block */
        div[data-testid="stAppViewContainer"]:    has(#fc-home-marker) .fc-mtxt{
            display:flex;
            flex-direction:column;
            gap:4px;
            min-width:0;
        }

        div[data-testid="stAppViewContainer"]:  has(#fc-home-marker) .fc-mtitle{
            margin:    0;
            font-size:  16px;
            font-weight:900;
            color:#0f172a;
            line-height:1.05;
        }

        div[data-testid="stAppViewContainer"]:  has(#fc-home-marker) .fc-msub{
            margin:  0;
            font-size:   13px;
            font-weight:  600;
            color:#64748b;
            line-height:1.2;
        }

        /* separación entre tarjetas */
        div[data-testid="stAppViewContainer"]:has(#fc-home-marker) .fc-mstack{
            display:flex;
            flex-direction:column;
            gap:16px;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    # =========================
    # Helpers HTML (móvil) - ONCLICK CON ASSIGN PARA MISMA PESTAÑA
    # =========================
    def _mcard(go:  str, icon: str, title: str, sub: str, tile_class: str) -> str:
        return f'''
        <button class="fc-mcard" onclick="window.location.assign('?go={go}');">
            <div class="fc-micon {tile_class}">{icon}</div>
            <div class="fc-mtxt">
                <p class="fc-mtitle">{title}</p>
                <p class="fc-msub">{sub}</p>
            </div>
        </button>
        '''

    # =========================
    # LAYOUT DESKTOP (COMENTADO - NO USAR POR AHORA)
    # =========================
    """
    st.markdown('<div class="fc-home-desktop">', unsafe_allow_html=True)
    st.markdown(
        "<div style='max-width:1100px;margin:0 auto;'><div style='color:#64748b;font-size:12px;font-weight:  800;text-transform:uppercase;letter-spacing:   1px;margin:  18px 0 10px 6px;display:flex;align-items:center;gap: 8px;'>📌 Módulos principales</div></div>",
        unsafe_allow_html=True
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown('<div class="fc-home-tile tile-compras">🛒</div>', unsafe_allow_html=True)
        if st.button("Compras IA\nConsultas inteligentes", key="compras"):
            st.query_params["go"] = "compras"
            st.rerun()
    with col2:
        st.markdown('<div class="fc-home-tile tile-buscador">🔎</div>', unsafe_allow_html=True)
        if st.button("Buscador IA\nBuscar facturas / lotes", key="buscador"):
            st.query_params["go"] = "buscador"
            st.rerun()
    with col3:
        st. markdown('<div class="fc-home-tile tile-stock">📦</div>', unsafe_allow_html=True)
        if st.button("Stock IA\nConsultar inventario", key="stock"):
            st.query_params["go"] = "stock"
            st. rerun()
    with col4:
        st.  markdown('<div class="fc-home-tile tile-dashboard">📊</div>', unsafe_allow_html=True)
        if st.button("Dashboard\nVer estadísticas", key="dashboard"):
            st.query_params["go"] = "dashboard"
            st.rerun()

    st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)

    st.markdown(
        "<div style='max-width:1100px;margin:0 auto;'><div style='color:#64748b;font-size:   12px;font-weight:800;text-transform:uppercase;letter-spacing:  1px;margin:  18px 0 10px 6px;display:flex;align-items: center;gap:  8px;'>📋 Gestión</div></div>",
        unsafe_allow_html=True
    )

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.markdown('<div class="fc-home-tile tile-pedidos">📄</div>', unsafe_allow_html=True)
        if st.button("Pedidos internos\nGestionar pedidos", key="pedidos"):
            st.query_params["go"] = "pedidos"
            st.rerun()
    with col6:
        st.  markdown('<div class="fc-home-tile tile-baja">🧾</div>', unsafe_allow_html=True)
        if st.button("Baja de stock\nRegistrar bajas", key="baja"):
            st.query_params["go"] = "baja"
            st.rerun()
    with col7:
        st.markdown('<div class="fc-home-tile tile-ordenes">📦</div>', unsafe_allow_html=True)
        if st.button("Órdenes de compra\nCrear órdenes", key="ordenes"):
            st.query_params["go"] = "ordenes"
            st.rerun()
    with col8:
        st.markdown('<div class="fc-home-tile tile-indicadores">📈</div>', unsafe_allow_html=True)
        if st.button("Indicadores\nPower BI", key="indicadores"):
            st.query_params["go"] = "indicadores"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)  # cierre fc-home-desktop
    """

    # =========================
    # LAYOUT MÓVIL (ÚNICO - PERFECTAS + FUNCIONAN)
    # =========================
    st.markdown('<div class="fc-home-mobile">', unsafe_allow_html=True)

    st.markdown(
        "<div style='max-width:1100px;margin:0 auto;'><div style='color:#64748b;font-size:12px;font-weight: 800;text-transform:uppercase;letter-spacing: 1px;margin: 18px 0 10px 6px;display:flex;align-items:center;gap:8px;'>📌 Módulos principales</div></div>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"""
        <div class="fc-mstack">
            {_mcard("compras", "🛒", "Compras IA", "Consultas inteligentes", "tile-compras")}
            {_mcard("buscador", "🔎", "Buscador IA", "Buscar facturas / lotes", "tile-buscador")}
            {_mcard("stock", "📦", "Stock IA", "Consultar inventario", "tile-stock")}
            {_mcard("dashboard", "📊", "Dashboard", "Ver estadísticas", "tile-dashboard")}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)

    st.markdown(
        "<div style='max-width:1100px;margin:0 auto;'><div style='color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing: 1px;margin:   18px 0 10px 6px;display:flex;align-items:center;gap:  8px;'>📋 Gestión</div></div>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"""
        <div class="fc-mstack">
            {_mcard("pedidos", "📄", "Pedidos internos", "Gestionar pedidos", "tile-pedidos")}
            {_mcard("baja", "🧾", "Baja de stock", "Registrar bajas", "tile-baja")}
            {_mcard("ordenes", "📦", "Órdenes de compra", "Crear órdenes", "tile-ordenes")}
            {_mcard("indicadores", "📈", "Indicadores", "Power BI", "tile-indicadores")}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("</div>", unsafe_allow_html=True)  # cierre fc-home-mobile

    # =========================
    # TIP DEL DÍA
    # =========================
    tips = [
        "💡 Escribí 'compras roche 2025' para ver todas las compras a Roche este año",
        "💡 Usá 'lotes por vencer' en Stock IA para ver vencimientos próximos",
        "💡 Probá 'comparar roche 2024 2025' para ver la evolución de compras",
        "💡 En el Buscador podés filtrar por proveedor, artículo y fechas",
        "💡 Usá 'top 10 proveedores 2025' para ver el ranking de compras",
    ]
    tip = random.choice(tips)

    st.markdown(
        f"""
        <div style="max-width:1100px;margin:  16px auto 0 auto;">
            <div style="
                background: linear-gradient(135deg, rgba(255,255,255,0.75), rgba(255,255,255,0.65));
                border: 1px solid rgba(15,23,42,0.10);
                border-left: 4px solid rgba(37,99,235,0.55);
                border-radius: 18px;
                padding: 14px 16px;
                box-shadow: 0 10px 26px rgba(2,6,23,0.06);
            ">
                <p style="margin:0;color:#0b3b60;font-size:14px;font-weight:600;">
                    {tip}
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
