"""Tests for tools/extract_protos.py on synthetic descriptors: varint/fields, parse_*, render, scan(), sort_deps, main() on a fake exe, CLI conventions."""
import random
import unittest

from support import (desc_enum, desc_field, desc_file, desc_message, pb_bytes, pb_f32, pb_f64, pb_int, pb_str,
                     pb_varint, run_tool, tmp)

import extract_protos as ep

TYPE_INT32, TYPE_STRING, TYPE_MESSAGE, TYPE_ENUM = 5, 9, 11, 14
REPEATED = 3


def demo_file():
    entry = desc_message("PropsEntry", fields=[desc_field("key", 1, TYPE_STRING), desc_field("value", 2, TYPE_INT32)],
                         options=pb_int(7, 1))
    inner = desc_message("Inner", fields=[desc_field("x", 1, TYPE_INT32)])
    kind = desc_enum("Kind", [("UNKNOWN", 0), ("A", 1), ("NEG", -1)])
    outer = desc_message(
        "Outer",
        fields=[
            desc_field("id", 1, TYPE_INT32),
            desc_field("name", 2, TYPE_STRING),
            desc_field("tags", 3, TYPE_STRING, label=REPEATED),
            desc_field("inner", 4, TYPE_MESSAGE, type_name=".demo.Outer.Inner"),
            desc_field("kind", 5, TYPE_ENUM, type_name=".demo.Outer.Kind"),
            desc_field("a", 6, TYPE_INT32, oneof=0),
            desc_field("b", 7, TYPE_STRING, oneof=0),
            desc_field("props", 8, TYPE_MESSAGE, label=REPEATED, type_name=".demo.Outer.PropsEntry"),
            desc_field("samples", 9, TYPE_INT32, label=REPEATED, options=pb_int(2, 1)),
            desc_field("maybe", 10, TYPE_INT32, oneof=1, proto3_optional=True),
        ],
        nested=[inner, entry], enums=[kind], oneofs=["choice", "_maybe"],
        exts=[desc_field("mext", 100, TYPE_INT32, extendee=".demo.Inner")])
    return desc_file("demo/a.proto", "demo", deps=["demo/b.proto"], messages=[outer],
                     enums=[desc_enum("Color", [("RED", 0), ("GREEN", 1)])],
                     services=[("Svc", [("Get", ".demo.Outer", ".demo.Outer")])],
                     exts=[desc_field("fext", 200, TYPE_STRING, extendee=".demo.Outer")], syntax="proto3")


DEMO_PROTO = """\
syntax = "proto3";
package demo;
import "demo/b.proto";

enum Color {
  RED = 0;
  GREEN = 1;
}

extend Outer {
  string fext = 200;
}

message Outer {
  int32 id = 1;
  string name = 2;
  repeated string tags = 3;
  Outer.Inner inner = 4;
  Outer.Kind kind = 5;
  map<string, int32> props = 8;
  repeated int32 samples = 9;
  optional int32 maybe = 10;
  oneof choice {
    int32 a = 6;
    string b = 7;
  }
  extend Inner {
    int32 mext = 100;
  }
  enum Kind {
    UNKNOWN = 0;
    A = 1;
    NEG = -1;
  }
  message Inner {
    int32 x = 1;
  }
}

service Svc {
  rpc Get(Outer) returns (Outer);
}
"""


def simple_file(name, deps=(), package="p"):
    return desc_file(name, package, deps=deps, messages=[desc_message("M", fields=[desc_field("f", 1, TYPE_INT32)])])


def build_exe(blobs, seed=1, gap=300):
    """Random filler around zero-delimited blobs; returns (exe bytes, [offset of each blob])."""
    rnd = random.Random(seed)
    data = bytearray(rnd.randbytes(gap))
    offsets = []
    for b in blobs:
        data += b"\x00"
        offsets.append(len(data))
        data += b + b"\x00" + rnd.randbytes(gap)
    return bytes(data), offsets


