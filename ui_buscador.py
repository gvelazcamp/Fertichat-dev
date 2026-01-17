# =========================
# UI_BUSCADOR.PY - MÓDULO BUSCADOR IA REFACTORIZADO
# =========================

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Tuple, Optional

from utils_format import formatear_dataframe, df_to_excel
from sql_core import (
    ejecutar_consulta,
    get_lista_proveedores,
    get_lista_tipos_comprobante,
    get_lista_articulos,
    get_lista_articulos_stock,
    get_lista_familias_stock,
    get_lista_depositos_stock,
    buscar_stock_por_lote,
    _sql_fecha_expr,
    _sql_total_num_expr_general,
)

# =====================================================================
# FUNCIONES AUXILIARES
# =====================================================================

def guardar_busqueda_reciente(tipo: str, proveedor: str, articulo: str, fecha_desde, fecha_hasta, pregunta: str = None):
    """Guarda una búsqueda en el histórico."""
    if "historico_busquedas" not in st.session_state:
        st.session_state["historico_busquedas"] = []
    
    # Construir descripción
    desc = []
    if tipo == "factura":
        if proveedor and proveedor != "Todos":
            desc.append(f"Facturas de {proveedor.split('(')[0].strip()}")
        if articulo and articulo != "Todos":
            desc.append(f"Artículo {articulo}")
        if fecha_desde and fecha_hasta:
            desc.append(f"{fecha_desde.strftime('%d/%m/%Y')} - {fecha_hasta.strftime('%d/%m/%Y')}")
        if pregunta:
            desc.append(f"Pregunta: {pregunta}")
    else:
        desc.append("Búsqueda de lotes en stock")
    
    if desc:
        busqueda = {
            "timestamp": datetime.now(),
            "tipo": tipo,
            "descripcion": " | ".join(desc)
        }
        st.session_state["historico_busquedas"].insert(0, busqueda)
        # Limitar a últimas 10
        st.session_state["historico_busquedas"] = st.session_state["historico_busquedas"][:10]


def obtener_historico():
    """Obtiene el histórico de búsquedas."""
    return st.session_state.get("historico_busquedas", [])


def detectar_intencion_buscador(pregunta: str) -> str:
    """
    Detecta qué tipo de consulta quiere el usuario.
    Devuelve: 'ultima_factura', 'total_compras', 'cuantas_facturas', 'detalle', 'general'
    """
    p = pregunta.lower().strip()

    if any(k in p for k in ['ultimo', 'última', 'ultima', 'cuando llego', 'cuando vino', 'llegó', 'vino']):
        return 'ultima_factura'

    if any(k in p for k in ['total', 'cuanto', 'cuánto', 'gastamos', 'compramos', 'suma']):
        return 'total_compras'

    if any(k in p for k in ['cuantas', 'cuántas', 'cantidad de', 'numero de']):
        return 'cuantas_facturas'

    if any(k in p for k in ['detalle', 'todas', 'listado', 'lista']):
        return 'detalle'

    return 'general'


