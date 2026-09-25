import copy
import unittest
import monologue_grammar

def fixture():
    rows = {
        "opening": (
            ("cold_open", "The hot seat may be biologically literal."),
            ("comic_turn", "Your testicles did not sign that lease.")),
        "explanations": (
            ("stakes", "Heat exposure can raise scrotal temperature enough to matter."),
            ("escalation", "That is an awkward thermostat problem.")),
        "evidence": (
            ("receipt", "Human studies report semen changes after repeated heat exposure."),
            ("reveal", "So the signal is not purely theoretical.")),
        "limits": (
            ("reversal", "But observational data cannot isolate every behavior or timing effect."),
            ("qualification", "The evidence has more asterisks than confidence.")),
        "next_test": (
            ("callback", "The hot seat question is whether recovery follows cooling."),
            ("button", "That is the experiment worth watching.")),
    }
    segments = []
    for beat, moves in rows.items():
        mm = [{"function": fn, "text": text} for fn, text in moves]
        segments.append({"beat": beat, "text": " ".join(x["text"] for x in mm),
                         "monologue_moves": mm})
    return {"title": "Fixture", "open_question": "What next?",
            "callback_anchor": "hot seat", "segments": segments}

class MonologueGrammarTests(unittest.TestCase):
    def test_accepts_exact_move_sequence_and_callback(self):
        result = monologue_grammar.validate_script(fixture())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["callback_anchor"], "hot seat")
        self.assertEqual(len(result["move_sequence"]), 10)

    def test_rejects_move_order_drift(self):
        script = fixture()
        script["segments"][1]["monologue_moves"][0]["function"] = "comic_turn"
        with self.assertRaises(ValueError):
            monologue_grammar.validate_script(script)

    def test_rejects_text_not_compiled_from_moves(self):
        script = fixture()
        script["segments"][2]["text"] += " Extra prose."
        with self.assertRaises(ValueError):
            monologue_grammar.validate_script(script)

    def test_rejects_missing_callback_anchor(self):
        script = fixture()
        script["segments"][-1]["monologue_moves"][0]["text"] = "Recovery remains the unresolved question."
        script["segments"][-1]["text"] = " ".join(
            x["text"] for x in script["segments"][-1]["monologue_moves"])
        with self.assertRaises(ValueError):
            monologue_grammar.validate_script(script)

if __name__ == "__main__":
    unittest.main()
