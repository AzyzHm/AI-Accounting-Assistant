import contextlib

from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import auth as firebase_auth

from core.security import require_roles
from schemas.admin import LimitsUpdateRequest, RoleUpdateRequest
from schemas.roles import Role
from services import limits_service, users_service
from services.stats_service import list_recent_logins, list_usage_totals

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users")
async def list_users(
    current_user: dict = Depends(require_roles(Role.ADMIN, Role.SUPER_ADMIN)),
):
    """Lists accounts the caller is allowed to manage.

    There is exactly one SUPER_ADMIN, so it is never included in this list,
    not even for itself. ADMIN sees USER accounts only. SUPER_ADMIN sees
    USER and ADMIN accounts.
    """
    visible = users_service.list_visible_profiles(current_user, exclude_viewer=False)
    return [{"uid": uid, **profile} for uid, profile in visible.items()]


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

    target = users_service.get_profile(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    if target["role"] == Role.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="The SUPER_ADMIN account cannot be modified")

    return users_service.update_role(uid, body.role.value)


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
    target = users_service.get_profile(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    if target["role"] == Role.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="The SUPER_ADMIN account cannot be modified")

    if current_user["role"] == Role.ADMIN.value and target["role"] != Role.USER.value:
        raise HTTPException(status_code=403, detail="ADMIN can only approve USER accounts")

    return users_service.approve(uid)


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

    target = users_service.get_profile(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    target_role = target.get("role")
    if target_role == Role.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="The SUPER_ADMIN account cannot be deleted")

    if current_user["role"] == Role.ADMIN.value and target_role != Role.USER.value:
        raise HTTPException(status_code=403, detail="ADMIN can only delete USER accounts")

    users_service.delete_profile(uid)
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
    """Lists running token usage totals per account, including lifetime
    search credits spent. ADMIN sees USER accounts only, SUPER_ADMIN also
    sees ADMIN accounts. The caller never sees their own usage."""
    return list_usage_totals(current_user)


@router.get("/users/{uid}/limits")
async def get_user_limits(
    uid: str,
    current_user: dict = Depends(require_roles(Role.ADMIN, Role.SUPER_ADMIN)),
):
    """Returns a user's configured daily/monthly token and web search
    limits, alongside their current consumption and the exact dates those
    counters reset. Visibility mirrors the rest of this router: ADMIN can
    only view USER accounts, SUPER_ADMIN can also view ADMIN accounts."""
    target = users_service.get_profile(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user["role"] == Role.ADMIN.value and target["role"] != Role.USER.value:
        raise HTTPException(status_code=403, detail="ADMIN can only view USER accounts")

    return limits_service.get_limits_and_usage(uid)


@router.patch("/users/{uid}/limits")
async def update_user_limits(
    uid: str,
    body: LimitsUpdateRequest,
    current_user: dict = Depends(require_roles(Role.ADMIN, Role.SUPER_ADMIN)),
):
    """Sets a user's daily/monthly token and web search limits. Visibility
    mirrors the rest of this router: ADMIN can only edit USER accounts,
    SUPER_ADMIN can also edit ADMIN accounts. The SUPER_ADMIN account
    itself is never editable, it has no quota to begin with."""
    target = users_service.get_profile(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    if target["role"] == Role.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="The SUPER_ADMIN account cannot be modified")

    if current_user["role"] == Role.ADMIN.value and target["role"] != Role.USER.value:
        raise HTTPException(status_code=403, detail="ADMIN can only edit USER accounts")

    limits_service.set_limits(uid, **body.model_dump())
    return limits_service.get_limits_and_usage(uid)
