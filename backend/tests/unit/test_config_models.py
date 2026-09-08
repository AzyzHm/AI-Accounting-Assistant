import config.models as models_mod


class FakeGeminiResponse:
    def __init__(self, text):
        self.text = text
        self.usage_metadata = None


class _FakeGenaiModels:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    def generate_content(self, **kwargs):
        if self._exc:
            raise self._exc
        return self._response


class _FakeGenaiClient:
    def __init__(self, response=None, exc=None):
        self.models = _FakeGenaiModels(response=response, exc=exc)


class _FakeHttpResponse:
    def __init__(self, payload, status_ok=True):
        self._payload = payload
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            raise RuntimeError("Mistral HTTP error")

    def json(self):
        return self._payload


class TestGetResponseFromLLM:
    def test_returns_gemini_response_when_gemini_succeeds(self, monkeypatch):
        gemini_response = FakeGeminiResponse("Gemini answered this.")
        monkeypatch.setattr(
            models_mod.genai, "Client", lambda api_key: _FakeGenaiClient(response=gemini_response)
        )

        called = {}
        monkeypatch.setattr(
            models_mod, "_call_mistral", lambda *a, **kw: called.setdefault("yes", True)
        )

        result = models_mod.getResponseFromLLM("system", "user", 0.0)

        assert result is gemini_response
        assert "yes" not in called

    def test_falls_back_to_mistral_when_gemini_raises(self, monkeypatch):
        monkeypatch.setattr(
            models_mod.genai,
            "Client",
            lambda api_key: _FakeGenaiClient(exc=RuntimeError("out of tokens")),
        )
        monkeypatch.setattr(
            models_mod,
            "requests",
            type(
                "R",
                (),
                {
                    "post": staticmethod(
                        lambda *a, **kw: _FakeHttpResponse(
                            {
                                "choices": [{"message": {"content": "Mistral answered this."}}],
                                "usage": {
                                    "prompt_tokens": 5,
                                    "completion_tokens": 7,
                                    "total_tokens": 12,
                                },
                            }
                        )
                    )
                },
            ),
        )

        result = models_mod.getResponseFromLLM("system", "user", 0.0)

        assert result.text == "Mistral answered this."
        assert result.usage_metadata.prompt_token_count == 5
        assert result.usage_metadata.candidates_token_count == 7
        assert result.usage_metadata.total_token_count == 12

    def test_falls_back_to_mistral_when_gemini_returns_empty_text(self, monkeypatch):
        gemini_response = FakeGeminiResponse(None)
        monkeypatch.setattr(
            models_mod.genai, "Client", lambda api_key: _FakeGenaiClient(response=gemini_response)
        )

        captured = {}

        def _fake_call_mistral(system_prompt, user_prompt, model_temp, format):
            captured.update(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model_temp=model_temp,
                format=format,
            )
            return models_mod._LLMResponse(text="Mistral picked up the slack.")

        monkeypatch.setattr(models_mod, "_call_mistral", _fake_call_mistral)

        result = models_mod.getResponseFromLLM("sys", "usr", 0.3, format="text")

        assert result.text == "Mistral picked up the slack."
        assert captured == {
            "system_prompt": "sys",
            "user_prompt": "usr",
            "model_temp": 0.3,
            "format": "text",
        }

    def test_mistral_response_has_empty_text_when_mistral_also_fails(self, monkeypatch):
        monkeypatch.setattr(
            models_mod.genai,
            "Client",
            lambda api_key: _FakeGenaiClient(exc=RuntimeError("gemini down")),
        )
        monkeypatch.setattr(
            models_mod,
            "requests",
            type(
                "R",
                (),
                {"post": staticmethod(lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("no")))},
            ),
        )

        result = models_mod.getResponseFromLLM("system", "user", 0.0)

        assert result.text is None
