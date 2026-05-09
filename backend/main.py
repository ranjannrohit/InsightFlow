from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np

app = FastAPI()

# ---------------------------------
# CORS
# ---------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------
# GLOBAL DATASTORE
# ---------------------------------
DATASTORE = {}

# ---------------------------------
# ROOT
# ---------------------------------
@app.get("/")
def root():
    return {"status": "InsightFlow Backend Running"}

# ---------------------------------
# UPLOAD DATASET
# ---------------------------------
@app.post("/upload")
async def upload(file: UploadFile = File(...)):

    # ---------- FILE TYPE HANDLING ----------
    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(file.file)

        elif file.filename.endswith(".xlsx"):
            df = pd.read_excel(file.file)

        elif file.filename.endswith(".json"):
            df = pd.read_json(file.file)

        else:
            return {
                "error": "Unsupported file type. Use CSV, XLSX, or JSON."
            }

    except Exception as e:
        return {
            "error": f"File processing failed: {str(e)}"
        }

    # ---------- STORE DATAFRAME ----------
    DATASTORE["df"] = df

    # ---------- BASIC STATS ----------
    rows, cols = df.shape

    missing = int(df.isnull().sum().sum())

    duplicates = int(df.duplicated().sum())

    numeric_cols = df.select_dtypes(
        include=np.number
    ).columns.tolist()

    categorical_cols = df.select_dtypes(
        exclude=np.number
    ).columns.tolist()

    # ---------- KPI CARDS ----------
    kpis = [
        {
            "label": "Rows",
            "value": rows
        },
        {
            "label": "Columns",
            "value": cols
        },
        {
            "label": "Missing Values",
            "value": missing
        },
        {
            "label": "Duplicates",
            "value": duplicates
        }
    ]

    # ---------- TABLE PREVIEW ----------
    preview = df.head(10).fillna("").values.tolist()

    # ---------- RESPONSE ----------
    return {
    "summary": {
        "rows": rows,
        "columns": cols,
        "missing": missing,
        "duplicates": duplicates,
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "column_names": list(df.columns),
    },

    "preview": df.head(10).values.tolist(),

    "kpis": kpis
}

# ---------------------------------
# EDA
# ---------------------------------
@app.get("/eda")
def eda():

    df = DATASTORE.get("df")

    if df is None:
        return {
            "error": "Upload dataset first"
        }

    try:
        # Statistical summary
        description = (
            df.describe(include="all")
            .fillna("")
            .to_dict()
        )

        # Correlation matrix
        correlation = (
            df.corr(numeric_only=True)
            .fillna(0)
            .to_dict()
        )

        return {
            "description": description,
            "correlation": correlation
        }

    except Exception as e:
        return {
            "error": str(e)
        }

# ---------------------------------
# DATA TABLE
# ---------------------------------
@app.get("/data")
def get_data(limit: int = 20):

    df = DATASTORE.get("df")

    if df is None:
        return {
            "error": "Upload dataset first"
        }

    rows = (
        df.head(limit)
        .fillna("")
        .to_dict(orient="records")
    )

    return {
        "columns": list(df.columns),
        "rows": rows
    }

# ---------------------------------
# CLEANING INSIGHTS
# ---------------------------------
@app.get("/cleaning")
def cleaning():

    df = DATASTORE.get("df")

    if df is None:
        return {
            "error": "Upload dataset first"
        }

    missing_by_column = (
        df.isnull()
        .sum()
        .to_dict()
    )

    duplicate_count = int(df.duplicated().sum())

    return {
        "duplicates": duplicate_count,
        "missing": missing_by_column
    }

# ---------------------------------
# ASK YOUR DATA (AGENT)
# ---------------------------------
@app.post("/ask")
async def ask(query: dict):

    df = DATASTORE.get("df")

    if df is None:
        return {
            "answer": "Please upload a dataset first."
        }

    q = query.get("question", "").lower()

    # ---------- MISSING VALUES ----------
    if "missing" in q:

        missing = df.isnull().sum()

        return {
            "answer": missing.to_string()
        }

    # ---------- DUPLICATES ----------
    elif "duplicate" in q:

        duplicates = int(df.duplicated().sum())

        return {
            "answer": f"Duplicate rows found: {duplicates}"
        }

    # ---------- COLUMN NAMES ----------
    elif "column" in q or "columns" in q:

        return {
            "answer": ", ".join(df.columns)
        }

    # ---------- SUMMARY ----------
    elif "summary" in q or "describe" in q:

        return {
            "answer": str(df.describe())
        }

    # ---------- ROW COUNT ----------
    elif "rows" in q:

        return {
            "answer": f"Total rows: {len(df)}"
        }

    # ---------- NUMERIC COLUMNS ----------
    elif "numeric" in q:

        numeric_cols = df.select_dtypes(
            include=np.number
        ).columns.tolist()

        return {
            "answer": ", ".join(numeric_cols)
        }

    # ---------- CATEGORICAL COLUMNS ----------
    elif "categorical" in q:

        categorical_cols = df.select_dtypes(
            exclude=np.number
        ).columns.tolist()

        return {
            "answer": ", ".join(categorical_cols)
        }

    # ---------- DEFAULT ----------
    return {
        "answer": (
            "Try asking about:\n"
            "- missing values\n"
            "- duplicates\n"
            "- columns\n"
            "- summary\n"
            "- numeric columns\n"
            "- categorical columns"
        )
    }