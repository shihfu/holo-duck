"""Build the duck's animation frames from the base sprites.

Reads assets/sprites/<name>.png (60x60). For each state it moves parts of the
sprite by whole grid pixels, then writes:
  firmware/src/sprites.h     unique RGB565 frames + one sequence per state
  assets/preview/<state>.gif 4x preview (one blink in the middle)

Run from anywhere: tools/.venv/bin/python tools/animate.py
Coordinates are grid pixels (x0, y0, x1, y1), inclusive.
"""
import math
from collections import Counter
from pathlib import Path

from PIL import Image

from png2c import to_c

ROOT = Path(__file__).resolve().parent.parent
N, BLACK, SHADOW = 60, (0, 0, 0), (38, 50, 76)


def lit(p): return max(p) > 16
def dark(p): return max(p) < 110 or p[2] > p[0] + 35  # outline, pupil, blue eye
def warm(p): return p[0] > 170 and p[2] < 110 and p[0] - p[2] > 90  # beak, feet


def load(name):
    im = Image.open(ROOT / f"assets/sprites/{name}.png").convert("RGB")
    f = [[im.getpixel((x, y)) for x in range(N)] for y in range(N)]
    if SHADOW not in f[58]:  # the crisp extraction drops faint shadows; draw idle's under the feet
        xs = [x for y in (55, 56, 57) for x in range(N) if warm(f[y][x])]
        f = ground(f, (min(xs) + max(xs)) // 2, 8)
    return f


def ground(f, cx, w):
    """Shadow behind the feet, shaped like idle's: row 58 is cx +- w, row 57 is 3 px wider each side."""
    f = [r[:] for r in f]
    for y, hw in ((57, w + 3), (58, w)):
        for x in range(N):
            if f[y][x] == SHADOW: f[y][x] = BLACK
        for x in range(cx - hw, cx + hw + 1):
            if not lit(f[y][x]): f[y][x] = SHADOW
    return f


def background(f):
    """Black pixels reachable from the border; other black pixels are pupils or gaps."""
    bg, todo = set(), [(x, y) for i in range(N) for x, y in ((i, 0), (i, N - 1), (0, i), (N - 1, i))]
    while todo:
        x, y = todo.pop()
        if 0 <= x < N and 0 <= y < N and (x, y) not in bg and not lit(f[y][x]):
            bg.add((x, y))
            todo += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return bg


def pick(f, rect, ground=None):
    """Solid pixels in rect, minus dark pixels at y >= ground (shadow)."""
    bg, (x0, y0, x1, y1) = background(f), rect
    return {(x, y): f[y][x] for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)
            if (x, y) not in bg and not (ground is not None and y >= ground and dark(f[y][x]))}


def body(f, ground=57):
    """The duck: the largest 8-connected solid shape, without the shadow. Effects
    (marks, sparkles, motion lines) don't touch it, so hops leave them in place."""
    todo, parts = pick(f, (0, 0, N - 1, N - 1), ground), []
    while todo:
        stack = [next(iter(todo))]
        part = {stack[0]: todo.pop(stack[0])}
        while stack:
            x, y = stack.pop()
            for q in ((x + a, y + b) for a in (-1, 0, 1) for b in (-1, 0, 1)):
                if q in todo:
                    part[q] = todo.pop(q)
                    stack.append(q)
        parts.append(part)
    return max(parts, key=len)


def stretch(f, k, at):
    """Duck k rows taller (k < 0: shorter). Body rows above `at` move; row `at` fills the gap."""
    if not k: return f
    b = body(f)
    g = move(f, {p: c for p, c in b.items() if p[1] < at}, 0, -k, fill=False)
    for (x, y), c in b.items():
        if y == at:
            for j in range(1, k + 1): g[at - j][x] = c
    return g


