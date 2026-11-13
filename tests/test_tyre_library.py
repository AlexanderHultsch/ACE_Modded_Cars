"""Tests for the tyre library of tools/tune.py (data layer and CLI): ids and names, the file format in <work>/tyres, source tyres of the extracted cars, values and rows, users and delete.

No game data and no schemas: the cars are synthetic (support.FakeCar replaces tune.load_msg with in-memory messages, one shared store for both fake cars); the CLI is run in-process on those cars, and as a subprocess where nothing decodes a car file.
"""
import contextlib
import io
import json
import os
import sys
import unittest
from unittest import mock

from support import FakeCar, mini_catalogue, mini_setting, run_tool, tmp

import tune

USAGE = tune.__doc__.split("\n\n")[1]
GS = "content\\cars\\common_phsx\\"
ROAD_A, ROAD_B, SLICK_S = GS + "tyres\\road\\a.tyre", GS + "tyres\\road\\b.tyre", GS + "tyres\\slick\\s.tyre"
KEY_AB, KEY_SS = ROAD_A + "|" + ROAD_B, SLICK_S + "|" + SLICK_S
CURVES = {"road": GS + "tyres\\road\\tcurve_road.curve", "slick": GS + "tyres\\slick\\tcurve_slick.curve"}


def tyre_cat():
    return mini_catalogue(
        mini_setting("tyre_dy_front", group="Tyres", unit="mu", min=0.5, max=2.5, targets=[("@tyre_front", "modelData.Dy0")]),
        mini_setting("tyre_dy_rear", group="Tyres", unit="mu", min=0.5, max=2.5, targets=[("@tyre_rear", "modelData.Dy0")]),
        mini_setting("tyre_th_front", group="Tyres", type="enum", choices=["road", "slick"], choice_values=CURVES,
                     targets=[("@tyre_front", "thermalData.thermalPerformanceCurve")]),
        mini_setting("tyre_deep_front", group="Tyres", targets=[("@tyre_front", "modelData.nope.x")]),
        mini_setting("limiter", type="int", targets=[("@engine", "limiter")]))


