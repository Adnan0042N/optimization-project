"""
Prerequisite Tree Builder — recursively decomposes a topic into prerequisites
until reaching fundamental facts, then produces a bottom-up teaching order.
"""

import json
from typing import Any

from modules.llm_client import call_llm
from modules import cache


DECOMPOSE_PROMPT = """You are a knowledge decomposition expert. Break down the topic "{topic}" into its prerequisite concepts.

Rules:
1. List 2-4 prerequisite concepts that someone MUST understand BEFORE they can learn "{topic}".
2. Each prerequisite must be SIMPLER than "{topic}".
3. If "{topic}" is a basic fact that can be explained in ONE sentence without prerequisites, respond with exactly: FACT
4. Order from most fundamental to most complex.

RESPOND IN THIS EXACT FORMAT (no extra text):
1. First prerequisite
2. Second prerequisite
3. Third prerequisite

Or just: FACT"""

FACT_EXPLAIN_PROMPT = """Explain "{topic}" in exactly ONE simple sentence that a 10-year-old could understand. No jargon."""


def build_prerequisite_tree(
    topic: str,
    depth: int = 0,
    max_depth: int = 5,
    visited: set | None = None,
) -> dict:
    """
    Recursively build a prerequisite tree for the given topic.
    Returns a dict: {topic, type, explanation?, children[]}
    """
    if visited is None:
        visited = set()

    # Prevent cycles
    topic_key = topic.lower().strip()
    if topic_key in visited:
        return {"topic": topic, "type": "LEAF", "children": [], "reason": "cycle"}
    visited.add(topic_key)

    # Check cache first
    cached = cache.get_cached_tree(topic)
    if cached and depth == 0:
        return cached

    # Max depth reached
    if depth >= max_depth:
        explanation = call_llm(FACT_EXPLAIN_PROMPT.format(topic=topic))
        return {"topic": topic, "type": "LEAF", "explanation": explanation, "children": []}

    # Ask LLM for prerequisites
    response = call_llm(DECOMPOSE_PROMPT.format(topic=topic), temperature=0.4)

    # Basic fact — no prerequisites needed
    if response.strip().upper() == "FACT" or "FACT" in response.strip().upper().split("\n")[0]:
        explanation = call_llm(FACT_EXPLAIN_PROMPT.format(topic=topic))
        return {"topic": topic, "type": "FACT", "explanation": explanation, "children": []}

    # Parse prerequisites from numbered list
    prerequisites = _parse_prerequisites(response)

    if not prerequisites:
        explanation = call_llm(FACT_EXPLAIN_PROMPT.format(topic=topic))
        return {"topic": topic, "type": "FACT", "explanation": explanation, "children": []}

    # Recursively build subtrees
    tree = {"topic": topic, "type": "CONCEPT", "children": []}
    for prereq in prerequisites[:4]:  # Limit branching factor
        subtree = build_prerequisite_tree(prereq, depth + 1, max_depth, visited)
        tree["children"].append(subtree)

    # Cache at root level
    if depth == 0:
        cache.store_tree(topic, tree)

    return tree


def _parse_prerequisites(response: str) -> list[str]:
    """Extract prerequisite names from a numbered/bulleted list."""
    prerequisites = []
    for line in response.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Remove number prefix (1. 2. 3.) or bullet (- *)
        if len(line) > 2 and line[0].isdigit() and ("." in line[:3] or ")" in line[:3]):
            prereq = line.split(".", 1)[-1].strip() if "." in line[:3] else line.split(")", 1)[-1].strip()
        elif line.startswith(("-", "*", "•")):
            prereq = line.lstrip("-*• ").strip()
        else:
            continue
        # Clean up
        prereq = prereq.strip("`\"'")
        if prereq and len(prereq) > 1:
            prerequisites.append(prereq)
    return prerequisites


def tree_to_teaching_order(tree: dict) -> list[dict]:
    """
    Post-order traversal → bottom-up teaching sequence.
    Returns list of {topic, type, explanation?} dicts (no duplicates).
    """
    order: list[dict] = []
    seen: set[str] = set()

    def _traverse(node: dict) -> None:
        for child in node.get("children", []):
            _traverse(child)
        key = node["topic"].lower().strip()
        if key not in seen:
            seen.add(key)
            order.append({
                "topic": node["topic"],
                "type": node.get("type", "CONCEPT"),
                "explanation": node.get("explanation", ""),
            })

    _traverse(tree)
    return order


def tree_to_text(tree: dict, indent: int = 0) -> str:
    """Pretty-print tree as indented text."""
    prefix = "  " * indent
    marker = " [FACT]" if tree.get("type") == "FACT" else ""
    lines = [f"{prefix}├─ {tree['topic']}{marker}"]
    for child in tree.get("children", []):
        lines.append(tree_to_text(child, indent + 1))
    return "\n".join(lines)


def prune_mastered(tree: dict, mastered: set[str]) -> dict:
    """
    Remove already-mastered concepts from the tree.
    Keeps the node but marks it as MASTERED.
    """
    topic_lower = tree["topic"].lower().strip()
    new_type = "MASTERED" if topic_lower in mastered else tree.get("type", "CONCEPT")
    pruned_children = [
        prune_mastered(child, mastered) for child in tree.get("children", [])
    ]
    return {
        **tree,
        "type": new_type,
        "children": pruned_children,
    }
