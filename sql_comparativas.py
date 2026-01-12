# ... (el resto del archivo permanece igual hasta la función)

def get_comparacion_proveedor_anios(*args, **kwargs) -> pd.DataFrame:
    """
    Compara proveedores entre años. Compatible con firmas flexibles:
    
    - get_comparacion_proveedor_anios(proveedor: str, anios: List[int])  # Un proveedor
    - get_comparacion_proveedor_anios(proveedores: List[str], anios: List[int])  # Múltiples proveedores
    - get_comparacion_proveedor_anios(proveedor1: str, proveedor2: str, anio1: int, anio2: int)  # Dos proveedores, dos años
    - Y otros formatos similares detectados automáticamente.
    """
    
    proveedores = None
    anios = None
    
    if len(args) == 2:
        # Firma canónica: (proveedor/es, anios)
        first, second = args
        if isinstance(first, str) and isinstance(second, list):
            # Un proveedor: ("roche", [2024, 2025])
            proveedores = [first]
            anios = second
        elif isinstance(first, list) and isinstance(second, list):
            # Múltiples proveedores: (["roche", "tresul"], [2024, 2025])
            proveedores = first
            anios = second
        else:
            return pd.DataFrame()
    
    elif len(args) == 4:
        # Firma extendida: (prov1, prov2, anio1, anio2)
        prov1, prov2, anio1, anio2 = args
        if isinstance(prov1, str) and isinstance(prov2, str):
            proveedores = [prov1, prov2]
            try:
                anios = [int(anio1), int(anio2)]
            except ValueError:
                return pd.DataFrame()
        else:
            return pd.DataFrame()
    
    else:
        return pd.DataFrame()
    
    # Normalizar y validar
    if not proveedores or not anios:
        return pd.DataFrame()
    
    # Si proveedores es str (por compatibilidad), convertir a lista
    if isinstance(proveedores, str):
        proveedores = [proveedores]
    
    # Llamar a la función multi existente para manejar la lógica
    return get_comparacion_proveedores_anios_multi(proveedores, anios)

# ... (el resto del archivo permanece igual)
