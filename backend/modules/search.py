"""
Hybrid Search — combines keyword (exact) and vector (semantic) search
across the 3 memory files. Uses sentence-transformers + FAISS for vectors,
with SQLite-cached embeddings to avoid recomputation.
"""

import os
from typing import Any

import numpy as np

from config import config
from modules import cache as cache_mod

# Lazy-load heavy ML libs
_model = None
_index = None
_index_lines: list[str] = []


def _get_model():
    """Lazily load sentence-transformers model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(config.EMBEDDING_MODEL)
    return _model


def _embed(text: str) -> np.ndarray:
    """Get embedding for text, using cache when available."""
    cached = cache_mod.get_cached_embedding(text, config.EMBEDDING_MODEL)
    if cached is not None:
        return np.array(cached)
    model = _get_model()
    emb = model.encode([text])[0]
    cache_mod.store_embedding(text, emb.tolist(), config.EMBEDDING_MODEL)
    return emb


def _build_index(lines: list[str]):
    """Build FAISS index from memory lines."""
    global _index, _index_lines
    import faiss

    if not lines:
        _index = None
        _index_lines = []
        return

    embeddings = np.array([_embed(line) for line in lines], dtype="float32")
    dimension = embeddings.shape[1]
    _index = faiss.IndexFlatL2(dimension)
    _index.add(embeddings)
    _index_lines = lines


# ── Exact (keyword) search ─────────────────────────────────────────────

def exact_search(query: str, top_k: int = 3) -> list[dict]:
    """Keyword-based search across all 3 memory files."""
    keywords = [w.lower() for w in query.split() if len(w) > 2]
    if not keywords:
        return []

    results: list[dict] = []
    for fname in ("conversation.md", "daily.md", "memory.md"):
        fpath = os.path.join(config.MEMORY_DIR, fname)
        if not os.path.exists(fpath):
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            lines = f.read().split("\n")

        for i, line in enumerate(lines):
            lower = line.lower()
            matched = sum(1 for kw in keywords if kw in lower)
            if matched > 0:
                ctx_start = max(0, i - 2)
                ctx_end = min(len(lines), i + 3)
                context = "\n".join(lines[ctx_start:ctx_end])
                results.append({
                    "file": fname,
                    "line": i + 1,
                    "content": context,
                    "type": "exact",
                    "score": matched / len(keywords),
                })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]


# ── Vector (semantic) search ───────────────────────────────────────────

def vector_search(query: str, top_k: int = 5) -> list[dict]:
    """Semantic similarity search over memory.md."""
    # Read + chunk memory
    mem_path = os.path.join(config.MEMORY_DIR, "memory.md")
    if not os.path.exists(mem_path):
        return []
    with open(mem_path, "r", encoding="utf-8") as f:
        raw = f.read()

    lines = [l.strip() for l in raw.split("\n") if l.strip() and len(l.strip()) > 5]
    if not lines:
        return []

    # Rebuild index if content changed
    global _index_lines
    if lines != _index_lines:
        _build_index(lines)

    if _index is None:
        return []

    query_emb = _embed(query).astype("float32").reshape(1, -1)
    k = min(top_k, len(_index_lines))
    distances, indices = _index.search(query_emb, k)

    results: list[dict] = []
    for i, idx in enumerate(indices[0]):
        if idx < len(_index_lines):
            score = 1 / (1 + distances[0][i])
            results.append({
                "file": "memory.md",
                "content": _index_lines[idx],
                "type": "semantic",
                "score": float(score),
            })
    return results


# ── Hybrid combine ─────────────────────────────────────────────────────

def search(query: str, top_k: int = 8) -> list[dict]:
    """Combine exact + vector search, deduplicate, and rank."""
    results: list[dict] = []

    # Exact search (fast, high precision)
    exact = exact_search(query, top_k=config.TOP_K_EXACT)
    results.extend(exact)

    # Vector search (semantic)
    try:
        vec = vector_search(query, top_k=config.TOP_K_VECTOR)
        seen = {r["content"][:80] for r in results}
        for v in vec:
            if v["content"][:80] not in seen:
                results.append(v)
                seen.add(v["content"][:80])
    except Exception as e:
        print(f"[SEARCH] Vector search failed (may need model download): {e}")

    # Rank: exact first, then by score
    results.sort(
        key=lambda r: (r["type"] == "exact", r["score"]),
        reverse=True,
    )
    return results[:top_k]
