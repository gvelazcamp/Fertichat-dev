# =========================
# BAJASTOCK.PY - Baja de Stock / Movimiento con historial
# =========================

import streamlit as st
import pandas as pd
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

# =========================
# CONEXIÓN A POSTGRESQL (SUPABASE)
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


def _match_deposito_case_insensitive(target: str, depositos: list) -> str:
    t = _norm_str(target).lower()
    for d in depositos:
        if _norm_str(d).lower() == t:
            return d
    return target


# =========================
# TABLAS HISTORIAL
# =========================
def crear_tablas_historial():
    conn = get_connection()
    cur = conn.cursor()

    # Historial de bajas
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

    # Historial de movimientos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS historial_movimientos (
            id SERIAL PRIMARY KEY,
            usuario VARCHAR(100),
            fecha DATE,
            hora TIME,
            codigo VARCHAR(50),
            articulo VARCHAR(255),
            cantidad DECIMAL(10,2),
            deposito_origen VARCHAR(255),
            deposito_destino VARCHAR(255),
            lote VARCHAR(255),
            vencimiento VARCHAR(255),
            stock_origen_antes DECIMAL(14,4),
            stock_origen_despues DECIMAL(14,4),
            stock_destino_antes DECIMAL(14,4),
            stock_destino_despues DECIMAL(14,4),
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()

    cur.close()
    conn.close()


# =========================
# STOCK (TABLA: stock) - BÚSQUEDA Y DETALLE
# =========================
def buscar_items_stock(busqueda: str, limite_filas: int = 500):
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

    # FEFO: primero vencimiento más cercano, luego lote
    out.sort(key=lambda x: (_parse_fecha_for_sort(x.get("VENCIMIENTO")), x.get("LOTE", "")))
    return out


# =========================
# HISTORIAL (INSERT + SELECT)
# =========================
def registrar_baja(
    usuario,
    codigo_interno,
    articulo,
    cantidad,
    deposito=None,
    lote=None,
    vencimiento=None,
    stock_antes_lote=None,
    stock_despues_lote=None,
    stock_total_articulo=None,
    stock_total_deposito=None,
    stock_casa_central=None
):
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
        usuario, ahora.date(), ahora.time(),
        str(codigo_interno), str(articulo), float(cantidad), "Baja",
        deposito, lote, vencimiento,
        stock_antes_lote, stock_despues_lote,
        stock_total_articulo, stock_total_deposito, stock_casa_central
    ))

    conn.commit()
    cur.close()
    conn.close()


def obtener_historial_bajas(limite=50):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT * FROM historial_bajas
        ORDER BY created_at DESC
        LIMIT %s
    """, (limite,))
    res = cur.fetchall()
    cur.close()
    conn.close()
    return res


def registrar_movimiento(
    usuario: str,
    codigo: str,
    articulo: str,
    cantidad: float,
    deposito_origen: str,
    deposito_destino: str,
    lote: str,
    vencimiento: str,
    stock_origen_antes: float,
    stock_origen_despues: float,
    stock_destino_antes: float,
    stock_destino_despues: float
):
    conn = get_connection()
    cur = conn.cursor()
    ahora = datetime.now()

    cur.execute("""
        INSERT INTO historial_movimientos (
            usuario, fecha, hora,
            codigo, articulo, cantidad,
            deposito_origen, deposito_destino,
            lote, vencimiento,
            stock_origen_antes, stock_origen_despues,
            stock_destino_antes, stock_destino_despues
        )
        VALUES (%s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s)
    """, (
        usuario, ahora.date(), ahora.time(),
        str(codigo), str(articulo), float(cantidad),
        str(deposito_origen), str(deposito_destino),
        str(lote), str(vencimiento),
        float(stock_origen_antes), float(stock_origen_despues),
        float(stock_destino_antes), float(stock_destino_despues)
    ))

    conn.commit()
    cur.close()
    conn.close()


def obtener_historial_movimientos(limite=50):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT * FROM historial_movimientos
        ORDER BY created_at DESC
        LIMIT %s
    """, (limite,))
    res = cur.fetchall()
    cur.close()
    conn.close()
    return res


