"""Tests for tools/pbedit.py. Run: python3 -m unittest discover -s tests"""
import pathlib
import struct
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import pb_raw  # noqa: E402
import pbedit  # noqa: E402

CORPUS = pathlib.Path(__file__).resolve().parents[1] / "hdc_1.4" / "extracted"
SUFFIXES = {".car", ".carengine", ".drivetrain", ".gearbox", ".curve", ".carsetup", ".carsetuplimits",
            ".clutch", ".coilover", ".suspension", ".tyre", ".wing", ".turbo", ".aicardata",
            ".brakesystem", ".moddedcarcontent", ".mechanicalcarpreset", ".visualcarpreset",
            ".carfinalstate", ".compatibletyres", ".cartuning", ".tuningpart"}
E46 = CORPUS / "e46" / "content" / "cars" / "hdc_bmw_e46_01" / "data"


def vi(v):
    out = bytearray()
    while v > 0x7F:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    out.append(v)
    return bytes(out)


def f_f32(n, x):
    return vi(n << 3 | 5) + struct.pack("<f", x)


def f_int(n, v):
    return vi(n << 3) + vi(v)


def f_bytes(n, b, lenraw=None):
    return vi(n << 3 | 2) + (lenraw if lenraw is not None else vi(len(b))) + b


def build():
    gears = b"".join(f_bytes(10, f_bytes(1, name) + f_f32(2, ratio))
                     for name, ratio in ((b"R", -3.678), (b"1", 4.2), (b"2", 2.5)))
    inner = f_f32(1, 0.5) + f_int(2, 300) + f_bytes(3, b"hello") + f_bytes(4, b"")
    overlong = f_bytes(39, f_f32(1, 0.85) + f_f32(2, 0.7), lenraw=bytes([0x80 | 10, 0x00]))
    holder = f_bytes(6, f_bytes(1, b"a" * 100) + f_int(2, 1))
    return f_bytes(5, inner) + gears + overlong + holder + f_f32(7, 1.5)


def curve(points):
    return b"".join(f_bytes(1, f_f32(1, rpm) + f_bytes(3, b"") + (f_f32(10, v) if v is not None else b""))
                    for rpm, v in points)


def f32(b):
    return struct.unpack("<f", b)[0]


