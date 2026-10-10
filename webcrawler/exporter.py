"""Writes crawl results to JSON and CSV."""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import asdict
from pathlib import Path

from .exceptions import CrawlerError
from .models import CrawlResult

logger = logging.getLogger("webcrawler")


def export_json(result: CrawlResult, path: str | Path) -> None:
    path = Path(path)
    data = {
        "stats": result.stats.as_dict(),
        "pages": [asdict(p) for p in result.pages],
        "failures": [asdict(f) for f in result.failures],
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        raise CrawlerError(f"Could not write '{path}': {exc}") from exc
    logger.info("Exported %d page(s) to %s", len(result.pages), path)


def export_csv(result: CrawlResult, path: str | Path) -> None:
    path = Path(path)
    fieldnames = [
        "url", "depth", "status_code", "title", "word_count",
        "heading_count", "paragraph_count", "link_count", "image_count",
        "meta_description", "fetched_at",
    ]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for page in result.pages:
                writer.writerow(
                    {
                        "url": page.url,
                        "depth": page.depth,
                        "status_code": page.status_code,
                        "title": page.title,
                        "word_count": page.word_count,
                        "heading_count": len(page.headings),
                        "paragraph_count": len(page.paragraphs),
                        "link_count": len(page.links),
                        "image_count": len(page.images),
                        "meta_description": page.meta_description,
                        "fetched_at": page.fetched_at,
                    }
                )
    except OSError as exc:
        raise CrawlerError(f"Could not write '{path}': {exc}") from exc
    logger.info("Exported %d page(s) to %s", len(result.pages), path)
