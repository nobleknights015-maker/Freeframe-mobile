from modal_worker.production_pipeline import inspect_master, production_stage


def test_character_rejects_duplicate_subjects_and_routes_extraction():
    result = inspect_master(
        asset_class="character_master", fmt="PNG", width=768, height=1024,
        has_alpha=False, subject_count=2,
    )
    assert not result.accepted
    assert "expected one subject" in result.errors[0]
    assert result.needs_background_removal


def test_guardian_flags_border_text_and_extraction_for_cleanup():
    result = inspect_master(
        asset_class="guardian_master", fmt="PNG", width=768, height=768,
        has_alpha=False, subject_count=1, border_detected=True,
        text_artifact_detected=True,
    )
    assert result.accepted
    assert result.needs_border_cleanup
    assert result.needs_text_cleanup
    assert result.needs_background_removal


def test_environment_rejects_indoor_scene_and_never_extracts_subject():
    result = inspect_master(
        asset_class="environment_master", fmt="PNG", width=1024, height=768,
        has_alpha=False, indoor_detected=True,
    )
    assert not result.accepted
    assert not result.needs_background_removal


def test_sprite_bypasses_semantic_extraction_but_requires_alpha_downstream():
    result = inspect_master(
        asset_class="sprite_master", fmt="PNG", width=512, height=512,
        has_alpha=False, subject_count=1,
    )
    assert result.accepted
    assert not result.needs_background_removal
    assert "downstream engine asset requires alpha before packaging" in result.warnings
    assert production_stage("sprite_master") == "composite_and_validate_engine_sheet"


def test_clean_enemy_master_passes_policy_and_routes_extraction():
    result = inspect_master(
        asset_class="enemy_master", fmt="PNG", width=896, height=640,
        has_alpha=False, subject_count=1,
    )
    assert result.accepted
    assert result.needs_background_removal
    assert "subject master requires semantic background removal" in result.warnings
    assert production_stage("enemy_master") == "cleanup_extract_and_package"


def test_opaque_alpha_container_does_not_skip_semantic_extraction():
    result = inspect_master(
        asset_class="portrait_master", fmt="PNG", width=768, height=768,
        has_alpha=True, subject_count=1,
    )
    assert result.accepted
    assert result.needs_background_removal
