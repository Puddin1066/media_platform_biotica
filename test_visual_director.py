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
                         "production_note":"A concrete visual about " + beat,
                         "monologue_moves":mm})
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
        self.assertEqual(value["schema_version"], 2)
        visual_director.validate(value)

    def test_every_render_slot_has_rich_bounded_shot_spec(self):
        value=visual_director.plan(script())
        required={
            "subject","environment","composition","camera","subject_motion",
            "environment_motion","timing","lighting","aesthetic","editorial_function",
            "energy","continuity","overlay_safe_area","literalness","safety"
        }
        for slot in value["render_slots"]:
            self.assertTrue(required.issubset(slot["shot_spec"]))
            self.assertLessEqual(len(slot["prompt"]),1800)
            self.assertIn("Camera:",slot["prompt"])
            self.assertIn("Action:",slot["prompt"])
            self.assertIn("Timing over 5 seconds:",slot["prompt"])
            self.assertIn("Framing:",slot["prompt"])

    def test_visual_grammars_are_differentiated(self):
        value=visual_director.plan(script())
        aesthetics={s["shot_spec"]["aesthetic"] for s in value["render_slots"]}
        cameras={s["shot_spec"]["camera"] for s in value["render_slots"]}
        self.assertGreaterEqual(len(aesthetics),4)
        self.assertGreaterEqual(len(cameras),4)
        self.assertEqual(value["render_slots"][3]["visual_function"],"evidence_receipt")
        self.assertIn("never fabricate exact paper text",value["render_slots"][3]["shot_spec"]["literalness"])

    def test_callback_carries_opening_continuity_reference(self):
        value=visual_director.plan(script())
        opening=value["render_slots"][0]["shot_spec"]
        callback=value["render_slots"][-1]["shot_spec"]
        self.assertEqual(callback["continuity_reference"]["aesthetic"], opening["aesthetic"])
        self.assertEqual(callback["continuity_reference"]["lighting"], opening["lighting"])


if __name__=="__main__":
    unittest.main()
