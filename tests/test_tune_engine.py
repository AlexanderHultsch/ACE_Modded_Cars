"""Tests for the engine of tools/tune.py without the game: path parser, field access, coerce, state files, resolving defaults on a stubbed car, apply orchestration, car list, work folder, CLI.

Everything that decodes car files is stubbed (support.FakeCar replaces tune.load_msg / save_msg with in-memory messages, clone_car.build and kspkg.cmd_pack are stubbed for apply); the committed tuner/*.json are read only where a test says so.
"""
import builtins
import contextlib
import io
import json
import os
import shutil
import sys
import threading
import unittest
from unittest import mock

from support import FakeCar, mini_catalogue, mini_setting, run_tool, tmp

import car_json
import clone_car
import kspkg
import tune

REAL_LOAD_CATALOGUE = tune.load_catalogue
REAL_RENAME = os.rename
USAGE = tune.__doc__.split("\n\n")[1]
GAME_SHARED = "content\\cars\\common_phsx\\"


def limiter(**kw):
    return mini_setting("limiter", type="int", min=3000, max=12000, targets=[("@engine", "limiter"), ("@car", "engine.limiter", True)], **kw)


def suffix():
    return mini_setting("name_suffix", kind="meta", type="string", default="_MY", handler="name_suffix")


def variant():
    return mini_setting("variant_name", kind="meta", type="string", default_template="{stock_variant_name}", handler="variant_name")


def metas():
    return [suffix(), variant()]


def not_chained(test, exc):
    test.assertTrue(exc.__context__ is None or exc.__suppress_context__, "implicit exception chain: %r" % (exc.__context__,))


class Base(unittest.TestCase):
    def setUp(self):
        cm = tmp()
        self.d = cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        self.work = str(self.d / "work")

    def patch(self, target, name, value):
        p = mock.patch.object(target, name, value)
        p.start()
        self.addCleanup(p.stop)
        return value

    def cars(self, *tested, default=None):
        tested = tested or (("ks_x", "Car X"),)
        data = {"default": default or tested[0][0], "cars": [{"id": i, "label": label} for i, label in tested]}
        self.patch(tune, "load_cars", lambda path=None: data)
        return data

    def write(self, path, data, binary=False):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8"})) as f:
            f.write(data if isinstance(data, (str, bytes)) else json.dumps(data))
        return path

    def run_main(self, *argv):
        out, err, code = io.StringIO(), io.StringIO(), None
        with mock.patch.object(sys, "argv", ["tune.py", *argv]), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                tune.main()
            except SystemExit as e:
                code = e.code
        if isinstance(code, str):
            err.write(code + "\n")
            code = 1
        return code or 0, out.getvalue(), err.getvalue()


class CarCase(Base):
    """A stubbed extracted car ks_x with engine, setup, curve and preset; self.car / self.engine / self.setup are the live stub objects."""

    def setUp(self):
        super().setUp()
        self.fc = FakeCar(self.work).install(self)
        gp = self.fc.game_path
        self.car = {"engine_path": gp("data/engine.carengine"), "stock_setup": gp("data/setup.carsetup"),
                    "engine": {"limiter": 7000.0, "minimum": 900}, "frontTyreCompounds": [GAME_SHARED + "tyres\\road\\a.tyre"],
                    "rearTyreCompounds": [GAME_SHARED + "tyres\\road\\b.tyre"],
                    "performance_modes": [{"electronics_settings": {"tc1": 3, "esc": 2}}, {"electronics_settings": {"tc1": 2, "tc2": 1}}]}
        self.engine = {"limiter": 7000.0, "minimum": 800, "powerCurve": gp("data/power.curve"), "turbos_to_load": []}
        self.setup = {"alignments": [{"camber": -1.5, "pressure": 30.0}, {"camber": -1.25, "pressure": 30.0}],
                      "electronics": {"tc1": 2}}
        self.fc.add("data/x.car", self.car)
        self.fc.add("data/engine.carengine", self.engine)
        self.fc.add("data/setup.carsetup", self.setup)
        self.fc.add("data/power.curve", {"points": [{"value": 1.0}, {"value": 3.0}, {"x": 5}]})
        self.fc.add("presets/p.mechanicalcarpreset", {"brand": "Brand", "description": "Name Preset Base",
                                                      "car_specs": {"items": [{"key": "KEY_POWER", "value": 380.0}, {"key": 7, "value": 9}]}})
        self.fc.add_shared("tyres/road/a.tyre", {"modelData": {"Dy0": 1.2}, "thermalData": {"thermalPerformanceCurve": GAME_SHARED + "tyres\\road\\tcurve_road.curve"}})
        self.fc.add_shared("tyres/road/b.tyre", {"modelData": {"Dy0": 1.1}})

    def stock_info(self, **kw):
        info = {"car_id": "ks_x", "display_name": "Car X", "brand": "Brand", "year": 1999, "property_1": "P1", "property_2": "P2",
                "property_3": "P3", "variant_name": "Base"}
        info.update(kw)
        return self.write(tune.stock_info_path(self.work, "ks_x"), info)

    def rows(self, *settings, **kw):
        return {r["id"]: r for r in tune.resolve_defaults(self.work, "ks_x", mini_catalogue(*settings), hidden=kw.pop("hidden", True), **kw)}

    def row(self, setting, **kw):
        return self.rows(setting, **kw)[setting["id"]]


# --------------------------------------------------------------------------------------------- path parser and field access
class TestPathParser(unittest.TestCase):
    def test_plain_dotted_path(self):
        self.assertEqual(tune.parse_path("a.b_1.C"), [("key", "a"), ("key", "b_1"), ("key", "C")])

    def test_index_selector_find_selector_and_wildcard(self):
        self.assertEqual(tune.parse_path("gears[1].ratio"), [("key", "gears"), ("idx", 1), ("key", "ratio")])
        self.assertEqual(tune.parse_path("m[*].x"), [("key", "m"), ("all",), ("key", "x")])
        self.assertEqual(tune.parse_path("items[key=KEY_POWER].value"), [("key", "items"), ("find", "key", "KEY_POWER"), ("key", "value")])

    def test_several_selectors_in_a_row(self):
        self.assertEqual(tune.parse_path("a[0][2]"), [("key", "a"), ("idx", 0), ("idx", 2)])

    def test_find_value_may_hold_dots_and_equal_signs(self):
        self.assertEqual(tune.parse_path("a[k=x.y=z].v"), [("key", "a"), ("find", "k", "x.y=z"), ("key", "v")])

    def test_selector_on_the_last_step(self):
        self.assertEqual(tune.parse_path("a[3]"), [("key", "a"), ("idx", 3)])

    def test_bad_paths_are_refused(self):
        for path in ("", "1a", "a..b", "a.", ".a", "a[", "a[x]", "a[]", "a b", "a-b", "a[0]b", "a[0"):
            with self.subTest(path):
                with self.assertRaises(ValueError):
                    tune.parse_path(path)

    def test_bad_selector_message_names_selector_and_path(self):
        with self.assertRaisesRegex(ValueError, r"bad selector \[x\] in field path 'a\[x\]'"):
            tune.parse_path("a[x]")


class TestFieldAccess(unittest.TestCase):
    def obj(self):
        return {"a": {"b": 1.5}, "xs": [{"k": 1, "v": "one"}, {"k": car_json_f32("2.5"), "v": "two"}, {"k": True, "v": "yes"}],
                "n": [[1, 2], [3]], "empty": []}

    def test_get_value_reads_nested_fields_indexes_and_selectors(self):
        o = self.obj()
        self.assertEqual(tune.get_value(o, "a.b"), (1.5, False))
        self.assertEqual(tune.get_value(o, "xs[1].v"), ("two", False))
        self.assertEqual(tune.get_value(o, "n[0][1]"), (2, False))
        self.assertEqual(tune.get_value(o, "xs[k=1].v"), ("one", False))

    def test_find_compares_the_text_of_numbers_floats_and_bools(self):
        o = self.obj()
        self.assertEqual(tune.get_value(o, "xs[k=2.5].v")[0], "two")
        self.assertEqual(tune.get_value(o, "xs[k=true].v")[0], "yes")

    def test_find_takes_the_first_match(self):
        o = {"xs": [{"k": 1, "v": "first"}, {"k": 1, "v": "second"}]}
        self.assertEqual(tune.get_value(o, "xs[k=1].v")[0], "first")

    def test_find_skips_elements_without_the_key_and_non_objects(self):
        o = {"xs": [5, {"other": 1}, {"k": 3, "v": "hit"}]}
        self.assertEqual(tune.get_value(o, "xs[k=3].v")[0], "hit")

    def test_find_without_a_match_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "no list element with k=9"):
            tune.get_value(self.obj(), "xs[k=9].v")

    def test_missing_last_field_reads_absent(self):
        self.assertEqual(tune.get_value(self.obj(), "a.zzz"), (None, True))

    def test_missing_object_on_the_way_is_an_error_unless_missing_ok(self):
        with self.assertRaisesRegex(ValueError, "missing field 'q'"):
            tune.get_value(self.obj(), "q.r")
        self.assertEqual(tune.get_value(self.obj(), "q.r", missing_ok=True), (None, True))

    def test_index_out_of_range_and_not_a_list(self):
        with self.assertRaisesRegex(ValueError, "list has no element 5"):
            tune.get_value(self.obj(), "xs[5].v")
        with self.assertRaisesRegex(ValueError, "expected a list before"):
            tune.get_value(self.obj(), "a[0]")

    def test_field_inside_a_non_object_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "is not inside an object"):
            tune.get_value(self.obj(), "a.b.c")

    def test_wildcard_must_be_expanded_first(self):
        with self.assertRaisesRegex(ValueError, r"\[\*\] must be expanded"):
            tune.get_value(self.obj(), "xs[*].v")

    def test_expand_path_gives_one_path_per_element(self):
        self.assertEqual(tune.expand_path(self.obj(), "xs[*].v"), ["xs[0].v", "xs[1].v", "xs[2].v"])
        self.assertEqual(tune.expand_path(self.obj(), "n[*][*]"), ["n[0][0]", "n[0][1]", "n[1][0]"])
        self.assertEqual(tune.expand_path(self.obj(), "a.b"), ["a.b"])

    def test_expand_path_of_empty_or_absent_list_is_empty(self):
        self.assertEqual(tune.expand_path(self.obj(), "empty[*].v"), [])
        self.assertEqual(tune.expand_path(self.obj(), "nolist[*].v"), [])

    def test_expand_path_needs_a_list(self):
        with self.assertRaisesRegex(ValueError, "needs a list at a"):
            tune.expand_path(self.obj(), "a[*].b")

    def test_expand_path_missing_object_on_the_way(self):
        with self.assertRaisesRegex(ValueError, "missing field 'q'"):
            tune.expand_path(self.obj(), "q.xs[*].v")
        self.assertEqual(tune.expand_path(self.obj(), "q.xs[*].v", missing_ok=True), [])

    def test_put_value_replaces_an_existing_field_and_list_element(self):
        o = self.obj()
        tune.put_value(o, "a.b", 9)
        tune.put_value(o, "xs[1].v", "changed")
        tune.put_value(o, "n[0][1]", 20)
        self.assertEqual((o["a"]["b"], o["xs"][1]["v"], o["n"][0]), (9, "changed", [1, 20]))

    def test_put_value_adds_a_missing_last_field_and_keeps_the_key_order_list(self):
        o = {"a": {"_order": ["b"], "b": 1}}
        tune.put_value(o, "a.c", 2)
        self.assertEqual(o["a"]["_order"], ["b", "c"])
        self.assertEqual(o["a"]["c"], 2)

    def test_put_value_creates_missing_objects_on_the_way(self):
        o = {"_order": []}
        tune.put_value(o, "x.y.z", 3)
        self.assertEqual(o["x"]["y"]["z"], 3)
        self.assertEqual(o["_order"], ["x"])

    def test_put_value_does_not_create_list_elements(self):
        with self.assertRaisesRegex(ValueError, "list has no element 4"):
            tune.put_value({"xs": [1]}, "xs[4]", 1)

    def test_locate_returns_container_and_key(self):
        o = self.obj()
        container, key = tune.locate(o, "xs[0].v")
        self.assertIs(container, o["xs"][0])
        self.assertEqual(key, "v")
        container, key = tune.locate(o, "xs[2]")
        self.assertIs(container, o["xs"])
        self.assertEqual(key, 2)

    def test_locate_missing_object_on_the_way(self):
        self.assertEqual(tune.locate({}, "a.b", missing_ok=True), (None, None))
        with self.assertRaisesRegex(ValueError, "missing field 'a'"):
            tune.locate({}, "a.b")

    def test_text_of(self):
        self.assertEqual([tune.text_of(v) for v in (True, False, 3, "s", car_json_f32("1.5"))], ["true", "false", "3", "s", "1.5"])


def car_json_f32(text):
    return tune.to_f32(float(text))


# --------------------------------------------------------------------------------------------- values
class TestCoerce(unittest.TestCase):
    def test_bool_words_numbers_and_case(self):
        s = mini_setting("b", kind="flag", type="bool", value=0, targets=[("@car", "a")])
        for v in (True, "true", "TRUE", " Yes ", "1", 1, "on", "ON"):
            self.assertIs(tune.coerce(s, v), True, v)
        for v in (False, "false", "No", "0", 0, "off", " OFF "):
            self.assertIs(tune.coerce(s, v), False, v)

    def test_bool_refuses_everything_else(self):
        s = mini_setting("b", kind="flag", type="bool", value=0, targets=[("@car", "a")])
        for v in ("maybe", "", 2, 1.0, None, [], "tru"):
            with self.subTest(v):
                with self.assertRaisesRegex(ValueError, "b expects true or false"):
                    tune.coerce(s, v)

    def test_int_from_text_and_number(self):
        s = mini_setting("i", type="int")
        self.assertEqual([tune.coerce(s, v) for v in ("5", "+5", " -7 ", 5, "007")], [5, 5, -7, 5, 7])

    def test_int_refuses_floats_and_junk(self):
        s = mini_setting("i", type="int")
        for v in ("5.0", 5.0, "1e3", "0x10", "", "abc", None, True, "5 5"):
            with self.subTest(v):
                with self.assertRaisesRegex(ValueError, "i expects an integer"):
                    tune.coerce(s, v)

    def test_float_from_text_and_number(self):
        s = mini_setting("f")
        self.assertEqual([tune.coerce(s, v) for v in ("1.5", " 2 ", 3, 4.25, "-1e2")], [1.5, 2.0, 3.0, 4.25, -100.0])
        self.assertIs(type(tune.coerce(s, 3)), float)

    def test_float_refuses_junk_and_non_finite(self):
        s = mini_setting("f")
        for v in ("abc", "", None, True, [1], "nan", "inf", "-inf", float("nan"), "1e999"):
            with self.subTest(v):
                with self.assertRaises(ValueError) as cm:
                    tune.coerce(s, v)
                self.assertIn("f expects", str(cm.exception))

    def test_string_needs_text_without_control_characters(self):
        s = mini_setting("t", type="string")
        self.assertEqual(tune.coerce(s, " a b "), " a b ")
        for v in ("", "a\nb", "a\x00", 5, None):
            with self.subTest(v):
                with self.assertRaisesRegex(ValueError, "t expects non-empty text"):
                    tune.coerce(s, v)

    def test_enum_must_be_one_of_the_choices(self):
        s = mini_setting("e", type="enum", choices=["a", "b"])
        self.assertEqual(tune.coerce(s, "b"), "b")
        with self.assertRaisesRegex(ValueError, "e must be one of: a, b"):
            tune.coerce(s, "c")

    def test_enum_choice_check_is_case_sensitive(self):
        with self.assertRaises(ValueError):
            tune.coerce(mini_setting("e", type="enum", choices=["a"]), "A")

    def test_name_suffix_is_one_to_thirty_characters_and_not_trimmed(self):
        s = suffix()
        self.assertEqual(tune.coerce(s, " _X "), " _X ")
        self.assertEqual(tune.coerce(s, "x" * tune.NAME_SUFFIX_MAX), "x" * 30)
        for v in ("", "x" * 31, "a\tb", "\x1f", 3, None):
            with self.subTest(repr(v)):
                with self.assertRaisesRegex(ValueError, "name_suffix expects 1 to 30 characters"):
                    tune.coerce(s, v)

    def test_to_f32_rounds_to_single_precision_and_keeps_the_short_text(self):
        v = tune.to_f32(1.1)
        self.assertIsInstance(v, car_json.F32)
        self.assertEqual((v.text, tune.plain(v)), ("1.1", 1.1))
        self.assertEqual(tune.to_f32(16777217.0), 16777216.0)

    def test_to_f32_out_of_range(self):
        with self.assertRaisesRegex(ValueError, "float out of range"):
            tune.to_f32(1e300)

    def test_plain_unwraps_f32_only(self):
        self.assertIs(type(tune.plain(tune.to_f32(2.5))), float)
        self.assertEqual([tune.plain(v) for v in (3, "x", True, None)], [3, "x", True, None])

    def test_same_compares_floats_with_a_relative_tolerance(self):
        f, i = mini_setting("f"), mini_setting("i", type="int")
        self.assertTrue(tune.same(f, 1.0, 1.000001))
        self.assertTrue(tune.same(f, 1e6, 1e6 + 1))
        self.assertFalse(tune.same(f, 1.0, 1.001))
        self.assertTrue(tune.same(i, 3, 3))
        self.assertFalse(tune.same(i, 3, 4))
        self.assertFalse(tune.same(f, None, 1.0))
        self.assertTrue(tune.same(f, None, None))

    def test_fmt(self):
        self.assertEqual([tune.fmt(v) for v in (None, True, False, 3, 1.5, "t", 0.1)], ["-", "true", "false", "3", "1.5", "t", "0.1"])

    def test_zero(self):
        self.assertEqual([tune.zero(mini_setting("a", type=t)) for t in ("int", "float", "string")], [0, 0.0, ""])
        self.assertIs(tune.zero(mini_setting("a", kind="flag", type="bool", value=0, targets=[])), False)
        self.assertEqual(tune.zero(mini_setting("a", type="enum", choices=["x", "y"])), "x")
        self.assertEqual(tune.zero(mini_setting("a", type="enum")), "")

    def test_range_warning(self):
        s = mini_setting("lim", type="int", min=10, max=20)
        self.assertIsNone(tune.range_warning(s, 10))
        self.assertIsNone(tune.range_warning(s, 20))
        self.assertEqual(tune.range_warning(s, 9), "lim=9 is outside the suggested range 10..20")
        self.assertEqual(tune.range_warning(s, 21), "lim=21 is outside the suggested range 10..20")

    def test_range_warning_with_one_bound_or_none_and_for_other_types(self):
        self.assertIsNone(tune.range_warning(mini_setting("a"), 1e9))
        self.assertEqual(tune.range_warning(mini_setting("a", min=1.5), 1.0), "a=1.0 is outside the suggested range 1.5..-")
        self.assertIsNone(tune.range_warning(mini_setting("a", min=1.5), 99.0))
        self.assertIsNone(tune.range_warning(mini_setting("t", type="string", min=1), "x"))


# --------------------------------------------------------------------------------------------- json files and state
class TestJsonFiles(Base):
    def test_save_json_layout(self):
        path = os.path.join(self.work, "sub", "f.json")
        tune.save_json(path, {"b": 1, "a": ["é", 2.5]})
        with open(path, "rb") as f:
            self.assertEqual(f.read(), b'{\n  "b": 1,\n  "a": [\n    "\xc3\xa9",\n    2.5\n  ]\n}\n')

    def test_save_json_replaces_the_old_content(self):
        path = os.path.join(self.work, "f.json")
        tune.save_json(path, {"a": 1})
        tune.save_json(path, {"b": 2})
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"b": 2})

    def test_save_json_keeps_the_old_file_when_serialising_fails(self):
        path = os.path.join(self.work, "f.json")
        tune.save_json(path, {"a": 1})
        with self.assertRaises(Exception):
            tune.save_json(path, {"a": object()})
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"a": 1})

    def test_load_state_missing_file_is_empty(self):
        self.assertEqual(tune.load_state(self.work, "ks_x"), {})

    def test_save_and_load_state_round_trip(self):
        tune.save_state(self.work, "ks_x", {"a": 1, "b": "x", "c": True, "d": 1.5})
        self.assertEqual(tune.load_state(self.work, "ks_x"), {"a": 1, "b": "x", "c": True, "d": 1.5})
        self.assertTrue(os.path.isfile(os.path.join(self.work, "ks_x", "tune_state.json")))

    def test_states_are_per_car(self):
        tune.save_state(self.work, "ks_x", {"a": 1})
        self.assertEqual(tune.load_state(self.work, "ks_y"), {})

    def test_state_must_be_an_object_and_the_error_names_the_file(self):
        path = self.write(tune.state_path(self.work, "ks_x"), "[1]")
        with self.assertRaises(ValueError) as cm:
            tune.load_state(self.work, "ks_x")
        self.assertIn(path, str(cm.exception))
        self.assertIn("expected an object", str(cm.exception))

    LOADERS = {"state": ("ks_x/tune_state.json", lambda w: tune.load_state(w, "ks_x")),
               "stock_info": ("ks_x/stock_info.json", lambda w: tune.load_stock_info(w, "ks_x")),
               "cars": ("cars.json", lambda w: tune.load_cars(os.path.join(w, "cars.json"))),
               "catalogue": ("catalogue.json", lambda w: tune.load_catalogue(os.path.join(w, "catalogue.json")))}

    def broken(self, name, text, encoding="utf-8"):
        rel, load = self.LOADERS[name]
        path = os.path.join(self.work, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding=encoding) as f:
            f.write(text)
        return path, lambda: load(self.work)

    def check_syntax_error_names_the_file(self, name):
        path, load = self.broken(name, '{"a": 1,')
        with self.assertRaises(ValueError) as cm:
            load()
        self.assertIn(os.path.basename(path), str(cm.exception))

    def check_bom_is_tolerated(self, name, good):
        path, load = self.broken(name, json.dumps(good), encoding="utf-8-sig")
        load()

    def test_state_syntax_error_names_the_file(self):
        self.check_syntax_error_names_the_file("state")

    def test_cars_syntax_error_names_the_file(self):
        self.check_syntax_error_names_the_file("cars")

    def test_catalogue_syntax_error_names_the_file(self):
        self.check_syntax_error_names_the_file("catalogue")

    def test_stock_info_syntax_error_names_the_file(self):
        self.check_syntax_error_names_the_file("stock_info")

    def test_state_with_a_bom_loads(self):
        self.check_bom_is_tolerated("state", {"a": 1})

    def test_cars_with_a_bom_loads(self):
        self.check_bom_is_tolerated("cars", {"default": "ks_x", "cars": [{"id": "ks_x", "label": "X"}]})

    def test_catalogue_with_a_bom_loads(self):
        self.check_bom_is_tolerated("catalogue", mini_catalogue(mini_setting("a", targets=[("@car", "a")])))

    def test_stock_info_with_a_bom_loads(self):
        self.check_bom_is_tolerated("stock_info", {"car_id": "ks_x", "display_name": "X", "brand": "B", "year": 2000})


