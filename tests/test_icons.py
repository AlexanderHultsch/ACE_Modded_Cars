"""Tests for tools/make_icons.py and the icon files in tuner/web: PNG and ICO structure, determinism, the colours of the page, the committed files, the manifest, usage and exit codes.

The generator runs as a subprocess into temp folders (two runs); the committed files are compared by their decoded pixels, not by their compressed bytes, because another zlib build may compress the same pixels to other bytes.
"""
import contextlib
import io
import json
import re
import struct
import sys
import unittest
import zlib
from unittest import mock

from support import ROOT, run_tool, tmp

import make_icons

WEB = ROOT / "tuner" / "web"
USAGE = make_icons.__doc__.split("\n\n")[1]
PNGS = {"apple-touch-icon.png": 180, "icon-192.png": 192, "icon-512.png": 512, "favicon.png": 32}
FILES = sorted(list(PNGS) + ["favicon.ico"])
STYLE = (WEB / "index.html").read_text(encoding="utf-8")


def css_colour(token):
    return tuple(bytes.fromhex(re.search(r"%s: #([0-9a-f]{6});" % re.escape(token), STYLE).group(1)))


BG, ACCENT, TEXT = css_colour("--color-bg"), css_colour("--color-accent"), css_colour("--color-text")


def parse_png(data):
    """(width, height, pixel rows without the filter bytes); asserts the structure: signature, IHDR first, IDAT, IEND last, valid CRCs."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "signature"
    chunks, pos = [], 8
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body, crc = data[pos + 8:pos + 8 + length], struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])[0]
        assert crc == zlib.crc32(kind + body) & 0xFFFFFFFF, "crc of " + kind.decode()
        chunks.append((kind, body))
        pos += 12 + length
    assert pos == len(data), "trailing bytes"
    assert [k for k, _ in chunks] == [b"IHDR", b"IDAT", b"IEND"], [k for k, _ in chunks]
    width, height, depth, colour, compression, filtering, interlace = struct.unpack(">IIBBBBB", chunks[0][1])
    assert (depth, colour, compression, filtering, interlace) == (8, 2, 0, 0, 0)
    assert chunks[2][1] == b""
    raw = zlib.decompress(chunks[1][1])
    assert len(raw) == height * (1 + 3 * width), (len(raw), width, height)
    rows = []
    for j in range(height):
        row = raw[j * (1 + 3 * width):(j + 1) * (1 + 3 * width)]
        assert row[0] == 0, "filter type"
        rows.append(row[1:])
    return width, height, rows


def pixel(rows, x, y):
    return tuple(rows[y][3 * x:3 * x + 3])


class Generated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tmp()
        base = cls._tmp.__enter__()
        cls.a, cls.b = base / "a", base / "b"
        cls.runs = [run_tool("make_icons.py", d) for d in (cls.a, cls.b)]
        cls.files = {name: (cls.a / name).read_bytes() for name in FILES}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.__exit__(None, None, None)


class TestGenerator(Generated):
    def test_the_runs_succeed_and_print_one_line_per_file(self):
        for r, d in zip(self.runs, (self.a, self.b)):
            self.assertEqual((r.returncode, r.stderr), (0, ""))
            expected = ["%s: %d bytes" % (d / n, len((d / n).read_bytes())) for n in ("apple-touch-icon.png", "icon-192.png", "icon-512.png", "favicon.png", "favicon.ico")]
            self.assertEqual(r.stdout.splitlines(), expected)

    def test_it_writes_exactly_the_five_files(self):
        self.assertEqual(sorted(p.name for p in self.a.iterdir()), FILES)

    def test_two_runs_give_identical_bytes(self):
        for name in FILES:
            with self.subTest(name):
                self.assertEqual((self.a / name).read_bytes(), (self.b / name).read_bytes())

    def test_every_png_parses_with_the_documented_size(self):
        for name, size in PNGS.items():
            with self.subTest(name):
                width, height, rows = parse_png(self.files[name])
                self.assertEqual((width, height, len(rows[0])), (size, size, 3 * size))

    def test_the_png_is_rgb_without_alpha(self):
        for name in PNGS:
            with self.subTest(name):
                ihdr = self.files[name][16:29]
                self.assertEqual((ihdr[8], ihdr[9]), (8, 2))

    def test_the_ico_is_a_single_image_container_around_the_32_pixel_png(self):
        ico, png = self.files["favicon.ico"], self.files["favicon.png"]
        self.assertEqual(struct.unpack("<HHH", ico[:6]), (0, 1, 1))
        width, height, colours, reserved, planes, bits, size, offset = struct.unpack("<BBBBHHII", ico[6:22])
        self.assertEqual((width, height, colours, reserved, planes, bits), (32, 32, 0, 0, 1, 32))
        self.assertEqual((offset, size, len(ico)), (22, len(png), 22 + len(png)))
        self.assertEqual(ico[offset:], png)

    def test_the_corners_are_the_page_background_and_the_margin_is_empty(self):
        for name, size in PNGS.items():
            with self.subTest(name):
                _, _, rows = parse_png(self.files[name])
                margin = int(size * 0.11)
                for y in range(size):
                    for x in range(size):
                        if min(x, y, size - 1 - x, size - 1 - y) < margin:
                            self.assertEqual(pixel(rows, x, y), BG, (x, y))

    def test_the_drawing_uses_the_accent_the_white_text_colour_and_the_red_zone(self):
        for name in PNGS:
            with self.subTest(name):
                _, _, rows = parse_png(self.files[name])
                colours = {pixel(rows, x, y) for y in range(len(rows)) for x in range(len(rows))}
                self.assertTrue({BG, ACCENT, TEXT, make_icons.RED} <= colours)

    def test_the_hub_sits_in_the_centre(self):
        for name, size in PNGS.items():
            with self.subTest(name):
                _, _, rows = parse_png(self.files[name])
                self.assertEqual(pixel(rows, size // 2, size // 2), TEXT)

    def test_the_needle_points_to_the_upper_right_and_the_gap_is_at_the_bottom(self):
        _, _, rows = parse_png(self.files["icon-512.png"])
        self.assertEqual(pixel(rows, 256 + 45, 256 - 78), TEXT)
        self.assertEqual(pixel(rows, 256 - 45, 256 - 78), BG)
        self.assertEqual(pixel(rows, 256, 256 + 195 - 20), BG)
        self.assertEqual(pixel(rows, 256, 256 - 195 + 20), ACCENT)
        self.assertEqual(pixel(rows, 256 + 195 - 20, 256), make_icons.RED)
        self.assertEqual(pixel(rows, 256 - 195 + 20, 256), ACCENT)

    def test_the_edges_are_anti_aliased(self):
        _, _, rows = parse_png(self.files["icon-512.png"])
        colours = {pixel(rows, x, y) for y in range(512) for x in range(512)}
        self.assertGreater(len(colours), 30)

    def test_the_render_is_deterministic_in_process(self):
        palette = make_icons.read_palette()
        self.assertEqual(make_icons.render(32, palette), make_icons.render(32, palette))


class TestCommittedFiles(Generated):
    def test_the_five_files_exist_in_the_web_folder(self):
        for name in FILES:
            self.assertTrue((WEB / name).is_file(), name)

    def test_the_committed_pngs_have_the_pixels_the_generator_produces(self):
        for name in PNGS:
            with self.subTest(name):
                self.assertEqual(parse_png((WEB / name).read_bytes()), parse_png(self.files[name]))

    def test_the_committed_ico_is_the_generated_container_around_the_committed_png(self):
        ico = (WEB / "favicon.ico").read_bytes()
        self.assertEqual(ico[:22], self.files["favicon.ico"][:22])
        self.assertEqual(ico[22:], (WEB / "favicon.png").read_bytes())

    def test_the_palette_comes_from_the_page(self):
        palette = make_icons.read_palette()
        self.assertEqual(palette["bg"], BG)
        self.assertEqual(palette["accent"], ACCENT)
        self.assertEqual(palette["text"], TEXT)
        self.assertEqual(palette["muted"], css_colour("--color-text-muted"))


class TestManifest(unittest.TestCase):
    MANIFEST = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))

    def test_the_fields_of_the_app(self):
        m = self.MANIFEST
        self.assertEqual((m["name"], m["short_name"]), ("ACE - Simple Car Tuner", "ACE Tuner"))
        self.assertEqual((m["start_url"], m["scope"], m["display"]), ("/ACESCT/", "/ACESCT/", "standalone"))
        self.assertEqual(set(m), {"name", "short_name", "start_url", "scope", "display", "background_color", "theme_color", "icons"})

    def test_the_colours_are_the_dark_background_of_the_page(self):
        bg = "#%02x%02x%02x" % BG
        self.assertEqual((self.MANIFEST["background_color"], self.MANIFEST["theme_color"]), (bg, bg))

    def test_the_icons_are_relative_files_of_the_right_size(self):
        icons = self.MANIFEST["icons"]
        self.assertEqual([i["src"] for i in icons], ["icon-192.png", "icon-512.png"])
        for icon in icons:
            with self.subTest(icon["src"]):
                self.assertEqual((icon["type"], icon["purpose"]), ("image/png", "any"))
                width, height, _ = parse_png((WEB / icon["src"]).read_bytes())
                self.assertEqual(icon["sizes"], "%dx%d" % (width, height))

    def test_the_manifest_is_ascii(self):
        (WEB / "manifest.webmanifest").read_bytes().decode("ascii")


class TestCli(unittest.TestCase):
    def test_a_second_positional_argument_is_usage_with_exit_2(self):
        with tmp() as d:
            for argv in (("a", "b"), (str(d / "x"), str(d / "y"), "z")):
                with self.subTest(argv):
                    r = run_tool("make_icons.py", *argv, cwd=d)
                    self.assertEqual((r.returncode, r.stdout.strip(), r.stderr), (2, USAGE.strip(), ""))
            self.assertEqual(list(d.iterdir()), [])

    def test_an_option_is_usage_with_exit_2(self):
        for argv in (("--help",), ("--out", "x")):
            with self.subTest(argv):
                r = run_tool("make_icons.py", *argv)
                self.assertEqual((r.returncode, r.stdout.strip(), r.stderr), (2, USAGE.strip(), ""))

    def test_the_usage_block_is_the_first_paragraph_after_the_title(self):
        self.assertEqual(len(make_icons.__doc__.split("\n\n")[0].splitlines()), 1)
        self.assertTrue(USAGE.startswith("usage: python tools/make_icons.py [<out dir>]"), USAGE)

    def test_an_out_dir_that_is_a_file_is_an_error_line_on_stderr_with_exit_1(self):
        with tmp() as d:
            (d / "file").write_bytes(b"x")
            r = run_tool("make_icons.py", d / "file")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertRegex(r.stderr, r"^error: .+\n$")

    def test_without_an_argument_the_files_go_to_the_web_folder(self):
        with tmp() as d, mock.patch.object(make_icons, "WEB", d), mock.patch.object(sys, "argv", ["make_icons.py"]), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            make_icons.main()
            self.assertEqual(sorted(p.name for p in d.iterdir()), FILES)
        self.assertEqual(len(out.getvalue().splitlines()), 5)

    def test_the_out_dir_is_created_when_missing(self):
        with tmp() as d:
            r = run_tool("make_icons.py", d / "new" / "dir")
            self.assertEqual((r.returncode, sorted(p.name for p in (d / "new" / "dir").iterdir())), (0, FILES))

    def test_a_page_without_the_colour_tokens_is_an_error_line_with_exit_1(self):
        with tmp() as d:
            page = d / "index.html"
            page.write_text(":root { --color-bg: #000000; }", encoding="utf-8")
            with mock.patch.object(make_icons, "PAGE", page), mock.patch.object(sys, "argv", ["make_icons.py", str(d / "out")]), \
                    mock.patch.object(sys, "stderr", io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    make_icons.main()
            self.assertRegex(str(cm.exception.code), r"^error: .*--color-accent")
            self.assertFalse((d / "out").exists())


if __name__ == "__main__":
    unittest.main()
