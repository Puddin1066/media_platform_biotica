import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class StudioWorkflowTests(unittest.TestCase):
    def test_every_module_has_a_callable_workflow(self):
        modules = json.loads((ROOT / "studio/modules.json").read_text(encoding="utf-8"))["modules"]
        board = (ROOT / "studio/index.html").read_text(encoding="utf-8")
        self.assertIn("'/api/dispatch'", board)
        self.assertIn("body:JSON.stringify({episode,module,allow_media_spend:media})", board)
        dispatch = (ROOT / "studio/api/dispatch.js").read_text(encoding="utf-8")
        self.assertIn("['assets', 'host'].includes(module) && !allowMediaSpend", dispatch)
        for module in modules:
            slug = module["id"].replace("_", "-")
            path = ROOT / ".github/workflows" / f"studio-{slug}.yml"
            text = path.read_text(encoding="utf-8")
            self.assertIn(f"name: Studio — {module['name']}", text)
            self.assertIn("uses: ./.github/workflows/satoshi-studio-module.yml", text)
            self.assertIn(f"module: {module['id']}", text)
            self.assertNotIn("workflow_dispatch:\n    inputs:\n      module:", text)

    def test_shared_runner_accepts_a_called_module(self):
        text = (ROOT / ".github/workflows/satoshi-studio-module.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_call:", text)
        self.assertIn("python studio/module_runner.py", text)


if __name__ == "__main__":
    unittest.main()
