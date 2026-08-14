import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional

# ─────────────────────────────────────────────────────────
# ANOMALY DETECTION TOOL (IQR + Z-SCORE)
# ─────────────────────────────────────────────────────────

def detect_anomalies(df: pd.DataFrame) -> List[Dict[str, Any]]:
    anomalies = []
    num_cols = df.select_dtypes(include=np.number).columns.tolist()

    for col in num_cols:
        s = df[col].dropna()
        if len(s) < 5 or s.std() == 0:
            continue

        # Z-score method
        mean_val = s.mean()
        std_val = s.std()
        z_scores = np.abs((s - mean_val) / std_val)
        outlier_indices = s[z_scores > 2.8].index.tolist()

        if len(outlier_indices) > 0:
            # IQR method
            q1 = s.quantile(0.25)
            q3 = s.quantile(0.75)
            iqr = q3 - q1
            outlier_vals = s.loc[outlier_indices].tolist()

            anomalies.append({
                "column": col,
                "count": len(outlier_indices),
                "severity": "CRITICAL" if len(outlier_indices) > 5 else "MODERATE",
                "type": "Spike / Extreme Outlier" if max(outlier_vals) > mean_val + 2 * std_val else "Drop / Low Outlier",
                "sample_values": [round(float(v), 2) for v in outlier_vals[:5]],
                "description": f"Found {len(outlier_indices)} statistical outliers in '{col}' exceeding 2.8 std deviations (Mean: {mean_val:,.2f}, Max: {s.max():,.2f})."
            })

    return anomalies


# ─────────────────────────────────────────────────────────
# TIME-SERIES & TREND FORECASTING TOOL
# ─────────────────────────────────────────────────────────

def compute_forecast(df: pd.DataFrame, target_col: str, periods: int = 6) -> Dict[str, Any]:
    if target_col not in df.columns or not pd.api.types.is_numeric_dtype(df[target_col]):
        return {"error": f"Column '{target_col}' is not numeric"}

    s = df[target_col].dropna().values
    if len(s) < 4:
        return {"error": "Need at least 4 numerical records for forecasting"}

    x = np.arange(len(s))
    slope, intercept = np.polyfit(x, s, 1)

    future_x = np.arange(len(s), len(s) + periods)
    future_y = slope * future_x + intercept

    # Add trend direction
    growth_rate = ((future_y[-1] - s[-1]) / abs(s[-1])) * 100 if s[-1] != 0 else 0

    return {
        "target": target_col,
        "historical": [round(float(v), 2) for v in s[-12:]],
        "forecast": [round(float(v), 2) for v in future_y],
        "slope": round(float(slope), 4),
        "trend": "UPWARD" if slope > 0 else ("DOWNWARD" if slope < 0 else "STABLE"),
        "predicted_change_pct": round(float(growth_rate), 1),
        "summary": f"Projected {target_col} to {'increase' if slope > 0 else 'decrease'} by {abs(growth_rate):.1f}% over next {periods} periods based on linear trend analysis."
    }


# ─────────────────────────────────────────────────────────
# RFM / ABC SEGMENTATION TOOL
# ─────────────────────────────────────────────────────────

def run_segmentation(df: pd.DataFrame) -> Dict[str, Any]:
    num_cols = df.select_dtypes(include=np.number).columns.tolist()
    cat_cols = df.select_dtypes(exclude=np.number).columns.tolist()

    if not cat_cols or not num_cols:
        return {"segments": [], "type": "ABC Analysis", "summary": "Dataset lacks entity/numerical pairings for segmentation"}

    entity_col = cat_cols[0]
    value_col = num_cols[0]

    grouped = df.groupby(entity_col)[value_col].sum().sort_values(ascending=False)
    total_val = grouped.sum() or 1

    cum_sum = grouped.cumsum()
    cum_pct = cum_sum / total_val

    group_a = grouped[cum_pct <= 0.70]
    group_b = grouped[(cum_pct > 0.70) & (cum_pct <= 0.90)]
    group_c = grouped[cum_pct > 0.90]

    return {
        "entity_column": entity_col,
        "value_column": value_col,
        "segments": [
            {
                "tier": "Tier A (High Value - Top 70% Share)",
                "count": len(group_a),
                "share_pct": round(float((group_a.sum() / total_val) * 100), 1),
                "top_items": [str(k) for k in group_a.index[:5]]
            },
            {
                "tier": "Tier B (Medium Value - Next 20% Share)",
                "count": len(group_b),
                "share_pct": round(float((group_b.sum() / total_val) * 100), 1),
                "top_items": [str(k) for k in group_b.index[:5]]
            },
            {
                "tier": "Tier C (Low Value - Bottom 10% Share)",
                "count": len(group_c),
                "share_pct": round(float((group_c.sum() / total_val) * 100), 1),
                "top_items": [str(k) for k in group_c.index[:5]]
            }
        ],
        "summary": f"ABC Analysis on '{entity_col}' by '{value_col}': {len(group_a)} key items drive 70% of total volume."
    }


