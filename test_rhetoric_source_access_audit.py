import json
import unittest
from pathlib import Path


class RhetoricSourceAccessAuditTests(unittest.TestCase):
    def test_audit_covers_manifest_and_is_currently_public(self):
        root = Path(__file__).parent
        manifest = json.loads((root / "rhetoric_source_manifest.json").read_text())
        audit = json.loads((root / "rhetoric_source_access_audit.json").read_text())
        manifest_ids = {row["id"] for row in manifest["episodes"]}
        audited_ids = {row["id"] for row in audit["episodes"]}
        self.assertEqual(manifest_ids, audited_ids)
        self.assertEqual(len(manifest_ids), 30)
        self.assertEqual(audit["result"]["public_transcript_exposed"], 30)
        self.assertEqual(audit["result"]["premium_only_or_gated"], 0)
        self.assertEqual(audit["result"]["unavailable"], 0)
        self.assertTrue(all(row["access"] == "public_transcript_exposed" for row in audit["episodes"]))


if __name__ == "__main__":
    unittest.main()
