import services.search_service as search_service_mod


class TestSearchWeb:
    def test_builds_context_from_results(self, monkeypatch):
        monkeypatch.setattr(
            search_service_mod.tavily,
            "search",
            lambda **kw: {
                "results": [
                    {"url": "https://example.com/a", "content": "First snippet."},
                    {"url": "https://example.com/b", "content": "Second snippet."},
                ]
            },
        )

        result = search_service_mod.search_web("EUR to TND exchange rate")

        assert result == (
            "Source: https://example.com/a\nContent: First snippet.\n\n"
            "Source: https://example.com/b\nContent: Second snippet.\n\n"
        )

    def test_passes_expected_search_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            search_service_mod.tavily,
            "search",
            lambda **kw: captured.update(kw) or {"results": []},
        )
        search_service_mod.search_web("some query")
        assert captured == {"query": "some query", "search_depth": "advanced", "max_results": 5}

    def test_returns_fallback_message_when_no_results(self, monkeypatch):
        monkeypatch.setattr(search_service_mod.tavily, "search", lambda **kw: {"results": []})
        assert search_service_mod.search_web("obscure query") == "No web results found."

    def test_returns_failure_message_on_exception(self, monkeypatch, capsys):
        def _raise(**kw):
            raise RuntimeError("Tavily API down")

        monkeypatch.setattr(search_service_mod.tavily, "search", _raise)

        result = search_service_mod.search_web("some query")

        assert result == "Web search failed."
        assert "Tavily Error: Tavily API down" in capsys.readouterr().out

    def test_returns_failure_message_when_results_key_missing(self, monkeypatch):
        monkeypatch.setattr(search_service_mod.tavily, "search", lambda **kw: {})
        assert search_service_mod.search_web("query") == "Web search failed."