def ref_scan(d):
    """Plain per-position reference of scan(): every offset with 0x0A, a length 7..127 and a name start letter."""
    found = []
    for start in range(len(d) - 2):
        c = d[start + 2]
        if d[start] != 0x0A or not 7 <= d[start + 1] <= 0x7F or not (65 <= c <= 90 or 97 <= c <= 122 or c == 95):
            continue
        n = d[start + 1]
        name = d[start + 2:start + 2 + n]
        if len(name) != n or not name.endswith(b".proto") or b"\x0a" in name:
            continue
        end = ep.file_end(d, start)
        try:
            ep.parse_file(d[start:end])
        except (ValueError, UnicodeDecodeError, TypeError):
            continue
        found.append((start, d[start:end]))
    return found


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def usage_block():
    return ep.__doc__.split("\n\n")[1].strip()


class Varint(unittest.TestCase):
    def test_known_encodings(self):
        for data, value in ((b"\x00", 0), (b"\x7f", 127), (b"\x80\x01", 128), (b"\xac\x02", 300),
                            (b"\xff\xff\xff\xff\x0f", 2 ** 32 - 1), (b"\xff" * 9 + b"\x01", 2 ** 64 - 1)):
            with self.subTest(value=value):
                self.assertEqual(ep.varint(data, 0), (value, len(data)))

    def test_reads_at_an_offset_and_returns_the_next_offset(self):
        self.assertEqual(ep.varint(b"xx\xac\x02yy", 2), (300, 4))

    def test_truncated_input_raises_value_error(self):
        for data in (b"", b"\x80", b"\xff\xff\xff"):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    ep.varint(data, 0)

    def test_offset_at_or_beyond_the_end_raises_value_error(self):
        for i in (1, 5):
            with self.assertRaises(ValueError):
                ep.varint(b"\x01", i)

    def test_more_than_ten_bytes_raises_value_error(self):
        with self.assertRaises(ValueError):
            ep.varint(b"\x80" * 10 + b"\x01", 0)
        with self.assertRaises(ValueError):
            ep.varint(b"\xff" * 12, 0)

    def test_varint_bytes_matches_the_reference_encoder_and_round_trips(self):
        for n in (0, 1, 127, 128, 255, 300, 16383, 16384, 2 ** 32, 2 ** 63, 2 ** 64 - 1):
            with self.subTest(n=n):
                enc = ep.varint_bytes(n)
                self.assertEqual(enc, pb_varint(n))
                self.assertEqual(ep.varint(enc, 0), (n, len(enc)))


class Fields(unittest.TestCase):
    def test_empty_message_has_no_fields(self):
        self.assertEqual(ep.fields(b""), [])

    def test_every_supported_wire_type_in_order(self):
        data = pb_int(1, 150) + pb_f64(2, 1.5) + pb_str(3, "hi") + pb_f32(4, -2.5) + pb_int(1, 7)
        self.assertEqual(ep.fields(data), [(1, 0, 150), (2, 1, 1.5), (3, 2, b"hi"), (4, 5, -2.5), (1, 0, 7)])

    def test_multi_byte_field_key_and_empty_length_delimited_value(self):
        self.assertEqual(ep.fields(pb_int(300, 5) + pb_bytes(2000, b"")), [(300, 0, 5), (2000, 2, b"")])

    def test_field_number_zero_raises(self):
        with self.assertRaises(ValueError):
            ep.fields(b"\x00\x01")

    def test_group_wire_types_raise(self):
        for wt in (3, 4, 6, 7):
            with self.subTest(wt=wt):
                with self.assertRaises(ValueError):
                    ep.fields(bytes([1 << 3 | wt]) + b"\x00" * 8)

    def test_truncated_values_raise(self):
        cases = {
            "varint": pb_int(1, 300)[:-1],
            "fixed64": pb_f64(1, 1.0)[:-1],
            "fixed32": pb_f32(1, 1.0)[:-1],
            "length prefix": b"\x0a",
            "payload": pb_str(1, "hello")[:-1],
            "key": b"\x80",
        }
        for label, data in cases.items():
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    ep.fields(data)

    def test_length_beyond_the_buffer_raises(self):
        with self.assertRaises(ValueError):
            ep.fields(b"\x0a\x7f" + b"x" * 5)


