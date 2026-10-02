import io
import json
import os
from unittest.mock import patch

from studio import production_store


class Missing(Exception):
    response = {"Error": {"Code": "NoSuchKey"}}


class FakeR2:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.objects[(Bucket, Key)] = bytes(Body)

    def get_object(self, Bucket, Key):
        try:
            body = self.objects[(Bucket, Key)]
        except KeyError:
            raise Missing()
        return {"Body": io.BytesIO(body)}


def test_manifest_round_trip_and_history_snapshot():
    r2 = FakeR2()
    manifest = {"episode_id": "e", "production_id": "p", "schema_version": 2, "stages": {}}
    with patch.dict(os.environ, {"R2_BUCKET": "bucket"}):
        saved = production_store.save_manifest(manifest, client=r2)
        loaded = production_store.load_manifest("e", "p", client=r2)
    assert saved["key"] == "studio/e/p/production_manifest.json"
    assert "/manifests/" in saved["history_key"]
    assert loaded["episode_id"] == "e"
    assert loaded["production_id"] == "p"
    assert "updated_at" in loaded


def test_missing_manifest_returns_none():
    with patch.dict(os.environ, {"R2_BUCKET": "bucket"}):
        assert production_store.load_manifest("e", "missing", client=FakeR2()) is None


def test_identity_mismatch_fails_closed():
    r2 = FakeR2()
    key = "studio/e/p/production_manifest.json"
    r2.objects[("bucket", key)] = json.dumps({"episode_id": "other", "production_id": "p"}).encode()
    with patch.dict(os.environ, {"R2_BUCKET": "bucket"}):
        try:
            production_store.load_manifest("e", "p", client=r2)
        except RuntimeError as exc:
            assert "identity mismatch" in str(exc)
        else:
            raise AssertionError("identity mismatch must fail closed")
