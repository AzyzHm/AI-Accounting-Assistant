from fastapi import APIRouter, Depends, Request

from core.security import get_current_user
from schemas.auth import UpdateProfileRequest
from services.stats_service import client_ip_from_request, record_login
from services.users_service import update_profile_fields

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/me")
async def read_current_user(request: Request, current_user: dict = Depends(get_current_user)):
    """Returns the caller's profile, creating it on their very first sign-in.

    The frontend calls this right after a successful Firebase login so it
    knows the caller's role before routing them anywhere. Each call is also
    logged as a login event (IP, user agent) for the admin dashboard.
    """
    record_login(
        uid=current_user["uid"],
        email=current_user.get("email"),
        ip=client_ip_from_request(request),
        user_agent=request.headers.get("User-Agent"),
    )
    return current_user


@router.patch("/me")
async def update_current_user(
    body: UpdateProfileRequest, current_user: dict = Depends(get_current_user)
):
    """Syncs the caller's display name and/or email into Firestore.

    Called after the frontend has already applied the change via the
    Firebase Auth client SDK (updateProfile / updateEmail), which is the
    source of truth for the credential itself. Password changes never call
    this endpoint, they stay entirely client-side.
    """
    return update_profile_fields(
        current_user["uid"], display_name=body.display_name, email=body.email
    )
