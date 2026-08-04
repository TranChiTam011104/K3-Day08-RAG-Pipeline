"""Task 5 — dense semantic search and HyDE retrieval.

The module deliberately reuses Task 4's model, collection name and persistence
directory.  Heavy dependencies are imported lazily so the rest of the project
can still be imported while the vector database is being prepared upstream.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv

from .task4_chunking_indexing import CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL

load_dotenv()

HYDE_SYSTEM_PROMPT = (
    "Bạn là trợ lý tra cứu chính sách đại học. Hãy viết một đoạn văn ngắn, "
    "mang phong cách tài liệu chính thức, có khả năng chứa câu trả lời cho câu "
    "hỏi. Không bịa số liệu cụ thể; chỉ dùng thuật ngữ có trong câu hỏi."
)


def _validate_search_input(query: str, top_k: int) -> str:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    return query.strip()


@lru_cache(maxsize=1)
def _get_embedding_model():
    """Load exactly the embedding model configured by Task 4, once per process."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def _get_collection():
    """Open Task 4's persisted Chroma collection without creating an empty one."""
    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(name=COLLECTION_NAME)


def _first_row(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key) or []
    if value and isinstance(value[0], list):
        return value[0]
    return value


def _search_text(search_text: str, top_k: int) -> list[dict]:
    """Embed ``search_text`` and query Chroma using cosine distance."""
    try:
        collection = _get_collection()
        count = int(collection.count())
    except (ImportError, ModuleNotFoundError, ValueError):
        # Task 4 dependencies/database are an upstream prerequisite.  Returning an
        # empty result keeps the public search contract and lets the UI explain the
        # unavailable evidence instead of crashing at import time.
        return []

    if count <= 0:
        return []

    model = _get_embedding_model()
    query_vector = model.encode(search_text, normalize_embeddings=True)
    if hasattr(query_vector, "tolist"):
        query_vector = query_vector.tolist()

    raw = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, count),
        include=["documents", "metadatas", "distances"],
    )
    documents = _first_row(raw, "documents")
    metadatas = _first_row(raw, "metadatas")
    distances = _first_row(raw, "distances")

    results: list[dict] = []
    for index, document in enumerate(documents):
        if not document:
            continue
        distance = float(distances[index]) if index < len(distances) else 1.0
        # Task 4 creates a cosine collection. Chroma returns distance, therefore
        # similarity = 1 - distance. Clamp to the rubric's documented [0, 1].
        score = max(0.0, min(1.0, 1.0 - distance))
        metadata = metadatas[index] if index < len(metadatas) else {}
        results.append(
            {
                "content": str(document),
                "score": round(score, 6),
                "metadata": metadata or {},
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """Return dense-retrieval results sorted by cosine similarity descending."""
    clean_query = _validate_search_input(query, top_k)
    return _search_text(clean_query, top_k)


def _generate_hypothetical_doc(query: str) -> str:
    """Generate a short hypothetical answer for HyDE.

    When no LLM key is configured, the original query is returned.  This keeps
    HyDE opt-in and deterministic in offline development environments.
    """
    clean_query = _validate_search_input(query, 1)
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not openrouter_key and not openai_key:
        return clean_query

    from openai import OpenAI

    if openrouter_key:
        client = OpenAI(
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=30.0,
            max_retries=1,
        )
        model = os.getenv("HYDE_LLM_MODEL", "openai/gpt-4o-mini")
    else:
        client = OpenAI(api_key=openai_key, timeout=30.0, max_retries=1)
        model = os.getenv("HYDE_LLM_MODEL", "gpt-4o-mini")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": HYDE_SYSTEM_PROMPT},
            {"role": "user", "content": clean_query},
        ],
        temperature=0.0,
        max_tokens=220,
    )
    content = response.choices[0].message.content
    return content.strip() if content and content.strip() else clean_query


def hyde_search(
    query: str,
    top_k: int = 10,
    hypothetical_document: str | None = None,
) -> list[dict]:
    """Search with a hypothetical document embedding instead of the raw query."""
    clean_query = _validate_search_input(query, top_k)
    search_text = hypothetical_document or _generate_hypothetical_doc(clean_query)
    if not isinstance(search_text, str) or not search_text.strip():
        search_text = clean_query
    return _search_text(search_text.strip(), top_k)


if __name__ == "__main__":
    for result in semantic_search("what is the tuition fee", top_k=5):
        print(f"[{result['score']:.3f}] {result['content'][:100]}...")
