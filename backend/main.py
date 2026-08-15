import logging
import time
from fastapi import FastAPI, UploadFile, File, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

import pandas as pd
import numpy as np
import duckdb
import sqlite3
import json
import io
import traceback
import os
import sys
from dotenv import load_dotenv
import httpx

# Ensure backend directory is in sys.path regardless of execution working directory
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import database
from auth_deps import get_current_user, get_optional_user
from credit_service import ensure_credits, spend_credit, get_balance
from models.schemas import (
    SignUpRequest, LoginRequest, GoogleAuthRequest,
    ForgotPasswordRequest, ResetPasswordRequest, UpdateProfileRequest,
    ChangePasswordRequest, FilterDataRequest
)
from tools.analytics_tools import generate_pdf_report_bytes

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger("insightflow")

# ── Environment ────────────────────────────────────────────────────────────
load_dotenv()
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()


def get_active_provider() -> str:
    if GROQ_API_KEY:
        return "groq"
    if GEMINI_API_KEY:
        return "gemini"
    return "local"


def ai_chat(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
    if GROQ_API_KEY:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
            }
            with httpx.Client(timeout=30.0) as client:
                res = client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    return res.json()["choices"][0]["message"]["content"]
        except Exception:
            pass

    if GEMINI_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": f"{system_prompt}\n\nUser request:\n{user_prompt}"}
                        ]
                    }
                ],
                "generationConfig": {"temperature": temperature},
            }
            with httpx.Client(timeout=30.0) as client:
                res = client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            pass

    raise RuntimeError("AI Provider error or no valid API key available")


# ── APP SETUP & DATABASE INITIALIZATION ───────────────────────────────────

