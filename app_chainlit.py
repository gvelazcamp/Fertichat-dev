# ====================================
# app_chainlit.py
# ====================================

import io
import os
import pandas as pd
import chainlit as cl

# ------------------------------------
# DEBUG BÁSICO DE ENTORNO (Render)
# ------------------------------------
print("🔧 DB_HOST:", os.getenv("DB_HOST"))
print("🔧 SUPABASE_URL:", os.getenv("SUPABASE_URL"))
print("🔧 OPENAI_API_KEY existe:", bool(os.getenv("OPENAI_API_KEY")))

# ------------------------------------
# IMPORT DEL ORQUESTADOR (PROTEGIDO)
# ------------------------------------
try:
    from orquestador import procesar_pregunta_router
    print("✅ Orquestador importado correctamente")
except Exception as e:
    print("❌ ERROR importando orquestador:", e)
    procesar_pregunta_router = None


# ------------------------------------
# MENSAJE INICIAL (EVITA PANTALLA NEGRA)
# ------------------------------------
@cl.on_chat_start
async def start():
    await cl.Message(
        content="🟢 **Fertichat activo**\n\nEscribí una consulta, por ejemplo:\n`compras roche noviembre 2025`"
    ).send()


# ------------------------------------
# NORMALIZADOR DE SALIDA (NO TOCA TU LÓGICA)
# ------------------------------------
def _normalizar_salida(res):
    """
    Soporta retornos comunes sin tocar tu lógica:
    - (respuesta, df)
    - {"respuesta": "...", "df": df}
    - "respuesta"
    """
    if isinstance(res, (tuple, list)) and len(res) >= 2:
        return res[0], res[1]

    if isinstance(res, dict):
        return (
            res.get("respuesta")
            or res.get("respuesta_texto")
            or "",
            res.get("df"),
        )

    return str(res or ""), None


# ------------------------------------
# HANDLER PRINCIPAL
# ------------------------------------
@cl.on_message
async def main(message: cl.Message):
    pregunta = (message.content or "").strip()
    if not pregunta:
        return

    # Si el orquestador no cargó, avisamos claro
    if procesar_pregunta_router is None:
        await cl.Message(
            content="❌ Error interno: el orquestador no pudo cargarse. Revisá los logs."
        ).send()
        return

    try:
        res = procesar_pregunta_router(pregunta)
        respuesta, df = _normalizar_salida(res)

        elements = []

        # --------------------------------
        # TABLA + EXCEL DESCARGABLE
        # --------------------------------
        if isinstance(df, pd.DataFrame) and not df.empty:
            elements.append(
                cl.Dataframe(
                    data=df,
                    display="inline",
                    name="Resultado",
                )
            )

            buf = io.BytesIO()
            df.to_excel(buf, index=False)
            elements.append(
                cl.File(
                    name="resultado.xlsx",
                    content=buf.getvalue(),
                    display="inline",
                )
            )

        await cl.Message(
            content=respuesta or "(sin texto)",
            elements=elements,
        ).send()

    except Exception as e:
        await cl.Message(
            content=f"❌ Error: {type(e).__name__}: {e}"
        ).send()
