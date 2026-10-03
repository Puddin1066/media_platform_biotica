import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import runway_qualification as qualification

class QualificationCacheTests(unittest.TestCase):
    def test_resume_keeps_prepared_inputs_and_request_ids(self):
        config={'revision':'cache-test','character_url':'https://media.test/character.mp4','driver_url':'https://media.test/driver.mp4','aleph_prompt':'lab','allow_media_spend':True}
        with tempfile.TemporaryDirectory() as directory:
            original=os.getcwd()
            os.chdir(directory)
            try:
                target=Path('studio/runway_jobs/qualification-cache-test')
                target.mkdir(parents=True)
                source={key:config[key] for key in ('revision','character_url','driver_url','aleph_prompt')}
                (target/'inputs.json').write_text(json.dumps({'source_config':source,'inputs':{'character':{'url':config['character_url']},'driver':{'url':config['driver_url']}}}))
                with patch.object(qualification,'clip',side_effect=AssertionError('Cached media re-encoded')),patch.object(qualification.media_store,'fetch',side_effect=AssertionError('Cached media downloaded')),patch.object(qualification,'git_checkpoint'),patch.object(qualification,'execute',return_value={'media':[{'url':'https://media.test/output.mp4'}]}) as execute:
                    qualification.run(config)
                    requests=[call.args[0] for call in execute.call_args_list]
                    execute.reset_mock()
                    qualification.run(config)
                    self.assertEqual(requests,[call.args[0] for call in execute.call_args_list])
                config['aleph_prompt']='different scene'
                with self.assertRaisesRegex(ValueError,'different inputs'):
                    qualification.run(config)
            finally:
                os.chdir(original)

if __name__=='__main__':
    unittest.main()
