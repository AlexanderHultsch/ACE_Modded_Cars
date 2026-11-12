"""Tests for tools/car_json.py on a synthetic schema: scalar/repeated/nested round trips, unknown fields, NaN, JSON text, seeded random messages, CLI."""
import ast
import json
import math
import pathlib
import random
import shutil
import struct
import subprocess
import sys
import unittest

from support import (TOOLS, desc_enum, desc_field, desc_file, desc_message, desc_set, pb_bytes, pb_int, pb_key, pb_msg,
                     pb_str, pb_varint, pb_vint, run_tool, tmp)

import car_json as cj

NAME = "CurveDataEx"
MASK64 = (1 << 64) - 1
SCALARS = {"d": 1, "f": 2, "i64": 3, "u64": 4, "i32": 5, "fx64": 6, "fx32": 7, "b": 8, "u32": 13, "e": 14,
           "sfx32": 15, "sfx64": 16, "s32": 17, "s64": 18}
FN = {name: t for name, t in SCALARS.items()}
FN.update({"s": 9, "sub": 11, "by": 12, "rs": 109, "rsub": 111, "rby": 112, "inner": 20, "mode": 21, "pk_item": 30,
           "pk_level": 31})
FN.update({"r_" + name: 100 + t for name, t in SCALARS.items()})
ENUM_NUM = {"A": 0, "B": 1, "NEG": -5, "B2": 1}
WIRE_TYPE = {1: 1, 2: 5, 3: 0, 4: 0, 5: 0, 6: 1, 7: 5, 8: 0, 13: 0, 14: 0, 15: 5, 16: 1, 17: 0, 18: 0}


def schema_bytes():
    fields = []
    for name, t in SCALARS.items():
        type_name = ".E" if t == 14 else ""
        fields.append(desc_field(name, t, t, 1, type_name))
        fields.append(desc_field("r_" + name, 100 + t, t, 3, type_name))
    fields += [
        desc_field("s", 9, 9), desc_field("rs", 109, 9, 3),
        desc_field("sub", 11, 11, 1, ".CurveDataEx"), desc_field("rsub", 111, 11, 3, ".CurveDataEx"),
        desc_field("by", 12, 12), desc_field("rby", 112, 12, 3),
        desc_field("inner", 20, 11, 1, ".CurveDataEx.Inner"), desc_field("mode", 21, 14, 1, ".CurveDataEx.Mode"),
        desc_field("pk_item", 30, 11, 1, ".pk.Item"), desc_field("pk_level", 31, 14, 1, ".pk.Level"),
    ]
    inner = desc_message("Inner", [desc_field("x", 1, 5), desc_field("y", 2, 9)])
    curve = desc_message(NAME, fields, nested=[inner], enums=[desc_enum("Mode", [("M0", 0), ("M1", 1)])])
    main = desc_file("t.proto", messages=[curve], enums=[desc_enum("E", [(n, v) for n, v in ENUM_NUM.items()])])
    pk = desc_file("pk.proto", "pk", messages=[desc_message("Item", [desc_field("n", 1, 5)])],
                   enums=[desc_enum("Level", [("LOW", 0), ("HIGH", 3)])])
    return desc_set(pk, main)


def zigzag(v):
    return (v << 1) ^ (v >> 63)


def body(t, v):
    """Wire bytes of one value of scalar type t, built without car_json (enum v is a name or a number)."""
    if t in (3, 4, 5, 13):
        return pb_varint(v & MASK64)
    if t == 14:
        return pb_varint((ENUM_NUM[v] if isinstance(v, str) else v) & MASK64)
    if t == 8:
        return pb_varint(int(v))
    if t in (17, 18):
        return pb_varint(zigzag(v))
    fmt = {1: "<d", 2: "<f", 6: "<Q", 7: "<I", 15: "<i", 16: "<q"}[t]
    return struct.pack(fmt, v)


def one(name, v):
    t = SCALARS[name]
    return pb_key(FN[name], WIRE_TYPE[t]) + body(t, v)


def packed(name, values):
    t = SCALARS[name[2:]]
    return pb_bytes(FN[name], b"".join(body(t, v) for v in values))


def unpacked(name, values):
    t = SCALARS[name[2:]]
    return b"".join(pb_key(FN[name], WIRE_TYPE[t]) + body(t, v) for v in values)


def fixed32(fn, bits):
    return pb_key(fn, 5) + struct.pack("<I", bits)


def fixed64(fn, bits):
    return pb_key(fn, 1) + struct.pack("<Q", bits)


def usage_block():
    return cj.__doc__.split("\n\n")[1].strip()


class SchemaCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tmp()
        base = cls._tmp.__enter__()
        (base / "acevo.desc").write_bytes(schema_bytes())
        cls.sch = cj.load_schema(base / "acevo.desc")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.__exit__(None, None, None)

    def decode(self, wire):
        return cj.decode_msg(self.sch, NAME, wire)

    def encode(self, obj):
        return cj.encode_msg(self.sch, NAME, obj)

    def text_round_trip(self, wire):
        """decode -> JSON text -> parse -> encode, as the CLI does."""
        return self.encode(cj.loads(cj.dumps(self.decode(wire))))

    def assert_lossless(self, wire):
        obj, err = cj.roundtrip(self.sch, NAME, wire)
        self.assertIsNone(err)
        self.assertEqual(self.encode(obj), wire, "in-memory path")
        return obj


class Schema(SchemaCase):
    def test_messages_nested_messages_and_enums_are_registered_with_their_full_names(self):
        self.assertEqual(sorted(self.sch["msgs"]), ["CurveDataEx", "CurveDataEx.Inner", "pk.Item"])
        self.assertEqual(sorted(self.sch["enums"]), ["CurveDataEx.Mode", "E", "pk.Level"])

    def test_enum_tables_map_names_to_numbers_and_the_first_name_wins_for_a_number(self):
        names, by_num = self.sch["enums"]["E"]
        self.assertEqual(names, {"A": 0, "B": 1, "NEG": -5, "B2": 1})
        self.assertEqual(by_num, {0: "A", 1: "B", -5: "NEG"})

    def test_missing_schema_file_raises_value_error(self):
        with tmp() as d, self.assertRaises(ValueError) as cm:
            cj.load_schema(d / "nope.desc")
        self.assertIn("missing schema file", str(cm.exception))