class Synthetic(unittest.TestCase):
    def setUp(self):
        self.buf = build()

    def test_roundtrip_identical(self):
        self.assertEqual(pbedit.parse(self.buf).encode(), self.buf)

    def test_get_field(self):
        g = lambda p: pbedit.get_field(self.buf, p)
        self.assertEqual(g("5.1"), (5, struct.pack("<f", 0.5)))
        self.assertEqual(g("5.2"), (0, 300))
        self.assertEqual(g("5.3"), (2, b"hello"))
        self.assertEqual(g("5.4"), (2, b""))
        self.assertEqual(g("10[0].1"), (2, b"R"))
        self.assertEqual(g("10[1].1"), (2, b"1"))
        wt, v = g("10[2].2")
        self.assertEqual(wt, 5)
        self.assertAlmostEqual(f32(v), 2.5)
        self.assertAlmostEqual(f32(g("39.2")[1]), 0.7, places=6)
        self.assertEqual(g("6.2"), (0, 1))

    def test_set_f32_changes_only_value_bytes(self):
        new = pbedit.set_value(self.buf, "10[2].2", "f32", 9.75)
        self.assertEqual(len(new), len(self.buf))
        diff = [i for i in range(len(new)) if new[i] != self.buf[i]]
        self.assertTrue(diff)
        self.assertLessEqual(len(diff), 4)
        self.assertEqual(diff[-1] - diff[0] + 1, len(diff))
        self.assertEqual(f32(pbedit.get_field(new, "10[2].2")[1]), 9.75)
        self.assertEqual(pbedit.get_field(new, "10[1].1"), (2, b"1"))

    def test_set_int(self):
        new = pbedit.set_value(self.buf, "5.2", "int", 6)
        self.assertEqual(pbedit.get_field(new, "5.2"), (0, 6))
        self.assertEqual(pbedit.get_field(new, "5.3"), (2, b"hello"))

    def test_set_str_longer_recomputes_ancestor_lengths(self):
        old = b"a" * 100
        new_val = "b" * 200
        new = pbedit.set_value(self.buf, "6.1", "str", new_val)
        container_old = len(f_bytes(1, old) + f_int(2, 1))
        container_new = len(f_bytes(1, new_val.encode()) + f_int(2, 1))
        delta = (200 - 100) + (len(vi(200)) - len(vi(100))) + (len(vi(container_new)) - len(vi(container_old)))
        self.assertEqual(len(vi(100)), 1)
        self.assertEqual(len(vi(200)), 2)
        self.assertEqual(len(new) - len(self.buf), delta)
        self.assertEqual(pbedit.get_field(new, "6.1"), (2, new_val.encode()))
        self.assertEqual(pbedit.get_field(new, "6.2"), (0, 1))
        self.assertEqual(pbedit.get_field(new, "5.3"), (2, b"hello"))
        self.assertEqual(pbedit.get_field(new, "10[2].2"), pbedit.get_field(self.buf, "10[2].2"))
        self.assertEqual(pbedit.parse(new).encode(), new)

    def test_set_str_untouched_siblings_and_overlong_kept(self):
        new = pbedit.set_value(self.buf, "5.3", "str", "hi")
        self.assertEqual(len(new) - len(self.buf), -3)
        overlong = vi(39 << 3 | 2) + bytes([0x8A, 0x00])
        self.assertIn(overlong, new)
        self.assertEqual(new.count(overlong), 1)
        self.assertEqual(pbedit.get_field(new, "5.3"), (2, b"hi"))

    def test_set_inside_overlong_message_canonicalizes_its_length(self):
        new = pbedit.set_value(self.buf, "39.1", "f32", 1.0)
        self.assertEqual(len(new), len(self.buf) - 1)
        self.assertEqual(f32(pbedit.get_field(new, "39.1")[1]), 1.0)

    def test_mismatched_kind(self):
        for path, kind in (("5.1", "int"), ("5.1", "str"), ("5.2", "f32"), ("5.3", "int"), ("5.3", "f32")):
            with self.subTest(path=path, kind=kind):
                with self.assertRaises(ValueError):
                    pbedit.set_value(self.buf, path, kind, 1)

    def test_missing_path(self):
        for path in ("99", "5.99", "10[3].1", "99.1"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    pbedit.get_field(self.buf, path)
                with self.assertRaises(ValueError):
                    pbedit.set_value(self.buf, path, "int", 1)

    def test_descend_into_non_message(self):
        with self.assertRaises(ValueError) as cm:
            pbedit.get_field(self.buf, "5.2.1")
        self.assertIn("not a message", str(cm.exception))
        with self.assertRaises(ValueError):
            pbedit.get_field(self.buf, "5.3.1")

    def test_bad_input(self):
        for bad in (b"\x1b", b"\x0d\x00", b"\x0a\x05ab", b"\x08"):
            with self.subTest(buf=bad):
                with self.assertRaises(ValueError):
                    pbedit.parse(bad)
        with self.assertRaises(ValueError):
            pbedit.get_field(self.buf, "5.x")

    def test_scale_curve(self):
        buf = curve([(-1000, 0.5), (500, None), (1000, 213.081), (5000, 377.878)])
        new = pbedit.scale_curve(buf, 1.2)
        self.assertEqual(len(new), len(buf))
        for i, v in ((0, 0.5), (2, 213.081), (3, 377.878)):
            got = f32(pbedit.get_field(new, f"1[{i}].10")[1])
            self.assertAlmostEqual(got, v * 1.2, delta=abs(v * 1.2) * 1e-6)
        for i in range(4):
            self.assertEqual(pbedit.get_field(new, f"1[{i}].1"), pbedit.get_field(buf, f"1[{i}].1"))
        self.assertEqual(pbedit.get_field(new, "1[1].3"), (2, b""))
        with self.assertRaises(ValueError):
            pbedit.get_field(new, "1[1].10")

    def test_scale_curve_no_points(self):
        with self.assertRaises(ValueError):
            pbedit.scale_curve(f_f32(2, 1.0), 2.0)


class Corpus(unittest.TestCase):
    def files(self):
        return sorted(p for p in CORPUS.rglob("*") if p.is_file() and p.suffix.lower() in SUFFIXES)

    def test_corpus_has_files(self):
        self.assertTrue(self.files(), f"no matching files under {CORPUS}")

    def test_parse_and_roundtrip(self):
        non_identical = []
        for p in self.files():
            with self.subTest(file=str(p.relative_to(CORPUS))):
                buf = p.read_bytes()
                msg = pbedit.parse(buf)
                self.assertEqual(msg.encode(), buf)
                full = pbedit.reencode_full(buf)
                self.assertEqual(pbedit.parse(full).semantic(), msg.semantic())
                if full != buf:
                    non_identical.append(str(p.relative_to(CORPUS)))
        if non_identical:
            print(f"\nfull re-encode not byte-identical for {len(non_identical)} files: {non_identical}")


class CorpusEdit(unittest.TestCase):
    def check_single_float_edit(self, path, field_path):
        old = path.read_bytes()
        new = pbedit.set_value(old, field_path, "f32", 1.0)
        self.assertEqual(len(new), len(old))
        diff = [i for i in range(len(old)) if old[i] != new[i]]
        self.assertTrue(0 < len(diff) <= 4)
        self.assertEqual(diff[-1] - diff[0] + 1, len(diff))
        wt, v = pbedit.get_field(new, field_path)
        self.assertEqual((wt, f32(v)), (5, 1.0))
        a, b = [], []
        pb_raw.dump(old, 0, out=a.append)
        pb_raw.dump(new, 0, out=b.append)
        self.assertEqual(len(a), len(b))
        changed = [(x, y) for x, y in zip(a, b) if x != y]
        self.assertEqual([(x.strip(), y.strip()) for x, y in changed], [("1: (f32) 0.85", "1: (f32) 1")])

    def test_e46_drivetrain(self):
        self.check_single_float_edit(E46 / "ks_bmw_m3_e46_1.drivetrain", "39.1")

    def test_e46_cardata(self):
        self.check_single_float_edit(E46 / "cardata.car", "3.39.1")

    def test_e46_scale_curve(self):
        path = E46 / "bmw_m3_e46_coupe_engine_power_1.curve"
        old = path.read_bytes()
        new = pbedit.scale_curve(old, 1.2)
        self.assertEqual(len(new), len(old))
        old_pts = [f.message() for f in pbedit.parse(old).fields if f.num == 1]
        new_pts = [f.message() for f in pbedit.parse(new).fields if f.num == 1]
        self.assertEqual(len(old_pts), len(new_pts))
        found = scaled = untouched = 0
        for o, n in zip(old_pts, new_pts):
            if o.find(10) is None:
                self.assertIsNone(n.find(10))
                self.assertEqual(o.encode(), n.encode())
                untouched += 1
                continue
            ov, nv = f32(o.find(10).payload), f32(n.find(10).payload)
            self.assertAlmostEqual(nv, ov * 1.2, delta=abs(ov * 1.2) * 1e-3)
            scaled += 1
            if f32(o.find(1).payload) == 5000:
                found += 1
                self.assertAlmostEqual(f32(n.find(10).payload), 377.878 * 1.2, delta=377.878 * 1.2 * 1e-3)
        self.assertEqual(found, 1)
        self.assertTrue(scaled)
        self.assertTrue(untouched)


if __name__ == "__main__":
    unittest.main()
