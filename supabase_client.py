  import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # <-- CORRECCIÓN: Usa la key correcta (no ANON_KEY)

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ ERROR: Faltan las credenciales de Supabase en las variables de entorno")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Test de conexión (opcional, pero recomendado para debug)
try:
    response = supabase.table("chatbot_raw").select("*").limit(1).execute()
    print("✅ Conexión a Supabase OK:", len(response.data), "registros de prueba")
except Exception as e:
    print("❌ Error de conexión:", str(e))
