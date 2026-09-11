import pytest
from fastapi.testclient import TestClient

from core.security import get_current_user
from tests.setup.fakes import FakeFirestore


@pytest.fixture()
def admin_client(monkeypatch):
    """
    Yields a factory `make_client(current_user, users)` returning a TestClient
    with get_current_user overridden to `current_user` and services.users_service
    (plus services.stats_service, used by the stats endpoints) backed by a fresh
    FakeFirestore seeded with `users`. `routes.admin.firebase_auth.delete_user`
    is replaced with a no-op recorder, exposed as `make_client.deleted_auth_uids`,
    so delete tests never make a real call to Firebase and can assert on what
    would have been deleted.
    """
    import routes.admin as r_admin
    from main import app as _app
    from services import stats_service, users_service

    deleted_auth_uids: list[str] = []

    def make_client(current_user, users):
        fake_db = FakeFirestore(users=users)
        monkeypatch.setattr(users_service, "get_firestore_client", lambda: fake_db)
        monkeypatch.setattr(stats_service, "get_firestore_client", lambda: fake_db)
        monkeypatch.setattr(r_admin.firebase_auth, "delete_user", deleted_auth_uids.append)
        _app.dependency_overrides[get_current_user] = lambda: current_user
        return TestClient(_app), fake_db

    make_client.deleted_auth_uids = deleted_auth_uids

    yield make_client

    _app.dependency_overrides.pop(get_current_user, None)


class TestListUsers:
    def test_admin_only_sees_user_accounts(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={
                "u1": {"email": "a@a.com", "role": "USER"},
                "a1": {"email": "other-admin@a.com", "role": "ADMIN"},
                "s1": {"email": "s@a.com", "role": "SUPER_ADMIN"},
            },
        )

        response = client.get("/admin/users")

        assert response.status_code == 200
        assert [u["uid"] for u in response.json()] == ["u1"]

    def test_super_admin_sees_users_and_admins_but_not_itself(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"},
            users={
                "u1": {"email": "a@a.com", "role": "USER"},
                "a1": {"email": "admin@a.com", "role": "ADMIN"},
                "super-1": {"email": "s@a.com", "role": "SUPER_ADMIN"},
            },
        )

        response = client.get("/admin/users")

        assert response.status_code == 200
        assert {u["uid"] for u in response.json()} == {"u1", "a1"}

    def test_plain_user_cannot_list_users(self, admin_client):
        client, _fake_db = admin_client(current_user={"uid": "u1", "role": "USER"}, users={})

        response = client.get("/admin/users")

        assert response.status_code == 403


class TestUpdateUserRole:
    def test_super_admin_can_grant_admin_role(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"},
            users={"target": {"email": "t@t.com", "role": "USER"}},
        )

        response = client.patch("/admin/users/target/role", json={"role": "ADMIN"})

        assert response.status_code == 200
        assert response.json()["role"] == "ADMIN"

    def test_granting_a_role_also_approves_the_account(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"},
            users={"target": {"email": "t@t.com", "role": "USER", "approved": False}},
        )

        response = client.patch("/admin/users/target/role", json={"role": "ADMIN"})

        assert response.status_code == 200
        assert response.json()["approved"] is True

    def test_super_admin_can_demote_an_admin_back_to_user(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"},
            users={"target": {"email": "t@t.com", "role": "ADMIN"}},
        )

        response = client.patch("/admin/users/target/role", json={"role": "USER"})

        assert response.status_code == 200
        assert response.json()["role"] == "USER"

    def test_super_admin_cannot_grant_super_admin_role(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"},
            users={"target": {"email": "t@t.com", "role": "USER"}},
        )

        response = client.patch("/admin/users/target/role", json={"role": "SUPER_ADMIN"})

        assert response.status_code == 403

    def test_admin_cannot_change_any_role(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={"target": {"email": "t@t.com", "role": "USER"}},
        )

        response = client.patch("/admin/users/target/role", json={"role": "ADMIN"})

        assert response.status_code == 403

    def test_cannot_change_own_role(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"},
            users={"super-1": {"email": "a@a.com", "role": "SUPER_ADMIN"}},
        )

        response = client.patch("/admin/users/super-1/role", json={"role": "USER"})

        assert response.status_code == 400

    def test_returns_404_for_unknown_user(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"}, users={}
        )

        response = client.patch("/admin/users/ghost/role", json={"role": "USER"})

        assert response.status_code == 404


