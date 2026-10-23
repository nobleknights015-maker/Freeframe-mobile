"""Procedural project-owned anatomy guides for bounded creature generation tests.

The guides are deliberately simple silhouettes. They contain no third-party art and
no rendering style. Their sole job is to communicate body orientation, limb count,
and broad creature proportions separately from the Plushbound visual reference.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

POSE_GUIDE_VERSION = "creature-pose-guide-v1"


def _canvas(size: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (size, size), "white")
    return image, ImageDraw.Draw(image)


def _quadruped(size: int, *, low: bool, large: bool, horns: bool = False) -> Image.Image:
    image, draw = _canvas(size)
    s = size / 512.0
    if large:
        body = (85, 175, 365, 335)
        head = (335, 180, 455, 290)
        leg_top = 285
        feet_y = 430
        leg_xs = (125, 200, 305, 365)
        leg_w = 45
    elif low:
        body = (95, 225, 350, 325)
        head = (335, 215, 440, 295)
        leg_top = 285
        feet_y = 400
        leg_xs = (125, 195, 300, 360)
        leg_w = 34
    else:
        body = (120, 210, 345, 325)
        head = (330, 185, 435, 290)
        leg_top = 285
        feet_y = 405
        leg_xs = (150, 210, 305, 355)
        leg_w = 32

    def box(values):
        return tuple(int(v * s) for v in values)

    draw.ellipse(box(body), fill="black")
    draw.ellipse(box(head), fill="black")
    for x in leg_xs:
        draw.rounded_rectangle(
            box((x, leg_top, x + leg_w, feet_y)), radius=max(2, int(14 * s)), fill="black"
        )
    draw.polygon(
        [
            (int(105 * s), int(245 * s)),
            (int(55 * s), int(205 * s)),
            (int(85 * s), int(285 * s)),
        ],
        fill="black",
    )
    if horns:
        draw.line(
            [(int(375 * s), int(205 * s)), (int(390 * s), int(120 * s)), (int(355 * s), int(75 * s))],
            fill="black", width=max(3, int(14 * s)),
        )
        draw.line(
            [(int(410 * s), int(210 * s)), (int(435 * s), int(130 * s)), (int(470 * s), int(100 * s))],
            fill="black", width=max(3, int(14 * s)),
        )
    return image


def _hexapod(size: int, *, boss: bool) -> Image.Image:
    image, draw = _canvas(size)
    s = size / 512.0

    def box(values):
        return tuple(int(v * s) for v in values)

    if boss:
        draw.ellipse(box((55, 190, 370, 325)), fill="black")
        draw.ellipse(box((345, 180, 465, 285)), fill="black")
        xs = (90, 145, 215, 270, 330, 375)
        for i, x in enumerate(xs):
            y0 = 270 if i < 3 else 280
            draw.rounded_rectangle(box((x, y0, x + 34, 420)), radius=max(2, int(12*s)), fill="black")
        draw.line(
            [(int(390*s), int(195*s)), (int(410*s), int(110*s)), (int(370*s), int(65*s))],
            fill="black", width=max(3, int(13*s)),
        )
        draw.line(
            [(int(425*s), int(200*s)), (int(455*s), int(120*s)), (int(490*s), int(85*s))],
            fill="black", width=max(3, int(13*s)),
        )
    else:
        draw.ellipse(box((80, 225, 360, 320)), fill="black")
        draw.ellipse(box((345, 215, 445, 290)), fill="black")
        for x in (105, 165, 230, 285, 335, 380):
            draw.rounded_rectangle(box((x, 280, x + 26, 390)), radius=max(2, int(10*s)), fill="black")
        draw.polygon(
            [(int(85*s), int(250*s)), (int(40*s), int(220*s)), (int(70*s), int(280*s))],
            fill="black",
        )
    return image


def build_pose_guide(family: str, size: int = 512) -> Image.Image:
    if size < 128 or size > 1024:
        raise ValueError("pose guide size must be between 128 and 1024")
    if family == "guardian_friendly":
        return _quadruped(size, low=False, large=False)
    if family == "guardian_corrupt":
        return _quadruped(size, low=True, large=False)
    if family == "guardian_boss":
        return _hexapod(size, boss=True)
    if family == "enemy_creature":
        return _hexapod(size, boss=False)
    raise ValueError(f"unsupported creature pose-guide family: {family}")
