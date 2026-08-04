# 📤 BÀN GIAO TỪ ROLE 4 → ROLE 1 / ROLE 2 / ROLE 3

Role 4 đã hoàn thành **Task 6, 7, 8**. Dưới đây là những gì các role khác cần biết và cần làm.

---

## 🔴 KHẨN: dữ liệu Task 1/2/3 đã biến mất

Lúc 10:23 sáng nay `data/` còn đầy đủ:
- `data/landing/legal/` — 6 file PDF
- `data/landing/news/` — 10 file JSON
- `data/standardized/` — 16 file `.md` (tổng 15.837 ký tự)

Đến khoảng 11:10 thì **toàn bộ đã bị xoá**, chỉ còn lại các file `.gitkeep`. Đã quét toàn
bộ cây thư mục `LabDay08` — file không bị di chuyển đi đâu, mà bị xoá hẳn.

**Ai đang chạy lại Task 1/2/3 xin xác nhận.** Repo **không phải git repository** (không có
`.git`) nên không khôi phục được bằng `git checkout`.

👉 **Đề xuất làm ngay: `git init` + commit lần đầu.** Không có version control thì mỗi lần
chạy lại script crawl là một lần có nguy cơ mất trắng dữ liệu, và yêu cầu chấm điểm cũng
bắt buộc "code push lên repository chung của nhóm".

---

## ✅ Trạng thái code của Role 4

| Task | File | Trạng thái | Test |
| :-- | :--- | :--- | :--- |
| 6 | `src/task6_lexical_search.py` | ✅ Xong (BM25 + TF-IDF) | 1 passed, 3 skipped¹ |
| 7 | `src/task7_reranking.py` | ✅ Xong (RRF + MMR + cross-encoder) | 3/3 passed |
| 8 | `src/task8_pageindex_vectorless.py` | ✅ Xong (upload + query + cache) | 2/2 passed |

¹ 3 test skip vì corpus rỗng, **không phải vì code lỗi**. Đã verify đầy đủ trên corpus thật
trước khi dữ liệu bị xoá: 44 chunk, BM25 trả kết quả đúng cho cả query tiếng Việt có dấu
lẫn không dấu.

Chạy kiểm tra bất cứ lúc nào:
```powershell
$env:PYTHONIOENCODING="utf-8"
python -m dev.smoke_role4
```

---

## 📄 Hợp đồng API — code theo đúng chữ ký này

```python
# Task 6
lexical_search(query: str, top_k: int = 10) -> list[dict]
    # [{'content', 'score' (BM25 thô, KHÔNG chuẩn hoá [0,1]), 'metadata', 'retriever': 'bm25'}]
tfidf_search(query: str, top_k: int = 10) -> list[dict]     # bonus, để so sánh khi demo
fold(text) / tokenize(text)                                 # dùng chung được cho module khác

# Task 7
rerank_rrf(ranked_lists: list[list[dict]], top_k=5, k=60) -> list[dict]
rerank(query, candidates, top_k=5, method="rrf") -> list[dict]   # nhận list PHẲNG

# Task 8
pageindex_search(query: str, top_k: int = 5) -> list[dict]
    # [{'content', 'score', 'metadata', 'source': 'pageindex'}]
```

**Cam kết:** không hàm nào raise khi thiếu tài nguyên — thiếu corpus / thiếu API key đều
trả `[]`. Đã test 7 tình huống biên (mục 6 của `smoke_role4.py`). Yên tâm import ở
top-level trong `task9`.

### ⚠️ Dành riêng cho Role 1 (Task 9)

`rerank_rrf` trả về mỗi item kèm 2 trường:
```python
{'score': <điểm RRF>, 'original_score': <điểm gốc của ranker đầu tiên>, 'retrievers': [...]}
```
**Để quyết định fallback, dùng `dense_results[0]["score"]` (cosine gốc từ Task 5), TUYỆT ĐỐI
KHÔNG dùng điểm RRF.** Điểm RRF top-1 luôn ≈ `1/(60+1)` = 0.0164 bất kể nội dung có liên
quan hay không → so với `SCORE_THRESHOLD` thì fallback không bao giờ kích hoạt.

---

## 📌 3 việc Role 4 KHÔNG tự làm được, cần các role khác xử lý

### 1️⃣ Role 2 — sinh lại PDF với font Unicode (ưu tiên cao)

6 file PDF ở `data/landing/legal/` **mất toàn bộ dấu tiếng Việt**. Đã kiểm chứng:
0/6 file legal có dấu, 10/10 file news có dấu.