class Parse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = ep.parse_file(demo_file())
        cls.outer = cls.f["messages"][0]
        cls.by_name = {f["name"]: f for f in cls.outer["fields"]}

    def test_file_header(self):
        f = self.f
        self.assertEqual((f["name"], f["package"], f["deps"], f["syntax"]), ("demo/a.proto", "demo", ["demo/b.proto"], "proto3"))
        self.assertEqual(len(f["messages"]), 1)

    def test_defaults_for_a_minimal_file(self):
        f = ep.parse_file(pb_str(1, "x.proto"))
        self.assertEqual(f, {"name": "x.proto", "package": "", "deps": [], "messages": [], "enums": [], "services": [],
                             "exts": [], "syntax": ""})

    def test_message_fields_in_order_with_scalar_message_and_enum_types(self):
        got = [(f["name"], f["number"], f["type"], f["label"], f["type_name"]) for f in self.outer["fields"]]
        self.assertEqual(got, [
            ("id", 1, 5, 1, ""), ("name", 2, 9, 1, ""), ("tags", 3, 9, 3, ""),
            ("inner", 4, 11, 1, ".demo.Outer.Inner"), ("kind", 5, 14, 1, ".demo.Outer.Kind"),
            ("a", 6, 5, 1, ""), ("b", 7, 9, 1, ""), ("props", 8, 11, 3, ".demo.Outer.PropsEntry"),
            ("samples", 9, 5, 3, ""), ("maybe", 10, 5, 1, "")])

    def test_oneof_names_and_member_indices(self):
        self.assertEqual(self.outer["oneofs"], ["choice", "_maybe"])
        self.assertEqual([(f["name"], f["oneof"]) for f in self.outer["fields"] if f["oneof"] is not None],
                         [("a", 0), ("b", 0), ("maybe", 1)])
        self.assertTrue(self.by_name["maybe"]["proto3_optional"])
        self.assertFalse(self.by_name["a"]["proto3_optional"])

    def test_nested_messages_and_map_entry_flag(self):
        self.assertEqual([(n["name"], n["map_entry"]) for n in self.outer["nested"]], [("Inner", False), ("PropsEntry", True)])
        entry = self.outer["nested"][1]
        self.assertEqual([(f["name"], f["number"], f["type"]) for f in entry["fields"]], [("key", 1, 9), ("value", 2, 5)])

    def test_message_options_without_map_entry_do_not_set_the_flag(self):
        for options in (pb_int(3, 1), pb_int(7, 0), b""):
            with self.subTest(options=options):
                m = ep.parse_message(desc_message("M", options=options))
                self.assertFalse(m["map_entry"])

    def test_packed_field_option_is_ignored(self):
        plain = dict(self.by_name["samples"])
        again = ep.parse_field(desc_field("samples", 9, TYPE_INT32, label=REPEATED))
        self.assertEqual(plain, again)

    def test_enums_at_message_and_file_level_keep_negative_numbers(self):
        self.assertEqual(self.outer["enums"], [{"name": "Kind", "values": [
            {"name": "UNKNOWN", "number": 0}, {"name": "A", "number": 1}, {"name": "NEG", "number": -1}]}])
        self.assertEqual(self.f["enums"], [{"name": "Color", "values": [{"name": "RED", "number": 0}, {"name": "GREEN", "number": 1}]}])

    def test_enum_value_of_minimum_int64_is_negative(self):
        e = ep.parse_enum(desc_enum("E", [("LOW", -2 ** 63), ("HIGH", 2 ** 63 - 1)]))
        self.assertEqual([v["number"] for v in e["values"]], [-2 ** 63, 2 ** 63 - 1])

    def test_extensions_at_file_and_message_level(self):
        self.assertEqual([(x["name"], x["number"], x["extendee"]) for x in self.f["exts"]], [("fext", 200, ".demo.Outer")])
        self.assertEqual([(x["name"], x["number"], x["extendee"]) for x in self.outer["exts"]], [("mext", 100, ".demo.Inner")])

    def test_services_and_methods(self):
        self.assertEqual(self.f["services"], [{"name": "Svc", "methods": [{"name": "Get", "input": ".demo.Outer", "output": ".demo.Outer"}]}])

    def test_malformed_structures_raise_value_error(self):
        field_ok = desc_field("f", 1, TYPE_INT32)
        cases = {
            "file name without .proto": lambda: ep.parse_file(pb_str(1, "x.txt")),
            "file without name": lambda: ep.parse_file(pb_str(2, "pkg")),
            "file name as a varint": lambda: ep.parse_file(pb_int(1, 5)),
            "file name not UTF-8": lambda: ep.parse_file(pb_bytes(1, b"\xff\xfe.proto")),
            "message without name": lambda: ep.parse_message(pb_bytes(2, field_ok)),
            "enum without name": lambda: ep.parse_enum(pb_bytes(2, pb_str(1, "A"))),
            "field number 0": lambda: ep.parse_field(desc_field("f", 0, TYPE_INT32)),
            "field type 0": lambda: ep.parse_field(desc_field("f", 1, 0)),
            "field type 19": lambda: ep.parse_field(desc_field("f", 1, 19)),
            "field without name": lambda: ep.parse_field(pb_int(3, 1) + pb_int(5, 5)),
            "truncated nested message": lambda: ep.parse_file(pb_str(1, "x.proto") + pb_bytes(4, desc_message("M"))[:-1]),
        }
        for label, call in cases.items():
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    call()


