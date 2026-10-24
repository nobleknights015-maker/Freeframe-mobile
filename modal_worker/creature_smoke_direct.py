"""Two-image post-deploy smoke test for creature conditioning on Vera's production worker."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import modal

from modal_worker.production_request_builder import build_production_request

OUT = Path("creature-smoke-output")
OUT.mkdir(exist_ok=True)

CASES = [
    (
        "guardian",
        "plushbound_guardian",
        "small living emberfox Guardian companion native to Plushtopia, alert friendly posture, woven biological textile hide, clear functional anatomy, subtle Thread magic accents, living creature not a retail toy",
        771001,
    ),
    (
        "enemy",
        "plushbound_enemy",
        "Elyndor mossback prowler, hostile low nonhuman living-textile battle creature, woven biological hide, believable quadruped weight and locomotion, dangerous readable silhouette, single monster only",
        771002,
    ),
]


def main() -> None:
    generator = modal.Cls.from_name("freeframe-worker", "FreeFrameProductionGenerator")()
    results = []
    for name, preset, prompt, seed in CASES:
        request = build_production_request(preset, prompt, seed=seed)
        payload = generator.generate.remote(request)
        raw = base64.b64decode(payload["image_base64"], validate=True)
        if payload.get("mime_type") != "image/png":
            raise RuntimeError(f"{name}: expected image/png")
        if hashlib.sha256(raw).hexdigest() != payload.get("sha256"):
            raise RuntimeError(f"{name}: SHA-256 mismatch")
        path = OUT / f"{name}.png"
        path.write_bytes(raw)
        results.append({
            "name": name,
            "preset": preset,
            "seed": payload.get("seed"),
            "model": payload.get("model"),
            "renderer_route": payload.get("renderer_route"),
            "width": payload.get("width"),
            "height": payload.get("height"),
            "bytes": payload.get("bytes"),
            "sha256": payload.get("sha256"),
            "elapsed_seconds": payload.get("elapsed_seconds"),
            "structural_conditioning": payload.get("structural_conditioning"),
            "ok": True,
        })
    (OUT / "report.json").write_text(json.dumps({"count": len(results), "results": results}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"count": len(results), "ok": True, "elapsed_seconds": sum(float(x.get("elapsed_seconds") or 0) for x in results)}))


if __name__ == "__main__":
    main()
