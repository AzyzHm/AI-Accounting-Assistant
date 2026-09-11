import services.users_service as users_mod
from tests.setup.fakes import FakeFirestore


def _wire(monkeypatch, fake_db):
    monkeypatch.setattr(users_mod, "get_firestore_client", lambda: fake_db)


class TestGetOrCreateProfile:
    def test_first_ever_account_becomes_super_admin_and_is_approved(self, monkeypatch):
        fake_db = FakeFirestore()
        _wire(monkeypatch, fake_db)

        profile = users_mod.get_or_create_profile({"uid": "u1", "email": "a@a.com"})

        assert profile["role"] == "SUPER_ADMIN"
        assert profile["approved"] is True

    def test_subsequent_accounts_default_to_user_and_are_unapproved(self, monkeypatch):
        fake_db = FakeFirestore(users={"existing": {"email": "e@e.com", "role": "SUPER_ADMIN"}})
        _wire(monkeypatch, fake_db)

        profile = users_mod.get_or_create_profile({"uid": "u2", "email": "b@b.com"})

        assert profile["role"] == "USER"
        assert profile["approved"] is False

    def test_this_applies_to_google_sign_in_the_same_as_email_password(self, monkeypatch):
        fake_db = FakeFirestore(users={"existing": {"email": "e@e.com", "role": "SUPER_ADMIN"}})
        _wire(monkeypatch, fake_db)

        profile = users_mod.get_or_create_profile(
            {"uid": "u3", "email": "c@c.com", "name": "Carol"}
        )

        assert profile["approved"] is False

    def test_returning_user_keeps_their_stored_approval_state(self, monkeypatch):
        fake_db = FakeFirestore(
            users={"u1": {"email": "a@a.com", "role": "USER", "approved": True}}
        )
        _wire(monkeypatch, fake_db)

        profile = users_mod.get_or_create_profile({"uid": "u1", "email": "a@a.com"})

        assert profile["approved"] is True


class TestUpdateProfileFields:
    def test_updates_display_name_only(self, monkeypatch):
        fake_db = FakeFirestore(users={"u1": {"email": "a@a.com", "display_name": "Old Name"}})
        _wire(monkeypatch, fake_db)

        result = users_mod.update_profile_fields("u1", display_name="New Name")

        assert result["display_name"] == "New Name"
        assert result["email"] == "a@a.com"

    def test_updates_email_only(self, monkeypatch):
        fake_db = FakeFirestore(users={"u1": {"email": "old@a.com", "display_name": "Name"}})
        _wire(monkeypatch, fake_db)

        result = users_mod.update_profile_fields("u1", email="new@a.com")

        assert result["email"] == "new@a.com"
        assert result["display_name"] == "Name"

    def test_updates_both_fields_together(self, monkeypatch):
        fake_db = FakeFirestore(users={"u1": {"email": "old@a.com", "display_name": "Old"}})
        _wire(monkeypatch, fake_db)

        result = users_mod.update_profile_fields("u1", display_name="New", email="new@a.com")

        assert result["display_name"] == "New"
        assert result["email"] == "new@a.com"

    def test_leaves_other_fields_untouched(self, monkeypatch):
        fake_db = FakeFirestore(users={"u1": {"email": "a@a.com", "role": "ADMIN"}})
        _wire(monkeypatch, fake_db)

        result = users_mod.update_profile_fields("u1", display_name="New Name")

        assert result["role"] == "ADMIN"

    def test_no_fields_given_is_a_no_op_read(self, monkeypatch):
        fake_db = FakeFirestore(users={"u1": {"email": "a@a.com", "display_name": "Name"}})
        _wire(monkeypatch, fake_db)

        result = users_mod.update_profile_fields("u1")

        assert result == {"uid": "u1", "email": "a@a.com", "display_name": "Name"}


class TestListVisibleProfiles:
    def test_admin_only_sees_user_accounts(self, monkeypatch):
        fake_db = FakeFirestore(
            users={
                "u1": {"role": "USER"},
                "a1": {"role": "ADMIN"},
            }
        )
        _wire(monkeypatch, fake_db)

        visible = users_mod.list_visible_profiles(
            {"uid": "admin-1", "role": "ADMIN"}, exclude_viewer=False
        )

        assert set(visible.keys()) == {"u1"}

    def test_super_admin_sees_user_and_admin_accounts(self, monkeypatch):
        fake_db = FakeFirestore(
            users={
                "u1": {"role": "USER"},
                "a1": {"role": "ADMIN"},
            }
        )
        _wire(monkeypatch, fake_db)

        visible = users_mod.list_visible_profiles(
            {"uid": "super-1", "role": "SUPER_ADMIN"}, exclude_viewer=False
        )

        assert set(visible.keys()) == {"u1", "a1"}

    def test_exclude_viewer_drops_the_viewer_s_own_account(self, monkeypatch):
        fake_db = FakeFirestore(
            users={
                "u1": {"role": "USER"},
                "u2": {"role": "USER"},
            }
        )
        _wire(monkeypatch, fake_db)

        visible = users_mod.list_visible_profiles(
            {"uid": "u1", "role": "USER"}, exclude_viewer=True
        )

        assert set(visible.keys()) == {"u2"}
