# 🚀 Configurar Supabase en Streamlit

## ⚡ Solución Rápida

### PASO 1: Subir archivo a GitHub

1. Descarga el archivo `supabase_client.py`
2. Ponlo en tu carpeta `Fertichat_clean`
3. Ejecuta en CMD:

```cmd
cd C:\Users\gvela\OneDrive\Escritorio\Fertichat_clean
git add supabase_client.py
git commit -m "Agregar supabase_client"
git push origin main
```

---

### PASO 2: Configurar Secrets en Streamlit

1. Ve a: https://share.streamlit.io/
2. Click en tu app **fertichat**
3. Click en **⚙️ Settings** (esquina superior derecha)
4. Click en **Secrets**
5. Pega esto:

```toml
SUPABASE_URL = "https://ytmpjhdjecocoitptvjn.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl0bXBqaGRqZWNvY29pdHB0dmpuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY4NjU2MTYsImV4cCI6MjA4MjQ0MTYxNn0.Cd1BuRwE1y4X7DqLJqvXH3b6VCZQQ4-4tfhV2f4EsE4"
```

6. Click en **Save**
7. La app se reiniciará automáticamente

---

### PASO 3: Verificar requirements.txt

Asegúrate que `requirements.txt` tenga:

```
supabase>=2.0.0
python-dotenv
```

Si no está, agrégalo y sube a GitHub:

```cmd
git add requirements.txt
git commit -m "Actualizar requirements"
git push origin main
```

---

## ✅ Checklist

- [ ] Archivo `supabase_client.py` subido a GitHub
- [ ] Secrets configurados en Streamlit
- [ ] `requirements.txt` tiene `supabase`
- [ ] App reiniciada

---

## 🎯 Resultado

Tu app debería funcionar en: https://fertichat.streamlit.app/

Si sigue dando error, avísame qué dice el mensaje.
