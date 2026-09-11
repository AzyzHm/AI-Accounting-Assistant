import logging

from fastapi import Depends, HTTPException, Request
from firebase_admin import auth as firebase_auth

from schemas.roles import Role
from services import users_service

logger = logging.getLogger(__name__)


def _extract_bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization")
    if not header or not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    return header.removeprefix("Bearer ").strip()


def get_current_user(request: Request) -> dict:
    """Verifies the Firebase ID token on the request and returns the caller's
    Firestore profile (uid, email, display_name, role, approved). Raises 401
    if the token is missing, malformed, expired, or revoked.

    `clock_skew_seconds=60` tolerates the caller's machine clock being off
    by up to a minute (the maximum this SDK allows). Without it, a local
    dev machine whose clock has drifted gets "Token used too early/late"
    errors on every request, forcing manual clock syncs before the app
    works at all. Firebase issues and expires tokens using its own server
    clock regardless, so this only relaxes the local comparison, it does
    not change how long a token is actually valid for.
    """
    token = _extract_bearer_token(request)
    try:
        decoded_token = firebase_auth.verify_id_token(token, clock_skew_seconds=60)
    except (
        firebase_auth.InvalidIdTokenError,
        firebase_auth.ExpiredIdTokenError,
        firebase_auth.RevokedIdTokenError,
        ValueError,
    ) as exc:
        logger.warning("Firebase token verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    return users_service.get_or_create_profile(decoded_token)


def require_approved(current_user: dict = Depends(get_current_user)) -> dict:
    """FastAPI dependency, raises 403 unless the caller's account has been
    approved by an ADMIN or SUPER_ADMIN. Use as `Depends(require_approved)`
    on every route a brand-new sign-up must not be able to reach yet (chat,
    and anything else that does real work). `/auth/me` deliberately does
    NOT use this, an unapproved caller still needs it to learn their own
    status so the frontend can show a "pending approval" screen instead of
    a bare 403.
    """
    if not current_user.get("approved", False):
        raise HTTPException(status_code=403, detail="Account pending admin approval")
    return current_user


def require_roles(*roles: Role):
    """FastAPI dependency factory, raises 403 unless the caller's role is
    one of `roles`. Use as `Depends(require_roles(Role.ADMIN, Role.SUPER_ADMIN))`.
    """
    allowed = {role.value for role in roles}

    def _dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return current_user

    return _dependency
