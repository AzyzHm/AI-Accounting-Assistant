from google.cloud.firestore_v1 import SERVER_TIMESTAMP, Increment

from config.firebase import get_firestore_client
from services import users_service

LOGIN_EVENTS_COLLECTION = "login_events"
USAGE_TOTALS_COLLECTION = "usage_totals"
USERS_COLLECTION = "users"
RECENT_LOGINS_LIMIT = 200


def client_ip_from_request(request) -> str | None:
    """Best-effort caller IP: the first hop in X-Forwarded-For when the app
    is behind a proxy or load balancer, otherwise the direct socket peer."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


def record_login(uid: str, email: str | None, ip: str | None, user_agent: str | None) -> None:
    """Appends a login event and stamps the user's profile with their most
    recent sign-in, so the admin dashboard can show "who logged in, from
    what IP" without scanning every event for a quick per-user summary."""
    db = get_firestore_client()
    db.collection(LOGIN_EVENTS_COLLECTION).document().set(
        {
            "uid": uid,
            "email": email,
            "ip": ip,
            "user_agent": user_agent,
            "created_at": SERVER_TIMESTAMP,
        }
    )
    db.collection(USERS_COLLECTION).document(uid).update(
        {"last_login_at": SERVER_TIMESTAMP, "last_login_ip": ip}
    )


def list_recent_logins(viewer: dict, limit: int = RECENT_LOGINS_LIMIT) -> list[dict]:
    """Returns the most recent login events for accounts the viewer is
    allowed to see, newest first: ADMIN sees USER logins, SUPER_ADMIN sees
    USER and ADMIN logins. The viewer's own logins are never included, and
    each event is enriched with the account's current display name and role
    so the dashboard doesn't need a second lookup."""
    visible_users = users_service.list_visible_profiles(viewer, exclude_viewer=True)
    db = get_firestore_client()
    query = db.collection(LOGIN_EVENTS_COLLECTION).order_by("created_at", direction="DESCENDING")

    events: list[dict] = []
    for doc in query.stream():
        event = doc.to_dict()
        profile = visible_users.get(event.get("uid"))
        if profile is None:
            continue
        events.append(
            {
                "id": doc.id,
                **event,
                "display_name": profile.get("display_name"),
                "role": profile.get("role"),
            }
        )
        if len(events) >= limit:
            break
    return events


def record_usage(uid: str, token_usage: dict) -> None:
    """Rolls one reply's token cost into a per-user running total, so the
    admin dashboard can read one small doc per user instead of summing every
    message they have ever sent."""
    db = get_firestore_client()
    db.collection(USAGE_TOTALS_COLLECTION).document(uid).set(
        {
            "prompt_tokens": Increment(token_usage.get("prompt_tokens", 0)),
            "completion_tokens": Increment(token_usage.get("completion_tokens", 0)),
            "total_tokens": Increment(token_usage.get("total_tokens", 0)),
            "message_count": Increment(1),
            "updated_at": SERVER_TIMESTAMP,
        },
        merge=True,
    )


def list_usage_totals(viewer: dict) -> list[dict]:
    """Returns running token usage totals for accounts the viewer is allowed
    to see, enriched with each account's email, display name, and role:
    ADMIN sees USER totals, SUPER_ADMIN sees USER and ADMIN totals. The
    viewer's own usage is never included."""
    visible_users = users_service.list_visible_profiles(viewer, exclude_viewer=True)
    db = get_firestore_client()

    totals: list[dict] = []
    for doc in db.collection(USAGE_TOTALS_COLLECTION).stream():
        profile = visible_users.get(doc.id)
        if profile is None:
            continue
        totals.append(
            {
                "uid": doc.id,
                "email": profile.get("email"),
                "display_name": profile.get("display_name"),
                "role": profile.get("role"),
                **doc.to_dict(),
            }
        )
    return totals
