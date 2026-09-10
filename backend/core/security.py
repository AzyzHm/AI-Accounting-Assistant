import logging

from fastapi import Depends, HTTPException, Request
from firebase_admin import auth as firebase_auth
from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from config.firebase import get_firestore_client
from models.roles import Role

logger = logging.getLogger(__name__)

USERS_COLLECTION = "users"


def _extract_bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization")
    if not header or not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    return header.removeprefix("Bearer ").strip()


def _get_or_create_profile(decoded_token: dict) -> dict:
    """Fetches the Firestore profile for this uid, creating it on first sign-in.

    The very first account ever created becomes SUPER_ADMIN and is approved
    immediately, so there is always at least one admin able to approve and
    promote everyone else. Every subsequent account defaults to USER and is
    created unapproved, they cannot use the app (see `require_approved`)
    until an ADMIN or SUPER_ADMIN approves them from the admin dashboard.
    This applies no matter how the account was created (email/password or
    Google), the check happens here, after Firebase has already verified
    the caller's identity.
    """
    db = get_firestore_client()
    uid = decoded_token["uid"]
    doc_ref = db.collection(USERS_COLLECTION).document(uid)
    doc = doc_ref.get()

    if doc.exists:
        return {"uid": uid, **doc.to_dict()}

    is_first_user = len(list(db.collection(USERS_COLLECTION).limit(1).stream())) == 0
    profile = {
        "email": decoded_token.get("email"),
        "display_name": decoded_token.get("name"),
        "role": Role.SUPER_ADMIN.value if is_first_user else Role.USER.value,
        "approved": is_first_user,
        "created_at": SERVER_TIMESTAMP,
    }
    doc_ref.set(profile)

    return {"uid": uid, **doc_ref.get().to_dict()}


def update_profile_fields(
    uid: str, *, display_name: str | None = None, email: str | None = None
) -> dict:
    """Merges the given fields into the caller's Firestore profile.

    Only fields that are not None are written, so a name-only update never
    touches the stored email and vice versa. Password changes never reach
    this function, they happen entirely client-side via the Firebase Auth
    SDK and are never mirrored into Firestore.
    """
    db = get_firestore_client()
    doc_ref = db.collection(USERS_COLLECTION).document(uid)
    updates = {
        key: value
        for key, value in {"display_name": display_name, "email": email}.items()
        if value is not None
    }
    if updates:
        doc_ref.update(updates)
    return {"uid": uid, **doc_ref.get().to_dict()}


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

    return _get_or_create_profile(decoded_token)


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
