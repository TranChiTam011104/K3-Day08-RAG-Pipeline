"""Task 2 — crawl verified university news pages into JSON.

The source list contains real, official university URLs. Page content is always
read from the live response; no article body or policy figure is hard-coded.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"
MIN_ARTICLES = 5

SOURCES = [
    {
        "url": "https://www.hust.edu.vn/vi/news/tin-tuc-su-kien/chi-tiet-55-chuong-trinh-dao-tao-tai-bach-khoa-ha-noi-nhan-hoc-bong-chinh-phu-theo-nghi-dinh-179-655959.html",
        "title": "Chi tiết 55 Chương trình đào tạo tại Bách khoa Hà Nội nhận Học bổng Chính phủ theo Nghị định 179",
        "school": "HUST",
        "category": "hoc_bong",
    },
    {
        "url": "https://hust.edu.vn/vi/news/tuyen-sinh-dao-tao-cong-tac-sinh-vien/bach-khoa-ha-noi-trao-4-ty-dong-hoc-bong-sau-dai-hoc-mien-hoc-phi-cho-tat-ca-ncs-trung-tuyen-tu-2026-655834.html",
        "title": "Bách khoa Hà Nội trao 4 tỷ đồng học bổng sau đại học, miễn học phí cho tất cả NCS trúng tuyển từ 2026",
        "school": "HUST",
        "category": "hoc_bong",
    },
    {
        "url": "https://www.hust.edu.vn/vi/news/tin-tuc-su-kien/sinh-vien-tot-nghiep-bach-khoa-ha-noi-tiep-tuc-khang-dinh-nang-luc-voi-hoc-bong-chau-au-2026-655942.html",
        "title": "Sinh viên tốt nghiệp Bách khoa Hà Nội tiếp tục khẳng định năng lực với học bổng châu Âu 2026",
        "school": "HUST",
        "category": "hoc_bong",
    },
    {
        "url": "https://fit.neu.edu.vn/post/thong-bao-ve-viec-thu-ho-so-mien-giam-hoc-phi-va-ho-tro-chi-phi-hoc-tap-cho-sinh-vien-dot-2-nam-hoc-2025-2026",
        "title": "Thông báo thu hồ sơ miễn giảm học phí và hỗ trợ chi phí học tập đợt 2 năm học 2025-2026",
        "school": "NEU",
        "category": "hoc_phi",
    },
    {
        "url": "https://nct.neu.edu.vn/post/truong-cong-nghe-ghi-dau-an-tai-neu-open-day-2026-voi-nhieu-hoat-dong-tu-van-va-trai-nghiem-cong-nghe-hap-dan",
        "title": "Trường Công nghệ ghi dấu ấn tại NEU Open Day 2026",
        "school": "NEU",
        "category": "tuyen_sinh",
    },
    {
        "url": "https://www.hust.edu.vn/vi/news/tin-tuc-su-kien/bach-khoa-ha-noi-cong-bo-du-kien-phuong-an-tuyen-sinh-dai-hoc-2026-655641.html",
        "title": "Dự kiến phương án tuyển sinh đại học 2026 của Bách khoa Hà Nội",
        "school": "HUST",
        "category": "tuyen_sinh",
    },
    {
        "url": "https://www.hust.edu.vn/vi/news/tin-tuc-su-kien/dai-hoc-bach-khoa-ha-noi-trien-khai-cong-tac-phat-trien-dang-vien-nam-2026-655811.html",
        "title": "Đại học Bách khoa Hà Nội triển khai công tác phát triển Đảng viên năm 2026",
        "school": "HUST",
        "category": "thong_bao",
    },
]


def setup_directory() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _markdown_text(markdown_result) -> str:
    if isinstance(markdown_result, str):
        return markdown_result.strip()
    for attribute in ("fit_markdown", "raw_markdown"):
        value = getattr(markdown_result, attribute, None)
        if value and str(value).strip():
            return str(value).strip()
    return str(markdown_result or "").strip()


async def crawl_article(crawler, source: dict, run_config) -> dict:
    result = await crawler.arun(url=source["url"], config=run_config)
    if not result.success:
        raise RuntimeError(result.error_message or "unknown crawl error")

    content = _markdown_text(result.markdown)
    if len(content) < 500:
        raise RuntimeError(f"extracted content is too short ({len(content)} chars)")

    metadata = result.metadata or {}
    return {
        "url": result.url or source["url"],
        "title": metadata.get("title") or source["title"],
        "school": source["school"],
        "category": source["category"],
        "date_crawled": datetime.now(timezone.utc).isoformat(),
        "content_markdown": content,
    }


async def crawl_all() -> list[Path]:
    """Crawl all sources and replace the landing set only after >=5 succeed."""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

    setup_directory()
    browser_config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        check_robots_txt=True,
        excluded_tags=["nav", "footer", "form", "script", "style"],
        remove_overlay_elements=True,
    )

    articles: list[dict] = []
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for index, source in enumerate(SOURCES, start=1):
            print(f"[{index}/{len(SOURCES)}] Crawling: {source['url']}")
            try:
                articles.append(await crawl_article(crawler, source, run_config))
            except Exception as exc:
                print(f"  [ERROR] {exc}")

    if len(articles) < MIN_ARTICLES:
        raise RuntimeError(
            f"Only {len(articles)}/{len(SOURCES)} sources succeeded; "
            f"need at least {MIN_ARTICLES}. Existing landing files were preserved."
        )

    # The operation is intentionally transactional: stale files are removed only
    # after enough live pages have been collected in memory.
    for old_file in DATA_DIR.glob("article_*.json"):
        old_file.unlink()

    saved: list[Path] = []
    for index, article in enumerate(articles, start=1):
        path = DATA_DIR / f"article_{index:02d}.json"
        path.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
        saved.append(path)
        print(f"  [OK] Saved: {path} ({path.stat().st_size} bytes)")
    return saved


if __name__ == "__main__":
    asyncio.run(crawl_all())
