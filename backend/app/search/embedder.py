"""
Embedding layer.

Priority order:
1. Gemini text-embedding-004  (if GEMINI_API_KEY set)
2. OpenAI text-embedding-3-small  (if OPENAI_API_KEY set)
3. Stub  (SHA-256 hash — deterministic, no API key needed)

The stub guarantees the full pipeline runs with zero config.
Dimension is always settings.embedding_dim (384 by default).
"""
from __future__ import annotations

import hashlib
import math
import os

import numpy as np

from app.config import settings


# ---------------------------------------------------------------------------
# Gemini embeddings
# ---------------------------------------------------------------------------

def _embed_gemini(texts: list[str]) -> list[list[float]]:
    from google import genai

    key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
    client = genai.Client(api_key=key)

    result = []
    for text in texts:
        response = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
        )
        result.append(response.embeddings[0].values)
    return result


# ---------------------------------------------------------------------------
# OpenAI embeddings
# ---------------------------------------------------------------------------

def _embed_openai(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key or os.environ.get("OPENAI_API_KEY", ""))
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
        dimensions=settings.embedding_dim,
    )
    return [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]


# ---------------------------------------------------------------------------
# Stub (offline / no key)
# ---------------------------------------------------------------------------

def _embed_stub(texts: list[str]) -> list[list[float]]:
    """
    Deterministic pseudo-embedding via SHA-256.
    Not semantically meaningful — for offline/test use only.
    """
    dim = settings.embedding_dim
    result = []
    for text in texts:
        seeds = [
            hashlib.sha256(f"{i}:{text}".encode("utf-8")).digest()
            for i in range(math.ceil(dim * 4 / 32))
        ]
        raw = b"".join(seeds)[: dim * 4]
        arr = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)[:dim]
        arr = (arr / 127.5) - 1.0
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr /= norm
        else:
            arr = np.ones(dim, dtype=np.float32) / math.sqrt(dim)
        result.append(arr.tolist())
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_embedding_provider() -> str:
    """Return which provider will be used: 'gemini', 'openai', or 'stub'."""
    if settings.gemini_api_key or os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if settings.openai_api_key or os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "stub"


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts. Returns float vectors of length embedding_dim."""
    if not texts:
        return []

    provider = get_embedding_provider()

    if provider == "gemini":
        try:
            return _embed_gemini(texts)
        except Exception:
            pass  # fall through

    if provider == "openai":
        try:
            return _embed_openai(texts)
        except Exception:
            pass  # fall through

    return _embed_stub(texts)


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
