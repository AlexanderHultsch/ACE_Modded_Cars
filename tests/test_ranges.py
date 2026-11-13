"""Tests for the ranges of tools/tune.py: compute_ranges (lowest and highest default of every numeric setting over the extracted base cars), write_ranges / load_ranges (<work>/ranges.json) and the ranges command.

No game data and no schemas: the cars are synthetic (support.FakeCar replaces tune.load_msg / save_msg with in-memory messages, one shared store for all fake cars); the command runs in-process on those cars, and as a subprocess where no car is decoded.
"""
import contextlib
import io
import json
import math
import os
import sys
import unittest
from unittest import mock

from support import FakeCar, mini_catalogue, mini_setting, run_tool, tmp

import kspkg
import tune

USAGE = tune.__doc__.split("\n\n")[1]


def numeric():
    return [mini_setting("limiter", type="int", targets=[("@car", "engine.limiter")]),
            mini_setting("gain", targets=[("@car", "engine.gain")]),
            mini_setting("extra", targets=[("@car", "engine.extra")]),
            mini_setting("ghost", targets=[("@car", "engine.nope.x")])]


def stock_info(car_id):
    return {"car_id": car_id, "display_name": "Car " + car_id, "brand": "Brand", "year": 1999, "property_1": "P1",
            "property_2": "P2", "property_3": "P3", "variant_name": "Base"}


