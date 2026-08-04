# 📋 KẾ HOẠCH LÀM VIỆC — ROLE 4 (Sparse Retrieval & Fallback Dev)

> **Chủ đề nhóm:** #4 — 🎓 Trợ Lý Tra Cứu Điểm Chuẩn & Đề Án Tuyển Sinh Đại Học
> **Phạm vi Role 4:** Task 6 (Lexical Search) + Task 7 (Reranking) + Task 8 (PageIndex Vectorless Fallback)
> **Điểm chịu trách nhiệm trực tiếp:** 6 + 6 + 4 = **16 / 50 điểm cá nhân**, cộng cơ hội **+5 bonus** (giải thích cơ chế lexical search khác BM25) và đóng góp chính cho A/B testing của bài nhóm (hybrid vs dense-only).
>
> **Cập nhật:** sau khi Role 2 hoàn thành Task 1–2–3. Repo **không phải git repository** (không có `.git`) nên trạng thái dưới đây được kiểm tra trực tiếp trên filesystem, không phải qua commit log.

---

## ✅ TIẾN ĐỘ — Phase 0, 1, 2 ĐÃ HOÀN THÀNH

| Phase | Nội dung | Kết quả |
| :-- | :--- | :--- |
| **0** | Môi trường + Task 7 + smoke script | ✅ `.venv` (Python 3.11.9) đã cài đủ package; `src/task7_reranking.py` xong (RRF + MMR + cross-encoder), **3/3 test passed**; `dev/smoke_role4.py`; `dev/HANDOFF_ROLE4.md` |
| **1** | Task 6 trên dữ liệu thật | ✅ `src/task6_lexical_search.py` xong (BM25 + TF-IDF + fold-tokenizer). Đã verify trên corpus thật: **44 chunk**, query có dấu và không dấu cho **kết quả giống hệt nhau** và chạm được **cả legal lẫn news** → lỗi lệch dấu (mục 1.1) đã vá |
| **2** | Task 8 PageIndex | ✅ `src/task8_pageindex_vectorless.py` xong (upload + poll + parse + cache doc_id). API key verify OK. ⚠️ **Chưa upload được** vì PDF nguồn đã bị xoá |

**Test hiện tại:** `TestTask6` 1 passed / 3 skipped · `TestTask7` 3/3 passed · `TestTask8` 2/2 passed.
3 test skip của Task 6 là do **corpus rỗng**, không phải code lỗi.

> ### 🔴 SỰ CỐ: dữ liệu Task 1/2/3 đã bị xoá lúc ~11:10
> Toàn bộ 6 PDF + 10 JSON + 16 file `.md` biến mất khỏi `data/`, chỉ còn `.gitkeep`. Đã quét
> toàn bộ cây `LabDay08` — file bị xoá hẳn chứ không bị di chuyển. Repo không có `.git` nên
> không khôi phục được. **Cần Role 2 chạy lại Task 1/2/3, và nhóm nên `git init` ngay.**
> Chi tiết + 3 việc cần các role khác xử lý: xem `dev/HANDOFF_ROLE4.md`.

---

## 0. Trạng thái repo (đã kiểm tra lại)

| Hạng mục | Trạng thái | Ảnh hưởng tới Role 4 |
| :--- | :--- | :--- |
| `data/landing/legal/` | ✅ **6 PDF** (`quy-che-dao-tao-*`, `quy-dinh-hoc-phi-hoc-bong-*` × HUST/NEU/HUCE), 1.3–1.8 KB/file | Task 8 đã có PDF để upload → **hết chặn** |
| `data/landing/news/` | ✅ **10 JSON** (`article_01..10`), có `url`/`title`/`school`/`category`/`date_crawled` | Nguồn metadata tốt cho lọc/boost |
| `data/standardized/` | ✅ **16 file `.md`** (6 legal + 10 news), tổng **15.837 ký tự** | Task 6 đã có corpus → **hết chặn** |
| `chroma_db/` | ❌ Chưa tồn tại | Task 4 chưa xong → Task 6 tạm dùng resolver tầng 2 |
| `src/task4`, `task5` | ❌ Stub `NotImplementedError` | Chưa verify được overlap dense∩sparse |
| `src/task9`, `task10` | ❌ Stub | Chưa tích hợp |

### 🎉 Kết luận mới: Role 4 **không còn bị chặn bởi ai cả**

| Task | Trước đây | Bây giờ |
| :--- | :--- | :--- |
| **Task 7** (6đ) | Không bị chặn | Không bị chặn |
| **Task 6** (6đ) | Chặn mềm — thiếu corpus | ✅ **Hết chặn** — chạy ngay trên `data/standardized/` (16 file .md) |
| **Task 8** (4đ) | Chặn — thiếu PDF | ✅ **Hết chặn** — 6 PDF sẵn sàng upload |

