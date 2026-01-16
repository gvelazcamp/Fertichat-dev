import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Tuple, Optional
import time

from utils_format import formatear_dataframe, df_to_excel
from sql_stock import (
    get_stock_total,
    get_stock_por_familia,
    get_stock_por_deposito,
    get_stock_articulo,
    get_stock_familia,
    get_lotes_por_vencer,
    get_lotes_vencidos,
    get_stock_bajo,
    get_stock_lote_especifico,
    get_alertas_vencimiento_multiple,
)

# =====================================================================
# MÓDULO STOCK IA (CHATBOT)
# =====================================================================

def detectar_intencion_stock(texto: str) -> dict:
    """Detecta la intención para consultas de stock"""
    texto_lower = texto.lower().strip()

    # Vencimientos
    if any(k in texto_lower for k in ['vencer', 'vencen', 'vencimiento', 'vence', 'por vencer']):
        if 'vencido' in texto_lower or 'ya vencio' in texto_lower:
            return {'tipo': 'lotes_vencidos', 'debug': 'Lotes vencidos'}
        # Extraer días si se menciona
        import re
        match = re.search(r'(\d+)\s*(dias|día|dia|días)', texto_lower)
        dias = int(match.group(1)) if match else 90
        return {'tipo': 'lotes_por_vencer', 'dias': dias, 'debug': f'Lotes por vencer en {dias} días'}

    # Vencidos
    if any(k in texto_lower for k in ['vencido', 'vencidos', 'ya vencio', 'caducado']):
        return {'tipo': 'lotes_vencidos', 'debug': 'Lotes vencidos'}

    # Stock bajo
    if any(k in texto_lower for k in ['stock bajo', 'poco stock', 'bajo stock', 'quedan pocos', 'se acaba', 'reponer']):
        return {'tipo': 'stock_bajo', 'debug': 'Stock bajo'}

    # Lote específico
    if any(k in texto_lower for k in ['lote', 'nro lote', 'numero de lote']):
        # Buscar patrón de lote (alfanumérico)
        import re
        match = re.search(r'lote\s+(\w+)', texto_lower)
        if match:
            return {'tipo': 'lote_especifico', 'lote': match.group(1), 'debug': f'Lote específico: {match.group(1)}'}

    # Stock por familia
    if any(k in texto_lower for k in ['familia', 'familias', 'por familia', 'seccion', 'secciones']):
        # Ver si menciona una familia específica
        familias_conocidas = ['id', 'fb', 'g', 'tr', 'xx', 'hm', 'mi']
        for fam in familias_conocidas:
            if fam in texto_lower.split():
                return {'tipo': 'stock_familia', 'familia': fam.upper(), 'debug': f'Stock familia {fam.upper()}'}
        return {'tipo': 'stock_por_familia', 'debug': 'Stock por familias'}

    # ✅ NUEVO: Detectar familias cortas ANTES de buscar artículos
    familias_conocidas = ['id', 'fb', 'g', 'tr', 'xx', 'hm', 'mi']
    palabras = texto_lower.split()
    for fam in familias_conocidas:
        if fam in palabras:
            return {'tipo': 'stock_familia', 'familia': fam.upper(), 'debug': f'Stock familia {fam.upper()}'}

    # Stock por depósito
    if any(k in texto_lower for k in ['deposito', 'depósito', 'depositos', 'depósitos', 'almacen']):
        return {'tipo': 'stock_por_deposito', 'debug': 'Stock por depósito'}

    # Stock de artículo específico
    if any(k in texto_lower for k in ['stock', 'cuanto hay', 'cuánto hay', 'tenemos', 'disponible', 'hay']):
        # Extraer nombre del artículo
        palabras_excluir = ['stock', 'cuanto', 'cuánto', 'hay', 'de', 'del', 'tenemos', 'disponible', 'el', 'la', 'los', 'las', 'que']
        palabras = [p for p in texto_lower.split() if p not in palabras_excluir and len(p) > 2]
        if palabras:
            articulo = ' '.join(palabras)
            return {'tipo': 'stock_articulo', 'articulo': articulo, 'debug': f'Stock de artículo: {articulo}'}

    # Total general
    if any(k in texto_lower for k in ['total', 'resumen', 'general', 'todo el stock']):
        return {'tipo': 'stock_total', 'debug': 'Stock total'}

    # Por defecto, intentar buscar artículo
    return {'tipo': 'stock_articulo', 'articulo': texto, 'debug': f'Búsqueda general: {texto}'}