class Fleet(unittest.TestCase):
    """A work folder in a scratch folder with synthetic extracted cars; car() adds one with the given engine values."""

    def setUp(self):
        cm = tmp()
        self.d = cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        self.work = str(self.d / "work")
        self.first = None
        self.cat = mini_catalogue(*numeric())

    def car(self, car_id, preset=False, info=False, **engine):
        fc = FakeCar(self.work, car_id)
        if self.first is None:
            self.first = fc.install(self)
        else:
            fc.store = self.first.store
        fc.add("data/x.car", {"engine": engine})
        if preset:
            fc.add("presets/p.mechanicalcarpreset", {"brand": "Brand", "description": "Name Preset Base"})
        if info:
            self.write(tune.stock_info_path(self.work, car_id), stock_info(car_id))
        return fc

    def write(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
        return path

    def compute(self, **kw):
        return tune.compute_ranges(self.work, kw.pop("catalogue", self.cat), game="")

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


class TestComputeRanges(Fleet):
    def test_lowest_and_highest_default_over_the_cars(self):
        self.car("ks_c", limiter=6000.0, gain=2.5, extra=4.0)
        self.car("ks_a", limiter=7000.0, gain=1.5, extra=10.0)
        self.car("ks_b", limiter=9000.0, gain=0.5, extra=7.0)
        res = self.compute()
        self.assertEqual(res["ranges"], {"limiter": {"low": 6000, "high": 9000}, "gain": {"low": 0.5, "high": 2.5},
                                         "extra": {"low": 4.0, "high": 10.0}})
        self.assertEqual((res["cars"], res["skipped"]), (["ks_a", "ks_b", "ks_c"], []))

    def test_numbers_are_stored_as_found(self):
        self.car("ks_a", limiter=7000.0, gain=1.5, extra=1.0 / 3)
        self.car("ks_b", limiter=7500.0, gain=1.25, extra=2.0 / 3)
        ranges = self.compute()["ranges"]
        self.assertIs(type(ranges["limiter"]["low"]), int)
        self.assertIs(type(ranges["limiter"]["high"]), int)
        self.assertEqual(ranges["extra"], {"low": 1.0 / 3, "high": 2.0 / 3})

    def test_a_setting_on_one_car_only_has_the_same_low_and_high(self):
        self.car("ks_a", limiter=7000.0, gain=1.5)
        self.car("ks_b", limiter=8000.0, gain=2.0, extra=3.0)
        self.assertEqual(self.compute()["ranges"]["extra"], {"low": 3.0, "high": 3.0})

    def test_a_setting_no_car_has_gets_no_entry(self):
        self.car("ks_a", limiter=7000.0, gain=1.5, extra=1.0)
        self.assertNotIn("ghost", self.compute()["ranges"])

    def test_a_field_the_car_does_not_store_is_ignored_for_that_car(self):
        self.car("ks_a", limiter=7000.0, gain=1.5, extra=10.0)
        self.car("ks_b", limiter=8000.0, gain=2.0)
        self.car("ks_c", limiter=9000.0, gain=2.5, extra=4.0)
        res = self.compute()
        self.assertEqual(res["ranges"]["extra"], {"low": 4.0, "high": 10.0})
        self.assertEqual(res["cars"], ["ks_a", "ks_b", "ks_c"])

    def test_a_setting_absent_on_every_car_gets_no_entry(self):
        self.car("ks_a", limiter=7000.0, gain=1.5)
        self.car("ks_b", limiter=8000.0, gain=2.0)
        self.assertNotIn("extra", self.compute()["ranges"])

    def test_only_numeric_value_settings_get_a_range(self):
        self.car("ks_a", limiter=7000.0, gain=1.5, flag=1, on=True, label="a", mode="x")
        self.car("ks_b", limiter=8000.0, gain=2.0, flag=1, on=False, label="b", mode="y")
        cat = mini_catalogue(
            *numeric()[:2],
            mini_setting("on", type="bool", targets=[("@car", "engine.on")]),
            mini_setting("flag", kind="flag", type="bool", value=1, targets=[("@car", "engine.flag")]),
            mini_setting("label", type="string", targets=[("@car", "engine.label")]),
            mini_setting("mode", type="enum", choices=["x", "y"], targets=[("@car", "engine.mode")]),
            mini_setting("name_suffix", kind="meta", type="string", default="_MY", handler="name_suffix"))
        rows = {r["id"]: r for r in tune.resolve_defaults(self.work, "ks_a", cat, "", hidden=True)}
        self.assertTrue(all(rows[i]["applicable"] for i in ("on", "flag", "label", "mode", "name_suffix")), {i: r["reason"] for i, r in rows.items()})
        self.assertEqual(sorted(self.compute(catalogue=cat)["ranges"]), ["gain", "limiter"])

    def test_a_curve_scale_that_resolves_gets_no_range(self):
        for car_id in ("ks_a", "ks_b"):
            fc = self.car(car_id, limiter=7000.0, gain=1.5, curve=fc_curve(car_id))
            fc.add("data/power.curve", {"points": [{"value": 1.0}, {"value": 3.0}]})
        cat = mini_catalogue(*numeric()[:2], mini_setting("scale", kind="curve_scale", default=1.0,
                                                          curve_from={"file": "@car", "path": "engine.curve"}))
        rows = {r["id"]: r for r in tune.resolve_defaults(self.work, "ks_a", cat, "", hidden=True)}
        self.assertTrue(rows["scale"]["applicable"], rows["scale"]["reason"])
        self.assertEqual(sorted(self.compute(catalogue=cat)["ranges"]), ["gain", "limiter"])

    def test_a_default_that_is_not_a_finite_number_is_ignored(self):
        self.car("ks_a", limiter=7000.0, gain=1.5, extra=2.0)
        self.car("ks_b", limiter=8000.0, gain=math.nan, extra=math.inf)
        self.car("ks_c", limiter=9000.0, gain=-math.inf, extra=5.0)
        ranges = self.compute()["ranges"]
        self.assertEqual(ranges["gain"], {"low": 1.5, "high": 1.5})
        self.assertEqual(ranges["extra"], {"low": 2.0, "high": 5.0})

    def test_finite_number(self):
        self.assertTrue(all(tune.finite_number(v) for v in (0, -3, 2.5, 1e300)))
        self.assertFalse(any(tune.finite_number(v) for v in (None, True, False, "1", [1], math.nan, math.inf, -math.inf)))

    def test_a_car_that_cannot_be_resolved_is_skipped_and_the_others_still_count(self):
        # variant_name needs the stock info or a presets folder with a mechanical preset, ks_b has neither
        cat = mini_catalogue(*numeric(), mini_setting("variant_name", kind="meta", type="string", default_template="{stock_variant_name}", handler="variant_name"))
        self.car("ks_c", info=True, limiter=6000.0, gain=2.5)
        self.car("ks_b", limiter=9999.0, gain=99.0)
        self.car("ks_a", preset=True, limiter=7000.0, gain=1.5)
        res = self.compute(catalogue=cat)
        self.assertEqual(res["cars"], ["ks_a", "ks_c"])
        self.assertEqual([s["car"] for s in res["skipped"]], ["ks_b"])
        self.assertIn("presets not found", res["skipped"][0]["reason"])
        self.assertEqual(res["ranges"]["limiter"], {"low": 6000, "high": 7000})
        self.assertEqual(res["ranges"]["gain"], {"low": 1.5, "high": 2.5})

    def test_value_errors_os_errors_and_system_exits_skip_the_car(self):
        for car_id in ("ks_a", "ks_b", "ks_c", "ks_d"):
            self.car(car_id, limiter=7000.0, gain=1.5)
        real = tune.resolve_defaults
        errors = {"ks_a": ValueError("bad"), "ks_b": OSError("disk"), "ks_c": SystemExit("gone")}

        def resolve(work, car_id, *a, **kw):
            if car_id in errors:
                raise errors[car_id]
            return real(work, car_id, *a, **kw)

        with mock.patch.object(tune, "resolve_defaults", resolve):
            res = self.compute()
        self.assertEqual(res["cars"], ["ks_d"])
        self.assertEqual([(s["car"], s["reason"]) for s in res["skipped"]], [("ks_a", "bad"), ("ks_b", "disk"), ("ks_c", "gone")])

    def test_resolve_defaults_is_called_with_the_catalogue_the_game_and_hidden_rows(self):
        self.car("ks_a", limiter=7000.0)
        with mock.patch.object(tune, "resolve_defaults", return_value=[]) as resolve:
            tune.compute_ranges(self.work, self.cat, "G")
        resolve.assert_called_once_with(self.work, "ks_a", self.cat, "G", hidden=True)

    def test_only_cars_with_an_extracted_base_count(self):
        self.car("ks_a", limiter=7000.0, gain=1.5)
        os.makedirs(os.path.join(self.work, "ks_built", "build", "ax_built"))
        self.write(os.path.join(self.work, "ks_state", "tune_state.json"), {})
        os.makedirs(tune.car_root_of(tune.base_dir(self.work, "ks_empty"), "ks_empty"))
        res = self.compute()
        self.assertEqual((res["cars"], res["skipped"]), (["ks_a"], []))

    def test_no_work_folder_and_no_cars(self):
        self.assertEqual(self.compute(), {"ranges": {}, "cars": [], "skipped": []})
        os.makedirs(self.work)
        self.assertEqual(self.compute(), {"ranges": {}, "cars": [], "skipped": []})

    def test_the_catalogue_defaults_to_load_catalogue(self):
        self.car("ks_a", limiter=7000.0, gain=1.5)
        with mock.patch.object(tune, "load_catalogue", lambda path=None: self.cat):
            self.assertEqual(sorted(tune.compute_ranges(self.work, game="")["ranges"]), ["gain", "limiter"])


def fc_curve(car_id):
    return "content\\cars\\%s\\data\\power.curve" % car_id


class TestWriteAndLoad(Fleet):
    def test_ranges_path_is_ranges_json_in_the_work_folder(self):
        self.assertEqual(tune.RANGES_FILE, "ranges.json")
        self.assertEqual(tune.ranges_path(self.work), os.path.join(self.work, "ranges.json"))

    def test_round_trip_keeps_the_numbers(self):
        ranges = {"limiter": {"low": 6000, "high": 9000}, "gain": {"low": 0.5, "high": 2.5}, "same": {"low": 3, "high": 3}}
        path = tune.write_ranges(self.work, ranges)
        self.assertEqual(path, tune.ranges_path(self.work))
        loaded = tune.load_ranges(self.work)
        self.assertEqual(loaded, ranges)
        self.assertIs(type(loaded["limiter"]["low"]), int)
        self.assertIs(type(loaded["gain"]["low"]), float)

    def test_the_file_is_a_flat_object_of_low_and_high_written_atomically(self):
        tune.write_ranges(self.work, {"a": {"low": -1, "high": 2.5}})
        with open(tune.ranges_path(self.work), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"a": {"low": -1, "high": 2.5}})
        self.assertEqual(os.listdir(self.work), ["ranges.json"])

    def test_a_missing_file_gives_nothing(self):
        self.assertEqual(tune.load_ranges(self.work), {})
        os.makedirs(self.work)
        self.assertEqual(tune.load_ranges(self.work), {})

    def test_an_empty_object_is_valid_and_gives_nothing(self):
        self.write(tune.ranges_path(self.work), {})
        self.assertEqual(tune.load_ranges(self.work), {})

    def test_damaged_and_invalid_files_give_nothing(self):
        good = {"low": 1, "high": 2}
        bad = ["", "{nope", "[]", "[1, 2]", "1", "null", '"text"', '{"a": 1}', '{"a": null}', '{"a": []}', '{"a": {}}',
               '{"a": {"low": 1}}', '{"a": {"high": 1}}', '{"a": {"low": 2, "high": 1}}', '{"a": {"low": "1", "high": 2}}',
               '{"a": {"low": true, "high": 2}}', '{"a": {"low": 1, "high": null}}', '{"a": {"low": NaN, "high": 1}}',
               '{"a": {"low": 1, "high": Infinity}}', '{"a": {"low": -Infinity, "high": 1}}',
               json.dumps({"ok": good, "a": {"low": 3, "high": 1}}), json.dumps({"ok": good, "a": {"low": [1], "high": 2}})]
        for text in bad:
            with self.subTest(text):
                self.write(tune.ranges_path(self.work), text)
                self.assertEqual(tune.load_ranges(self.work), {})

    def test_a_binary_file_and_a_folder_give_nothing(self):
        os.makedirs(self.work)
        with open(tune.ranges_path(self.work), "wb") as f:
            f.write(b"\xff\xfe\x00\x80")
        self.assertEqual(tune.load_ranges(self.work), {})
        os.remove(tune.ranges_path(self.work))
        os.makedirs(tune.ranges_path(self.work))
        self.assertEqual(tune.load_ranges(self.work), {})

    def test_extra_keys_of_an_entry_are_dropped(self):
        self.write(tune.ranges_path(self.work), {"a": {"low": 1, "high": 2, "cars": ["ks_x"]}})
        self.assertEqual(tune.load_ranges(self.work), {"a": {"low": 1, "high": 2}})

    def test_the_file_is_read_again_only_when_it_changed(self):
        tune.write_ranges(self.work, {"a": {"low": 1, "high": 2}})
        with mock.patch.object(tune, "read_json", wraps=tune.read_json) as read:
            first = tune.load_ranges(self.work)
            first["a"]["low"] = 99
            first["b"] = {"low": 0, "high": 0}
            self.assertEqual(tune.load_ranges(self.work), {"a": {"low": 1, "high": 2}})
            self.assertEqual(read.call_count, 1)
            tune.write_ranges(self.work, {"a": {"low": 1, "high": 2}, "bb": {"low": 5, "high": 6}})
            self.assertEqual(tune.load_ranges(self.work), {"a": {"low": 1, "high": 2}, "bb": {"low": 5, "high": 6}})
            self.assertEqual(read.call_count, 2)
        self.write(tune.ranges_path(self.work), "{broken")
        self.assertEqual(tune.load_ranges(self.work), {})
        os.remove(tune.ranges_path(self.work))
        self.assertEqual(tune.load_ranges(self.work), {})