→ **Toàn bộ 16 điểm của Role 4 có thể hoàn thành ngay hôm nay**, không cần chờ Task 4/5. Việc duy nhất phải chờ là *verify* độ khớp chunk giữa dense và sparse (mục 2c) khi `chroma_db/` xuất hiện.

---

## 1. 🔴 BA PHÁT HIỆN VỀ DỮ LIỆU THẬT — ảnh hưởng trực tiếp tới Task 6/8

### 1.1 CRITICAL: Corpus bị chia làm **hai hệ chữ viết** — legal MẤT HẾT DẤU tiếng Việt

Kiểm chứng: quét ký tự có dấu trên toàn bộ `data/standardized/` →
**0/6 file legal có dấu**, **10/10 file news có dấu** (142 lượt).

```
legal/quy-dinh-hoc-phi-hoc-bong-hust.md :  "MUC 1: Quy dinh ve Hoc phi"
                                            "Hoc bong loai A \(Xuat sac\): GPA >= 3.6"
news/article_01.md                      :  "## 1. Đối tượng và Điều kiện xét Học bổng KKHT"
                                            "**Học bổng loại A (Xuất sắc):** GPA >= 3.6"
```

Hai đoạn trên **nội dung giống hệt nhau** nhưng với BM25 là **hai tập token hoàn toàn rời nhau**:

| Query người dùng gõ | Khớp legal? | Khớp news? |
| :--- | :-: | :-: |
| `"học bổng loại A"` (có dấu) | ❌ | ✅ |
| `"hoc bong loai A"` (không dấu) | ✅ | ❌ |

→ **Dù query thế nào cũng chỉ thấy được một nửa corpus.** Đây là lỗi nghiêm trọng nhất hiện tại và nó **im lặng** — pipeline vẫn chạy, vẫn trả kết quả, chỉ là mất một nửa.

**Nguyên nhân:** PDF ở `data/landing/legal/` được sinh bằng `fpdf2` với font mặc định (Helvetica/latin-1) không encode được tiếng Việt → dấu bị lược bỏ ngay từ khâu tạo PDF, MarkItDown chỉ trích xuất đúng cái đã mất. Đây chính xác là cái bẫy đã ghi ở mục 4.3 của kế hoạch cũ, chỉ khác là nó xảy ra ở Task 1 chứ không phải Task 8.

**Xử lý — hai tầng, làm cả hai:**

| Tầng | Ai làm | Nội dung |
| :-- | :-- | :--- |
| **Tầng 1 — Role 4 tự làm ngay** | Role 4 | **Tokenizer fold dấu** (mục 4.1): chuẩn hoá cả corpus lẫn query về dạng không dấu trước khi index BM25 → `"học phí"` và `"hoc phi"` thành cùng một token. Không cần chờ ai, không sửa dữ liệu của ai. |
| **Tầng 2 — báo Role 2 sửa gốc** | Role 2 | Sinh lại 6 PDF với font Unicode: `pdf.add_font("DejaVu", fname="C:/Windows/Fonts/arial.ttf")` rồi `pdf.set_font("DejaVu")`, chạy lại Task 3. |

> ⚠️ **Phải báo Role 1/3 ngay:** fold dấu chỉ cứu được **lexical search**. **Dense search (Task 5, bge-m3) vẫn bị ảnh hưởng** — embedding của `"hoc phi"` không đồng nhất với `"học phí"`, chất lượng retrieval trên 6 file legal sẽ kém hơn hẳn news. Chỉ tầng 2 mới sửa được triệt để. Nếu không sửa, cần nêu rõ hạn chế này trong `results.md` của Role 6.

### 1.2 Corpus rất nhỏ (15.837 ký tự ≈ **36 chunk** với size=500/overlap=50)

| | legal | news | tổng |
| :-- | --: | --: | --: |
| Số file | 6 | 10 | 16 |
| Ký tự | 5.052 | 10.785 | 15.837 |
| Heading markdown | **0** | 4–5/file | — |

Hệ quả cho Role 4:

- **IDF mỏng.** BM25 tính `IDF` trên 36 document; một từ xuất hiện ở 5 chunk đã bị coi là "phổ biến". Điểm số sẽ nhiễu hơn bình thường — đừng ngạc nhiên nếu ranking không ổn định giữa các query gần giống nhau.
- **`top_k` đang quá lớn so với corpus.** Task 9 gọi `semantic_search(top_k=top_k*2)` + `lexical_search(top_k=top_k*2)` = 10+10 → RRF fuse tối đa 20/36 chunk = **55% toàn bộ corpus**. Hybrid gần như mất khả năng phân biệt.
  → **Đề xuất chốt với Role 1:** `DEFAULT_TOP_K = 3~4` thay vì 5, và `lexical_search` mặc định `top_k=5` thay vì 10, cho tới khi corpus lớn hơn.
