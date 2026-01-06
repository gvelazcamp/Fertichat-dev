# =========================
# UI_BUSCADOR.PY - MÓDULO BUSCADOR IA
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
# MÓDULO BUSCADOR IA
# =====================================================================

def detectar_intencion_buscador(pregunta: str) -> str:
    """
    Detecta qué tipo de consulta quiere el usuario en el buscador.
    Devuelve: 'ultima_factura', 'total_compras', 'cuantas_facturas', 'detalle', 'general'
    """
    p = pregunta.lower().strip()

    # Última factura / cuándo llegó
    if any(k in p for k in ['ultimo', 'última', 'ultima', 'cuando llego', 'cuando vino', 'llegó', 'vino']):
        return 'ultima_factura'

    # Total / cuánto gastamos
    if any(k in p for k in ['total', 'cuanto', 'cuánto', 'gastamos', 'compramos', 'suma']):
        return 'total_compras'

    # Cuántas facturas
    if any(k in p for k in ['cuantas', 'cuántas', 'cantidad de', 'numero de']):
        return 'cuantas_facturas'

    # Detalle
    if any(k in p for k in ['detalle', 'todas', 'listado', 'lista']):
        return 'detalle'

    return 'general'


def ejecutar_consulta_buscador(intencion: str, proveedor: str, articulo: str,
                               fecha_desde, fecha_hasta) -> Tuple[str, Optional[pd.DataFrame]]:
    """
    Ejecuta la consulta específica según la intención detectada.
    Usa directamente los filtros seleccionados.
    """

    # Limpiar valores
    prov_clean = proveedor.split('(')[0].strip() if proveedor and proveedor != "Todos" else None
    art_clean = articulo.strip() if articulo and articulo != "Todos" else None

    # =====================================================================
    # ÚLTIMA FACTURA
    # =====================================================================
    if intencion == 'ultima_factura':
        if art_clean:
            # Buscar última factura del artículo
            df = get_ultima_factura_de_articulo(art_clean)
            if df is not None and not df.empty:
                return f"🧾 Última factura del artículo '{art_clean}':", df
            return f"No encontré facturas del artículo '{art_clean}'.", None

        elif prov_clean:
            # Buscar última factura del proveedor
            df = get_ultima_factura_inteligente(prov_clean)
            if df is not None and not df.empty:
                return f"🧾 Última factura de '{prov_clean}':", df
            return f"No encontré facturas de '{prov_clean}'.", None

        return "Seleccioná un proveedor o artículo para ver la última factura.", None

    # =====================================================================
    # TOTAL COMPRAS
    # =====================================================================
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

            # Construir contexto para el título
            contexto = []
            if prov_clean:
                contexto.append(f"proveedor '{prov_clean}'")
            if art_clean:
                contexto.append(f"artículo '{art_clean}'")
            if fecha_desde or fecha_hasta:
                if fecha_desde and fecha_hasta:
                    contexto.append(f"del {fecha_desde.strftime('%d/%m/%Y')} al {fecha_hasta.strftime('%d/%m/%Y')}")
                elif fecha_desde:
                    contexto.append(f"desde {fecha_desde.strftime('%d/%m/%Y')}")
                else:
                    contexto.append(f"hasta {fecha_hasta.strftime('%d/%m/%Y')}")

            titulo = "💰 Total de compras"
            if contexto:
                titulo += f" ({', '.join(contexto)})"

            total_fmt = f"${float(total):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if total else "$0"

            resultado = pd.DataFrame({
                'Concepto': [titulo],
                'Registros': [int(registros) if registros else 0],
                'Total': [total_fmt]
            })

            return f"✅ {titulo}:", resultado

        return "No encontré compras con esos filtros.", None

    # =====================================================================
    # CUÁNTAS FACTURAS
    # =====================================================================
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
                'Concepto': ['Cantidad de facturas'],
                'Facturas únicas': [int(facturas) if facturas else 0],
                'Líneas totales': [int(lineas) if lineas else 0]
            })

            return "📊 Cantidad de facturas:", resultado

        return "No encontré facturas con esos filtros.", None

    # =====================================================================
    # GENERAL (pasar al procesador principal)
    # =====================================================================
    return None, None


# =====================================================================
# FUNCIÓN BUSCAR COMPROBANTES (para Buscador IA)
# =====================================================================

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


