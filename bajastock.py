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
def get_connection():
    return psycopg2.connect(
        host=st.secrets["DB_HOST"],
        port=st.secrets["DB_PORT"],
        dbname=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        sslmode="require"
    )


# =========================
# HELPERS
# =========================
def _norm_str(x) -> str:
    return ("" if x is None else str(x)).strip()


def _to_float(x) -> float:
    """
    Convierte texto a float de forma tolerante:
    - "10" / "10.5" / "10,5" / " 10 " / "10 u"
    """
    s = _norm_str(x)
    if not s:
        return 0.0
    s = s.replace(" ", "")
    limpio = "".join(ch for ch in s if ch.isdigit() or ch in [",", ".", "-"])
    if not limpio:
        return 0.0
    if "," in limpio and "." in limpio:
        limpio = limpio.replace(",", "")
    else:
        limpio = limpio.replace(",", ".")
    try:
        return float(limpio)
    except Exception:
        return 0.0


def _fmt_num(x: float) -> str:
    if x is None:
        return "0"
    try:
        if abs(x - round(x)) < 1e-9:
            return str(int(round(x)))
        return f"{x:.2f}".rstrip("0").rstrip(".")
    except Exception:
        return "0"


def _parse_fecha_for_sort(venc_text: str):
    s = _norm_str(venc_text)
    if not s:
        return pd.Timestamp.max
    dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
    if pd.isna(dt):
        return pd.Timestamp.max
    return dt


# =========================
# TABLA HISTORIAL (CON CAMPOS EXTRA)
# =========================
def crear_tabla_historial():
    """Crea la tabla de historial de bajas si no existe + columnas extra (no rompe lo existente)"""
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

    cur.execute("""ALTER TABLE historial_bajas ADD COLUMN IF NOT EXISTS deposito VARCHAR(255)""")
    cur.execute("""ALTER TABLE historial_bajas ADD COLUMN IF NOT EXISTS lote VARCHAR(255)""")
    cur.execute("""ALTER TABLE historial_bajas ADD COLUMN IF NOT EXISTS vencimiento VARCHAR(255)""")
    cur.execute("""ALTER TABLE historial_bajas ADD COLUMN IF NOT EXISTS stock_antes_lote DECIMAL(14,4)""")
    cur.execute("""ALTER TABLE historial_bajas ADD COLUMN IF NOT EXISTS stock_despues_lote DECIMAL(14,4)""")
    cur.execute("""ALTER TABLE historial_bajas ADD COLUMN IF NOT EXISTS stock_total_articulo DECIMAL(14,4)""")
    cur.execute("""ALTER TABLE historial_bajas ADD COLUMN IF NOT EXISTS stock_total_deposito DECIMAL(14,4)""")
    cur.execute("""ALTER TABLE historial_bajas ADD COLUMN IF NOT EXISTS stock_casa_central DECIMAL(14,4)""")
    conn.commit()

    cur.close()
    conn.close()


