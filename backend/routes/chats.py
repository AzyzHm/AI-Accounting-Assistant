import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from core.logger import get_logger
from core.security import require_approved
from graph.workflow import NODE_LABELS, app
from schemas.chats import MessageRequest, RenameRequest
from services.chats_service import (
    MAX_HISTORY_MESSAGES,
    add_message,
    create_chat,
    delete_chat,
    get_chat,
    get_messages,
    list_chats,
    rename_chat,
    touch_chat,
)
from services.stats_service import record_usage

logger = get_logger(__name__)

router = APIRouter(prefix="/chats", tags=["Chats"])


def _owned_chat_or_404(chat_id: str, uid: str) -> dict:
    chat = get_chat(chat_id)
    if chat is None or chat["owner_uid"] != uid:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


def _sse_event(payload: dict) -> str:
    """Formats a dict as a single Server-Sent Event line."""
    return f"data: {json.dumps(payload)}\n\n"


def _stream_chat_reply(chat_id: str, query: str, history: list[dict], uid: str):
    """
    Runs the RAG graph for one message, yielding an SSE "progress" event
    every time a node finishes (refining the query, searching the web,
    searching sources, writing the answer...), so the frontend can show the
    agent's progress in real time. Ends with a "done" event carrying the
    final answer, or an "error" event if the agent failed.

    Also persists the assistant's reply and rolls its token cost into the
    caller's usage total, exactly like a synchronous call would.
    """
    result: dict = {}
    try:
        for update in app.stream({"query": query, "history": history}, stream_mode="updates"):  # type: ignore
            for node_name, node_update in update.items():
                result.update(node_update)
                label = NODE_LABELS.get(node_name, node_name)
                logger.info("Chat %s progress: %s (%s)", chat_id, node_name, label)
                yield _sse_event({"event": "progress", "node": node_name, "label": label})
    except Exception as e:
        logger.error("Chat %s graph error: %s", chat_id, e)
        yield _sse_event({"event": "error", "detail": str(e)})
        return

    answer = result.get("answer") or ""
    category = result.get("category")
    token_usage = result.get("token_usage")

    add_message(
        chat_id, role="assistant", content=answer, category=category, token_usage=token_usage
    )
    touch_chat(chat_id)
    if token_usage:
        record_usage(uid, token_usage)

    yield _sse_event(
        {"event": "done", "response": answer, "category": category, "chat_id": chat_id}
    )


@router.post("/")
async def start_chat(current_user: dict = Depends(require_approved)):
    """Creates a new, empty chat owned by the caller."""
    return create_chat(current_user["uid"])


@router.get("/")
async def list_my_chats(current_user: dict = Depends(require_approved)):
    """Lists the caller's chats, most recently active first."""
    return list_chats(current_user["uid"])


@router.get("/{chat_id}")
async def get_chat_detail(chat_id: str, current_user: dict = Depends(require_approved)):
    """Returns a chat and its full message history. Only the owner can read it."""
    chat = _owned_chat_or_404(chat_id, current_user["uid"])
    chat["messages"] = get_messages(chat_id)
    return chat


@router.patch("/{chat_id}")
async def rename_my_chat(
    chat_id: str, body: RenameRequest, current_user: dict = Depends(require_approved)
):
    """Renames a chat. Only the owner can rename it."""
    _owned_chat_or_404(chat_id, current_user["uid"])
    rename_chat(chat_id, body.title)
    return {"id": chat_id, "title": body.title}


@router.delete("/{chat_id}", status_code=204)
async def delete_my_chat(chat_id: str, current_user: dict = Depends(require_approved)):
    """Deletes a chat and all of its messages. Only the owner can delete it."""
    _owned_chat_or_404(chat_id, current_user["uid"])
    delete_chat(chat_id)


@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: str, body: MessageRequest, current_user: dict = Depends(require_approved)
):
    """Sends a message in an existing chat and streams the agent's progress.

    Runs the agent with the chat's last MAX_HISTORY_MESSAGES messages as
    conversational context. The response is a Server-Sent Events stream:
    one "progress" event per graph node the agent moves through (refining
    the query, searching the web, searching sources, writing the answer...),
    then a final "done" event with the answer, or an "error" event if the
    agent failed. Stores both the user's message and the assistant's reply,
    and rolls the reply's token cost into the caller's usage total. The
    chat's title is left untouched, it stays "Untitled chat" (or whatever
    the owner renamed it to) until they rename it.
    """
    _owned_chat_or_404(chat_id, current_user["uid"])

    history = [
        {"role": message["role"], "content": message["content"]}
        for message in get_messages(chat_id, limit=MAX_HISTORY_MESSAGES)
    ]

    add_message(chat_id, role="user", content=body.query)

    return StreamingResponse(
        _stream_chat_reply(chat_id, body.query, history, current_user["uid"]),
        media_type="text/event-stream",
    )
