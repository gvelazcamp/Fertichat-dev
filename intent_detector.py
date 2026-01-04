# =========================
# INTENT DETECTOR - DETECCIÓN DE INTENCIONES (CORREGIDO CON STOCK)
# =========================
# CAMBIOS:
# 1. Agregado "comparame", "compara", "comparar" a todas las detecciones
# 2. Agregado "comparame" a las palabras a excluir del proveedor
# 3. Nueva lógica para detectar "comparar mes X año1 año2"
# 4. Mejor orden de prioridades
# 5. ✅ NUEVO: Intenciones de STOCK agregadas
# 6. ✅ CORREGIDO: extraer_meses_para_comparacion ahora detecta año global
# 7. ✅ NUEVO: Comparativas "expertas": múltiples proveedores por coma y meses + múltiples años (ej: "noviembre 2024 2025")

import re
import unicodedata
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta


# =====================================================================
# NORMALIZACIÓN TEXTO
# =====================================================================

def normalizar_texto(texto: str) -> str:
    """Normaliza texto: minúsculas, sin acentos, sin espacios extras"""
    if texto is None:
        return ""
    s = str(texto)
    s = s.lower().strip()
    s = ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )
    s = ' '.join(s.split())
    return s

# =====================================================================
# DETECCIÓN ARTÍCULO vs PROVEEDOR (ARTÍCULO TIENE PRIORIDAD)
# =====================================================================

def detectar_articulo_o_proveedor(patron: str, lista_articulos: list, lista_proveedores: list) -> str | None:
    """
    Regla:
    - Si aparece en ARTICULOS → ARTICULO
    - Si NO aparece en ARTICULOS pero sí en PROVEEDORES → PROVEEDOR
    """

    if not patron:
        return None

    p = normalizar_texto(patron)

    # 1️⃣ ARTÍCULO (PRIORIDAD)
    for a in lista_articulos:
        if p in normalizar_texto(a):
            return "ARTICULO"

    # 2️⃣ PROVEEDOR
    for prov in lista_proveedores:
        if p in normalizar_texto(prov):
            return "PROVEEDOR"

    return None

# =====================================================================
# HELPERS DE EXTRACCIÓN
# =====================================================================

def es_conocimiento_general(pregunta: str) -> bool:
    txt = pregunta.lower().strip()
    patrones = [
        "que es", "qué es", "para que sirve", "para qué sirve",
        "qué significa", "que significa", "explica", "explicame",
    ]
    for p in patrones:
        if txt.startswith(p):
            return True
    return False


def extraer_meses(texto: str):
    """Detecta meses en texto y devuelve lista de mes_key 'YYYY-MM'"""
    if not texto:
        return []

    texto = texto.lower()

    meses = {
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
        "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
        "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
    }

    anio_match = re.search(r"(20\d{2})", texto)
    anio = anio_match.group(1) if anio_match else str(datetime.now().year)

    encontrados = []
    for nombre, num in meses.items():
        if nombre in texto:
            encontrados.append(f"{anio}-{num}")

    return encontrados


def _es_token_mes_o_periodo(tok: str) -> bool:
    """Detecta si un token es un mes o período temporal"""
    t = normalizar_texto(tok or "")

    meses = {
        'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
        'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
    }
    if t in meses:
        return True

    if t in {'este', 'esta', 'mes', 'pasado', 'pasada', 'hoy', 'ayer', 'semana'}:
        return True

    if re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', t):
        return True

    if re.fullmatch(r'20\d{2}', t):
        return True

    return False


def extraer_valores_multiples(texto: str, tipo: str) -> List[str]:
    """Extrae valores múltiples (proveedor/articulo/familia) del texto"""
    texto_norm = normalizar_texto(texto)

    patron = rf'{tipo}(?:es|s)?\s+([a-z0-9,\s\.\-]+?)(?:\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|este|mes|pasado|del|de|en|20\d{{2}}|comparar|gastos|compras|detalle|factura|vs)|$)'
    match = re.search(patron, texto_norm)
    if match:
        valores_str = match.group(1).strip()
        valores = re.split(r'\s*,\s*|\s+y\s+', valores_str)
        valores = [v.strip() for v in valores if v.strip() and len(v.strip()) > 1]
        valores = [v for v in valores if not _es_token_mes_o_periodo(v)]
        return valores

    return []


# =====================================================================
# PALABRAS A EXCLUIR (CENTRALIZADO)
# =====================================================================

