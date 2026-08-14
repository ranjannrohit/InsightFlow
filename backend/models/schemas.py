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

class SignUpRequest(BaseModel):
    name: str
    email: str
    password: str
    confirm_password: str

class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: Optional[bool] = True

class GoogleAuthRequest(BaseModel):
    email: str
    name: str
    google_id: str
    profile_photo: Optional[str] = None
    remember_me: Optional[bool] = True

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
    confirm_password: str

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    profile_photo: Optional[str] = None
    theme: Optional[str] = None
    history_enabled: Optional[int] = None

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str

class FilterDataRequest(BaseModel):
    column: Optional[str] = None
    operator: Optional[str] = "contains"  # "contains", "equals", "greater_than", "less_than"
    value: Optional[Any] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = "asc"  # "asc", "desc"
    limit: Optional[int] = 50
    offset: Optional[int] = 0


