"""Task 8 — PageIndex vectorless retrieval fallback.

This adapter uses PageIndex's documented REST endpoints because the current
Python SDK does not expose the legacy raw-node retrieval flow required by this
task's return schema.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Iterable

import requests
from dotenv import load_dotenv

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "").strip()
PAGEINDEX_API_URL = os.getenv("PAGEINDEX_API_URL", "https://api.pageindex.ai").rstrip("/")
PAGEINDEX_DOCUMENT_IDS = os.getenv("PAGEINDEX_DOCUMENT_IDS", os.getenv("PAGEINDEX_DOC_IDS", ""))
LANDING_LEGAL_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"
REQUEST_TIMEOUT = float(os.getenv("PAGEINDEX_REQUEST_TIMEOUT", "30"))
POLL_INTERVAL = float(os.getenv("PAGEINDEX_POLL_INTERVAL", "1"))
POLL_TIMEOUT = float(os.getenv("PAGEINDEX_POLL_TIMEOUT", "60"))
MAX_DOCUMENTS = int(os.getenv("PAGEINDEX_MAX_DOCUMENTS", "5"))


def _headers() -> dict[str, str]:
    return {"api_key": PAGEINDEX_API_KEY}


def _validate_query(query: str, top_k: int) -> str:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    return query.strip()


def _configured_doc_ids() -> list[str]:
    return [item.strip() for item in PAGEINDEX_DOCUMENT_IDS.split(",") if item.strip()]


def upload_documents() -> list[dict]:
    """Upload source PDFs and return their PageIndex document IDs.

    PageIndex's document endpoint accepts PDFs. The repository's original legal
    PDFs are uploaded directly so structure is preserved; the returned IDs can
    be stored in ``PAGEINDEX_DOCUMENT_IDS`` (comma-separated) for retrieval.
    """
    if not PAGEINDEX_API_KEY:
        raise RuntimeError("PAGEINDEX_API_KEY is not configured")

    uploaded: list[dict] = []
    with requests.Session() as session:
        for pdf_path in sorted(LANDING_LEGAL_DIR.glob("*.pdf")):
            with pdf_path.open("rb") as file_handle:
                response = session.post(
                    f"{PAGEINDEX_API_URL}/doc/",
                    headers=_headers(),
                    files={"file": (pdf_path.name, file_handle, "application/pdf")},
                    timeout=REQUEST_TIMEOUT,
                )
            response.raise_for_status()
            payload = response.json()
            doc_id = payload.get("doc_id")
            if not doc_id:
                raise RuntimeError(f"PageIndex upload response has no doc_id for {pdf_path.name}")
            uploaded.append({"path": str(pdf_path), "doc_id": str(doc_id)})
    return uploaded


def _discover_documents(session: requests.Session) -> list[dict]:
    configured = _configured_doc_ids()
    if configured:
        return [{"id": doc_id, "name": doc_id, "status": "completed"} for doc_id in configured]

    response = session.get(
        f"{PAGEINDEX_API_URL}/docs",
        headers=_headers(),
        params={"limit": min(max(MAX_DOCUMENTS, 1), 100), "offset": 0},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    documents = response.json().get("documents", [])
    return [
        doc
        for doc in documents
        if isinstance(doc, dict)
        and (doc.get("id") or doc.get("doc_id"))
        and doc.get("status") == "completed"
    ][:MAX_DOCUMENTS]


def _poll_retrieval(session: requests.Session, retrieval_id: str) -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT
    while True:
        response = session.get(
            f"{PAGEINDEX_API_URL}/retrieval/{retrieval_id}/",
            headers=_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        status = str(payload.get("status", "")).lower()
        if status == "completed":
            return payload
        if status in {"failed", "error", "cancelled"}:
            raise RuntimeError(f"PageIndex retrieval {retrieval_id} ended with status={status}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"PageIndex retrieval {retrieval_id} timed out")
        time.sleep(POLL_INTERVAL)


def _iter_relevant_items(value: Any) -> Iterable[dict]:
    """Flatten current and legacy ``relevant_contents`` response shapes."""
    if isinstance(value, dict):
        if value.get("relevant_content"):
            yield value
        else:
            for nested in value.values():
                yield from _iter_relevant_items(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_relevant_items(nested)


def _parse_retrieval(payload: dict, document: dict) -> list[dict]:
    doc_id = str(document.get("id") or document.get("doc_id") or payload.get("doc_id") or "unknown")
    doc_name = str(document.get("name") or document.get("title") or doc_id)
    parsed: list[dict] = []
    for node in payload.get("retrieved_nodes", []) or []:
        if not isinstance(node, dict):
            continue
        section = node.get("title") or node.get("section_title") or "Unknown section"
        for item in _iter_relevant_items(node.get("relevant_contents", [])):
            content = str(item.get("relevant_content", "")).strip()
            if not content:
                continue
            item_section = item.get("section_title") or section
            parsed.append(
                {
                    "content": content,
                    "score": 0.0,
                    "metadata": {
                        "source": doc_name,
                        "doc_id": doc_id,
                        "section": item_section,
                        "page": item.get("page_index"),
                        "type": "pageindex",
                    },
                    "source": "pageindex",
                }
            )
    return parsed


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Retrieve structural evidence from PageIndex's raw-node API.

    Missing credentials or an empty PageIndex account produce an empty list so
    the caller can fall back to a truthful "cannot verify" answer.
    """
    clean_query = _validate_query(query, top_k)
    if not PAGEINDEX_API_KEY:
        return []

    results: list[dict] = []
    with requests.Session() as session:
        documents = _discover_documents(session)
        for document in documents:
            doc_id = str(document.get("id") or document.get("doc_id"))
            try:
                response = session.post(
                    f"{PAGEINDEX_API_URL}/retrieval/",
                    headers=_headers(),
                    json={"doc_id": doc_id, "query": clean_query, "thinking": False},
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                retrieval_id = response.json().get("retrieval_id")
                if not retrieval_id:
                    continue
                payload = _poll_retrieval(session, str(retrieval_id))
                results.extend(_parse_retrieval(payload, document))
            except (requests.RequestException, RuntimeError, TimeoutError):
                # A single failed document should not discard evidence already
                # retrieved from the remaining documents.
                continue

    for rank, result in enumerate(results, start=1):
        result["score"] = round(1.0 / rank, 6)
    return results[:top_k]


if __name__ == "__main__":
    if not PAGEINDEX_API_KEY:
        print("PAGEINDEX_API_KEY chưa được cấu hình.")
    else:
        for result in pageindex_search("tuition fee payment methods", top_k=3):
            print(f"[{result['score']:.3f}] {result['content'][:100]}...")