# =========================
# BAJA: ACTUALIZAR STOCK (TABLA stock)
# =========================
def aplicar_baja_en_lote(
    usuario: str,
    codigo: str,
    articulo: str,
    deposito: str,
    lote: str,
    vencimiento: str,
    cantidad: float
):
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

        # Totales post-baja
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

        # Historial baja
        registrar_baja(
            usuario=usuario,
            codigo_interno=codigo,
            articulo=articulo,
            cantidad=float(cantidad),
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


# =========================
# MOVIMIENTO: RESTAR ORIGEN + SUMAR DESTINO
# =========================
def aplicar_movimiento_en_lote(
    usuario: str,
    codigo: str,
    articulo: str,
    familia: str,
    deposito_origen: str,
    deposito_destino: str,
    lote: str,
    vencimiento: str,
    cantidad: float
):
    codigo = _norm_str(codigo)
    articulo = _norm_str(articulo)
    familia = _norm_str(familia)
    deposito_origen = _norm_str(deposito_origen)
    deposito_destino = _norm_str(deposito_destino)
    lote = _norm_str(lote)
    vencimiento = _norm_str(vencimiento)

    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor a 0.")

    conn = get_connection()
    try:
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Lock origen
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
        """, (codigo, articulo, deposito_origen, lote, vencimiento))

        row_o = cur.fetchone()
        if not row_o:
            raise ValueError("No se encontró el lote en el depósito ORIGEN.")

        stock_origen_antes = _to_float(row_o.get("STOCK"))
        if cantidad > stock_origen_antes + 1e-9:
            raise ValueError(f"No hay stock suficiente en ORIGEN. Stock: {stock_origen_antes}")

        stock_origen_despues = stock_origen_antes - float(cantidad)

        # Update origen
        cur.execute("""
            UPDATE stock
            SET "STOCK" = %s
            WHERE
                TRIM("CODIGO") = %s
                AND TRIM("ARTICULO") = %s
                AND TRIM("DEPOSITO") = %s
                AND COALESCE(TRIM("LOTE"), '') = %s
                AND COALESCE(TRIM("VENCIMIENTO"), '') = %s
        """, (_fmt_num(stock_origen_despues), codigo, articulo, deposito_origen, lote, vencimiento))

        # Lock / crear destino
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
        """, (codigo, articulo, deposito_destino, lote, vencimiento))

        row_d = cur.fetchone()
        stock_destino_antes = 0.0

        if row_d:
            stock_destino_antes = _to_float(row_d.get("STOCK"))
            stock_destino_despues = stock_destino_antes + float(cantidad)

            cur.execute("""
                UPDATE stock
                SET "STOCK" = %s
                WHERE
                    TRIM("CODIGO") = %s
                    AND TRIM("ARTICULO") = %s
                    AND TRIM("DEPOSITO") = %s
                    AND COALESCE(TRIM("LOTE"), '') = %s
                    AND COALESCE(TRIM("VENCIMIENTO"), '') = %s
            """, (_fmt_num(stock_destino_despues), codigo, articulo, deposito_destino, lote, vencimiento))
        else:
            stock_destino_despues = float(cantidad)
            cur.execute("""
                INSERT INTO stock ("FAMILIA","CODIGO","ARTICULO","DEPOSITO","LOTE","VENCIMIENTO","STOCK")
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                familia, codigo, articulo, deposito_destino, lote, vencimiento, _fmt_num(stock_destino_despues)
            ))

        conn.commit()

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

    # Historial movimiento (afuera de la transacción de stock para no mezclar commits)
    registrar_movimiento(
        usuario=usuario,
        codigo=codigo,
        articulo=articulo,
        cantidad=float(cantidad),
        deposito_origen=deposito_origen,
        deposito_destino=deposito_destino,
        lote=lote,
        vencimiento=vencimiento,
        stock_origen_antes=float(stock_origen_antes),
        stock_origen_despues=float(stock_origen_despues),
        stock_destino_antes=float(stock_destino_antes),
        stock_destino_despues=float(stock_destino_despues)
    )

    return {
        "stock_origen_antes": stock_origen_antes,
        "stock_origen_despues": stock_origen_despues,
        "stock_destino_antes": stock_destino_antes,
        "stock_destino_despues": stock_destino_despues
    }


# =========================
# UI - SELECCIÓN (callback)
# =========================
def _set_item_seleccionado(codigo: str, articulo: str, familia: str, accion_key: str):
    st.session_state[f"ITEM_SEL_{accion_key}"] = {
        "CODIGO": _norm_str(codigo),
        "ARTICULO": _norm_str(articulo),
        "FAMILIA": _norm_str(familia),
    }


# =========================
# INTERFAZ STREAMLIT
# =========================
def mostrar_baja_stock():
    """
    Pantalla única:
    - Acción: Baja de stock / Movimiento
    - Buscar por CODIGO o ARTICULO
    - Seleccionar -> aparece el formulario (SIEMPRE)
    - Historial de bajas y movimientos
    """

    # -------------------------
    # Qué se tocó (3 líneas)
    # -------------------------
    # 1) Seleccionar ahora usa callback (sin st.rerun manual) + keys por acción para que SIEMPRE funcione.
    # 2) Lotes/vencimientos muestran SOLO stock > 0 (no aparecen los 0).
    # 3) Se quitó “motivo”: es baja/movimiento automático, más simple.

    try:
        crear_tablas_historial()
    except Exception:
        pass

    st.markdown("## 🧾 Baja de Stock / Movimiento")

    accion = st.radio(
        "Acción",
        ["Baja de stock", "Movimiento"],
        horizontal=True,
        key="ACCION_BAJA_MOV"
    )

    accion_key = "BAJA" if accion == "Baja de stock" else "MOV"

    st.markdown("---")

    # Usuario actual
    user = st.session_state.get("user", {})
    usuario_actual = user.get("nombre", user.get("Usuario", "Usuario"))

    # =========================
    # BUSCAR
    # =========================
    col1, col2 = st.columns([3, 1])

    with col1:
        busqueda = st.text_input(
            "🔍 Buscar por CODIGO o ARTICULO",
            placeholder="Ej: 8057800190 / ana profile / rotors",
            key=f"BUSQ_{accion_key}"
        )

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        btn_buscar = st.button("Buscar", type="primary", use_container_width=True, key=f"BTN_BUSCAR_{accion_key}")

    # Guardar resultados para que no dependan del botón en el rerun
    if btn_buscar:
        st.session_state[f"RESULTS_{accion_key}"] = []
        if busqueda:
            try:
                with st.spinner("Buscando en stock..."):
                    st.session_state[f"RESULTS_{accion_key}"] = buscar_items_stock(busqueda)
            except Exception as e:
                st.error(f"Error al buscar: {str(e)}")

    # =========================
    # RESULTADOS
    # =========================
    items = st.session_state.get(f"RESULTS_{accion_key}", [])

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
                    st.button(
                        "Seleccionar",
                        key=f"SEL_{accion_key}_{i}",
                        use_container_width=True,
                        on_click=_set_item_seleccionado,
                        kwargs={
                            "codigo": codigo,
                            "articulo": articulo,
                            "familia": familia,
                            "accion_key": accion_key
                        }
                    )

                st.markdown("---")

    elif btn_buscar and busqueda:
        st.warning("No se encontraron artículos con ese criterio en la tabla stock.")

    # =========================
    # FORMULARIO (BAJA o MOV) - aparece si hay selección
    # =========================
    sel_key = f"ITEM_SEL_{accion_key}"
    if sel_key in st.session_state:
        it = st.session_state[sel_key]
        codigo = _norm_str(it.get("CODIGO"))
        articulo = _norm_str(it.get("ARTICULO"))
        familia = _norm_str(it.get("FAMILIA"))

        st.markdown("### ✅ Seleccionado")
        st.info(f"**{codigo} - {articulo}**  | Familia: **{familia or '—'}**")

        # Cargar lotes
        try:
            lotes_all = obtener_lotes_item(codigo, articulo)
        except Exception as e:
            st.error(f"No se pudo cargar lotes: {str(e)}")
            lotes_all = []

        # Si no hay nada, cortar
        if not lotes_all:
            st.warning("No hay lotes/stock para este artículo en la tabla stock.")
        else:
            # Depósitos existentes en el item
            depositos = sorted({x.get("DEPOSITO", "") for x in lotes_all if _norm_str(x.get("DEPOSITO"))})

            # =========================
            # BAJA
            # =========================
            if accion == "Baja de stock":
                # Depósito: se elige
                default_dep = 0
                for idx, d in enumerate(depositos):
                    if "casa central" in _norm_str(d).lower():
                        default_dep = idx
                        break

                deposito_sel = st.selectbox(
                    "Depósito",
                    options=depositos,
                    index=default_dep if depositos else 0,
                    key=f"DEP_BAJA_{accion_key}"
                )

                # Lotes del depósito con STOCK > 0
                lotes_dep = [
                    x for x in lotes_all
                    if _norm_str(x.get("DEPOSITO")) == _norm_str(deposito_sel)
                    and float(x.get("STOCK_NUM", 0.0) or 0.0) > 0
                ]

                total_articulo = _sum_stock(lotes_all)
                total_deposito = _sum_stock(lotes_all, filtro_deposito=deposito_sel)
                total_casa_central = _sum_stock(lotes_all, solo_casa_central=True)

                st.caption(f"📦 Stock total artículo (todas): **{_fmt_num(total_articulo)}**")
                st.caption(f"🏠 Stock en depósito seleccionado: **{_fmt_num(total_deposito)}**")
                st.caption(f"🏛️ Stock en Casa Central: **{_fmt_num(total_casa_central)}**")

                if not lotes_dep:
                    st.warning("No hay lotes con stock (>0) en el depósito seleccionado.")
                else:
                    df_lotes = pd.DataFrame([{
                        "LOTE": x.get("LOTE") or "—",
                        "VENCIMIENTO": x.get("VENCIMIENTO") or "—",
                        "STOCK": _fmt_num(float(x.get("STOCK_NUM", 0.0) or 0.0))
                    } for x in lotes_dep])

                    st.markdown("#### Lotes / Vencimientos (FEFO)")
                    st.dataframe(df_lotes, use_container_width=True, hide_index=True)

                    # FEFO recomendado = primero (ya vienen ordenados)
                    idx_recomendado = 0

                    opciones = []
                    for j, x in enumerate(lotes_dep):
                        opciones.append(
                            f"{j+1}. Lote: {x.get('LOTE') or '—'} | Venc: {x.get('VENCIMIENTO') or '—'} | Stock: {_fmt_num(float(x.get('STOCK_NUM', 0.0) or 0.0))}"
                        )

                    opcion = st.selectbox(
                        "Elegí el lote a bajar",
                        options=opciones,
                        index=idx_recomendado,
                        key=f"LOTESEL_BAJA_{accion_key}"
                    )

                    idx_sel = int(opcion.split(".")[0]) - 1
                    elegido = lotes_dep[idx_sel]

                    lote_sel = _norm_str(elegido.get("LOTE"))
                    venc_sel = _norm_str(elegido.get("VENCIMIENTO"))
                    stock_lote_sel = float(elegido.get("STOCK_NUM", 0.0) or 0.0)

                    # Aviso si NO es el recomendado (hay uno con vencimiento más cercano antes)
                    confirm_no_fefo = True
                    if idx_sel != idx_recomendado and len(lotes_dep) > 1:
                        ref = lotes_dep[idx_recomendado]
                        st.warning(
                            "⚠️ Por FEFO se recomienda bajar primero el lote con vencimiento más cercano.\n\n"
                            f"Recomendado: **Lote {ref.get('LOTE') or '—'}** | "
                            f"Venc: **{ref.get('VENCIMIENTO') or '—'}** | "
                            f"Stock: **{_fmt_num(float(ref.get('STOCK_NUM', 0.0) or 0.0))}**"
                        )
                        confirm_no_fefo = st.checkbox(
                            "Sí, estoy seguro y quiero bajar este lote igualmente",
                            value=False,
                            key=f"CONF_NO_FEFO_BAJA_{accion_key}"
                        )

                    st.caption(f"Stock lote seleccionado: **{_fmt_num(stock_lote_sel)}**")

                    cantidad = st.number_input(
                        "Cantidad a bajar",
                        min_value=0.01,
                        value=1.0,
                        step=1.0,
                        max_value=float(stock_lote_sel),
                        key=f"CANT_BAJA_{accion_key}"
                    )

                    col_ok, col_cancel = st.columns(2)

                    with col_ok:
                        if st.button("✅ Confirmar Baja", type="primary", use_container_width=True, key=f"OK_BAJA_{accion_key}"):
                            if not deposito_sel:
                                st.error("No elegiste depósito.")
                                st.stop()
                            if float(stock_lote_sel) <= 0:
                                st.error("No elegiste un lote con stock > 0.")
                                st.stop()
                            if float(cantidad) <= 0:
                                st.error("No pusiste cantidad.")
                                st.stop()
                            if not confirm_no_fefo:
                                st.error("Tenés un lote con vencimiento más cercano. Confirmá para continuar.")
                                st.stop()

                            try:
                                res = aplicar_baja_en_lote(
                                    usuario=usuario_actual,
                                    codigo=codigo,
                                    articulo=articulo,
                                    deposito=deposito_sel,
                                    lote=lote_sel,
                                    vencimiento=venc_sel,
                                    cantidad=float(cantidad)
                                )
                                st.success(
                                    f"✅ Baja registrada: {_fmt_num(float(cantidad))} de **{articulo}** "
                                    f"(Lote {lote_sel or '—'} | Venc {venc_sel or '—'})"
                                )
                                st.caption(f"Resta en el lote: **{_fmt_num(res.get('stock_despues_lote', 0.0))}**")
                                st.caption(f"Resta total artículo: **{_fmt_num(res.get('total_articulo', 0.0))}**")
                                st.caption(f"Resta en {deposito_sel}: **{_fmt_num(res.get('total_deposito', 0.0))}**")
                                st.caption(f"Resta en Casa Central: **{_fmt_num(res.get('total_casa_central', 0.0))}**")

                                # Limpiar selección
                                del st.session_state[sel_key]

                            except Exception as e:
                                st.error(f"Error al registrar baja: {str(e)}")

                    with col_cancel:
                        if st.button("❌ Cancelar", use_container_width=True, key=f"CANCEL_BAJA_{accion_key}"):
                            del st.session_state[sel_key]

            # =========================
            # MOVIMIENTO
            # =========================
            else:
                # Mapa familia -> depósito destino
                MAP_FAMILIA_DEP_DESTINO = {
                    "G": "Generales",
                    "XX": "Inmunoanalisis",
                    "ID": "Inmunodiagnostico",
                    "FB": "Microbiologia",
                    "LP": "Limpieza",
                    "AF": "Alejandra Fajardo",
                    "CT": "Citometria",
                }

                # Origen: preferir Casa Central si existe
                origen_default = None
                for d in depositos:
                    if "casa central" in _norm_str(d).lower():
                        origen_default = d
                        break
                if origen_default is None:
                    origen_default = depositos[0] if depositos else ""

                deposito_origen = st.selectbox(
                    "Depósito ORIGEN",
                    options=depositos,
                    index=depositos.index(origen_default) if origen_default in depositos else 0,
                    key=f"DEP_ORIG_{accion_key}"
                )

                # Destino automático por familia si existe
                fam_up = _norm_str(familia).upper()
                destino_auto = MAP_FAMILIA_DEP_DESTINO.get(fam_up, "")

                # Ajustar case si el destino ya existe en la lista de depósitos
                destino_auto = _match_deposito_case_insensitive(destino_auto, depositos)

                # Si el destino auto coincide con origen o no existe, permitir elegir
                depositos_destino = [d for d in depositos if _norm_str(d) and _norm_str(d) != _norm_str(deposito_origen)]
                if destino_auto and _norm_str(destino_auto) != _norm_str(deposito_origen):
                    deposito_destino = destino_auto
                    st.caption(f"Depósito DESTINO (por familia **{fam_up}**): **{deposito_destino}**")
                else:
                    deposito_destino = st.selectbox(
                        "Depósito DESTINO",
                        options=depositos_destino if depositos_destino else ["—"],
                        index=0,
                        key=f"DEP_DEST_{accion_key}"
                    )
                    if deposito_destino == "—":
                        deposito_destino = ""

                # Lotes del ORIGEN con STOCK > 0
                lotes_origen = [
                    x for x in lotes_all
                    if _norm_str(x.get("DEPOSITO")) == _norm_str(deposito_origen)
                    and float(x.get("STOCK_NUM", 0.0) or 0.0) > 0
                ]

                total_origen = _sum_stock(lotes_all, filtro_deposito=deposito_origen)

                st.caption(f"📦 Stock en ORIGEN ({deposito_origen}): **{_fmt_num(total_origen)}**")

                if not lotes_origen:
                    st.warning("No hay lotes con stock (>0) en el depósito ORIGEN.")
                else:
                    df_lotes = pd.DataFrame([{
                        "LOTE": x.get("LOTE") or "—",
                        "VENCIMIENTO": x.get("VENCIMIENTO") or "—",
                        "STOCK": _fmt_num(float(x.get("STOCK_NUM", 0.0) or 0.0))
                    } for x in lotes_origen])

                    st.markdown("#### Lotes / Vencimientos (FEFO)")
                    st.dataframe(df_lotes, use_container_width=True, hide_index=True)

                    # FEFO recomendado = primero
                    idx_recomendado = 0

                    opciones = []
                    for j, x in enumerate(lotes_origen):
                        opciones.append(
                            f"{j+1}. Lote: {x.get('LOTE') or '—'} | Venc: {x.get('VENCIMIENTO') or '—'} | Stock: {_fmt_num(float(x.get('STOCK_NUM', 0.0) or 0.0))}"
                        )

                    opcion = st.selectbox(
                        "Elegí el lote a mover",
                        options=opciones,
                        index=idx_recomendado,
                        key=f"LOTESEL_MOV_{accion_key}"
                    )

                    idx_sel = int(opcion.split(".")[0]) - 1
                    elegido = lotes_origen[idx_sel]

                    lote_sel = _norm_str(elegido.get("LOTE"))
                    venc_sel = _norm_str(elegido.get("VENCIMIENTO"))
                    stock_lote_sel = float(elegido.get("STOCK_NUM", 0.0) or 0.0)

                    confirm_no_fefo = True
                    if idx_sel != idx_recomendado and len(lotes_origen) > 1:
                        ref = lotes_origen[idx_recomendado]
                        st.warning(
                            "⚠️ Por FEFO se recomienda mover primero el lote con vencimiento más cercano.\n\n"
                            f"Recomendado: **Lote {ref.get('LOTE') or '—'}** | "
                            f"Venc: **{ref.get('VENCIMIENTO') or '—'}** | "
                            f"Stock: **{_fmt_num(float(ref.get('STOCK_NUM', 0.0) or 0.0))}**"
                        )
                        confirm_no_fefo = st.checkbox(
                            "Sí, estoy seguro y quiero mover este lote igualmente",
                            value=False,
                            key=f"CONF_NO_FEFO_MOV_{accion_key}"
                        )

                    st.caption(f"Stock lote seleccionado: **{_fmt_num(stock_lote_sel)}**")

                    cantidad = st.number_input(
                        "Cantidad a mover",
                        min_value=0.01,
                        value=1.0,
                        step=1.0,
                        max_value=float(stock_lote_sel),
                        key=f"CANT_MOV_{accion_key}"
                    )

                    col_ok, col_cancel = st.columns(2)

                    with col_ok:
                        if st.button("✅ Confirmar Movimiento", type="primary", use_container_width=True, key=f"OK_MOV_{accion_key}"):
                            if not deposito_origen:
                                st.error("No elegiste depósito ORIGEN.")
                                st.stop()
                            if not deposito_destino:
                                st.error("No elegiste depósito DESTINO.")
                                st.stop()
                            if float(stock_lote_sel) <= 0:
                                st.error("No elegiste un lote con stock > 0.")
                                st.stop()
                            if float(cantidad) <= 0:
                                st.error("No pusiste cantidad.")
                                st.stop()
                            if not confirm_no_fefo:
                                st.error("Tenés un lote con vencimiento más cercano. Confirmá para continuar.")
                                st.stop()

                            try:
                                res = aplicar_movimiento_en_lote(
                                    usuario=usuario_actual,
                                    codigo=codigo,
                                    articulo=articulo,
                                    familia=familia,
                                    deposito_origen=deposito_origen,
                                    deposito_destino=deposito_destino,
                                    lote=lote_sel,
                                    vencimiento=venc_sel,
                                    cantidad=float(cantidad)
                                )

                                st.success(
                                    f"✅ Movimiento OK: {_fmt_num(float(cantidad))} de **{articulo}** "
                                    f"de **{deposito_origen}** → **{deposito_destino}** "
                                    f"(Lote {lote_sel or '—'} | Venc {venc_sel or '—'})"
                                )
                                st.caption(f"Origen: {res.get('stock_origen_antes', 0.0)} → {res.get('stock_origen_despues', 0.0)}")
                                st.caption(f"Destino: {res.get('stock_destino_antes', 0.0)} → {res.get('stock_destino_despues', 0.0)}")

                                del st.session_state[sel_key]

                            except Exception as e:
                                st.error(f"Error al mover: {str(e)}")

                    with col_cancel:
                        if st.button("❌ Cancelar", use_container_width=True, key=f"CANCEL_MOV_{accion_key}"):
                            del st.session_state[sel_key]

    # =========================
    # HISTORIALES
    # =========================
    st.markdown("---")
    st.markdown("### 📋 Historial de Bajas")
    try:
        historial = obtener_historial_bajas(50)
        if historial:
            df = pd.DataFrame(historial)
            if "fecha" in df.columns:
                df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.strftime("%d/%m/%Y")
            if "hora" in df.columns:
                df["hora"] = df["hora"].astype(str).str[:8]

            cols = [
                "fecha", "hora", "usuario",
                "codigo_interno", "articulo",
                "deposito", "lote", "vencimiento",
                "cantidad",
                "stock_total_deposito", "stock_casa_central"
            ]
            cols = [c for c in cols if c in df.columns]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)
        else:
            st.info("No hay registros de bajas todavía")
    except Exception as e:
        st.warning(f"No se pudo cargar el historial de bajas: {str(e)}")

    st.markdown("### 📋 Historial de Movimientos")
    try:
        hist_m = obtener_historial_movimientos(50)
        if hist_m:
            dfm = pd.DataFrame(hist_m)
            if "fecha" in dfm.columns:
                dfm["fecha"] = pd.to_datetime(dfm["fecha"], errors="coerce").dt.strftime("%d/%m/%Y")
            if "hora" in dfm.columns:
                dfm["hora"] = dfm["hora"].astype(str).str[:8]

            cols = [
                "fecha", "hora", "usuario",
                "codigo", "articulo",
                "deposito_origen", "deposito_destino",
                "lote", "vencimiento",
                "cantidad",
                "stock_origen_antes", "stock_origen_despues",
                "stock_destino_antes", "stock_destino_despues"
            ]
            cols = [c for c in cols if c in dfm.columns]
            st.dataframe(dfm[cols], use_container_width=True, hide_index=True)
        else:
            st.info("No hay registros de movimientos todavía")
    except Exception as e:
        st.warning(f"No se pudo cargar el historial de movimientos: {str(e)}")
