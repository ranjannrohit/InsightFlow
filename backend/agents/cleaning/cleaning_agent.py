from typing import Dict, Any, List
import pandas as pd
from tools.analytics_tools import run_cleaning_audit

def run_cleaning_agent(df: pd.DataFrame) -> List[Dict[str, Any]]:
    # Statistical clean audit
    issues = run_cleaning_audit(df)
    return issues

def apply_auto_fix(df: pd.DataFrame, action: str, column: str = None, method: str = "mean") -> pd.DataFrame:
    df_fixed = df.copy()

    if action == "drop_duplicates":
        df_fixed = df_fixed.drop_duplicates()
    elif action == "drop_empty_cols":
        empty_cols = [c for c in df_fixed.columns if df_fixed[c].isnull().all()]
        df_fixed = df_fixed.drop(columns=empty_cols)
    elif action == "fill_missing" and column and column in df_fixed.columns:
        if pd.api.types.is_numeric_dtype(df_fixed[column]):
            val = df_fixed[column].median() if method == "median" else df_fixed[column].mean()
            df_fixed[column] = df_fixed[column].fillna(val)
        else:
            mode_val = df_fixed[column].mode().iloc[0] if len(df_fixed[column].mode()) else "Unknown"
            df_fixed[column] = df_fixed[column].fillna(mode_val)
    elif action == "drop_outliers" and column and column in df_fixed.columns:
        if pd.api.types.is_numeric_dtype(df_fixed[column]):
            q1 = df_fixed[column].quantile(0.01)
            q99 = df_fixed[column].quantile(0.99)
            df_fixed[column] = df_fixed[column].clip(lower=q1, upper=q99)

    return df_fixed
