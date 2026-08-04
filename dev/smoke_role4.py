"""
Smoke test tổng hợp cho Role 4 (Task 6 + 7 + 8).

Chạy:
    $env:PYTHONIOENCODING="utf-8"
    python -m dev.smoke_role4

Mục đích:
    1. Kiểm tra 3 module không raise trong mọi tình huống (kể cả corpus rỗng)
    2. Chứng minh fold-tokenizer vá được lỗi corpus lệch dấu legal/news
    3. So sánh BM25 vs TF-IDF (chuẩn bị cho phần demo +5 bonus)
    4. Đo OVERLAP giữa ranked list dense và sparse — cảnh báo sớm nếu RRF suy biến
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.task6_lexical_search import (  # noqa: E402
    corpus_info, fold, lexical_search, load_corpus, tfidf_search, tokenize,
)
from src.task7_reranking import rerank, rerank_rrf  # noqa: E402
from src.task8_pageindex_vectorless import pageindex_search  # noqa: E402

LINE = "=" * 78


def section(title: str) -> None:
    print(f"\n{LINE}\n{title}\n{LINE}")


# =============================================================================
# 1. Tokenizer
# =============================================================================

def check_tokenizer() -> None:
    section("1. TOKENIZER — fold dấu + giữ thực thể số")

    cases = [
        ("Học bổng loại A", "hoc bong loai a"),
        ("Hoc bong loai A", "hoc bong loai a"),
        ("Điểm rèn luyện", "diem ren luyen"),      # đ nguyên khối, NFD không tách được
        ("Đăng ký học phần", "dang ky hoc phan"),
    ]
    ok = True
    for raw, expected in cases:
        got = fold(raw)
        status = "✓" if got == expected else "✗"
        ok &= got == expected
        print(f"  {status} fold({raw!r}) = {got!r}")

    print("\n  Token của các thực thể số/mã (chỗ BM25 thắng dense):")
    for raw in ["28.000.000 VN", "1024/QD-DHBK", "GPA >= 3.6", "7h30 - 21h30"]:
        print(f"    {raw!r:22} → {tokenize(raw)}")

    print(f"\n  → Tokenizer: {'ĐẠT' if ok else 'LỖI'}")


# =============================================================================
# 2. Corpus + BM25
# =============================================================================

def check_corpus() -> bool:
    section("2. CORPUS & BM25")
    print(f"  Nguồn: {corpus_info()}")

    corpus = load_corpus()
    if not corpus:
        print("  ⚠ Corpus RỖNG — bỏ qua các kiểm tra phụ thuộc dữ liệu.")
        print("    (Task 1/2/3 của Role 2 cần chạy lại để sinh data/standardized/)")
        return False

    types: dict[str, int] = {}
    schools: dict[str, int] = {}
    for c in corpus:
        types[c["metadata"].get("type", "?")] = types.get(c["metadata"].get("type", "?"), 0) + 1
        s = c["metadata"].get("school") or "?"
        schools[s] = schools.get(s, 0) + 1
    print(f"  Phân bố theo type   : {types}")
    print(f"  Phân bố theo school : {schools}")
    return True


def check_diacritics_fix() -> None:
    """Bài kiểm tra QUAN TRỌNG NHẤT của Task 6."""
    section("3. VÁ LỖI CORPUS LỆCH DẤU (legal không dấu vs news có dấu)")

    with_marks = lexical_search("học bổng loại A xuất sắc", top_k=8)
    without = lexical_search("hoc bong loai A xuat sac", top_k=8)

    if not with_marks:
        print("  ⚠ Không có kết quả (corpus rỗng) — bỏ qua.")
        return

    same = [r["content"] for r in with_marks] == [r["content"] for r in without]
    types = {r["metadata"].get("type") for r in with_marks}

    print(f"  Query CÓ dấu    → {len(with_marks)} kết quả")
    print(f"  Query KHÔNG dấu → {len(without)} kết quả")
    print(f"  {'✓' if same else '✗'} Hai truy vấn cho kết quả GIỐNG HỆT nhau")
    print(f"  {'✓' if len(types) > 1 else '✗'} Chạm tới cả 2 nửa corpus: {sorted(types)}")

    if not same or len(types) < 2:
        print("  ✗ THẤT BẠI: fold-tokenizer chưa vá được lỗi lệch dấu")


# =============================================================================
# 3. BM25 vs TF-IDF
# =============================================================================

def compare_rankers() -> None:
    section("4. BM25 vs TF-IDF (chuẩn bị demo +5 bonus)")

    for q in ["học phí", "học bổng Trần Đại Nghĩa", "đăng ký học phần"]:
        bm = lexical_search(q, top_k=3)
        tf = tfidf_search(q, top_k=3)
        if not bm and not tf:
            print(f"\n  {q!r}: không có kết quả (corpus rỗng)")
            continue
        print(f"\n  Query: {q!r}")
        print(f"    BM25  {[r['metadata'].get('source') for r in bm]}")
        print(f"    TFIDF {[r['metadata'].get('source') for r in tf]}")


# =============================================================================
# 4. RRF + cảnh báo overlap
# =============================================================================

def check_rrf_overlap() -> None:
    section("5. RRF FUSION & CẢNH BÁO OVERLAP")

    query = "điều kiện xét học bổng"
    sparse = lexical_search(query, top_k=10)

    # Dense chưa sẵn sàng (Task 5 chưa implement) → mô phỏng bằng TF-IDF để vẫn kiểm
    # tra được cơ chế fusion. Khi Task 4/5 xong thì thay bằng semantic_search thật.
    try:
        from src.task5_semantic_search import semantic_search
        dense = semantic_search(query, top_k=10)
        dense_label = "semantic_search (Task 5 THẬT)"
    except (ImportError, NotImplementedError):
        dense = [dict(r, retriever="dense") for r in tfidf_search(query, top_k=10)]
        dense_label = "TF-IDF (giả lập vì Task 5 chưa xong)"
    except Exception:
        dense, dense_label = [], "không khả dụng"

    print(f"  Ranked list 'dense' : {dense_label} → {len(dense)} kết quả")
    print(f"  Ranked list 'sparse': BM25 → {len(sparse)} kết quả")

    if not dense or not sparse:
        print("  ⚠ Thiếu một trong hai danh sách — bỏ qua kiểm tra overlap.")
        return

    keys_d = {" ".join(r["content"].split()) for r in dense}
    keys_s = {" ".join(r["content"].split()) for r in sparse}
    overlap = keys_d & keys_s

    print(f"\n  Overlap dense ∩ sparse: {len(overlap)}/{min(len(keys_d), len(keys_s))}")
    if not overlap:
        print("  🔴 BÁO ĐỘNG: overlap = 0 → RRF suy biến thành 'nối 2 danh sách'.")
        print("     Nguyên nhân thường gặp: Task 6 chunk khác Task 4 (lệch CHUNK_SIZE).")
        print("     Xử lý: đảm bảo Task 6 đọc corpus từ chính ChromaDB của Task 4.")
    else:
        print("  ✓ Có overlap → RRF hoạt động đúng nghĩa (ưu tiên sự đồng thuận).")

    fused = rerank_rrf([dense, sparse], top_k=5)
    print(f"\n  Top-5 sau RRF:")
    for i, r in enumerate(fused, 1):
        print(f"    {i}. rrf={r['score']:.5f} gốc={r['original_score']:7.3f} "
              f"votes={'+'.join(r['retrievers']):<12} {r['metadata'].get('source')}")

    if fused:
        print(f"\n  ⚠ Nhắc lại: điểm RRF top-1 = {fused[0]['score']:.5f} ≈ 1/(60+1). "
              f"ĐỪNG so nó với SCORE_THRESHOLD ở Task 9 —")
        print(f"     hãy dùng cosine gốc của semantic_search (trường 'original_score').")


# =============================================================================
# 5. Không-raise contract
# =============================================================================

def check_no_raise() -> None:
    section("6. HỢP ĐỒNG 'KHÔNG RAISE' (task9 import 3 module này ở top-level)")

    checks = [
        ("lexical_search('')", lambda: lexical_search("", top_k=3)),
        ("lexical_search(rác)", lambda: lexical_search("xyzabc123nonsense", top_k=3)),
        ("tfidf_search(rác)", lambda: tfidf_search("xyzabc123nonsense", top_k=3)),
        ("rerank([])", lambda: rerank("q", [], top_k=3)),
        ("rerank_rrf([])", lambda: rerank_rrf([], top_k=3)),
        ("rerank(item thiếu content)", lambda: rerank_rrf([[{"score": 1.0}]], top_k=3)),
        ("pageindex_search(rác)", lambda: pageindex_search("xyzabc123nonsense", top_k=2)),
    ]
    for label, fn in checks:
        try:
            out = fn()
            print(f"  ✓ {label:<30} → {type(out).__name__}(len={len(out)})")
        except Exception as e:
            print(f"  ✗ {label:<30} → RAISE {type(e).__name__}: {e}")


if __name__ == "__main__":
    print(LINE)
    print("SMOKE TEST — ROLE 4 (Sparse Retrieval & Fallback)")
    print(LINE)

    check_tokenizer()
    has_data = check_corpus()
    check_diacritics_fix()
    compare_rankers()
    check_rrf_overlap()
    check_no_raise()

    print(f"\n{LINE}")
    if not has_data:
        print("KẾT LUẬN: code Role 4 chạy đúng nhưng CORPUS RỖNG.")
        print("          Cần Role 2 chạy lại Task 1/2/3 để sinh data/standardized/.")
    else:
        print("KẾT LUẬN: xem các dấu ✓/✗ ở trên.")
    print(LINE)
