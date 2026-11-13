"""Desktop auto sign-in must only work for the exe's own loopback page."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.models.user import User

URL = "/api/v1/auth/desktop-session"
OK_HEADERS = {"X-MailFlow-Desktop": "1", "Host": "127.0.0.1:8000"}


@pytest.fixture()
def desktop_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAILFLOW_DESKTOP", "1")


def _from_loopback():
    # TestClient reports its peer as "testclient"; pretend to be loopback.
    return patch("app.api.routes.auth._client_host", return_value="127.0.0.1")


def test_desktop_session_signs_in_admin(client: TestClient, admin_user: User, desktop_env) -> None:
    with _from_loopback():
        response = client.post(URL, headers=OK_HEADERS)
    assert response.status_code == 200
    token = response.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == admin_user.email


def test_desktop_session_off_outside_desktop_mode(client: TestClient, admin_user: User, monkeypatch) -> None:
    monkeypatch.delenv("MAILFLOW_DESKTOP", raising=False)
    with _from_loopback():
        assert client.post(URL, headers=OK_HEADERS).status_code == 404


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "127.0.0.1:8000"},
        {"X-MailFlow-Desktop": "1", "Host": "evil.example:8000"},
        {**OK_HEADERS, "Origin": "https://evil.example"},
    ],
)
def test_desktop_session_rejects_foreign_requests(
    client: TestClient, admin_user: User, desktop_env, headers
) -> None:
    with _from_loopback():
        assert client.post(URL, headers=headers).status_code == 404


def test_desktop_session_rejects_non_loopback_peer(client: TestClient, admin_user: User, desktop_env) -> None:
    assert client.post(URL, headers=OK_HEADERS).status_code == 404