def ejecutar_consulta_buscador(intencion: str, proveedor: str, articulo: str,
                               fecha_desde, fecha_hasta) -> Tuple[str, Optional[pd.DataFrame]]:
    """Ejecuta la consulta según la intención detectada."""
    
    prov_clean = proveedor.split('(')[0].strip() if proveedor and proveedor != "Todos" else None
    art_clean = articulo.strip() if articulo and articulo != "Todos" else None

    # ÚLTIMA FACTURA
    if intencion == 'ultima_factura':
        if art_clean:
            df = get_ultima_factura_de_articulo(art_clean)
            if df is not None and not df.empty:
                return f"🧾 Última factura del artículo '{art_clean}':", df
            return f"No encontré facturas del artículo '{art_clean}'.", None
        elif prov_clean:
            df = get_ultima_factura_inteligente(prov_clean)
            if df is not None and not df.empty:
                return f"🧾 Última factura de '{prov_clean}':", df
            return f"No encontré facturas de '{prov_clean}'.", None
        return "Seleccioná un proveedor o artículo para ver la última factura.", None

    # TOTAL COMPRAS
    elif intencion == 'total_compras':
        fecha_expr = _sql_fecha_expr()
        total_expr = _sql_total_num_expr_general()

        sql = f"""
            SELECT 
                COUNT(*) AS Registros,
                SUM({total_expr}) AS Total
            FROM chatbot
            WHERE (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
        """
        params = []

        if prov_clean:
            sql += " AND LOWER(TRIM(Proveedor)) LIKE LOWER(%s)"
            params.append(f"%{prov_clean}%")

        if art_clean:
            sql += " AND LOWER(TRIM(Articulo)) LIKE LOWER(%s)"
            params.append(f"%{art_clean}%")

        if fecha_desde:
            sql += f" AND {fecha_expr} >= %s"
            params.append(fecha_desde.strftime('%Y-%m-%d'))

        if fecha_hasta:
            sql += f" AND {fecha_expr} <= %s"
            params.append(fecha_hasta.strftime('%Y-%m-%d'))

        df = ejecutar_consulta(sql, tuple(params) if params else None)

        if df is not None and not df.empty:
            registros = df['Registros'].iloc[0]
            total = df['Total'].iloc[0]
            total_fmt = f"${float(total):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if total else "$0"

            resultado = pd.DataFrame({
                'Total': [total_fmt],
                'Registros': [int(registros) if registros else 0]
            })
            return f"💰 Total de compras:", resultado

        return "No encontré compras con esos filtros.", None

    # CUÁNTAS FACTURAS
    elif intencion == 'cuantas_facturas':
        fecha_expr = _sql_fecha_expr()

        sql = f"""
            SELECT 
                COUNT(DISTINCT `N Factura`) AS Facturas,
                COUNT(*) AS Lineas
            FROM chatbot
            WHERE (tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')
        """
        params = []

        if prov_clean:
            sql += " AND LOWER(TRIM(Proveedor)) LIKE LOWER(%s)"
            params.append(f"%{prov_clean}%")

        if art_clean:
            sql += " AND LOWER(TRIM(Articulo)) LIKE LOWER(%s)"
            params.append(f"%{art_clean}%")

        if fecha_desde:
            sql += f" AND {fecha_expr} >= %s"
            params.append(fecha_desde.strftime('%Y-%m-%d'))

        if fecha_hasta:
            sql += f" AND {fecha_expr} <= %s"
            params.append(fecha_hasta.strftime('%Y-%m-%d'))

        df = ejecutar_consulta(sql, tuple(params) if params else None)

        if df is not None and not df.empty:
            facturas = df['Facturas'].iloc[0]
            lineas = df['Lineas'].iloc[0]

            resultado = pd.DataFrame({
                'Facturas únicas': [int(facturas) if facturas else 0],
                'Líneas totales': [int(lineas) if lineas else 0]
            })
            return "📊 Cantidad de facturas:", resultado

        return "No encontré facturas con esos filtros.", None

    return None, None


def buscar_comprobantes(
    proveedor: str = None,
    tipo_comprobante: str = None,
    articulo: str = None,
    fecha_desde = None,
    fecha_hasta = None,
    texto_busqueda: str = None
) -> pd.DataFrame:
    """Busca comprobantes en chatbot_raw con filtros opcionales."""
    try:
        sql = """
            SELECT 
                "Fecha",
                "Tipo Comprobante" AS "Tipo",
                "Nro. Comprobante" AS "Nro Factura",
                "Cliente / Proveedor" AS "Proveedor",
                "Articulo",
                "Cantidad",
                "Monto Neto" AS "Monto"
            FROM chatbot_raw
            WHERE 1=1
        """
        params = []

        if tipo_comprobante:
            sql += ' AND "Tipo Comprobante" = %s'
            params.append(tipo_comprobante)
        else:
            sql += ' AND ("Tipo Comprobante" = \'Compra Contado\' OR "Tipo Comprobante" LIKE \'Compra%%\')'

        if proveedor:
            prov_clean = proveedor.split('(')[0].strip()
            sql += ' AND LOWER(TRIM("Cliente / Proveedor")) LIKE LOWER(%s)'
            params.append(f"%{prov_clean}%")

        if articulo:
            sql += ' AND LOWER(TRIM("Articulo")) LIKE LOWER(%s)'
            params.append(f"%{articulo}%")

        if fecha_desde:
            sql += ' AND "Fecha" >= %s'
            params.append(fecha_desde.strftime('%Y-%m-%d'))

        if fecha_hasta:
            sql += ' AND "Fecha" <= %s'
            params.append(fecha_hasta.strftime('%Y-%m-%d'))

        if texto_busqueda and texto_busqueda.strip():
            txt = texto_busqueda.strip()
            sql += """
                AND (
                    LOWER("Nro. Comprobante") LIKE LOWER(%s) OR
                    LOWER("Articulo") LIKE LOWER(%s) OR
                    LOWER("Cliente / Proveedor") LIKE LOWER(%s)
                )
            """
            params.extend([f"%{txt}%", f"%{txt}%", f"%{txt}%"])

        sql += ' ORDER BY "Fecha" DESC LIMIT 500'

        return ejecutar_consulta(sql, tuple(params) if params else None)

    except Exception as e:
        print(f"Error en buscar_comprobantes: {e}")
        return pd.DataFrame()


