"""Streamlit chatbot for the university-services RAG pipeline.

Run from the repository root with ``streamlit run app.py``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.task10_generation import generate_with_citation  # noqa: E402

st.set_page_config(
    page_title="University Services RAG Chatbot",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None


def render_sources(sources: list[dict]) -> None:
    """Render retrieved evidence consistently for current and historic turns."""
    if not sources:
        return
    with st.expander(f"📚 Nguồn tham khảo ({len(sources)} chunks)"):
        for index, source in enumerate(sources, start=1):
            metadata = source.get("metadata") or {}
            source_name = metadata.get("source", "Unknown")
            doc_type = metadata.get("type", "unknown")
            section = metadata.get("section")
            try:
                score = float(source.get("score", 0.0))
            except (TypeError, ValueError):
                score = 0.0
            label = f"**[{index}] {source_name}** · `{doc_type}` · score `{score:.4f}`"
            if section:
                label += f" · {section}"
            st.markdown(label)
            content = str(source.get("content", "")).strip()
            preview = content[:500] + ("…" if len(content) > 500 else "")
            st.text(preview)
            if index < len(sources):
                st.divider()


with st.sidebar:
    st.title("🎓 University Services RAG")
    st.caption("Trợ lý hỏi đáp có dẫn nguồn về chính sách và dịch vụ đại học.")

    st.subheader("💡 Câu hỏi gợi ý")
    suggestions = [
        "Quy định về học phí được nêu như thế nào?",
        "Điều kiện xét học bổng dành cho sinh viên là gì?",
        "Quy trình đăng ký học phần gồm những bước nào?",
        "Sinh viên được cảnh báo học tập trong trường hợp nào?",
        "Quyền và nghĩa vụ của sinh viên gồm những gì?",
    ]
    for index, suggestion in enumerate(suggestions):
        if st.button(suggestion, use_container_width=True, key=f"suggestion_{index}"):
            st.session_state.pending_query = suggestion

    st.divider()
    st.subheader("⚙️ Thiết lập")
    top_k = st.slider("Số chunks retrieval (top_k)", min_value=3, max_value=10, value=5)
    show_diagnostics = st.checkbox("Hiện chi tiết lỗi kỹ thuật", value=False)
    if st.button("🗑️ Xóa lịch sử chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_query = None
        st.rerun()

    st.divider()
    st.subheader("Trạng thái demo")
    llm_ready = bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"))
    pageindex_ready = bool(os.getenv("PAGEINDEX_API_KEY"))
    chroma_ready = (PROJECT_ROOT / "chroma_db").exists()
    st.caption(f"{'✅' if chroma_ready else '⚠️'} ChromaDB index")
    st.caption(f"{'✅' if llm_ready else '⚠️'} LLM API key")
    st.caption(f"{'✅' if pageindex_ready else '⚠️'} PageIndex API key")
    st.caption("Hybrid → RRF → PageIndex fallback → cited generation")

st.title("🎓 University Services RAG Chatbot")
st.caption("Hỏi đáp trên kho văn bản quy chế, học phí, học bổng và thông báo đại học.")

if not st.session_state.messages:
    st.info("Chọn một câu hỏi gợi ý ở thanh bên hoặc nhập câu hỏi để bắt đầu.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_sources(message.get("sources", []))
            if show_diagnostics and message.get("error"):
                st.caption(f"Chi tiết: {message['error']}")

user_input = st.chat_input("Nhập câu hỏi về chính sách hoặc dịch vụ đại học…")
query = user_input or st.session_state.pending_query

if query:
    st.session_state.pending_query = None
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Đang tìm kiếm tài liệu và tổng hợp câu trả lời…"):
            try:
                response = generate_with_citation(query, top_k=top_k)
            except Exception as exc:
                response = {
                    "answer": "Tôi không thể xác minh thông tin này từ nguồn hiện có.",
                    "sources": [],
                    "retrieval_source": "none",
                    "error": str(exc),
                }

        answer = response.get("answer") or "Tôi không thể xác minh thông tin này từ nguồn hiện có."
        sources = response.get("sources") or []
        st.markdown(answer)
        render_sources(sources)
        if show_diagnostics and response.get("error"):
            st.caption(f"Chi tiết: {response['error']}")

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "retrieval_source": response.get("retrieval_source", "none"),
            "error": response.get("error"),
        }
    )