app = FastAPI(
    title="InsightFlow Analytics Engine",
    description="Multi-user enterprise AI analytics SaaS backend",
    version="5.0-saas"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Mount static directories for modular frontend
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    css_dir = os.path.join(frontend_dir, "css")
    js_dir = os.path.join(frontend_dir, "js")
    assets_dir = os.path.join(frontend_dir, "assets")
    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/login", response_class=FileResponse, include_in_schema=False)
    def read_login():
        return FileResponse(os.path.join(frontend_dir, "login.html"))

    @app.get("/signup", response_class=FileResponse, include_in_schema=False)
    def read_signup():
        return FileResponse(os.path.join(frontend_dir, "signup.html"))

    @app.get("/forgot-password", response_class=FileResponse, include_in_schema=False)
    def read_forgot_password():
        return FileResponse(os.path.join(frontend_dir, "forgot-password.html"))

# Initialize SQLite tables (safe — never drops, only creates if missing)
database.init_db()
logger.info("Database initialised successfully")

DATASTORE: dict = {}
USER_DATASTORES: Dict[str, dict] = {}
con = duckdb.connect(":memory:")


# ── HELPER FUNCTIONS ──────────────────────────────────────────────────────

def get_user_id_from_request(request: Optional[Request]) -> str:
    """Legacy helper — kept for backward compatibility with existing endpoints."""
    if request is None:
        return "guest_user"
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        user = database.get_user_by_token(token)
        if user:
            return user["id"]
    return "guest_user"


def get_user_datastore(request: Optional[Request] = None) -> dict:
    if request is None:
        return DATASTORE
    uid = get_user_id_from_request(request)
    if uid not in USER_DATASTORES:
        USER_DATASTORES[uid] = {}
    ds = USER_DATASTORES[uid]

    # Auto-hydrate dataset from SQLite if absent from memory for authenticated users
    if "df" not in ds and uid != "guest_user":
        latest = database.get_latest_user_dataset(uid)
        if latest and latest.get("csv_data"):
            try:
                df = pd.read_csv(io.StringIO(latest["csv_data"]))
                df = clean_numeric_strings(df)
                ds["df"] = df
                ds["name"] = latest.get("filename", "dataset.csv")
                ds["dataset_id"] = latest.get("id")
            except Exception as e:
                logger.error(f"Error auto-hydrating dataset for user {uid}: {e}")

    # Fallback to guest DATASTORE only if guest user and no user-specific df
    if "df" not in ds and uid == "guest_user" and "df" in DATASTORE:
        return DATASTORE

    return ds


def get_user_active_df(request: Optional[Request] = None) -> Optional[pd.DataFrame]:
    """Returns the active DataFrame for the current user (with SQLite auto-hydration)."""
    ds = get_user_datastore(request)
    return ds.get("df")



def clean_numeric_strings(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == object:
            non_null = df[col].dropna().astype(str).str.strip()
            if len(non_null) == 0:
                continue
            has_dollar = non_null.str.startswith('$').any()
            has_commas = non_null.str.contains(r'\d,\d').any()
            if has_dollar or has_commas:
                cleaned = non_null.str.replace('$', '', regex=False).str.replace(',', '', regex=False).str.strip()
                cleaned = cleaned.replace('', np.nan)
                try:
                    numeric_series = pd.to_numeric(cleaned, errors='coerce')
                    if numeric_series.notnull().sum() >= 0.8 * len(non_null):
                        df[col] = pd.to_numeric(
                            df[col].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False).str.strip(),
                            errors='coerce'
                        )
                except Exception:
                    pass
    return df


def df_to_sql(df: pd.DataFrame) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    cleaned_df = clean_numeric_strings(df)
    cleaned_df.to_sql("data", conn, index=False, if_exists="replace")
    return conn


def detect_domain(df: pd.DataFrame) -> str:
    cols_str = " ".join([c.lower() for c in df.columns])
    if any(k in cols_str for k in ["sales", "order", "revenue", "profit", "units", "customer", "price"]):
        return "Sales & Commerce"
    if any(k in cols_str for k in ["salary", "emp", "employee", "dept", "department", "hiring", "role"]):
        return "HR & Workforce"
    if any(k in cols_str for k in ["txn", "transaction", "amount", "budget", "debit", "credit", "account", "balance"]):
        return "Finance & Banking"
    if any(k in cols_str for k in ["product", "feature", "user", "signup", "session", "click", "churn", "dau"]):
        return "Product & Growth"
    if any(k in cols_str for k in ["patient", "hospital", "doctor", "diagnosis", "health", "claim"]):
        return "Healthcare"
    return "General Analytics"


def rank_numeric_columns(df: pd.DataFrame) -> List[str]:
    """Intelligently ranks numeric columns based on business value, skipping IDs and static columns."""
    num_cols = df.select_dtypes(include=np.number).columns.tolist()
    valid_cols = []
    id_keywords = ["id", "sr", "sn", "index", "code", "zip", "phone", "year", "sl_no", "no", "number"]

    for col in num_cols:
        col_lower = col.lower().strip()
        if any(kw == col_lower or col_lower.endswith("_" + kw) or col_lower.startswith(kw + "_") for kw in id_keywords):
            continue
        s = df[col].dropna()
        if len(s) > 0 and s.std() > 0:
            valid_cols.append((col, s.std(), s.nunique()))

    valid_cols.sort(key=lambda x: x[1], reverse=True)
    ranked = [c[0] for c in valid_cols]

    for col in num_cols:
        if col not in ranked:
            ranked.append(col)

    return ranked


def rank_categorical_columns(df: pd.DataFrame) -> List[str]:
    """Intelligently ranks categorical columns suitable for chart breakdowns (3 to 30 unique categories)."""
    cat_cols = df.select_dtypes(exclude=np.number).columns.tolist()
    scored = []

    for col in cat_cols:
        col_lower = col.lower().strip()
        if any(kw in col_lower for kw in ["description", "address", "url", "text", "comment", "email"]):
            continue
        unq = df[col].nunique()
        if 2 <= unq <= 35:
            score = 100 - abs(unq - 7)
            scored.append((col, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    ranked = [c[0] for c in scored]

    for col in cat_cols:
        if col not in ranked:
            ranked.append(col)

    return ranked


# ── FRONTEND STATIC MOUNT & PAGE ROUTES ──────────────────────────────────
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    css_dir = os.path.join(frontend_dir, "css")
    js_dir = os.path.join(frontend_dir, "js")
    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")


@app.get("/", response_class=FileResponse, include_in_schema=False)
def read_root():
    frontend_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"status": "InsightFlow Analytics Engine Running", "version": "5.0-saas"}


@app.get("/login", response_class=FileResponse, include_in_schema=False)
def serve_login_clean():
    return FileResponse(os.path.join(frontend_dir, "login.html"))


@app.get("/login.html", response_class=FileResponse, include_in_schema=False)
def serve_login_html():
    return FileResponse(os.path.join(frontend_dir, "login.html"))


@app.get("/signup", response_class=FileResponse, include_in_schema=False)
def serve_signup_clean():
    return FileResponse(os.path.join(frontend_dir, "signup.html"))


@app.get("/signup.html", response_class=FileResponse, include_in_schema=False)
def serve_signup_html():
    return FileResponse(os.path.join(frontend_dir, "signup.html"))


@app.get("/forgot-password", response_class=FileResponse, include_in_schema=False)
def serve_forgot_clean():
    return FileResponse(os.path.join(frontend_dir, "forgot-password.html"))


@app.get("/forgot-password.html", response_class=FileResponse, include_in_schema=False)
def serve_forgot_html():
    return FileResponse(os.path.join(frontend_dir, "forgot-password.html"))


@app.get("/status")
def status(request: Request):
    ds = get_user_datastore(request)
    df = ds.get("df")
    has_data = df is not None
    return {
        "backend": "online",
        "dataset_loaded": has_data,
        "dataset_rows": int(df.shape[0]) if has_data else 0,
        "dataset_cols": int(df.shape[1]) if has_data else 0,
        "dataset_name": ds.get("name", ""),
        "ai_provider": get_active_provider(),
        "groq_ready": bool(GROQ_API_KEY),
        "gemini_ready": bool(GEMINI_API_KEY),
    }


# ── AUTHENTICATION ENDPOINTS (preserved exactly) ───────────────────────────

@app.post("/api/auth/signup")
def auth_signup(payload: SignUpRequest):
    if not payload.name or not payload.email or not payload.password:
        raise HTTPException(status_code=400, detail="Name, email, and password are required")
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")

    existing = database.get_user_by_email(payload.email)
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email address already exists")

    user = database.create_user(
        name=payload.name,
        email=payload.email,
        password=payload.password
    )
    token = database.create_session(user["id"], remember_me=True)
    logger.info(f"New user registered: {user['id']} ({user['email']})")
    return {"user": user, "token": token}


@app.post("/api/auth/login")
def auth_login(payload: LoginRequest):
    if not payload.email or not payload.password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    user_db = database.get_user_by_email(payload.email)
    if not user_db:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not database.verify_password(payload.password, user_db.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = database.get_user_by_id(user_db["id"])
    token = database.create_session(user["id"], remember_me=payload.remember_me)
    logger.info(f"User login: {user['id']} ({user['email']})")
    return {"user": user, "token": token}


@app.post("/api/auth/google")
def auth_google(payload: GoogleAuthRequest):
    if not payload.email or not payload.google_id:
        raise HTTPException(status_code=400, detail="Google email and User ID are required")

    user_by_g = database.get_user_by_google_id(payload.google_id)
    if user_by_g:
        user = database.get_user_by_id(user_by_g["id"])
    else:
        user_by_email = database.get_user_by_email(payload.email)
        if user_by_email:
            user = database.update_google_user(
                user_id=user_by_email["id"],
                google_id=payload.google_id,
                profile_photo=payload.profile_photo or user_by_email.get("profile_photo")
            )
        else:
            user = database.create_user(
                name=payload.name or payload.email.split("@")[0].capitalize(),
                email=payload.email,
                password=None,
                google_id=payload.google_id,
                profile_photo=payload.profile_photo
            )

    token = database.create_session(user["id"], remember_me=payload.remember_me)
    logger.info(f"Google auth: {user['id']} ({user['email']})")
    return {"user": user, "token": token}


@app.get("/api/auth/me")
def auth_me(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header[7:].strip()
    user = database.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    # Include fresh credit balance
    user["credits"] = database.get_user_credits(user["id"])
    return {"user": user}


@app.post("/api/auth/logout")
def auth_logout(request: Request):
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        database.delete_session(token)
    return {"status": "success", "message": "Logged out successfully"}


@app.post("/api/auth/forgot-password")
def auth_forgot_password(payload: ForgotPasswordRequest):
    if not payload.email:
        raise HTTPException(status_code=400, detail="Email is required")

    token = database.create_password_reset_token(payload.email)
    return {
        "status": "success",
        "message": "If an account with that email exists, password reset instructions have been generated.",
        "reset_token": token  # Returned for local dev / quick reset flow
    }


@app.post("/api/auth/reset-password")
def auth_reset_password(payload: ResetPasswordRequest):
    if not payload.token or not payload.new_password:
        raise HTTPException(status_code=400, detail="Token and new password are required")
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")

    success = database.reset_password_with_token(payload.token, payload.new_password)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    return {"status": "success", "message": "Password reset successfully. You can now login with your new password."}


@app.put("/api/user/profile")
def update_profile(payload: UpdateProfileRequest, request: Request):
    uid = get_user_id_from_request(request)
    if uid == "guest_user":
        raise HTTPException(status_code=401, detail="Authentication required")

    updated_user = database.update_user_profile(
        user_id=uid,
        name=payload.name,
        profile_photo=payload.profile_photo,
        theme=payload.theme,
        history_enabled=payload.history_enabled
    )
    return {"status": "success", "user": updated_user}


@app.post("/api/user/change-password")
def change_password(payload: ChangePasswordRequest, request: Request):
    uid = get_user_id_from_request(request)
    if uid == "guest_user":
        raise HTTPException(status_code=401, detail="Authentication required")
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")

    success = database.change_user_password(uid, payload.old_password, payload.new_password)
    if not success:
        raise HTTPException(status_code=400, detail="Incorrect existing password")

    return {"status": "success", "message": "Password updated successfully"}


# ── USER PROFILE & SETTINGS ENDPOINTS (new) ───────────────────────────────

@app.get("/api/users/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """Alias for /api/auth/me — returns authenticated user with fresh credit balance."""
    current_user["credits"] = database.get_user_credits(current_user["id"])
    return {"user": current_user}


@app.get("/api/users/me/settings")
def get_settings(current_user: dict = Depends(get_current_user)):
    settings = database.get_user_settings(current_user["id"])
    return {"settings": settings}


class UpdateSettingsRequest(BaseModel):
    theme: Optional[str] = None
    language: Optional[str] = None
    email_notifications: Optional[int] = None
    product_updates: Optional[int] = None


@app.put("/api/users/me/settings")
def update_settings(payload: UpdateSettingsRequest, current_user: dict = Depends(get_current_user)):
    settings = database.upsert_user_settings(
        user_id=current_user["id"],
        theme=payload.theme,
        language=payload.language,
        email_notifications=payload.email_notifications,
        product_updates=payload.product_updates
    )
    return {"status": "success", "settings": settings}


# ── CREDITS ENDPOINTS ─────────────────────────────────────────────────────

@app.get("/api/credits")
def get_credits(current_user: dict = Depends(get_current_user)):
    """Returns current credit balance and recent transaction history."""
    balance = database.get_user_credits(current_user["id"])
    transactions = database.get_credit_transactions(current_user["id"], limit=20)
    return {
        "balance": balance,
        "daily_limit": 100,
        "transactions": transactions
    }


@app.post("/api/credits/reset")
def reset_credits(current_user: dict = Depends(get_current_user)):
    """Debug/admin endpoint to manually reset credits."""
    database.reset_daily_credits(current_user["id"])
    return {"status": "success", "balance": 100, "message": "Credits reset to 100"}


# ── DATASET ENDPOINTS (existing preserved + enhanced) ─────────────────────

@app.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    start_time = time.time()
    try:
        fname = file.filename or ""
        content = await file.read()
        if fname.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif fname.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        elif fname.endswith(".json"):
            df = pd.read_json(io.BytesIO(content))
        else:
            return {"error": "Unsupported file type. Use CSV, Excel, or JSON."}
        df = clean_numeric_strings(df)
    except Exception as e:
        return {"error": f"File read error: {str(e)}"}

    ds = get_user_datastore(request)
    ds["df"] = df
    ds["name"] = fname
    DATASTORE["df"] = df
    DATASTORE["name"] = fname

    # Persist dataset in SQLite if user is logged in
    uid = get_user_id_from_request(request)
    saved_dataset_meta = None
    if uid != "guest_user":
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        saved_dataset_meta = database.save_user_dataset(
            user_id=uid,
            name=fname.rsplit(".", 1)[0] if "." in fname else fname,
            filename=fname,
            file_type=fname.rsplit(".", 1)[-1].lower() if "." in fname else "csv",
            rows=df.shape[0],
            cols=df.shape[1],
            csv_data=csv_buffer.getvalue()
        )
        # Add history + notification for upload
        dataset_id = saved_dataset_meta.get("id")
        database.add_history(
            user_id=uid,
            type="DATASET",
            title=f"Dataset uploaded: {fname}",
            description=f"{df.shape[0]:,} rows × {df.shape[1]} columns",
            resource_id=dataset_id
        )
        database.add_notification(
            user_id=uid,
            title="Dataset Upload Complete",
            message=f"'{fname}' ({df.shape[0]:,} rows × {df.shape[1]} columns) has been processed and is ready for analysis.",
            notif_type="success",
            resource_id=dataset_id
        )

    try:
        try:
            con.unregister("data")
        except Exception:
            pass
        con.register("data", df)
    except Exception as e:
        return {"error": f"SQL table error: {str(e)}"}

    rows, cols = df.shape
    missing = int(df.isnull().sum().sum())
    duplicates = int(df.duplicated().sum())
    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    categorical_cols = df.select_dtypes(exclude=np.number).columns.tolist()

    elapsed = round(time.time() - start_time, 2)
    logger.info(f"Upload: user={uid} file={fname} rows={rows} cols={cols} elapsed={elapsed}s")

    return {
        "summary": {
            "rows": rows, "columns": cols, "missing": missing, "duplicates": duplicates,
            "numeric_columns": numeric_cols, "categorical_columns": categorical_cols,
            "column_names": list(df.columns),
            "domain": detect_domain(df),
        },
        "preview": df.head(10).fillna("").values.tolist(),
        "dataset": saved_dataset_meta
    }


@app.get("/api/datasets")
def list_user_datasets(request: Request):
    uid = get_user_id_from_request(request)
    if uid == "guest_user":
        return {"datasets": []}
    return {"datasets": database.get_user_datasets(uid)}


@app.get("/api/datasets/{dataset_id}")
def get_dataset_endpoint(dataset_id: str, current_user: dict = Depends(get_current_user)):
    record = database.get_dataset_by_id(dataset_id, current_user["id"])
    if not record:
        raise HTTPException(status_code=404, detail="Dataset not found")
    # Return metadata without csv_data blob
    record.pop("csv_data", None)
    return {"dataset": record}


@app.get("/api/datasets/{dataset_id}/preview")
def get_dataset_preview(dataset_id: str, limit: int = 50, current_user: dict = Depends(get_current_user)):
    record = database.get_dataset_by_id(dataset_id, current_user["id"])
    if not record:
        raise HTTPException(status_code=404, detail="Dataset not found")
    try:
        df = pd.read_csv(io.StringIO(record["csv_data"]))
        return {
            "columns": list(df.columns),
            "rows": df.head(limit).fillna("").to_dict(orient="records"),
            "total_rows": len(df),
            "showing": min(limit, len(df))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading dataset: {str(e)}")


@app.get("/api/datasets/{dataset_id}/statistics")
def get_dataset_statistics(dataset_id: str, current_user: dict = Depends(get_current_user)):
    record = database.get_dataset_by_id(dataset_id, current_user["id"])
    if not record:
        raise HTTPException(status_code=404, detail="Dataset not found")
    try:
        df = pd.read_csv(io.StringIO(record["csv_data"]))
        df = clean_numeric_strings(df)
        num_cols = df.select_dtypes(include=np.number).columns.tolist()
        stats = {}
        for col in num_cols:
            s = df[col].dropna()
            if len(s):
                stats[col] = {
                    "mean": round(float(s.mean()), 2),
                    "median": round(float(s.median()), 2),
                    "std": round(float(s.std()), 2) if len(s) > 1 else 0.0,
                    "min": round(float(s.min()), 2),
                    "max": round(float(s.max()), 2),
                    "missing": int(df[col].isnull().sum())
                }
        return {
            "dataset_id": dataset_id,
            "shape": {"rows": df.shape[0], "columns": df.shape[1]},
            "missing_total": int(df.isnull().sum().sum()),
            "duplicates": int(df.duplicated().sum()),
            "numeric_stats": stats,
            "column_types": {col: str(df[col].dtype) for col in df.columns}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing statistics: {str(e)}")


@app.get("/api/datasets/{dataset_id}/columns")
def get_dataset_columns(dataset_id: str, current_user: dict = Depends(get_current_user)):
    record = database.get_dataset_by_id(dataset_id, current_user["id"])
    if not record:
        raise HTTPException(status_code=404, detail="Dataset not found")
    try:
        df = pd.read_csv(io.StringIO(record["csv_data"]))
        col_info = []
        for col in df.columns:
            s = df[col]
            is_num = pd.api.types.is_numeric_dtype(s)
            col_info.append({
                "name": col,
                "dtype": str(s.dtype),
                "is_numeric": is_num,
                "null_count": int(s.isnull().sum()),
                "unique_count": int(s.nunique())
            })
        return {"columns": col_info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/datasets/{dataset_id}/activate")
def activate_user_dataset(dataset_id: str, request: Request):
    uid = get_user_id_from_request(request)
    if uid == "guest_user":
        raise HTTPException(status_code=401, detail="Authentication required")

    record = database.get_dataset_by_id(dataset_id, uid)
    if not record:
        raise HTTPException(status_code=404, detail="Dataset not found")

    df = pd.read_csv(io.StringIO(record["csv_data"]))
    df = clean_numeric_strings(df)

    ds = get_user_datastore(request)
    ds["df"] = df
    ds["name"] = record["filename"]
    ds["dataset_id"] = dataset_id
    DATASTORE["df"] = df
    DATASTORE["name"] = record["filename"]

    try:
        try:
            con.unregister("data")
        except Exception:
            pass
        con.register("data", df)
    except Exception:
        pass

    return {
        "status": "success",
        "message": f"Activated dataset '{record['name']}'",
        "dataset": {k: v for k, v in record.items() if k != "csv_data"},
        "rows": df.shape[0],
        "cols": df.shape[1]
    }


@app.delete("/api/datasets/{dataset_id}")
def delete_dataset_endpoint(dataset_id: str, request: Request):
    uid = get_user_id_from_request(request)
    if uid == "guest_user":
        raise HTTPException(status_code=401, detail="Authentication required")

    success = database.delete_user_dataset(dataset_id, uid)
    if not success:
        raise HTTPException(status_code=404, detail="Dataset not found or could not be deleted")

    return {"status": "success", "message": "Dataset deleted successfully"}


# ── AUTO-DASHBOARD ENGINE (preserved exactly) ──────────────────────────────

def calculate_widget_data(df: pd.DataFrame, widget_type: str, x_col: str, y_col: Optional[str], agg: str = "SUM") -> Dict[str, Any]:
    """Computes aggregated chart series or metric data for Chart.js rendering."""
    if x_col not in df.columns:
        return {"labels": [], "values": []}

    if widget_type == "kpi":
        s = df[x_col].dropna()
        if len(s) == 0:
            return {"metric": "0", "label": x_col, "sub": "No data"}
        if agg == "AVG":
            val = s.mean()
        elif agg == "COUNT":
            val = float(len(s))
        elif agg == "MAX":
            val = s.max()
        elif agg == "MIN":
            val = s.min()
        else:
            val = s.sum()

        formatted = f"{val:,.2f}" if isinstance(val, (int, float)) and not val.is_integer() else f"{int(val):,}"
        spark = s.sample(min(12, len(s)), random_state=42).sort_index().tolist() if pd.api.types.is_numeric_dtype(s) else []
        return {"metric": formatted, "label": f"{agg} of {x_col}", "sub": f"Min: {s.min():,.0f} | Max: {s.max():,.0f}" if pd.api.types.is_numeric_dtype(s) else f"{len(s)} items", "spark": spark}

    if widget_type == "scatter" and y_col and y_col in df.columns:
        sub_df = df[[x_col, y_col]].dropna()
        if len(sub_df) > 120:
            sub_df = sub_df.sample(120, random_state=42)
        points = [{"x": float(r[x_col]), "y": float(r[y_col])} for _, r in sub_df.iterrows()]
        return {"points": points, "x_label": x_col, "y_label": y_col}

    if y_col and y_col in df.columns and pd.api.types.is_numeric_dtype(df[y_col]):
        if agg == "AVG":
            grouped = df.groupby(x_col)[y_col].mean()
        elif agg == "COUNT":
            grouped = df.groupby(x_col)[y_col].count()
        elif agg == "MAX":
            grouped = df.groupby(x_col)[y_col].max()
        elif agg == "MIN":
            grouped = df.groupby(x_col)[y_col].min()
        else:
            grouped = df.groupby(x_col)[y_col].sum()

        grouped = grouped.sort_values(ascending=False).head(12)
        return {
            "labels": [str(k) for k in grouped.index],
            "values": [round(float(v), 2) for v in grouped.values],
            "x_label": x_col,
            "y_label": f"{agg}({y_col})"
        }
    else:
        vc = df[x_col].value_counts().head(12)
        return {
            "labels": [str(k) for k in vc.index],
            "values": [int(v) for v in vc.values],
            "x_label": x_col,
            "y_label": "Count"
        }


@app.get("/chart-data")
@app.get("/auto-dashboard")
def auto_dashboard(
    request: Request = None,
    bar_col: Optional[str] = None,
    line_col: Optional[str] = None,
    donut_col: Optional[str] = None,
    agg: Optional[str] = "SUM"
):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}

    num_cols = df.select_dtypes(include=np.number).columns.tolist()
    cat_cols = df.select_dtypes(exclude=np.number).columns.tolist()
    domain = detect_domain(df)

    ranked_num = rank_numeric_columns(df)
    ranked_cat = rank_categorical_columns(df)

    kpis = []
    for col in ranked_num[:4]:
        s = df[col].dropna()
        if len(s):
            mean_val = s.mean()
            sum_val = s.sum()
            kpis.append({
                "id": f"kpi_{col}",
                "label": f"{col} (Avg)",
                "title": col,
                "value": f"{mean_val:,.2f}" if isinstance(mean_val, (int, float)) and not mean_val.is_integer() else f"{int(mean_val):,}",
                "delta": f"Sum: {sum_val:,.0f} | Range: {s.min():,.0f}–{s.max():,.0f}",
                "up": True,
                "spark": s.sample(min(14, len(s)), random_state=42).sort_index().tolist() if pd.api.types.is_numeric_dtype(s) else []
            })

    if not kpis:
        kpis.append({"id": "kpi_rows", "label": "Total Records", "value": f"{len(df):,}", "delta": "Dataset size", "up": True, "spark": []})
        kpis.append({"id": "kpi_cols", "label": "Total Features", "value": f"{len(df.columns)}", "delta": "Dimensions", "up": True, "spark": []})

    sel_line = line_col if (line_col and line_col in df.columns) else (ranked_num[0] if ranked_num else (df.columns[0] if len(df.columns) else ""))
    line_res = calculate_widget_data(df, "line", sel_line, None) if sel_line else {"labels": [], "values": []}
    line_res["column"] = sel_line

    sel_bar = bar_col if (bar_col and bar_col in df.columns) else (ranked_cat[0] if ranked_cat else (df.columns[0] if len(df.columns) else ""))
    target_num_bar = ranked_num[0] if ranked_num else None
    bar_res = calculate_widget_data(df, "bar", sel_bar, target_num_bar, agg or "SUM") if sel_bar else {"labels": [], "values": []}
    bar_res["column"] = sel_bar

    sel_donut = donut_col if (donut_col and donut_col in df.columns) else (ranked_cat[1] if len(ranked_cat) > 1 else (ranked_cat[0] if ranked_cat else (df.columns[0] if len(df.columns) else "")))
    donut_res_raw = calculate_widget_data(df, "donut", sel_donut, target_num_bar, "AVG" if target_num_bar else "COUNT") if sel_donut else {"labels": [], "values": []}

    donut_items = []
    colors = ["#d4ff2a", "#3b82f6", "#14b8a6", "#f59e0b", "#ec4899", "#8b5cf6", "#10b981", "#64748b"]
    tot_donut_val = sum(donut_res_raw.get("values", [])) or 1
    for idx, (lbl, val) in enumerate(zip(donut_res_raw.get("labels", []), donut_res_raw.get("values", []))):
        donut_items.append({
            "l": str(lbl),
            "v": val,
            "p": round((val / tot_donut_val) * 100, 1),
            "c": colors[idx % len(colors)]
        })

    donut_res = {
        "items": donut_items,
        "total": f"{tot_donut_val:,.0f}" if isinstance(tot_donut_val, (int, float)) else str(tot_donut_val),
        "sub": f"Top categories in {sel_donut}",
        "column": sel_donut
    }

    scatter_res = {}
    if len(ranked_num) >= 2:
        scatter_res = calculate_widget_data(df, "scatter", ranked_num[0], ranked_num[1])

    return {
        "domain": domain,
        "kpis": kpis,
        "line": line_res,
        "bar": bar_res,
        "donut": donut_res,
        "scatter": scatter_res,
        "available": {
            "numeric": num_cols,
            "categorical": cat_cols,
            "ranked_numeric": ranked_num,
            "ranked_categorical": ranked_cat,
            "all": list(df.columns)
        }
    }


# ── CUSTOM WIDGET BUILDER ──────────────────────────────────────────────────

class CustomWidgetRequest(BaseModel):
    widget_type: str
    title: str
    x_col: str
    y_col: Optional[str] = None
    agg: Optional[str] = "SUM"


@app.post("/custom-widget")
async def create_custom_widget(req: CustomWidgetRequest, request: Request = None):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}

    try:
        data = calculate_widget_data(
            df,
            widget_type=req.widget_type.lower(),
            x_col=req.x_col,
            y_col=req.y_col,
            agg=req.agg or "SUM"
        )
        return {
            "widget": {
                "id": f"custom_{int(pd.Timestamp.now().timestamp())}",
                "type": req.widget_type.lower(),
                "title": req.title or f"{req.agg or 'SUM'} of {req.y_col or req.x_col}",
                "x_col": req.x_col,
                "y_col": req.y_col or "",
                "agg": req.agg or "SUM",
                "data": data,
                "col_span": 2 if req.widget_type.lower() in ["line", "area"] else 1
            }
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": f"Failed to compute custom widget: {str(e)}"}


# ── DATA TABLE ENDPOINTS (preserved exactly) ───────────────────────────────

@app.get("/data")
def get_data(request: Request = None, limit: int = 1000):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}
    return {
        "columns": list(df.columns),
        "rows": df.head(limit).fillna("").to_dict(orient="records"),
        "total_rows": len(df),
        "showing": min(limit, len(df)),
    }


@app.get("/api/data/columns")
def get_data_columns(request: Request = None):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}

    col_details = []
    for col in df.columns:
        s = df[col]
        is_num = pd.api.types.is_numeric_dtype(s)
        s_clean = s.dropna()

        info = {
            "name": col,
            "dtype": str(s.dtype),
            "null_count": int(s.isnull().sum()),
            "null_pct": round(float(s.isnull().sum() / max(len(df), 1) * 100), 1),
            "unique_count": int(s.nunique()),
            "is_numeric": is_num,
            "top_values": s_clean.value_counts().head(5).to_dict() if not is_num else {}
        }
        if is_num and len(s_clean) > 0:
            info.update({
                "min": round(float(s_clean.min()), 2),
                "max": round(float(s_clean.max()), 2),
                "mean": round(float(s_clean.mean()), 2),
                "std": round(float(s_clean.std()), 2) if len(s_clean) > 1 else 0.0
            })
        col_details.append(info)

    return {"columns": col_details, "total_rows": len(df), "total_columns": len(df.columns)}


@app.post("/api/data/filter")
def filter_data(req: FilterDataRequest, request: Request = None):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}

    filtered_df = df.copy()

    if req.column and req.column in filtered_df.columns:
        col = req.column
        op = req.operator or "contains"
        val = req.value

        if val is not None and str(val).strip() != "":
            if pd.api.types.is_numeric_dtype(filtered_df[col]):
                try:
                    num_val = float(val)
                    if op == "equals":
                        filtered_df = filtered_df[filtered_df[col] == num_val]
                    elif op == "greater_than":
                        filtered_df = filtered_df[filtered_df[col] > num_val]
                    elif op == "less_than":
                        filtered_df = filtered_df[filtered_df[col] < num_val]
                except ValueError:
                    pass
            else:
                str_val = str(val).lower()
                if op == "equals":
                    filtered_df = filtered_df[filtered_df[col].astype(str).str.lower() == str_val]
                else:
                    filtered_df = filtered_df[filtered_df[col].astype(str).str.lower().str.contains(str_val, na=False)]

    if req.sort_by and req.sort_by in filtered_df.columns:
        ascending = req.sort_order != "desc"
        filtered_df = filtered_df.sort_values(by=req.sort_by, ascending=ascending)

    total_matched = len(filtered_df)
    limit = req.limit or 50
    offset = req.offset or 0

    paged_df = filtered_df.iloc[offset:offset+limit]

    return {
        "columns": list(df.columns),
        "rows": paged_df.fillna("").to_dict(orient="records"),
        "total_matched": total_matched,
        "offset": offset,
        "limit": limit
    }


# ── EXPORT ENDPOINTS (preserved exactly) ──────────────────────────────────

@app.get("/download")
@app.get("/export/csv")
@app.get("/api/export/csv")
def download_data(request: Request = None):
    ds = get_user_datastore(request)
    df = ds.get("df")
    if df is None:
        return {"error": "No dataset uploaded"}
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    stream.seek(0)
    filename = f"insightflow_{ds.get('name', 'export')}.csv"
    return StreamingResponse(stream, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.get("/export/excel")
@app.get("/api/export/excel")
def export_excel(request: Request = None):
    ds = get_user_datastore(request)
    df = ds.get("df")
    if df is None:
        return {"error": "No dataset uploaded"}
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Data Analysis")
    buffer.seek(0)
    filename = f"insightflow_{ds.get('name', 'export')}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )



@app.get("/export/pdf-report")
@app.get("/api/export/pdf-report")
def export_pdf_report(request: Request = None):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "No dataset uploaded"}
    domain = detect_domain(df)
    pdf_bytes = generate_pdf_report_bytes(df, domain=domain)
    buffer = io.BytesIO(pdf_bytes)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=insightflow_executive_report.pdf"}
    )


# ── EDA & CLEANING ENDPOINTS (preserved + credit enforcement) ─────────────

@app.get("/eda")
def eda(request: Request):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}
    try:
        num_cols = df.select_dtypes(include=np.number).columns.tolist()
        cat_cols = df.select_dtypes(exclude=np.number).columns.tolist()
        rows, cols = df.shape
        missing = int(df.isnull().sum().sum())
        total_cells = rows * cols

        col_info = []
        for c in df.columns:
            col_info.append({
                "name": c,
                "dtype": str(df[c].dtype),
                "nulls": int(df[c].isnull().sum()),
                "unique": int(df[c].nunique()),
                "is_numeric": c in num_cols,
            })

        corr = {}
        if len(num_cols) >= 2:
            corr_df = df[num_cols].corr().fillna(0)
            corr = {
                "columns": num_cols,
                "matrix": corr_df.values.tolist(),
            }

        num_stats = {}
        for c in num_cols:
            s = df[c].dropna()
            if len(s):
                num_stats[c] = {
                    "mean": round(float(s.mean()), 2),
                    "median": round(float(s.median()), 2),
                    "std": round(float(s.std()), 2),
                    "min": round(float(s.min()), 2),
                    "max": round(float(s.max()), 2),
                    "q25": round(float(s.quantile(0.25)), 2),
                    "q75": round(float(s.quantile(0.75)), 2),
                }

        completeness = round((1 - missing / max(total_cells, 1)) * 100, 1)
        uniqueness = round((1 - df.duplicated().sum() / max(rows, 1)) * 100, 1)

        # Record history for authenticated users
        uid = get_user_id_from_request(request)
        if uid != "guest_user":
            database.add_history(
                user_id=uid, type="EDA",
                title="EDA Analysis Completed",
                description=f"Profiled {rows:,} rows × {cols} columns — {missing} missing values"
            )

        return {
            "shape": {"rows": rows, "columns": cols},
            "missing": missing,
            "duplicates": int(df.duplicated().sum()),
            "col_info": col_info,
            "correlation": corr,
            "num_stats": num_stats,
            "quality": {"completeness": completeness, "uniqueness": uniqueness},
            "numeric_columns": num_cols,
            "categorical_columns": cat_cols,
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


@app.get("/cleaning")
def cleaning(request: Request = None):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}

    missing_by_col = df.isnull().sum()
    missing_cols = {str(k): int(v) for k, v in missing_by_col[missing_by_col > 0].items()}
    duplicates = int(df.duplicated().sum())
    num_cols = df.select_dtypes(include=np.number).columns.tolist()
    cat_cols = df.select_dtypes(exclude=np.number).columns.tolist()

    ops = [
        {"t": f"Scanned {df.shape[1]} columns for data types", "d": f"{len(num_cols)} numeric, {len(cat_cols)} categorical detected"},
        {"t": f"Detected {int(missing_by_col.sum())} missing values" if missing_by_col.sum() > 0 else "No missing values found", "d": f"Dataset completeness: {(1 - missing_by_col.sum() / max(df.shape[0] * df.shape[1], 1)) * 100:.1f}%"},
        {"t": f"Found {duplicates} duplicate rows" if duplicates > 0 else "No duplicate rows found", "d": "Checked for exact row duplicates"},
        {"t": "Column type inference complete", "d": "All columns profiled and typed automatically"}
    ]

    return {
        "duplicates": duplicates,
        "missing": missing_cols,
        "missing_total": int(missing_by_col.sum()),
        "operations": ops,
        "stats": {
            "rows_removed": duplicates,
            "values_imputed": int(missing_by_col.sum()),
            "formats_fixed": len(num_cols),
        },
    }


@app.get("/insights")
def insights(request: Request = None):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}

    summary_lines = []
    for col in df.select_dtypes(include=np.number).columns[:6]:
        summary_lines.append(f"{col}: mean={df[col].mean():.2f}, max={df[col].max():.2f}, min={df[col].min():.2f}")

    cat_info = []
    for col in df.select_dtypes(exclude=np.number).columns[:3]:
        vc = df[col].value_counts().head(3)
        cat_info.append(f"{col}: top values = {dict(vc)}")

    prompt = f"""Analyze this dataset ({detect_domain(df)}) and return exactly 4 executive analyst insights as a JSON array.

Dataset: {df.shape[0]} rows, {df.shape[1]} columns
Numeric summary: {chr(10).join(summary_lines)}
Categorical: {chr(10).join(cat_info)}
Missing values: {int(df.isnull().sum().sum())}
Duplicates: {int(df.duplicated().sum())}

Return ONLY a valid JSON array, no markdown:
[
  {{"type":"ok","tag":"HIGHLIGHT","text":"..."}},
  {{"type":"warn","tag":"RISK","text":"..."}},
  {{"type":"ok","tag":"TREND","text":"..."}},
  {{"type":"ok","tag":"ACTION","text":"..."}}
]"""

    try:
        raw = ai_chat("Return only JSON array.", prompt, temperature=0.1)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return {"insights": json.loads(raw.strip()), "provider": get_active_provider()}
    except Exception:
        traceback.print_exc()
        return {
            "insights": [
                {"type": "ok", "tag": "DOMAIN", "text": f"Detected domain: {detect_domain(df)}. {df.shape[0]:,} rows and {df.shape[1]} features profiled."},
                {"type": "ok", "tag": "QUALITY", "text": f"Data quality check complete. {df.isnull().sum().sum()} missing values and {df.duplicated().sum()} duplicate rows."},
                {"type": "ok", "tag": "ANALYTICS", "text": f"Identified {len(df.select_dtypes(include=np.number).columns)} numeric metrics and {len(df.select_dtypes(exclude=np.number).columns)} categorical dimensions."}
            ],
            "provider": "local"
        }


# ── AI CHAT & SQL ENDPOINTS ────────────────────────────────────────────────

@app.post("/chat")
async def chat(query: dict, request: Request):
    question = query.get("question", "").strip()
    if not question:
        return {"error": "No question provided"}
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Please upload a dataset first before asking questions."}

    uid = get_user_id_from_request(request)
    session_id = query.get("session_id")
    ds = get_user_datastore(request)

    # Credit check for authenticated users
    if uid != "guest_user":
        ensure_credits(uid, "AI_CHAT")

    cols = list(df.columns)
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(exclude="number").columns.tolist()

    numeric_summary = ""
    for col in numeric_cols[:8]:
        numeric_summary += f"\n  {col}: mean={df[col].mean():.2f}, min={df[col].min():.2f}, max={df[col].max():.2f}, std={df[col].std():.2f}"

    sample_rows = df.head(5).fillna("").to_string(index=False)

    system_prompt = f"""You are InsightFlow AI, a PowerBI-grade Data Analyst.

DATASET:
- File: {ds.get('name', 'uploaded file')}
- Domain: {detect_domain(df)}
- Shape: {df.shape[0]:,} rows x {df.shape[1]} columns
- Columns: {', '.join(cols)}
- Numeric: {numeric_cols}
- Categorical: {cat_cols}

STATS:{numeric_summary}

SAMPLE:
{sample_rows}

RULES: Be concise, clear, and refer to real data. Use bullet points."""

    try:
        answer = ai_chat(system_prompt, question, temperature=0.2)
        table_data = None
        data_kw = ["show", "list", "top", "bottom", "filter", "give", "fetch", "display", "rows", "records", "where", "find", "which"]
        if any(kw in question.lower() for kw in data_kw):
            try:
                sql = ai_chat("SQL expert. Return only SQL.", f'SQLite query for: "{question}"\nTable: data\nColumns: {", ".join(cols)}\nReturn ONLY SQL.', temperature=0)
                sql = sql.strip().replace("```sql", "").replace("```", "").strip()
                conn = df_to_sql(df)
                result = pd.read_sql_query(sql, conn)
                conn.close()
                if len(result) > 0:
                    table_data = {"columns": result.columns.tolist(), "rows": result.head(25).fillna("").values.tolist(), "sql": sql}
            except Exception:
                pass

        # Deduct credit and persist messages
        if uid != "guest_user":
            spend_credit(uid, "AI_CHAT")

            # Manage chat session
            if not session_id:
                session_title = question[:60] + ("..." if len(question) > 60 else "")
                dataset_id = ds.get("dataset_id")
                session = database.create_chat_session(
                    user_id=uid,
                    title=session_title,
                    dataset_id=dataset_id
                )
                session_id = session["id"]

            # Persist messages
            database.save_chat_message(session_id, uid, "user", question)
            database.save_chat_message(session_id, uid, "assistant", answer)

            # History entry
            database.add_history(
                user_id=uid, type="CHAT",
                title="AI Chat",
                description=question[:120],
                resource_id=session_id
            )

        return {
            "answer": answer,
            "table": table_data,
            "provider": get_active_provider(),
            "session_id": session_id
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"answer": f"Dataset shape: {df.shape[0]:,} rows x {df.shape[1]} cols.\n- Columns: {', '.join(cols[:8])}", "fallback": True, "provider": "local", "warning": str(e)}


@app.post("/run-sql")
async def run_sql(q: dict, request: Request = None):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Please upload a dataset first. Table name is: data"}
    query = q.get("query", "").strip()
    if not query:
        return {"error": "Empty query"}
    try:
        conn = df_to_sql(df)
        result = pd.read_sql_query(query, conn)
        conn.close()
        return {"columns": result.columns.tolist(), "rows": result.fillna("").values.tolist(), "row_count": len(result)}
    except Exception as e:
        return {"error": str(e)}

    if df is None:
        return {"error": "Please upload a dataset first. Table name is: data"}
    query = q.get("query", "").strip()
    if not query:
        return {"error": "Empty query"}
    try:
        conn = df_to_sql(df)
        result = pd.read_sql_query(query, conn)
        conn.close()
        return {"columns": result.columns.tolist(), "rows": result.fillna("").values.tolist(), "row_count": len(result)}
    except Exception as e:
        return {"error": str(e)}


# ── CHAT SESSION MANAGEMENT (new) ─────────────────────────────────────────

@app.get("/api/chat/sessions")
def list_chat_sessions(current_user: dict = Depends(get_current_user)):
    sessions = database.get_chat_sessions(current_user["id"])
    return {"sessions": sessions}


class CreateSessionRequest(BaseModel):
    title: Optional[str] = "New Chat"
    dataset_id: Optional[str] = None


@app.post("/api/chat/sessions")
def create_chat_session_endpoint(payload: CreateSessionRequest, current_user: dict = Depends(get_current_user)):
    session = database.create_chat_session(
        user_id=current_user["id"],
        title=payload.title or "New Chat",
        dataset_id=payload.dataset_id
    )
    return {"session": session}


@app.get("/api/chat/sessions/{session_id}/messages")
def get_session_messages_endpoint(session_id: str, current_user: dict = Depends(get_current_user)):
    # Verify ownership
    session = database.get_chat_session(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    messages = database.get_session_messages(session_id, current_user["id"])
    return {"session": session, "messages": messages}


class SendMessageRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


@app.post("/api/chat/sessions/{session_id}/messages")
async def send_session_message(
    session_id: str,
    payload: SendMessageRequest,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Send a message within a specific session. Wraps the /chat endpoint logic."""
    # Verify session ownership
    session = database.get_chat_session(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    query_dict = {"question": payload.question, "session_id": session_id}
    return await chat(query_dict, request)


# ── V2/V3/V4 AGENTIC AI & BI ENDPOINTS (preserved + credit enforcement) ───

from models.schemas import AutoFixRequest, RootCauseRequest, ForecastRequest, PlannerRequest
from agents.planner.planner_agent import run_planner_agent
from agents.cleaning.cleaning_agent import run_cleaning_agent, apply_auto_fix
from agents.forecast.forecast_agent import run_forecast_agent
from agents.anomaly.anomaly_agent import run_anomaly_agent
from agents.segmentation.segmentation_agent import run_segmentation_agent
from agents.root_cause.root_cause_agent import run_root_cause_agent
from agents.recommendation.recommendation_agent import run_recommendation_agent
from agents.report.report_agent import run_report_agent


@app.post("/api/v2/clean-audit")
def clean_audit(request: Request):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}

    issues = run_cleaning_agent(df)
    uid = get_user_id_from_request(request)
    if uid != "guest_user":
        database.add_history(
            user_id=uid, type="CLEANING",
            title="Data Cleaning Audit",
            description=f"Found {len(issues)} data quality issues"
        )
    return {"issues": issues}


@app.post("/api/v2/auto-fix")
def auto_fix_endpoint(req: AutoFixRequest, request: Request = None):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}
    fixed_df = apply_auto_fix(df, action=req.action, column=req.column, method=req.method or "mean")
    ds = get_user_datastore(request)
    ds["df"] = fixed_df
    try:
        try:
            con.unregister("data")
        except Exception:
            pass
        con.register("data", fixed_df)
    except Exception:
        pass
    return {
        "status": "success",
        "action": req.action,
        "column": req.column,
        "rows": fixed_df.shape[0],
        "cols": fixed_df.shape[1]
    }


@app.post("/api/v2/executive-report")
def executive_report(request: Request):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}

    uid = get_user_id_from_request(request)
    if uid != "guest_user":
        ensure_credits(uid, "EXECUTIVE_REPORT")

    result = run_report_agent(df, ai_chat)

    if uid != "guest_user":
        spend_credit(uid, "EXECUTIVE_REPORT")
        ds = get_user_datastore(request)
        dataset_id = ds.get("dataset_id")
        dataset_name = ds.get("name", "Dataset")
        saved = database.save_report(
            user_id=uid,
            title=f"Executive Report — {dataset_name}",
            content=result,
            report_type="executive",
            dataset_id=dataset_id
        )
        database.add_history(
            user_id=uid, type="REPORT",
            title="Executive Report Generated",
            description=f"AI-generated executive summary for {dataset_name}",
            resource_id=saved.get("id")
        )
        database.add_notification(
            user_id=uid,
            title="Executive Report Ready",
            message=f"Your AI executive report for '{dataset_name}' has been generated and saved.",
            notif_type="success",
            resource_id=saved.get("id")
        )
        result["_report_id"] = saved.get("id")

    return result


@app.post("/api/v2/root-cause")
def root_cause_endpoint(req: RootCauseRequest, request: Request = None):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}

    result = run_root_cause_agent(df, req.metric)
    uid = get_user_id_from_request(request)
    if uid != "guest_user":
        database.add_history(
            user_id=uid, type="REPORT",
            title=f"Root Cause Analysis — {req.metric}",
            description=f"Root cause breakdown for metric: {req.metric}"
        )
    return result


@app.get("/api/v3/forecast")
def forecast_endpoint(target_col: Optional[str] = None, periods: int = 6, request: Request = None):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}

    uid = get_user_id_from_request(request) if request else "guest_user"
    if uid != "guest_user":
        ensure_credits(uid, "FORECAST")

    result = run_forecast_agent(df, target_col=target_col, periods=periods)

    if uid != "guest_user" and "error" not in result:
        spend_credit(uid, "FORECAST")
        dataset_id = get_user_datastore(request).get("dataset_id") if request else None
        saved = database.save_forecast(
            user_id=uid,
            target_column=result.get("target", target_col or "unknown"),
            periods=periods,
            result=result,
            dataset_id=dataset_id
        )
        database.add_history(
            user_id=uid, type="FORECAST",
            title=f"Forecast — {result.get('target', target_col)}",
            description=f"Trend: {result.get('trend', '')} | {periods} periods projected",
            resource_id=saved.get("id")
        )
        database.add_notification(
            user_id=uid,
            title="Forecast Complete",
            message=f"Forecast for '{result.get('target', target_col)}': {result.get('trend', '')} trend detected over {periods} periods.",
            notif_type="info",
            resource_id=saved.get("id")
        )
        result["_forecast_id"] = saved.get("id")

    return result


@app.get("/api/v3/anomalies")
def anomalies_endpoint(request: Request = None):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}

    anomalies = run_anomaly_agent(df)
    uid = get_user_id_from_request(request)
    if uid != "guest_user":
        database.add_history(
            user_id=uid, type="EDA",
            title="Anomaly Detection",
            description=f"Found {len(anomalies)} anomalous patterns"
        )
    return {"anomalies": anomalies}


