import unittest
from unittest.mock import patch

import satoshi_supervisor


class SupervisorWritingContractTests(unittest.TestCase):
    def test_request_identity_changes_with_writing_contract(self):
        request = {"topic": "TRT", "angle": "cardiovascular safety"}
        with patch("satoshi_supervisor.writing_contract.digest", return_value="a" * 64):
            first = satoshi_supervisor._request_id(request)
        with patch("satoshi_supervisor.writing_contract.digest", return_value="b" * 64):
            second = satoshi_supervisor._request_id(request)
        self.assertNotEqual(first, second)


class UploadedPlateFallbackTests(unittest.TestCase):
    def test_detects_definitive_r2_headobject_404(self):
        message = (
            "botocore.exceptions.ClientError: An error occurred (404) when "
            "calling the HeadObject operation: Not Found"
        )
        self.assertTrue(satoshi_supervisor._definite_uploaded_plate_not_found(message))

    def test_preview_command_passes_visual_mode(self):
        with patch.dict("os.environ", {"RUNWAY_AVATAR_ID": "avatar-1"}, clear=False):
            cmd = satoshi_supervisor._preview_command(
                "outputs/draft.json", "avatar", visual_mode="lean")
        self.assertIn("--visual-mode", cmd)
        self.assertEqual(cmd[cmd.index("--visual-mode") + 1], "lean")


if __name__ == "__main__":
    unittest.main()
