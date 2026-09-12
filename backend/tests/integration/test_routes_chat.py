import json

from core.security import get_current_user
from tests.conftest import DEFAULT_TEST_USER


class TestUnapprovedUserBlocked:
    """The shared `app` fixture always uses an approved DEFAULT_TEST_USER,
    so these temporarily swap get_current_user's override to exercise an
    unapproved account instead, the same override pattern
    test_routes_admin.py and test_routes_auth.py use, then restore it so
    later tests in the run keep seeing an approved caller.
    """

    def test_unapproved_user_cannot_create_a_chat(self, app):
        client, _fake_graph, _fake_db = app
        from main import app as _app

        _app.dependency_overrides[get_current_user] = lambda: {
            "uid": "pending-uid",
            "role": "USER",
            "approved": False,
        }
        try:
            response = client.post("/chats/")
        finally:
            _app.dependency_overrides[get_current_user] = lambda: DEFAULT_TEST_USER

        assert response.status_code == 403

    def test_unapproved_user_cannot_list_chats(self, app):
        client, _fake_graph, _fake_db = app
        from main import app as _app

        _app.dependency_overrides[get_current_user] = lambda: {
            "uid": "pending-uid",
            "role": "USER",
            "approved": False,
        }
        try:
            response = client.get("/chats/")
        finally:
            _app.dependency_overrides[get_current_user] = lambda: DEFAULT_TEST_USER

        assert response.status_code == 403


class TestCreateChat:
    def test_creates_an_empty_chat_owned_by_the_caller(self, app):
        client, _fake_graph, _fake_db = app

        response = client.post("/chats/")

        assert response.status_code == 200
        body = response.json()
        assert body["owner_uid"] == "test-uid"
        assert body["title"] == "Untitled chat"
        assert "id" in body


class TestListChats:
    def test_lists_only_the_caller_s_chats(self, app):
        client, _fake_graph, fake_db = app
        fake_db.collection("chats").document("mine").set(
            {"owner_uid": "test-uid", "title": "Mine", "updated_at": 2}
        )
        fake_db.collection("chats").document("theirs").set(
            {"owner_uid": "someone-else", "title": "Theirs", "updated_at": 3}
        )

        response = client.get("/chats/")

        assert response.status_code == 200
        ids = [chat["id"] for chat in response.json()]
        assert ids == ["mine"]

    def test_orders_by_most_recently_updated_first(self, app):
        client, _fake_graph, fake_db = app
        fake_db.collection("chats").document("older").set(
            {"owner_uid": "test-uid", "title": "Older", "updated_at": 1}
        )
        fake_db.collection("chats").document("newer").set(
            {"owner_uid": "test-uid", "title": "Newer", "updated_at": 5}
        )

        response = client.get("/chats/")

        ids = [chat["id"] for chat in response.json()]
        assert ids == ["newer", "older"]


class TestGetChatDetail:
    def test_returns_chat_and_its_messages(self, app):
        client, _fake_graph, fake_db = app
        chat_ref = fake_db.collection("chats").document("c1")
        chat_ref.set({"owner_uid": "test-uid", "title": "Hello", "updated_at": 1})
        chat_ref.collection("messages").document("m1").set(
            {"role": "user", "content": "hi", "created_at": 1}
        )
        chat_ref.collection("messages").document("m2").set(
            {"role": "assistant", "content": "hello!", "created_at": 2}
        )

        response = client.get("/chats/c1")

        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "Hello"
        assert [m["content"] for m in body["messages"]] == ["hi", "hello!"]

    def test_returns_404_for_someone_else_s_chat(self, app):
        client, _fake_graph, fake_db = app
        fake_db.collection("chats").document("not-mine").set(
            {"owner_uid": "someone-else", "title": "x", "updated_at": 1}
        )

        response = client.get("/chats/not-mine")

        assert response.status_code == 404

    def test_returns_404_for_an_unknown_chat(self, app):
        client, _fake_graph, _fake_db = app

        response = client.get("/chats/ghost")

        assert response.status_code == 404


class TestRenameChat:
    def test_renames_the_caller_s_chat(self, app):
        client, _fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "test-uid", "title": "Old", "updated_at": 1}
        )

        response = client.patch("/chats/c1", json={"title": "New title"})

        assert response.status_code == 200
        assert response.json()["title"] == "New title"
        assert fake_db.collection("chats").document("c1").get().to_dict()["title"] == "New title"

    def test_cannot_rename_someone_else_s_chat(self, app):
        client, _fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "someone-else", "title": "Old", "updated_at": 1}
        )

        response = client.patch("/chats/c1", json={"title": "New title"})

        assert response.status_code == 404


class TestDeleteChat:
    def test_deletes_the_chat_and_its_messages(self, app):
        client, _fake_graph, fake_db = app
        chat_ref = fake_db.collection("chats").document("c1")
        chat_ref.set({"owner_uid": "test-uid", "title": "x", "updated_at": 1})
        chat_ref.collection("messages").document("m1").set(
            {"role": "user", "content": "hi", "created_at": 1}
        )

        response = client.delete("/chats/c1")

        assert response.status_code == 204
        assert not chat_ref.get().exists
        assert chat_ref.collection("messages").stream() == []

    def test_cannot_delete_someone_else_s_chat(self, app):
        client, _fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "someone-else", "title": "x", "updated_at": 1}
        )

        response = client.delete("/chats/c1")

        assert response.status_code == 404


def _parse_sse_events(response_text: str) -> list[dict]:
    """Parses a `text/event-stream` body into a list of the JSON payloads
    carried by each `data: ...` line."""
    events = []
    for line in response_text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


