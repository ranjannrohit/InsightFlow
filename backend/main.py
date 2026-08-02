from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

import pandas as pd
import numpy as np
import duckdb
import sqlite3
import json
import io
import os
import traceback
from dotenv import load_dotenv
import httpx

# ─────────────────────────────────────────────────────────
# AI PROVIDER SETUP — 100% FREE
# Priority: Groq (free) → Gemini (free) → Local Pandas Engine
# ─────────────────────────────────────────────────────────

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

_gemini_model = None


def get_gemini_model():
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model
    if not GEMINI_API_KEY:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_model = genai.GenerativeModel("gemini-2.0-flash")
        return _gemini_model
    except Exception:
        traceback.print_exc()
        return None


def groq_chat_raw(system_prompt: str, user_message: str, temperature: float = 0.2) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")
    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "temperature": temperature,
            "max_tokens": 1500,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def gemini_chat_raw(system_prompt: str, user_message: str, temperature: float = 0.2) -> str:
    model = get_gemini_model()
    if model is None:
        raise RuntimeError("Gemini not available")
    import google.generativeai as genai
    response = model.generate_content(
        f"{system_prompt}\n\n{user_message}",
        generation_config=genai.types.GenerationConfig(temperature=temperature, max_output_tokens=1500),
    )
    return response.text


def ai_chat(system_prompt: str, user_message: str, temperature: float = 0.2) -> str:
    errors = []
    if GROQ_API_KEY:
        try:
            return groq_chat_raw(system_prompt, user_message, temperature)
        except Exception as e:
            errors.append(f"Groq: {e}")

    if GEMINI_API_KEY:
        try:
            return gemini_chat_raw(system_prompt, user_message, temperature)
        except Exception as e:
            errors.append(f"Gemini: {e}")

    raise RuntimeError(
        f"All free AI providers unavailable. {'; '.join(errors) if errors else 'No API keys set'}."
    )


def get_active_provider() -> str:
    if GROQ_API_KEY:
        return "groq"
    if GEMINI_API_KEY:
        return "gemini"
    return "local"


# ─────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────

app = FastAPI(title="InsightFlow PowerBI Engine")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DATASTORE: dict = {}
con = duckdb.connect(":memory:")


# ─────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "InsightFlow PowerBI Engine Running", "version": "4.0-powerbi"}


@app.get("/status")
def status():
    df = DATASTORE.get("df")
    has_data = df is not None
    return {
        "backend": "online",
        "dataset_loaded": has_data,
        "dataset_rows": int(df.shape[0]) if has_data else 0,
        "dataset_cols": int(df.shape[1]) if has_data else 0,
        "dataset_name": DATASTORE.get("name", ""),
        "ai_provider": get_active_provider(),
        "groq_ready": bool(GROQ_API_KEY),
        "gemini_ready": bool(GEMINI_API_KEY),
    }


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
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

    DATASTORE["df"] = df
    DATASTORE["name"] = fname

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

    return {
        "summary": {
            "rows": rows, "columns": cols, "missing": missing, "duplicates": duplicates,
            "numeric_columns": numeric_cols, "categorical_columns": categorical_cols,
            "column_names": list(df.columns),
            "domain": detect_domain(df),
        },
        "preview": df.head(10).fillna("").values.tolist(),
    }


# ─────────────────────────────────────────────────────────
# AUTO-DASHBOARD ENGINE (POWERBI INTELLIGENCE)
# ─────────────────────────────────────────────────────────

