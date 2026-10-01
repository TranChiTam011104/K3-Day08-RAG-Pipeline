# RAG Evaluation Results

> Sinh tự động bởi `python -m group_project.evaluation.eval_pipeline` lúc 2026-08-04 16:17.

## Framework sử dụng

**RAGAS 0.1.21**

- Judge LLM: `gpt-4o-mini` (temperature 0)
- Judge embeddings: `text-embedding-3-small`
- Golden dataset: 18 cặp Q&A, `top_k=5`
- Generation: Task 10 `generate_with_citation()` giữ nguyên cho cả hai config; chỉ tầng retrieval được thay.

---

## Overall Scores

| Metric | Config A (hybrid + rerank) | Config B (dense-only) | Δ (A−B) | Mẫu chấm được |
|--------|---------------------------|----------------------|---------|---------------|
| Faithfulness | 0.915 | 0.704 | +0.211 | A 18/18 · B 18/18 |
| Answer Relevance | 0.592 | 0.491 | +0.101 | A 18/18 · B 18/18 |
| Context Recall | 1.000 | 0.944 | +0.056 | A 18/18 · B 18/18 |
| Context Precision | 0.945 | 0.882 | +0.062 | A 18/18 · B 18/18 |
| **Average** | 0.863 | 0.755 | +0.107 | — |

> ✅ Cả 4 metric đều chấm được đủ 18/18 mẫu ở cả hai config.

---

## A/B Comparison Analysis

**Config A — hybrid (dense + BM25) + RRF rerank**

> Task 9 đầy đủ: semantic_search (OpenAI text-embedding-3-small) chạy song song lexical_search (BM25 fold dấu), fuse bằng RRF k=60, rerank RRF, có nhánh fallback PageIndex khi best cosine < 0.3.

**Config B — dense-only, không rerank**

> Chỉ Task 5 semantic_search với cùng embedding model và cùng top_k. Không BM25, không RRF, không rerank, không fallback.

**Retrieval hit-rate** (ít nhất 1 tài liệu kỳ vọng lọt vào top-5): Config A `18/18` · Config B `15/18`

**Latency trung bình / câu** (retrieval + generation): Config A `2.44s` · Config B `1.94s`

> ✅ Không câu nào hỏng vì rate limit ở cả hai config — chênh lệch điểm phản ánh đúng khác biệt về retrieval.

<!-- ANALYSIS:CONCLUSION:START -->
**Kết luận: Config A tốt hơn trên cả 4 metric, và nguyên nhân nằm ở một chỗ rất cụ thể — tài liệu pháp quy không dấu.**

Toàn bộ khoảng cách A/B đến từ đúng 3 câu mà Config B trượt: **Q08, Q10, Q16 — cả ba đều là `doc_type=legal`, cả ba đều `MISS`**. 15 câu còn lại hai config gần như ngang nhau. Config B không hề kém đều; nó thủng đúng một chỗ.

Lý do: 6 file legal được trích từ PDF ra dạng **không dấu** (`"Sinh vien bi canh bao hoc tap 3 lan lien tiep se bi buoc thoi hoc"`), trong khi người dùng hỏi bằng tiếng Việt có dấu đầy đủ. Embedding `text-embedding-3-small` không bắc được cầu giữa *"cảnh báo học tập"* và *"canh bao hoc tap"*, nên dense-only xếp toàn `article_*.md` lên top-5 và bỏ sót hoàn toàn văn bản pháp quy. BM25 của Config A thì `fold()` bỏ dấu trước khi index nên khớp chính xác — đây là lý do hybrid thắng, và là lý do rất riêng của corpus tiếng Việt này chứ không phải lợi ích lý thuyết chung chung của hybrid search.

Hệ quả dây chuyền đáng chú ý: khi Config B trượt evidence, Task 10 **từ chối trả lời** (đúng thiết kế, không bịa) → RAGAS gắn cờ `noncommittal` → `answer_relevancy = 0` và `faithfulness = 0`. Nên `faithfulness` tụt 0.211 không có nghĩa Config B "bịa nhiều hơn" — nó có nghĩa Config B **im lặng nhiều hơn**. Guardrail hoạt động đúng; thứ hỏng là retrieval.

Cái giá phải trả: Config A chậm hơn **+0.50s/câu (2.44s vs 1.94s, +26%)** do chạy thêm BM25 và RRF. Đổi 0,5 giây lấy 3/18 câu từ "không trả lời được" thành "trả lời đúng" là đáng, nên **chọn Config A cho sản phẩm**.
<!-- ANALYSIS:CONCLUSION:END -->

---

## Điểm chi tiết từng câu (Config A)

