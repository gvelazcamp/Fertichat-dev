# app_chainlit.py
import io
import pandas as pd
import chainlit as cl

# AJUSTÁ SOLO ESTA LÍNEA si tu orquestador está en otro archivo
from orquestador import procesar_pregunta_router


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
        return res.get("respuesta") or res.get("respuesta_texto") or "", res.get("df")
    return str(res or ""), None


@cl.on_message
async def main(message: cl.Message):
    pregunta = (message.content or "").strip()
    if not pregunta:
        return

    try:
        res = procesar_pregunta_router(pregunta)
        respuesta, df = _normalizar_salida(res)

        elements = []

        if isinstance(df, pd.DataFrame) and not df.empty:
            elements.append(cl.Dataframe(data=df, display="inline", name="Resultado"))

            # Excel descargable
            buf = io.BytesIO()
            df.to_excel(buf, index=False)
            elements.append(cl.File(name="resultado.xlsx", content=buf.getvalue(), display="inline"))

        await cl.Message(content=respuesta or "(sin texto)", elements=elements).send()

    except Exception as e:
        await cl.Message(content=f"Error: {type(e).__name__}: {e}").send()

