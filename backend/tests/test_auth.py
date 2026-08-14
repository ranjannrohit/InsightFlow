import pytest
import uuid

def test_auth_flow(client):
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecretPassword123"

    # 1. Signup
    signup_res = client.post("/api/auth/signup", json={
        "name": "Test User",
        "email": unique_email,
        "password": password,
        "confirm_password": password
    })
    assert signup_res.status_code == 200
    signup_data = signup_res.json()
    assert "token" in signup_data
    token = signup_data["token"]
    assert signup_data["user"]["email"] == unique_email.lower()

    # 2. Auth Me
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["user"]["email"] == unique_email.lower()

    # 3. Update Profile
    update_res = client.put("/api/user/profile", json={
        "name": "Updated User Name",
        "theme": "light"
    }, headers={"Authorization": f"Bearer {token}"})
    assert update_res.status_code == 200
    assert update_res.json()["user"]["name"] == "Updated User Name"

    # 4. Change Password
    new_password = "BrandNewPassword123"
    change_res = client.post("/api/user/change-password", json={
        "old_password": password,
        "new_password": new_password,
        "confirm_password": new_password
    }, headers={"Authorization": f"Bearer {token}"})
    assert change_res.status_code == 200

    # 5. Login with new password
    login_res = client.post("/api/auth/login", json={
        "email": unique_email,
        "password": new_password
    })
    assert login_res.status_code == 200
    assert "token" in login_res.json()

    # 6. Forgot Password
    forgot_res = client.post("/api/auth/forgot-password", json={"email": unique_email})
    assert forgot_res.status_code == 200
    reset_token = forgot_res.json().get("reset_token")
    assert reset_token is not None

    # 7. Reset Password
    reset_res = client.post("/api/auth/reset-password", json={
        "token": reset_token,
        "new_password": "ResetPassword456",
        "confirm_password": "ResetPassword456"
    })
    assert reset_res.status_code == 200

    # 8. Logout
    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200


def test_google_auth_flow(client):
    google_id = f"goog_{uuid.uuid4().hex[:10]}"
    email = f"google_user_{uuid.uuid4().hex[:6]}@gmail.com"

    res = client.post("/api/auth/google", json={
        "email": email,
        "name": "Google User",
        "google_id": google_id,
        "profile_photo": "https://lh3.googleusercontent.com/a/default-user",
        "remember_me": True
    })

    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["user"]["email"] == email.lower()
    assert data["user"]["google_id"] == google_id

    # Test login again with existing Google user
    res2 = client.post("/api/auth/google", json={
        "email": email,
        "name": "Google User Updated",
        "google_id": google_id,
        "remember_me": True
    })

    assert res2.status_code == 200
    assert res2.json()["user"]["google_id"] == google_id

