# =========================
# BAJASTOCK.PY - Baja de stock con historial
# =========================

import streamlit as st
import pandas as pd
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

# =========================
# CONEXIÓN A POSTGRESQL
# =========================
DATABASE_URL = "postgresql://postgres.ytmpjhdjecocoitptvjn:TU_PASSWORD_ACA@aws-0-us-west-2.pooler.supabase.com:5432/postgres"

def get_connection():
    """Obtiene conexión a PostgreSQL"""
    return psycopg2.connect(DATABASE_URL)


def crear_tabla_historial():
    """Crea la tabla de historial de bajas si no existe"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS historial_bajas (
            id SERIAL PRIMARY KEY,
            usuario VARCHAR(100),
            fecha DATE,
            hora TIME,
            codigo_interno VARCHAR(50),
            articulo VARCHAR(255),
            cantidad DECIMAL(10,2),
            motivo VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def buscar_articulo(busqueda):
    """Busca artículo por código de barras, interno o descripción"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Buscar por coincidencia exacta primero, luego por LIKE
    cur.execute("""
        SELECT * FROM chatbot_raw 
        WHERE CAST(interno AS TEXT) = %s 
           OR codigo_barras = %s 
           OR LOWER(articulo) LIKE LOWER(%s)
        LIMIT 20
    """, (busqueda, busqueda, f"%{busqueda}%"))
    
    resultados = cur.fetchall()
    cur.close()
    conn.close()
    
    return resultados


def registrar_baja(usuario, codigo_interno, articulo, cantidad, motivo):
    """Registra una baja en el historial"""
    conn = get_connection()
    cur = conn.cursor()
    
    ahora = datetime.now()
    
    cur.execute("""
        INSERT INTO historial_bajas (usuario, fecha, hora, codigo_interno, articulo, cantidad, motivo)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (usuario, ahora.date(), ahora.time(), codigo_interno, articulo, cantidad, motivo))
    
    conn.commit()
    cur.close()
    conn.close()


def obtener_historial(limite=50):
    """Obtiene el historial de bajas"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM historial_bajas 
        ORDER BY created_at DESC 
        LIMIT %s
    """, (limite,))
    
    resultados = cur.fetchall()
    cur.close()
    conn.close()
    
    return resultados


# =========================
# INTERFAZ STREAMLIT
# =========================
def mostrar_baja_stock():
    """Muestra la pantalla de baja de stock"""
    
    # Crear tabla si no existe
    try:
        crear_tabla_historial()
    except:
        pass
    
    st.markdown("## 🧾 Baja de Stock")
    st.markdown("Registrá las bajas de inventario buscando por código de barras, interno o nombre del artículo.")
    
    st.markdown("---")
    
    # Obtener usuario actual
    user = st.session_state.get("user", {})
    usuario_actual = user.get("nombre", user.get("Usuario", "Usuario"))
    
    # =========================
    # BÚSQUEDA DE ARTÍCULO
    # =========================
    col1, col2 = st.columns([3, 1])
    
    with col1:
        busqueda = st.text_input(
            "🔍 Buscar artículo",
            placeholder="Ingresá código de barras, interno o nombre...",
            key="busqueda_baja"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        btn_buscar = st.button("Buscar", type="primary", use_container_width=True)
    
    # =========================
    # RESULTADOS DE BÚSQUEDA
    # =========================
    if busqueda and (btn_buscar or "articulo_seleccionado" not in st.session_state):
        with st.spinner("Buscando..."):
            try:
                resultados = buscar_articulo(busqueda)
                
                if resultados:
                    st.success(f"Se encontraron {len(resultados)} artículo(s)")
                    
                    # Mostrar resultados en una tabla seleccionable
                    for i, art in enumerate(resultados):
                        with st.container():
                            col_info, col_btn = st.columns([4, 1])
                            
                            with col_info:
                                interno = art.get('interno', 'N/A')
                                nombre = art.get('articulo', art.get('descripcion', 'Sin nombre'))
                                stock = art.get('stock', art.get('cantidad', 0))
                                
                                st.markdown(f"""
                                    **{interno}** - {nombre}  
                                    📦 Stock actual: **{stock}**
                                """)
                            
                            with col_btn:
                                if st.button("Seleccionar", key=f"sel_{i}"):
                                    st.session_state["articulo_seleccionado"] = art
                                    st.rerun()
                            
                            st.markdown("---")
                else:
                    st.warning("No se encontraron artículos con ese criterio")
                    
            except Exception as e:
                st.error(f"Error al buscar: {str(e)}")
    
    # =========================
    # FORMULARIO DE BAJA
    # =========================
    if "articulo_seleccionado" in st.session_state:
        art = st.session_state["articulo_seleccionado"]
        
        st.markdown("### 📝 Registrar Baja")
        
        interno = art.get('interno', 'N/A')
        nombre = art.get('articulo', art.get('descripcion', 'Sin nombre'))
        stock_actual = art.get('stock', art.get('cantidad', 0))
        
        st.info(f"**Artículo seleccionado:** {interno} - {nombre} | Stock actual: {stock_actual}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            cantidad = st.number_input(
                "Cantidad a bajar",
                min_value=0.01,
                value=1.0,
                step=1.0,
                key="cantidad_baja"
            )
        
        with col2:
            motivo = st.selectbox(
                "Motivo de la baja",
                ["Vencimiento", "Rotura", "Pérdida", "Ajuste de inventario", "Consumo interno", "Otro"],
                key="motivo_baja"
            )
        
        observacion = st.text_input("Observación (opcional)", key="obs_baja")
        
        col_guardar, col_cancelar = st.columns(2)
        
        with col_guardar:
            if st.button("✅ Confirmar Baja", type="primary", use_container_width=True):
                try:
                    motivo_final = f"{motivo} - {observacion}" if observacion else motivo
                    registrar_baja(usuario_actual, str(interno), nombre, cantidad, motivo_final)
                    st.success(f"✅ Baja registrada: {cantidad} unidad(es) de {nombre}")
                    del st.session_state["articulo_seleccionado"]
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al registrar baja: {str(e)}")
        
        with col_cancelar:
            if st.button("❌ Cancelar", use_container_width=True):
                del st.session_state["articulo_seleccionado"]
                st.rerun()
    
    # =========================
    # HISTORIAL DE BAJAS
    # =========================
    st.markdown("---")
    st.markdown("### 📋 Historial de Bajas")
    
    try:
        historial = obtener_historial(50)
        
        if historial:
            df = pd.DataFrame(historial)
            
            # Formatear columnas
            if 'fecha' in df.columns:
                df['fecha'] = pd.to_datetime(df['fecha']).dt.strftime('%d/%m/%Y')
            if 'hora' in df.columns:
                df['hora'] = df['hora'].astype(str).str[:8]
            
            # Seleccionar columnas a mostrar
            columnas_mostrar = ['fecha', 'hora', 'usuario', 'codigo_interno', 'articulo', 'cantidad', 'motivo']
            columnas_existentes = [c for c in columnas_mostrar if c in df.columns]
            
            st.dataframe(
                df[columnas_existentes],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No hay registros de bajas todavía")
            
    except Exception as e:
        st.warning(f"No se pudo cargar el historial: {str(e)}")
