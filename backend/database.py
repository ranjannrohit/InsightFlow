import sqlite3
import os
import uuid
import hashlib
import hmac
import secrets
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(__file__), "insightflow.db")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _safe_alter(cursor, table: str, column: str, col_def: str):
    """Adds a column only if it doesn't already exist (SQLite safe migration)."""
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
    except Exception:
        pass  # Column already exists — safe to ignore


def init_db():
    """Initializes ALL database tables. Safe to call on existing database — never drops tables."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # ── Core User & Session Tables (original, preserved) ──────────────────────

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
        updated_at TEXT NOT NULL,
        last_credit_reset TEXT
    )
    """)

    # Safe migration: add last_credit_reset if missing on existing DB
    _safe_alter(cursor, "users", "last_credit_reset", "TEXT")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS datasets (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        filename TEXT NOT NULL,
        file_type TEXT NOT NULL,
        rows INTEGER DEFAULT 0,
        cols INTEGER DEFAULT 0,
        csv_data TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_resets (
        token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # ── Credit Transactions ────────────────────────────────────────────────────

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS credit_transactions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        amount INTEGER NOT NULL,
        operation TEXT NOT NULL,
        resource_id TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # ── Chat ──────────────────────────────────────────────────────────────────

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        dataset_id TEXT,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # ── Forecasts ─────────────────────────────────────────────────────────────

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS forecasts (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        dataset_id TEXT,
        target_column TEXT NOT NULL,
        periods INTEGER DEFAULT 6,
        result_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # ── Visualizations ────────────────────────────────────────────────────────

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS visualizations (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        dataset_id TEXT,
        chart_type TEXT NOT NULL,
        title TEXT,
        configuration_json TEXT,
        result_metadata_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # ── Reports ───────────────────────────────────────────────────────────────

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        dataset_id TEXT,
        type TEXT NOT NULL DEFAULT 'executive',
        title TEXT NOT NULL,
        content_json TEXT,
        status TEXT NOT NULL DEFAULT 'completed',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # ── History ───────────────────────────────────────────────────────────────

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        resource_id TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # ── Notifications ─────────────────────────────────────────────────────────

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'info',
        title TEXT NOT NULL,
        message TEXT,
        resource_id TEXT,
        read INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # ── User Settings ─────────────────────────────────────────────────────────

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_settings (
        id TEXT PRIMARY KEY,
        user_id TEXT UNIQUE NOT NULL,
        theme TEXT DEFAULT 'dark',
        language TEXT DEFAULT 'en',
        email_notifications INTEGER DEFAULT 1,
        product_updates INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # ── Indexes ───────────────────────────────────────────────────────────────

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_datasets_user_id ON datasets(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_datasets_created_at ON datasets(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_forecasts_user_id ON forecasts(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_visualizations_user_id ON visualizations(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_history_user_id ON history(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_history_created_at ON history(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read)",
        "CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_id ON credit_transactions(user_id)",
    ]
    for idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
        except Exception:
            pass

    conn.commit()
    conn.close()


# ── Password Hashing Helpers (PBKDF2-HMAC-SHA256) ──────────────────────────

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


# ── User CRUD ──────────────────────────────────────────────────────────────

def user_row_to_dict(row: sqlite3.Row) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    d = dict(row)
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

    if not profile_photo:
        initials = "".join([part[0].upper() for part in name.split()[:2]]) or "IF"
        profile_photo = f"https://ui-avatars.com/api/?name={initials}&background=d4ff2a&color=040507&bold=true"

    cursor.execute(
        """
        INSERT INTO users (id, name, email, password_hash, google_id, profile_photo, credits,
                           history_enabled, theme, created_at, updated_at, last_credit_reset)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, name, email.lower().strip(), pwd_hash, google_id, profile_photo,
         100, 1, 'dark', now, now, now)
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
    return dict(row)


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


# ── Session Management ─────────────────────────────────────────────────────

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


# ── Profile & Password Reset Management ───────────────────────────────────

def update_user_profile(
    user_id: str,
    name: Optional[str] = None,
    profile_photo: Optional[str] = None,
    theme: Optional[str] = None,
    history_enabled: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    updates = []
    params = []

    if name:
        updates.append("name = ?")
        params.append(name.strip())
    if profile_photo:
        updates.append("profile_photo = ?")
        params.append(profile_photo.strip())
    if theme:
        updates.append("theme = ?")
        params.append(theme)
    if history_enabled is not None:
        updates.append("history_enabled = ?")
        params.append(history_enabled)

    if not updates:
        conn.close()
        return get_user_by_id(user_id)

    updates.append("updated_at = ?")
    params.append(now)
    params.append(user_id)

    sql = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(sql, tuple(params))
    conn.commit()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return user_row_to_dict(row)


def change_user_password(user_id: str, old_password: str, new_password: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row or not row["password_hash"]:
        conn.close()
        return False

    if not verify_password(old_password, row["password_hash"]):
        conn.close()
        return False

    new_hash = hash_password(new_password)
    now = datetime.utcnow().isoformat()
    cursor.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?", (new_hash, now, user_id))
    conn.commit()
    conn.close()
    return True


def create_password_reset_token(email: str) -> Optional[str]:
    user = get_user_by_email(email)
    if not user:
        return None
    token = secrets.token_hex(24)
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    now = datetime.utcnow().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO password_resets (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (token, user["id"], expires_at, now)
    )
    conn.commit()
    conn.close()
    return token


def verify_reset_token(token: str) -> Optional[str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, expires_at FROM password_resets WHERE token = ?", (token,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None

    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at < datetime.utcnow():
        return None
    return row["user_id"]


def reset_password_with_token(token: str, new_password: str) -> bool:
    user_id = verify_reset_token(token)
    if not user_id:
        return False

    new_hash = hash_password(new_password)
    now = datetime.utcnow().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?", (new_hash, now, user_id))
    cursor.execute("DELETE FROM password_resets WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    return True


# ── Dataset History & Storage ──────────────────────────────────────────────

def save_user_dataset(
    user_id: str,
    name: str,
    filename: str,
    file_type: str,
    rows: int,
    cols: int,
    csv_data: str
) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    dataset_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    cursor.execute(
        """
        INSERT INTO datasets (id, user_id, name, filename, file_type, rows, cols, csv_data, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (dataset_id, user_id, name, filename, file_type, rows, cols, csv_data, now)
    )
    conn.commit()
    cursor.execute("SELECT id, user_id, name, filename, file_type, rows, cols, created_at FROM datasets WHERE id = ?", (dataset_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)


def get_user_datasets(user_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, user_id, name, filename, file_type, rows, cols, created_at FROM datasets WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_dataset_by_id(dataset_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM datasets WHERE id = ? AND user_id = ?", (dataset_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_latest_user_dataset(user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM datasets WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None



def delete_user_dataset(dataset_id: str, user_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM datasets WHERE id = ? AND user_id = ?", (dataset_id, user_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# ── Credits ───────────────────────────────────────────────────────────────

def get_user_credits(user_id: str) -> int:
    """Returns current credit balance for user, resetting if a new day has started."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT credits, last_credit_reset FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return 0

    # Daily reset check
    now = datetime.utcnow()
    last_reset_str = row["last_credit_reset"]
    if last_reset_str:
        try:
            last_reset = datetime.fromisoformat(last_reset_str)
            if last_reset.date() < now.date():
                reset_daily_credits(user_id)
                return 100
        except Exception:
            pass
    else:
        # First time — initialise reset timestamp
        reset_daily_credits(user_id)
        return 100

    return int(row["credits"])


def reset_daily_credits(user_id: str) -> None:
    """Resets user's credits to 100 and records timestamp."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute(
        "UPDATE users SET credits = 100, last_credit_reset = ?, updated_at = ? WHERE id = ?",
        (now, now, user_id)
    )
    conn.commit()

    # Record the reset as a transaction
    tx_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO credit_transactions (id, user_id, amount, operation, resource_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (tx_id, user_id, 100, "DAILY_RESET", None, now)
    )
    conn.commit()
    conn.close()


def spend_credit(user_id: str, operation: str, resource_id: Optional[str] = None) -> bool:
    """
    Atomically deducts 1 credit. Returns True if successful.
    Returns False if insufficient credits.
    """
    # Ensure daily reset has been applied first
    current_credits = get_user_credits(user_id)
    if current_credits <= 0:
        return False

    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    # Atomic decrement — only update if credits > 0 to prevent race conditions
    cursor.execute(
        "UPDATE users SET credits = credits - 1, updated_at = ? WHERE id = ? AND credits > 0",
        (now, user_id)
    )
    affected = cursor.rowcount

    if affected > 0:
        # Record the transaction
        tx_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO credit_transactions (id, user_id, amount, operation, resource_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (tx_id, user_id, -1, operation, resource_id, now)
        )
        conn.commit()
        conn.close()
        return True

    conn.close()
    return False


def get_credit_transactions(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM credit_transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Chat Sessions ──────────────────────────────────────────────────────────

def create_chat_session(user_id: str, title: str, dataset_id: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    session_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    cursor.execute(
        "INSERT INTO chat_sessions (id, user_id, dataset_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, user_id, dataset_id, title, now, now)
    )
    conn.commit()
    cursor.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)


def get_chat_sessions(user_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_chat_session(session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM chat_sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def save_chat_message(
    session_id: str,
    user_id: str,
    role: str,
    content: str
) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    msg_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    cursor.execute(
        "INSERT INTO chat_messages (id, session_id, user_id, role, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (msg_id, session_id, user_id, role, content, now)
    )
    # Update session's updated_at
    cursor.execute(
        "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
        (now, session_id)
    )
    conn.commit()
    cursor.execute("SELECT * FROM chat_messages WHERE id = ?", (msg_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)


def get_session_messages(session_id: str, user_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    # Verify ownership via session
    cursor.execute(
        "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id)
    )
    if not cursor.fetchone():
        conn.close()
        return []
    cursor.execute(
        "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Forecasts ─────────────────────────────────────────────────────────────

def save_forecast(
    user_id: str,
    target_column: str,
    periods: int,
    result: Dict[str, Any],
    dataset_id: Optional[str] = None
) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    forecast_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    cursor.execute(
        "INSERT INTO forecasts (id, user_id, dataset_id, target_column, periods, result_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (forecast_id, user_id, dataset_id, target_column, periods, json.dumps(result), now)
    )
    conn.commit()
    cursor.execute("SELECT id, user_id, dataset_id, target_column, periods, created_at FROM forecasts WHERE id = ?", (forecast_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)


def get_user_forecasts(user_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, user_id, dataset_id, target_column, periods, created_at FROM forecasts WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_forecast_by_id(forecast_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM forecasts WHERE id = ? AND user_id = ?",
        (forecast_id, user_id)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    if d.get("result_json"):
        try:
            d["result"] = json.loads(d["result_json"])
        except Exception:
            d["result"] = {}
    return d


# ── Visualizations ────────────────────────────────────────────────────────

def save_visualization(
    user_id: str,
    chart_type: str,
    title: str,
    configuration: Dict[str, Any],
    result_metadata: Optional[Dict[str, Any]] = None,
    dataset_id: Optional[str] = None
) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    viz_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    cursor.execute(
        """
        INSERT INTO visualizations (id, user_id, dataset_id, chart_type, title, configuration_json, result_metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (viz_id, user_id, dataset_id, chart_type, title,
         json.dumps(configuration), json.dumps(result_metadata or {}), now)
    )
    conn.commit()
    cursor.execute("SELECT id, user_id, dataset_id, chart_type, title, created_at FROM visualizations WHERE id = ?", (viz_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)


def get_user_visualizations(user_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, user_id, dataset_id, chart_type, title, created_at FROM visualizations WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_visualization_by_id(viz_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM visualizations WHERE id = ? AND user_id = ?",
        (viz_id, user_id)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    for key in ("configuration_json", "result_metadata_json"):
        if d.get(key):
            try:
                d[key.replace("_json", "")] = json.loads(d[key])
            except Exception:
                pass
    return d


# ── Reports ───────────────────────────────────────────────────────────────

def save_report(
    user_id: str,
    title: str,
    content: Dict[str, Any],
    report_type: str = "executive",
    dataset_id: Optional[str] = None
) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    report_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    cursor.execute(
        """
        INSERT INTO reports (id, user_id, dataset_id, type, title, content_json, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (report_id, user_id, dataset_id, report_type, title, json.dumps(content), "completed", now, now)
    )
    conn.commit()
    cursor.execute("SELECT id, user_id, dataset_id, type, title, status, created_at FROM reports WHERE id = ?", (report_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)


def get_user_reports(user_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, user_id, dataset_id, type, title, status, created_at FROM reports WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_report_by_id(report_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM reports WHERE id = ? AND user_id = ?",
        (report_id, user_id)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    if d.get("content_json"):
        try:
            d["content"] = json.loads(d["content_json"])
        except Exception:
            d["content"] = {}
    return d


# ── History ───────────────────────────────────────────────────────────────

def add_history(
    user_id: str,
    type: str,
    title: str,
    description: Optional[str] = None,
    resource_id: Optional[str] = None
) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    history_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    cursor.execute(
        "INSERT INTO history (id, user_id, type, title, description, resource_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (history_id, user_id, type, title, description, resource_id, now)
    )
    conn.commit()
    cursor.execute("SELECT * FROM history WHERE id = ?", (history_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)


def get_user_history(user_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM history WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (user_id, limit, offset)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_history_count(user_id: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM history WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row["cnt"] if row else 0


# ── Notifications ─────────────────────────────────────────────────────────

def add_notification(
    user_id: str,
    title: str,
    message: str,
    notif_type: str = "info",
    resource_id: Optional[str] = None
) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    notif_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    cursor.execute(
        """
        INSERT INTO notifications (id, user_id, type, title, message, resource_id, read, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (notif_id, user_id, notif_type, title, message, resource_id, 0, now)
    )
    conn.commit()
    cursor.execute("SELECT * FROM notifications WHERE id = ?", (notif_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)


def get_user_notifications(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_notification_read(notif_id: str, user_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?",
        (notif_id, user_id)
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def mark_all_notifications_read(user_id: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE notifications SET read = 1 WHERE user_id = ? AND read = 0",
        (user_id,)
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected


def delete_notification(notif_id: str, user_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM notifications WHERE id = ? AND user_id = ?",
        (notif_id, user_id)
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_unread_notification_count(user_id: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) as cnt FROM notifications WHERE user_id = ? AND read = 0",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row["cnt"] if row else 0


# ── User Settings ─────────────────────────────────────────────────────────

def get_user_settings(user_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)

    # Return defaults if no settings row yet
    return {
        "user_id": user_id,
        "theme": "dark",
        "language": "en",
        "email_notifications": 1,
        "product_updates": 1
    }


def upsert_user_settings(
    user_id: str,
    theme: Optional[str] = None,
    language: Optional[str] = None,
    email_notifications: Optional[int] = None,
    product_updates: Optional[int] = None
) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    # Check existing
    cursor.execute("SELECT id FROM user_settings WHERE user_id = ?", (user_id,))
    existing = cursor.fetchone()

    if existing:
        updates = []
        params = []
        if theme is not None:
            updates.append("theme = ?")
            params.append(theme)
        if language is not None:
            updates.append("language = ?")
            params.append(language)
        if email_notifications is not None:
            updates.append("email_notifications = ?")
            params.append(email_notifications)
        if product_updates is not None:
            updates.append("product_updates = ?")
            params.append(product_updates)

        if updates:
            updates.append("updated_at = ?")
            params.append(now)
            params.append(user_id)
            cursor.execute(f"UPDATE user_settings SET {', '.join(updates)} WHERE user_id = ?", tuple(params))
    else:
        settings_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO user_settings (id, user_id, theme, language, email_notifications, product_updates, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (settings_id, user_id,
             theme or "dark",
             language or "en",
             email_notifications if email_notifications is not None else 1,
             product_updates if product_updates is not None else 1,
             now, now)
        )

    conn.commit()
    cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}
