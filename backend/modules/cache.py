"""
SQLite Caching Layer — persists embeddings, prerequisite trees,
synthesis questions, and concept mastery to avoid redundant computation.
"""

import hashlib
import json
import pickle
import sqlite3
import time
from typing import Any, Optional

from config import config


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.CACHE_DB, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


_conn: sqlite3.Connection | None = None


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _connect()
        _create_tables(_conn)
    return _conn


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS embedding_cache (
            text_hash    TEXT PRIMARY KEY,
            embedding    BLOB NOT NULL,
            model_name   TEXT NOT NULL,
            dimension    INTEGER NOT NULL,
            created_at   INTEGER NOT NULL,
            last_accessed INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS prerequisite_cache (
            topic           TEXT PRIMARY KEY,
            tree_json       TEXT NOT NULL,
            depth           INTEGER NOT NULL,
            total_concepts  INTEGER NOT NULL,
            created_at      INTEGER NOT NULL,
            expires_at      INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS synthesis_cache (
            concept        TEXT,
            prerequisites  TEXT,
            question_text  TEXT NOT NULL,
            difficulty     TEXT NOT NULL DEFAULT 'medium',
            times_used     INTEGER DEFAULT 0,
            success_rate   REAL DEFAULT 0.0,
            avg_time_secs  INTEGER DEFAULT 0,
            created_at     INTEGER NOT NULL,
            PRIMARY KEY (concept, prerequisites)
        );

        CREATE TABLE IF NOT EXISTS concept_mastery (
            user_id        TEXT DEFAULT 'default',
            concept        TEXT,
            mastered_at    INTEGER NOT NULL,
            synthesis_answer TEXT,
            insights       TEXT,
            time_to_master INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, concept)
        );

        CREATE INDEX IF NOT EXISTS idx_emb_accessed
            ON embedding_cache(last_accessed);
        """
    )
    conn.commit()


# ── Embedding cache ────────────────────────────────────────────────────

def get_cached_embedding(text: str, model_name: str = "all-MiniLM-L6-v2") -> Optional[Any]:
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    row = _db().execute(
        "SELECT embedding FROM embedding_cache WHERE text_hash=? AND model_name=?",
        (text_hash, model_name),
    ).fetchone()
    if row:
        _db().execute(
            "UPDATE embedding_cache SET last_accessed=? WHERE text_hash=?",
            (int(time.time()), text_hash),
        )
        _db().commit()
        return pickle.loads(row[0])
    return None


def store_embedding(text: str, embedding: Any, model_name: str = "all-MiniLM-L6-v2") -> None:
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    now = int(time.time())
    _db().execute(
        "INSERT OR REPLACE INTO embedding_cache VALUES (?,?,?,?,?,?)",
        (text_hash, pickle.dumps(embedding), model_name, len(embedding), now, now),
    )
    _db().commit()


# ── Prerequisite tree cache ────────────────────────────────────────────

def get_cached_tree(topic: str) -> Optional[dict]:
    row = _db().execute(
        "SELECT tree_json FROM prerequisite_cache WHERE topic=? AND expires_at>?",
        (topic, int(time.time())),
    ).fetchone()
    return json.loads(row[0]) if row else None


def store_tree(topic: str, tree: dict, ttl_days: int = 7) -> None:
    def _count(node: dict) -> int:
        return 1 + sum(_count(c) for c in node.get("children", []))

    def _depth(node: dict, d: int = 0) -> int:
        children = node.get("children", [])
        return d if not children else max(_depth(c, d + 1) for c in children)

    now = int(time.time())
    _db().execute(
        "INSERT OR REPLACE INTO prerequisite_cache VALUES (?,?,?,?,?,?)",
        (topic, json.dumps(tree), _depth(tree), _count(tree), now, now + ttl_days * 86400),
    )
    _db().commit()


# ── Synthesis question cache ───────────────────────────────────────────

def get_cached_synthesis(concept: str, prerequisites: list[str]) -> Optional[str]:
    key = json.dumps(sorted(prerequisites))
    row = _db().execute(
        "SELECT question_text FROM synthesis_cache WHERE concept=? AND prerequisites=?",
        (concept, key),
    ).fetchone()
    return row[0] if row else None


def store_synthesis(concept: str, prerequisites: list[str], question: str, difficulty: str = "medium") -> None:
    key = json.dumps(sorted(prerequisites))
    _db().execute(
        "INSERT OR REPLACE INTO synthesis_cache VALUES (?,?,?,?,?,?,?,?)",
        (concept, key, question, difficulty, 0, 0.0, 0, int(time.time())),
    )
    _db().commit()


# ── Concept mastery ───────────────────────────────────────────────────

def track_mastery(
    concept: str,
    synthesis_answer: str = "",
    insights: str = "",
    time_spent: int = 0,
    user_id: str = "default",
) -> None:
    _db().execute(
        "INSERT OR REPLACE INTO concept_mastery VALUES (?,?,?,?,?,?)",
        (user_id, concept, int(time.time()), synthesis_answer, insights, time_spent),
    )
    _db().commit()


def get_mastered_concepts(user_id: str = "default") -> list[dict]:
    rows = _db().execute(
        "SELECT concept, mastered_at, insights FROM concept_mastery WHERE user_id=?",
        (user_id,),
    ).fetchall()
    return [{"concept": r[0], "mastered_at": r[1], "insights": r[2]} for r in rows]


def is_mastered(concept: str, user_id: str = "default") -> bool:
    row = _db().execute(
        "SELECT 1 FROM concept_mastery WHERE user_id=? AND concept=?",
        (user_id, concept),
    ).fetchone()
    return row is not None