| ID | Trường | Loại | Faith. | Relev. | Recall | Prec. | Hit | Nguồn truy xuất top-1 |
|----|--------|------|--------|--------|--------|-------|-----|----------------------|
| Q01 | HUST | news | 1.000 | 0.627 | 1.000 | 0.887 | ✅ | `article_01.md` |
| Q02 | HUST | news | 0.800 | 0.664 | 1.000 | 1.000 | ✅ | `article_01.md` |
| Q03 | HUST | news | 1.000 | 0.585 | 1.000 | 1.000 | ✅ | `article_01.md` |
| Q04 | HUST | legal | 1.000 | 0.534 | 1.000 | 1.000 | ✅ | `article_02.md` |
| Q05 | HUST | news | 1.000 | 0.717 | 1.000 | 1.000 | ✅ | `article_02.md` |
| Q06 | HUST | news | 1.000 | 0.707 | 1.000 | 1.000 | ✅ | `article_02.md` |
| Q07 | HUST | news | 1.000 | 0.702 | 1.000 | 1.000 | ✅ | `article_03.md` |
| Q08 | HUST | legal | 1.000 | 0.547 | 1.000 | 0.950 | ✅ | `article_03.md` |
| Q09 | HUST | legal | 0.000 | 0.511 | 1.000 | 0.700 | ✅ | `quy-che-dao-tao-dai-hoc-hust.md` |
| Q10 | HUST | legal | 1.000 | 0.555 | 1.000 | 1.000 | ✅ | `article_02.md` |
| Q11 | NEU | news | 1.000 | 0.359 | 1.000 | 1.000 | ✅ | `article_04.md` |
| Q12 | NEU | news | 0.667 | 0.554 | 1.000 | 0.950 | ✅ | `article_04.md` |
| Q13 | NEU | news | 1.000 | 0.556 | 1.000 | 1.000 | ✅ | `article_05.md` |
| Q14 | NEU | news | 1.000 | 0.637 | 1.000 | 1.000 | ✅ | `article_07.md` |
| Q15 | NEU | news | 1.000 | 0.644 | 1.000 | 0.887 | ✅ | `article_07.md` |
| Q16 | NEU | legal | 1.000 | 0.518 | 1.000 | 0.679 | ✅ | `article_04.md` |
| Q17 | HUCE | news | 1.000 | 0.596 | 1.000 | 0.950 | ✅ | `article_08.md` |
| Q18 | HUCE | news | 1.000 | 0.648 | 1.000 | 1.000 | ✅ | `article_09.md` |

---

## Worst Performers (Bottom 3 — Config A)

| # | Question | Faithfulness | Relevance | Recall | Precision | Failure Stage |
|---|----------|-------------|-----------|--------|-----------|---------------|
| 1 | Q09 — Chuẩn đầu ra tiếng Anh của sinh viên đại học chính quy Bách Khoa Hà Nộ… | 0.000 | 0.511 | 1.000 | 0.700 | Ranking — evidence bị đẩy xuống dưới |
| 2 | Q12 — Sinh viên NEU nộp hồ sơ miễn giảm học phí ở địa điểm nào và trước thời… | 0.667 | 0.554 | 1.000 | 0.950 | Generation — câu trả lời không bám context |
| 3 | Q16 — Điểm trung bình tích lũy toàn khóa tối thiểu để sinh viên NEU được xét… | 1.000 | 0.518 | 1.000 | 0.679 | Ranking — evidence bị đẩy xuống dưới |

<!-- ANALYSIS:ROOT_CAUSE:START -->
### Q09 — `faithfulness = 0.000` nhưng câu trả lời **đúng**

Đây là ca quan trọng nhất vì nó cho thấy bảng điểm không được đọc mù quáng.

> **Câu trả lời:** "Chuẩn đầu ra tiếng Anh cho sinh viên đại học chính quy Bách Khoa Hà Nội là TOEIC 500 hoặc IELTS 5.5 trở lên. [Source: quy-che-dao-tao-dai-hoc-hust.md]"
> **Ground truth:** "Chuẩn đầu ra tiếng Anh là TOEIC 500 hoặc IELTS 5.5 trở lên."

Trùng khớp hoàn toàn, trích dẫn đúng nguồn, `context_recall = 1.000`. Vậy mà judge chấm 0.

Nguyên nhân nằm ở **chất lượng trích xuất PDF** (Task 3). Chunk gốc trong index là:

```
Chuan dau ra Tieng Anh cho sinh vien dai hoc chinh quy: TOEIC 500 hoac IELTS 5.5 tr len.
```