```
legal:  "MUC 2: Chinh sach Hoc bong Khuyen khich Hoc tap"
news:   "## 1. Đối tượng và Điều kiện xét Học bổng KKHT"
```

Nguyên nhân: `fpdf2` dùng font mặc định (Helvetica/latin-1) không encode được tiếng Việt.
Cách sửa:
```python
pdf.add_font("uni", "", "C:/Windows/Fonts/arial.ttf")   # BẮT BUỘC, thiếu dòng này là mất dấu
pdf.set_font("uni", size=11)
```
(Có sẵn hàm tham khảo `markdown_to_pdf()` trong `src/task8_pageindex_vectorless.py`.)

> Role 4 đã vá được phía **lexical** bằng fold-tokenizer (chuẩn hoá cả corpus lẫn query về
> không dấu) nên BM25 vẫn chạy đúng. Nhưng **dense search của Task 5 thì không vá được như
> vậy** — embedding của `"hoc phi"` không đồng nhất với `"học phí"`. Chỉ sửa từ gốc mới
> triệt để.

### 2️⃣ Role 2 — thêm 1 tài liệu tiếng Anh

`tests/test_individual.py` dùng query tiếng Anh (`"tuition fee"`, `"scholarship eligibility"`,
`"library study room"`). Corpus cũ không có từ nào trong số đó → **3 test của Task 6 và các
test tương ứng của Task 5 đều bị SKIP**, không đạt mốc "35/35 test passed" ở CP4.

Chỉ cần **1 bài** trang tiếng Anh của HUST/NEU về *"International Student Tuition Fees &
Scholarships"* là cứu được cả Task 5 lẫn Task 6. Tốn ~5 phút.

### 3️⃣ Role 1 + Role 3 — chốt tham số Task 4

| Việc | Lý do |
| :--- | :--- |
| Chốt `CHUNK_SIZE`: **500/50** hay 800/100? | `task4` ghi 500/50, LAB_GUIDE ghi 800/100 — mâu thuẫn. Task 6 đang import trực tiếp từ `task4` nên **chỉ cần sửa ở `task4` là Task 6 tự theo**. |
| Dùng `RecursiveCharacterTextSplitter` | 6 file legal **không có heading markdown nào** → `MarkdownHeaderTextSplitter` sẽ để nguyên mỗi file thành 1 chunk, lệch hẳn so với news (4–5 heading/file). |
| Giữ metadata `school` + `category` vào chunk | JSON news đã có sẵn. Corpus có 3 trường (HUST/NEU/HUCE) nội dung rất giống nhau → rất dễ trả nhầm trường. Có metadata thì lọc/boost được. |
| Cân nhắc `DEFAULT_TOP_K = 3~4` thay vì 5 | Corpus chỉ ~44 chunk. Task 9 gọi `top_k*2` cho cả 2 retriever = 20/44 ≈ 45% toàn corpus → hybrid gần như mất khả năng phân biệt. |

---

## 🔍 Việc Role 4 sẽ làm tiếp khi `chroma_db/` sẵn sàng

1. Chuyển corpus resolver từ tầng 2 (markdown) sang **tầng 1 (ChromaDB)** — code đã viết sẵn,
   tự động nhận diện, không cần sửa gì.
2. Verify `len(BM25 corpus) == collection.count()`.
3. **Đo overlap giữa ranked list dense và sparse.** Nếu overlap = 0 thì RRF suy biến thành
   "nối 2 danh sách" — hybrid search mất hết ý nghĩa mà không hề báo lỗi. `smoke_role4.py`
   mục 5 đã có sẵn cảnh báo này.
4. Đo và bàn giao bảng calibrate `SCORE_THRESHOLD` cho Role 1.

---

## ⚠️ Ghi chú về PageIndex (Task 8)

- `PAGEINDEX_API_KEY` trong `.env` đã hoạt động (verify bằng `list_documents()` → HTTP 200).
- **Chưa upload được document nào** vì PDF nguồn đã bị xoá. Chạy lại sau khi có PDF:
  ```powershell
  python -m src.task8_pageindex_vectorless
  ```
  Doc_id được cache vào `data/pageindex_docs.json` → chỉ upload một lần, không tốn quota lặp.
- Khi Role 2 sinh lại PDF **có dấu**, nhớ chạy lại với `upload_documents(force=True)` để
  thay bản không dấu đang lưu trên PageIndex.