PALABRAS_EXCLUIR_PROVEEDOR = [
    # Verbos de comparación
    'comparar', 'comparame', 'compara', 'comparacion', 'comparaciones',
    # Verbos de compras
    'compras', 'compra', 'compre', 'compramos', 'comprado',
    # Verbos de acción
    'traer', 'mostrar', 'ver', 'dame', 'pasame', 'mostrame',
    'necesito', 'quiero', 'buscar', 'busco', 'listar',
    # Artículos y preposiciones
    'de', 'del', 'la', 'el', 'los', 'las', 'en', 'por', 'para',
    'un', 'una', 'unos', 'unas', 'al', 'a', 'con', 'sin',
    # Temporal
    'mes', 'año', 'ano', 'meses', 'años', 'anos',
    # Meses (correctos + typos + abreviaturas)
    'enero', 'ene', 'ener', 'enro',
    'febrero', 'feb', 'febr', 'febrer', 'febreo',
    'marzo', 'mar', 'marz', 'marso',
    'abril', 'abr', 'abri', 'abrl',
    'mayo', 'may', 'mallo',
    'junio', 'jun', 'juni', 'juno',
    'julio', 'jul', 'juli', 'julo',
    'agosto', 'ago', 'agost', 'agoto', 'agsoto',
    'septiembre', 'sep', 'sept', 'set', 'setiembre', 'septirmbre', 'septiembr', 'setiembr',
    'octubre', 'oct', 'octu', 'octub', 'octubr', 'octbre', 'ocutbre',
    'noviembre', 'nov', 'noviem', 'noviemb', 'novimbre', 'novimbr', 'novienbre', 'novmbre',
    'diciembre', 'dic', 'diciem', 'diciemb', 'dicimbre', 'dicimbr', 'dicienbre', 'dicmbre',
    # Años
    '2020', '2021', '2022', '2023', '2024', '2025', '2026', '2027', '2028', '2029', '2030',
    # Otros
    'vs', 'versus', 'contra', 'detalle', 'total', 'gastos', 'gasto',
    'importe', 'importes',  # ✅ NUEVO
    'proveedor', 'proveedores', 'articulo', 'articulos', 'familia', 'familias',
    # Saludos
    'hola', 'buenos', 'buenas', 'dias', 'tardes', 'noches', 'buen', 'dia',
    'gracias', 'porfa', 'por', 'favor',
    # Nombres comunes a ignorar
    'che', 'me', 'podrias', 'podes', 'puedes',
    # ✅ NUEVO: Palabras de stock a excluir
    'stock', 'lote', 'lotes', 'vencimiento', 'vencer', 'deposito', 'depositos',
]

# Palabras que disparan comparación
PALABRAS_COMPARACION = ['comparar', 'comparame', 'compara', 'comparacion', 'comparaciones', 'vs', 'versus']

# ✅ NUEVO: Palabras que disparan consultas de stock
PALABRAS_STOCK = [
    'stock', 'lote', 'lotes', 'vencimiento', 'vencer', 'vencido', 'vencidos',
    'deposito', 'depositos', 'inventario', 'existencia', 'existencias',
    'disponible', 'disponibles', 'cuanto hay', 'cuantos hay', 'tenemos',
    'por vencer', 'proximo a vencer', 'proximos a vencer'
]


def _extraer_patron_libre(texto: str, excluir_palabras: List[str] = None) -> str:
    """Extrae patrón libre eliminando palabras clave"""
    if excluir_palabras is None:
        excluir_palabras = PALABRAS_EXCLUIR_PROVEEDOR
    
    txt = normalizar_texto(texto)
    txt = txt.replace("última", "ultima")
    
    tokens = txt.split()
    resto = []
    
    for t in tokens:
        if t not in excluir_palabras and not re.fullmatch(r'20\d{2}', t):
            resto.append(t)
    
    patron = ' '.join(resto).strip()
    
    # Limpiar puntuación al inicio/fin
    patron = re.sub(r'^[^\w]+|[^\w]+$', '', patron)
    
    return patron


# =====================================================================
# ✅ NUEVO: HELPERS PARA COMPARATIVAS "EXPERTAS" (SIN ROMPER LO EXISTENTE)
# =====================================================================

def _split_lista_libre(valores_str: str) -> List[str]:
    """
    Divide una lista libre tipo:
    - "biodiagnostico, roche"
    - "biodiagnostico y roche"
    - "biodiagnostico e roche"
    """
    if not valores_str:
        return []
    s = normalizar_texto(valores_str)
    partes = re.split(r'\s*,\s*|\s+y\s+|\s+e\s+|\s*&\s*', s)
    out = []
    for p in partes:
        p = p.strip(" .;:|/\\-").strip()
        if not p:
            continue
        if _es_token_mes_o_periodo(p):
            continue
        if p in PALABRAS_EXCLUIR_PROVEEDOR:
            continue
        if len(p) <= 1:
            continue
        out.append(p)
    # dedupe manteniendo orden
    seen = set()
    res = []
    for x in out:
        if x not in seen:
            seen.add(x)
            res.append(x)
    return res


def _extraer_proveedores_multiples_libre(texto: str) -> List[str]:
    """
    Extrae proveedores aunque el usuario NO escriba 'proveedor'.
    Caso típico: "comparar biodiagnostico, roche junio julio 2023 2024"
    """
    patron_raw = _extraer_patron_libre(texto, PALABRAS_EXCLUIR_PROVEEDOR)
    if not patron_raw:
        return []
    return _split_lista_libre(patron_raw)


def _extraer_meses_numeros_en_orden(texto: str) -> List[int]:
    """
    Extrae meses (números) respetando el orden de aparición en el texto.
    Soporta alias (jun/jul/ago, set, etc).
    """
    texto_norm = normalizar_texto(texto)

    meses_map = {
        'enero': 1, 'ene': 1,
        'febrero': 2, 'feb': 2,
        'marzo': 3, 'mar': 3,
        'abril': 4, 'abr': 4,
        'mayo': 5, 'may': 5,
        'junio': 6, 'jun': 6,
        'julio': 7, 'jul': 7,
        'agosto': 8, 'ago': 8,
        'septiembre': 9, 'sep': 9, 'sept': 9, 'set': 9, 'setiembre': 9,
        'octubre': 10, 'oct': 10,
        'noviembre': 11, 'nov': 11,
        'diciembre': 12, 'dic': 12
    }

    ocurrencias: List[Tuple[int, int]] = []
    for alias, num in meses_map.items():
        for m in re.finditer(rf'\b{re.escape(alias)}\b', texto_norm):
            ocurrencias.append((m.start(), num))

    ocurrencias.sort(key=lambda x: x[0])

    meses = []
    seen = set()
    for _, num in ocurrencias:
        if num not in seen:
            seen.add(num)
            meses.append(num)

    return meses