class TestStateFlow(CarCase):
    def cat(self, *settings):
        cat = mini_catalogue(*(settings or (limiter(), suffix())))
        self.patch(tune, "load_catalogue", lambda path=None: cat)
        return cat

    def test_set_stores_the_coerced_value_and_returns_it(self):
        self.cat()
        self.assertEqual(tune.set_value(self.work, "ks_x", "limiter", "8000"), {"id": "limiter", "value": 8000, "warnings": []})
        self.assertEqual(tune.load_state(self.work, "ks_x"), {"limiter": 8000})

    def test_set_keeps_other_entries_and_overwrites_the_same_id(self):
        self.cat()
        tune.save_state(self.work, "ks_x", {"name_suffix": "_A", "limiter": 1})
        tune.set_value(self.work, "ks_x", "limiter", "9000")
        self.assertEqual(tune.load_state(self.work, "ks_x"), {"name_suffix": "_A", "limiter": 9000})

    def test_set_outside_the_range_warns_but_stores(self):
        self.cat()
        res = tune.set_value(self.work, "ks_x", "limiter", "20000")
        self.assertEqual(res["warnings"], ["limiter=20000 is outside the suggested range 3000..12000"])
        self.assertEqual(tune.load_state(self.work, "ks_x")["limiter"], 20000)

    def test_set_with_a_bad_value_changes_nothing(self):
        self.cat()
        tune.save_state(self.work, "ks_x", {"limiter": 7500})
        with self.assertRaisesRegex(ValueError, "limiter expects an integer"):
            tune.set_value(self.work, "ks_x", "limiter", "fast")
        self.assertEqual(tune.load_state(self.work, "ks_x"), {"limiter": 7500})

    def test_set_unknown_setting(self):
        self.cat()
        with self.assertRaisesRegex(ValueError, "unknown setting 'nope'"):
            tune.set_value(self.work, "ks_x", "nope", "1")
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x")))

    def test_set_refuses_a_setting_that_is_not_applicable_with_the_reason(self):
        self.cat(mini_setting("deep", targets=[("@engine", "gone.deeper")]))
        with self.assertRaisesRegex(ValueError, "deep is not applicable to ks_x: @engine gone.deeper: missing field 'gone'"):
            tune.set_value(self.work, "ks_x", "deep", "1")
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x")))

    def test_set_name_suffix_and_flag(self):
        flag = mini_setting("aids", kind="flag", type="bool", value=0, targets=[("@car", "performance_modes[*].electronics_settings.tc1", True)])
        self.cat(suffix(), flag)
        tune.set_value(self.work, "ks_x", "name_suffix", "_TUNED")
        tune.set_value(self.work, "ks_x", "aids", "yes")
        self.assertEqual(tune.load_state(self.work, "ks_x"), {"name_suffix": "_TUNED", "aids": True})

    def test_unset_removes_and_reports(self):
        self.cat()
        tune.save_state(self.work, "ks_x", {"limiter": 8000, "name_suffix": "_A"})
        self.assertEqual(tune.unset_value(self.work, "ks_x", "limiter"), {"id": "limiter", "removed": True})
        self.assertEqual(tune.load_state(self.work, "ks_x"), {"name_suffix": "_A"})

    def test_unset_of_a_known_setting_that_is_not_set_leaves_the_file_alone(self):
        self.cat()
        self.assertEqual(tune.unset_value(self.work, "ks_x", "limiter"), {"id": "limiter", "removed": False})
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x")))

    def test_unset_unknown_setting_that_is_not_in_the_state(self):
        self.cat()
        with self.assertRaisesRegex(ValueError, "unknown setting 'nope'"):
            tune.unset_value(self.work, "ks_x", "nope")

    def test_unset_removes_a_stale_id_from_the_state(self):
        self.cat()
        tune.save_state(self.work, "ks_x", {"stale_id": 1, "limiter": 8000})
        self.assertEqual(tune.unset_value(self.work, "ks_x", "stale_id"), {"id": "stale_id", "removed": True})
        self.assertEqual(tune.load_state(self.work, "ks_x"), {"limiter": 8000})

    def test_set_then_unset_leaves_an_empty_state(self):
        self.cat()
        tune.set_value(self.work, "ks_x", "limiter", "8000")
        tune.unset_value(self.work, "ks_x", "limiter")
        self.assertEqual(tune.load_state(self.work, "ks_x"), {})

    def test_effective_rows_use_state_value_and_mark_changes(self):
        cat = self.cat()
        tune.save_state(self.work, "ks_x", {"limiter": 8000, "name_suffix": "_MY"})
        rows = {r["id"]: r for r in tune.effective_rows(self.work, "ks_x", cat)}
        self.assertEqual((rows["limiter"]["value"], rows["limiter"]["default"], rows["limiter"]["changed"]), (8000, 7000, True))
        self.assertEqual((rows["name_suffix"]["value"], rows["name_suffix"]["changed"]), ("_MY", False))

    def test_effective_rows_without_state_show_defaults_unchanged(self):
        rows = tune.effective_rows(self.work, "ks_x", self.cat())
        self.assertEqual([(r["value"], r["changed"]) for r in rows], [(7000, False), ("_MY", False)])

    def test_effective_rows_a_state_value_equal_to_the_default_is_not_a_change(self):
        cat = self.cat(mini_setting("f", targets=[("@engine", "limiter")]))
        tune.save_state(self.work, "ks_x", {"f": 7000.000001})
        self.assertFalse(tune.effective_rows(self.work, "ks_x", cat)[0]["changed"])

    def test_effective_rows_reject_a_state_value_of_the_wrong_type(self):
        cat = self.cat()
        tune.save_state(self.work, "ks_x", {"limiter": "fast"})
        with self.assertRaisesRegex(ValueError, "limiter expects an integer"):
            tune.effective_rows(self.work, "ks_x", cat)

    def test_effective_rows_hidden_flag_keeps_non_applicable_rows(self):
        cat = self.cat(limiter(), mini_setting("deep", targets=[("@engine", "gone.deeper")]))
        self.assertEqual([r["id"] for r in tune.effective_rows(self.work, "ks_x", cat)], ["limiter"])
        self.assertEqual([r["id"] for r in tune.effective_rows(self.work, "ks_x", cat, hidden=True)], ["limiter", "deep"])

    def test_unknown_state_ids(self):
        cat = self.cat()
        tune.save_state(self.work, "ks_x", {"limiter": 1, "old_a": 2, "old_b": 3})
        self.assertEqual(tune.unknown_state_ids(self.work, "ks_x", cat), ["old_a", "old_b"])

    def test_unknown_state_ids_are_kept_in_the_file_and_ignored_by_the_rows(self):
        cat = self.cat()
        tune.save_state(self.work, "ks_x", {"old_a": 2})
        self.assertEqual([r["id"] for r in tune.effective_rows(self.work, "ks_x", cat)], ["limiter", "name_suffix"])
        self.assertEqual(tune.load_state(self.work, "ks_x"), {"old_a": 2})

    def test_warn_unknown_state_names_each_id(self):
        self.cat()
        tune.save_state(self.work, "ks_x", {"old_a": 2, "old_b": 3, "limiter": 1})
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            tune.warn_unknown_state(self.work, "ks_x")
        self.assertEqual(err.getvalue().splitlines(), ["warning: ignoring unknown setting 'old_a' in the saved state",
                                                         "warning: ignoring unknown setting 'old_b' in the saved state"])

    def test_warn_unknown_state_is_silent_without_unknown_ids(self):
        self.cat()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            tune.warn_unknown_state(self.work, "ks_x")
        self.assertEqual((out.getvalue(), err.getvalue()), ("", ""))

    def test_warn_unknown_state_writes_to_stderr(self):
        self.cat()
        tune.save_state(self.work, "ks_x", {"old_a": 2})
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            tune.warn_unknown_state(self.work, "ks_x")
        self.assertEqual(out.getvalue(), "")
        self.assertIn("old_a", err.getvalue())

    def test_show_keeps_warnings_off_stdout(self):
        self.cars()
        self.cat()
        tune.save_state(self.work, "ks_x", {"old_a": 2})
        code, out, err = self.run_main("show", "--work", self.work)
        self.assertNotIn("warning", out)
        self.assertIn("warning", err)


# --------------------------------------------------------------------------------------------- resolving defaults
class TestResolveDefaults(CarCase):
    def test_no_base_car_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "no base car in .*, run init first"):
            tune.resolve_defaults(os.path.join(self.work, "other"), "ks_x", mini_catalogue(limiter()))

    def test_row_carries_the_catalogue_fields(self):
        s = limiter()
        row = self.row(s)
        for key in ("id", "group", "label", "kind", "type", "unit", "verified", "min", "max", "description"):
            self.assertEqual(row[key], s[key])

    def test_copies_that_agree_give_a_consistent_int_default(self):
        row = self.row(limiter())
        self.assertEqual((row["default"], type(row["default"]), row["consistent"], row["copies_differ"], row["applicable"], row["reason"]),
                         (7000, int, True, False, True, None))
        self.assertEqual([(t["file"], t["resolved"], t.get("optional"), t["rel"]) for t in row["targets"]],
                         [("@engine", True, None, "data/engine.carengine"), ("@car", True, True, "data/x.car")])

    def test_copies_that_differ_are_listed_and_the_first_required_value_is_the_default(self):
        row = self.row(mini_setting("m", type="int", targets=[("@engine", "minimum"), ("@car", "engine.minimum", True)]))
        self.assertEqual((row["default"], row["consistent"], row["copies_differ"], row["applicable"]), (800, False, True, True))
        self.assertEqual(row["copy_values"], [{"target": "@engine minimum", "value": 800}, {"target": "@car engine.minimum", "value": 900}])

    def test_float_copies_within_the_tolerance_agree(self):
        self.car["engine"]["limiter"] = 7000.000001
        row = self.row(mini_setting("f", targets=[("@engine", "limiter"), ("@car", "engine.limiter")]))
        self.assertTrue(row["consistent"])

    def test_f32_values_become_plain_floats(self):
        self.engine["limiter"] = tune.to_f32(1.1)
        row = self.row(mini_setting("f", targets=[("@engine", "limiter")]))
        self.assertEqual((type(row["default"]), row["default"]), (float, 1.1))

    def test_index_selector(self):
        row = self.row(mini_setting("c", targets=[("@setup", "alignments[1].camber")]))
        self.assertEqual(row["default"], -1.25)

    def test_find_selector_by_text_of_the_key(self):
        a = mini_setting("p", targets=[("@mech_preset", "car_specs.items[key=KEY_POWER].value")])
        b = mini_setting("q", targets=[("@mech_preset", "car_specs.items[key=7].value")])
        rows = self.rows(a, b)
        self.assertEqual((rows["p"]["default"], rows["q"]["default"]), (380.0, 9.0))

    def test_list_element_that_is_missing_makes_the_setting_hidden_with_the_reason(self):
        row = self.row(mini_setting("c", targets=[("@setup", "alignments[5].camber")]))
        self.assertEqual((row["applicable"], row["reason"]), (False, "@setup alignments[5].camber: list has no element 5"))

    def test_find_selector_without_a_match_hides_the_setting(self):
        row = self.row(mini_setting("p", targets=[("@mech_preset", "car_specs.items[key=NOPE].value")]))
        self.assertFalse(row["applicable"])
        self.assertIn("no list element with key=NOPE", row["reason"])

    def test_optional_target_that_does_not_resolve_does_not_block(self):
        row = self.row(mini_setting("o", targets=[("@engine", "limiter"), ("@car", "nothere.deeper", True)]))
        self.assertEqual((row["applicable"], row["resolved"], row["default"]), (True, True, 7000.0))
        self.assertEqual([t["resolved"] for t in row["targets"]], [True, False])

    def test_required_target_that_does_not_resolve_hides_the_setting(self):
        row = self.row(mini_setting("deep", targets=[("@engine", "limiter"), ("@car", "nothere.deeper")]))
        self.assertEqual((row["applicable"], row["reason"]), (False, "@car nothere.deeper: missing field 'nothere'"))

    def test_absent_last_field_counts_as_resolved_with_the_zero_default(self):
        row = self.row(mini_setting("z", targets=[("@engine", "nothere")]))
        self.assertEqual((row["applicable"], row["absent"], row["default"], row["targets"][0]["absent"]), (True, True, 0.0, True))

    def test_absent_int_and_enum_defaults(self):
        rows = self.rows(mini_setting("zi", type="int", targets=[("@engine", "nothere")]),
                         mini_setting("ze", type="enum", choices=["x", "y"], targets=[("@engine", "nothere")]))
        self.assertEqual((rows["zi"]["default"], rows["ze"]["default"]), (0, "x"))

    def test_hide_if_absent(self):
        rows = self.rows(mini_setting("h", targets=[("@engine", "nothere")], hide_if_absent=True),
                         mini_setting("k", targets=[("@engine", "limiter")], hide_if_absent=True),
                         mini_setting("mixed", targets=[("@engine", "limiter"), ("@car", "engine.nothere")], hide_if_absent=True),
                         mini_setting("optonly", targets=[("@engine", "nothere"), ("@car", "engine.limiter", True)], hide_if_absent=True))
        self.assertEqual({k: (v["applicable"], v["reason"]) for k, v in rows.items()},
                         {"h": (False, "field absent in the stock data"), "k": (True, None), "mixed": (True, None),
                          "optonly": (False, "field absent in the stock data")})

    def test_create_missing_makes_missing_objects_resolve_as_absent(self):
        plain = mini_setting("plain", targets=[("@car", "suspensions.arbFront.stiffness")])
        creating = mini_setting("creating", targets=[("@car", "suspensions.arbFront.stiffness")], create_missing=True)
        rows = self.rows(plain, creating)
        self.assertEqual((rows["plain"]["applicable"], rows["plain"]["reason"]),
                         (False, "@car suspensions.arbFront.stiffness: missing field 'suspensions'"))
        self.assertEqual((rows["creating"]["applicable"], rows["creating"]["absent"], rows["creating"]["default"]), (True, True, 0.0))

    def test_needs_must_resolve_but_are_not_compared(self):
        ok = mini_setting("ok", targets=[("@engine", "limiter")], needs=[{"file": "@car", "path": "engine.minimum"}])
        bad = mini_setting("bad", targets=[("@engine", "limiter")], needs=[{"file": "@setup", "path": "gone.deeper"}])
        rows = self.rows(ok, bad)
        self.assertEqual((rows["ok"]["applicable"], rows["ok"]["consistent"], rows["ok"]["copies_differ"]), (True, True, False))
        self.assertEqual((rows["bad"]["applicable"], rows["bad"]["reason"]), (False, "@setup gone.deeper: missing field 'gone'"))

    def test_wildcard_target_expands_to_every_list_element(self):
        row = self.row(mini_setting("w", type="int", targets=[("@car", "performance_modes[*].electronics_settings.tc1")]))
        self.assertEqual([t["path"] for t in row["targets"]], ["performance_modes[0].electronics_settings.tc1",
                                                                "performance_modes[1].electronics_settings.tc1"])
        self.assertEqual((row["consistent"], row["copies_differ"], row["default"]), (False, True, 3))

    def test_wildcard_copies_that_agree_are_consistent(self):
        self.car["performance_modes"][1]["electronics_settings"]["tc1"] = 3
        row = self.row(mini_setting("w", type="int", targets=[("@car", "performance_modes[*].electronics_settings.tc1")]))
        self.assertEqual((row["consistent"], row["default"]), (True, 3))

    def test_wildcard_over_an_empty_or_absent_list_hides_a_required_target(self):
        self.car["performance_modes"] = []
        row = self.row(mini_setting("w", targets=[("@car", "performance_modes[*].electronics_settings.tc1")]))
        self.assertEqual((row["applicable"], row["reason"]), (False, "@car performance_modes[*].electronics_settings.tc1: the list has no elements"))
        row = self.row(mini_setting("w", targets=[("@car", "nolist[*].x")]))
        self.assertFalse(row["applicable"])

    def test_wildcard_with_a_field_absent_in_some_elements(self):
        row = self.row(mini_setting("w", type="int", targets=[("@car", "performance_modes[*].electronics_settings.tc2")]))
        self.assertEqual([(t["path"], t["absent"]) for t in row["targets"]],
                         [("performance_modes[0].electronics_settings.tc2", True), ("performance_modes[1].electronics_settings.tc2", False)])
        self.assertEqual(row["default"], 0)

    def test_flag_has_default_false_and_ignores_the_target_values(self):
        flag = mini_setting("aids", kind="flag", type="bool", value=0,
                            targets=[("@car", "performance_modes[*].electronics_settings.tc1", True), ("@setup", "electronics.tc1", True),
                                     ("@setup", "electronics.nothere", True)])
        row = self.row(flag)
        self.assertEqual((row["default"], row["consistent"], row["absent"], row["applicable"]), (False, True, False, True))
        self.assertEqual(len(row["targets"]), 4)

    def test_flag_with_no_resolvable_optional_target_is_still_applicable(self):
        flag = mini_setting("aids", kind="flag", type="bool", value=0, targets=[("@car", "gone.x", True)])
        self.assertTrue(self.row(flag)["applicable"])

    def test_meta_has_no_targets_and_its_default(self):
        self.stock_info()
        rows = self.rows(*metas())
        self.assertEqual((rows["name_suffix"]["default"], rows["name_suffix"]["targets"], rows["name_suffix"]["applicable"]), ("_MY", [], True))

    def test_variant_name_default_is_the_stock_variant_text(self):
        self.stock_info(variant_name="GT Base")
        self.assertEqual(self.row(variant())["default"], "GT Base")

    def test_variant_name_is_hidden_when_the_stock_car_has_no_variant(self):
        self.stock_info(variant_name="")
        row = self.row(variant())
        self.assertEqual((row["applicable"], row["reason"], row["default"]), (False, "the stock car has no variant name", "Car X"))

    def test_default_template_placeholders(self):
        self.stock_info(variant_name="Base")
        row = self.row(mini_setting("t", kind="meta", type="string", handler="name_suffix", default_template="{stock_display_name}/{stock_variant_name}"))
        self.assertEqual(row["default"], "Car X/Base")

    def test_stock_name_comes_from_the_mechanical_preset_without_stock_info(self):
        row = self.row(mini_setting("t", kind="meta", type="string", handler="name_suffix", default_template="{stock_display_name}"))
        self.assertEqual(row["default"], "Brand Name")

    def test_incomplete_stock_info_is_used_as_far_as_it_goes(self):
        self.write(tune.stock_info_path(self.work, "ks_x"), {"car_id": "ks_x", "display_name": "Car X", "brand": "B", "year": 2000})
        setting = mini_setting("t", kind="meta", type="string", handler="name_suffix", default_template="{stock_display_name}")
        self.assertEqual(self.rows(setting, game=os.path.join(self.work, "no_game.kspkg"))["t"]["default"], "Car X")

    def test_curve_scale_reads_the_curve_and_keeps_the_catalogue_default(self):
        curve = mini_setting("ps", kind="curve_scale", default=1.0, curve_from={"file": "@engine", "path": "powerCurve"}, targets=[])
        row = self.row(curve)
        self.assertEqual((row["applicable"], row["default"], row["targets"][0]["curve"]), (True, 1.0, self.fc.game_path("data/power.curve")))
        self.assertEqual(row["targets"][0]["info"], "3 points, peak 3.0")

    def test_curve_scale_without_a_curve_file_is_hidden(self):
        del self.engine["powerCurve"]
        row = self.row(mini_setting("ps", kind="curve_scale", default=1.0, curve_from={"file": "@engine", "path": "powerCurve"}, targets=[]))
        self.assertEqual((row["applicable"], row["reason"]), (False, "@engine powerCurve: powerCurve holds no curve file name"))

    def test_curve_scale_with_an_empty_curve_is_hidden(self):
        self.fc.add("data/power.curve", {"points": [{"x": 1}]})
        row = self.row(mini_setting("ps", kind="curve_scale", default=1.0, curve_from={"file": "@engine", "path": "powerCurve"}, targets=[]))
        self.assertFalse(row["applicable"])
        self.assertIn("has no points with a value", row["reason"])

    def thermal(self, **kw):
        return mini_setting("th", type="enum", choices=["road", "slick"], targets=[("@tyre_front", "thermalData.thermalPerformanceCurve")],
                            choice_values={"road": GAME_SHARED + "tyres\\road\\tcurve_road.curve",
                                           "slick": GAME_SHARED + "tyres\\slick\\tcurve_slick.curve"}, **kw)

    def test_choice_values_default_is_the_choice_whose_text_matches(self):
        self.assertEqual(self.row(self.thermal())["default"], "road")

    def test_choice_values_match_ignoring_case_and_slash_direction(self):
        self.fc.add_shared("tyres/road/a.tyre", {"thermalData": {"thermalPerformanceCurve": "CONTENT/CARS/COMMON_PHSX/TYRES/SLICK/TCURVE_SLICK.CURVE"}})
        self.assertEqual(self.row(self.thermal())["default"], "slick")

    def test_choice_values_text_that_is_no_choice_hides_the_setting(self):
        self.fc.add_shared("tyres/road/a.tyre", {"thermalData": {"thermalPerformanceCurve": GAME_SHARED + "tyres\\other.curve"}})
        row = self.row(self.thermal())
        self.assertFalse(row["applicable"])
        self.assertIn("is not one of the choices of th", row["reason"])

    def test_tyre_role_resolves_to_the_shared_file(self):
        row = self.row(mini_setting("dy", targets=[("@tyre_front", "modelData.Dy0")]))
        self.assertEqual((row["default"], row["targets"][0]["rel"]), (1.2, "../common_phsx/tyres/road/a.tyre"))

    def test_tyre_role_matches_the_game_path_case_insensitively(self):
        self.car["frontTyreCompounds"] = ["CONTENT\\CARS\\COMMON_PHSX\\TYRES\\ROAD\\A.TYRE"]
        self.assertEqual(self.row(mini_setting("dy", targets=[("@tyre_front", "modelData.Dy0")]))["default"], 1.2)

    def test_tyre_file_that_is_not_extracted_hides_the_setting(self):
        os.remove(os.path.join(self.fc.shared, "tyres", "road", "a.tyre"))
        row = self.row(mini_setting("dy", targets=[("@tyre_front", "modelData.Dy0")]), game=os.path.join(self.work, "no_game.kspkg"))
        self.assertFalse(row["applicable"])
        self.assertTrue(row["reason"].startswith("@tyre_front modelData.Dy0: " + tune.TYRE_UNAVAILABLE), row["reason"])

    def test_tyre_failure_shows_the_real_cause(self):
        self.fc.add("presets/bad.compatibletyres", ValueError("bad.compatibletyres: truncated protobuf"))
        os.remove(os.path.join(self.fc.shared, "tyres", "road", "a.tyre"))
        row = self.row(mini_setting("dy", targets=[("@tyre_front", "modelData.Dy0")]), game=os.path.join(self.work, "no_game.kspkg"))
        self.assertFalse(row["applicable"])
        self.assertIn("truncated protobuf", row["reason"])

    def test_role_files_are_decoded_once_per_resolve(self):
        loads = []
        orig = tune.load_msg
        self.patch(tune, "load_msg", lambda p: (loads.append(os.path.basename(p)), orig(p))[1])
        self.rows(limiter(), mini_setting("m", type="int", targets=[("@engine", "minimum"), ("@car", "engine.minimum")]))
        self.assertEqual(sorted(loads), ["engine.carengine", "x.car"])

    def test_mech_preset_is_the_first_in_sorted_order(self):
        self.fc.add("presets/a_first.MECHANICALCARPRESET", {"brand": "First", "description": "x"})
        row = self.row(mini_setting("b", type="string", targets=[("@mech_preset", "brand")]))
        self.assertEqual(row["default"], "First")

    def test_turbo_role_follows_turbos_to_load(self):
        self.engine["turbos_to_load"] = [self.fc.game_path("data/t0.turbo"), self.fc.game_path("data/t1.turbo")]
        self.fc.add("data/t0.turbo", {"max_boost": 0.8})
        self.fc.add("data/t1.turbo", {"max_boost": 1.2})
        rows = self.rows(mini_setting("t0", targets=[("@turbo[0]", "max_boost")]), mini_setting("t1", targets=[("@turbo[1]", "max_boost")]),
                         mini_setting("t2", targets=[("@turbo[2]", "max_boost")]))
        self.assertEqual((rows["t0"]["default"], rows["t1"]["default"]), (0.8, 1.2))
        self.assertEqual(rows["t2"]["reason"], "@turbo[2] max_boost: the engine file lists 2 turbo file(s), no turbos_to_load[2]")

    def test_manifest_path_is_found_whatever_its_case(self):
        self.car["engine_path"] = "CONTENT\\Cars\\KS_X\\DATA\\Engine.CarEngine"
        self.assertEqual(self.row(limiter())["default"], 7000)

    def test_manifest_role_without_a_path_in_the_car_file(self):
        del self.car["engine_path"]
        row = self.row(limiter())
        self.assertEqual((row["applicable"], row["reason"]), (False, "@engine limiter: no engine_path in the car file"))

    def test_manifest_path_to_a_file_that_is_not_there(self):
        self.car["engine_path"] = self.fc.game_path("data/missing.carengine")
        row = self.row(limiter())
        self.assertFalse(row["applicable"])
        self.assertIn("missing.carengine not found in", row["reason"])

    def test_several_car_files_the_one_with_an_engine_path_wins(self):
        self.fc.add("data/other.car", {"general": {}})
        self.assertEqual(self.row(limiter())["default"], 7000)

    def test_several_car_files_with_an_engine_path_are_ambiguous(self):
        self.fc.add("data/other.car", {"engine_path": "x"})
        row = self.row(limiter())
        self.assertFalse(row["applicable"])
        self.assertIn("ambiguous: 2 .car files", row["reason"])

    def test_no_car_file(self):
        os.remove(os.path.join(self.fc.car_root, "data", "x.car"))
        row = self.row(limiter())
        self.assertIn("no .car file in", row["reason"])

    def test_hidden_false_keeps_only_applicable_rows(self):
        rows = tune.resolve_defaults(self.work, "ks_x", mini_catalogue(limiter(), mini_setting("deep", targets=[("@engine", "q.r")])))
        self.assertEqual([r["id"] for r in rows], ["limiter"])

    def test_row_of_undecodable_file_is_hidden_with_the_decoder_message(self):
        self.fc.add("data/engine.carengine", ValueError("engine.carengine: wire type mismatch"))
        row = self.row(limiter())
        self.assertEqual((row["applicable"], row["reason"]), (False, "@engine limiter: engine.carengine: wire type mismatch"))

    def test_car_path_and_curve_path_stay_inside_their_folder(self):
        root = self.fc.car_root
        with self.assertRaises(ValueError):
            tune.car_path(root, "../../etc/passwd")
        with self.assertRaises(ValueError):
            tune.curve_path(self.fc.root, "..\\..\\evil.curve")
        self.assertEqual(tune.car_path(root, "data/x.car"), os.path.realpath(os.path.join(root, "data", "x.car")))
        self.assertTrue(tune.car_path(root, "../common_phsx/tyres/road/a.tyre").endswith(os.path.join("common_phsx", "tyres", "road", "a.tyre")))

    def test_renamed_replaces_the_old_id_case_insensitively(self):
        self.assertEqual(tune.renamed("data/KS_X_engine.car", "ks_x", "ax_x"), "data/ax_x_engine.car")


