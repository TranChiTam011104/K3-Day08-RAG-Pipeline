"""Task 7 — Reranking Module.

Đã implement cả 3 phương pháp, mặc định dùng **RRF**:
    - RRF (Reciprocal Rank Fusion) — gộp nhiều ranker, không cần API key, không cần model
    - MMR (Maximal Marginal Relevance) — giảm trùng lặp, tăng diversity
    - Cross-encoder — Jina Reranker API (nếu có JINA_API_KEY) hoặc degrade về RRF

Vì sao chọn RRF làm mặc định:
    1. Không cần API key / không tốn quota / chạy offline → cả nhóm dùng được ngay.
    2. Semantic score (cosine, thang [0,1]) và BM25 score (thang không chặn trên, có thể
       > 10) KHÔNG cùng đơn vị. RRF chỉ dùng THỨ HẠNG nên miễn nhiễm với việc 2 ranker
       có thang điểm khác nhau.
    3. Corpus của nhóm chỉ ~28 chunk → điểm số nhiễu, thứ hạng ổn định hơn giá trị tuyệt
       đối.

⚠️ Lưu ý quan trọng về RRF (dùng lại ở Task 9): điểm RRF fused CHỈ phụ thuộc thứ hạng,
không phải độ tương đồng thật. Top-1 sau khi fuse luôn xấp xỉ 1/(k+1) ≈ 0.0164 (k=60),
bất kể nội dung đó có thật sự liên quan hay không. ĐỪNG dùng điểm RRF để quyết định
fallback ở Task 9 — hãy dùng `original_score` (cosine gốc) mà module này giữ lại.
"""

from __future__ import annotations

import math
import os
import sys
from typing import Any

from dotenv import load_dotenv

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

JINA_API_KEY = os.getenv("JINA_API_KEY", "")
JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"
JINA_MODEL = "jina-reranker-v2-base-multilingual"

# k=60 theo paper gốc Cormack et al. 2009 (TREC). k lớn "làm phẳng" chênh lệch
# giữa các hạng đầu — ưu tiên sự ĐỒNG THUẬN giữa dense và sparse.
RRF_K = 60


# =============================================================================
# Helpers
# =============================================================================

def _fuse_key(content: str) -> str:
    """Khoá gộp giữa các ranked list.

    Chuẩn hoá khoảng trắng để cùng chunk đi qua ChromaDB và BM25 không bị coi
    là 2 tài liệu khác nhau do lệch whitespace.
    """
    return " ".join(content.split())


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Tính cosine similarity giữa hai vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _group_by_retriever(candidates: list[dict]) -> list[list[dict]]:
    """Tách danh sách phẳng thành nhiều ranked list theo trường 'retriever'."""
    groups: dict[str, list[dict]] = {}
    for item in candidates:
        name = item.get("retriever") or item.get("source") or "_default"
        groups.setdefault(name, []).append(item)
    if len(groups) < 2:
        return [list(candidates)]
    return list(groups.values())


# =============================================================================
# RRF — Reciprocal Rank Fusion (phương pháp chính)
# =============================================================================

