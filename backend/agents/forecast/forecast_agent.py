from typing import Dict, Any
import pandas as pd
import numpy as np
from tools.analytics_tools import compute_forecast

def run_forecast_agent(df: pd.DataFrame, target_col: str = None, periods: int = 6) -> Dict[str, Any]:
    num_cols = df.select_dtypes(include=np.number).columns.tolist()
    if not num_cols:
        return {"error": "No numerical features present for forecasting."}

    if not target_col or target_col not in num_cols:
        # Choose highest variance numerical column
        target_col = num_cols[0]

    return compute_forecast(df, target_col, periods=periods)