def _generar_periodos_mes_keys(anios: List[int], meses_nums: List[int], anio_default: int) -> List[str]:
    """
    Genera lista de 'YYYY-MM' combinando meses y años.
    - Si anios trae 2+ años y meses trae 1+ meses => combina todos (ej 2024/2025 x noviembre)
    - Si anios vacío => usa anio_default
    """
    if not meses_nums:
        return []

    if not anios:
        anios = [anio_default]

    # dedupe anios conservando orden ascendente por consistencia
    anios = sorted(set(int(a) for a in anios))

    out: List[str] = []
    for a in anios:
        for m in meses_nums:
            out.append(f"{a}-{int(m):02d}")

    # dedupe final por seguridad
    seen = set()
    res = []
    for x in out:
        if x not in seen:
            seen.add(x)
            res.append(x)
    return res


# =====================================================================
# ✅ NUEVO: DETECTOR DE INTENCIÓN DE STOCK
# =====================================================================

def _es_consulta_stock(texto_norm: str) -> bool:
    """Detecta si el texto es una consulta de stock"""
    for palabra in PALABRAS_STOCK:
        if palabra in texto_norm:
            return True
    return False


def _detectar_intencion_stock(texto: str) -> Dict:
    """
    ✅ NUEVO: Detecta la intención específica para consultas de stock
    Retorna: {'tipo': 'stock_xxx', 'parametros': {...}, 'debug': 'info'}
    """
    texto_lower = normalizar_texto(texto)
    
    # Lista de familias comunes (puedes expandir)
    familias_conocidas = ['id', 'fb', 'g', 'hm', 'ur', 'bc', 'ch', 'mi', 'se', 'co']
    
    # =====================================================================
    # LOTES POR VENCER
    # =====================================================================
    if any(k in texto_lower for k in ['por vencer', 'proximo a vencer', 'proximos a vencer', 'vence pronto', 'vencen pronto']):
        # Extraer días si se especifica
        dias = 90  # default
        match_dias = re.search(r'(\d+)\s*dias?', texto_lower)
        if match_dias:
            dias = int(match_dias.group(1))
        return {
            'tipo': 'stock_lotes_por_vencer',
            'parametros': {'dias': dias},
            'debug': f'Stock: lotes por vencer en {dias} días'
        }
    
    # =====================================================================
    # LOTES VENCIDOS
    # =====================================================================
    if any(k in texto_lower for k in ['vencido', 'vencidos', 'ya vencio', 'ya vencieron']):
        return {
            'tipo': 'stock_lotes_vencidos',
            'parametros': {},
            'debug': 'Stock: lotes vencidos'
        }
    
    # =====================================================================
    # STOCK BAJO
    # =====================================================================
    if any(k in texto_lower for k in ['stock bajo', 'poco stock', 'bajo stock', 'quedan pocos', 'se acaba', 'reponer', 'agotando']):
        return {
            'tipo': 'stock_bajo',
            'parametros': {},
            'debug': 'Stock: stock bajo'
        }
    
    # =====================================================================
    # BUSCAR LOTE ESPECÍFICO
    # =====================================================================
    match_lote = re.search(r'lote\s+([A-Za-z0-9\-]+)', texto_lower)
    if match_lote:
        lote = match_lote.group(1).upper()
        return {
            'tipo': 'stock_lote_especifico',
            'parametros': {'lote': lote},
            'debug': f'Stock: buscar lote {lote}'
        }
    
    # =====================================================================
    # STOCK POR FAMILIA / SECCIÓN
    # =====================================================================
    if any(k in texto_lower for k in ['familia', 'familias', 'seccion', 'secciones', 'por familia', 'por seccion']):
        # Buscar si hay familia específica
        for fam in familias_conocidas:
            if fam in texto_lower.split():
                return {
                    'tipo': 'stock_familia',
                    'parametros': {'familia': fam.upper()},
                    'debug': f'Stock: familia {fam.upper()}'
                }
        return {
            'tipo': 'stock_por_familia',
            'parametros': {},
            'debug': 'Stock: resumen por familias'
        }
    
    # =====================================================================
    # STOCK POR DEPÓSITO
    # =====================================================================
    if any(k in texto_lower for k in ['deposito', 'depositos', 'por deposito', 'ubicacion', 'almacen']):
        return {
            'tipo': 'stock_por_deposito',
            'parametros': {},
            'debug': 'Stock: resumen por depósito'
        }
    
    # =====================================================================
    # STOCK DE ARTÍCULO ESPECÍFICO
    # =====================================================================
    if any(k in texto_lower for k in ['stock', 'cuanto hay', 'cuantos hay', 'tenemos', 'disponible', 'hay']):
        # Extraer artículo (todo lo que no sea palabra clave)
        palabras_excluir = ['stock', 'cuanto', 'cuantos', 'hay', 'de', 'del', 'tenemos', 'disponible', 
                           'el', 'la', 'los', 'las', 'que', 'en', 'total', 'resumen']
        tokens = texto_lower.split()
        articulo_tokens = [t for t in tokens if t not in palabras_excluir]
        articulo = ' '.join(articulo_tokens).strip()
        
        if articulo and len(articulo) > 1:
            return {
                'tipo': 'stock_articulo',
                'parametros': {'articulo': articulo},
                'debug': f'Stock: artículo {articulo}'
            }
    
    # =====================================================================
    # STOCK TOTAL (fallback)
    # =====================================================================
    if any(k in texto_lower for k in ['stock total', 'todo el stock', 'resumen stock', 'stock general', 'inventario total']):
        return {
            'tipo': 'stock_total',
            'parametros': {},
            'debug': 'Stock: resumen total'
        }
    
    # =====================================================================
    # BÚSQUEDA GENERAL DE STOCK
    # =====================================================================
    # Si llegó acá y tiene palabra de stock, buscar como artículo
    articulo = _extraer_patron_libre(texto, PALABRAS_EXCLUIR_PROVEEDOR)
    if articulo:
        return {
            'tipo': 'stock_articulo',
            'parametros': {'articulo': articulo},
            'debug': f'Stock: búsqueda general {articulo}'
        }
    
    # Fallback: stock total
    return {
        'tipo': 'stock_total',
        'parametros': {},
        'debug': 'Stock: total (fallback)'
    }


