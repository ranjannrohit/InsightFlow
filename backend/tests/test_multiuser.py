"""
InsightFlow — Multi-User Isolation & Security Tests

Tests every critical security boundary:
- User A cannot access User B's data
- Credits are enforced per user
- History and notifications are user-scoped
- Settings belong to authenticated user only
"""

import pytest
import uuid
import io
import pandas as pd


def make_test_user(client, name_prefix="User"):
    """Helper: creates a unique user and returns (user_data, token)."""
    unique_email = f"{name_prefix.lower()}_{uuid.uuid4().hex[:8]}@testdomain.com"
    password = "TestPassword123"
    res = client.post("/api/auth/signup", json={
        "name": f"{name_prefix} Test",
        "email": unique_email,
        "password": password,
        "confirm_password": password
    })
    assert res.status_code == 200, f"Signup failed: {res.text}"
    data = res.json()
    return data["user"], data["token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def sample_csv_bytes_fixture() -> bytes:
    df = pd.DataFrame({
        "Category": ["Electronics", "Furniture", "Electronics"],
        "Sales": [1200.50, 450.00, 890.00],
        "Units": [5, 2, 4],
    })
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────
# DATASET ISOLATION
# ─────────────────────────────────────────────────────────

class TestDatasetIsolation:
    def test_user_a_cannot_see_user_b_dataset(self, client):
        user_a, token_a = make_test_user(client, "Alice")
        user_b, token_b = make_test_user(client, "Bob")

        # Upload dataset as User A
        csv_bytes = sample_csv_bytes_fixture()
        upload_res = client.post(
            "/upload",
            files={"file": ("test_a.csv", csv_bytes, "text/csv")},
            headers=auth_headers(token_a)
        )
        assert upload_res.status_code == 200
        dataset_data = upload_res.json().get("dataset")
        assert dataset_data is not None
        dataset_id = dataset_data["id"]

        # User A can see their dataset
        list_a = client.get("/api/datasets", headers=auth_headers(token_a))
        assert list_a.status_code == 200
        a_ids = [d["id"] for d in list_a.json()["datasets"]]
        assert dataset_id in a_ids

        # User B cannot see User A's dataset in their list
        list_b = client.get("/api/datasets", headers=auth_headers(token_b))
        assert list_b.status_code == 200
        b_ids = [d["id"] for d in list_b.json()["datasets"]]
        assert dataset_id not in b_ids

    def test_user_b_cannot_access_user_a_dataset_directly(self, client):
        user_a, token_a = make_test_user(client, "Alice2")
        user_b, token_b = make_test_user(client, "Bob2")

        csv_bytes = sample_csv_bytes_fixture()
        upload_res = client.post(
            "/upload",
            files={"file": ("private.csv", csv_bytes, "text/csv")},
            headers=auth_headers(token_a)
        )
        assert upload_res.status_code == 200
        dataset_id = upload_res.json()["dataset"]["id"]

        # User B tries to directly access User A's dataset
        get_res = client.get(f"/api/datasets/{dataset_id}", headers=auth_headers(token_b))
        assert get_res.status_code == 404, "User B should not be able to access User A's dataset"

    def test_user_b_cannot_delete_user_a_dataset(self, client):
        user_a, token_a = make_test_user(client, "Alice3")
        user_b, token_b = make_test_user(client, "Bob3")

        csv_bytes = sample_csv_bytes_fixture()
        upload_res = client.post(
            "/upload",
            files={"file": ("todelete.csv", csv_bytes, "text/csv")},
            headers=auth_headers(token_a)
        )
        dataset_id = upload_res.json()["dataset"]["id"]

        # User B tries to delete User A's dataset
        del_res = client.delete(f"/api/datasets/{dataset_id}", headers=auth_headers(token_b))
        assert del_res.status_code == 404, "User B should not be able to delete User A's dataset"

        # User A's dataset still exists
        get_res = client.get(f"/api/datasets/{dataset_id}", headers=auth_headers(token_a))
        assert get_res.status_code == 200

    def test_unauthenticated_cannot_list_datasets(self, client):
        res = client.get("/api/datasets")
        assert res.status_code == 200
        # Guest returns empty list (not 401) per existing logic
        assert res.json()["datasets"] == []


# ─────────────────────────────────────────────────────────
# HISTORY ISOLATION
# ─────────────────────────────────────────────────────────

class TestHistoryIsolation:
    def test_history_is_user_scoped(self, client):
        user_a, token_a = make_test_user(client, "HistA")
        user_b, token_b = make_test_user(client, "HistB")

        # Upload triggers a history record for User A
        csv_bytes = sample_csv_bytes_fixture()
        client.post(
            "/upload",
            files={"file": ("hist_test.csv", csv_bytes, "text/csv")},
            headers=auth_headers(token_a)
        )

        # User A sees history
        hist_a = client.get("/api/history", headers=auth_headers(token_a))
        assert hist_a.status_code == 200
        assert hist_a.json()["total"] > 0

        # User B sees their own (empty) history
        hist_b = client.get("/api/history", headers=auth_headers(token_b))
        assert hist_b.status_code == 200
        assert hist_b.json()["total"] == 0

    def test_history_requires_authentication(self, client):
        res = client.get("/api/history")
        assert res.status_code == 401


# ─────────────────────────────────────────────────────────
# NOTIFICATIONS ISOLATION
# ─────────────────────────────────────────────────────────

class TestNotificationsIsolation:
    def test_notifications_are_user_scoped(self, client):
        user_a, token_a = make_test_user(client, "NotifA")
        user_b, token_b = make_test_user(client, "NotifB")

        # Upload triggers a notification for User A
        csv_bytes = sample_csv_bytes_fixture()
        client.post(
            "/upload",
            files={"file": ("notif_test.csv", csv_bytes, "text/csv")},
            headers=auth_headers(token_a)
        )

        # User A has a notification
        notif_a = client.get("/api/notifications", headers=auth_headers(token_a))
        assert notif_a.status_code == 200
        assert len(notif_a.json()["notifications"]) > 0

        # User B has no notifications
        notif_b = client.get("/api/notifications", headers=auth_headers(token_b))
        assert notif_b.status_code == 200
        assert len(notif_b.json()["notifications"]) == 0

    def test_user_b_cannot_mark_user_a_notification_read(self, client):
        user_a, token_a = make_test_user(client, "NotifC")
        user_b, token_b = make_test_user(client, "NotifD")

        # Create a notification for User A via upload
        csv_bytes = sample_csv_bytes_fixture()
        client.post("/upload", files={"file": ("n.csv", csv_bytes, "text/csv")}, headers=auth_headers(token_a))

        # Get the notification ID
        notif_a = client.get("/api/notifications", headers=auth_headers(token_a))
        assert len(notif_a.json()["notifications"]) > 0
        notif_id = notif_a.json()["notifications"][0]["id"]

        # User B tries to mark it as read — should 404
        res = client.put(f"/api/notifications/{notif_id}/read", headers=auth_headers(token_b))
        assert res.status_code == 404


# ─────────────────────────────────────────────────────────
# CREDITS ISOLATION
# ─────────────────────────────────────────────────────────

class TestCredits:
    def test_new_user_has_100_credits(self, client):
        user, token = make_test_user(client, "Credits")
        res = client.get("/api/credits", headers=auth_headers(token))
        assert res.status_code == 200
        data = res.json()
        assert data["balance"] == 100
        assert data["daily_limit"] == 100

    def test_credits_require_authentication(self, client):
        res = client.get("/api/credits")
        assert res.status_code == 401

    def test_credits_are_independent_per_user(self, client):
        user_a, token_a = make_test_user(client, "CreditA")
        user_b, token_b = make_test_user(client, "CreditB")

        credits_a = client.get("/api/credits", headers=auth_headers(token_a))
        credits_b = client.get("/api/credits", headers=auth_headers(token_b))

        assert credits_a.json()["balance"] == 100
        assert credits_b.json()["balance"] == 100

        # User A resets credits (debug endpoint)
        client.post("/api/credits/reset", headers=auth_headers(token_a))

        # User B's credits are unaffected
        credits_b_after = client.get("/api/credits", headers=auth_headers(token_b))
        assert credits_b_after.json()["balance"] == 100


# ─────────────────────────────────────────────────────────
# SETTINGS ISOLATION
# ─────────────────────────────────────────────────────────

class TestSettingsIsolation:
    def test_settings_are_user_scoped(self, client):
        user_a, token_a = make_test_user(client, "SettA")
        user_b, token_b = make_test_user(client, "SettB")

        # User A saves dark theme
        client.put(
            "/api/users/me/settings",
            json={"theme": "dark", "language": "en"},
            headers=auth_headers(token_a)
        )

        # User B saves light theme
        client.put(
            "/api/users/me/settings",
            json={"theme": "light", "language": "fr"},
            headers=auth_headers(token_b)
        )

        # Verify settings are distinct
        sett_a = client.get("/api/users/me/settings", headers=auth_headers(token_a))
        sett_b = client.get("/api/users/me/settings", headers=auth_headers(token_b))

        assert sett_a.json()["settings"]["theme"] == "dark"
        assert sett_b.json()["settings"]["theme"] == "light"
        assert sett_a.json()["settings"]["language"] == "en"
        assert sett_b.json()["settings"]["language"] == "fr"

    def test_settings_require_authentication(self, client):
        res = client.get("/api/users/me/settings")
        assert res.status_code == 401

        put_res = client.put("/api/users/me/settings", json={"theme": "light"})
        assert put_res.status_code == 401


# ─────────────────────────────────────────────────────────
# CHAT SESSION ISOLATION
# ─────────────────────────────────────────────────────────

class TestChatIsolation:
    def test_chat_sessions_are_user_scoped(self, client):
        user_a, token_a = make_test_user(client, "ChatA")
        user_b, token_b = make_test_user(client, "ChatB")

        # User A creates a session
        sess_res = client.post(
            "/api/chat/sessions",
            json={"title": "User A Private Chat"},
            headers=auth_headers(token_a)
        )
        assert sess_res.status_code == 200
        session_id = sess_res.json()["session"]["id"]

        # User A can see their sessions
        sessions_a = client.get("/api/chat/sessions", headers=auth_headers(token_a))
        a_session_ids = [s["id"] for s in sessions_a.json()["sessions"]]
        assert session_id in a_session_ids

        # User B cannot see User A's sessions
        sessions_b = client.get("/api/chat/sessions", headers=auth_headers(token_b))
        b_session_ids = [s["id"] for s in sessions_b.json()["sessions"]]
        assert session_id not in b_session_ids

    def test_user_b_cannot_access_user_a_chat_session(self, client):
        user_a, token_a = make_test_user(client, "ChatC")
        user_b, token_b = make_test_user(client, "ChatD")

        sess_res = client.post(
            "/api/chat/sessions",
            json={"title": "Secret Chat"},
            headers=auth_headers(token_a)
        )
        session_id = sess_res.json()["session"]["id"]

        # User B tries to read User A's messages
        msg_res = client.get(
            f"/api/chat/sessions/{session_id}/messages",
            headers=auth_headers(token_b)
        )
        assert msg_res.status_code == 404


# ─────────────────────────────────────────────────────────
# AUTH ENDPOINTS SANITY
# ─────────────────────────────────────────────────────────

class TestAuthSanity:
    def test_me_endpoint_requires_auth(self, client):
        res = client.get("/api/users/me")
        assert res.status_code == 401

    def test_me_endpoint_returns_correct_user(self, client):
        user, token = make_test_user(client, "MeUser")
        res = client.get("/api/users/me", headers=auth_headers(token))
        assert res.status_code == 200
        assert res.json()["user"]["id"] == user["id"]

    def test_invalid_token_returns_401(self, client):
        res = client.get("/api/history", headers={"Authorization": "Bearer fake_invalid_token_xyz"})
        assert res.status_code == 401

    def test_missing_token_on_protected_endpoint(self, client):
        res = client.get("/api/forecast")
        assert res.status_code == 401


# ─────────────────────────────────────────────────────────
# DATAFRAME MULTI-TENANT ISOLATION & HYDRATION
# ─────────────────────────────────────────────────────────

class TestDataFrameMultiTenantIsolation:
    def test_user_data_queries_do_not_bleed(self, client):
        user_a, token_a = make_test_user(client, "DfIsoA")
        user_b, token_b = make_test_user(client, "DfIsoB")

        # User A uploads dataset A
        df_a = pd.DataFrame({"ProductA": ["Laptop", "Phone"], "SalesA": [1000, 500]})
        buf_a = io.BytesIO()
        df_a.to_csv(buf_a, index=False)
        buf_a.seek(0)
        client.post("/upload", files={"file": ("dataset_a.csv", buf_a.getvalue(), "text/csv")}, headers=auth_headers(token_a))

        # User B uploads dataset B
        df_b = pd.DataFrame({"VehicleB": ["Car", "Bike"], "CostB": [20000, 1500]})
        buf_b = io.BytesIO()
        df_b.to_csv(buf_b, index=False)
        buf_b.seek(0)
        client.post("/upload", files={"file": ("dataset_b.csv", buf_b.getvalue(), "text/csv")}, headers=auth_headers(token_b))

        # User A queries auto-dashboard -> sees ProductA & SalesA
        dash_a = client.get("/auto-dashboard", headers=auth_headers(token_a))
        assert dash_a.status_code == 200
        cols_a = dash_a.json()["available"]["all"]
        assert "ProductA" in cols_a
        assert "VehicleB" not in cols_a

        # User B queries auto-dashboard -> sees VehicleB & CostB
        dash_b = client.get("/auto-dashboard", headers=auth_headers(token_b))
        assert dash_b.status_code == 200
        cols_b = dash_b.json()["available"]["all"]
        assert "VehicleB" in cols_b
        assert "ProductA" not in cols_b

    def test_sqlite_dataset_auto_hydration(self, client):
        user, token = make_test_user(client, "HydrateUser")

        # Upload dataset
        df = pd.DataFrame({"City": ["New York", "London"], "Pop": [8000000, 9000000]})
        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        client.post("/upload", files={"file": ("cities.csv", buf.getvalue(), "text/csv")}, headers=auth_headers(token))

        # Clear in-memory datastores to simulate server restart / cache clear
        from main import USER_DATASTORES, DATASTORE
        USER_DATASTORES.clear()
        DATASTORE.clear()

        # User queries eda endpoint -> auto-hydrates from SQLite
        eda_res = client.get("/eda", headers=auth_headers(token))
        assert eda_res.status_code == 200
        assert "shape" in eda_res.json()
        assert eda_res.json()["shape"]["rows"] == 2

