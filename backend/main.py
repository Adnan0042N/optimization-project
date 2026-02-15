"""
Learning Chatbot — FastAPI Backend (Stateless)
Serves the chat API and static frontend files.
All session state lives in the frontend (localStorage).
The backend receives session_context in each request and returns session_update.
"""

import json
import os
import time
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import config
from modules import cache
from modules import prerequisite as prereq_mod
from modules import explainer
from modules import synthesis
from modules import validator


# ── Pydantic models ────────────────────────────────────────────────────

class SessionContext(BaseModel):
    tree: Optional[dict] = None
    teaching_order: list = []
    current_index: int = 0
    waiting_for_synthesis: bool = False
    current_question: str = ""
    attempt_count: int = 0
    target_topic: str = ""
    all_topics: list = []
    explained_current: bool = False


class ChatRequest(BaseModel):
    message: str
    session_context: Optional[SessionContext] = None


class ChatResponse(BaseModel):
    response: str
    type: str  # "message" | "explanation" | "synthesis_question" | "feedback" | "tree"
    data: Optional[dict] = None
    session_update: Optional[dict] = None
    turn_data: Optional[dict] = None


# ── Lifespan ───────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


# ── FastAPI app ────────────────────────────────────────────────────────

app = FastAPI(title="Learning Chatbot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routes ─────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict:
    """Main chat endpoint — stateless. Receives session_context, returns session_update."""
    user_msg = req.message.strip()
    if not user_msg:
        return {"response": "Please type something!", "type": "message"}

    ctx = req.session_context or SessionContext()

    # If waiting for synthesis answer → validate it
    if ctx.waiting_for_synthesis:
        return _handle_synthesis_answer(user_msg, ctx)

    # If we have a teaching flow going and haven't explained yet
    if ctx.tree and not ctx.explained_current and ctx.current_index < len(ctx.teaching_order):
        return _explain_current_concept(ctx)

    # Check if this is a learning request
    if _is_learning_request(user_msg):
        topic = _extract_topic(user_msg)
        return _start_learning(topic, ctx)

    # General conversation or "yes/ready/next" to proceed
    if ctx.tree and ctx.current_index < len(ctx.teaching_order):
        lower = user_msg.lower()
        if any(w in lower for w in ["yes", "ready", "next", "continue", "ok", "sure", "yeah", "got it", "makes sense"]):
            return _ask_synthesis_or_next(ctx)

    # Fallback: general response
    from modules.llm_client import call_llm
    response = call_llm(
        user_msg,
        system_prompt=(
            "You are a friendly learning assistant focused on recall-based learning. "
            "If the user wants to learn a topic, tell them to type 'Learn: [topic name]'. "
            "Keep responses brief and helpful."
        ),
    )
    return {"response": response, "type": "message"}


@app.post("/api/reset")
async def reset_session() -> dict:
    """Reset server-side caches if needed."""
    return {"status": "ok", "message": "Session reset."}


# ── Serve frontend ─────────────────────────────────────────────────────

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ── Internal helpers ───────────────────────────────────────────────────

def _is_learning_request(msg: str) -> bool:
    lower = msg.lower().strip()
    triggers = [
        "what is", "explain", "teach me", "learn:", "learn about",
        "how does", "i want to learn", "help me understand",
        "tell me about", "break down",
    ]
    return any(lower.startswith(t) or t in lower for t in triggers)


def _extract_topic(msg: str) -> str:
    lower = msg.lower().strip()
    prefixes = [
        "learn:", "teach me about", "teach me", "what is",
        "explain", "i want to learn about", "i want to learn",
        "help me understand", "tell me about", "break down",
        "learn about", "how does",
    ]
    topic = msg.strip()
    for prefix in sorted(prefixes, key=len, reverse=True):
        if lower.startswith(prefix):
            topic = msg[len(prefix):].strip()
            break
    return topic.rstrip("?.!").strip()


def _start_learning(topic: str, ctx: SessionContext) -> dict:
    """Build tree, set up teaching flow, teach first concept."""
    # Build prerequisite tree
    tree = prereq_mod.build_prerequisite_tree(topic, max_depth=config.MAX_TREE_DEPTH)

    # Get mastered concepts from cache to skip them
    mastered_set = {c["concept"].lower() for c in cache.get_mastered_concepts()}
    full_order = prereq_mod.tree_to_teaching_order(tree)
    teaching_order = [t for t in full_order if t["topic"].lower() not in mastered_set]

    if not teaching_order:
        return {
            "response": f"🎉 You've already mastered all prerequisites for **{topic}**! Ask me anything about it.",
            "type": "message",
            "session_update": {
                "tree": tree,
                "is_new_tree": True,
                "topic": topic,
                "teaching_order": teaching_order,
                "current_index": 0,
                "target_topic": topic,
                "explained_current": False,
            },
        }

    tree_text = prereq_mod.tree_to_text(tree)

    # Build response
    total = len(teaching_order)
    first_topic = teaching_order[0]["topic"]
    response = (
        f"Great! Let me break down **{topic}** into building blocks.\n\n"
        f"```\n{tree_text}\n```\n\n"
        f"We'll learn **{total} concepts**, starting with the simplest: **{first_topic}**.\n\n"
    )

    # Explain the first concept immediately
    known = []
    explanation = explainer.explain_concept(first_topic, known)
    response += f"**{first_topic}**\n\n{explanation}\n\nDoes this make sense? Ready to continue?"

    # Build turn data for conversation.md tracking
    concept_id = first_topic.lower().replace(" ", "_")
    turn_data = {
        "user": f"Learn: {topic}",
        "concepts": [concept_id],
        "explanation": explanation,
        "examples": "",
        "checkQuestion": "",
    }

    return {
        "response": response,
        "type": "tree",
        "session_update": {
            "tree": tree,
            "is_new_tree": True,
            "topic": topic,
            "teaching_order": teaching_order,
            "current_index": 0,
            "target_topic": topic,
            "explained_current": True,
            "waiting_for_synthesis": False,
        },
        "turn_data": turn_data,
        "data": {"tree": tree, "teaching_order": [t["topic"] for t in teaching_order]},
    }


def _explain_current_concept(ctx: SessionContext) -> dict:
    """Explain the concept at current_index."""
    index = ctx.current_index
    concept_info = ctx.teaching_order[index]
    concept = concept_info["topic"] if isinstance(concept_info, dict) else concept_info

    known = [
        (t["topic"] if isinstance(t, dict) else t)
        for t in ctx.teaching_order[:index]
    ]

    explanation = explainer.explain_concept(concept, known)
    concept_id = concept.lower().replace(" ", "_")

    return {
        "response": f"**{concept}**\n\n{explanation}\n\nDoes this make sense?",
        "type": "explanation",
        "session_update": {
            "explained_current": True,
        },
        "turn_data": {
            "concepts": [concept_id],
            "explanation": explanation,
        },
    }


def _ask_synthesis_or_next(ctx: SessionContext) -> dict:
    """After user confirms understanding, ask synthesis Q or move on."""
    idx = ctx.current_index
    teaching_order = ctx.teaching_order

    concept_info = teaching_order[idx]
    concept = concept_info["topic"] if isinstance(concept_info, dict) else concept_info
    concept_id = concept.lower().replace(" ", "_")

    # Get prerequisites (last 2-3 learned concepts)
    prerequisites = [
        (teaching_order[i]["topic"] if isinstance(teaching_order[i], dict) else teaching_order[i])
        for i in range(max(0, idx - 2), idx + 1)
    ]

    # For the very first concept with no prereqs, just move on
    if idx == 0 and len(prerequisites) <= 1:
        cache.track_mastery(concept, "First concept — basic understanding confirmed", "")
        new_index = idx + 1

        if new_index >= len(teaching_order):
            return _learning_complete(ctx.target_topic, new_index, teaching_order)

        # Explain next concept
        next_info = teaching_order[new_index]
        next_concept = next_info["topic"] if isinstance(next_info, dict) else next_info
        known = [(t["topic"] if isinstance(t, dict) else t) for t in teaching_order[:new_index]]
        explanation = explainer.explain_concept(next_concept, known)
        next_concept_id = next_concept.lower().replace(" ", "_")

        return {
            "response": f"✅ **{concept}** — got it!\n\n---\n\n**{next_concept}**\n\n{explanation}\n\nDoes this make sense?",
            "type": "explanation",
            "session_update": {
                "current_index": new_index,
                "explained_current": True,
                "waiting_for_synthesis": False,
            },
            "turn_data": {
                "concepts": [concept_id, next_concept_id],
                "explanation": explanation,
                "correct": True,
            },
        }

    # Ask synthesis question
    question = synthesis.generate_synthesis_question(
        concept, prerequisites, config.SYNTHESIS_DIFFICULTY,
    )

    return {
        "response": f"Now let's test your understanding of **{concept}**.\n\n{question}\n\nTake your time — explain your reasoning!",
        "type": "synthesis_question",
        "session_update": {
            "waiting_for_synthesis": True,
            "current_question": question,
            "attempt_count": 0,
        },
        "turn_data": {
            "concepts": [concept_id],
            "checkQuestion": question,
        },
    }


def _handle_synthesis_answer(answer: str, ctx: SessionContext) -> dict:
    """Validate user's synthesis answer."""
    idx = ctx.current_index
    teaching_order = ctx.teaching_order

    concept_info = teaching_order[idx]
    concept = concept_info["topic"] if isinstance(concept_info, dict) else concept_info
    concept_id = concept.lower().replace(" ", "_")

    prerequisites = [
        (teaching_order[i]["topic"] if isinstance(teaching_order[i], dict) else teaching_order[i])
        for i in range(max(0, idx - 2), idx + 1)
    ]

    result = validator.validate_answer(ctx.current_question, answer, prerequisites)
    attempt_count = ctx.attempt_count + 1

    if result["passed"]:
        # ✅ Passed — record mastery, move on
        cache.track_mastery(concept, answer[:500], result.get("insight", ""))
        new_index = idx + 1

        response = f"**Excellent!** {result['feedback']}\n\n✅ You've mastered **{concept}** (Score: {result['score']}/100)\n\n"

        if result.get("insight"):
            response += f"💡 Key insight: *{result['insight']}*\n\n"

        session_update = {
            "waiting_for_synthesis": False,
            "current_index": new_index,
            "explained_current": False,
            "attempt_count": 0,
        }

        turn_data = {
            "concepts": [concept_id],
            "userAnswer": answer[:500],
            "correct": True,
            "checkQuestion": ctx.current_question,
        }

        if new_index >= len(teaching_order):
            complete = _learning_complete(ctx.target_topic, new_index, teaching_order)
            response += complete["response"]
            session_update.update(complete.get("session_update", {}))
            return {
                "response": response,
                "type": "feedback",
                "data": {"passed": True, "score": result["score"]},
                "session_update": session_update,
                "turn_data": turn_data,
            }

        # Explain next concept
        response += "---\n\n"
        next_info = teaching_order[new_index]
        next_concept = next_info["topic"] if isinstance(next_info, dict) else next_info
        known = [(t["topic"] if isinstance(t, dict) else t) for t in teaching_order[:new_index]]
        explanation = explainer.explain_concept(next_concept, known)
        session_update["explained_current"] = True
        response += f"**{next_concept}**\n\n{explanation}\n\nDoes this make sense?"

        next_concept_id = next_concept.lower().replace(" ", "_")
        turn_data["concepts"].append(next_concept_id)
        turn_data["explanation"] = explanation

        return {
            "response": response,
            "type": "feedback",
            "data": {"passed": True, "score": result["score"]},
            "session_update": session_update,
            "turn_data": turn_data,
        }

    else:
        # ❌ Failed
        turn_data = {
            "concepts": [concept_id],
            "userAnswer": answer[:500],
            "correct": False,
            "checkQuestion": ctx.current_question,
        }

        if attempt_count >= config.SYNTHESIS_MAX_ATTEMPTS:
            # Too many attempts — explain and move on
            new_index = idx + 1
            response = f"{result['feedback']}\n\nLet me explain the key connections:\n\n"

            if result["missing"]:
                from modules.llm_client import call_llm
                explanation = call_llm(
                    f"Briefly explain how {', '.join(result['missing'])} connect in the context of {concept}. "
                    f"Prerequisites: {', '.join(prerequisites)}. 3-4 sentences max."
                )
                response += explanation + "\n\n"

            response += "Let's move forward — we can revisit this later.\n\n"

            session_update = {
                "waiting_for_synthesis": False,
                "current_index": new_index,
                "explained_current": False,
                "attempt_count": 0,
            }

            if new_index < len(teaching_order):
                response += "---\n\n"
                next_info = teaching_order[new_index]
                next_concept = next_info["topic"] if isinstance(next_info, dict) else next_info
                known = [(t["topic"] if isinstance(t, dict) else t) for t in teaching_order[:new_index]]
                expl = explainer.explain_concept(next_concept, known)
                session_update["explained_current"] = True
                response += f"**{next_concept}**\n\n{expl}\n\nDoes this make sense?"

            return {
                "response": response,
                "type": "feedback",
                "data": {"passed": False, "score": result["score"]},
                "session_update": session_update,
                "turn_data": turn_data,
            }
        else:
            # Give a hint
            hint = ""
            if result["missing"]:
                hint = validator.generate_hint(result["missing"], prerequisites)

            remaining = config.SYNTHESIS_MAX_ATTEMPTS - attempt_count
            response = (
                f"{result['feedback']}\n\n"
                f"💡 **Hint:** {hint}\n\n"
                f"Try again! ({remaining} attempt{'s' if remaining != 1 else ''} remaining)"
            )

            return {
                "response": response,
                "type": "feedback",
                "data": {"passed": False, "score": result["score"]},
                "session_update": {
                    "attempt_count": attempt_count,
                },
                "turn_data": turn_data,
            }


def _learning_complete(target_topic: str, current_index: int, teaching_order: list) -> dict:
    """All concepts mastered!"""
    return {
        "response": (
            f"🎉 **Amazing work!** You've mastered all the building blocks for **{target_topic}**!\n\n"
            f"Now for the final challenge — explain **{target_topic}** in your own words.\n\n"
            f"**Requirements:**\n"
            f"- Use at least 3 concepts from your learning path\n"
            f"- Explain how they connect to form {target_topic}\n"
            f"- Give a real-world example\n\n"
            f"This is your chance to put it all together! 🚀"
        ),
        "type": "message",
        "session_update": {
            "current_index": current_index,
            "waiting_for_synthesis": False,
        },
    }
