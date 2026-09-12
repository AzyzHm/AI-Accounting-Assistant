import json
from datetime import date

import services.limits_service as limits_mod
from core.security import get_current_user
from tests.conftest import DEFAULT_TEST_USER


def _parse_sse_events(response_text: str) -> list[dict]:
    """Parses a `text/event-stream` body into a list of the JSON payloads
    carried by each `data: ...` line."""
    events = []
    for line in response_text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


class TestSendMessageWhenTokenLimitReached:
    """When the caller has already reached their daily or monthly token
    limit, the graph must never run: a canned reply naming the limit and
    its exact reset date is stored and streamed back instead."""

    def test_never_invokes_the_graph(self, app, monkeypatch):
        client, fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "test-uid", "title": "Untitled chat", "updated_at": 1}
        )
        monkeypatch.setattr(limits_mod, "_today_utc", lambda: date(2026, 9, 11))
        fake_db.collection("usage_limits").document("test-uid").set({"daily_token_limit": 10})
        fake_db.collection("usage_periods").document("test-uid").set(
            {"daily_period": "2026-09-11", "daily_tokens": 10, "monthly_period": "2026-09"}
        )

        response = client.post("/chats/c1/messages", json={"query": "q"})

        assert response.status_code == 200
        assert fake_graph.last_invoke_state is None

    def test_streams_a_done_event_naming_the_limit_and_reset_date(self, app, monkeypatch):
        client, _fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "test-uid", "title": "Untitled chat", "updated_at": 1}
        )
        monkeypatch.setattr(limits_mod, "_today_utc", lambda: date(2026, 9, 11))
        fake_db.collection("usage_limits").document("test-uid").set({"daily_token_limit": 10})
        fake_db.collection("usage_periods").document("test-uid").set(
            {"daily_period": "2026-09-11", "daily_tokens": 10, "monthly_period": "2026-09"}
        )

        response = client.post("/chats/c1/messages", json={"query": "q"})

        events = _parse_sse_events(response.text)
        assert len(events) == 1
        assert events[0]["event"] == "done"
        assert "daily token limit" in events[0]["response"]
        assert "2026-09-12" in events[0]["response"]
        assert events[0]["category"] is None

    def test_persists_the_user_message_and_the_canned_reply(self, app, monkeypatch):
        client, _fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "test-uid", "title": "Untitled chat", "updated_at": 1}
        )
        monkeypatch.setattr(limits_mod, "_today_utc", lambda: date(2026, 9, 11))
        fake_db.collection("usage_limits").document("test-uid").set({"daily_token_limit": 10})
        fake_db.collection("usage_periods").document("test-uid").set(
            {"daily_period": "2026-09-11", "daily_tokens": 10, "monthly_period": "2026-09"}
        )

        client.post("/chats/c1/messages", json={"query": "a blocked question"})

        messages = fake_db.collection("chats").document("c1").collection("messages").stream()
        contents = [(m.to_dict()["role"], m.to_dict()["content"]) for m in messages]
        assert ("user", "a blocked question") in contents
        assert any(
            role == "assistant" and "daily token limit" in content for role, content in contents
        )

    def test_does_not_roll_up_any_further_token_usage(self, app, monkeypatch):
        client, _fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "test-uid", "title": "Untitled chat", "updated_at": 1}
        )
        monkeypatch.setattr(limits_mod, "_today_utc", lambda: date(2026, 9, 11))
        fake_db.collection("usage_limits").document("test-uid").set({"daily_token_limit": 10})
        fake_db.collection("usage_periods").document("test-uid").set(
            {"daily_period": "2026-09-11", "daily_tokens": 10, "monthly_period": "2026-09"}
        )

        client.post("/chats/c1/messages", json={"query": "q"})

        usage = fake_db.collection("usage_periods").document("test-uid").get().to_dict()
        assert usage["daily_tokens"] == 10
        assert fake_db.collection("usage_totals").document("test-uid").get().to_dict() is None

    def test_users_still_under_their_limit_are_not_affected(self, app, monkeypatch):
        client, fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "test-uid", "title": "Untitled chat", "updated_at": 1}
        )
        monkeypatch.setattr(limits_mod, "_today_utc", lambda: date(2026, 9, 11))
        fake_db.collection("usage_limits").document("test-uid").set({"daily_token_limit": 10})
        fake_db.collection("usage_periods").document("test-uid").set(
            {"daily_period": "2026-09-11", "daily_tokens": 5, "monthly_period": "2026-09"}
        )

        response = client.post("/chats/c1/messages", json={"query": "q"})

        assert fake_graph.last_invoke_state is not None
        events = _parse_sse_events(response.text)
        assert events[-1]["response"] == fake_graph.answer

    def test_admin_sender_bypasses_the_limit_entirely(self, app, monkeypatch):
        client, fake_graph, fake_db = app
        from main import app as _app

        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "admin-uid", "title": "Untitled chat", "updated_at": 1}
        )
        monkeypatch.setattr(limits_mod, "_today_utc", lambda: date(2026, 9, 11))
        fake_db.collection("usage_limits").document("admin-uid").set({"daily_token_limit": 10})
        fake_db.collection("usage_periods").document("admin-uid").set(
            {"daily_period": "2026-09-11", "daily_tokens": 10_000, "monthly_period": "2026-09"}
        )

        _app.dependency_overrides[get_current_user] = lambda: {
            **DEFAULT_TEST_USER,
            "uid": "admin-uid",
            "role": "ADMIN",
        }
        try:
            response = client.post("/chats/c1/messages", json={"query": "q"})
        finally:
            _app.dependency_overrides[get_current_user] = lambda: DEFAULT_TEST_USER

        assert fake_graph.last_invoke_state is not None
        assert fake_graph.last_invoke_state["role"] == "ADMIN"
        events = _parse_sse_events(response.text)
        assert events[-1]["response"] == fake_graph.answer

    def test_super_admin_sender_bypasses_the_limit_entirely(self, app, monkeypatch):
        client, fake_graph, fake_db = app
        from main import app as _app

        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "super-uid", "title": "Untitled chat", "updated_at": 1}
        )
        monkeypatch.setattr(limits_mod, "_today_utc", lambda: date(2026, 9, 11))
        fake_db.collection("usage_periods").document("super-uid").set(
            {"daily_period": "2026-09-11", "daily_tokens": 10_000_000, "monthly_period": "2026-09"}
        )

        _app.dependency_overrides[get_current_user] = lambda: {
            **DEFAULT_TEST_USER,
            "uid": "super-uid",
            "role": "SUPER_ADMIN",
        }
        try:
            response = client.post("/chats/c1/messages", json={"query": "q"})
        finally:
            _app.dependency_overrides[get_current_user] = lambda: DEFAULT_TEST_USER

        assert fake_graph.last_invoke_state is not None
        events = _parse_sse_events(response.text)
        assert events[-1]["response"] == fake_graph.answer
