from datetime import UTC, date, datetime, timedelta

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from config.firebase import get_firestore_client
from schemas.roles import Role

USAGE_LIMITS_COLLECTION = "usage_limits"
USAGE_PERIODS_COLLECTION = "usage_periods"

DEFAULT_LIMITS = {
    "daily_token_limit": 100_000,
    "daily_search_limit": 30,
    "monthly_token_limit": 2_000_000,
    "monthly_search_limit": 600,
}

EXEMPT_ROLES = {Role.ADMIN.value, Role.SUPER_ADMIN.value}


def is_exempt(role: str | None) -> bool:
    """True for ADMIN and SUPER_ADMIN, who chat and search without limit."""
    return role in EXEMPT_ROLES


def _today_utc() -> date:
    return datetime.now(UTC).date()


def _current_periods() -> tuple[str, str]:
    """Returns (daily_period, monthly_period) keys for right now, as
    "YYYY-MM-DD" and "YYYY-MM". Stored usage is only valid for the period
    key it was recorded under, any other key means it has rolled over."""
    today = _today_utc()
    return today.isoformat(), today.strftime("%Y-%m")


def next_daily_reset() -> str:
    """The date (UTC) the daily token/search counters next reset."""
    return (_today_utc() + timedelta(days=1)).isoformat()


def next_monthly_reset() -> str:
    """The date (UTC) the monthly token/search counters next reset."""
    today = _today_utc()
    if today.month == 12:
        return date(today.year + 1, 1, 1).isoformat()
    return date(today.year, today.month + 1, 1).isoformat()


def get_limits(uid: str) -> dict:
    """Returns a user's effective token/search limits: DEFAULT_LIMITS with
    any admin-configured override applied on top, field by field."""
    db = get_firestore_client()
    doc = db.collection(USAGE_LIMITS_COLLECTION).document(uid).get()
    overrides = doc.to_dict() or {}
    return {key: overrides.get(key, default) for key, default in DEFAULT_LIMITS.items()}


def set_limits(
    uid: str,
    *,
    daily_token_limit: int,
    daily_search_limit: int,
    monthly_token_limit: int,
    monthly_search_limit: int,
) -> dict:
    """Sets a user's token/search limit overrides, replacing all four
    fields at once so an admin editing the form always saves a complete,
    consistent set of limits."""
    db = get_firestore_client()
    db.collection(USAGE_LIMITS_COLLECTION).document(uid).set(
        {
            "daily_token_limit": daily_token_limit,
            "daily_search_limit": daily_search_limit,
            "monthly_token_limit": monthly_token_limit,
            "monthly_search_limit": monthly_search_limit,
        }
    )
    return get_limits(uid)


def _usage_now(uid: str) -> dict:
    """Returns the caller's token/search usage for the current day and
    month. A stored period that has already rolled over reads as zero,
    the actual reset is only persisted the next time usage is recorded."""
    db = get_firestore_client()
    doc = db.collection(USAGE_PERIODS_COLLECTION).document(uid).get()
    stored = doc.to_dict() or {}
    daily_period, monthly_period = _current_periods()

    daily_current = stored.get("daily_period") == daily_period
    monthly_current = stored.get("monthly_period") == monthly_period

    return {
        "daily_period": daily_period,
        "daily_tokens": stored.get("daily_tokens", 0) if daily_current else 0,
        "daily_searches": stored.get("daily_searches", 0) if daily_current else 0,
        "monthly_period": monthly_period,
        "monthly_tokens": stored.get("monthly_tokens", 0) if monthly_current else 0,
        "monthly_searches": stored.get("monthly_searches", 0) if monthly_current else 0,
    }


def _apply_usage_delta(uid: str, *, tokens: int = 0, searches: int = 0) -> None:
    """Adds `tokens` and/or `searches` to a user's current daily and
    monthly counters, rolling either counter over to zero first if it
    belongs to a period that has since ended."""
    usage = _usage_now(uid)
    db = get_firestore_client()
    db.collection(USAGE_PERIODS_COLLECTION).document(uid).set(
        {
            "daily_period": usage["daily_period"],
            "daily_tokens": usage["daily_tokens"] + tokens,
            "daily_searches": usage["daily_searches"] + searches,
            "monthly_period": usage["monthly_period"],
            "monthly_tokens": usage["monthly_tokens"] + tokens,
            "monthly_searches": usage["monthly_searches"] + searches,
            "updated_at": SERVER_TIMESTAMP,
        }
    )


def record_token_usage(uid: str, token_usage: dict, role: str | None = None) -> None:
    """Rolls one reply's token cost into the caller's daily and monthly
    quota counters. A no-op for ADMIN/SUPER_ADMIN, whose usage is never
    checked against a limit, so there is nothing to track it against."""
    if is_exempt(role):
        return
    _apply_usage_delta(uid, tokens=token_usage.get("total_tokens", 0))


def record_search_usage(uid: str, role: str | None = None) -> None:
    """Rolls one Tavily web search credit into the caller's daily and
    monthly quota counters. A no-op for ADMIN/SUPER_ADMIN, see
    record_token_usage."""
    if is_exempt(role):
        return
    _apply_usage_delta(uid, searches=1)


def _token_limit_message(period: str, limit: int, reset_at: str) -> str:
    return (
        f"You've reached your {period} token limit of {limit:,} tokens. "
        f"Chat is unavailable until it resets on {reset_at}."
    )


def _search_limit_message(reset_at: str) -> str:
    return (
        "Answering this needs a live web search, but your web search limit has been "
        f"reached. I can't search the web again until it resets on {reset_at}."
    )


def token_limit_message(uid: str, role: str | None = None) -> str | None:
    """Returns a ready-to-display message if the caller has reached their
    daily or monthly token limit, naming the limit and its exact reset
    date, or None if they are still within both. Always None for
    ADMIN/SUPER_ADMIN, who are exempt."""
    if is_exempt(role):
        return None

    limits = get_limits(uid)
    usage = _usage_now(uid)

    if usage["daily_tokens"] >= limits["daily_token_limit"]:
        return _token_limit_message("daily", limits["daily_token_limit"], next_daily_reset())
    if usage["monthly_tokens"] >= limits["monthly_token_limit"]:
        return _token_limit_message("monthly", limits["monthly_token_limit"], next_monthly_reset())
    return None


def search_limit_message(uid: str, role: str | None = None) -> str | None:
    """Returns a ready-to-display message if the caller has reached their
    daily or monthly web search limit, naming the exact reset date, or
    None if they are still within both. Always None for ADMIN/SUPER_ADMIN,
    who are exempt."""
    if is_exempt(role):
        return None

    limits = get_limits(uid)
    usage = _usage_now(uid)

    if usage["daily_searches"] >= limits["daily_search_limit"]:
        return _search_limit_message(next_daily_reset())
    if usage["monthly_searches"] >= limits["monthly_search_limit"]:
        return _search_limit_message(next_monthly_reset())
    return None


def get_limits_and_usage(uid: str) -> dict:
    """Returns a user's configured limits alongside their current daily and
    monthly consumption and the exact reset dates, for the admin dashboard."""
    usage = _usage_now(uid)
    return {
        "limits": get_limits(uid),
        "usage": {
            "daily_tokens": usage["daily_tokens"],
            "daily_searches": usage["daily_searches"],
            "monthly_tokens": usage["monthly_tokens"],
            "monthly_searches": usage["monthly_searches"],
        },
        "daily_reset_at": next_daily_reset(),
        "monthly_reset_at": next_monthly_reset(),
    }