class Scalars(SchemaCase):
    VALUES = {
        "i32": [0, 1, -1, 2 ** 31 - 1, -2 ** 31],
        "i64": [0, 1, -1, 2 ** 63 - 1, -2 ** 63],
        "u32": [0, 1, 2 ** 32 - 1],
        "u64": [0, 1, 2 ** 63, 2 ** 64 - 1],
        "s32": [0, 1, -1, 2, -2, 2 ** 31 - 1, -2 ** 31],
        "s64": [0, 1, -1, 2 ** 63 - 1, -2 ** 63],
        "fx32": [0, 1, 2 ** 32 - 1],
        "fx64": [0, 1, 2 ** 64 - 1],
        "sfx32": [0, -1, 2 ** 31 - 1, -2 ** 31],
        "sfx64": [0, -1, 2 ** 63 - 1, -2 ** 63],
        "b": [False, True],
        "d": [0.0, -0.0, 1.5, -2.5, 0.1, 5e-324, 1.7976931348623157e308, 1e22, 123456789.125],
        "f": [0.0, -0.0, 1.5, -2.5, 0.25, 3.4028234663852886e38, 1.401298464324817e-45],
        "e": ["A", "B", "NEG"],
    }

    def test_every_scalar_type_decodes_to_its_value_and_round_trips_in_memory_and_through_json_text(self):
        for name, values in self.VALUES.items():
            for v in values:
                with self.subTest(field=name, value=v):
                    wire = one(name, v)
                    obj = self.assert_lossless(wire)
                    self.assertEqual(obj, {name: v})
                    self.assertIs(type(obj[name]), type(v) if name != "f" else cj.F32)
                    self.assertEqual(self.text_round_trip(wire), wire)
                    json.loads(cj.dumps(obj))

    def test_zigzag_decoding_of_sint32_and_sint64(self):
        for name in ("s32", "s64"):
            for raw, want in ((0, 0), (1, -1), (2, 1), (3, -2), (4, 2), (4294967294, 2 ** 31 - 1), (4294967295, -2 ** 31)):
                with self.subTest(field=name, raw=raw):
                    self.assertEqual(self.decode(pb_vint(FN[name], raw)), {name: want})
        self.assertEqual(self.decode(pb_vint(FN["s64"], 2 ** 64 - 1)), {"s64": -2 ** 63})

    def test_negative_int32_and_int64_use_ten_byte_varints(self):
        self.assertEqual(one("i32", -1), pb_key(5, 0) + b"\xff" * 9 + b"\x01")
        self.assertEqual(self.encode({"i32": -1, "i64": -1}), pb_key(3, 0) + b"\xff" * 9 + b"\x01" + pb_key(5, 0) + b"\xff" * 9 + b"\x01")

    def test_negative_zero_keeps_its_sign(self):
        for name in ("f", "d"):
            obj = self.decode(one(name, -0.0))
            self.assertEqual(math.copysign(1.0, obj[name]), -1.0)
        self.assertIn('"d": -0.0', cj.dumps(self.decode(one("d", -0.0))))

    def test_64_bit_integers_are_exact_in_the_json_text(self):
        wire = one("i64", 2 ** 63 - 1) + one("u64", 2 ** 64 - 1) + one("sfx64", -2 ** 63) + one("fx64", 2 ** 64 - 3)
        text = cj.dumps(self.decode(wire))
        for digits in ("9223372036854775807", "18446744073709551615", "-9223372036854775808", "18446744073709551613"):
            self.assertIn(digits, text)
        back = cj.loads(text)
        self.assertEqual((back["i64"], back["u64"], back["sfx64"], back["fx64"]),
                         (2 ** 63 - 1, 2 ** 64 - 1, -2 ** 63, 2 ** 64 - 3))
        self.assertTrue(all(type(back[k]) is int for k in ("i64", "u64", "sfx64", "fx64")))

    def test_float32_is_printed_as_the_shortest_decimal_that_parses_back(self):
        for x, text in ((0.1, "0.1"), (1.5, "1.5"), (0.0, "0.0"), (-0.0, "-0.0"), (3.4028234663852886e38, "3.4028235e+38"),
                        (1.401298464324817e-45, "1e-45")):
            with self.subTest(text=text):
                x32 = struct.unpack("<f", struct.pack("<f", x))[0]
                obj = self.decode(one("f", x32))
                self.assertEqual(obj["f"].text, text)
                self.assertIn('"f": %s' % text, cj.dumps(obj))

    def test_float32_text_is_stable_and_parses_back_to_the_same_bits(self):
        rnd = random.Random(99)
        for i in range(300):
            bits = rnd.getrandbits(32)
            if (bits >> 23) & 0xFF == 0xFF:
                continue
            wire = fixed32(2, bits)
            text = cj.dumps(self.decode(wire))
            self.assertEqual(text, cj.dumps(self.decode(wire)), hex(bits))
            number = float(json.loads(text)["f"])
            self.assertEqual(struct.pack("<f", number), struct.pack("<I", bits), hex(bits))
            self.assertEqual(self.text_round_trip(wire), wire, hex(bits))

    def test_one_decimal_float32_values_print_with_one_decimal(self):
        for i in range(-50, 51):
            x = round(i / 10, 1)
            x32 = struct.unpack("<f", struct.pack("<f", x))[0]
            self.assertEqual(cj.f32_text(x32), repr(x))

    def test_double_text_is_repr(self):
        text = cj.dumps(self.decode(one("d", 0.1) + one("u64", 1)))
        self.assertIn('"d": 0.1', text)
        self.assertIn('"d": %s' % repr(1e22), cj.dumps(self.decode(one("d", 1e22))))

    def test_infinities_and_the_canonical_nan_become_strings_and_round_trip(self):
        cases = (("f", fixed32(2, 0x7F800000), "inf"), ("f", fixed32(2, 0xFF800000), "-inf"), ("f", fixed32(2, 0x7FC00000), "nan"),
                 ("d", fixed64(1, 0x7FF0000000000000), "inf"), ("d", fixed64(1, 0xFFF0000000000000), "-inf"),
                 ("d", fixed64(1, 0x7FF8000000000000), "nan"))
        for name, wire, text in cases:
            with self.subTest(field=name, text=text):
                self.assertEqual(self.assert_lossless(wire), {name: text})
                self.assertEqual(self.text_round_trip(wire), wire)
                self.assertIn('"%s": "%s"' % (name, text), cj.dumps(self.decode(wire)))

    # R2-003 (characterisation, not a wanted property): a NaN other than the canonical quiet NaN does not round trip and the whole file is reported
    def test_non_canonical_nan_decodes_to_nan_but_roundtrip_reports_a_mismatch(self):
        for wire in (fixed32(2, 0xFFC00000), fixed32(2, 0x7FA00000), fixed32(2, 0x7FC00001),
                     fixed64(1, 0xFFF8000000000000), fixed64(1, 0x7FF0000000000001)):
            with self.subTest(wire=wire.hex()):
                obj, err = cj.roundtrip(self.sch, NAME, wire)
                self.assertEqual(list(obj.values()), ["nan"])
                self.assertTrue(err.startswith("round-trip mismatch at byte "), err)
                self.assertNotEqual(self.encode(obj), wire)

    def test_canonical_nan_is_written_as_0x7fc00000_and_the_double_one_as_0x7ff8(self):
        self.assertEqual(self.encode({"f": "nan"}), fixed32(2, 0x7FC00000))
        self.assertEqual(self.encode({"d": "nan"}), fixed64(1, 0x7FF8000000000000))

    def test_strings_round_trip_with_non_ascii_and_json_escapes(self):
        for s in ("", "abc", "é€\U0001F600", 'line\nbreak\t"quote"\\slash', "\x00\x1f"):
            with self.subTest(s=s):
                wire = pb_str(9, s)
                self.assertEqual(self.assert_lossless(wire), {"s": s})
                self.assertEqual(self.text_round_trip(wire), wire)
        self.assertIn('"s": "é€"', cj.dumps({"s": "é€"}))
        self.assertIn(r'"s": "a\nb"', cj.dumps({"s": "a\nb"}))

    def test_bytes_are_hex_prefixed(self):
        for data, text in ((b"", "hex:"), (b"\x00\xff\x7f", "hex:00ff7f")):
            with self.subTest(text=text):
                self.assertEqual(self.assert_lossless(pb_bytes(12, data)), {"by": text})
                self.assertEqual(self.text_round_trip(pb_bytes(12, data)), pb_bytes(12, data))

    def test_enums_decode_to_names_and_unknown_numbers_stay_integers(self):
        for number, want in ((0, "A"), (1, "B"), (-5, "NEG"), (7, 7), (-9, -9), (2 ** 31 - 1, 2 ** 31 - 1), (-2 ** 31, -2 ** 31)):
            with self.subTest(number=number):
                wire = one("e", number)
                self.assertEqual(self.assert_lossless(wire), {"e": want})
                self.assertEqual(self.text_round_trip(wire), wire)

    def test_enum_alias_decodes_to_the_first_name_and_encodes_to_the_same_number(self):
        self.assertEqual(self.decode(one("e", 1)), {"e": "B"})
        self.assertEqual(self.encode({"e": "B2"}), self.encode({"e": "B"}))

    def test_nested_and_package_enums_use_their_own_tables(self):
        wire = pb_vint(21, 1) + pb_vint(31, 3)
        self.assertEqual(self.assert_lossless(wire), {"mode": "M1", "pk_level": "HIGH"})
        self.assertEqual(self.encode({"mode": "M1", "pk_level": "HIGH"}), wire)
        self.assertEqual(self.decode(pb_vint(21, 5)), {"mode": 5})

    def test_enum_given_as_a_number_is_encoded_as_is(self):
        self.assertEqual(self.encode({"e": 7}), one("e", 7))
        self.assertEqual(self.encode({"e": -5}), one("e", "NEG"))

    def test_out_of_range_values_raise_value_error_naming_the_field(self):
        cases = {
            "i32": 2 ** 32, "u32": 2 ** 32, "s32": 2 ** 32, "e": 2 ** 32,
            "b": 2,
        }
        for name, raw in cases.items():
            with self.subTest(field=name):
                with self.assertRaises(ValueError) as cm:
                    self.decode(pb_vint(FN[name], raw))
                self.assertTrue(str(cm.exception).startswith(name + ": "), str(cm.exception))

    def test_invalid_utf8_string_raises(self):
        with self.assertRaises(ValueError) as cm:
            self.decode(pb_bytes(9, b"\xff"))
        self.assertEqual(str(cm.exception), "s: string is not valid UTF-8")

    def test_non_sign_extended_negative_int32_is_decoded_but_reported_as_a_mismatch(self):
        obj, err = cj.roundtrip(self.sch, NAME, pb_vint(5, 2 ** 32 - 1))
        self.assertEqual(obj, {"i32": -1})
        self.assertTrue(err.startswith("round-trip mismatch"), err)

    def test_roundtrip_reports_decode_errors_as_text_and_no_object(self):
        obj, err = cj.roundtrip(self.sch, NAME, pb_vint(5, 2 ** 32))
        self.assertIsNone(obj)
        self.assertEqual(err, "ValueError: i32: int32 value out of range")


