"""Draw the website icons of the tuner (a rev-counter gauge) and write them as PNG and ICO files.

usage: python tools/make_icons.py [<out dir>]
  e.g. python tools/make_icons.py            (writes into tuner/web)

Writes apple-touch-icon.png (180x180), icon-192.png, icon-512.png, favicon.png (32x32) and favicon.ico (the 32x32 PNG in an ICO container) into <out dir> (default tuner/web, created when missing). Existing files are overwritten.
The files are 8-bit RGB PNGs without alpha (full-bleed squares: iOS rounds the corners itself), the same drawing at every size, 4x4 supersampling for the edges, a ring stroke that gets thicker below 128 px. Colours: background, accent, text and muted text are read from the :root rule of tuner/web/index.html, the red of the last quarter of the ring is fixed in this file. The output is deterministic: the same bytes on every run (on one zlib build; another zlib may compress the same pixels to other bytes).

Exit code 0 on success, 1 on a runtime error (error: ... on stderr), 2 on bad usage (usage block on stdout).

Stdlib only.
"""
import math
import pathlib
import re
import struct
import sys
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import kspkg  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]
WEB = REPO / "tuner" / "web"
PAGE = WEB / "index.html"
SIZES = (("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512), ("favicon.png", 32))
ICO = "favicon.ico"
TOKENS = {"bg": "--color-bg", "accent": "--color-accent", "text": "--color-text", "muted": "--color-text-muted"}
RED = (0xE5, 0x48, 0x4D)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SUPER = 4
ARC_START, ARC_END, RED_START = -135.0, 135.0, 67.5
TICKS = 7


def read_palette():
    style = PAGE.read_text(encoding="utf-8")
    palette = {}
    for key, token in TOKENS.items():
        m = re.search(r"%s:\s*#([0-9a-fA-F]{6})\s*;" % re.escape(token), style)
        if not m:
            raise ValueError("%s: no colour %s" % (kspkg.plain_path(PAGE), token))
        palette[key] = tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
    return palette


def direction(degrees):
    """Unit vector of an angle measured clockwise from 12 o'clock on a screen with y pointing down."""
    a = math.radians(degrees)
    return math.sin(a), -math.cos(a)


def scene(size, palette):
    """The drawing as a function colour_at(x, y) of a point in unit coordinates (the centre is 0, 0, the canvas -0.5 .. 0.5)."""
    bold = 1.0 + 0.75 * max(0, 128 - size) / 96
    r_out = 0.38
    width = 0.075 * bold
    r_in = r_out - width
    cap = r_out - width / 2
    cap_x, cap_y = math.sqrt(0.5) * cap, math.sqrt(0.5) * cap
    tick_out = r_in - 0.025
    tick_in = tick_out - 0.05
    tick_half = 0.012 * bold
    ticks = []
    for k in range(TICKS):
        degrees = ARC_START + k * (ARC_END - ARC_START) / (TICKS - 1)
        sx, sy = direction(degrees)
        ticks.append((sx, sy, palette["muted"] if degrees < RED_START else RED))
    needle_x, needle_y = direction(30.0)
    needle_len, needle_tail, needle_base, needle_tip = tick_in - 0.02, 0.07 * bold, 0.022 * bold, 0.007 * bold
    hub = 0.058 * bold
    red_x, red_y = direction(RED_START)
    accent, text, bg = palette["accent"], palette["text"], palette["bg"]
    out2, in2, cap2, hub2 = r_out * r_out, r_in * r_in, (width / 2) ** 2, hub * hub

    def colour_at(x, y):
        r2 = x * x + y * y
        if r2 > out2:
            return bg
        if r2 <= hub2:
            return text
        along = x * needle_x + y * needle_y
        across = x * -needle_y + y * needle_x
        if -needle_tail <= along <= needle_len and abs(across) <= needle_base + (needle_tip - needle_base) * max(along, 0.0) / needle_len:
            return text
        if r2 >= in2:
            if y > 0 and abs(x) < y:
                if (x + cap_x) ** 2 + (y - cap_y) ** 2 <= cap2:
                    return accent
                if (x - cap_x) ** 2 + (y - cap_y) ** 2 <= cap2:
                    return RED
                return bg
            return RED if x > 0 and red_x * y - red_y * x > 0 else accent
        r = math.sqrt(r2)
        if tick_in - tick_half <= r <= tick_out + tick_half:
            for sx, sy, colour in ticks:
                along = x * sx + y * sy
                if tick_in <= along <= tick_out and abs(x * -sy + y * sx) <= tick_half:
                    return colour
        return bg

    return colour_at


def render(size, palette):
    """size x size RGB pixels as rows of bytes: the pixel is flat when its four corners and its centre agree, else the mean of SUPER x SUPER samples."""
    colour_at = scene(size, palette)
    count = SUPER * SUPER
    rows = []
    for j in range(size):
        row = bytearray()
        for i in range(size):
            probes = {colour_at((i + a) / size - 0.5, (j + b) / size - 0.5) for a, b in ((0, 0), (1, 0), (0, 1), (1, 1), (0.5, 0.5))}
            if len(probes) == 1:
                row += bytes(probes.pop())
                continue
            sums = [0, 0, 0]
            for b in range(SUPER):
                for a in range(SUPER):
                    c = colour_at((i + (a + 0.5) / SUPER) / size - 0.5, (j + (b + 0.5) / SUPER) / size - 0.5)
                    sums[0] += c[0]
                    sums[1] += c[1]
                    sums[2] += c[2]
            row += bytes((s + count // 2) // count for s in sums)
        rows.append(bytes(row))
    return rows


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def png_bytes(rows):
    height, width = len(rows), len(rows[0]) // 3
    raw = b"".join(b"\x00" + row for row in rows)
    return (PNG_SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def ico_bytes(png, size):
    return struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(png), 22) + png


def make_files(palette):
    files = {}
    for name, size in SIZES:
        files[name] = png_bytes(render(size, palette))
    files[ICO] = ico_bytes(files["favicon.png"], 32)
    return files


def usage():
    print(__doc__.split("\n\n")[1])
    sys.exit(2)


def main():
    try:
        pos, _ = kspkg.parse_args(sys.argv[1:], ())
    except ValueError:
        usage()
    if len(pos) > 1:
        usage()
    out = pathlib.Path(kspkg.long_path(pos[0] if pos else WEB))
    try:
        files = make_files(read_palette())
        out.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (out / name).write_bytes(data)
    except (ValueError, OSError) as e:
        sys.exit("error: %s" % e)
    for name, data in files.items():
        print("%s: %d bytes" % (kspkg.plain_path(out / name), len(data)))


if __name__ == "__main__":
    main()
