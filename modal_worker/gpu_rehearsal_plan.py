"""Deterministic 32-generation rehearsal using production request policy."""
from __future__ import annotations

try:
    from .production_request_builder import build_production_request
except ImportError:  # direct-module compatibility for local CI/tests
    from production_request_builder import build_production_request

GPU_REHEARSAL_VERSION = "plushbound-gpu-rehearsal-v4"

_PROMPTS = {
    "plushbound_character": [
        "adult Elyndor field adventurer with practical layered travel clothes and leather satchel",
        "adult Plushtopia herbalist traveler with sturdy boots and gathered herb pouch",
        "adult road warden traveler with weathered cloak and simple utility belt",
        "adult village courier traveler carrying a compact canvas shoulder bag",
        "adult woodland scout traveler in practical green and brown layered clothing",
        "adult plains guide traveler with sun scarf and durable travel coat",
        "adult artisan traveler carrying rolled cloth and a small tool satchel",
        "adult wandering scholar traveler with field notebook pouch and simple coat",
    ],
    "plushbound_guardian": [
        "small moonmoth Guardian companion species with soft woven wing membranes, silver thread markings and lively flight posture",
        "small emberfox Guardian companion species with warm woven hide, subtle seam markings and tiny glowing accents",
        "small mossbun Guardian companion species with leaf-shaped ears, green thread markings and alert hopping posture",
        "small cloudram Guardian companion species with fiber-fleece coat, curled horns and pale blue magical accents",
        "small pebbletoad Guardian companion species with rounded textile hide, natural seam markings and earthy Thread accents",
        "small starling Guardian companion species with fiber-feather plumage, gold thread markings and lively bird posture",
        "small riverotter Guardian companion species with smooth woven hide, aqua thread markings and playful living posture",
        "small acornmouse Guardian companion species with woven ears, woodland thread markings and alert foraging posture",
    ],
    "plushbound_enemy": [
        "mossback living-textile woodland prowler, low quadruped predator with woven hide, bark plates and thread-fiber mane",
        "thornhide living-textile plains stalker, low quadruped predator with quilted hide, bramble growth and thread bristles",
        "duskmane living-textile ridge prowler, low quadruped feline-shaped predator with woven hide and dark fiber mane",
        "stonepaw living-textile ravine hunter, low quadruped predator with felt-like hide and stone plates along its back",
        "reedfang living-textile marsh prowler, lean low quadruped predator with woven wetland hide and reed-fiber camouflage",
        "frostbrush living-textile highland hunter, low quadruped predator with quilted hide and pale fiber-bristle coat",
        "sunscale living-textile scrubland stalker, low quadruped predator with woven hide and scale-like stitched plates",
        "rootclaw living-textile forest hunter, low quadruped predator with woven hide, gnarled root claws and thread-fiber bristles",
    ],
    "plushbound_environment": [
        "sunny plains of Elyndor with a winding path, wildflowers and distant handcrafted village",
        "quiet Plushtopia woodland trail with mossy stones and a distant lantern shrine",
        "rolling pastoral hills with patchwork farms and a distant windmill settlement",
        "clear river valley crossing with stepping stones and a distant timber bridge",
        "highland meadow route with rocky slopes and a distant watchtower",
        "autumn forest road with amber foliage and a distant cozy waystation",
        "misty marsh boardwalk route with reeds and a distant raised village",
        "coastal grassland path with sea cliffs and a distant harbor settlement",
    ],
}


def rehearsal_requests() -> list[dict]:
    requests = []
    seed = 9100
    for preset_name in sorted(_PROMPTS):
        for index, prompt in enumerate(_PROMPTS[preset_name]):
            seed += 1
            request = build_production_request(preset_name, prompt, seed=seed)
            requests.append({"asset_id": f"{preset_name}-{index+1:02d}", "preset": preset_name, "request": request})
    assert len(requests) == 32
    return requests