class Repeated(SchemaCase):
    VALUES = {
        "r_i32": [1, -1, 2 ** 31 - 1], "r_i64": [-2 ** 63, 0, 2 ** 63 - 1], "r_u32": [0, 7, 2 ** 32 - 1],
        "r_u64": [0, 2 ** 64 - 1, 3], "r_s32": [0, -1, 5, -2 ** 31], "r_s64": [-1, 1, 2 ** 63 - 1],
        "r_fx32": [0, 1, 2 ** 32 - 1], "r_fx64": [2 ** 64 - 1, 0], "r_sfx32": [-1, 1, -2 ** 31],
        "r_sfx64": [-2 ** 63, 5], "r_b": [True, False, True], "r_f": [1.5, -0.25, 0.0], "r_d": [1.5, -0.25, 1e100],
        "r_e": ["A", "NEG", 7],
    }

    def test_unpacked_occurrences_decode_to_a_list_without_packed_marker(self):
        for name, values in self.VALUES.items():
            with self.subTest(field=name):
                wire = unpacked(name, values)
                obj = self.assert_lossless(wire)
                self.assertEqual(obj, {name: values})
                self.assertEqual(self.text_round_trip(wire), wire)

    def test_packed_chunk_decodes_to_the_same_list_and_is_marked_packed(self):
        for name, values in self.VALUES.items():
            with self.subTest(field=name):
                wire = packed(name, values)
                obj = self.assert_lossless(wire)
                self.assertEqual(obj, {name: values, "_packed": [name]})
                self.assertEqual(self.text_round_trip(wire), wire)

    def test_empty_packed_chunk_is_an_empty_list_marked_packed(self):
        wire = packed("r_i32", [])
        self.assertEqual(self.assert_lossless(wire), {"r_i32": [], "_packed": ["r_i32"]})

    def test_packed_marker_decides_the_wire_form_when_encoding(self):
        self.assertEqual(self.encode({"r_i32": [1, 2]}), unpacked("r_i32", [1, 2]))
        self.assertEqual(self.encode({"r_i32": [1, 2], "_packed": ["r_i32"]}), packed("r_i32", [1, 2]))
        self.assertEqual(self.encode({"r_i32": []}), b"")

    def test_repeated_strings_bytes_and_messages_are_never_packed(self):
        wire = pb_str(109, "a") + pb_str(109, "") + pb_str(109, "b") + pb_msg(111, pb_vint(5, 1)) + pb_msg(111) + pb_bytes(112, b"\x00") + pb_bytes(112, b"")
        obj = self.assert_lossless(wire)
        self.assertEqual(obj, {"rs": ["a", "", "b"], "rby": ["hex:00", "hex:"], "rsub": [{"i32": 1}, {}]})

    def test_packed_then_unpacked_raises(self):
        wire = packed("r_i32", [1]) + unpacked("r_i32", [2])
        with self.assertRaises(ValueError) as cm:
            self.decode(wire)
        self.assertEqual(str(cm.exception), "r_i32: repeated field mixes packed and unpacked")

    def test_unpacked_then_packed_raises(self):
        wire = unpacked("r_i32", [2]) + packed("r_i32", [1])
        with self.assertRaises(ValueError) as cm:
            self.decode(wire)
        self.assertEqual(str(cm.exception), "r_i32: repeated field split into several chunks or mixed packed/unpacked")

    def test_two_packed_chunks_raise_and_roundtrip_reports_the_reason(self):
        wire = packed("r_i32", [1]) + packed("r_i32", [2])
        obj, err = cj.roundtrip(self.sch, NAME, wire)
        self.assertIsNone(obj)
        self.assertEqual(err, "ValueError: r_i32: repeated field split into several chunks or mixed packed/unpacked")

    def test_packed_chunk_with_a_bad_length_is_kept_as_unknown_with_a_mismatch_mark(self):
        for name, payload in (("r_fx32", b"\x01\x02\x03"), ("r_d", b"\x00" * 9), ("r_i32", b"\x80")):
            with self.subTest(field=name):
                wire = pb_bytes(FN[name], payload)
                obj = self.assert_lossless(wire)
                self.assertEqual(obj, {"_unknown": [[FN[name], 2, "hex:" + payload.hex(), {"mismatch": name}]]})

    def test_interleaved_occurrences_record_the_wire_order(self):
        wire = unpacked("r_i32", [1]) + one("d", 1.5) + unpacked("r_i32", [2])
        obj = self.assert_lossless(wire)
        self.assertEqual(obj, {"r_i32": [1, 2], "d": 1.5, "_order": ["r_i32", "d", "r_i32"]})
        self.assertEqual(self.text_round_trip(wire), wire)

    def test_a_repeated_field_that_is_not_a_list_is_rejected_when_encoding(self):
        with self.assertRaises(ValueError) as cm:
            self.encode({"r_i32": 5})
        self.assertEqual(str(cm.exception), "r_i32: expected an array")


