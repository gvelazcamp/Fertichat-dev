# =====================================================================
# 📒 MÓDULO FICHA DE STOCK - FERTI CHAT
# Archivo: ficha_stock.py
# =====================================================================

import streamlit as st
import pandas as pd
from datetime import datetime, date
from typing import List, Dict, Any, Optional

from supabase_client import supabase


# =====================================================================
# Helpers
# =====================================================================

def _to_datetime_safe(x) -> Optional[pd.Timestamp]:
    if x is None or x == "":
        return None
    try:
        return pd.to_datetime(x)
    except Exception:
        return None


def _safe_float(x) -> float:
    try:
        if x is None or x == "":
            return 0.0
        return float(x)
    except Exception:
        return 0.0


def _fmt_num(x, dec=2) -> str:
    try:
        return f"{float(x):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0"


def _fetch_articulos(q: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Requiere tabla 'articulos' con al menos: id, nombre.
    Opcionales: codigo_interno.
    """
    q = (q or "").strip()
    try:
        query = supabase.table("articulos").select("id,nombre,codigo_interno")
        if q:
            # Busca por nombre o código interno
            query = query.or_(f"nombre.ilike.%{q}%,codigo_interno.ilike.%{q}%")
        resp = query.limit(limit).execute()
        data = resp.data or []
        return data
    except Exception as e:
        st.error(f"No pude leer 'articulos' desde Supabase. Error: {e}")
        return []


def _fetch_movimientos(articulo_id: Any, fecha_desde: Optional[date], fecha_hasta: Optional[date]) -> List[Dict[str, Any]]:
    """
    Requiere tabla 'movimientos_stock' con columnas sugeridas:
    - id, articulo_id, fecha_hora, tipo_mov, deposito_id (o deposito_origen_id/deposito_destino_id)
    - qty_base (cantidad en unidad base; entrada positiva / salida negativa)
    - lote, vencimiento
    - ref_tipo, ref_nro, proveedor_id (o proveedor), usuario, observacion
    - precio_unit_aplicado, moneda

    Nota: Si tus nombres difieren, ajustá SOLO los campos del select().
    """
    try:
        sel = (
            "id,articulo_id,fecha_hora,tipo_mov,"
            "deposito_id,deposito_origen_id,deposito_destino_id,"
            "qty_base,unidad_mov,factor_conversion,"
            "lote,vencimiento,"
            "ref_tipo,ref_nro,proveedor,proveedor_id,usuario,observacion,"
            "precio_unit_aplicado,moneda"
        )

        q = supabase.table("movimientos_stock").select(sel).eq("articulo_id", articulo_id)

        if fecha_desde:
            q = q.gte("fecha_hora", datetime.combine(fecha_desde, datetime.min.time()).isoformat())
        if fecha_hasta:
            q = q.lte("fecha_hora", datetime.combine(fecha_hasta, datetime.max.time()).isoformat())

        # Orden cronológico
        resp = q.order("fecha_hora", desc=False).execute()
        return resp.data or []
    except Exception as e:
        st.error(f"No pude leer 'movimientos_stock' desde Supabase. Error: {e}")
        return []


def _calcular_kardex_promedio_movil(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula:
    - qty_in / qty_out
    - costo_promedio (móvil)
    - costo_unit_aplicado en BAJAS (usa costo_promedio previo)
    - valor_mov (positivo entradas / negativo salidas)
    - saldo_qty / saldo_valor

    Supone qty_base:
      > 0 = entrada
      < 0 = salida
    """
    if df.empty:
        return df

    df = df.copy()

    # Normaliza fecha
    if "fecha_hora" in df.columns:
        df["fecha_hora_dt"] = df["fecha_hora"].apply(_to_datetime_safe)
    else:
        df["fecha_hora_dt"] = None

    # Normaliza qty_base
    if "qty_base" not in df.columns:
        df["qty_base"] = 0

    df["qty_base"] = df["qty_base"].apply(_safe_float)

    # Entradas / salidas
    df["qty_in"] = df["qty_base"].apply(lambda x: x if x > 0 else 0)
    df["qty_out"] = df["qty_base"].apply(lambda x: abs(x) if x < 0 else 0)

    # Precio entrada (factura/alta)
    if "precio_unit_aplicado" not in df.columns:
        df["precio_unit_aplicado"] = 0

    df["precio_unit_aplicado"] = df["precio_unit_aplicado"].apply(_safe_float)

    # Costo promedio móvil + valorización
    saldo_qty = 0.0
    saldo_valor = 0.0
    costo_prom = 0.0

    costo_unit_baja: List[float] = []
    valor_mov: List[float] = []
    saldo_qty_list: List[float] = []
    saldo_valor_list: List[float] = []
    costo_prom_list: List[float] = []

    for _, r in df.iterrows():
        qty = _safe_float(r.get("qty_base", 0))
        precio_in = _safe_float(r.get("precio_unit_aplicado", 0))

        costo_previo = costo_prom

        if qty > 0:
            # Entrada: valorizamos con precio_unit_aplicado
            v = qty * precio_in
            saldo_qty += qty
            saldo_valor += v
        elif qty < 0:
            # Salida: valorizamos con costo_promedio previo
            q_out = abs(qty)
            v = -1 * q_out * costo_previo
            saldo_qty -= q_out
            saldo_valor += v
        else:
            v = 0.0

        # Recalcular costo promedio si hay saldo_qty > 0
        if saldo_qty > 0:
            costo_prom = saldo_valor / saldo_qty
        else:
            # Si no hay stock, resetea costos
            costo_prom = 0.0
            saldo_valor = 0.0  # si querés mantener negativo, eliminar esta línea

        # Guardar campos fila
        costo_unit_baja.append(costo_previo if qty < 0 else 0.0)
        valor_mov.append(v)
        saldo_qty_list.append(saldo_qty)
        saldo_valor_list.append(saldo_valor)
        costo_prom_list.append(costo_prom)

    df["costo_unit_aplicado"] = costo_unit_baja
    df["valor_mov"] = valor_mov
    df["saldo_qty"] = saldo_qty_list
    df["saldo_valor"] = saldo_valor_list
    df["costo_promedio"] = costo_prom_list

    return df


# =====================================================================
# UI principal
# =====================================================================

def mostrar_ficha_stock():
    st.subheader("📒 Ficha de stock (Kardex por artículo)")

    col1, col2 = st.columns([2, 1])

    with col1:
        q = st.text_input("Buscar artículo (nombre o código interno):", value="", placeholder="Ej: Roche, Pepito, 12345")

    with col2:
        st.caption("Rango de fechas (opcional)")
        fecha_desde = st.date_input("Desde", value=None)
        fecha_hasta = st.date_input("Hasta", value=None)

    articulos = _fetch_articulos(q, limit=80)

    if not articulos:
        st.info("No hay artículos para mostrar (o no se encontró el texto buscado).")
        return

    # Selector legible
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

    # Resumen final
    stock_final = float(df_k["saldo_qty"].iloc[-1]) if not df_k.empty else 0.0
    valor_final = float(df_k["saldo_valor"].iloc[-1]) if not df_k.empty else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Stock actual (saldo)", f"{_fmt_num(stock_final, 2)}")
    c2.metric("Valor del stock (saldo)", f"$ {_fmt_num(valor_final, 2)}")
    c3.metric("Costo promedio actual", f"$ {_fmt_num(float(df_k['costo_promedio'].iloc[-1]), 4)}")

    # Tabla (una sola, con todo)
    cols_show = [
        "fecha_hora",
        "tipo_mov",
        "deposito_id", "deposito_origen_id", "deposito_destino_id",
        "lote", "vencimiento",
        "qty_in", "qty_out", "qty_base",
        "precio_unit_aplicado", "costo_unit_aplicado",
        "valor_mov",
        "saldo_qty", "saldo_valor",
        "ref_tipo", "ref_nro",
        "proveedor", "proveedor_id",
        "usuario", "observacion",
    ]
    cols_show = [c for c in cols_show if c in df_k.columns]

    st.dataframe(
        df_k[cols_show],
        use_container_width=True,
        hide_index=True
    )

    # Descarga
    csv = df_k[cols_show].to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Descargar ficha (CSV)",
        data=csv,
        file_name=f"ficha_stock_articulo_{articulo_id}.csv",
        mime="text/csv"
    )