- **Legal không có heading nào** → nếu Role 3 chọn `MarkdownHeaderTextSplitter` cho Task 4 thì 6 file legal sẽ **không bị cắt** (mỗi file 1 chunk 679–1096 ký tự), lệch hẳn so với news. → **Đề xuất Role 3 dùng `RecursiveCharacterTextSplitter`** cho đồng nhất.

### 1.3 Nội dung corpus **không khớp với mô tả chủ đề 4**

Chủ đề 4 nói *"tra cứu điểm chuẩn & đề án tuyển sinh"*, nhưng dữ liệu thực tế là **quy chế đào tạo + học phí/học bổng + tin dịch vụ sinh viên** của HUST/NEU/HUCE. Trong toàn bộ 16 file: **không có một bảng điểm chuẩn nào, không có mã ngành 7 chữ số, không có chỉ tiêu tuyển sinh.**

Ảnh hưởng tới Role 4 (và cần báo Role 1 + Role 6):
- Ví dụ query trong kế hoạch cũ (`"điểm chuẩn 25.75 khối A00"`) **không dùng được** → phải đổi sang các thực thể có thật trong corpus (mục 4.1).
- Golden dataset của Role 6 **không thể hỏi về điểm chuẩn** → hoặc Role 2 bổ sung dữ liệu điểm chuẩn, hoặc nhóm điều chỉnh tên/phạm vi sản phẩm thành *"Trợ lý tra cứu quy chế đào tạo, học phí & học bổng"* cho trung thực với dữ liệu.

**Các thực thể số CÓ THẬT trong corpus — đây mới là chỗ BM25 thắng dense:**
`GPA >= 3.6` · `ĐRL >= 90` · `28.000.000 VN` · `45.000.000` · `120% học phí` · `12 tín chỉ` · số quyết định `1024/QD-DHBK` · hạn nộp `28/11/2025` · giờ mở cửa `7h30 - 21h30` · `50.000 giáo trình`

### 1.4 🟠 Test chấm điểm sẽ bị SKIP (rủi ro đã hiện thực hoá)

`tests/test_individual.py` dùng query tiếng Anh. Quét toàn corpus: **không có** `tuition`, `scholarship`, `fee`, `payment`. Chỉ `article_05.md` có vài từ tiếng Anh (`NEU Library`, `Digital Library`, `Co-working space`, `ProQuest`).

Dự đoán kết quả `TestTask6`:

| Test | Query | Dự kiến |
| :--- | :--- | :--- |
| `test_returns_list` | `"tuition fee payment policy"` | ✅ pass (list rỗng vẫn là list) |
| `test_results_have_required_keys` | `"scholarship eligibility"` | ⏭️ **SKIP** (0 kết quả) |
| `test_results_sorted_descending` | `"library study room"` | ⚠️ tuỳ số chunk chứa `library` |
| `test_keyword_match_scores_higher` | `"tuition fee"` | ⏭️ **SKIP** (0 kết quả) |

→ Mốc *"35/35 test passed"* ở CP4 (LAB_GUIDE) **không đạt được**. `TestTask5` của Role 3 cũng dính y hệt.

> **Đề xuất gửi Role 1/2 ngay:** thêm **1 bài news tiếng Anh** — ví dụ trang tiếng Anh của HUST/NEU về *"International Student Tuition Fees & Scholarships"* hoặc *"Library services"*. Một file duy nhất cứu được cả `TestTask5` lẫn `TestTask6`, vẫn đúng chủ đề, tốn ~5 phút. **Tokenizer không cứu được việc này** — fold dấu biến `"học phí"` thành `"hoc phi"` chứ không thành `"tuition"`.

---

## 2. Hợp đồng API (API Contract) — chốt với Role 1/2/3

Role 4 cam kết export đúng các hàm sau, không đổi chữ ký:

```python
# src/task6_lexical_search.py
def lexical_search(query: str, top_k: int = 10) -> list[dict]: ...
    # -> [{'content': str, 'score': float, 'metadata': dict, 'retriever': 'bm25'}]
    # score: BM25 thô (>=0, KHÔNG chuẩn hoá [0,1]), sorted desc, loại bỏ score == 0
def tfidf_search(query: str, top_k: int = 10) -> list[dict]: ...   # bonus +5

# src/task7_reranking.py
def rerank_rrf(ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60) -> list[dict]: ...
def rerank(query: str, candidates: list[dict], top_k: int = 5, method: str = "rrf") -> list[dict]: ...

# src/task8_pageindex_vectorless.py
def pageindex_search(query: str, top_k: int = 5) -> list[dict]: ...
    # -> [{'content': str, 'score': float, 'metadata': dict, 'source': 'pageindex'}]
```

