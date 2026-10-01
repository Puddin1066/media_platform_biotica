import json
import tempfile
import unittest
from pathlib import Path

from studio import software_assembler as assembler


class SoftwareAssemblerTests(unittest.TestCase):
    def test_dependencies_python(self):
        text = "import os\nfrom studio.module_runner import main\nimport openai_runtime\n"
        self.assertEqual(assembler.dependencies("x.py", text), ["openai_runtime", "os", "studio"])

    def test_classify(self):
        self.assertEqual(assembler.classify(".github/workflows/test.yml"), "workflow")
        self.assertEqual(assembler.classify("studio/module_runner.py"), "studio")
        self.assertEqual(assembler.classify("remotion/src/index.ts"), "renderer")
        self.assertEqual(assembler.classify("tests/test_x.py"), "test")

    def test_crawl_small_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "studio").mkdir()
            (root / ".github/workflows").mkdir(parents=True)
            (root / "studio/modules.json").write_text(json.dumps({"schema_version": 1, "modules": [{"id": "source"}]}))
            (root / "studio/a.py").write_text("import os\ndef main():\n    pass\n")
            (root / ".github/workflows/x.yml").write_text("on:\n  workflow_dispatch:\n")
            result = assembler.crawl(root)
            self.assertEqual(result["summary"]["module_count"], 1)
            self.assertEqual(result["summary"]["workflow_count"], 1)
            self.assertTrue(result["root_sha256"])

    def test_render_markdown(self):
        plan = {
            "objective": "Produce an MP4",
            "endpoint_contract": {"input": "approved script", "output": "public MP4", "success_criteria": ["reachable URL"]},
            "current_state": ["assembly exists"],
            "gaps": ["preview gate missing"],
            "implementation_plan": [{"order": 1, "change": "Add gate", "paths": ["studio/x.py"], "reason": "prevent bad spend", "tests": ["unit test"]}],
            "verification": ["render passes"],
            "maintenance": ["watch failures"],
            "risk_controls": ["no direct main writes"],
        }
        rendered = assembler.render_markdown(plan)
        self.assertIn("Produce an MP4", rendered)
        self.assertIn("studio/x.py", rendered)
        self.assertIn("no direct main writes", rendered)


if __name__ == "__main__":
    unittest.main()
