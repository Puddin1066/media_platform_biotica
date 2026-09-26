import unittest

import studio_episode


class StudioEpisodeTests(unittest.TestCase):
    def test_user_topic_is_authoritative(self):
        episode = studio_episode.new_episode("Are sperm counts really collapsing?")
        self.assertTrue(episode["topic"]["authoritative"])
        self.assertEqual(episode["status"], "topic")

    def test_classification_does_not_choose_or_rewrite_topic(self):
        episode = studio_episode.new_episode("Who defines normal testosterone?")
        classified = studio_episode.classify(episode, {
            "pillar": "conspiracy_files",
            "sponsor_fit": ["diagnostics"],
            "audience_job": "Investigate incentives without assuming conspiracy",
        })
        self.assertEqual(classified["topic"], episode["topic"])
        self.assertEqual(classified["classification"]["pillar"], "conspiracy_files")

    def test_stages_advance_in_order(self):
        episode = studio_episode.new_episode("TRT and fertility")
        research = studio_episode.attach(episode, "research", {"bundle": "research.json"})
        script = studio_episode.attach(research, "script", {"storyboard": "storyboard.json"})
        visual = studio_episode.attach(script, "visual_plan", {"plan": "footage-plan.json"})
        self.assertEqual(visual["status"], "visual_plan")
        self.assertEqual(studio_episode.production_summary(visual)["next_stage"], "assets")

    def test_cannot_skip_required_stage(self):
        episode = studio_episode.new_episode("ED diagnostics")
        with self.assertRaisesRegex(ValueError, "before research"):
            studio_episode.attach(episode, "script", {"script": "draft"})

    def test_cannot_change_topic_identity(self):
        episode = studio_episode.new_episode("Male contraception")
        episode["topic"]["text"] = "Different topic"
        with self.assertRaisesRegex(ValueError, "Episode ID"):
            studio_episode.validate(episode)


if __name__ == "__main__":
    unittest.main()
