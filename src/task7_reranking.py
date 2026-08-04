"""Task 7 — Reranking Module.

Phương pháp đã implement:
    - RRF (Reciprocal Rank Fusion): gộp kết quả từ nhiều ranker — CHÍNH, dùng ở Task 9.
    - MMR (Maximal Marginal Relevance): giảm trùng lặp, tăng diversity.
    - Cross-encoder: placeholder, cần API key (Jina / Qwen).

Lưu ý quan trọng về RRF (sẽ dùng lại ở Task 9): điểm RRF fused CHỈ phụ thuộc thứ hạng,
không phải độ tương đồng thật. Top-1 sau khi fuse luôn xấp xỉ 1/(k+1) ≈ 0.0164 (k=60),
bất kể nội dung đó có thật sự liên quan đến câu hỏi hay không. Đừng dùng điểm RRF để
quyết định fallback ở Task 9 — xem ghi chú ở đó.
"""

from __future__ import annotations

import math
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from typing import Any


# =============================================================================
# HELPERS
# =============================================================================

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Tính cosine similarity giữa hai vectors. Trả về 0.0 nếu vector rỗng."""
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)


def _content_key(item: dict[str, Any]) -> str:
    """Tạo key duy nhất cho mỗi candidate dựa trên content.

    Dùng source_path + chunk_index từ metadata nếu có, fallback sang nội dung
    text. Điều này giúp phân biệt đúng khi hai chunk có content trùng nhau
    nhưng đến từ file khác.
    """
    meta = item.get("metadata", {})
    source_path = meta.get("source_path", "")
    chunk_index = meta.get("chunk_index")

    if source_path and chunk_index is not None:
        return f"{source_path}::chunk::{chunk_index}"

    # Fallback: dùng content text
    return item.get("content", "")


# =============================================================================
# RRF — Reciprocal Rank Fusion
# =============================================================================

def rerank_rrf(
    ranked_lists: list[list[dict[str, Any]]],
    top_k: int = 5,
    k: int = 60,
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion — gộp kết quả từ nhiều ranker.

    RRF(d) = Σ 1 / (k + rank_r(d))

    Mỗi ranker đóng góp 1/(k + rank) cho mỗi document, trong đó rank bắt đầu
    từ 1 (top result). k=60 là giá trị mặc định từ paper gốc (Cormack et al.
    2009) — đủ lớn để "làm mượt" sự khác biệt thứ hạng giữa các ranker.

    Args:
        ranked_lists: Danh sách các ranked result list (mỗi list từ 1 ranker).
                      Mỗi item là dict với ít nhất {'content', 'score', 'metadata'}.
        top_k: Số lượng kết quả cuối cùng.
        k: Smoothing constant (default=60).

    Returns:
        List of top_k candidates sorted by RRF score descending.
        Mỗi item giữ nguyên metadata gốc, score được thay bằng RRF score.
    """
    if not ranked_lists:
        return []

    rrf_scores: dict[str, float] = {}
    content_map: dict[str, dict[str, Any]] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, start=1):
            key = _content_key(item)

            # Cộng dồn RRF score từ mỗi ranker
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)

            # Giữ bản ghi đầy đủ nhất (ưu tiên bản có score cao hơn)
            if key not in content_map:
                content_map[key] = item
            else:
                existing_score = content_map[key].get("score", 0.0)
                new_score = item.get("score", 0.0)
                if new_score > existing_score:
                    content_map[key] = item

    # Sắp xếp theo RRF score giảm dần
    sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    results: list[dict[str, Any]] = []
    for key, score in sorted_items[:top_k]:
        item = content_map[key].copy()
        # Giữ metadata gốc, chỉ ghi đè score bằng RRF score
        item["score"] = score
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
        List of top_k candidates selected by MMR, score = MMR score.
    """
    if not candidates:
        return []

    n = min(top_k, len(candidates))
    selected_indices: list[int] = []
    remaining = list(range(len(candidates)))

    for _ in range(n):
        best_idx: int | None = None
        best_score = float("-inf")

        for idx in remaining:
            candidate_emb = candidates[idx].get("embedding", [])

            # Relevance: cosine(query, candidate)
            relevance = _cosine_similarity(query_embedding, candidate_emb)

            # Redundancy: max cosine với các candidates đã chọn
            max_sim_to_selected = 0.0
            for sel_idx in selected_indices:
                sel_emb = candidates[sel_idx].get("embedding", [])
                sim = _cosine_similarity(candidate_emb, sel_emb)
                max_sim_to_selected = max(max_sim_to_selected, sim)

            # MMR score
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim_to_selected

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        if best_idx is not None:
            selected_indices.append(best_idx)
            remaining.remove(best_idx)

    results: list[dict[str, Any]] = []
    for idx in selected_indices:
        item = candidates[idx].copy()
        # Ghi đè score bằng MMR score (đã tính ở vòng lặp trên)
        # Tính lại ở đây cho chính xác
        candidate_emb = item.get("embedding", [])
        relevance = _cosine_similarity(query_embedding, candidate_emb)
        max_sim_to_selected = 0.0
        for other_idx in selected_indices:
            if other_idx == idx:
                continue
            other_emb = candidates[other_idx].get("embedding", [])
            sim = _cosine_similarity(candidate_emb, other_emb)
            max_sim_to_selected = max(max_sim_to_selected, sim)
        item["score"] = lambda_param * relevance - (1 - lambda_param) * max_sim_to_selected
        results.append(item)

    return results


# =============================================================================
# Cross-encoder (placeholder — cần API key)
# =============================================================================

def rerank_cross_encoder(
    query: str, candidates: list[dict[str, Any]], top_k: int = 5
) -> list[dict[str, Any]]:
    """Rerank candidates sử dụng cross-encoder model.

    Args:
        query: Câu truy vấn.
        candidates: List of {'content': str, 'score': float, 'metadata': dict}.
        top_k: Số lượng kết quả sau rerank.

    Returns:
        List of top_k candidates, re-scored và sorted by rerank_score descending.
    """
    # Cross-encoder cần Jina API key hoặc local model.
    # Xem README Task 7 để biết cách cài đặt.
    raise NotImplementedError(
        "Cross-encoder reranking cần API key (Jina) hoặc local model (Qwen). "
        "Dùng rerank_rrf() hoặc rerank_mmr() thay thế."
    )


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

    Với method="rrf", hàm này tạo MỘT ranked list từ candidates rồi chạy RRF.
    Khi cần gộp NHIỀU ranked lists thật sự (ví dụ semantic + lexical ở Task 9),
    hãy gọi ``rerank_rrf()`` trực tiếp.

    Args:
        query: Câu truy vấn.
        candidates: Danh sách candidates từ retrieval.
        top_k: Số lượng kết quả sau rerank.
        method: "rrf" (default) | "mmr" | "cross_encoder".

    Returns:
        List of top_k reranked candidates, mỗi item có key 'score'.
    """
    if not candidates:
        return []

    if method == "rrf":
        # Một ranked list duy nhất — RRF sẽ giữ nguyên thứ tự,
        # nhưng chuẩn hoá score sang thang RRF.
        return rerank_rrf([candidates], top_k=top_k)

    elif method == "mmr":
        # MMR cần query_embedding. Nếu candidates đã có embedding thì dùng
        # heuristic: lấy embedding từ candidate đầu tiên làm proxy cho query.
        # Cách tốt hơn: caller truyền query_embedding và gọi rerank_mmr() trực tiếp.
        first_emb = candidates[0].get("embedding")
        if first_emb is None:
            raise ValueError(
                "MMR cần embedding. Hãy gọi rerank_mmr() trực tiếp với "
                "query_embedding, hoặc đảm bảo candidates có key 'embedding'."
            )
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
        {"content": "Học phí đại học Bách khoa 2025", "score": 0.92, "metadata": {"source": "a.md"}},
        {"content": "Thư viện Tạ Quang Bửu", "score": 0.78, "metadata": {"source": "b.md"}},
        {"content": "Học bổng dành cho SV giỏi", "score": 0.65, "metadata": {"source": "c.md"}},
    ]
    lexical_results = [
        {"content": "Học bổng dành cho SV giỏi", "score": 5.2, "metadata": {"source": "c.md"}},
        {"content": "Học phí đại học Bách khoa 2025", "score": 3.1, "metadata": {"source": "a.md"}},
        {"content": "Quy định thi lại", "score": 1.8, "metadata": {"source": "d.md"}},
    ]

    rrf_results = rerank_rrf([semantic_results, lexical_results], top_k=5)
    for i, r in enumerate(rrf_results, 1):
        print(f"  {i}. [RRF={r['score']:.4f}] {r['content']}")

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

    print("\n[OK] Task 7 hoàn tất")