# --------------------------------------------------------------------------------------------- resolve cache, effective_row (R3-011)
class TestResolveCache(CarCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(tune._resolved.clear)
        self.stock_info()
        self.cat = mini_catalogue(*metas(), limiter())
        self.reads = []
        real = tune.load_msg
        self.patch(tune, "load_msg", lambda path: (self.reads.append(path), real(path))[1])

    def resolve(self, cat=None, **kw):
        return tune.resolve_defaults(self.work, "ks_x", cat or self.cat, **kw)

    def reads_after(self, call):
        call()
        return len(self.reads)

    def test_a_second_resolve_of_an_unchanged_car_reads_no_file(self):
        first = self.resolve()
        reads = len(self.reads)
        self.assertGreater(reads, 0)
        self.assertEqual(self.resolve(), first)
        self.assertEqual(self.resolve(hidden=True)[:len(first)], first)
        self.assertEqual(len(self.reads), reads)

    def test_a_changed_stamp_of_a_car_file_resolves_again(self):
        self.resolve()
        reads = len(self.reads)
        path = os.path.join(self.fc.car_root, "data", "x.car")
        st = os.stat(path)
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1000000))
        self.resolve()
        self.assertGreater(len(self.reads), reads)

    def test_a_changed_stock_info_resolves_again(self):
        self.resolve()
        reads = len(self.reads)
        path = tune.stock_info_path(self.work, "ks_x")
        st = os.stat(path)
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1000000))
        self.resolve()
        self.assertGreater(len(self.reads), reads)

    def test_init_forgets_the_cached_rows(self):
        self.write(tune.stock_loc_path(self.work), "loc")
        self.resolve()
        reads = self.reads_after(lambda: tune.init(self.work, "ks_x", os.path.join(self.work, "none.kspkg")))
        self.resolve()
        self.assertGreater(len(self.reads), reads)

    def test_ensure_tyre_files_forgets_the_cached_rows_when_it_extracts(self):
        game = self.write(os.path.join(self.work, "g.kspkg"), b"x", binary=True)
        self.patch(kspkg, "cmd_extract", lambda pkg, outdir, prefix=None: self.fc.add_shared("tyres/road/a.tyre"))
        self.resolve()
        os.remove(os.path.join(self.fc.shared, "tyres", "road", "a.tyre"))
        reads = self.reads_after(lambda: self.assertEqual(tune.ensure_tyre_files(self.work, "ks_x", game), "extracted 1 file(s)"))
        self.resolve()
        self.assertGreater(len(self.reads), reads)

    def test_ensure_tyre_files_keeps_the_cached_rows_when_nothing_is_extracted(self):
        game = os.path.join(self.work, "none.kspkg")
        self.resolve()
        reads = self.reads_after(lambda: self.assertEqual(tune.ensure_tyre_files(self.work, "ks_x", game), "present"))
        self.resolve()
        self.assertEqual(len(self.reads), reads)

    def test_the_caller_gets_its_own_copy_of_the_rows(self):
        expected = json.dumps(self.resolve(hidden=True), sort_keys=True)
        for _ in range(2):
            rows = self.resolve(hidden=True)
            rows[0]["default"] = "changed"
            rows[0]["targets"].append({})
            rows[-1]["targets"].clear()
            rows.pop(1)
        self.assertEqual(json.dumps(self.resolve(hidden=True), sort_keys=True), expected)

    def test_a_different_catalogue_is_resolved_on_its_own(self):
        self.resolve()
        self.assertEqual([r["id"] for r in self.resolve(mini_catalogue(*metas()))], ["name_suffix", "variant_name"])
        self.assertEqual([r["id"] for r in self.resolve(mini_catalogue(limiter()))], ["limiter"])

    def test_rows_are_not_cached_when_the_stock_info_is_missing(self):
        os.remove(tune.stock_info_path(self.work, "ks_x"))
        self.resolve()
        reads = len(self.reads)
        self.resolve()
        self.assertGreater(len(self.reads), reads)

    def test_effective_row_resolves_only_its_setting(self):
        cat = mini_catalogue(*metas(), limiter(), mini_setting("tc", type="int", targets=[("@setup", "electronics.tc1")]))
        tune.save_state(self.work, "ks_x", {"limiter": 8000})
        row = tune.effective_row(self.work, "ks_x", "limiter", cat)
        self.assertNotIn("setup.carsetup", [os.path.basename(p) for p in self.reads])
        self.assertEqual((row["id"], row["value"], row["default"], row["changed"]), ("limiter", 8000, 7000, True))
        every = {r["id"]: r for r in tune.effective_rows(self.work, "ks_x", cat, hidden=True)}
        self.assertEqual(row, every["limiter"])

    def test_effective_row_of_an_unknown_setting(self):
        with self.assertRaisesRegex(ValueError, "unknown setting 'nope'"):
            tune.effective_row(self.work, "ks_x", "nope", self.cat)


# --------------------------------------------------------------------------------------------- stock info, car list
class TestStockInfo(Base):
    def info(self, **kw):
        info = {"car_id": "ks_x", "display_name": "Car X", "brand": "B", "year": 2000}
        info.update(kw)
        return info

    def test_valid_and_complete(self):
        self.assertTrue(tune.valid_stock_info(self.info(), "ks_x"))
        self.assertFalse(tune.complete_stock_info(self.info()))
        full = self.info(property_1="a", property_2="b", property_3="c", variant_name="")
        self.assertTrue(tune.complete_stock_info(full))
        self.assertFalse(tune.complete_stock_info(None))

    def test_invalid_variants(self):
        for bad in (self.info(car_id="ks_y"), self.info(display_name=""), self.info(brand=3), self.info(year="2000"),
                    self.info(year=True), {"car_id": "ks_x"}, [1], None):
            with self.subTest(bad):
                self.assertFalse(tune.valid_stock_info(bad, "ks_x"))

    def test_load_missing_is_none_and_invalid_names_the_file(self):
        self.assertIsNone(tune.load_stock_info(self.work, "ks_x"))
        path = self.write(tune.stock_info_path(self.work, "ks_x"), {"car_id": "ks_other"})
        with self.assertRaises(ValueError) as cm:
            tune.load_stock_info(self.work, "ks_x")
        self.assertIn(path, str(cm.exception))

    def test_stock_info_or_none_with_nothing_and_no_game(self):
        self.assertIsNone(tune.stock_info_or_none(self.work, "ks_x", os.path.join(self.work, "no_game.kspkg")))

    def test_stock_info_or_none_returns_incomplete_info_when_the_game_cannot_complete_it(self):
        self.write(tune.stock_info_path(self.work, "ks_x"), self.info())
        got = tune.stock_info_or_none(self.work, "ks_x", os.path.join(self.work, "no_game.kspkg"))
        self.assertEqual(got, self.info())

    def stub_game(self, rows, loc=b""):
        sch = {"enums": {"CarContentData.Property%d" % i: ({}, {0: "Prop%d_Zero" % i}) for i in (1, 2, 3)}}
        self.patch(tune, "schema", lambda: sch)
        self.patch(tune, "read_game_file", lambda work, game, rel: b"table")
        self.patch(car_json, "decode_msg", lambda s, name, data: {"preset": {"lines": [{"car_content": r} for r in rows]}})
        if loc:
            self.write(tune.stock_loc_path(self.work), loc, binary=True)

    def test_write_stock_info_from_the_cars_table(self):
        self.stub_game([{"name": "ks_x", "display_name": "Car X", "brand": "B", "year": 1999, "property_2": "Property2_Modern"},
                        {"name": "ks_y", "display_name": "Other", "brand": "O", "year": 1}],
                       b"ks_x_preset_base=GT Base\r\nks_x_other=Z\r\nks_y_preset_base=No\r\n")
        self.assertEqual(tune.write_stock_info(self.work, "ks_x", "game"), "written")
        with open(tune.stock_info_path(self.work, "ks_x"), encoding="utf-8") as f:
            info = json.load(f)
        self.assertEqual(info, {"car_id": "ks_x", "display_name": "Car X", "brand": "B", "year": 1999, "property_1": "Prop1_Zero",
                                "property_2": "Property2_Modern", "property_3": "Prop3_Zero", "variant_name": "GT Base"})
        self.assertEqual(tune.write_stock_info(self.work, "ks_x", "game"), "present")

    def test_write_stock_info_needs_exactly_one_row(self):
        self.stub_game([], b"x=y\r\n")
        with self.assertRaisesRegex(ValueError, "has 0 rows for ks_x, expected 1"):
            tune.write_stock_info(self.work, "ks_x", "game")
        self.stub_game([{"name": "ks_x", "display_name": "A", "brand": "B", "year": 1}] * 2, b"x=y\r\n")
        with self.assertRaisesRegex(ValueError, "has 2 rows"):
            tune.write_stock_info(self.work, "ks_x", "game")

    def test_write_stock_info_row_without_a_year(self):
        self.stub_game([{"name": "ks_x", "display_name": "A", "brand": "B"}], b"x=y\r\n")
        with self.assertRaisesRegex(ValueError, "lacks display_name, brand or year"):
            tune.write_stock_info(self.work, "ks_x", "game")

    def test_ensure_stock_loc_copies_once(self):
        calls = []
        self.patch(tune, "read_game_file", lambda work, game, rel: calls.append(rel) or b"loc bytes")
        self.assertEqual(tune.ensure_stock_loc(self.work, "game"), "written")
        self.assertEqual(tune.ensure_stock_loc(self.work, "game"), "present")
        self.assertEqual(calls, [tune.STOCK_LOC])
        with open(tune.stock_loc_path(self.work), "rb") as f:
            self.assertEqual(f.read(), b"loc bytes")

    def test_read_game_file_requires_the_package(self):
        with self.assertRaisesRegex(ValueError, "game package not found"):
            tune.read_game_file(self.work, os.path.join(self.work, "nope.kspkg"), "a\\b")

    def test_read_game_file_extracts_through_a_temp_folder_and_cleans_up(self):
        game = self.write(os.path.join(self.work, "g.kspkg"), b"x", binary=True)

        def extract(pkg, outdir, prefix=None):
            self.write(os.path.join(outdir, "system", "cars.table"), b"DATA", binary=True)
            print("noise from kspkg")
        self.patch(kspkg, "cmd_extract", extract)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            data = tune.read_game_file(self.work, game, "system\\cars.table")
        self.assertEqual((data, out.getvalue()), (b"DATA", ""))
        self.assertFalse(os.path.exists(os.path.join(self.work, "stock_tmp")))

    def test_read_game_file_file_not_in_the_package(self):
        game = self.write(os.path.join(self.work, "g.kspkg"), b"x", binary=True)
        self.patch(kspkg, "cmd_extract", lambda pkg, outdir, prefix=None: None)
        with self.assertRaisesRegex(ValueError, "system.cars.table not found in"):
            tune.read_game_file(self.work, game, "system\\cars.table")
        self.assertFalse(os.path.exists(os.path.join(self.work, "stock_tmp")))


class TestPickCarAndIndex(Base):
    CARS = {"default": "ks_a", "cars": [{"id": "ks_a", "label": "A"}, {"id": "ks_b", "label": "B"}]}

    def test_pick_car_default_and_known(self):
        self.assertEqual(tune.pick_car(self.CARS), "ks_a")
        self.assertEqual(tune.pick_car(self.CARS, "ks_b"), "ks_b")

    def test_pick_car_without_index_lists_the_tested_cars(self):
        with self.assertRaisesRegex(ValueError, r"unknown car 'ks_z', the car list of the game is not available, the tested cars \(tuner/cars.json\) are: ks_a, ks_b"):
            tune.pick_car(self.CARS, "ks_z")

    def test_pick_car_with_index_accepts_any_game_car(self):
        index = [{"id": "ks_a", "display_name": "A"}, {"id": "ks_q", "display_name": "Q"}]
        self.assertEqual(tune.pick_car(self.CARS, "ks_q", index), "ks_q")

    def test_pick_car_with_index_suggests_close_matches_or_counts(self):
        index = [{"id": "ks_alfa_romeo", "display_name": "A"}, {"id": "ks_toyota_gr86", "display_name": "T"}]
        with self.assertRaisesRegex(ValueError, "unknown car 'ks_alfa_romeu', close matches: ks_alfa_romeo"):
            tune.pick_car(self.CARS, "ks_alfa_romeu", index)
        with self.assertRaisesRegex(ValueError, "the game has 2 cars, tune.py cars lists them"):
            tune.pick_car(self.CARS, "zzzz", index)

    def test_new_id_for(self):
        self.assertEqual(tune.new_id_for("ks_bmw_m3_e46_csl"), "ax_bmw_m3_e46_csl")
        self.assertEqual(tune.new_id_for("mx_thing"), "ax_thing")
        for car in ("ks_a", "ab_cd_ef"):
            self.assertEqual(len(tune.new_id_for(car)), len(car))

    def test_index_from_a_valid_cache(self):
        index = [{"id": "ks_a", "display_name": "A", "brand": "x", "year": 1}]
        self.write(tune.cars_index_path(self.work), index)
        self.assertEqual(tune.load_cars_index(self.work, os.path.join(self.work, "none.kspkg")), index)

    def test_index_cache_that_is_damaged_or_empty_falls_back_to_none_without_a_game(self):
        for text in ("[]", "{", '[{"id": 1}]', '{"id": "ks_a"}', '[{"id": "ks_a"}]'):
            with self.subTest(text):
                self.write(tune.cars_index_path(self.work), text)
                self.assertIsNone(tune.load_cars_index(self.work, os.path.join(self.work, "none.kspkg")))

    def test_index_without_cache_and_without_game_is_none(self):
        self.assertIsNone(tune.load_cars_index(self.work, os.path.join(self.work, "none.kspkg")))

    def stub_table(self, lines):
        self.patch(tune, "read_game_file", lambda work, game, rel: b"table")
        self.patch(tune, "schema", lambda: {})
        self.patch(car_json, "decode_msg", lambda s, name, data: {"preset": {"lines": lines}})

    def test_index_from_the_game_is_sorted_cached_and_cleaned(self):
        game = self.write(os.path.join(self.work, "g.kspkg"), b"x", binary=True)
        self.stub_table([{"car_content": {"name": "ks_b", "display_name": "beta", "brand": "BB", "year": 2001}},
                         {"car_content": {"name": "ks_a", "display_name": "Zeta", "brand": "AA", "year": 2002}},
                         {"car_content": {"name": "ks_c"}},
                         {"car_content": {"name": ""}},
                         {"car_content": {"display_name": "no name"}},
                         {"other": 1},
                         {"car_content": {"name": "ks_b", "display_name": "beta again"}}])
        index = tune.load_cars_index(self.work, game)
        self.assertEqual([c["id"] for c in index], ["ks_b", "ks_c", "ks_a"])
        self.assertEqual(index[1], {"id": "ks_c", "display_name": "ks_c", "brand": "", "year": None})
        self.assertEqual(index[0]["display_name"], "beta again")
        with open(tune.cars_index_path(self.work), encoding="utf-8") as f:
            self.assertEqual(json.load(f), index)

    def test_index_with_an_unreadable_table_is_none_and_nothing_is_cached(self):
        game = self.write(os.path.join(self.work, "g.kspkg"), b"x", binary=True)
        self.patch(tune, "read_game_file", lambda work, game, rel: (_ for _ in ()).throw(ValueError("package damaged")))
        self.assertIsNone(tune.load_cars_index(self.work, game))
        self.assertFalse(os.path.exists(tune.cars_index_path(self.work)))

    def test_unknown_car_message_carries_the_real_reason(self):
        self.cars(("ks_a", "A"))
        game = self.write(os.path.join(self.work, "g.kspkg"), b"x", binary=True)
        self.patch(tune, "read_game_file", lambda work, game, rel: (_ for _ in ()).throw(ValueError("missing schema file acevo.desc")))
        with self.assertRaises(ValueError) as cm:
            tune.start({"work": self.work, "car": "ks_other", "game": game})
        self.assertIn("missing schema file acevo.desc", str(cm.exception))


