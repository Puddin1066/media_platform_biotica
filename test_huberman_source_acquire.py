import unittest

import huberman_source_acquire as hsa


class HubermanSourceAcquireTests(unittest.TestCase):
    def test_rejects_non_official_url(self):
        with self.assertRaises(ValueError):
            hsa._validate_official_url("https://example.com/episode/foo")

    def test_extracts_after_public_transcript_disclaimer_without_speaker_label(self):
        body = " ".join(["mechanism evidence qualification transition"] * 180)
        page = f"""
        <html><body>
        <p>Show notes and timestamps that should not enter the transcript.</p>
        <p>This transcript is currently under human review and may contain errors. The fully reviewed version will be posted as soon as it is available.</p>
        <p>Welcome to the podcast. I'm Andrew Huberman.</p><p>{body}</p>
        </body></html>
        """
        text, status = hsa.extract_public_transcript(page)
        self.assertEqual(status, "public_under_review")
        self.assertGreater(len(text.split()), 500)
        self.assertTrue(text.startswith("Welcome to the podcast"))
        self.assertNotIn("Show notes and timestamps", text)

    def test_legacy_short_disclaimer_is_supported(self):
        body = " ".join(["mechanism evidence qualification transition"] * 180)
        page = f"""
        <html><body>
        <p>This transcript is currently under human review</p>
        <p>Andrew Huberman:</p><p>{body}</p>
        </body></html>
        """
        text, status = hsa.extract_public_transcript(page)
        self.assertEqual(status, "public_under_review")
        self.assertGreater(len(text.split()), 500)
        self.assertTrue(text.startswith("Andrew Huberman:"))

    def test_fails_closed_without_transcript_marker(self):
        body = " ".join(["mechanism evidence qualification transition"] * 180)
        page = f"<html><body><p>Welcome to the podcast.</p><p>{body}</p></body></html>"
        with self.assertRaises(ValueError):
            hsa.extract_public_transcript(page)

    def test_fails_closed_on_incomplete_text_after_marker(self):
        page = """
        <html><body>
        <p>This transcript is currently under human review</p>
        <p>Welcome to the podcast. Short transcript.</p>
        </body></html>
        """
        with self.assertRaises(ValueError):
            hsa.extract_public_transcript(page)


if __name__ == "__main__":
    unittest.main()
