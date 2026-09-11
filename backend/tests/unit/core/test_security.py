import pytest
from fastapi import HTTPException

from core.security import require_approved


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