class TestListCars(Base):
    def setUp(self):
        super().setUp()
        self.cars(("ks_a", "Alpha"), ("ks_b", "Beta"))
        self.mods = str(self.d / "mods")
        self.game = os.path.join(self.work, "none.kspkg")

    def extract(self, car_id, size=10, name="f.bin"):
        self.write(os.path.join(tune.car_root_of(tune.base_dir(self.work, car_id), car_id), name), b"x" * size, binary=True)

    def test_without_index_only_tested_cars_sorted_by_display_name(self):
        rows = tune.list_cars(self.work, self.mods, game=self.game)
        self.assertEqual([(r["id"], r["display_name"], r["tested"], r["default"], r["extracted"], r["installed"], r["bytes"], r["new_id"])
                          for r in rows],
                         [("ks_a", "Alpha", True, True, False, False, None, "ax_a"), ("ks_b", "Beta", True, False, False, False, None, "ax_b")])

    def test_cache_adds_untested_cars_and_names(self):
        self.write(tune.cars_index_path(self.work), [{"id": "ks_c", "display_name": "Charlie"}, {"id": "ks_b", "display_name": "Beta Game"},
                                                     {"id": "ks_d", "display_name": "alpha two"}])
        rows = tune.list_cars(self.work, self.mods, game=self.game)
        self.assertEqual([(r["id"], r["display_name"], r["label"], r["tested"]) for r in rows],
                         [("ks_a", "Alpha", "Alpha", True), ("ks_d", "alpha two", "alpha two", False), ("ks_b", "Beta Game", "Beta", True),
                          ("ks_c", "Charlie", "Charlie", False)])

    def test_tested_only_ignores_the_cache(self):
        self.write(tune.cars_index_path(self.work), [{"id": "ks_c", "display_name": "Charlie"}])
        self.assertEqual([r["id"] for r in tune.list_cars(self.work, self.mods, tested_only=True, game=self.game)], ["ks_a", "ks_b"])

    def test_extracted_size_and_stock_name(self):
        self.extract("ks_a", 10)
        self.extract("ks_a", 5, "sub/g.bin")
        self.write(tune.stock_info_path(self.work, "ks_a"), {"car_id": "ks_a", "display_name": "Zulu Stock", "brand": "B", "year": 1})
        rows = {r["id"]: r for r in tune.list_cars(self.work, self.mods, game=self.game)}
        self.assertEqual((rows["ks_a"]["extracted"], rows["ks_a"]["bytes"], rows["ks_a"]["display_name"], rows["ks_a"]["label"]),
                         (True, 15, "Zulu Stock", "Alpha"))
        self.assertEqual((rows["ks_b"]["extracted"], rows["ks_b"]["bytes"]), (False, None))

    def test_empty_car_folder_does_not_count_as_extracted(self):
        os.makedirs(tune.car_root_of(tune.base_dir(self.work, "ks_a"), "ks_a"))
        self.assertFalse([r for r in tune.list_cars(self.work, self.mods, game=self.game) if r["id"] == "ks_a"][0]["extracted"])

    def test_installed_means_the_new_id_package_is_in_the_mods_folder(self):
        self.write(os.path.join(self.mods, "ax_b.kspkg"), b"p", binary=True)
        self.write(os.path.join(self.mods, "ax_a.txt"), b"p", binary=True)
        rows = {r["id"]: r["installed"] for r in tune.list_cars(self.work, self.mods, game=self.game)}
        self.assertEqual(rows, {"ks_a": False, "ks_b": True})

    def test_list_survives_a_damaged_stock_info(self):
        self.extract("ks_a")
        self.extract("ks_b")
        self.write(tune.stock_info_path(self.work, "ks_b"), '{"car_id": "ks_b", "disp')
        rows = tune.list_cars(self.work, self.mods, game=self.game)
        self.assertEqual([r["id"] for r in rows], ["ks_a", "ks_b"])

    def test_display_name_of_prefers_the_stock_info_then_the_list(self):
        self.write(tune.stock_info_path(self.work, "ks_a"), {"car_id": "ks_a", "display_name": "Stock A", "brand": "B", "year": 1})
        self.assertEqual(tune.display_name_of(self.work, "ks_a"), "Stock A")
        self.assertEqual(tune.display_name_of(self.work, "ks_b"), "Beta")

    def test_without_sizes_no_tree_is_walked(self):
        self.extract("ks_a", 10)
        walked = []
        real = tune.count_tree
        self.patch(tune, "count_tree", lambda path: walked.append(path) or real(path))
        rows = {r["id"]: r for r in tune.list_cars(self.work, self.mods, game=self.game, sizes=False)}
        self.assertEqual((walked, rows["ks_a"]["extracted"], rows["ks_a"]["bytes"]), ([], True, None))
        rows = {r["id"]: r for r in tune.list_cars(self.work, self.mods, game=self.game)}
        self.assertEqual((len(walked), rows["ks_a"]["bytes"]), (1, 10))

    def test_an_unexpandable_mods_folder_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "cannot expand"):
            tune.list_cars(self.work, "%ACE_TEST_NO_SUCH_VAR%" + os.sep + "m", game=self.game)

    def test_note_untested(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            tune.note_untested("ks_a")
            tune.note_untested("ks_zzz")
        self.assertEqual(out.getvalue(), "note: ks_zzz is not in the tested list; results are unverified\n")


# --------------------------------------------------------------------------------------------- modded cars (tunes)
class TuneCase(Base):
    """Two synthetic stock cars ks_alpha / ks_bravo (default tunes ax_alpha / ax_bravo) in a scratch work folder and mods folder."""

    def setUp(self):
        super().setUp()
        self.cars(("ks_alpha", "Alpha"), ("ks_bravo", "Bravo"))
        self.patch(tune, "load_catalogue", lambda path=None: mini_catalogue(suffix()))
        self.mods = str(self.d / "mods")
        os.makedirs(self.mods)

    def extract(self, car_id):
        self.write(os.path.join(tune.car_root_of(tune.base_dir(self.work, car_id), car_id), "f.bin"), b"x", binary=True)

    def build(self, car_id, tune_id):
        self.write(os.path.join(tune.build_dir(self.work, car_id), tune_id, tune_id + ".kspkg"), b"p", binary=True)

    def install(self, tune_id):
        self.write(os.path.join(self.mods, tune_id + ".kspkg"), b"p", binary=True)

    def files(self):
        return sorted(os.path.relpath(os.path.join(dp, n), self.work) for dp, _, names in os.walk(self.work) for n in names)

    def dirs(self):
        return sorted(os.path.relpath(os.path.join(dp, n), self.work) for dp, names, _ in os.walk(self.work) for n in names)


class TestTuneStatePaths(TuneCase):
    def test_old_calls_keep_the_legacy_path(self):
        self.assertEqual(tune.state_path(self.work, "ks_alpha"), os.path.join(self.work, "ks_alpha", "tune_state.json"))
        tune.save_state(self.work, "ks_alpha", {"limiter": 1})
        self.assertEqual(tune.load_state(self.work, "ks_alpha"), {"limiter": 1})
        self.assertEqual(self.files(), [os.path.join("ks_alpha", "tune_state.json")])

    def test_default_id_and_none_are_the_legacy_path_and_write_no_meta(self):
        self.assertEqual(tune.state_path(self.work, "ks_alpha", "ax_alpha"), tune.state_path(self.work, "ks_alpha"))
        tune.save_state(self.work, "ks_alpha", {"a": 1}, "ax_alpha")
        self.assertEqual(tune.load_state(self.work, "ks_alpha"), {"a": 1})
        self.assertEqual(tune.load_state(self.work, "ks_alpha", "ax_alpha"), {"a": 1})
        self.assertEqual(self.files(), [os.path.join("ks_alpha", "tune_state.json")])

    def test_draft_path_and_no_meta(self):
        self.assertEqual(tune.DRAFT, "draft")
        self.assertEqual(tune.state_path(self.work, "ks_alpha", tune.DRAFT), os.path.join(self.work, "ks_alpha", "draft_state.json"))
        tune.save_state(self.work, "ks_alpha", {"d": 1}, tune.DRAFT)
        self.assertEqual(tune.load_state(self.work, "ks_alpha", tune.DRAFT), {"d": 1})
        self.assertEqual(self.files(), [os.path.join("ks_alpha", "draft_state.json")])
        self.assertEqual(tune.load_state(self.work, "ks_alpha"), {})

    def test_other_ids_live_in_tunes_with_a_meta_file(self):
        self.assertEqual(tune.TUNES, "tunes")
        self.assertEqual(tune.state_path(self.work, "ks_alpha", "ax_alp01"), os.path.join(self.work, "ks_alpha", "tunes", "ax_alp01", "tune_state.json"))
        tune.save_state(self.work, "ks_alpha", {"x": 2}, "ax_alp01")
        self.assertEqual(tune.load_state(self.work, "ks_alpha", "ax_alp01"), {"x": 2})
        self.assertEqual(self.files(), [os.path.join("ks_alpha", "tunes", "ax_alp01", "meta.json"), os.path.join("ks_alpha", "tunes", "ax_alp01", "tune_state.json")])
        with open(os.path.join(self.work, "ks_alpha", "tunes", "ax_alp01", "meta.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"stock": "ks_alpha"})

    def test_an_existing_meta_file_is_kept(self):
        meta = self.write(os.path.join(self.work, "ks_alpha", "tunes", "ax_alp01", "meta.json"), {"stock": "ks_alpha", "keep": True})
        tune.save_state(self.work, "ks_alpha", {}, "ax_alp01")
        with open(meta, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"stock": "ks_alpha", "keep": True})

    def test_a_missing_tune_state_is_empty(self):
        self.assertEqual(tune.load_state(self.work, "ks_alpha", "ax_alp01"), {})

    def test_tune_dir(self):
        car = os.path.join(self.work, "ks_alpha")
        self.assertEqual([tune.tune_dir(self.work, "ks_alpha", t) for t in (None, "ax_alpha", tune.DRAFT)], [car] * 3)
        self.assertEqual(tune.tune_dir(self.work, "ks_alpha", "ax_alp02"), os.path.join(car, "tunes", "ax_alp02"))

    def test_invalid_ids_are_refused_everywhere_and_write_nothing(self):
        for bad in ("ax_alp1", "ax_alpha1", "AX_ALP01", "ax_alp0!", "..", "../ax_al", "ax/alp01", "ax\\alp01", "ks_alpha", "", 5):
            with self.subTest(bad=bad):
                for call in (lambda: tune.state_path(self.work, "ks_alpha", bad), lambda: tune.load_state(self.work, "ks_alpha", bad),
                             lambda: tune.save_state(self.work, "ks_alpha", {}, bad)):
                    with self.assertRaises(ValueError):
                        call()
        self.assertFalse(os.path.exists(self.work))

    def test_the_stock_id_is_refused_with_the_clone_message(self):
        with self.assertRaisesRegex(ValueError, "new id equals the old id 'ks_alpha'"):
            tune.state_path(self.work, "ks_alpha", "ks_alpha")


class TestListTunes(TuneCase):
    def test_nothing_without_a_state_or_build(self):
        self.extract("ks_alpha")
        self.assertEqual(tune.list_tunes(self.work, "ks_alpha"), [])
        self.assertEqual(tune.list_tunes(self.work, "ks_missing"), [])

    def test_default_is_listed_for_its_state_file(self):
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_A"})
        self.assertEqual(tune.list_tunes(self.work, "ks_alpha"),
                         [{"id": "ax_alpha", "stock": "ks_alpha", "default": True, "name_suffix": "_A", "has_state": True}])

    def test_default_is_listed_for_its_build_folder_without_a_state(self):
        self.build("ks_alpha", "ax_alpha")
        self.assertEqual(tune.list_tunes(self.work, "ks_alpha"),
                         [{"id": "ax_alpha", "stock": "ks_alpha", "default": True, "name_suffix": "_MY", "has_state": False}])

    def test_an_empty_build_folder_of_another_tune_does_not_list_it(self):
        self.build("ks_alpha", "ax_alp01")
        self.assertEqual(tune.list_tunes(self.work, "ks_alpha"), [])

    def test_other_tunes_need_a_state_file_and_the_default_comes_first(self):
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_Z"}, "ax_alp02")
        tune.save_state(self.work, "ks_alpha", {}, "ax_alp01")
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_D"})
        os.makedirs(os.path.join(self.work, "ks_alpha", "tunes", "ax_alp03"))
        self.write(os.path.join(self.work, "ks_alpha", "tunes", "ax_alp04", "meta.json"), {"stock": "ks_alpha"})
        rows = tune.list_tunes(self.work, "ks_alpha")
        self.assertEqual([(r["id"], r["default"], r["name_suffix"], r["has_state"]) for r in rows],
                         [("ax_alpha", True, "_D", True), ("ax_alp01", False, "_MY", True), ("ax_alp02", False, "_Z", True)])
        self.assertEqual({r["stock"] for r in rows}, {"ks_alpha"})

    def test_stray_and_reserved_folders_are_ignored(self):
        for name in ("notes", "AX_ALP01", "ax_alp1", "draft", "ax_alpha"):
            self.write(os.path.join(self.work, "ks_alpha", "tunes", name, "tune_state.json"), {"name_suffix": "_S"})
        self.assertEqual(tune.list_tunes(self.work, "ks_alpha"), [])

    def test_the_tunes_of_another_car_are_not_listed(self):
        tune.save_state(self.work, "ks_bravo", {}, "ax_bra01")
        self.assertEqual(tune.list_tunes(self.work, "ks_alpha"), [])

    def test_suffix_comes_from_the_catalogue_default_when_the_state_has_none(self):
        self.patch(tune, "load_catalogue", lambda path=None: mini_catalogue(dict(suffix(), default="_DEF")))
        tune.save_state(self.work, "ks_alpha", {"limiter": 5}, "ax_alp01")
        self.assertEqual(tune.list_tunes(self.work, "ks_alpha")[0]["name_suffix"], "_DEF")

    def test_a_catalogue_without_the_suffix_setting_is_an_error(self):
        self.patch(tune, "load_catalogue", lambda path=None: mini_catalogue(limiter()))
        with self.assertRaisesRegex(ValueError, "no name_suffix setting"):
            tune.list_tunes(self.work, "ks_alpha")

    def test_a_damaged_state_is_an_error_naming_the_file(self):
        self.write(tune.state_path(self.work, "ks_alpha"), '{"name_su')
        with self.assertRaisesRegex(ValueError, "tune_state.json"):
            tune.list_tunes(self.work, "ks_alpha")


class TestKnownTuneIds(TuneCase):
    def test_default_ids_of_tested_cars_even_without_a_work_folder(self):
        self.assertEqual(tune.known_tune_ids(self.work), {"ax_alpha", "ax_bravo"})

    def test_cars_index_and_extracted_folders_add_default_ids(self):
        self.write(tune.cars_index_path(self.work), [{"id": "ks_charlie", "display_name": "Charlie"}])
        self.extract("ks_delta")
        self.write(os.path.join(self.work, "backups", "x.kspkg"), b"p", binary=True)
        self.assertEqual(tune.known_tune_ids(self.work), {"ax_alpha", "ax_bravo", "ax_charlie", "ax_delta"})

    def test_tunes_folders_of_every_car(self):
        tune.save_state(self.work, "ks_alpha", {}, "ax_alp01")
        tune.save_state(self.work, "ks_bravo", {}, "ax_bra07")
        os.makedirs(os.path.join(self.work, "ks_bravo", "tunes", "ax_bra08"))
        self.write(os.path.join(self.work, "ks_bravo", "tunes", "stray.txt"), "x")
        self.assertEqual(tune.known_tune_ids(self.work), {"ax_alpha", "ax_bravo", "ax_alp01", "ax_bra07", "ax_bra08"})

    def test_mods_folder_packages_only_when_given(self):
        self.install("ax_alp05")
        self.write(os.path.join(self.mods, "ax_alp06.txt"), b"x", binary=True)
        self.write(os.path.join(self.mods, "AX_ALP07.KSPKG"), b"x", binary=True)
        self.assertNotIn("ax_alp05", tune.known_tune_ids(self.work))
        self.assertEqual(tune.known_tune_ids(self.work, self.mods), {"ax_alpha", "ax_bravo", "ax_alp05", "ax_alp07"})

    def test_a_missing_mods_folder_adds_nothing(self):
        self.assertEqual(tune.known_tune_ids(self.work, str(self.d / "nowhere")), {"ax_alpha", "ax_bravo"})

    def test_the_game_package_is_never_read(self):
        real = tune.read_game_file
        calls = []
        self.patch(tune, "read_game_file", lambda *a, **k: calls.append(a) or real(*a, **k))
        tune.known_tune_ids(self.work)
        self.assertEqual(calls, [])


class TestFreeTuneId(TuneCase):
    def test_first_id_replaces_the_last_two_characters_and_keeps_the_length(self):
        got = tune.free_tune_id(self.work, "ks_alpha")
        self.assertEqual((got, len(got)), ("ax_alp01", len("ks_alpha")))
        self.assertEqual(tune.free_tune_id(self.work, "ks_bmw_m3_e46_csl"), "ax_bmw_m3_e46_c01")

    def test_nothing_is_written(self):
        tune.free_tune_id(self.work, "ks_alpha", self.mods)
        self.assertFalse(os.path.exists(self.work))

    def test_the_counter_skips_tunes_mods_packages_and_other_default_ids(self):
        tune.save_state(self.work, "ks_alpha", {}, "ax_alp01")
        self.install("ax_alp02")
        self.cars(("ks_alpha", "Alpha"), ("ks_alp03", "Other"))
        # the default id of another stock car sits in the sequence: ks_alp03 -> ax_alp03
        self.assertEqual(tune.free_tune_id(self.work, "ks_alpha", self.mods), "ax_alp04")

    def test_without_the_mods_folder_its_packages_do_not_count(self):
        self.install("ax_alp01")
        self.assertEqual(tune.free_tune_id(self.work, "ks_alpha"), "ax_alp01")
        self.assertEqual(tune.free_tune_id(self.work, "ks_alpha", self.mods), "ax_alp02")

    def test_a_tune_of_another_stock_car_blocks_the_id_too(self):
        tune.save_state(self.work, "ks_bravo", {}, "ax_alp01")
        self.assertEqual(tune.free_tune_id(self.work, "ks_alpha"), "ax_alp02")

    def test_ids_up_to_99_then_exhausted(self):
        for n in range(1, 100):
            self.install("ax_alp%02d" % n)
        os.remove(os.path.join(self.mods, "ax_alp99.kspkg"))
        self.assertEqual(tune.free_tune_id(self.work, "ks_alpha", self.mods), "ax_alp99")
        self.install("ax_alp99")
        with self.assertRaisesRegex(ValueError, "no free tuned car id left for ks_alpha"):
            tune.free_tune_id(self.work, "ks_alpha", self.mods)

    def test_a_stock_id_too_short_for_the_pattern_has_no_valid_id(self):
        self.cars(("k", "K"))
        with self.assertRaisesRegex(ValueError, "no free tuned car id left"):
            tune.free_tune_id(self.work, "k")


class TestTuneSuffix(TuneCase):
    def setUp(self):
        super().setUp()
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_A"})
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_B"}, "ax_alp01")
        tune.save_state(self.work, "ks_bravo", {"name_suffix": "_C"})

    def test_taken_is_per_stock_car(self):
        self.assertTrue(tune.suffix_taken(self.work, "ks_alpha", "_A"))
        self.assertTrue(tune.suffix_taken(self.work, "ks_alpha", "_B"))
        self.assertFalse(tune.suffix_taken(self.work, "ks_alpha", "_C"))
        self.assertFalse(tune.suffix_taken(self.work, "ks_alpha", "_a"))
        self.assertFalse(tune.suffix_taken(self.work, "ks_alpha", "_A "))

    def test_exclude_ignores_that_tune(self):
        self.assertFalse(tune.suffix_taken(self.work, "ks_alpha", "_A", exclude="ax_alpha"))
        self.assertTrue(tune.suffix_taken(self.work, "ks_alpha", "_A", exclude="ax_alp01"))

    def test_the_default_suffix_counts_when_the_state_has_none(self):
        tune.save_state(self.work, "ks_alpha", {}, "ax_alp02")
        self.assertTrue(tune.suffix_taken(self.work, "ks_alpha", "_MY"))

    def test_free_suffix_returns_a_free_one_unchanged(self):
        self.assertEqual(tune.free_suffix(self.work, "ks_alpha", "_NEW"), "_NEW")
        self.assertEqual(tune.free_suffix(self.work, "ks_alpha", "_C"), "_C")

    def test_free_suffix_counts_up_from_2(self):
        self.assertEqual(tune.free_suffix(self.work, "ks_alpha", "_A"), "_A2")
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_A2"}, "ax_alp02")
        self.assertEqual(tune.free_suffix(self.work, "ks_alpha", "_A"), "_A3")

    def test_free_suffix_counts_a_trailing_number_up_instead_of_appending(self):
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_MY"}, "ax_alp02")
        self.assertEqual(tune.free_suffix(self.work, "ks_alpha", "_MY"), "_MY2")
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_MY2"}, "ax_alp03")
        self.assertEqual(tune.free_suffix(self.work, "ks_alpha", "_MY"), "_MY3")
        self.assertEqual(tune.free_suffix(self.work, "ks_alpha", "_MY2"), "_MY3")
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_MY3"}, "ax_alp04")
        self.assertEqual(tune.free_suffix(self.work, "ks_alpha", "_MY2"), "_MY4")

    def test_free_suffix_with_a_wanted_number_goes_to_the_next_one(self):
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_T1"}, "ax_alp02")
        self.assertEqual(tune.free_suffix(self.work, "ks_alpha", "_T1"), "_T2")
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_T2"}, "ax_alp03")
        self.assertEqual(tune.free_suffix(self.work, "ks_alpha", "_T1"), "_T3")
        self.assertEqual(tune.free_suffix(self.work, "ks_alpha", "_T3"), "_T3")

    def test_free_suffix_keeps_the_width_of_a_number_with_leading_zeros(self):
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_T01"}, "ax_alp02")
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_T09"}, "ax_alp03")
        self.assertEqual(tune.free_suffix(self.work, "ks_alpha", "_T01"), "_T02")
        self.assertEqual(tune.free_suffix(self.work, "ks_alpha", "_T09"), "_T10")

    def test_free_suffix_cuts_the_stem_and_never_the_number(self):
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "x" * 29 + "9"}, "ax_alp02")
        got = tune.free_suffix(self.work, "ks_alpha", "x" * 29 + "9")
        self.assertEqual((got, len(got)), ("x" * 28 + "10", 30))
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "9" * 30}, "ax_alp03")
        with self.assertRaisesRegex(ValueError, "no free name suffix left"):
            tune.free_suffix(self.work, "ks_alpha", "9" * 30)

    def test_free_suffix_with_exclude_keeps_its_own(self):
        self.assertEqual(tune.free_suffix(self.work, "ks_alpha", "_B", exclude="ax_alp01"), "_B")

    def test_free_suffix_stays_within_the_length_limit(self):
        long = "x" * tune.NAME_SUFFIX_MAX
        tune.save_state(self.work, "ks_alpha", {"name_suffix": long}, "ax_alp02")
        got = tune.free_suffix(self.work, "ks_alpha", long)
        self.assertEqual((got, len(got)), ("x" * 29 + "2", 30))

    def test_free_suffix_validates_the_wanted_suffix(self):
        for bad in ("", "x" * 31, "a\nb", 5, None):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "name_suffix expects 1 to 30 characters"):
                tune.free_suffix(self.work, "ks_alpha", bad)

    def test_suffixes_are_not_trimmed(self):
        self.assertEqual(tune.free_suffix(self.work, "ks_alpha", " _A"), " _A")


