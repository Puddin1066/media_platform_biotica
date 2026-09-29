import unittest
from unittest.mock import patch

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


class InstagramPublishContainerTests(unittest.TestCase):
    def test_error_status_is_terminal_failure_not_awaiting(self):
        import sqlite3
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as root:
            ledger = str(Path(root) / 'ledger.sqlite')
            with sqlite3.connect(ledger) as db:
                db.execute(
                    'CREATE TABLE posts (job TEXT PRIMARY KEY, state TEXT, '
                    'container TEXT, media TEXT)'
                )
                db.execute(
                    "INSERT INTO posts (job, state, container) VALUES "
                    "('j1', 'container_created', 'c1')"
                )
                db.commit()
            with patch.object(instagram, 'graph', return_value={
                'status_code': 'ERROR', 'status': 'Download failed',
            }):
                result = instagram.publish_container('j1', ledger, '123', 'token')
            self.assertEqual(result['state'], 'failed')
            self.assertEqual(result['status_code'], 'ERROR')
            with sqlite3.connect(ledger) as db:
                state = db.execute('SELECT state FROM posts WHERE job=?', ('j1',)).fetchone()[0]
            self.assertEqual(state, 'container_failed')


if __name__ == '__main__':
    unittest.main()