class TestApproveUser:
    def test_admin_can_approve_a_pending_user(self, admin_client):
        client, fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={"target": {"email": "t@t.com", "role": "USER", "approved": False}},
        )

        response = client.patch("/admin/users/target/approve")

        assert response.status_code == 200
        assert response.json()["approved"] is True
        assert fake_db.collection("users").document("target").get().to_dict()["approved"] is True

    def test_super_admin_can_approve_a_pending_admin(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"},
            users={"target": {"email": "t@t.com", "role": "ADMIN", "approved": False}},
        )

        response = client.patch("/admin/users/target/approve")

        assert response.status_code == 200
        assert response.json()["approved"] is True

    def test_admin_cannot_approve_an_admin_account(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={"target": {"email": "t@t.com", "role": "ADMIN", "approved": False}},
        )

        response = client.patch("/admin/users/target/approve")

        assert response.status_code == 403

    def test_approving_an_already_approved_user_is_a_no_op(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={"target": {"email": "t@t.com", "role": "USER", "approved": True}},
        )

        response = client.patch("/admin/users/target/approve")

        assert response.status_code == 200
        assert response.json()["approved"] is True

    def test_cannot_approve_super_admin(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={"super-1": {"email": "s@a.com", "role": "SUPER_ADMIN", "approved": True}},
        )

        response = client.patch("/admin/users/super-1/approve")

        assert response.status_code == 403

    def test_plain_user_cannot_approve_anyone(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "u1", "role": "USER"},
            users={"target": {"email": "t@t.com", "role": "USER", "approved": False}},
        )

        response = client.patch("/admin/users/target/approve")

        assert response.status_code == 403

    def test_returns_404_for_unknown_user(self, admin_client):
        client, _fake_db = admin_client(current_user={"uid": "admin-1", "role": "ADMIN"}, users={})

        response = client.patch("/admin/users/ghost/approve")

        assert response.status_code == 404


class TestDeleteUser:
    def test_super_admin_can_delete_a_user(self, admin_client):
        client, fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"},
            users={"target": {"email": "t@t.com", "role": "USER"}},
        )

        response = client.delete("/admin/users/target")

        assert response.status_code == 204
        assert fake_db.collection("users").document("target").get().exists is False
        assert admin_client.deleted_auth_uids == ["target"]

    def test_admin_can_delete_a_user(self, admin_client):
        client, fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={"target": {"email": "t@t.com", "role": "USER"}},
        )

        response = client.delete("/admin/users/target")

        assert response.status_code == 204
        assert fake_db.collection("users").document("target").get().exists is False
        assert admin_client.deleted_auth_uids == ["target"]

    def test_admin_cannot_delete_another_admin(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={"target": {"email": "t@t.com", "role": "ADMIN"}},
        )

        response = client.delete("/admin/users/target")

        assert response.status_code == 403

    def test_admin_cannot_delete_super_admin(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={"super-1": {"email": "s@a.com", "role": "SUPER_ADMIN"}},
        )

        response = client.delete("/admin/users/super-1")

        assert response.status_code == 403

    def test_super_admin_can_delete_an_admin(self, admin_client):
        client, fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"},
            users={"target": {"email": "t@t.com", "role": "ADMIN"}},
        )

        response = client.delete("/admin/users/target")

        assert response.status_code == 204
        assert fake_db.collection("users").document("target").get().exists is False

    def test_cannot_delete_own_account(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"},
            users={"super-1": {"email": "s@a.com", "role": "SUPER_ADMIN"}},
        )

        response = client.delete("/admin/users/super-1")

        assert response.status_code == 400

    def test_returns_404_for_unknown_user(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"}, users={}
        )

        response = client.delete("/admin/users/ghost")

        assert response.status_code == 404