### 4 điều khoản bắt buộc

**(a) `rerank_rrf` giữ lại điểm gốc.**
```python
{'content': ..., 'score': <điểm RRF>, 'original_score': <điểm gốc của ranker đầu tiên chứa nó>,
 'retriever': 'bm25'|'dense', 'metadata': {...}}
```
`score` = điểm RRF (để `test_rerank_has_score` pass và để Task 9 sắp xếp), `original_score` giữ lại làm đường lùi. **Task 9 vẫn phải dùng `dense_results[0]["score"]` (cosine gốc, chưa fuse) để so `SCORE_THRESHOLD`** — bẫy đã ghi ở [README:328-333](README.md#L328-L333) và LAB_GUIDE mục 5 lỗi #4.

**(b) Không hàm nào của Role 4 được raise khi thiếu tài nguyên.** [task9:28-31](src/task9_retrieval_pipeline.py#L28-L31) import cả 3 module ở top-level; nếu `task6` load corpus lúc import mà thiếu tài nguyên → Task 9 + Task 10 + `app.py` sập ngay khi import. Quy tắc: lazy init + cache global, thiếu corpus → trả `[]` + warning, thiếu `PAGEINDEX_API_KEY` → trả `[]`.

**(c) 🔴 Chunk phải khớp tuyệt đối với Task 4.** `rerank_rrf` gộp bằng khoá `content`. Nếu Task 6 chunk khác Task 4 → không chunk nào trùng → RRF suy biến thành "nối 2 danh sách", hybrid mất ý nghĩa mà không báo lỗi.
> **Giải pháp:** khi có `chroma_db/`, Task 6 đọc corpus **trực tiếp từ collection** (`collection.get(include=["documents","metadatas"])`).
> **Cần Role 1/3 chốt:** `CHUNK_SIZE` = **500/50** ([task4:44-45](src/task4_chunking_indexing.py#L44-L45)) hay **800/100** (LAB_GUIDE CP2)? Hai tài liệu mâu thuẫn. Với corpus 15.8K ký tự, **500/50 hợp lý hơn** (36 chunk vs 20 chunk).

**(d) 🆕 Giữ metadata `school` và `category`.** JSON news đã có sẵn `school` (HUST/NEU/HUCE) và `category` (`hoc_bong`, ...). Nếu Task 4 giữ được 2 field này vào chunk metadata, Role 4 sẽ làm được **metadata boost** (query chứa "HUST" → ưu tiên chunk `school=HUST`) — nâng chất lượng rõ rệt vì corpus có 3 trường nội dung song song rất giống nhau, rất dễ trả nhầm trường. File legal không có metadata → Role 4 tự parse từ tên file (`...-hust.md` → `HUST`) trong corpus resolver.

---

## 3. Kế hoạch theo giai đoạn (đã cập nhật — bỏ toàn bộ phần chờ đợi)

### 🟢 Phase 0 — Làm được ngay, không phụ thuộc ai (≈70 phút)

| # | Việc | Output | Ước lượng |
| :- | :--- | :--- | :--- |
| 0.1 | Đăng ký **pageindex.ai**, verify email, lấy API key → `.env` | `PAGEINDEX_API_KEY` | 10' |
| 0.2 | `pip install -r requirements.txt`; verify `rank_bm25`, `sklearn`, `pageindex`; `$env:PYTHONIOENCODING="utf-8"` | Import sạch | 5' |
| 0.3 | Gửi **mục 1.1 + 1.4 + hợp đồng mục 2** cho Role 1/2 — 3 việc cần họ xử lý: sinh lại PDF có dấu, thêm 1 doc tiếng Anh, chốt `CHUNK_SIZE` | Nhóm thống nhất | 10' |
| 0.4 | **Hoàn thành trọn vẹn Task 7** (mục 4.2) | 6đ chốt sổ | 25' |
| 0.5 | Viết `dev/smoke_role4.py`: BM25 → TF-IDF → RRF, in bảng so sánh top-5 + đếm overlap | Script demo CP6 | 15' |

> ~~0.4 cũ: tạo mock corpus~~ — **bỏ**, đã có 16 file .md thật.
> ~~0.7 cũ: tự tải PDF test~~ — **bỏ**, đã có 6 PDF thật.
> `dev/` là thư mục riêng của Role 4, không đụng `data/` (địa phận Role 2).

### 🟡 Phase 1 — Task 6 trên dữ liệu thật (≈35 phút, làm được NGAY)
- Corpus resolver tầng 2 (`data/standardized/**/*.md` + tự chunk 500/50) → BM25 chạy trên 36 chunk thật.
- Tokenizer fold dấu (mục 4.1) → verify: `lexical_search("học bổng loại A")` **phải trả về CẢ** chunk legal lẫn news. Đây là bài test quan trọng nhất của Task 6.
- `tfidf_search()` cho bonus.
- `pytest tests/test_individual.py::TestTask6 -v`.

### 🟠 Phase 2 — Task 8 trên 6 PDF thật (≈25 phút, làm được NGAY)
- Upload 6 PDF ở `data/landing/legal/`, cache `doc_id`.
- Parse `retrieved_nodes`, trả `source: "pageindex"`.

### 🔵 Phase 3 — Khi `chroma_db/` + Task 5 xong
- Chuyển resolver sang tầng 1 (ChromaDB), verify `len(bm25_corpus) == collection.count()`.
- Đo **overlap dense∩sparse**; overlap = 0 → báo động đỏ (điều khoản 2c).
- Đo và bàn giao bảng calibrate `SCORE_THRESHOLD` cho Role 1 (mục 4.4).

### 🟣 Phase 4 — Tích hợp & demo
- Hỗ trợ Role 1 ráp Task 9; hỗ trợ Role 6 chạy A/B `hybrid+rerank` vs `dense-only`.
- Chuẩn bị 3 phút "BM25 vs TF-IDF" → **+5 bonus**.

---

## 4. Thiết kế chi tiết

### 4.1 Task 6 — Lexical Search (6 điểm)

**Corpus resolver (3 tầng, tự động degrade):**
```
1. ChromaDB collection "university_services_docs"        ← chuẩn nhất, khớp Task 4 (2c)
2. data/standardized/**/*.md + tự chunk 500/50           ← DÙNG NGAY HÔM NAY (16 file, ~36 chunk)
3. (không có gì) → trả [] + warning, KHÔNG raise
```
Ở tầng 2, tự bồi metadata: `source` = tên file, `type` = `legal|news`, `school` parse từ tên file (`-hust`/`-neu`/`-huce`) hoặc từ JSON gốc ở `data/landing/news/` (điều khoản 2d).

**🔴 Tokenizer fold dấu — thay đổi lớn nhất so với kế hoạch cũ, sửa trực tiếp vấn đề 1.1:**

```python
import re, unicodedata

_MARKS    = re.compile(r"[\u0300-\u036f]")            # dấu thanh + dấu mũ tổ hợp
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[./\-][a-z0-9]+)*")

def fold(text: str) -> str:
    """Chuẩn hoá về ASCII không dấu — dùng cho CẢ corpus lẫn query."""
    text = text.replace("\\", " ")                     # bỏ escape "\(" của MarkItDown
    text = text.replace("đ", "d").replace("Đ", "D")    # đ/Đ KHÔNG tách được bằng NFD
    text = unicodedata.normalize("NFD", text)
    text = _MARKS.sub("", text)
    return unicodedata.normalize("NFC", text).lower()

def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(fold(text))
```

Vì sao từng dòng:
- **`replace("đ","d")` phải đứng riêng** — `đ` (U+0111) là ký tự nguyên khối, NFD **không** tách nó thành `d` + dấu. Bỏ dòng này thì `"đăng ký"` → `"dang"` + `"ky"` ở news nhưng legal viết `"dang ky"` → vẫn khớp, còn `"điểm"` → `"điem"` (còn `đ`) ≠ `"diem"` → **trượt**. Đây là lỗi rất dễ bỏ sót.
- **`NFD` + strip marks** xử lý được cả `ă â ê ô ơ ư` (đều tách thành base + combining mark trong dải `U+0300–U+036F`).
- **`replace("\\", " ")`** — legal .md chứa `\(HUST\)` do MarkItDown escape; không bỏ backslash thì token thành `\(hust\)`.
- **Regex cho phép `. / -` ở giữa** → giữ nguyên `28.000.000`, `1024/qd-dhbk`, `3.6`, `28/11/2025`, `7h30` làm **một token** — chính là các thực thể BM25 thắng dense (mục 1.3).
- **Trả về `content` GỐC** (có dấu), chỉ fold ở tầng index/query. Không được trả text đã fold cho Task 10, kẻo LLM sinh citation mất dấu.

**Test bắt buộc tự viết (quan trọng hơn test chấm điểm):**
```python
r = lexical_search("học bổng loại A xuất sắc", top_k=10)
types = {x["metadata"]["type"] for x in r}
assert "legal" in types and "news" in types   # ← chứng minh đã vá được vấn đề 1.1
assert lexical_search("hoc bong loai A")[0]["content"] == r[0]["content"]  # ← bất biến với dấu
```

**Index & search:** `BM25Okapi(tokenized_corpus, k1=1.5, b=0.75)`, cache global build 1 lần; loại `score <= 0`; sort desc; cắt `top_k`; gắn `retriever: "bm25"`.

**Bonus +5 — `tfidf_search()`:** `scikit-learn` đã có sẵn trong `requirements.txt`. Dùng `TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5), preprocessor=fold)` — char n-gram chịu được cả corpus lệch dấu lẫn lỗi gõ thiếu dấu của người dùng.
**Nội dung trình bày lấy điểm:** TF-IDF chấm tuyến tính theo tần suất → văn bản dài luôn thắng. BM25 thêm (1) **term saturation** qua `k1=1.5` — lần lặp thứ 10 của từ khoá gần như không tăng điểm, (2) **length normalization** qua `b=0.75` — phạt văn bản dài theo `|d|/avgdl`. Corpus của nhóm có độ dài chunk lệch nhau (legal 679–1096 ký tự không heading vs news 969–1328 có heading) nên khác biệt này thấy rõ.

**Definition of Done:** 2 assert ở trên pass + `TestTask6` không có test nào **fail** (chấp nhận skip do vấn đề 1.4 nếu Role 2 chưa thêm doc tiếng Anh) + `lexical_search("1024/QD-DHBK")` trả đúng file quy định HUST.

---

### 4.2 Task 7 — Reranking (6 điểm) — **LÀM TRƯỚC TIÊN**

**`rerank_rrf(ranked_lists, top_k, k=60)`** — `RRF(d) = Σ 1/(k + rank_r(d))`
- Khoá gộp: `content.strip()` (chống lệch khoảng trắng đầu/cuối giữa 2 nguồn).
- Giữ `original_score` + `retriever` của lần gặp đầu (điều khoản 2a).
- Xử lý biên: `ranked_lists=[]`, list rỗng, item thiếu `content` → trả `[]`.

**`rerank()` — dispatcher phải chạy được với `method="rrf"` mặc định.** Stub hiện raise `NotImplementedError` cho cả `rrf` lẫn `mmr` ([task7:179-182](src/task7_reranking.py#L179-L182)), trong khi `test_rerank_returns_list` gọi đúng đường mặc định đó:
```python
def rerank(query, candidates, top_k=5, method="rrf"):
    if method == "rrf":
        groups = _group_by_retriever(candidates) or [candidates]
        return rerank_rrf(groups, top_k=top_k)
    ...
```

**`rerank_cross_encoder()`:** có `JINA_API_KEY` → `jina-reranker-v2-base-multilingual`; không có → local `CrossEncoder` (`BAAI/bge-reranker-v2-m3`) hoặc degrade về RRF kèm log — **không raise** (2b).
> Lưu ý riêng với corpus này: cross-encoder cũng bị vấn đề 1.1 làm giảm chất lượng trên 6 file legal không dấu. Nếu demo cross-encoder, nên demo trên chunk news.

**`rerank_mmr()`:** `lambda_param=0.7`. Corpus có **3 trường nói cùng một chủ đề** (học phí/học bổng HUST + NEU + HUCE, nội dung gần trùng) → không có MMR thì top-5 rất dễ là 5 biến thể của cùng một nội dung. Đây là ví dụ MMR đắt giá để demo. Chưa có embedding từ Task 4 → vector hoá tạm bằng `TfidfVectorizer` để test ngay.

**Definition of Done:** `TestTask7` 3/3 passed + `python -m src.task7_reranking` in ra kết quả đã re-sort.

---

### 4.3 Task 8 — PageIndex Vectorless Fallback (4 điểm)

**Nguồn upload: 6 PDF sẵn có ở `data/landing/legal/`** — không cần convert markdown→PDF nữa, tránh hẳn cái bẫy font fpdf2.

Đánh giá chất lượng đầu vào:
- ✅ PDF text-based (1.3–1.8 KB), trích xuất được.
- ✅ Có cấu trúc `MUC 1:` / `MUC 2:` / `MUC 3:` → đủ để PageIndex dựng cây mục lục.
- ⚠️ **Nội dung không dấu** (vấn đề 1.1) → kết quả PageIndex trả về sẽ không dấu, chảy thẳng vào citation của Task 10. Cần **nói rõ trong demo** hoặc chờ Role 2 sinh lại PDF rồi re-upload.
- ⚠️ Mỗi PDF rất ngắn → cây mục lục nông, lợi thế "vectorless structural retrieval" khó thể hiện. Cân nhắc **upload thêm 2–3 PDF sinh từ news .md** (news có 4–5 heading/file + đủ dấu) bằng `fpdf2` **kèm font Unicode**: `pdf.add_font("DejaVu", fname="C:/Windows/Fonts/arial.ttf"); pdf.set_font("DejaVu")` — bỏ bước add_font là mất dấu y hệt lỗi của Role 2.

**4 bẫy còn lại:**
1. **API `/retrieval` deprecated** (vẫn chạy, response có field `"deprecation"`). Kết quả ở `retrieved_nodes[].relevant_contents[][]` — list lồng 2 tầng, mỗi item có `section_title` + `relevant_content`. → **In `json.dumps(resp, indent=2, ensure_ascii=False)` trước khi viết parser**, đừng đoán schema.
2. **PageIndex không trả score** → tự gán giảm dần theo rank (`1.0 - 0.05*i`) cho đồng nhất format.
3. **Upload bất đồng bộ + tốn quota** → cache `{filename: doc_id}` vào `data/pageindex_docs.json`, upload **một lần**; không bao giờ upload bên trong `pageindex_search()`.
4. **Phải poll** đến `status == "completed"` mới có kết quả.

**Phương án dự phòng nếu PageIndex không dùng được:** tự implement **local tree-search vectorless** đúng tinh thần thuật toán PageIndex — dựng cây từ heading markdown, cho LLM chọn nhánh theo tiêu đề, trả nội dung node. Lưu ý: **chỉ 10 file news có heading**, 6 file legal không có → cây chỉ dựng được trên news, phải fallback tiếp sang tên file cho legal. Đánh dấu `metadata={"engine": "local-tree-search"}` và **nói rõ trong demo là bản tự implement**.

**Definition of Done:** `pageindex_search("học bổng Trần Đại Nghĩa", top_k=3)` trả ≥1 kết quả có `source == "pageindex"`; xoá API key vẫn trả `[]` không raise.

---

### 4.4 Bàn giao cho Task 9 — bảng calibrate threshold

`SCORE_THRESHOLD = 0.3` trong stub là **giá trị mẫu, không được copy** ([task9:38-40](src/task9_retrieval_pipeline.py#L38-L40)). Role 4 chủ động đo và bàn giao cho Role 1 (chạy ở Phase 3):

| Nhóm query | Ví dụ **theo corpus thật** | Cosine gốc `semantic_search` |
| :--- | :--- | :--- |
| Chắc chắn liên quan (5 câu) | "Điều kiện học bổng loại A ở HUST", "Học phí chương trình ELITECH", "Đăng ký phòng học nhóm thư viện NEU" | đo → lấy _min_ |
| Cùng lĩnh vực nhưng ngoài corpus (3 câu) | "Điểm chuẩn ngành CNTT Bách Khoa 2024" ⟵ *corpus không có điểm chuẩn (mục 1.3)*, "Học phí ĐH Y Hà Nội" | đo |
| Hoàn toàn lạc đề (3 câu) | "cách nấu phở bò", "xyzabc123nonsense" | đo → lấy _max_ |

→ Chọn ngưỡng nằm giữa `min(nhóm liên quan)` và `max(nhóm lạc đề)`. LAB_GUIDE gợi ý 0.48 cho corpus RMIT tiếng Anh; corpus tiếng Việt (nửa có dấu nửa không) + bge-m3 chắc chắn cho dải khác — **phải đo lại**.
> Nhóm giữa rất đáng đo với corpus này: câu hỏi về **điểm chuẩn** nghe rất "đúng chủ đề" nhưng corpus không hề có → đây chính là ca fallback PageIndex nên kích hoạt, và là ví dụ thuyết phục nhất để demo ở CP6.

---

## 5. Rủi ro & phương án (đã cập nhật)

| # | Rủi ro | Trạng thái | Phương án |
| :-: | :--- | :--- | :--- |
| 1 | ~~Role 2 trễ, không có corpus~~ | ✅ **Đã giải quyết** | Task 1/2/3 xong, 16 file .md sẵn sàng |
| 2 | **Corpus lệch dấu legal/news** | 🔴 **Đang xảy ra** | Tầng 1: fold-tokenizer (Role 4, ngay). Tầng 2: Role 2 sinh lại PDF font Unicode |
| 3 | **Test tiếng Anh bị skip** | 🟠 **Đang xảy ra** | Role 2 thêm 1 doc tiếng Anh (mục 1.4) |
| 4 | Corpus quá nhỏ so với `top_k` | 🟠 Đang xảy ra | Chốt `DEFAULT_TOP_K=3~4`, `lexical_search top_k=5` |
| 5 | RRF overlap = 0 do lệch chunk | ⏳ Chưa verify được | Điều khoản 2c + đếm overlap trong `smoke_role4.py` khi có chroma |
| 6 | Task 9/app.py sập vì import | ⏳ Phòng ngừa | Điều khoản 2b: lazy init, không raise |
| 7 | PageIndex hết quota / không kịp | ⏳ Phòng ngừa | Local tree-search (mục 4.3) |
| 8 | Nội dung không khớp chủ đề 4 | 🟡 Cần nhóm quyết | Bổ sung dữ liệu điểm chuẩn **hoặc** đổi phạm vi sản phẩm (mục 1.3) |
| 9 | `UnicodeEncodeError` khi print tiếng Việt | ⏳ Phòng ngừa | `$env:PYTHONIOENCODING="utf-8"` |
| 10 | Lỗi relative import | ⏳ Phòng ngừa | Luôn chạy `python -m src.task6_lexical_search` |

---

## 6. Checklist theo Checkpoint

**CP0** — ☐ `pip install -r requirements.txt` ☐ verify `rank_bm25`/`sklearn`/`pageindex` ☐ **đăng ký pageindex.ai lấy API key ngay** ☐ `PYTHONIOENCODING=utf-8`

**CP1** — ☐ **Gửi Role 1/2: (i) lỗi mất dấu PDF, (ii) thiếu doc tiếng Anh, (iii) chốt CHUNK_SIZE + giữ metadata `school`** ☐ **Hoàn thành Task 7 + pass `TestTask7`**

**CP2** — ☐ Tokenizer fold dấu + 2 assert ở mục 4.1 ☐ Corpus resolver ☐ `lexical_search()` + cache ☐ `tfidf_search()` (bonus) ☐ Chạy `TestTask6`

**CP3** — ☐ Upload 6 PDF lên PageIndex + cache `doc_id` ☐ `pageindex_search()` parse `retrieved_nodes` ☐ Pass `TestTask8` ☐ Test query "điểm chuẩn" để chắc fallback kích hoạt

**CP4** — ☐ Chuyển resolver sang ChromaDB, verify số chunk khớp ☐ Đếm overlap dense∩sparse > 0 ☐ Bàn giao bảng threshold cho Role 1 ☐ `pytest tests/ -v`

**CP5** — ☐ A/B `hybrid+rerank` vs `dense-only` cùng Role 6 ☐ Cung cấp số liệu + **ghi rõ hạn chế corpus lệch dấu** vào `results.md`

**CP6** — ☐ Demo BM25 vs TF-IDF (`k1` saturation, `b` length-norm) → **+5 bonus** ☐ Demo fold-tokenizer cứu corpus lệch dấu (câu chuyện kỹ thuật mạnh nhất của nhóm) ☐ Sẵn sàng trả lời: vì sao `k=60`, vì sao không dùng điểm RRF làm ngưỡng fallback

---

## 7. Lệnh chạy nhanh

```powershell
$env:PYTHONIOENCODING="utf-8"

# Test riêng phần Role 4
pytest tests/test_individual.py::TestTask6 tests/test_individual.py::TestTask7 tests/test_individual.py::TestTask8 -v

# Chạy từng module (luôn dùng -m vì task9 dùng relative import)
python -m src.task6_lexical_search
python -m src.task7_reranking
python -m src.task8_pageindex_vectorless

# Smoke test tổng hợp
python -m dev.smoke_role4
```

---

## 8. Thứ tự thực thi (tóm tắt)

**Task 7 (6đ, thuần hàm) → Task 6 trên `data/standardized/` + fold-tokenizer (6đ) → Task 8 upload 6 PDF (4đ) → khi có `chroma_db/` thì đổi resolver sang tầng 1 + verify overlap → bàn giao threshold cho Task 9 → bonus TF-IDF.**

**3 việc phải đẩy sang Role 1/2 ngay trong CP1** (Role 4 không tự làm được):
1. Sinh lại 6 PDF legal với font Unicode → khôi phục dấu tiếng Việt (mục 1.1)
2. Thêm 1 tài liệu tiếng Anh → cứu `TestTask5` + `TestTask6` khỏi bị skip (mục 1.4)
3. Chốt `CHUNK_SIZE`, chọn `RecursiveCharacterTextSplitter`, giữ metadata `school`/`category` (mục 1.2, 2c, 2d)