class TestDuplicateTune(TuneCase):
    def snapshot(self):
        out = {}
        for dp, _, names in os.walk(self.work):
            for n in names:
                with open(os.path.join(dp, n), "rb") as f:
                    out[os.path.relpath(os.path.join(dp, n), self.work)] = f.read()
        return out, self.dirs()

    def test_from_the_default_tune(self):
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_A", "limiter": 8000, "nested": {"a": [1]}})
        res = tune.duplicate_tune(self.work, "ks_alpha", None)
        self.assertEqual(res, {"id": "ax_alp01", "stock": "ks_alpha", "name_suffix": "_A2"})
        self.assertEqual(tune.load_state(self.work, "ks_alpha", "ax_alp01"), {"name_suffix": "_A2", "limiter": 8000, "nested": {"a": [1]}})
        self.assertEqual(tune.load_state(self.work, "ks_alpha"), {"name_suffix": "_A", "limiter": 8000, "nested": {"a": [1]}})
        with open(os.path.join(self.work, "ks_alpha", "tunes", "ax_alp01", "meta.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"stock": "ks_alpha"})

    def test_the_default_id_as_src_is_the_default_tune(self):
        tune.save_state(self.work, "ks_alpha", {"limiter": 1})
        tune.duplicate_tune(self.work, "ks_alpha", "ax_alpha")
        self.assertEqual(tune.load_state(self.work, "ks_alpha", "ax_alp01")["limiter"], 1)

    def test_the_copy_is_deep(self):
        tune.save_state(self.work, "ks_alpha", {"nested": {"a": [1]}})
        tune.duplicate_tune(self.work, "ks_alpha", None)
        state = tune.load_state(self.work, "ks_alpha", "ax_alp01")
        state["nested"]["a"].append(2)
        tune.save_state(self.work, "ks_alpha", state, "ax_alp01")
        self.assertEqual(tune.load_state(self.work, "ks_alpha")["nested"], {"a": [1]})

    def test_from_a_modded_tune_and_a_chain_of_copies(self):
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_A", "x": 1})
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_DRIFT", "x": 2}, "ax_alp01")
        first = tune.duplicate_tune(self.work, "ks_alpha", "ax_alp01")
        second = tune.duplicate_tune(self.work, "ks_alpha", "ax_alp01")
        self.assertEqual((first["id"], first["name_suffix"], second["id"], second["name_suffix"]), ("ax_alp02", "_DRIFT2", "ax_alp03", "_DRIFT3"))
        self.assertEqual(tune.load_state(self.work, "ks_alpha", "ax_alp03"), {"name_suffix": "_DRIFT3", "x": 2})

    def test_from_the_draft(self):
        tune.save_state(self.work, "ks_alpha", {"limiter": 9000}, tune.DRAFT)
        res = tune.duplicate_tune(self.work, "ks_alpha", tune.DRAFT)
        self.assertEqual(res, {"id": "ax_alp01", "stock": "ks_alpha", "name_suffix": "_MY"})
        self.assertEqual(tune.load_state(self.work, "ks_alpha", "ax_alp01"), {"limiter": 9000, "name_suffix": "_MY"})
        self.assertEqual(tune.load_state(self.work, "ks_alpha", tune.DRAFT), {"limiter": 9000})

    def test_an_absent_draft_or_default_state_copies_an_empty_state(self):
        self.assertEqual(tune.duplicate_tune(self.work, "ks_alpha", tune.DRAFT)["id"], "ax_alp01")
        self.assertEqual(tune.duplicate_tune(self.work, "ks_alpha", None)["name_suffix"], "_MY2")
        self.assertEqual(tune.load_state(self.work, "ks_alpha", "ax_alp02"), {"name_suffix": "_MY2"})

    def test_the_first_modded_car_can_take_the_default_id(self):
        tune.save_state(self.work, "ks_alpha", {"limiter": 9000}, tune.DRAFT)
        res = tune.duplicate_tune(self.work, "ks_alpha", tune.DRAFT, new_id="ax_alpha")
        self.assertEqual(res["id"], "ax_alpha")
        self.assertEqual(tune.load_state(self.work, "ks_alpha"), {"limiter": 9000, "name_suffix": "_MY"})
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_alpha", "tunes")))
        self.assertEqual([t["id"] for t in tune.list_tunes(self.work, "ks_alpha")], ["ax_alpha"])

    def test_the_default_id_is_refused_when_the_default_tune_exists(self):
        for make in (lambda: tune.save_state(self.work, "ks_alpha", {}), lambda: self.build("ks_alpha", "ax_alpha")):
            make()
            with self.assertRaisesRegex(ValueError, "ax_alpha is already a tune of ks_alpha"):
                tune.duplicate_tune(self.work, "ks_alpha", tune.DRAFT, new_id="ax_alpha")
            shutil.rmtree(os.path.join(self.work, "ks_alpha"))

    def test_an_explicit_id(self):
        res = tune.duplicate_tune(self.work, "ks_alpha", None, new_id="ax_alp42", suffix="_X")
        self.assertEqual(res, {"id": "ax_alp42", "stock": "ks_alpha", "name_suffix": "_X"})
        self.assertEqual(tune.load_state(self.work, "ks_alpha", "ax_alp42"), {"name_suffix": "_X"})

    def test_the_auto_id_skips_the_mods_folder_when_given(self):
        self.install("ax_alp01")
        self.assertEqual(tune.duplicate_tune(self.work, "ks_alpha", None, mods_dir=self.mods)["id"], "ax_alp02")

    def test_explicit_ids_that_are_used_are_refused(self):
        tune.save_state(self.work, "ks_alpha", {}, "ax_alp01")
        self.install("ax_alp02")
        for bad in ("ax_alp01", "ax_bravo"):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "already used or reserved"):
                tune.duplicate_tune(self.work, "ks_alpha", None, new_id=bad, mods_dir=self.mods)
        with self.assertRaisesRegex(ValueError, "already used or reserved"):
            tune.duplicate_tune(self.work, "ks_alpha", None, new_id="ax_alp02", mods_dir=self.mods)
        self.assertEqual(tune.duplicate_tune(self.work, "ks_alpha", None, new_id="ax_alp02")["id"], "ax_alp02")

    def test_invalid_explicit_ids_are_refused(self):
        for bad in ("ax_alp1", "ax_alpha1", "AX_ALP01", "ax/alp01", "ax\\alp01", "..", "../ax_alp", "ks_alpha", "", 5):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                tune.duplicate_tune(self.work, "ks_alpha", None, new_id=bad)
        self.assertFalse(os.path.exists(self.work))

    def test_the_draft_name_is_reserved_for_a_five_character_stock_id(self):
        self.cars(("ks_ab", "Ab"))
        with self.assertRaisesRegex(ValueError, "already used or reserved"):
            tune.duplicate_tune(self.work, "ks_ab", None, new_id="draft")
        self.assertEqual(tune.duplicate_tune(self.work, "ks_ab", None)["id"], "ax_01")

    def test_suffix_defaults_to_a_unique_one_and_an_explicit_one_is_checked(self):
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_A"})
        self.assertEqual(tune.duplicate_tune(self.work, "ks_alpha", None, suffix="_NEW")["name_suffix"], "_NEW")
        with self.assertRaisesRegex(ValueError, "name suffix already used by ax_alpha"):
            tune.duplicate_tune(self.work, "ks_alpha", None, suffix="_A")
        with self.assertRaisesRegex(ValueError, "name suffix already used by ax_alp01"):
            tune.duplicate_tune(self.work, "ks_alpha", None, suffix="_NEW")

    def test_a_suffix_of_another_stock_car_is_no_collision(self):
        tune.save_state(self.work, "ks_bravo", {"name_suffix": "_A"})
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_Q"})
        self.assertEqual(tune.duplicate_tune(self.work, "ks_alpha", None, suffix="_A")["name_suffix"], "_A")

    def test_an_invalid_explicit_suffix_is_refused(self):
        for bad in ("", "x" * 31, "a\tb", 3):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "name_suffix expects"):
                tune.duplicate_tune(self.work, "ks_alpha", None, suffix=bad)
        self.assertFalse(os.path.exists(self.work))

    def test_an_unknown_source_tune_is_refused(self):
        with self.assertRaisesRegex(ValueError, "ks_alpha has no tune ax_alp09"):
            tune.duplicate_tune(self.work, "ks_alpha", "ax_alp09")
        with self.assertRaises(ValueError):
            tune.duplicate_tune(self.work, "ks_alpha", "../x")
        self.assertFalse(os.path.exists(self.work))

    def test_nothing_is_left_behind_when_validation_fails(self):
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_A", "x": 1})
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_B"}, "ax_alp01")
        before = self.snapshot()
        for kw in ({"new_id": "ax_alp01"}, {"new_id": "bad"}, {"suffix": "_A"}, {"suffix": ""}, {"src": "ax_alp09"}, {"new_id": "ax_alpha"}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                tune.duplicate_tune(self.work, "ks_alpha", kw.pop("src", None), **kw)
            self.assertEqual(self.snapshot(), before)

    def test_a_failing_save_leaves_no_temp_file(self):
        tune.save_state(self.work, "ks_alpha", {"x": 1})
        before = self.snapshot()
        self.patch(os, "replace", mock.Mock(side_effect=OSError("disk full")))
        with self.assertRaises(OSError):
            tune.duplicate_tune(self.work, "ks_alpha", None)
        self.assertEqual(sorted(self.snapshot()[0]), sorted(before[0]))

    def test_exhausted_ids_fail_before_anything_is_written(self):
        for n in range(1, 100):
            self.install("ax_alp%02d" % n)
        with self.assertRaisesRegex(ValueError, "no free tuned car id left"):
            tune.duplicate_tune(self.work, "ks_alpha", None, mods_dir=self.mods)
        self.assertFalse(os.path.exists(self.work))

    def test_the_state_files_are_written_with_lf_only(self):
        tune.duplicate_tune(self.work, "ks_alpha", None)
        with open(tune.state_path(self.work, "ks_alpha", "ax_alp01"), "rb") as f:
            self.assertNotIn(b"\r", f.read())


class TestNewTuneFromDraft(TuneCase):
    def test_the_first_modded_car_takes_the_default_id(self):
        tune.save_state(self.work, "ks_alpha", {"limiter": 9000}, tune.DRAFT)
        res = tune.new_tune_from_draft(self.work, "ks_alpha")
        self.assertEqual(res, {"id": "ax_alpha", "stock": "ks_alpha", "name_suffix": "_MY"})
        self.assertEqual(tune.load_state(self.work, "ks_alpha"), {"limiter": 9000, "name_suffix": "_MY"})
        self.assertEqual(tune.load_state(self.work, "ks_alpha", tune.DRAFT), {"limiter": 9000})
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_alpha", "tunes")))
        self.assertEqual([(t["id"], t["default"]) for t in tune.list_tunes(self.work, "ks_alpha")], [("ax_alpha", True)])

    def test_the_second_one_takes_a_free_id_and_a_counted_suffix(self):
        tune.save_state(self.work, "ks_alpha", {"limiter": 9000}, tune.DRAFT)
        tune.new_tune_from_draft(self.work, "ks_alpha")
        res = tune.new_tune_from_draft(self.work, "ks_alpha")
        self.assertEqual(res, {"id": "ax_alp01", "stock": "ks_alpha", "name_suffix": "_MY2"})
        self.assertEqual(tune.load_state(self.work, "ks_alpha", "ax_alp01"), {"limiter": 9000, "name_suffix": "_MY2"})
        self.assertEqual(tune.new_tune_from_draft(self.work, "ks_alpha")["name_suffix"], "_MY3")

    def test_a_build_of_the_default_id_without_a_state_counts_as_the_default_tune(self):
        self.build("ks_alpha", "ax_alpha")
        self.assertEqual(tune.new_tune_from_draft(self.work, "ks_alpha")["id"], "ax_alp01")

    def test_an_installed_package_of_the_free_ids_is_skipped_when_the_mods_folder_is_given(self):
        tune.new_tune_from_draft(self.work, "ks_alpha", mods_dir=self.mods)
        self.install("ax_alp01")
        self.assertEqual(tune.new_tune_from_draft(self.work, "ks_alpha", mods_dir=self.mods)["id"], "ax_alp02")

    def test_explicit_suffix_and_id_are_passed_on(self):
        res = tune.new_tune_from_draft(self.work, "ks_alpha", suffix="_X", new_id="ax_alp42")
        self.assertEqual(res, {"id": "ax_alp42", "stock": "ks_alpha", "name_suffix": "_X"})
        self.assertEqual(tune.list_tunes(self.work, "ks_alpha")[0]["id"], "ax_alp42")
        self.assertEqual(tune.new_tune_from_draft(self.work, "ks_alpha")["id"], "ax_alpha")

    def test_errors_leave_nothing_behind(self):
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_A"})
        before = sorted(self.files())
        for kw in ({"suffix": "_A"}, {"suffix": ""}, {"new_id": "ax_alpha"}, {"new_id": "bad"}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                tune.new_tune_from_draft(self.work, "ks_alpha", **kw)
            self.assertEqual(sorted(self.files()), before)

    def test_the_draft_stays_unsaved_state_of_the_base_car(self):
        tune.new_tune_from_draft(self.work, "ks_alpha")
        self.assertEqual(tune.list_modded(self.work, self.mods)[0]["id"], "ax_alpha")
        self.assertEqual(tune.load_state(self.work, "ks_alpha", tune.DRAFT), {})


class TestListModded(TuneCase):
    def info(self, car_id, name):
        self.write(tune.stock_info_path(self.work, car_id), {"car_id": car_id, "display_name": name, "brand": "B", "year": 1})

    def test_nothing_without_tunes(self):
        self.extract("ks_alpha")
        self.write(os.path.join(self.work, "backups", "ax_x.kspkg"), b"p", binary=True)
        self.assertEqual(tune.list_modded(self.work, self.mods), [])
        self.assertEqual(tune.list_modded(str(self.d / "nowhere"), self.mods), [])

    def test_two_stock_cars_sorted_by_label(self):
        self.info("ks_alpha", "Zeta Stock")
        self.info("ks_bravo", "Bravo Stock")
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_Z"})
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_A"}, "ax_alp01")
        tune.save_state(self.work, "ks_bravo", {}, "ax_bra01")
        self.build("ks_alpha", "ax_alpha")
        self.build("ks_alpha", "ax_alp01")
        self.install("ax_alp01")
        self.install("ax_bra01")
        self.extract("ks_alpha")
        rows = tune.list_modded(self.work, self.mods)
        self.assertEqual([(r["label"], r["id"], r["stock"], r["name_suffix"], r["default"], r["installed"], r["built"]) for r in rows],
                         [("Bravo Stock_MY", "ax_bra01", "ks_bravo", "_MY", False, True, False),
                          ("Zeta Stock_A", "ax_alp01", "ks_alpha", "_A", False, True, True),
                          ("Zeta Stock_Z", "ax_alpha", "ks_alpha", "_Z", True, False, True)])
        self.assertEqual(set(rows[0]), {"id", "stock", "label", "name_suffix", "default", "installed", "built"})

    def test_a_build_only_default_tune_is_listed_and_built_needs_the_package(self):
        self.build("ks_bravo", "ax_bravo")
        os.makedirs(os.path.join(tune.build_dir(self.work, "ks_alpha"), "ax_alpha"))
        tune.save_state(self.work, "ks_alpha", {})
        rows = {r["id"]: r for r in tune.list_modded(self.work, self.mods)}
        self.assertEqual({k: (v["built"], v["installed"]) for k, v in rows.items()}, {"ax_alpha": (False, False), "ax_bravo": (True, False)})

    def test_label_falls_back_to_the_index_then_the_tested_label_then_the_id(self):
        self.write(tune.cars_index_path(self.work), [{"id": "ks_bravo", "display_name": "Bravo Game"}, {"id": "ks_other", "display_name": "Other Game"}])
        for car_id in ("ks_alpha", "ks_bravo", "ks_other", "ks_zzz"):
            tune.save_state(self.work, car_id, {})
        self.assertEqual({r["stock"]: r["label"] for r in tune.list_modded(self.work, self.mods)},
                         {"ks_alpha": "Alpha_MY", "ks_bravo": "Bravo Game_MY", "ks_other": "Other Game_MY", "ks_zzz": "ks_zzz_MY"})

    def test_an_unreadable_stock_info_does_not_break_the_list(self):
        self.info("ks_alpha", "Alpha Stock")
        self.write(tune.stock_info_path(self.work, "ks_bravo"), '{"car_id": "ks_bravo", "disp')
        self.write(tune.stock_info_path(self.work, "ks_other"), {"car_id": "ks_wrong", "display_name": "X", "brand": "B", "year": 1})
        for car_id in ("ks_alpha", "ks_bravo", "ks_other"):
            tune.save_state(self.work, car_id, {})
        self.assertEqual({r["stock"]: r["label"] for r in tune.list_modded(self.work, self.mods)},
                         {"ks_alpha": "Alpha Stock_MY", "ks_bravo": "Bravo_MY", "ks_other": "ks_other_MY"})

    def test_installed_is_the_exact_package_name(self):
        tune.save_state(self.work, "ks_alpha", {})
        self.write(os.path.join(self.mods, "ax_alpha.txt"), b"x", binary=True)
        self.assertFalse(tune.list_modded(self.work, self.mods)[0]["installed"])

    def test_an_unexpandable_mods_folder_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "cannot expand"):
            tune.list_modded(self.work, "%ACE_TEST_NO_SUCH_VAR%" + os.sep + "m")

    def test_the_draft_is_not_a_modded_car(self):
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_D"}, tune.DRAFT)
        self.assertEqual(tune.list_modded(self.work, self.mods), [])

    def test_a_duplicate_shows_up(self):
        tune.save_state(self.work, "ks_alpha", {"name_suffix": "_A"})
        tune.duplicate_tune(self.work, "ks_alpha", None)
        self.assertEqual([(r["id"], r["name_suffix"]) for r in tune.list_modded(self.work, self.mods)],
                         [("ax_alpha", "_A"), ("ax_alp01", "_A2")])


class TestPerTuneState(CarCase):
    """set / unset / rows / unknown ids on the default tune (tune=None), the draft and a modded car ax01 of the stub car ks_x."""

    def setUp(self):
        super().setUp()
        self.cars(("ks_x", "Car X"))
        self.cat = mini_catalogue(suffix(), limiter())
        self.patch(tune, "load_catalogue", lambda path=None: self.cat)
        tune.save_state(self.work, "ks_x", {"limiter": 8000, "name_suffix": "_D"})
        tune.save_state(self.work, "ks_x", {"limiter": 6000, "name_suffix": "_DR"}, tune.DRAFT)
        tune.save_state(self.work, "ks_x", {"limiter": 9000, "name_suffix": "_M"}, "ax01")

    def states(self):
        return [tune.load_state(self.work, "ks_x", t) for t in (None, tune.DRAFT, "ax01")]

    def test_set_changes_only_the_chosen_tune(self):
        res = tune.set_value(self.work, "ks_x", "limiter", "9500", tune="ax01")
        self.assertEqual(res, {"id": "limiter", "value": 9500, "warnings": []})
        self.assertEqual([s["limiter"] for s in self.states()], [8000, 6000, 9500])
        tune.set_value(self.work, "ks_x", "limiter", "4000", tune=tune.DRAFT)
        self.assertEqual([s["limiter"] for s in self.states()], [8000, 4000, 9500])
        tune.set_value(self.work, "ks_x", "limiter", "7500", tune="ax_x")
        self.assertEqual([s["limiter"] for s in self.states()], [7500, 4000, 9500])
        tune.set_value(self.work, "ks_x", "limiter", "7000")
        self.assertEqual([s["limiter"] for s in self.states()], [7000, 4000, 9500])

    def test_set_with_a_range_warning_and_errors_write_nothing(self):
        self.assertEqual(tune.set_value(self.work, "ks_x", "limiter", "20000", tune="ax01")["warnings"],
                         ["limiter=20000 is outside the suggested range 3000..12000"])
        before = self.states()
        for text, setting in (("fast", "limiter"), ("1", "nope")):
            with self.subTest(setting), self.assertRaises(ValueError):
                tune.set_value(self.work, "ks_x", setting, text, tune="ax01")
        self.assertEqual(self.states(), before)

    def test_unset_removes_from_the_chosen_tune_only(self):
        self.assertEqual(tune.unset_value(self.work, "ks_x", "limiter", tune="ax01"), {"id": "limiter", "removed": True})
        self.assertEqual(self.states(), [{"limiter": 8000, "name_suffix": "_D"}, {"limiter": 6000, "name_suffix": "_DR"}, {"name_suffix": "_M"}])
        self.assertEqual(tune.unset_value(self.work, "ks_x", "limiter", tune="ax01"), {"id": "limiter", "removed": False})
        self.assertEqual(tune.unset_value(self.work, "ks_x", "limiter", tune=tune.DRAFT)["removed"], True)
        self.assertEqual(tune.load_state(self.work, "ks_x"), {"limiter": 8000, "name_suffix": "_D"})
        with self.assertRaisesRegex(ValueError, "unknown setting 'nope'"):
            tune.unset_value(self.work, "ks_x", "nope", tune="ax01")

    def test_rows_show_the_values_of_the_chosen_tune(self):
        values = {t: {r["id"]: (r["value"], r["changed"]) for r in tune.effective_rows(self.work, "ks_x", self.cat, tune=t)} for t in (None, tune.DRAFT, "ax01")}
        self.assertEqual([values[t]["limiter"] for t in (None, tune.DRAFT, "ax01")], [(8000, True), (6000, True), (9000, True)])
        self.assertEqual([values[t]["name_suffix"] for t in (None, tune.DRAFT, "ax01")], [("_D", True), ("_DR", True), ("_M", True)])
        row = tune.effective_row(self.work, "ks_x", "limiter", self.cat, tune="ax01")
        self.assertEqual((row["value"], row["default"], row["changed"]), (9000, 7000, True))
        self.assertEqual(tune.effective_row(self.work, "ks_x", "limiter", self.cat)["value"], 8000)
        self.assertEqual(tune.effective_rows(self.work, "ks_x", self.cat, True, "ax01")[0]["value"], "_M")

    def test_a_tune_without_a_state_shows_the_defaults(self):
        rows = {r["id"]: (r["value"], r["changed"]) for r in tune.effective_rows(self.work, "ks_x", self.cat, tune="ax02")}
        self.assertEqual(rows, {"name_suffix": ("_MY", False), "limiter": (7000, False)})

    def test_unknown_state_ids_and_their_warning_follow_the_tune(self):
        tune.save_state(self.work, "ks_x", {"old_m": 1}, "ax01")
        tune.save_state(self.work, "ks_x", {"old_d": 1})
        self.assertEqual(tune.unknown_state_ids(self.work, "ks_x", self.cat, "ax01"), ["old_m"])
        self.assertEqual(tune.unknown_state_ids(self.work, "ks_x", self.cat), ["old_d"])
        self.assertEqual(tune.unknown_state_ids(self.work, "ks_x", self.cat, tune.DRAFT), [])
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            tune.warn_unknown_state(self.work, "ks_x", self.cat, "ax01")
        self.assertEqual(err.getvalue(), "warning: ignoring unknown setting 'old_m' in the saved state\n")

    def test_the_tune_is_an_optional_trailing_keyword_after_the_old_arguments(self):
        for fn, args in ((tune.set_value, ("ks_x", "limiter", "7000", self.cat)), (tune.unset_value, ("ks_x", "limiter", self.cat)),
                         (tune.unknown_state_ids, ("ks_x", self.cat)), (tune.warn_unknown_state, ("ks_x", self.cat)),
                         (tune.effective_row, ("ks_x", "limiter", self.cat))):
            with self.subTest(fn.__name__), contextlib.redirect_stderr(io.StringIO()):
                fn(self.work, *args, tune=None)
                fn(self.work, *args)
        self.assertEqual(len(tune.effective_rows(self.work, "ks_x", self.cat, False, None)), 2)

    def test_invalid_tune_ids_are_refused_by_every_function_and_write_nothing(self):
        before = self.states()
        calls = (lambda t: tune.set_value(self.work, "ks_x", "limiter", "7000", self.cat, t), lambda t: tune.unset_value(self.work, "ks_x", "limiter", self.cat, t),
                 lambda t: tune.unknown_state_ids(self.work, "ks_x", self.cat, t), lambda t: tune.warn_unknown_state(self.work, "ks_x", self.cat, t),
                 lambda t: tune.effective_rows(self.work, "ks_x", self.cat, tune=t), lambda t: tune.effective_row(self.work, "ks_x", "limiter", self.cat, t))
        for bad in ("ax1", "AX01", "ax0!", "..", "ax/1", "ks_x", "", 5):
            for call in calls:
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    call(bad)
        self.assertEqual(self.states(), before)
        self.assertEqual(sorted(os.listdir(os.path.join(self.work, "ks_x", "tunes"))), ["ax01"])

    def test_the_default_tune_files_stay_where_they_were(self):
        tune.set_value(self.work, "ks_x", "limiter", "7100", tune="ax_x")
        self.assertEqual(sorted(f for f in os.listdir(os.path.join(self.work, "ks_x")) if f.endswith(".json")), ["draft_state.json", "tune_state.json"])


# --------------------------------------------------------------------------------------------- work folder
class TestWorkFolder(Base):
    def test_work_dir_expands_environment_variables(self):
        var = "%ACE_TEST_WORK%" if os.name == "nt" else "$ACE_TEST_WORK"
        with mock.patch.dict(os.environ, {"ACE_TEST_WORK": str(self.d)}):
            self.assertEqual(tune.work_dir(var + os.sep + "w"), os.path.join(str(self.d), "w"))

    def test_work_dir_refuses_an_unexpanded_variable(self):
        with self.assertRaisesRegex(ValueError, "cannot expand the work directory"):
            tune.work_dir("%ACE_TEST_NO_SUCH_VAR%" + os.sep + "w")

    def test_work_dir_makes_the_path_absolute(self):
        self.assertTrue(os.path.isabs(tune.work_dir("relative_work")))

    def test_inside_accepts_children_and_refuses_others(self):
        root = str(self.d)
        self.assertEqual(tune.inside(root, os.path.join(root, "a", "b")), os.path.realpath(os.path.join(root, "a", "b")))
        with self.assertRaisesRegex(ValueError, "is not inside"):
            tune.inside(root, os.path.join(root, "..", "elsewhere"))

    def test_remove_tree_removes_a_subfolder(self):
        self.write(os.path.join(self.work, "a", "f.txt"), "x")
        tune.remove_tree(self.work, os.path.join(self.work, "a"))
        self.assertFalse(os.path.exists(os.path.join(self.work, "a")))

    def test_remove_tree_refuses_the_work_folder_and_outside_paths(self):
        self.write(os.path.join(self.work, "f.txt"), "x")
        with self.assertRaisesRegex(ValueError, "refusing to remove the work directory"):
            tune.remove_tree(self.work, self.work)
        with self.assertRaises(ValueError):
            tune.remove_tree(self.work, str(self.d))
        self.assertTrue(os.path.exists(os.path.join(self.work, "f.txt")))

    def old_layout(self, names=tune.OLD_LAYOUT):
        for name in names:
            if name in ("base", "build"):
                self.write(os.path.join(self.work, name, "f.txt"), name)
            else:
                self.write(os.path.join(self.work, name), "{}")

    def test_migrate_moves_the_old_single_car_layout(self):
        self.old_layout()
        self.write(os.path.join(self.work, "backups", "b.kspkg"), "b")
        moved = tune.migrate_old_layout(self.work, "ks_a")
        self.assertEqual(moved, list(tune.OLD_LAYOUT))
        for name in tune.OLD_LAYOUT:
            self.assertFalse(os.path.exists(os.path.join(self.work, name)), name)
            self.assertTrue(os.path.exists(os.path.join(self.work, "ks_a", name)), name)
        self.assertTrue(os.path.exists(os.path.join(self.work, "backups", "b.kspkg")))
        self.assertTrue(os.path.exists(os.path.join(self.work, "ks_a", "base", "f.txt")))

    def test_migrate_moves_only_what_exists(self):
        self.old_layout(("base", "tune_state.json"))
        self.assertEqual(tune.migrate_old_layout(self.work, "ks_a"), ["base", "tune_state.json"])

    def test_migrate_does_nothing_twice_or_without_a_base(self):
        self.old_layout()
        tune.migrate_old_layout(self.work, "ks_a")
        self.assertEqual(tune.migrate_old_layout(self.work, "ks_a"), [])
        other = os.path.join(self.work, "second")
        self.write(os.path.join(other, "tune_state.json"), "{}")
        self.assertEqual(tune.migrate_old_layout(other, "ks_a"), [])
        self.assertTrue(os.path.exists(os.path.join(other, "tune_state.json")))

    def test_migrate_leaves_a_layout_alone_when_the_car_folder_exists(self):
        self.old_layout()
        os.makedirs(os.path.join(self.work, "ks_a"))
        self.assertEqual(tune.migrate_old_layout(self.work, "ks_a"), [])
        self.assertTrue(os.path.exists(os.path.join(self.work, "base", "f.txt")))

    def test_start_migrates_and_says_so(self):
        self.cars(("ks_a", "A"))
        self.old_layout(("base", "defaults.json"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            work, car_id = tune.start({"work": self.work, "game": os.path.join(self.work, "none.kspkg")})
        self.assertEqual((work, car_id), (os.path.abspath(self.work), "ks_a"))
        self.assertEqual(out.getvalue(), "moved the old single-car layout of %s into %s: base, defaults.json\n"
                         % (os.path.abspath(self.work), os.path.join(os.path.abspath(self.work), "ks_a")))

    def test_start_rejects_an_unknown_car_before_moving_anything(self):
        self.cars(("ks_a", "A"))
        self.old_layout()
        with self.assertRaisesRegex(ValueError, "unknown car 'ks_zzz'"):
            tune.start({"work": self.work, "car": "ks_zzz", "game": os.path.join(self.work, "none.kspkg")})
        self.assertTrue(os.path.exists(os.path.join(self.work, "base")))

    def test_start_refuses_an_unexpanded_work_folder(self):
        self.cars()
        with self.assertRaisesRegex(ValueError, "cannot expand the work directory"):
            tune.start({"work": "%ACE_TEST_NO_SUCH_VAR%" + os.sep + "w"})

    def test_init_reports_a_present_base_without_the_game(self):
        fc = FakeCar(self.work).install(self)
        fc.add("data/x.car", {"engine_path": "x"})
        self.write(tune.stock_loc_path(self.work), "loc")
        self.write(tune.stock_info_path(self.work, "ks_x"), {"car_id": "ks_x", "display_name": "X", "brand": "B", "year": 1, "property_1": "a",
                                                          "property_2": "b", "property_3": "c", "variant_name": ""})
        res = tune.init(self.work, "ks_x", os.path.join(self.work, "none.kspkg"))
        self.assertEqual((res["present"], res["files"], res["stock_loc"], res["stock_info"], res["tyre_files"]),
                         (True, 1, "present", "present", "present"))
        self.assertEqual(res["dir"], fc.car_root)

    def test_init_without_base_and_without_game(self):
        with self.assertRaisesRegex(ValueError, "game package not found"):
            tune.init(self.work, "ks_x", os.path.join(self.work, "none.kspkg"))

    def test_init_extracts_through_a_partial_folder(self):
        game = self.write(os.path.join(self.work, "g.kspkg"), b"x", binary=True)
        seen = []

        def extract(pkg, outdir, prefix=None):
            seen.append((outdir, prefix))
            self.write(os.path.join(outdir, "content", "cars", "ks_x", "data", "x.car"), b"car", binary=True)
        self.patch(kspkg, "cmd_extract", extract)
        self.patch(tune, "ensure_stock_loc", lambda work, game: "written")
        self.patch(tune, "write_stock_info", lambda work, car_id, game: "written")
        self.patch(tune, "ensure_tyre_files", lambda work, car_id, game: "present")
        res = tune.init(self.work, "ks_x", game)
        self.assertEqual((res["present"], res["files"], res["bytes"]), (False, 1, 3))
        self.assertEqual(seen, [(tune.base_dir(self.work, "ks_x") + ".partial", "content\\cars\\ks_x")])
        self.assertTrue(os.path.isfile(os.path.join(tune.base_dir(self.work, "ks_x"), "content", "cars", "ks_x", "data", "x.car")))
        self.assertFalse(os.path.exists(tune.base_dir(self.work, "ks_x") + ".partial"))

    def test_init_with_a_package_that_lacks_the_car_leaves_no_partial_folder(self):
        game = self.write(os.path.join(self.work, "g.kspkg"), b"x", binary=True)
        self.patch(kspkg, "cmd_extract", lambda pkg, outdir, prefix=None: os.makedirs(outdir))
        with self.assertRaisesRegex(ValueError, "ks_x not found in"):
            tune.init(self.work, "ks_x", game)
        self.assertFalse(os.path.exists(tune.base_dir(self.work, "ks_x") + ".partial"))
        self.assertFalse(os.path.exists(tune.base_dir(self.work, "ks_x")))


# --------------------------------------------------------------------------------------------- apply
class TestApply(CarCase):
    def setUp(self):
        super().setUp()
        self.cars(("ks_x", "Car X"))
        self.stock_info()
        self.calls = []
        self.patch(clone_car, "build", self.build)
        self.patch(kspkg, "cmd_pack", self.pack)
        self.patch(tune, "ensure_stock_loc", lambda work, game=None: "present")
        self.game = os.path.join(self.work, "no_game.kspkg")
        self.notes = ["note: from build"]
        self.build_error = None
        self.pack_error = None
        self.patch(os, "rename", self.rename)

    def rename(self, src, dst):
        """os.rename that also moves the stub contents of the files below src, like the files themselves."""
        old, new = self.fc.key(src), self.fc.key(dst)
        moved = [k for k in self.fc.store if k.startswith(old + os.sep)]
        REAL_RENAME(src, dst)
        self.fc.store.update({new + k[len(old):]: self.fc.store.pop(k) for k in moved})

    def build(self, car_dir, new_id, out_dir, name, year, brand, variant, stock_loc, props, pack=True):
        self.calls.append(("build", car_dir, new_id, out_dir, name, year, brand, variant, stock_loc, props, pack))
        if self.build_error:
            self.write(os.path.join(out_dir, "content", "cars", new_id, "partial.bin"), b"half", binary=True)
            raise self.build_error
        print("progress noise of the clone")
        self.fc.clone_into(out_dir, new_id)
        return list(self.notes)

    def pack(self, indir, pkg):
        self.calls.append(("pack", indir, pkg))
        if self.pack_error:
            raise self.pack_error
        with open(pkg, "wb") as f:
            f.write(b"PKG-NEW")

    def settings(self, *more):
        return mini_catalogue(*metas(), *more)

    def apply(self, cat, state=None, **kw):
        if state is not None:
            tune.save_state(self.work, "ks_x", state)
        kw.setdefault("install", False)
        return tune.apply(self.work, "ks_x", catalogue=cat, game=self.game, **kw)

    def built(self, res, rel):
        return self.fc.store[self.fc.key(os.path.join(res["build_dir"], "content", "cars", res["new_id"], *rel.split("/")))]

    def test_without_changes_nothing_is_applied_and_the_build_gets_the_stock_data(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            res = self.apply(self.settings(limiter()))
        self.assertEqual(out.getvalue(), "")
        self.assertEqual((res["new_id"], res["applied"], res["notes"], res["installed"], res["backup"], res["size"]),
                         ("ax_x", [], ["note: from build"], None, None, 7))
        build = self.calls[0]
        self.assertEqual(build[1:], (self.fc.car_root, "ax_x", os.path.join(self.work, "ks_x", "build", "ax_x.partial"), "Car X_MY", 1999, "Brand", "Base",
                                     None, {"property_1": "P1", "property_2": "P2", "property_3": "P3"}, False))
        part = res["build_dir"] + ".partial"
        self.assertEqual(self.calls[1], ("pack", part, os.path.join(part, "ax_x.kspkg")))
        self.assertEqual(res["package"], os.path.join(res["build_dir"], "ax_x.kspkg"))

    def test_build_and_pack_output_stays_out_of_stdout(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.apply(self.settings())
        self.assertEqual(out.getvalue(), "")

    def test_custom_new_id(self):
        res = self.apply(self.settings(), new_id="ax_y")
        self.assertEqual((res["new_id"], self.calls[0][2]), ("ax_y", "ax_y"))

    def test_name_suffix_and_variant_reach_the_build(self):
        self.apply(self.settings(), {"name_suffix": "_TUNED", "variant_name": "My Variant"})
        self.assertEqual((self.calls[0][4], self.calls[0][7]), ("Car X_TUNED", "My Variant"))

    def test_meta_changes_are_listed_with_the_file_they_land_in(self):
        res = self.apply(self.settings(), {"name_suffix": "_TUNED", "variant_name": "My Variant"})
        self.assertEqual([(a["id"], a["old"], a["new"], a["files"]) for a in res["applied"]],
                         [("name_suffix", "_MY", "_TUNED", ["ax_x.moddedcarcontent"]),
                          ("variant_name", "Base", "My Variant", ["uiresources/localization/en.cars.loc"])])

    def test_a_changed_value_is_written_into_every_resolved_copy_of_the_build_only(self):
        before = {k: json.dumps(v, sort_keys=True) for k, v in self.fc.store.items()}
        res = self.apply(self.settings(limiter()), {"limiter": 8000})
        self.assertEqual(self.built(res, "data/engine.carengine")["limiter"], 8000)
        self.assertEqual(self.built(res, "data/x.car")["engine"]["limiter"], 8000)
        self.assertEqual({k: json.dumps(v, sort_keys=True) for k, v in self.fc.store.items() if k in before}, before)
        self.assertTrue(all(p.startswith(self.fc.key(res["build_dir"])) for p in self.fc.saved))
        item = [a for a in res["applied"] if a["id"] == "limiter"][0]
        self.assertEqual((item["old"], item["new"], item["files"]), (7000, 8000, ["data/engine.carengine", "data/x.car"]))

    def test_unchanged_settings_are_not_written(self):
        res = self.apply(self.settings(limiter(), mini_setting("m", targets=[("@engine", "minimum")])), {"m": 900.0})
        self.assertEqual([a["id"] for a in res["applied"]], ["m"])
        self.assertEqual(len(self.fc.saved), 1)

    def test_state_equal_to_the_default_is_not_a_change(self):
        res = self.apply(self.settings(limiter()), {"limiter": 7000, "name_suffix": "_MY"})
        self.assertEqual((res["applied"], self.fc.saved), ([], []))

    def test_floats_are_written_as_f32_with_the_short_text(self):
        res = self.apply(self.settings(mini_setting("f", targets=[("@engine", "minimum")])), {"f": 1.1})
        v = self.built(res, "data/engine.carengine")["minimum"]
        self.assertIsInstance(v, car_json.F32)
        self.assertEqual(v.text, "1.1")

    def test_an_optional_copy_that_does_not_resolve_is_skipped(self):
        s = mini_setting("o", targets=[("@engine", "minimum"), ("@car", "nothere.deeper", True)])
        res = self.apply(self.settings(s), {"o": 5.0})
        self.assertEqual([a["files"] for a in res["applied"]], [["data/engine.carengine"]])

    def test_a_missing_last_field_is_created(self):
        res = self.apply(self.settings(mini_setting("z", targets=[("@engine", "nothere")])), {"z": 2.0})
        self.assertEqual(self.built(res, "data/engine.carengine")["nothere"], 2.0)

    def test_create_missing_creates_the_objects_on_the_way(self):
        s = mini_setting("arb", targets=[("@car", "suspensions.arbFront.stiffness")], create_missing=True)
        res = self.apply(self.settings(s), {"arb": 1000.0})
        self.assertEqual(self.built(res, "data/x.car")["suspensions"], {"arbFront": {"stiffness": 1000.0}})

    def test_curve_scale_multiplies_every_point_value(self):
        s = mini_setting("ps", kind="curve_scale", default=1.0, curve_from={"file": "@engine", "path": "powerCurve"}, targets=[])
        res = self.apply(self.settings(s), {"ps": 1.5})
        self.assertEqual(self.built(res, "data/power.curve")["points"], [{"value": 1.5}, {"value": 4.5}, {"x": 5}])
        self.assertEqual([a["files"] for a in res["applied"] if a["id"] == "ps"], [["data/power.curve"]])
        self.assertEqual(self.fc.store[self.fc.key(os.path.join(self.fc.car_root, "data", "power.curve"))]["points"][0], {"value": 1.0})

    def flag(self, **kw):
        return mini_setting("aids", kind="flag", type="bool", value=0, targets=[
            ("@car", "performance_modes[*].electronics_settings.tc1", True), ("@car", "performance_modes[*].electronics_settings.tc2", True),
            ("@setup", "electronics.tc1", True)], **kw)

    def test_flag_writes_its_value_into_all_resolved_copies_and_skips_absent_zero_fields(self):
        res = self.apply(self.settings(self.flag()), {"aids": True})
        modes = self.built(res, "data/x.car")["performance_modes"]
        self.assertEqual([m["electronics_settings"] for m in modes], [{"tc1": 0, "esc": 2}, {"tc1": 0, "tc2": 0}])
        self.assertEqual(self.built(res, "data/setup.carsetup")["electronics"]["tc1"], 0)
        item = [a for a in res["applied"] if a["id"] == "aids"][0]
        self.assertEqual((item["old"], item["new"], sorted(item["files"])), (False, True, ["data/setup.carsetup", "data/x.car"]))

    def test_flag_that_is_off_writes_nothing(self):
        res = self.apply(self.settings(self.flag()), {"aids": False})
        self.assertEqual((res["applied"], self.fc.saved), ([], []))

    def test_flag_wins_over_a_value_on_the_same_field(self):
        value = mini_setting("tc", type="int", targets=[("@setup", "electronics.tc1")])
        res = self.apply(self.settings(self.flag(), value), {"aids": True, "tc": 7})
        self.assertEqual(self.built(res, "data/setup.carsetup")["electronics"]["tc1"], 0)

    def test_a_flag_with_a_non_zero_value_creates_absent_fields(self):
        flag = mini_setting("on", kind="flag", type="bool", value=5, targets=[("@setup", "electronics.nothere", True)])
        res = self.apply(self.settings(flag), {"on": True})
        self.assertEqual(self.built(res, "data/setup.carsetup")["electronics"]["nothere"], 5)

    def test_unknown_state_ids_do_not_stop_apply(self):
        res = self.apply(self.settings(limiter()), {"old_id": 1, "limiter": 8000})
        self.assertEqual([a["id"] for a in res["applied"]], ["limiter"])
        self.assertEqual(tune.load_state(self.work, "ks_x")["old_id"], 1)

    def test_changed_setting_that_is_not_applicable_is_refused_before_building(self):
        with self.assertRaisesRegex(ValueError, r"cannot apply the changed setting\(s\), not applicable to ks_x: deep \(@engine q.r: missing field 'q'\)"):
            self.apply(self.settings(mini_setting("deep", targets=[("@engine", "q.r")])), {"deep": 1.0})
        self.assertEqual(self.calls, [])

    def test_unchanged_setting_that_is_not_applicable_does_not_matter(self):
        self.apply(self.settings(mini_setting("deep", targets=[("@engine", "q.r")])))
        self.assertEqual(len(self.calls), 2)

    def test_no_base_car(self):
        with self.assertRaisesRegex(ValueError, "no base car in .*, run init first"):
            tune.apply(os.path.join(self.work, "elsewhere"), "ks_x", catalogue=self.settings(), install=False, game=self.game)

    def test_new_id_must_have_the_length_of_the_old_one(self):
        with self.assertRaisesRegex(ValueError, "must have exactly 4"):
            self.apply(self.settings(), new_id="ax_xy")
        self.assertEqual(self.calls, [])

    def test_new_id_must_differ_and_use_plain_characters(self):
        for bad, message in (("ks_x", "equals the old id"), ("AX_X", "may only contain")):
            with self.subTest(bad):
                with self.assertRaisesRegex(ValueError, message):
                    self.apply(self.settings(), new_id=bad)

    def test_other_car_than_the_default_needs_its_stock_info(self):
        self.cars(("ks_a", "Other"), ("ks_x", "Car X"))
        os.remove(tune.stock_info_path(self.work, "ks_x"))
        with self.assertRaisesRegex(ValueError, "stock info missing, run init with the game installed"):
            self.apply(self.settings())

    def test_default_car_without_stock_info_falls_back_to_the_preset_name_and_clone_defaults(self):
        os.remove(tune.stock_info_path(self.work, "ks_x"))
        self.apply(self.settings())
        build = self.calls[0]
        self.assertEqual((build[4], build[5], build[6], build[7], build[9]),
                         ("Brand Name_MY", tune.CLONE_YEAR, tune.CLONE_BRAND, "Brand Name", {"property_1": None, "property_2": None, "property_3": None}))

    def test_stock_localization_is_passed_on_when_present(self):
        self.write(tune.stock_loc_path(self.work), b"ks_x_preset_base=Base\r\n", binary=True)
        self.apply(self.settings())
        self.assertEqual(self.calls[0][8], tune.stock_loc_path(self.work))

    def test_a_failing_self_check_becomes_an_error_with_the_log(self):
        def failing(*a, **k):
            print("self-check (a) old id in names: 1 FOUND")
            raise ValueError("self-check failed (see the lines above)")
        self.patch(clone_car, "build", failing)
        with self.assertRaisesRegex(ValueError, "clone self-check failed:\nself-check \\(a\\) old id in names: 1 FOUND"):
            self.apply(self.settings())

    def test_a_leftover_build_of_the_same_id_is_replaced(self):
        old = self.write(os.path.join(self.work, "ks_x", "build", "ax_x", "leftover.txt"), "old")
        res = self.apply(self.settings())
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.isfile(res["package"]))

    def test_a_stale_partial_build_is_removed_at_the_start(self):
        stale = self.write(os.path.join(self.work, "ks_x", "build", "ax_x.partial", "stale.txt"), "old")
        self.apply(self.settings())
        self.assertFalse(os.path.exists(stale))
        self.assertEqual(os.listdir(os.path.join(self.work, "ks_x", "build")), ["ax_x"])

    def test_a_failed_build_leaves_only_the_partial_folder_and_the_next_run_removes_it(self):
        builds = os.path.join(self.work, "ks_x", "build")
        self.apply(self.settings())
        self.build_error = ValueError("disk full")
        with self.assertRaises(ValueError):
            self.apply(self.settings())
        self.assertEqual(sorted(os.listdir(builds)), ["ax_x", "ax_x.partial"])
        self.build_error = None
        self.apply(self.settings())
        self.assertEqual(os.listdir(builds), ["ax_x"])

    def test_other_builds_are_left_alone(self):
        other = self.write(os.path.join(self.work, "ks_x", "build", "ax_other", "keep.txt"), "keep")
        self.apply(self.settings())
        self.assertTrue(os.path.exists(other))

    def test_install_copies_the_package_and_reports_no_backup_the_first_time(self):
        mods = str(self.d / "mods")
        res = self.apply(self.settings(), install=True, mods_dir=mods)
        self.assertEqual((res["installed"], res["backup"]), (os.path.join(os.path.abspath(mods), "ax_x.kspkg"), None))
        with open(res["installed"], "rb") as f:
            self.assertEqual(f.read(), b"PKG-NEW")

    def test_install_backs_up_the_previous_package(self):
        mods = str(self.d / "mods")
        self.write(os.path.join(mods, "ax_x.kspkg"), b"OLD PACKAGE", binary=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            res = self.apply(self.settings(), install=True, mods_dir=mods)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(os.path.dirname(res["backup"]), os.path.join(self.work, "backups"))
        self.assertRegex(os.path.basename(res["backup"]), r"^ax_x_\d{8}_\d{6}\.kspkg$")
        with open(res["backup"], "rb") as f:
            self.assertEqual(f.read(), b"OLD PACKAGE")
        with open(res["installed"], "rb") as f:
            self.assertEqual(f.read(), b"PKG-NEW")

    def test_the_backup_is_the_path_install_returns(self):
        mods, seen = str(self.d / "mods"), []

        def install(pkg, mods_dir, backups):
            seen.append((pkg, mods_dir, backups))
            return "elsewhere" + os.sep + "backup.kspkg"
        self.patch(clone_car, "install", install)
        res = self.apply(self.settings(), install=True, mods_dir=mods)
        self.assertEqual(res["backup"], "elsewhere" + os.sep + "backup.kspkg")
        self.assertEqual(seen, [(res["package"], os.path.abspath(mods), os.path.join(self.work, "backups"))])
        self.assertEqual(res["installed"], os.path.join(os.path.abspath(mods), "ax_x.kspkg"))

    def test_an_unexpandable_mods_folder_is_an_error_before_anything_is_built(self):
        with self.assertRaisesRegex(ValueError, "cannot expand"):
            self.apply(self.settings(), install=True, mods_dir="%ACE_TEST_NO_SUCH_VAR%" + os.sep + "m")
        self.assertEqual(self.calls, [])
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "build")))

    def test_without_install_the_mods_folder_is_not_touched(self):
        mods = self.d / "mods"
        self.apply(self.settings(), install=False, mods_dir=str(mods))
        self.assertFalse(mods.exists())

    def test_the_result_names_the_tune_and_its_suffix(self):
        res = self.apply(self.settings(), {"name_suffix": "_TUNED"})
        self.assertEqual((res["tune"], res["new_id"], res["name_suffix"]), ("ax_x", "ax_x", "_TUNED"))
        self.assertEqual(self.apply(self.settings())["name_suffix"], "_TUNED")

    def modded(self, state, tune_id="ax01"):
        tune.save_state(self.work, "ks_x", state, tune_id)

    def test_a_modded_car_builds_under_its_id_with_its_suffix_and_its_state_only(self):
        self.modded({"limiter": 8000, "name_suffix": "_DRIFT"})
        tune.save_state(self.work, "ks_x", {"limiter": 9500, "name_suffix": "_MY"})
        res = self.apply(self.settings(limiter()), new_id="ax01")
        self.assertEqual((res["tune"], res["new_id"], res["name_suffix"]), ("ax01", "ax01", "_DRIFT"))
        self.assertEqual((res["build_dir"], res["package"]), (os.path.join(self.work, "ks_x", "build", "ax01"),
                                                             os.path.join(self.work, "ks_x", "build", "ax01", "ax01.kspkg")))
        self.assertEqual((self.calls[0][2], self.calls[0][4]), ("ax01", "Car X_DRIFT"))
        self.assertEqual(self.built(res, "data/engine.carengine")["limiter"], 8000)
        self.assertEqual(self.built(res, "data/x.car")["engine"]["limiter"], 8000)
        self.assertEqual([(a["id"], a["new"]) for a in res["applied"]], [("name_suffix", "_DRIFT"), ("limiter", 8000)])
        self.assertEqual(os.listdir(os.path.join(self.work, "ks_x", "build")), ["ax01"])

    def test_building_a_modded_car_leaves_the_default_tune_and_the_draft_alone(self):
        self.modded({"limiter": 8000, "name_suffix": "_DRIFT"})
        tune.save_state(self.work, "ks_x", {"limiter": 9500}, tune.DRAFT)
        before = {n: tune.load_state(self.work, "ks_x", t) for n, t in (("default", None), ("draft", tune.DRAFT), ("ax01", "ax01"))}
        self.apply(self.settings(limiter()), new_id="ax01")
        self.assertEqual({n: tune.load_state(self.work, "ks_x", t) for n, t in (("default", None), ("draft", tune.DRAFT), ("ax01", "ax01"))}, before)
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x")))

    def test_each_tune_builds_its_own_values(self):
        self.modded({"limiter": 8000, "name_suffix": "_A"})
        self.modded({"limiter": 9000, "name_suffix": "_B"}, "ax02")
        first, second = (self.apply(self.settings(limiter()), new_id=t) for t in ("ax01", "ax02"))
        self.assertEqual([self.built(r, "data/engine.carengine")["limiter"] for r in (first, second)], [8000, 9000])
        self.assertEqual([c[4] for c in self.calls if c[0] == "build"], ["Car X_A", "Car X_B"])

    def test_a_modded_car_is_installed_under_its_id(self):
        self.modded({"name_suffix": "_DRIFT"})
        mods = str(self.d / "mods")
        res = self.apply(self.settings(), new_id="ax01", install=True, mods_dir=mods)
        self.assertEqual(res["installed"], os.path.join(os.path.abspath(mods), "ax01.kspkg"))

    def test_a_name_suffix_used_by_another_tune_is_refused_before_building(self):
        self.modded({"name_suffix": "_SAME"})
        tune.save_state(self.work, "ks_x", {"name_suffix": "_SAME"})
        with self.assertRaisesRegex(ValueError, "^name suffix _SAME is already used by ax_x$"):
            self.apply(self.settings(), new_id="ax01")
        with self.assertRaisesRegex(ValueError, "^name suffix _SAME is already used by ax01$"):
            self.apply(self.settings())
        self.assertEqual(self.calls, [])
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "build")))

    def test_the_suffix_of_another_stock_car_or_of_the_tune_itself_is_no_collision(self):
        self.cars(("ks_x", "Car X"), ("ks_y", "Car Y"))
        tune.save_state(self.work, "ks_y", {"name_suffix": "_SAME"})
        self.modded({"name_suffix": "_SAME"})
        self.assertEqual(self.apply(self.settings(), new_id="ax01")["name_suffix"], "_SAME")

    def test_the_default_suffix_of_a_tune_without_one_collides_too(self):
        self.modded({"limiter": 8000})
        tune.save_state(self.work, "ks_x", {})
        with self.assertRaisesRegex(ValueError, "name suffix _MY is already used by ax_x"):
            self.apply(self.settings(limiter()), new_id="ax01")

    def test_an_id_that_is_not_a_modded_car_is_refused_when_the_stock_car_has_modded_cars(self):
        tune.save_state(self.work, "ks_x", {})
        with self.assertRaisesRegex(ValueError, "^ax02 is not a modded car of ks_x, create it with duplicate first$"):
            self.apply(self.settings(), new_id="ax02")
        self.modded({"name_suffix": "_A"})
        with self.assertRaisesRegex(ValueError, "ax02 is not a modded car of ks_x"):
            self.apply(self.settings(), new_id="ax02")
        self.assertEqual(self.calls, [])
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "build")))
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "tunes", "ax02")))

    def test_the_default_id_is_always_a_tune_and_a_stock_car_without_modded_cars_accepts_any_valid_id(self):
        self.assertEqual(self.apply(self.settings(), new_id="ax_x")["tune"], "ax_x")
        shutil.rmtree(os.path.join(self.work, "ks_x", "build"))
        self.assertEqual(self.apply(self.settings(), new_id="ax_y")["tune"], "ax_y")

    def test_the_tune_id_is_validated_before_any_state_is_read(self):
        self.modded({})
        for bad, message in (("ax_xy", "must have exactly 4"), ("AX01", "may only contain"), ("ks_x", "equals the old id")):
            with self.subTest(bad), self.assertRaisesRegex(ValueError, message):
                self.apply(self.settings(), new_id=bad)

    def tyre_world(self):
        self.fc.add_shared("tyres/slick/s.tyre", {"modelData": {"Dy0": 1.0}})
        self.fc.add("presets/c.compatibletyres", {"physic_compounds": [
            {"front_tyre_data_path": "content/cars/common_phsx/tyres/road/A.tyre", "rear_tyre_data_paths": GAME_SHARED + "tyres\\road\\b.tyre"},
            {"front_tyre_data_path": GAME_SHARED + "tyres\\slick\\s.tyre", "rear_tyre_data_paths": GAME_SHARED + "tyres\\slick\\s.tyre"}]})
        return mini_setting("dy", targets=[("@tyre_front", "modelData.Dy0")])

    def test_a_changed_tyre_value_goes_into_the_cars_own_tyre_file_and_the_references_follow(self):
        s = self.tyre_world()
        self.car["frontTyreCompounds"] = ["CONTENT\\CARS\\COMMON_PHSX\\TYRES\\ROAD\\A.TYRE", GAME_SHARED + "tyres\\slick\\s.tyre"]
        res = self.apply(self.settings(s), {"dy": 1.4})
        own = "data/tyres/ax_x_front.tyre"
        self.assertEqual(tune.plain(self.built(res, own)["modelData"]["Dy0"]), 1.4)
        self.assertEqual(self.built(res, "data/x.car")["frontTyreCompounds"],
                         ["content\\cars\\ax_x\\data\\tyres\\ax_x_front.tyre", GAME_SHARED + "tyres\\slick\\s.tyre"])
        compounds = self.built(res, "presets/c.compatibletyres")["physic_compounds"]
        self.assertEqual(compounds[0]["front_tyre_data_path"], "content\\cars\\ax_x\\data\\tyres\\ax_x_front.tyre")
        self.assertEqual(compounds[0]["rear_tyre_data_paths"], GAME_SHARED + "tyres\\road\\b.tyre")
        self.assertEqual(compounds[1]["front_tyre_data_path"], GAME_SHARED + "tyres\\slick\\s.tyre")
        item = [a for a in res["applied"] if a["id"] == "dy"][0]
        self.assertEqual(item["files"], [own])
        self.assertIn("tyre front: own file content\\cars\\ax_x\\data\\tyres\\ax_x_front.tyre replaces", res["notes"][-1])
        self.assertIn("in 1 .car entry(ies) and 1 compatibletyres entry(ies)", res["notes"][-1])

    def test_a_tyre_file_inside_the_car_folder_is_refused_before_building(self):
        self.fc.add("data/tyres/own.tyre", {"modelData": {"Dy0": 1.0}})
        self.car["frontTyreCompounds"] = [self.fc.game_path("data/tyres/own.tyre")]
        s = mini_setting("dy", targets=[("@tyre_front", "modelData.Dy0")])
        with self.assertRaisesRegex(ValueError, "^@tyre_front: the tyre file is inside the car folder, not supported yet$"):
            self.apply(self.settings(s), {"dy": 1.4})
        self.assertEqual(self.calls, [])
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "build")))

    def test_the_shared_tyre_file_and_the_other_axle_stay_untouched(self):
        s = self.tyre_world()
        res = self.apply(self.settings(s), {"dy": 1.4})
        self.assertEqual(self.fc.store[self.fc.key(os.path.join(self.fc.shared, "tyres", "road", "a.tyre"))]["modelData"]["Dy0"], 1.2)
        self.assertNotIn(self.fc.key(os.path.join(res["build_dir"], "content", "cars", "ax_x", "data", "tyres", "ax_x_rear.tyre")), self.fc.store)
        self.assertEqual(self.built(res, "data/x.car")["rearTyreCompounds"], [GAME_SHARED + "tyres\\road\\b.tyre"])

    def test_both_axles_get_their_own_file_when_both_change(self):
        s = [self.tyre_world(), mini_setting("dyr", targets=[("@tyre_rear", "modelData.Dy0")])]
        res = self.apply(self.settings(*s), {"dy": 1.4, "dyr": 1.3})
        self.assertEqual(tune.plain(self.built(res, "data/tyres/ax_x_front.tyre")["modelData"]["Dy0"]), 1.4)
        self.assertEqual(tune.plain(self.built(res, "data/tyres/ax_x_rear.tyre")["modelData"]["Dy0"]), 1.3)
        self.assertEqual(self.built(res, "data/x.car")["rearTyreCompounds"], ["content\\cars\\ax_x\\data\\tyres\\ax_x_rear.tyre"])

    def test_a_choice_setting_writes_the_text_of_the_choice(self):
        s = mini_setting("th", type="enum", choices=["road", "slick"], targets=[("@tyre_front", "thermalData.thermalPerformanceCurve")],
                         choice_values={"road": GAME_SHARED + "tyres\\road\\tcurve_road.curve", "slick": GAME_SHARED + "tyres\\slick\\tcurve_slick.curve"})
        res = self.apply(self.settings(s), {"th": "slick"})
        self.assertEqual(self.built(res, "data/tyres/ax_x_front.tyre")["thermalData"]["thermalPerformanceCurve"],
                         GAME_SHARED + "tyres\\slick\\tcurve_slick.curve")
        item = [a for a in res["applied"] if a["id"] == "th"][0]
        self.assertEqual((item["old"], item["new"]), ("road", "slick"))

    def test_failed_build_keeps_the_previous_build(self):
        res = self.apply(self.settings())
        self.build_error = ValueError("disk full while copying")
        with self.assertRaisesRegex(ValueError, "disk full"):
            self.apply(self.settings(), new_id=res["new_id"])
        self.assertTrue(os.path.isfile(res["package"]), "the previous package is gone")
        with open(res["package"], "rb") as f:
            self.assertEqual(f.read(), b"PKG-NEW")

    def test_failed_pack_keeps_the_previous_build(self):
        res = self.apply(self.settings())
        self.pack_error = OSError(28, "No space left on device")
        with self.assertRaises(OSError):
            self.apply(self.settings())
        self.assertTrue(os.path.isfile(res["package"]), "the previous package is gone")
        with open(res["package"], "rb") as f:
            self.assertEqual(f.read(), b"PKG-NEW")

    def test_failed_build_does_not_touch_the_installed_package(self):
        mods = str(self.d / "mods")
        installed = self.write(os.path.join(mods, "ax_x.kspkg"), b"INSTALLED", binary=True)
        self.build_error = ValueError("disk full")
        with self.assertRaises(ValueError):
            self.apply(self.settings(), install=True, mods_dir=mods)
        with open(installed, "rb") as f:
            self.assertEqual(f.read(), b"INSTALLED")

    def test_self_check_failure_error_is_not_chained(self):
        def failing(*a, **k):
            raise ValueError("self-check failed (see the lines above)")
        self.patch(clone_car, "build", failing)
        with self.assertRaises(ValueError) as cm:
            self.apply(self.settings())
        not_chained(self, cm.exception)


