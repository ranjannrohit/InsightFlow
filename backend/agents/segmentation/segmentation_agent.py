from typing import Dict, Any
import pandas as pd
from tools.analytics_tools import run_segmentation

def run_segmentation_agent(df: pd.DataFrame) -> Dict[str, Any]:
    return run_segmentation(df)