class Messages(SchemaCase):
    def test_nested_messages_decode_to_nested_objects_and_empty_ones_to_empty_objects(self):
        wire = pb_msg(11, pb_vint(5, 1), pb_msg(11, pb_str(9, "deep"), pb_msg(11))) + pb_msg(20, pb_vint(1, 3), pb_str(2, "y")) + pb_msg(30, pb_vint(1, 4))
        obj = self.assert_lossless(wire)
        self.assertEqual(obj, {"sub": {"i32": 1, "sub": {"s": "deep", "sub": {}}}, "inner": {"x": 3, "y": "y"}, "pk_item": {"n": 4}})
        self.assertEqual(self.text_round_trip(wire), wire)
        self.assertIn('"sub": {}', cj.dumps(obj))

    def test_empty_message_is_an_empty_object(self):
        self.assertEqual(self.decode(b""), {})
        self.assertEqual(self.encode({}), b"")
        self.assertEqual(cj.dumps({}), "{}")

    def test_keys_follow_the_wire_order_and_only_present_fields_appear(self):
        wire = one("s32", 1) + pb_str(9, "x") + one("d", 2.5)
        obj = self.decode(wire)
        self.assertEqual(list(obj), ["s32", "s", "d", "_order"])
        self.assertEqual(obj["_order"], ["s32", "s", "d"])

    def test_dumps_layout(self):
        obj = {"i32": 5, "r_i32": [1, 2, 3], "sub": {}, "rs": ["a", "b"], "rsub": [{"i32": 1}], "r_s32": list(range(12))}
        self.assertEqual(cj.dumps(obj), "\n".join([
            "{", '  "i32": 5,', '  "r_i32": [1, 2, 3],', '  "sub": {},', '  "rs": ["a", "b"],', '  "rsub": [', "    {",
            '      "i32": 1', "    }", "  ],", '  "r_s32": [', "    0, 1, 2, 3, 4, 5, 6, 7, 8, 9,", "    10, 11", "  ]", "}"]))

    def test_dumps_is_deterministic_and_reparses_to_the_same_object(self):
        wire = pb_msg(11, one("s32", -3) + one("f", 0.25)) + unpacked("r_i32", [1, 2]) + pb_str(9, "x")
        obj = self.decode(wire)
        self.assertEqual(cj.dumps(obj), cj.dumps(self.decode(wire)))
        self.assertEqual(json.loads(cj.dumps(obj)), json.loads(json.dumps(obj, ensure_ascii=False)))


