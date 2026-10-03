import json
from pathlib import Path
from unittest.mock import patch

from studio.production_state import Artifact, ProductionManifest
from studio import production_adapter


def test_valid_host_is_reused_without_calling_runway():
    manifest = ProductionManifest(2, "episode", "production")
    manifest.stage("host").status = "complete"
    manifest.stage("host").artifacts = [Artifact("r2://host.mp4", "sha", "production", provider="runway")]
    with patch.object(production_adapter.studio_media, "run_host") as run_host:
        result = production_adapter.run_media_stage(manifest, "host", {}, allow_media_spend=True)
    assert result == []
    run_host.assert_not_called()


def test_host_generation_requires_spend_authorization():
    manifest = ProductionManifest(2, "episode", "production")
    try:
        production_adapter.run_media_stage(manifest, "host", {}, allow_media_spend=False)
    except PermissionError as exc:
        assert "allow_media_spend" in str(exc)
    else:
        raise AssertionError("host generation must fail closed")


def test_assembly_retry_does_not_touch_host_provider():
    manifest = ProductionManifest(2, "episode", "production")
    manifest.stage("host").status = "complete"
    manifest.stage("host").artifacts = [Artifact("r2://host.mp4", "sha", "production", provider="runway")]
    with patch.object(production_adapter.studio_media, "run_host") as run_host, \
         patch.object(production_adapter.studio_media, "run_assembly", return_value=[Path("assembly_manifest.json")]) as assembly:
        result = production_adapter.run_media_stage(manifest, "assembly", {}, allow_media_spend=False)
    assert result == ["assembly_manifest.json"]
    assembly.assert_called_once()
    run_host.assert_not_called()
