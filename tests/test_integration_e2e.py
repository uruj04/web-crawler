"""End-to-end test: a real local HTTP server, crawled through the real Crawler
class using a requests-based fetcher (same Fetcher interface as aiohttp's),
to catch wiring bugs the mocked unit tests can't see.
"""

import asyncio
import functools
import http.server
import tempfile
import threading
import unittest
from pathlib import Path

import requests

from webcrawler.crawler import Crawler
from webcrawler.exporter import export_csv, export_json
from webcrawler.models import FetchResult
from webcrawler.robots import RobotsChecker
from webcrawler.search import keyword_frequency, search_pages

FIXTURES = Path(__file__).parent / "fixtures" / "site"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args) -> None:
        return None


class RequestsFetcher:
    """Implements the same Fetcher interface as AiohttpFetcher, using `requests`
    run in a thread pool so it can be awaited - fully real HTTP, fully testable
    here since `requests` (unlike aiohttp) is installed in this sandbox."""

    def __init__(self, user_agent: str, timeout_s: float) -> None:
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.timeout_s = timeout_s

    async def fetch(self, url: str) -> FetchResult:
        def _get():
            response = self.session.get(url, timeout=self.timeout_s)
            return FetchResult(url=url, status_code=response.status_code, text=response.text)
        return await asyncio.to_thread(_get)

    async def fetch_text_or_none(self, url: str):
        def _get():
            try:
                response = self.session.get(url, timeout=self.timeout_s)
                return response.text if response.status_code < 400 else None
            except requests.RequestException:
                return None
        return await asyncio.to_thread(_get)

    async def close(self) -> None:
        self.session.close()


class CrawlerEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        handler = functools.partial(QuietHandler, directory=str(FIXTURES))
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    async def _crawl(self, **overrides):
        fetcher = RequestsFetcher("TestCrawler/1.0", 5.0)
        defaults = dict(
            max_depth=2, max_pages=50, concurrency=4, delay_s=0,
            max_retries=2, retry_delay_s=0, respect_robots=True, user_agent="TestCrawler/1.0",
        )
        defaults.update(overrides)
        robots = RobotsChecker("TestCrawler/1.0", lambda u: (_ for _ in ()).throw(FileNotFoundError()))
        text = await fetcher.fetch_text_or_none(f"{self.base_url}/robots.txt")
        robots.load_rules(self.base_url, text)
        crawler = Crawler(fetcher=fetcher, robots_checker=robots, **defaults)
        try:
            return await crawler.crawl([f"{self.base_url}/"])
        finally:
            await fetcher.close()

    def test_full_crawl_against_real_server(self) -> None:
        result = asyncio.run(self._crawl(max_depth=2))
        urls = {p.url for p in result.pages}

        self.assertIn(f"{self.base_url}/", urls)
        self.assertIn(f"{self.base_url}/category/books.html", urls)
        self.assertIn(f"{self.base_url}/category/toys.html", urls)
        self.assertIn(f"{self.base_url}/product/book1.html", urls)
        self.assertIn(f"{self.base_url}/product/book2.html", urls)
        self.assertIn(f"{self.base_url}/product/toy1.html", urls)

        self.assertNotIn(f"{self.base_url}/private/secret.html", urls)
        self.assertEqual(result.stats.pages_skipped_robots, 1)

        self.assertNotIn("https://external.example.com/ad", urls)

        home = next(p for p in result.pages if p.url == f"{self.base_url}/")
        self.assertEqual(home.title, "Test Shop - Home")
        self.assertEqual(home.meta_description, "A tiny test shop.")
        self.assertIn(f"{self.base_url}/images/banner.png", home.images)

    def test_depth_limit_is_respected_on_real_crawl(self) -> None:
        result = asyncio.run(self._crawl(max_depth=1))
        urls = {p.url for p in result.pages}
        self.assertIn(f"{self.base_url}/category/books.html", urls)
        self.assertNotIn(f"{self.base_url}/product/book1.html", urls)

    def test_export_and_search_work_on_real_crawl_output(self) -> None:
        result = asyncio.run(self._crawl(max_depth=2))
        with tempfile.TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "out.json"
            csv_path = Path(tmp) / "out.csv"
            export_json(result, json_path)
            export_csv(result, csv_path)
            self.assertTrue(json_path.exists())
            self.assertTrue(csv_path.exists())

        python_matches = search_pages(result.pages, "python")
        self.assertEqual(len(python_matches), 1)
        self.assertIn("Book One", python_matches[0].title)

        top_words = dict(keyword_frequency(result.pages, top_n=50))
        self.assertIn("book", top_words)

    def test_404_page_is_recorded_as_failure(self) -> None:
        result = asyncio.run(self._crawl(max_depth=0))
        fetcher = RequestsFetcher("TestCrawler/1.0", 5.0)
        robots = RobotsChecker("TestCrawler/1.0", lambda u: (_ for _ in ()).throw(FileNotFoundError()))
        crawler = Crawler(
            fetcher=fetcher, robots_checker=robots, max_depth=0, max_pages=5,
            concurrency=2, delay_s=0, max_retries=1, retry_delay_s=0, respect_robots=False,
        )
        async def run():
            try:
                return await crawler.crawl([f"{self.base_url}/does-not-exist.html"])
            finally:
                await fetcher.close()
        result2 = asyncio.run(run())
        self.assertEqual(len(result2.pages), 0)
        self.assertEqual(len(result2.failures), 1)


if __name__ == "__main__":
    unittest.main()
