from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from config.firebase import get_firestore_client
from schemas.roles import Role

USERS_COLLECTION = "users"


def get_or_create_profile(decoded_token: dict) -> dict:
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


def get_profile(uid: str) -> dict | None:
    """Returns a user's Firestore profile, or None if it does not exist."""
    db = get_firestore_client()
    doc = db.collection(USERS_COLLECTION).document(uid).get()
    if not doc.exists:
        return None
    return {"uid": uid, **doc.to_dict()}


def list_profiles() -> dict[str, dict]:
    """Returns every user profile as {uid: profile}, unfiltered.

    Callers apply their own visibility rules (who can see whom) on top of
    this, see `list_visible_profiles` for the shared ADMIN/SUPER_ADMIN rule.
    """
    db = get_firestore_client()
    return {doc.id: doc.to_dict() for doc in db.collection(USERS_COLLECTION).stream()}


def list_visible_profiles(viewer: dict, *, exclude_viewer: bool) -> dict[str, dict]:
    """Returns {uid: profile} for every account the viewer is allowed to see.

    ADMIN sees USER accounts only, SUPER_ADMIN sees USER and ADMIN accounts.
    `exclude_viewer` drops the viewer's own account from the result, used by
    the login/usage dashboards so nobody ever sees themselves in a log.
    """
    visible_roles = (
        {Role.USER.value, Role.ADMIN.value}
        if viewer["role"] == Role.SUPER_ADMIN.value
        else {Role.USER.value}
    )
    visible: dict[str, dict] = {}
    for uid, profile in list_profiles().items():
        if exclude_viewer and uid == viewer["uid"]:
            continue
        if profile.get("role") in visible_roles:
            visible[uid] = profile
    return visible


def update_role(uid: str, role: str) -> dict:
    """Sets a user's role and auto-approves the account, since a role grant
    should never leave the promoted account locked out."""
    db = get_firestore_client()
    doc_ref = db.collection(USERS_COLLECTION).document(uid)
    doc_ref.update({"role": role, "approved": True})
    return {"uid": uid, **doc_ref.get().to_dict()}


def approve(uid: str) -> dict:
    """Marks a user's account as approved."""
    db = get_firestore_client()
    doc_ref = db.collection(USERS_COLLECTION).document(uid)
    doc_ref.update({"approved": True})
    return {"uid": uid, **doc_ref.get().to_dict()}


def delete_profile(uid: str) -> None:
    """Deletes a user's Firestore profile. Does not touch Firebase Auth,
    callers are responsible for also deleting the Auth user if needed."""
    db = get_firestore_client()
    db.collection(USERS_COLLECTION).document(uid).delete()
