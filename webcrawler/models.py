"""Plain data objects shared between modules."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PageData:
    """Everything extracted from one successfully fetched page."""

    url: str
    depth: int
    status_code: int
    title: str
    headings: list[str]
    paragraphs: list[str]
    links: list[str]
    images: list[str]
    meta_description: str
    fetched_at: str
    word_count: int = 0

    def __post_init__(self) -> None:
        self.word_count = sum(len(p.split()) for p in self.paragraphs)


@dataclass
class FetchResult:
    """What a fetcher returns for one URL, independent of which HTTP library fetched it."""

    url: str
    status_code: int
    text: str


@dataclass
class FailedPage:
    """A URL that could not be crawled, and why."""

    url: str
    depth: int
    reason: str


@dataclass
class CrawlStats:
    """Summary of one crawl run."""

    pages_visited: int = 0
    pages_failed: int = 0
    pages_skipped_robots: int = 0
    duplicate_urls_skipped: int = 0
    execution_seconds: float = 0.0
    start_url: str = ""
    max_depth: int = 0

    def as_dict(self) -> dict:
        return {
            "start_url": self.start_url,
            "max_depth": self.max_depth,
            "pages_visited": self.pages_visited,
            "pages_failed": self.pages_failed,
            "pages_skipped_robots": self.pages_skipped_robots,
            "duplicate_urls_skipped": self.duplicate_urls_skipped,
            "execution_seconds": round(self.execution_seconds, 2),
        }


@dataclass
class CrawlResult:
    """The full output of a crawl: every page plus every failure plus stats."""

    pages: list[PageData] = field(default_factory=list)
    failures: list[FailedPage] = field(default_factory=list)
    stats: CrawlStats = field(default_factory=CrawlStats)