def mostrar_buscador_ia():
    """Pantalla del Buscador de Comprobantes - CON INTENCIONES IA"""

    st.title("🔍 Buscador de Comprobantes")
    st.markdown("Búsqueda con filtros + preguntas en lenguaje natural")

    # --- Selector principal: Factura o Lote ---
    tipo_busqueda = st.radio(
        "Buscar por:",
        ["📄 Factura", "📦 Lote"],
        horizontal=True,
        key="tipo_busqueda"
    )

    st.markdown("---")

    # =========================================================================
    # MODO FACTURA (tabla chatbot)
    # =========================================================================
    if tipo_busqueda == "📄 Factura":

        # ✅ CSS: Botón "🔎 Buscar" más chico (solo en Factura)
        st.markdown("""
        <style>
        div[data-testid="stButton"] button{
          padding: 0.25rem 0.65rem !important;
          font-size: 0.85rem !important;
          line-height: 1.1 !important;
          min-height: 32px !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # --- Cargar listas desde la DB ---
        lista_proveedores = get_lista_proveedores()
        lista_tipos = get_lista_tipos_comprobante()
        lista_articulos = get_lista_articulos()

        # --- Fila 1: Filtros principales ---
        col1, col2, col3, col4 = st.columns([2, 3, 3, 3])

        with col1:
            empresa = st.selectbox("Empresa", ["FERTILAB SA"], disabled=True)

        with col2:
            proveedor = st.selectbox(
                "Cliente / Proveedor",
                lista_proveedores,
                index=0
            )

        with col3:
            tipo_comprobante = st.selectbox(
                "Tipo de Comprobante",
                lista_tipos,
                index=0
            )

        with col4:
            articulo = st.selectbox(
                "Artículo",
                lista_articulos,
                index=0
            )

        # --- Fila 2: Fechas y búsqueda ---
        col5, col6, col7, col8, col9 = st.columns([2, 2, 3, 3, 1])

        with col5:
            fecha_desde = st.date_input(
                "Fecha desde",
                value=None,
                format="DD/MM/YYYY"
            )

        with col6:
            fecha_hasta = st.date_input(
                "Fecha hasta",
                value=None,
                format="DD/MM/YYYY"
            )

        with col7:
            texto_busqueda = st.text_input(
                "Buscar número o texto",
                placeholder="Ej: 275217 o VITEK"
            )

        with col8:
            pregunta_ia = st.text_input(
                "Preguntar IA (opcional)",
                placeholder="Ej: cuándo llegó el último?"
            )

        with col9:
            st.markdown("<br>", unsafe_allow_html=True)
            buscar = st.button("🔎 Buscar", use_container_width=True)

        # --- Ayuda contextual ---
        if proveedor != "Todos" or articulo != "Todos":
            contexto_actual = []
            if proveedor != "Todos":
                contexto_actual.append(f"**{proveedor.split('(')[0].strip()}**")
            if articulo != "Todos":
                contexto_actual.append(f"**{articulo}**")

            st.caption(f"💡 Contexto seleccionado: {', '.join(contexto_actual)} — Podés preguntar: 'cuánto compramos', 'última factura', 'total del mes'...")

        st.markdown("---")

        # --- Ejecutar búsqueda FACTURA ---
        if buscar:

            # OPCIÓN 1: PREGUNTA IA
            if pregunta_ia and pregunta_ia.strip():
                intencion = detectar_intencion_buscador(pregunta_ia)

                contexto_texto = []
                if proveedor != "Todos":
                    contexto_texto.append(f"proveedor: {proveedor.split('(')[0].strip()}")
                if articulo != "Todos":
                    contexto_texto.append(f"artículo: {articulo}")

                if contexto_texto:
                    st.info(f"🧠 Procesando: *\"{pregunta_ia}\"* con contexto: {', '.join(contexto_texto)}")
                else:
                    st.info(f"🧠 Procesando: *\"{pregunta_ia}\"*")

                with st.spinner("🧠 Analizando..."):
                    respuesta, df = ejecutar_consulta_buscador(
                        intencion,
                        proveedor if proveedor != "Todos" else None,
                        articulo if articulo != "Todos" else None,
                        fecha_desde,
                        fecha_hasta
                    )

                    if respuesta is None:
                        pregunta_completa = pregunta_ia.strip()
                        if proveedor != "Todos":
                            pregunta_completa += f" {proveedor.split('(')[0].strip()}"
                        if articulo != "Todos":
                            pregunta_completa += f" {articulo}"
                        respuesta, df = procesar_pregunta(pregunta_completa)
                    else:
                        pregunta_completa = pregunta_ia.strip()

                    render_orquestador_output(pregunta_completa, respuesta, df)

                    if df is not None and not df.empty:
                        st.dataframe(
                            formatear_dataframe(df),
                            use_container_width=True,
                            hide_index=True
                        )

            # OPCIÓN 2: BÚSQUEDA POR FILTROS
            else:
                with st.spinner("🔍 Buscando comprobantes..."):
                    df = buscar_comprobantes(
                        proveedor=proveedor if proveedor != "Todos" else None,
                        tipo_comprobante=tipo_comprobante if tipo_comprobante != "Todos" else None,
                        articulo=articulo if articulo != "Todos" else None,
                        fecha_desde=fecha_desde,
                        fecha_hasta=fecha_hasta,
                        texto_busqueda=texto_busqueda
                    )

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
            st.info("👆 Seleccioná filtros y presioná **Buscar**, o escribí una pregunta en 'Preguntar IA'")

    # =========================================================================
    # MODO LOTE (tabla stock)
    # =========================================================================
    else:  # tipo_busqueda == "📦 Lote"

        # --- Cargar listas desde tabla stock ---
        lista_articulos_stock = get_lista_articulos_stock()
        lista_familias_stock = get_lista_familias_stock()
        lista_depositos_stock = get_lista_depositos_stock()

        # --- Fila 1: Filtros principales ---
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

        with col1:
            articulo_stock = st.selectbox(
                "Artículo",
                lista_articulos_stock,
                index=0,
                key="articulo_stock"
            )

        with col2:
            familia_stock = st.selectbox(
                "Familia",
                lista_familias_stock,
                index=0,
                key="familia_stock"
            )

        with col3:
            deposito_stock = st.selectbox(
                "Depósito",
                lista_depositos_stock,
                index=0,
                key="deposito_stock"
            )

        with col4:
            lote_busqueda = st.text_input(
                "Número de Lote",
                placeholder="Ej: D250829AF",
                key="lote_busqueda"
            )

        # --- Fila 2: Búsqueda y botón ---
        col5, col6, col7 = st.columns([4, 4, 1])

        with col5:
            texto_busqueda_stock = st.text_input(
                "Buscar texto (artículo, código o lote)",
                placeholder="Ej: VITEK o 15625",
                key="texto_stock"
            )

        with col6:
            pregunta_ia_stock = st.text_input(
                "Preguntar IA (opcional)",
                placeholder="Ej: qué lotes vencen pronto?",
                key="pregunta_stock"
            )

        with col7:
            st.markdown("<br>", unsafe_allow_html=True)
            buscar_stock = st.button("🔎 Buscar", use_container_width=True, key="btn_stock")

        st.markdown("---")

        # --- Ejecutar búsqueda LOTE ---
        if buscar_stock:

            with st.spinner("🔍 Buscando en stock..."):
                df = buscar_stock_por_lote(
                    articulo=articulo_stock if articulo_stock != "Todos" else None,
                    lote=lote_busqueda,
                    familia=familia_stock if familia_stock != "Todos" else None,
                    deposito=deposito_stock if deposito_stock != "Todos" else None,
                    texto_busqueda=texto_busqueda_stock
                )

                if df is not None and not df.empty:
                    st.success(f"✅ Se encontraron **{len(df)}** registros de stock")

                    # Calcular total de stock
                    if 'STOCK' in df.columns:
                        try:
                            total_stock = df['STOCK'].apply(lambda x: float(
                                str(x).replace(',', '.')
                            ) if pd.notna(x) else 0).sum()
                            st.info(f"📦 **Stock total:** {total_stock:,.0f} unidades".replace(',', '.'))
                        except:
                            pass

                    st.dataframe(
                        df,
                        use_container_width=True,
                        hide_index=True
                    )

                    # Descargar Excel
                    excel_data = df_to_excel(df)
                    st.download_button(
                        label="📥 Descargar Excel",
                        data=excel_data,
                        file_name="stock_lotes.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("⚠️ No se encontraron resultados con esos filtros")

        else:
            st.info("👆 Seleccioná filtros y presioná **Buscar** para buscar lotes en stock")

