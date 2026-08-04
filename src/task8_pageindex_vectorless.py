"""
Task 8 — PageIndex Vectorless RAG.

Đăng ký tài khoản tại: https://pageindex.ai/
SDK & sample code: https://github.com/VectifyAI/PageIndex

PageIndex cho phép RAG mà không cần vector store — nó dựng CÂY MỤC LỤC của tài liệu
(chương → mục → tiểu mục) rồi để LLM duyệt cây chọn nhánh liên quan, thay vì chunking
+ embedding + cosine. Đây là lý do nó được dùng làm FALLBACK ở Task 9: khi hybrid search
(dense + BM25) không tìm thấy gì đủ tốt, ta đổi hẳn sang một cơ chế truy hồi khác bản
chất chứ không phải chạy lại cùng một cơ chế.

Nguồn upload: 6 file PDF ở data/landing/legal/ (quy chế đào tạo + quy định học phí/học
bổng của HUST/NEU/HUCE). Dùng PDF gốc thay vì convert markdown → PDF để tránh hẳn bẫy
font Unicode của fpdf2 (xem `markdown_to_pdf` bên dưới).

⚠️ Hạn chế đã biết của corpus hiện tại: 6 PDF này MẤT DẤU tiếng Việt (được sinh bằng
font latin-1), nên nội dung PageIndex trả về cũng không dấu. Cần nói rõ khi demo, và
Role 2 nên sinh lại PDF với font Unicode rồi re-upload để sửa triệt để.

⚠️ API `/retrieval` của PageIndex đã deprecated (vẫn hoạt động, response có field
"deprecation") và trả kết quả trong "retrieved_nodes" — mỗi node có "relevant_contents":
list[list[{section_title, relevant_content}]]. Schema được xác nhận bằng cách in response
thật (chạy module này với biến môi trường PAGEINDEX_DEBUG=1), không đoán từ code mẫu cũ.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
DEBUG_RAW = os.getenv("PAGEINDEX_DEBUG", "") == "1"

PROJECT_DIR = Path(__file__).parent.parent
STANDARDIZED_DIR = PROJECT_DIR / "data" / "standardized"
LEGAL_LANDING_DIR = PROJECT_DIR / "data" / "landing" / "legal"

# Cache {filename: doc_id}. Upload là thao tác bất đồng bộ, chậm và tốn quota →
# chỉ upload MỘT LẦN, các lần chạy sau đọc lại từ file này.
DOC_CACHE_PATH = PROJECT_DIR / "data" / "pageindex_docs.json"

POLL_INTERVAL = 2.0    # giây giữa 2 lần hỏi trạng thái retrieval
POLL_TIMEOUT = 90.0    # tổng thời gian chờ tối đa cho 1 truy vấn
MAX_PARALLEL_DOCS = 6  # số document truy vấn song song


# =============================================================================
# Client & cache
# =============================================================================

def _get_client():
    """
    Trả về PageIndexClient, hoặc None nếu chưa cấu hình / chưa cài SDK.

    KHÔNG raise (điều khoản (b) của hợp đồng API): task9 import module này ở
    top-level, một exception ở đây sẽ làm sập cả Task 9, Task 10 và app.py.
    """
    if not PAGEINDEX_API_KEY:
        return None
    try:
        from pageindex import PageIndexClient

        return PageIndexClient(api_key=PAGEINDEX_API_KEY)
    except Exception as e:
        print(f"  ⚠ Không khởi tạo được PageIndexClient: {e}")
        return None


def _load_doc_cache() -> dict[str, str]:
    if DOC_CACHE_PATH.exists():
        try:
            return json.loads(DOC_CACHE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_doc_cache(cache: dict[str, str]) -> None:
    DOC_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_CACHE_PATH.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# =============================================================================
# Upload
# =============================================================================

def markdown_to_pdf(md_path: Path, out_path: Path) -> Path:
    """
    Convert markdown → PDF giữ nguyên dấu tiếng Việt (dùng khi muốn upload file news).

    🔴 Bẫy: font mặc định của fpdf2 (Helvetica) chỉ encode latin-1 → toàn bộ dấu tiếng
    Việt bị mất hoặc raise UnicodeEncodeError. BẮT BUỘC phải add_font một TTF Unicode
    trước. Đây chính là lỗi đã làm 6 PDF ở data/landing/legal/ mất sạch dấu.
    """
    from fpdf import FPDF

    font_candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    font_path = next((f for f in font_candidates if f.exists()), None)
    if font_path is None:
        raise FileNotFoundError("Không tìm thấy TTF Unicode để render tiếng Việt")

    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("uni", "", str(font_path))
    pdf.set_font("uni", size=11)
    for line in md_path.read_text(encoding="utf-8").splitlines():
        pdf.multi_cell(0, 6, line or " ")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return out_path


def upload_documents(force: bool = False, include_news: bool = False) -> dict[str, str]:
    """
    Upload documents lên PageIndex và cache lại doc_id.

    Args:
        force: Upload lại kể cả file đã có trong cache
        include_news: Sinh thêm PDF từ data/standardized/news/*.md (có dấu đầy đủ,
                      4–5 heading/file → cây mục lục sâu hơn) rồi upload

    Returns:
        dict {filename: doc_id}
    """
    client = _get_client()
    if client is None:
        print("⚠ Chưa có PAGEINDEX_API_KEY trong .env — bỏ qua upload")
        return {}

    cache = _load_doc_cache()
    targets = sorted(LEGAL_LANDING_DIR.glob("*.pdf"))

    if include_news:
        tmp_dir = PROJECT_DIR / "data" / "landing" / "news_pdf"
        for md in sorted((STANDARDIZED_DIR / "news").glob("*.md")):
            targets.append(markdown_to_pdf(md, tmp_dir / f"{md.stem}.pdf"))

    for pdf_path in targets:
        if pdf_path.name in cache and not force:
            print(f"  ↷ Bỏ qua (đã upload): {pdf_path.name} -> {cache[pdf_path.name]}")
            continue
        try:
            resp = client.submit_document(str(pdf_path))
            doc_id = resp.get("doc_id") or resp.get("id")
            if not doc_id:
                print(f"  ✗ {pdf_path.name}: response không có doc_id → {resp}")
                continue
            cache[pdf_path.name] = doc_id
            print(f"  ✓ Uploaded: {pdf_path.name} -> {doc_id}")
        except Exception as e:
            print(f"  ✗ Lỗi upload {pdf_path.name}: {e}")

    _save_doc_cache(cache)
    return cache


def wait_until_ready(timeout: float = 180.0) -> dict[str, bool]:
    """
    Chờ PageIndex xử lý xong (dựng cây + OCR) cho toàn bộ document đã upload.

    submit_document trả doc_id NGAY nhưng việc dựng cây chạy bất đồng bộ — query
    trước khi tài liệu sẵn sàng sẽ không ra kết quả.
    """
    client = _get_client()
    cache = _load_doc_cache()
    if client is None or not cache:
        return {}

    deadline = time.time() + timeout
    status = {name: False for name in cache}
    while time.time() < deadline and not all(status.values()):
        for name, doc_id in cache.items():
            if not status[name]:
                status[name] = client.is_retrieval_ready(doc_id)
        if all(status.values()):
            break
        time.sleep(POLL_INTERVAL)

    for name, ok in status.items():
        print(f"  {'✓' if ok else '…'} {name}: {'sẵn sàng' if ok else 'chưa xong'}")
    return status


# =============================================================================
# Retrieval
# =============================================================================

def _query_one_doc(client, doc_id: str, source_name: str, query: str) -> list[dict]:
    """Truy vấn 1 document, poll tới khi completed, parse retrieved_nodes."""
    try:
        resp = client.submit_query(doc_id=doc_id, query=query)
        retrieval_id = resp.get("retrieval_id") or resp.get("id")
        if not retrieval_id:
            return []

        deadline = time.time() + POLL_TIMEOUT
        retrieval: dict = {}
        while time.time() < deadline:
            retrieval = client.get_retrieval(retrieval_id)
            if retrieval.get("status") in ("completed", "failed", "error"):
                break
            time.sleep(POLL_INTERVAL)

        if DEBUG_RAW:
            print(f"\n--- RAW response ({source_name}) ---")
            print(json.dumps(retrieval, indent=2, ensure_ascii=False)[:3000])

        if retrieval.get("status") != "completed":
            return []

        # Schema: retrieved_nodes[] → relevant_contents[][] → {section_title, relevant_content}
        out = []
        for node in retrieval.get("retrieved_nodes", []):
            for group in node.get("relevant_contents", []) or []:
                for item in group or []:
                    text = (item or {}).get("relevant_content", "")
                    if text and text.strip():
                        out.append({
                            "content": text.strip(),
                            "section": (item or {}).get("section_title", ""),
                            "source_name": source_name,
                        })
        return out
    except Exception as e:
        print(f"  ⚠ PageIndex query lỗi trên {source_name}: {e}")
        return []


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Vectorless retrieval sử dụng PageIndex.
    Dùng làm fallback khi hybrid search không có kết quả tốt.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,
            'metadata': dict,
            'source': 'pageindex'   # Đánh dấu nguồn retrieval
        }
    """
    client = _get_client()
    cache = _load_doc_cache()
    if client is None or not cache or not query.strip():
        return []

    # PageIndex truy hồi theo TỪNG document (submit_query nhận 1 doc_id), nên để
    # "tìm trên cả corpus" ta phải hỏi song song rồi trộn kết quả lại.
    items = list(cache.items())[:MAX_PARALLEL_DOCS]
    with ThreadPoolExecutor(max_workers=len(items)) as pool:
        per_doc = list(pool.map(
            lambda kv: _query_one_doc(client, kv[1], kv[0], query), items
        ))

    # Trộn round-robin giữa các document: PageIndex không trả score nên không có cơ sở
    # so sánh chéo document. Round-robin đảm bảo không để 1 file chiếm hết top_k.
    merged: list[dict] = []
    for rank in range(max((len(d) for d in per_doc), default=0)):
        for doc_results in per_doc:
            if rank < len(doc_results):
                merged.append(doc_results[rank])

    results = []
    for i, hit in enumerate(merged[:top_k]):
        results.append({
            "content": hit["content"],
            # PageIndex không trả relevance score → tự gán giảm dần theo thứ hạng.
            # Thang điểm này KHÔNG so sánh được với cosine của Task 5, chỉ dùng để
            # giữ đúng format chung của pipeline.
            "score": round(max(0.0, 1.0 - 0.05 * i), 4),
            "metadata": {
                "source": hit["source_name"],
                "section": hit["section"],
                "type": "legal",
                "engine": "pageindex-api",
            },
            "source": "pageindex",
        })
    return results


if __name__ == "__main__":
    if not PAGEINDEX_API_KEY:
        print("⚠ Hãy set PAGEINDEX_API_KEY trong file .env")
        print("  Đăng ký tại: https://pageindex.ai/")
    else:
        print("=" * 70)
        print("Task 8 — PageIndex Vectorless RAG")
        print("=" * 70)

        print("\n[1] Upload documents:")
        cache = upload_documents()

        print("\n[2] Chờ PageIndex dựng cây mục lục:")
        wait_until_ready()

        print("\n[3] Test query:")
        for q in ["học bổng Trần Đại Nghĩa", "điều kiện xét học bổng loại A"]:
            results = pageindex_search(q, top_k=3)
            print(f"\n  Query: {q!r} → {len(results)} kết quả")
            for r in results:
                print(f"    [{r['score']:.2f}] ({r['metadata']['source']} | "
                      f"{r['metadata']['section']}) {r['content'][:70]}...")