# =====================================================================
# HELPERS ADICIONALES (del archivo original)
# =====================================================================

def _extraer_nro_factura(texto: str) -> str:
    """Extrae número de factura del texto"""
    texto_norm = normalizar_texto(texto)
    
    # Patrones de número de factura
    patrones = [
        r'(?:factura|nro|numero|n°|#)\s*[:\s]*([A-Za-z]?\s*\d{5,8})',
        r'\b([A-Za-z]\s*\d{7,8})\b',
        r'\b(\d{5,8})\b'
    ]
    
    for patron in patrones:
        match = re.search(patron, texto_norm)
        if match:
            return match.group(1).replace(' ', '').upper()
    
    return ""


def extraer_anios(texto: str) -> List[int]:
    """Extrae años del texto"""
    anios = re.findall(r'\b(20\d{2})\b', texto)
    return sorted(set(int(a) for a in anios))


def _extraer_mes_key(texto: str) -> Optional[str]:
    """Extrae mes_key en formato YYYY-MM"""
    texto_norm = normalizar_texto(texto)
    
    meses_map = {
        'enero': 1, 'ene': 1,
        'febrero': 2, 'feb': 2,
        'marzo': 3, 'mar': 3,
        'abril': 4, 'abr': 4,
        'mayo': 5, 'may': 5,
        'junio': 6, 'jun': 6,
        'julio': 7, 'jul': 7,
        'agosto': 8, 'ago': 8,
        'septiembre': 9, 'sep': 9, 'sept': 9, 'set': 9,
        'octubre': 10, 'oct': 10,
        'noviembre': 11, 'nov': 11,
        'diciembre': 12, 'dic': 12
    }
    
    anio = None
    mes = None
    
    # Buscar año
    match_anio = re.search(r'\b(20\d{2})\b', texto_norm)
    if match_anio:
        anio = int(match_anio.group(1))
    
    # Buscar mes
    for mes_nombre, mes_num in meses_map.items():
        if mes_nombre in texto_norm:
            mes = mes_num
            break
    
    if mes:
        if not anio:
            anio = datetime.now().year
        return f"{anio}-{mes:02d}"
    
    return None


def extraer_meses_para_comparacion(texto: str) -> List[Tuple[int, int, str]]:
    """
    Extrae meses con su año para comparaciones.
    Retorna lista de tuplas (año, mes_numero, mes_key)
    
    ✅ CORREGIDO: Ahora detecta el año global del texto y lo aplica a todos los meses
    Ejemplo: "comparar roche junio julio 2025" → [(2025, 6, "2025-06"), (2025, 7, "2025-07")]
    """
    texto_norm = normalizar_texto(texto)
    hoy = datetime.now()
    
    meses_map = {
        'enero': 1, 'ene': 1,
        'febrero': 2, 'feb': 2,
        'marzo': 3, 'mar': 3,
        'abril': 4, 'abr': 4,
        'mayo': 5, 'may': 5,
        'junio': 6, 'jun': 6,
        'julio': 7, 'jul': 7,
        'agosto': 8, 'ago': 8,
        'septiembre': 9, 'sep': 9, 'sept': 9, 'set': 9,
        'octubre': 10, 'oct': 10,
        'noviembre': 11, 'nov': 11,
        'diciembre': 12, 'dic': 12
    }
    
    # 1️⃣ PRIMERO: Extraer el año global del texto (si existe)
    anio_global = None
    match_anio = re.search(r'\b(20\d{2})\b', texto_norm)
    if match_anio:
        anio_global = int(match_anio.group(1))
    
    resultados = []
    meses_encontrados = set()  # Para evitar duplicados
    
    # 2️⃣ Buscar cada mes en el texto
    for mes_nombre, mes_num in meses_map.items():
        if mes_nombre in texto_norm:
            # Evitar duplicados (ej: "junio" y "jun" son el mismo mes)
            if mes_num not in meses_encontrados:
                meses_encontrados.add(mes_num)
                
                # Buscar si este mes tiene año específico inmediatamente después
                patron_con_anio = rf'{mes_nombre}\s*(?:de\s*)?(20\d{{2}})'
                match_especifico = re.search(patron_con_anio, texto_norm)
                
                if match_especifico:
                    anio = int(match_especifico.group(1))
                elif anio_global:
                    anio = anio_global
                else:
                    anio = hoy.year
                
                mes_key = f"{anio}-{mes_num:02d}"
                resultados.append((anio, mes_num, mes_key))
    
    # 3️⃣ Ordenar por mes para consistencia
    resultados.sort(key=lambda x: (x[0], x[1]))
    
    return resultados


