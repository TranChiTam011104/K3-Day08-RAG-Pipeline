"""
Task 7 — Reranking Module.

Đã implement cả 3 phương pháp, mặc định dùng **RRF**:
    - RRF (Reciprocal Rank Fusion) — gộp nhiều ranker, không cần API key, không cần model
    - MMR (Maximal Marginal Relevance) — giảm trùng lặp, tăng diversity
    - Cross-encoder — Jina Reranker API (nếu có JINA_API_KEY) hoặc model local

Vì sao chọn RRF làm mặc định:
    1. Không cần API key / không tốn quota / chạy offline → cả nhóm dùng được ngay.
    2. Semantic score (cosine, thang [0,1]) và BM25 score (thang không chặn trên, có thể
       > 10) KHÔNG cùng đơn vị. Weighted fusion kiểu `a*cosine + b*bm25` buộc phải chuẩn
       hoá 2 thang đo khác bản chất — rất dễ sai. RRF chỉ dùng THỨ HẠNG nên miễn nhiễm
       với việc 2 ranker có thang điểm khác nhau.
    3. Corpus của nhóm chỉ ~36 chunk (15.8K ký tự) → điểm số nhiễu, thứ hạng ổn định hơn
       giá trị tuyệt đối.

⚠️ Lưu ý quan trọng về RRF (dùng lại ở Task 9): điểm RRF fused CHỈ phụ thuộc thứ hạng,
không phải độ tương đồng thật. Top-1 sau khi fuse luôn xấp xỉ 1/(k+1) ≈ 0.0164 (k=60),
bất kể nội dung đó có thật sự liên quan hay không. ĐỪNG dùng điểm RRF để quyết định
fallback ở Task 9 — hãy dùng `original_score` (cosine gốc) mà module này giữ lại.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

JINA_API_KEY = os.getenv("JINA_API_KEY", "")
JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"
JINA_MODEL = "jina-reranker-v2-base-multilingual"

# k=60 theo paper gốc Cormack et al. 2009 (TREC). Ý nghĩa: k lớn làm "làm phẳng" chênh
# lệch giữa các hạng đầu — hạng 1 (1/61) và hạng 2 (1/62) gần bằng nhau, nên một tài
# liệu được CẢ HAI ranker đồng thuận ở hạng 2 sẽ thắng tài liệu chỉ một ranker xếp hạng 1.
# Đó chính là hành vi ta muốn ở hybrid search: ưu tiên sự ĐỒNG THUẬN giữa dense và sparse.
RRF_K = 60


# =============================================================================
# Helpers
# =============================================================================

def _fuse_key(content: str) -> str:
    """
    Khoá gộp giữa các ranked list.

    Chuẩn hoá khoảng trắng (`" ".join(split())`) thay vì chỉ `.strip()`: cùng một chunk
    đi qua ChromaDB và đi qua đường đọc file có thể lệch nhau ở xuống dòng / khoảng
    trắng thừa. Lệch một ký tự trắng là RRF coi như 2 tài liệu khác nhau → fusion suy
    biến thành "nối 2 danh sách" mà không hề báo lỗi.
    """
    return " ".join(content.split())


def _group_by_retriever(candidates: list[dict]) -> list[list[dict]]:
    """
    Tách một danh sách phẳng thành nhiều ranked list theo trường 'retriever'.

    Cho phép `rerank(query, candidates, method="rrf")` hoạt động với input phẳng:
        - Có ≥2 retriever khác nhau → tách đúng thành các ranked list riêng rồi fuse.
        - Chỉ 1 retriever (hoặc không có trường này) → coi như 1 ranked list duy nhất.
    """
    groups: dict[str, list[dict]] = {}
    for item in candidates:
        name = (item or {}).get("retriever") or (item or {}).get("source") or "_default"
        groups.setdefault(name, []).append(item)

    if len(groups) < 2:
        return [list(candidates)]
    return list(groups.values())


# =============================================================================
# RRF — Reciprocal Rank Fusion (phương pháp chính)
# =============================================================================

def rerank_rrf(
    ranked_lists: list[list[dict]], top_k: int = 5, k: int = RRF_K
) -> list[dict]:
    """
    Reciprocal Rank Fusion — gộp kết quả từ nhiều ranker.

        RRF(d) = Σ_r  1 / (k + rank_r(d))

    Args:
        ranked_lists: List các ranked result list (mỗi list từ 1 ranker), đã sort desc
        top_k: Số lượng kết quả cuối cùng
        k: Smoothing constant (default=60, Cormack et al. 2009)

    Returns:
        List of top_k candidates sorted by RRF score descending. Mỗi item có thêm:
            'score'          — điểm RRF (dùng để sắp xếp)
            'original_score' — điểm gốc của ranker đầu tiên chứa nó (cosine hoặc BM25)
            'retrievers'     — danh sách ranker đã bỏ phiếu cho nó
    """
    if not ranked_lists:
        return []

    fused: dict[str, float] = {}
    first_seen: dict[str, dict] = {}
    voters: dict[str, list[str]] = {}

    for ranked_list in ranked_lists:
        if not ranked_list:
            continue
        for rank, item in enumerate(ranked_list, start=1):
            content = (item or {}).get("content")
            if not content:
                continue  # bỏ qua item hỏng, không để cả pipeline chết vì 1 record lỗi

            key = _fuse_key(content)
            fused[key] = fused.get(key, 0.0) + 1.0 / (k + rank)

            if key not in first_seen:
                first_seen[key] = item
                voters[key] = []

            retriever = item.get("retriever") or item.get("source") or "unknown"
            if retriever not in voters[key]:
                voters[key].append(retriever)

    # Sort theo điểm RRF; tie-break bằng original_score để kết quả tất định.
    # Với corpus nhỏ (~36 chunk) việc đồng điểm RRF xảy ra thường xuyên, không có
    # tie-break thì thứ tự phụ thuộc thứ tự insert của dict → khó debug, khó eval lại.
    ordered = sorted(
        fused.items(),
        key=lambda kv: (kv[1], float(first_seen[kv[0]].get("score") or 0.0)),
        reverse=True,
    )

    results: list[dict] = []
    for key, rrf_score in ordered[:top_k]:
        item = dict(first_seen[key])  # copy, không mutate input của caller
        item["original_score"] = float(item.get("score") or 0.0)
        item["score"] = rrf_score
        item["retrievers"] = voters[key]
        results.append(item)

    return results


# =============================================================================
# MMR — Maximal Marginal Relevance
# =============================================================================

def _cosine(a: list[float], b: list[float]) -> float:
    import numpy as np

    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return float(np.dot(va, vb) / denom) if denom else 0.0


def rerank_mmr(
    query_embedding: list[float],
    candidates: list[dict],
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> list[dict]:
    """
    Maximal Marginal Relevance — chọn candidates vừa relevant vừa diverse.

        MMR = λ * sim(query, doc) - (1-λ) * max(sim(doc, đã_chọn))

    λ=0.7: nghiêng về relevance nhưng vẫn phạt trùng lặp. Corpus của nhóm có 3 trường
    (HUST/NEU/HUCE) nói về cùng chủ đề học phí–học bổng với nội dung gần trùng nhau,
    không có MMR thì top-5 rất dễ là 5 biến thể của cùng một nội dung.

    Yêu cầu: mỗi candidate phải có key 'embedding'. Dùng `rerank(..., method="mmr")`
    nếu muốn tự động sinh embedding tạm bằng TF-IDF.
    """
    usable = [c for c in candidates if c.get("embedding")]
    if not usable:
        raise ValueError(
            "rerank_mmr cần candidates có key 'embedding'. "
            "Dùng rerank(query, candidates, method='mmr') để tự sinh vector tạm."
        )

    selected: list[int] = []
    remaining = list(range(len(usable)))

    while remaining and len(selected) < top_k:
        best_idx, best_score = None, float("-inf")

        for idx in remaining:
            relevance = _cosine(query_embedding, usable[idx]["embedding"])
            max_sim = 0.0
            for sel in selected:
                max_sim = max(
                    max_sim, _cosine(usable[idx]["embedding"], usable[sel]["embedding"])
                )
            mmr = lambda_param * relevance - (1 - lambda_param) * max_sim
            if mmr > best_score:
                best_score, best_idx = mmr, idx

        selected.append(best_idx)
        remaining.remove(best_idx)

    results = []
    for rank, idx in enumerate(selected, start=1):
        item = dict(usable[idx])
        item["original_score"] = float(item.get("score") or 0.0)
        item["score"] = lambda_param * _cosine(query_embedding, item["embedding"])
        item["mmr_rank"] = rank
        results.append(item)
    return results


def _tfidf_embeddings(query: str, candidates: list[dict]) -> tuple[list[float], list[dict]]:
    """
    Sinh vector tạm bằng TF-IDF khi candidates chưa có embedding thật.

    Dùng cho MMR khi Task 4 chưa xong (chưa có bge-m3). Rẻ, không cần load model,
    đủ để đo độ trùng lặp giữa các chunk — vốn là mục đích duy nhất của MMR.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    try:
        from .task6_lexical_search import fold
    except ImportError:  # chạy standalone
        from task6_lexical_search import fold  # type: ignore

    texts = [c.get("content", "") for c in candidates]
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), preprocessor=fold)
    matrix = vec.fit_transform(texts + [query])

    dense = matrix.toarray()
    enriched = [dict(c, embedding=dense[i].tolist()) for i, c in enumerate(candidates)]
    return dense[-1].tolist(), enriched


