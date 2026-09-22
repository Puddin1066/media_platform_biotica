import json
import unittest
from pathlib import Path
from unittest.mock import patch

import produce
from prompts import short as short_prompts


class ShortPromptTests(unittest.TestCase):
    def setUp(self):
        self.case = json.loads(Path('cases/mens-health.json').read_text())
        self.plan = [{'hypothesis_id': 'H1', 'query': 'fixture short query'}]

    def test_package_outline(self):
        outline = short_prompts.package_outline(self.case)
        self.assertEqual(outline['format'], 'short')
        self.assertEqual(len(outline['beats']), 5)
        self.assertIn('web_search', outline['assignment'])
        self.assertIn('Peloton', outline['media']['host_ride_plate'])

    def test_produce_uses_short_pack(self):
        body = produce.request_body(self.case, self.plan, 'short', 'model', 4)
        self.assertEqual(body['_prompt_version'], short_prompts.PROMPT_VERSION)
        brief = json.loads(body['input'])
        self.assertEqual(brief['format'], 'short')
        self.assertEqual(brief['required_beats'], short_prompts.BEAT_IDS)
        self.assertIn('vertical SHORT', brief['assignment'])
        self.assertIn('Peloton', brief['assignment'])

    def test_dry_run_reports_prompt_pack(self):
        with patch('produce.call_openai') as api:
            result = produce.run(self.case, self.plan, 'short', 'model', 'unused')
            api.assert_not_called()
            self.assertEqual(result['prompt_pack'], 'short')
            self.assertEqual(result['prompt_version'], short_prompts.PROMPT_VERSION)

    def test_research_cues_bounded(self):
        cues = short_prompts.research_cues(self.case)
        self.assertTrue(1 <= len(cues) <= 4)
        self.assertTrue(all('query' in c for c in cues))


if __name__ == '__main__':
    unittest.main()
