import unittest

import instagram


class InstagramGraphHostTests(unittest.TestCase):
    def test_igaa_token_uses_instagram_graph_host(self):
        self.assertEqual(
            instagram.graph_host('IGAAabcdefghijklmnopqrstuvwxyz'),
            'https://graph.instagram.com/',
        )

    def test_facebook_page_token_uses_facebook_graph_host(self):
        self.assertEqual(
            instagram.graph_host('EAAXabcdefghijklmnopqrstuvwxyz'),
            'https://graph.facebook.com/',
        )


if __name__ == '__main__':
    unittest.main()
