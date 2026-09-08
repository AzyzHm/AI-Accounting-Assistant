import graph.workflow as workflow_mod


def _state(**overrides):
    state = {
        "intent": "retrieve",
        "is_valid": False,
        "retrieval_attempts": 0,
    }
    state.update(overrides)
    return state


class TestRouteAfterRouter:
    def test_general_knowledge_skips_refine(self):
        assert workflow_mod.route_after_router(_state(intent="general_knowledge")) == "generate"

    def test_web_search_intent_goes_to_refine(self):
        assert workflow_mod.route_after_router(_state(intent="web_search")) == "refine"

    def test_retrieve_intent_goes_to_refine(self):
        assert workflow_mod.route_after_router(_state(intent="retrieve")) == "refine"


class TestRouteAfterRefine:
    def test_web_search_intent_goes_to_web_search_node(self):
        assert workflow_mod.route_after_refine(_state(intent="web_search")) == "web_search"

    def test_retrieve_intent_goes_to_retrieve_node(self):
        assert workflow_mod.route_after_refine(_state(intent="retrieve")) == "retrieve"


class TestPostValRouting:
    def test_valid_context_goes_to_generate(self):
        assert workflow_mod.post_val_routing(_state(is_valid=True)) == "generate"

    def test_invalid_context_retries_retrieval_when_attempts_remain(self):
        state = _state(is_valid=False, retrieval_attempts=1)
        assert workflow_mod.post_val_routing(state) == "retrieve"

    def test_invalid_context_falls_back_to_web_search_after_max_attempts(self):
        state = _state(is_valid=False, retrieval_attempts=workflow_mod.MAX_RETRIEVAL_ATTEMPTS)
        assert workflow_mod.post_val_routing(state) == "web_search"

    def test_retries_up_to_but_not_beyond_max_attempts(self):
        for attempts in range(workflow_mod.MAX_RETRIEVAL_ATTEMPTS):
            state = _state(is_valid=False, retrieval_attempts=attempts)
            assert workflow_mod.post_val_routing(state) == "retrieve"

        state = _state(is_valid=False, retrieval_attempts=workflow_mod.MAX_RETRIEVAL_ATTEMPTS)
        assert workflow_mod.post_val_routing(state) == "web_search"


class TestNodeLabels:
    def test_every_graph_node_has_a_progress_label(self):
        expected_nodes = {"router", "refine", "web_search", "retrieve", "validate", "generate"}
        assert set(workflow_mod.NODE_LABELS.keys()) == expected_nodes

    def test_labels_are_non_empty_strings(self):
        for label in workflow_mod.NODE_LABELS.values():
            assert isinstance(label, str)
            assert label.strip() != ""
