import unittest
import visual_director

def script():
    rows = {
        "opening": [("cold_open", "The hot seat may be biologically literal."), ("comic_turn", "Your testicles did not sign that lease.")],
        "explanations": [("stakes", "Heat exposure can raise scrotal temperature enough to matter."), ("escalation", "That is an awkward thermostat problem.")],
        "evidence": [("receipt", "Human studies report semen changes after repeated heat exposure."), ("reveal", "So the signal is not purely theoretical.")],
        "limits": [("reversal", "But observational data cannot isolate every behavior or timing effect."), ("qualification", "The evidence has more asterisks than confidence.")],
        "next_test": [("callback", "The hot seat question is whether recovery follows cooling."), ("button", "That is the experiment worth watching.")],
    }
    segments=[]
    for beat,moves in rows.items():
        mm=[{"function":f,"text":t} for f,t in moves]
        segments.append({"beat":beat,"text":" ".join(x["text"] for x in mm),
                         "source_urls":["https://example.org/"+beat],
                         "production_note":"fixture","monologue_moves":mm})
    return {
        "title":"Fixture","open_question":"What next?","callback_anchor":"hot seat",
        "positioning":{"positioned_premise":"Heat may affect sperm, but magnitude and reversibility matter."},
        "segments":segments
    }

class VisualDirectorTests(unittest.TestCase):
    def test_maps_all_ten_moves(self):
        value=visual_director.plan(script())
        self.assertEqual([e["visual_function"] for e in value["events"]], [
            "pattern_interrupt","absurd_contrast","personal_consequence","scale_or_intensify",
            "evidence_receipt","annotation_or_punch_in","contrast_reset","limitation_overlay",
            "callback_visual","reaction_or_end_card"
        ])

    def test_compiles_to_existing_six_slot_renderer(self):
        value=visual_director.plan(script())
        self.assertEqual(len(value["render_slots"]),6)
        visual_director.validate(value)

if __name__=="__main__":
    unittest.main()