def tyre_obj(dy, curve="road"):
    return {"modelData": {"Dy0": dy}, "thermalData": {"thermalPerformanceCurve": CURVES[curve]}}


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

    def read(self, tyre_id):
        with open(tune.tyre_path(self.work, tyre_id), "rb") as f:
            return f.read()

    def write_tyre(self, tyre_id, data):
        path = os.path.join(self.work, "tyres", tyre_id + ".json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
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


class World(Base):
    """Two extracted cars. ks_a: road a/b (rear as a string), slick s (rear as a list), a pair with a missing rear file and a
    pair with a file inside the car folder. ks_b: road a/b again (rear as a list, other case and slashes) and slick s, whose
    file ks_b does not have."""

    def setUp(self):
        super().setUp()
        self.a = FakeCar(self.work, "ks_a").install(self)
        self.b = FakeCar(self.work, "ks_b")
        self.b.store = self.a.store
        self.a.add_shared("tyres/road/a.tyre", tyre_obj(1.2))
        self.a.add_shared("tyres/road/b.tyre", {"modelData": {"Dy0": 1.1}})
        self.a.add_shared("tyres/slick/s.tyre", tyre_obj(1.0, "slick"))
        self.a.add("data/tyres/own.tyre", {"modelData": {"Dy0": 0.9}})
        self.a.add("presets/p.compatibletyres", {"physic_compounds": [
            {"front_tyre_data_path": ROAD_A, "rear_tyre_data_paths": ROAD_B},
            {"front_tyre_data_path": SLICK_S, "rear_tyre_data_paths": [SLICK_S, ROAD_B]},
            {"front_tyre_data_path": ROAD_A, "rear_tyre_data_paths": GS + "tyres\\road\\missing.tyre"},
            {"front_tyre_data_path": self.a.game_path("data/tyres/own.tyre"), "rear_tyre_data_paths": ROAD_B},
            {"front_tyre_data_path": ROAD_A},
            {"front_tyre_data_path": ROAD_A, "rear_tyre_data_paths": []}]})
        self.b.add_shared("tyres/road/a.tyre", tyre_obj(1.25))
        self.b.add_shared("tyres/road/b.tyre", {"modelData": {"Dy0": 1.15}})
        self.b.add("presets/q.compatibletyres", {"physic_compounds": [
            {"front_tyre_data_path": "CONTENT/CARS/COMMON_PHSX/TYRES/ROAD/A.TYRE", "rear_tyre_data_paths": [ROAD_B, SLICK_S]},
            {"front_tyre_data_path": SLICK_S, "rear_tyre_data_paths": SLICK_S}]})
        self.cat = tyre_cat()

    def create(self, name="Slick", key=KEY_AB):
        return tune.create_tyre(self.work, name, key)["id"]

    def rows(self, tyre_id):
        return {r["id"]: r for r in tune.tyre_rows(self.work, tyre_id, self.cat)}


class TestIds(Base):
    BAD = ("..", "../x", "a/b", "a\\b", "A", "", "x" * 25, "a b", "a.json", "a\n", "é", None, 5, ["a"])

    def test_the_pattern_is_one_to_24_of_a_z_0_9_and_underscore(self):
        for good in ("a", "x_1", "0", "_", "a" * 24):
            tune.check_tyre_id(good)
        for bad in self.BAD:
            with self.subTest(bad), self.assertRaisesRegex(ValueError, "^bad tyre id "):
                tune.check_tyre_id(bad)

    def test_every_function_that_takes_an_id_checks_it_before_a_path_is_built(self):
        self.write_tyre("x", {"version": 1, "name": "X", "source": {"front": ROAD_A, "rear": ROAD_B}, "values": {}})
        calls = (lambda i: tune.load_tyre(self.work, i), lambda i: tune.rename_tyre(self.work, i, "N"),
                 lambda i: tune.set_tyre_source(self.work, i, KEY_AB), lambda i: tune.set_tyre_value(self.work, i, "tyre_dy_front", "1", tyre_cat()),
                 lambda i: tune.unset_tyre_value(self.work, i, "tyre_dy_front", tyre_cat()), lambda i: tune.reset_tyre(self.work, i),
                 lambda i: tune.tyre_rows(self.work, i, tyre_cat()), lambda i: tune.tyre_users(self.work, i),
                 lambda i: tune.delete_tyre(self.work, i))
        self.patch(tune, "tyres_dir", lambda work: self.fail("a path was built for a bad id"))
        for bad in self.BAD:
            for call in calls:
                with self.subTest(bad), self.assertRaisesRegex(ValueError, "^bad tyre id "):
                    call(bad)

    def test_a_traversal_id_does_not_reach_a_file_outside_the_library(self):
        self.write_tyre("x", {"version": 1, "name": "X", "source": {"front": ROAD_A, "rear": ROAD_B}, "values": {}})
        outside = os.path.join(self.work, "x.json")
        os.replace(os.path.join(self.work, "tyres", "x.json"), outside)
        with self.assertRaisesRegex(ValueError, "^bad tyre id "):
            tune.load_tyre(self.work, "../x")
        with self.assertRaisesRegex(ValueError, "^bad tyre id "):
            tune.delete_tyre(self.work, "../x")
        self.assertTrue(os.path.isfile(outside))

    def test_free_tyre_id_makes_a_slug(self):
        for name, expected in (("Slick Soft", "slick_soft"), ("  Road / Hard!! ", "road_hard"), ("A--B__C", "a_b_c"), ("Tyre 2024", "tyre_2024"),
                               ("", "tyre"), ("  ", "tyre"), ("---", "tyre"), ("Ä Ö", "tyre"), ("Ä x", "x")):
            with self.subTest(name):
                self.assertEqual(tune.free_tyre_id(self.work, name), expected)

    def test_free_tyre_id_cuts_to_24_characters(self):
        self.assertEqual(tune.free_tyre_id(self.work, "a" * 30), "a" * 24)
        self.assertEqual(len(tune.free_tyre_id(self.work, "ab cd " * 10)), 24)
        tune.check_tyre_id(tune.free_tyre_id(self.work, "x" * 100))

    def test_a_taken_id_gets_a_number_and_the_base_is_cut_to_stay_within_24_characters(self):
        for taken in ("slick", "slick2", "a" * 24, "a" * 23 + "2"):
            self.write_tyre(taken, "{}")
        self.assertEqual(tune.free_tyre_id(self.work, "Slick"), "slick3")
        self.assertEqual(tune.free_tyre_id(self.work, "a" * 30), "a" * 23 + "3")
        for n in range(3, 10):
            self.write_tyre("a" * 23 + str(n), "{}")
        self.assertEqual(tune.free_tyre_id(self.work, "a" * 30), "a" * 22 + "10")
        self.write_tyre("a" * 22 + "10", "{}")
        self.assertEqual(tune.free_tyre_id(self.work, "a" * 30), "a" * 22 + "11")

    def test_a_damaged_file_with_the_id_counts_as_taken(self):
        self.write_tyre("tyre", "not json")
        self.assertEqual(tune.free_tyre_id(self.work, ""), "tyre2")


class TestNames(World):
    def test_name_rules(self):
        for bad in ("", "   ", "a\x01b", "a\tb", "a\nb", "a\x7fb", "x" * 41, None, 5):
            with self.subTest(repr(bad)), self.assertRaisesRegex(ValueError, "a tyre name"):
                tune.create_tyre(self.work, bad, KEY_AB)
        self.assertFalse(os.path.exists(os.path.join(self.work, "tyres")))

    def test_the_name_is_stripped_and_40_characters_are_fine(self):
        self.assertEqual(tune.create_tyre(self.work, "  Soft  ", KEY_AB)["name"], "Soft")
        self.assertEqual(tune.create_tyre(self.work, "y" * 40, KEY_AB)["name"], "y" * 40)

    def test_the_name_must_be_unique_ignoring_case(self):
        self.create("Slick")
        for dup in ("Slick", "SLICK", " slick "):
            with self.subTest(dup), self.assertRaisesRegex(ValueError, "^a tyre named 'Slick' exists already"):
                tune.create_tyre(self.work, dup, KEY_AB)
        self.assertEqual([t["id"] for t in tune.list_tyres(self.work)], ["slick"])

    def test_rename_changes_the_name_and_keeps_id_source_and_values(self):
        tid = self.create("Slick")
        tune.set_tyre_value(self.work, tid, "tyre_dy_front", "1.4", self.cat)
        self.assertEqual(tune.rename_tyre(self.work, tid, "Soft"), {"id": "slick", "name": "Soft"})
        t = tune.load_tyre(self.work, "slick")
        self.assertEqual((t["name"], t["source"], t["values"]), ("Soft", {"front": ROAD_A, "rear": ROAD_B}, {"tyre_dy_front": 1.4}))

    def test_rename_to_the_same_name_or_another_case_of_it_is_fine(self):
        tid = self.create("Slick")
        self.assertEqual(tune.rename_tyre(self.work, tid, "Slick")["name"], "Slick")
        self.assertEqual(tune.rename_tyre(self.work, tid, "SLICK")["name"], "SLICK")

    def test_rename_to_the_name_of_another_tyre_is_refused_and_changes_nothing(self):
        tid = self.create("Slick")
        self.create("Soft")
        before = self.read(tid)
        with self.assertRaisesRegex(ValueError, "^a tyre named 'Soft' exists already"):
            tune.rename_tyre(self.work, tid, "soft")
        with self.assertRaisesRegex(ValueError, "a tyre name needs"):
            tune.rename_tyre(self.work, tid, "")
        self.assertEqual(self.read(tid), before)

    def test_rename_of_a_missing_tyre(self):
        with self.assertRaisesRegex(ValueError, "^no tyre 'nope' in the library$"):
            tune.rename_tyre(self.work, "nope", "x")


class TestLibraryFiles(World):
    def test_create_writes_the_documented_file(self):
        res = tune.create_tyre(self.work, "Slick Soft", KEY_AB)
        self.assertEqual(res, {"id": "slick_soft", "name": "Slick Soft", "source": {"front": ROAD_A, "rear": ROAD_B}})
        raw = self.read("slick_soft")
        self.assertNotIn(b"\r", raw)
        self.assertTrue(raw.endswith(b"}\n"))
        self.assertEqual(json.loads(raw), {"version": 1, "name": "Slick Soft", "source": {"front": ROAD_A, "rear": ROAD_B}, "values": {}})
        self.assertEqual(list(json.loads(raw)), ["version", "name", "source", "values"])
        self.assertEqual(os.listdir(os.path.join(self.work, "tyres")), ["slick_soft.json"])

    def test_the_file_is_written_like_a_state_file(self):
        tid = self.create()
        tune.save_state(self.work, "ks_a", {"x": 1})
        with open(tune.state_path(self.work, "ks_a"), "rb") as f:
            state_raw = f.read()
        self.assertEqual(self.read(tid).decode("utf-8"), json.dumps(json.loads(self.read(tid)), indent=2, ensure_ascii=False) + "\n")
        self.assertEqual(state_raw.decode("utf-8"), json.dumps({"x": 1}, indent=2) + "\n")

    def test_the_file_is_written_atomically(self):
        tid = self.create()
        before = self.read(tid)
        self.patch(tune.os, "replace", mock.Mock(side_effect=OSError("disk full")))
        with self.assertRaises(OSError):
            tune.set_tyre_value(self.work, tid, "tyre_dy_front", "1.3", self.cat)
        self.assertEqual(self.read(tid), before)
        self.assertEqual(os.listdir(os.path.join(self.work, "tyres")), ["slick.json"])

    def test_non_ascii_names_are_kept_as_they_are(self):
        res = tune.create_tyre(self.work, "Reifen Größe", KEY_AB)
        self.assertEqual(res["id"], "reifen_gr_e")
        self.assertIn("Größe".encode("utf-8"), self.read(res["id"]))
        self.assertEqual(tune.load_tyre(self.work, res["id"])["name"], "Reifen Größe")

    def test_create_load_list_round_trip(self):
        self.create("Slick")
        t = tune.load_tyre(self.work, "slick")
        self.assertEqual(t, {"version": 1, "name": "Slick", "source": {"front": ROAD_A, "rear": ROAD_B}, "values": {}})
        self.assertEqual(tune.list_tyres(self.work), [{"id": "slick", "name": "Slick", "source": {"front": ROAD_A, "rear": ROAD_B}, "changed": 0}])

    def test_create_never_overwrites(self):
        self.write_tyre("slick", "damaged")
        self.assertEqual(self.create("Slick"), "slick2")
        with open(os.path.join(self.work, "tyres", "slick.json"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "damaged")

    def test_create_with_an_unknown_source_writes_nothing(self):
        for key in ("nope", "", KEY_AB + "x", ROAD_B + "|" + ROAD_A, None):
            with self.subTest(key), self.assertRaisesRegex(ValueError, "^unknown tyre source"):
                tune.create_tyre(self.work, "Slick", key)
        self.assertFalse(os.path.exists(os.path.join(self.work, "tyres")))

    def test_list_is_empty_without_the_folder(self):
        self.assertEqual(tune.list_tyres(self.work), [])
        self.assertEqual(tune.list_tyres(os.path.join(self.work, "none")), [])

    def test_list_sorts_by_name_ignoring_case_and_counts_the_values(self):
        for name in ("gamma", "Beta", "alpha"):
            self.create(name)
        tune.set_tyre_value(self.work, "beta", "tyre_dy_front", "1.4", self.cat)
        tune.set_tyre_value(self.work, "beta", "tyre_dy_rear", "1.3", self.cat)
        self.assertEqual([(t["name"], t["changed"]) for t in tune.list_tyres(self.work)], [("alpha", 0), ("Beta", 2), ("gamma", 0)])

    def test_list_ignores_other_files(self):
        self.create("Slick")
        for n in ("notes.txt", "Upper.json", "bad name.json", "slick.json.tmp"):
            with open(os.path.join(self.work, "tyres", n), "w", encoding="utf-8") as f:
                f.write("x")
        self.assertEqual([t["id"] for t in tune.list_tyres(self.work)], ["slick"])

    def test_a_damaged_file_is_listed_with_its_error_after_the_good_ones(self):
        self.create("Zeta")
        self.write_tyre("broken", "{not json")
        self.write_tyre("aaa", "[]")
        listed = tune.list_tyres(self.work)
        self.assertEqual([t["id"] for t in listed], ["zeta", "aaa", "broken"])
        self.assertEqual(set(listed[1]), {"id", "error"})
        self.assertIn("expected an object", listed[1]["error"])
        self.assertIn("broken.json", listed[2]["error"])

    def test_wrong_shapes_are_errors(self):
        good = {"version": 1, "name": "N", "source": {"front": ROAD_A, "rear": ROAD_B}, "values": {}}
        cases = {"list": [], "no_version": {k: v for k, v in good.items() if k != "version"}, "version_2": dict(good, version=2),
                 "version_true": dict(good, version=True), "version_text": dict(good, version="1"), "name_int": dict(good, name=5),
                 "name_empty": dict(good, name=""), "no_source": {k: v for k, v in good.items() if k != "source"},
                 "source_text": dict(good, source="x"), "source_no_rear": dict(good, source={"front": ROAD_A}),
                 "source_int": dict(good, source={"front": ROAD_A, "rear": 5}), "values_list": dict(good, values=[]),
                 "no_values": {k: v for k, v in good.items() if k != "values"}}
        for tid, data in cases.items():
            self.write_tyre(tid, data)
            with self.subTest(tid):
                with self.assertRaisesRegex(ValueError, tid + r"\.json"):
                    tune.load_tyre(self.work, tid)
        self.assertEqual(sorted(t["id"] for t in tune.list_tyres(self.work)), sorted(cases))
        self.assertTrue(all("error" in t for t in tune.list_tyres(self.work)))

    def test_a_good_file_is_loaded(self):
        self.write_tyre("ok", {"version": 1, "name": "N", "source": {"front": ROAD_A, "rear": ROAD_B}, "values": {"tyre_dy_front": 1.5}})
        self.assertEqual(tune.load_tyre(self.work, "ok")["values"], {"tyre_dy_front": 1.5})

    def test_invalid_json_and_a_byte_order_mark(self):
        self.write_tyre("bad", "{")
        with self.assertRaisesRegex(ValueError, "bad.json"):
            tune.load_tyre(self.work, "bad")
        self.write_tyre("bom", "﻿" + json.dumps({"version": 1, "name": "N", "source": {"front": "f", "rear": "r"}, "values": {}}))
        self.assertEqual(tune.load_tyre(self.work, "bom")["name"], "N")

    def test_a_missing_tyre(self):
        with self.assertRaisesRegex(ValueError, "^no tyre 'nope' in the library$"):
            tune.load_tyre(self.work, "nope")


class TestValues(World):
    def setUp(self):
        super().setUp()
        self.tid = self.create()

    def values(self):
        return tune.load_tyre(self.work, self.tid)["values"]

    def test_set_stores_the_coerced_value_and_returns_it_like_set_value(self):
        res = tune.set_tyre_value(self.work, self.tid, "tyre_dy_front", "1.4", self.cat)
        self.assertEqual(res, {"id": "tyre_dy_front", "value": 1.4, "warnings": []})
        self.assertEqual(self.values(), {"tyre_dy_front": 1.4})
        self.assertIn(b'"tyre_dy_front": 1.4', self.read(self.tid))
        tune.set_tyre_value(self.work, self.tid, "tyre_dy_front", 1.5, self.cat)
        tune.set_tyre_value(self.work, self.tid, "tyre_th_front", "slick", self.cat)
        self.assertEqual(self.values(), {"tyre_dy_front": 1.5, "tyre_th_front": "slick"})

    def test_a_value_outside_the_suggested_range_is_a_warning_and_stored(self):
        res = tune.set_tyre_value(self.work, self.tid, "tyre_dy_front", "9", self.cat)
        self.assertEqual(res["warnings"], ["tyre_dy_front=9.0 is outside the suggested range 0.5..2.5"])
        self.assertEqual(self.values(), {"tyre_dy_front": 9.0})

    def test_coerce_errors_change_nothing(self):
        before = self.read(self.tid)
        for sid, text, message in (("tyre_dy_front", "fast", "expects a number"), ("tyre_dy_front", "nan", "finite"),
                                   ("tyre_dy_front", True, "expects a number"), ("tyre_th_front", "mud", "must be one of"),
                                   ("tyre_th_front", "", "non-empty text")):
            with self.subTest("%s %r" % (sid, text)), self.assertRaisesRegex(ValueError, message):
                tune.set_tyre_value(self.work, self.tid, sid, text, self.cat)
        self.assertEqual(self.read(self.tid), before)

    def test_a_setting_that_is_not_a_tyre_setting_is_refused(self):
        before = self.read(self.tid)
        with self.assertRaisesRegex(ValueError, "^limiter is not a tyre setting$"):
            tune.set_tyre_value(self.work, self.tid, "limiter", "7000", self.cat)
        with self.assertRaisesRegex(ValueError, "^unknown setting 'nope'$"):
            tune.set_tyre_value(self.work, self.tid, "nope", "1", self.cat)
        self.assertEqual(self.read(self.tid), before)

    def test_set_on_a_missing_tyre(self):
        with self.assertRaisesRegex(ValueError, "^no tyre 'nope' in the library$"):
            tune.set_tyre_value(self.work, "nope", "tyre_dy_front", "1", self.cat)

    def test_unset_removes_one_value(self):
        tune.set_tyre_value(self.work, self.tid, "tyre_dy_front", "1.4", self.cat)
        tune.set_tyre_value(self.work, self.tid, "tyre_dy_rear", "1.3", self.cat)
        self.assertEqual(tune.unset_tyre_value(self.work, self.tid, "tyre_dy_front", self.cat), {"id": "tyre_dy_front", "removed": True})
        self.assertEqual(self.values(), {"tyre_dy_rear": 1.3})
        self.assertEqual(tune.unset_tyre_value(self.work, self.tid, "tyre_dy_front", self.cat), {"id": "tyre_dy_front", "removed": False})

    def test_unset_checks_the_setting_only_when_it_is_not_set(self):
        with self.assertRaisesRegex(ValueError, "^limiter is not a tyre setting$"):
            tune.unset_tyre_value(self.work, self.tid, "limiter", self.cat)
        with self.assertRaisesRegex(ValueError, "^unknown setting 'old'$"):
            tune.unset_tyre_value(self.work, self.tid, "old", self.cat)
        self.write_tyre(self.tid, {"version": 1, "name": "Slick", "source": {"front": ROAD_A, "rear": ROAD_B}, "values": {"old": 1}})
        self.assertTrue(tune.unset_tyre_value(self.work, self.tid, "old", self.cat)["removed"])
        self.assertEqual(self.values(), {})

    def test_reset_clears_all_values_and_keeps_name_and_source(self):
        tune.set_tyre_value(self.work, self.tid, "tyre_dy_front", "1.4", self.cat)
        tune.set_tyre_value(self.work, self.tid, "tyre_dy_rear", "1.3", self.cat)
        self.assertEqual(tune.reset_tyre(self.work, self.tid), {"id": "slick", "cleared": 2})
        self.assertEqual(tune.load_tyre(self.work, self.tid), {"version": 1, "name": "Slick", "source": {"front": ROAD_A, "rear": ROAD_B}, "values": {}})
        self.assertEqual(tune.reset_tyre(self.work, self.tid)["cleared"], 0)

    def test_set_source_keeps_the_values(self):
        tune.set_tyre_value(self.work, self.tid, "tyre_dy_front", "1.4", self.cat)
        res = tune.set_tyre_source(self.work, self.tid, KEY_SS)
        self.assertEqual(res, {"id": "slick", "source": {"front": SLICK_S, "rear": SLICK_S}})
        t = tune.load_tyre(self.work, self.tid)
        self.assertEqual((t["name"], t["source"], t["values"]), ("Slick", {"front": SLICK_S, "rear": SLICK_S}, {"tyre_dy_front": 1.4}))

    def test_set_source_with_an_unknown_key_changes_nothing(self):
        before = self.read(self.tid)
        with self.assertRaisesRegex(ValueError, "^unknown tyre source"):
            tune.set_tyre_source(self.work, self.tid, "nope")
        self.assertEqual(self.read(self.tid), before)

    def test_tyre_settings_are_the_ones_with_a_tyre_role(self):
        self.assertEqual([s["id"] for s in tune.tyre_settings(self.cat)], ["tyre_dy_front", "tyre_dy_rear", "tyre_th_front", "tyre_deep_front"])
        self.assertEqual([tune.tyre_axle(s) for s in tune.tyre_settings(self.cat)], ["front", "rear", "front", "front"])

    def test_the_committed_catalogue_has_24_tyre_settings_that_only_target_tyre_files(self):
        cat = tune.load_catalogue()
        found = tune.tyre_settings(cat)
        self.assertEqual(len(found), 24)
        self.assertEqual({s["group"] for s in found}, {"Tyres"})
        for s in found:
            self.assertEqual({t["file"] for t in s["targets"]}, {"@tyre_" + tune.tyre_axle(s)}, s["id"])
            self.assertEqual((s["kind"], s.get("needs"), "curve_from" in s), ("value", None, False), s["id"])
            self.assertTrue(s["id"].endswith("_" + tune.tyre_axle(s)))
        self.assertEqual(sorted(s["id"] for s in cat["settings"] if s["group"] == "Tyres"), sorted(s["id"] for s in found))

    def test_the_committed_catalogue_gives_range_warnings_and_refuses_other_settings(self):
        res = tune.set_tyre_value(self.work, self.tid, "tyre_grip_lateral_front", "9")
        self.assertEqual(res["value"], 9.0)
        self.assertIn("outside the suggested range 0.5..2.5", res["warnings"][0])
        with self.assertRaisesRegex(ValueError, "^name_suffix is not a tyre setting$"):
            tune.set_tyre_value(self.work, self.tid, "name_suffix", "_X")
        with self.assertRaisesRegex(ValueError, "must be one of"):
            tune.set_tyre_value(self.work, self.tid, "tyre_thermal_curve_rear", "mud")
        self.assertEqual(tune.set_tyre_value(self.work, self.tid, "tyre_thermal_curve_rear", "slick")["value"], "slick")


class TestSources(World):
    def test_pairs_are_deduplicated_sorted_and_list_their_cars(self):
        found = tune.list_source_tyres(self.work)
        self.assertEqual(found, [
            {"key": KEY_AB, "front": ROAD_A, "rear": ROAD_B, "label": "tyres\\road\\a + tyres\\road\\b", "cars": ["ks_a", "ks_b"]},
            {"key": KEY_SS, "front": SLICK_S, "rear": SLICK_S, "label": "tyres\\slick\\s", "cars": ["ks_a"]}])

    def test_the_rear_is_the_string_or_the_first_entry_of_the_list(self):
        self.assertEqual([e["rear"] for e in tune.list_source_tyres(self.work)], [ROAD_B, SLICK_S])
        self.assertNotIn(ROAD_B + "|" + ROAD_B, [e["key"] for e in tune.list_source_tyres(self.work)])

    def test_pairs_with_a_missing_file_or_a_file_in_the_car_folder_are_skipped(self):
        keys = [e["key"] for e in tune.list_source_tyres(self.work)]
        self.assertEqual(len(keys), 2)
        self.assertFalse([k for k in keys if "missing" in k or "ks_a" in k or "own" in k])

    def test_a_pair_needs_both_files_in_the_base_of_the_car_that_names_it(self):
        os.remove(os.path.join(self.a.shared, "tyres", "road", "b.tyre"))
        found = {e["key"]: e["cars"] for e in tune.list_source_tyres(self.work)}
        self.assertEqual(found, {KEY_AB: ["ks_b"], KEY_SS: ["ks_a"]})

    def test_the_game_path_case_and_slashes_do_not_matter(self):
        self.assertEqual(tune.list_source_tyres(self.work)[0]["cars"], ["ks_a", "ks_b"])

    def test_an_unreadable_preset_or_car_is_skipped(self):
        self.a.store[self.a.key(os.path.join(self.a.car_root, "presets", "p.compatibletyres"))] = ValueError("truncated")
        self.assertEqual([(e["key"], e["cars"]) for e in tune.list_source_tyres(self.work)], [(KEY_AB, ["ks_b"])])
        os.remove(os.path.join(self.b.car_root, "presets", "q.compatibletyres"))
        os.rmdir(os.path.join(self.b.car_root, "presets"))
        self.assertEqual(tune.list_source_tyres(self.work), [])

    def test_a_folder_without_a_base_car_offers_nothing(self):
        os.makedirs(os.path.join(self.work, "ks_c", "tunes"))
        self.assertEqual(len(tune.list_source_tyres(self.work)), 2)

    def test_nothing_is_extracted_and_the_game_package_is_not_needed(self):
        self.patch(tune.kspkg, "cmd_extract", lambda *a, **k: self.fail("extract"))
        self.patch(tune, "read_game_file", lambda *a, **k: self.fail("game"))
        before = sorted(os.walk(self.work))
        tune.list_source_tyres(self.work)
        self.assertEqual(sorted(os.walk(self.work)), before)

    def test_the_label_adds_the_rear_only_when_it_differs(self):
        self.assertEqual(tune.source_label(ROAD_A, ROAD_A), "tyres\\road\\a")
        self.assertEqual(tune.source_label(ROAD_A, ROAD_B), "tyres\\road\\a + tyres\\road\\b")

    def test_no_work_folder_gives_no_sources(self):
        self.assertEqual(tune.list_source_tyres(os.path.join(self.work, "none")), [])


class TestRows(World):
    def test_defaults_come_from_the_source_files_of_the_axle(self):
        rows = self.rows(self.create())
        self.assertEqual(list(rows), ["tyre_dy_front", "tyre_dy_rear", "tyre_th_front", "tyre_deep_front"])
        self.assertEqual((rows["tyre_dy_front"]["default"], rows["tyre_dy_rear"]["default"], rows["tyre_th_front"]["default"]), (1.2, 1.1, "road"))
        self.assertEqual([(r["axle"], r["value"], r["changed"], r["applicable"]) for r in list(rows.values())[:3]],
                         [("front", 1.2, False, True), ("rear", 1.1, False, True), ("front", "road", False, True)])

    def test_rows_carry_the_fields_a_page_needs(self):
        row = self.rows(self.create())["tyre_th_front"]
        self.assertEqual({k: row[k] for k in ("label", "group", "unit", "type", "kind", "description", "verified", "choices", "reason")},
                         {"label": "L tyre_th_front", "group": "Tyres", "unit": "", "type": "enum", "kind": "value",
                          "description": "d tyre_th_front", "verified": False, "choices": ["road", "slick"], "reason": None})
        dy = self.rows("slick")["tyre_dy_front"]
        self.assertEqual((dy["min"], dy["max"], dy["unit"]), (0.5, 2.5, "mu"))
        self.assertNotIn("choices", dy)

    def test_overrides_are_the_value_and_mark_the_row_changed(self):
        tid = self.create()
        tune.set_tyre_value(self.work, tid, "tyre_dy_front", "1.4", self.cat)
        tune.set_tyre_value(self.work, tid, "tyre_th_front", "slick", self.cat)
        tune.set_tyre_value(self.work, tid, "tyre_dy_rear", "1.1", self.cat)
        rows = self.rows(tid)
        self.assertEqual([(r["value"], r["default"], r["changed"]) for r in list(rows.values())[:3]],
                         [(1.4, 1.2, True), (1.1, 1.1, False), ("slick", "road", True)])

    def test_a_changed_source_changes_the_defaults_and_keeps_the_values(self):
        tid = self.create()
        tune.set_tyre_value(self.work, tid, "tyre_dy_front", "1.4", self.cat)
        tune.set_tyre_source(self.work, tid, KEY_SS)
        row = self.rows(tid)["tyre_dy_front"]
        self.assertEqual((row["default"], row["value"], row["changed"]), (1.0, 1.4, True))
        self.assertEqual(self.rows(tid)["tyre_th_front"]["default"], "slick")

    def test_the_files_are_read_from_a_car_that_offers_the_source(self):
        tid = self.create()
        self.assertEqual(self.rows(tid)["tyre_dy_front"]["default"], 1.2)
        os.remove(os.path.join(self.a.shared, "tyres", "road", "a.tyre"))
        self.assertEqual(self.rows(tid)["tyre_dy_front"]["default"], 1.25)

    def test_a_setting_whose_default_cannot_be_read_is_not_applicable_with_a_reason(self):
        tid = self.create()
        tune.set_tyre_value(self.work, tid, "tyre_dy_front", "1.4", self.cat)
        row = self.rows(tid)["tyre_deep_front"]
        self.assertEqual((row["applicable"], row["default"], row["value"], row["changed"]), (False, None, None, False))
        self.assertEqual(row["reason"], "modelData.nope.x: missing field 'nope'")
        self.assertTrue(self.rows(tid)["tyre_dy_front"]["applicable"])

    def test_an_override_of_an_unreadable_setting_is_kept_in_its_row(self):
        tid = self.create()
        tune.set_tyre_value(self.work, tid, "tyre_deep_front", "2", self.cat)
        row = self.rows(tid)["tyre_deep_front"]
        self.assertEqual((row["applicable"], row["default"], row["value"], row["changed"]), (False, None, 2.0, True))

    def test_a_curve_that_is_not_a_choice_is_not_applicable(self):
        self.a.add_shared("tyres/road/a.tyre", {"modelData": {"Dy0": 1.2}, "thermalData": {"thermalPerformanceCurve": GS + "tyres\\x.curve"}})
        row = self.rows(self.create())["tyre_th_front"]
        self.assertEqual((row["applicable"], row["default"]), (False, None))
        self.assertIn("is not one of the choices of tyre_th_front", row["reason"])

    def test_an_unreadable_source_file_makes_only_its_axle_unsupported(self):
        tid = self.create()
        self.a.store[self.a.key(os.path.join(self.a.shared, "tyres", "road", "a.tyre"))] = ValueError("a.tyre: truncated protobuf")
        rows = self.rows(tid)
        self.assertEqual([(r["id"], r["applicable"]) for r in rows.values()],
                         [("tyre_dy_front", False), ("tyre_dy_rear", True), ("tyre_th_front", False), ("tyre_deep_front", False)])
        self.assertIn("truncated protobuf", rows["tyre_dy_front"]["reason"])

    def test_without_an_extracted_car_that_offers_the_source_it_is_an_error(self):
        tid = self.create("Slick", KEY_SS)
        os.remove(os.path.join(self.a.shared, "tyres", "slick", "s.tyre"))
        with self.assertRaisesRegex(ValueError, "^tyre slick: no extracted car offers its source tyres\\\\slick\\\\s any more"):
            tune.tyre_rows(self.work, tid, self.cat)

    def test_a_stored_value_that_does_not_fit_the_setting_is_an_error(self):
        self.write_tyre("hand", {"version": 1, "name": "H", "source": {"front": ROAD_A, "rear": ROAD_B}, "values": {"tyre_dy_front": "fast"}})
        with self.assertRaisesRegex(ValueError, "^tyre hand: tyre_dy_front expects a number"):
            tune.tyre_rows(self.work, "hand", self.cat)

    def test_values_of_unknown_settings_are_ignored_and_kept(self):
        self.write_tyre("old", {"version": 1, "name": "O", "source": {"front": ROAD_A, "rear": ROAD_B}, "values": {"gone": 1}})
        self.assertEqual(len(tune.tyre_rows(self.work, "old", self.cat)), 4)
        tune.set_tyre_value(self.work, "old", "tyre_dy_front", "1.3", self.cat)
        self.assertEqual(tune.load_tyre(self.work, "old")["values"], {"gone": 1, "tyre_dy_front": 1.3})

    def test_a_missing_tyre(self):
        with self.assertRaisesRegex(ValueError, "^no tyre 'nope' in the library$"):
            tune.tyre_rows(self.work, "nope", self.cat)

    def test_every_setting_of_the_committed_catalogue_is_read_from_a_file_with_its_paths(self):
        cat = tune.load_catalogue()
        front, rear = {}, {}
        for s in tune.tyre_settings(cat):
            for t in s["targets"]:
                tune.put_value(front if t["file"] == "@tyre_front" else rear, t["path"],
                               s["choice_values"]["slick"] if s["type"] == "enum" else 1.5 if tune.tyre_axle(s) == "front" else 1.25)
        self.a.add_shared("tyres/road/a.tyre", front)
        self.a.add_shared("tyres/road/b.tyre", rear)
        rows = tune.tyre_rows(self.work, self.create(), cat)
        self.assertEqual(len(rows), 24)
        self.assertTrue(all(r["applicable"] for r in rows), [r["id"] for r in rows if not r["applicable"]])
        by_axle = {(r["axle"], r["type"]): r["default"] for r in rows}
        self.assertEqual(by_axle, {("front", "float"): 1.5, ("front", "enum"): "slick", ("rear", "float"): 1.25, ("rear", "enum"): "slick"})


class TestUsers(World):
    def uses(self, car, tune_id, *entries):
        tune.save_state(self.work, car, {"limiter": 1, tune.TYRE_KEY: list(entries)}, tune_id)

    def test_nothing_uses_a_tyre_without_states(self):
        self.assertEqual(tune.tyre_users(self.work, "slick"), [])
        self.assertEqual(tune.tyre_users(os.path.join(self.work, "none"), "slick"), [])

    def test_the_default_tune_the_draft_and_other_tunes_are_found(self):
        self.uses("ks_a", None, "own:slick")
        self.uses("ks_a", "ax01", "own:slick", "own:soft")
        self.uses("ks_a", "ax02", "own:soft")
        self.uses("ks_a", tune.DRAFT, "own:slick")
        self.uses("ks_b", "ax_b", "own:slick")
        self.assertEqual(tune.tyre_users(self.work, "slick"), [{"car": "ks_a", "tune": "ax_a"}, {"car": "ks_a", "tune": "ax01"},
                                                               {"car": "ks_a", "tune": "draft"}, {"car": "ks_b", "tune": "ax_b"}])
        self.assertEqual(tune.tyre_users(self.work, "soft"), [{"car": "ks_a", "tune": "ax01"}, {"car": "ks_a", "tune": "ax02"}])

    def test_only_an_exact_own_entry_in_a_list_counts(self):
        self.uses("ks_a", None, "own:slick2", "slick", "game:slick", "OWN:slick", "own:slic")
        self.assertEqual(tune.tyre_users(self.work, "slick"), [])
        self.assertEqual(tune.tyre_users(self.work, "slick2"), [{"car": "ks_a", "tune": "ax_a"}])
        tune.save_state(self.work, "ks_b", {tune.TYRE_KEY: "own:slick"})
        tune.save_state(self.work, "ks_b", {tune.TYRE_KEY: {"own:slick": 1}}, "ax01")
        tune.save_state(self.work, "ks_b", {tune.TYRE_KEY: None}, tune.DRAFT)
        self.assertEqual(tune.tyre_users(self.work, "slick"), [])

    def test_unreadable_state_files_are_ignored(self):
        self.uses("ks_a", None, "own:slick")
        for rel, text in (("tune_state.json", "{not json"), (os.path.join("tunes", "ax01", "tune_state.json"), "[1]"),
                          ("draft_state.json", "\x00")):
            path = os.path.join(self.work, "ks_b", rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        self.assertEqual(tune.tyre_users(self.work, "slick"), [{"car": "ks_a", "tune": "ax_a"}])

    def test_the_tune_folders_that_are_no_tune_ids_are_ignored(self):
        self.uses("ks_a", "ax01", "own:slick")
        path = os.path.join(self.work, "ks_a", "tunes", "Bad Id", "tune_state.json")
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({tune.TYRE_KEY: ["own:slick"]}, f)
        self.assertEqual(tune.tyre_users(self.work, "slick"), [{"car": "ks_a", "tune": "ax01"}])

    def test_the_constants(self):
        self.uses("ks_a", None, "own:slick")
        self.assertEqual(tune.TYRE_KEY, "_tyres")
        self.assertEqual(tune.TYRES_DIR, "tyres")


class TestDelete(World):
    def test_a_tyre_that_nobody_uses_is_removed(self):
        tid = self.create()
        self.assertEqual(tune.delete_tyre(self.work, tid), {"id": "slick", "deleted": True})
        self.assertEqual(tune.list_tyres(self.work), [])
        self.assertFalse(os.path.exists(tune.tyre_path(self.work, tid)))

    def test_refused_while_a_modded_car_or_the_draft_uses_it(self):
        tid = self.create()
        tune.save_state(self.work, "ks_a", {tune.TYRE_KEY: ["own:slick"]}, "ax01")
        tune.save_state(self.work, "ks_a", {tune.TYRE_KEY: ["own:slick"]}, tune.DRAFT)
        tune.save_state(self.work, "ks_b", {tune.TYRE_KEY: ["own:slick"]})
        with self.assertRaisesRegex(ValueError, "^tyre slick is used by ks_a / ax01, ks_a \\(draft\\), ks_b / ax_b$"):
            tune.delete_tyre(self.work, tid)
        self.assertTrue(os.path.isfile(tune.tyre_path(self.work, tid)))

    def test_allowed_after_the_last_user_let_go(self):
        tid = self.create()
        tune.save_state(self.work, "ks_a", {tune.TYRE_KEY: ["own:slick"]}, tune.DRAFT)
        with self.assertRaisesRegex(ValueError, "ks_a \\(draft\\)"):
            tune.delete_tyre(self.work, tid)
        tune.save_state(self.work, "ks_a", {tune.TYRE_KEY: []}, tune.DRAFT)
        self.assertTrue(tune.delete_tyre(self.work, tid)["deleted"])

    def test_a_missing_tyre(self):
        with self.assertRaisesRegex(ValueError, "^no tyre 'nope' in the library$"):
            tune.delete_tyre(self.work, "nope")

    def test_a_damaged_tyre_can_be_deleted(self):
        self.write_tyre("broken", "{")
        self.assertTrue(tune.delete_tyre(self.work, "broken")["deleted"])
        self.assertEqual(tune.list_tyres(self.work), [])

    def test_the_name_can_be_reused_after_a_delete(self):
        tid = self.create("Slick")
        tune.delete_tyre(self.work, tid)
        self.assertEqual(self.create("Slick"), "slick")


class TestCommands(World):
    def setUp(self):
        super().setUp()
        self.patch(tune, "load_catalogue", lambda path=None: self.cat)

    def main(self, *argv):
        return self.run_main(*argv, "--work", self.work)

    def test_tyres_on_an_empty_work_folder(self):
        self.assertEqual(self.main("tyres"), (0, "no tyres in the library\n", ""))
        self.assertFalse(os.path.exists(os.path.join(self.work, "tyres")))

    def test_tyre_sources_lists_the_pairs_with_label_cars_and_key(self):
        code, out, err = self.main("tyre-sources")
        self.assertEqual((code, err), (0, ""))
        lines = out.splitlines()
        self.assertEqual([c.strip() for c in lines[0].split(" | ")], ["label", "cars", "key"])
        self.assertEqual([c.strip() for c in lines[2].split(" | ")], ["tyres\\road\\a + tyres\\road\\b", "ks_a, ks_b", KEY_AB])
        self.assertEqual([c.strip() for c in lines[3].split(" | ")], ["tyres\\slick\\s", "ks_a", KEY_SS])

    def test_tyre_sources_without_cars(self):
        code, out, err = self.run_main("tyre-sources", "--work", str(self.d / "empty"))
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.startswith("note: no extracted car offers a tyre pair"))

    def test_new_set_show_unset_delete(self):
        code, out, err = self.main("tyre-new", "--name", "Slick Soft", "--source", KEY_AB)
        self.assertEqual((code, out, err), (0, "created tyre slick_soft: Slick Soft (tyres\\road\\a + tyres\\road\\b)\n", ""))
        self.assertEqual(self.main("tyre-set", "slick_soft", "tyre_dy_front", "1.4"), (0, "tyre_dy_front = 1.4\n", ""))
        code, out, err = self.main("tyre-show", "slick_soft")
        self.assertEqual((code, err), (0, ""))
        lines = out.splitlines()
        self.assertEqual(lines[0], "tyre slick_soft: Slick Soft, source tyres\\road\\a + tyres\\road\\b")
        rows = {line.split("|")[1].strip(): [c.strip() for c in line.split("|")] for line in lines[3:]}
        self.assertEqual(rows["tyre_dy_front"][:5], ["*", "tyre_dy_front", "1.4", "1.2", "mu"])
        self.assertEqual(rows["tyre_dy_rear"][:5], ["", "tyre_dy_rear", "1.1", "1.1", "mu"])
        self.assertEqual(rows["tyre_deep_front"][1:4], ["tyre_deep_front", "-", "-"])
        self.assertIn("modelData.nope.x: missing field 'nope'", rows["tyre_deep_front"][5])
        self.assertEqual(self.main("tyre-unset", "slick_soft", "tyre_dy_front"), (0, "tyre_dy_front removed from the tyre\n", ""))
        self.assertEqual(self.main("tyre-unset", "slick_soft", "tyre_dy_front"), (0, "tyre_dy_front was not set\n", ""))
        self.assertEqual(self.main("tyre-delete", "slick_soft"), (0, "deleted tyre slick_soft\n", ""))
        self.assertEqual(self.main("tyres"), (0, "no tyres in the library\n", ""))

    def test_tyres_lists_one_line_per_tyre_and_the_damaged_ones(self):
        self.main("tyre-new", "--name", "Slick", "--source", KEY_AB)
        self.main("tyre-set", "slick", "tyre_dy_rear", "1.2")
        self.write_tyre("broken", "{")
        code, out, err = self.main("tyres")
        self.assertEqual((code, err), (0, ""))
        lines = out.splitlines()
        self.assertEqual([c.strip() for c in lines[0].split("|")], ["id", "name", "source", "changed"])
        self.assertEqual([c.strip() for c in lines[2].split("|")], ["slick", "Slick", "tyres\\road\\a + tyres\\road\\b", "1"])
        self.assertTrue(lines[3].startswith("broken"))
        self.assertIn("error: ", lines[3])
        self.assertEqual(len(lines), 4)

    def test_set_prints_the_range_warning_on_stderr(self):
        self.main("tyre-new", "--name", "Slick", "--source", KEY_AB)
        self.assertEqual(self.main("tyre-set", "slick", "tyre_dy_front", "9"),
                         (0, "tyre_dy_front = 9.0\n", "warning: tyre_dy_front=9.0 is outside the suggested range 0.5..2.5\n"))

    def test_runtime_errors_are_error_lines_with_exit_1(self):
        self.main("tyre-new", "--name", "Slick", "--source", KEY_AB)
        for argv, message in ((("tyre-new", "--name", "Slick", "--source", KEY_AB), "error: a tyre named 'Slick' exists already (slick)\n"),
                              (("tyre-new", "--name", "X", "--source", "nope"), "error: unknown tyre source 'nope'"),
                              (("tyre-set", "slick", "limiter", "1"), "error: limiter is not a tyre setting\n"),
                              (("tyre-set", "slick", "tyre_dy_front", "fast"), "error: tyre_dy_front expects a number, got 'fast'\n"),
                              (("tyre-set", "nope", "tyre_dy_front", "1"), "error: no tyre 'nope' in the library\n"),
                              (("tyre-show", "../x"), "error: bad tyre id '../x'"), (("tyre-delete", "nope"), "error: no tyre 'nope' in the library\n"),
                              (("tyre-unset", "slick", "nope"), "error: unknown setting 'nope'\n")):
            with self.subTest(argv):
                code, out, err = self.main(*argv)
                self.assertEqual((code, out), (1, ""))
                self.assertTrue(err.startswith(message), err)

    def test_delete_is_refused_while_a_modded_car_uses_the_tyre(self):
        self.main("tyre-new", "--name", "Slick", "--source", KEY_AB)
        tune.save_state(self.work, "ks_a", {tune.TYRE_KEY: ["own:slick"]}, "ax01")
        self.assertEqual(self.main("tyre-delete", "slick"), (1, "", "error: tyre slick is used by ks_a / ax01\n"))
        self.assertTrue(os.path.isfile(tune.tyre_path(self.work, "slick")))

    def test_show_of_a_tyre_whose_source_is_gone_is_an_error_line(self):
        self.main("tyre-new", "--name", "Slick", "--source", KEY_SS)
        os.remove(os.path.join(self.a.shared, "tyres", "slick", "s.tyre"))
        code, out, err = self.main("tyre-show", "slick")
        self.assertEqual((code, out), (1, ""))
        self.assertTrue(err.startswith("error: tyre slick: no extracted car offers its source"), err)

    def test_the_work_folder_is_expanded(self):
        code, out, err = self.run_main("tyres", "--work", "%ACE_TEST_NO_SUCH_VAR%/w")
        self.assertEqual((code, out), (1, ""))
        self.assertTrue(err.startswith("error: cannot expand the work directory"), err)


def usage_case(name, argv):
    def test(self):
        with tmp() as d:
            r = run_tool("tune.py", *argv, cwd=d)
            self.assertEqual(os.listdir(d), [])
        self.assertEqual((r.returncode, r.stdout.strip(), r.stderr), (2, USAGE.strip(), ""))
    test.__name__ = "test_usage_" + name
    return test


class TestCliUsage(unittest.TestCase):
    def test_the_usage_block_lists_every_tyre_command(self):
        for cmd in ("tyres", "tyre-sources", "tyre-new", "tyre-show", "tyre-set", "tyre-unset", "tyre-delete"):
            self.assertIn("python tools/tune.py " + cmd + " ", USAGE)
        self.assertNotIn("--car", "\n".join(line for line in USAGE.splitlines() if "tyre" in line))


for _name, _argv in (("no_arguments", []), ("tyres_with_a_positional", ["tyres", "x"]), ("tyre_sources_with_a_positional", ["tyre-sources", "x"]),
                     ("tyre_new_without_options", ["tyre-new"]), ("tyre_new_without_source", ["tyre-new", "--name", "x"]),
                     ("tyre_new_without_name", ["tyre-new", "--source", "k"]),
                     ("tyre_new_with_a_positional", ["tyre-new", "--name", "x", "--source", "k", "y"]),
                     ("tyre_new_option_without_value", ["tyre-new", "--name"]),
                     ("tyre_show_without_id", ["tyre-show"]), ("tyre_show_with_two_ids", ["tyre-show", "a", "b"]),
                     ("tyre_set_with_two_operands", ["tyre-set", "a", "b"]), ("tyre_set_with_four_operands", ["tyre-set", "a", "b", "c", "d"]),
                     ("tyre_set_without_operands", ["tyre-set"]),
                     ("tyre_unset_with_one_operand", ["tyre-unset", "a"]), ("tyre_unset_with_three_operands", ["tyre-unset", "a", "b", "c"]),
                     ("tyre_delete_without_id", ["tyre-delete"]), ("tyre_delete_with_two_ids", ["tyre-delete", "a", "b"]),
                     ("tyres_with_a_car", ["tyres", "--car", "ks_x"]), ("tyre_show_with_a_tune", ["tyre-show", "a", "--tune", "ax01"]),
                     ("tyre_set_with_an_unknown_option", ["tyre-set", "a", "b", "c", "--bogus", "1"])):
    setattr(TestCliUsage, "test_usage_" + _name, usage_case(_name, _argv))


class TestCliSubprocess(unittest.TestCase):
    def test_tyres_on_an_empty_work_folder_writes_nothing(self):
        with tmp() as d:
            r = run_tool("tune.py", "tyres", "--work", d / "w", cwd=d)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "no tyres in the library\n", ""))
            self.assertEqual(os.listdir(d), [])

    def test_tyre_sources_on_an_empty_work_folder(self):
        with tmp() as d:
            r = run_tool("tune.py", "tyre-sources", "--work", d / "w", cwd=d)
            self.assertEqual((r.returncode, r.stderr), (0, ""))
            self.assertTrue(r.stdout.startswith("note: no extracted car offers a tyre pair"))

    def test_runtime_errors_are_error_lines_on_stderr_with_exit_1(self):
        with tmp() as d:
            for argv, message in ((("tyre-new", "--name", "x", "--source", "nokey"), "error: unknown tyre source 'nokey'"),
                                  (("tyre-show", "nope"), "error: no tyre 'nope' in the library\n"),
                                  (("tyre-set", "nope", "tyre_grip_lateral_front", "1"), "error: no tyre 'nope' in the library\n"),
                                  (("tyre-unset", "../x", "a"), "error: bad tyre id '../x'"), (("tyre-delete", "A"), "error: bad tyre id 'A'")):
                with self.subTest(argv):
                    r = run_tool("tune.py", *argv, "--work", d / "w", cwd=d)
                    self.assertEqual((r.returncode, r.stdout), (1, ""))
                    self.assertTrue(r.stderr.startswith(message), r.stderr)
            self.assertEqual(os.listdir(d), [])

    def test_a_tyre_file_in_the_work_folder_is_listed_and_shown_as_an_error_when_damaged(self):
        with tmp() as d:
            os.makedirs(d / "w" / "tyres")
            (d / "w" / "tyres" / "x.json").write_text("{", encoding="utf-8")
            r = run_tool("tune.py", "tyres", "--work", d / "w", cwd=d)
            self.assertEqual((r.returncode, r.stderr), (0, ""))
            self.assertIn("error: ", r.stdout)
            r = run_tool("tune.py", "tyre-delete", "x", "--work", d / "w", cwd=d)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "deleted tyre x\n", ""))


if __name__ == "__main__":
    unittest.main()