# =====================================================================
# COMPONENTES UI
# =====================================================================

def mostrar_filtros_rapidos():
    """Panel de búsqueda rápida."""
    st.subheader("🔍 Búsqueda Rápida")
    
    lista_proveedores = get_lista_proveedores()
    lista_articulos = get_lista_articulos()
    lista_tipos = get_lista_tipos_comprobante()
    
    # Fila 1: Filtros principales
    col1, col2, col3 = st.columns([2.5, 2.5, 2.5])
    
    with col1:
        proveedor = st.selectbox(
            "Cliente / Proveedor",
            lista_proveedores,
            index=0,
            key="prov_rapida"
        )
    
    with col2:
        tipo_comprobante = st.selectbox(
            "Tipo de Comprobante",
            lista_tipos,
            index=0,
            key="tipo_rapida"
        )
    
    with col3:
        articulo = st.selectbox(
            "Artículo",
            lista_articulos,
            index=0,
            key="art_rapida"
        )
    
    # Fila 2: Fechas y búsqueda
    col4, col5, col6, col7 = st.columns([2, 2, 2.5, 0.8])
    
    with col4:
        fecha_desde = st.date_input(
            "Fecha desde",
            value=None,
            format="DD/MM/YYYY",
            key="fecha_desde_rapida"
        )
    
    with col5:
        fecha_hasta = st.date_input(
            "Fecha hasta",
            value=None,
            format="DD/MM/YYYY",
            key="fecha_hasta_rapida"
        )
    
    with col6:
        texto_busqueda = st.text_input(
            "Buscar número o texto",
            placeholder="Ej: 275217 o VITEK",
            key="texto_rapida"
        )
    
    with col7:
        st.markdown("<br>", unsafe_allow_html=True)
        buscar_rapido = st.button("Buscar", use_container_width=True, key="btn_rapida")
    
    return buscar_rapido, proveedor, tipo_comprobante, articulo, fecha_desde, fecha_hasta, texto_busqueda


def mostrar_filtros_avanzados():
    """Panel de búsqueda avanzada."""
    st.subheader("🔎 Búsqueda Avanzada")
    
    lista_proveedores = get_lista_proveedores()
    lista_articulos = get_lista_articulos()
    lista_tipos = get_lista_tipos_comprobante()
    
    # Fila 1: Empresa y Cliente
    col1, col2 = st.columns([2, 4])
    
    with col1:
        empresa = st.selectbox("Empresa", ["FERTILAB SA"], disabled=True, key="empresa_avanza")
    
    with col2:
        proveedor = st.selectbox(
            "Cliente / Proveedor",
            lista_proveedores,
            index=0,
            key="prov_avanza"
        )
    
    # Fila 2: Tipo y Artículo
    col3, col4 = st.columns([3, 3])
    
    with col3:
        tipo_comprobante = st.selectbox(
            "Tipo de Comprobante",
            lista_tipos,
            index=0,
            key="tipo_avanza"
        )
    
    with col4:
        articulo = st.selectbox(
            "Artículo",
            lista_articulos,
            index=0,
            key="art_avanza"
        )
    
    # Fila 3: Fechas
    col5, col6 = st.columns([3, 3])
    
    with col5:
        fecha_desde = st.date_input(
            "Fecha desde",
            value=None,
            format="DD/MM/YYYY",
            key="fecha_desde_avanza"
        )
    
    with col6:
        fecha_hasta = st.date_input(
            "Fecha hasta",
            value=None,
            format="DD/MM/YYYY",
            key="fecha_hasta_avanza"
        )
    
    # Fila 4: Búsquedas de texto
    col7, col8 = st.columns([3, 3])
    
    with col7:
        texto_busqueda = st.text_input(
            "Buscar número o artículo",
            placeholder="Ej: 275217 o VITEK",
            key="texto_avanza"
        )
    
    with col8:
        palabra_clave = st.text_input(
            "Palabra clave adicional",
            placeholder="Búsqueda adicional",
            key="palabra_avanza"
        )
    
    # Botón
    col9, col10, col11 = st.columns([3, 3, 1])
    with col11:
        st.markdown("<br>", unsafe_allow_html=True)
        buscar_avanza = st.button("Buscar", use_container_width=True, key="btn_avanza")
    
    return buscar_avanza, proveedor, tipo_comprobante, articulo, fecha_desde, fecha_hasta, texto_busqueda


