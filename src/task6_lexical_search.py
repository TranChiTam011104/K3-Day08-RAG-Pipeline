"""
Task 6 — Lexical Search Module (BM25 + TF-IDF).

Mặc định dùng BM25. Có thêm `tfidf_search()` để so sánh cơ chế trong buổi demo (+5 bonus).

BM25 hoạt động thế nào:
    - Term Frequency (TF): từ xuất hiện nhiều trong document → điểm cao
    - Inverse Document Frequency (IDF): từ hiếm → quan trọng hơn
    - Document length normalization: document dài không bị ưu tiên quá mức
    - Formula: score(q,d) = Σ IDF(qi) * (tf(qi,d) * (k1+1)) / (tf(qi,d) + k1*(1-b+b*|d|/avgdl))
    - k1=1.5 (term saturation), b=0.75 (length normalization)

🔴 VẤN ĐỀ ĐẶC THÙ CỦA CORPUS NHÓM — lý do phải có `fold()`:
    6 file trong data/standardized/legal/ MẤT TOÀN BỘ DẤU tiếng Việt (PDF gốc được sinh
    bằng font latin-1 nên dấu bị lược từ khâu tạo file), trong khi 10 file news/ giữ
    nguyên dấu. Cùng một nội dung nhưng:

        legal:  "Hoc bong loai A (Xuat sac): GPA >= 3.6"
        news:   "Học bổng loại A (Xuất sắc): GPA >= 3.6"

    Với BM25 đây là HAI TẬP TOKEN RỜI NHAU → gõ "học bổng loại A" chỉ thấy news, gõ
    "hoc bong loai A" chỉ thấy legal. Dù query kiểu nào cũng mất một nửa corpus, mà
    pipeline vẫn chạy êm không báo lỗi.

    Cách xử lý ở module này: chuẩn hoá CẢ corpus LẪN query về dạng không dấu (`fold`)
    trước khi index. Lưu ý đây chỉ vá được phía lexical — dense search (Task 5) vẫn bị
    ảnh hưởng, muốn sửa triệt để thì Role 2 phải sinh lại PDF với font Unicode.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

# Lấy config từ Task 4 làm nguồn chân lý duy nhất — nếu Role 3 đổi CHUNK_SIZE thì
# BM25 tự động đổi theo, tránh lệch chunk giữa dense và sparse (xem ghi chú ở
# _load_from_markdown).
try:
    from .task4_chunking_indexing import (
        CHROMA_DIR, CHUNK_OVERLAP, CHUNK_SIZE, COLLECTION_NAME, STANDARDIZED_DIR,
    )
except ImportError:  # chạy standalone: python src/task6_lexical_search.py
    from task4_chunking_indexing import (  # type: ignore
        CHROMA_DIR, CHUNK_OVERLAP, CHUNK_SIZE, COLLECTION_NAME, STANDARDIZED_DIR,
    )

NEWS_LANDING_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"

# BM25 hyperparameters (mặc định của BM25Okapi, ghi tường minh để giải thích khi demo)
BM25_K1 = 1.5   # term saturation: lần lặp thứ 10 của từ khoá gần như không tăng điểm nữa
BM25_B = 0.75   # length normalization: phạt document dài theo tỉ lệ |d|/avgdl


# =============================================================================
# Tokenizer — fold dấu tiếng Việt
# =============================================================================

_MARKS = re.compile(r"[\u0300-\u036f]")  # dau thanh/dau mu dang to hop (combining marks)
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[./\-][a-z0-9]+)*")
_SEP_RE = re.compile(r"[./\-]")


def fold(text: str) -> str:
    """
    Chuẩn hoá text về ASCII không dấu, chữ thường. Áp dụng cho CẢ corpus lẫn query.

        "Học bổng loại A"  →  "hoc bong loai a"
        "Hoc bong loai A"  →  "hoc bong loai a"     ← hai nguồn gặp nhau ở đây
    """
    # 1. Bỏ escape "\(" / "\)" mà MarkItDown chèn vào file legal .md
    text = text.replace("\\", " ")

    # 2. đ/Đ phải xử lý RIÊNG: U+0111 là ký tự nguyên khối, NFD KHÔNG tách nó thành
    #    "d" + dấu. Thiếu dòng này thì "điểm" → "điem" (vẫn còn đ) ≠ "diem" → trượt.
    text = text.replace("đ", "d").replace("Đ", "D")

    # 3. Tách ký tự cơ sở khỏi dấu tổ hợp rồi bỏ dấu.
    #    Xử lý được cả ă â ê ô ơ ư (đều tách thành base + combining mark U+0300–U+036F).
    text = unicodedata.normalize("NFD", text)
    text = _MARKS.sub("", text)

    return unicodedata.normalize("NFC", text).lower()


def tokenize(text: str) -> list[str]:
    """
    Tách token, giữ nguyên các thực thể số/mã — chính là chỗ BM25 thắng dense search.

        "28.000.000 VN"      →  ['28.000.000', '28', '000', '000', 'vn']
        "1024/QD-DHBK"       →  ['1024/qd-dhbk', '1024', 'qd', 'dhbk']
        "GPA >= 3.6"         →  ['gpa', '3.6', '3', '6']

    Sinh thêm sub-token của các cụm có dấu . / - : với corpus chỉ ~36 chunk, recall
    quan trọng hơn precision — query "QD-DHBK" hay "1024" đều phải tìm ra được cùng
    một văn bản.
    """
    tokens: list[str] = []
    for tok in _TOKEN_RE.findall(fold(text)):
        tokens.append(tok)
        if _SEP_RE.search(tok):
            tokens.extend(p for p in _SEP_RE.split(tok) if p)
    return tokens


# =============================================================================
# Corpus resolver — 3 tầng, tự động degrade
# =============================================================================

CORPUS: list[dict] = []          # List of {'content': str, 'metadata': dict}
_BM25 = None                     # cache index BM25
_TFIDF = None                    # cache (vectorizer, matrix)
_CORPUS_SOURCE = "chưa nạp"      # tầng nào đang được dùng — hiển thị khi debug
_WARNED_EMPTY = False            # chỉ cảnh báo "corpus rỗng" một lần cho mỗi process


def _school_from_name(name: str) -> str:
    """Suy ra trường từ tên file legal: 'quy-dinh-hoc-phi-hoc-bong-hust.md' → 'HUST'."""
    for school in ("hust", "neu", "huce"):
        if school in name.lower():
            return school.upper()
    return ""


def _load_from_chroma() -> list[dict] | None:
    """
    Tầng 1 (chuẩn nhất): đọc thẳng chunk từ ChromaDB của Task 4.

    Bắt buộc phải ưu tiên tầng này: Task 7 gộp kết quả dense và sparse bằng khoá
    `content`. Nếu BM25 chunk văn bản theo cách khác Task 4, sẽ KHÔNG có chunk nào
    trùng nhau giữa 2 danh sách → RRF suy biến thành "nối 2 list", hybrid search mất
    hết ý nghĩa mà không hề báo lỗi.
    """
    try:
        import chromadb

        if not CHROMA_DIR.exists():
            return None
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        col = client.get_collection(COLLECTION_NAME)
        got = col.get(include=["documents", "metadatas"])
        docs = got.get("documents") or []
        metas = got.get("metadatas") or [{}] * len(docs)
        if not docs:
            return None
        return [
            {"content": d, "metadata": dict(m or {})}
            for d, m in zip(docs, metas)
        ]
    except Exception:
        return None


def _split_text(text: str) -> list[str]:
    """Chunk giống Task 4: RecursiveCharacterTextSplitter(CHUNK_SIZE, CHUNK_OVERLAP)."""
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        return splitter.split_text(text)
    except ImportError:
        # Fallback không phụ thuộc thư viện — cắt theo đoạn rồi gộp tới CHUNK_SIZE
        chunks, buf = [], ""
        for para in text.split("\n\n"):
            if len(buf) + len(para) + 2 <= CHUNK_SIZE:
                buf = f"{buf}\n\n{para}" if buf else para
            else:
                if buf:
                    chunks.append(buf)
                buf = para[-CHUNK_OVERLAP:] + para if len(para) <= CHUNK_SIZE else para
                while len(buf) > CHUNK_SIZE:
                    chunks.append(buf[:CHUNK_SIZE])
                    buf = buf[CHUNK_SIZE - CHUNK_OVERLAP:]
        if buf:
            chunks.append(buf)
        return chunks


def _load_from_markdown() -> list[dict] | None:
    """
    Tầng 2: đọc data/standardized/**/*.md rồi tự chunk.

    Dùng khi Task 4 chưa chạy xong. Chunk bằng ĐÚNG tham số của Task 4 để khi
    chroma_db/ xuất hiện, kết quả không đổi nhiều.
    """
    if not STANDARDIZED_DIR.exists():
        return None

    corpus: list[dict] = []
    for md_file in sorted(STANDARDIZED_DIR.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        if not content.strip():
            continue

        doc_type = "legal" if "legal" in md_file.parts else "news"
        meta_base = {
            "source": md_file.name,
            "type": doc_type,
            "school": _school_from_name(md_file.stem),
        }

        # News có sẵn metadata phong phú trong JSON gốc (school/category/url/title) —
        # tận dụng để sau này lọc/boost theo trường, vì corpus có 3 trường nội dung
        # rất giống nhau nên rất dễ trả nhầm trường.
        news_json = NEWS_LANDING_DIR / f"{md_file.stem}.json"
        if doc_type == "news" and news_json.exists():
            try:
                raw = json.loads(news_json.read_text(encoding="utf-8"))
                meta_base.update({
                    "school": raw.get("school", meta_base["school"]),
                    "category": raw.get("category", ""),
                    "url": raw.get("url", ""),
                    "title": raw.get("title", ""),
                })
            except (json.JSONDecodeError, OSError):
                pass

        for i, chunk in enumerate(_split_text(content)):
            if chunk.strip():
                corpus.append({
                    "content": chunk,
                    "metadata": {**meta_base, "chunk_index": i},
                })

    return corpus or None


def load_corpus(force: bool = False) -> list[dict]:
    """
    Nạp corpus theo thứ tự ưu tiên: ChromaDB → markdown → rỗng.

    KHÔNG raise khi không có dữ liệu (điều khoản (b) của hợp đồng API: task9 import
    module này ở top-level, raise ở đây làm sập cả Task 9/Task 10/app.py).
    """
    global CORPUS, _CORPUS_SOURCE, _BM25, _TFIDF

    if CORPUS and not force:
        return CORPUS

    for loader, label in (
        (_load_from_chroma, f"ChromaDB ({COLLECTION_NAME})"),
        (_load_from_markdown, f"markdown ({STANDARDIZED_DIR.name}/, chunk={CHUNK_SIZE}/{CHUNK_OVERLAP})"),
    ):
        data = loader()
        if data:
            CORPUS, _CORPUS_SOURCE = data, label
            _BM25 = _TFIDF = None  # invalidate cache khi đổi nguồn
            return CORPUS

    CORPUS, _CORPUS_SOURCE = [], "KHÔNG CÓ DỮ LIỆU"
    # Chỉ cảnh báo 1 lần: corpus rỗng nên cache không "dính", mọi lời gọi sau đều
    # chạy lại resolver — không chặn log thì mỗi truy vấn in thêm 1 dòng rác.
    global _WARNED_EMPTY
    if not _WARNED_EMPTY:
        _WARNED_EMPTY = True
        print("  ⚠ Task 6: không tìm thấy corpus "
              "(chroma_db/ lẫn data/standardized/ đều trống)")
    return CORPUS


def corpus_info() -> str:
    """Mô tả nguồn corpus đang dùng — cho smoke test và demo."""
    load_corpus()
    return f"{len(CORPUS)} chunks từ {_CORPUS_SOURCE}"


# =============================================================================
# BM25
# =============================================================================

def build_bm25_index(corpus: list[dict]):
    """
    Xây dựng BM25 index từ corpus.

    Args:
        corpus: List of {'content': str, 'metadata': dict}
    """
    from rank_bm25 import BM25Okapi

    tokenized_corpus = [tokenize(doc["content"]) for doc in corpus]
    return BM25Okapi(tokenized_corpus, k1=BM25_K1, b=BM25_B)


def _get_bm25():
    """Lazy init + cache: chỉ build index 1 lần cho cả process."""
    global _BM25
    if _BM25 is None:
        corpus = load_corpus()
        if not corpus:
            return None
        _BM25 = build_bm25_index(corpus)
    return _BM25


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm từ khóa sử dụng BM25.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,      # BM25 score thô (>=0, KHÔNG chuẩn hoá về [0,1])
            'metadata': dict,
            'retriever': 'bm25'
        }
        Sorted by score descending.
    """
    import numpy as np

    bm25 = _get_bm25()
    if bm25 is None or not query.strip():
        return []

    scores = bm25.get_scores(tokenize(query))
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        if scores[idx] > 0:  # BM25 = 0 nghĩa là không khớp token nào → bỏ
            results.append({
                "content": CORPUS[idx]["content"],
                "score": float(scores[idx]),
                "metadata": CORPUS[idx]["metadata"],
                "retriever": "bm25",
            })
    return results


