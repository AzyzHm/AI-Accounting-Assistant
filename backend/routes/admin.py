import contextlib

from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import auth as firebase_auth
from pydantic import BaseModel

from config.firebase import get_firestore_client
from core.security import USERS_COLLECTION, require_roles
from core.stats import list_recent_logins, list_usage_totals
from models.roles import Role

router = APIRouter(prefix="/admin", tags=["Admin"])


class RoleUpdateRequest(BaseModel):
    role: Role


@router.get("/users")
async def list_users(
    current_user: dict = Depends(require_roles(Role.ADMIN, Role.SUPER_ADMIN)),
):
    """Lists accounts the caller is allowed to manage.

    There is exactly one SUPER_ADMIN, so it is never included in this list,
    not even for itself. ADMIN sees USER accounts only. SUPER_ADMIN sees
    USER and ADMIN accounts.
    """
    db = get_firestore_client()
    docs = db.collection(USERS_COLLECTION).stream()
    visible_roles = (
        {Role.USER.value, Role.ADMIN.value}
        if current_user["role"] == Role.SUPER_ADMIN.value
        else {Role.USER.value}
    )
    return [
        {"uid": doc.id, **doc.to_dict()}
        for doc in docs
        if doc.to_dict().get("role") in visible_roles
    ]


@router.patch("/users/{uid}/role")
async def update_user_role(
    uid: str,
    body: RoleUpdateRequest,
    current_user: dict = Depends(require_roles(Role.SUPER_ADMIN)),
):
    """Moves a user between USER and ADMIN. SUPER_ADMIN only.

    There is exactly one SUPER_ADMIN, granted automatically to the first
    account ever created, and that never changes: nobody, including the
    SUPER_ADMIN itself, can grant or revoke that role through this endpoint.
    The SUPER_ADMIN also cannot change their own role, to avoid accidentally
    locking themselves out.
    """
    if body.role == Role.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="The SUPER_ADMIN role cannot be assigned")

    if uid == current_user["uid"]:
        raise HTTPException(status_code=400, detail="You cannot change your own role")

    db = get_firestore_client()
    doc_ref = db.collection(USERS_COLLECTION).document(uid)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    target = doc.to_dict()
    if target["role"] == Role.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="The SUPER_ADMIN account cannot be modified")

    doc_ref.update({"role": body.role.value, "approved": True})
    return {"uid": uid, **target, "role": body.role.value, "approved": True}


@router.patch("/users/{uid}/approve")
async def approve_user(
    uid: str,
    current_user: dict = Depends(require_roles(Role.ADMIN, Role.SUPER_ADMIN)),
):
    """Approves a pending sign-up so the account can start using the app.

    Every new account is created unapproved and stays locked out of chat
    until an ADMIN or SUPER_ADMIN approves it here, no matter how they
    signed up (email/password or Google). Visibility mirrors the rest of
    this router: ADMIN can only approve USER accounts, SUPER_ADMIN can
    approve USER and ADMIN accounts. Approving an already-approved account
    is a harmless no-op.
    """
    db = get_firestore_client()
    doc_ref = db.collection(USERS_COLLECTION).document(uid)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    target = doc.to_dict()
    if target["role"] == Role.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="The SUPER_ADMIN account cannot be modified")

    if current_user["role"] == Role.ADMIN.value and target["role"] != Role.USER.value:
        raise HTTPException(status_code=403, detail="ADMIN can only approve USER accounts")

    doc_ref.update({"approved": True})
    return {"uid": uid, **target, "approved": True}


@router.delete("/users/{uid}", status_code=204)
async def delete_user(
    uid: str,
    current_user: dict = Depends(require_roles(Role.ADMIN, Role.SUPER_ADMIN)),
):
    """Deletes a user's account: the Firestore profile and the Firebase Auth
    user. ADMIN can only delete USER accounts. SUPER_ADMIN can delete USER
    and ADMIN accounts. Chats already owned by the deleted account are left
    in place, they become unreachable once the account is gone."""
    if uid == current_user["uid"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    db = get_firestore_client()
    doc_ref = db.collection(USERS_COLLECTION).document(uid)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    target_role = doc.to_dict().get("role")
    if target_role == Role.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="The SUPER_ADMIN account cannot be deleted")

    if current_user["role"] == Role.ADMIN.value and target_role != Role.USER.value:
        raise HTTPException(status_code=403, detail="ADMIN can only delete USER accounts")

    doc_ref.delete()
    with contextlib.suppress(firebase_auth.UserNotFoundError):
        firebase_auth.delete_user(uid)


@router.get("/stats/logins")
async def list_login_events(
    current_user: dict = Depends(require_roles(Role.ADMIN, Role.SUPER_ADMIN)),
):
    """Lists the most recent sign-ins: who logged in, from what IP, and
    when. ADMIN sees USER accounts only, SUPER_ADMIN also sees ADMIN
    accounts. The caller never sees their own logins."""
    return list_recent_logins(current_user)


@router.get("/stats/usage")
async def list_token_usage(
    current_user: dict = Depends(require_roles(Role.ADMIN, Role.SUPER_ADMIN)),
):
    """Lists running token usage totals per account. ADMIN sees USER
    accounts only, SUPER_ADMIN also sees ADMIN accounts. The caller never
    sees their own usage."""
    return list_usage_totals(current_user)
