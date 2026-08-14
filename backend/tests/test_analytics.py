import pytest

def test_analytics_and_agent_endpoints(client, sample_csv_bytes):
    # Upload dataset first
    upload_res = client.post("/upload", files={"file": ("analytics_data.csv", sample_csv_bytes, "text/csv")})
    assert upload_res.status_code == 200

    # 1. Auto Dashboard
    db_res = client.get("/auto-dashboard")
    assert db_res.status_code == 200
    assert "kpis" in db_res.json()

    # 2. Custom Widget
    widget_res = client.post("/custom-widget", json={
        "widget_type": "bar",
        "title": "Sales by Category",
        "x_col": "Category",
        "y_col": "Sales",
        "agg": "SUM"
    })
    assert widget_res.status_code == 200
    assert "widget" in widget_res.json()

    # 3. Data Preview & Columns Info
    data_res = client.get("/data?limit=5")
    assert data_res.status_code == 200
    assert len(data_res.json()["rows"]) <= 5

    cols_res = client.get("/api/data/columns")
    assert cols_res.status_code == 200
    assert len(cols_res.json()["columns"]) == 4

    # 4. Filter Data
    filter_res = client.post("/api/data/filter", json={
        "column": "Category",
        "operator": "equals",
        "value": "Electronics"
    })
    assert filter_res.status_code == 200
    assert len(filter_res.json()["rows"]) == 2

    # 5. EDA
    eda_res = client.get("/eda")
    assert eda_res.status_code == 200
    assert "shape" in eda_res.json()

    # 6. Cleaning Audit & Auto Fix
    clean_res = client.get("/cleaning")
    assert clean_res.status_code == 200

    audit_res = client.post("/api/v2/clean-audit")
    assert audit_res.status_code == 200

    autofix_res = client.post("/api/v2/auto-fix", json={"action": "drop_duplicates"})
    assert autofix_res.status_code == 200

    # 7. Agentic BI Endpoints
    forecast_res = client.get("/api/v3/forecast?target_col=Sales&periods=3")
    assert forecast_res.status_code == 200
    assert "forecast" in forecast_res.json()

    anomalies_res = client.get("/api/v3/anomalies")
    assert anomalies_res.status_code == 200

    seg_res = client.get("/api/v3/segmentation")
    assert seg_res.status_code == 200

    rca_res = client.post("/api/v2/root-cause", json={"metric": "Sales"})
    assert rca_res.status_code == 200

    plan_res = client.post("/api/v4/agent-plan", json={"goal": "Analyze sales performance"})
    assert plan_res.status_code == 200

    # 8. SQL Query execution
    sql_res = client.post("/run-sql", json={"query": "SELECT Category, SUM(Sales) as Total FROM data GROUP BY Category"})
    assert sql_res.status_code == 200
    assert "rows" in sql_res.json()