Không chỉ mất dấu mà còn **mất ký tự**: `"trở lên"` → `"tr len"`, và ở các file khác `"Điều 1"` → `"Chieu 1"`, `"Mức thu"` → `"Mc thu"`, `"Nghiên cứu sinh"` → `"Nghin cuu sinh"`. Judge phải phán "mệnh đề này có suy trực tiếp từ context không" và từ chối bắc cầu từ `"tr len"` sang `"trở lên"`. Đây là **lỗi dữ liệu ở Task 3, lộ ra ở metric của Task 10** — không phải lỗi generation.

Ghi nhận thêm: `context_precision = 0.700` do 2/5 chunk top-5 là tài liệu của **trường khác** (`quy-dinh-hoc-phi-hoc-bong-neu.md`, `quy-che-dao-tao-dai-hoc-neu.md`) lẫn vào câu hỏi về HUST.

### Q16 — `context_precision = 0.679`, nhiễu chéo trường

Câu trả lời đúng (`faithfulness = 1.000`) nhưng chunk đúng (`quy-che-dao-tao-dai-hoc-neu.md`) bị xếp **hạng 5/5**, bốn vị trí trên là `article_04`, `article_07`, `article_01`, `quy-che-dao-tao-dai-hoc-hust.md`. Nhờ reorder `front + back[::-1]` của Task 10 đưa chunk hạng cuối lên **cuối prompt** nên LLM vẫn đọc được — đúng tác dụng chống *lost in the middle*. Nhưng nếu `top_k` giảm xuống 4 thì câu này sẽ trượt.

### Q12 — `faithfulness = 0.667`

Câu trả lời gộp "nộp tại Phòng 102 Nhà A1 **hoặc gửi bưu điện** trước 15/10/2025" thành một mệnh đề. Judge tách thành nhiều mệnh đề nguyên tử và không xác nhận được một mệnh đề phái sinh. Sai lệch nhỏ về cách diễn đạt, không phải bịa đặt.

### Nhiễu hệ thống: `answer_relevancy` thấp đều (0.36–0.72) ở **mọi** câu

Kể cả những câu hoàn hảo (`faithfulness = 1.0`, `recall = 1.0`, `precision = 1.0`) vẫn chỉ được ~0.6. Nguyên nhân đã kiểm chứng bằng cách chạy lại đúng prompt của RAGAS trên Q11 ba lần:

| Lần | Câu hỏi sinh ngược |
|---|---|
| 1 | "Ai là đối tượng được miễn hoặc giảm học phí tại Đại học Kinh tế Quốc dân?" |
| 2 | "Ai là những đối tượng được miễn hoặc giảm học phí tại Đại học Kinh tế Quốc dân?" |
| 3 | **"Who are the eligible groups for tuition exemption or reduction at National Economics University?"** |

RAGAS sinh 3 câu hỏi ngược rồi lấy trung bình cosine với câu hỏi gốc, nhưng **prompt nội bộ của RAGAS viết bằng tiếng Anh** nên một phần câu sinh ra là tiếng Anh. Cosine giữa câu hỏi tiếng Việt và câu hỏi tiếng Anh thấp hẳn, kéo trung bình xuống ~1/3. Đây là **nhiễu đo đạc trên corpus tiếng Việt**, không phải khuyết điểm của pipeline. Vì vậy `answer_relevancy` chỉ nên dùng để **so sánh tương đối A vs B** (0.592 vs 0.491), tuyệt đối không đọc như "chatbot chỉ trả lời đúng trọng tâm 59%".
<!-- ANALYSIS:ROOT_CAUSE:END -->

---

## Guardrail check — câu hỏi ngoài phạm vi corpus

Không chấm RAGAS (không có ground truth). Chỉ kiểm tra Task 10 có trả về đúng câu từ chối khi thiếu evidence hay không.

| Câu hỏi | Từ chối đúng? | Câu trả lời |
|---------|---------------|-------------|
| Học phí ngành Y khoa của Đại học Y Hà Nội năm 2026 là bao nhiêu? | ✅ | Tôi không thể xác minh thông tin này từ nguồn hiện có. |
| Tỷ giá đồng yên Nhật hôm nay là bao nhiêu? | ✅ | Tôi không thể xác minh thông tin này từ nguồn hiện có. |

---

## Recommendations

<!-- ANALYSIS:RECOMMENDATIONS:START -->
Xếp theo tỉ lệ lợi ích / công sức.

### Cải tiến 1 — Trích xuất lại 6 PDF pháp quy cho ra tiếng Việt có dấu

