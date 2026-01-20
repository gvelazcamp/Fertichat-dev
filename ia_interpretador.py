CAMBIO EXACTO QUE TENÉS QUE HACER
📍 Archivo

ia_interpretador.py

📍 Dentro de interpretar_pregunta(...)

Buscá el bloque donde decidís proveedor / facturas_proveedor
(es algo parecido a esto):

if proveedores:
    return {
        "tipo": "facturas_proveedor",
        ...
    }

🔴 ANTES DE ESO, agregá ESTE BLOQUE (tal cual)
# ==================================================
# COMPRAS POR ARTÍCULO + AÑO (PRIORIDAD ALTA)
# ==================================================
if articulos and anios:
    return {
        "tipo": "compras_articulo_anio",
        "parametros": {
            "articulo": articulos[0],
            "anio": anios[0],
            "limite": 5000
        },
        "debug": "compras articulo año"
    }


⚠️ Tiene que ir ANTES de cualquier if proveedores:

🧠 POR QUÉ ESTO FUNCIONA

articulos viene de _match_best() → ya detecta “VITEK”

anios viene bien (2024 / 2025)

Si hay artículo + año, eso manda

El proveedor queda como fallback, no como default