class UnknownFieldsAndOrder(SchemaCase):
    def test_unknown_fields_of_every_wire_type_are_kept_in_wire_order(self):
        wire = one("i32", 5) + pb_vint(200, 150) + pb_bytes(201, b"\x01\x02") + fixed64(202, 0x0102030405060708) + fixed32(203, 0xDEADBEEF) + pb_bytes(204, b"")
        obj = self.assert_lossless(wire)
        self.assertEqual(obj, {"i32": 5, "_unknown": [[200, 0, 150], [201, 2, "hex:0102"], [202, 1, 0x0102030405060708],
                                                      [203, 5, 0xDEADBEEF], [204, 2, "hex:"]]})
        self.assertEqual(self.text_round_trip(wire), wire)

    def test_descending_field_numbers_add_an_order_list_naming_unknown_fields_with_a_question_mark(self):
        wire = pb_vint(200, 1) + one("i32", 5) + pb_vint(150, 2) + one("d", 1.5)
        obj = self.assert_lossless(wire)
        self.assertEqual(obj["_order"], ["?200", "i32", "?150", "d"])
        self.assertEqual(obj["_unknown"], [[200, 0, 1], [150, 0, 2]])
        self.assertEqual(self.text_round_trip(wire), wire)

    def test_known_field_with_the_wrong_wire_type_is_kept_as_unknown_with_a_mismatch_mark(self):
        cases = {
            "i32 as fixed32": (fixed32(5, 7), [5, 5, 7, {"mismatch": "i32"}]),
            "f as varint": (pb_vint(2, 7), [2, 0, 7, {"mismatch": "f"}]),
            "s as varint": (pb_vint(9, 7), [9, 0, 7, {"mismatch": "s"}]),
            "d as length-delimited": (pb_bytes(1, b"\x01"), [1, 2, "hex:01", {"mismatch": "d"}]),
            "sub as varint": (pb_vint(11, 1), [11, 0, 1, {"mismatch": "sub"}]),
        }
        for label, (wire, entry) in cases.items():
            with self.subTest(label):
                self.assertEqual(self.assert_lossless(wire), {"_unknown": [entry]})

    def test_same_field_number_with_different_keys_needs_an_order_list(self):
        wire = one("i32", 3) + fixed32(5, 9)
        obj = self.assert_lossless(wire)
        self.assertEqual(obj, {"i32": 3, "_order": ["i32", "?5"], "_unknown": [[5, 5, 9, {"mismatch": "i32"}]]})

    def test_unknown_fields_inside_nested_messages_stay_in_the_nested_object(self):
        wire = pb_msg(11, one("i32", 1), pb_vint(300, 4))
        self.assertEqual(self.assert_lossless(wire), {"sub": {"i32": 1, "_unknown": [[300, 0, 4]]}})

    def test_without_an_order_list_fields_are_written_in_ascending_field_number_stable_for_repeats(self):
        got = self.encode({"i32": 5, "d": 1.5, "r_i32": [3, 1, 2]})
        self.assertEqual(got, one("d", 1.5) + one("i32", 5) + unpacked("r_i32", [3, 1, 2]))

    def test_order_list_reproduces_any_wire_order(self):
        wire = one("i32", 5) + one("d", 1.5)
        self.assertEqual(self.encode({"d": 1.5, "i32": 5, "_order": ["i32", "d"]}), wire)

    def test_order_list_with_wrong_counts_is_rejected(self):
        for obj, text in (({"d": 1.5, "_order": ["d", "d"]}, "_order names 'd' more often than it occurs"),
                          ({"d": 1.5, "i32": 1, "_order": ["d"]}, "_order does not cover every field occurrence"),
                          ({"d": 1.5, "_order": ["nope"]}, "_order names 'nope' more often than it occurs")):
            with self.subTest(text=text):
                with self.assertRaises(ValueError) as cm:
                    self.encode(obj)
                self.assertEqual(str(cm.exception), text)

    def test_malformed_wire_data_raises_value_error(self):
        cases = {
            "group start": pb_key(1, 3),
            "group end": pb_key(1, 4),
            "field number 0": b"\x00\x01",
            "truncated fixed32": pb_key(200, 5) + b"\x01\x02",
            "truncated fixed64": pb_key(200, 1) + b"\x01\x02",
            "length beyond the end": pb_key(200, 2) + b"\x7f" + b"x",
            "truncated varint": pb_key(200, 0) + b"\x80",
            "singular field twice": one("i32", 1) + one("i32", 2),
            "bad bool": pb_vint(8, 2),
        }
        for label, wire in cases.items():
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    self.decode(wire)
                obj, err = cj.roundtrip(self.sch, NAME, wire)
                self.assertIsNone(obj)
                self.assertTrue(err.startswith("ValueError: "), err)


class EncodeErrors(SchemaCase):
    def test_hand_edited_json_with_bad_values_raises_value_error_naming_the_field(self):
        cases = [
            ('{"nope": 1}', "CurveDataEx: unknown field 'nope'"),
            ('[1]', "CurveDataEx: expected an object"),
            ('{"i32": 2147483648}', "i32: integer 2147483648 out of range"),
            ('{"u32": -1}', "u32: integer -1 out of range"),
            ('{"u64": 18446744073709551616}', "u64: integer 18446744073709551616 out of range"),
            ('{"i32": "5"}', "i32: expected an integer, got '5'"),
            ('{"i32": 1.5}', "i32: expected an integer, got '1.5'"),
            ('{"i32": true}', "i32: expected an integer, got True"),
            ('{"b": 1}', "b: expected true/false, got 1"),
            ('{"s": 5}', "s: expected a string, got 5"),
            ('{"by": "00"}', "by: expected \"hex:..\", got '00'"),
            ('{"e": "NOPE"}', "e: unknown enum value 'NOPE'"),
            ('{"f": 1e39}', "f: float out of range: '1e39'"),
            ('{"f": [1]}', "f: expected a number, got [1]"),
            ('{"f": true}', "f: expected a number, got True"),
            ('{"d": null}', "d: expected a number, got None"),
            ('{"r_i32": [1, "x"]}', "r_i32: expected an integer, got 'x'"),
            ('{"sub": {"i32": 2147483648}}', "sub: i32: integer 2147483648 out of range"),
            ('{"sub": 5}', "sub: CurveDataEx: expected an object"),
            ('{"rsub": [{}, {"nope": 1}]}', "rsub: CurveDataEx: unknown field 'nope'"),
        ]
        for text, message in cases:
            with self.subTest(text):
                with self.assertRaises(ValueError) as cm:
                    self.encode(cj.loads(text))
                self.assertEqual(str(cm.exception), message)

    def test_invalid_hex_and_bad_float_text_raise_value_error(self):
        for text in ('{"by": "hex:abc"}', '{"by": "hex:zz"}', '{"f": "abc"}', '{"d": "1.2.3"}'):
            with self.subTest(text):
                with self.assertRaises(ValueError):
                    self.encode(cj.loads(text))

    def test_numbers_and_special_strings_are_accepted_for_float_fields(self):
        self.assertEqual(self.encode(cj.loads('{"d": 1e3}')), one("d", 1000.0))
        self.assertEqual(self.encode(cj.loads('{"f": 2}')), one("f", 2.0))
        self.assertEqual(self.encode(cj.loads('{"f": "inf", "d": "-inf"}')), fixed64(1, 0xFFF0000000000000) + fixed32(2, 0x7F800000))

    def test_roundtrip_reports_truncated_input_as_text(self):
        obj, err = cj.roundtrip(self.sch, NAME, pb_key(200, 5) + b"\x01")
        self.assertIsNone(obj)
        self.assertEqual(err, "ValueError: truncated")