# --------------------------------------------------------------------------------------------- error chains (R3-009 / R2-006)
class TestErrorChains(Base):
    def test_to_f32_error_is_not_chained(self):
        with self.assertRaises(ValueError) as cm:
            tune.to_f32(1e300)
        not_chained(self, cm.exception)

    def test_coerce_float_error_is_not_chained(self):
        with self.assertRaises(ValueError) as cm:
            tune.coerce(mini_setting("f"), "abc")
        not_chained(self, cm.exception)

    def test_load_msg_read_error_is_not_chained(self):
        with self.assertRaises(ValueError) as cm:
            tune.load_msg(os.path.join(self.work, "missing.car"))
        not_chained(self, cm.exception)

    def test_save_msg_encode_error_is_not_chained(self):
        self.patch(tune, "schema", lambda: {})

        def encode(sch, name, obj):
            raise ValueError("cannot encode")
        self.patch(car_json, "encode_msg", encode)
        with self.assertRaises(ValueError) as cm:
            tune.save_msg(os.path.join(self.work, "x.car"), "CarData", {})
        not_chained(self, cm.exception)

    def test_find_ci_listing_error_is_not_chained(self):
        with self.assertRaises(ValueError) as cm:
            tune.find_ci(os.path.join(self.work, "no_such_folder"), "a/b")
        not_chained(self, cm.exception)

    def test_tyre_found_error_is_not_chained(self):
        os.makedirs(self.work)
        with self.assertRaises(ValueError) as cm:
            tune.tyre_found(self.work, "content\\cars\\common_phsx\\a.tyre")
        not_chained(self, cm.exception)

    def test_the_messages_themselves(self):
        with self.assertRaisesRegex(ValueError, "missing.car: "):
            tune.load_msg(os.path.join(self.work, "missing.car"))
        with self.assertRaisesRegex(ValueError, "a not found in|no_such_folder"):
            tune.find_ci(os.path.join(self.work, "no_such_folder"), "a/b")
        os.makedirs(self.work)
        with self.assertRaisesRegex(ValueError, tune.TYRE_UNAVAILABLE):
            tune.tyre_found(self.work, "content\\x.tyre")


