from typing import Dict, Any, List
import pandas as pd
from tools.analytics_tools import detect_anomalies

def run_anomaly_agent(df: pd.DataFrame) -> List[Dict[str, Any]]:
    return detect_anomalies(df)