# =========================
# STOCK (TABLA: stock) - BÚSQUEDA Y DETALLE
# =========================
def buscar_items_stock(busqueda: str, limite_filas: int = 400):
    """
    Busca por:
    - CODIGO exacto
    - ARTICULO LIKE
    Devuelve items agregados con stock total y depósitos.
    """
    b = _norm_str(busqueda)
    if not b:
        return []

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            "FAMILIA",
            "CODIGO",
            "ARTICULO",
            "DEPOSITO",
            "LOTE",
            "VENCIMIENTO",
            "STOCK"
        FROM stock
        WHERE
            TRIM("CODIGO") = %s
            OR LOWER(TRIM("ARTICULO")) LIKE LOWER(%s)
        LIMIT %s
    """, (b, f"%{b}%", limite_filas))

    filas = cur.fetchall()
    cur.close()
    conn.close()

    agg = {}
    for r in filas:
        codigo = _norm_str(r.get("CODIGO"))
        articulo = _norm_str(r.get("ARTICULO"))
        familia = _norm_str(r.get("FAMILIA"))
        deposito = _norm_str(r.get("DEPOSITO"))
        stock_val = _to_float(r.get("STOCK"))

        key = (codigo, articulo, familia)
        if key not in agg:
            agg[key] = {
                "FAMILIA": familia,
                "CODIGO": codigo,
                "ARTICULO": articulo,
                "STOCK_TOTAL": 0.0,
                "DEPOSITOS": set()
            }
        agg[key]["STOCK_TOTAL"] += stock_val
        if deposito:
            agg[key]["DEPOSITOS"].add(deposito)

    items = list(agg.values())
    items.sort(key=lambda x: x.get("STOCK_TOTAL", 0.0), reverse=True)
    return items[:20]


def obtener_lotes_item(codigo: str, articulo: str):
    """Trae todos los lotes/vencimientos para un item (todas las ubicaciones)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            "FAMILIA",
            "CODIGO",
            "ARTICULO",
            "DEPOSITO",
            "LOTE",
            "VENCIMIENTO",
            "STOCK"
        FROM stock
        WHERE
            TRIM("CODIGO") = %s
            AND TRIM("ARTICULO") = %s
    """, (_norm_str(codigo), _norm_str(articulo)))

    filas = cur.fetchall()
    cur.close()
    conn.close()

    out = []
    for r in filas:
        out.append({
            "FAMILIA": _norm_str(r.get("FAMILIA")),
            "CODIGO": _norm_str(r.get("CODIGO")),
            "ARTICULO": _norm_str(r.get("ARTICULO")),
            "DEPOSITO": _norm_str(r.get("DEPOSITO")),
            "LOTE": _norm_str(r.get("LOTE")),
            "VENCIMIENTO": _norm_str(r.get("VENCIMIENTO")),
            "STOCK_TXT": _norm_str(r.get("STOCK")),
            "STOCK_NUM": _to_float(r.get("STOCK")),
        })

    out.sort(key=lambda x: (_parse_fecha_for_sort(x.get("VENCIMIENTO")), x.get("LOTE", "")))
    return out


def _sum_stock(filas, filtro_deposito: str = None, solo_casa_central: bool = False) -> float:
    total = 0.0
    for r in filas:
        dep = _norm_str(r.get("DEPOSITO"))
        if filtro_deposito is not None and dep != _norm_str(filtro_deposito):
            continue
        if solo_casa_central:
            if "casa central" not in dep.lower():
                continue
        total += float(r.get("STOCK_NUM", 0.0) or 0.0)
    return total


# =========================
# HISTORIAL (INSERT + SELECT)
# =========================
def registrar_baja(
    usuario,
    codigo_interno,
    articulo,
    cantidad,
    motivo,
    deposito=None,
    lote=None,
    vencimiento=None,
    stock_antes_lote=None,
    stock_despues_lote=None,
    stock_total_articulo=None,
    stock_total_deposito=None,
    stock_casa_central=None
):
    """Registra una baja en el historial (compatible con versión vieja)."""
    conn = get_connection()
    cur = conn.cursor()

    ahora = datetime.now()

    cur.execute("""
        INSERT INTO historial_bajas (
            usuario, fecha, hora, codigo_interno, articulo, cantidad, motivo,
            deposito, lote, vencimiento,
            stock_antes_lote, stock_despues_lote,
            stock_total_articulo, stock_total_deposito, stock_casa_central
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s)
    """, (
        usuario, ahora.date(), ahora.time(), str(codigo_interno), str(articulo), cantidad, motivo,
        deposito, lote, vencimiento,
        stock_antes_lote, stock_despues_lote,
        stock_total_articulo, stock_total_deposito, stock_casa_central
    ))

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
# ACTUALIZAR STOCK (TABLA: stock)
# =========================
def aplicar_baja_en_lote(
    usuario: str,
    codigo: str,
    articulo: str,
    deposito: str,
    lote: str,
    vencimiento: str,
    cantidad: float,
    motivo_final: str
):
    """
    Baja stock de un lote específico (fila específica) + registra historial.
    Todo en una transacción.
    """
    codigo = _norm_str(codigo)
    articulo = _norm_str(articulo)
    deposito = _norm_str(deposito)
    lote = _norm_str(lote)
    vencimiento = _norm_str(vencimiento)

    conn = get_connection()
    try:
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT "STOCK"
            FROM stock
            WHERE
                TRIM("CODIGO") = %s
                AND TRIM("ARTICULO") = %s
                AND TRIM("DEPOSITO") = %s
                AND COALESCE(TRIM("LOTE"), '') = %s
                AND COALESCE(TRIM("VENCIMIENTO"), '') = %s
            FOR UPDATE
        """, (codigo, articulo, deposito, lote, vencimiento))

        row = cur.fetchone()
        if not row:
            raise ValueError("No se encontró el lote seleccionado en la tabla stock.")

        stock_antes = _to_float(row.get("STOCK"))
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a 0.")
        if cantidad > stock_antes + 1e-9:
            raise ValueError(f"No hay stock suficiente en ese lote. Stock lote: {stock_antes}")

        stock_despues = stock_antes - float(cantidad)

        cur.execute("""
            UPDATE stock
            SET "STOCK" = %s
            WHERE
                TRIM("CODIGO") = %s
                AND TRIM("ARTICULO") = %s
                AND TRIM("DEPOSITO") = %s
                AND COALESCE(TRIM("LOTE"), '') = %s
                AND COALESCE(TRIM("VENCIMIENTO"), '') = %s
        """, (_fmt_num(stock_despues), codigo, articulo, deposito, lote, vencimiento))

        cur.execute("""
            SELECT "DEPOSITO", "STOCK"
            FROM stock
            WHERE TRIM("CODIGO") = %s AND TRIM("ARTICULO") = %s
        """, (codigo, articulo))
        rows_all = cur.fetchall()

        filas_norm = []
        for r in rows_all:
            filas_norm.append({
                "DEPOSITO": _norm_str(r.get("DEPOSITO")),
                "STOCK_NUM": _to_float(r.get("STOCK"))
            })

        total_articulo = sum(r["STOCK_NUM"] for r in filas_norm)
        total_deposito = sum(r["STOCK_NUM"] for r in filas_norm if r["DEPOSITO"] == deposito)
        total_casa_central = sum(r["STOCK_NUM"] for r in filas_norm if "casa central" in r["DEPOSITO"].lower())

        registrar_baja(
            usuario=usuario,
            codigo_interno=codigo,
            articulo=articulo,
            cantidad=float(cantidad),
            motivo=motivo_final,
            deposito=deposito,
            lote=lote,
            vencimiento=vencimiento,
            stock_antes_lote=float(stock_antes),
            stock_despues_lote=float(stock_despues),
            stock_total_articulo=float(total_articulo),
            stock_total_deposito=float(total_deposito),
            stock_casa_central=float(total_casa_central)
        )

        conn.commit()

        return {
            "stock_antes_lote": stock_antes,
            "stock_despues_lote": stock_despues,
            "total_articulo": total_articulo,
            "total_deposito": total_deposito,
            "total_casa_central": total_casa_central
        }

    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def aplicar_baja_fifo(
    usuario: str,
    codigo: str,
    articulo: str,
    deposito: str,
    cantidad: float,
    motivo_final: str
):
    """
    Baja por FIFO/FEFO automático en un depósito:
    consume primero el lote con vencimiento más cercano (ordenado).
    Si la cantidad supera el stock del primer lote, continúa con el siguiente.
    Registra UNA entrada de historial por cada lote consumido.
    """
    codigo = _norm_str(codigo)
    articulo = _norm_str(articulo)
    deposito = _norm_str(deposito)

    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor a 0.")

    lotes_all = obtener_lotes_item(codigo, articulo)
    lotes_dep = [
        x for x in lotes_all
        if _norm_str(x.get("DEPOSITO")) == deposito and float(x.get("STOCK_NUM", 0.0) or 0.0) > 0
    ]

    if not lotes_dep:
        raise ValueError("No hay lotes con stock disponible en el depósito seleccionado.")

    restante = float(cantidad)
    resumen = []

    for lt in lotes_dep:
        if restante <= 1e-9:
            break

        disponible = float(lt.get("STOCK_NUM", 0.0) or 0.0)
        if disponible <= 1e-9:
            continue

        a_bajar = min(disponible, restante)

        r = aplicar_baja_en_lote(
            usuario=usuario,
            codigo=codigo,
            articulo=articulo,
            deposito=deposito,
            lote=_norm_str(lt.get("LOTE")),
            vencimiento=_norm_str(lt.get("VENCIMIENTO")),
            cantidad=a_bajar,
            motivo_final=motivo_final + " (FIFO/FEFO)"
        )

        resumen.append({
            "lote": _norm_str(lt.get("LOTE")),
            "vencimiento": _norm_str(lt.get("VENCIMIENTO")),
            "bajado": a_bajar,
            "stock_lote_restante": r.get("stock_despues_lote", 0.0)
        })
        restante -= a_bajar

    if restante > 1e-6:
        raise ValueError(f"No alcanzó el stock en FIFO. Faltó bajar: {restante}")

    return resumen