class RandomMessages(SchemaCase):
    @staticmethod
    def canonical(bits, width):
        if width == 32 and (bits >> 23) & 0xFF == 0xFF and bits & 0x7FFFFF:
            return 0x7FC00000
        if width == 64 and (bits >> 52) & 0x7FF == 0x7FF and bits & ((1 << 52) - 1):
            return 0x7FF8000000000000
        return bits

    def rand_body(self, rnd, t):
        if t in (3, 5):
            lim = 31 if t == 5 else 63
            return pb_varint(rnd.choice([0, -1, 1, rnd.randint(-(1 << lim), (1 << lim) - 1)]) & MASK64)
        if t == 4:
            return pb_varint(rnd.getrandbits(64))
        if t == 13:
            return pb_varint(rnd.getrandbits(32))
        if t == 8:
            return pb_varint(rnd.randint(0, 1))
        if t == 14:
            return pb_varint(rnd.choice([0, 1, -5, 9, -9]) & MASK64)
        if t == 17:
            return pb_varint(rnd.getrandbits(32))
        if t == 18:
            return pb_varint(rnd.getrandbits(64))
        if t in (6, 16):
            return struct.pack("<Q", rnd.getrandbits(64))
        if t in (7, 15):
            return struct.pack("<I", rnd.getrandbits(32))
        if t == 1:
            return struct.pack("<Q", self.canonical(rnd.choice([rnd.getrandbits(64), 0, 1 << 63, 0x3FF8000000000000]), 64))
        return struct.pack("<I", self.canonical(rnd.choice([rnd.getrandbits(32), 0, 1 << 31, 0x3FC00000]), 32))

    def chunks(self, rnd, depth=0):
        out = []
        for name, t in SCALARS.items():
            if rnd.random() < .5:
                out.append(pb_key(FN[name], WIRE_TYPE[t]) + self.rand_body(rnd, t))
            if rnd.random() < .4:
                bodies = [self.rand_body(rnd, t) for _ in range(rnd.randint(0, 6))]
                if rnd.random() < .5:
                    out.append(pb_bytes(FN["r_" + name], b"".join(bodies)))
                else:
                    out += [pb_key(FN["r_" + name], WIRE_TYPE[t]) + b for b in bodies]
        if rnd.random() < .5:
            out.append(pb_str(9, "".join(rnd.choice("abcé€ \n") for _ in range(rnd.randint(0, 8)))))
        for _ in range(rnd.randint(0, 2)):
            out.append(pb_str(109, "".join(rnd.choice("xyz") for _ in range(rnd.randint(0, 4)))))
        if rnd.random() < .3:
            out.append(pb_bytes(12, bytes(rnd.getrandbits(8) for _ in range(rnd.randint(0, 5)))))
        if rnd.random() < .3:
            out.append(pb_msg(20, pb_vint(1, rnd.randint(-5, 5)), pb_str(2, "q")))
        if rnd.random() < .2:
            out.append(pb_vint(21, rnd.choice([0, 1, 2])) + pb_vint(31, rnd.choice([0, 3, 4])))
        if depth < 3 and rnd.random() < .5:
            out.append(pb_bytes(11, self.message(rnd, depth + 1)))
        for _ in range(rnd.randint(0, 2) if depth < 3 else 0):
            out.append(pb_bytes(111, self.message(rnd, depth + 1)))
        if rnd.random() < .3:
            for _ in range(rnd.randint(1, 3)):
                fn = rnd.randint(200, 220)
                wt = rnd.choice([0, 1, 2, 5])
                if wt == 0:
                    out.append(pb_vint(fn, rnd.getrandbits(64)))
                elif wt == 1:
                    out.append(fixed64(fn, rnd.getrandbits(64)))
                elif wt == 5:
                    out.append(fixed32(fn, rnd.getrandbits(32)))
                else:
                    out.append(pb_bytes(fn, bytes(rnd.getrandbits(8) for _ in range(rnd.randint(0, 4)))))
        if rnd.random() < .1:
            out.append(fixed32(5, rnd.getrandbits(32)))
        if rnd.random() < .3:
            rnd.shuffle(out)
        return out

    def message(self, rnd, depth=0):
        return b"".join(self.chunks(rnd, depth))

    def test_300_seeded_random_messages_round_trip_through_text_and_in_memory(self):
        rnd = random.Random(20240607)
        seen = set()
        for i in range(300):
            wire = self.message(rnd)
            obj, err = cj.roundtrip(self.sch, NAME, wire)
            self.assertIsNone(err, "message %d" % i)
            self.assertEqual(self.encode(obj), wire, "message %d in memory" % i)
            self.collect_keys(obj, seen)
        self.assertLessEqual({"_order", "_packed", "_unknown", "sub", "rsub", "r_f", "r_d", "inner"}, seen)

    def collect_keys(self, obj, seen):
        if isinstance(obj, dict):
            seen.update(obj)
            for v in obj.values():
                self.collect_keys(v, seen)
        elif isinstance(obj, list):
            for v in obj:
                self.collect_keys(v, seen)


class Types(unittest.TestCase):
    @staticmethod
    def literal_keys():
        tree = ast.parse(pathlib.Path(cj.__file__).read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "TYPES" for t in node.targets):
                return [k.value for k in node.value.keys]
        raise AssertionError("TYPES literal not found")

    def test_source_literal_has_no_duplicate_extensions(self):
        keys = self.literal_keys()
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(sorted(keys), sorted(cj.TYPES))

    def test_extensions_are_plain_lowercase_names_and_messages_are_identifiers(self):
        self.assertGreater(len(cj.TYPES), 20)
        for ext, name in cj.TYPES.items():
            with self.subTest(ext=ext):
                self.assertIsInstance(ext, str)
                self.assertIsInstance(name, str)
                self.assertRegex(ext, r"^[a-z0-9_]+$")
                self.assertRegex(name, r"^[A-Za-z_][A-Za-z0-9_]*$")

    def test_message_for_ignores_case_and_a_leading_dot_in_the_suffix(self):
        for path in ("car.curve", "dir/CAR.CURVE", "a\\b\\Wing.Wing"):
            self.assertEqual(cj.message_for(path), cj.TYPES[path.lower().rsplit(".", 1)[1]])

    def test_message_for_rejects_unmapped_and_missing_extensions(self):
        for path in ("file.xyz", "noextension", "x.", ".hidden"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError) as cm:
                    cj.message_for(path)
                self.assertIn("no message type for extension", str(cm.exception))