# =============================================================================
# Cross-encoder
# =============================================================================

def rerank_cross_encoder(
    query: str, candidates: list[dict], top_k: int = 5
) -> list[dict]:
    """
    Rerank bằng cross-encoder (chấm điểm cặp query–document, chính xác hơn bi-encoder).

    Thứ tự ưu tiên, tự động degrade — KHÔNG BAO GIỜ raise (điều khoản (b) của hợp đồng
    API: task9 import module này ở top-level, một exception ở đây làm sập cả pipeline):
        1. Jina Reranker API   (nếu có JINA_API_KEY)
        2. CrossEncoder local  (nếu đã cài sentence-transformers)
        3. Degrade về RRF trên chính danh sách đầu vào
    """
    if not candidates:
        return []

    documents = [c.get("content", "") for c in candidates]

    # --- 1. Jina API ---------------------------------------------------------
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
            out = []
            for r in resp.json()["results"]:
                item = dict(candidates[r["index"]])
                item["original_score"] = float(item.get("score") or 0.0)
                item["score"] = float(r["relevance_score"])
                item["retriever"] = "cross_encoder:jina"
                out.append(item)
            return out
        except Exception as e:
            print(f"  ⚠ Jina rerank thất bại ({e}) → thử model local")

    # --- 2. CrossEncoder local ----------------------------------------------
    try:
        from sentence_transformers import CrossEncoder

        model = CrossEncoder("BAAI/bge-reranker-v2-m3")
        scores = model.predict([(query, d) for d in documents])
        out = []
        for cand, s in zip(candidates, scores):
            item = dict(cand)
            item["original_score"] = float(item.get("score") or 0.0)
            item["score"] = float(s)
            item["retriever"] = "cross_encoder:local"
            out.append(item)
        out.sort(key=lambda x: x["score"], reverse=True)
        return out[:top_k]
    except Exception as e:
        print(f"  ⚠ Cross-encoder local không dùng được ({e}) → degrade về RRF")

    # --- 3. Degrade ----------------------------------------------------------
    return rerank_rrf([candidates], top_k=top_k)


