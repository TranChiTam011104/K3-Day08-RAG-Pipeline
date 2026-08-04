"""Script to review and QA test citation formatting in LLM responses (Role 4/5/6 Task in Checkpoint 4)."""

from __future__ import annotations

import re
from pathlib import Path
from src.task10_generation import _source_label, _has_known_citation


def verify_citation_format_robust(answer: str, sources: list[dict]) -> dict:
    """
    Robust citation checker that parses and validates citation formatting and content.
    
    QA Review Criteria:
    1. Checks if citation tokens (e.g., [Source Name] or [Document X]) exist.
    2. Validates that citations match the source names or indices provided in context.
    3. Handles case-insensitivity and strips file extensions for flexible LLM outputs.
    """
    # Extract brackets contents: [source]
    matches = re.findall(r'\[([^\]]+)\]', answer)
    
    valid_citations = []
    invalid_citations = []
    warnings = []
    
    # 1. Create a set of valid source representations
    valid_source_representations = {}
    for index, source in enumerate(sources, start=1):
        label = _source_label(source, index)
        # Store index mappings
        valid_source_representations[f"document {index}"] = label
        valid_source_representations[f"doc {index}"] = label
        valid_source_representations[str(index)] = label
        
        # Store label variations
        label_lower = label.lower()
        valid_source_representations[label_lower] = label
        
        # Strip extension if any (e.g. tuition-fees-rmit.pdf -> tuition-fees-rmit)
        stem = Path(label).stem.lower()
        valid_source_representations[stem] = label
        
        # Replace dashes/underscores with spaces
        spaced = stem.replace("-", " ").replace("_", " ")
        valid_source_representations[spaced] = label

    # 2. Check each matched citation in brackets
    for match in matches:
        match_clean = match.strip().lower()
        
        # Ignore common UI/Markdown bracket elements if they aren't citations
        # (e.g. [Image], [Link], [Table], [PDF])
        if match_clean in ("image", "link", "table", "pdf", "docx"):
            continue
            
        # Extract source name from comma-separated format (e.g. [Source, 2026])
        parts = [p.strip() for p in match_clean.split(',')]
        cited_name = parts[0]
        
        # Check if the cited name maps to any valid source
        matched_source = None
        for key, value in valid_source_representations.items():
            if cited_name == key or cited_name.startswith(key) or key.startswith(cited_name):
                matched_source = value
                break
                
        if matched_source:
            valid_citations.append({
                "raw": f"[{match}]",
                "resolved_source": matched_source
            })
        else:
            invalid_citations.append(f"[{match}]")
            warnings.append(f"Cited source '{match}' does not match any of the provided documents.")
            
    is_valid = len(invalid_citations) == 0 and len(valid_citations) > 0
    if len(matches) == 0:
        warnings.append("No citations found in the LLM answer.")
        
    return {
        "is_valid": is_valid,
        "total_matches": len(matches),
        "valid_citations": valid_citations,
        "invalid_citations": invalid_citations,
        "warnings": warnings
    }


def run_qa_review():
    """Run simulated LLM responses against current and robust citation check implementations."""
    print("=" * 70)
    # Highlight Role 4/5/6 Task in CP4
    print("ROLE 4/5/6 QA TASK: CITATION FORMAT & QUALITY REVIEW")
    print("=" * 70)
    
    mock_sources = [
        {"content": "Học phí tại RMIT Vietnam đóng theo học kỳ...", "metadata": {"source": "tuition-fees-rmit.pdf", "type": "legal"}},
        {"content": "Thư viện mở cửa từ 8h đến 21h...", "metadata": {"source": "library-services.md", "type": "news"}},
    ]
    
    # Test cases containing different citation formats
    test_cases = [
        {
            "name": "Case A: Perfect matching citations",
            "answer": "Học phí tại RMIT đóng theo từng kỳ học [tuition-fees-rmit.pdf]. Thư viện mở cửa đến tối [library-services.md]."
        },
        {
            "name": "Case B: Minor variation (missing extensions)",
            "answer": "Đóng học phí theo từng học kỳ [tuition-fees-rmit] và bạn có thể mượn sách thư viện [library-services]."
        },
        {
            "name": "Case C: Index-based citation (e.g. Document 1)",
            "answer": "Thư viện RMIT mở cửa từ 8h [Document 2] và tiền học phí nộp đầu học kỳ [Document 1]."
        },
        {
            "name": "Case D: Case variations",
            "answer": "Học phí được thanh toán trực tuyến [Tuition-Fees-Rmit.pdf]."
        },
        {
            "name": "Case E: Hallucinated / missing citation",
            "answer": "Ký túc xá có máy lạnh đầy đủ [dormitory-policy.pdf]. Học phí rất hợp lý."
        },
        {
            "name": "Case F: No citations at all",
            "answer": "Học phí tại RMIT Vietnam đóng theo học kỳ."
        }
    ]
    
    print(f"Total test cases: {len(test_cases)}")
    print("-" * 70)
    
    for case in test_cases:
        print(f"\n📌 {case['name']}")
        print(f"Answer: \"{case['answer']}\"")
        
        # Test current implementation in task10_generation.py
        try:
            current_ok = _has_known_citation(case["answer"], mock_sources)
        except Exception as e:
            current_ok = f"Error: {e}"
            
        # Test our robust implementation
        robust_res = verify_citation_format_robust(case["answer"], mock_sources)
        
        print(f"  -> Current Check (`_has_known_citation`): {'PASS' if current_ok else 'FAIL'}")
        print(f"  -> Robust QA Check (`verify_citation_format_robust`): {'PASS' if robust_res['is_valid'] else 'FAIL'}")
        print(f"     * Total detected: {robust_res['total_matches']}")
        if robust_res["valid_citations"]:
            print(f"     * Valid: {robust_res['valid_citations']}")
        if robust_res["invalid_citations"]:
            print(f"     * Invalid: {robust_res['invalid_citations']}")
        if robust_res["warnings"]:
            for warning in robust_res["warnings"]:
                print(f"     * [Warning] {warning}")
                
    print("\n" + "=" * 70)
    print("RECOMMENDATION FOR ROLE 3 (FRONTEND & CHATBOT DEV):")
    print("The current `_has_known_citation` is strictly case-sensitive and requires the exact file suffix.")
    print("Consider adopting the robust regex/stem resolution logic in production to prevent valid LLM responses from being rejected.")
    print("=" * 70)


if __name__ == "__main__":
    run_qa_review()
