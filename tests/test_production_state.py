from studio.production_state import Artifact, ProductionManifest, checksum_failure


def test_resume_starts_at_failed_assembly_and_reuses_runway_host():
    manifest = ProductionManifest(
        schema_version=2,
        episode_id="northeastern-video-2026-10-01",
        production_id="northeastern-video-r12-test",
        publish_instagram=True,
    )
    for stage in ("request", "script", "prosody", "voice", "audio_review", "alignment", "visual_plan", "assets"):
        manifest.stage(stage).status = "complete"

    manifest.stage("host").status = "complete"
    manifest.stage("host").artifacts.append(
        Artifact(
            uri="r2://bucket/host.mp4",
            sha256="host-sha",
            production_id=manifest.production_id,
            provider="runway",
            provider_job_id="runway-job-1",
            source_hash="source-sha",
            narration_hash="voice-sha",
        )
    )
    manifest.stage("assembly").status = "failed"

    assert manifest.host_reusable("source-sha", "voice-sha") is True
    assert manifest.first_incomplete_stage() == "assembly"


def test_host_is_not_reused_for_changed_narration():
    manifest = ProductionManifest(2, "episode", "production")
    manifest.stage("host").status = "complete"
    manifest.stage("host").artifacts.append(
        Artifact("r2://host", "sha", "production", source_hash="source", narration_hash="old")
    )
    assert manifest.host_reusable("source", "new") is False


def test_checksum_failure_is_actionable():
    failure = checksum_failure(
        shot_id="shot_07",
        r2_key="studio/p/assets/shot_07.png",
        expected="abc",
        actual="def",
        production_id="p",
        generating_stage="assets",
        safe_to_regenerate=True,
    )
    assert failure["code"] == "ASSET_INTEGRITY_FAILURE"
    assert failure["shot_id"] == "shot_07"
    assert failure["expected_sha256"] == "abc"
    assert failure["actual_sha256"] == "def"
    assert failure["safe_to_regenerate"] is True
