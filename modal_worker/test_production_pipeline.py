from modal_worker.production_pipeline import inspect_master, production_stage


def test_character_rejects_duplicate_subjects():
    result = inspect_master(
        asset_class="character_master", fmt="PNG", width=768, height=1024,
        has_alpha=False, subject_count=2,
    )
    assert not result.accepted
    assert "expected one subject" in result.errors[0]


def test_guardian_flags_border_and_text_for_cleanup():
    result = inspect_master(
        asset_class="guardian_master", fmt="PNG", width=768, height=768,
        has_alpha=False, subject_count=1, border_detected=True,
        text_artifact_detected=True,
    )
    assert result.accepted
    assert result.needs_border_cleanup
    assert result.needs_text_cleanup


def test_environment_rejects_indoor_scene():
    result = inspect_master(
        asset_class="environment_master", fmt="PNG", width=1024, height=768,
        has_alpha=False, indoor_detected=True,
    )
    assert not result.accepted


def test_sprite_requests_background_removal_before_packaging():
    result = inspect_master(
        asset_class="sprite_master", fmt="PNG", width=512, height=512,
        has_alpha=False, subject_count=1,
    )
    assert result.accepted
    assert result.needs_background_removal
    assert production_stage("sprite_master") == "composite_and_validate_engine_sheet"


def test_clean_enemy_master_passes():
    result = inspect_master(
        asset_class="enemy_master", fmt="PNG", width=768, height=768,
        has_alpha=False, subject_count=1,
    )
    assert result.accepted
    assert not result.warnings
