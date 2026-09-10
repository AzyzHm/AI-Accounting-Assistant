import pytest
from fastapi import HTTPException

from core.security import _get_or_create_profile, require_approved, update_profile_fields
from tests.setup.fakes import FakeFirestore


class TestGetOrCreateProfile:
    def test_first_ever_account_becomes_super_admin_and_is_approved(self, monkeypatch):
        import core.security as core_security

        fake_db = FakeFirestore()
        monkeypatch.setattr(core_security, "get_firestore_client", lambda: fake_db)

        profile = _get_or_create_profile({"uid": "u1", "email": "a@a.com"})

        assert profile["role"] == "SUPER_ADMIN"
        assert profile["approved"] is True

    def test_subsequent_accounts_default_to_user_and_are_unapproved(self, monkeypatch):
        import core.security as core_security

        fake_db = FakeFirestore(users={"existing": {"email": "e@e.com", "role": "SUPER_ADMIN"}})
        monkeypatch.setattr(core_security, "get_firestore_client", lambda: fake_db)

        profile = _get_or_create_profile({"uid": "u2", "email": "b@b.com"})

        assert profile["role"] == "USER"
        assert profile["approved"] is False

    def test_this_applies_to_google_sign_in_the_same_as_email_password(self, monkeypatch):
        import core.security as core_security

        fake_db = FakeFirestore(users={"existing": {"email": "e@e.com", "role": "SUPER_ADMIN"}})
        monkeypatch.setattr(core_security, "get_firestore_client", lambda: fake_db)

        profile = _get_or_create_profile({"uid": "u3", "email": "c@c.com", "name": "Carol"})

        assert profile["approved"] is False

    def test_returning_user_keeps_their_stored_approval_state(self, monkeypatch):
        import core.security as core_security

        fake_db = FakeFirestore(
            users={"u1": {"email": "a@a.com", "role": "USER", "approved": True}}
        )
        monkeypatch.setattr(core_security, "get_firestore_client", lambda: fake_db)

        profile = _get_or_create_profile({"uid": "u1", "email": "a@a.com"})

        assert profile["approved"] is True


class TestRequireApproved:
    def test_allows_an_approved_user_through(self):
        current_user = {"uid": "u1", "role": "USER", "approved": True}

        assert require_approved(current_user) == current_user

    def test_rejects_an_unapproved_user_with_403(self):
        with pytest.raises(HTTPException) as exc_info:
            require_approved({"uid": "u1", "role": "USER", "approved": False})

        assert exc_info.value.status_code == 403

    def test_rejects_a_profile_missing_the_approved_field(self):
        with pytest.raises(HTTPException) as exc_info:
            require_approved({"uid": "u1", "role": "USER"})

        assert exc_info.value.status_code == 403


class TestUpdateProfileFields:
    def test_updates_display_name_only(self, monkeypatch):
        import core.security as core_security

        fake_db = FakeFirestore(users={"u1": {"email": "a@a.com", "display_name": "Old Name"}})
        monkeypatch.setattr(core_security, "get_firestore_client", lambda: fake_db)

        result = update_profile_fields("u1", display_name="New Name")

        assert result["display_name"] == "New Name"
        assert result["email"] == "a@a.com"

    def test_updates_email_only(self, monkeypatch):
        import core.security as core_security

        fake_db = FakeFirestore(users={"u1": {"email": "old@a.com", "display_name": "Name"}})
        monkeypatch.setattr(core_security, "get_firestore_client", lambda: fake_db)

        result = update_profile_fields("u1", email="new@a.com")

        assert result["email"] == "new@a.com"
        assert result["display_name"] == "Name"

    def test_updates_both_fields_together(self, monkeypatch):
        import core.security as core_security

        fake_db = FakeFirestore(users={"u1": {"email": "old@a.com", "display_name": "Old"}})
        monkeypatch.setattr(core_security, "get_firestore_client", lambda: fake_db)

        result = update_profile_fields("u1", display_name="New", email="new@a.com")

        assert result["display_name"] == "New"
        assert result["email"] == "new@a.com"

    def test_leaves_other_fields_untouched(self, monkeypatch):
        import core.security as core_security

        fake_db = FakeFirestore(users={"u1": {"email": "a@a.com", "role": "ADMIN"}})
        monkeypatch.setattr(core_security, "get_firestore_client", lambda: fake_db)

        result = update_profile_fields("u1", display_name="New Name")

        assert result["role"] == "ADMIN"

    def test_no_fields_given_is_a_no_op_read(self, monkeypatch):
        import core.security as core_security

        fake_db = FakeFirestore(users={"u1": {"email": "a@a.com", "display_name": "Name"}})
        monkeypatch.setattr(core_security, "get_firestore_client", lambda: fake_db)

        result = update_profile_fields("u1")

        assert result == {"uid": "u1", "email": "a@a.com", "display_name": "Name"}
