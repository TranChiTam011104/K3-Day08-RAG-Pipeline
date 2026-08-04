# Role 3 — Live Demo & Technical Handoff

## Ownership applied

Theo phân công checkpoint trong `LAB_GUIDE.md`, phạm vi Role 3 của nhánh này gồm
Task 2, Task 5, Task 8, Task 10 và `app.py`. Task 4 thuộc Role 2 và không được sửa
ngoài commit upstream đã merge từ `origin/main`.

## Phần đã hoàn thiện

- Task 2: crawler Crawl4AI dùng URL thật từ HUST/NEU; landing corpus hiện có 5
  bản ghi đã kiểm tra nguồn và không còn nội dung chính sách synthetic.
- Task 5: semantic search dùng đúng cấu hình model/Chroma collection của Task 4,
  chuyển cosine distance sang similarity, sort giảm dần, và có `hyde_search()`.
- Task 8: PageIndex REST adapter cho raw-node retrieval, polling, parser cho schema
  hiện tại và schema lồng legacy, đánh dấu `source="pageindex"`.
- Task 10: `front + back[::-1]`, context có nhãn nguồn, gọi OpenRouter/OpenAI,
  kiểm tra citation và fail-closed khi thiếu evidence/API.
- Streamlit: lịch sử chat, câu hỏi gợi ý, `top_k`, danh sách nguồn/score, trạng thái
  cấu hình, xóa lịch sử và diagnostics tùy chọn.

## Cấu hình cần có

Tạo `.env` tại project root (không commit secret):

```dotenv
OPENROUTER_API_KEY=...
LLM_MODEL=openai/gpt-4o-mini

PAGEINDEX_API_KEY=...
PAGEINDEX_DOCUMENT_IDS=pi-id-1,pi-id-2
```

Có thể dùng `OPENAI_API_KEY` và `OPENAI_MODEL` thay cho OpenRouter. Để lấy
`PAGEINDEX_DOCUMENT_IDS`, upload PDF rồi lưu các `doc_id` trả về:

```powershell
python -X utf8 -c "from src.task8_pageindex_vectorless import upload_documents; print(upload_documents())"
```

## Thứ tự chạy demo

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
python -X utf8 -m src.task2_crawl_news
python -X utf8 -m src.task3_convert_markdown
python -X utf8 -m src.task4_chunking_indexing
python -X utf8 -m pytest tests/test_individual.py tests/test_role3.py -v
streamlit run app.py
```

Trước demo, kiểm tra sidebar phải hiển thị ChromaDB và LLM key ở trạng thái sẵn
sàng. Có thể dùng các câu hỏi:

1. `Những chương trình nào thuộc diện học bổng Chính phủ theo Nghị định 179?`
2. `Chính sách học phí cho nghiên cứu sinh trúng tuyển từ năm 2026 là gì?`
3. `Thời hạn nộp hồ sơ miễn giảm học phí đợt 2 tại NEU là khi nào?`

Mở expander “Nguồn tham khảo” để demo source, loại tài liệu và score. Câu trả lời
không có citation hợp lệ sẽ bị thay bằng thông báo không thể xác minh.

## Trạng thái kiểm thử và blockers tại thời điểm handoff

- `py_compile`: pass cho toàn bộ file Role 3 và tests mới.
- `pytest tests/test_individual.py tests/test_role3.py -v`: **26 passed, 16 skipped**.
- 16 skip thuộc Task 4, 6, 7 và 9 upstream vẫn còn `NotImplementedError`; vì vậy
  chưa thể xác nhận full hybrid RAG end-to-end hoặc mốc 35/35 của rubric.
- Máy kiểm thử dùng Python 3.14.6 và chưa có Streamlit. Cài đặt từ PyPI thất bại do
  kết nối mạng của môi trường, nên chỉ xác nhận được syntax của `app.py`, chưa xác
  nhận server Streamlit khởi động thực tế.
- `git fetch upstream` cũng thất bại vì môi trường không kết nối GitHub; nhánh đã
  fast-forward tới remote ref local mới nhất `origin/main` (`33c71b6`).
- Không có `OPENROUTER_API_KEY`/`OPENAI_API_KEY`, `PAGEINDEX_API_KEY` hoặc
  `chroma_db/` trong môi trường kiểm thử; các đường gọi network được kiểm tra bằng
  mocks và chế độ fail-closed.

Role 2 cần hoàn thiện Task 4, 6, 7 và 9, tạo `chroma_db/`, sau đó chạy lại toàn bộ
35 tests gốc và smoke test Streamlit trước live demo.