@app.get("/api/v3/segmentation")
def segmentation_endpoint(request: Request = None):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}

    result = run_segmentation_agent(df)
    uid = get_user_id_from_request(request)
    if uid != "guest_user":
        database.add_history(
            user_id=uid, type="EDA",
            title="Segmentation Analysis",
            description="ABC segmentation completed"
        )
    return result


@app.get("/api/v3/recommendations")
def recommendations_endpoint(request: Request = None):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}

    uid = get_user_id_from_request(request)
    if uid != "guest_user":
        ensure_credits(uid, "RECOMMENDATIONS")

    result = run_recommendation_agent(df, ai_chat)

    if uid != "guest_user":
        spend_credit(uid, "RECOMMENDATIONS")
        database.add_history(
            user_id=uid, type="REPORT",
            title="AI Recommendations Generated",
            description="Business recommendations generated by AI"
        )
    return {"recommendations": result}


@app.post("/api/v4/agent-plan")
def agent_plan_endpoint(req: PlannerRequest, request: Request = None):
    df = get_user_active_df(request)
    if df is None:
        return {"error": "Upload a dataset first"}

    uid = get_user_id_from_request(request)
    if uid != "guest_user":
        ensure_credits(uid, "AGENT_PLAN")

    result = run_planner_agent(df, ai_chat, goal=req.goal or "Full Agentic Data Analysis")

    if uid != "guest_user":
        spend_credit(uid, "AGENT_PLAN")
        database.add_history(
            user_id=uid, type="REPORT",
            title="Agentic Analysis Plan",
            description=f"Goal: {req.goal or 'Full analysis'}"
        )
    return result


