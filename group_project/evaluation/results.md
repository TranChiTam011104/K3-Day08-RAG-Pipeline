# RAG Evaluation Results

> Sinh tự động bởi `python -m group_project.evaluation.eval_pipeline` lúc 2026-08-04 12:23.

## Framework sử dụng

**RAGAS 0.1.21**

- Judge LLM: `gpt-4o-mini` (temperature 0)
- Judge embeddings: `text-embedding-3-small`
- Golden dataset: 18 cặp Q&A, `top_k=5`
- Generation: Task 10 `generate_with_citation()` giữ nguyên cho cả hai config; chỉ tầng retrieval được thay.

---

## Overall Scores

| Metric | Config A (hybrid + rerank) | Config B (dense-only) | Δ (A−B) |
|--------|---------------------------|----------------------|---------|
| Faithfulness | 0.931 | 0.435 | +0.495 |
| Answer Relevance | 0.592 | 0.363 | +0.229 |
| Context Recall | 1.000 | 0.944 | +0.056 |
| Context Precision | 0.930 | 0.879 | +0.051 |
| **Average** | 0.863 | 0.656 | +0.208 |

---

## A/B Comparison Analysis

**Config A — hybrid (dense + BM25) + RRF rerank**

> Task 9 đầy đủ: semantic_search (OpenAI text-embedding-3-small) chạy song song lexical_search (BM25 fold dấu), fuse bằng RRF k=60, rerank RRF, có nhánh fallback PageIndex khi best cosine < 0.3.

**Config B — dense-only, không rerank**

> Chỉ Task 5 semantic_search với cùng embedding model và cùng top_k. Không BM25, không RRF, không rerank, không fallback.

**Retrieval hit-rate** (ít nhất 1 tài liệu kỳ vọng lọt vào top-5): Config A `18/18` · Config B `15/18`

**Latency trung bình / câu** (retrieval + generation): Config A `2.47s` · Config B `2.21s`

<!-- ANALYSIS:CONCLUSION -->

---

## Điểm chi tiết từng câu (Config A)

| ID | Trường | Loại | Faith. | Relev. | Recall | Prec. | Hit | Nguồn truy xuất top-1 |
|----|--------|------|--------|--------|--------|-------|-----|----------------------|
| Q01 | HUST | news | 1.000 | 0.627 | 1.000 | 0.887 | ✅ | `article_01.md` |
| Q02 | HUST | news | 0.750 | 0.648 | 1.000 | 1.000 | ✅ | `article_01.md` |
| Q03 | HUST | news | 1.000 | 0.526 | 1.000 | 1.000 | ✅ | `article_01.md` |
| Q04 | HUST | legal | 1.000 | 0.534 | 1.000 | 1.000 | ✅ | `article_02.md` |
| Q05 | HUST | news | 1.000 | 0.717 | 1.000 | 1.000 | ✅ | `article_02.md` |
| Q06 | HUST | news | 0.000 | 0.707 | 1.000 | 0.917 | ✅ | `article_02.md` |
| Q07 | HUST | news | 1.000 | 0.693 | 1.000 | 1.000 | ✅ | `article_03.md` |
| Q08 | HUST | legal | 1.000 | 0.547 | 1.000 | 0.950 | ✅ | `article_03.md` |
| Q09 | HUST | legal | 1.000 | 0.511 | 1.000 | 0.700 | ✅ | `quy-che-dao-tao-dai-hoc-hust.md` |
| Q10 | HUST | legal | 1.000 | 0.561 | 1.000 | 1.000 | ✅ | `article_02.md` |
| Q11 | NEU | news | 1.000 | 0.359 | 1.000 | 1.000 | ✅ | `article_04.md` |
| Q12 | NEU | news | 1.000 | 0.554 | 1.000 | 0.950 | ✅ | `article_04.md` |
| Q13 | NEU | news | 1.000 | 0.556 | 1.000 | 1.000 | ✅ | `article_05.md` |
| Q14 | NEU | news | 1.000 | 0.713 | 1.000 | 1.000 | ✅ | `article_07.md` |
| Q15 | NEU | news | 1.000 | 0.644 | 1.000 | 0.887 | ✅ | `article_07.md` |
| Q16 | NEU | legal | 1.000 | 0.518 | 1.000 | 0.589 | ✅ | `article_04.md` |
| Q17 | HUCE | news | 1.000 | 0.596 | 1.000 | 0.867 | ✅ | `article_08.md` |
| Q18 | HUCE | news | 1.000 | 0.648 | 1.000 | 1.000 | ✅ | `article_09.md` |

---

## Worst Performers (Bottom 3 — Config A)

| # | Question | Faithfulness | Relevance | Recall | Precision | Failure Stage |
|---|----------|-------------|-----------|--------|-----------|---------------|
| 1 | Q06 — Chuyện gì xảy ra nếu sinh viên HUST không hoàn tất nghĩa vụ học phí đú… | 0.000 | 0.707 | 1.000 | 0.917 | Generation — câu trả lời không bám context |
| 2 | Q16 — Điểm trung bình tích lũy toàn khóa tối thiểu để sinh viên NEU được xét… | 1.000 | 0.518 | 1.000 | 0.589 | Ranking — evidence bị đẩy xuống dưới |
| 3 | Q09 — Chuẩn đầu ra tiếng Anh của sinh viên đại học chính quy Bách Khoa Hà Nộ… | 1.000 | 0.511 | 1.000 | 0.700 | Ranking — evidence bị đẩy xuống dưới |

<!-- ANALYSIS:ROOT_CAUSE -->

---

## Guardrail check — câu hỏi ngoài phạm vi corpus

Không chấm RAGAS (không có ground truth). Chỉ kiểm tra Task 10 có trả về đúng câu từ chối khi thiếu evidence hay không.

| Câu hỏi | Từ chối đúng? | Câu trả lời |
|---------|---------------|-------------|
| Học phí ngành Y khoa của Đại học Y Hà Nội năm 2026 là bao nhiêu? | ✅ | Tôi không thể xác minh thông tin này từ nguồn hiện có. |
| Tỷ giá đồng yên Nhật hôm nay là bao nhiêu? | ✅ | Tôi không thể xác minh thông tin này từ nguồn hiện có. |

---

## Recommendations

<!-- ANALYSIS:RECOMMENDATIONS -->