def rerank_rrf(
    ranked_lists: list[list[dict[str, Any]]],
    top_k: int = 5,
    k: int = RRF_K,
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion — gộp kết quả từ nhiều ranker.

    RRF(d) = Σ 1 / (k + rank_r(d))

    Args:
        ranked_lists: Danh sách các ranked result list (mỗi list từ 1 ranker).
        top_k: Số lượng kết quả cuối cùng.
        k: Smoothing constant (default=60).

    Returns:
        List of top_k candidates sorted by RRF score descending. Mỗi item có thêm:
            'score'          — điểm RRF (dùng để sắp xếp)
            'original_score' — điểm gốc của ranker đầu tiên chứa nó
            'retrievers'     — danh sách ranker đã bỏ phiếu cho nó
    """
    if not ranked_lists:
        return []

    fused: dict[str, float] = {}
    first_seen: dict[str, dict[str, Any]] = {}
    voters: dict[str, list[str]] = {}

    for ranked_list in ranked_lists:
        if not ranked_list:
            continue
        for rank, item in enumerate(ranked_list, start=1):
            content = item.get("content")
            if not content:
                continue

            key = _fuse_key(content)
            fused[key] = fused.get(key, 0.0) + 1.0 / (k + rank)

            if key not in first_seen:
                first_seen[key] = item
                voters[key] = []

            retriever = item.get("retriever") or item.get("source") or "unknown"
            if retriever not in voters[key]:
                voters[key].append(retriever)

    # Sort: RRF score desc, tie-break bằng original score desc
    ordered = sorted(
        fused.items(),
        key=lambda kv: (kv[1], float(first_seen[kv[0]].get("score") or 0.0)),
        reverse=True,
    )

    results: list[dict[str, Any]] = []
    for key, rrf_score in ordered[:top_k]:
        item = dict(first_seen[key])
        item["original_score"] = float(item.get("score") or 0.0)
        item["score"] = rrf_score
        item["retrievers"] = voters[key]
        results.append(item)

    return results


# =============================================================================
# MMR — Maximal Marginal Relevance
# =============================================================================

def rerank_mmr(
    query_embedding: list[float],
    candidates: list[dict[str, Any]],
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> list[dict[str, Any]]:
    """Maximal Marginal Relevance — chọn candidates vừa relevant vừa diverse.

    MMR = λ * sim(query, doc) - (1-λ) * max(sim(doc, selected_docs))

    Args:
        query_embedding: Vector embedding của query.
        candidates: Danh sách candidate, mỗi item PHẢI có key 'embedding'.
        top_k: Số lượng kết quả.
        lambda_param: Trade-off giữa relevance (1.0) và diversity (0.0).

    Returns:
        List of top_k candidates selected by MMR.
    """
    usable = [c for c in candidates if c.get("embedding")]
    if not usable:
        return candidates[:top_k]

    selected: list[int] = []
    remaining = list(range(len(usable)))

    while remaining and len(selected) < top_k:
        best_idx: int | None = None
        best_score = float("-inf")

        for idx in remaining:
            relevance = _cosine_similarity(query_embedding, usable[idx]["embedding"])
            max_sim = 0.0
            for sel in selected:
                max_sim = max(
                    max_sim,
                    _cosine_similarity(usable[idx]["embedding"], usable[sel]["embedding"]),
                )
            mmr = lambda_param * relevance - (1 - lambda_param) * max_sim
            if mmr > best_score:
                best_score = mmr
                best_idx = idx

        if best_idx is not None:
            selected.append(best_idx)
            remaining.remove(best_idx)

    results: list[dict[str, Any]] = []
    for idx in selected:
        item = dict(usable[idx])
        item["original_score"] = float(item.get("score") or 0.0)
        relevance = _cosine_similarity(query_embedding, item.get("embedding", []))
        item["score"] = relevance
        results.append(item)

    return results


# =============================================================================
# Cross-encoder (graceful degrade)
# =============================================================================

def rerank_cross_encoder(
    query: str, candidates: list[dict[str, Any]], top_k: int = 5
) -> list[dict[str, Any]]:
    """Rerank bằng cross-encoder.

    Thứ tự ưu tiên, tự động degrade:
        1. Jina Reranker API (nếu có JINA_API_KEY)
        2. Degrade về RRF trên danh sách đầu vào
    """
    if not candidates:
        return []

    documents = [c.get("content", "") for c in candidates]

    # --- Jina API ---
    if JINA_API_KEY:
        try:
            import requests

            resp = requests.post(
                JINA_RERANK_URL,
                headers={"Authorization": f"Bearer {JINA_API_KEY}"},
                json={
                    "model": JINA_MODEL,
                    "query": query,
                    "documents": documents,
                    "top_n": top_k,
                },
                timeout=30,
            )
            resp.raise_for_status()
            out: list[dict[str, Any]] = []
            for r in resp.json()["results"]:
                item = dict(candidates[r["index"]])
                item["original_score"] = float(item.get("score") or 0.0)
                item["score"] = float(r["relevance_score"])
                out.append(item)
            return out
        except Exception as e:
            print(f"  [!] Jina rerank failed ({e}) -> degrade to RRF")

    # --- Degrade ---
    return rerank_rrf([candidates], top_k=top_k)


# =============================================================================
# Unified rerank interface
# =============================================================================

def rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int = 5,
    method: str = "rrf",
) -> list[dict[str, Any]]:
    """Unified reranking interface.

    Với method="rrf", hàm này tách list phẳng theo 'retriever' rồi fuse.
    Khi cần gộp NHIỀU ranked lists thật sự (ví dụ semantic + lexical ở Task 9),
    hãy gọi ``rerank_rrf()`` trực tiếp.

    Args:
        query: Câu truy vấn.
        candidates: Danh sách candidates từ retrieval (list phẳng).
        top_k: Số lượng kết quả sau rerank.
        method: "rrf" (default) | "mmr" | "cross_encoder".

    Returns:
        List of top_k reranked candidates, mỗi item có key 'score'.
    """
    if not candidates:
        return []

    if method == "rrf":
        return rerank_rrf(_group_by_retriever(candidates), top_k=top_k)

    elif method == "mmr":
        first_emb = candidates[0].get("embedding")
        if first_emb is None:
            # Không có embedding → fallback về RRF
            return rerank_rrf(_group_by_retriever(candidates), top_k=top_k)
        return rerank_mmr(first_emb, candidates, top_k=top_k)

    elif method == "cross_encoder":
        return rerank_cross_encoder(query, candidates, top_k)

    else:
        raise ValueError(f"Unknown rerank method: {method}")


# =============================================================================
# Demo / Manual test
# =============================================================================

if __name__ == "__main__":
    print("=" * 64)
    print("Task 7 — Reranking Module Demo")
    print("=" * 64)

    # ── Demo RRF ──────────────────────────────────────────────────────
    print("\n--- RRF Demo ---")
    semantic_results = [
        {"content": "Hoc phi dai hoc Bach khoa 2025", "score": 0.92, "metadata": {"source": "a.md"}, "retriever": "dense"},
        {"content": "Thu vien Ta Quang Buu", "score": 0.78, "metadata": {"source": "b.md"}, "retriever": "dense"},
        {"content": "Hoc bong danh cho SV gioi", "score": 0.65, "metadata": {"source": "c.md"}, "retriever": "dense"},
    ]
    lexical_results = [
        {"content": "Hoc bong danh cho SV gioi", "score": 5.2, "metadata": {"source": "c.md"}, "retriever": "bm25"},
        {"content": "Hoc phi dai hoc Bach khoa 2025", "score": 3.1, "metadata": {"source": "a.md"}, "retriever": "bm25"},
        {"content": "Quy dinh thi lai", "score": 1.8, "metadata": {"source": "d.md"}, "retriever": "bm25"},
    ]

    rrf_results = rerank_rrf([semantic_results, lexical_results], top_k=5)
    for i, r in enumerate(rrf_results, 1):
        votes = "+".join(r.get("retrievers", []))
        print(f"  {i}. [RRF={r['score']:.4f}] (votes={votes}) {r['content']}")

    # ── Demo unified rerank() ─────────────────────────────────────────
    print("\n--- Unified rerank() Demo ---")
    candidates = [
        {"content": "Tuition fee payment schedule", "score": 0.8, "metadata": {}},
        {"content": "Scholarship eligibility requirements", "score": 0.6, "metadata": {}},
        {"content": "Library study room booking guide", "score": 0.5, "metadata": {}},
    ]
    results = rerank("tuition fee payment", candidates, top_k=2)
    for r in results:
        print(f"  [{r['score']:.4f}] {r['content']}")

    print("\n[OK] Task 7 hoan tat")
