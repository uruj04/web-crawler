import unittest

from webcrawler.config import Settings
from webcrawler.exceptions import ConfigError


class SettingsTests(unittest.TestCase):
    def test_defaults(self) -> None:
        settings = Settings.from_env({})
        self.assertEqual(settings.seed_urls, ("https://books.toscrape.com/",))
        self.assertEqual(settings.max_depth, 2)
        self.assertTrue(settings.respect_robots)

    def test_seed_urls_are_split_and_trimmed(self) -> None:
        settings = Settings.from_env({"SEED_URLS": " https://a.test/ , https://b.test/ "})
        self.assertEqual(settings.seed_urls, ("https://a.test/", "https://b.test/"))

    def test_values_are_converted(self) -> None:
        settings = Settings.from_env(
            {"MAX_DEPTH": "3", "MAX_PAGES": "100", "DELAY_S": "0.5", "RESPECT_ROBOTS": "false"}
        )
        self.assertEqual(settings.max_depth, 3)
        self.assertEqual(settings.max_pages, 100)
        self.assertEqual(settings.delay_s, 0.5)
        self.assertFalse(settings.respect_robots)

    def test_invalid_seed_url_raises(self) -> None:
        with self.assertRaises(ConfigError):
            Settings.from_env({"SEED_URLS": "not-a-url"})

    def test_invalid_numbers_raise(self) -> None:
        for env in ({"MAX_DEPTH": "x"}, {"MAX_PAGES": "0"}, {"CONCURRENCY": "0"}):
            with self.subTest(env=env):
                with self.assertRaises(ConfigError):
                    Settings.from_env(env)


if __name__ == "__main__":
    unittest.main()
