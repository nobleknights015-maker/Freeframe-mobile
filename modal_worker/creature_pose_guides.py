"""Procedural project-owned anatomy guides for bounded creature generation tests.

The guides contain no third-party art and no rendering style. They communicate body
orientation, limb count and broad creature proportions separately from the
Plushbound visual reference.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

POSE_GUIDE_VERSION = "creature-pose-guide-v2-diverse-anatomy"


def _canvas(size: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (size, size), "white")
    return image, ImageDraw.Draw(image)


def _scaled(size: int, point: tuple[int, int]) -> tuple[int, int]:
    s = size / 512.0
    return int(point[0] * s), int(point[1] * s)


def _box(size: int, values: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    s = size / 512.0
    return tuple(int(v * s) for v in values)


def _quadruped(size: int, *, low: bool = False, long_body: bool = False) -> Image.Image:
    image, draw = _canvas(size)
    s = size / 512.0
    if long_body:
        body = (65, 225, 365, 315); head = (350, 205, 445, 285); leg_top = 280; feet_y = 385
        leg_xs = (100, 160, 300, 350); leg_w = 26
    elif low:
        body = (95, 225, 350, 325); head = (335, 215, 440, 295); leg_top = 285; feet_y = 400
        leg_xs = (125, 195, 300, 360); leg_w = 34
    else:
        body = (120, 205, 345, 320); head = (330, 185, 435, 290); leg_top = 280; feet_y = 405
        leg_xs = (150, 210, 305, 355); leg_w = 30
    draw.ellipse(_box(size, body), fill="black")
    draw.ellipse(_box(size, head), fill="black")
    for x in leg_xs:
        draw.rounded_rectangle(_box(size, (x, leg_top, x + leg_w, feet_y)), radius=max(2, int(12*s)), fill="black")
    draw.polygon([_scaled(size, (105 if not long_body else 70, 245)), _scaled(size, (45, 205)), _scaled(size, (80, 285))], fill="black")
    return image


def _winged(size: int) -> Image.Image:
    image, draw = _canvas(size)
    draw.ellipse(_box(size, (175, 205, 340, 330)), fill="black")
    draw.ellipse(_box(size, (315, 205, 410, 290)), fill="black")
    draw.polygon([_scaled(size,(220,235)),_scaled(size,(80,110)),_scaled(size,(120,285)),_scaled(size,(230,300))],fill="black")
    draw.polygon([_scaled(size,(275,235)),_scaled(size,(390,95)),_scaled(size,(405,250)),_scaled(size,(300,300))],fill="black")
    for x in (215, 285):
        draw.rounded_rectangle(_box(size,(x,290,x+24,395)),radius=max(2,int(10*size/512)),fill="black")
    draw.polygon([_scaled(size,(180,255)),_scaled(size,(125,225)),_scaled(size,(155,285))],fill="black")
    return image


def _small_biped(size: int) -> Image.Image:
    image, draw = _canvas(size)
    s=size/512.0
    draw.ellipse(_box(size,(185,180,330,330)),fill="black")
    draw.ellipse(_box(size,(225,110,355,225)),fill="black")
    for x in (205,285):
        draw.rounded_rectangle(_box(size,(x,285,x+36,420)),radius=max(2,int(12*s)),fill="black")
    for x,dx in ((190,-55),(315,55)):
        draw.line([_scaled(size,(x,245)),_scaled(size,(x+dx,315))],fill="black",width=max(4,int(22*s)))
    draw.polygon([_scaled(size,(185,265)),_scaled(size,(90,300)),_scaled(size,(175,325))],fill="black")
    return image


def _hexapod(size: int, *, boss: bool) -> Image.Image:
    image, draw = _canvas(size)
    s = size / 512.0
    if boss:
        body=(55,190,360,325); head=(340,175,465,285); xs=(85,135,200,250,315,365); leg_w=30; feet_y=425
    else:
        body=(75,220,360,320); head=(345,205,445,290); xs=(95,145,210,260,325,375); leg_w=24; feet_y=395
    draw.ellipse(_box(size,body),fill="black")
    draw.ellipse(_box(size,head),fill="black")
    # Three visibly separated leg pairs. Offset the middle pair so six feet remain readable.
    for i,x in enumerate(xs):
        y0 = 268 + (i % 2) * 12 if boss else 275 + (i % 2) * 10
        draw.rounded_rectangle(_box(size,(x,y0,x+leg_w,feet_y)),radius=max(2,int(10*s)),fill="black")
        draw.ellipse(_box(size,(x-4,feet_y-8,x+leg_w+6,feet_y+10)),fill="black")
    if boss:
        draw.line([_scaled(size,(385,195)),_scaled(size,(405,105)),_scaled(size,(365,60))],fill="black",width=max(3,int(12*s)))
        draw.line([_scaled(size,(420,200)),_scaled(size,(452,115)),_scaled(size,(490,80))],fill="black",width=max(3,int(12*s)))
    else:
        draw.polygon([_scaled(size,(80,250)),_scaled(size,(35,220)),_scaled(size,(68,280))],fill="black")
    return image


def build_pose_guide(family: str, size: int = 512, *, variant: str | None = None) -> Image.Image:
    if size < 128 or size > 1024:
        raise ValueError("pose guide size must be between 128 and 1024")
    if family == "guardian_friendly":
        selected = variant or "quadruped"
        if selected == "quadruped": return _quadruped(size)
        if selected == "winged": return _winged(size)
        if selected == "biped": return _small_biped(size)
        if selected == "long_low": return _quadruped(size, long_body=True)
        raise ValueError(f"unsupported friendly Guardian pose variant: {selected}")
    if family == "guardian_corrupt":
        if variant not in (None, "low_quadruped"):
            raise ValueError(f"unsupported corrupt Guardian pose variant: {variant}")
        return _quadruped(size, low=True)
    if family == "guardian_boss":
        if variant not in (None, "hexapod"):
            raise ValueError(f"unsupported boss Guardian pose variant: {variant}")
        return _hexapod(size, boss=True)
    if family == "enemy_creature":
        if variant not in (None, "hexapod"):
            raise ValueError(f"unsupported enemy creature pose variant: {variant}")
        return _hexapod(size, boss=False)
    raise ValueError(f"unsupported creature pose-guide family: {family}")