class TestLoginStats:
    def test_admin_can_list_recent_logins_newest_first(self, admin_client):
        client, fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={
                "u1": {"email": "a@a.com", "role": "USER"},
                "u2": {"email": "b@b.com", "role": "USER"},
            },
        )
        fake_db.collection("login_events").document("e1").set(
            {"uid": "u1", "email": "a@a.com", "ip": "1.1.1.1", "created_at": 1}
        )
        fake_db.collection("login_events").document("e2").set(
            {"uid": "u2", "email": "b@b.com", "ip": "2.2.2.2", "created_at": 2}
        )

        response = client.get("/admin/stats/logins")

        assert response.status_code == 200
        emails = [event["email"] for event in response.json()]
        assert emails == ["b@b.com", "a@a.com"]

    def test_admin_only_sees_user_logins_not_admin_logins(self, admin_client):
        client, fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={
                "u1": {"email": "a@a.com", "role": "USER"},
                "a2": {"email": "other-admin@a.com", "role": "ADMIN"},
            },
        )
        fake_db.collection("login_events").document("e1").set(
            {"uid": "u1", "email": "a@a.com", "ip": "1.1.1.1", "created_at": 1}
        )
        fake_db.collection("login_events").document("e2").set(
            {"uid": "a2", "email": "other-admin@a.com", "ip": "2.2.2.2", "created_at": 2}
        )

        response = client.get("/admin/stats/logins")

        assert response.status_code == 200
        assert [event["uid"] for event in response.json()] == ["u1"]

    def test_super_admin_sees_user_and_admin_logins(self, admin_client):
        client, fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"},
            users={
                "u1": {"email": "a@a.com", "role": "USER"},
                "a1": {"email": "admin@a.com", "role": "ADMIN"},
            },
        )
        fake_db.collection("login_events").document("e1").set(
            {"uid": "u1", "email": "a@a.com", "ip": "1.1.1.1", "created_at": 1}
        )
        fake_db.collection("login_events").document("e2").set(
            {"uid": "a1", "email": "admin@a.com", "ip": "2.2.2.2", "created_at": 2}
        )

        response = client.get("/admin/stats/logins")

        assert response.status_code == 200
        assert {event["uid"] for event in response.json()} == {"u1", "a1"}

    def test_caller_never_sees_their_own_logins(self, admin_client):
        client, fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "SUPER_ADMIN"},
            users={"admin-1": {"email": "admin@a.com", "role": "SUPER_ADMIN"}},
        )
        fake_db.collection("login_events").document("e1").set(
            {"uid": "admin-1", "email": "admin@a.com", "ip": "1.1.1.1", "created_at": 1}
        )

        response = client.get("/admin/stats/logins")

        assert response.status_code == 200
        assert response.json() == []

    def test_plain_user_cannot_view_login_stats(self, admin_client):
        client, _fake_db = admin_client(current_user={"uid": "u1", "role": "USER"}, users={})

        response = client.get("/admin/stats/logins")

        assert response.status_code == 403


class TestUsageStats:
    def test_admin_can_list_usage_totals(self, admin_client):
        client, fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={"u1": {"email": "a@a.com", "display_name": "Ali", "role": "USER"}},
        )
        fake_db.collection("usage_totals").document("u1").set(
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "message_count": 1}
        )

        response = client.get("/admin/stats/usage")

        assert response.status_code == 200
        assert response.json() == [
            {
                "uid": "u1",
                "email": "a@a.com",
                "display_name": "Ali",
                "role": "USER",
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "message_count": 1,
            }
        ]

    def test_admin_only_sees_user_usage_not_admin_usage(self, admin_client):
        client, fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={
                "u1": {"email": "a@a.com", "role": "USER"},
                "a2": {"email": "other-admin@a.com", "role": "ADMIN"},
            },
        )
        fake_db.collection("usage_totals").document("u1").set(
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "message_count": 1}
        )
        fake_db.collection("usage_totals").document("a2").set(
            {"prompt_tokens": 99, "completion_tokens": 99, "total_tokens": 198, "message_count": 9}
        )

        response = client.get("/admin/stats/usage")

        assert response.status_code == 200
        assert [row["uid"] for row in response.json()] == ["u1"]

    def test_super_admin_sees_user_and_admin_usage(self, admin_client):
        client, fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"},
            users={
                "u1": {"email": "a@a.com", "role": "USER"},
                "a1": {"email": "admin@a.com", "role": "ADMIN"},
            },
        )
        fake_db.collection("usage_totals").document("u1").set(
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "message_count": 1}
        )
        fake_db.collection("usage_totals").document("a1").set(
            {"prompt_tokens": 99, "completion_tokens": 99, "total_tokens": 198, "message_count": 9}
        )

        response = client.get("/admin/stats/usage")

        assert response.status_code == 200
        assert {row["uid"] for row in response.json()} == {"u1", "a1"}

    def test_caller_never_sees_their_own_usage(self, admin_client):
        client, fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"},
            users={"super-1": {"email": "s@a.com", "role": "SUPER_ADMIN"}},
        )
        fake_db.collection("usage_totals").document("super-1").set(
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "message_count": 1}
        )

        response = client.get("/admin/stats/usage")

        assert response.status_code == 200
        assert response.json() == []

    def test_plain_user_cannot_view_usage_stats(self, admin_client):
        client, _fake_db = admin_client(current_user={"uid": "u1", "role": "USER"}, users={})

        response = client.get("/admin/stats/usage")

        assert response.status_code == 403
