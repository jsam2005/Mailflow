"""Authentication endpoint tests."""

from fastapi.testclient import TestClient

from app.models.user import User


def test_login_success(client: TestClient, admin_user: User) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "test-admin-password"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == admin_user.email
    assert body["user"]["name"] == admin_user.name
    assert "password_hash" not in body["user"]


def test_login_invalid_password(client: TestClient, admin_user: User) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "wrong-password"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "unauthorized"
    assert "password" not in body["error"].lower() or "invalid" in body["error"].lower()


def test_login_unknown_user(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "anything"},
    )
    assert response.status_code == 401


def test_me_unauthorized(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_invalid_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


def test_me_authorized(client: TestClient, admin_user: User) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "test-admin-password"},
    )
    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == admin_user.email
    assert body["id"] == str(admin_user.id)