# =========================
# INTERFAZ STREAMLIT
# =========================
def mostrar_baja_stock():
    """Muestra la pantalla de baja de stock (tomando stock desde tabla 'stock')"""

    try:
        crear_tabla_historial()
    except Exception:
        pass

    st.markdown("## 🧾 Baja de Stock")
    st.markdown("Buscá por **CODIGO** o por **ARTICULO**, elegí lote/vencimiento y registrá la baja con historial.")
    st.markdown("---")

    user = st.session_state.get("user", {})
    usuario_actual = user.get("nombre", user.get("Usuario", "Usuario"))

    # =========================
    # BÚSQUEDA DE ARTÍCULO (TABLA stock)
    # =========================
    col1, col2 = st.columns([3, 1])

    with col1:
        busqueda = st.text_input(
            "🔍 Buscar por CODIGO o ARTICULO",
            placeholder="Ej: 12345  /  ana profile",
            key="busqueda_baja_stock"
        )

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        btn_buscar = st.button("Buscar", type="primary", use_container_width=True)

    # =========================
    # RESULTADOS DE BÚSQUEDA
    # (IMPORTANTE: SOLO SE MUESTRAN CUANDO APRETÁS BUSCAR)
    # =========================
    if busqueda and btn_buscar:
        with st.spinner("Buscando en stock..."):
            try:
                items = buscar_items_stock(busqueda)

                if items:
                    st.success(f"Se encontraron {len(items)} artículo(s)")

                    for i, it in enumerate(items):
                        codigo = it.get("CODIGO", "N/A")
                        articulo = it.get("ARTICULO", "Sin artículo")
                        familia = it.get("FAMILIA", "")
                        stock_total = float(it.get("STOCK_TOTAL", 0.0) or 0.0)
                        depositos = sorted(list(it.get("DEPOSITOS", set())))

                        with st.container():
                            col_info, col_btn = st.columns([4, 1])

                            with col_info:
                                st.markdown(
                                    f"**{codigo}** - {articulo}  \n"
                                    f"🏷️ Familia: **{familia or '—'}**  \n"
                                    f"📦 Stock total (todas las ubicaciones): **{_fmt_num(stock_total)}**  \n"
                                    f"🏠 Depósitos: {', '.join(depositos) if depositos else '—'}"
                                )

                            with col_btn:
                                if st.button("Seleccionar", key=f"sel_item_{i}"):
                                    st.session_state["item_seleccionado_stock"] = {
                                        "CODIGO": codigo,
                                        "ARTICULO": articulo,
                                        "FAMILIA": familia
                                    }
                                    st.rerun()

                            st.markdown("---")
                else:
                    st.warning("No se encontraron artículos con ese criterio en la tabla stock.")

            except Exception as e:
                st.error(f"Error al buscar: {str(e)}")

    # =========================
    # FORMULARIO DE BAJA (APARECE CUANDO YA HAY SELECCIÓN)
    # =========================
    if "item_seleccionado_stock" in st.session_state:
        it = st.session_state["item_seleccionado_stock"]

        codigo = _norm_str(it.get("CODIGO"))
        articulo = _norm_str(it.get("ARTICULO"))
        familia = _norm_str(it.get("FAMILIA"))

        st.markdown("### 📝 Registrar Baja")
        st.info(f"Artículo seleccionado: **{codigo} - {articulo}**")

        try:
            lotes = obtener_lotes_item(codigo, articulo)
        except Exception as e:
            st.error(f"No se pudo cargar lotes del artículo: {str(e)}")
            lotes = []

        if not lotes:
            st.warning("Este artículo no tiene lotes/stock cargado en la tabla stock.")
        else:
            depositos = sorted({x.get("DEPOSITO", "") for x in lotes if _norm_str(x.get("DEPOSITO"))})

            default_dep = 0
            for idx, d in enumerate(depositos):
                if "casa central" in d.lower():
                    default_dep = idx
                    break

            colA, colB = st.columns([2, 1])
            with colA:
                deposito_sel = st.selectbox(
                    "Depósito",
                    options=depositos,
                    index=default_dep if depositos else 0,
                    key="baja_dep_sel"
                )
            with colB:
                st.caption(f"Código: **{codigo}**")
                st.caption(f"Familia: **{familia or '—'}**")

            lotes_dep = [x for x in lotes if _norm_str(x.get("DEPOSITO")) == _norm_str(deposito_sel)]

            total_articulo = _sum_stock(lotes)
            total_deposito = _sum_stock(lotes, filtro_deposito=deposito_sel)
            total_casa_central = _sum_stock(lotes, solo_casa_central=True)

            st.caption(f"📦 Stock total artículo (todas): **{_fmt_num(total_articulo)}**")
            st.caption(f"🏠 Stock en depósito seleccionado: **{_fmt_num(total_deposito)}**")
            st.caption(f"🏛️ Stock en Casa Central: **{_fmt_num(total_casa_central)}**")

            df_lotes = pd.DataFrame([{
                "LOTE": x.get("LOTE"),
                "VENCIMIENTO": x.get("VENCIMIENTO"),
                "STOCK": _fmt_num(float(x.get("STOCK_NUM", 0.0) or 0.0))
            } for x in lotes_dep])

            if df_lotes.empty:
                st.warning("No hay lotes en el depósito seleccionado.")
            else:
                st.markdown("#### Lotes / Vencimientos (orden FIFO/FEFO)")
                st.dataframe(df_lotes, use_container_width=True, hide_index=True)

                idx_fifo = None
                for j, x in enumerate(lotes_dep):
                    if float(x.get("STOCK_NUM", 0.0) or 0.0) > 0:
                        idx_fifo = j
                        break
                if idx_fifo is None:
                    idx_fifo = 0

                usar_fifo = st.checkbox(
                    "✅ Bajar siguiendo FIFO/FEFO automático (recomendado)",
                    value=True,
                    key="baja_fifo_auto"
                )

                lote_sel = None
                venc_sel = None
                stock_lote_sel = 0.0
                confirm_no_fifo = False

                if not usar_fifo:
                    opciones = []
                    for j, x in enumerate(lotes_dep):
                        opciones.append(
                            f"{j+1}. Lote: {x.get('LOTE') or '—'} | Venc: {x.get('VENCIMIENTO') or '—'} | Stock: {_fmt_num(float(x.get('STOCK_NUM', 0.0) or 0.0))}"
                        )

                    idx_default = idx_fifo if idx_fifo < len(opciones) else 0
                    opcion = st.selectbox(
                        "Elegí el lote a bajar",
                        options=opciones,
                        index=idx_default,
                        key="baja_lote_sel"
                    )
                    idx = int(opcion.split(".")[0]) - 1
                    elegido = lotes_dep[idx]

                    lote_sel = _norm_str(elegido.get("LOTE"))
                    venc_sel = _norm_str(elegido.get("VENCIMIENTO"))
                    stock_lote_sel = float(elegido.get("STOCK_NUM", 0.0) or 0.0)

                    if idx_fifo is not None and idx != idx_fifo and len(lotes_dep) > 1:
                        fifo_ref = lotes_dep[idx_fifo]
                        st.warning(
                            "⚠️ Estás eligiendo un lote que NO es el recomendado por FIFO/FEFO.\n\n"
                            f"Antes hay: **Lote {fifo_ref.get('LOTE') or '—'}** | "
                            f"Venc: **{fifo_ref.get('VENCIMIENTO') or '—'}** | "
                            f"Stock: **{_fmt_num(float(fifo_ref.get('STOCK_NUM', 0.0) or 0.0))}**"
                        )
                        confirm_no_fifo = st.checkbox(
                            "Sí, estoy seguro y quiero bajar este lote igualmente",
                            value=False,
                            key="baja_confirm_no_fifo"
                        )

                    st.caption(f"Stock lote seleccionado: **{_fmt_num(stock_lote_sel)}**")

                col1x, col2x = st.columns(2)

                with col1x:
                    if (not usar_fifo) and stock_lote_sel > 0:
                        cantidad = st.number_input(
                            "Cantidad a bajar",
                            min_value=0.01,
                            value=1.0,
                            step=1.0,
                            max_value=float(stock_lote_sel),
                            key="cantidad_baja_stock"
                        )
                    else:
                        cantidad = st.number_input(
                            "Cantidad a bajar",
                            min_value=0.01,
                            value=1.0,
                            step=1.0,
                            key="cantidad_baja_stock"
                        )

                with col2x:
                    motivo = st.selectbox(
                        "Motivo de la baja",
                        ["Vencimiento", "Rotura", "Pérdida", "Ajuste de inventario", "Consumo interno", "Otro"],
                        key="motivo_baja_stock"
                    )

                observacion = st.text_input("Observación (opcional)", key="obs_baja_stock")
                st.markdown("---")

                col_guardar, col_cancelar = st.columns(2)

                with col_guardar:
                    if st.button("✅ Confirmar Baja", type="primary", use_container_width=True):
                        try:
                            motivo_final = f"{motivo} - {observacion}" if observacion else motivo

                            if (not usar_fifo) and (len(lotes_dep) > 1) and (idx_fifo is not None):
                                if "baja_lote_sel" in st.session_state:
                                    opcion_txt = st.session_state.get("baja_lote_sel", "")
                                    if opcion_txt:
                                        idx_sel = int(opcion_txt.split(".")[0]) - 1
                                        if idx_sel != idx_fifo and not confirm_no_fifo:
                                            st.error("Tenés un lote anterior. Marcá la confirmación para continuar.")
                                            st.stop()

                            if usar_fifo:
                                resumen = aplicar_baja_fifo(
                                    usuario=usuario_actual,
                                    codigo=codigo,
                                    articulo=articulo,
                                    deposito=deposito_sel,
                                    cantidad=float(cantidad),
                                    motivo_final=motivo_final
                                )
                                st.success("✅ Baja registrada por FIFO/FEFO.")
                                for r in resumen:
                                    st.caption(
                                        f"- Lote **{r['lote'] or '—'}** | Venc: **{r['vencimiento'] or '—'}** "
                                        f"| Bajado: **{_fmt_num(r['bajado'])}** | Resta lote: **{_fmt_num(r['stock_lote_restante'])}**"
                                    )
                            else:
                                res = aplicar_baja_en_lote(
                                    usuario=usuario_actual,
                                    codigo=codigo,
                                    articulo=articulo,
                                    deposito=deposito_sel,
                                    lote=lote_sel,
                                    vencimiento=venc_sel,
                                    cantidad=float(cantidad),
                                    motivo_final=motivo_final
                                )
                                st.success(
                                    f"✅ Baja registrada: {_fmt_num(float(cantidad))} de **{articulo}** "
                                    f"(Lote {lote_sel or '—'} | Venc {venc_sel or '—'})"
                                )
                                st.caption(f"Resta en el lote: **{_fmt_num(res.get('stock_despues_lote', 0.0))}**")
                                st.caption(f"Resta total artículo: **{_fmt_num(res.get('total_articulo', 0.0))}**")
                                st.caption(f"Resta en {deposito_sel}: **{_fmt_num(res.get('total_deposito', 0.0))}**")
                                st.caption(f"Resta en Casa Central: **{_fmt_num(res.get('total_casa_central', 0.0))}**")

                            del st.session_state["item_seleccionado_stock"]
                            st.rerun()

                        except Exception as e:
                            st.error(f"Error al registrar baja: {str(e)}")

                with col_cancelar:
                    if st.button("❌ Cancelar", use_container_width=True):
                        del st.session_state["item_seleccionado_stock"]
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

            if "fecha" in df.columns:
                df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.strftime("%d/%m/%Y")
            if "hora" in df.columns:
                df["hora"] = df["hora"].astype(str).str[:8]

            columnas_preferidas = [
                "fecha", "hora", "usuario",
                "codigo_interno", "articulo",
                "deposito", "lote", "vencimiento",
                "cantidad",
                "stock_total_deposito", "stock_casa_central",
                "motivo"
            ]
            columnas_existentes = [c for c in columnas_preferidas if c in df.columns]

            st.dataframe(
                df[columnas_existentes],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No hay registros de bajas todavía")

    except Exception as e:
        st.warning(f"No se pudo cargar el historial: {str(e)}")