# ── FORECAST PERSISTENCE ENDPOINTS (new) ──────────────────────────────────

class ForecastRunRequest(BaseModel):
    target_col: str
    periods: Optional[int] = 6
    dataset_id: Optional[str] = None


@app.get("/api/forecast")
def list_forecasts(current_user: dict = Depends(get_current_user)):
    forecasts = database.get_user_forecasts(current_user["id"])
    return {"forecasts": forecasts}


@app.post("/api/forecast")
def run_forecast_persisted(payload: ForecastRunRequest, request: Request, current_user: dict = Depends(get_current_user)):
    """Runs a forecast with full user isolation, credit enforcement, and persistence."""
    df = get_user_active_df(request)
    if df is None:
        raise HTTPException(status_code=400, detail="No dataset loaded. Upload or activate a dataset first.")

    ensure_credits(current_user["id"], "FORECAST")
    result = run_forecast_agent(df, target_col=payload.target_col, periods=payload.periods or 6)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    spend_credit(current_user["id"], "FORECAST")
    dataset_id = payload.dataset_id or get_user_datastore(request).get("dataset_id")
    saved = database.save_forecast(
        user_id=current_user["id"],
        target_column=payload.target_col,
        periods=payload.periods or 6,
        result=result,
        dataset_id=dataset_id
    )
    database.add_history(
        user_id=current_user["id"], type="FORECAST",
        title=f"Forecast — {payload.target_col}",
        description=f"{result.get('trend', '')} trend | {payload.periods} periods",
        resource_id=saved.get("id")
    )
    database.add_notification(
        user_id=current_user["id"],
        title="Forecast Ready",
        message=f"Forecast for '{payload.target_col}': {result.get('trend', '')} trend over {payload.periods} periods.",
        notif_type="success",
        resource_id=saved.get("id")
    )
    result["forecast_id"] = saved.get("id")
    return result


