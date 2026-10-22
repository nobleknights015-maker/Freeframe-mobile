import pytest

from modal_worker.mv_compositor import (
    MV_FACESET,
    placement_manifest,
    regular_character_sheet,
    single_character_sheet,
    validate_cells,
)


def test_faceset_geometry():
    assert (MV_FACESET.width, MV_FACESET.height) == (576, 288)
    assert len(MV_FACESET.boxes()) == 8
    assert MV_FACESET.boxes()[0] == (0, 0, 144, 144)
    assert MV_FACESET.boxes()[-1] == (432, 144, 576, 288)


def test_single_character_geometry():
    spec = single_character_sheet(48, 48)
    assert (spec.width, spec.height) == (144, 192)
    assert len(spec.boxes()) == 12


def test_regular_character_geometry():
    spec = regular_character_sheet(48, 48)
    assert (spec.width, spec.height) == (576, 384)
    assert len(spec.boxes()) == 96


def test_manifest_is_stable_row_major():
    spec = single_character_sheet(32, 48)
    names = [f"frame-{i}" for i in range(12)]
    manifest = placement_manifest(spec, names)
    assert manifest["placements"][0] == {"name": "frame-0", "box": [0, 0, 32, 48]}
    assert manifest["placements"][3] == {"name": "frame-3", "box": [0, 48, 32, 96]}
    assert manifest["placements"][-1]["box"] == [64, 144, 96, 192]


def test_wrong_cell_count_is_rejected():
    with pytest.raises(ValueError, match="expected 12 cells"):
        validate_cells(single_character_sheet(48, 48), 11)


def test_non_positive_cell_dimensions_are_rejected():
    with pytest.raises(ValueError, match="positive"):
        single_character_sheet(0, 48)
