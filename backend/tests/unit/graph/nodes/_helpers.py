def base_state(**overrides):
    state = {
        "query": "What is IFRS 16?",
        "search_query": "What is IFRS 16?",
        "intent": "retrieve",
        "category": "ifrs",
        "context": "",
        "answer": "",
        "is_valid": False,
        "retrieval_attempts": 0,
    }
    state.update(overrides)
    return state


class FakeResponse:
    def __init__(self, text, usage_metadata=None):
        self.text = text
        self.usage_metadata = usage_metadata


class FakeUsage:
    def __init__(self, prompt_token_count=0, candidates_token_count=0, total_token_count=0):
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count
        self.total_token_count = total_token_count


ZERO_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