GOOD = (one("i32", 5) + pb_str(9, "hi") + pb_msg(11, one("i32", 7)) + packed("r_i32", [1, 2, 3]) + pb_vint(200, 9))
NAN_FILE = fixed32(2, 0xFFC00000)
CORRUPT = b"\x0a\x7fxx"


class Result:
    def __init__(self, cp):
        self.returncode = cp.returncode
        self.stdout_bytes = cp.stdout
        self.stdout = cp.stdout.decode("utf-8", "replace")
        self.stderr = cp.stderr.decode("utf-8", "replace")


class Cli(unittest.TestCase):
    """car_json.py runs from a copy of the tools folder next to a temporary schemas/acevo.desc (the tool looks for ../schemas)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tmp()
        base = cls._tmp.__enter__()
        cls.install, cls.bare, cls.work = base / "install", base / "bare", base / "work"
        for root in (cls.install, cls.bare):
            (root / "tools").mkdir(parents=True)
            for n in ("car_json.py", "extract_protos.py", "kspkg.py"):
                shutil.copy(TOOLS / n, root / "tools" / n)
        (cls.install / "schemas").mkdir()
        (cls.install / "schemas" / "acevo.desc").write_bytes(schema_bytes())
        (cls.work / "sub").mkdir(parents=True)
        (cls.work / "good.curve").write_bytes(GOOD)
        (cls.work / "sub" / "more.curve").write_bytes(GOOD)
        (cls.work / "nan.curve").write_bytes(NAN_FILE)
        (cls.work / "bad.curve").write_bytes(CORRUPT)
        (cls.work / "skip.txt").write_bytes(b"x")
        (cls.work / "noext").write_bytes(b"x")
        sch = cj.load_schema(cls.install / "schemas" / "acevo.desc")
        cls.good_text = cj.dumps(cj.decode_msg(sch, NAME, GOOD)) + "\n"

    @classmethod
    def tearDownClass(cls):
        cls._tmp.__exit__(None, None, None)

    def run_cli(self, *args, root=None):
        root = root or self.install
        cp = subprocess.run([sys.executable, "-B", "-I", str(root / "tools" / "car_json.py"), *map(str, args)],
                            capture_output=True, cwd=str(self.work))
        return Result(cp)

    def scratch(self):
        d = self.work / "scratch"
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return d

    def test_decode_prints_the_json_to_stdout(self):
        r = self.run_cli("decode", self.work / "good.curve")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(r.stdout, self.good_text)
        self.assertEqual(json.loads(r.stdout)["_unknown"], [[200, 0, 9]])
        self.assertFalse(r.stdout_bytes.startswith(b"\xef\xbb\xbf"))

    def test_decode_writes_the_json_to_the_out_file_and_prints_nothing(self):
        out = self.scratch() / "good.json"
        r = self.run_cli("decode", self.work / "good.curve", out)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        self.assertEqual(out.read_bytes(), self.good_text.encode("utf-8"))

    def test_decode_then_encode_reproduces_the_original_bytes(self):
        d = self.scratch()
        self.assertEqual(self.run_cli("decode", self.work / "good.curve", d / "g.json").returncode, 0)
        r = self.run_cli("encode", d / "g.json", d / "back.curve")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        self.assertEqual((d / "back.curve").read_bytes(), GOOD)

    def test_encode_accepts_a_json_file_with_a_utf8_bom(self):
        d = self.scratch()
        (d / "bom.json").write_bytes(b"\xef\xbb\xbf" + self.good_text.encode("utf-8"))
        r = self.run_cli("encode", d / "bom.json", d / "back.curve")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((d / "back.curve").read_bytes(), GOOD)

    def test_extension_is_matched_case_insensitively(self):
        d = self.scratch()
        (d / "UPPER.CURVE").write_bytes(GOOD)
        r = self.run_cli("decode", d / "UPPER.CURVE")
        self.assertEqual((r.returncode, r.stdout), (0, self.good_text))

    def test_decode_of_an_unmapped_extension_fails_with_error_on_stderr(self):
        r = self.run_cli("decode", self.work / "skip.txt")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "")
        self.assertTrue(r.stderr.startswith("error: no message type for extension .txt"), r.stderr)

    def test_decode_of_a_missing_file_prints_error_and_exits_1(self):
        r = self.run_cli("decode", self.work / "missing.curve")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("error:"), r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_decode_of_a_corrupt_file_prints_error_exits_1_and_writes_nothing(self):
        out = self.scratch() / "out.json"
        r = self.run_cli("decode", self.work / "bad.curve", out)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr.strip(), "error: ValueError: truncated")
        self.assertFalse(out.exists())

    def test_without_a_schema_file_the_tool_reports_it_and_exits_1(self):
        r = self.run_cli("decode", self.work / "good.curve", root=self.bare)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("error: missing schema file "), r.stderr)

    def test_encode_of_an_invalid_value_prints_error_exits_1_and_writes_nothing(self):
        d = self.scratch()
        (d / "in.json").write_text('{"i32": 2147483648}', encoding="utf-8")
        r = self.run_cli("encode", d / "in.json", d / "out.curve")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr.strip(), "error: i32: integer 2147483648 out of range")
        self.assertFalse((d / "out.curve").exists())

    def test_encode_of_malformed_json_prints_error_exits_1_and_writes_nothing(self):
        d = self.scratch()
        (d / "in.json").write_text('{"i32": ', encoding="utf-8")
        r = self.run_cli("encode", d / "in.json", d / "out.curve")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("error:"), r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertFalse((d / "out.curve").exists())

    def test_encode_to_an_unmapped_extension_prints_error_and_writes_nothing(self):
        d = self.scratch()
        (d / "in.json").write_text("{}", encoding="utf-8")
        r = self.run_cli("encode", d / "in.json", d / "out.xyz")
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(r.stderr.startswith("error: no message type for extension .xyz"), r.stderr)
        self.assertFalse((d / "out.xyz").exists())

    def test_check_of_good_files_only_reports_them_all_ok(self):
        d = self.scratch()
        (d / "a.curve").write_bytes(GOOD)
        (d / "b.curve").write_bytes(b"")
        r = self.run_cli("check", d)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0].split(), ["extension", "message", "files", "ok", "failed", "unknown", "mismatch"])
        self.assertEqual(lines[1].split(), [".curve", NAME, "2", "2", "0", "1", "0"])
        self.assertEqual(lines[2:], ["total: ok 2, failed 0"])

    def test_check_walks_subfolders_lists_failures_and_the_skipped_extensions(self):
        r = self.run_cli("check", self.work)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[1].split(), [".curve", NAME, "4", "2", "2", "2", "0"])
        failed = [l for l in lines if l.startswith("FAILED ")]
        self.assertEqual(sorted(failed), sorted(["FAILED %s" % (self.work / "bad.curve"), "FAILED %s" % (self.work / "nan.curve")]))
        self.assertIn("  ValueError: truncated", lines)
        self.assertIn("  round-trip mismatch at byte 4 (encoded 5 bytes, original 5)", lines)
        self.assertEqual(lines[-2:], ["total: ok 2, failed 2", "skipped (no mapped message): (none) x1, .txt x1"])

    def test_types_lists_every_mapped_extension_sorted(self):
        r = self.run_cli("types")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(r.stdout.splitlines(), [".%-20s %s" % (e, n) for e, n in sorted(cj.TYPES.items())])
        self.assertIn(".aicardata            AiCarData", r.stdout)

    # R2-001: a file that does not round-trip must not be decoded, today a warning on stderr, rc 0 and a written file
    @unittest.expectedFailure
    def test_decode_of_a_file_that_does_not_round_trip_prints_error_and_exits_1(self):
        r = self.run_cli("decode", self.work / "nan.curve", self.scratch() / "nan.json")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertTrue(r.stderr.startswith("error: round-trip mismatch"), r.stderr)

    # R2-001: and no output file may be left behind
    @unittest.expectedFailure
    def test_decode_of_a_file_that_does_not_round_trip_writes_no_output_file(self):
        out = self.scratch() / "nan.json"
        self.run_cli("decode", self.work / "nan.curve", out)
        self.assertFalse(out.exists(), "decode wrote a JSON that does not encode back to the original")

    # R2-001: nor may it print the JSON to stdout
    @unittest.expectedFailure
    def test_decode_of_a_file_that_does_not_round_trip_prints_no_json_on_stdout(self):
        r = self.run_cli("decode", self.work / "nan.curve")
        self.assertEqual(r.stdout, "")

    def assert_encode_error(self, json_text):
        d = self.scratch()
        (d / "bad.json").write_text(json_text, encoding="utf-8")
        r = self.run_cli("encode", d / "bad.json", d / "out.curve")
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertTrue(r.stderr.startswith("error:"), r.stderr)
        self.assertFalse((d / "out.curve").exists())

    # R2-002: reserved keys and huge numbers in hand-edited JSON end in a traceback, wanted is "error: ..." and rc 1
    @unittest.expectedFailure
    def test_encode_with_packed_not_a_list_is_an_error(self):
        self.assert_encode_error('{"r_i32": [1], "_packed": 5}')

    # R2-002
    @unittest.expectedFailure
    def test_encode_with_unknown_not_a_list_is_an_error(self):
        self.assert_encode_error('{"_unknown": 5}')

    # R2-002
    @unittest.expectedFailure
    def test_encode_with_an_unknown_entry_that_is_not_a_list_is_an_error(self):
        self.assert_encode_error('{"_unknown": [5]}')

    # R2-002
    @unittest.expectedFailure
    def test_encode_with_a_string_value_for_an_unknown_varint_is_an_error(self):
        self.assert_encode_error('{"_unknown": [[5, 0, "abc"]]}')

    # R2-002
    @unittest.expectedFailure
    def test_encode_with_a_string_value_for_an_unknown_fixed64_is_an_error(self):
        self.assert_encode_error('{"_unknown": [[5, 1, "abc"]]}')

    # R2-002
    @unittest.expectedFailure
    def test_encode_with_a_number_value_for_an_unknown_length_delimited_field_is_an_error(self):
        self.assert_encode_error('{"_unknown": [[5, 2, 7]]}')

    # R2-002
    @unittest.expectedFailure
    def test_encode_with_order_not_a_list_is_an_error(self):
        self.assert_encode_error('{"d": 1.0, "_order": 5}')

    # R2-002
    @unittest.expectedFailure
    def test_encode_with_an_unhashable_order_entry_is_an_error(self):
        self.assert_encode_error('{"d": 1.0, "_order": [["d"]]}')

    # R2-002
    @unittest.expectedFailure
    def test_encode_with_an_integer_too_large_for_a_double_is_an_error(self):
        self.assert_encode_error('{"d": 1%s}' % ("0" * 400))


class CommandLine(unittest.TestCase):
    # D5: no arguments is a usage error (rc 2, usage block on stdout), today the usage goes to stderr with rc 1
    @unittest.expectedFailure
    def test_no_arguments_exits_2_with_usage_on_stdout(self):
        r = run_tool("car_json.py")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout.strip(), usage_block())

    # D5: an unknown command is a usage error, today stderr and rc 1
    @unittest.expectedFailure
    def test_unknown_command_exits_2_with_usage_on_stdout(self):
        r = run_tool("car_json.py", "frobnicate")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout.strip(), usage_block())

    # D5: decode without a file is a usage error, today stderr and rc 1
    @unittest.expectedFailure
    def test_decode_without_operand_exits_2_with_usage_on_stdout(self):
        r = run_tool("car_json.py", "decode")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout.strip(), usage_block())

    # D5: encode with one operand is a usage error, today stderr and rc 1
    @unittest.expectedFailure
    def test_encode_with_one_operand_exits_2_with_usage_on_stdout(self):
        r = run_tool("car_json.py", "encode", "in.json")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout.strip(), usage_block())

    # D5: check without a folder is a usage error, today stderr and rc 1
    @unittest.expectedFailure
    def test_check_without_operand_exits_2_with_usage_on_stdout(self):
        r = run_tool("car_json.py", "check")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout.strip(), usage_block())

    def test_today_the_usage_text_is_printed_and_the_exit_is_not_0(self):
        r = run_tool("car_json.py")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(usage_block(), r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
