# =====================================================================
# 🔐 MÓDULO DE AUTENTICACIÓN - FERTI CHAT
# =====================================================================
# Login por USUARIO (no email)
# Base de datos: SQLite (users.db)
# Uso: Auth local simple (Streamlit Cloud)
# =====================================================================

import os
import sqlite3
import hashlib
from datetime import datetime
from typing import Optional, Tuple

# =====================================================================
# 📁 RUTA DE LA BASE DE DATOS
# Siempre relativa a este archivo (evita errores en cloud)
# =====================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")


# =====================================================================
# 👥 USUARIOS PREDEFINIDOS (SOLO ESTOS PUEDEN ENTRAR)
# =====================================================================
USUARIOS_PREDEFINIDOS = [
    {"usuario": "gvelazquez", "password": "123abc", "nombre": "G. Velazquez", "empresa": "Fertilab"},
    {"usuario": "dserveti", "password": "abc123", "nombre": "D. Serveti", "empresa": "Fertilab"},
    {"usuario": "jesteves", "password": "123abc", "nombre": "J. Esteves", "empresa": "Fertilab"},
    {"usuario": "sruiz", "password": "123abc", "nombre": "S. Ruiz", "empresa": "Fertilab"},
]

# =====================================================================
# FUNCIONES DE HASH
# =====================================================================

def hash_password(password: str) -> str:
    """Genera hash SHA-256 de la contraseña"""
    salt = "ferti_chat_2024_salt"
    salted = f"{salt}{password}{salt}"
    return hashlib.sha256(salted.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """Verifica si la contraseña coincide con el hash"""
    return hash_password(password) == password_hash

# =====================================================================
# INICIALIZACIÓN DE BASE DE DATOS (MIGRACIÓN SI HAY TABLA VIEJA)
# =====================================================================

def init_db():
    """
    Crea la tabla de usuarios y carga los predefinidos.
    Si detecta una tabla vieja (sin columna 'usuario'), la recrea automáticamente.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # -------------------------------------------------
    # Detectar si existe tabla vieja con otra estructura
    # -------------------------------------------------
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    existe = cursor.fetchone() is not None

    if existe:
        cursor.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cursor.fetchall()]  # r[1] = nombre de columna

        # Si no existe 'usuario' (o falta lo básico), es la tabla vieja -> recrear
        if ("usuario" not in cols) or ("password_hash" not in cols):
            cursor.execute("DROP TABLE IF EXISTS users")
            conn.commit()

    # -----------------------
    # Crear tabla nueva
    # -----------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nombre TEXT,
            empresa TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    conn.commit()

    # -----------------------
    # Cargar usuarios predefinidos
    # -----------------------
    for u in USUARIOS_PREDEFINIDOS:
        usuario_norm = (u["usuario"] or "").lower().strip()

        cursor.execute("SELECT id FROM users WHERE usuario = ?", (usuario_norm,))
        if not cursor.fetchone():
            password_hash = hash_password(u["password"])
            cursor.execute('''
                INSERT INTO users (usuario, password_hash, nombre, empresa)
                VALUES (?, ?, ?, ?)
            ''', (usuario_norm, password_hash, u.get("nombre"), u.get("empresa")))

    conn.commit()
    conn.close()


# =====================================================================
# LOGIN
# =====================================================================

def login_user(usuario: str, password: str) -> Tuple[bool, str, Optional[dict]]:
    """
    Inicia sesión por usuario.
    Returns: (éxito, mensaje, datos_usuario)
    """
    if not usuario or not password:
        return False, "Usuario y contraseña son requeridos", None

    usuario_norm = usuario.lower().strip()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, usuario, password_hash, nombre, empresa, is_active
        FROM users
        WHERE usuario = ?
    """, (usuario_norm,))

    row = cursor.fetchone()

    if not row:
        conn.close()
        return False, "Usuario no autorizado", None

    user_id, user_usuario, password_hash, nombre, empresa, is_active = row

    if not is_active:
        conn.close()
        return False, "Cuenta desactivada", None

    if not verify_password(password, password_hash):
        conn.close()
        return False, "Contraseña incorrecta", None

    # Actualizar último login
    cursor.execute(
        "UPDATE users SET last_login = ? WHERE id = ?",
        (datetime.now(), user_id)
    )
    conn.commit()
    conn.close()

    user_data = {
        "id": user_id,
        "usuario": user_usuario,
        "nombre": nombre,
        "empresa": empresa,
        # Si tu UI muestra email, lo dejamos “virtual” para compatibilidad (no viene de la DB)
        "email": f"{user_usuario}@fertilab.com",
    }

    return True, f"¡Bienvenido {nombre}!", user_data


# =====================================================================
# REGISTRO (DESHABILITADO) - SOLO PARA COMPATIBILIDAD DE IMPORTS
# =====================================================================

def register_user(usuario: str, password: str, nombre: str = "", empresa: str = "Fertilab"):
    """
    Registro deshabilitado: en este sistema solo entran USUARIOS_PREDEFINIDOS.
    Se deja esta función para que no falle el import desde login_page.py.
    """
    return False, "Registro deshabilitado. Contactá al administrador.", None

# =====================================================================
# CAMBIO DE CONTRASEÑA
# =====================================================================

def change_password(usuario: str, old_password: str, new_password: str) -> Tuple[bool, str]:
    """Cambia la contraseña del usuario."""
    if len(new_password) < 4:
        return False, "La nueva contraseña debe tener al menos 4 caracteres"

    usuario_norm = usuario.lower().strip()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, password_hash FROM users WHERE usuario = ?", (usuario_norm,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return False, "Usuario no encontrado"

    user_id, password_hash = row

    if not verify_password(old_password, password_hash):
        conn.close()
        return False, "Contraseña actual incorrecta"

    new_hash = hash_password(new_password)
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    conn.commit()
    conn.close()

    return True, "¡Contraseña actualizada!"

# =====================================================================
# FUNCIONES AUXILIARES
# =====================================================================

def get_user_count() -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def listar_usuarios() -> list:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, usuario, nombre, empresa, last_login FROM users WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()
    return rows

def reset_password(usuario: str, new_password: str) -> Tuple[bool, str]:
    usuario_norm = usuario.lower().strip()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE usuario = ?", (usuario_norm,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return False, "Usuario no encontrado"

    user_id = row[0]
    new_hash = hash_password(new_password)
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    conn.commit()
    conn.close()

    return True, f"Contraseña de {usuario_norm} reseteada"

# Inicializar DB al importar
init_db()
