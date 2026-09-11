import re

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from config.firebase import get_firestore_client

CHATS_COLLECTION = "chats"
MESSAGES_SUBCOLLECTION = "messages"
DEFAULT_TITLE = "Untitled chat"
MAX_HISTORY_MESSAGES = 10
TITLE_MAX_LENGTH = 60

_UNTITLED_SUFFIX_RE = re.compile(r"^Untitled chat \((\d+)\)$")


def _chat_doc(db, chat_id: str):
    return db.collection(CHATS_COLLECTION).document(chat_id)


def _next_untitled_title(owner_uid: str) -> str:
    """Picks the next free "Untitled chat" / "Untitled chat (N)" title for
    this owner, so a fresh chat never silently shares a name with one that
    still has it. Only ever consulted for the auto-generated default,
    a title the owner picks themselves through rename is never touched."""
    existing = {chat["title"] for chat in list_chats(owner_uid)}
    if DEFAULT_TITLE not in existing:
        return DEFAULT_TITLE

    used = {1}
    for title in existing:
        match = _UNTITLED_SUFFIX_RE.match(title)
        if match:
            used.add(int(match.group(1)))

    next_n = max(used) + 1
    return f"{DEFAULT_TITLE} ({next_n})"


def create_chat(owner_uid: str) -> dict:
    """Creates a new, empty chat owned by `owner_uid`, titled "Untitled
    chat", or "Untitled chat (N)" if that title is already in use."""
    db = get_firestore_client()
    doc_ref = db.collection(CHATS_COLLECTION).document()
    chat = {
        "owner_uid": owner_uid,
        "title": _next_untitled_title(owner_uid),
        "created_at": SERVER_TIMESTAMP,
        "updated_at": SERVER_TIMESTAMP,
    }
    doc_ref.set(chat)
    return {"id": doc_ref.id, **doc_ref.get().to_dict()}


def list_chats(owner_uid: str) -> list[dict]:
    """Lists every chat owned by `owner_uid`, most recently active first."""
    db = get_firestore_client()
    query = (
        db.collection(CHATS_COLLECTION)
        .where("owner_uid", "==", owner_uid)
        .order_by("updated_at", direction="DESCENDING")
    )
    return [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]


def get_chat(chat_id: str) -> dict | None:
    """Returns a chat's metadata, or None if it does not exist."""
    db = get_firestore_client()
    doc = _chat_doc(db, chat_id).get()
    if not doc.exists:
        return None
    return {"id": doc.id, **doc.to_dict()}


def get_messages(chat_id: str, limit: int | None = None) -> list[dict]:
    """Returns a chat's messages, oldest first. When `limit` is given, only
    the most recent `limit` messages are returned (still oldest first)."""
    db = get_firestore_client()
    query = _chat_doc(db, chat_id).collection(MESSAGES_SUBCOLLECTION).order_by("created_at")
    docs = list(query.stream())
    if limit is not None:
        docs = docs[-limit:]
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def add_message(
    chat_id: str,
    role: str,
    content: str,
    category: str | None = None,
    token_usage: dict | None = None,
) -> dict:
    """Appends a message to a chat's messages subcollection."""
    db = get_firestore_client()
    messages = _chat_doc(db, chat_id).collection(MESSAGES_SUBCOLLECTION)
    doc_ref = messages.document()
    message: dict = {"role": role, "content": content, "created_at": SERVER_TIMESTAMP}
    if category is not None:
        message["category"] = category
    if token_usage is not None:
        message["token_usage"] = token_usage
    doc_ref.set(message)
    return {"id": doc_ref.id, **doc_ref.get().to_dict()}


def touch_chat(chat_id: str, title: str | None = None) -> None:
    """Bumps a chat's updated_at, optionally also (re)setting its title."""
    db = get_firestore_client()
    update: dict = {"updated_at": SERVER_TIMESTAMP}
    if title is not None:
        update["title"] = title
    _chat_doc(db, chat_id).update(update)


def rename_chat(chat_id: str, title: str) -> None:
    """Explicitly renames a chat, for example from a "rename" action in the UI."""
    db = get_firestore_client()
    _chat_doc(db, chat_id).update({"title": title, "updated_at": SERVER_TIMESTAMP})


def delete_chat(chat_id: str) -> None:
    """Deletes a chat and every message in it."""
    db = get_firestore_client()
    doc_ref = _chat_doc(db, chat_id)
    messages = doc_ref.collection(MESSAGES_SUBCOLLECTION)
    for message in messages.stream():
        messages.document(message.id).delete()
    doc_ref.delete()


def title_from_query(query: str) -> str:
    """Derives a short title from a message's text.

    Not used to auto-title chats (they keep "Untitled chat" until the owner
    renames one), kept as a small utility other callers might still want.
    """
    trimmed = query.strip()
    if len(trimmed) <= TITLE_MAX_LENGTH:
        return trimmed or DEFAULT_TITLE
    return trimmed[:TITLE_MAX_LENGTH].rstrip() + "…"
