import sqlite3
import os
import uuid
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "insightflow.db")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the database schema for Users and Sessions if not existing."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT,
        google_id TEXT,
        profile_photo TEXT,
        credits INTEGER DEFAULT 100,
        history_enabled INTEGER DEFAULT 1,
        theme TEXT DEFAULT 'dark',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    conn.commit()
    conn.close()


# ── Password Hashing Helpers (PBKDF2-HMAC-SHA256) ──

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"{salt}${key.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash or '$' not in password_hash:
        return False
    try:
        salt, key_hex = password_hash.split('$', 1)
        expected_key = bytes.fromhex(key_hex)
        key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return hmac.compare_digest(key, expected_key)
    except Exception:
        return False


# ── User CRUD ──

def user_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    if not row:
        return None
    d = dict(row)
    # Exclude password_hash from return dict for security
    d.pop("password_hash", None)
    return d


def create_user(
    name: str,
    email: str,
    password: Optional[str] = None,
    google_id: Optional[str] = None,
    profile_photo: Optional[str] = None
) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    pwd_hash = hash_password(password) if password else None

    # Generate initials-based avatar fallback if profile_photo is missing
    if not profile_photo:
        initials = "".join([part[0].upper() for part in name.split()[:2]]) or "IF"
        profile_photo = f"https://ui-avatars.com/api/?name={initials}&background=d4ff2a&color=040507&bold=true"

    cursor.execute(
        """
        INSERT INTO users (id, name, email, password_hash, google_id, profile_photo, credits, history_enabled, theme, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, name, email.lower().strip(), pwd_hash, google_id, profile_photo, 100, 1, 'dark', now, now)
    )

    conn.commit()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return user_row_to_dict(row)


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email.lower().strip(),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    return d


def get_user_by_google_id(google_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE google_id = ?", (google_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return user_row_to_dict(row)


def update_google_user(user_id: str, google_id: str, profile_photo: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    if profile_photo:
        cursor.execute(
            "UPDATE users SET google_id = ?, profile_photo = ?, updated_at = ? WHERE id = ?",
            (google_id, profile_photo, now, user_id)
        )
    else:
        cursor.execute(
            "UPDATE users SET google_id = ?, updated_at = ? WHERE id = ?",
            (google_id, now, user_id)
        )
    conn.commit()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return user_row_to_dict(row)


# ── Session Management ──

def create_session(user_id: str, remember_me: bool = True) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()

    token = secrets.token_hex(32)
    days = 30 if remember_me else 1
    expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat()
    now = datetime.utcnow().isoformat()

    cursor.execute(
        "INSERT INTO sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (token, user_id, expires_at, now)
    )
    conn.commit()
    conn.close()
    return token


def get_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT u.*, s.expires_at 
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
        """,
        (token,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    # Check expiration
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at < datetime.utcnow():
        delete_session(token)
        return None

    return user_row_to_dict(row)


def delete_session(token: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()
