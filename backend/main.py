from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import pandas as pd
import numpy as np
import duckdb
import sqlite3

from openai import OpenAI


# ---------------------------------
# APP + DB
# ---------------------------------

app = FastAPI()

con = duckdb.connect("insightflow.db")

client = OpenAI(
    api_key="YOUR_OPENAI_API_KEY"
)

DATASTORE = {}


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
# ROOT
# ---------------------------------

@app.get("/")
def root():
    return {
        "status": "InsightFlow Backend Running"
    }


# ---------------------------------
# UPLOAD DATASET
# ---------------------------------

@app.post("/upload")
async def upload(file: UploadFile = File(...)):

    try:

        if file.filename.endswith(".csv"):
            df = pd.read_csv(file.file)

        elif file.filename.endswith(".xlsx"):
            df = pd.read_excel(file.file)

        elif file.filename.endswith(".json"):
            df = pd.read_json(file.file)

        else:
            return {
                "error": "Unsupported file type"
            }

    except Exception as e:

        return {
            "error": str(e)
        }

    # SAVE DATAFRAME
    DATASTORE["df"] = df

    # CREATE SQL TABLE
    try:

        con.register("temp_df", df)

        con.execute("""
            CREATE OR REPLACE TABLE uploaded_data AS
            SELECT * FROM temp_df
        """)

    except Exception as e:

        return {
            "error": f"SQL error: {str(e)}"
        }

    rows, cols = df.shape

    missing = int(df.isnull().sum().sum())

    duplicates = int(df.duplicated().sum())

    numeric_cols = df.select_dtypes(
        include=np.number
    ).columns.tolist()

    categorical_cols = df.select_dtypes(
        exclude=np.number
    ).columns.tolist()

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

    return {

        "summary": {
            "rows": rows,
            "columns": cols,
            "missing": missing,
            "duplicates": duplicates,
            "numeric_columns": numeric_cols,
            "categorical_columns": categorical_cols,
            "column_names": list(df.columns)
        },

        "preview": (
            df.head(10)
            .fillna("")
            .values.tolist()
        ),

        "kpis": kpis
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

    return {

        "columns": list(df.columns),

        "rows": (
            df.head(limit)
            .fillna("")
            .to_dict(orient="records")
        )
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

        description = (
            df.describe(include="all")
            .fillna("")
            .to_dict()
        )

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
# CLEANING
# ---------------------------------

@app.get("/cleaning")
def cleaning():

    df = DATASTORE.get("df")

    if df is None:
        return {
            "error": "Upload dataset first"
        }

    return {

        "duplicates": int(df.duplicated().sum()),

        "missing": (
            df.isnull()
            .sum()
            .to_dict()
        )
    }


# ---------------------------------
# ASK AI
# ---------------------------------

@app.post("/ask")
async def ask(query: dict):

    question = query.get("question")

    if not question:

        return {
            "error": "No question provided"
        }

    df = DATASTORE.get("df")

    if df is None:

        return {
            "error": "Upload dataset first"
        }

    try:

        columns = ", ".join(df.columns)

        prompt = f"""
        You are an expert SQL analyst.

        Table name: uploaded_data

        Columns:
        {columns}

        Generate ONLY SQL query.
        """

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": prompt
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            temperature=0
        )

        sql_query = (
            response
            .choices[0]
            .message.content
            .replace("```sql", "")
            .replace("```", "")
            .strip()
        )

        result = con.execute(sql_query).fetchdf()

        return {

            "question": question,

            "sql": sql_query,

            "columns": result.columns.tolist(),

            "rows": (
                result.fillna("")
                .values.tolist()
            )
        }

    except Exception as e:

        return {
            "error": str(e)
        }


# ---------------------------------
# RUN RAW SQL
# ---------------------------------

class SQLQuery(BaseModel):
    query: str


@app.post("/run-sql")
async def run_sql(q: SQLQuery):

    try:

        df = DATASTORE["df"]

        conn = sqlite3.connect(":memory:")

        df.to_sql(
            "data",
            conn,
            index=False,
            if_exists="replace"
        )

        result = pd.read_sql_query(
            q.query,
            conn
        )

        return {

            "columns": result.columns.tolist(),

            "rows": result.values.tolist()
        }

    except Exception as e:

        return {
            "error": str(e)
        }