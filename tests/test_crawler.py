"""Crawler orchestration tests, driven by a fake async fetcher (no aiohttp needed)."""

import asyncio
import unittest

from webcrawler.crawler import Crawler
from webcrawler.exceptions import FetchError
from webcrawler.models import FetchResult
from webcrawler.robots import RobotsChecker


def page(title: str, links: list[str]) -> str:
    link_tags = "".join(f'<a href="{href}">x</a>' for href in links)
    return f"<html><head><title>{title}</title></head><body><p>Body of {title}.</p>{link_tags}</body></html>"


class FakeFetcher:
    """Serves canned HTML per URL. Can simulate failures and delay."""

    def __init__(self, pages: dict[str, str], fail_first_n: dict[str, int] | None = None) -> None:
        self.pages = pages
        self.fail_first_n = fail_first_n or {}
        self.calls: list[str] = []
        self._attempt_count: dict[str, int] = {}

    async def fetch(self, url: str) -> FetchResult:
        self.calls.append(url)
        self._attempt_count[url] = self._attempt_count.get(url, 0) + 1
        remaining_failures = self.fail_first_n.get(url, 0)
        if self._attempt_count[url] <= remaining_failures:
            raise ConnectionError("simulated network error")
        if url not in self.pages:
            return FetchResult(url=url, status_code=404, text="")
        return FetchResult(url=url, status_code=200, text=self.pages[url])

    async def fetch_text_or_none(self, url: str):
        return None

    async def close(self) -> None:
        pass


def make_crawler(fetcher, **overrides) -> Crawler:
    defaults = dict(
        max_depth=2,
        max_pages=50,
        concurrency=5,
        delay_s=0,
        max_retries=2,
        retry_delay_s=0,
        respect_robots=False,
    )
    defaults.update(overrides)
    return Crawler(fetcher, **defaults)


def run(coro):
    return asyncio.run(coro)


class CrawlerDepthAndDedupTests(unittest.TestCase):
    def test_follows_internal_links_up_to_max_depth(self) -> None:
        site = {
            "https://x.test/": page("Home", ["https://x.test/a", "https://x.test/b"]),
            "https://x.test/a": page("A", ["https://x.test/a1"]),
            "https://x.test/b": page("B", []),
            "https://x.test/a1": page("A1 (depth 2)", ["https://x.test/a1a"]),
            "https://x.test/a1a": page("Too deep", []),
        }
        fetcher = FakeFetcher(site)
        crawler = make_crawler(fetcher, max_depth=2)
        result = run(crawler.crawl(["https://x.test/"]))

        urls = {p.url for p in result.pages}
        self.assertEqual(
            urls, {"https://x.test/", "https://x.test/a", "https://x.test/b", "https://x.test/a1"}
        )
        self.assertNotIn("https://x.test/a1a", urls)

    def test_each_url_is_fetched_only_once(self) -> None:
        site = {
            "https://x.test/": page("Home", ["https://x.test/a", "https://x.test/b"]),
            "https://x.test/a": page("A", ["https://x.test/b"]),
            "https://x.test/b": page("B", ["https://x.test/a"]),
        }
        fetcher = FakeFetcher(site)
        crawler = make_crawler(fetcher, max_depth=3)
        result = run(crawler.crawl(["https://x.test/"]))

        self.assertEqual(len(result.pages), 3)
        self.assertEqual(len(fetcher.calls), 3)

    def test_external_links_are_not_followed(self) -> None:
        site = {
            "https://x.test/": page("Home", ["https://x.test/a", "https://other.test/page"]),
            "https://x.test/a": page("A", []),
        }
        fetcher = FakeFetcher(site)
        crawler = make_crawler(fetcher, max_depth=3)
        result = run(crawler.crawl(["https://x.test/"]))

        urls = {p.url for p in result.pages}
        self.assertNotIn("https://other.test/page", urls)

    def test_max_pages_limits_the_crawl(self) -> None:
        site = {f"https://x.test/{i}": page(f"P{i}", [f"https://x.test/{i+1}"]) for i in range(20)}
        site["https://x.test/0"] = page("P0", ["https://x.test/1"])
        fetcher = FakeFetcher(site)
        crawler = make_crawler(fetcher, max_depth=20, max_pages=5)
        result = run(crawler.crawl(["https://x.test/0"]))

        self.assertLessEqual(len(result.pages), 5)
        self.assertLessEqual(result.stats.pages_visited, 5)

    def test_multiple_seed_urls(self) -> None:
        site = {
            "https://x.test/a": page("A", []),
            "https://x.test/b": page("B", []),
        }
        fetcher = FakeFetcher(site)
        crawler = make_crawler(fetcher, max_depth=0)
        result = run(crawler.crawl(["https://x.test/a", "https://x.test/b"]))
        self.assertEqual(len(result.pages), 2)


