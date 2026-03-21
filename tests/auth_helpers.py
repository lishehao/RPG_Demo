from __future__ import annotations

from fastapi.testclient import TestClient

DEFAULT_TEST_PASSWORD = "TestPass123!"


def ensure_authenticated_client(
    client: TestClient,
    *,
    email: str,
    display_name: str,
    password: str = DEFAULT_TEST_PASSWORD,
):
    register_response = client.post(
        "/auth/register",
        json={
            "display_name": display_name,
            "email": email,
            "password": password,
        },
    )
    if register_response.status_code == 200:
        return register_response
    if register_response.status_code == 409:
        login_response = client.post(
            "/auth/login",
            json={
                "email": email,
                "password": password,
            },
        )
        assert login_response.status_code == 200, login_response.text
        return login_response
    raise AssertionError(register_response.text)
