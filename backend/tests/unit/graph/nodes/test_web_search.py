import graph.nodes.web_search as web_search_mod
from tests.unit.graph.nodes._helpers import base_state


class TestWebSearchNode:
    def test_returns_context_from_search_service(self, monkeypatch):
        monkeypatch.setattr(
            web_search_mod,
            "search_web",
            lambda query: "Source: example.com\nContent: EUR/TND rate today.",
        )
        result = web_search_mod.web_search_node(
            base_state(query="current EUR/TND exchange rate", search_query="EUR/TND rate today")
        )
        assert result == {"context": "Source: example.com\nContent: EUR/TND rate today."}

    def test_passes_search_query_through_unchanged(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            web_search_mod,
            "search_web",
            lambda query: captured.setdefault("query", query) and "",
        )
        web_search_mod.web_search_node(
            base_state(query="some question", search_query="refined question")
        )
        assert captured["query"] == "refined question"

    def test_falls_back_to_raw_query_when_search_query_missing(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            web_search_mod,
            "search_web",
            lambda query: captured.setdefault("query", query) and "",
        )
        state = base_state(query="some question")
        state.pop("search_query")
        web_search_mod.web_search_node(state)
        assert captured["query"] == "some question"

    def test_ignores_other_state_fields(self, monkeypatch):
        monkeypatch.setattr(web_search_mod, "search_web", lambda query: "context text")
        state = base_state(category="tax_code", answer="stale", is_valid=False)
        assert web_search_mod.web_search_node(state) == {"context": "context text"}

    def test_skips_search_and_no_uid_never_checks_limits(self, monkeypatch):
        """A graph run with no `uid` in state (e.g. the module's own smoke
        test) always performs the search, it never touches limits_service."""

        def _boom(*_args, **_kwargs):
            raise AssertionError("limits_service should not be consulted without a uid")

        monkeypatch.setattr(web_search_mod.limits_service, "search_limit_message", _boom)
        monkeypatch.setattr(web_search_mod, "search_web", lambda query: "context")

        result = web_search_mod.web_search_node(base_state())

        assert result == {"context": "context"}

    def test_performs_the_search_and_records_usage_when_within_limits(self, monkeypatch):
        recorded = {}
        monkeypatch.setattr(web_search_mod.limits_service, "search_limit_message", lambda uid: None)
        monkeypatch.setattr(
            web_search_mod.limits_service,
            "record_search_usage",
            lambda uid: recorded.setdefault("limits_uid", uid),
        )
        monkeypatch.setattr(
            web_search_mod.stats_service,
            "record_search_credit",
            lambda uid: recorded.setdefault("stats_uid", uid),
        )
        monkeypatch.setattr(web_search_mod, "search_web", lambda query: "fresh context")

        result = web_search_mod.web_search_node(base_state(uid="user-1"))

        assert result == {"context": "fresh context"}
        assert recorded == {"limits_uid": "user-1", "stats_uid": "user-1"}

    def test_skips_the_search_and_returns_a_block_message_when_limit_reached(self, monkeypatch):
        monkeypatch.setattr(
            web_search_mod.limits_service,
            "search_limit_message",
            lambda uid: "Limit reached, resets on 2026-09-12.",
        )

        def _boom(*_args, **_kwargs):
            raise AssertionError("search_web should not be called once the limit is reached")

        monkeypatch.setattr(web_search_mod, "search_web", _boom)

        result = web_search_mod.web_search_node(base_state(uid="user-1"))

        assert result == {
            "context": "",
            "search_blocked": True,
            "search_block_message": "Limit reached, resets on 2026-09-12.",
        }

    def test_does_not_record_usage_when_the_search_is_blocked(self, monkeypatch):
        monkeypatch.setattr(
            web_search_mod.limits_service, "search_limit_message", lambda uid: "blocked"
        )

        def _boom(*_args, **_kwargs):
            raise AssertionError("usage should not be recorded when the search is skipped")

        monkeypatch.setattr(web_search_mod.limits_service, "record_search_usage", _boom)
        monkeypatch.setattr(web_search_mod.stats_service, "record_search_credit", _boom)

        web_search_mod.web_search_node(base_state(uid="user-1"))
