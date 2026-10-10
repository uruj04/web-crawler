"""End-to-end CLI tests, with the real network layer replaced by a fake fetcher."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from webcrawler import cli
from webcrawler.config import Settings


def page(title: str, links: list[str]) -> str:
    link_tags = "".join(f'<a href="{href}">x</a>' for href in links)
    return f"<html><head><title>{title}</title></head><body><p>About {title}.</p>{link_tags}</body></html>"


class FakeFetcher:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    async def fetch(self, url: str):
        from webcrawler.models import FetchResult

        if url not in self.pages:
            return FetchResult(url, 404, "")
        return FetchResult(url, 200, self.pages[url])

    async def fetch_text_or_none(self, url: str):
        return None

    async def close(self) -> None:
        pass


class CrawlCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.output_dir = Path(self._tmp.name) / "output"
        self.site = {
            "https://x.test/": page("Home", ["https://x.test/about"]),
            "https://x.test/about": page("About Us", []),
        }

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_crawl_exports_json_and_csv(self) -> None:
        settings = Settings(
            seed_urls=("https://x.test/",), max_depth=2, max_pages=10, concurrency=2,
            delay_s=0, max_retries=1, retry_delay_s=0, respect_robots=False,
            output_dir=self.output_dir, log_file=self.output_dir / "log.txt",
        )
        with mock.patch("webcrawler.cli.AiohttpFetcher", return_value=FakeFetcher(self.site)):
            args = cli.build_parser().parse_args(["crawl"])
            exit_code = cli.command_crawl(args, settings)

        self.assertEqual(exit_code, 0)
        json_path = self.output_dir / "crawl_result.json"
        csv_path = self.output_dir / "crawl_result.csv"
        self.assertTrue(json_path.exists())
        self.assertTrue(csv_path.exists())
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["pages"]), 2)
        self.assertEqual(data["stats"]["pages_visited"], 2)

    def test_crawl_depth_override(self) -> None:
        settings = Settings(
            seed_urls=("https://x.test/",), max_depth=5, max_pages=10, concurrency=2,
            delay_s=0, max_retries=1, retry_delay_s=0, respect_robots=False,
            output_dir=self.output_dir, log_file=self.output_dir / "log.txt",
        )
        with mock.patch("webcrawler.cli.AiohttpFetcher", return_value=FakeFetcher(self.site)):
            args = cli.build_parser().parse_args(["crawl", "--depth", "0"])
            cli.command_crawl(args, settings)

        data = json.loads((self.output_dir / "crawl_result.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["pages"]), 1)


class SearchAndKeywordsCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.output_dir = Path(self._tmp.name) / "output"
        self.output_dir.mkdir(parents=True)
        self.settings = Settings(output_dir=self.output_dir)

        export = {
            "stats": {"pages_visited": 2},
            "failures": [],
            "pages": [
                {
                    "url": "https://x.test/a", "depth": 0, "status_code": 200,
                    "title": "Python Guide", "headings": [], "paragraphs": ["Learn Python here."],
                    "links": [], "images": [], "meta_description": "", "fetched_at": "t",
                    "word_count": 3,
                },
                {
                    "url": "https://x.test/b", "depth": 1, "status_code": 200,
                    "title": "Cooking", "headings": [], "paragraphs": ["A baking guide."],
                    "links": [], "images": [], "meta_description": "", "fetched_at": "t",
                    "word_count": 3,
                },
            ],
        }
        (self.output_dir / "crawl_result.json").write_text(json.dumps(export), encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_search_finds_matching_pages(self) -> None:
        args = cli.build_parser().parse_args(["search", "python"])
        exit_code = cli.command_search(args, self.settings)
        self.assertEqual(exit_code, 0)

    def test_search_with_missing_export_raises_cleanly(self) -> None:
        empty_settings = Settings(output_dir=Path(self._tmp.name) / "nope")
        args = cli.build_parser().parse_args(["search", "python"])
        with self.assertRaises(Exception):
            cli.command_search(args, empty_settings)

    def test_keywords_command_runs(self) -> None:
        args = cli.build_parser().parse_args(["keywords"])
        exit_code = cli.command_keywords(args, self.settings)
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
