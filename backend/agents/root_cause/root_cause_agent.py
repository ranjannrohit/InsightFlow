from typing import Dict, Any
import pandas as pd
from tools.analytics_tools import run_root_cause_analysis

def run_root_cause_agent(df: pd.DataFrame, metric: str = None) -> Dict[str, Any]:
    return run_root_cause_analysis(df, metric)