class TestStdoutCapture(Base):
    def test_overlapping_captures_restore_stdout(self):
        real = sys.stdout
        self.addCleanup(setattr, sys, "stdout", real)
        game = self.write(os.path.join(self.work, "g.kspkg"), b"x", binary=True)
        a_in, b_in, a_out = threading.Event(), threading.Event(), threading.Event()
        errors = []

        def extract(pkg, outdir, prefix=None):
            self.write(os.path.join(outdir, "f.txt"), b"d", binary=True)
            if threading.current_thread().name == "A":
                a_in.set()
                b_in.wait(1.5)
            else:
                a_in.wait(1.5)
                b_in.set()
                a_out.wait(1.5)
        self.patch(kspkg, "cmd_extract", extract)

        def run(name, work):
            try:
                tune.read_game_file(work, game, "f.txt")
            except Exception as e:
                errors.append(e)
            if name == "A":
                a_out.set()
        threads = [threading.Thread(target=run, args=(n, os.path.join(self.work, n)), name=n) for n in "AB"]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        stdout_after = sys.stdout
        sys.stdout = real
        self.assertEqual(errors, [])
        self.assertIs(stdout_after, real)

    def test_single_capture_restores_stdout(self):
        real = sys.stdout
        game = self.write(os.path.join(self.work, "g.kspkg"), b"x", binary=True)
        self.patch(kspkg, "cmd_extract", lambda pkg, outdir, prefix=None: self.write(os.path.join(outdir, "f.txt"), b"d", binary=True))
        self.assertEqual(tune.read_game_file(self.work, game, "f.txt"), b"d")
        self.assertIs(sys.stdout, real)


# --------------------------------------------------------------------------------------------- CLI
class TestParseAndTable(unittest.TestCase):
    def test_parse_args_positionals_options_and_switches(self):
        pos, opts = tune.parse_args(["a", "--car", "x", "b", "--hidden", "--work", "w"], ("car", "work"), ("hidden",))
        self.assertEqual((pos, opts), (["a", "b"], {"car": "x", "hidden": True, "work": "w"}))

    def test_parse_args_unknown_option_and_missing_value(self):
        with self.assertRaisesRegex(ValueError, "bad option --bogus"):
            tune.parse_args(["--bogus", "1"], ("car",))
        with self.assertRaisesRegex(ValueError, "--car"):
            tune.parse_args(["--car"], ("car",))
        with self.assertRaisesRegex(ValueError, "bad option --hidden"):
            tune.parse_args(["--hidden"], ("car",))

    def test_table_pads_columns_and_strips_trailing_blanks(self):
        self.assertEqual(tune.table(["a", "bb"], [["x", "yyy"], ["zz", 1]]), "a  | bb\n---+----\nx  | yyy\nzz | 1")

    def test_consistency_text(self):
        self.assertEqual(tune.consistency_text({"targets": [], "consistent": True}), "yes")
        self.assertEqual(tune.consistency_text({"targets": [{"resolved": True, "value": 1}], "consistent": True}), "yes")
        row = {"targets": [{"resolved": True, "value": 1}, {"resolved": False, "value": 5}, {"resolved": True, "value": 2.5}], "consistent": False}
        self.assertEqual(tune.consistency_text(row), "NO (1 / 2.5)")


