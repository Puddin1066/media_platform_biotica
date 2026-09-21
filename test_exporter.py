import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from exporter import export, files_for, DESTINATIONS


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads(Path('cases/mens-health.json').read_text())

    def test_all_formats_have_manifest_and_outline(self):
        for name in DESTINATIONS:
            _, files = files_for(self.packet, name)
            manifest = json.loads(files['manifest.json'])
            self.assertFalse(manifest['publishable'])
            self.assertFalse(manifest['uploaded'])
            self.assertIn('NOT FOR PUBLICATION', files['outline.md'])
            for path, checksum in manifest['sha256'].items():
                self.assertEqual(checksum, hashlib.sha256(files[path].encode()).hexdigest())

    def test_repeat_export_reuses_path(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(export(self.packet, 'short', root), export(self.packet, 'short', root))

    def test_edited_export_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            path = export(self.packet, 'short', root) / 'outline.md'
            path.write_text('User revision')
            with self.assertRaises(ValueError):
                export(self.packet, 'short', root)
            self.assertEqual(path.read_text(), 'User revision')

    def test_unknown_format_rejected(self):
        with self.assertRaises(ValueError):
            files_for(self.packet, '../escape')