def _extraer_lista_familias(texto: str) -> List[str]:
    """Extrae lista de familias (1-6 chars, ej: G, FB, ID)"""
    raw = str(texto).strip()
    txt = normalizar_texto(raw)

    m = re.search(r'(secciones|seccion|familias|familia)\s+(.+)$', txt)
    if not m:
        return []

    tail = m.group(2)
    tail = re.split(r'\b(20\d{2}-(0[1-9]|1[0-2]))\b', tail)[0]
    meses_nombres = "(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)"
    tail = re.split(meses_nombres, tail)[0]

    tokens = re.split(r'[\s,]+', tail)
    out = []
    for t in tokens:
        t = t.strip()
        if not t or _es_token_mes_o_periodo(t):
            continue
        if t in {"gastos", "gasto", "comparar", "compras"}:
            continue
        if 1 <= len(t) <= 6:
            out.append(t.upper())

    seen = set()
    res = []
    for x in out:
        if x not in seen:
            seen.add(x)
            res.append(x)
    return res


# =====================================================================
# HELPER: DETECTAR SI ES COMPARACIÓN
# =====================================================================

def _es_comparacion(texto_norm: str) -> bool:
    """Detecta si el texto pide una comparación"""
    return any(p in texto_norm for p in PALABRAS_COMPARACION)


def _extraer_proveedor_limpio(texto: str) -> str:
    """Extrae el proveedor limpiando todas las palabras innecesarias"""
    return _extraer_patron_libre(texto, PALABRAS_EXCLUIR_PROVEEDOR)


def _extraer_mes_keys_multiples(texto: str) -> List[str]:
    """Extrae múltiples mes_key del texto"""
    meses = extraer_meses_para_comparacion(texto)
    return [m[2] for m in meses]


# =====================================================================
# DETECTOR DE INTENCIÓN PRINCIPAL CON ORDEN DE PRIORIDAD (CORREGIDO + STOCK)
# =====================================================================