class CrawlerRetryAndFailureTests(unittest.TestCase):
    def test_transient_failure_is_retried_and_succeeds(self) -> None:
        site = {"https://x.test/": page("Home", [])}
        fetcher = FakeFetcher(site, fail_first_n={"https://x.test/": 1})
        crawler = make_crawler(fetcher, max_retries=3)
        result = run(crawler.crawl(["https://x.test/"]))

        self.assertEqual(len(result.pages), 1)
        self.assertEqual(len(result.failures), 0)
        self.assertEqual(fetcher.calls.count("https://x.test/"), 2)

    def test_persistent_failure_is_recorded_not_raised(self) -> None:
        site = {"https://x.test/": page("Home", [])}
        fetcher = FakeFetcher(site, fail_first_n={"https://x.test/": 99})
        crawler = make_crawler(fetcher, max_retries=2)
        result = run(crawler.crawl(["https://x.test/"]))

        self.assertEqual(len(result.pages), 0)
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.stats.pages_failed, 1)

    def test_one_failing_page_does_not_stop_the_rest_of_the_crawl(self) -> None:
        site = {
            "https://x.test/": page("Home", ["https://x.test/broken", "https://x.test/ok"]),
            "https://x.test/ok": page("OK", []),
        }
        fetcher = FakeFetcher(site, fail_first_n={"https://x.test/broken": 99})
        crawler = make_crawler(fetcher, max_retries=2, max_depth=2)
        result = run(crawler.crawl(["https://x.test/"]))

        urls = {p.url for p in result.pages}
        self.assertIn("https://x.test/ok", urls)
        self.assertEqual(len(result.failures), 1)

    def test_404_is_treated_as_a_failure(self) -> None:
        fetcher = FakeFetcher({})
        crawler = make_crawler(fetcher, max_retries=1)
        result = run(crawler.crawl(["https://x.test/missing"]))
        self.assertEqual(len(result.pages), 0)
        self.assertEqual(len(result.failures), 1)


class CrawlerRobotsTests(unittest.TestCase):
    def test_disallowed_seed_is_skipped(self) -> None:
        site = {"https://x.test/": page("Home", [])}
        fetcher = FakeFetcher(site)

        class DenyAll:
            def is_allowed(self, url: str) -> bool:
                return False

        crawler = make_crawler(fetcher, respect_robots=True, robots_checker=DenyAll())
        result = run(crawler.crawl(["https://x.test/"]))
        self.assertEqual(len(result.pages), 0)
        self.assertEqual(result.stats.pages_skipped_robots, 1)
        self.assertEqual(fetcher.calls, [])

    def test_robots_disabled_ignores_rules(self) -> None:
        site = {"https://x.test/": page("Home", [])}
        fetcher = FakeFetcher(site)

        class DenyAll:
            def is_allowed(self, url: str) -> bool:
                return False

        crawler = make_crawler(fetcher, respect_robots=False, robots_checker=DenyAll())
        result = run(crawler.crawl(["https://x.test/"]))
        self.assertEqual(len(result.pages), 1)


class CrawlerStatsTests(unittest.TestCase):
    def test_stats_reflect_the_crawl(self) -> None:
        site = {
            "https://x.test/": page("Home", ["https://x.test/a"]),
            "https://x.test/a": page("A", []),
        }
        fetcher = FakeFetcher(site)
        crawler = make_crawler(fetcher, max_depth=2)
        result = run(crawler.crawl(["https://x.test/"]))

        self.assertEqual(result.stats.pages_visited, 2)
        self.assertEqual(result.stats.pages_failed, 0)
        self.assertEqual(result.stats.start_url, "https://x.test/")
        self.assertGreaterEqual(result.stats.execution_seconds, 0)


if __name__ == "__main__":
    unittest.main()
