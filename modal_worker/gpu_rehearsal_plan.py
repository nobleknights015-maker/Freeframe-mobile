"""Deterministic 32-generation rehearsal using the four GPU-proven master presets."""
from __future__ import annotations

from production_presets import get_preset

GPU_REHEARSAL_VERSION = "plushbound-gpu-rehearsal-v1"

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
        "small moonmoth plush guardian with soft wings and silver thread accents",
        "small emberfox plush guardian with warm stitched fur and tiny glowing accents",
        "small mossbun plush guardian with leaf-shaped ears and green thread seams",
        "small cloudram plush guardian with curled fleece and pale blue magical accents",
        "small pebbletoad plush guardian with rounded sewn body and earthy thread",
        "small starling plush guardian with fabric feathers and gold thread accents",
        "small riverotter plush guardian with smooth sewn body and aqua thread accents",
        "small acornmouse plush guardian with patchwork ears and woodland thread accents",
    ],
    "plushbound_enemy": [
        "mossback woodland prowler, quadruped forest monster, bark armor plates and leaf mane",
        "thornhide plains stalker, quadruped beast with bramble-like hide and low hunting posture",
        "duskmane ridge prowler, quadruped feline monster with dark shaggy mane",
        "stonepaw ravine hunter, quadruped beast with rocky plates along its back",
        "reedfang marsh prowler, lean quadruped monster with wetland camouflage",
        "frostbrush highland hunter, quadruped beast with pale shaggy fur",
        "sunscale scrubland stalker, quadruped reptilian beast with warm scale plates",
        "rootclaw forest hunter, quadruped monster with gnarled bark-like claws",
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
            request = get_preset(preset_name).apply(prompt, seed=seed)
            requests.append({"asset_id": f"{preset_name}-{index+1:02d}", "preset": preset_name, "request": request})
    assert len(requests) == 32
    return requests
