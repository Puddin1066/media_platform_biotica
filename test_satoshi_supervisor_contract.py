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

    def test_ignores_unrelated_runtime_errors(self):
        self.assertFalse(
            satoshi_supervisor._definite_uploaded_plate_not_found(
                "runwayml.BadRequestError: not enough credits"
            )
        )


if __name__ == "__main__":
    unittest.main()