def mostrar_panel_ia():
    """Panel colapsable de consulta a IA."""
    with st.sidebar:
        st.markdown("---")
        with st.expander("💬 Consultar a la IA", expanded=False):
            st.markdown("""
            **Pregúntale a la IA en lenguaje natural:**
            
            Ejemplos:
            - "¿Cuáles fueron las compras de Roche este mes?"
            - "¿Cuándo llegó el último comprobante?"
            - "Total de compras de ABBOTT"
            - "Facturas del mes pasado"
            """)
            
            pregunta_ia = st.text_input(
                "Tu pregunta:",
                placeholder="Ej: cuándo llegó el último comprobante de Roche?",
                key="pregunta_ia_main"
            )
            
            buscar_ia = st.button("🤖 Preguntar", use_container_width=True, key="btn_ia")
            
            return pregunta_ia, buscar_ia
    
    return None, False


def mostrar_historico():
    """Muestra el histórico de búsquedas recientes."""
    historico = obtener_historico()
    
    if historico:
        st.markdown("---")
        col1, col2 = st.columns([5, 1])
        
        with col1:
            st.subheader("🕐 Búsquedas Recientes")
        
        with col2:
            if st.button("Ver más", key="ver_mas_historico"):
                st.session_state["mostrar_todo_historico"] = True
        
        mostrar_todo = st.session_state.get("mostrar_todo_historico", False)
        items_mostrar = historico if mostrar_todo else historico[:2]
        
        for i, busqueda in enumerate(items_mostrar):
            tiempo_atras = datetime.now() - busqueda["timestamp"]
            
            if tiempo_atras.total_seconds() < 60:
                tiempo_texto = "Hace poco"
            elif tiempo_atras.total_seconds() < 3600:
                minutos = int(tiempo_atras.total_seconds() / 60)
                tiempo_texto = f"Hace {minutos} min"
            elif tiempo_atras.total_seconds() < 86400:
                horas = int(tiempo_atras.total_seconds() / 3600)
                tiempo_texto = f"Hace {horas} horas"
            else:
                dias = int(tiempo_atras.total_seconds() / 86400)
                tiempo_texto = f"Hace {dias} días"
            
            col1, col2 = st.columns([0.9, 4])
            
            with col1:
                if busqueda["tipo"] == "factura":
                    st.markdown("🔍")
                else:
                    st.markdown("📦")
            
            with col2:
                st.caption(f"**{busqueda['descripcion']}**")
                st.caption(f"_{tiempo_texto}_", help="Última búsqueda")


# =====================================================================
# FUNCIÓN PRINCIPAL
# =====================================================================

