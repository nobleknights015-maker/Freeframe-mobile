from modal_worker.plushbound_enemy_runtime_canary import deterministic_replay


def test_enemy_runtime_canary_replays_identically():
    result = deterministic_replay()
    assert result["ok"], result.get("errors")
    assert result["asset_count"] == 8
