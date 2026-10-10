"""Command line interface."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

from . import __version__
from .config import Settings
from .crawler import Crawler, _no_robots_txt
from .exceptions import CrawlerError
from .fetcher import AiohttpFetcher
from .logger_config import setup_logging
from .models import CrawlResult, PageData
from .robots import RobotsChecker
from .search import keyword_frequency, search_pages
from .exporter import export_csv, export_json

logger = logging.getLogger("webcrawler")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="web-crawler", description="Crawl a site and extract structured data."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    crawl = commands.add_parser("crawl", help="Crawl starting from one or more seed URLs.")
    crawl.add_argument("urls", nargs="*", help="Seed URL(s). Defaults to SEED_URLS from .env.")
    crawl.add_argument("--depth", type=int, help="Override MAX_DEPTH.")
    crawl.add_argument("--max-pages", type=int, help="Override MAX_PAGES.")
    crawl.add_argument("--no-robots", action="store_true", help="Ignore robots.txt.")

    search = commands.add_parser("search", help="Search a previous crawl's JSON export.")
    search.add_argument("keyword", help="Keyword to search for.")
    search.add_argument("--file", default=None, help="Path to the JSON export.")

    keywords = commands.add_parser("keywords", help="Show the most common words in a crawl.")
    keywords.add_argument("--file", default=None, help="Path to the JSON export.")
    keywords.add_argument("--top", type=int, default=20)

    return parser


async def _prime_robots(robots: RobotsChecker, fetcher: AiohttpFetcher, seed_urls: list[str]) -> None:
    """Fetch robots.txt for every seed URL's origin before the crawl starts.

    The crawler only follows same-site links, so every origin it will ever
    touch is one of these seed origins; priming them up front means
    RobotsChecker never needs to do its own (synchronous) fetch at all.
    """
    seen_origins: set[str] = set()
    for url in seed_urls:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin in seen_origins:
            continue
        seen_origins.add(origin)
        text = await fetcher.fetch_text_or_none(f"{origin}/robots.txt")
        robots.load_rules(origin, text)


async def _run_crawl(settings: Settings, seed_urls: list[str]) -> CrawlResult:
    fetcher = AiohttpFetcher(settings.user_agent, settings.timeout_s)
    robots = RobotsChecker(settings.user_agent, _no_robots_txt)
    if settings.respect_robots:
        await _prime_robots(robots, fetcher, seed_urls)
    crawler = Crawler(
        fetcher=fetcher,
        max_depth=settings.max_depth,
        max_pages=settings.max_pages,
        concurrency=settings.concurrency,
        delay_s=settings.delay_s,
        max_retries=settings.max_retries,
        retry_delay_s=settings.retry_delay_s,
        respect_robots=settings.respect_robots,
        user_agent=settings.user_agent,
        robots_checker=robots,
    )
    try:
        return await crawler.crawl(seed_urls)
    finally:
        await fetcher.close()


def command_crawl(args: argparse.Namespace, settings: Settings) -> int:
    if args.depth is not None:
        settings = _replace(settings, max_depth=args.depth)
    if args.max_pages is not None:
        settings = _replace(settings, max_pages=args.max_pages)
    if args.no_robots:
        settings = _replace(settings, respect_robots=False)

    seed_urls = args.urls or list(settings.seed_urls)
    result = asyncio.run(_run_crawl(settings, seed_urls))

    settings.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = settings.output_dir / "crawl_result.json"
    csv_path = settings.output_dir / "crawl_result.csv"
    export_json(result, json_path)
    export_csv(result, csv_path)

    stats = result.stats
    print(
        f"\nPages visited: {stats.pages_visited} | Failed: {stats.pages_failed} | "
        f"Skipped (robots): {stats.pages_skipped_robots} | Time: {stats.execution_seconds:.2f}s"
    )
    print(f"JSON: {json_path}")
    print(f"CSV:  {csv_path}")
    return 2 if stats.pages_failed and not stats.pages_visited else 0


def _replace(settings: Settings, **changes):
    import dataclasses

    return dataclasses.replace(settings, **changes)


def _load_pages(settings: Settings, file_arg: str | None) -> list[PageData]:
    path = Path(file_arg) if file_arg else settings.output_dir / "crawl_result.json"
    if not path.exists():
        raise CrawlerError(f"No crawl export found at '{path}'. Run 'crawl' first.")
    data = json.loads(path.read_text(encoding="utf-8"))
    return [PageData(**p) for p in data["pages"]]


def command_search(args: argparse.Namespace, settings: Settings) -> int:
    pages = _load_pages(settings, args.file)
    matches = search_pages(pages, args.keyword)
    if not matches:
        print(f"No pages mention '{args.keyword}'.")
        return 0
    print(f"\n{len(matches)} page(s) mention '{args.keyword}':\n")
    for page in matches:
        print(f"  [{page.depth}] {page.title or '(untitled)'}")
        print(f"      {page.url}")
    return 0


def command_keywords(args: argparse.Namespace, settings: Settings) -> int:
    pages = _load_pages(settings, args.file)
    top = keyword_frequency(pages, top_n=args.top)
    if not top:
        print("No words to show.")
        return 0
    print(f"\nTop {len(top)} word(s):\n")
    for word, count in top:
        print(f"  {word:<20}{count}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = Settings.from_env()
        setup_logging(settings.log_file)
        if args.command == "crawl":
            return command_crawl(args, settings)
        if args.command == "search":
            return command_search(args, settings)
        return command_keywords(args, settings)
    except CrawlerError as exc:
        print(f"Error: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