# =============================================================================
# Main rerank interface
# =============================================================================

def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
    method: str = "rrf",  # "cross_encoder" | "mmr" | "rrf"
) -> list[dict]:
    """
    Unified reranking interface.

    Args:
        query: Câu truy vấn
        candidates: Danh sách candidates từ retrieval (list PHẲNG)
        top_k: Số lượng kết quả sau rerank
        method: Phương pháp reranking

    Returns:
        List of top_k reranked candidates.
    """
    if not candidates:
        return []

    if method == "rrf":
        # Tách list phẳng theo 'retriever' rồi fuse. Nếu chỉ có 1 nguồn thì RRF trên
        # 1 list = giữ nguyên thứ tự nhưng chuẩn hoá điểm về thang RRF — vẫn hợp lệ.
        return rerank_rrf(_group_by_retriever(candidates), top_k=top_k)

    if method == "cross_encoder":
        return rerank_cross_encoder(query, candidates, top_k)

    if method == "mmr":
        if all(c.get("embedding") for c in candidates):
            # Có embedding thật (từ Task 4) → dùng luôn. Query embedding lấy từ
            # caller không có, nên tạm dùng centroid của top-3 làm proxy cho query.
            import numpy as np

            proxy = np.mean(
                [c["embedding"] for c in candidates[:3]], axis=0
            ).tolist()
            return rerank_mmr(proxy, candidates, top_k=top_k)
        query_vec, enriched = _tfidf_embeddings(query, candidates)
        return rerank_mmr(query_vec, enriched, top_k=top_k)

    raise ValueError(f"Unknown rerank method: {method}")


