import hashlib
import json
from pathlib import Path

from plushbound_enemy_runtime_production import build_canary, load_spec


def test_enemy_canary_contract(tmp_path: Path):
    spec = load_spec()
    manifest = build_canary(tmp_path)
    assets = manifest["assets"]
    assert len(assets) == spec["canary"]["expected_asset_count"] == 8
    assert len({a["path"] for a in assets}) == len(assets)
    required = set(spec["manifest"]["required_fields"])
    for asset in assets:
        assert required <= set(asset)
        assert (asset["width"], asset["height"]) == tuple(spec["crop"]["output_size"])
        assert asset["mode"] == "RGBA"
        path = tmp_path / asset["path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == asset["sha256"]
    assert not any((tmp_path / "quarantine").iterdir())


def test_enemy_canary_is_byte_deterministic(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    m1 = build_canary(first)
    m2 = build_canary(second)
    assert m1 == m2
    for a in m1["assets"]:
        assert (first / a["path"]).read_bytes() == (second / a["path"]).read_bytes()


def test_manifest_serialization_is_stable(tmp_path: Path):
    build_canary(tmp_path)
    raw = (tmp_path / "enemy_runtime_manifest.json").read_text(encoding="utf-8")
    assert json.loads(raw)["family"] == "enemy_runtime"
    assert raw.endswith("\n")
