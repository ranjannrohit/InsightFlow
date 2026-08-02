from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class CustomWidgetRequest(BaseModel):
    widget_type: str
    title: str
    x_col: str
    y_col: Optional[str] = None
    agg: Optional[str] = "SUM"

class AutoFixRequest(BaseModel):
    action: str  # "fill_missing", "drop_duplicates", "drop_empty_cols", "drop_outliers"
    column: Optional[str] = None
    method: Optional[str] = "mean"  # "mean", "median", "mode", "drop"

class RootCauseRequest(BaseModel):
    metric: str
    question: Optional[str] = "Why did this metric change?"

class ForecastRequest(BaseModel):
    target_col: str
    time_col: Optional[str] = None
    periods: Optional[int] = 6

class PlannerRequest(BaseModel):
    goal: Optional[str] = "Full Agentic Data Analysis"
