import unittest

from webcrawler.robots import RobotsChecker


class FakeFetcher:
    """Returns canned robots.txt text per origin, or raises for 'no robots.txt'."""

    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.calls: list[str] = []

    def __call__(self, url: str) -> str:
        self.calls.append(url)
        if url not in self.pages:
            raise FileNotFoundError(url)
        return self.pages[url]


class RobotsCheckerTests(unittest.TestCase):
    def test_allows_everything_when_no_robots_txt(self) -> None:
        checker = RobotsChecker("TestBot", FakeFetcher({}))
        self.assertTrue(checker.is_allowed("https://x.test/anything"))

    def test_disallowed_path_is_blocked(self) -> None:
        fetcher = FakeFetcher(
            {"https://x.test/robots.txt": "User-agent: *\nDisallow: /private/\n"}
        )
        checker = RobotsChecker("TestBot", fetcher)
        self.assertFalse(checker.is_allowed("https://x.test/private/secret"))
        self.assertTrue(checker.is_allowed("https://x.test/public/page"))

    def test_malformed_robots_txt_allows_everything(self) -> None:
        fetcher = FakeFetcher({"https://x.test/robots.txt": "\x00\x01 not valid at all \ufffe"})
        checker = RobotsChecker("TestBot", fetcher)
        self.assertTrue(checker.is_allowed("https://x.test/page"))

    def test_rules_are_fetched_once_per_site(self) -> None:
        fetcher = FakeFetcher({"https://x.test/robots.txt": "User-agent: *\nDisallow:\n"})
        checker = RobotsChecker("TestBot", fetcher)
        checker.is_allowed("https://x.test/a")
        checker.is_allowed("https://x.test/b")
        checker.is_allowed("https://x.test/c")
        self.assertEqual(fetcher.calls, ["https://x.test/robots.txt"])

    def test_different_sites_get_their_own_rules(self) -> None:
        fetcher = FakeFetcher(
            {
                "https://a.test/robots.txt": "User-agent: *\nDisallow: /blocked\n",
                "https://b.test/robots.txt": "User-agent: *\nDisallow:\n",
            }
        )
        checker = RobotsChecker("TestBot", fetcher)
        self.assertFalse(checker.is_allowed("https://a.test/blocked"))
        self.assertTrue(checker.is_allowed("https://b.test/blocked"))


class LoadRulesTests(unittest.TestCase):
    def test_load_rules_from_already_fetched_text(self) -> None:
        checker = RobotsChecker("TestBot", FakeFetcher({}))
        checker.load_rules("https://x.test/", "User-agent: *\nDisallow: /admin\n")
        self.assertFalse(checker.is_allowed("https://x.test/admin/panel"))
        self.assertTrue(checker.is_allowed("https://x.test/home"))

    def test_load_rules_with_none_means_allow_all(self) -> None:
        checker = RobotsChecker("TestBot", FakeFetcher({}))
        checker.load_rules("https://x.test/", None)
        self.assertTrue(checker.is_allowed("https://x.test/anything"))

    def test_loaded_rules_prevent_any_further_fetch(self) -> None:
        fetcher = FakeFetcher({"https://x.test/robots.txt": "User-agent: *\nDisallow: /blocked\n"})
        checker = RobotsChecker("TestBot", fetcher)
        checker.load_rules("https://x.test/", "User-agent: *\nDisallow:\n")
        checker.is_allowed("https://x.test/blocked")
        self.assertEqual(fetcher.calls, [])


if __name__ == "__main__":
    unittest.main()