# ─────────────────────────────────────────────────────────
# DATA CLEANING AUDIT TOOL
# ─────────────────────────────────────────────────────────

def run_cleaning_audit(df: pd.DataFrame) -> List[Dict[str, Any]]:
    issues = []
    rows, cols = df.shape

    # 1. Missing Values
    null_counts = df.isnull().sum()
    for col, n_null in null_counts[null_counts > 0].items():
        pct = (n_null / rows) * 100
        issues.append({
            "issue": f"{n_null} missing values ({pct:.1f}%) in '{col}'",
            "category": "Missing Values",
            "column": str(col),
            "impact": "HIGH" if pct > 20 else "MEDIUM",
            "recommendation": f"Impute missing values with {'median' if pd.api.types.is_numeric_dtype(df[col]) else 'mode'} or drop empty rows.",
            "confidence": 95,
            "auto_fixable": True
        })

    # 2. Duplicates
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        issues.append({
            "issue": f"{dup_count} exact duplicate rows detected",
            "category": "Duplicates",
            "column": "ALL",
            "impact": "MEDIUM",
            "recommendation": "Remove duplicate rows to prevent skewed aggregate totals.",
            "confidence": 99,
            "auto_fixable": True
        })

    # 3. Empty Columns
    for col in df.columns:
        if df[col].isnull().all():
            issues.append({
                "issue": f"Column '{col}' is completely empty (100% nulls)",
                "category": "Empty Column",
                "column": str(col),
                "impact": "HIGH",
                "recommendation": "Drop this 100% empty feature column.",
                "confidence": 100,
                "auto_fixable": True
            })

    # 4. Constant / Single Value Columns
    for col in df.columns:
        if df[col].nunique() == 1 and rows > 1:
            issues.append({
                "issue": f"Column '{col}' has zero variance (only 1 unique value: '{df[col].iloc[0]}')",
                "category": "Constant Column",
                "column": str(col),
                "impact": "LOW",
                "recommendation": "Drop constant column as it provides zero predictive information.",
                "confidence": 90,
                "auto_fixable": True
            })

    # 5. Outliers in numeric columns
    num_cols = df.select_dtypes(include=np.number).columns.tolist()
    for col in num_cols:
        s = df[col].dropna()
        if len(s) > 10 and s.std() > 0:
            z = np.abs((s - s.mean()) / s.std())
            n_outliers = (z > 3.0).sum()
            if n_outliers > 0:
                issues.append({
                    "issue": f"{n_outliers} statistical extreme outliers in '{col}'",
                    "category": "Outliers",
                    "column": str(col),
                    "impact": "MEDIUM",
                    "recommendation": "Cap extreme values using 99th percentile capping.",
                    "confidence": 88,
                    "auto_fixable": True
                })

    return issues


# ─────────────────────────────────────────────────────────
# ROOT CAUSE ANALYTICS TOOL
# ─────────────────────────────────────────────────────────