def _clean_stock_df(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia el DataFrame de stock: filtra (INACTIVO), si hay stock >0 mostrar solo esos; si todo =0 mostrar 1 fila genérica."""
    if df is None or df.empty:
        return df
    
    df = df.copy()
    df['STOCK'] = df['STOCK'].apply(lambda x: float(str(x).replace(',', '.').replace(' ', '')) if pd.notna(x) else 0)
    
    # ✅ FILTRAR ARTÍCULOS (INACTIVO) ANTES DE PROCESAR
    df = df[~df['ARTICULO'].str.lower().str.contains('(inactivo)', na=False)]
    
    grouped = df.groupby('ARTICULO')
    cleaned_rows = []
    
    for articulo, group in grouped:
        stock_positive = group[group['STOCK'] > 0]
        if not stock_positive.empty:
            # ✅ Si hay lotes con stock >0, mostrar SOLO esos (sin filas genéricas de 0)
            cleaned_rows.extend(stock_positive.to_dict('records'))
        else:
            # ✅ Si todos =0, mostrar 1 fila genérica para pedir
            row = group.iloc[0].copy()
            row['LOTE'] = '-'
            row['VENCIMIENTO'] = None
            row['Dias_Para_Vencer'] = None
            cleaned_rows.append(row)
    
    return pd.DataFrame(cleaned_rows)

def procesar_pregunta_stock(pregunta: str) -> Tuple[str, Optional[pd.DataFrame]]:
    """Procesa una pregunta sobre stock"""

    intencion = detectar_intencion_stock(pregunta)
    tipo = intencion.get('tipo')

    print(f"🔍 STOCK IA - Intención: {tipo}")
    print(f"📋 Debug: {intencion.get('debug')}")

    # Stock total
    if tipo == 'stock_total':
        df = get_stock_total()
        if df is not None and not df.empty:
            return "📦 Resumen de stock total:", df
        return "No pude obtener el stock total.", None

    # Stock por familia
    if tipo == 'stock_por_familia':
        df = get_stock_por_familia()
        if df is not None and not df.empty:
            return "📊 Stock agrupado por familia:", df
        return "No encontré datos de stock por familia.", None

    # Stock de una familia específica
    if tipo == 'stock_familia':
        familia = intencion.get('familia', '')
        df = get_stock_familia(familia)
        if df is not None and not df.empty:
            df = _clean_stock_df(df)  # ✅ Limpiar stock 0
            return f"📦 Stock de familia {familia}:", df
        return f"No encontré stock para la familia {familia}.", None

    # Stock por depósito
    if tipo == 'stock_por_deposito':
        df = get_stock_por_deposito()
        if df is not None and not df.empty:
            return "🏢 Stock agrupado por depósito:", df
        return "No encontré datos de stock por depósito.", None

    # Lotes por vencer
    if tipo == 'lotes_por_vencer':
        dias = intencion.get('dias', 90)
        df = get_lotes_por_vencer(dias)
        if df is not None and not df.empty:
            df = _clean_stock_df(df)  # ✅ Limpiar stock 0
            return f"⚠️ Lotes que vencen en los próximos {dias} días:", df
        return f"No hay lotes que venzan en los próximos {dias} días.", None

    # Lotes vencidos
    if tipo == 'lotes_vencidos':
        df = get_lotes_vencidos()
        if df is not None and not df.empty:
            df = _clean_stock_df(df)  # ✅ Limpiar stock 0
            return "🚨 Lotes ya vencidos:", df
        return "No hay lotes vencidos registrados.", None

    # Stock bajo
    if tipo == 'stock_bajo':
        df = get_stock_bajo(10)
        if df is not None and not df.empty:
            df = _clean_stock_df(df)  # ✅ Limpiar stock 0
            return "📉 Artículos con stock bajo (≤10 unidades):", df
        return "No hay artículos con stock bajo.", None

    # Lote específico
    if tipo == 'lote_especifico':
        lote = intencion.get('lote', '')
        df = get_stock_lote_especifico(lote)
        if df is not None and not df.empty:
            df = _clean_stock_df(df)  # ✅ Limpiar stock 0
            return f"🔍 Información del lote {lote}:", df
        return f"No encontré el lote {lote}.", None

    # Stock de artículo
    if tipo == 'stock_articulo':
        articulo = intencion.get('articulo', pregunta)
        df = get_stock_articulo(articulo)
        if df is not None and not df.empty:
            df = _clean_stock_df(df)  # ✅ Limpiar stock 0
            return f"📦 Stock de '{articulo}':", df
        return f"No encontré stock para '{articulo}'.", None

    return "No entendí la consulta. Probá con: 'stock vitek', 'lotes por vencer', 'stock bajo'.", None


# =========================
# 📦 RESUMEN STOCK (ROTATIVO CADA 5s)
# =========================
def _stock_to_float(x) -> float:
    try:
        if x is None:
            return 0.0
        s = str(x).strip().replace(" ", "")
        s = s.replace(",", ".")
        return float(s)
    except Exception:
        return 0.0


# Removido @st.cache_data para debug
def _get_stock_cantidad_1(top_n: int = 200) -> pd.DataFrame:
    # Cambiar a stock bajo (<=10) en lugar de exactamente =1
    df = get_stock_bajo(10)
    # DEBUG removido
    if df is None or df.empty:
        return pd.DataFrame(columns=["FAMILIA", "CODIGO", "ARTICULO", "DEPOSITO", "LOTE", "VENCIMIENTO", "STOCK"])

    # No filtrar a ≈1, mostrar todos con stock <=10
    dfx = df.copy()
    return dfx.head(int(top_n))


# Removido @st.cache_data para debug
def _get_lotes_proximos_a_vencer(dias: int = 365) -> pd.DataFrame:  # ✅ CAMBIADO A 365 DÍAS
    df = get_lotes_por_vencer(dias)
    # DEBUG removido
    if df is None or df.empty:
        return pd.DataFrame(columns=["FAMILIA", "CODIGO", "ARTICULO", "DEPOSITO", "LOTE", "VENCIMIENTO", "STOCK", "Dias_Para_Vencer"])
    return df


def mostrar_resumen_stock_rotativo(dias_vencer: int = 365):  # ✅ CAMBIADO DEFAULT A 365
    # ✅ No auto-refresh mientras el usuario está escribiendo en el input del Stock
    pregunta_actual = ""
    try:
        pregunta_actual = str(st.session_state.get(f"input_stock_{st.session_state.get('stock_input_counter', 0)}", "") or "")
    except Exception:
        pregunta_actual = ""

    tick = 0
    if not pregunta_actual.strip():
        try:
            from streamlit_autorefresh import st_autorefresh
            tick = st_autorefresh(interval=5000, key="__rotar_stock_5s__") or 0
        except Exception:
            tick = 0  # si no está instalado, queda fijo

    df_stock_1 = _get_stock_cantidad_1(top_n=200)
    df_vencer = _get_lotes_proximos_a_vencer(dias=int(dias_vencer))

    stock1_txt = "—"
    stock1_sub = "Sin registros con stock bajo"
    stock1_count = 0

    if df_stock_1 is not None and not df_stock_1.empty:
        stock1_count = len(df_stock_1)
        idx1 = int(tick) % stock1_count
        r1 = df_stock_1.iloc[idx1]

        art = str(r1.get("ARTICULO", "—"))
        lote = str(r1.get("LOTE", "—"))
        dep = str(r1.get("DEPOSITO", "—"))
        ven = str(r1.get("VENCIMIENTO", "—"))
        stk = str(r1.get("STOCK", "—"))

        stock1_txt = art
        stock1_sub = f"Lote {lote} | Depósito {dep} | Venc {ven} | Stock {stk}"

    vencer_txt = "—"
    vencer_sub = f"Sin lotes que venzan en {dias_vencer} días"
    vencer_count = 0

    if df_vencer is not None and not df_vencer.empty:
        vencer_count = len(df_vencer)
        idx2 = int(tick) % vencer_count
        r2 = df_vencer.iloc[idx2]

        art = str(r2.get("ARTICULO", "—"))
        lote = str(r2.get("LOTE", "—"))
        dep = str(r2.get("DEPOSITO", "—"))
        ven = str(r2.get("VENCIMIENTO", "—"))
        stk = str(r2.get("STOCK", "—"))
        dias = str(r2.get("Dias_Para_Vencer", "—"))

        vencer_txt = art
        vencer_sub = f"Lote {lote} | Depósito {dep} | Venc {ven} ({dias} días) | Stock {stk}"

    st.markdown("""
    <style>
      .mini-stock-wrap{
        display:flex;
        gap:12px;
        margin: 6px 0 10px 0;
      }
      .mini-stock-card{
        flex:1;
        border:1px solid #e5e7eb;
        border-radius:12px;
        padding:10px 12px;
        background: rgba(255,255,255,0.85);
      }
      .mini-stock-t{
        font-size:0.80rem;
        font-weight:600;
        opacity:0.85;
        margin:0;
      }
      .mini-stock-v{
        font-size:1.00rem;
        font-weight:700;
        margin:4px 0 0 0;
        line-height:1.15;
      }
      .mini-stock-s{
        font-size:0.80rem;
        opacity:0.75;
        margin:4px 0 0 0;
        line-height:1.2;
      }
      .mini-stock-badge{
        font-size:0.75rem;
        opacity:0.75;
        border:1px solid #e5e7eb;
        padding:2px 8px;
        border-radius:999px;
        background: rgba(255,255,255,0.7);
        white-space:nowrap;
        margin:4px 0 0 0;
      }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
      <div class="mini-stock-wrap">
        <div class="mini-stock-card">
          <div class="mini-stock-t">📉 Artículos con STOCK bajo (≤10)</div>
          <div class="mini-stock-v">{stock1_txt}</div>
          <div class="mini-stock-s">{stock1_sub}</div>
          <div class="mini-stock-badge">{stock1_count} regs</div>
        </div>

        <div class="mini-stock-card">
          <div class="mini-stock-t">⏳ Lotes próximos a vencer ({dias_vencer} días)</div>
          <div class="mini-stock-v">{vencer_txt}</div>
          <div class="mini-stock-s">{vencer_sub}</div>
          <div class="mini-stock-badge">{vencer_count} regs</div>
        </div>
      </div>
    """, unsafe_allow_html=True)


# =========================
# 📦 STOCK IA (SIN TARJETAS ADENTRO)
# =========================
def mostrar_stock_ia():
    """Módulo Stock IA - Chat para consultas de stock"""

    # ✅ INICIALIZAR FLAG PARA PAUSAR AUTOREFRESH
    if "pause_autorefresh_stock" not in st.session_state:
        st.session_state["pause_autorefresh_stock"] = False

    # ✅ Inicializar contador para forzar reset del input
    if "stock_input_counter" not in st.session_state:
        st.session_state["stock_input_counter"] = 0

    # Agregar espacio superior para compensar padding removido
    st.markdown("<div style='margin-top: 2.5rem;'></div>", unsafe_allow_html=True)
    
    st.title("📦 Stock IA")
    st.markdown("*Consultas de stock con lenguaje natural*")

    # ⛔ IMPORTANTE: NO LLAMAR mostrar_resumen_stock_rotativo() ACÁ
    # porque se renderiza arriba del menú desde main()

    st.markdown("---")

    if 'historial_stock' not in st.session_state:
        st.session_state.historial_stock = []

    with st.sidebar:
        st.header("📦 Stock IA - Ayuda")
        st.markdown("""
        **Este módulo entiende:**

        📊 **Consultas generales:**
        - "stock total"
        - "stock por familia"
        - "stock por depósito"

        🔍 **Búsquedas específicas:**
        - "stock vitek"
        - "lote D250829AF"
        - "stock familia ID"

        ⚠️ **Vencimientos:**
        - "lotes por vencer"
        - "vencen en 30 días"
        - "lotes vencidos"

        📉 **Alertas:**
        - "stock bajo"
        - "artículos a reponer"
        """)

        st.markdown("---")

        if st.button("🗑️ Limpiar historial", key="limpiar_stock", use_container_width=True):
            st.session_state.historial_stock = []
            st.session_state["pause_autorefresh_stock"] = False  # ✅ REACTIVAR AUTOREFRESH
            st.rerun()

    # ✅ ALERTAS ARRIBA DEL INPUT (SOLO SI NO HAY HISTORIAL Y NO ESTÁ PAUSADO)
    if not st.session_state.historial_stock and not st.session_state.get("pause_autorefresh_stock", False):
        try:
            alertas = get_alertas_vencimiento_multiple(5)
            if alertas:
                import time
                indice = int(time.time() // 5) % len(alertas)
                alerta = alertas[indice]

                # ✅ CORREGIDO: usar 'dias_restantes' en vez de 'dias'
                dias = alerta['dias_restantes']
                articulo = alerta['articulo']
                lote = alerta['lote']
                venc = alerta['vencimiento']
                stock = alerta['stock']

                # Contador
                contador = f"<div style='text-align: center; font-size: 0.8em; color: #666; margin-top: 5px;'>{indice + 1} de {len(alertas)} alertas</div>"

                html = ""
                if dias <= 7:
                    # Crítico - rojo
                    html = """
                    <div style="background-color: #fee2e2; border-left: 5px solid #dc2626; padding: 15px; border-radius: 5px; margin: 10px 0;">
                        <span style="color: #dc2626; font-weight: bold; font-size: 1.1em;">🚨 ¡ALERTA CRÍTICA!</span><br>
                        <span style="color: #7f1d1d;"><b>{}</b> - Lote: <b>{}</b></span><br>
                        <span style="color: #7f1d1d;">Vence: <b>{}</b> ({} días) | Stock: {}</span>
                    </div>
                    {}
                    """.format(articulo, lote, venc, dias, stock, contador)
                elif dias <= 30:
                    # Urgente - naranja
                    html = """
                    <div style="background-color: #fff7ed; border-left: 5px solid #ea580c; padding: 15px; border-radius: 5px; margin: 10px 0;">
                        <span style="color: #ea580c; font-weight: bold; font-size: 1.1em;">⚠️ PRÓXIMO A VENCER</span><br>
                        <span style="color: #9a3412;"><b>{}</b> - Lote: <b>{}</b></span><br>
                        <span style="color: #9a3412;">Vence: <b>{}</b> ({} días) | Stock: {}</span>
                    </div>
                    {}
                    """.format(articulo, lote, venc, dias, stock, contador)
                else:
                    # Atención - amarillo
                    html = """
                    <div style="background-color: #fefce8; border-left: 5px solid #ca8a04; padding: 15px; border-radius: 5px; margin: 10px 0;">
                        <span style="color: #ca8a04; font-weight: bold; font-size: 1.1em;">📋 Próximo vencimiento</span><br>
                        <span style="color: #854d0e;"><b>{}</b> - Lote: <b>{}</b></span><br>
                        <span style="color: #854d0e;">Vence: <b>{}</b> ({} días) | Stock: {}</span>
                    </div>
                    {}
                    """.format(articulo, lote, venc, dias, stock, contador)

                st.markdown(html, unsafe_allow_html=True)
        except Exception as e:
            print(f"⚠️ Error en alertas de vencimiento: {e}")
            pass  # Si falla la alerta, no afecta el resto

    # ✅ Crear un contenedor para el input (se limpia después de procesar)
    col_input = st.container()
    with col_input:
        pregunta = st.text_input(
            "Escribe tu consulta de stock:",
            placeholder="Ej: stock vitek / lotes por vencer / stock bajo",
            key=f"input_stock_{st.session_state['stock_input_counter']}"  # ✅ Key dinámica
        )

    if pregunta and pregunta.strip():
        # ✅ PAUSAR AUTOREFRESH AL HACER PREGUNTA
        st.session_state["pause_autorefresh_stock"] = True
        
        with st.spinner("🔍 Consultando stock."):
            respuesta, df = procesar_pregunta_stock(pregunta)
            
            st.session_state.historial_stock.append({
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'pregunta': pregunta,
                'respuesta': respuesta,
                'df': df,  # ✅ Agregar DataFrame
                'tiene_datos': df is not None and not df.empty
            })

            # ✅ Incrementar contador para crear nuevo input (esto limpia el campo)
            st.session_state["stock_input_counter"] += 1
            st.rerun()

    # ✅ MOSTRAR HISTORIAL CON DASHBOARD MODERNO
    if st.session_state.historial_stock:
        st.markdown("---")
        
        for idx, item in enumerate(st.session_state.historial_stock):
            with st.chat_message("user"):
                st.markdown(item['pregunta'])
            
            with st.chat_message("assistant"):
                st.markdown(item['respuesta'])
                
                if 'df' in item and item['df'] is not None and not item['df'].empty:
                    df = item['df']
                    
                    # Mostrar info básica
                    if 'STOCK' in df.columns:
                        try:
                            total_stock = df['STOCK'].apply(lambda x: float(
                                str(x).replace(',', '.').replace(' ', '')
                            ) if pd.notna(x) else 0).sum()
                            st.info(f"📦 **Total stock:** {total_stock:,.0f} unidades".replace(',', '.'))
                        except Exception:
                            pass

                    # Mostrar tabla
                    st.dataframe(df, use_container_width=True, hide_index=True)

                    # Botón descargar
                    excel_data = df_to_excel(df)
                    st.download_button(
                        label="📥 Descargar Excel",
                        data=excel_data,
                        file_name="consulta_stock.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"download_stock_{idx}"
                    )

    # ✅ AUTOREFRESH CONDICIONAL: SOLO SI NO ESTÁ PAUSADO
    if not st.session_state.get("pause_autorefresh_stock", False):
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=5000, key="stock_keepalive")
        except Exception:
            pass
