"""Focused offline tests for Role 3 implementation details."""

from unittest.mock import patch

from src import task5_semantic_search as task5
from src import task8_pageindex_vectorless as task8
from src import task10_generation as task10


class FakeEmbeddingModel:
    def encode(self, text, normalize_embeddings=False):
        assert text
        assert normalize_embeddings is True
        return [0.1, 0.2, 0.3]


class FakeCollection:
    def count(self):
        return 3

    def query(self, **kwargs):
        assert kwargs["n_results"] == 2
        return {
            "documents": [["lower score", "higher score"]],
            "metadatas": [[{"source": "a.md"}, {"source": "b.md"}]],
            "distances": [[0.4, 0.1]],
        }


def test_semantic_search_converts_cosine_distance_and_sorts():
    with patch.object(task5, "_get_collection", return_value=FakeCollection()), patch.object(
        task5, "_get_embedding_model", return_value=FakeEmbeddingModel()
    ):
        results = task5.semantic_search("tuition policy", top_k=2)

    assert [item["content"] for item in results] == ["higher score", "lower score"]
    assert [item["score"] for item in results] == [0.9, 0.6]


def test_hyde_search_embeds_hypothetical_document():
    with patch.object(task5, "_search_text", return_value=[]) as search:
        task5.hyde_search("short query", top_k=4, hypothetical_document="hypothetical answer")
    search.assert_called_once_with("hypothetical answer", 4)


def test_pageindex_parser_supports_current_and_nested_shapes():
    payload = {
        "doc_id": "pi-1",
        "retrieved_nodes": [
            {
                "title": "Tuition",
                "relevant_contents": [
                    {"page_index": 2, "relevant_content": "Current schema"},
                    [[{"section_title": "Fees", "relevant_content": "Legacy schema"}]],
                ],
            }
        ],
    }
    results = task8._parse_retrieval(payload, {"id": "pi-1", "name": "policy.pdf"})
    assert [item["content"] for item in results] == ["Current schema", "Legacy schema"]
    assert all(item["source"] == "pageindex" for item in results)
    assert results[1]["metadata"]["section"] == "Fees"


def test_reorder_and_context_citation_labels():
    chunks = [
        {"content": f"Chunk {index}", "score": 1 - index / 10, "metadata": {"source": f"s{index}.md"}}
        for index in range(5)
    ]
    reordered = task10.reorder_for_llm(chunks)
    assert [item["content"] for item in reordered] == ["Chunk 0", "Chunk 2", "Chunk 4", "Chunk 3", "Chunk 1"]
    context = task10.format_context(reordered)
    assert "Source: s0.md" in context
    assert "Chunk 0" in context


def test_generation_fails_closed_when_upstream_is_unavailable():
    with patch.object(task10, "retrieve", side_effect=NotImplementedError("Task 9 pending")):
        result = task10.generate_with_citation("What is the policy?")
    assert result["answer"] == task10.UNVERIFIED_ANSWER
    assert result["sources"] == []
    assert result["retrieval_source"] == "none"


def test_generation_returns_cited_llm_answer_and_reordered_sources():
    chunks = [
        {"content": "Evidence A", "score": 0.9, "metadata": {"source": "a.pdf"}, "source": "hybrid"},
        {"content": "Evidence B", "score": 0.8, "metadata": {"source": "b.pdf"}, "source": "hybrid"},
        {"content": "Evidence C", "score": 0.7, "metadata": {"source": "c.pdf"}, "source": "hybrid"},
    ]
    with patch.object(task10, "retrieve", return_value=chunks), patch.object(
        task10, "_call_llm", return_value="Grounded answer [a.pdf]"
    ) as llm:
        result = task10.generate_with_citation("Question", top_k=3)

    assert result["answer"] == "Grounded answer [a.pdf]"
    assert [item["content"] for item in result["sources"]] == ["Evidence A", "Evidence C", "Evidence B"]
    assert result["retrieval_source"] == "hybrid"
    assert "Source: a.pdf" in llm.call_args.args[0]


def test_generation_rejects_answer_without_known_citation():
    chunks = [
        {"content": "Evidence", "score": 0.9, "metadata": {"source": "policy.pdf"}, "source": "hybrid"}
    ]
    with patch.object(task10, "retrieve", return_value=chunks), patch.object(
        task10, "_call_llm", return_value="An answer without a citation"
    ):
        result = task10.generate_with_citation("Question")
    assert result["answer"] == task10.UNVERIFIED_ANSWER
    assert "did not cite" in result["error"]