def hop(f, h, k=0, at=51):
    """Jump h px, squashed or stretched by k at row `at`; the shadow narrows by h // 2 each side."""
    row = [x for x in range(N) if f[58][x] == SHADOW]
    g = stretch(f, k, at)
    g = move(g, body(g), 0, -h, fill=False) if h else g
    return ground(g, (row[0] + row[-1]) // 2, (row[-1] - row[0]) // 2 - h // 2)


def move(f, part, dx=0, dy=0, fill=True):
    """Erase part, paint it at the offset. fill: a vacated pixel between two lit
    pixels takes a neighbour's colour, so necks and legs don't crack open."""
    g = [r[:] for r in f]
    for x, y in part: g[y][x] = BLACK
    for (x, y), c in part.items():
        if 0 <= x + dx < N and 0 <= y + dy < N: g[y + dy][x + dx] = c
    if fill:
        for x, y in set(part) - {(x + dx, y + dy) for x, y in part}:
            for (ax, ay), (bx, by) in (((x, y - 1), (x, y + 1)), ((x - 1, y), (x + 1, y))):
                if 0 <= min(ax, bx, ay, by) and max(ax, bx, ay, by) < N and lit(g[ay][ax]) and lit(g[by][bx]):
                    g[y][x] = g[ay][ax]
                    break
    return g


def shift(f, rect, dx=0, dy=0, fill=True, fx=False):
    """Move the duck's pixels in rect, or with fx the effect pixels (dots, lines, marks), so a
    rect that overlaps both never drags the other along."""
    if not (dx or dy): return f
    b = body(f)
    return move(f, {p: c for p, c in pick(f, rect).items() if (p in b) != fx}, dx, dy, fill)


def hide(f, rect): return shift(f, rect, N, N, fill=False, fx=True)


def feet(f, rect, dy): return move(f, {p: c for p, c in pick(f, rect).items() if warm(c)}, 0, dy, fill=False) if dy else f


def _eye(f, rect):
    x0, y0, x1, y1 = rect
    pts = {(x, y): f[y][x] for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)
           if min(f[y][x]) < 200 and not warm(f[y][x])}  # pupil and its grey edge, not the beak
    ring = [f[y][x] for y in range(y0 - 2, y1 + 3) for x in range(x0 - 2, x1 + 3) if min(f[y][x]) >= 200]
    return pts, Counter(ring).most_common(1)[0][0]


def look(f, eyes, dx, dy):
    for r in eyes:
        pts, skin = _eye(f, r)
        f = [row[:] for row in f]
        for x, y in pts: f[y][x] = skin
        for (x, y), c in pts.items(): f[y + dy][x + dx] = c
    return f