class TestSendMessage:
    def test_streams_progress_events_then_a_done_event(self, app):
        client, fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "test-uid", "title": "Untitled chat", "updated_at": 1}
        )
        fake_graph.answer = "IFRS 16 requires lessees to recognize a right-of-use asset."
        fake_graph.category = "ifrs"

        response = client.post("/chats/c1/messages", json={"query": "What is IFRS 16?"})

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        events = _parse_sse_events(response.text)
        assert events[0] == {
            "event": "progress",
            "node": "router",
            "label": "Understanding your question",
        }
        assert events[-1] == {
            "event": "done",
            "response": "IFRS 16 requires lessees to recognize a right-of-use asset.",
            "category": "ifrs",
            "chat_id": "c1",
        }

    def test_stores_both_the_user_and_assistant_messages(self, app):
        client, fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "test-uid", "title": "Untitled chat", "updated_at": 1}
        )
        fake_graph.answer = "Sure, here's the answer."

        client.post("/chats/c1/messages", json={"query": "Comment calculer la TVA ?"})

        messages = fake_db.collection("chats").document("c1").collection("messages").stream()
        contents = [(m.to_dict()["role"], m.to_dict()["content"]) for m in messages]
        assert ("user", "Comment calculer la TVA ?") in contents
        assert ("assistant", "Sure, here's the answer.") in contents

    def test_passes_the_last_ten_messages_as_history(self, app):
        client, fake_graph, fake_db = app
        chat_ref = fake_db.collection("chats").document("c1")
        chat_ref.set({"owner_uid": "test-uid", "title": "Ongoing", "updated_at": 1})
        for i in range(12):
            chat_ref.collection("messages").document(f"m{i}").set(
                {
                    "role": "user" if i % 2 == 0 else "assistant",
                    "content": f"turn {i}",
                    "created_at": i,
                }
            )

        client.post("/chats/c1/messages", json={"query": "latest question"})

        history = fake_graph.last_invoke_state["history"]
        assert len(history) == 10
        assert history[0]["content"] == "turn 2"
        assert history[-1]["content"] == "turn 11"

    def test_does_not_title_the_chat_from_the_first_message(self, app):
        client, _fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "test-uid", "title": "Untitled chat", "updated_at": 1}
        )

        client.post("/chats/c1/messages", json={"query": "What is a deferred tax asset?"})

        assert (
            fake_db.collection("chats").document("c1").get().to_dict()["title"] == "Untitled chat"
        )

    def test_does_not_retitle_an_already_titled_chat(self, app):
        client, _fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "test-uid", "title": "Already named", "updated_at": 1}
        )

        client.post("/chats/c1/messages", json={"query": "second message"})

        assert (
            fake_db.collection("chats").document("c1").get().to_dict()["title"] == "Already named"
        )

    def test_rolls_token_usage_into_the_caller_s_running_total(self, app):
        client, fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "test-uid", "title": "Untitled chat", "updated_at": 1}
        )
        fake_graph.token_usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

        client.post("/chats/c1/messages", json={"query": "q"})

        totals = fake_db.collection("usage_totals").document("test-uid").get().to_dict()
        assert totals["prompt_tokens"] == 10
        assert totals["completion_tokens"] == 5
        assert totals["total_tokens"] == 15
        assert totals["message_count"] == 1

    def test_passes_the_caller_s_uid_to_the_graph(self, app):
        client, fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "test-uid", "title": "Untitled chat", "updated_at": 1}
        )

        client.post("/chats/c1/messages", json={"query": "q"})

        assert fake_graph.last_invoke_state["uid"] == "test-uid"

    def test_rolls_token_usage_into_the_caller_s_daily_and_monthly_quota(self, app):
        client, fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "test-uid", "title": "Untitled chat", "updated_at": 1}
        )
        fake_graph.token_usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

        client.post("/chats/c1/messages", json={"query": "q"})

        usage = fake_db.collection("usage_periods").document("test-uid").get().to_dict()
        assert usage["daily_tokens"] == 15
        assert usage["monthly_tokens"] == 15

    def test_returns_404_for_someone_else_s_chat(self, app):
        client, _fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "someone-else", "title": "x", "updated_at": 1}
        )

        response = client.post("/chats/c1/messages", json={"query": "q"})

        assert response.status_code == 404

    def test_emits_an_error_event_when_graph_raises(self, app):
        client, fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "test-uid", "title": "Untitled chat", "updated_at": 1}
        )
        fake_graph.raise_exc = RuntimeError("LLM unavailable")

        response = client.post("/chats/c1/messages", json={"query": "q"})

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        assert events == [{"event": "error", "detail": "LLM unavailable"}]

    def test_does_not_persist_an_assistant_message_when_graph_raises(self, app):
        client, fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "test-uid", "title": "Untitled chat", "updated_at": 1}
        )
        fake_graph.raise_exc = RuntimeError("LLM unavailable")

        client.post("/chats/c1/messages", json={"query": "q"})

        messages = fake_db.collection("chats").document("c1").collection("messages").stream()
        roles = [m.to_dict()["role"] for m in messages]
        assert roles == ["user"]

    def test_returns_422_when_query_field_missing(self, app):
        client, _fake_graph, fake_db = app
        fake_db.collection("chats").document("c1").set(
            {"owner_uid": "test-uid", "title": "Untitled chat", "updated_at": 1}
        )

        response = client.post("/chats/c1/messages", json={})

        assert response.status_code == 422
