"""
RAG Evaluation Pipeline — framework đã chọn: **RAGAS**.

Chạy từ thư mục gốc repo:
    python -m group_project.evaluation.eval_pipeline

Luồng thực thi:
    1. Load golden_dataset.json (18 cặp Q&A, ground theo đúng nội dung đã index).
    2. Với mỗi config A/B: chạy retrieval + generation (Task 9 + Task 10) trên
       toàn bộ golden dataset, thu (question, answer, contexts, ground_truth).
    3. Chấm 4 metric RAGAS: faithfulness, answer_relevancy, context_recall,
       context_precision.
    4. So sánh A/B + tìm worst performers.
    5. Xuất results.md và raw_runs.json.

Vì sao dùng OpenAI (gpt-4o-mini) làm judge thay vì model OpenRouter ":free":
RAGAS gọi LLM rất nhiều lần (nhiều call/metric/câu hỏi, không phải 1 call/câu).
Model free của OpenRouter giới hạn 50 request/ngày CHO CẢ TÀI KHOẢN nên chạy
18 câu × 2 config chắc chắn đứt giữa chừng. Judge model được ghim cứng để điểm
giữa các lần chạy còn so sánh được với nhau.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results.md"
RAW_RUNS_PATH = Path(__file__).parent / "raw_runs.json"

# Judge model cho RAGAS. Tách khỏi LLM_MODEL của Task 10 để judge không bao giờ
# là chính model đang bị chấm.
JUDGE_MODEL = os.getenv("RAGAS_JUDGE_MODEL", "gpt-4o-mini")
JUDGE_EMBEDDING_MODEL = os.getenv("RAGAS_JUDGE_EMBEDDING", "text-embedding-3-small")
TOP_K = 5

METRIC_COLUMNS = [
    "faithfulness",
    "answer_relevancy",
    "context_recall",
    "context_precision",
]

# Câu hỏi nằm ngoài phạm vi corpus — KHÔNG chấm RAGAS, chỉ kiểm tra guardrail
# "không đủ evidence thì phải từ chối" của Task 10 có thật sự chặn được không.
GUARDRAIL_PROBES = [
    "Học phí ngành Y khoa của Đại học Y Hà Nội năm 2026 là bao nhiêu?",
    "Tỷ giá đồng yên Nhật hôm nay là bao nhiêu?",
]


def load_golden_dataset() -> list[dict]:
    """Load golden dataset từ JSON file."""
    with open(GOLDEN_DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# CONFIGS cho A/B comparison
# =============================================================================

def _retriever_hybrid_rerank(query: str, top_k: int = TOP_K, **_: Any) -> list[dict]:
    """Config A — pipeline đầy đủ của Task 9: dense + BM25, fuse RRF, rerank."""
    from src.task9_retrieval_pipeline import retrieve

    return retrieve(query, top_k=top_k, use_reranking=True)


def _retriever_dense_only(query: str, top_k: int = TOP_K, **_: Any) -> list[dict]:
    """Config B — chỉ dense retrieval (Task 5), không lexical, không rerank.

    Đây là baseline để đo xem hybrid + rerank thực sự đóng góp bao nhiêu.
    """
    from src.task5_semantic_search import semantic_search

    results = semantic_search(query, top_k=top_k)
    for item in results:
        item["source"] = "dense"
    return results


CONFIGS: dict[str, dict[str, Any]] = {
    "A_hybrid_rerank": {
        "label": "Config A — hybrid (dense + BM25) + RRF rerank",
        "description": (
            "Task 9 đầy đủ: semantic_search (OpenAI text-embedding-3-small) chạy "
            "song song lexical_search (BM25 fold dấu), fuse bằng RRF k=60, rerank "
            "RRF, có nhánh fallback PageIndex khi best cosine < 0.3."
        ),
        "retriever": _retriever_hybrid_rerank,
    },
    "B_dense_only": {
        "label": "Config B — dense-only, không rerank",
        "description": (
            "Chỉ Task 5 semantic_search với cùng embedding model và cùng top_k. "
            "Không BM25, không RRF, không rerank, không fallback."
        ),
        "retriever": _retriever_dense_only,
    },
}


# =============================================================================
# Chạy RAG pipeline trên golden dataset
# =============================================================================

def run_pipeline(config_name: str, golden_dataset: list[dict]) -> list[dict]:
    """Chạy retrieval + generation cho 1 config, trả về records để chấm điểm.

    Task 10 import ``retrieve`` vào namespace của module nên ta thay chính
    attribute đó — cả hai config dùng chung một hàm generation, khác biệt duy
    nhất nằm ở tầng retrieval. Đó là điều kiện để so sánh A/B có ý nghĩa.
    """
    from src import task10_generation

    config = CONFIGS[config_name]
    original_retrieve = task10_generation.retrieve
    task10_generation.retrieve = config["retriever"]

    records: list[dict] = []
    try:
        for index, item in enumerate(golden_dataset, start=1):
            question = item["question"]
            print(f"  [{index:02d}/{len(golden_dataset)}] {item['id']}: {question[:60]}...")
            started = time.time()
            result = task10_generation.generate_with_citation(question, top_k=TOP_K)
            elapsed = time.time() - started

            sources = result.get("sources") or []
            contexts = [str(s.get("content", "")) for s in sources if s.get("content")]
            retrieved_files = [
                str((s.get("metadata") or {}).get("source", "?")) for s in sources
            ]
            records.append(
                {
                    "id": item["id"],
                    "school": item.get("school", ""),
                    "doc_type": item.get("doc_type", ""),
                    "question": question,
                    "answer": result.get("answer", ""),
                    "contexts": contexts,
                    "ground_truth": item["expected_answer"],
                    "expected_sources": item.get("expected_sources", []),
                    "retrieved_sources": retrieved_files,
                    "retrieval_source": result.get("retrieval_source", "none"),
                    "error": result.get("error"),
                    "latency_s": round(elapsed, 2),
                }
            )
    finally:
        task10_generation.retrieve = original_retrieve

    return records


def run_guardrail_probes(config_name: str) -> list[dict]:
    """Kiểm tra Task 10 có từ chối đúng khi câu hỏi nằm ngoài corpus không."""
    from src import task10_generation

    config = CONFIGS[config_name]
    original_retrieve = task10_generation.retrieve
    task10_generation.retrieve = config["retriever"]

    probes: list[dict] = []
    try:
        for question in GUARDRAIL_PROBES:
            result = task10_generation.generate_with_citation(question, top_k=TOP_K)
            answer = result.get("answer", "")
            probes.append(
                {
                    "question": question,
                    "answer": answer,
                    "refused": answer.strip() == task10_generation.UNVERIFIED_ANSWER,
                    "error": result.get("error"),
                }
            )
    finally:
        task10_generation.retrieve = original_retrieve

    return probes


# =============================================================================
# Chấm điểm bằng RAGAS
# =============================================================================

def evaluate_with_ragas(records: list[dict]) -> Any:
    """Chấm 4 metric RAGAS, trả về DataFrame per-sample."""
    from datasets import Dataset
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas import evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    dataset = Dataset.from_dict(
        {
            "question": [r["question"] for r in records],
            "answer": [r["answer"] for r in records],
            # RAGAS yêu cầu contexts không rỗng; câu nào retrieval trắng tay thì
            # đưa placeholder để metric chấm 0 thay vì làm sập cả run.
            "contexts": [r["contexts"] or ["(không truy xuất được ngữ cảnh)"] for r in records],
            "ground_truth": [r["ground_truth"] for r in records],
        }
    )

    judge_llm = ChatOpenAI(model=JUDGE_MODEL, temperature=0.0)
    judge_embeddings = OpenAIEmbeddings(model=JUDGE_EMBEDDING_MODEL)

    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        llm=judge_llm,
        embeddings=judge_embeddings,
    )

    frame = result.to_pandas()
    frame.insert(0, "id", [r["id"] for r in records])
    return frame


def _mean_scores(frame: Any) -> dict[str, float]:
    """Trung bình từng metric, bỏ qua NaN (RAGAS trả NaN khi judge parse lỗi)."""
    scores: dict[str, float] = {}
    for column in METRIC_COLUMNS:
        if column in frame.columns:
            value = frame[column].astype("float64").mean(skipna=True)
            scores[column] = float(value) if value == value else float("nan")
        else:
            scores[column] = float("nan")
    valid = [v for v in scores.values() if v == v]
    scores["average"] = sum(valid) / len(valid) if valid else float("nan")
    return scores


# =============================================================================
# A/B Comparison
# =============================================================================

def compare_configs(golden_dataset: list[dict]) -> dict[str, Any]:
    """Chạy full eval cho từng config và gom lại để so sánh."""
    comparison: dict[str, Any] = {}

    for config_name, config in CONFIGS.items():
        print(f"\n=== {config['label']} ===")
        records = run_pipeline(config_name, golden_dataset)
        print(f"  -> chấm điểm RAGAS ({len(records)} samples, judge={JUDGE_MODEL})...")
        frame = evaluate_with_ragas(records)
        comparison[config_name] = {
            "label": config["label"],
            "description": config["description"],
            "records": records,
            "frame": frame,
            "scores": _mean_scores(frame),
        }
        print(f"  -> {comparison[config_name]['scores']}")

    return comparison


# =============================================================================
# Phân tích
# =============================================================================

def _retrieval_hit(record: dict) -> bool:
    """Có ít nhất 1 tài liệu kỳ vọng nằm trong danh sách file đã truy xuất?"""
    expected = set(record.get("expected_sources") or [])
    retrieved = set(record.get("retrieved_sources") or [])
    return bool(expected & retrieved)


def _failure_stage(row: dict) -> str:
    """Quy trách nhiệm điểm thấp về đúng tầng của pipeline."""
    recall = row.get("context_recall")
    precision = row.get("context_precision")
    faith = row.get("faithfulness")
    relevancy = row.get("answer_relevancy")

    def low(value: Any, threshold: float = 0.7) -> bool:
        return value is not None and value == value and value < threshold

    if low(recall, 0.5):
        return "Retrieval — context thiếu evidence"
    if low(precision):
        return "Ranking — evidence bị đẩy xuống dưới"
    if low(faith):
        return "Generation — câu trả lời không bám context"
    if low(relevancy):
        return "Generation — câu trả lời lệch trọng tâm câu hỏi"
    return "—"


def worst_performers(config_result: dict, limit: int = 3) -> list[dict]:
    """Bottom-N câu hỏi theo điểm trung bình 4 metric."""
    frame = config_result["frame"]
    records = {r["id"]: r for r in config_result["records"]}

    rows: list[dict] = []
    for _, raw in frame.iterrows():
        row = {column: raw.get(column) for column in METRIC_COLUMNS}
        valid = [v for v in row.values() if v is not None and v == v]
        record = records.get(raw["id"], {})
        rows.append(
            {
                "id": raw["id"],
                **row,
                "mean": sum(valid) / len(valid) if valid else 0.0,
                "question": record.get("question", ""),
                "stage": _failure_stage(row),
                "retrieval_hit": _retrieval_hit(record),
                "retrieved_sources": record.get("retrieved_sources", []),
                "error": record.get("error"),
            }
        )

    rows.sort(key=lambda r: r["mean"])
    return rows[:limit]


# =============================================================================
# Export Results
# =============================================================================

def _fmt(value: Any) -> str:
    if value is None or value != value:
        return "n/a"
    return f"{float(value):.3f}"


def _fmt_delta(a: Any, b: Any) -> str:
    if a is None or b is None or a != a or b != b:
        return "n/a"
    delta = float(a) - float(b)
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.3f}"


METRIC_LABELS = {
    "faithfulness": "Faithfulness",
    "answer_relevancy": "Answer Relevance",
    "context_recall": "Context Recall",
    "context_precision": "Context Precision",
    "average": "**Average**",
}


def export_results(comparison: dict[str, Any], probes: list[dict]) -> None:
    """Ghi bảng điểm + phân tích ra results.md."""
    config_a = comparison["A_hybrid_rerank"]
    config_b = comparison["B_dense_only"]
    scores_a = config_a["scores"]
    scores_b = config_b["scores"]

    lines: list[str] = []
    lines.append("# RAG Evaluation Results")
    lines.append("")
    lines.append(
        f"> Sinh tự động bởi `python -m group_project.evaluation.eval_pipeline` "
        f"lúc {time.strftime('%Y-%m-%d %H:%M')}."
    )
    lines.append("")
    lines.append("## Framework sử dụng")
    lines.append("")
    lines.append("**RAGAS 0.1.21**")
    lines.append("")
    lines.append(f"- Judge LLM: `{JUDGE_MODEL}` (temperature 0)")
    lines.append(f"- Judge embeddings: `{JUDGE_EMBEDDING_MODEL}`")
    lines.append(f"- Golden dataset: {len(config_a['records'])} cặp Q&A, `top_k={TOP_K}`")
    lines.append(
        "- Generation: Task 10 `generate_with_citation()` giữ nguyên cho cả hai "
        "config; chỉ tầng retrieval được thay."
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Overall scores ───────────────────────────────────────────────────
    lines.append("## Overall Scores")
    lines.append("")
    lines.append("| Metric | Config A (hybrid + rerank) | Config B (dense-only) | Δ (A−B) |")
    lines.append("|--------|---------------------------|----------------------|---------|")
    for key in [*METRIC_COLUMNS, "average"]:
        lines.append(
            f"| {METRIC_LABELS[key]} | {_fmt(scores_a.get(key))} | "
            f"{_fmt(scores_b.get(key))} | {_fmt_delta(scores_a.get(key), scores_b.get(key))} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── A/B ──────────────────────────────────────────────────────────────
    lines.append("## A/B Comparison Analysis")
    lines.append("")
    for config in (config_a, config_b):
        lines.append(f"**{config['label']}**")
        lines.append("")
        lines.append(f"> {config['description']}")
        lines.append("")

    hit_a = sum(1 for r in config_a["records"] if _retrieval_hit(r))
    hit_b = sum(1 for r in config_b["records"] if _retrieval_hit(r))
    total = len(config_a["records"])
    lines.append(
        f"**Retrieval hit-rate** (ít nhất 1 tài liệu kỳ vọng lọt vào top-{TOP_K}): "
        f"Config A `{hit_a}/{total}` · Config B `{hit_b}/{total}`"
    )
    lines.append("")
    latency_a = sum(r["latency_s"] for r in config_a["records"]) / max(total, 1)
    latency_b = sum(r["latency_s"] for r in config_b["records"]) / max(total, 1)
    lines.append(
        f"**Latency trung bình / câu** (retrieval + generation): "
        f"Config A `{latency_a:.2f}s` · Config B `{latency_b:.2f}s`"
    )
    lines.append("")
    lines.append("<!-- ANALYSIS:CONCLUSION -->")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Per-question ─────────────────────────────────────────────────────
    lines.append("## Điểm chi tiết từng câu (Config A)")
    lines.append("")
    lines.append("| ID | Trường | Loại | Faith. | Relev. | Recall | Prec. | Hit | Nguồn truy xuất top-1 |")
    lines.append("|----|--------|------|--------|--------|--------|-------|-----|----------------------|")
    frame_a = config_a["frame"]
    records_a = {r["id"]: r for r in config_a["records"]}
    for _, raw in frame_a.iterrows():
        record = records_a.get(raw["id"], {})
        retrieved = record.get("retrieved_sources") or ["—"]
        lines.append(
            f"| {raw['id']} | {record.get('school','')} | {record.get('doc_type','')} | "
            f"{_fmt(raw.get('faithfulness'))} | {_fmt(raw.get('answer_relevancy'))} | "
            f"{_fmt(raw.get('context_recall'))} | {_fmt(raw.get('context_precision'))} | "
            f"{'✅' if _retrieval_hit(record) else '❌'} | `{retrieved[0]}` |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Worst performers ─────────────────────────────────────────────────
    lines.append("## Worst Performers (Bottom 3 — Config A)")
    lines.append("")
    lines.append("| # | Question | Faithfulness | Relevance | Recall | Precision | Failure Stage |")
    lines.append("|---|----------|-------------|-----------|--------|-----------|---------------|")
    worst = worst_performers(config_a, limit=3)
    for index, row in enumerate(worst, start=1):
        question = row["question"][:70] + ("…" if len(row["question"]) > 70 else "")
        lines.append(
            f"| {index} | {row['id']} — {question} | {_fmt(row['faithfulness'])} | "
            f"{_fmt(row['answer_relevancy'])} | {_fmt(row['context_recall'])} | "
            f"{_fmt(row['context_precision'])} | {row['stage']} |"
        )
    lines.append("")
    lines.append("<!-- ANALYSIS:ROOT_CAUSE -->")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Guardrail ────────────────────────────────────────────────────────
    lines.append("## Guardrail check — câu hỏi ngoài phạm vi corpus")
    lines.append("")
    lines.append(
        "Không chấm RAGAS (không có ground truth). Chỉ kiểm tra Task 10 có trả về "
        "đúng câu từ chối khi thiếu evidence hay không."
    )
    lines.append("")
    lines.append("| Câu hỏi | Từ chối đúng? | Câu trả lời |")
    lines.append("|---------|---------------|-------------|")
    for probe in probes:
        answer = probe["answer"][:80] + ("…" if len(probe["answer"]) > 80 else "")
        lines.append(
            f"| {probe['question']} | {'✅' if probe['refused'] else '❌'} | {answer} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## Recommendations")
    lines.append("")
    lines.append("<!-- ANALYSIS:RECOMMENDATIONS -->")
    lines.append("")

    RESULTS_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] Đã ghi {RESULTS_PATH}")

    raw = {
        name: {
            "label": config["label"],
            "scores": config["scores"],
            "records": config["records"],
            "per_question": json.loads(
                config["frame"][["id", *METRIC_COLUMNS]].to_json(orient="records")
            ),
        }
        for name, config in comparison.items()
    }
    raw["guardrail_probes"] = probes
    RAW_RUNS_PATH.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] Đã ghi {RAW_RUNS_PATH}")


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise SystemExit("Thiếu OPENAI_API_KEY trong .env — RAGAS judge không chạy được.")

    golden_dataset = load_golden_dataset()
    print(f"Loaded {len(golden_dataset)} test cases")

    comparison = compare_configs(golden_dataset)

    print("\n=== Guardrail probes (Config A) ===")
    probes = run_guardrail_probes("A_hybrid_rerank")
    for probe in probes:
        print(f"  refused={probe['refused']} | {probe['question']}")

    export_results(comparison, probes)

    print("\n=== TỔNG KẾT ===")
    for name, config in comparison.items():
        scores = config["scores"]
        print(
            f"  {name:18s} avg={_fmt(scores['average'])} "
            f"faith={_fmt(scores['faithfulness'])} "
            f"relev={_fmt(scores['answer_relevancy'])} "
            f"recall={_fmt(scores['context_recall'])} "
            f"prec={_fmt(scores['context_precision'])}"
        )
