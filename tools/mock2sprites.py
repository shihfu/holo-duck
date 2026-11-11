"""Placeholder 60x60 sprites from juno-design-mock.png -> assets/sprites/<state>.png.

The mock draws the duck at different sizes, so each tile is cropped and
scaled so the duck is DUCK_H px tall, feet centred at x=30, standing on GROUND.
Table values are mock pixels relative to each panel: feet centre x, feet bottom y,
duck height (head top to feet bottom). Replace the PNGs with real art later.

Each sprite pixel is the mean of the duck pixels in its box, snapped to a 16-colour
palette of the mock; a box less than half covered by the duck stays black. Plain box
averaging blends the soft mock edges into the background and looks blurry on the cube.
"""
from pathlib import Path

from PIL import Image, ImageChops

DUCK_H, GROUND, SIZE = 33, 58, 60
ROOT = Path(__file__).resolve().parent.parent
TILES = {  # state: (col, row, feet_x, feet_bottom, duck_h)
    "idle": (0, 0, 167, 279, 189),
    "thinking": (1, 0, 150, 279, 179),
    "working": (2, 0, 145, 288, 172),  # one foot hidden by the laptop
    "permission": (0, 1, 165, 278, 206),
    "success": (1, 1, 162, 274, 187),
    "error": (2, 1, 167, 278, 184),
    "sleeping": (0, 2, 149, 269, 189),  # lying down: body centre/bottom, idle's scale
    "excited": (1, 2, 159, 233, 189),
    "loading": (2, 2, 172, 292, 156),
}


def blacken(img, t):
    """Pixels whose brightest channel is <= t become pure black (navy bg shows as a square in the prism)."""
    peak = ImageChops.lighter(ImageChops.lighter(*img.split()[:2]), img.split()[2])
    return Image.composite(img, Image.new("RGB", img.size), peak.point(lambda v: 255 if v > t else 0))


src = blacken(Image.open(ROOT / "juno-design-mock.png").convert("RGB"), 32)
mock = Image.new("RGB", src.size)  # keep only the 9 panels, not the labels between them
for x0, x1 in ((72, 407), (459, 794), (846, 1181)):
    for y0, y1 in ((72, 392), (455, 770), (832, 1145)):
        mock.paste(src.crop((x0, y0, x1, y1)), (x0, y0))
q = mock.quantize(16, Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).getpalette()[:48]
PAL = [tuple(q[i:i + 3]) for i in range(0, 48, 3)]
px = mock.load()


def cell(x0, y0, x1, y1):
    box = [px[x, y] for x in range(round(x0), round(x1)) for y in range(round(y0), round(y1))]
    fg = [c for c in box if max(c)]
    if len(fg) * 2 < len(box):
        return (0, 0, 0)
    m = [sum(c[i] for c in fg) / len(fg) for i in range(3)]
    return min(PAL, key=lambda p: 2 * (p[0] - m[0]) ** 2 + 4 * (p[1] - m[1]) ** 2 + 3 * (p[2] - m[2]) ** 2)


out = ROOT / "assets" / "sprites"
out.mkdir(parents=True, exist_ok=True)
for name, (col, row, fx, fb, h) in TILES.items():
    k = h / DUCK_H
    left = (72, 459, 846)[col] + fx - SIZE / 2 * k
    top = (72, 455, 832)[row] + fb + 1 - GROUND * k
    img = Image.new("RGB", (SIZE, SIZE))
    img.putdata([cell(left + x * k, top + y * k, left + (x + 1) * k, top + (y + 1) * k) for y in range(SIZE) for x in range(SIZE)])
    img.save(out / f"{name}.png")