def detectar_intencion(texto: str) -> Dict:
    """
    Detecta intención con ORDEN DE PRIORIDAD claro
    Retorna: {'tipo': 'xxx', 'parametros': {...}, 'debug': 'info'}
    
    CAMBIOS:
    - Comparaciones tienen MAYOR prioridad
    - "comparame", "compara" ahora se detectan
    - Mejor limpieza del proveedor
    - ✅ NUEVO: Intenciones de STOCK agregadas
    - ✅ NUEVO: Comparativas "expertas": proveedores múltiples y mes + múltiples años
    """
    
    texto_norm = normalizar_texto(texto).replace("última", "ultima")
    intencion = {'tipo': 'consulta_general', 'parametros': {}, 'debug': ''}

    # =====================================================================
    # ✅ PRIORIDAD 0: CONSULTAS DE STOCK (NUEVA)
    # =====================================================================
    if _es_consulta_stock(texto_norm):
        return _detectar_intencion_stock(texto)

    # =====================================================================
    # 🏆 PRIORIDAD X: TOP PROVEEDORES (COMPRAS IA) - DETECCIÓN FLEXIBLE
    # =====================================================================
    palabras_top = ['top', 'ranking', 'mayores', 'principales', 'mayor gasto', 'mas compramos', 'mas gastamos']
    tiene_top = any(p in texto_norm for p in palabras_top)
    tiene_proveedores = 'proveedor' in texto_norm or 'proveedores' in texto_norm
    
    if tiene_top and tiene_proveedores:
        anios = extraer_anios(texto)
        mes_key = _extraer_mes_key(texto)
        
        # Detectar moneda
        moneda = None
        if any(m in texto_norm for m in ['dolares', 'dolar', 'usd', 'u$s']):
            moneda = 'U$S'
        elif any(m in texto_norm for m in ['pesos', '$']):
            moneda = '$'

        params = {}
        
        if moneda:
            params["moneda"] = moneda
        if mes_key:
            params["mes"] = mes_key
        elif anios:
            params["anio"] = anios[0]

        return {
            "tipo": "top_10_proveedores",
            "parametros": params,
            "debug": f"Match: top proveedores (mes={mes_key}, anio={anios[0] if anios else None}, moneda={moneda})"
        }

    # =====================================================================
    # PRIORIDAD 1: LISTAR VALORES (muy específico)
    # =====================================================================
    if 'listar' in texto_norm and any(x in texto_norm for x in ['proveedores', 'familias', 'articulos', 'proveedor', 'familia', 'articulo']):
        intencion['tipo'] = 'listar_valores'
        intencion['debug'] = 'Match: listar valores'
        return intencion

    # =====================================================================
    # PRIORIDAD 2: FACTURA POR NÚMERO (más específico que "última factura")
    # =====================================================================
    nro = _extraer_nro_factura(texto)
    if nro and ('factura' in texto_norm) and any(x in texto_norm for x in ['detalle', 'ver', 'mostrar', 'numero', 'nro']):
        intencion['tipo'] = 'detalle_factura_numero'
        intencion['parametros']['nro_factura'] = nro
        intencion['debug'] = f'Match: factura número {nro}'
        return intencion

    # =====================================================================
    # PRIORIDAD 3: FACTURA COMPLETA DE ARTÍCULO
    # =====================================================================
    if ('factura completa' in texto_norm) or (('ultima' in texto_norm) and ('factura' in texto_norm) and ('completa' in texto_norm or 'toda' in texto_norm)):
        intencion['tipo'] = 'factura_completa_articulo'
        intencion['debug'] = 'Match: factura completa artículo'
        return intencion

    # =====================================================================
    # PRIORIDAD 4: ÚLTIMA FACTURA
    # =====================================================================
    tiene_ultimo = any(x in texto_norm for x in ['ultima', 'ultimo', 'ultim'])
    tiene_factura = 'factura' in texto_norm
    tiene_cuando_vino = any(x in texto_norm for x in ['cuando vino', 'cuando llego', 'cuando entro'])
    
    if (tiene_ultimo and tiene_factura) or (tiene_cuando_vino and tiene_ultimo) or (tiene_ultimo and not tiene_factura and len(texto_norm.split()) >= 2):
        if not any(x in texto_norm for x in ['completa', 'toda', 'todas', 'entera']):
            # NO si es comparación
            if not _es_comparacion(texto_norm):
                intencion['tipo'] = 'ultima_factura_articulo'
                intencion['debug'] = 'Match: última factura (flexible - ignora ruido)'
                return intencion

    # =====================================================================
    # PRIORIDAD 5: TODAS LAS FACTURAS DE ARTÍCULO
    # =====================================================================
    if any(x in texto_norm for x in ['facturas', 'en que factura', 'cuando vino', 'listar facturas', 'factura vino']):
        if 'ultima' not in texto_norm and not _es_comparacion(texto_norm):
            intencion['tipo'] = 'facturas_articulo'
            intencion['debug'] = 'Match: todas las facturas de artículo'
            return intencion

    # =====================================================================
    # PRIORIDAD 6: GASTOS SECCIONES / FAMILIAS (solo si NO es comparación)
    # =====================================================================
    tiene_gastos = any(k in texto_norm for k in ['gastos', 'gasto', 'gastado', 'gastamos', 'importes', 'importe', 'cuanto gasto', 'cuanto fue'])
    tiene_familia = any(k in texto_norm for k in ['familia', 'familias', 'seccion', 'secciones'])
    
    # ⚠️ NO matchear si es comparación (eso va a PRIORIDAD 7)
    if tiene_gastos and tiene_familia and not _es_comparacion(texto_norm):
        intencion['tipo'] = 'gastos_secciones'
        intencion['debug'] = 'Match: gastos por familias/secciones'
        return intencion


    # =====================================================================
    # 🌟 PRIORIDAD 7: COMPARACIONES (ANTES DE COMPRAS)
    # =====================================================================
    if _es_comparacion(texto_norm):
        hoy = datetime.now()

        anios = extraer_anios(texto)
        meses_nums = _extraer_meses_numeros_en_orden(texto)
        meses_simple = extraer_meses_para_comparacion(texto)  # mantiene soporte existente

        # Proveedores múltiples: primero si explícita "proveedor", si no, libre (coma / y)
        proveedores = []
        if 'proveedor' in texto_norm or 'proveedores' in texto_norm:
            proveedores = extraer_valores_multiples(texto, 'proveedor')

        if not proveedores:
            proveedores = _extraer_proveedores_multiples_libre(texto)

        # Fallback (compatibilidad): si quedó 1 string limpio
        if not proveedores:
            prov_limpio = _extraer_proveedor_limpio(texto)
            proveedores = [prov_limpio] if prov_limpio else []

        # Detectar si es comparación de FAMILIAS/GASTOS
        es_familia = any(x in texto_norm for x in ['familia', 'familias', 'seccion', 'secciones'])
        tiene_gastos_comp = any(x in texto_norm for x in ['gastos', 'gasto', 'gastado', 'importe', 'importes'])

        # Detectar moneda
        moneda = None
        if any(m in texto_norm for m in ['dolares', 'dolar', 'usd', 'u$s']):
            moneda = 'U$S'
        elif any(m in texto_norm for m in ['pesos', '$']):
            moneda = '$'

        # ---------------------------------------------------------------
        # ✅ CASO EXPERTO: MESES + 2+ AÑOS  (ej: "noviembre 2024 2025")
        # Genera períodos combinando todo: 2024-11 y 2025-11
        # ---------------------------------------------------------------
        if meses_nums and len(anios) >= 2:
            periodos = _generar_periodos_mes_keys(anios, meses_nums, hoy.year)

            if len(periodos) >= 2:
                intencion['parametros']['meses'] = periodos
                if moneda:
                    intencion['parametros']['moneda'] = moneda

                if es_familia or tiene_gastos_comp:
                    intencion['tipo'] = 'comparar_familia_meses'
                    intencion['debug'] = f"Match: comparar familia por períodos {periodos} (años={anios}, meses={meses_nums})"
                    return intencion

                if proveedores:
                    intencion['parametros']['proveedores'] = proveedores
                intencion['tipo'] = 'comparar_proveedor_meses'
                intencion['debug'] = f"Match: comparar proveedor(es) {proveedores} por períodos {periodos}"
                return intencion

        # --- COMPARACIÓN POR AÑOS (sin meses explícitos) ---
        if len(anios) >= 2 and not meses_nums:
            intencion['parametros']['anios'] = anios

            if moneda:
                intencion['parametros']['moneda'] = moneda

            # Familia
            if es_familia or tiene_gastos_comp:
                intencion['tipo'] = 'comparar_familia_anios'
                intencion['debug'] = f'Match: comparar familia años {anios}'
                return intencion

            # Proveedor
            if proveedores:
                intencion['parametros']['proveedores'] = proveedores
                intencion['tipo'] = 'comparar_proveedor_anios'
                intencion['debug'] = f'Match: comparar proveedor(es) {proveedores} años {anios}'
                return intencion

            # Artículo
            articulo = _extraer_proveedor_limpio(texto)
            if articulo:
                intencion['parametros']['articulo_like'] = articulo
                intencion['tipo'] = 'comparar_articulo_anios'
                intencion['debug'] = f'Match: comparar artículo {articulo} años {anios}'
                return intencion

        # --- COMPARACIÓN POR MESES (caso existente) ---
        # Si el usuario puso 2+ meses (con o sin año global), sigue usando la lógica existente,
        # pero ahora también soporta múltiples proveedores en 'proveedores'.
        if len(meses_simple) >= 2:
            intencion['parametros']['meses'] = [m[2] for m in meses_simple]

            if moneda:
                intencion['parametros']['moneda'] = moneda

            # Proveedor
            if proveedores:
                intencion['parametros']['proveedores'] = proveedores
                intencion['tipo'] = 'comparar_proveedor_meses'
                intencion['debug'] = f"Match: comparar proveedor(es) {proveedores} meses {[m[2] for m in meses_simple]}"
                return intencion

            # Comparar familia (si tiene palabras de familia/gastos)
            if es_familia or tiene_gastos_comp:
                intencion['tipo'] = 'comparar_familia_meses'
                intencion['debug'] = f"Match: comparar familia meses {[m[2] for m in meses_simple]}"
                return intencion

            # Default: proveedor (sin proveedor explícito)
            intencion['tipo'] = 'comparar_proveedor_meses'
            intencion['parametros']['proveedores'] = proveedores
            intencion['debug'] = f"Match: comparar (default) meses {[m[2] for m in meses_simple]}"
            return intencion

        # Fallback comparación
        intencion['tipo'] = 'consulta_general'
        intencion['debug'] = 'Comparación detectada pero sin parámetros suficientes → IA'
        return intencion

    # =====================================================================
    # PRIORIDAD 8: COMPRAS POR MES (formato Excel)
    # =====================================================================
    if (
        ('compras' in texto_norm or 'compra' in texto_norm)
        and ('por mes' in texto_norm or 'del mes' in texto_norm)
        and any(x in texto_norm for x in ['listar', 'detalle', 'ver', 'mostrar', 'excel'])
    ):
        intencion['tipo'] = 'compras_por_mes'
        intencion['debug'] = 'Match: compras por mes'
        return intencion

        # =====================================================================
    # ✅ PRIORIDAD 8.5: COMPRAS POR AÑO COMPLETO (NUEVO)
    # Ejemplos: "compras 2025", "compras del 2024", "mostrame las compras 2025"
    # =====================================================================
    if 'compra' in texto_norm or 'compramos' in texto_norm:
        # Verificar que NO sea comparación, NO tenga proveedor/artículo explícito
        es_comparacion_check = _es_comparacion(texto_norm)
        tiene_proveedor_explicito = 'proveedor' in texto_norm
        tiene_articulo_explicito = 'articulo' in texto_norm
        tiene_familia_explicita = 'familia' in texto_norm or 'seccion' in texto_norm
        
        # Patrón específico: "compras 2025", "compras del 2024", "compras año 2023"
        patron_compras_anio = re.search(r'compras?\s+(?:del\s+)?(?:año\s+)?(?:en\s+)?(20\d{2})\b', texto_norm)
        
        # También detectar: "mostrame/ver/dame las compras 2025"
        patron_mostrar_compras = re.search(r'(?:mostrar?|mostrame|ver|dame|listado|todas?\s+las?)\s+(?:las?\s+)?compras?\s+(?:del?\s+)?(?:año\s+)?(?:en\s+)?(20\d{2})\b', texto_norm)
        
        # Detectar "cuanto compramos en 2025" o "total compras 2025"
        patron_total_anio = re.search(r'(?:cuanto|total|resumen)\s+(?:compramos|compras?|gastamos)?\s+(?:en\s+)?(20\d{2})\b', texto_norm)
        
        if (patron_compras_anio or patron_mostrar_compras or patron_total_anio) and not es_comparacion_check:
            # Extraer el año del patrón que matcheó
            if patron_compras_anio:
                anio = int(patron_compras_anio.group(1))
            elif patron_mostrar_compras:
                anio = int(patron_mostrar_compras.group(1))
            else:
                anio = int(patron_total_anio.group(1))
            
            # Solo si NO tiene filtros adicionales explícitos
            prov_limpio = _extraer_proveedor_limpio(texto)
            
            # Si el patrón libre está vacío o es muy corto, es compras año puro
            if not tiene_proveedor_explicito and not tiene_articulo_explicito and not tiene_familia_explicita:
                if not prov_limpio or len(prov_limpio) <= 2:
                    intencion['tipo'] = 'compras_anio'
                    intencion['parametros']['anio'] = anio
                    intencion['debug'] = f'Match: compras año {anio} (sin filtros)'
                    return intencion


    # =====================================================================
    # PRIORIDAD 9: DETALLE COMPRAS PROVEEDOR / ARTÍCULO + MES O AÑO
    # =====================================================================
    if ('compra' in texto_norm or 'compras' in texto_norm or 'compre' in texto_norm):

        # NO si ya es comparación
        if not _es_comparacion(texto_norm):

            mes_key = _extraer_mes_key(texto)
            prov = _extraer_proveedor_limpio(texto)
            articulos = extraer_valores_multiples(texto, 'articulo')

            # DESAMBIGUACIÓN: términos que son ARTÍCULO (no proveedor)
            if (not articulos) and prov:
                prov_norm = (prov or "").strip().lower()
                if prov_norm in {"vitek"}:
                    articulos = [prov]
                    prov = None

            # ARTÍCULO + MES
            if mes_key and articulos:
                intencion['tipo'] = 'detalle_compras_articulo_mes'
                intencion['parametros']['mes_key'] = mes_key
                intencion['parametros']['articulo_like'] = articulos[0]
                intencion['debug'] = f"Match: detalle compras artículo {articulos[0]} en {mes_key}"
                return intencion

            # PROVEEDOR + MES
            if mes_key and prov:
                intencion['tipo'] = 'detalle_compras_proveedor_mes'
                intencion['parametros']['mes_key'] = mes_key
                intencion['parametros']['proveedor_like'] = prov
                intencion['debug'] = f"Match: detalle compras {prov} en {mes_key}"
                return intencion

            # AÑO EXPLÍCITO
            anios = sorted({int(y) for y in re.findall(r"\b(20\d{2})\b", texto_norm)})

            # ARTÍCULO + 2+ AÑOS → COMPARACIÓN
            if len(anios) >= 2 and articulos:
                intencion['tipo'] = 'comparar_articulo_anios'
                intencion['parametros']['anios'] = anios
                intencion['parametros']['articulo_like'] = articulos[0]
                intencion['debug'] = f"Match: comparar artículo {articulos[0]} en años {anios}"
                return intencion

            # ARTÍCULO + 1 AÑO
            if anios and articulos:
                intencion['tipo'] = 'detalle_compras_articulo_anio'
                intencion['parametros']['anio'] = anios[0]
                intencion['parametros']['articulo_like'] = articulos[0]
                intencion['debug'] = f"Match: detalle compras artículo {articulos[0]} en año {anios[0]}"
                return intencion

            # PROVEEDOR + AÑO
            if anios and prov:
                intencion['tipo'] = 'detalle_compras_proveedor_anio'
                intencion['parametros']['anio'] = anios[0]
                intencion['parametros']['proveedor_like'] = prov
                intencion['debug'] = f"Match: detalle compras {prov} en año {anios[0]}"
                return intencion

    # =====================================================================
    # PRIORIDAD 10: TOTAL COMPRAS PROVEEDOR + MONEDA + 2+ PERÍODOS
    # =====================================================================
    if any(k in texto_norm for k in ["proveedor", "proveedores", "por proveedor"]) and any(k in texto_norm for k in ["total", "ranking", "mayor", "gasto", "gastado", "se gasto", "cuanto"]):
        periodos = _extraer_mes_keys_multiples(texto)
        if len(periodos) >= 2:
            intencion['tipo'] = 'total_proveedor_moneda_periodos'
            intencion['parametros']['periodos'] = periodos
            intencion['debug'] = f'Match: total proveedor múltiples períodos {periodos}'
            return intencion

    # =====================================================================
    # PRIORIDAD 11: DETALLE GENERAL
    # =====================================================================
    if 'detalle' in texto_norm or 'que vino' in texto_norm or 'listado' in texto_norm:
        intencion['tipo'] = 'detalle'
        intencion['debug'] = 'Match: detalle general'
        return intencion

    # =====================================================================
    # PRIORIDAD 12: COMPRAS GENERAL
    # =====================================================================
    if 'compras' in texto_norm or 'compra' in texto_norm:
        intencion['tipo'] = 'consulta_general'
        intencion['debug'] = 'Match: compras general'
        return intencion

    # =====================================================================
    # FALLBACK: CONSULTA GENERAL
    # =====================================================================
    intencion['debug'] = 'No match específico, consulta general'
    return intencion


