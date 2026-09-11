import services.chats_service as chats_mod
from tests.setup.fakes import FakeFirestore


def _wire(monkeypatch, fake_db):
    monkeypatch.setattr(chats_mod, "get_firestore_client", lambda: fake_db)


class TestCreateChat:
    def test_creates_a_chat_with_a_default_title(self, monkeypatch):
        fake_db = FakeFirestore()
        _wire(monkeypatch, fake_db)

        chat = chats_mod.create_chat("uid-1")

        assert chat["owner_uid"] == "uid-1"
        assert chat["title"] == "Untitled chat"
        assert "id" in chat

    def test_second_untitled_chat_gets_a_numbered_suffix(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "chats": {"c1": {"owner_uid": "uid-1", "title": "Untitled chat", "updated_at": 1}}
            }
        )
        _wire(monkeypatch, fake_db)

        chat = chats_mod.create_chat("uid-1")

        assert chat["title"] == "Untitled chat (2)"

    def test_numbering_skips_to_the_next_free_slot(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "chats": {
                    "c1": {"owner_uid": "uid-1", "title": "Untitled chat", "updated_at": 1},
                    "c2": {"owner_uid": "uid-1", "title": "Untitled chat (2)", "updated_at": 2},
                }
            }
        )
        _wire(monkeypatch, fake_db)

        chat = chats_mod.create_chat("uid-1")

        assert chat["title"] == "Untitled chat (3)"

    def test_numbering_only_considers_the_owners_own_chats(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "chats": {
                    "c1": {"owner_uid": "someone-else", "title": "Untitled chat", "updated_at": 1}
                }
            }
        )
        _wire(monkeypatch, fake_db)

        chat = chats_mod.create_chat("uid-1")

        assert chat["title"] == "Untitled chat"

    def test_renamed_chats_dont_block_reuse_of_the_default_title(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "chats": {"c1": {"owner_uid": "uid-1", "title": "IFRS 16 notes", "updated_at": 1}}
            }
        )
        _wire(monkeypatch, fake_db)

        chat = chats_mod.create_chat("uid-1")

        assert chat["title"] == "Untitled chat"


class TestListChats:
    def test_only_returns_chats_owned_by_the_given_uid(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "chats": {
                    "c1": {"owner_uid": "uid-1", "title": "Mine", "updated_at": 1},
                    "c2": {"owner_uid": "uid-2", "title": "Not mine", "updated_at": 2},
                }
            }
        )
        _wire(monkeypatch, fake_db)

        result = chats_mod.list_chats("uid-1")

        assert [c["id"] for c in result] == ["c1"]

    def test_orders_newest_first(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "chats": {
                    "old": {"owner_uid": "uid-1", "title": "Old", "updated_at": 1},
                    "new": {"owner_uid": "uid-1", "title": "New", "updated_at": 9},
                }
            }
        )
        _wire(monkeypatch, fake_db)

        result = chats_mod.list_chats("uid-1")

        assert [c["id"] for c in result] == ["new", "old"]


class TestGetChat:
    def test_returns_none_for_a_missing_chat(self, monkeypatch):
        fake_db = FakeFirestore()
        _wire(monkeypatch, fake_db)

        assert chats_mod.get_chat("ghost") is None

    def test_returns_the_chat_when_it_exists(self, monkeypatch):
        fake_db = FakeFirestore(seed={"chats": {"c1": {"owner_uid": "uid-1", "title": "x"}}})
        _wire(monkeypatch, fake_db)

        chat = chats_mod.get_chat("c1")

        assert chat == {"id": "c1", "owner_uid": "uid-1", "title": "x"}


class TestMessages:
    def test_add_message_then_get_messages_round_trips(self, monkeypatch):
        fake_db = FakeFirestore(seed={"chats": {"c1": {"owner_uid": "uid-1"}}})
        _wire(monkeypatch, fake_db)

        chats_mod.add_message("c1", role="user", content="hi")
        chats_mod.add_message("c1", role="assistant", content="hello", category="ifrs")

        messages = chats_mod.get_messages("c1")

        assert [m["content"] for m in messages] == ["hi", "hello"]
        assert messages[1]["category"] == "ifrs"

    def test_get_messages_respects_limit_keeping_the_most_recent(self, monkeypatch):
        fake_db = FakeFirestore(seed={"chats": {"c1": {"owner_uid": "uid-1"}}})
        _wire(monkeypatch, fake_db)

        for i in range(5):
            fake_db.collection("chats").document("c1").collection("messages").document(f"m{i}").set(
                {"role": "user", "content": f"turn {i}", "created_at": i}
            )

        messages = chats_mod.get_messages("c1", limit=2)

        assert [m["content"] for m in messages] == ["turn 3", "turn 4"]


class TestRenameAndTouch:
    def test_rename_chat_updates_title(self, monkeypatch):
        fake_db = FakeFirestore(seed={"chats": {"c1": {"owner_uid": "uid-1", "title": "old"}}})
        _wire(monkeypatch, fake_db)

        chats_mod.rename_chat("c1", "new title")

        assert fake_db.collection("chats").document("c1").get().to_dict()["title"] == "new title"

    def test_touch_chat_without_title_leaves_title_untouched(self, monkeypatch):
        fake_db = FakeFirestore(seed={"chats": {"c1": {"owner_uid": "uid-1", "title": "kept"}}})
        _wire(monkeypatch, fake_db)

        chats_mod.touch_chat("c1")

        assert fake_db.collection("chats").document("c1").get().to_dict()["title"] == "kept"


class TestDeleteChat:
    def test_deletes_chat_and_all_of_its_messages(self, monkeypatch):
        fake_db = FakeFirestore(seed={"chats": {"c1": {"owner_uid": "uid-1"}}})
        _wire(monkeypatch, fake_db)
        chats_mod.add_message("c1", role="user", content="hi")

        chats_mod.delete_chat("c1")

        assert chats_mod.get_chat("c1") is None
        assert chats_mod.get_messages("c1") == []


class TestTitleFromQuery:
    def test_short_query_is_used_as_is(self):
        assert chats_mod.title_from_query("What is IFRS 16?") == "What is IFRS 16?"

    def test_long_query_is_truncated_with_an_ellipsis(self):
        long_query = "a" * 100
        title = chats_mod.title_from_query(long_query)

        assert len(title) == chats_mod.TITLE_MAX_LENGTH + 1
        assert title.endswith("…")

    def test_blank_query_falls_back_to_default_title(self):
        assert chats_mod.title_from_query("   ") == chats_mod.DEFAULT_TITLE