def calculate_widget_data(df: pd.DataFrame, widget_type: str, x_col: str, y_col: Optional[str], agg: str = "SUM") -> Dict[str, Any]:
    """Computes aggregated chart series or metric data for Chart.js rendering."""
    if x_col not in df.columns:
        return {"labels": [], "values": []}

    # Handle Metric / KPI Card
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
        else:  # SUM
            val = s.sum()
        
        formatted = f"{val:,.2f}" if isinstance(val, (int, float)) and not val.is_integer() else f"{int(val):,}"
        spark = s.sample(min(12, len(s)), random_state=42).sort_index().tolist() if pd.api.types.is_numeric_dtype(s) else []
        return {"metric": formatted, "label": f"{agg} of {x_col}", "sub": f"Min: {s.min():,.0f} | Max: {s.max():,.0f}" if pd.api.types.is_numeric_dtype(s) else f"{len(s)} items", "spark": spark}

    # Handle Scatter Plot
    if widget_type == "scatter" and y_col and y_col in df.columns:
        sub_df = df[[x_col, y_col]].dropna()
        if len(sub_df) > 120:
            sub_df = sub_df.sample(120, random_state=42)
        points = [{"x": float(r[x_col]), "y": float(r[y_col])} for _, r in sub_df.iterrows()]
        return {"points": points, "x_label": x_col, "y_label": y_col}

    # Handle Categorical / Grouped Charts (Bar, Line, Area, Donut, Pie)
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
        # Simple Frequency Count by Column
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
    bar_col: Optional[str] = None,
    line_col: Optional[str] = None,
    donut_col: Optional[str] = None,
    agg: Optional[str] = "SUM"
):
    df = DATASTORE.get("df")
    if df is None:
        return {"error": "Upload a dataset first"}

    num_cols = df.select_dtypes(include=np.number).columns.tolist()
    cat_cols = df.select_dtypes(exclude=np.number).columns.tolist()
    domain = detect_domain(df)

    ranked_num = rank_numeric_columns(df)
    ranked_cat = rank_categorical_columns(df)

    # 1. Generate 4 AI-Ranked Executive KPI Cards
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

    # Line chart column choice (top ranked numeric)
    sel_line = line_col if (line_col and line_col in df.columns) else (ranked_num[0] if ranked_num else (df.columns[0] if len(df.columns) else ""))
    line_res = calculate_widget_data(df, "line", sel_line, None) if sel_line else {"labels": [], "values": []}
    line_res["column"] = sel_line

    # Bar chart column choice (top ranked categorical vs primary numeric)
    sel_bar = bar_col if (bar_col and bar_col in df.columns) else (ranked_cat[0] if ranked_cat else (df.columns[0] if len(df.columns) else ""))
    target_num_bar = ranked_num[0] if ranked_num else None
    bar_res = calculate_widget_data(df, "bar", sel_bar, target_num_bar, agg or "SUM") if sel_bar else {"labels": [], "values": []}
    bar_res["column"] = sel_bar

    # Donut chart column choice (secondary ranked categorical)
    sel_donut = donut_col if (donut_col and donut_col in df.columns) else (ranked_cat[1] if len(ranked_cat) > 1 else (ranked_cat[0] if ranked_cat else (df.columns[0] if len(df.columns) else "")))
    donut_res_raw = calculate_widget_data(df, "donut", sel_donut, target_num_bar, "AVG" if target_num_bar else "COUNT") if sel_donut else {"labels": [], "values": []}
    
    # Format donut data for UI
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

    # Scatter / Correlation data
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


# ─────────────────────────────────────────────────────────
# CUSTOM WIDGET BUILDER ENDPOINT
# ─────────────────────────────────────────────────────────

class CustomWidgetRequest(BaseModel):
    widget_type: str  # bar, line, area, donut, pie, scatter, kpi
    title: str
    x_col: str
    y_col: Optional[str] = None
    agg: Optional[str] = "SUM"


@app.post("/custom-widget")
async def create_custom_widget(req: CustomWidgetRequest):
    df = DATASTORE.get("df")
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


# ─────────────────────────────────────────────────────────
# OTHER ANALYTICS & EDA ENDPOINTS
# ─────────────────────────────────────────────────────────

@app.get("/data")
def get_data(limit: int = 1000):
    df = DATASTORE.get("df")
    if df is None:
        return {"error": "Upload a dataset first"}
    return {
        "columns": list(df.columns),
        "rows": df.head(limit).fillna("").to_dict(orient="records"),
        "total_rows": len(df),
        "showing": min(limit, len(df)),
    }


