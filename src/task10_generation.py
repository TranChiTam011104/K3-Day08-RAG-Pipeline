"""Task 10 — grounded generation with document reordering and citations."""

from __future__ import annotations

import os
import re
from typing import Any

from dotenv import load_dotenv

from .task9_retrieval_pipeline import retrieve

load_dotenv()

# Five chunks normally provide enough evidence without overloading the prompt.
TOP_K = 5
# Low temperature prioritises faithful synthesis; top_p still permits natural prose.
TOP_P = 0.9
TEMPERATURE = 0.2
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
UNVERIFIED_ANSWER = "Tôi không thể xác minh thông tin này từ nguồn hiện có."

SYSTEM_PROMPT = """Bạn là trợ lý trả lời câu hỏi về dịch vụ và chính sách đại học.

Quy tắc bắt buộc:
1. Chỉ sử dụng thông tin trong context; không dùng kiến thức bên ngoài và không bịa đặt.
2. Mỗi khẳng định thực tế phải có trích dẫn ngay sau, dùng đúng tên file ở trường
   Source của context, đặt trong ngoặc vuông. Ví dụ: [Source: article_01.md].
3. Nếu context không đủ, trả lời chính xác: "Tôi không thể xác minh thông tin này từ nguồn hiện có."
4. Trả lời bằng tiếng Việt, ngắn gọn và rõ ràng.
5. Không trích dẫn nguồn không xuất hiện trong context."""


def _validate_input(query: str, top_k: int) -> str:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    return query.strip()


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """Place high-ranked chunks at the prompt's beginning and end.

    For ``[1, 2, 3, 4, 5]`` the documented strategy produces
    ``[1, 3, 5, 4, 2]`` (``front + back[::-1]``).  A new list is returned and
    the caller's ranked list is never mutated.
    """
    if not isinstance(chunks, list):
        raise TypeError("chunks must be a list")
    return list(chunks[::2]) + list(chunks[1::2][::-1])


def _source_label(chunk: dict, index: int) -> str:
    metadata = chunk.get("metadata") or {}
    return str(
        metadata.get("source")
        or metadata.get("document")
        or metadata.get("title")
        or metadata.get("section")
        or f"Source {index}"
    )


def format_context(chunks: list[dict]) -> str:
    """Format evidence with stable source labels that the LLM can cite."""
    if not isinstance(chunks, list):
        raise TypeError("chunks must be a list")

    parts: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        if not isinstance(chunk, dict):
            continue
        content = str(chunk.get("content", "")).strip()
        if not content:
            continue
        metadata = chunk.get("metadata") or {}
        source = _source_label(chunk, index)
        doc_type = metadata.get("type", "unknown")
        section = metadata.get("section")
        header = f"[Document {index} | Source: {source} | Type: {doc_type}"
        if section:
            header += f" | Section: {section}"
        header += "]"
        parts.append(f"{header}\n{content}")
    return "\n\n---\n\n".join(parts)


def _call_llm(user_message: str) -> str:
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not openrouter_key and not openai_key:
        raise RuntimeError("OPENROUTER_API_KEY or OPENAI_API_KEY is not configured")

    from openai import OpenAI

    if openrouter_key:
        client = OpenAI(
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=45.0,
            max_retries=1,
        )
        model = LLM_MODEL
    else:
        client = OpenAI(api_key=openai_key, timeout=45.0, max_retries=1)
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=TEMPERATURE,
        top_p=TOP_P,
        max_tokens=800,
    )
    answer = response.choices[0].message.content
    if not answer or not answer.strip():
        raise RuntimeError("LLM returned an empty answer")
    return answer.strip()


def _result(answer: str, sources: list[dict], error: str | None = None) -> dict[str, Any]:
    retrieval_source = sources[0].get("source", "hybrid") if sources else "none"
    payload: dict[str, Any] = {
        "answer": answer,
        "sources": sources,
        "retrieval_source": retrieval_source,
    }
    if error:
        payload["error"] = error
    return payload


def _has_known_citation(answer: str, sources: list[dict]) -> bool:
    """Accept citations only when they name a source present in the context.

    The label is matched *inside* the brackets rather than as the whole bracket
    body: the context header reads ``[Document 1 | Source: x.md | Type: news]``,
    so models reliably cite ``[Source: x.md]`` or ``[x.md, 2025]`` instead of a
    bare ``[x.md]``. Demanding the bare form rejected every grounded answer and
    made the pipeline answer "cannot verify" to questions it had evidence for.
    Anything naming a source absent from the context is still rejected.
    """
    labels = {
        _source_label(source, index).casefold()
        for index, source in enumerate(sources, start=1)
    }
    return any(
        label in citation.casefold()
        for citation in re.findall(r"\[([^\[\]]+)\]", answer)
        for label in labels
    )


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """Run retrieval, reorder evidence, and generate a cited answer.

    The function always returns the documented dictionary schema.  Retrieval or
    generation failures fail closed with the rubric's verification refusal;
    technical details are exposed in an optional ``error`` field for the UI.
    """
    clean_query = _validate_input(query, top_k)

    try:
        chunks = retrieve(clean_query, top_k=top_k)
    except Exception as exc:
        return _result(UNVERIFIED_ANSWER, [], f"Retrieval unavailable: {exc}")

    if not chunks:
        return _result(UNVERIFIED_ANSWER, [])

    reordered = reorder_for_llm(chunks)
    context = format_context(reordered)
    if not context:
        return _result(UNVERIFIED_ANSWER, reordered)

    user_message = (
        "Context:\n"
        f"{context}\n\n"
        "---\n\n"
        f"Câu hỏi: {clean_query}\n\n"
        "Hãy trả lời chỉ từ context và dùng tên Source làm nhãn trích dẫn."
    )
    try:
        answer = _call_llm(user_message)
    except Exception as exc:
        return _result(UNVERIFIED_ANSWER, reordered, f"Generation unavailable: {exc}")
    if answer != UNVERIFIED_ANSWER and not _has_known_citation(answer, reordered):
        return _result(
            UNVERIFIED_ANSWER,
            reordered,
            "Generation rejected: answer did not cite a provided source",
        )
    return _result(answer, reordered)


if __name__ == "__main__":
    for test_query in (
        "Học phí được quy định như thế nào?",
        "Điều kiện nhận học bổng là gì?",
    ):
        response = generate_with_citation(test_query)
        print(f"\nQ: {test_query}\nA: {response['answer']}")
        print(f"Sources: {len(response['sources'])} | via {response['retrieval_source']}")
