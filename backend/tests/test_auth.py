"""Auth endpoint tests."""

from __future__ import annotations

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret-password")
    assert hashed != "s3cret-password"
    assert verify_password("s3cret-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_verify_password_rejects_garbage():
    assert not verify_password("", "")
    assert not verify_password("x", "not-a-bcrypt-hash")


def test_password_longer_than_72_bytes_is_handled():
    """bcrypt only reads 72 bytes; the helper must not raise on long input."""
    long_password = "a" * 200
    hashed = hash_password(long_password)
    assert verify_password(long_password, hashed)
    # Same first 72 bytes -> same result, which is bcrypt's documented behaviour.
    assert verify_password("a" * 72 + "DIFFERENT", hashed)


def test_access_token_roundtrip():
    token = create_access_token("user-123", role="DOCTOR")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "DOCTOR"
    assert payload["typ"] == "access"


def test_login_success(app_client, staff_user):
    response = app_client.post(
        "/api/auth/login",
        json={"username": "testdoctor", "password": "test-password-123"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == "testdoctor"
    assert "password_hash" not in body["user"]


def test_login_wrong_password_uses_unified_error(app_client, staff_user):
    response = app_client.post(
        "/api/auth/login",
        json={"username": "testdoctor", "password": "wrong"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "INVALID_CREDENTIALS"
    assert "message" in body["error"]


def test_login_unknown_user_gives_same_message(app_client, staff_user):
    """Unknown user and wrong password must be indistinguishable."""
    unknown = app_client.post(
        "/api/auth/login", json={"username": "nobody", "password": "whatever"}
    )
    wrong = app_client.post(
        "/api/auth/login", json={"username": "testdoctor", "password": "whatever"}
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error"]["code"] == wrong.json()["error"]["code"]
    assert unknown.json()["error"]["message"] == wrong.json()["error"]["message"]


def test_inactive_user_cannot_login(app_client, db, staff_user):
    staff_user.is_active = False
    db.commit()
    response = app_client.post(
        "/api/auth/login",
        json={"username": "testdoctor", "password": "test-password-123"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INACTIVE_USER"


def test_me_requires_token(app_client):
    response = app_client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_me_returns_current_user(app_client, auth_headers):
    response = app_client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == "testdoctor"


def test_me_rejects_invalid_token(app_client):
    response = app_client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not.a.token"}
    )
    assert response.status_code == 401


def test_logout(app_client, auth_headers):
    response = app_client.post("/api/auth/logout", headers=auth_headers)
    assert response.status_code == 200
    assert "已登出" in response.json()["message"]
