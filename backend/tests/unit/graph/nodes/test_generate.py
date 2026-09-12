import graph.nodes.generate as generate_mod
from config.prompts import expert_prompt_v1, expert_prompt_v2
from tests.unit.graph.nodes._helpers import ZERO_USAGE, FakeResponse, FakeUsage, base_state


class TestSearchBlockedShortCircuit:
    def test_returns_the_block_message_verbatim_without_calling_the_llm(self, monkeypatch):
        def _boom(**_kwargs):
            raise AssertionError("the LLM should not be called when the search was blocked")

        monkeypatch.setattr(generate_mod, "getResponseFromLLM", _boom)
        state = base_state(
            context="",
            search_blocked=True,
            search_block_message="Limit reached, resets on 2026-09-12.",
        )

        result = generate_mod.generate_answer_node(state)

        assert result == {
            "answer": "Limit reached, resets on 2026-09-12.",
            "token_usage": ZERO_USAGE,
        }

    def test_falls_back_to_an_empty_answer_if_no_message_was_set(self):
        result = generate_mod.generate_answer_node(base_state(search_blocked=True))
        assert result == {"answer": "", "token_usage": ZERO_USAGE}


class TestGenerateNode:
    def test_uses_v1_prompt_for_general_knowledge(self, monkeypatch):
        captured = {}

        def _fake(**kwargs):
            captured.update(kwargs)
            return FakeResponse("A concise answer.")

        monkeypatch.setattr(generate_mod, "getResponseFromLLM", _fake)
        state = base_state(query="What is an asset?", context="", intent="general_knowledge")

        assert generate_mod.generate_answer_node(state) == {
            "answer": "A concise answer.",
            "token_usage": ZERO_USAGE,
        }
        assert captured["system_prompt"] == expert_prompt_v1
        assert captured["user_prompt"] == "QUESTION: What is an asset?"

    def test_uses_v1_prompt_when_context_missing_even_for_retrieve_intent(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            generate_mod,
            "getResponseFromLLM",
            lambda **kw: captured.update(kw) or FakeResponse("answer"),
        )
        generate_mod.generate_answer_node(base_state(context=""))
        assert captured["system_prompt"] == expert_prompt_v1

    def test_uses_v2_prompt_when_context_present(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            generate_mod,
            "getResponseFromLLM",
            lambda **kw: captured.update(kw) or FakeResponse("A grounded answer."),
        )
        state = base_state(
            query="What are the recognition criteria for a provision?",
            context="IAS 37 requires a present obligation from a past event.",
        )
        result = generate_mod.generate_answer_node(state)

        assert result == {"answer": "A grounded answer.", "token_usage": ZERO_USAGE}
        assert captured["system_prompt"] == expert_prompt_v2
        assert (
            "CONTEXT: IAS 37 requires a present obligation from a past event."
            in (captured["user_prompt"])
        )
        assert (
            "QUESTION: What are the recognition criteria for a provision?"
            in (captured["user_prompt"])
        )

    def test_passes_expected_temperature_and_format(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            generate_mod,
            "getResponseFromLLM",
            lambda **kw: captured.update(kw) or FakeResponse("answer"),
        )
        generate_mod.generate_answer_node(base_state(context="c"))
        assert captured["model_temp"] == 0.5
        assert captured["format"] == "text"

    def test_defaults_intent_to_general_knowledge_when_absent(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            generate_mod,
            "getResponseFromLLM",
            lambda **kw: captured.update(kw) or FakeResponse("answer"),
        )
        state = {"query": "q", "context": "some context"}
        generate_mod.generate_answer_node(state)
        assert captured["system_prompt"] == expert_prompt_v1

    def test_includes_recent_history_in_the_prompt(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            generate_mod,
            "getResponseFromLLM",
            lambda **kw: captured.update(kw) or FakeResponse("answer"),
        )
        state = base_state(
            query="And what about the VAT rate?",
            context="",
            intent="general_knowledge",
            history=[
                {"role": "user", "content": "What is the corporate tax rate?"},
                {"role": "assistant", "content": "It is 15% for most companies."},
            ],
        )

        generate_mod.generate_answer_node(state)

        assert "CONVERSATION SO FAR:" in captured["user_prompt"]
        assert "User: What is the corporate tax rate?" in captured["user_prompt"]
        assert "Assistant: It is 15% for most companies." in captured["user_prompt"]
        assert "QUESTION: And what about the VAT rate?" in captured["user_prompt"]

    def test_omits_history_block_when_history_is_empty(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            generate_mod,
            "getResponseFromLLM",
            lambda **kw: captured.update(kw) or FakeResponse("answer"),
        )
        generate_mod.generate_answer_node(base_state(context="", history=[]))
        assert "CONVERSATION SO FAR" not in captured["user_prompt"]

    def test_only_keeps_the_last_ten_history_turns(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            generate_mod,
            "getResponseFromLLM",
            lambda **kw: captured.update(kw) or FakeResponse("answer"),
        )
        history = [{"role": "user", "content": f"turn {i}"} for i in range(15)]
        generate_mod.generate_answer_node(base_state(context="", history=history))

        assert "turn 5" in captured["user_prompt"]
        assert "turn 14" in captured["user_prompt"]
        assert "turn 4" not in captured["user_prompt"]

    def test_extracts_token_usage_from_response_metadata(self, monkeypatch):
        usage = FakeUsage(prompt_token_count=10, candidates_token_count=20, total_token_count=30)
        monkeypatch.setattr(
            generate_mod,
            "getResponseFromLLM",
            lambda **kw: FakeResponse("answer", usage_metadata=usage),
        )
        result = generate_mod.generate_answer_node(base_state(context="c"))

        assert result["token_usage"] == {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        }

    def test_defaults_token_usage_to_zero_when_metadata_missing(self, monkeypatch):
        monkeypatch.setattr(generate_mod, "getResponseFromLLM", lambda **kw: FakeResponse("answer"))
        result = generate_mod.generate_answer_node(base_state(context="c"))
        assert result["token_usage"] == ZERO_USAGE
