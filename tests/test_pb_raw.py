"""Tests for tools/pb_raw.py: schema-less protobuf text dump on hand-built messages, error types, CLI."""
import contextlib
import io
import struct
import unittest

from support import (pb_bytes, pb_f32, pb_f64, pb_int, pb_key, pb_msg, pb_str, pb_varint, run_tool, tmp)

import pb_raw


def lines_of(data, depth=0):
    lines = []
    pb_raw.dump(data, depth, out=lines.append)
    return lines


GOLDEN_MESSAGE = b"".join([
    pb_int(1, 150),
    pb_int(2, 0),
    pb_int(3, 2 ** 64 - 1),
    pb_f32(4, 1.5),
    pb_f32(5, -0.1),
    pb_f64(6, 3.14159265358979),
    pb_f64(7, 1e-10),
    pb_str(8, "hello world"),
    pb_str(9, "Ünïcödé"),
    pb_msg(10, pb_int(1, 7), pb_str(2, "inner"), pb_msg(3, pb_int(1, 1))),
    pb_int(11, 1),
    pb_int(11, 2),
    pb_int(11, 3),
    pb_bytes(12, b"\xff\xfe\xfd"),
    pb_bytes(13, b""),
    pb_bytes(14, b" A B C"),
    pb_bytes(15, b" \xc2\xa1A"),
])

GOLDEN_TEXT = [
    "1: 150",
    "2: 0",
    "3: 18446744073709551615",
    "4: (f32) 1.5",
    "5: (f32) -0.1",
    "6: (f64) 3.14159",
    "7: (f64) 1e-10",
    '8: "hello world"',
    '9: "Ünïcödé"',
    "10 {",
    "  1: 7",
    '  2: "inner"',
    "  3 {",
    "    1: 1",
    "  }",
    "}",
    "11: 1",
    "11: 2",
    "11: 3",
    "12: <3 bytes>",
    '13: ""',
    '14: " A B C"',
    "15 {",
    "  4: 1069250",
    "}",
]


class Varint(unittest.TestCase):
    def test_reads_values_and_returns_the_next_offset(self):
        for v in (0, 1, 127, 128, 300, 2 ** 32, 2 ** 64 - 1):
            enc = pb_varint(v)
            self.assertEqual(pb_raw.varint(enc + b"\x99", 0), (v, len(enc)), v)

    def test_reads_from_an_offset(self):
        self.assertEqual(pb_raw.varint(b"\xaa\xac\x02", 1), (300, 3))

    def test_truncated_varint_raises_value_error(self):
        with self.assertRaises(ValueError):
            pb_raw.varint(b"\x80\x80", 0)


class DumpScalars(unittest.TestCase):
    def test_varint_field(self):
        self.assertEqual(lines_of(pb_int(1, 150)), ["1: 150"])

    def test_varint_field_with_large_field_number(self):
        self.assertEqual(lines_of(pb_int(2000, 1)), ["2000: 1"])

    def test_fixed32_is_printed_as_float(self):
        self.assertEqual(lines_of(pb_f32(2, 1.5)), ["2: (f32) 1.5"])

    def test_fixed64_is_printed_as_double(self):
        self.assertEqual(lines_of(pb_f64(3, 0.25)), ["3: (f64) 0.25"])

    def test_floats_use_general_format_with_six_significant_digits(self):
        self.assertEqual(lines_of(pb_f64(1, 1234567.891)), ["1: (f64) 1.23457e+06"])

    def test_string_field_is_quoted(self):
        self.assertEqual(lines_of(pb_str(4, "abc")), ['4: "abc"'])

    def test_non_ascii_string_field_is_quoted(self):
        self.assertEqual(lines_of(pb_str(4, "éè")), ['4: "éè"'])

    def test_repeated_field_prints_one_line_per_occurrence(self):
        data = pb_int(5, 1) + pb_int(5, 2) + pb_int(5, 3)
        self.assertEqual(lines_of(data), ["5: 1", "5: 2", "5: 3"])

    def test_bytes_that_are_not_utf8_print_their_length(self):
        self.assertEqual(lines_of(pb_bytes(6, b"\xff\xfe\xfd")), ["6: <3 bytes>"])

    def test_non_printable_bytes_that_are_not_a_message_print_their_length(self):
        self.assertEqual(lines_of(pb_bytes(6, b"\x01\x02\x03\x04\x05")), ["6: <5 bytes>"])

    def test_empty_length_delimited_field_prints_an_empty_string(self):
        self.assertEqual(lines_of(pb_bytes(7, b"")), ['7: ""'])

    def test_empty_message_prints_nothing(self):
        self.assertEqual(lines_of(b""), [])