class Render(unittest.TestCase):
    def test_demo_file_renders_to_the_expected_proto_text(self):
        self.assertEqual(ep.render(ep.parse_file(demo_file())), DEMO_PROTO)

    def test_file_without_syntax_or_package_renders_proto2_header_only(self):
        self.assertEqual(ep.render(ep.parse_file(pb_str(1, "x.proto"))), 'syntax = "proto2";\n')


class Scan(unittest.TestCase):
    def test_finds_every_embedded_descriptor_with_exact_offsets_and_bytes(self):
        blobs = [simple_file("a%d.proto" % i, package="pk%d" % i) for i in range(5)]
        data, offsets = build_exe(blobs, seed=3)
        self.assertEqual(ep.scan(data), list(zip(offsets, blobs)))

    def test_filler_without_descriptors_gives_nothing(self):
        self.assertEqual(ep.scan(random.Random(5).randbytes(5000)), [])
        self.assertEqual(ep.scan(b""), [])

    def test_a_blob_ending_at_the_end_of_the_data_is_found(self):
        blob = simple_file("tail.proto")
        self.assertEqual(ep.scan(b"\x00" * 7 + blob), [(7, blob)])

    def test_candidates_with_wrong_names_are_skipped(self):
        for name in (b"abc.txt", b"abcdefg", b"ab\n.proto"):
            with self.subTest(name=name):
                data = b"\x00\x00" + pb_bytes(1, name) + b"\x00\x00"
                self.assertEqual(ep.scan(data), [])

    def test_name_longer_than_the_data_is_skipped(self):
        self.assertEqual(ep.scan(b"\x00\x0a\x7fabc.proto"), [])

    def test_blob_that_does_not_parse_strictly_is_skipped(self):
        bad = pb_str(1, "bad.proto") + pb_bytes(4, b"\x0a\x05M")
        self.assertEqual(ep.scan(b"\x00" + bad + b"\x00"), [])

    def test_a_stray_0a_byte_directly_before_a_descriptor_does_not_hide_it(self):
        blob = simple_file("a" * 59 + ".proto")
        self.assertEqual(len(blob[2:blob[1] + 2]), 65)
        data = b"\x00\x00\x0a" + blob + b"\x00"
        self.assertEqual(ep.scan(data), [(3, blob)])

    def test_candidates_equal_a_plain_reference_search_on_dense_filler(self):
        tokens = [b"\x0a", b"\x0a\x0a", b"A", b"abc", b".proto", b"\x0a\x09abc.proto", b"\x0a\x41", b"_", b"\x00",
                  b"\x0a\x0b\x0ax.proto", simple_file("z.proto")]
        total = 0
        for seed in range(40):
            rnd = random.Random(seed)
            data = b"".join(rnd.choice(tokens) for _ in range(rnd.randint(1, 200)))
            got = ep.scan(data)
            self.assertEqual(got, ref_scan(data), "seed %d" % seed)
            total += len(got)
        self.assertGreater(total, 20)

    def test_candidates_equal_the_reference_on_random_bytes_with_embedded_descriptors(self):
        blobs = [simple_file("n%d.proto" % i, deps=["n%d.proto" % (i - 1)] if i else ()) for i in range(6)]
        for seed in range(5):
            data, offsets = build_exe(blobs, seed=seed, gap=2000)
            self.assertEqual(ep.scan(data), ref_scan(data))
            self.assertEqual([o for o, _ in ep.scan(data)], offsets)

    def test_candidate_with_a_varint_where_a_message_is_expected_is_skipped(self):
        bad = pb_str(1, "a_bad.proto") + pb_bytes(4, pb_str(1, "M") + pb_int(2, 1))
        good = simple_file("good.proto")
        self.assertEqual([b for _, b in ep.scan(b"\x00\x00" + bad + b"\x00\x00" + good + b"\x00")], [good])

    def test_candidate_with_bytes_where_an_enum_number_is_expected_is_skipped(self):
        bad = pb_str(1, "e_bad.proto") + pb_bytes(5, pb_str(1, "E") + pb_bytes(2, pb_str(1, "A") + pb_bytes(2, b"xy")))
        self.assertEqual(ep.scan(b"\x00\x00" + bad + b"\x00\x00"), [])


