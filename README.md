# 🧠 LearnBot — First Principles Learning Chatbot

An AI-powered learning chatbot that breaks **any topic** into its prerequisite building blocks, teaches them bottom-up using first principles, and tests understanding with synthesis questions. Built with a hybrid memory system (keyword + semantic search), SQLite caching, and a stateless FastAPI backend.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)
![LLM](https://img.shields.io/badge/LLM-Llama%203.3%2070B-purple)
![FAISS](https://img.shields.io/badge/Search-FAISS%20%2B%20Keyword-orange)

---

## 📋 Table of Contents

- [How It Works](#-how-it-works)
- [Architecture Overview](#-architecture-overview)
- [Memory System](#-memory-system-3-file-architecture)
- [Hybrid Search Engine](#-hybrid-search-engine)
- [Caching Layer](#-caching-layer-sqlite)
- [Teaching Pipeline](#-teaching-pipeline)
- [Setup & Installation](#-setup--installation)
- [Configuration](#-configuration)
- [Project Structure](#-project-structure)

---

## 🔍 How It Works

LearnBot uses a **recall-based learning** approach inspired by first principles thinking:

1. **You ask to learn a topic** (e.g., _"Learn: Neural Networks"_)
2. **The LLM recursively decomposes it** into prerequisite concepts, building a tree
3. **Already-mastered concepts are skipped** (checked via the mastery cache)
4. **Teaching happens bottom-up** — starting from the simplest leaf concepts
5. **After each concept, a synthesis question** forces you to _combine_ what you learned
6. **Your answer is validated** for genuine integration, not just keyword matching
7. **If you fail, you get hints** — if you fail 3 times, the system explains and moves on
8. **Everything is persisted** in markdown memory files and a SQLite cache

```
User: "Learn: Machine Learning"
                │
                ▼
    ┌─ Prerequisite Tree Builder (LLM) ─┐
    │                                    │
    │   Machine Learning                 │
    │   ├─ Statistics                    │
    │   │  ├─ Mean & Median [FACT]       │
    │   │  └─ Standard Deviation         │
    │   ├─ Linear Algebra                │
    │   │  ├─ Vectors [FACT]             │
    │   │  └─ Matrix Multiplication      │
    │   └─ Optimization                  │
    │      └─ Gradient Descent           │
    └────────────────────────────────────┘
                │
                ▼
    Teaching order (bottom-up):
    1. Mean & Median → explain → quiz
    2. Vectors → explain → quiz
    3. Standard Deviation → explain → quiz
    4. Matrix Multiplication → explain → quiz
    5. Gradient Descent → explain → quiz
    6. Statistics → explain → quiz
    7. Linear Algebra → explain → quiz
    8. Optimization → explain → quiz
    9. Machine Learning → final synthesis
```

---

## 🏗 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                 │
│  index.html + Tailwind CSS + Vanilla JS                        │
│  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌────────────────┐  │
│  │ chat.js  │ │ tree.js  │ │sessions.js │ │memory-store.js │  │
│  │ messages │ │ renders  │ │ localStorage│ │ syncs memory   │  │
│  │ & submit │ │ tree UI  │ │ persistence│ │ from backend   │  │
│  └────┬─────┘ └──────────┘ └────────────┘ └────────────────┘  │
│       │  POST /api/chat  {message, session_context}            │
└───────┼─────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                             │
│                                                                 │
│  main.py ─── Stateless API: receives session_context,           │
│              returns session_update                              │
│                                                                 │
│  ┌─────────────────── modules/ ───────────────────────────┐     │
│  │                                                        │     │
│  │  llm_client.py ──── NVIDIA API (OpenAI-compatible)     │     │
│  │       │                                                │     │
│  │       ├──► prerequisite.py ── Recursive tree builder   │     │
│  │       ├──► explainer.py ───── First-principles teach   │     │
│  │       ├──► synthesis.py ───── Synthesis Q generator    │     │
│  │       └──► validator.py ───── Answer checker + hints   │     │
│  │                                                        │     │
│  │  memory_manager.py ── Read/write 3 markdown files      │     │
│  │  search.py ─────────── Hybrid keyword + FAISS search   │     │
│  │  cache.py ──────────── SQLite persistence layer        │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                 │
│  config.py ── Environment-based configuration                   │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DATA LAYER                                  │
│                                                                 │
│  data/memory/                                                   │
│  ├── memory.md ──────── Lifetime knowledge graph                │
│  ├── daily.md ───────── Today's session log                     │
│  ├── conversation.md ── Active chat transcript                  │
│  ├── cache.db ───────── SQLite (embeddings, trees, mastery)     │
│  └── state.json ─────── Session state snapshots                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🗃 Memory System (3-File Architecture)

The memory system uses **three markdown files**, each serving a distinct purpose. This design is inspired by the [OpenClaw memory pattern](https://github.com/openclaw):

### `memory.md` — Lifetime Knowledge Graph

Stores **everything the user has ever learned**, persisted across sessions:

```markdown
# User Knowledge Graph

## User Profile
- Learning style: unknown
- Struggles with: unknown

## Topics Mastered

### Linear Algebra
- Mastered: 2026-02-15 14:30
- Synthesis answer: Vectors are like arrows with direction...
- Key insight: Connected matrix ops to image transformations

## Learning Progress Tree
├─ Machine Learning
│  ├─ Statistics
│  └─ Linear Algebra [MASTERED]

## Synthesis Insights
```

**How it's used:**
- When the user starts learning a new topic, mastered concepts are looked up and **skipped** in the teaching order
- The `## Learning Progress Tree` section is updated whenever a new topic tree is built
- Search queries match against this file for long-term context

### `daily.md` — Session Log

Tracks **today's learning activity**:

```markdown
# Daily Log: 2026-02-15

## Session Goal

## Progress Timeline
### 14:30 — Started learning Machine Learning
### 14:35 — Mastered: Vectors
### 14:42 — Mastered: Mean & Median
```

**How it's used:**
- Timestamped entries are appended as the user progresses
- Reset at the start of each new day/session

### `conversation.md` — Chat Transcript

Raw record of the active conversation with timestamps:

```markdown
# Conversation: 2026-02-15 14:30

[14:30] user: Learn: Machine Learning
[14:30] assistant: Great! Let me break down Machine Learning...
[14:32] user: yes, makes sense
[14:32] assistant: Now let's test your understanding...
```

**How it's used:**
- Enables context-aware search across the current conversation
- Reset when a new chat session starts

### How Memory Files Connect

```
┌─────────────┐     writes to      ┌──────────────┐
│ conversation │ ──────────────────►│  memory.md   │
│     .md      │  (on mastery)     │ (permanent)  │
└─────────────┘                    └──────┬───────┘
                                          │
┌─────────────┐     reads from            │
│  daily.md   │ ◄────────────────────────┘
│ (per-session)│     summarizes
└─────────────┘

All 3 files ──► search.py (queryable via hybrid search)
All 3 files ──► memory_manager.py (read/write/append)
```

---

## 🔎 Hybrid Search Engine

The `search.py` module combines **two search strategies** for maximum recall:

### 1. Exact (Keyword) Search

- Splits the query into keywords (words > 2 characters)
- Scans all 3 memory files line-by-line
- Scores each line by **keyword overlap ratio** (`matched_keywords / total_keywords`)
- Returns surrounding context (2 lines above/below the match)
- Fast, high-precision — great for exact terms

### 2. Vector (Semantic) Search

- Uses the **`all-MiniLM-L6-v2`** sentence-transformer model to embed text
- Builds a **FAISS** (Facebook AI Similarity Search) flat L2 index over `memory.md` lines
- Query embedding is compared against the index using L2 distance
- Score is computed as `1 / (1 + distance)` — closer = higher score
- Embeddings are **cached in SQLite** to avoid recomputation
- The FAISS index is rebuilt only when `memory.md` content changes

### 3. Hybrid Combining

```python
search(query, top_k=8)
├── exact_search(query, top_k=3)     # Fast keyword matches
├── vector_search(query, top_k=5)    # Semantic similarity
├── Deduplicate (by first 80 chars)
├── Rank: exact matches first, then by score
└── Return top_k results
```

Each result contains:
```python
{
    "file": "memory.md",       # Which file the match came from
    "line": 42,                # Line number (exact search only)
    "content": "...",          # The matching content with context
    "type": "exact|semantic",  # Which search found it
    "score": 0.85,             # Relevance score (0-1)
}
```

---

## 💾 Caching Layer (SQLite)

The `cache.py` module uses SQLite (with WAL mode for concurrency) to persist 4 types of data:

| Table | Purpose | Key | TTL |
|---|---|---|---|
| `embedding_cache` | Sentence-transformer embeddings | SHA-256 of text | ∞ (LRU tracked) |
| `prerequisite_cache` | LLM-generated topic trees | Topic name | 7 days |
| `synthesis_cache` | Generated quiz questions | Concept + prereqs | ∞ |
| `concept_mastery` | What the user has mastered | User ID + concept | ∞ |

**Why caching matters:**
- Building a prerequisite tree requires **many LLM calls** (one per node). Caching avoids regeneration.
- Embeddings are expensive to compute. The cache stores them as pickled blobs.
- Synthesis questions can be reused if the same concept/prerequisites combination appears again.
- Mastered concepts are tracked so the learner **never re-learns** what they already know.

---

## 📚 Teaching Pipeline

The teaching flow is orchestrated by `main.py` and uses 4 specialized modules:

### Step 1: Prerequisite Decomposition (`prerequisite.py`)

```
Input: "Machine Learning"
    │
    ▼
LLM Prompt: "Break down Machine Learning into 2-4 prerequisites"
    │
    ▼
Response: "1. Statistics  2. Linear Algebra  3. Optimization"
    │
    ▼
Recurse on each prerequisite (up to depth 5)
    │
    ▼
Stop when LLM says "FACT" (a concept explainable in one sentence)
    │
    ▼
Output: Tree structure with CONCEPT / FACT / LEAF nodes
```

- **Cycle detection**: Tracks visited topics to prevent infinite recursion
- **Cache**: Trees are cached for 7 days after first generation
- **Teaching order**: Post-order traversal produces a bottom-up sequence (leaves first)

### Step 2: First-Principles Explanation (`explainer.py`)

For each concept in the teaching order:
- Tells the LLM what concepts the student **already knows** (previously explained ones)
- Asks for a 5-sentence explanation a 12-year-old could understand
- Must include a **concrete real-world example** and a **"think of it like..."** analogy
- No jargon unless defined in the same sentence

### Step 3: Synthesis Question (`synthesis.py`)

After the user confirms understanding:
- Generates a **scenario-based** question combining 2-3 recent prerequisites
- The question has 2-3 sub-parts probing different angles
- Cannot be answered by **repeating definitions** — requires **reasoning**
- Questions are cached so the same combo doesn't regenerate

### Step 4: Answer Validation (`validator.py`)

The user's answer is scored on 4 criteria (0-100 each):
- **Coverage** — Did they mention all listed prerequisites?
- **Integration** — Did they explain how prerequisites relate?
- **Reasoning** — Logical reasoning, not just facts?
- **Depth** — Nuances, edge cases, "what if" scenarios?

**Pass threshold**: Score ≥ 60

| Outcome | Action |
|---|---|
| ✅ Pass | Record mastery → move to next concept |
| ❌ Fail (attempts remaining) | Generate a targeted hint → let them retry |
| ❌ Fail (max 3 attempts) | Explain the connections → move on |

---

## 🚀 Setup & Installation

### Prerequisites

- **Python 3.10+** installed ([download](https://www.python.org/downloads/))
- **Git** installed ([download](https://git-scm.com/downloads))
- An **NVIDIA API key** from [build.nvidia.com](https://build.nvidia.com/) (free tier available)

### Step 1: Clone the Repository

```bash
git clone https://github.com/Adnan0042N/optimization-project.git
cd optimization-project
```

### Step 2: Create a Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r backend/requirements.txt
```

This installs:
| Package | Purpose |
|---|---|
| `fastapi` | Web framework (API + static file serving) |
| `uvicorn` | ASGI server |
| `openai` | OpenAI-compatible client (used for NVIDIA API) |
| `sentence-transformers` | Local embedding model (`all-MiniLM-L6-v2`) |
| `faiss-cpu` | Vector similarity search (FAISS) |
| `numpy` | Numerical operations |
| `pydantic` | Request/response validation |
| `python-dotenv` | Environment variable loading |

> **Note:** The first run will download the `all-MiniLM-L6-v2` model (~80MB). This only happens once.

### Step 4: Configure Environment Variables

Create a `.env` file inside the `backend/` directory:

```bash
# backend/.env
NVIDIA_API_KEY=your_nvidia_api_key_here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_MODEL=meta/llama-3.3-70b-instruct
EMBEDDING_MODEL=all-MiniLM-L6-v2
MEMORY_DIR=../data/memory
CACHE_DB=../data/memory/cache.db
```

**How to get your NVIDIA API key:**
1. Go to [build.nvidia.com](https://build.nvidia.com/)
2. Sign up / Log in
3. Navigate to any model → click **"Get API Key"**
4. Copy the key (starts with `nvapi-`)

### Step 5: Run the Server

```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Step 6: Open the App

Open your browser and go to:

```
http://localhost:8000
```

You should see the LearnBot UI with a chat interface and sidebar. Type something like **"Learn: Photosynthesis"** to start!

---

## ⚙ Configuration

All configuration lives in `backend/config.py` and can be overridden via `.env`:

| Variable | Default | Description |
|---|---|---|
| `NVIDIA_API_KEY` | _(required)_ | Your NVIDIA API key |
| `NVIDIA_BASE_URL` | `https://integrate.api.nvidia.com/v1` | API endpoint |
| `LLM_MODEL` | `meta/llama-3.3-70b-instruct` | LLM model to use |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model |
| `MEMORY_DIR` | `../data/memory` | Path to memory files |
| `CACHE_DB` | `../data/memory/cache.db` | Path to SQLite cache |
| `MAX_TREE_DEPTH` | `5` | Max recursion depth for prerequisite trees |
| `CACHE_TTL_DAYS` | `7` | How long cached trees remain valid |
| `SYNTHESIS_DIFFICULTY` | `medium` | Quiz difficulty (`easy` / `medium` / `hard`) |
| `SYNTHESIS_MAX_ATTEMPTS` | `3` | Max attempts before auto-advancing |
| `TOP_K_EXACT` | `3` | Max keyword search results |
| `TOP_K_VECTOR` | `5` | Max semantic search results |

---

## 📁 Project Structure

```
optimization-project/
├── backend/
│   ├── main.py                 # FastAPI app, routes, teaching flow orchestration
│   ├── config.py               # Environment-based configuration
│   ├── requirements.txt        # Python dependencies
│   ├── .env                    # API keys & settings (create this yourself)
│   └── modules/
│       ├── __init__.py
│       ├── llm_client.py       # NVIDIA LLM API wrapper (OpenAI-compatible)
│       ├── prerequisite.py     # Recursive topic → prerequisite tree builder
│       ├── explainer.py        # First-principles concept explainer
│       ├── synthesis.py        # Synthesis question generator
│       ├── validator.py        # Answer validation, scoring, hints
│       ├── search.py           # Hybrid keyword + FAISS vector search
│       ├── memory_manager.py   # Read/write/append markdown memory files
│       └── cache.py            # SQLite caching (embeddings, trees, mastery)
│
├── frontend/
│   ├── index.html              # Main UI (Tailwind CSS, dark theme)
│   ├── css/
│   │   └── styles.css          # Custom styles & animations
│   └── js/
│       ├── app.js              # Main app initialization & event handlers
│       ├── chat.js             # Chat message rendering & submission
│       ├── tree.js             # Knowledge tree visualization
│       ├── progress.js         # Progress bar & tracking
│       ├── sessions.js         # Session management (localStorage)
│       └── memory-store.js     # Memory file sync from backend
│
├── data/
│   └── memory/                 # Auto-created on first run
│       ├── memory.md           # Lifetime knowledge graph
│       ├── daily.md            # Today's session log
│       ├── conversation.md     # Active chat transcript
│       ├── cache.db            # SQLite cache database
│       └── state.json          # Session state snapshots
│
└── README.md                   # You are here
```

---

## 🛠 Troubleshooting

| Problem | Solution |
|---|---|
| `NVIDIA API key denied` | Make sure your key starts with `nvapi-` and is valid at [build.nvidia.com](https://build.nvidia.com/) |
| `ModuleNotFoundError` | Run `pip install -r backend/requirements.txt` inside your virtual environment |
| `Port 8000 already in use` | Use `--port 8001` or kill the existing process |
| `Model download hangs` | The first run downloads `all-MiniLM-L6-v2` (~80MB). Ensure internet access. |
| `cache.db locked` | Only one server instance should run at a time. Stop duplicates. |

---

## 📄 License

This project is for educational purposes.
