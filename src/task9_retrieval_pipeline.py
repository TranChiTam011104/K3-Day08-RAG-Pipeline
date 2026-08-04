"""Task 9 — Retrieval Pipeline Hoàn Chỉnh.

Kết hợp semantic search + lexical search + reranking + PageIndex fallback
thành một pipeline thống nhất.

Logic:
    1. Chạy semantic_search (Task 5) + lexical_search (Task 6) — tolerant failures
    2. Merge kết quả bằng RRF (Task 7)
    3. Rerank
    4. Nếu best cosine score GỐC < threshold → fallback PageIndex (Task 8)
    5. Return top_k results

⚠️ BẪY THƯỜNG GẶP — đọc kỹ trước khi sửa:
    Điểm RRF fused CHỈ phụ thuộc thứ hạng, KHÔNG phản ánh độ liên quan thật.
    Top-1 RRF luôn ≈ 1/(k+1) ≈ 0.0164 (k=60), bất kể query có liên quan hay không.
    Vì vậy score_threshold được so với điểm COSINE GỐC từ semantic_search, KHÔNG
    phải điểm RRF.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from dotenv import load_dotenv

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# =============================================================================
# CONFIGURATION
# =============================================================================

# So sánh với điểm cosine GỐC từ semantic_search (thang [0, 1]).
# Nếu best cosine < threshold → hybrid search "không đủ tự tin" → fallback PageIndex.
SCORE_THRESHOLD = 0.3
DEFAULT_TOP_K = 5
RERANK_METHOD = "rrf"  # "rrf" | "mmr" | "cross_encoder"


# =============================================================================
# SAFE IMPORTS — Task 9 KHÔNG được crash vì một Task phụ thuộc chưa implement
# =============================================================================

def _safe_semantic_search(query: str, top_k: int) -> list[dict[str, Any]]:
    """Gọi Task 5 semantic_search, trả [] nếu Task 5 chưa sẵn sàng."""
    try:
        from .task5_semantic_search import semantic_search
        results = semantic_search(query, top_k=top_k)
        # Gắn nhãn retriever để RRF phân biệt nguồn
        for r in results:
            r["retriever"] = "dense"
        return results
    except Exception as e:
        print(f"  [!] Semantic search failed: {e}")
        return []


def _safe_lexical_search(query: str, top_k: int) -> list[dict[str, Any]]:
    """Gọi Task 6 lexical_search, trả [] nếu Task 6 chưa sẵn sàng."""
    try:
        from .task6_lexical_search import lexical_search
        results = lexical_search(query, top_k=top_k)
        for r in results:
            r["retriever"] = "bm25"
        return results
    except Exception as e:
        print(f"  [!] Lexical search failed: {e}")
        return []


def _safe_pageindex_search(query: str, top_k: int) -> list[dict[str, Any]]:
    """Gọi Task 8 pageindex_search, trả [] nếu Task 8 chưa sẵn sàng."""
    try:
        from .task8_pageindex_vectorless import pageindex_search
        results = pageindex_search(query, top_k=top_k)
        for r in results:
            r["source"] = "pageindex"
        return results
    except Exception as e:
        print(f"  [!] PageIndex search failed: {e}")
        return []


# =============================================================================
# RETRIEVAL PIPELINE
# =============================================================================

def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
) -> list[dict[str, Any]]:
    """Retrieval pipeline hoàn chỉnh với fallback logic.

    Pipeline:
        Query
          ├→ Semantic Search (Task 5) → dense_results (giữ điểm cosine gốc)
          ├→ Lexical Search  (Task 6) → sparse_results
          │
          ├→ Merge (RRF, Task 7) → merged_results
          ├→ Rerank → reranked_results
          │
          └→ If dense_results[0]["score"] < threshold:
                └→ PageIndex Vectorless (Task 8) → fallback_results

    Args:
        query: Câu truy vấn.
        top_k: Số lượng kết quả cuối cùng.
        score_threshold: Ngưỡng điểm cosine gốc tối thiểu (KHÔNG phải điểm RRF).
        use_reranking: Có áp dụng reranking hay không.

    Returns:
        List of {
            'content': str,
            'score': float,
            'metadata': dict,
            'source': str  # 'hybrid' hoặc 'pageindex'
        }
    """
    from .task7_reranking import rerank, rerank_rrf

    # ── Step 1: Chạy semantic + lexical (tolerant) ─────────────────────
    retrieval_top_k = top_k * 2  # Lấy gấp đôi để reranking có đủ candidates

    dense_results = _safe_semantic_search(query, retrieval_top_k)
    sparse_results = _safe_lexical_search(query, retrieval_top_k)

    print(f"  [i] Dense: {len(dense_results)} results, "
          f"Sparse: {len(sparse_results)} results")

    # Lấy best cosine score GỐC TRƯỚC khi merge RRF
    best_cosine_score = dense_results[0]["score"] if dense_results else 0.0

    # ── Step 2: Merge bằng RRF ──────────────────────────────────────────
    ranked_lists: list[list[dict[str, Any]]] = []
    if dense_results:
        ranked_lists.append(dense_results)
    if sparse_results:
        ranked_lists.append(sparse_results)

    if ranked_lists:
        merged = rerank_rrf(ranked_lists, top_k=retrieval_top_k)
    else:
        merged = []

    # Gắn source = "hybrid" cho tất cả kết quả merged
    for item in merged:
        item["source"] = "hybrid"

    # ── Step 3: Rerank (optional) ────────────────────────────────────────
    if use_reranking and merged:
        final_results = rerank(query, merged, top_k=top_k, method=RERANK_METHOD)
    else:
        final_results = merged[:top_k]

    # Đảm bảo mỗi item có "source"
    for item in final_results:
        if "source" not in item:
            item["source"] = "hybrid"

    # ── Step 4: Fallback check dùng COSINE GỐC ──────────────────────────
    print(f"  [i] Best cosine score (dense): {best_cosine_score:.4f}, "
          f"threshold: {score_threshold}")

    if best_cosine_score < score_threshold:
        print(f"  [!] Best cosine ({best_cosine_score:.4f}) < threshold "
              f"({score_threshold}) -> trying PageIndex fallback...")

        fallback = _safe_pageindex_search(query, top_k)
        if fallback:
            print(f"  [i] PageIndex returned {len(fallback)} results")
            return fallback[:top_k]
        else:
            print("  [!] PageIndex returned no results -> returning hybrid results")

    return final_results[:top_k]


# =============================================================================
# Demo / Manual test
# =============================================================================

if __name__ == "__main__":
    print("=" * 64)
    print("Task 9 — Retrieval Pipeline Demo")
    print("=" * 64)

    test_queries = [
        "hoc phi dai hoc Bach khoa",
        "hoc bong sinh vien gioi",
        "thu vien phong hoc nhom",
        "xyzabc123nonsense",  # Query rác → test fallback
    ]

    for q in test_queries:
        print(f"\nQuery: {q}")
        print("-" * 60)
        try:
            results = retrieve(q, top_k=3)
            if results:
                for i, r in enumerate(results, 1):
                    content_preview = r["content"][:80].replace("\n", " ")
                    print(f"  {i}. [{r['score']:.4f}] [{r['source']}] {content_preview}...")
            else:
                print("  (no results)")
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\n[OK] Task 9 hoan tat")