# =============================================================================
# TF-IDF (bonus +5 — giải thích cơ chế lexical search khác BM25)
# =============================================================================

def _get_tfidf():
    """Lazy init + cache cho TF-IDF."""
    global _TFIDF
    if _TFIDF is None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        corpus = load_corpus()
        if not corpus:
            return None
        # analyzer='char_wb' + ngram 3–5: char n-gram không cần word segmentation
        # tiếng Việt, và chịu được cả corpus lệch dấu lẫn người dùng gõ thiếu dấu.
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), preprocessor=fold)
        matrix = vec.fit_transform([d["content"] for d in corpus])
        _TFIDF = (vec, matrix)
    return _TFIDF


def tfidf_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Lexical search bằng TF-IDF + cosine similarity (để so sánh với BM25 khi demo).

    Khác biệt cốt lõi so với BM25:
        - TF-IDF: điểm TĂNG TUYẾN TÍNH theo tần suất từ → văn bản dài lặp nhiều từ
          khoá luôn thắng. Không có cơ chế bão hoà, không phạt độ dài (chỉ chuẩn hoá
          L2 toàn vector).
        - BM25: (1) bão hoà tần suất qua k1=1.5 — lần lặp thứ 10 gần như không tăng
          điểm; (2) phạt độ dài qua b=0.75 theo tỉ lệ |d|/avgdl.
    """
    import numpy as np

    tf = _get_tfidf()
    if tf is None or not query.strip():
        return []

    vec, matrix = tf
    qv = vec.transform([query])
    sims = (matrix @ qv.T).toarray().ravel()
    top_indices = np.argsort(sims)[::-1][:top_k]

    return [
        {
            "content": CORPUS[idx]["content"],
            "score": float(sims[idx]),
            "metadata": CORPUS[idx]["metadata"],
            "retriever": "tfidf",
        }
        for idx in top_indices
        if sims[idx] > 0
    ]


if __name__ == "__main__":
    print("=" * 74)
    print(f"Task 6 — Lexical Search | corpus: {corpus_info()}")
    print("=" * 74)

    # Bài test QUAN TRỌNG NHẤT: cùng một câu hỏi, gõ CÓ DẤU và KHÔNG DẤU phải cho
    # cùng kết quả, và phải chạm được cả 2 nửa corpus (legal không dấu + news có dấu).
    for q in ["học bổng loại A xuất sắc", "hoc bong loai A xuat sac"]:
        res = lexical_search(q, top_k=5)
        types = {r["metadata"].get("type") for r in res}
        print(f"\n[BM25] {q!r} → {len(res)} kết quả, chạm tới: {sorted(types)}")
        for r in res[:3]:
            print(f"   [{r['score']:6.3f}] ({r['metadata'].get('type')}/"
                  f"{r['metadata'].get('school')}) {r['content'][:60].strip()}...")

    print("\n" + "-" * 74)
    for q in ["1024/QD-DHBK", "học phí chương trình ELITECH", "đăng ký phòng học nhóm"]:
        res = lexical_search(q, top_k=3)
        print(f"\n[BM25] {q!r} → {len(res)} kết quả")
        for r in res:
            print(f"   [{r['score']:6.3f}] {r['metadata'].get('source')}: "
                  f"{r['content'][:60].strip()}...")

    print("\n" + "-" * 74)
    q = "học phí"
    print(f"\nSo sánh BM25 vs TF-IDF trên {q!r}:")
    for name, fn in (("BM25 ", lexical_search), ("TFIDF", tfidf_search)):
        res = fn(q, top_k=3)
        for i, r in enumerate(res, 1):
            print(f"  {name} {i}. [{r['score']:6.3f}] {r['metadata'].get('source')}")
