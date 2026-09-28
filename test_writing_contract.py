import tempfile
import unittest
from pathlib import Path

import writing_contract


class WritingContractTests(unittest.TestCase):
    def test_repo_contract_includes_persona_and_mode_exemplars(self):
        rels = {
            path.relative_to(Path('.')).as_posix()
            for path in writing_contract.contract_paths('.')
        }
        self.assertIn('SATOSHI_PERSONA.md', rels)
        for mode in ('argumentative', 'explanatory', 'discovery'):
            self.assertIn(
                f'references/corpus/exemplars/00-satoshi-persona-{mode}.json', rels
            )
        self.assertEqual(len(writing_contract.digest('.')), 64)

    def test_digest_changes_when_contract_content_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'SATOSHI_PERSONA.md').write_text('one\n', encoding='utf-8')
            first = writing_contract.digest(root)
            (root / 'SATOSHI_PERSONA.md').write_text('two\n', encoding='utf-8')
            second = writing_contract.digest(root)
            self.assertNotEqual(first, second)


if __name__ == '__main__':
    unittest.main()