class SortDeps(unittest.TestCase):
    @staticmethod
    def blobs(spec):
        return {n: simple_file(n, deps=deps) for n, deps in spec}

    def test_dependencies_come_before_their_dependents(self):
        order = ep.sort_deps(self.blobs([("c.proto", ["b.proto"]), ("b.proto", ["a.proto"]), ("a.proto", [])]))
        self.assertEqual(order, ["a.proto", "b.proto", "c.proto"])

    def test_independent_files_keep_discovery_order(self):
        order = ep.sort_deps(self.blobs([("z.proto", []), ("m.proto", []), ("a.proto", [])]))
        self.assertEqual(order, ["z.proto", "m.proto", "a.proto"])

    def test_diamond_lists_the_shared_base_once_and_first(self):
        order = ep.sort_deps(self.blobs([("top.proto", ["l.proto", "r.proto"]), ("l.proto", ["base.proto"]),
                                         ("r.proto", ["base.proto"]), ("base.proto", [])]))
        self.assertEqual(order, ["base.proto", "l.proto", "r.proto", "top.proto"])

    def test_dependency_outside_the_set_is_ignored(self):
        order = ep.sort_deps(self.blobs([("a.proto", ["google/protobuf/any.proto"])]))
        self.assertEqual(order, ["a.proto"])

    def test_a_dependency_cycle_terminates_and_keeps_every_file_once(self):
        order = ep.sort_deps(self.blobs([("a.proto", ["b.proto"]), ("b.proto", ["a.proto"]), ("c.proto", ["a.proto"])]))
        self.assertEqual(sorted(order), ["a.proto", "b.proto", "c.proto"])
        self.assertLess(order.index("a.proto"), order.index("c.proto"))

    def test_empty_set(self):
        self.assertEqual(ep.sort_deps({}), [])