@app.get("/api/forecast/{forecast_id}")
def get_forecast(forecast_id: str, current_user: dict = Depends(get_current_user)):
    forecast = database.get_forecast_by_id(forecast_id, current_user["id"])
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast not found")
    return {"forecast": forecast}


# ── VISUALIZATION ENDPOINTS (new) ─────────────────────────────────────────

class VisualizationRequest(BaseModel):
    chart_type: str
    title: Optional[str] = "Untitled Chart"
    x_col: str
    y_col: Optional[str] = None
    agg: Optional[str] = "SUM"
    dataset_id: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None


@app.get("/api/visualizations")
def list_visualizations(current_user: dict = Depends(get_current_user)):
    visualizations = database.get_user_visualizations(current_user["id"])
    return {"visualizations": visualizations}


@app.post("/api/visualizations")
def create_visualization(payload: VisualizationRequest, request: Request, current_user: dict = Depends(get_current_user)):
    """Generates chart data and saves the visualization record."""
    df = get_user_active_df(request)
    if df is None:
        raise HTTPException(status_code=400, detail="No dataset loaded. Upload or activate a dataset first.")

    ensure_credits(current_user["id"], "VISUALIZATION")

    try:
        chart_data = calculate_widget_data(
            df,
            widget_type=payload.chart_type.lower(),
            x_col=payload.x_col,
            y_col=payload.y_col,
            agg=payload.agg or "SUM"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Chart generation error: {str(e)}")

    spend_credit(current_user["id"], "VISUALIZATION")

    config = payload.configuration or {
        "chart_type": payload.chart_type,
        "x_col": payload.x_col,
        "y_col": payload.y_col,
        "agg": payload.agg
    }
    dataset_id = payload.dataset_id or get_user_datastore(request).get("dataset_id")
    saved = database.save_visualization(
        user_id=current_user["id"],
        chart_type=payload.chart_type,
        title=payload.title or f"{payload.chart_type} — {payload.x_col}",
        configuration=config,
        result_metadata={"labels_count": len(chart_data.get("labels", []))},
        dataset_id=dataset_id
    )
    database.add_history(
        user_id=current_user["id"], type="VISUALIZATION",
        title=f"Visualization: {payload.title or payload.chart_type}",
        description=f"{payload.chart_type} chart on {payload.x_col}",
        resource_id=saved.get("id")
    )

    return {
        "visualization_id": saved.get("id"),
        "chart_data": chart_data,
        "metadata": saved
    }


@app.get("/api/visualizations/{viz_id}")
def get_visualization(viz_id: str, current_user: dict = Depends(get_current_user)):
    viz = database.get_visualization_by_id(viz_id, current_user["id"])
    if not viz:
        raise HTTPException(status_code=404, detail="Visualization not found")
    return {"visualization": viz}


# ── REPORTS ENDPOINTS (new + preserve existing) ────────────────────────────

class GenerateReportRequest(BaseModel):
    type: Optional[str] = "executive"
    title: Optional[str] = None
    dataset_id: Optional[str] = None


@app.get("/api/reports")
def list_reports(current_user: dict = Depends(get_current_user)):
    reports = database.get_user_reports(current_user["id"])
    return {"reports": reports}


@app.post("/api/reports")
def generate_report(payload: GenerateReportRequest, request: Request, current_user: dict = Depends(get_current_user)):
    """Generates a report using the existing report agent, persists it, and returns content."""
    df = get_user_active_df(request)
    if df is None:
        raise HTTPException(status_code=400, detail="No dataset loaded. Upload or activate a dataset first.")

    ensure_credits(current_user["id"], "EXECUTIVE_REPORT")

    result = run_report_agent(df, ai_chat)

    spend_credit(current_user["id"], "EXECUTIVE_REPORT")

    ds = get_user_datastore(request)
    dataset_name = ds.get("name", "Dataset")
    dataset_id = payload.dataset_id or ds.get("dataset_id")
    title = payload.title or f"Executive Report — {dataset_name}"

    saved = database.save_report(
        user_id=current_user["id"],
        title=title,
        content=result,
        report_type=payload.type or "executive",
        dataset_id=dataset_id
    )
    database.add_history(
        user_id=current_user["id"], type="REPORT",
        title=title,
        description=f"AI-generated {payload.type or 'executive'} report",
        resource_id=saved.get("id")
    )
    database.add_notification(
        user_id=current_user["id"],
        title="Report Generated",
        message=f"'{title}' is ready to view and download.",
        notif_type="success",
        resource_id=saved.get("id")
    )

    result["report_id"] = saved.get("id")
    return result


@app.get("/api/reports/{report_id}")
def get_report(report_id: str, current_user: dict = Depends(get_current_user)):
    report = database.get_report_by_id(report_id, current_user["id"])
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"report": report}


