"""Offline contracts for lean Commons insets (no Gen-4.5 spend)."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lean_visuals
import unreviewed_video_preview as uvp
import visual_director


class LeanVisualsTests(unittest.TestCase):
    def draft(self):
        rows = {
            "opening": [
                ("cold_open", "The hot seat may be biologically literal."),
                ("comic_turn", "Your testicles did not sign that lease.")],
            "explanations": [
                ("stakes", "Heat exposure can raise scrotal temperature enough to matter."),
                ("escalation", "That is an awkward thermostat problem.")],
            "evidence": [
                ("receipt", "Human studies report semen changes after repeated heat exposure."),
                ("reveal", "So the signal is not purely theoretical.")],
            "limits": [
                ("reversal", "But observational data cannot isolate every behavior or timing effect."),
                ("qualification", "The evidence has more asterisks than confidence.")],
            "next_test": [
                ("callback", "The hot seat question is whether recovery follows cooling."),
                ("button", "That is the experiment worth watching.")],
        }
        segments = []
        for beat, moves in rows.items():
            mm = [{"function": fn, "text": text} for fn, text in moves]
            segments.append({
                "beat": beat,
                "text": " ".join(m["text"] for m in mm),
                "source_urls": ["https://example.org/" + beat],
                "production_note": "Abstract visual for " + beat,
                "monologue_moves": mm,
            })
        return {
            "status": "review_required", "format": "short",
            "case": {"question": "Fixture topic?"},
            "script": {
                "title": "Fixture",
                "open_question": "What next?",
                "callback_anchor": "hot seat",
                "positioning": {
                    "territory": "fertility_reproductive",
                    "male_consequence": "fertility",
                    "prevailing_belief": "Heat is either harmless or obviously catastrophic for sperm.",
                    "evidence_conflict": "Human studies suggest changes, but magnitude and reversibility vary.",
                    "evidence_receipt": "A human study reports semen changes after repeated heat exposure.",
                    "evidence_receipt_url": "https://example.org/evidence",
                    "audience_tension": "Men want heat benefits without quietly trading off fertility.",
                    "share_trigger": "A sauna-using man could send this to a friend tracking fertility.",
                    "positioned_premise": "Heat may affect sperm, but the key question is how much and whether it reverses.",
                    "hook_variants": [
                        {"type": "threat_tradeoff", "text": "Your sauna habit may be costing your sperm more than you think."},
                        {"type": "conflict", "text": "Sauna is sold as healthy, but your sperm may have a different opinion."},
                        {"type": "counterintuitive_receipt", "text": "Human semen data make the sauna story much less simple."}
                    ],
                },
                "segments": segments,
            }
        }

    def test_query_for_slot_uses_overlay_and_topic(self):
        slot = {"overlay_text": "PCR gel", "visual_function": "evidence_receipt"}
        self.assertIn("PCR gel", lean_visuals.query_for_slot(slot, "Haemanthus"))
        self.assertIn("Haemanthus", lean_visuals.query_for_slot(slot, "Haemanthus"))

    def test_dry_collect_returns_six_commons_placeholders(self):
        with tempfile.TemporaryDirectory() as d:
            direction = visual_director.plan(self.draft()["script"])
            rows = lean_visuals.collect_commons_insets(
                d, direction, draft_topic="Fixture topic?", live=False)
            self.assertEqual(len(rows), 6)
            self.assertTrue(all(r["candidate"]["provider"] == "commons" for r in rows))
            self.assertTrue(all(r["visual_type"] == "source" for r in rows))
            self.assertTrue(all(r["state"] == "dry_run" for r in rows))

    def test_build_plan_preserves_commons_credit(self):
        draft = self.draft()
        board = uvp.build_board(draft)
        direction = visual_director.plan(draft["script"])
        with tempfile.TemporaryDirectory() as d:
            rows = lean_visuals.collect_commons_insets(
                d, direction, draft_topic=board["topic"], live=False)
            plan = uvp.build_plan(d, board, rows, direction)
        self.assertEqual(plan["shots"][0]["provider"], "commons")
        self.assertEqual(plan["shots"][0]["visual_type"], "source")
        self.assertEqual(plan["shots"][0]["selection_basis"], "commons_still_lean_visuals")
        self.assertNotEqual(plan["shots"][0]["credit"], "AI-GENERATED ILLUSTRATION")

    def test_lean_budget_skips_gen45_visual_credits(self):
        board = uvp.build_board(self.draft())
        estimate = uvp.estimated_runway_credits(board, visual_count=0, visual_mode="lean")
        self.assertEqual(estimate["visuals"], 0)
        self.assertEqual(estimate["visual_mode"], "lean")
        self.assertEqual(estimate["avatar_max"], 12)

    def test_lean_dry_run_does_not_call_runway_visuals(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.json"
            draft.write_text(json.dumps(self.draft()))
            with patch.dict("os.environ", {"SATOSHI_VISUAL_MODE": "lean"}, clear=False), \
                 patch("unreviewed_video_preview.episode.submit_audio",
                       return_value={"opening": {"state": "dry_run"}}) as audio, \
                 patch("unreviewed_video_preview.episode.submit_visual") as visual:
                result = uvp.run(draft, Path(d) / "episode", "voice", "avatar")
            self.assertEqual(result["status"], "dry_run")
            self.assertEqual(result["visual_mode"], "lean")
            self.assertEqual(result["runway_budget"]["visuals"], 0)
            self.assertEqual(len(result["visuals"]), 6)
            self.assertEqual(result["visuals"][0]["candidate"]["provider"], "commons")
            visual.assert_not_called()
            audio.assert_called_once()

    def test_ai_dry_run_still_submits_six_gen45_specs(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.json"
            draft.write_text(json.dumps(self.draft()))
            with patch.dict("os.environ", {"SATOSHI_VISUAL_MODE": "ai"}, clear=False), \
                 patch("unreviewed_video_preview.episode.submit_audio",
                       return_value={"opening": {"state": "dry_run"}}) as audio, \
                 patch("unreviewed_video_preview.episode.submit_visual",
                       return_value={"state": "dry_run", "specification": {}}) as visual:
                result = uvp.run(draft, Path(d) / "episode", "voice", "avatar",
                                 visual_mode="ai")
            self.assertEqual(result["visual_mode"], "ai")
            self.assertEqual(visual.call_count, 6)
            self.assertEqual(result["runway_budget"]["visuals"], 360)
            audio.assert_called_once()

    def test_live_collect_writes_mp4_when_discover_and_ffmpeg_available(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg required")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            direction = visual_director.plan(self.draft()["script"])
            # Tiny real JPEG via ffmpeg so download→encode path is exercised.
            jpeg = root / "seed.jpg"
            subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i",
                 "color=c=red:s=320x180:d=1", "-frames:v", "1", str(jpeg)],
                check=True)
            fake = {
                "id": "commons-image:1",
                "provider": "commons",
                "title": "Test still",
                "page_url": "https://commons.wikimedia.org/wiki/File:Test",
                "direct_url": "https://example.org/test.jpg",
                "license_name": "CC BY 4.0",
                "artist_html": "Fixture Artist",
            }

            def fake_download(url, destination, max_bytes=40 * 1024 * 1024):
                Path(destination).write_bytes(jpeg.read_bytes())
                return jpeg.stat().st_size

            with patch.object(lean_visuals, "download_https", side_effect=fake_download):
                rows = lean_visuals.collect_commons_insets(
                    root, direction, draft_topic="Fixture", live=True,
                    discover=lambda query, limit=8: [fake])
            self.assertEqual(len(rows), 6)
            self.assertTrue(all(r["state"] == "collected" for r in rows))
            for row in rows:
                media = root / row["candidate"]["media_source"]
                self.assertTrue(media.is_file())
                self.assertGreater(media.stat().st_size, 0)
            catalog = json.loads(
                (root / "generated" / "commons-visuals" / "catalog.json").read_text())
            self.assertEqual(len(catalog["candidates"]), 6)


class CommonsImageDiscoveryTests(unittest.TestCase):
    def test_discover_commons_images_filters_to_bitmaps(self):
        import footage
        payload = {
            "query": {
                "pages": {
                    "1": {
                        "pageid": 1,
                        "title": "File:Gel.png",
                        "imageinfo": [{
                            "mime": "image/png",
                            "url": "https://upload.wikimedia.org/gel.png",
                            "width": 800,
                            "height": 600,
                            "extmetadata": {
                                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                "LicenseUrl": {"value": "https://creativecommons.org/"},
                                "Artist": {"value": "Lab"},
                                "Credit": {"value": "Lab"},
                            },
                        }],
                    },
                    "2": {
                        "pageid": 2,
                        "title": "File:Diagram.svg",
                        "imageinfo": [{
                            "mime": "image/svg+xml",
                            "url": "https://upload.wikimedia.org/diagram.svg",
                            "extmetadata": {},
                        }],
                    },
                }
            }
        }
        with patch.object(footage, "fetch_json", return_value=payload):
            rows = footage.discover_commons_images("PCR gel", limit=8)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "commons-image:1")
        self.assertEqual(rows[0]["media_kind"], "image")
        self.assertEqual(rows[0]["license_name"], "CC BY-SA 4.0")


if __name__ == "__main__":
    unittest.main()
