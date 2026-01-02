# =========================
# UTILS_FORMAT.PY - FORMATEO DE DATOS
# =========================

import pandas as pd
from typing import Optional
import io
import re

# Importar normalizar_texto del intent_detector original
from intent_detector import normalizar_texto

# =====================================================================
# FORMATEO DE NÚMEROS (LATAM)
# =====================================================================

def _fmt_num_latam(valor, decimales: int = 2) -> str:
    """Convierte números a formato LATAM (1.568.687,40)"""
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    prefijo = ""
    if isinstance(valor, str):
        v0 = valor.strip()
        if "U$S" in v0:
            prefijo = "U$S "
        elif "$" in v0:
            prefijo = "$ "

        s = v0.replace("U$S", "").replace("$", "").strip()
        s = s.replace("(", "-").replace(")", "").replace(" ", "")

        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        else:
            if "," in s and "." not in s:
                s = s.replace(".", "").replace(",", ".")

        try:
            num = float(s)
        except Exception:
            return str(valor).strip()
    else:
        try:
            num = float(valor)
        except Exception:
            return str(valor)

    base = f"{num:,.{decimales}f}"
    latam = base.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{prefijo}{latam}".strip()


def _es_col_importe_latam(nombre_col: str) -> bool:
    """Detecta si una columna es un importe"""
    n = normalizar_texto(nombre_col or "")

    if "cantidad" in n:
        return False
    if ("factura" in n) and ("total" not in n) and ("importe" not in n) and ("monto" not in n):
        return False

    if any(k in n for k in ["total", "monto", "importe", "diferencia", "comparacion"]):
        return True
    if n.endswith("_$") or n.endswith("_usd"):
        return True

    return False


def formatear_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Formatea DataFrame con números en formato LATAM"""
    if df is None or df.empty:
        return df

    d = df.copy()
    for c in d.columns:
        if _es_col_importe_latam(c):
            d[c] = d[c].apply(_fmt_num_latam)
        elif "variacion" in normalizar_texto(c) or "%" in c:
            d[c] = d[c].apply(lambda x: (f"{float(x):.2f}%" if pd.notna(x) else ""))
    return d


# =====================================================================
# HELPER PARA EXPORTAR A EXCEL
# =====================================================================

def df_to_excel(df: pd.DataFrame) -> bytes:
    """Convierte un DataFrame a bytes de Excel (.xlsx)"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    output.seek(0)
    return output.getvalue()


# =====================================================================
# HELPERS ADICIONALES
# =====================================================================

def _norm_colname(x: str) -> str:
    try:
        return normalizar_texto(str(x or ""))
    except Exception:
        return str(x or "").lower().strip()


def _pick_col(df: pd.DataFrame, posibles: list) -> Optional[str]:
    if df is None or df.empty:
        return None
    cols = list(df.columns)
    cols_norm = {_norm_colname(c): c for c in cols}
    for p in posibles:
        pnorm = _norm_colname(p)
        if pnorm in cols_norm:
            return cols_norm[pnorm]
        for cnorm, corig in cols_norm.items():
            if pnorm in cnorm:
                return corig
    return None


def _latam_to_float(valor) -> float:
    """Convierte string LATAM/currency a float (robusto)."""
    if valor is None:
        return 0.0
    try:
        if pd.isna(valor):
            return 0.0
    except Exception:
        pass

    if isinstance(valor, (int, float)):
        try:
            return float(valor)
        except Exception:
            return 0.0

    s = str(valor).strip()
    if not s:
        return 0.0

    s = s.replace("U$S", "").replace("USD", "").replace("$", "").strip()
    s = s.replace("(", "-").replace(")", "")
    s = s.replace(" ", "")

    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        if "," in s and "." not in s:
            s = s.replace(".", "").replace(",", ".")

    try:
        return float(s)
    except Exception:
        return 0.0


def _safe_float(x) -> float:
    try:
        if x is None:
            return 0.0
        return float(x)
    except Exception:
        return 0.0


def _fmt_money_latam(valor: float, moneda: str = "$", dec: int = 2) -> str:
    if moneda and moneda.strip().upper() in ["U$S", "USD", "U$$"]:
        pref = "U$S "
    else:
        pref = "$ "
    return pref + _fmt_num_latam(valor, dec)