def run_root_cause_analysis(df: pd.DataFrame, target_metric: str) -> Dict[str, Any]:
    if target_metric not in df.columns or not pd.api.types.is_numeric_dtype(df[target_metric]):
        num_cols = df.select_dtypes(include=np.number).columns.tolist()
        if not num_cols:
            return {"error": "No numeric metric found for root cause analysis"}
        target_metric = num_cols[0]

    cat_cols = df.select_dtypes(exclude=np.number).columns.tolist()
    valid_cats = [c for c in cat_cols if 2 <= df[c].nunique() <= 30]

    tree = []
    primary_driver = "Overall Distribution"

    if valid_cats:
        dim = valid_cats[0]
        primary_driver = dim
        grp = df.groupby(dim)[target_metric].agg(['sum', 'mean', 'count']).sort_values(by='sum', ascending=False)
        top_cat = grp.index[0]
        top_share = (grp['sum'].iloc[0] / max(grp['sum'].sum(), 1)) * 100

        tree.append({
            "level": "1. Metric Baseline",
            "finding": f"Target metric '{target_metric}' total sum is {df[target_metric].sum():,.2f} with average of {df[target_metric].mean():,.2f}."
        })
        tree.append({
            "level": f"2. Primary Dimension Breakdown ({dim})",
            "finding": f"Sub-segment '{top_cat}' is the primary driver, accounting for {top_share:.1f}% of total {target_metric}."
        })

        if len(valid_cats) > 1:
          dim2 = valid_cats[1]
          sub_df = df[df[dim] == top_cat]
          grp2 = sub_df.groupby(dim2)[target_metric].sum().sort_values(ascending=False)
          if len(grp2):
              tree.append({
                  "level": f"3. Secondary Breakdown ({dim2} within {top_cat})",
                  "finding": f"Within '{top_cat}', key contributor is '{grp2.index[0]}' driving {grp2.iloc[0]:,.2f}."
              })

    return {
        "metric": target_metric,
        "primary_driver": primary_driver,
        "reasoning_chain": tree,
        "recommendation": f"Focus optimizations on top driver category '{primary_driver}' to achieve highest incremental impact."
    }


# ─────────────────────────────────────────────────────────
# PDF EXECUTIVE REPORT GENERATOR (REPORTLAB)
# ─────────────────────────────────────────────────────────

def generate_pdf_report_bytes(df: pd.DataFrame, domain: str = "General Analytics") -> bytes:
    """Generates a professional executive PDF summary report using ReportLab."""
    import io
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=22,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=12
    )
    heading_style = ParagraphStyle(
        'DocHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=14,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6
    )

    # Title & Metadata
    story.append(Paragraph("InsightFlow Executive Analytics Report", title_style))
    story.append(Paragraph(f"<b>Domain:</b> {domain} | <b>Generated:</b> {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}", body_style))
    story.append(Spacer(1, 12))

    # Overview Table
    num_cols = df.select_dtypes(include=np.number).columns.tolist()
    cat_cols = df.select_dtypes(exclude=np.number).columns.tolist()
    missing_count = int(df.isnull().sum().sum())
    dup_count = int(df.duplicated().sum())

    summary_data = [
        ["Metric", "Value"],
        ["Total Rows", f"{len(df):,}"],
        ["Total Columns", f"{len(df.columns)}"],
        ["Numeric Features", f"{len(num_cols)}"],
        ["Categorical Features", f"{len(cat_cols)}"],
        ["Missing Values", f"{missing_count:,}"],
        ["Duplicate Rows", f"{dup_count:,}"]
    ]
    t = Table(summary_data, colWidths=[200, 300])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0"))
    ]))
    story.append(Paragraph("Dataset Overview", heading_style))
    story.append(t)
    story.append(Spacer(1, 14))

    # Key Numeric Metrics Table
    if num_cols:
        story.append(Paragraph("Key Numerical Statistics", heading_style))
        stats_data = [["Column", "Mean", "Median", "Min", "Max", "Std Dev"]]
        for c in num_cols[:6]:
            s = df[c].dropna()
            if len(s):
                stats_data.append([
                    str(c),
                    f"{s.mean():,.2f}",
                    f"{s.median():,.2f}",
                    f"{s.min():,.2f}",
                    f"{s.max():,.2f}",
                    f"{s.std():,.2f}"
                ])
        st_table = Table(stats_data, colWidths=[110, 80, 80, 80, 80, 70])
        st_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f1f5f9"), colors.white]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1"))
        ]))
        story.append(st_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

