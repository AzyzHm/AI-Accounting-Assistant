from graph.state import HistoryTurn

MAX_HISTORY_TURNS = 10


def format_history(history: list[HistoryTurn], max_turns: int = MAX_HISTORY_TURNS) -> str:
    """Renders the last `max_turns` turns of the conversation as plain
    dialogue lines, oldest first, so a prompt can follow up on what was
    already discussed. Returns an empty string when there is no history."""
    recent = history[-max_turns:]
    lines = []
    for turn in recent:
        speaker = "User" if turn.get("role") == "user" else "Assistant"
        lines.append(f"{speaker}: {turn.get('content', '')}")
    return "\n".join(lines)
