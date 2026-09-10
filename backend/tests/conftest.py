import pytest
from fastapi.testclient import TestClient

from tests.setup import mock_modules
from tests.setup.fakes import FakeChatGraph, FakeFirestore

DEFAULT_TEST_USER = {
    "uid": "test-uid",
    "email": "test@example.com",
    "display_name": "Test User",
    "role": "USER",
    "approved": True,
}


@pytest.fixture()
def app():
    """
    Yields (TestClient, FakeChatGraph, FakeFirestore).

    Replaces the compiled LangGraph workflow (routes.chats.app) with a fake
    before the TestClient is built, so chat requests never touch a real
    ChromaDB collection, Ollama embedding call, or Gemini API call. Those
    are already stubbed at the module level by mock_modules, this replaces
    the graph's actual routing/retrieval/generation *logic* too, which is
    covered separately by tests/unit/test_graph_nodes.py.

    Also overrides the get_current_user auth dependency with a fixed USER
    profile, so tests that only care about chat behavior don't need to
    send a real Firebase ID token. Auth/role behavior itself is covered
    separately by tests/unit/test_core_security.py and
    tests/integration/test_routes_admin.py.

    core.chats and core.stats both get pointed at a single fresh
    FakeFirestore instance, so chats, their messages, and the resulting
    usage totals are all backed by the same in-memory store within a test.
    """
    import core.chats as core_chats
    import core.stats as core_stats
    import routes.chats as r_chats
    from core.security import get_current_user

    fake_graph = FakeChatGraph()
    fake_db = FakeFirestore()

    original_graph_app = r_chats.app
    original_chats_get_client = core_chats.get_firestore_client
    original_stats_get_client = core_stats.get_firestore_client

    r_chats.app = fake_graph
    core_chats.get_firestore_client = lambda: fake_db
    core_stats.get_firestore_client = lambda: fake_db

    from main import app as _app

    _app.dependency_overrides[get_current_user] = lambda: DEFAULT_TEST_USER

    with TestClient(_app) as client:
        yield client, fake_graph, fake_db

    r_chats.app = original_graph_app
    core_chats.get_firestore_client = original_chats_get_client
    core_stats.get_firestore_client = original_stats_get_client
    _app.dependency_overrides.pop(get_current_user, None)