if __name__ == "__main__":
    print("=" * 70)
    print("Task 7 — Reranking demo")
    print("=" * 70)

    # Mô phỏng 2 ranked list như Task 9 sẽ đưa vào: dense (cosine) và sparse (BM25).
    dense = [
        {"content": "Hoc bong loai A (Xuat sac): GPA >= 3.6, Diem ren luyen >= 90",
         "score": 0.71, "metadata": {"source": "quy-dinh-hoc-phi-hoc-bong-hust.md"},
         "retriever": "dense"},
        {"content": "Muc hoc phi chuong trinh chuan: 28.000.000 VN den 35.000.000 VN",
         "score": 0.64, "metadata": {"source": "quy-dinh-hoc-phi-hoc-bong-hust.md"},
         "retriever": "dense"},
        {"content": "Thư viện cung cấp 20 phòng học nhóm trang bị màn hình tương tác",
         "score": 0.41, "metadata": {"source": "article_05.md"}, "retriever": "dense"},
    ]
    sparse = [
        {"content": "Muc hoc phi chuong trinh chuan: 28.000.000 VN den 35.000.000 VN",
         "score": 8.42, "metadata": {"source": "quy-dinh-hoc-phi-hoc-bong-hust.md"},
         "retriever": "bm25"},
        {"content": "Hoc ky he: Muc hoc phi tinh bang 1.5 lan hoc ky chinh",
         "score": 5.13, "metadata": {"source": "quy-dinh-hoc-phi-hoc-bong-hust.md"},
         "retriever": "bm25"},
    ]

    print("\n[1] RRF fusion (dense + bm25):")
    for i, r in enumerate(rerank_rrf([dense, sparse], top_k=4), 1):
        votes = "+".join(r["retrievers"])
        print(f"  {i}. rrf={r['score']:.5f} (goc={r['original_score']:.2f}, "
              f"votes={votes}) {r['content'][:55]}...")
    print("  → Chunk được CẢ 2 ranker bình chọn leo lên hạng 1 dù cosine gốc thấp hơn.")

    print("\n[2] rerank() với list phẳng, method='rrf' (đường Task 9 gọi):")
    for i, r in enumerate(rerank("hoc phi", dense + sparse, top_k=3), 1):
        print(f"  {i}. [{r['score']:.5f}] {r['content'][:55]}...")

    print("\n[3] MMR (tự sinh vector TF-IDF vì chưa có embedding thật):")
    for i, r in enumerate(rerank("hoc phi hoc bong", dense + sparse, top_k=3,
                                 method="mmr"), 1):
        print(f"  {i}. [{r['score']:.4f}] {r['content'][:55]}...")
