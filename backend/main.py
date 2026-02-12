"""
Learning Chatbot — FastAPI Backend
Serves the chat API and static frontend files.
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
from modules import memory_manager as mem
from modules import cache
from modules import prerequisite as prereq_mod
from modules import explainer
from modules import synthesis
from modules import validator
from modules import search


# ── Pydantic models ────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str

class StartLearningRequest(BaseModel):
    topic: str

class ChatResponse(BaseModel):
    response: str
    type: str  # "message" | "explanation" | "synthesis_question" | "feedback" | "tree"
    data: Optional[dict] = None


# ── Application state ──────────────────────────────────────────────────

STATE_FILE = os.path.join(config.MEMORY_DIR, "state.json")

class LearningState:
    """Tracks the current learning session — persists to disk."""

    def __init__(self):
        self.tree: dict | None = None
        self.teaching_order: list[dict] = []
        self.current_index: int = 0
        self.waiting_for_synthesis: bool = False
        self.current_question: str = ""
        self.synthesis_start_time: float = 0
        self.attempt_count: int = 0
        self.target_topic: str = ""
        self.explained_current: bool = False
        self.chat_history: list[dict] = []  # [{role, content, type}]

    def reset(self):
        self.tree = None
        self.teaching_order = []
        self.current_index = 0
        self.waiting_for_synthesis = False
        self.current_question = ""
        self.synthesis_start_time = 0
        self.attempt_count = 0
        self.target_topic = ""
        self.explained_current = False
        self.chat_history = []
        self.save()

    def save(self):
        """Persist state to disk so it survives server restarts and page reloads."""
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            data = {
                "tree": self.tree,
                "teaching_order": self.teaching_order,
                "current_index": self.current_index,
                "waiting_for_synthesis": self.waiting_for_synthesis,
                "current_question": self.current_question,
                "synthesis_start_time": self.synthesis_start_time,
                "attempt_count": self.attempt_count,
                "target_topic": self.target_topic,
                "explained_current": self.explained_current,
                "chat_history": self.chat_history[-100:],  # keep last 100 messages
            }
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] Could not save state: {e}")

    def load(self):
        """Load state from disk."""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.tree = data.get("tree")
                self.teaching_order = data.get("teaching_order", [])
                self.current_index = data.get("current_index", 0)
                self.waiting_for_synthesis = data.get("waiting_for_synthesis", False)
                self.current_question = data.get("current_question", "")
                self.synthesis_start_time = data.get("synthesis_start_time", 0)
                self.attempt_count = data.get("attempt_count", 0)
                self.target_topic = data.get("target_topic", "")
                self.explained_current = data.get("explained_current", False)
                self.chat_history = data.get("chat_history", [])
                print(f"[INFO] Loaded state: topic={self.target_topic}, {len(self.chat_history)} messages")
        except Exception as e:
            print(f"[WARN] Could not load state: {e}")

    def add_message(self, role: str, content: str, msg_type: str = "message"):
        """Add a message to chat history and save."""
        self.chat_history.append({
            "role": role,
            "content": content,
            "type": msg_type,
            "time": datetime.now().strftime("%H:%M"),
        })
        self.save()


state = LearningState()


# ── Lifespan ───────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    mem.ensure_files()
    state.load()  # restore previous session
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
    """Main chat endpoint — handles all user messages."""
    user_msg = req.message.strip()
    if not user_msg:
        return {"response": "Please type something!", "type": "message"}

    # Log user message
    state.add_message("user", user_msg)
    mem.log_conversation("User", user_msg)

    # If waiting for synthesis answer → validate it
    if state.waiting_for_synthesis:
        result = _handle_synthesis_answer(user_msg)
        state.add_message("bot", result["response"], result["type"])
        mem.log_conversation("Bot", result["response"])
        return result

    # If we have a teaching flow going and haven't explained yet
    if state.tree and not state.explained_current and state.current_index < len(state.teaching_order):
        result = _explain_current_concept()
        state.add_message("bot", result["response"], result["type"])
        mem.log_conversation("Bot", result["response"])
        return result

    # Check if this is a learning request
    if _is_learning_request(user_msg):
        topic = _extract_topic(user_msg)
        result = _start_learning(topic)
        state.add_message("bot", result["response"], result["type"])
        mem.log_conversation("Bot", result["response"])
        return result

    # General conversation or "yes/ready/next" to proceed
    if state.tree and state.current_index < len(state.teaching_order):
        lower = user_msg.lower()
        if any(w in lower for w in ["yes", "ready", "next", "continue", "ok", "sure", "yeah", "got it", "makes sense"]):
            result = _ask_synthesis_or_next()
            state.add_message("bot", result["response"], result["type"])
            mem.log_conversation("Bot", result["response"])
            return result

    # Fallback: general response
    from modules.llm_client import call_llm
    context = mem.read("memory.md")[:500]
    response = call_llm(
        user_msg,
        system_prompt=(
            "You are a friendly learning assistant. "
            "If the user wants to learn a topic, tell them to type 'Learn: [topic name]'. "
            f"User context:\n{context}"
        ),
    )
    state.add_message("bot", response)
    mem.log_conversation("Bot", response)
    return {"response": response, "type": "message"}


@app.post("/api/start-learning")
async def start_learning(req: StartLearningRequest) -> dict:
    """Build prerequisite tree and start teaching."""
    result = _start_learning(req.topic)
    return result


@app.get("/api/tree")
async def get_tree() -> dict:
    """Return the current prerequisite tree."""
    if state.tree is None:
        return {"tree": None, "teaching_order": [], "current_index": 0}

    mastered = {c["concept"].lower() for c in cache.get_mastered_concepts()}
    pruned = prereq_mod.prune_mastered(state.tree, mastered)
    return {
        "tree": pruned,
        "teaching_order": [t["topic"] for t in state.teaching_order],
        "current_index": state.current_index,
        "target_topic": state.target_topic,
    }


@app.get("/api/progress")
async def get_progress() -> dict:
    """Return learning progress."""
    mastered = cache.get_mastered_concepts()
    total = len(state.teaching_order) if state.teaching_order else 0
    return {
        "mastered": mastered,
        "mastered_count": len(mastered),
        "total_concepts": total,
        "current_index": state.current_index,
        "current_concept": (
            state.teaching_order[state.current_index]["topic"]
            if state.teaching_order and state.current_index < len(state.teaching_order)
            else None
        ),
        "target_topic": state.target_topic,
        "waiting_for_synthesis": state.waiting_for_synthesis,
    }


@app.get("/api/history")
async def get_history() -> dict:
    """Return chat history for rendering on page load."""
    return {
        "messages": state.chat_history,
        "target_topic": state.target_topic,
    }


@app.get("/api/memory/search")
async def search_memory(q: str) -> dict:
    """Search across memory files."""
    results = search.search(q)
    return {"query": q, "results": results}


@app.get("/api/memory")
async def get_memory() -> dict:
    """Return raw memory file contents."""
    return mem.read_all()


@app.post("/api/reset")
async def reset_session() -> dict:
    """Reset the current learning session."""
    state.reset()
    mem.reset_conversation()
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
    # Remove trailing ? or .
    return topic.rstrip("?.!").strip()


def _start_learning(topic: str) -> dict:
    """Build tree, set up teaching flow, teach first concept."""
    state.reset()
    state.target_topic = topic

    mem.log_daily(f"User wants to learn: {topic}")

    # Build prerequisite tree
    tree = prereq_mod.build_prerequisite_tree(topic, max_depth=config.MAX_TREE_DEPTH)
    state.tree = tree

    # Remove already mastered concepts from teaching order
    mastered_set = {c["concept"].lower() for c in cache.get_mastered_concepts()}
    full_order = prereq_mod.tree_to_teaching_order(tree)
    state.teaching_order = [t for t in full_order if t["topic"].lower() not in mastered_set]

    if not state.teaching_order:
        return {
            "response": f"🎉 You've already mastered all prerequisites for **{topic}**! Ask me anything about it.",
            "type": "message",
            "data": {"tree": tree},
        }

    tree_text = prereq_mod.tree_to_text(tree)
    mem.update_progress_tree(tree_text)

    # Build response
    total = len(state.teaching_order)
    first_topic = state.teaching_order[0]["topic"]
    response = (
        f"Great! Let me break down **{topic}** into building blocks.\n\n"
        f"```\n{tree_text}\n```\n\n"
        f"We'll learn **{total} concepts**, starting with the simplest: **{first_topic}**.\n\n"
    )

    # Explain the first concept immediately
    explanation = _do_explain(0)
    response += explanation + "\n\nDoes this make sense? Ready to continue?"
    state.explained_current = True

    mem.log_daily(f"Built tree for {topic} — {total} concepts")
    state.save()
    return {
        "response": response,
        "type": "tree",
        "data": {"tree": tree, "teaching_order": [t["topic"] for t in state.teaching_order]},
    }


def _explain_current_concept() -> dict:
    """Explain the concept at current_index."""
    explanation = _do_explain(state.current_index)
    state.explained_current = True
    state.save()
    return {
        "response": explanation + "\n\nDoes this make sense?",
        "type": "explanation",
    }


def _do_explain(index: int) -> str:
    """Generate explanation text for a concept."""
    concept_info = state.teaching_order[index]
    concept = concept_info["topic"]

    # What does the user already know?
    known = [
        state.teaching_order[i]["topic"]
        for i in range(index)
    ]

    explanation = explainer.explain_concept(concept, known)
    mem.log_daily(f"Explained: {concept}")
    return f"**{concept}**\n\n{explanation}"


def _ask_synthesis_or_next() -> dict:
    """After user confirms understanding, ask synthesis Q or move on."""
    idx = state.current_index

    # Get prerequisites (last 2-3 learned concepts)
    prerequisites = [
        state.teaching_order[i]["topic"]
        for i in range(max(0, idx - 2), idx + 1)
    ]

    # For the very first concept with no prereqs, just move on
    if idx == 0 and len(prerequisites) <= 1:
        # Mark as understood and move to next
        concept = state.teaching_order[idx]["topic"]
        cache.track_mastery(concept, "First concept — basic understanding confirmed", "")
        mem.update_mastery(concept, "Basic understanding confirmed", "First concept in path")
        state.current_index += 1
        state.explained_current = False

        if state.current_index >= len(state.teaching_order):
            state.save()
            return _learning_complete()

        # Explain next concept
        explanation = _do_explain(state.current_index)
        state.explained_current = True
        state.save()
        return {
            "response": f"✅ **{concept}** — got it!\n\n---\n\n{explanation}\n\nDoes this make sense?",
            "type": "explanation",
        }

    # Ask synthesis question
    concept = state.teaching_order[idx]["topic"]
    question = synthesis.generate_synthesis_question(
        concept, prerequisites, config.SYNTHESIS_DIFFICULTY,
    )

    state.waiting_for_synthesis = True
    state.current_question = question
    state.synthesis_start_time = time.time()
    state.attempt_count = 0

    mem.log_daily(f"Synthesis Q for: {concept}")
    state.save()
    return {
        "response": f"Now let's test your understanding of **{concept}**.\n\n{question}\n\nTake your time — explain your reasoning!",
        "type": "synthesis_question",
    }


def _handle_synthesis_answer(answer: str) -> dict:
    """Validate user's synthesis answer."""
    idx = state.current_index
    concept = state.teaching_order[idx]["topic"]
    prerequisites = [
        state.teaching_order[i]["topic"]
        for i in range(max(0, idx - 2), idx + 1)
    ]

    result = validator.validate_answer(state.current_question, answer, prerequisites)
    state.attempt_count += 1

    if result["passed"]:
        # ✅ Passed — record mastery, move on
        time_spent = int(time.time() - state.synthesis_start_time)
        cache.track_mastery(concept, answer[:500], result.get("insight", ""), time_spent)
        mem.update_mastery(concept, answer[:200], result.get("insight", ""))
        mem.log_daily(f"MASTERED: {concept} (score: {result['score']}, time: {time_spent}s)")

        state.waiting_for_synthesis = False
        state.current_index += 1
        state.explained_current = False

        response = f"**Excellent!** {result['feedback']}\n\n✅ You've mastered **{concept}** (Score: {result['score']}/100)\n\n"

        if result.get("insight"):
            response += f"💡 Key insight: *{result['insight']}*\n\n"

        if state.current_index >= len(state.teaching_order):
            response += _learning_complete()["response"]
            state.save()
            return {"response": response, "type": "feedback", "data": {"passed": True, "score": result["score"]}}

        # Explain next concept
        response += "---\n\n"
        explanation = _do_explain(state.current_index)
        state.explained_current = True
        response += explanation + "\n\nDoes this make sense?"

        state.save()
        return {"response": response, "type": "feedback", "data": {"passed": True, "score": result["score"]}}

    else:
        # ❌ Failed
        if state.attempt_count >= config.SYNTHESIS_MAX_ATTEMPTS:
            # Too many attempts — explain and move on
            state.waiting_for_synthesis = False
            state.current_index += 1
            state.explained_current = False

            response = (
                f"{result['feedback']}\n\n"
                f"Let me explain the key connections:\n\n"
            )
            # Get missing connections explained
            if result["missing"]:
                from modules.llm_client import call_llm
                explanation = call_llm(
                    f"Briefly explain how {', '.join(result['missing'])} connect in the context of {concept}. "
                    f"Prerequisites: {', '.join(prerequisites)}. 3-4 sentences max."
                )
                response += explanation + "\n\n"

            response += "Let's move forward — we can revisit this later.\n\n"

            if state.current_index < len(state.teaching_order):
                response += "---\n\n"
                expl = _do_explain(state.current_index)
                state.explained_current = True
                response += expl + "\n\nDoes this make sense?"

            state.save()
            return {"response": response, "type": "feedback", "data": {"passed": False, "score": result["score"]}}
        else:
            # Give a hint
            hint = ""
            if result["missing"]:
                hint = validator.generate_hint(result["missing"], prerequisites)

            remaining = config.SYNTHESIS_MAX_ATTEMPTS - state.attempt_count
            response = (
                f"{result['feedback']}\n\n"
                f"💡 **Hint:** {hint}\n\n"
                f"Try again! ({remaining} attempt{'s' if remaining != 1 else ''} remaining)"
            )
            state.save()
            return {"response": response, "type": "feedback", "data": {"passed": False, "score": result["score"]}}


def _learning_complete() -> dict:
    """All concepts mastered!"""
    target = state.target_topic
    mem.log_daily(f"🎉 COMPLETED all prerequisites for: {target}")

    return {
        "response": (
            f"🎉 **Amazing work!** You've mastered all the building blocks for **{target}**!\n\n"
            f"Now for the final challenge — explain **{target}** in your own words.\n\n"
            f"**Requirements:**\n"
            f"- Use at least 3 concepts from your learning path\n"
            f"- Explain how they connect to form {target}\n"
            f"- Give a real-world example\n\n"
            f"This is your chance to put it all together! 🚀"
        ),
        "type": "message",
    }