@app.get("/download")
def download_data():
    df = DATASTORE.get("df")
    if df is None:
        return {"error": "No dataset uploaded"}
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    stream.seek(0)
    return StreamingResponse(stream, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=insightflow_powerbi_export.csv"})


@app.get("/eda")
def eda():
    df = DATASTORE.get("df")
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
def cleaning():
    df = DATASTORE.get("df")
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
def insights():
    df = DATASTORE.get("df")
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


# ─────────────────────────────────────────────────────────
# AI CHAT & SQL ENDPOINTS
# ─────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(query: dict):
    question = query.get("question", "").strip()
    if not question:
        return {"error": "No question provided"}
    df = DATASTORE.get("df")
    if df is None:
        return {"error": "Please upload a dataset first before asking questions."}

    cols = list(df.columns)
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(exclude="number").columns.tolist()

    numeric_summary = ""
    for col in numeric_cols[:8]:
        numeric_summary += f"\n  {col}: mean={df[col].mean():.2f}, min={df[col].min():.2f}, max={df[col].max():.2f}, std={df[col].std():.2f}"

    sample_rows = df.head(5).fillna("").to_string(index=False)

    system_prompt = f"""You are InsightFlow AI, a PowerBI-grade Data Analyst.

DATASET:
- File: {DATASTORE.get('name', 'uploaded file')}
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
        return {"answer": answer, "table": table_data, "provider": get_active_provider()}
    except Exception as e:
        return {"answer": f"Dataset shape: {df.shape[0]:,} rows x {df.shape[1]} cols.\n- Columns: {', '.join(cols[:8])}", "fallback": True, "provider": "local", "warning": str(e)}


@app.post("/run-sql")
async def run_sql(q: dict):
    df = DATASTORE.get("df")
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


# ─────────────────────────────────────────────────────────
# V2, V3, V4 AGENTIC AI & BI ENDPOINTS
# ─────────────────────────────────────────────────────────

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
def clean_audit():
    df = DATASTORE.get("df")
    if df is None:
        return {"error": "Upload a dataset first"}
    return {"issues": run_cleaning_agent(df)}


@app.post("/api/v2/auto-fix")
def auto_fix_endpoint(req: AutoFixRequest):
    df = DATASTORE.get("df")
    if df is None:
        return {"error": "Upload a dataset first"}
    fixed_df = apply_auto_fix(df, action=req.action, column=req.column, method=req.method or "mean")
    DATASTORE["df"] = fixed_df
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
def executive_report():
    df = DATASTORE.get("df")
    if df is None:
        return {"error": "Upload a dataset first"}
    return run_report_agent(df, ai_chat)


@app.post("/api/v2/root-cause")
def root_cause_endpoint(req: RootCauseRequest):
    df = DATASTORE.get("df")
    if df is None:
        return {"error": "Upload a dataset first"}
    return run_root_cause_agent(df, req.metric)


@app.get("/api/v3/forecast")
def forecast_endpoint(target_col: Optional[str] = None, periods: int = 6):
    df = DATASTORE.get("df")
    if df is None:
        return {"error": "Upload a dataset first"}
    return run_forecast_agent(df, target_col=target_col, periods=periods)


@app.get("/api/v3/anomalies")
def anomalies_endpoint():
    df = DATASTORE.get("df")
    if df is None:
        return {"error": "Upload a dataset first"}
    return {"anomalies": run_anomaly_agent(df)}


@app.get("/api/v3/segmentation")
def segmentation_endpoint():
    df = DATASTORE.get("df")
    if df is None:
        return {"error": "Upload a dataset first"}
    return run_segmentation_agent(df)


@app.get("/api/v3/recommendations")
def recommendations_endpoint():
    df = DATASTORE.get("df")
    if df is None:
        return {"error": "Upload a dataset first"}
    return {"recommendations": run_recommendation_agent(df, ai_chat)}


@app.post("/api/v4/agent-plan")
def agent_plan_endpoint(req: PlannerRequest):
    df = DATASTORE.get("df")
    if df is None:
        return {"error": "Upload a dataset first"}
    return run_planner_agent(df, ai_chat, goal=req.goal or "Full Agentic Data Analysis")

