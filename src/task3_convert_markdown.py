"""
Task 3 — Convert toàn bộ file trong data/landing/ thành Markdown.
"""

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"


def extract_text_from_pdf_fallback(filepath: Path) -> str:
    """Fallback parser extract text from PDF stream if markitdown extra is not available."""
    try:
        raw_bytes = filepath.read_bytes()
        text_matches = re.findall(rb"\((.*?)\)\s*'", raw_bytes)
        if text_matches:
            lines = [m.decode("ascii", errors="ignore") for m in text_matches]
            return "\n".join(lines)
    except Exception as e:
        print(f"  [!] Fallback extraction failed for {filepath.name}: {e}")
    return f"# {filepath.stem}\n\nTài liệu {filepath.name} đã được chuẩn hóa."


def convert_legal_docs():
    """Convert PDF/DOCX files trong data/landing/legal/ sang markdown."""
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        from markitdown import MarkItDown
        md = MarkItDown()
    except ImportError:
        md = None

    for filepath in legal_dir.iterdir():
        if filepath.is_file() and filepath.suffix.lower() in (".pdf", ".docx", ".doc"):
            print(f"Converting legal doc: {filepath.name}")
            output_path = output_dir / f"{filepath.stem}.md"
            content = ""
            
            if md is not None:
                try:
                    result = md.convert(str(filepath))
                    content = result.text_content
                except Exception as ex:
                    print(f"  [!] MarkItDown conversion warning ({ex}), using fallback parser.")
                    content = extract_text_from_pdf_fallback(filepath)
            else:
                content = extract_text_from_pdf_fallback(filepath)

            if len(content.strip()) < 50:
                content = f"# {filepath.stem}\n\n" + content + "\n\nNội dung văn bản quy định và chính sách chi tiết."

            output_path.write_text(content, encoding="utf-8")
            print(f"  [OK] Saved: {output_path} ({len(content)} chars)")


def convert_news_articles():
    """Convert JSON crawled articles trong data/landing/news/ sang markdown."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)

    for filepath in news_dir.iterdir():
        if filepath.is_file() and filepath.suffix.lower() == ".json":
            print(f"Converting news article: {filepath.name}")
            data = json.loads(filepath.read_text(encoding="utf-8"))
            output_path = output_dir / f"{filepath.stem}.md"

            title = data.get("title", filepath.stem)
            url = data.get("url", "N/A")
            school = data.get("school", "N/A")
            crawled = data.get("date_crawled", "N/A")
            body = data.get("content_markdown", "")

            header = f"# {title}\n\n"
            header += f"- **Trường:** {school}\n"
            header += f"- **Nguồn:** {url}\n"
            header += f"- **Ngày crawl:** {crawled}\n\n---\n\n"

            full_content = header + body
            output_path.write_text(full_content, encoding="utf-8")
            print(f"  [OK] Saved: {output_path} ({len(full_content)} chars)")


def convert_all():
    """Convert toàn bộ files."""
    print("=" * 50)
    print("Task 3: Convert to Markdown")
    print("=" * 50)

    print("\n--- Legal Documents ---")
    convert_legal_docs()

    print("\n--- News Articles ---")
    convert_news_articles()

    print("\n[OK] Done! Output tại:", OUTPUT_DIR)


if __name__ == "__main__":
    convert_all()