def close(f, eyes):
    """Closed eye: paint the eye over with skin, draw a lid line across the pupil, 1 px below centre."""
    f = [row[:] for row in f]
    for r in eyes:
        pts, skin = _eye(f, r)
        core = {p: c for p, c in pts.items() if dark(c)}
        xs, ys = [x for x, _ in core], [y for _, y in core]
        lid = min(core.values(), key=sum)
        for x, y in pts: f[y][x] = skin
        for x in range(min(xs), max(xs) + 1): f[(min(ys) + max(ys) + 1) // 2][x] = lid
    return f


def eye(f, rects, shut, d=(0, 0)):
    """Closed eyes, or pupils looking by d. Runs before moves so eyes travel with the head."""
    return close(f, rects) if shut else look(f, rects, *d) if d != (0, 0) else f


# --- states, in DuckState order ------------------------------------------------
# pose(img, shut) -> frames; shut=True builds the blink copies (same length).

def idle(f, shut):
    def P(k=0, tail=0, sway=0, lift=None, d=(0, 0), tilt=0):
        g = eye(f, [(28, 33, 30, 38), (38, 33, 40, 36)], shut, d)
        g = shift(g, (15, 46, 18, 51), dy=-tail)
        g = shift(g, (14, 20, 45, 32), dx=tilt)  # top of the head only: reads as a tilt
        g = stretch(g, k, 48)  # breathing
        g = shift(g, (0, 0, 59, 54), dx=sway)
        g = feet(g, (22, 55, 29, 57), -(lift == "l"))
        return feet(g, (31, 55, 38, 57), -(lift == "r"))
    breathe = [P()] * 3 + [P(k=1)] * 4 + [P()] * 3
    waddle = ([P(sway=-1, lift="r")] * 2 + [P()] + [P(sway=1, lift="l")] * 2 + [P()]) * 2
    return (breathe + [P(tail=1), P(), P(tail=1), P()] + breathe
            + [P(d=(-1, 0))] * 6 + [P()] * 2 + [P(d=(1, 0))] * 6 + breathe
            + [P(tilt=1)] * 3 + [P(tilt=1, k=1)] * 4 + [P(tilt=1)] * 3 + waddle + breathe)


def thinking(f, shut):
    dots = [(43, 19, 45, 23), (47, 19, 49, 23), (51, 19, 53, 23)]
    out = []
    for i in range(16):
        up = i < 8  # dots appear while the duck looks up, head tilted
        g = eye(f, [(25, 34, 28, 38), (35, 31, 37, 33)], shut, (0, -1) if up else (0, 0))
        g = shift(g, (14, 20, 41, 29), dx=int(up))
        g = shift(g, (31, 41, 41, 49), dy=-(i in (9, 11, 13)))  # wing taps chin
        for d in dots[i // 2 if up else 3:]: g = hide(g, d)
        out.append(g)
    return out


def working(f, shut):
    lines = (46, 25, 54, 39)
    f = eye(f, [(30, 36, 32, 40), (40, 35, 42, 39)], shut)
    out = []
    for i in range(8):
        g = shift(f, (30, 42, 37, 50), dy=-(i % 2))  # wing types
        g = shift(g, (21, 24, 45, 41), dy=int(i % 4 >= 2), fill=False)  # head bob
        o = [0, 0, 1, 1, 0, 0, None, None][i]
        g = hide(g, lines) if o is None else shift(g, lines, dx=o, fill=False, fx=True)
        out.append(g)
    return out


def permission(f, shut):
    marks = [(10, 26, 18, 35), (43, 24, 50, 33)]
    f = eye(f, [(27, 33, 30, 37), (36, 32, 39, 35)], shut)
    out = []
    H, K = [0, 1, 2, 2, 1, 0, 0, 0], [-1, 1, 0, 0, 1, -1, 0, 0]  # crouch, stretch up, land squashed
    for i in range(16):
        up = -(i % 4 < 2)
        g = shift(f, (14, 40, 21, 50), dy=up)
        g = shift(g, (38, 40, 44, 48), dy=up)
        o = (i // 2) % 2
        g = shift(g, marks[0], dx=-o, dy=-o, fill=False, fx=True)
        g = shift(g, marks[1], dx=o, dy=-o, fill=False, fx=True)
        out.append(hop(g, H[i % 8], K[i % 8], 52))
    return out


def success(f, shut):
    sparks = [(10, 31, 15, 37), (13, 21, 20, 29), (40, 18, 48, 26), (45, 30, 51, 36)]
    H, K = [0, 0, 2, 4, 5, 5, 4, 2, 0, 0], [0, -1, 1, 1, 0, 0, 0, 1, -1, 0]
    out = []
    for i in range(20):
        up = -(i % 4 < 2)
        g = shift(f, (12, 37, 21, 46), dy=up)
        g = shift(g, (40, 36, 47, 43), dy=up)
        for j, (x0, y0, x1, y1) in enumerate(sparks):  # twinkle: shrink to the core
            if (i + 2 * j) % 6 < 2:
                cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
                g = hide(g, (x0, y0, x1, cy - 2)); g = hide(g, (x0, cy + 2, x1, y1))
                g = hide(g, (x0, y0, cx - 2, y1)); g = hide(g, (cx + 2, y0, x1, y1))
        out.append(hop(g, H[i % 10], K[i % 10]))
    return out


def error(f, shut):
    eyes = [(26, 35, 29, 39), (36, 36, 38, 39)]
    out = []
    shake = [1, -1, 1, -1, 1, -1]  # feet stay planted
    for i in range(50):
        g = close(f, eyes) if i < 8 or i in (24, 25, 26, 40, 41, 42) else f  # wince, then slow blinks
        g = shift(g, (40, 12, 50, 25), dx=[0, 1, 0, -1][i // 3 % 4], fill=False, fx=True)  # swirl
        g = shift(g, (0, 0, 59, 54), dx=shake[i] if i < 6 else 0)
        out.append(shift(g, (19, 24, 41, 43), dy=int(i >= 10)))  # head droops
    return out


def sleeping(f, shut):
    big, small = ["#####", "...#.", "..#..", ".#...", "#####"], ["####", "..#.", ".#..", "####"]
    blue = max(pick(f, (45, 23, 51, 29)).values(), key=sum)
    f = hide(hide(f, (45, 23, 51, 29)), (39, 28, 46, 35))  # the mock's Z's blur at this size; redraw them
    breath = [0] * 2 + [1] * 7 + [0] * 3 + [-1] * 5 + [0] * 3  # slow: in, hold, out
    out = []
    for i in range(20):
        g = [r[:] for r in stretch(f, breath[i], 55)]
        for glyph, x, y, p in ((big, 46, 23, i), (small, 39, 31, (i + 10) % 20)):  # rise, drift, fade in and out
            c = tuple(round(v * min(1, (p + 1) / 3, (20 - p) / 6)) for v in blue)
            for dy, row in enumerate(glyph):
                for dx, ch in enumerate(row):
                    if ch == "#": g[y - p // 4 + dy][x + p // 8 + dx] = c
        out.append(g)
    return out


def excited(f, shut):
    lines = [(8, 32, 17, 43), (44, 25, 53, 35)]
    f = eye(f, [(29, 33, 32, 37), (37, 30, 39, 33)], shut)
    out = []
    for i, (h, k) in enumerate(((0, -1), (3, 1), (5, 0), (6, 0), (5, 0), (3, 1), (0, -1), (0, 0))):
        up = -(i % 2)
        g = shift(f, (16, 39, 25, 44), dy=up)
        g = shift(g, (39, 37, 47, 43), dy=up)
        o = (i // 2) % 2
        g = shift(g, lines[0], dx=-o, fill=False, fx=True)
        g = shift(g, lines[1], dx=o, fill=False, fx=True)
        out.append(hop(g, h, k))
    return out


def connecting(f, shut):
    spin = (19, 0, 40, 20)
    blues = [c for c in pick(f, spin).values() if c[2] > c[0] + 35]
    hi, lo = max(blues, key=sum), (24, 32, 64)
    f = eye(hide(f, spin), [(25, 34, 27, 38), (36, 33, 38, 36)], shut, (0, -1))  # eyes on the spinner
    out = []
    walk = [(0, None, 0), (1, "l", 0), (1, "l", 1), (1, "l", 0), (0, None, 0), (-1, "r", 0), (-1, "r", 1), (-1, "r", 0)]
    for i in range(16):  # waddle in place: lift a foot, lean onto the other, bob at mid-step
        sway, lift, bob = walk[i % 8]
        g = shift(f, (0, 0, 59, 54), dx=sway, dy=-bob)
        g = feet(g, (22, 55, 28, 57), -(lift == "l"))
        g = feet(g, (32, 55, 37, 57), -(lift == "r"))
        g = [r[:] for r in g]
        for j in range(8):  # 8 dots clockwise from 12 o'clock; dot i % 8 is brightest
            t = ((i - j) % 8) / 7
            c = tuple(round(h + (l - h) * t) for h, l in zip(hi, lo))
            a = math.radians(45 * j - 90)
            cx, cy = round(29.5 + 6.5 * math.cos(a)), round(10 + 6.5 * math.sin(a))
            for dx in range(-1, 2):
                for dy in range(-1, 2): g[cy + dy][cx + dx] = c
        out.append(g)
    return out


STATES = [  # (state, sprite, ms per frame, random blink, pose)
    ("idle", "idle", 125, True, idle),
    ("thinking", "thinking", 150, True, thinking),
    ("working", "working", 100, True, working),
    ("permission", "permission", 100, True, permission),
    ("success", "success", 100, False, success),
    ("error", "error", 100, False, error),  # slow blink is in the sequence
    ("sleeping", "sleeping", 250, False, sleeping),
    ("excited", "excited", 80, True, excited),
    ("connecting", "loading", 125, True, connecting),
]


def main():
    frames, index = [], {}

    def add(g):
        k = bytes(v for row in g for p in row for v in p)
        if k not in index:
            index[k] = len(frames)
            frames.append(g)
        return index[k]

    def img(g, scale=1):
        im = Image.new("RGB", (N, N))
        im.putdata([p for row in g for p in row])
        return im.resize((N * scale, N * scale), Image.Resampling.NEAREST)

    (ROOT / "assets/preview").mkdir(exist_ok=True)
    seqs = []
    for state, sprite, ms, blinks, pose in STATES:
        opened = pose(load(sprite), False)
        closed = blinks and pose(load(sprite), True)
        seqs.append((state, ms, [add(g) for g in opened], closed and [add(g) for g in closed]))
        gif = opened[:]
        if closed: gif[len(gif) // 2] = closed[len(gif) // 2]
        ims = [img(g, 4) for g in gif]
        ims[0].save(ROOT / f"assets/preview/{state}.gif", save_all=True, append_images=ims[1:], duration=ms, loop=0)

    out = ["// Generated by tools/animate.py from assets/sprites/*.png. Do not edit.",
           "#pragma once", "#include <stdint.h>", "",
           "struct Seq { uint16_t ms, n; const uint16_t *open, *closed; };  // closed: blink copies or nullptr", ""]
    out += [to_c(f"frame_{i}", img(g)) for i, g in enumerate(frames)]
    out.append("const uint16_t *const FRAMES[] = {" + ", ".join(f"frame_{i}" for i in range(len(frames))) + "};")
    for state, ms, o, c in seqs:
        out.append(f"const uint16_t seq_{state}[] = {{{', '.join(map(str, o))}}};")
        if c: out.append(f"const uint16_t blink_{state}[] = {{{', '.join(map(str, c))}}};")
    out.append("const Seq SEQS[] = {")
    out += [f"    {{{ms}, {len(o)}, seq_{s}, {'blink_' + s if c else 'nullptr'}}}," for s, ms, o, c in seqs]
    out.append("};")
    (ROOT / "firmware/src/sprites.h").write_text("\n".join(out) + "\n")
    print(f"{len(frames)} frames, {len(frames) * N * N * 2 // 1024} KB")


if __name__ == "__main__":
    main()
