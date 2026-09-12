import pytest
from fastapi.testclient import TestClient

from core.security import get_current_user
from tests.setup.fakes import FakeFirestore


@pytest.fixture()
def admin_client(monkeypatch):
    """
    Yields a factory `make_client(current_user, users)` returning a TestClient
    with get_current_user overridden to `current_user` and services.users_service
    (plus services.stats_service and services.limits_service, used by the
    stats and limits endpoints) backed by a fresh FakeFirestore seeded with
    `users`. `routes.admin.firebase_auth.delete_user` is replaced with a
    no-op recorder, exposed as `make_client.deleted_auth_uids`, so delete
    tests never make a real call to Firebase and can assert on what would
    have been deleted.

    Shared across test_routes_admin.py and test_routes_admin_limits.py, the
    admin route tests are split across those two files to stay under the
    per-file line guardrail.
    """
    import routes.admin as r_admin
    from main import app as _app
    from services import limits_service, stats_service, users_service

    deleted_auth_uids: list[str] = []

    def make_client(current_user, users):
        fake_db = FakeFirestore(users=users)
        monkeypatch.setattr(users_service, "get_firestore_client", lambda: fake_db)
        monkeypatch.setattr(stats_service, "get_firestore_client", lambda: fake_db)
        monkeypatch.setattr(limits_service, "get_firestore_client", lambda: fake_db)
        monkeypatch.setattr(r_admin.firebase_auth, "delete_user", deleted_auth_uids.append)
        _app.dependency_overrides[get_current_user] = lambda: current_user
        return TestClient(_app), fake_db

    make_client.deleted_auth_uids = deleted_auth_uids

    yield make_client

    _app.dependency_overrides.pop(get_current_user, None)
