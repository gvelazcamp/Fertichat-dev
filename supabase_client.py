import os
from supabase import create_client, Client

# Obtener credenciales desde variables de entorno
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

# Validar credenciales
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ ERROR: Faltan las credenciales de Supabase en las variables de entorno")

# Crear cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
