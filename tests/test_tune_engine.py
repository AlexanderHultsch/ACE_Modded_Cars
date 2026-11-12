"""Tests for the engine of tools/tune.py without the game: path parser, field access, coerce, state files, resolving defaults on a stubbed car, apply orchestration, car list, work folder, CLI.

Everything that decodes car files is stubbed (support.FakeCar replaces tune.load_msg / save_msg with in-memory messages, clone_car.build and kspkg.cmd_pack are stubbed for apply); the committed tuner/*.json are read only where a test says so.
"""
import builtins
import contextlib
import io
import json
import os
import sys
import threading
import unittest
from unittest import mock

from support import ROOT, FakeCar, mini_catalogue, mini_setting, run_tool, tmp

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
        code, out, err = self.main("apply", "--no-install")
        self.assertEqual((code, out, err, built), (1, "", "error: the game is running, close it first\n", []))
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "build")))

    def test_init_is_not_refused_while_the_game_runs(self):
        self.patch(tune, "game_running", lambda: True)
        self.patch(tune, "init", lambda work, car_id, game=None: {"present": True, "dir": "d", "files": 1, "dirs": 0, "bytes": 2, "stock_loc": "present",
                                                                  "stock_info": "present", "tyre_files": "present"})
        code, out, err = self.main("init")
        self.assertEqual((code, err, out.splitlines()[0]), (0, "", "base already present"))

    def test_cars_tested_has_no_note(self):
        code, out, err = self.run_main("cars", "--tested", "--work", self.work, "--game", os.path.join(self.work, "none.kspkg"))
        self.assertNotIn("note:", out)

    def test_show_opens_the_catalogue_once(self):
        self.patch(tune, "load_catalogue", REAL_LOAD_CATALOGUE)
        self.patch(tune, "resolve_defaults", lambda work, car, cat=None, game=None, hidden=False: [
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
        with open(ROOT / "tools" / "tune.py", encoding="utf-8") as f:
            src = f.read()
        main_src = src[src.index("def main():"):]
        commands = [line.split()[2] for line in self.usage_lines()]
        self.assertEqual(commands, ["cars", "init", "defaults", "set", "unset", "show", "apply", "doc"])
        for cmd in commands:
            self.assertIn('cmd == "%s"' % cmd, main_src)

    def test_every_documented_option_and_positional_is_accepted_by_the_parser(self):
        class Reached(Exception):
            pass

        def reached(opts):
            raise Reached

        with mock.patch.object(tune, "start", reached):
            for line in self.usage_lines():
                words = line.split()
                cmd = words[2]
                positional = [w for w in line.replace("[", " [").split("[")[0].split()[3:]]
                values = ["value%d" % i for i in range(len(positional))]
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
                     ("option_without_value", ["show", "--car"])):
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

    def test_unexpanded_work_folder_is_an_error_line(self):
        with tmp() as d:
            r = run_tool("tune.py", "show", "--work", "%ACE_TEST_NO_SUCH_VAR%/w", cwd=d)
            self.assertEqual((r.returncode, r.stdout), (1, ""))
            self.assertTrue(r.stderr.startswith("error: cannot expand the work directory"), r.stderr)
            self.assertEqual(os.listdir(d), [])


if __name__ == "__main__":
    unittest.main()
