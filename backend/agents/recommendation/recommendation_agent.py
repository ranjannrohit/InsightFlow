import json
from typing import Dict, Any, List
import pandas as pd
from prompts.agent_prompts import RECOMMENDATION_PROMPT

def run_recommendation_agent(df: pd.DataFrame, ai_chat_fn) -> List[Dict[str, Any]]:
    rows, cols = df.shape
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(exclude="number").columns.tolist()

    stats_summary = []
    for c in num_cols[:4]:
        s = df[c].dropna()
        if len(s):
            stats_summary.append(f"{c}: mean={s.mean():,.2f}, total={s.sum():,.0f}")

    prompt = f"""Dataset: {rows} rows x {cols} cols.
Features: {num_cols + cat_cols}
Metrics: {', '.join(stats_summary)}

Recommend 4 strategic business actions."""

    try:
        raw = ai_chat_fn(RECOMMENDATION_PROMPT, prompt, temperature=0.2)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        # Fallback recommendations
        return [
            {
                "category": "Pricing & Revenue Strategy",
                "title": "Optimize High-Volume Segment Margins",
                "action": f"Focus pricing adjustments on top volume dimension '{cat_cols[0] if cat_cols else 'Primary Category'}' to maximize margin efficiency.",
                "impact": "HIGH",
                "effort": "MEDIUM"
            },
            {
                "category": "Marketing & Demand Growth",
                "title": "Target Outlier Performance Segments",
                "action": f"Allocate marketing budget towards segments associated with top values in '{num_cols[0] if num_cols else 'Key Metric'}'.",
                "impact": "HIGH",
                "effort": "LOW"
            },
            {
                "category": "Inventory & Operations",
                "title": "Streamline Category Distribution",
                "action": "Consolidate low-performing Tier C items from ABC analysis to reduce operational complexity.",
                "impact": "MEDIUM",
                "effort": "LOW"
            },
            {
                "category": "Data Governance & Strategy",
                "title": "Automate Data Hygiene & Pipelines",
                "action": "Implement automated daily cleaning rules for missing values to maintain high analytics completeness.",
                "impact": "HIGH",
                "effort": "HIGH"
            }
        ]
