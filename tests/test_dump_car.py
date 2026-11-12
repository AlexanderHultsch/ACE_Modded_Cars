"""Tests for tools/dump_car.py on a synthetic extracted car folder."""
import contextlib
import io
import sys
import unittest
from unittest import mock

from support import pb_int, pb_msg, pb_str, run_tool, tmp

import dump_car

ENGINE = pb_int(1, 5) + pb_str(2, "turbo")
SETUP = pb_msg(1, pb_int(1, 3))
TEXT = b"line one\nbad byte \xff\nline three\n"


def make_car(root):
    files = {
        "data/engine.engine": ENGINE,
        "data/setups/deep/stock.setup": SETUP,
        "data/UPPER.ENGINE": ENGINE,
        "data/empty.engine": b"",
        "data/broken.engine": b"\x00\x01",
        "ui/en.cars.loc": TEXT,
        "meshes/body.mesh": b"\x00\x01 not decoded",
        "meshes/Skin.MESH": b"\x00\x01 not decoded",
        "ui/icon.png": b"\x89PNG",
    }
    for rel, data in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def run_main(src, dst):
    buf = io.StringIO()
    with mock.patch.object(sys, "argv", ["dump_car.py", str(src), str(dst)]), contextlib.redirect_stdout(buf):
        dump_car.main()
    return buf.getvalue()


def produced(dst):
    return {p.relative_to(dst).as_posix(): p.read_text(encoding="utf-8") for p in dst.rglob("*") if p.is_file()}


class DumpCar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tmp()
        base = cls._tmp.__enter__()
        cls.src, cls.dst = base / "car", base / "decoded" / "car"
        make_car(cls.src)
        cls.stdout = run_main(cls.src, cls.dst)
        cls.files = produced(cls.dst)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.__exit__(None, None, None)

    def test_prints_source_folder_and_counts(self):
        self.assertEqual(self.stdout, f"{self.src}: decoded 5, failed 1\n")

    def test_output_has_one_txt_per_handled_file_in_the_same_layout(self):
        self.assertEqual(sorted(self.files), [
            "data/UPPER.ENGINE.txt",
            "data/broken.engine.txt",
            "data/empty.engine.txt",
            "data/engine.engine.txt",
            "data/setups/deep/stock.setup.txt",
            "ui/en.cars.loc.txt",
        ])

    def test_protobuf_file_is_dumped_as_field_text(self):
        self.assertEqual(self.files["data/engine.engine.txt"], '1: 5\n2: "turbo"\n')

    def test_nested_protobuf_in_a_subfolder_is_dumped_with_braces(self):
        self.assertEqual(self.files["data/setups/deep/stock.setup.txt"], "1 {\n  1: 3\n}\n")

    def test_extension_match_ignores_case(self):
        self.assertEqual(self.files["data/UPPER.ENGINE.txt"], self.files["data/engine.engine.txt"])

    def test_empty_file_decodes_to_a_single_newline(self):
        self.assertEqual(self.files["data/empty.engine.txt"], "\n")

    def test_skipped_extensions_produce_no_output_and_are_not_counted(self):
        self.assertFalse([k for k in self.files if k.endswith((".mesh.txt", ".MESH.txt", ".png.txt"))])

    def test_text_extension_is_copied_with_invalid_bytes_replaced(self):
        self.assertEqual(self.files["ui/en.cars.loc.txt"], "line one\nbad byte �\nline three\n")

    def test_undecodable_file_gets_a_decode_failed_note_with_size_and_first_bytes(self):
        self.assertEqual(self.files["data/broken.engine.txt"],
                         "# DECODE FAILED: field 0\n# size=2 first bytes=00 01\n")

    def test_existing_output_folder_is_reused(self):
        with tmp() as d:
            src, dst = d / "car", d / "out"
            make_car(src)
            (dst / "data").mkdir(parents=True)
            self.assertEqual(run_main(src, dst), f"{src}: decoded 5, failed 1\n")
            self.assertEqual(produced(dst), self.files)

    def test_cli_runs_the_same_conversion(self):
        with tmp() as d:
            src, dst = d / "car", d / "out"
            make_car(src)
            r = run_tool("dump_car.py", src, dst)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, f"{src}: decoded 5, failed 1\n")
            self.assertEqual(produced(dst), self.files)

    def test_nonexistent_source_folder_is_an_error(self):
        with tmp() as d:
            r = run_tool("dump_car.py", d / "does-not-exist", d / "out")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue(r.stderr.startswith("error:"), r.stderr)

    def test_no_arguments_exits_2_with_usage_on_stdout(self):
        r = run_tool("dump_car.py")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout.strip(), dump_car.__doc__.split("\n\n")[1].strip())


if __name__ == "__main__":
    unittest.main()
