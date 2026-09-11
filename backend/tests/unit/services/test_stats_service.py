from types import SimpleNamespace

import services.stats_service as stats_mod
import services.users_service as users_mod
from tests.setup.fakes import FakeFirestore


def _wire(monkeypatch, fake_db):
    monkeypatch.setattr(stats_mod, "get_firestore_client", lambda: fake_db)
    monkeypatch.setattr(users_mod, "get_firestore_client", lambda: fake_db)


class TestClientIpFromRequest:
    def test_prefers_x_forwarded_for_first_hop(self):
        request = SimpleNamespace(
            headers={"X-Forwarded-For": "203.0.113.5, 10.0.0.1"},
            client=SimpleNamespace(host="10.0.0.1"),
        )
        assert stats_mod.client_ip_from_request(request) == "203.0.113.5"

    def test_falls_back_to_the_socket_peer(self):
        request = SimpleNamespace(headers={}, client=SimpleNamespace(host="10.0.0.1"))
        assert stats_mod.client_ip_from_request(request) == "10.0.0.1"

    def test_returns_none_when_no_client_info_is_available(self):
        request = SimpleNamespace(headers={}, client=None)
        assert stats_mod.client_ip_from_request(request) is None


class TestRecordLogin:
    def test_appends_a_login_event(self, monkeypatch):
        fake_db = FakeFirestore(seed={"users": {"u1": {"role": "USER"}}})
        _wire(monkeypatch, fake_db)

        stats_mod.record_login("u1", "a@a.com", "1.1.1.1", "pytest-agent")

        events = fake_db.collection("login_events").stream()
        assert len(events) == 1
        assert events[0].to_dict()["uid"] == "u1"
        assert events[0].to_dict()["ip"] == "1.1.1.1"

    def test_stamps_the_user_profile_with_last_login(self, monkeypatch):
        fake_db = FakeFirestore(seed={"users": {"u1": {"role": "USER"}}})
        _wire(monkeypatch, fake_db)

        stats_mod.record_login("u1", "a@a.com", "1.1.1.1", "pytest-agent")

        profile = fake_db.collection("users").document("u1").get().to_dict()
        assert profile["last_login_ip"] == "1.1.1.1"
        assert "last_login_at" in profile


class TestListRecentLogins:
    def test_orders_newest_first_and_respects_limit(self, monkeypatch):
        fake_db = FakeFirestore(seed={"users": {"u1": {"role": "USER"}}})
        _wire(monkeypatch, fake_db)
        for i in range(3):
            fake_db.collection("login_events").document(f"e{i}").set({"uid": "u1", "created_at": i})

        result = stats_mod.list_recent_logins({"uid": "admin-1", "role": "ADMIN"}, limit=2)

        assert [e["created_at"] for e in result] == [2, 1]

    def test_admin_only_sees_user_logins(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "users": {
                    "u1": {"role": "USER", "display_name": "Ali"},
                    "a1": {"role": "ADMIN", "display_name": "Bea"},
                }
            }
        )
        _wire(monkeypatch, fake_db)
        fake_db.collection("login_events").document("e1").set({"uid": "u1", "created_at": 1})
        fake_db.collection("login_events").document("e2").set({"uid": "a1", "created_at": 2})

        result = stats_mod.list_recent_logins({"uid": "admin-1", "role": "ADMIN"})

        assert [e["uid"] for e in result] == ["u1"]

    def test_super_admin_sees_user_and_admin_logins(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "users": {
                    "u1": {"role": "USER"},
                    "a1": {"role": "ADMIN"},
                }
            }
        )
        _wire(monkeypatch, fake_db)
        fake_db.collection("login_events").document("e1").set({"uid": "u1", "created_at": 1})
        fake_db.collection("login_events").document("e2").set({"uid": "a1", "created_at": 2})

        result = stats_mod.list_recent_logins({"uid": "super-1", "role": "SUPER_ADMIN"})

        assert {e["uid"] for e in result} == {"u1", "a1"}

    def test_viewer_never_sees_their_own_logins(self, monkeypatch):
        fake_db = FakeFirestore(seed={"users": {"admin-1": {"role": "ADMIN"}}})
        _wire(monkeypatch, fake_db)
        fake_db.collection("login_events").document("e1").set({"uid": "admin-1", "created_at": 1})

        result = stats_mod.list_recent_logins({"uid": "admin-1", "role": "SUPER_ADMIN"})

        assert result == []

    def test_enriches_events_with_display_name_and_role(self, monkeypatch):
        fake_db = FakeFirestore(seed={"users": {"u1": {"role": "USER", "display_name": "Ali"}}})
        _wire(monkeypatch, fake_db)
        fake_db.collection("login_events").document("e1").set(
            {"uid": "u1", "email": "a@a.com", "ip": "1.1.1.1", "created_at": 1}
        )

        result = stats_mod.list_recent_logins({"uid": "admin-1", "role": "ADMIN"})

        assert result == [
            {
                "id": "e1",
                "uid": "u1",
                "email": "a@a.com",
                "ip": "1.1.1.1",
                "created_at": 1,
                "display_name": "Ali",
                "role": "USER",
            }
        ]