class DumpNesting(unittest.TestCase):
    def test_nested_message_is_braced_and_indented(self):
        data = pb_msg(1, pb_int(1, 7), pb_str(2, "inner"))
        self.assertEqual(lines_of(data), ["1 {", "  1: 7", '  2: "inner"', "}"])

    def test_depth_argument_indents_every_line(self):
        self.assertEqual(lines_of(pb_int(1, 7), depth=2), ["    1: 7"])

    def test_deeply_nested_messages_print_one_brace_pair_per_level(self):
        data = pb_int(1, 1)
        for _ in range(6):
            data = pb_msg(1, data)
        expected = [f"{'  ' * d}1 {{" for d in range(6)] + ["  " * 6 + "1: 1"] + [f"{'  ' * d}}}" for d in reversed(range(6))]
        self.assertEqual(lines_of(data), expected)

    def test_printable_ascii_that_also_parses_as_a_message_prints_as_a_string(self):
        data = pb_bytes(1, b" A B C")
        self.assertTrue(pb_raw.looks_like_msg(b" A B C"))
        self.assertEqual(lines_of(data), ['1: " A B C"'])

    def test_printable_non_ascii_text_that_parses_as_a_message_prints_as_a_message(self):
        data = pb_bytes(1, b" \xc2\xa1B")
        self.assertEqual(lines_of(data), ["1 {", "  4: 1085634", "}"])

    def test_out_none_prints_nothing_and_returns_none(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertIsNone(pb_raw.dump(pb_int(1, 1), 0, out=None))
        self.assertEqual(buf.getvalue(), "")

    def test_default_output_goes_to_stdout(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pb_raw.dump(pb_int(1, 150), 0)
        self.assertEqual(buf.getvalue(), "1: 150\n")


class GoldenOutput(unittest.TestCase):
    def test_mixed_message_dumps_to_exactly_this_text(self):
        self.assertEqual(lines_of(GOLDEN_MESSAGE), GOLDEN_TEXT)

    def test_cli_prints_the_same_text_for_a_file(self):
        with tmp() as d:
            path = d / "mixed.bin"
            path.write_bytes(GOLDEN_MESSAGE)
            r = run_tool("pb_raw.py", path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), GOLDEN_TEXT)


class Errors(unittest.TestCase):
    def test_field_number_zero_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "field 0"):
            lines_of(b"\x00\x01")

    def test_group_and_reserved_wire_types_raise_value_error(self):
        for wt in (3, 4, 6, 7):
            with self.subTest(wire_type=wt), self.assertRaisesRegex(ValueError, f"wire type {wt}"):
                lines_of(pb_key(1, wt))

    def test_truncated_length_delimited_field_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "truncated"):
            lines_of(pb_key(1, 2) + pb_varint(5) + b"abc")

    def test_truncated_key_raises_value_error(self):
        with self.assertRaises(ValueError):
            lines_of(b"\x80")

    def test_truncated_varint_value_raises_value_error(self):
        with self.assertRaises(ValueError):
            lines_of(pb_key(1, 0) + b"\x80")

    def test_missing_length_raises_value_error(self):
        with self.assertRaises(ValueError):
            lines_of(pb_key(1, 2))

    def test_truncated_fixed32_raises_struct_error(self):
        with self.assertRaises(struct.error):
            lines_of(pb_key(1, 5) + b"\x00\x00\x00")

    def test_truncated_fixed64_raises_struct_error(self):
        with self.assertRaises(struct.error):
            lines_of(pb_key(1, 1) + b"\x00" * 7)


class LooksLikeMsg(unittest.TestCase):
    def test_valid_message_is_accepted(self):
        self.assertTrue(pb_raw.looks_like_msg(pb_int(1, 1) + pb_str(2, "x")))

    def test_empty_input_is_not_a_message(self):
        self.assertFalse(pb_raw.looks_like_msg(b""))

    def test_plain_text_is_not_a_message(self):
        self.assertFalse(pb_raw.looks_like_msg(b"hello world"))

    def test_field_zero_is_not_a_message(self):
        self.assertFalse(pb_raw.looks_like_msg(b"\x00\x01"))

    def test_truncated_data_is_not_a_message(self):
        self.assertFalse(pb_raw.looks_like_msg(pb_key(1, 2) + pb_varint(9) + b"ab"))

    def test_unsupported_wire_type_is_not_a_message(self):
        self.assertFalse(pb_raw.looks_like_msg(pb_key(1, 3)))

    def test_looks_like_msg_prints_nothing(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pb_raw.looks_like_msg(GOLDEN_MESSAGE)
        self.assertEqual(buf.getvalue(), "")


class CommandLine(unittest.TestCase):
    def test_no_arguments_exits_2_with_usage_on_stdout(self):
        r = run_tool("pb_raw.py")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertTrue(r.stdout.startswith("usage:"), r.stdout)


if __name__ == "__main__":
    unittest.main()
