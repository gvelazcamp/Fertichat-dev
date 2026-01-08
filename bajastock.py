# =========================
# BAJASTOCK.PY - Baja de stock + Movimiento (con historial)
# =========================
# CAMBIOS (3 líneas):
# 1) UI: agrego selector “Acción: Baja / Movimiento” y estados separados de selección para que “Seleccionar” funcione en ambos.
# 2) MOVIMIENTO: agrego tabla historial_movimientos + funciones aplicar_movimiento_en_lote / aplicar_movimiento_fifo (mueve entre depósitos).
# 3) BAJA: filtro lotes con STOCK > 0 (no muestra ceros) y saco “Motivo” obligatorio (se registra automático como “Baja”).

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
# TABLAS HISTORIALES
# =========================
def crear_tabla_historial_bajas():
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


def crear_tabla_historial_movimientos():
    """Crea historial de movimientos si no existe (no rompe lo existente)."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS historial_movimientos (
            id SERIAL PRIMARY KEY,
            usuario VARCHAR(100),
            fecha DATE,
            hora TIME,
            codigo_interno VARCHAR(50),
            articulo VARCHAR(255),
            cantidad DECIMAL(14,4),
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
    """Registra una baja en el historial (motivo automático)."""
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
        usuario, ahora.date(), ahora.time(), str(codigo_interno), str(articulo), float(cantidad), "Baja",
        deposito, lote, vencimiento,
        stock_antes_lote, stock_despues_lote,
        stock_total_articulo, stock_total_deposito, stock_casa_central
    ))

    conn.commit()
    cur.close()
    conn.close()


def obtener_historial_bajas(limite=50):
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


def registrar_movimiento(
    usuario,
    codigo_interno,
    articulo,
    cantidad,
    deposito_origen,
    deposito_destino,
    lote,
    vencimiento,
    stock_origen_antes,
    stock_origen_despues,
    stock_destino_antes,
    stock_destino_despues
):
    conn = get_connection()
    cur = conn.cursor()

    ahora = datetime.now()

    cur.execute("""
        INSERT INTO historial_movimientos (
            usuario, fecha, hora,
            codigo_interno, articulo, cantidad,
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
        str(codigo_interno), str(articulo), float(cantidad),
        deposito_origen, deposito_destino,
        lote, vencimiento,
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
# ACTUALIZAR STOCK (TABLA: stock) - BAJA
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
        if float(cantidad) <= 0:
            raise ValueError("La cantidad debe ser mayor a 0.")
        if float(cantidad) > stock_antes + 1e-9:
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
    cantidad: float
):
    """
    Baja por FIFO/FEFO automático en un depósito:
    consume primero el lote con vencimiento más cercano.
    Registra UNA entrada de historial por cada lote consumido.
    """
    codigo = _norm_str(codigo)
    articulo = _norm_str(articulo)
    deposito = _norm_str(deposito)

    if float(cantidad) <= 0:
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
            cantidad=float(a_bajar)
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
# MOVIMIENTO (CASA CENTRAL -> DEPÓSITO DESTINO)
# =========================
def aplicar_movimiento_en_lote(
    usuario: str,
    codigo: str,
    articulo: str,
    deposito_origen: str,
    deposito_destino: str,
    lote: str,
    vencimiento: str,
    cantidad: float
):
    """
    Movimiento = restar en ORIGEN (lote/venc) y sumar en DESTINO (mismo lote/venc).
    Si el lote no existe en destino, lo crea.
    """
    codigo = _norm_str(codigo)
    articulo = _norm_str(articulo)
    deposito_origen = _norm_str(deposito_origen)
    deposito_destino = _norm_str(deposito_destino)
    lote = _norm_str(lote)
    vencimiento = _norm_str(vencimiento)

    if not deposito_origen:
        raise ValueError("No elegiste depósito de origen.")
    if not deposito_destino:
        raise ValueError("No elegiste depósito destino.")
    if deposito_origen.lower() == deposito_destino.lower():
        raise ValueError("El depósito destino no puede ser igual al origen.")
    if float(cantidad) <= 0:
        raise ValueError("La cantidad debe ser mayor a 0.")

    conn = get_connection()
    try:
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Lock ORIGEN
        cur.execute("""
            SELECT "STOCK", "FAMILIA"
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
            raise ValueError("No se encontró el lote en el depósito de origen.")

        familia = _norm_str(row_o.get("FAMILIA"))
        stock_origen_antes = _to_float(row_o.get("STOCK"))
        if float(cantidad) > stock_origen_antes + 1e-9:
            raise ValueError(f"No hay stock suficiente en origen. Stock: {stock_origen_antes}")

        stock_origen_despues = stock_origen_antes - float(cantidad)

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

        # Lock/crear DESTINO
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
            stock_destino_antes = 0.0
            stock_destino_despues = float(cantidad)

            cur.execute("""
                INSERT INTO stock ("FAMILIA","CODIGO","ARTICULO","DEPOSITO","LOTE","VENCIMIENTO","STOCK")
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (familia, codigo, articulo, deposito_destino, lote, vencimiento, _fmt_num(stock_destino_despues)))

        registrar_movimiento(
            usuario=usuario,
            codigo_interno=codigo,
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

        conn.commit()

        return {
            "stock_origen_antes": stock_origen_antes,
            "stock_origen_despues": stock_origen_despues,
            "stock_destino_antes": stock_destino_antes,
            "stock_destino_despues": stock_destino_despues
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


def aplicar_movimiento_fifo(
    usuario: str,
    codigo: str,
    articulo: str,
    deposito_origen: str,
    deposito_destino: str,
    cantidad: float
):
    """
    Movimiento FEFO: toma primero el lote con vencimiento más cercano del depósito origen.
    Registra una fila de historial por cada lote movido.
    """
    if float(cantidad) <= 0:
        raise ValueError("La cantidad debe ser mayor a 0.")

    lotes_all = obtener_lotes_item(codigo, articulo)
    lotes_o = [
        x for x in lotes_all
        if _norm_str(x.get("DEPOSITO")) == _norm_str(deposito_origen) and float(x.get("STOCK_NUM", 0.0) or 0.0) > 0
    ]

    if not lotes_o:
        raise ValueError("No hay lotes con stock en el depósito origen.")

    restante = float(cantidad)
    resumen = []

    for lt in lotes_o:
        if restante <= 1e-9:
            break

        disp = float(lt.get("STOCK_NUM", 0.0) or 0.0)
        if disp <= 1e-9:
            continue

        a_mover = min(disp, restante)

        r = aplicar_movimiento_en_lote(
            usuario=usuario,
            codigo=codigo,
            articulo=articulo,
            deposito_origen=deposito_origen,
            deposito_destino=deposito_destino,
            lote=_norm_str(lt.get("LOTE")),
            vencimiento=_norm_str(lt.get("VENCIMIENTO")),
            cantidad=float(a_mover)
        )

        resumen.append({
            "lote": _norm_str(lt.get("LOTE")),
            "vencimiento": _norm_str(lt.get("VENCIMIENTO")),
            "movido": float(a_mover),
            "origen_resta": float(r.get("stock_origen_despues", 0.0)),
            "destino_queda": float(r.get("stock_destino_despues", 0.0))
        })

        restante -= float(a_mover)

    if restante > 1e-6:
        raise ValueError(f"No alcanzó el stock en origen. Faltó mover: {restante}")

    return resumen


# =========================
# INTERFAZ STREAMLIT
# =========================
def mostrar_baja_stock():
    """
    Pantalla:
    - Acción: Baja de stock / Movimiento
    - Buscar por CODIGO o ARTICULO
    - Seleccionar abre el flujo (lotes + confirmar) en ambos
    """
    try:
        crear_tabla_historial_bajas()
        crear_tabla_historial_movimientos()
    except Exception:
        pass

    st.markdown("## 🧾 Baja de Stock / Movimiento")
    st.markdown("---")

    user = st.session_state.get("user", {})
    usuario_actual = user.get("nombre", user.get("Usuario", "Usuario"))

    # Acción
    accion = st.radio(
        "Acción",
        ["Baja de stock", "Movimiento"],
        index=0,
        horizontal=True,
        key="accion_bajastock"
    )

    # Si cambia la acción, limpiamos selección para evitar “queda clavado”
    last_accion = st.session_state.get("accion_bajastock_last")
    if last_accion != accion:
        st.session_state.pop("item_seleccionado_stock", None)
        st.session_state.pop("item_seleccionado_mov_stock", None)
        st.session_state["accion_bajastock_last"] = accion

    # =========================
    # BÚSQUEDA (MISMA IDEA, KEYS DIFERENTES)
    # =========================
    col1, col2 = st.columns([3, 1])

    if accion == "Baja de stock":
        key_busqueda = "busqueda_baja_stock"
        key_btn = "btn_buscar_baja"
        key_sel_prefix = "sel_item_baja_"
        key_item_sel = "item_seleccionado_stock"
    else:
        key_busqueda = "busqueda_mov_stock"
        key_btn = "btn_buscar_mov"
        key_sel_prefix = "sel_item_mov_"
        key_item_sel = "item_seleccionado_mov_stock"

    with col1:
        busqueda = st.text_input(
            "🔍 Buscar por CODIGO o ARTICULO",
            placeholder="Ej: 12345 / rotors / gluc3",
            key=key_busqueda
        )

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        btn_buscar = st.button("Buscar", type="primary", use_container_width=True, key=key_btn)

    # =========================
    # RESULTADOS (SOLO AL APRETAR BUSCAR)
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
                                if st.button("Seleccionar", key=f"{key_sel_prefix}{i}"):
                                    st.session_state[key_item_sel] = {
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
    # FORMULARIO (BAJA o MOVIMIENTO)
    # =========================
    if key_item_sel in st.session_state:
        it = st.session_state[key_item_sel]

        codigo = _norm_str(it.get("CODIGO"))
        articulo = _norm_str(it.get("ARTICULO"))
        familia = _norm_str(it.get("FAMILIA"))

        st.markdown("### 📝 Detalle")
        st.info(f"Artículo seleccionado: **{codigo} - {articulo}**")

        try:
            lotes = obtener_lotes_item(codigo, articulo)
        except Exception as e:
            st.error(f"No se pudo cargar lotes del artículo: {str(e)}")
            lotes = []

        # SOLO STOCK > 0 (NO MUESTRA CEROS)
        lotes = [x for x in lotes if float(x.get("STOCK_NUM", 0.0) or 0.0) > 0]

        if not lotes:
            st.warning("Este artículo no tiene lotes con stock > 0.")
        else:
            depositos = sorted({x.get("DEPOSITO", "") for x in lotes if _norm_str(x.get("DEPOSITO"))})

            # defaults
            default_dep_cc = 0
            for idx, d in enumerate(depositos):
                if "casa central" in d.lower():
                    default_dep_cc = idx
                    break

            if accion == "Baja de stock":
                colA, colB = st.columns([2, 1])
                with colA:
                    deposito_sel = st.selectbox(
                        "Depósito",
                        options=depositos,
                        index=default_dep_cc if depositos else 0,
                        key="baja_dep_sel"
                    )
                with colB:
                    st.caption(f"Código: **{codigo}**")
                    st.caption(f"Familia: **{familia or '—'}**")

                lotes_dep = [x for x in lotes if _norm_str(x.get("DEPOSITO")) == _norm_str(deposito_sel)]
                lotes_dep = [x for x in lotes_dep if float(x.get("STOCK_NUM", 0.0) or 0.0) > 0]

                total_articulo = _sum_stock(lotes)
                total_deposito = _sum_stock(lotes, filtro_deposito=deposito_sel)
                total_casa_central = _sum_stock(lotes, solo_casa_central=True)

                st.caption(f"📦 Stock total artículo (todas): **{_fmt_num(total_articulo)}**")
                st.caption(f"🏠 Stock en depósito seleccionado: **{_fmt_num(total_deposito)}**")
                st.caption(f"🏛️ Stock en Casa Central: **{_fmt_num(total_casa_central)}**")

                if not lotes_dep:
                    st.warning("No hay lotes con stock > 0 en el depósito seleccionado.")
                else:
                    df_lotes = pd.DataFrame([{
                        "LOTE": x.get("LOTE"),
                        "VENCIMIENTO": x.get("VENCIMIENTO"),
                        "STOCK": _fmt_num(float(x.get("STOCK_NUM", 0.0) or 0.0))
                    } for x in lotes_dep])

                    st.markdown("#### Lotes / Vencimientos (orden FIFO/FEFO)")
                    st.dataframe(df_lotes, use_container_width=True, hide_index=True)

                    # recomendado: el primero (porque ya viene ordenado por vencimiento)
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

                        opcion = st.selectbox(
                            "Elegí el lote a bajar",
                            options=opciones,
                            index=idx_fifo if idx_fifo < len(opciones) else 0,
                            key="baja_lote_sel"
                        )
                        idx = int(opcion.split(".")[0]) - 1
                        elegido = lotes_dep[idx]

                        lote_sel = _norm_str(elegido.get("LOTE"))
                        venc_sel = _norm_str(elegido.get("VENCIMIENTO"))
                        stock_lote_sel = float(elegido.get("STOCK_NUM", 0.0) or 0.0)

                        # alerta si elige uno que NO es el primero (FEFO)
                        if idx != idx_fifo and len(lotes_dep) > 1:
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

                    col_guardar, col_cancelar = st.columns(2)

                    with col_guardar:
                        if st.button("✅ Confirmar Baja", type="primary", use_container_width=True, key="btn_confirmar_baja"):
                            try:
                                if (not usar_fifo) and (len(lotes_dep) > 1):
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
                                        cantidad=float(cantidad)
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

                                del st.session_state[key_item_sel]
                                st.rerun()

                            except Exception as e:
                                st.error(f"Error al registrar baja: {str(e)}")

                    with col_cancelar:
                        if st.button("❌ Cancelar", use_container_width=True, key="btn_cancelar_baja"):
                            del st.session_state[key_item_sel]
                            st.rerun()

            # =========================
            # MOVIMIENTO
            # =========================
            else:
                # Mapeo sugerido por familia (no obliga, solo sugiere)
                FAMILIA_A_DESTINO = {
                    "g": "Generales",
                    "xx": "Inmunoanalisis",
                    "id": "Inmunodiagnostico",
                    "fb": "Microbiologia",
                    "lp": "Limpieza",
                    "af": "Alejandra Fajardo",
                    "ct": "Citometria",
                }

                # ORIGEN default: Casa Central
                deposito_origen = st.selectbox(
                    "Depósito ORIGEN",
                    options=depositos,
                    index=default_dep_cc if depositos else 0,
                    key="mov_dep_origen"
                )

                # opciones destino: depósitos existentes + destinos sugeridos
                destinos_sugeridos = list(set(FAMILIA_A_DESTINO.values()))
                destinos = sorted(set([d for d in depositos if _norm_str(d)] + destinos_sugeridos))

                # no permitir igual que origen
                destinos = [d for d in destinos if _norm_str(d).lower() != _norm_str(deposito_origen).lower()]
                if not destinos:
                    destinos = destinos_sugeridos

                sugerido = FAMILIA_A_DESTINO.get(_norm_str(familia).lower())
                idx_dest = 0
                if sugerido and sugerido in destinos:
                    idx_dest = destinos.index(sugerido)

                deposito_destino = st.selectbox(
                    "Depósito DESTINO",
                    options=destinos,
                    index=idx_dest,
                    key="mov_dep_destino"
                )

                lotes_o = [x for x in lotes if _norm_str(x.get("DEPOSITO")) == _norm_str(deposito_origen)]
                lotes_o = [x for x in lotes_o if float(x.get("STOCK_NUM", 0.0) or 0.0) > 0]

                total_articulo = _sum_stock(lotes)
                total_origen = _sum_stock(lotes, filtro_deposito=deposito_origen)

                st.caption(f"🏷️ Familia: **{familia or '—'}**")
                st.caption(f"📦 Stock total artículo (todas): **{_fmt_num(total_articulo)}**")
                st.caption(f"🏠 Stock en ORIGEN: **{_fmt_num(total_origen)}**")

                if not lotes_o:
                    st.warning("No hay lotes con stock > 0 en el depósito ORIGEN.")
                else:
                    df_lotes = pd.DataFrame([{
                        "LOTE": x.get("LOTE"),
                        "VENCIMIENTO": x.get("VENCIMIENTO"),
                        "STOCK": _fmt_num(float(x.get("STOCK_NUM", 0.0) or 0.0))
                    } for x in lotes_o])

                    st.markdown("#### Lotes / Vencimientos (orden FIFO/FEFO)")
                    st.dataframe(df_lotes, use_container_width=True, hide_index=True)

                    idx_fifo = 0

                    usar_fifo = st.checkbox(
                        "✅ Mover siguiendo FIFO/FEFO automático (recomendado)",
                        value=True,
                        key="mov_fifo_auto"
                    )

                    lote_sel = None
                    venc_sel = None
                    stock_lote_sel = 0.0
                    confirm_no_fifo = False

                    if not usar_fifo:
                        opciones = []
                        for j, x in enumerate(lotes_o):
                            opciones.append(
                                f"{j+1}. Lote: {x.get('LOTE') or '—'} | Venc: {x.get('VENCIMIENTO') or '—'} | Stock: {_fmt_num(float(x.get('STOCK_NUM', 0.0) or 0.0))}"
                            )

                        opcion = st.selectbox(
                            "Elegí el lote a mover",
                            options=opciones,
                            index=idx_fifo if idx_fifo < len(opciones) else 0,
                            key="mov_lote_sel"
                        )
                        idx = int(opcion.split(".")[0]) - 1
                        elegido = lotes_o[idx]

                        lote_sel = _norm_str(elegido.get("LOTE"))
                        venc_sel = _norm_str(elegido.get("VENCIMIENTO"))
                        stock_lote_sel = float(elegido.get("STOCK_NUM", 0.0) or 0.0)

                        if idx != idx_fifo and len(lotes_o) > 1:
                            fifo_ref = lotes_o[idx_fifo]
                            st.warning(
                                "⚠️ Estás eligiendo un lote que NO es el recomendado por FIFO/FEFO.\n\n"
                                f"Antes hay: **Lote {fifo_ref.get('LOTE') or '—'}** | "
                                f"Venc: **{fifo_ref.get('VENCIMIENTO') or '—'}** | "
                                f"Stock: **{_fmt_num(float(fifo_ref.get('STOCK_NUM', 0.0) or 0.0))}**"
                            )
                            confirm_no_fifo = st.checkbox(
                                "Sí, estoy seguro y quiero mover este lote igualmente",
                                value=False,
                                key="mov_confirm_no_fifo"
                            )

                        st.caption(f"Stock lote seleccionado: **{_fmt_num(stock_lote_sel)}**")

                    if (not usar_fifo) and stock_lote_sel > 0:
                        cantidad = st.number_input(
                            "Cantidad a mover",
                            min_value=0.01,
                            value=1.0,
                            step=1.0,
                            max_value=float(stock_lote_sel),
                            key="cantidad_mov_stock"
                        )
                    else:
                        cantidad = st.number_input(
                            "Cantidad a mover",
                            min_value=0.01,
                            value=1.0,
                            step=1.0,
                            key="cantidad_mov_stock"
                        )

                    col_guardar, col_cancelar = st.columns(2)

                    with col_guardar:
                        if st.button("✅ Confirmar Movimiento", type="primary", use_container_width=True, key="btn_confirmar_mov"):
                            try:
                                if (not usar_fifo) and (len(lotes_o) > 1):
                                    opcion_txt = st.session_state.get("mov_lote_sel", "")
                                    if opcion_txt:
                                        idx_sel = int(opcion_txt.split(".")[0]) - 1
                                        if idx_sel != idx_fifo and not confirm_no_fifo:
                                            st.error("Tenés un lote anterior. Marcá la confirmación para continuar.")
                                            st.stop()

                                if usar_fifo:
                                    resumen = aplicar_movimiento_fifo(
                                        usuario=usuario_actual,
                                        codigo=codigo,
                                        articulo=articulo,
                                        deposito_origen=deposito_origen,
                                        deposito_destino=deposito_destino,
                                        cantidad=float(cantidad)
                                    )
                                    st.success("✅ Movimiento registrado por FIFO/FEFO.")
                                    for r in resumen:
                                        st.caption(
                                            f"- Lote **{r['lote'] or '—'}** | Venc: **{r['vencimiento'] or '—'}** "
                                            f"| Movido: **{_fmt_num(r['movido'])}** | "
                                            f"Origen resta: **{_fmt_num(r['origen_resta'])}** | "
                                            f"Destino queda: **{_fmt_num(r['destino_queda'])}**"
                                        )
                                else:
                                    res = aplicar_movimiento_en_lote(
                                        usuario=usuario_actual,
                                        codigo=codigo,
                                        articulo=articulo,
                                        deposito_origen=deposito_origen,
                                        deposito_destino=deposito_destino,
                                        lote=lote_sel,
                                        vencimiento=venc_sel,
                                        cantidad=float(cantidad)
                                    )
                                    st.success(
                                        f"✅ Movimiento registrado: {_fmt_num(float(cantidad))} de **{articulo}** "
                                        f"(Lote {lote_sel or '—'} | Venc {venc_sel or '—'})"
                                    )
                                    st.caption(f"Origen queda: **{_fmt_num(res.get('stock_origen_despues', 0.0))}**")
                                    st.caption(f"Destino queda: **{_fmt_num(res.get('stock_destino_despues', 0.0))}**")

                                del st.session_state[key_item_sel]
                                st.rerun()

                            except Exception as e:
                                st.error(f"Error al registrar movimiento: {str(e)}")

                    with col_cancelar:
                        if st.button("❌ Cancelar", use_container_width=True, key="btn_cancelar_mov"):
                            del st.session_state[key_item_sel]
                            st.rerun()

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

            columnas_preferidas = [
                "fecha", "hora", "usuario",
                "codigo_interno", "articulo",
                "deposito", "lote", "vencimiento",
                "cantidad",
                "stock_total_deposito", "stock_casa_central"
            ]
            columnas_existentes = [c for c in columnas_preferidas if c in df.columns]

            st.dataframe(df[columnas_existentes], use_container_width=True, hide_index=True)
        else:
            st.info("No hay registros de bajas todavía")
    except Exception as e:
        st.warning(f"No se pudo cargar el historial: {str(e)}")

    st.markdown("---")
    st.markdown("### 📋 Historial de Movimientos")
    try:
        historial = obtener_historial_movimientos(50)
        if historial:
            df = pd.DataFrame(historial)
            if "fecha" in df.columns:
                df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.strftime("%d/%m/%Y")
            if "hora" in df.columns:
                df["hora"] = df["hora"].astype(str).str[:8]

            cols_pref = [
                "fecha", "hora", "usuario",
                "codigo_interno", "articulo",
                "deposito_origen", "deposito_destino",
                "lote", "vencimiento",
                "cantidad",
                "stock_origen_despues", "stock_destino_despues"
            ]
            cols_ok = [c for c in cols_pref if c in df.columns]
            st.dataframe(df[cols_ok], use_container_width=True, hide_index=True)
        else:
            st.info("No hay movimientos todavía")
    except Exception as e:
        st.warning(f"No se pudo cargar el historial: {str(e)}")
