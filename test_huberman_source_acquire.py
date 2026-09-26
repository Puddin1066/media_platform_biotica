import unittest

import huberman_source_acquire as hsa


class HubermanSourceAcquireTests(unittest.TestCase):
    def test_rejects_non_official_url(self):
        with self.assertRaises(ValueError):
            hsa._validate_official_url("https://example.com/episode/foo")

    def test_extracts_only_recognized_public_transcript(self):
        body = " ".join(["mechanism evidence qualification transition"] * 180)
        page = f"""
        <html><body>
        <p>This transcript is currently under human review and may contain errors.</p>
        <p>Andrew Huberman:</p><p>{body}</p>
        </body></html>
        """
        text, status = hsa.extract_public_transcript(page)
        self.assertEqual(status, "public_under_review")
        self.assertGreater(len(text.split()), 500)
        self.assertTrue(text.startswith("Andrew Huberman:"))

    def test_fails_closed_without_transcript_marker(self):
        body = " ".join(["mechanism evidence qualification transition"] * 180)
        page = f"<html><body><p>Andrew Huberman:</p><p>{body}</p></body></html>"
        with self.assertRaises(ValueError):
            hsa.extract_public_transcript(page)


if __name__ == "__main__":
    unittest.main()
