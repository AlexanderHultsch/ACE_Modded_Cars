"""Tests for tools/refgraph.py on a synthetic extracted car tree: classification, path boundaries, output format, exit codes."""
import contextlib
import io
import pathlib
import sys
import unittest
from unittest import mock

from support import pb_str, run_tool, tmp

import refgraph

CAR = "content\\cars\\ks_demo\\"
LONG_NAME = "a" * 100 + ".curve"
LONG_REF = CAR + "data\\" + LONG_NAME
POWER = CAR + r"data\power.curve"

FILES = {
    "data/engine.engine": b"".join([
        pb_str(1, POWER),
        pb_str(2, r"content\cars\ks_other\data\x.curve"),
        pb_str(3, CAR + r"data\gone.curve"),
        pb_str(4, CAR + "sfx"),
        pb_str(5, r"Content\Cars\KS_DEMO\Data\POWER.CURVE"),
        pb_str(7, CAR + r"data\mixed.tyre"),
        pb_str(8, r"content\cars\ks_other\data\y.curve"),
    ]),
    "data/glued.engine": pb_str(1, POWER) + pb_str(6, "x"),
    "data/long.engine": pb_str(1, LONG_REF) + pb_str(6, "x"),
    "data/self.engine": pb_str(1, CAR + r"data\self.engine"),
    "data/power.curve": b"1 2 3\n",
    "data/Mixed.Tyre": b"",
    "data/" + LONG_NAME: b"",
    "ui/icon.png": b"\x89PNG",
    "ui/refs.txt": b"content/cars/ks_demo/ui/icon.png.\nmore=content\\\\cars\\\\ks_demo\\\\data\\\\x.curve\n",
    "sfx/bank.bin": b"\x00",
}

EXPECTED = "\n".join([
    "== per-file references ==",
    CAR + r"data\engine.engine",
    "  MISSING  " + CAR + r"data\gone.curve",
    "  ok       " + CAR + r"data\mixed.tyre",
    "  ok       " + POWER,
    "  ok       " + CAR + "sfx",
    r"  external content\cars\ks_other\data\x.curve",
    r"  external content\cars\ks_other\data\y.curve",
    CAR + r"data\glued.engine",
    "  ok       " + POWER,
    CAR + r"data\long.engine",
    "  ok       " + LONG_REF,
    CAR + r"data\self.engine",
    "  ok       " + CAR + r"data\self.engine",
    CAR + r"ui\refs.txt",
    "  external content\\\\cars\\\\ks_demo\\\\data\\\\x.curve",
    "  ok       " + CAR + r"ui\icon.png",
    "",
    "== summary ==",
    "files scanned: 10, files with refs: 5, distinct refs: 10 (ok 6, missing 1, external 3, fallback 2)",
    "",
    "MISSING refs (1):",
    "  " + CAR + r"data\gone.curve",
    "    in " + CAR + r"data\engine.engine",
    "",
    "EXTERNAL refs by group (2 groups):",
    "  content\\\\cars  refs=1 files=1",
    r"  content\cars\ks_other  refs=2 files=1",
    "",
    "FALLBACK refs (2):",
    "  content\\\\cars\\\\ks_demo\\\\data\\\\x.curve",
    "    in " + CAR + r"ui\refs.txt",
    "  " + CAR + r"ui\icon.png",
    "    in " + CAR + r"ui\refs.txt",
    "",
    "Files never referenced by any other file (6):",
    "  " + CAR + r"data\engine.engine",
    "  " + CAR + r"data\glued.engine",
    "  " + CAR + r"data\long.engine",
    "  " + CAR + r"data\self.engine",
    "  " + CAR + r"sfx\bank.bin",
    "  " + CAR + r"ui\refs.txt",
    "",
])

CLEAN = {
    "data/engine.engine": pb_str(1, POWER) + pb_str(2, CAR + "sfx"),
    "data/power.curve": b"1 2 3\n",
    "sfx/bank.bin": b"\x00",
}

USAGE = refgraph.__doc__.split("\n\n")[1]


def write_tree(root, files):
    for rel, data in files.items():
        p = root / "content" / "cars" / "ks_demo" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def run_main(*args):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "argv", ["refgraph.py", *map(str, args)]), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            refgraph.main()
        except SystemExit as e:
            return e.code, out.getvalue(), err.getvalue()
    raise AssertionError("main() returned without exiting")


def section(out, title):
    """The lines of one report section: from its heading line up to the next blank line."""
    lines = out.split("\n")
    start = next(i for i, ln in enumerate(lines) if ln.startswith(title))
    end = start
    while lines[end]:
        end += 1
    return lines[start:end]


def file_section(out, rel):
    """The reference lines listed under one file in the per-file section."""
    lines = section(out, "== per-file references ==")[1:]
    start = lines.index(rel)
    end = start + 1
    while end < len(lines) and lines[end].startswith("  "):
        end += 1
    return lines[start + 1:end]