def mostrar_buscador_ia():
    """Pantalla principal del Buscador de Comprobantes - VERSIÓN PROFESIONAL."""
    
    # CSS para mejorar apariencia
    st.markdown("""
    <style>
    /* Tabs más compactas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 12px 24px;
        font-weight: 600;
        font-size: 14px;
    }
    
    /* Cards de filtros */
    div[data-testid="stExpander"] {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header con SVG Lupa
    lupa_svg = """
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg" style="display: inline-block; margin-right: 8px; vertical-align: middle;">
        <circle cx="11" cy="11" r="7" stroke="#2563eb" stroke-width="2" fill="none"/>
        <path d="M17 17L24 24" stroke="#2563eb" stroke-width="2" stroke-linecap="round"/>
    </svg>
    """
    
    col1, col2 = st.columns([0.12, 0.88])
    with col1:
        st.markdown(lupa_svg, unsafe_allow_html=True)
    with col2:
        st.title("Buscador de Comprobantes", anchor=False)
    
    st.markdown("Búsqueda con filtros + consultas a la IA")
    
    # Panel IA en sidebar
    pregunta_ia, buscar_ia = mostrar_panel_ia()
    
    # Tabs principales
    tab_rapida, tab_avanzada = st.tabs(["🚀 Búsqueda Rápida", "🔎 Búsqueda Avanzada"])
    
    with tab_rapida:
        buscar, prov, tipo, art, f_desde, f_hasta, texto = mostrar_filtros_rapidos()
        
        if buscar:
            with st.spinner("🔍 Buscando comprobantes..."):
                df = buscar_comprobantes(
                    proveedor=prov if prov != "Todos" else None,
                    tipo_comprobante=tipo if tipo != "Todos" else None,
                    articulo=art if art != "Todos" else None,
                    fecha_desde=f_desde,
                    fecha_hasta=f_hasta,
                    texto_busqueda=texto
                )
                
                guardar_busqueda_reciente("factura", prov, art, f_desde, f_hasta)
                
                if df is not None and not df.empty:
                    st.success(f"✅ Se encontraron **{len(df)}** comprobantes")
                    
                    if 'Monto' in df.columns:
                        try:
                            montos = df['Monto'].apply(lambda x: float(
                                str(x).replace('.', '').replace(',', '.').replace('$', '').replace(' ', '')
                            ) if pd.notna(x) else 0)
                            total = montos.sum()
                            st.info(f"💰 **Total:** ${total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
                        except:
                            pass
                    
                    st.dataframe(
                        formatear_dataframe(df),
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    excel_data = df_to_excel(df)
                    st.download_button(
                        label="📥 Descargar Excel",
                        data=excel_data,
                        file_name="comprobantes.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("⚠️ No se encontraron resultados con esos filtros")
        else:
            st.info("👆 Seleccioná filtros y presioná **Buscar**")
    
    with tab_avanzada:
        buscar_a, prov_a, tipo_a, art_a, f_desde_a, f_hasta_a, texto_a = mostrar_filtros_avanzados()
        
        if buscar_a:
            with st.spinner("🔍 Buscando comprobantes..."):
                df = buscar_comprobantes(
                    proveedor=prov_a if prov_a != "Todos" else None,
                    tipo_comprobante=tipo_a if tipo_a != "Todos" else None,
                    articulo=art_a if art_a != "Todos" else None,
                    fecha_desde=f_desde_a,
                    fecha_hasta=f_hasta_a,
                    texto_busqueda=texto_a
                )
                
                guardar_busqueda_reciente("factura", prov_a, art_a, f_desde_a, f_hasta_a)
                
                if df is not None and not df.empty:
                    st.success(f"✅ Se encontraron **{len(df)}** comprobantes")
                    
                    if 'Monto' in df.columns:
                        try:
                            montos = df['Monto'].apply(lambda x: float(
                                str(x).replace('.', '').replace(',', '.').replace('$', '').replace(' ', '')
                            ) if pd.notna(x) else 0)
                            total = montos.sum()
                            st.info(f"💰 **Total:** ${total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
                        except:
                            pass
                    
                    st.dataframe(
                        formatear_dataframe(df),
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    excel_data = df_to_excel(df)
                    st.download_button(
                        label="📥 Descargar Excel",
                        data=excel_data,
                        file_name="comprobantes.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("⚠️ No se encontraron resultados con esos filtros")
        else:
            st.info("👆 Seleccioná filtros y presioná **Buscar**")
    
    # Búsqueda IA desde sidebar
    if buscar_ia and pregunta_ia:
        st.markdown("---")
        st.subheader("🤖 Respuesta de la IA")
        
        with st.spinner("🧠 Analizando tu pregunta..."):
            intencion = detectar_intencion_buscador(pregunta_ia)
            respuesta, df = ejecutar_consulta_buscador(
                intencion,
                None,
                None,
                None,
                None
            )
            
            if respuesta:
                st.info(respuesta)
            
            if df is not None and not df.empty:
                st.dataframe(
                    formatear_dataframe(df),
                    use_container_width=True,
                    hide_index=True
                )
    
    # Histórico de búsquedas
    mostrar_historico()
