"""Semantic chunking node.

Algorithm
---------
1.  Split the raw text into sentences.
2.  Embed every sentence via the provided embed function (one batch call).
3.  Compute cosine similarity between consecutive sentence embeddings.
4.  Insert a chunk boundary wherever similarity drops below *breakpoint_threshold*.
5.  Group sentences between boundaries into chunks, respecting min/max size limits.

The windowed embedding approach (embedding a small context window around each
sentence) gives better boundary detection than single-sentence embeddings and is
what libraries such as LangChain's SemanticChunker use internally.
"""
import re
from typing import Callable, List

import numpy as np

from naturallangdata.agents.state import IngestionState


# ── helpers ───────────────────────────────────────────────────────────────────

def _split_sentences(text: str) -> List[str]:
    """Rough sentence splitter; adequate for English prose."""
    raw = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in raw if len(s.strip()) > 10]


def _is_tabular_text(text: str) -> bool:
    return "[TABLE " in text or "Schema for " in text


def _accumulate_chunks(parts: List[str], min_size: int, max_size: int) -> List[str]:
    chunks: List[str] = []
    current = ""

    for part in parts:
        item = part.strip()
        if not item:
            continue

        candidate = f"{current}\n\n{item}".strip() if current else item
        if len(candidate) <= max_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
        if len(item) <= max_size:
            current = item
            continue

        # Hard split oversized blocks without semantic embedding.
        start = 0
        while start < len(item):
            end = min(start + max_size, len(item))
            piece = item[start:end].strip()
            if piece:
                chunks.append(piece)
            start = end
        current = ""

    if current:
        chunks.append(current)

    merged: List[str] = []
    for chunk in chunks:
        if len(chunk) >= min_size or not merged:
            merged.append(chunk)
        else:
            merged[-1] = (merged[-1] + "\n\n" + chunk).strip()
    return [c for c in merged if c]


def _fallback_chunk(text: str, min_size: int, max_size: int) -> List[str]:
    blocks = [b for b in text.split("\n\n") if b.strip()]
    if not blocks:
        blocks = [line for line in text.splitlines() if line.strip()]
    return _accumulate_chunks(blocks, min_size=min_size, max_size=max_size)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _window_embeddings(
    sentence_embeddings: np.ndarray,
    window: int = 2,
) -> np.ndarray:
    """Average a context window around each sentence embedding."""
    n = len(sentence_embeddings)
    result = np.zeros_like(sentence_embeddings)
    for i in range(n):
        lo = max(0, i - window)
        hi = min(n, i + window + 1)
        result[i] = sentence_embeddings[lo:hi].mean(axis=0)
    return result


def semantic_chunk(
    text: str,
    embed_fn: Callable[[List[str]], List[List[float]]],
    breakpoint_threshold: float,
    min_size: int,
    max_size: int,
) -> List[str]:
    # Tabular extracts are already sectioned; skip semantic splitting to avoid
    # expensive sentence-level embedding calls and timeout risk.
    if _is_tabular_text(text):
        return _fallback_chunk(text, min_size=min_size, max_size=max_size)

    sentences = _split_sentences(text)
    if not sentences:
        return []
    if len(sentences) == 1:
        return [text.strip()]

    # Guardrail for very large inputs where sentence-level semantic boundaries
    # can trigger long embedding runs.
    if len(sentences) > 700:
        return _fallback_chunk(text, min_size=min_size, max_size=max_size)

    raw_embeddings = np.array(embed_fn(sentences), dtype=np.float32)
    windowed = _window_embeddings(raw_embeddings)

    similarities = [
        _cosine(windowed[i], windowed[i + 1]) for i in range(len(windowed) - 1)
    ]
    breakpoints = [
        i + 1 for i, sim in enumerate(similarities) if sim < breakpoint_threshold
    ]

    chunks: List[str] = []
    start = 0
    for bp in [*breakpoints, len(sentences)]:
        piece = " ".join(sentences[start:bp]).strip()
        if not piece:
            start = bp
            continue
        # If piece exceeds max_size, force-split by halving the sentence range.
        while len(piece) > max_size:
            mid = (start + bp) // 2
            if mid == start:
                break
            half = " ".join(sentences[start:mid]).strip()
            if len(half) >= min_size:
                chunks.append(half)
            start = mid
            piece = " ".join(sentences[start:bp]).strip()

        if len(piece) >= min_size:
            chunks.append(piece)
        elif chunks:
            chunks[-1] = (chunks[-1] + " " + piece).strip()
        else:
            chunks.append(piece)
        start = bp

    return [c for c in chunks if c]


# ── node factory ──────────────────────────────────────────────────────────────

def make_chunk_text_node(
    embed_fn: Callable[[List[str]], List[List[float]]],
    breakpoint_threshold: float,
    min_size: int,
    max_size: int,
):
    def chunk_text_node(state: IngestionState) -> IngestionState:
        try:
            chunks = semantic_chunk(
                text=state["raw_text"],
                embed_fn=embed_fn,
                breakpoint_threshold=breakpoint_threshold,
                min_size=min_size,
                max_size=max_size,
            )
            if not chunks:
                return {**state, "status": "error", "error": "Semantic chunker produced zero chunks"}
            return {**state, "chunks": chunks, "status": "embedding"}
        except Exception as exc:
            fallback = _fallback_chunk(state.get("raw_text", ""), min_size=min_size, max_size=max_size)
            if fallback:
                return {**state, "chunks": fallback, "status": "embedding"}
            return {**state, "status": "error", "error": f"chunking failed: {exc}"}

    return chunk_text_node