**Action:** Task 3 hiện dùng `markitdown` và cho ra text mất dấu lẫn mất ký tự (`"trở lên"` → `"tr len"`, `"Điều"` → `"Chieu"`). Đổi sang bộ trích xuất giữ được Unicode tiếng Việt (PyMuPDF/`pdfplumber`, hoặc OCR nếu PDF là ảnh scan), rồi chạy lại Task 4 để re-index.

**Expected impact:** Cao nhất trong ba đề xuất. Gỡ đồng thời ba vấn đề: (a) dense retrieval hết mù với tài liệu pháp quy → chính là 3 câu Config B trượt; (b) `faithfulness` của Q09 hết bị chấm oan; (c) citation hiển thị cho sinh viên hết bị lỗi font. Đây là lỗi gốc ở tầng dữ liệu, sửa một chỗ mà cải thiện cả pipeline.

### Cải tiến 2 — Lọc theo trường trước khi rerank

**Action:** Câu hỏi đã nêu rõ "Bách Khoa Hà Nội" / "Kinh tế Quốc dân" mà top-5 vẫn lẫn tài liệu trường khác (Q09: 2/5 chunk là của NEU; Q16: chunk đúng bị đẩy xuống hạng 5). Metadata `source` đã có sẵn tên trường — nhận diện trường trong câu hỏi rồi lọc hoặc cộng điểm ưu tiên trước bước `rerank()` của Task 7.

**Expected impact:** Nhắm thẳng vào `context_precision` (0.945 — metric thấp thứ hai sau `answer_relevancy`). Ước tính đẩy được Q09 và Q16 từ ~0.68–0.70 lên gần 1.0. Ít rủi ro vì không đụng tới embedding hay index.

### Cải tiến 3 — Kích hoạt nhánh fallback PageIndex, hiện đang chết

**Action:** Nhánh fallback ở Task 9 (`best cosine < 0.3` → `pageindex_search()`) chưa bao giờ trả về gì. Kiểm tra API cho thấy tài khoản **không có document nào** (`GET /docs` → `documents: []`) và `PAGEINDEX_DOCUMENT_IDS` chưa được set — chưa ai chạy `upload_documents()`. Cần upload 6 PDF trong `data/landing/legal/` rồi lưu doc_id vào `.env`.

**Expected impact:** Trung bình. Hiện nhánh này là code chết, khi cosine thấp thì Task 9 lặng lẽ trả về kết quả hybrid yếu thay vì có đường lui thật. PageIndex duyệt theo cây cấu trúc điều/khoản nên hợp với dạng câu hỏi "Điều nào quy định X". Nên làm **sau** Cải tiến 1 — nếu re-index xong mà dense đã khỏe thì fallback ít khi cần tới, lúc đó đánh giá lại xem có đáng giữ không.

---

## Giới hạn của phép đánh giá này

Ghi lại để người đọc sau không hiểu nhầm bảng điểm:

1. **`answer_relevancy` bị nhiễu ngôn ngữ** — prompt nội bộ RAGAS là tiếng Anh, sinh câu hỏi ngược lẫn tiếng Anh trên corpus tiếng Việt (xem phần Root Cause). Chỉ dùng để so A/B, không đọc trị tuyệt đối.
2. **Judge cũng sai** — Q09 bị chấm `faithfulness = 0` cho một câu trả lời đúng nguyên văn. Điểm số là tín hiệu, không phải phán quyết.
3. **NaN ≠ 0.** RAGAS trả NaN khi judge lỗi mạng/429. Trung bình bỏ qua NaN sẽ báo cáo điểm của vài mẫu như thể của cả 18 — bản chạy trước của chính báo cáo này từng cho `faithfulness = 1.000` chỉ dựa trên **2/18** mẫu. Vì vậy bảng điểm bắt buộc có cột "Mẫu chấm được"; chỉ tin khi đủ 18/18.
4. **Rate limit làm sai lệch A/B.** Config chạy sau dễ ăn 429 do config trước đã hút cạn hạn mức token/phút, khiến điểm tụt vì hạ tầng chứ không vì chất lượng. Đã xử lý bằng `RAGAS_MAX_WORKERS=4`, nghỉ 70s giữa hai config, và `max_retries` ở cả LLM sinh câu trả lời lẫn LLM judge.
5. **Golden dataset bám theo ChromaDB, không phải `data/standardized/`.** Index hiện chứa 10 news article khác với 5 file trong `data/standardized/news/`. Eval đo đúng hệ thống đang chạy; nhưng cần đồng bộ lại hai nguồn này trước khi nộp.
6. **18 câu là mẫu nhỏ** — mỗi câu nặng 5,6% điểm trung bình. Chênh lệch dưới ~0,06 giữa hai config không nên coi là có ý nghĩa.
<!-- ANALYSIS:RECOMMENDATIONS:END -->
