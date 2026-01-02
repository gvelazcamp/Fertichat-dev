# =====================================================================
# UI principal
# =====================================================================

def mostrar_ficha_stock():
    # -------------------------
    # CSS SOLO para esta vista
    # -------------------------
    st.markdown("""
    <style>
    /* Título */
    .fs-title{
        font-size: 1.6rem;
        font-weight: 800;
        margin: 0.2rem 0 0.8rem 0;
        display:flex;
        gap:.6rem;
        align-items:center;
    }
    .fs-sub{
        color: rgba(0,0,0,0.55);
        margin-top:-.4rem;
        margin-bottom: 1rem;
        font-size: .95rem;
    }

    /* “Tarjeta” visual usando container */
    div[data-testid="stVerticalBlockBorderWrapper"]{
        border-radius: 16px !important;
        border: 1px solid rgba(0,0,0,0.08) !important;
        box-shadow: 0 6px 18px rgba(0,0,0,0.04) !important;
    }

    /* Inputs un poco más prolijos */
    div[data-testid="stTextInput"] input,
    div[data-testid="stDateInput"] input{
        border-radius: 12px !important;
    }

    /* Dataframe más “limpio” */
    div[data-testid="stDataFrame"]{
        border-radius: 14px !important;
        overflow: hidden !important;
        border: 1px solid rgba(0,0,0,0.08) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # -------------------------
    # Cabecera
    # -------------------------
    st.markdown('<div class="fs-title">📒 Ficha de stock</div>', unsafe_allow_html=True)
    st.markdown('<div class="fs-sub">Kardex por artículo • Entradas/Salidas • Saldo y valorización (costo promedio móvil)</div>', unsafe_allow_html=True)

    # -------------------------
    # Filtros (tarjeta)
    # -------------------------
    with st.container(border=True):
        c1, c2, c3 = st.columns([2.2, 1, 1])

        with c1:
            st.caption("Buscar artículo")
            q = st.text_input(
                "Buscar artículo (nombre o código interno):",
                value="",
                placeholder="Ej: Roche, Pepito, 12345",
                label_visibility="collapsed"
            )

        with c2:
            st.caption("Desde (opcional)")
            fecha_desde = st.date_input("Desde", value=None, label_visibility="collapsed")

        with c3:
            st.caption("Hasta (opcional)")
            fecha_hasta = st.date_input("Hasta", value=None, label_visibility="collapsed")

        mostrar_avanzado = st.toggle("Mostrar columnas avanzadas", value=False)

    # -------------------------
    # Datos: artículos
    # -------------------------
    articulos = _fetch_articulos(q, limit=80)

    if not articulos:
        st.info("No hay artículos para mostrar (o no se encontró el texto buscado).")
        return

    opciones = []
    mapa = {}
    for a in articulos:
        nombre = a.get("nombre", "")
        cod = a.get("codigo_interno", "")
        label = f"{nombre}  |  {cod}" if cod else nombre
        opciones.append(label)
        mapa[label] = a

    sel = st.selectbox("Seleccionar artículo:", opciones, index=0)
    art = mapa.get(sel, {})
    articulo_id = art.get("id")

    if articulo_id is None:
        st.error("El artículo seleccionado no tiene 'id'.")
        return

    # Línea de contexto
    nombre_sel = art.get("nombre", "")
    cod_sel = art.get("codigo_interno", "")
    st.caption(f"Artículo: **{nombre_sel}**" + (f" • Código: **{cod_sel}**" if cod_sel else "") + f" • ID: **{articulo_id}**")

    # -------------------------
    # Datos: movimientos
    # -------------------------
    movs = _fetch_movimientos(articulo_id, fecha_desde, fecha_hasta)

    if not movs:
        st.warning("No hay movimientos para este artículo en el rango seleccionado.")
        return

    df = pd.DataFrame(movs)

    # Asegurar orden
    if "fecha_hora" in df.columns:
        df["fecha_hora_dt"] = df["fecha_hora"].apply(_to_datetime_safe)
        df = df.sort_values(by=["fecha_hora_dt", "id"], ascending=[True, True], na_position="last")

    # Calcular kardex (promedio móvil)
    df_k = _calcular_kardex_promedio_movil(df)

    # -------------------------
    # Resumen (tarjeta)
    # -------------------------
    stock_final = float(df_k["saldo_qty"].iloc[-1]) if not df_k.empty else 0.0
    valor_final = float(df_k["saldo_valor"].iloc[-1]) if not df_k.empty else 0.0
    costo_final = float(df_k["costo_promedio"].iloc[-1]) if not df_k.empty else 0.0

    with st.container(border=True):
        a, b, c, d = st.columns([1, 1, 1, 1])
        a.metric("Stock actual", f"{_fmt_num(stock_final, 2)}")
        b.metric("Valor stock", f"$ {_fmt_num(valor_final, 2)}")
        c.metric("Costo promedio", f"$ {_fmt_num(costo_final, 4)}")
        d.metric("Movimientos", f"{len(df_k)}")

    # -------------------------
    # Tabla principal (más “humana”)
    # -------------------------
    df_view = df_k.copy()

    # Renombres “bonitos” (sin romper lógica)
    rename_map = {
        "fecha_hora": "Fecha",
        "tipo_mov": "Tipo",
        "lote": "Lote",
        "vencimiento": "Vencimiento",
        "qty_in": "Entrada",
        "qty_out": "Salida",
        "qty_base": "Cantidad (base)",
        "precio_unit_aplicado": "Precio entrada",
        "costo_unit_aplicado": "Costo baja",
        "valor_mov": "Valor mov.",
        "saldo_qty": "Saldo qty",
        "saldo_valor": "Saldo $",
        "ref_tipo": "Ref tipo",
        "ref_nro": "Ref nro",
        "proveedor": "Proveedor",
        "usuario": "Usuario",
        "observacion": "Obs",
        "deposito_id": "Depósito",
        "deposito_origen_id": "Origen",
        "deposito_destino_id": "Destino",
    }
    df_view = df_view.rename(columns={k: v for k, v in rename_map.items() if k in df_view.columns})

    # Columnas base (modo simple)
    cols_simple = [
        "Fecha", "Tipo", "Lote", "Vencimiento",
        "Entrada", "Salida", "Saldo qty",
        "Costo baja", "Precio entrada", "Valor mov.", "Saldo $",
        "Ref tipo", "Ref nro", "Proveedor", "Usuario", "Obs"
    ]
    cols_simple = [c for c in cols_simple if c in df_view.columns]

    # Columnas avanzadas
    cols_adv = cols_simple.copy()
    for extra in ["Depósito", "Origen", "Destino", "Cantidad (base)"]:
        if extra in df_view.columns and extra not in cols_adv:
            cols_adv.insert(4, extra)

    cols_show = cols_adv if mostrar_avanzado else cols_simple

    # Orden final por fecha si existe
    if "Fecha" in df_view.columns:
        # si "fecha_hora_dt" quedó, lo usamos para ordenar “bien”
        if "fecha_hora_dt" in df_k.columns:
            df_view["_orden"] = df_k["fecha_hora_dt"]
            df_view = df_view.sort_values(by=["_orden"], ascending=True, na_position="last").drop(columns=["_orden"])

    st.dataframe(
        df_view[cols_show],
        use_container_width=True,
        hide_index=True
    )

    # -------------------------
    # Descarga
    # -------------------------
    with st.expander("⬇️ Descargar", expanded=False):
        csv = df_view[cols_show].to_csv(index=False).encode("utf-8")
        st.download_button(
            "Descargar ficha (CSV)",
            data=csv,
            file_name=f"ficha_stock_articulo_{articulo_id}.csv",
            mime="text/csv",
            use_container_width=True
        )