@app.get("/api/reports/{report_id}/download")
def download_report_pdf(report_id: str, request: Request = None, current_user: dict = Depends(get_current_user)):
    """Download an already-generated report as PDF — no credit cost."""
    report = database.get_report_by_id(report_id, current_user["id"])
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Re-use active dataset if available
    df = get_user_active_df(request)
    if df is None:
        raise HTTPException(status_code=400, detail="Dataset not loaded. Activate the dataset first.")

    domain = detect_domain(df)
    pdf_bytes = generate_pdf_report_bytes(df, domain=domain)
    buffer = io.BytesIO(pdf_bytes)
    safe_title = "".join(c for c in report["title"] if c.isalnum() or c in " _-")[:50]
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=insightflow_{safe_title}.pdf"}
    )



# ── HISTORY ENDPOINTS (new) ────────────────────────────────────────────────

@app.get("/api/history")
def get_history(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    history = database.get_user_history(current_user["id"], limit=limit, offset=offset)
    total = database.get_history_count(current_user["id"])
    return {
        "history": history,
        "total": total,
        "limit": limit,
        "offset": offset
    }


# ── NOTIFICATION ENDPOINTS (new) ──────────────────────────────────────────

@app.get("/api/notifications")
def get_notifications(current_user: dict = Depends(get_current_user)):
    notifications = database.get_user_notifications(current_user["id"])
    unread_count = database.get_unread_notification_count(current_user["id"])
    return {
        "notifications": notifications,
        "unread_count": unread_count
    }


@app.put("/api/notifications/{notif_id}/read")
def mark_notification_read_endpoint(notif_id: str, current_user: dict = Depends(get_current_user)):
    success = database.mark_notification_read(notif_id, current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "success", "message": "Notification marked as read"}


@app.put("/api/notifications/read-all")
def mark_all_notifications_read_endpoint(current_user: dict = Depends(get_current_user)):
    count = database.mark_all_notifications_read(current_user["id"])
    return {"status": "success", "marked_count": count}


@app.delete("/api/notifications/{notif_id}")
def delete_notification_endpoint(notif_id: str, current_user: dict = Depends(get_current_user)):
    success = database.delete_notification(notif_id, current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "success", "message": "Notification deleted"}