class TestRecordUsage:
    def test_creates_totals_on_first_call(self, monkeypatch):
        fake_db = FakeFirestore()
        _wire(monkeypatch, fake_db)

        stats_mod.record_usage(
            "u1", {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        )

        totals = fake_db.collection("usage_totals").document("u1").get().to_dict()
        assert totals["prompt_tokens"] == 10
        assert totals["message_count"] == 1

    def test_accumulates_across_multiple_calls(self, monkeypatch):
        fake_db = FakeFirestore()
        _wire(monkeypatch, fake_db)

        stats_mod.record_usage(
            "u1", {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        )
        stats_mod.record_usage(
            "u1", {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}
        )

        totals = fake_db.collection("usage_totals").document("u1").get().to_dict()
        assert totals["prompt_tokens"] == 13
        assert totals["total_tokens"] == 20
        assert totals["message_count"] == 2


class TestListUsageTotals:
    def test_returns_totals_for_every_visible_user(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "users": {
                    "u1": {"role": "USER", "email": "a@a.com", "display_name": "Ali"},
                    "u2": {"role": "USER", "email": "b@b.com", "display_name": "Bea"},
                },
                "usage_totals": {
                    "u1": {"total_tokens": 10, "message_count": 1},
                    "u2": {"total_tokens": 20, "message_count": 2},
                },
            }
        )
        _wire(monkeypatch, fake_db)

        result = stats_mod.list_usage_totals({"uid": "admin-1", "role": "ADMIN"})

        assert {r["uid"] for r in result} == {"u1", "u2"}

    def test_admin_only_sees_user_usage(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "users": {
                    "u1": {"role": "USER"},
                    "a1": {"role": "ADMIN"},
                },
                "usage_totals": {
                    "u1": {"total_tokens": 10, "message_count": 1},
                    "a1": {"total_tokens": 99, "message_count": 9},
                },
            }
        )
        _wire(monkeypatch, fake_db)

        result = stats_mod.list_usage_totals({"uid": "admin-1", "role": "ADMIN"})

        assert [r["uid"] for r in result] == ["u1"]

    def test_super_admin_sees_user_and_admin_usage(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "users": {
                    "u1": {"role": "USER"},
                    "a1": {"role": "ADMIN"},
                },
                "usage_totals": {
                    "u1": {"total_tokens": 10, "message_count": 1},
                    "a1": {"total_tokens": 99, "message_count": 9},
                },
            }
        )
        _wire(monkeypatch, fake_db)

        result = stats_mod.list_usage_totals({"uid": "super-1", "role": "SUPER_ADMIN"})

        assert {r["uid"] for r in result} == {"u1", "a1"}

    def test_viewer_never_sees_their_own_usage(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "users": {"super-1": {"role": "SUPER_ADMIN"}},
                "usage_totals": {"super-1": {"total_tokens": 10, "message_count": 1}},
            }
        )
        _wire(monkeypatch, fake_db)

        result = stats_mod.list_usage_totals({"uid": "super-1", "role": "SUPER_ADMIN"})

        assert result == []

    def test_enriches_totals_with_email_display_name_and_role(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "users": {"u1": {"role": "USER", "email": "a@a.com", "display_name": "Ali"}},
                "usage_totals": {
                    "u1": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15,
                        "message_count": 1,
                    }
                },
            }
        )
        _wire(monkeypatch, fake_db)

        result = stats_mod.list_usage_totals({"uid": "admin-1", "role": "ADMIN"})

        assert result == [
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