class TestCommands(CarCase):
    def setUp(self):
        super().setUp()
        self.cars(("ks_x", "Car X"))
        self.stock_info()
        self.cat = mini_catalogue(*metas(), limiter(), mini_setting("m", type="int", targets=[("@engine", "minimum"), ("@car", "engine.minimum", True)]),
                                  mini_setting("deep", targets=[("@engine", "q.r")]))
        self.patch(tune, "load_catalogue", lambda path=None: self.cat)

    def main(self, *argv):
        return self.run_main(*argv, "--work", self.work)

    def test_defaults_prints_the_table_hidden_count_and_writes_defaults_json(self):
        code, out, err = self.main("defaults")
        self.assertEqual((code, err), (0, ""))
        lines = out.splitlines()
        self.assertEqual(lines[0].split(" | ")[0].strip(), "id")
        self.assertIn("limiter", out)
        self.assertNotIn("deep", out.split("hidden")[0])
        self.assertIn("1 hidden for this car (not applicable)", out)
        with open(os.path.join(self.work, "ks_x", "defaults.json"), encoding="utf-8") as f:
            self.assertEqual([r["id"] for r in json.load(f)], ["name_suffix", "variant_name", "limiter", "m"])

    def test_defaults_hidden_lists_each_hidden_setting_with_its_reason(self):
        code, out, err = self.main("defaults", "--hidden")
        self.assertIn("  deep: @engine q.r: missing field 'q'\n", out)

    def test_defaults_lists_settings_whose_copies_differ(self):
        code, out, err = self.main("defaults")
        self.assertIn("copies differ in the stock data (1 setting(s), the default shown is the first required target):\n  m\n"
                      "    @engine minimum = 800\n    @car engine.minimum = 900\n", out)
        self.assertIn("NO (800 / 900)", out)

    def test_set_prints_value_and_warning_and_writes_the_state(self):
        code, out, err = self.main("set", "limiter", "20000")
        self.assertEqual((code, out, err), (0, "limiter = 20000\n", "warning: limiter=20000 is outside the suggested range 3000..12000\n"))
        self.assertEqual(tune.load_state(self.work, "ks_x"), {"limiter": 20000})

    def test_set_name_suffix(self):
        self.assertEqual(self.main("set", "name_suffix", "_Z")[1], "name_suffix = _Z\n")

    def test_set_errors_are_error_lines_with_exit_1(self):
        code, out, err = self.main("set", "limiter", "fast")
        self.assertEqual((code, out, err), (1, "", "error: limiter expects an integer, got 'fast'\n"))
        code, out, err = self.main("set", "nope", "1")
        self.assertEqual((code, out, err), (1, "", "error: unknown setting 'nope'\n"))
        code, out, err = self.main("set", "deep", "1")
        self.assertEqual((code, out), (1, ""))
        self.assertTrue(err.startswith("error: deep is not applicable to ks_x: @engine q.r"))

    def test_unset_prints_what_happened(self):
        self.main("set", "limiter", "8000")
        self.assertEqual(self.main("unset", "limiter")[1], "limiter removed from the state\n")
        self.assertEqual(self.main("unset", "limiter")[1], "limiter was not set\n")

    def test_show_marks_changed_rows_and_hides_non_applicable_ones(self):
        self.main("set", "limiter", "8000")
        code, out, err = self.main("show")
        self.assertEqual((code, err), (0, ""))
        rows = {line.split("|")[1].strip(): [c.strip() for c in line.split("|")] for line in out.splitlines()[2:]}
        self.assertEqual(rows["limiter"], ["*", "limiter", "8000", "7000", ""])
        self.assertEqual(rows["name_suffix"][0:4], ["", "name_suffix", "_MY", "_MY"])
        self.assertNotIn("deep", rows)
        self.assertEqual(out.splitlines()[0].split("|")[1].strip(), "id")

    def test_show_warns_about_unknown_ids_and_keeps_them(self):
        tune.save_state(self.work, "ks_x", {"old": 1})
        code, out, err = self.main("show")
        self.assertEqual(code, 0)
        self.assertIn("warning: ignoring unknown setting 'old' in the saved state", out + err)
        self.assertEqual(tune.load_state(self.work, "ks_x"), {"old": 1})

    def test_unknown_car_is_an_error_line(self):
        code, out, err = self.run_main("show", "--car", "ks_nope", "--work", self.work)
        self.assertEqual((code, out), (1, ""))
        self.assertTrue(err.startswith("error: unknown car 'ks_nope'"))

    def test_untested_car_note_is_printed_by_doc(self):
        self.write(tune.cars_index_path(self.work), [{"id": "ks_x", "display_name": "Car X"}, {"id": "ks_q", "display_name": "Q"}])
        code, out, err = self.run_main("doc", "--car", "ks_q", "--out", str(self.d / "q.md"), "--work", self.work)
        self.assertIn("note: ks_q is not in the tested list; results are unverified", out)
        self.assertEqual(code, 1)
        self.assertIn("no base car", err)

    def test_doc_writes_the_reference_for_the_applicable_settings(self):
        out_file = str(self.d / "sub" / "x.md")
        code, out, err = self.run_main("doc", "--car", "ks_x", "--out", out_file, "--work", self.work)
        self.assertEqual((code, err, out), (0, "", "wrote %s\n" % out_file))
        with open(out_file, encoding="utf-8", newline="") as f:
            text = f.read()
        rows = tune.resolve_defaults(self.work, "ks_x")
        self.assertEqual(text, tune.doc_text("ks_x", "Car X", rows))
        self.assertIn("| `limiter` | L limiter | 7000 |", text)
        self.assertIn("## G\n\nd G\n\n| Variable |", text)
        self.assertNotIn("`deep`", text)
        self.assertIn("## Copies differ in the stock data", text)

    def test_cars_table_and_note(self):
        mods = self.d / "mods"
        self.write(str(mods / "ax_x.kspkg"), b"p", binary=True)
        code, out, err = self.run_main("cars", "--work", self.work, "--mods", str(mods), "--game", os.path.join(self.work, "none.kspkg"))
        lines = out.splitlines()
        self.assertEqual([c.strip() for c in lines[0].split("|")], ["id", "display name", "extracted", "tested", "new id", "installed", "size"])
        self.assertEqual([c.strip() for c in lines[2].split("|")][:6], ["ks_x", "Car X", "yes", "yes", "ax_x", "yes"])
        self.assertRegex(lines[2], r"\d+\.\d MB$")
        self.assertEqual(lines[-1], "note: the game package is not available and there is no car index, only the tested cars are listed")

    def test_apply_is_refused_while_the_game_runs(self):
        self.patch(tune, "game_running", lambda: True)
        built = []
        self.patch(clone_car, "build", lambda *a, **k: built.append(a))
        code, out, err = self.main("apply")
        self.assertEqual((code, out, err, built), (1, "", "error: the game is running, close it first\n", []))
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "build")))

    def test_apply_no_install_is_not_refused_while_the_game_runs(self):
        self.patch(tune, "game_running", lambda: True)
        applied = []
        self.patch(tune, "apply", lambda *a: applied.append(a) or {"new_id": "ax_x", "applied": [], "notes": [], "package": "p.kspkg", "size": 1,
                                                                        "installed": None, "backup": None})
        code, out, err = self.main("apply", "--no-install")
        self.assertEqual((code, err, [a[3] for a in applied]), (0, "", [False]))
        self.assertIn("package: p.kspkg (1 bytes)", out)

    def test_init_is_not_refused_while_the_game_runs(self):
        self.patch(tune, "game_running", lambda: True)
        self.patch(tune, "init", lambda work, car_id, game=None: {"present": True, "dir": "d", "files": 1, "dirs": 0, "bytes": 2, "stock_loc": "present",
                                                                  "stock_info": "present", "tyre_files": "present"})
        code, out, err = self.main("init")
        self.assertEqual((code, err, out.splitlines()[0]), (0, "", "base already present"))

    def test_cars_tested_has_no_note(self):
        code, out, err = self.run_main("cars", "--tested", "--work", self.work, "--game", os.path.join(self.work, "none.kspkg"))
        self.assertNotIn("note:", out)

    def modded_car(self, *argv):
        code, out, err = self.main("duplicate", *argv)
        self.assertEqual((code, err), (0, ""), out)
        return out

    def test_duplicate_prints_the_new_id_and_suffix_and_writes_the_state(self):
        self.main("set", "limiter", "8000")
        code, out, err = self.main("duplicate")
        self.assertEqual((code, out, err), (0, "car: ks_x, new id: ax01\nname suffix: _MY2\n", ""))
        self.assertEqual(tune.load_state(self.work, "ks_x", "ax01"), {"limiter": 8000, "name_suffix": "_MY2"})
        self.assertEqual(tune.load_state(self.work, "ks_x"), {"limiter": 8000})

    def test_duplicate_takes_a_source_tune_the_draft_an_id_and_a_suffix(self):
        self.main("set", "limiter", "8000")
        self.main("set", "name_suffix", "_A")
        self.assertEqual(self.modded_car("--suffix", "_B"), "car: ks_x, new id: ax01\nname suffix: _B\n")
        self.assertEqual(self.modded_car("--tune", "ax01", "--new-id", "ax05"), "car: ks_x, new id: ax05\nname suffix: _B2\n")
        tune.save_state(self.work, "ks_x", {"limiter": 6000}, tune.DRAFT)
        self.assertEqual(self.modded_car("--draft"), "car: ks_x, new id: ax02\nname suffix: _MY\n")
        self.assertEqual(tune.load_state(self.work, "ks_x", "ax02"), {"limiter": 6000, "name_suffix": "_MY"})
        self.assertEqual(tune.load_state(self.work, "ks_x", "ax05")["limiter"], 8000)

    def test_duplicate_mods_folder_packages_take_ids(self):
        mods = self.d / "mods"
        self.write(str(mods / "ax01.kspkg"), b"p", binary=True)
        self.assertIn("new id: ax01\n", self.main("duplicate")[1])
        self.assertIn("new id: ax02\n", self.main("duplicate", "--mods", str(mods))[1])

    def test_duplicate_errors_are_error_lines_and_write_nothing(self):
        self.main("set", "name_suffix", "_A")
        before = sorted(os.listdir(os.path.join(self.work, "ks_x")))
        for argv, message in ((("--tune", "ax09"), "error: ks_x has no tune ax09\n"), (("--tune", "draft"), "error: ks_x has no tune draft\n"),
                              (("--suffix", "_A"), "error: name suffix already used by ax_x\n"), (("--new-id", "ax_x"), "error: ax_x is already a tune of ks_x\n"),
                              (("--suffix", ""), "error: name_suffix expects 1 to 30 characters without control characters\n")):
            with self.subTest(argv):
                self.assertEqual(self.main("duplicate", *argv), (1, "", message))
        code, out, err = self.main("duplicate", "--new-id", "AX01")
        self.assertEqual((code, out), (1, ""))
        self.assertTrue(err.startswith("error: new id 'AX01' may only contain"), err)
        self.assertEqual(sorted(os.listdir(os.path.join(self.work, "ks_x"))), before)

    def test_cars_modded_lists_the_modded_cars(self):
        mods = self.d / "mods"
        self.main("set", "name_suffix", "_A")
        self.modded_car("--suffix", "_B")
        self.write(str(mods / "ax01.kspkg"), b"p", binary=True)
        self.write(os.path.join(tune.build_dir(self.work, "ks_x"), "ax_x", "ax_x.kspkg"), b"p", binary=True)
        code, out, err = self.run_main("cars", "--modded", "--work", self.work, "--mods", str(mods), "--game", os.path.join(self.work, "none.kspkg"))
        self.assertEqual((code, err), (0, ""))
        lines = out.splitlines()
        self.assertEqual([c.strip() for c in lines[0].split("|")], ["id", "stock", "label", "suffix", "installed", "built"])
        self.assertEqual([[c.strip() for c in line.split("|")] for line in lines[2:]],
                         [["ax_x", "ks_x", "Car X_A", "_A", "no", "yes"], ["ax01", "ks_x", "Car X_B", "_B", "yes", "no"]])

    def test_cars_modded_without_modded_cars_prints_only_the_header(self):
        code, out, err = self.run_main("cars", "--modded", "--work", self.work, "--mods", str(self.d / "mods"), "--game", os.path.join(self.work, "none.kspkg"))
        self.assertEqual((code, err, len(out.splitlines())), (0, "", 2))
        self.assertNotIn("note:", out)

    def test_set_unset_and_show_with_a_tune_leave_the_default_tune_alone(self):
        self.main("set", "limiter", "8000")
        self.modded_car()
        self.assertEqual(self.main("set", "limiter", "9000", "--tune", "ax01")[1], "limiter = 9000\n")
        self.assertEqual(tune.load_state(self.work, "ks_x"), {"limiter": 8000})
        self.assertEqual(tune.load_state(self.work, "ks_x", "ax01"), {"limiter": 9000, "name_suffix": "_MY2"})
        shown = {tune_id: {line.split("|")[1].strip(): [c.strip() for c in line.split("|")] for line in self.main("show", *extra)[1].splitlines()[2:]}
                 for tune_id, extra in (("default", ()), ("ax01", ("--tune", "ax01")), ("ax_x", ("--tune", "ax_x")))}
        self.assertEqual(shown["default"]["limiter"], ["*", "limiter", "8000", "7000", ""])
        self.assertEqual(shown["ax01"]["limiter"], ["*", "limiter", "9000", "7000", ""])
        self.assertEqual(shown["ax01"]["name_suffix"][2], "_MY2")
        self.assertEqual(shown["ax_x"], shown["default"])
        self.assertEqual(self.main("unset", "limiter", "--tune", "ax01")[1], "limiter removed from the state\n")
        self.assertEqual(tune.load_state(self.work, "ks_x"), {"limiter": 8000})
        self.assertEqual(tune.load_state(self.work, "ks_x", "ax01"), {"name_suffix": "_MY2"})

    def test_show_with_a_tune_warns_about_its_unknown_ids_only(self):
        self.modded_car()
        tune.save_state(self.work, "ks_x", {"old_m": 1}, "ax01")
        tune.save_state(self.work, "ks_x", {"old_d": 1})
        err = self.main("show", "--tune", "ax01")[2]
        self.assertIn("'old_m'", err)
        self.assertNotIn("old_d", err)

    def test_an_unknown_or_invalid_tune_is_an_error_line_for_every_command(self):
        self.main("set", "limiter", "8000")
        before = sorted(os.listdir(os.path.join(self.work, "ks_x")))
        for argv in (("show",), ("defaults",), ("set", "limiter", "1"), ("unset", "limiter"), ("apply", "--no-install")):
            for bad, message in (("ax09", "error: ks_x has no tune ax09\n"), ("draft", "error: ks_x has no tune draft\n")):
                with self.subTest(argv=argv, bad=bad):
                    self.assertEqual(self.main(*argv, "--tune", bad), (1, "", message))
            with self.subTest(argv=argv, bad="bad"):
                code, out, err = self.main(*argv, "--tune", "bad")
                self.assertEqual((code, out), (1, ""))
                self.assertTrue(err.startswith("error: new id 'bad' has 3 characters"), err)
        self.assertEqual(sorted(os.listdir(os.path.join(self.work, "ks_x"))), before)

    def test_defaults_with_a_tune_prints_the_same_table(self):
        self.modded_car()
        self.assertEqual(self.main("defaults", "--tune", "ax01"), self.main("defaults"))

    def stub_apply(self):
        applied = []
        self.patch(tune, "apply", lambda *a: applied.append(a) or {"new_id": a[2] or "ax_x", "applied": [], "notes": [], "package": "p.kspkg", "size": 1,
                                                                    "installed": None, "backup": None})
        return applied

    def test_apply_with_a_tune_builds_that_tune(self):
        self.modded_car()
        applied = self.stub_apply()
        code, out, err = self.main("apply", "--tune", "ax01", "--no-install")
        self.assertEqual((code, err, [a[2] for a in applied]), (0, "", ["ax01"]))
        self.assertIn("car: ks_x, new id: ax01\n", out)
        self.main("apply", "--tune", "ax_x", "--no-install")
        self.main("apply", "--no-install")
        self.main("apply", "--new-id", "ax07", "--no-install")
        self.assertEqual([a[2] for a in applied], ["ax01", "ax_x", None, "ax07"])

    def test_apply_with_a_tune_and_a_new_id_is_an_error_before_anything_happens(self):
        self.modded_car()
        applied = self.stub_apply()
        self.patch(tune, "game_running", lambda: self.fail("the game check comes after the option check"))
        code, out, err = self.main("apply", "--tune", "ax01", "--new-id", "ax02")
        self.assertEqual((code, out, err, applied), (1, "", "error: --tune and --new-id cannot be combined\n", []))

    def test_apply_warns_about_the_unknown_ids_of_the_tune_it_builds(self):
        self.modded_car()
        tune.save_state(self.work, "ks_x", {"old_m": 1}, "ax01")
        self.stub_apply()
        code, out, err = self.main("apply", "--tune", "ax01", "--no-install")
        self.assertEqual(err, "warning: ignoring unknown setting 'old_m' in the saved state\n")

    def test_show_opens_the_catalogue_once(self):
        self.patch(tune, "load_catalogue", REAL_LOAD_CATALOGUE)
        self.patch(tune, "resolve_defaults", lambda work, car, cat=None, game=None, hidden=False, **_: [
            {"id": s["id"], "applicable": True, "reason": None, "default": tune.zero(s), "unit": s["unit"], "group": s["group"],
             "targets": [], "absent": False, "consistent": True, "copies_differ": False} for s in (cat or tune.load_catalogue())["settings"]])
        opened = []
        real_open = builtins.open

        def spy(file, *a, **k):
            if str(file).endswith("catalogue.json"):
                opened.append(str(file))
            return real_open(file, *a, **k)
        with mock.patch.object(builtins, "open", spy):
            code, out, err = self.run_main("show", "--work", self.work)
        self.assertEqual(code, 0)
        self.assertEqual(len(opened), 1)


class TestGameRunning(unittest.TestCase):
    def running(self, **kw):
        with mock.patch.object(tune.subprocess, "run", **kw) as run:
            return tune.game_running(), run

    def done(self, code, out):
        return mock.Mock(return_value=tune.subprocess.CompletedProcess([], code, stdout=out, stderr=b""))

    def test_the_image_name_is_looked_up_with_tasklist(self):
        found, run = self.running(new=self.done(0, b'"AssettoCorsaEVO.exe","1234","Console","1","9,999 K"\r\n'))
        self.assertTrue(found)
        self.assertEqual(run.call_args[0][0], ["tasklist", "/FI", "IMAGENAME eq AssettoCorsaEVO.exe", "/NH", "/FO", "CSV"])

    def test_no_matching_task_is_not_running(self):
        self.assertFalse(self.running(new=self.done(0, b"INFO: No tasks are running which match the specified criteria.\r\n"))[0])

    def test_a_failing_tasklist_is_not_running(self):
        self.assertFalse(self.running(new=self.done(1, b'"AssettoCorsaEVO.exe"'))[0])

    def test_a_missing_tasklist_is_not_running(self):
        self.assertFalse(self.running(side_effect=FileNotFoundError("tasklist"))[0])


class TestUsageText(unittest.TestCase):
    def usage_lines(self):
        return [line.strip() for line in USAGE.splitlines()[1:]]

    def test_usage_block_is_the_first_paragraph_after_the_title(self):
        self.assertTrue(USAGE.startswith("usage:\n  python tools/tune.py cars"))
        self.assertEqual(len(tune.__doc__.split("\n\n")[0].splitlines()), 1)

    def test_every_usage_line_is_a_command_main_dispatches(self):
        commands = [line.split()[2] for line in self.usage_lines()]
        self.assertEqual(commands, ["cars", "init", "defaults", "set", "unset", "show", "apply", "duplicate", "doc", "tyres", "tyre-sources",
                                    "tyre-new", "tyre-show", "tyre-set", "tyre-unset", "tyre-delete", "garage", "garage-set", "garage-reset", "turbo-donors",
                                    "turbo-add", "turbo-remove", "turbo-kit", "ranges"])
        self.assertEqual(list(tune.COMMANDS), commands)
        for cmd in commands:
            self.assertEqual(tune.COMMANDS[cmd].__name__, "cmd_" + cmd.replace("-", "_"))

    def test_every_documented_option_and_positional_is_accepted_by_the_parser(self):
        class Reached(Exception):
            pass

        def reached(opts):
            raise Reached

        with mock.patch.object(tune, "start", reached), mock.patch.object(tune, "work_arg", reached), mock.patch.object(tune, "game_running", lambda: False):
            for line in self.usage_lines():
                words = line.split()
                cmd = words[2]
                required = line.replace("[", " [").split("[")[0].split()[3:]
                positional = [w for i, w in enumerate(required) if not w.startswith("--") and not (i and required[i - 1].startswith("--"))]
                options = [w for w in required if w.startswith("--")]
                values = ["value%d" % i for i in range(len(positional))] + [x for o in options for x in (o, "x")]
                groups = [g for g in line.replace("]", "[").split("[")[1::2]]
                alternatives = [alt.split() for g in groups for alt in g.split(" | ")]
                for opt in alternatives or [[]]:
                    argv = [cmd] + values + [w if w.startswith("--") else "x" for w in opt]
                    with self.subTest(" ".join(argv)):
                        with mock.patch.object(sys, "argv", ["tune.py"] + argv):
                            with self.assertRaises(Reached):
                                tune.main()


def usage_case(name, argv):
    def test(self):
        with tmp() as d:
            r = run_tool("tune.py", *argv, cwd=d)
        self.assertEqual((r.returncode, r.stdout.strip(), r.stderr), (2, USAGE.strip(), ""))
    test.__name__ = "test_" + name
    return test


class TestCliUsage(unittest.TestCase):
    pass


for _name, _argv in (("no_arguments", []), ("unknown_command", ["frobnicate"]), ("cars_with_a_positional", ["cars", "x"]),
                     ("init_with_a_positional", ["init", "x"]), ("defaults_with_a_positional", ["defaults", "x"]),
                     ("set_with_one_operand", ["set", "limiter"]), ("set_with_three_operands", ["set", "a", "b", "c"]),
                     ("unset_without_operand", ["unset"]), ("unset_with_two_operands", ["unset", "a", "b"]),
                     ("show_with_a_positional", ["show", "x"]), ("apply_with_a_positional", ["apply", "x"]),
                     ("doc_with_a_positional", ["doc", "x"]), ("doc_all_with_car", ["doc", "--all", "--car", "ks_x"]),
                     ("doc_all_with_out", ["doc", "--all", "--out", "f.md"]), ("unknown_option", ["show", "--bogus", "1"]),
                     ("option_without_value", ["show", "--car"]), ("tune_without_value", ["show", "--tune"]),
                     ("cars_modded_with_tested", ["cars", "--modded", "--tested"]), ("duplicate_with_a_positional", ["duplicate", "x"]),
                     ("duplicate_tune_with_draft", ["duplicate", "--tune", "ax01", "--draft"]), ("duplicate_with_all", ["duplicate", "--all"]),
                     ("doc_with_a_tune", ["doc", "--tune", "ax01"]), ("init_with_a_tune", ["init", "--tune", "ax01"]),
                     ("cars_with_a_tune", ["cars", "--tune", "ax01"]), ("show_with_draft", ["show", "--draft"]),
                     ("apply_with_new_id_without_value", ["apply", "--tune", "ax01", "--new-id"])):
    setattr(TestCliUsage, "test_usage_" + _name, usage_case(_name, _argv))


class TestCliRuntimeErrors(unittest.TestCase):
    def test_unknown_car_is_an_error_line_on_stderr_with_exit_1(self):
        with tmp() as d:
            r = run_tool("tune.py", "show", "--car", "ks_no_such_car", "--work", d / "w", cwd=d)
            self.assertEqual((r.returncode, r.stdout), (1, ""))
            self.assertTrue(r.stderr.startswith("error: unknown car 'ks_no_such_car'"), r.stderr)
            self.assertEqual(os.listdir(d), [])

    def test_unknown_setting_is_an_error_line_on_stderr_with_exit_1(self):
        with tmp() as d:
            r = run_tool("tune.py", "unset", "no_such_setting", "--work", d / "w", cwd=d)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (1, "", "error: unknown setting 'no_such_setting'\n"))

    def test_unextracted_car_is_an_error_line_on_stderr_with_exit_1(self):
        with tmp() as d:
            r = run_tool("tune.py", "defaults", "--work", d / "w", cwd=d)
            self.assertEqual((r.returncode, r.stdout), (1, ""))
            self.assertRegex(r.stderr, r"^error: no base car in .*, run init first\n$")

    def test_tune_with_new_id_is_an_error_line_on_stderr_with_exit_1(self):
        with tmp() as d:
            r = run_tool("tune.py", "apply", "--tune", "ax01", "--new-id", "ax02", "--no-install", "--work", d / "w", cwd=d)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (1, "", "error: --tune and --new-id cannot be combined\n"))
            self.assertEqual(os.listdir(d), [])

    def test_unknown_tune_is_an_error_line_on_stderr_with_exit_1(self):
        with tmp() as d:
            r = run_tool("tune.py", "show", "--tune", "ax_zz99", "--work", d / "w", cwd=d)
            self.assertEqual((r.returncode, r.stdout), (1, ""))
            self.assertRegex(r.stderr, r"^error: .*ax_zz99")

    def test_unexpanded_work_folder_is_an_error_line(self):
        with tmp() as d:
            r = run_tool("tune.py", "show", "--work", "%ACE_TEST_NO_SUCH_VAR%/w", cwd=d)
            self.assertEqual((r.returncode, r.stdout), (1, ""))
            self.assertTrue(r.stderr.startswith("error: cannot expand the work directory"), r.stderr)
            self.assertEqual(os.listdir(d), [])


if __name__ == "__main__":
    unittest.main()
