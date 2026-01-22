# Archivo: ia_router.py (actualizado con el bloque duro al inicio)

def interpretar_pregunta(pregunta: str) -> Dict[str, Any]:
    """
    Interpretador principal (router): decide intención y extrae parámetros.
    BLOQUE DURO: compras solo por año tiene prioridad absoluta.
    """
    if not pregunta or not str(pregunta).strip():
        return {"tipo": "no_entendido", "parametros": {}, "debug": "pregunta vacía"}

    texto_original = str(pregunta).strip()
    texto_lower_original = texto_original.lower()

    texto_norm = normalizar_texto(texto_original)

    # ==================================================
    # 🔒 BLOQUE DURO – COMPRAS SOLO POR AÑO
    # PRIORIDAD ABSOLUTA – ANTES DE TODO
    # ==================================================
    import re

    m = re.search(r"\b(compra|compras)\s+(\d{4})\b", texto_lower_original)
    if m:
        anio = int(m.group(2))

        return {
            "tipo": "compras_anio",
            "parametros": {
                "anio": anio
            },
            "debug": "HARD BLOCK → compras solo por año"
        }

    # SALUDOS (continúa con el resto de la lógica)
    if es_saludo(texto_lower_original):
        usuario = st.session_state.get("nombre", "👋")

        return {
            "tipo": "saludo",
            "mensaje": (
                f"Hola **{usuario}** 👋\n\n"
                "¿En qué puedo ayudarte hoy?\n\n"
                "Puedo ayudarte con:\n"
                "• 🛒 **Compras**\n"
                "• 📦 **Stock**\n"
                "• 📊 **Comparativas**\n"
                "• 🧪 **Artículos**\n\n"
                "Escribí lo que necesites 👇"
            )
        }

    # CONOCIMIENTO (preguntas qué es, etc.)
    palabras_conocimiento = ["qué es", "que es", "qué significa", "que significa", 
                             "explica", "explicame", "explícame", "define", 
                             "dime sobre", "qué son", "que son", "cuál es", "cual es",
                             "para qué sirve", "para que sirve", "cómo funciona", "como funciona"]
    
    if any(palabra in texto_lower_original for palabra in palabras_conocimiento):
        return {
            "tipo": "conocimiento",
            "parametros": {},
            "debug": f"pregunta de conocimiento: {texto_original}"
        }

    # FAST-PATH: listado facturas por año
    if re.search(r"\b(listado|lista)\b", texto_lower_original) and re.search(r"\bfacturas?\b", texto_lower_original):
        anios_listado = _extraer_anios(texto_lower_original)
        if anios_listado:
            anio = anios_listado[0]
            return {
                "tipo": "listado_facturas_anio",
                "parametros": {"anio": anio},
                "debug": f"listado facturas año {anio}",
            }

    # FAST-PATH: detalle factura por número
    if contiene_factura(texto_lower_original):
        nro = _extraer_nro_factura(texto_original)
        if nro:
            return {
                "tipo": "detalle_factura_numero",
                "parametros": {"nro_factura": nro},
                "debug": f"factura nro={nro}",
            }

    # FAST-PATH: total facturas por moneda año
    if re.search(r"\b(total|totales)\b", texto_lower_original) and re.search(r"\b(2023|2024|2025|2026)\b", texto_lower_original):
        anios_total = _extraer_anios(texto_lower_original)
        if anios_total:
            anio = anios_total[0]
            return {
                "tipo": "total_facturas_por_moneda_anio",
                "parametros": {"anio": anio},
                "debug": f"total facturas por moneda año {anio}",
            }

    # FAST-PATH: total facturas por moneda generico (sin año)
    if re.search(r"\b(total|totales)\b", texto_lower_original) and re.search(r"\bfacturas?\b", texto_lower_original) and re.search(r"\bmoneda\b", texto_lower_original) and not re.search(r"\d{4}", texto_lower_original):
        return {
            "tipo": "total_facturas_por_moneda_generico",
            "parametros": {},
            "debug": "total facturas por moneda generico",
        }

    # FAST-PATH: total compras por moneda generico (sin año)
    if re.search(r"\b(total|totales)\b", texto_lower_original) and re.search(r"\bcompras?\b", texto_lower_original) and re.search(r"\bmoneda\b", texto_lower_original) and not re.search(r"\d{4}", texto_lower_original):
        return {
            "tipo": "total_compras_por_moneda_generico",
            "parametros": {},
            "debug": "total compras por moneda generico",
        }

    texto_limpio = limpiar_consulta(texto_original)
    texto_lower = texto_limpio.lower()

    idx_prov, idx_art = _get_indices()
    provs = _match_best(texto_lower, idx_prov, max_items=MAX_PROVEEDORES)
    arts = _match_best(texto_lower, idx_art, max_items=MAX_ARTICULOS)

    if not provs:
        prov_libre = _extraer_proveedor_libre(texto_lower_original)
        if prov_libre:
            provs = [_alias_proveedor(prov_libre)]

    tokens = _tokens(texto_lower_original)

    # EXTRACCIÓN BASE (OBLIGATORIA ANTES DE LOS IF)
    anios = _extraer_anios(texto_lower)
    meses_nombre = _extraer_meses_nombre(texto_lower)
    meses_yyyymm = _extraer_meses_yyyymm(texto_lower)

    # Fallback de artículo
    if not arts:
        listas = _cargar_listas_supabase()
        articulos_db = listas.get("articulos", [])
        tokens_restantes = [t for t in tokens if t not in provs]
        articulo = detectar_articulo_valido(tokens_restantes, articulos_db)
        if articulo:
            arts = [articulo]

    # RUTA ARTÍCULOS (CANÓNICA)
    if (
        contiene_compras(texto_lower_original)
        and not provs
        and not anios
    ):
        from ia_interpretador_articulos import interpretar_articulo
        meses = meses_nombre + meses_yyyymm
        return interpretar_articulo(texto_original, [], meses)

    # COMPRAS POR PROVEEDOR / ARTÍCULO + AÑO
    if provs and anios:
        tipo = "facturas_proveedor"

    elif arts and anios:
        return {
            "tipo": "compras_articulo_anio",
            "parametros": {
                "articulo": arts[0],
                "anios": anios
            },
            "debug": "compras articulo + año"
        }

    # FACTURAS PROVEEDOR (LISTADO)
    dispara_facturas_listado = False

    if contiene_factura(texto_lower_original) and (_extraer_nro_factura(texto_original) is None):
        dispara_facturas_listado = True

    if (
        re.search(r"\b(todas|todoas)\b", texto_lower_original)
        and re.search(r"\b(compras?|facturas?|comprobantes?)\b", texto_lower_original)
        and (_extraer_nro_factura(texto_original) is None)
    ):
        dispara_facturas_listado = True

    if (
        (not contiene_comparar(texto_lower_original))
        and provs
        and contiene_gastos_o_documentos(texto_lower_original)
        and (_extraer_nro_factura(texto_original) is None)
    ):
        dispara_facturas_listado = True

    if dispara_facturas_listado:
        proveedores_lista: List[str] = []
        if provs:
            proveedores_lista = [provs[0]]
        else:
            prov_libre = _extraer_proveedor_libre(texto_lower_original)
            if prov_libre:
                proveedores_lista = [_alias_proveedor(prov_libre)]

        if not proveedores_lista:
            return {
                "tipo": "no_entendido",
                "parametros": {},
                "sugerencia": "Indicá el proveedor. Ej: todas las facturas de Roche noviembre 2025.",
                "debug": "facturas_proveedor: no encontró proveedor (ni en BD ni libre)",
            }

        desde, hasta = _extraer_rango_fechas(texto_original)

        meses_out: List[str] = []
        if meses_yyyymm:
            meses_out = meses_yyyymm[:MAX_MESES]
        else:
            if meses_nombre and anios:
                for a in anios:
                    for mn in meses_nombre:
                        meses_out.append(_to_yyyymm(a, mn))
                        if len(meses_out) >= MAX_MESES:
                            break
                    if len(meses_out) >= MAX_MESES:
                        break

        moneda = _extraer_moneda(texto_lower_original)

        articulo = None
        if re.search(r"\b(articulo|artículo|producto)\b", texto_lower_original):
            articulo = arts[0] if arts else None

        limite = _extraer_limite(texto_lower_original)

        return {
            "tipo": "facturas_proveedor",
            "parametros": {
                "proveedores": proveedores_lista,
                "meses": meses_out or None,
                "anios": anios or None,
                "desde": desde,
                "hasta": hasta,
                "articulo": articulo,
                "moneda": moneda,
                "limite": limite,
            },
            "debug": f"facturas/compras proveedor(es): {', '.join(proveedores_lista)} | meses: {meses_out} | años: {anios}",
        }

    # COMPRAS (fusionado con facturas_proveedor)
    if contiene_compras(texto_lower_original) and not contiene_comparar(texto_lower_original):

        # EXTRAER PROVEEDORES CON COMA (MÚLTIPLES)
        proveedores_multiples: List[str] = []
        parts = texto_lower_original.split()

        if "compras" in parts or "compra" in parts:
            idx = parts.index("compras") if "compras" in parts else parts.index("compra")
            after_compras = parts[idx + 1:]

            # Encontrar el primer mes o año para detener
            first_stop = None
            for i, p in enumerate(after_compras):
                clean_p = re.sub(r"[^\w]", "", p)
                if clean_p in MESES or (clean_p.isdigit() and int(clean_p) in ANIOS_VALIDOS):
                    first_stop = i
                    break

            if first_stop is not None:
                proveedores_texto = " ".join(after_compras[:first_stop])
            else:
                proveedores_texto = " ".join(after_compras)

            if "," in proveedores_texto:
                proveedores_multiples = [
                    _alias_proveedor(p.strip())
                    for p in proveedores_texto.split(",")
                    if p.strip()
                ]
            elif proveedores_texto:
                proveedores_multiples = [_alias_proveedor(proveedores_texto)]

        if proveedores_multiples:
            provs = proveedores_multiples

        # COMPRAS POR ARTÍCULO + AÑO
        if arts and anios and not provs:
            return {
                "tipo": "compras_articulo_anio",
                "parametros": {
                    "articulo": arts[0],
                    "anios": anios
                },
                "debug": "compras por articulo y año",
            }

        # PRIORIZAR MES SOBRE AÑO
        if provs and (meses_yyyymm or (meses_nombre and anios)):
            if len(provs) > 1:
                # MÚLTIPLES PROVEEDORES + MES/AÑO
                meses_out = []
                if meses_yyyymm:
                    meses_out = meses_yyyymm
                elif meses_nombre and anios:
                    for a in anios[:1]:  # Solo el primer año
                        for mn in meses_nombre[:MAX_MESES]:
                            meses_out.append(_to_yyyymm(a, mn))
                            if len(meses_out) >= MAX_MESES:
                                break
                        if len(meses_out) >= MAX_MESES:
                            break

                return {
                    "tipo": "compras_multiples",
                    "parametros": {
                        "proveedores": provs,
                        "meses": meses_out,
                        "anios": anios,
                    },
                    "debug": "compras múltiples proveedores mes/año",
                }

            # UN SOLO PROVEEDOR
            proveedor = _alias_proveedor(provs[0])
            if meses_yyyymm:
                mes = meses_yyyymm[0]
            else:
                mes = _to_yyyymm(anios[0], meses_nombre[0]) if anios and meses_nombre else None

            if mes:
                return {
                    "tipo": "compras_proveedor_mes",
                    "parametros": {"proveedor": proveedor, "mes": mes},
                    "debug": "compras proveedor mes",
                }

        if provs and anios:
            if len(provs) > 1:
                # MÚLTIPLES PROVEEDORES + AÑO
                return {
                    "tipo": "compras_multiples",
                    "parametros": {
                        "proveedores": provs,
                        "meses": None,
                        "anios": anios,
                    },
                    "debug": "compras múltiples proveedores año",
                }

            # UN SOLO PROVEEDOR
            proveedor = _alias_proveedor(provs[0])
            return {
                "tipo": "facturas_proveedor",
                "parametros": {
                    "proveedores": [proveedor],
                    "anios": anios,  # PASAR TODOS LOS AÑOS
                    "limite": 5000,
                },
                "debug": "compras proveedor años (fusionado con facturas_proveedor)",
            }

        if meses_yyyymm:
            mes0 = meses_yyyymm[0]
            return {"tipo": "compras_mes", "parametros": {"mes": mes0}, "debug": "compras mes (yyyymm)"}
        if meses_nombre and anios:
            mes = _to_yyyymm(anios[0], meses_nombre[0])
            return {"tipo": "compras_mes", "parametros": {"mes": mes}, "debug": "compras mes (nombre+año)"}

        if anios:
            from ia_compras import interpretar_compras
            resultado = interpretar_compras(texto_original, anios)
            return resultado

    # COMPARAR
    if contiene_comparar(texto_lower_original):
        # EXTRAER MÚLTIPLES PROVEEDORES CON COMA
        proveedores_comparar: List[str] = []
        if "," in texto_lower_original:
            parts = texto_lower_original.split()
            for i, p in enumerate(parts):
                if "," in p or (i > 0 and parts[i-1].endswith(",")):
                    clean = re.sub(r"[^\w]", "", p)
                    if clean and clean not in MESES and clean not in ["comparar", "compara", "comparame"]:
                        match_prov = _match_best(clean, idx_prov, max_items=1)
                        if match_prov:
                            proveedores_comparar.append(_alias_proveedor(match_prov[0]))
        
        if not proveedores_comparar:
            proveedores_comparar = [_alias_proveedor(p) for p in provs] if provs else []
        
        # EXTRAER MESES PARA COMPARAR
        meses_cmp: List[str] = []
        if meses_yyyymm:
            meses_cmp = meses_yyyymm[:2]
        elif meses_nombre and anios:
            for mn in meses_nombre[:2]:
                meses_cmp.append(_to_yyyymm(anios[0], mn))
        
        # COMPARAR MESES
        if len(meses_cmp) == 2:
            if len(proveedores_comparar) >= 2:
                return {
                    "tipo": "comparar_proveedores_meses",
                    "parametros": {
                        "proveedores": proveedores_comparar[:MAX_PROVEEDORES],
                        "mes1": meses_cmp[0],
                        "mes2": meses_cmp[1],
                        "label1": meses_cmp[0],
                        "label2": meses_cmp[1],
                    },
                    "debug": f"comparar {len(proveedores_comparar)} proveedores meses",
                }
            elif len(proveedores_comparar) == 1:
                return {
                    "tipo": "comparar_proveedor_meses",
                    "parametros": {
                        "proveedor": proveedores_comparar[0],
                        "mes1": meses_cmp[0],
                        "mes2": meses_cmp[1],
                        "label1": meses_cmp[0],
                        "label2": meses_cmp[1],
                    },
                    "debug": "comparar proveedor meses",
                }
            else:
                return {
                    "tipo": "comparar_proveedores_meses_multi",
                    "parametros": {
                        "proveedores": [],  # Vacío = todos
                        "meses": meses_cmp,
                    },
                    "debug": "comparar todos los proveedores meses",
                }
        
        # COMPARAR AÑOS
        if len(anios) >= 2:
            if len(proveedores_comparar) >= 2:
                return {
                    "tipo": "comparar_proveedores_anios",
                    "parametros": {
                        "proveedores": proveedores_comparar[:MAX_PROVEEDORES],
                        "anios": anios[:2],
                        "label1": str(anios[0]),
                        "label2": str(anios[1]),
                    },
                    "debug": f"comparar {len(proveedores_comparar)} proveedores años",
                }
            elif len(proveedores_comparar) == 1:
                return {
                    "tipo": "comparar_proveedor_anios",
                    "parametros": {
                        "proveedor": proveedores_comparar[0],
                        "anios": anios[:2],
                        "label1": str(anios[0]),
                        "label2": str(anios[1]),
                    },
                    "debug": "comparar proveedor años",
                }
            else:
                return {
                    "tipo": "comparar_proveedores_anios_multi",
                    "parametros": {
                        "proveedores": [],  # Vacío = todos
                        "anios": anios[:2],
                    },
                    "debug": "comparar todos los proveedores años",
                }
        
        return {
            "tipo": "no_entendido",
            "parametros": {},
            "sugerencia": "Ej: comparar compras roche junio julio 2025 | comparar compras roche 2024 2025 | comparar 2024 2025",
            "debug": "comparar: faltan 2 meses o 2 años",
        }

    # STOCK
    if "stock" in texto_lower_original:
        if arts:
            return {"tipo": "stock_articulo", "parametros": {"articulo": arts[0]}, "debug": "stock articulo"}
        return {"tipo": "stock_total", "parametros": {}, "debug": "stock total"}

    # TOP PROVEEDORES POR AÑO/MES
    if (
        any(k in texto_lower_original for k in ["top", "ranking", "principales"])
        and "proveedor" in texto_lower_original
        and anios
    ):
        top_n = 10
        match = re.search(r'top\s+(\d+)', texto_lower_original)
        if match:
            top_n = int(match.group(1))

        moneda_extraida = _extraer_moneda(texto_lower_original)
        if moneda_extraida and moneda_extraida.upper() in ("USD", "U$S", "U$$", "US$"):
            moneda_param = "U$S"
        else:
            moneda_param = "$"

        meses_param = None
        if meses_yyyymm:
            meses_param = meses_yyyymm
        elif meses_nombre:
            meses_param = [_to_yyyymm(anios[0], mn) for mn in meses_nombre]

        return {
            "tipo": "dashboard_top_proveedores",
            "parametros": {
                "anio": anios[0],
                "meses": meses_param,
                "top_n": top_n,
                "moneda": moneda_param,
            },
            "debug": f"top proveedores año {anios[0]} {'mes ' + str(meses_param) if meses_param else ''} en {moneda_param}",
        }

    out_ai = _interpretar_con_openai(texto_original)
    if out_ai:
        return out_ai

    return {
        "tipo": "no_entendido",
        "parametros": {},
        "sugerencia": "Probá: compras roche noviembre 2025 | comparar compras roche junio julio 2025 | detalle factura 273279 | todas las facturas roche 2025 | listado facturas 2025 | total 2025 | total facturas por moneda | total compras por moneda | comparar 2024 2025",
        "debug": "no match",
    }