class Report(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tmp()
        cls.root = cls._tmp.__enter__()
        write_tree(cls.root, FILES)
        cls.r = run_tool("refgraph.py", cls.root)
        cls.out = cls.r.stdout

    @classmethod
    def tearDownClass(cls):
        cls._tmp.__exit__(None, None, None)

    def test_full_output_on_the_small_tree(self):
        self.assertEqual(self.out, EXPECTED)

    def test_missing_ref_gives_exit_1_and_nothing_on_stderr(self):
        self.assertEqual(self.r.returncode, 1)
        self.assertEqual(self.r.stderr, "")

    def test_classification_ok_missing_external(self):
        self.assertEqual(file_section(self.out, CAR + r"data\engine.engine"), [
            "  MISSING  " + CAR + r"data\gone.curve",
            "  ok       " + CAR + r"data\mixed.tyre",
            "  ok       " + POWER,
            "  ok       " + CAR + "sfx",
            r"  external content\cars\ks_other\data\x.curve",
            r"  external content\cars\ks_other\data\y.curve",
        ])

    def test_summary_counts(self):
        self.assertEqual(section(self.out, "== summary ==")[1],
                         "files scanned: 10, files with refs: 5, distinct refs: 10 "
                         "(ok 6, missing 1, external 3, fallback 2)")

    def test_missing_section_names_the_referring_file(self):
        self.assertEqual(section(self.out, "MISSING refs"), [
            "MISSING refs (1):",
            "  " + CAR + r"data\gone.curve",
            "    in " + CAR + r"data\engine.engine",
        ])

    def test_external_refs_are_grouped_by_first_three_segments(self):
        self.assertIn(r"  content\cars\ks_other  refs=2 files=1", section(self.out, "EXTERNAL refs by group"))

    def test_path_glued_to_the_next_field_tag_ends_at_the_length(self):
        self.assertEqual(file_section(self.out, CAR + r"data\glued.engine"), ["  ok       " + POWER])
        self.assertNotIn("power.curve2", self.out)

    def test_two_byte_length_prefix_for_a_path_over_127_bytes(self):
        self.assertGreater(len(LONG_REF), 127)
        self.assertEqual(file_section(self.out, CAR + r"data\long.engine"), ["  ok       " + LONG_REF])
        self.assertNotIn(LONG_NAME + "2", self.out)

    def test_case_differences_are_one_ref_and_match_files_case_insensitively(self):
        lines = file_section(self.out, CAR + r"data\engine.engine")
        self.assertEqual(sum(1 for ln in lines if ln.endswith("power.curve")), 1)
        self.assertIn("  ok       " + CAR + r"data\mixed.tyre", lines)
        self.assertNotIn("POWER", self.out)

    def test_directory_entry_counts_as_existing(self):
        self.assertIn("  ok       " + CAR + "sfx", file_section(self.out, CAR + r"data\engine.engine"))

    def test_fallback_lists_refs_found_only_by_the_regex_with_their_files(self):
        self.assertEqual(section(self.out, "FALLBACK refs"), [
            "FALLBACK refs (2):",
            "  content\\\\cars\\\\ks_demo\\\\data\\\\x.curve",
            "    in " + CAR + r"ui\refs.txt",
            "  " + CAR + r"ui\icon.png",
            "    in " + CAR + r"ui\refs.txt",
        ])

    def test_forward_slashes_are_normalized_and_the_trailing_dot_is_dropped(self):
        self.assertIn("  ok       " + CAR + r"ui\icon.png", file_section(self.out, CAR + r"ui\refs.txt"))

    def test_doubled_backslashes_are_not_collapsed_and_count_as_external(self):
        self.assertIn("  external content\\\\cars\\\\ks_demo\\\\data\\\\x.curve", file_section(self.out, CAR + r"ui\refs.txt"))
        self.assertIn("  content\\\\cars  refs=1 files=1", section(self.out, "EXTERNAL refs by group"))

    def test_never_referenced_list_ignores_self_and_directory_refs(self):
        listed = section(self.out, "Files never referenced")
        self.assertEqual(listed[0], "Files never referenced by any other file (6):")
        names = [ln.strip() for ln in listed[1:]]
        for rel in ("data\\power.curve", "data\\Mixed.Tyre", "data\\" + LONG_NAME, "ui\\icon.png"):
            self.assertNotIn(CAR + rel, names)
        for rel in ("data\\self.engine", "sfx\\bank.bin", "data\\engine.engine"):
            self.assertIn(CAR + rel, names)


class FindRefs(unittest.TestCase):
    def test_length_prefixed_string_gives_an_exact_ref(self):
        self.assertEqual(refgraph.find_refs(pb_str(1, POWER)), ({POWER}, set()))

    def test_exact_ref_ends_before_the_following_tag_byte(self):
        self.assertEqual(refgraph.find_refs(pb_str(1, POWER) + pb_str(6, "x")), ({POWER}, set()))

    def test_ref_in_unprefixed_text_is_a_fallback_ref(self):
        self.assertEqual(refgraph.find_refs(b"content/cars/ks_demo/data/a.curve and more"),
                         (set(), {CAR + r"data\a.curve"}))

    def test_a_ref_found_exactly_is_not_also_a_fallback_ref(self):
        data = pb_str(1, POWER) + b"\x00" + POWER.encode() + b" end"
        self.assertEqual(refgraph.find_refs(data), ({POWER}, set()))

    def test_string_without_separator_or_dot_is_no_ref(self):
        self.assertEqual(refgraph.normalize(b"content\\"), None)
        self.assertEqual(refgraph.normalize(b"content/"), None)

    def test_normalize_lowercases_and_strips_trailing_dots_and_backslashes(self):
        self.assertEqual(refgraph.normalize(b"Content/Cars/X/A.Curve..\\"), "content\\cars\\x\\a.curve")

    def test_empty_data_has_no_refs(self):
        self.assertEqual(refgraph.find_refs(b""), (set(), set()))


class ExitCodes(unittest.TestCase):
    def test_no_missing_refs_gives_exit_0(self):
        with tmp() as d:
            write_tree(d, CLEAN)
            r = run_tool("refgraph.py", d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        self.assertIn("(ok 2, missing 0, external 0, fallback 0)", r.stdout)
        self.assertIn("MISSING refs (0):\n\nEXTERNAL refs by group (0 groups):\n", r.stdout)

    def test_missing_ref_gives_exit_1_not_2(self):
        with tmp() as d:
            write_tree(d, {"data/a.engine": pb_str(1, CAR + r"data\nope.curve")})
            r = run_tool("refgraph.py", d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("(ok 0, missing 1, external 0, fallback 0)", r.stdout)

    def test_empty_folder_has_no_refs_and_exit_0(self):
        with tmp() as d:
            r = run_tool("refgraph.py", d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "\n".join([
            "== per-file references ==",
            "",
            "== summary ==",
            "files scanned: 0, files with refs: 0, distinct refs: 0 (ok 0, missing 0, external 0, fallback 0)",
            "",
            "MISSING refs (0):",
            "",
            "EXTERNAL refs by group (0 groups):",
            "",
            "FALLBACK refs (0):",
            "",
            "Files never referenced by any other file (0):",
            "",
        ]))

    def test_without_a_cars_folder_every_ref_is_external(self):
        with tmp() as d:
            (d / "x.bin").write_bytes(pb_str(1, POWER))
            r = run_tool("refgraph.py", d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("(ok 0, missing 0, external 1, fallback 0)", r.stdout)

    def test_no_arguments_prints_only_the_usage_block_on_stdout_and_exits_2(self):
        r = run_tool("refgraph.py")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout.strip(), USAGE.strip())
        self.assertEqual(r.stderr, "")

    def test_usage_block_is_the_paragraph_after_the_title(self):
        self.assertTrue(USAGE.startswith("usage: python tools/refgraph.py <extracted_root>"), USAGE)
        self.assertNotIn("Exit code", USAGE)

    def test_too_many_arguments_print_usage_and_exit_2(self):
        with tmp() as d:
            r = run_tool("refgraph.py", d, d)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout.strip(), USAGE.strip())
        self.assertEqual(r.stderr, "")

    def test_a_file_instead_of_a_directory_prints_usage_and_exits_2(self):
        with tmp() as d:
            f = d / "file.bin"
            f.write_bytes(b"")
            r = run_tool("refgraph.py", f)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout.strip(), USAGE.strip())
        self.assertEqual(r.stderr, "")

    def test_a_missing_folder_prints_usage_and_exits_2(self):
        with tmp() as d:
            r = run_tool("refgraph.py", d / "does-not-exist")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout.strip(), USAGE.strip())

    def test_unreadable_root_is_an_error_line_on_stderr_and_exit_1(self):
        with tmp() as d, mock.patch.object(pathlib.Path, "rglob", side_effect=PermissionError(13, "Permission denied")):
            code, out, err = run_main(d)
        self.assertEqual(code, "error: [Errno 13] Permission denied")
        self.assertEqual(out, "")
        self.assertEqual(err, "")

    def test_unreadable_file_is_an_error_line_and_exit_1(self):
        with tmp() as d:
            write_tree(d, CLEAN)
            with mock.patch.object(pathlib.Path, "read_bytes", side_effect=PermissionError(13, "Permission denied")):
                code, out, _ = run_main(d)
        self.assertTrue(code.startswith("error: "), code)
        self.assertEqual(out, "")

    def test_main_reports_missing_with_exit_code_1_and_usage_with_2(self):
        with tmp() as d:
            write_tree(d, FILES)
            code, out, _ = run_main(d)
            self.assertEqual((code, out), (1, EXPECTED))
            self.assertEqual(run_main(d / "nope")[0], 2)


if __name__ == "__main__":
    unittest.main()
