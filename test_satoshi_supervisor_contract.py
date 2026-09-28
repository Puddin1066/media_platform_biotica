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


if __name__ == "__main__":
    unittest.main()