class TestCommand(Fleet):
    def setUp(self):
        super().setUp()
        patch = mock.patch.object(tune, "load_catalogue", lambda path=None: self.cat)
        patch.start()
        self.addCleanup(patch.stop)

    def main(self, *argv):
        return self.run_main("ranges", *argv, "--work", self.work)

    def test_writes_the_file_and_prints_the_counts(self):
        self.car("ks_a", limiter=7000.0, gain=1.5, extra=10.0)
        self.car("ks_b", limiter=9000.0, gain=0.5)
        code, out, err = self.main()
        self.assertEqual((code, out, err), (0, "read 2 cars, skipped 0, 3 settings with a range\n", ""))
        with open(tune.ranges_path(self.work), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"limiter": {"low": 7000, "high": 9000}, "gain": {"low": 0.5, "high": 1.5},
                                            "extra": {"low": 10.0, "high": 10.0}})
        self.assertEqual(tune.load_ranges(self.work), tune.compute_ranges(self.work, self.cat, "")["ranges"])

    def test_a_skipped_car_is_listed_on_stderr_and_the_exit_code_stays_0(self):
        self.cat = mini_catalogue(*numeric(), mini_setting("variant_name", kind="meta", type="string", default_template="{stock_variant_name}", handler="variant_name"))
        self.car("ks_a", preset=True, limiter=7000.0, gain=1.5)
        self.car("ks_b", limiter=9000.0, gain=0.5)
        code, out, err = self.main()
        self.assertEqual((code, out), (0, "read 1 cars, skipped 1, 2 settings with a range\n"))
        self.assertRegex(err, r"^skipped ks_b: .*presets not found.*\n$")
        self.assertEqual(err.count("\n"), 1)
        self.assertEqual(tune.load_ranges(self.work), {"limiter": {"low": 7000, "high": 7000}, "gain": {"low": 1.5, "high": 1.5}})

    def test_without_a_readable_car_it_is_an_error_and_nothing_is_written(self):
        self.cat = mini_catalogue(*numeric(), mini_setting("variant_name", kind="meta", type="string", default_template="{stock_variant_name}", handler="variant_name"))
        self.car("ks_b", limiter=9000.0, gain=0.5)
        tune.write_ranges(self.work, {"old": {"low": 1, "high": 2}})
        code, out, err = self.main()
        self.assertEqual((code, out), (1, ""))
        self.assertRegex(err, r"^skipped ks_b: .*\nerror: no car could be read in .*\n$")
        self.assertEqual(tune.load_ranges(self.work), {"old": {"low": 1, "high": 2}})

    def test_without_an_installed_car_it_is_an_error_and_nothing_is_written(self):
        os.makedirs(os.path.join(self.work, "ks_built", "build"))
        code, out, err = self.main()
        self.assertEqual((code, out), (1, ""))
        self.assertTrue(err.startswith("error: no installed car in %s" % self.work), err)
        self.assertEqual(err.count("\n"), 1)
        self.assertFalse(os.path.exists(tune.ranges_path(self.work)))

    def test_the_game_package_is_never_read(self):
        self.cat = mini_catalogue(
            *numeric()[:2], mini_setting("tyre_dy", targets=[("@tyre_front", "modelData.Dy0")]),
            mini_setting("variant_name", kind="meta", type="string", default_template="{stock_variant_name}", handler="variant_name"))
        fc = self.car("ks_a", preset=True, limiter=7000.0, gain=1.5)
        fc.add("data/x.car", {"engine": {"limiter": 7000.0, "gain": 1.5}, "frontTyreCompounds": ["content\\cars\\common_phsx\\tyres\\a.tyre"]})
        with mock.patch.object(kspkg, "cmd_extract", side_effect=AssertionError("the game package was read")):
            code, out, err = self.main()
        self.assertEqual((code, out, err), (0, "read 1 cars, skipped 0, 2 settings with a range\n", ""))
        self.assertEqual(sorted(tune.load_ranges(self.work)), ["gain", "limiter"])
        self.assertEqual(sorted(os.listdir(self.work)), ["ks_a", "ranges.json"])

    def test_arguments_other_than_work_print_the_usage(self):
        for argv in (("x",), ("--bogus", "1"), ("--game", "x")):
            with self.subTest(argv):
                code, out, err = self.main(*argv)
                self.assertEqual((code, out.strip(), err), (2, USAGE.strip(), ""))

    def test_the_usage_lists_the_command(self):
        self.assertIn("  python tools/tune.py ranges       [--work <dir>]\n", USAGE + "\n")


class TestCommandSubprocess(unittest.TestCase):
    def test_no_installed_car_is_an_error_line_on_stderr_with_exit_1(self):
        with tmp() as d:
            r = run_tool("tune.py", "ranges", "--work", d / "w", cwd=d)
            self.assertEqual((r.returncode, r.stdout), (1, ""))
            self.assertRegex(r.stderr, r"^error: no installed car in .*\n$")
            self.assertEqual(os.listdir(d), [])

    def test_a_positional_prints_the_usage_with_exit_2(self):
        with tmp() as d:
            r = run_tool("tune.py", "ranges", "x", cwd=d)
            self.assertEqual((r.returncode, r.stdout.strip(), r.stderr), (2, USAGE.strip(), ""))


if __name__ == "__main__":
    unittest.main()
