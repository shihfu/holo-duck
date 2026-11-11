"""PNG -> RGB565 C array for TFT_eSPI pushImage (call tft.setSwapBytes(true)).

Usage: png2c.py NAME IMAGE [--crop X Y W H] [--size W H] >> out.h
Transparent pixels become black, which the prism shows as empty space.
"""
import argparse

from PIL import Image


def to_c(name, img):
    """RGB image -> `const uint16_t name[]` source, one row per line."""
    w, d = img.width, img.tobytes()
    px = [((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3) for r, g, b in zip(d[0::3], d[1::3], d[2::3])]
    rows = (", ".join(f"0x{v:04X}" for v in px[i:i + w]) for i in range(0, len(px), w))
    return f"const uint16_t {name}[] = {{\n" + ",\n".join(rows) + "\n};"


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("name")
    p.add_argument("image")
    p.add_argument("--crop", type=int, nargs=4, metavar=("X", "Y", "W", "H"))
    p.add_argument("--size", type=int, nargs=2, metavar=("W", "H"))
    a = p.parse_args()

    img = Image.open(a.image).convert("RGBA")
    if a.crop:
        x, y, w, h = a.crop
        img = img.crop((x, y, x + w, y + h))
    if a.size:
        img = img.resize(a.size, Image.Resampling.LANCZOS)
    img = Image.alpha_composite(Image.new("RGBA", img.size, (0, 0, 0, 255)), img).convert("RGB")
    print(f"// {a.name}: {img.width}x{img.height} RGB565 from {a.image}")
    print(f"constexpr int {a.name}_w = {img.width}, {a.name}_h = {img.height};")
    print(to_c(a.name, img))
