"""
Memory Manager — Read/write/append the 3 OpenClaw-style markdown memory files.
  memory.md   → lifetime knowledge graph
  daily.md    → today's session log
  conversation.md → active chat transcript
"""

import os
from datetime import datetime
from config import config


def _path(filename: str) -> str:
    return os.path.join(config.MEMORY_DIR, filename)


def ensure_files() -> None:
    """Create memory directory and seed files if they don't exist."""
    os.makedirs(config.MEMORY_DIR, exist_ok=True)

    defaults = {
        "memory.md": (
            "# User Knowledge Graph\n\n"
            "## User Profile\n"
            "- Learning style: unknown\n"
            "- Struggles with: unknown\n\n"
            "## Topics Mastered\n\n"
            "## Learning Progress Tree\n\n"
            "## Synthesis Insights\n\n"
        ),
        "daily.md": (
            f"# Daily Log: {datetime.now().strftime('%Y-%m-%d')}\n\n"
            "## Session Goal\n\n"
            "## Progress Timeline\n\n"
        ),
        "conversation.md": (
            f"# Conversation: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        ),
    }

    for fname, content in defaults.items():
        p = _path(fname)
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)


# ── Readers ────────────────────────────────────────────────────────────

def read(filename: str) -> str:
    p = _path(filename)
    if not os.path.exists(p):
        return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def read_all() -> dict[str, str]:
    """Return contents of all three files."""
    return {
        "memory": read("memory.md"),
        "daily": read("daily.md"),
        "conversation": read("conversation.md"),
    }


# ── Writers ────────────────────────────────────────────────────────────

def append(filename: str, content: str) -> None:
    with open(_path(filename), "a", encoding="utf-8") as f:
        f.write(content + "\n")


def overwrite(filename: str, content: str) -> None:
    with open(_path(filename), "w", encoding="utf-8") as f:
        f.write(content)


# ── High-Level Helpers ─────────────────────────────────────────────────

def _now() -> str:
    return datetime.now().strftime("%H:%M")


def log_conversation(role: str, message: str) -> None:
    """Append a timestamped message to conversation.md."""
    append("conversation.md", f"[{_now()}] {role}: {message}\n")


def log_daily(entry: str) -> None:
    """Append a timestamped entry to daily.md."""
    append("daily.md", f"### {_now()} — {entry}\n")


def update_mastery(concept: str, answer: str, insights: str) -> None:
    """Record mastery of a concept in memory.md."""
    entry = (
        f"\n### {concept}\n"
        f"- Mastered: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"- Synthesis answer: {answer[:200]}\n"
        f"- Key insight: {insights}\n"
    )
    append("memory.md", entry)


def update_progress_tree(tree_text: str) -> None:
    """Replace the Learning Progress Tree section in memory.md."""
    content = read("memory.md")
    marker = "## Learning Progress Tree"
    next_marker = "## Synthesis Insights"

    if marker in content and next_marker in content:
        before = content[: content.index(marker)]
        after = content[content.index(next_marker):]
        new_content = before + marker + "\n\n" + tree_text + "\n\n" + after
        overwrite("memory.md", new_content)
    else:
        append("memory.md", f"\n{marker}\n\n{tree_text}\n")


def reset_daily() -> None:
    """Reset daily.md for a new session."""
    overwrite(
        "daily.md",
        f"# Daily Log: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        "## Session Goal\n\n"
        "## Progress Timeline\n\n",
    )


def reset_conversation() -> None:
    """Reset conversation.md for a new chat."""
    overwrite(
        "conversation.md",
        f"# Conversation: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n",
    )
