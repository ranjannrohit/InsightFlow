import pytest
import os
import sys
import io
import pandas as pd
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from main import app
import database

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    database.init_db()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def sample_csv_bytes():
    df = pd.DataFrame({
        "Category": ["Electronics", "Furniture", "Electronics", "Clothing", "Furniture", "Clothing"],
        "Sales": [1200.50, 450.00, 890.00, 150.25, 600.00, 310.00],
        "Units": [5, 2, 4, 1, 3, 2],
        "Customer_ID": [101, 102, 103, 104, 105, 106]
    })
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf.getvalue()