# =====================================================================
# CONSTRUCCIÓN DE WHERE CLAUSE
# =====================================================================

def construir_where_clause(texto: str) -> Tuple[str, tuple]:
    """Construye cláusula WHERE basada en el texto"""
    condiciones = []
    params = []
    texto_norm = normalizar_texto(texto)

    condiciones.append("(tipo_comprobante = 'Compra Contado' OR tipo_comprobante LIKE 'Compra%%')")

    if 'proveedor' in texto_norm:
        proveedores = extraer_valores_multiples(texto, 'proveedor')
        if proveedores:
            parts = []
            for prov in proveedores:
                parts.append("LOWER(Proveedor) LIKE %s")
                params.append(f"%{prov.lower()}%")
            condiciones.append(f"({' OR '.join(parts)})")

    if 'articulo' in texto_norm:
        articulos = extraer_valores_multiples(texto, 'articulo')

        if articulos:
            parts = []

            for art in articulos:
                parts.append("LOWER(Articulo) LIKE %s")
                params.append(f"%{art.lower()}%")

            condiciones.append(f"({' OR '.join(parts)})")

    if 'familia' in texto_norm:
        familias = extraer_valores_multiples(texto, 'familia')
        if familias:
            parts = []
            for fam in familias:
                parts.append("LOWER(Familia) LIKE %s")
                params.append(f"%{fam.lower()}%")
            condiciones.append(f"({' OR '.join(parts)})")

    where_clause = " AND ".join(condiciones) if condiciones else "1=1"
    return where_clause, tuple(params)
