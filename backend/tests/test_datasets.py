import pytest
import uuid

def test_dataset_upload_and_export(client, sample_csv_bytes):
    # Upload CSV as guest
    res = client.post("/upload", files={"file": ("test_data.csv", sample_csv_bytes, "text/csv")})
    assert res.status_code == 200
    data = res.json()
    assert "summary" in data
    assert data["summary"]["rows"] == 6

    # Test status endpoint
    status_res = client.get("/status")
    assert status_res.status_code == 200
    assert status_res.json()["dataset_loaded"] is True

    # Test CSV Export
    csv_res = client.get("/export/csv")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]

    # Test Excel Export
    excel_res = client.get("/export/excel")
    assert excel_res.status_code == 200
    assert "spreadsheetml" in excel_res.headers["content-type"]

    # Test PDF Report Export
    pdf_res = client.get("/export/pdf-report")
    assert pdf_res.status_code == 200
    assert "application/pdf" in pdf_res.headers["content-type"]


def test_authenticated_dataset_history(client, sample_csv_bytes):
    # Create user & login
    email = f"ds_user_{uuid.uuid4().hex[:6]}@example.com"
    pwd = "DatasetUser123"
    signup_res = client.post("/api/auth/signup", json={
        "name": "Dataset Tester",
        "email": email,
        "password": pwd,
        "confirm_password": pwd
    })
    token = signup_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Upload dataset while authenticated
    upload_res = client.post(
        "/upload",
        files={"file": ("sales_records.csv", sample_csv_bytes, "text/csv")},
        headers=headers
    )
    assert upload_res.status_code == 200
    meta = upload_res.json().get("dataset")
    assert meta is not None
    dataset_id = meta["id"]

    # List datasets
    list_res = client.get("/api/datasets", headers=headers)
    assert list_res.status_code == 200
    datasets = list_res.json()["datasets"]
    assert len(datasets) >= 1

    # Activate dataset
    act_res = client.post(f"/api/datasets/{dataset_id}/activate", headers=headers)
    assert act_res.status_code == 200

    # Delete dataset
    del_res = client.delete(f"/api/datasets/{dataset_id}", headers=headers)
    assert del_res.status_code == 200
