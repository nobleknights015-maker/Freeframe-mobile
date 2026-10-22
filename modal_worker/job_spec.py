"""Canonical identity for one reproducible FreeFrame asset job."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json


@dataclass(frozen=True)
class AssetJob:
    path: str
    category: str
    profile: str
    prompt: str
    negative_prompt: str
    seed: int
    width: int
    height: int
    steps: int
    guidance_scale: float
    model_id: str
    style_preset: str
    output_path: str
    reference_id: str | None = None

    def canonical(self) -> dict:
        return asdict(self)

    @property
    def asset_id(self) -> str:
        payload = json.dumps(
            self.canonical(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:24]

    def manifest_record(self) -> dict:
        record = self.canonical()
        record["asset_id"] = self.asset_id
        return record
