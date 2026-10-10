import unittest

from webcrawler.parser import parse_page, same_site

SAMPLE_HTML = """
<html>
<head>
  <title>  Sample   Page  </title>
  <meta name="description" content="  A page about testing.  ">
</head>
<body>
  <h1>Welcome</h1>
  <h2>Section One</h2>
  <p>First paragraph with some words.</p>
  <p>   </p>
  <p>Second paragraph here.</p>
  <a href="/about">About</a>
  <a href="https://other.test/page">External</a>
  <a href="#section">Anchor only</a>
  <a href="javascript:void(0)">JS link</a>
  <a href="mailto:a@b.com">Mail</a>
  <a href="/about">About again (duplicate)</a>
  <img src="/images/pic.png">
  <img src="data:image/png;base64,AAAA">
</body>
</html>
"""


class ParsePageTests(unittest.TestCase):
    def test_title_and_meta_are_cleaned(self) -> None:
        page = parse_page("https://x.test/page", SAMPLE_HTML, 200, depth=1)
        self.assertEqual(page.title, "Sample Page")
        self.assertEqual(page.meta_description, "A page about testing.")

    def test_headings_and_paragraphs(self) -> None:
        page = parse_page("https://x.test/page", SAMPLE_HTML, 200, depth=1)
        self.assertEqual(page.headings, ["Welcome", "Section One"])
        self.assertEqual(
            page.paragraphs, ["First paragraph with some words.", "Second paragraph here."]
        )

    def test_word_count_is_computed(self) -> None:
        page = parse_page("https://x.test/page", SAMPLE_HTML, 200, depth=1)
        self.assertEqual(page.word_count, 5 + 3)

    def test_links_are_resolved_deduplicated_and_filtered(self) -> None:
        page = parse_page("https://x.test/page", SAMPLE_HTML, 200, depth=1)
        self.assertEqual(
            page.links, ["https://x.test/about", "https://other.test/page"]
        )

    def test_images_are_resolved_and_data_uris_kept_out(self) -> None:
        page = parse_page("https://x.test/page", SAMPLE_HTML, 200, depth=1)
        self.assertEqual(page.images, ["https://x.test/images/pic.png"])

    def test_missing_title_is_empty_string(self) -> None:
        page = parse_page("https://x.test/page", "<html><body>no title</body></html>", 200, 0)
        self.assertEqual(page.title, "")

    def test_malformed_html_does_not_raise(self) -> None:
        page = parse_page("https://x.test/page", "<html><p>Unclosed", 200, 0)
        self.assertIn("Unclosed", page.paragraphs[0])


class SameSiteTests(unittest.TestCase):
    def test_same_host_and_scheme(self) -> None:
        self.assertTrue(same_site("https://x.test/a", "https://x.test/b?x=1"))

    def test_different_host(self) -> None:
        self.assertFalse(same_site("https://x.test/a", "https://y.test/a"))

    def test_different_scheme(self) -> None:
        self.assertFalse(same_site("http://x.test/a", "https://x.test/a"))


if __name__ == "__main__":
    unittest.main()