class SplitSet(unittest.TestCase):
    def test_returns_the_records_of_a_descriptor_set(self):
        a, b = simple_file("a.proto"), simple_file("b.proto")
        self.assertEqual(ep.split_set(pb_bytes(1, a) + pb_bytes(1, b)), [a, b])

    def test_other_fields_raise(self):
        with self.assertRaises(ValueError):
            ep.split_set(pb_bytes(2, b"x"))
        with self.assertRaises(ValueError):
            ep.split_set(pb_int(1, 5))


def self_check_line(records, names, protos, missing, misordered):
    return ("self-check: %d records parse strictly, %d unique names, %d .proto files on disk, "
            "%d missing dependencies, %d files listed before a dependency" % (records, names, protos, missing, misordered))


class Main(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tmp()
        cls.base = cls._tmp.__enter__()
        cls.a = simple_file("a.proto", package="demo")
        cls.b = simple_file("b.proto", deps=["a.proto"], package="demo")
        cls.c = simple_file("sub/c.proto", deps=["b.proto"], package="demo")
        cls.a_other = simple_file("a.proto", package="other")
        blobs = [cls.c, cls.b, cls.a, cls.a, cls.a_other]
        cls.exe_bytes, cls.offsets = build_exe(blobs, seed=11, gap=500)
        cls.exe = cls.base / "fake.exe"
        cls.exe.write_bytes(cls.exe_bytes)
        cls.out1, cls.out2 = cls.base / "out1", cls.base / "out2"
        cls.r1 = run_tool("extract_protos.py", cls.exe, cls.out1)
        cls.r2 = run_tool("extract_protos.py", cls.exe, cls.out2)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.__exit__(None, None, None)

    def test_exits_0_with_nothing_on_stderr(self):
        self.assertEqual((self.r1.returncode, self.r1.stderr), (0, ""))

    def test_acevo_desc_lists_the_first_copies_dependencies_first(self):
        want = b"".join(b"\x0a" + ep.varint_bytes(len(x)) + x for x in (self.a, self.b, self.c))
        self.assertEqual((self.out1 / "acevo.desc").read_bytes(), want)

    def test_one_proto_file_per_descriptor_including_nested_folders(self):
        files = tree(self.out1)
        self.assertEqual(sorted(files), ["a.proto", "acevo.desc", "b.proto", "sub/c.proto"])

    def test_proto_files_hold_the_rendering_of_the_first_copy(self):
        files = tree(self.out1)
        self.assertEqual(files["a.proto"].decode("utf-8"), ep.render(ep.parse_file(self.a)))
        self.assertIn(b"package demo;", files["a.proto"])
        self.assertIn(b'import "b.proto";', files["sub/c.proto"])

    def test_stdout_lists_descriptors_duplicates_and_the_self_check(self):
        lines = self.r1.stdout.splitlines()
        want = [
            "0x%08x %7d bytes  sub/c.proto" % (self.offsets[0], len(self.c)),
            "0x%08x %7d bytes  b.proto" % (self.offsets[1], len(self.b)),
            "0x%08x %7d bytes  a.proto" % (self.offsets[2], len(self.a)),
            "%s: 3 descriptors found, 2 duplicates skipped" % self.exe,
            "  duplicate a.proto at 0x%08x (identical)" % self.offsets[3],
            "  duplicate a.proto at 0x%08x (DIFFERENT)" % self.offsets[4],
            "wrote %s (%d bytes) and 3 .proto files" % (self.out1 / "acevo.desc", (self.out1 / "acevo.desc").stat().st_size),
            self_check_line(3, 3, 3, 0, 0),
        ]
        self.assertEqual(lines, want)

    def test_output_is_deterministic_across_runs(self):
        self.assertEqual(self.r2.returncode, 0, self.r2.stderr)
        self.assertEqual(tree(self.out1), tree(self.out2))
        self.assertEqual(self.r1.stdout.replace(str(self.out1), "OUT"), self.r2.stdout.replace(str(self.out2), "OUT"))

    def test_missing_dependency_is_reported_by_the_self_check_without_failing(self):
        with tmp() as d:
            blob = simple_file("x.proto", deps=["gone.proto"])
            (d / "x.exe").write_bytes(build_exe([blob], seed=2)[0])
            r = run_tool("extract_protos.py", d / "x.exe", d / "out")
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[-2:], [self_check_line(1, 1, 1, 1, 0), "  missing: gone.proto"])

    def test_exe_without_descriptors_writes_an_empty_set(self):
        with tmp() as d:
            (d / "x.exe").write_bytes(random.Random(1).randbytes(3000))
            r = run_tool("extract_protos.py", d / "x.exe", d / "out")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("0 descriptors found, 0 duplicates skipped", r.stdout)
            self.assertEqual(tree(d / "out"), {"acevo.desc": b""})

    def test_output_folder_is_created_with_its_parents(self):
        with tmp() as d:
            r = run_tool("extract_protos.py", self.exe, d / "deep" / "er" / "out")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(tree(d / "deep" / "er" / "out"), tree(self.out1))

    def test_rerun_into_an_existing_folder_with_the_same_descriptors_passes(self):
        with tmp() as d:
            for _ in range(2):
                r = run_tool("extract_protos.py", self.exe, d / "out")
                self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(tree(d / "out"), tree(self.out1))

    def test_rerun_into_an_existing_folder_with_fewer_descriptors_passes_the_self_check(self):
        with tmp() as d:
            first = build_exe([simple_file("aaaaaaa.proto"), simple_file("bbbbbbb.proto")], seed=4)[0]
            second = build_exe([simple_file("aaaaaaa.proto")], seed=4)[0]
            (d / "x.exe").write_bytes(first)
            self.assertEqual(run_tool("extract_protos.py", d / "x.exe", d / "out").returncode, 0)
            (d / "x.exe").write_bytes(second)
            r = run_tool("extract_protos.py", d / "x.exe", d / "out")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((d / "out" / "acevo.desc").read_bytes(), b"\x0a" + ep.varint_bytes(len(simple_file("aaaaaaa.proto"))) +
                             simple_file("aaaaaaa.proto"))

    def test_descriptor_name_with_parent_references_is_refused_and_nothing_is_written_outside(self):
        with tmp() as d:
            work = d / "work"
            work.mkdir()
            (work / "x.exe").write_bytes(build_exe([simple_file("sub/../../esc_out.proto")], seed=6)[0])
            r = run_tool("extract_protos.py", work / "x.exe", work / "out")
            self.assertFalse((work / "esc_out.proto").exists(), "written outside the out folder")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertTrue(r.stderr.startswith("error:"), r.stderr)
            self.assertLessEqual({p.name for p in work.iterdir()}, {"out", "x.exe"})
            self.assertFalse((d / "esc_out.proto").exists())


class CommandLine(unittest.TestCase):
    def test_no_arguments_exits_2_with_usage_on_stdout(self):
        r = run_tool("extract_protos.py")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout.strip(), usage_block())

    def test_one_argument_exits_2_with_usage_on_stdout(self):
        r = run_tool("extract_protos.py", "only-the-exe.exe")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout.strip(), usage_block())

    def test_three_arguments_exit_2_with_usage_on_stdout(self):
        with tmp() as d:
            (d / "x.exe").write_bytes(b"")
            r = run_tool("extract_protos.py", d / "x.exe", d / "out", d / "extra")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout.strip(), usage_block())

    def test_missing_exe_prints_error_on_stderr_and_exits_1(self):
        with tmp() as d:
            r = run_tool("extract_protos.py", d / "missing.exe", d / "out")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("error:"), r.stderr)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
