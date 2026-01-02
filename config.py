# =========================
# CONFIG.PY - CONFIGURACIÓN Y CONSTANTES
# =========================

import os

# =========================
# CONFIGURACIÓN DEBUG
# =========================
DEBUG_MODE = False  # Cambiar a True para ver debug

# =========================
# CONFIGURACIÓN OPENAI
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o-mini"

# =========================
# OPCIONES DE MENÚ
# =========================
MENU_OPTIONS = [
    "🏠 Inicio",
    "🛒 Compras IA",
    "🔎 Buscador IA",
    "📦 Stock IA",
    "📊 Dashboard",
    "📄 Pedidos internos",
    "🧾 Baja de stock",
    "📈 Indicadores (Power BI)",
    "📦 Órdenes de compra",
    "📚 Artículos",
    "📒 Ficha de stock",
    "🏬 Depósitos":,
    "🧩 Familias":,
]

# Power BI URL
POWERBI_URL = "https://app.powerbi.com/view?r=eyJrIjoiMTBhMGY0ZjktYmM1YS00OTM4LTg3ZjItMTEzYWVmZWNkMGIyIiwidCI6ImQxMzBmYmU3LTFiZjAtNDczNi1hM2Q5LTQ1YjBmYWUwMDVmYSIsImMiOjR9"
