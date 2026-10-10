"""Core crawl orchestration: BFS by depth, dedup, retries, robots, stats.

Takes a `fetcher` object (see fetcher.py) rather than importing aiohttp
directly, so this entire module can be tested with a fake fetcher and plain
asyncio, independent of any real network library.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

from .exceptions import FetchError
from .models import CrawlResult, CrawlStats, FailedPage, PageData
from .parser import parse_page, same_site
from .robots import RobotsChecker

logger = logging.getLogger("webcrawler")


def _no_robots_txt(url: str) -> str:
    """Default sync fetch for RobotsChecker when no checker is supplied: always 'missing'."""
    raise FileNotFoundError(url)


class Crawler:
    def __init__(
        self,
        fetcher,
        max_depth: int,
        max_pages: int,
        concurrency: int,
        delay_s: float,
        max_retries: int,
        retry_delay_s: float,
        respect_robots: bool = True,
        user_agent: str = "Crawler/1.0",
        robots_checker: RobotsChecker | None = None,
    ) -> None:
        self.fetcher = fetcher
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.concurrency = concurrency
        self.delay_s = delay_s
        self.max_retries = max_retries
        self.retry_delay_s = retry_delay_s
        self.respect_robots = respect_robots
        self.robots = robots_checker or RobotsChecker(user_agent, _no_robots_txt)

        self._visited: set[str] = set()
        self._queued: set[str] = set()
        self._semaphore = asyncio.Semaphore(concurrency)
        self._lock = asyncio.Lock()

    async def crawl(self, seed_urls: list[str]) -> CrawlResult:
        start = time.monotonic()
        stats = CrawlStats(start_url=seed_urls[0] if seed_urls else "", max_depth=self.max_depth)
        pages: list[PageData] = []
        failures: list[FailedPage] = []

        queue: deque[tuple[str, int]] = deque()
        for url in seed_urls:
            if url not in self._queued:
                queue.append((url, 0))
                self._queued.add(url)

        while queue and len(self._visited) < self.max_pages:
            batch: list[tuple[str, int]] = []
            while queue and len(batch) < self.concurrency and len(self._visited) + len(batch) < self.max_pages:
                batch.append(queue.popleft())

            results = await asyncio.gather(*(self._process(url, depth) for url, depth in batch))

            for outcome in results:
                kind = outcome[0]
                if kind == "ok":
                    _, page, discovered = outcome
                    pages.append(page)
                    stats.pages_visited += 1
                    if page.depth < self.max_depth:
                        for link in discovered:
                            if link not in self._visited and link not in self._queued:
                                self._queued.add(link)
                                queue.append((link, page.depth + 1))
                elif kind == "failed":
                    _, failure = outcome
                    failures.append(failure)
                    stats.pages_failed += 1
                elif kind == "robots":
                    stats.pages_skipped_robots += 1
                elif kind == "duplicate":
                    stats.duplicate_urls_skipped += 1

            if queue and self.delay_s > 0:
                await asyncio.sleep(self.delay_s)

        stats.execution_seconds = time.monotonic() - start
        return CrawlResult(pages=pages, failures=failures, stats=stats)

    async def _process(self, url: str, depth: int):
        async with self._lock:
            if url in self._visited:
                return ("duplicate",)
            self._visited.add(url)

        if self.respect_robots and not self.robots.is_allowed(url):
            logger.info("Blocked by robots.txt: %s", url)
            return ("robots",)

        async with self._semaphore:
            try:
                page = await self._fetch_with_retries(url, depth)
            except FetchError as exc:
                logger.warning("Failed %s: %s", url, exc)
                return ("failed", FailedPage(url=url, depth=depth, reason=str(exc)))

        logger.info("Fetched (depth %d): %s", depth, url)
        internal_links = [link for link in page.links if same_site(link, url)]
        return ("ok", page, internal_links)

    async def _fetch_with_retries(self, url: str, depth: int) -> PageData:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                result = await self.fetcher.fetch(url)
                if result.status_code >= 400:
                    raise FetchError(f"HTTP {result.status_code}")
                return parse_page(url, result.text, result.status_code, depth)
            except FetchError as exc:
                last_error = exc
            except Exception as exc:
                last_error = exc

            if attempt < self.max_retries:
                logger.info("Retry %d/%d for %s", attempt, self.max_retries, url)
                await asyncio.sleep(self.retry_delay_s * attempt)

        raise FetchError(f"Gave up after {self.max_retries} attempt(s): {last_error}")
