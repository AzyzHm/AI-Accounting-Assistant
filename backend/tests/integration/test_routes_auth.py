import pytest
from fastapi.testclient import TestClient

from core.security import get_current_user
from tests.setup.fakes import FakeFirestore


@pytest.fixture()
def auth_client(monkeypatch):
    """
    Yields a factory `make_client(current_user, users=None)` returning a
    TestClient with get_current_user overridden and services.users_service /
    services.stats_service both backed by the same fresh FakeFirestore.
    """
    from main import app as _app
    from services import stats_service, users_service

    def make_client(current_user, users=None):
        fake_db = FakeFirestore(users=users or {})
        monkeypatch.setattr(users_service, "get_firestore_client", lambda: fake_db)
        monkeypatch.setattr(stats_service, "get_firestore_client", lambda: fake_db)
        _app.dependency_overrides[get_current_user] = lambda: current_user
        return TestClient(_app), fake_db

    yield make_client

    _app.dependency_overrides.pop(get_current_user, None)


class TestReadCurrentUser:
    def test_returns_the_caller_s_profile(self, auth_client):
        client, _fake_db = auth_client(
            current_user={"uid": "u1", "email": "a@a.com", "role": "USER"},
            users={"u1": {"email": "a@a.com", "role": "USER"}},
        )

        response = client.get("/auth/me")

        assert response.status_code == 200
        assert response.json() == {"uid": "u1", "email": "a@a.com", "role": "USER"}

    def test_logs_a_login_event_with_the_caller_s_ip(self, auth_client):
        client, fake_db = auth_client(
            current_user={"uid": "u1", "email": "a@a.com", "role": "USER"},
            users={"u1": {"email": "a@a.com", "role": "USER"}},
        )

        client.get("/auth/me")

        events = fake_db.collection("login_events").stream()
        assert len(events) == 1
        assert events[0].to_dict()["uid"] == "u1"

    def test_stamps_the_profile_with_last_login(self, auth_client):
        client, fake_db = auth_client(
            current_user={"uid": "u1", "email": "a@a.com", "role": "USER"},
            users={"u1": {"email": "a@a.com", "role": "USER"}},
        )

        client.get("/auth/me")

        profile = fake_db.collection("users").document("u1").get().to_dict()
        assert "last_login_at" in profile

    def test_logs_a_fresh_event_on_every_call(self, auth_client):
        client, fake_db = auth_client(
            current_user={"uid": "u1", "email": "a@a.com", "role": "USER"},
            users={"u1": {"email": "a@a.com", "role": "USER"}},
        )

        client.get("/auth/me")
        client.get("/auth/me")

        assert len(fake_db.collection("login_events").stream()) == 2


class TestUpdateCurrentUser:
    def test_updates_display_name(self, auth_client):
        client, _fake_db = auth_client(
            current_user={"uid": "u1", "email": "a@a.com", "role": "USER"},
            users={"u1": {"email": "a@a.com", "display_name": "Old", "role": "USER"}},
        )

        response = client.patch("/auth/me", json={"display_name": "New Name"})

        assert response.status_code == 200
        assert response.json()["display_name"] == "New Name"

    def test_updates_email(self, auth_client):
        client, _fake_db = auth_client(
            current_user={"uid": "u1", "email": "old@a.com", "role": "USER"},
            users={"u1": {"email": "old@a.com", "role": "USER"}},
        )

        response = client.patch("/auth/me", json={"email": "new@a.com"})

        assert response.status_code == 200
        assert response.json()["email"] == "new@a.com"

    def test_persists_the_change_in_firestore(self, auth_client):
        client, fake_db = auth_client(
            current_user={"uid": "u1", "email": "a@a.com", "role": "USER"},
            users={"u1": {"email": "a@a.com", "role": "USER"}},
        )

        client.patch("/auth/me", json={"display_name": "Persisted"})

        profile = fake_db.collection("users").document("u1").get().to_dict()
        assert profile["display_name"] == "Persisted"

    def test_partial_update_leaves_role_untouched(self, auth_client):
        client, _fake_db = auth_client(
            current_user={"uid": "u1", "email": "a@a.com", "role": "ADMIN"},
            users={"u1": {"email": "a@a.com", "role": "ADMIN"}},
        )

        response = client.patch("/auth/me", json={"display_name": "New"})

        assert response.json()["role"] == "ADMIN"
