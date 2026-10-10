import csv
import json
import tempfile
import unittest
from pathlib import Path

from webcrawler.exporter import export_csv, export_json
from webcrawler.models import CrawlResult, CrawlStats, FailedPage, PageData
from webcrawler.search import keyword_frequency, search_pages


def make_page(url: str, title: str, paragraphs: list[str], depth: int = 0) -> PageData:
    return PageData(
        url=url, depth=depth, status_code=200, title=title, headings=[],
        paragraphs=paragraphs, links=[], images=[], meta_description="",
        fetched_at="2026-10-01T10:00:00",
    )


class ExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.result = CrawlResult(
            pages=[
                make_page("https://x.test/a", "Page A", ["Hello world, café."]),
                make_page("https://x.test/b", "Page B", ["Second page."], depth=1),
            ],
            failures=[FailedPage("https://x.test/broken", 1, "Timeout")],
            stats=CrawlStats(pages_visited=2, pages_failed=1, start_url="https://x.test/a", max_depth=1),
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_json_export_round_trips_unicode(self) -> None:
        path = self.dir / "out.json"
        export_json(self.result, path)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["pages"]), 2)
        self.assertIn("café", data["pages"][0]["paragraphs"][0])
        self.assertEqual(data["stats"]["pages_visited"], 2)
        self.assertEqual(len(data["failures"]), 1)

    def test_csv_export_has_expected_rows_and_columns(self) -> None:
        path = self.dir / "out.csv"
        export_csv(self.result, path)
        with path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["title"], "Page A")
        self.assertEqual(rows[0]["word_count"], "3")

    def test_export_creates_missing_directories(self) -> None:
        path = self.dir / "nested" / "dir" / "out.json"
        export_json(self.result, path)
        self.assertTrue(path.exists())


class SearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pages = [
            make_page("https://x.test/a", "Python Guide", ["Learn Python programming today."]),
            make_page("https://x.test/b", "Cooking", ["A guide to baking bread."]),
            make_page("https://x.test/c", "Python Advanced", ["Advanced python topics."]),
        ]

    def test_search_is_case_insensitive(self) -> None:
        results = search_pages(self.pages, "PYTHON")
        self.assertEqual({p.url for p in results}, {"https://x.test/a", "https://x.test/c"})

    def test_search_matches_title_too(self) -> None:
        results = search_pages(self.pages, "cooking")
        self.assertEqual(len(results), 1)

    def test_search_empty_keyword_returns_nothing(self) -> None:
        self.assertEqual(search_pages(self.pages, "   "), [])

    def test_search_no_match(self) -> None:
        self.assertEqual(search_pages(self.pages, "nonexistent"), [])

    def test_keyword_frequency_counts_and_excludes_stop_words(self) -> None:
        freq = dict(keyword_frequency(self.pages))
        self.assertEqual(freq.get("python"), 4)
        self.assertNotIn("a", freq)
        self.assertNotIn("to", freq)

    def test_keyword_frequency_respects_top_n(self) -> None:
        freq = keyword_frequency(self.pages, top_n=2)
        self.assertEqual(len(freq), 2)


if __name__ == "__main__":
    unittest.main()
