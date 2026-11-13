"""Tests for the garage tyre selection of tools/tune.py: the "_tyres" state key, car_stock_tyres, garage_choices, set_garage, reset_garage, the garage step of apply (own tyre files, .car lists, compatibletyres) and the garage commands.

No game data and no schemas: the cars are synthetic (support.FakeCar replaces tune.load_msg / save_msg with in-memory messages, one shared store for both fake cars; clone_car.build is stubbed for apply, kspkg.cmd_pack is stubbed or, where a test says so, the real one); the commands run in-process on those cars, and as a subprocess where nothing decodes a car file.
"""
import contextlib
import io
import json
import os
import re
import sys
import unittest
from unittest import mock

from support import FakeCar, mini_catalogue, mini_setting, run_tool, tmp

import clone_car
import kspkg
import tune

USAGE = tune.__doc__.split("\n\n")[1]
REAL_PACK = kspkg.cmd_pack
REAL_RENAME = os.rename
GS = "content\\cars\\common_phsx\\"
A, B = GS + "tyres\\road\\a.tyre", GS + "tyres\\road\\b.tyre"
S, W, M = GS + "tyres\\slick\\s.tyre", GS + "tyres\\wet\\w.tyre", GS + "tyres\\misc\\m.tyre"
G_F, G_R = GS + "tyres\\gt\\f.tyre", GS + "tyres\\gt\\r.tyre"
A_UP = "CONTENT\\CARS\\COMMON_PHSX\\TYRES\\ROAD\\A.TYRE"
CURVES = {"road": GS + "tyres\\road\\tcurve_road.curve", "slick": GS + "tyres\\slick\\tcurve_slick.curve"}
KEY_AB, KEY_SS, KEY_GG = A + "|" + B, S + "|" + S, G_F + "|" + G_R
ST_AB, ST_SS, ST_WW = "stock:" + KEY_AB, "stock:" + KEY_SS, "stock:" + W + "|" + W
OWN_F, OWN_R = "content\\cars\\ax_x\\data\\tyres\\own_%s_front.tyre", "content\\cars\\ax_x\\data\\tyres\\own_%s_rear.tyre"
NO_TUNE_ERROR = "tyre settings are changed but the stock starting tyre of the car is not ticked in the garage, tick it or reset the tyre values"


def tyre_cat():
    meta = [mini_setting("name_suffix", kind="meta", type="string", default="_MY", handler="name_suffix"),
            mini_setting("variant_name", kind="meta", type="string", default_template="{stock_variant_name}", handler="variant_name")]
    return mini_catalogue(
        *meta,
        mini_setting("tyre_dy_front", group="Tyres", targets=[("@tyre_front", "modelData.Dy0"), ("@tyre_front", "modelData.Dy1")]),
        mini_setting("tyre_dy_rear", group="Tyres", targets=[("@tyre_rear", "modelData.Dy0")]),
        mini_setting("tyre_th_front", group="Tyres", type="enum", choices=["road", "slick"], choice_values=CURVES,
                     targets=[("@tyre_front", "thermalData.thermalPerformanceCurve")]),
        mini_setting("tyre_deep_front", group="Tyres", targets=[("@tyre_front", "modelData.nope.x")]),
        mini_setting("limiter", type="int", targets=[("@engine", "limiter")]))


def tyre_obj(dy, curve="road"):
    return {"modelData": {"Dy0": dy, "Dy1": dy, "Fz0": 3000}, "thermalData": {"thermalPerformanceCurve": CURVES[curve], "x": 1}}


class World(unittest.TestCase):
    """Two extracted cars. ks_x (the car under test): shared tyres a, b, s, w, m; .car lists front [A (upper case), S, W, M] and
    rear [B, S, W]; presets p (A+B with a string rear, S+[S, B] with a list rear and a wire order, W+W, one compound that names a
    file in the car folder) and q (S+[S], A+B). ks_y: only the pair gt f+r, which ks_x does not have."""

    def setUp(self):
        cm = tmp()
        self.d = cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        self.work = str(self.d / "work")
        data = {"default": "ks_x", "cars": [{"id": "ks_x", "label": "Car X"}]}
        self.patch(tune, "load_cars", lambda path=None: data)
        self.cat = tyre_cat()
        self.patch(tune, "load_catalogue", lambda path=None: self.cat)
        self.x = FakeCar(self.work, "ks_x").install(self)
        self.y = FakeCar(self.work, "ks_y")
        self.y.store = self.x.store
        self.car = {"frontTyreCompounds": [A_UP, S, W, M], "rearTyreCompounds": [B, S, W],
                    "_order": ["frontTyreCompounds"] * 4 + ["rearTyreCompounds"] * 3}
        self.p = {"physic_compounds": [
            {"front_tyre_data_path": A, "rear_tyre_data_paths": B, "name": "road", "grip": 1.0},
            {"front_tyre_data_path": S, "rear_tyre_data_paths": [S, B], "name": "slick",
             "_order": ["front_tyre_data_path", "rear_tyre_data_paths", "rear_tyre_data_paths", "name"]},
            {"front_tyre_data_path": W, "rear_tyre_data_paths": W, "name": "wet"},
            {"front_tyre_data_path": self.x.game_path("data/tyres/odd.tyre"), "rear_tyre_data_paths": B, "name": "odd"}],
            "_order": ["physic_compounds"] * 4, "default_index": 0}
        self.q = {"physic_compounds": [{"front_tyre_data_path": S, "rear_tyre_data_paths": [S], "name": "q_slick"},
                                       {"front_tyre_data_path": A, "rear_tyre_data_paths": B, "name": "q_road"}]}
        self.x.add("data/x.car", self.car)
        self.x.add("presets/p.compatibletyres", self.p)
        self.x.add("presets/q.compatibletyres", self.q)
        for rel, curve in (("road/a", "road"), ("road/b", "road"), ("slick/s", "slick"), ("wet/w", "road")):
            self.x.add_shared("tyres/%s.tyre" % rel, tyre_obj(1.2 if rel.endswith("a") else 1.1, curve))
        self.x.add_shared("tyres/misc/m.tyre", {"modelData": {"Dy0": 1.0}})
        self.y.add_shared("tyres/gt/f.tyre", tyre_obj(2.0))
        self.y.add_shared("tyres/gt/r.tyre", tyre_obj(2.5))
        self.y.add("presets/y.compatibletyres", {"physic_compounds": [{"front_tyre_data_path": G_F, "rear_tyre_data_paths": G_R}]})
        self.write(tune.stock_info_path(self.work, "ks_x"), {"car_id": "ks_x", "display_name": "Car X", "brand": "Brand", "year": 1999,
                                                              "property_1": "P1", "property_2": "P2", "property_3": "P3", "variant_name": "Base"})

    def patch(self, target, name, value):
        p = mock.patch.object(target, name, value)
        p.start()
        self.addCleanup(p.stop)
        return value

    def write(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
        return path

    def tyres(self):
        """The library: gt (source in ks_y only), slicky (source s+s), soft (source a+b); sorted in that order."""
        self.gt = tune.create_tyre(self.work, "gt", KEY_GG)["id"]
        self.slicky = tune.create_tyre(self.work, "Slicky", KEY_SS)["id"]
        self.soft = tune.create_tyre(self.work, "Soft", KEY_AB)["id"]
        return self

    def state(self, tune_id=None):
        return tune.load_state(self.work, "ks_x", tune_id)

    def stock_keys(self):
        return [s["key"] for s in tune.car_stock_tyres(self.work, "ks_x")]

    def run_main(self, *argv):
        out, err, code = io.StringIO(), io.StringIO(), None
        with mock.patch.object(sys, "argv", ["tune.py", *argv, "--work", self.work]), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                tune.main()
            except SystemExit as e:
                code = e.code
        if isinstance(code, str):
            err.write(code + "\n")
            code = 1
        return code or 0, out.getvalue(), err.getvalue()


class TestStateKey(World):
    def test_the_key_is_not_an_unknown_state_id_and_the_warning_skips_it(self):
        tune.save_state(self.work, "ks_x", {"limiter": 7000, tune.TYRE_KEY: [ST_AB], "old": 1})
        self.assertEqual(tune.unknown_state_ids(self.work, "ks_x", self.cat), ["old"])
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            tune.warn_unknown_state(self.work, "ks_x", self.cat)
        self.assertEqual(err.getvalue(), "warning: ignoring unknown setting 'old' in the saved state\n")
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: [ST_AB]}, tune.DRAFT)
        self.assertEqual(tune.unknown_state_ids(self.work, "ks_x", self.cat, tune.DRAFT), [])

    def test_the_key_is_no_row_and_not_shown(self):
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: [ST_AB]})
        for hidden in (False, True):
            self.assertNotIn(tune.TYRE_KEY, [r["id"] for r in tune.effective_rows(self.work, "ks_x", self.cat, hidden=hidden)])
        code, out, err = self.run_main("show")
        self.assertEqual((code, err), (0, ""))
        self.assertNotIn("_tyres", out)
        code, out, err = self.run_main("defaults")
        self.assertNotIn("_tyres", out + err)

    def test_set_and_unset_of_settings_keep_the_key_and_unset_does_not_touch_it(self):
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: [ST_AB]})
        tune.set_value(self.work, "ks_x", "tyre_dy_front", "1.4", self.cat)
        self.assertEqual(self.state()[tune.TYRE_KEY], [ST_AB])
        tune.unset_value(self.work, "ks_x", "tyre_dy_front", self.cat)
        self.assertEqual(self.state(), {tune.TYRE_KEY: [ST_AB]})
        with self.assertRaisesRegex(ValueError, "^unknown setting '_tyres'$"):
            tune.unset_value(self.work, "ks_x", tune.TYRE_KEY, self.cat)
        with self.assertRaisesRegex(ValueError, "^unknown setting '_tyres'$"):
            tune.set_value(self.work, "ks_x", tune.TYRE_KEY, "x", self.cat)
        self.assertEqual(self.state(), {tune.TYRE_KEY: [ST_AB]})

    def test_duplicate_tune_copies_the_key_with_the_rest_of_the_state(self):
        tune.save_state(self.work, "ks_x", {"limiter": 8000, tune.TYRE_KEY: ["own:soft", ST_AB]})
        res = tune.duplicate_tune(self.work, "ks_x", None)
        self.assertEqual(self.state(res["id"])[tune.TYRE_KEY], ["own:soft", ST_AB])
        copied = self.state(res["id"])
        copied[tune.TYRE_KEY].append(ST_SS)
        tune.save_state(self.work, "ks_x", copied, res["id"])
        self.assertEqual(self.state()[tune.TYRE_KEY], ["own:soft", ST_AB])
        again = tune.duplicate_tune(self.work, "ks_x", res["id"])
        self.assertEqual(self.state(again["id"])[tune.TYRE_KEY], ["own:soft", ST_AB, ST_SS])
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: [ST_WW]}, tune.DRAFT)
        res = tune.duplicate_tune(self.work, "ks_x", tune.DRAFT)
        self.assertEqual(self.state(res["id"])[tune.TYRE_KEY], [ST_WW])

    def test_new_tune_from_draft_copies_the_key_and_the_draft_keeps_it(self):
        tune.save_state(self.work, "ks_x", {"limiter": 9000, tune.TYRE_KEY: ["own:soft"]}, tune.DRAFT)
        res = tune.new_tune_from_draft(self.work, "ks_x")
        self.assertEqual(self.state(res["id"]), {"limiter": 9000, tune.TYRE_KEY: ["own:soft"], "name_suffix": "_MY"})
        self.assertEqual(self.state(tune.DRAFT), {"limiter": 9000, tune.TYRE_KEY: ["own:soft"]})
        tune.save_state(self.work, "ks_x", {}, tune.DRAFT)
        self.assertEqual(self.state(tune.DRAFT), {})
        self.assertEqual(self.state(res["id"])[tune.TYRE_KEY], ["own:soft"])

    def test_the_key_parser(self):
        self.assertEqual(tune.garage_key("own:soft"), ("own", "soft"))
        self.assertEqual(tune.garage_key(ST_AB), ("stock", KEY_AB))
        for bad in ("own:", "stock:", "OWN:soft", "soft", "game:soft", "", None, 5, ["own:soft"]):
            with self.subTest(repr(bad)):
                self.assertIsNone(tune.garage_key(bad))

    def test_tyre_users_count_own_entries_between_stock_ones_only(self):
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: [ST_AB, "own:soft", ST_SS]})
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: [ST_AB, 5, None]}, tune.DRAFT)
        self.assertEqual(tune.tyre_users(self.work, "soft"), [{"car": "ks_x", "tune": "ax_x"}])
        self.assertEqual(tune.tyre_users(self.work, "slick"), [])

    def test_a_selection_that_is_not_a_list_is_an_error_where_it_is_read_as_a_selection(self):
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: "own:soft"})
        for call in (lambda: tune.garage_choices(self.work, "ks_x"), lambda: tune.saved_garage(self.state())):
            with self.assertRaisesRegex(ValueError, r"^the saved tyre selection \(_tyres\) must be a list of tyre keys$"):
                call()
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: ["own:soft", 5]})
        with self.assertRaisesRegex(ValueError, "must be a list of tyre keys"):
            tune.garage_choices(self.work, "ks_x")


class TestStockTyres(World):
    def test_the_pairs_come_in_the_order_of_the_first_preset_and_are_deduplicated(self):
        found = tune.car_stock_tyres(self.work, "ks_x")
        self.assertEqual([s["key"] for s in found], [ST_AB, ST_SS, ST_WW])
        self.assertEqual(found[0], {"key": ST_AB, "label": "tyres\\road\\a + tyres\\road\\b", "front": A, "rear": B})
        self.assertEqual(found[1], {"key": ST_SS, "label": "tyres\\slick\\s", "front": S, "rear": S})

    def test_a_later_preset_adds_only_pairs_the_earlier_ones_do_not_have(self):
        self.x.add_shared("tyres/gt/f.tyre", tyre_obj(2.0))
        self.x.add_shared("tyres/gt/r.tyre", tyre_obj(2.5))
        self.x.add("presets/r.compatibletyres", {"physic_compounds": [{"front_tyre_data_path": S, "rear_tyre_data_paths": S},
                                                                       {"front_tyre_data_path": G_F.upper(), "rear_tyre_data_paths": [G_R.replace("\\", "/")]}]})
        self.assertEqual([s["key"] for s in tune.car_stock_tyres(self.work, "ks_x")], [ST_AB, ST_SS, ST_WW, "stock:" + KEY_GG])

    def test_pairs_without_a_shared_file_in_the_base_or_without_text_paths_are_skipped(self):
        self.p["physic_compounds"] += [
            {"front_tyre_data_path": A, "rear_tyre_data_paths": GS + "tyres\\road\\missing.tyre"}, {"front_tyre_data_path": A},
            {"front_tyre_data_path": A, "rear_tyre_data_paths": []}, {"rear_tyre_data_paths": B}, {"name": "empty"}]
        self.assertEqual([s["key"] for s in tune.car_stock_tyres(self.work, "ks_x")], [ST_AB, ST_SS, ST_WW])
        os.remove(os.path.join(self.x.shared, "tyres", "wet", "w.tyre"))
        self.assertEqual([s["key"] for s in tune.car_stock_tyres(self.work, "ks_x")], [ST_AB, ST_SS])

    def test_a_car_without_a_base_or_without_presets_or_with_a_damaged_preset_has_none(self):
        self.assertEqual(tune.car_stock_tyres(self.work, "ks_none"), [])
        self.assertEqual(tune.car_stock_tyres(self.work, "ks_y")[0]["front"], G_F)
        os.remove(os.path.join(self.y.car_root, "presets", "y.compatibletyres"))
        os.rmdir(os.path.join(self.y.car_root, "presets"))
        self.assertEqual(tune.car_stock_tyres(self.work, "ks_y"), [])

    def test_only_the_pairs_of_the_cars_own_base_count(self):
        self.assertNotIn("stock:" + KEY_GG, self.stock_keys())
        self.assertEqual([s["key"] for s in tune.car_stock_tyres(self.work, "ks_y")], ["stock:" + KEY_GG])

    def test_compound_pair_is_what_preset_tyre_pairs_reads(self):
        self.assertEqual(tune.compound_pair({"front_tyre_data_path": A_UP, "rear_tyre_data_paths": [S, B]}), (A, S))
        self.assertEqual(tune.compound_pair({"front_tyre_data_path": "content/cars/common_phsx/tyres/road/a.tyre", "rear_tyre_data_paths": B}),
                         (A, B))
        for bad in ({}, {"front_tyre_data_path": A}, {"front_tyre_data_path": A, "rear_tyre_data_paths": []}, {"rear_tyre_data_paths": B},
                    {"front_tyre_data_path": 5, "rear_tyre_data_paths": B}, "x", None):
            self.assertIsNone(tune.compound_pair(bad))


class TestChoices(World):
    def keys(self, res, **match):
        return [c["key"] for c in res["choices"] if all(c[k] == v for k, v in match.items())]

    def test_without_a_selection_every_stock_tyre_is_ticked_and_the_first_one_starts(self):
        res = tune.garage_choices(self.work, "ks_x")
        self.assertEqual((res["custom"], res["missing"]), (False, []))
        self.assertEqual([(c["key"], c["kind"], c["ticked"], c["start"]) for c in res["choices"]],
                         [(ST_AB, "stock", True, True), (ST_SS, "stock", True, False), (ST_WW, "stock", True, False)])
        self.assertEqual(res["choices"][0]["label"], "tyres\\road\\a + tyres\\road\\b")
        self.assertEqual(set(res["choices"][0]), {"key", "kind", "label", "ticked", "start"})

    def test_own_tyres_come_first_by_name_ignoring_case_and_are_not_ticked_by_default(self):
        self.tyres()
        res = tune.garage_choices(self.work, "ks_x")
        self.assertEqual(self.keys(res), ["own:gt", "own:slicky", "own:soft", ST_AB, ST_SS, ST_WW])
        self.assertEqual([c["label"] for c in res["choices"][:3]], ["gt", "Slicky", "Soft"])
        self.assertEqual((self.keys(res, ticked=True), self.keys(res, start=True)), ([ST_AB, ST_SS, ST_WW], [ST_AB]))
        self.assertEqual({c["kind"] for c in res["choices"][:3]}, {"own"})

    def test_a_saved_selection_ticks_its_keys_and_the_first_ticked_choice_starts(self):
        self.tyres()
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: [ST_WW, "own:soft", ST_AB]})
        res = tune.garage_choices(self.work, "ks_x")
        self.assertEqual((res["custom"], res["missing"]), (True, []))
        self.assertEqual(self.keys(res, ticked=True), ["own:soft", ST_AB, ST_WW])
        self.assertEqual(self.keys(res, start=True), ["own:soft"])

    def test_the_start_is_a_stock_tyre_when_no_own_tyre_is_ticked(self):
        self.tyres()
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: [ST_WW, ST_SS]})
        self.assertEqual(self.keys(tune.garage_choices(self.work, "ks_x"), start=True), [ST_SS])

    def test_keys_that_are_no_choice_any_more_are_reported_as_missing_and_not_listed(self):
        self.tyres()
        self.write(os.path.join(self.work, "tyres", "broken.json"), "{")
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: ["own:gone", "own:broken", "own:soft", "stock:x|y", "junk", "own:gone", ST_AB]})
        res = tune.garage_choices(self.work, "ks_x")
        self.assertEqual(res["missing"], ["own:gone", "own:broken", "stock:x|y", "junk"])
        self.assertEqual(self.keys(res), ["own:gt", "own:slicky", "own:soft", ST_AB, ST_SS, ST_WW])
        self.assertEqual(self.keys(res, ticked=True), ["own:soft", ST_AB])

    def test_an_empty_saved_selection_ticks_nothing(self):
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: []})
        res = tune.garage_choices(self.work, "ks_x")
        self.assertEqual((res["custom"], self.keys(res, ticked=True), self.keys(res, start=True)), (True, [], []))

    def test_a_car_without_presets_and_an_empty_library_has_no_choices(self):
        self.assertEqual(tune.garage_choices(self.work, "ks_none"), {"choices": [], "custom": False, "missing": []})

    def test_each_tune_and_the_draft_have_their_own_selection(self):
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: [ST_SS]})
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: [ST_WW]}, "ax01")
        tune.save_state(self.work, "ks_x", {}, tune.DRAFT)
        self.assertEqual([self.keys(tune.garage_choices(self.work, "ks_x", t), start=True) for t in (None, "ax_x", "ax01", tune.DRAFT)],
                         [[ST_SS], [ST_SS], [ST_WW], [ST_AB]])
        self.assertEqual(tune.garage_choices(self.work, "ks_x", tune.DRAFT)["custom"], False)

    def test_nothing_is_written(self):
        self.tyres()
        before = sorted(os.walk(self.work))
        tune.garage_choices(self.work, "ks_x")
        self.assertEqual(sorted(os.walk(self.work)), before)


class TestSetGarage(World):
    def setUp(self):
        super().setUp()
        self.tyres()

    def test_the_keys_are_sorted_into_the_fixed_order_and_stored(self):
        res = tune.set_garage(self.work, "ks_x", [ST_WW, "own:soft", ST_AB, "own:gt"])
        self.assertEqual(res, {"keys": ["own:gt", "own:soft", ST_AB, ST_WW], "start": "own:gt"})
        self.assertEqual(self.state(), {tune.TYRE_KEY: ["own:gt", "own:soft", ST_AB, ST_WW]})
        with open(tune.state_path(self.work, "ks_x"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), self.state())

    def test_the_start_is_the_first_stock_tyre_without_an_own_one(self):
        self.assertEqual(tune.set_garage(self.work, "ks_x", [ST_WW, ST_SS]), {"keys": [ST_SS, ST_WW], "start": ST_SS})

    def test_the_state_keeps_the_other_entries(self):
        tune.save_state(self.work, "ks_x", {"limiter": 8000, "old": 1})
        tune.set_garage(self.work, "ks_x", ["own:soft"])
        self.assertEqual(self.state(), {"limiter": 8000, "old": 1, tune.TYRE_KEY: ["own:soft"]})

    def test_a_second_call_replaces_the_selection(self):
        tune.set_garage(self.work, "ks_x", ["own:soft", ST_AB])
        tune.set_garage(self.work, "ks_x", [ST_SS])
        self.assertEqual(self.state(), {tune.TYRE_KEY: [ST_SS]})

    def test_all_stock_tyres_and_no_own_tyre_is_the_default_and_removes_the_key(self):
        tune.set_garage(self.work, "ks_x", ["own:soft"])
        tune.save_state(self.work, "ks_x", dict(self.state(), limiter=8000))
        res = tune.set_garage(self.work, "ks_x", [ST_WW, ST_AB, ST_SS])
        self.assertEqual(res, {"keys": [ST_AB, ST_SS, ST_WW], "start": ST_AB, "default": True})
        self.assertEqual(self.state(), {"limiter": 8000})

    def test_the_default_writes_no_state_file_when_there_is_no_key_to_remove(self):
        res = tune.set_garage(self.work, "ks_x", [ST_AB, ST_SS, ST_WW], tune="ax01")
        self.assertTrue(res["default"])
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "tunes")))

    def test_a_part_of_the_stock_tyres_or_stock_and_own_is_not_the_default(self):
        self.assertNotIn("default", tune.set_garage(self.work, "ks_x", [ST_AB, ST_SS]))
        self.assertNotIn("default", tune.set_garage(self.work, "ks_x", [ST_AB, ST_SS, ST_WW, "own:soft"]))
        self.assertEqual(self.state()[tune.TYRE_KEY], ["own:soft", ST_AB, ST_SS, ST_WW])

    def test_the_selection_goes_to_the_chosen_tune_or_the_draft_only(self):
        tune.set_garage(self.work, "ks_x", [ST_SS], tune.DRAFT)
        tune.set_garage(self.work, "ks_x", [ST_WW], "ax01")
        tune.set_garage(self.work, "ks_x", ["own:soft"], "ax_x")
        self.assertEqual([self.state(t).get(tune.TYRE_KEY) for t in (None, "ax01", tune.DRAFT)], [["own:soft"], [ST_WW], [ST_SS]])
        with open(os.path.join(self.work, "ks_x", "tunes", "ax01", "meta.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"stock": "ks_x"})

    def test_errors_change_nothing(self):
        tune.set_garage(self.work, "ks_x", [ST_SS])
        before = self.state()
        self.write(os.path.join(self.work, "tyres", "broken.json"), "{")
        for keys, message in (([], "^tick at least one tyre$"), ("own:soft", "must be a list"), (None, "must be a list"), ((ST_AB,), "must be a list"),
                              (["own:soft", "own:soft"], "^tyre key own:soft is listed twice$"), ([ST_AB, ST_AB], "listed twice"),
                              (["stock:%s|%s" % (A, A)], "^unknown stock tyre %s of ks_x" % re.escape(A + "|" + A)),
                              (["stock:" + KEY_GG], "unknown stock tyre"), (["own:nope"], "^no tyre 'nope' in the library$"),
                              (["own:broken"], "broken.json"), (["own:Soft"], "^bad tyre id 'Soft'"), (["own:../x"], "^bad tyre id"),
                              ([5], "^a tyre key must be text, got 5$"), ([None], "must be text"), ([["own:soft"]], "must be text"),
                              (["soft"], "^bad tyre key 'soft'"), (["own:"], "^bad tyre key 'own:'"), (["OWN:soft"], "^bad tyre key"),
                              (["stock:"], "^bad tyre key"), ([ST_AB, "own:nope"], "^no tyre 'nope'")):
            with self.subTest(keys=keys), self.assertRaisesRegex(ValueError, message):
                tune.set_garage(self.work, "ks_x", keys)
            self.assertEqual(self.state(), before)

    def test_an_invalid_tune_id_is_refused(self):
        for bad in ("ks_x", "AX01", "ax"):
            with self.subTest(bad), self.assertRaises(ValueError):
                tune.set_garage(self.work, "ks_x", [ST_SS], bad)

    def test_the_key_text_of_a_stock_tyre_is_the_key_of_the_tyre_sources(self):
        sources = [e["key"] for e in tune.list_source_tyres(self.work)]
        self.assertEqual(self.stock_keys(), ["stock:" + k for k in (KEY_AB, KEY_SS, W + "|" + W)])
        self.assertEqual(sorted(k for k in sources if "stock:" + k in self.stock_keys()), sorted(k[len("stock:"):] for k in self.stock_keys()))


class TestResetGarage(World):
    def test_reset_removes_the_key_and_keeps_the_rest(self):
        tune.save_state(self.work, "ks_x", {"limiter": 8000, tune.TYRE_KEY: [ST_SS]})
        self.assertEqual(tune.reset_garage(self.work, "ks_x"), {"removed": True})
        self.assertEqual(self.state(), {"limiter": 8000})
        self.assertEqual(tune.reset_garage(self.work, "ks_x"), {"removed": False})

    def test_reset_of_an_empty_selection_counts_as_removed(self):
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: []})
        self.assertEqual(tune.reset_garage(self.work, "ks_x"), {"removed": True})
        self.assertEqual(self.state(), {})

    def test_reset_writes_nothing_without_a_key_and_follows_the_tune(self):
        self.assertEqual(tune.reset_garage(self.work, "ks_x", "ax01"), {"removed": False})
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "tunes")))
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: [ST_SS]}, tune.DRAFT)
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: [ST_SS]})
        self.assertTrue(tune.reset_garage(self.work, "ks_x", tune.DRAFT)["removed"])
        self.assertEqual(self.state(), {tune.TYRE_KEY: [ST_SS]})

    def test_the_reset_selection_is_the_default_again(self):
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: [ST_SS]})
        tune.reset_garage(self.work, "ks_x")
        self.assertFalse(tune.garage_choices(self.work, "ks_x")["custom"])


class TestHelpers(unittest.TestCase):
    def test_set_list_follows_the_wire_order(self):
        obj = {"a": 1, "k": ["x", "y"], "_order": ["k", "a", "k"]}
        tune.set_list(obj, "k", ["p"])
        self.assertEqual((obj["k"], obj["_order"]), (["p"], ["k", "a"]))
        tune.set_list(obj, "k", ["p", "q", "r"])
        self.assertEqual(obj["_order"], ["k", "k", "k", "a"])

    def test_set_list_of_a_field_that_is_not_in_the_wire_order_appends_it(self):
        obj = {"a": 1, "_order": ["a"]}
        tune.set_list(obj, "k", ["p", "q"])
        self.assertEqual((obj["k"], obj["_order"]), (["p", "q"], ["a", "k", "k"]))

    def test_set_list_without_a_wire_order_just_sets_the_list(self):
        obj = {"k": ["x"]}
        tune.set_list(obj, "k", ["p", "q"])
        self.assertEqual(obj, {"k": ["p", "q"]})

    def plan(self, *entries):
        return {"entries": list(entries), "front_known": {A, S}, "rear_known": {B, S}}

    def test_garage_list_orders_the_ticked_tyres_keeps_their_text_and_puts_the_unknown_last(self):
        own = {"kind": "own", "front_text": "own_f", "rear_text": "own_r"}
        stock_ab = {"kind": "stock", "front": A, "rear": B}
        stock_w = {"kind": "stock", "front": W, "rear": W}
        current = [S, A_UP, "odd.tyre", W, "ODD.TYRE", 5]
        self.assertEqual(tune.garage_list(current, self.plan(own, stock_ab, stock_w), "front", {W: "texts_w"}),
                         ["own_f", A_UP, W, "odd.tyre", 5])
        self.assertEqual(tune.garage_list([], self.plan(stock_ab), "rear", {B: "text_b"}), ["text_b"])
        self.assertEqual(tune.garage_list([], self.plan(stock_ab), "rear", {}), [B])

    def test_garage_list_does_not_repeat_an_entry_that_is_a_ticked_one(self):
        own = {"kind": "own", "front_text": "OWN_F", "rear_text": "own_r"}
        self.assertEqual(tune.garage_list(["own_f", "x"], self.plan(own), "front", {}), ["OWN_F", "x"])


class Apply(World):
    """apply of ks_x with clone_car.build and kspkg.cmd_pack stubbed; the files of the build are the stub contents of FakeCar."""

    def setUp(self):
        super().setUp()
        self.calls, self.packed, self.real_pack = [], [], False
        self.patch(clone_car, "build", self.build)
        self.patch(kspkg, "cmd_pack", self.pack)
        self.patch(tune, "ensure_stock_loc", lambda work, game=None: "present")
        self.patch(os, "rename", self.rename)
        stub = tune.save_msg

        def save_and_touch(path, name, obj):
            stub(path, name, obj)
            with open(kspkg.long_path(path), "wb"):
                pass
        self.patch(tune, "save_msg", save_and_touch)
        self.game = os.path.join(self.work, "no_game.kspkg")

    def rename(self, src, dst):
        old, new = self.x.key(src), self.x.key(dst)
        moved = [k for k in self.x.store if k.startswith(old + os.sep)]
        REAL_RENAME(src, dst)
        self.x.store.update({new + k[len(old):]: self.x.store.pop(k) for k in moved})

    def build(self, car_dir, new_id, out_dir, name, year, brand, variant, stock_loc, props, pack=True):
        self.calls.append(("build", new_id))
        print("progress noise of the clone")
        self.x.clone_into(out_dir, new_id)
        return ["note: from build"]

    def pack(self, indir, pkg):
        self.calls.append(("pack", indir))
        self.packed.append(sorted(os.path.relpath(os.path.join(dp, n), indir).replace(os.sep, "/")
                                  for dp, _, names in os.walk(indir) for n in names))
        if self.real_pack:
            REAL_PACK(indir, pkg)
        else:
            with open(pkg, "wb") as f:
                f.write(b"PKG-NEW")

    def apply(self, state=None, **kw):
        if state is not None:
            tune.save_state(self.work, "ks_x", state)
        kw.setdefault("install", False)
        return tune.apply(self.work, "ks_x", catalogue=self.cat, game=self.game, **kw)

    def built(self, res, rel):
        return self.x.store[self.x.key(os.path.join(res["build_dir"], "content", "cars", res["new_id"], *rel.split("/")))]

    def tree(self, res):
        root = os.path.join(res["build_dir"], "content", "cars", res["new_id"])
        return sorted(os.path.relpath(os.path.join(dp, n), root).replace(os.sep, "/") for dp, _, names in os.walk(root) for n in names)

    def compounds(self, res, name):
        return self.built(res, "presets/%s.compatibletyres" % name)["physic_compounds"]

    def lists(self, res):
        car = self.built(res, "data/x.car")
        return car["frontTyreCompounds"], car["rearTyreCompounds"]

    def snapshot(self, res):
        root = self.x.key(os.path.join(res["build_dir"], "content", "cars", res["new_id"]))
        return {k[len(root):]: json.dumps(v, sort_keys=True) for k, v in self.x.store.items() if k.startswith(root + os.sep)}

    def select(self, *keys):
        tune.set_garage(self.work, "ks_x", list(keys))

    def own_value(self, tyre_id, **values):
        for sid, v in values.items():
            tune.set_tyre_value(self.work, tyre_id, sid, v, self.cat)


class TestApplyWithoutASelection(Apply):
    def test_without_the_key_nothing_of_the_garage_runs_and_the_build_keeps_its_stock_data(self):
        self.patch(tune, "garage_plan", lambda *a, **k: self.fail("garage_plan"))
        self.patch(tune, "write_garage", lambda *a, **k: self.fail("write_garage"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            res = self.apply({"name_suffix": "_Z"})
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(res["notes"], ["note: from build"])
        self.assertEqual([a["id"] for a in res["applied"]], ["name_suffix"])
        self.assertEqual(self.lists(res), ([A_UP, S, W, M], [B, S, W]))
        self.assertEqual(self.compounds(res, "p")[0], self.p["physic_compounds"][0])
        self.assertEqual(self.compounds(res, "p")[3]["front_tyre_data_path"], "content\\cars\\ax_x\\data\\tyres\\odd.tyre")
        self.assertEqual(self.built(res, "presets/q.compatibletyres"), self.q)
        self.assertEqual([t for t in self.tree(res) if "own_" in t], [])

    def test_the_default_selection_after_a_reset_builds_like_a_car_that_never_had_one(self):
        first = self.apply({"name_suffix": "_Z"})
        before, tree = self.snapshot(first), self.tree(first)
        tune.save_state(self.work, "ks_x", {"name_suffix": "_Z", tune.TYRE_KEY: [ST_SS]})
        self.apply()
        tune.set_garage(self.work, "ks_x", self.stock_keys())
        second = self.apply()
        self.assertEqual((self.snapshot(second), self.tree(second), second["notes"], second["applied"]),
                         (before, tree, first["notes"], first["applied"]))

    def test_a_tyre_setting_alone_works_as_before(self):
        res = self.apply({"tyre_dy_front": 1.4})
        self.assertIn("tyre front: own file content\\cars\\ax_x\\data\\tyres\\ax_x_front.tyre replaces", res["notes"][-1])
        self.assertEqual(len(res["notes"]), 2)


class TestApplyOwnTyre(Apply):
    def test_an_own_tyre_alone_gives_lists_with_only_its_paths(self):
        self.tyres()
        self.select("own:soft")
        res = self.apply()
        self.assertEqual(self.lists(res), ([OWN_F % "soft", M], [OWN_R % "soft"]))
        self.assertEqual(res["applied"], [])

    def test_the_own_files_hold_the_source_data_with_the_library_values_in_both_axles(self):
        self.tyres()
        self.own_value("soft", tyre_dy_front="1.5", tyre_th_front="slick", tyre_dy_rear="1.3")
        self.select("own:soft")
        res = self.apply()
        front, rear = self.built(res, "data/tyres/own_soft_front.tyre"), self.built(res, "data/tyres/own_soft_rear.tyre")
        self.assertEqual([tune.plain(front["modelData"][k]) for k in ("Dy0", "Dy1", "Fz0")], [1.5, 1.5, 3000])
        self.assertEqual(front["thermalData"], {"thermalPerformanceCurve": CURVES["slick"], "x": 1})
        self.assertEqual((tune.plain(rear["modelData"]["Dy0"]), rear["modelData"]["Dy1"], rear["modelData"]["Fz0"]), (1.3, 1.1, 3000))
        self.assertEqual(rear["thermalData"], tyre_obj(1.1)["thermalData"])
        self.assertIsInstance(front["modelData"]["Dy0"], tune.car_json.F32)

    def test_a_tyre_without_values_is_a_plain_copy_of_its_source_files(self):
        self.tyres()
        self.select("own:soft")
        res = self.apply()
        self.assertEqual(self.built(res, "data/tyres/own_soft_front.tyre"), tyre_obj(1.2))
        self.assertEqual(self.built(res, "data/tyres/own_soft_rear.tyre"), tyre_obj(1.1))

    def test_the_shared_source_files_stay_untouched(self):
        self.tyres()
        self.own_value("soft", tyre_dy_front="1.5")
        self.select("own:soft")
        before = {k: json.dumps(v, sort_keys=True) for k, v in self.x.store.items()}
        self.apply()
        self.assertEqual({k: json.dumps(v, sort_keys=True) for k, v in self.x.store.items() if k in before}, before)
        self.assertTrue(all(p.startswith(self.x.key(os.path.join(self.work, "ks_x", "build"))) for p in self.x.saved))

    def test_the_presets_get_a_copy_of_the_compound_of_the_source_pair_with_everything_else_intact(self):
        self.tyres()
        self.select("own:soft")
        res = self.apply()
        template = self.p["physic_compounds"][0]
        self.assertEqual(self.compounds(res, "p")[0], dict(template, front_tyre_data_path=OWN_F % "soft", rear_tyre_data_paths=OWN_R % "soft"))
        self.assertEqual(self.compounds(res, "q"), [{"front_tyre_data_path": OWN_F % "soft", "rear_tyre_data_paths": OWN_R % "soft", "name": "q_road"}])
        self.assertEqual(self.built(res, "presets/p.compatibletyres")["default_index"], 0)

    def test_compounds_that_no_stock_pair_names_are_appended_unchanged(self):
        self.tyres()
        self.select("own:soft")
        res = self.apply()
        self.assertEqual([c["name"] for c in self.compounds(res, "p")], ["road", "odd"])
        self.assertEqual(self.compounds(res, "p")[1], dict(self.p["physic_compounds"][3], front_tyre_data_path="content\\cars\\ax_x\\data\\tyres\\odd.tyre"))

    def test_a_list_rear_stays_a_list_with_one_element_and_the_wire_orders_follow(self):
        self.tyres()
        self.select("own:slicky")
        res = self.apply()
        own = self.compounds(res, "p")[0]
        self.assertEqual((own["front_tyre_data_path"], own["rear_tyre_data_paths"], own["name"]), (OWN_F % "slicky", [OWN_R % "slicky"], "slick"))
        self.assertEqual(own["_order"], ["front_tyre_data_path", "rear_tyre_data_paths", "name"])
        self.assertEqual(self.p["physic_compounds"][1]["rear_tyre_data_paths"], [S, B])
        self.assertEqual(self.compounds(res, "q")[0]["rear_tyre_data_paths"], [OWN_R % "slicky"])
        self.assertEqual(self.built(res, "presets/p.compatibletyres")["_order"], ["physic_compounds"] * 2)
        car = self.built(res, "data/x.car")
        self.assertEqual((car["_order"].count("frontTyreCompounds"), car["_order"].count("rearTyreCompounds")), (2, 1))

    def test_an_own_tyre_whose_source_only_another_car_offers_is_copied_from_that_base(self):
        self.tyres()
        self.own_value("gt", tyre_dy_front="1.9")
        self.select("own:gt")
        res = self.apply()
        front, rear = self.built(res, "data/tyres/own_gt_front.tyre"), self.built(res, "data/tyres/own_gt_rear.tyre")
        self.assertEqual((tune.plain(front["modelData"]["Dy0"]), tune.plain(front["modelData"]["Dy1"]), tune.plain(rear["modelData"]["Dy0"])), (1.9, 1.9, 2.5))
        self.assertEqual(self.lists(res), ([OWN_F % "gt", M], [OWN_R % "gt"]))
        self.assertEqual(self.compounds(res, "p")[0]["name"], "road")
        self.assertEqual(self.compounds(res, "q")[0]["name"], "q_slick")
        self.assertEqual(self.compounds(res, "q")[0]["rear_tyre_data_paths"], [OWN_R % "gt"])

    def test_the_source_files_come_from_the_same_car_as_the_defaults_of_the_tyre_editor(self):
        self.y.add("presets/y.compatibletyres", {"physic_compounds": [{"front_tyre_data_path": G_F, "rear_tyre_data_paths": G_R},
                                                                       {"front_tyre_data_path": A, "rear_tyre_data_paths": B}]})
        self.y.add_shared("tyres/road/a.tyre", tyre_obj(7.0))
        self.y.add_shared("tyres/road/b.tyre", tyre_obj(7.5))
        self.tyres()
        self.assertEqual(tune.tyre_rows(self.work, "soft", self.cat)[0]["default"], 1.2)
        self.select("own:soft")
        self.assertEqual(tune.plain(self.built(self.apply(), "data/tyres/own_soft_front.tyre")["modelData"]["Dy0"]), 1.2)

    def test_a_setting_with_a_value_the_source_file_cannot_take_is_an_error_before_building(self):
        self.tyres()
        self.own_value("soft", tyre_deep_front="2")
        self.select("own:soft")
        with self.assertRaisesRegex(ValueError, r"^garage: tyre soft: tyre_deep_front cannot be written into the source file: modelData\.nope\.x"):
            self.apply()
        self.assertEqual(self.calls, [])

    def test_library_values_of_settings_the_catalogue_does_not_have_any_more_are_ignored(self):
        self.tyres()
        self.write(os.path.join(self.work, "tyres", "soft.json"), {"version": 1, "name": "Soft", "source": {"front": A, "rear": B},
                                                                    "values": {"gone": 1, "tyre_dy_front": 1.6}})
        self.select("own:soft")
        res = self.apply()
        self.assertEqual(tune.plain(self.built(res, "data/tyres/own_soft_front.tyre")["modelData"]["Dy0"]), 1.6)

    def test_a_value_that_does_not_fit_its_setting_is_an_error_before_building(self):
        self.tyres()
        self.write(os.path.join(self.work, "tyres", "soft.json"), {"version": 1, "name": "Soft", "source": {"front": A, "rear": B},
                                                                    "values": {"tyre_dy_front": "fast"}})
        self.select("own:soft")
        with self.assertRaisesRegex(ValueError, "^garage: tyre soft: tyre_dy_front expects a number"):
            self.apply()
        self.assertEqual(self.calls, [])


class TestApplyMixedSelections(Apply):
    def test_own_tyres_come_first_then_the_ticked_stock_tyres_in_the_order_of_the_presets(self):
        self.tyres()
        self.select(ST_WW, "own:soft", ST_AB, "own:gt")
        self.assertEqual(self.state()[tune.TYRE_KEY], ["own:gt", "own:soft", ST_AB, ST_WW])
        res = self.apply()
        self.assertEqual(self.lists(res), ([OWN_F % "gt", OWN_F % "soft", A_UP, W, M], [OWN_R % "gt", OWN_R % "soft", B, W]))
        self.assertEqual([c["name"] for c in self.compounds(res, "p")], ["road", "road", "road", "wet", "odd"])
        self.assertEqual([c["front_tyre_data_path"] for c in self.compounds(res, "p")][:4],
                         [OWN_F % "gt", OWN_F % "soft", A, W])
        self.assertEqual([c["name"] for c in self.compounds(res, "q")], ["q_slick", "q_road", "q_road"])
        self.assertEqual(self.compounds(res, "q")[2], self.q["physic_compounds"][1])

    def test_a_stock_tyre_keeps_the_text_of_the_list_and_a_compound_that_the_file_lacks_is_skipped(self):
        self.select(ST_AB, ST_WW)
        res = self.apply()
        self.assertEqual(self.lists(res)[0][0], A_UP)
        self.assertEqual([c["name"] for c in self.compounds(res, "q")], ["q_road"])
        self.assertEqual([c["name"] for c in self.compounds(res, "p")], ["road", "wet", "odd"])

    def test_unticked_stock_tyres_are_dropped_from_the_car_and_the_presets(self):
        self.select(ST_SS)
        res = self.apply()
        self.assertEqual(self.lists(res), ([S, M], [S]))
        self.assertEqual([c["name"] for c in self.compounds(res, "p")], ["slick", "odd"])
        self.assertEqual(self.compounds(res, "p")[0], self.p["physic_compounds"][1])
        self.assertEqual([c["name"] for c in self.compounds(res, "q")], ["q_slick"])
        self.assertEqual(self.tree(res).count("data/x.car"), 1)

    def test_an_entry_of_the_tyre_lists_that_no_preset_pair_names_stays_at_the_end(self):
        self.car["frontTyreCompounds"] += [self.x.game_path("data/tyres/odd.tyre"), M.upper()]
        self.car["rearTyreCompounds"].insert(0, M)
        self.select(ST_SS, ST_AB)
        res = self.apply()
        self.assertEqual(self.lists(res), ([A_UP, S, M, "content\\cars\\ax_x\\data\\tyres\\odd.tyre"], [B, S, M]))

    def test_the_wire_order_of_the_car_follows_the_new_lengths(self):
        self.select(ST_SS, ST_AB)
        res = self.apply()
        car = self.built(res, "data/x.car")
        self.assertEqual((car["_order"].count("frontTyreCompounds"), car["_order"].count("rearTyreCompounds")),
                         (len(car["frontTyreCompounds"]), len(car["rearTyreCompounds"])))
        self.assertEqual(self.built(res, "presets/p.compatibletyres")["_order"], ["physic_compounds"] * len(self.compounds(res, "p")))

    def test_the_first_ticked_tyre_is_element_zero_of_both_lists(self):
        self.tyres()
        for keys, first in (([ST_SS, ST_WW], (S, S)), (["own:soft", ST_AB], (OWN_F % "soft", OWN_R % "soft")), ([ST_WW, ST_AB], (A_UP, B))):
            with self.subTest(keys):
                self.select(*keys)
                lists = self.lists(self.apply())
                self.assertEqual((lists[0][0], lists[1][0]), first)

    def test_a_preset_file_that_would_have_no_compound_is_an_error_naming_it_and_nothing_is_built(self):
        self.x.add("presets/r.compatibletyres", {"physic_compounds": [{"front_tyre_data_path": W, "rear_tyre_data_paths": W}]})
        self.select(ST_AB)
        with self.assertRaisesRegex(ValueError, r"^garage: presets/r\.compatibletyres would be left without a tyre compound"):
            self.apply()
        self.assertEqual(self.calls, [])
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "build")))

    def test_an_own_tyre_keeps_such_a_file_alive_with_a_copy_of_its_first_compound(self):
        self.tyres()
        self.x.add("presets/r.compatibletyres", {"physic_compounds": [{"front_tyre_data_path": W, "rear_tyre_data_paths": W, "name": "r_wet"}]})
        self.select("own:soft", ST_AB)
        res = self.apply()
        self.assertEqual([c["name"] for c in self.compounds(res, "r")], ["r_wet"])
        self.assertEqual(self.compounds(res, "r")[0]["front_tyre_data_path"], OWN_F % "soft")

    def test_an_empty_preset_file_is_an_error_even_with_a_selection_of_own_tyres(self):
        self.tyres()
        self.x.add("presets/r.compatibletyres", {"physic_compounds": []})
        self.select("own:soft")
        with self.assertRaisesRegex(ValueError, "presets/r.compatibletyres would be left without"):
            self.apply()
        self.assertEqual(self.calls, [])

    def test_a_car_without_preset_files_keeps_every_old_list_entry_behind_the_own_tyre(self):
        self.tyres()
        for n in ("p", "q"):
            os.remove(os.path.join(self.x.car_root, "presets", n + ".compatibletyres"))
        self.select("own:gt")
        res = self.apply()
        self.assertEqual(self.lists(res), ([OWN_F % "gt", A_UP, S, W, M], [OWN_R % "gt", B, S, W]))
        self.assertEqual([t for t in self.tree(res) if t.startswith("presets/")], [])


class TestApplyErrors(Apply):
    def assertNothingBuilt(self):
        self.assertEqual(self.calls, [])
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "build")))

    def test_a_source_that_no_car_offers_any_more_is_an_error_naming_the_tyre_and_nothing_is_built(self):
        self.tyres()
        self.select("own:gt", ST_AB)
        os.remove(os.path.join(self.y.shared, "tyres", "gt", "f.tyre"))
        with self.assertRaisesRegex(ValueError, r"^garage: tyre gt: no extracted car offers its source tyres\\gt\\f \+ tyres\\gt\\r"):
            self.apply()
        self.assertNothingBuilt()

    def test_a_deleted_or_damaged_or_unknown_own_tyre_is_an_error(self):
        self.tyres()
        self.write(os.path.join(self.work, "tyres", "broken.json"), "{")
        for key, message in (("own:nope", "^garage: no tyre 'nope' in the library$"), ("own:broken", "^garage: .*broken.json"),
                             ("own:Bad", "^garage: bad tyre id 'Bad'"), ("own:", "^garage: bad tyre key 'own:'"), ("soft", "^garage: bad tyre key 'soft'")):
            with self.subTest(key), self.assertRaisesRegex(ValueError, message):
                self.apply({tune.TYRE_KEY: [key, ST_AB]})
        self.assertNothingBuilt()

    def test_a_stock_key_the_car_does_not_have_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "^garage: the stock tyre %s is not in the presets of ks_x$" % re.escape(KEY_GG)):
            self.apply({tune.TYRE_KEY: ["stock:" + KEY_GG]})
        self.assertNothingBuilt()

    def test_an_empty_selection_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "^garage: the tyre selection is empty"):
            self.apply({tune.TYRE_KEY: []})
        self.assertNothingBuilt()

    def test_a_selection_that_is_not_a_list_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "must be a list of tyre keys"):
            self.apply({tune.TYRE_KEY: "own:soft"})
        self.assertNothingBuilt()

    def test_a_library_tyre_whose_source_file_is_not_shared_is_an_error(self):
        self.tyres()
        self.write(os.path.join(self.work, "tyres", "soft.json"), {"version": 1, "name": "Soft", "source": {"front": A, "rear": B}, "values": {}})
        os.remove(os.path.join(self.x.shared, "tyres", "road", "a.tyre"))
        self.select("own:soft")
        with self.assertRaisesRegex(ValueError, "^garage: tyre soft: no extracted car offers its source"):
            self.apply()
        self.assertNothingBuilt()

    def test_a_failed_garage_check_leaves_the_previous_build_alone(self):
        self.tyres()
        first = self.apply()
        self.select("own:soft")
        os.remove(os.path.join(self.work, "tyres", "soft.json"))
        with self.assertRaisesRegex(ValueError, "no tyre 'soft'"):
            self.apply()
        self.assertTrue(os.path.isfile(first["package"]))
        self.assertEqual(len(self.calls), 2)


class TestApplyWithTyreValues(Apply):
    def test_per_car_tyre_values_work_when_the_stock_starting_tyre_is_ticked_and_first(self):
        self.select(ST_AB, ST_SS)
        tune.set_value(self.work, "ks_x", "tyre_dy_front", "1.4", self.cat)
        res = self.apply()
        own = "content\\cars\\ax_x\\data\\tyres\\ax_x_front.tyre"
        self.assertEqual(tune.plain(self.built(res, "data/tyres/ax_x_front.tyre")["modelData"]["Dy0"]), 1.4)
        self.assertEqual(self.lists(res)[0], [own, S, M])
        self.assertEqual([c["front_tyre_data_path"] for c in self.compounds(res, "p")][:2], [own, S])
        self.assertEqual([c["front_tyre_data_path"] for c in self.compounds(res, "q")], [own, S])
        self.assertEqual(res["notes"][1:], ["note: garage: 2 tyre(s), starting on tyres\\road\\a + tyres\\road\\b",
                                            "note: tyre front: own file %s replaces %s in 1 .car entry(ies) and 2 compatibletyres entry(ies)" % (own, A_UP)])
        self.assertEqual([a["id"] for a in res["applied"]], ["tyre_dy_front"])

    def test_they_also_work_when_an_own_tyre_is_first_and_the_stock_starting_tyre_is_ticked_later(self):
        self.tyres()
        self.select("own:soft", ST_AB)
        tune.set_value(self.work, "ks_x", "tyre_dy_front", "1.4", self.cat)
        res = self.apply()
        own = "content\\cars\\ax_x\\data\\tyres\\ax_x_front.tyre"
        self.assertEqual(self.lists(res)[0], [OWN_F % "soft", own, M])
        self.assertEqual(tune.plain(self.built(res, "data/tyres/own_soft_front.tyre")["modelData"]["Dy0"]), 1.2)

    def test_the_stock_starting_tyre_not_ticked_is_an_error_before_install(self):
        self.select(ST_SS)
        tune.set_value(self.work, "ks_x", "tyre_dy_front", "1.4", self.cat)
        mods = str(self.d / "mods")
        with self.assertRaisesRegex(ValueError, "^%s$" % NO_TUNE_ERROR):
            self.apply(install=True, mods_dir=mods)
        self.assertFalse(os.path.exists(os.path.join(mods, "ax_x.kspkg")))
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "build", "ax_x")))
        self.assertEqual([c[0] for c in self.calls], ["build"])

    def test_an_own_tyre_alone_with_changed_tyre_values_is_the_same_error(self):
        self.tyres()
        self.select("own:soft")
        tune.set_value(self.work, "ks_x", "tyre_dy_front", "1.4", self.cat)
        with self.assertRaisesRegex(ValueError, "^%s$" % NO_TUNE_ERROR):
            self.apply()

    def test_without_changed_tyre_values_an_unticked_starting_tyre_is_fine(self):
        self.select(ST_SS)
        self.assertEqual(self.lists(self.apply())[0], [S, M])

    def test_without_a_selection_the_zero_case_is_not_an_error(self):
        tune.set_value(self.work, "ks_x", "tyre_dy_front", "1.4", self.cat)
        self.assertEqual(len(self.apply()["notes"]), 2)

    def test_build_tyre_reports_the_number_of_references_only_when_asked(self):
        item = {"id": "tyre_dy_front", "files": []}
        root, cache = tune.base_dir(self.work, "ks_x"), {}
        part = os.path.join(self.work, "part")
        self.x.clone_into(part, "ax_x")
        counts = []
        note = tune.build_tyre(root, "ks_x", "ax_x", os.path.join(part, "content", "cars", "ax_x"), "tyre_front", [(item, "modelData.Dy0", 1.4)], cache, counts)
        self.assertEqual(counts, [3])
        self.assertIn("in 1 .car entry(ies) and 2 compatibletyres entry(ies)", note)


class TestApplyResult(Apply):
    def test_the_notes_name_the_own_files_and_the_start(self):
        self.tyres()
        self.select(ST_AB, "own:soft", "own:slicky")
        res = self.apply()
        self.assertEqual(res["notes"], [
            "note: from build",
            "note: garage: own tyre slicky -> data/tyres/own_slicky_front.tyre, data/tyres/own_slicky_rear.tyre",
            "note: garage: own tyre soft -> data/tyres/own_soft_front.tyre, data/tyres/own_soft_rear.tyre",
            "note: garage: 3 tyre(s), starting on Slicky"])

    def test_a_stock_start_is_named_by_its_label(self):
        self.select(ST_WW, ST_SS)
        self.assertEqual(self.apply()["notes"][-1], "note: garage: 2 tyre(s), starting on tyres\\slick\\s")

    def test_the_garage_is_no_applied_setting_and_the_other_settings_still_are(self):
        self.tyres()
        self.select("own:soft")
        res = self.apply(dict(self.state(), name_suffix="_Z"))
        self.assertEqual([a["id"] for a in res["applied"]], ["name_suffix"])
        self.assertEqual(tune.load_state(self.work, "ks_x")[tune.TYRE_KEY], ["own:soft"])

    def test_the_state_is_not_changed_by_apply(self):
        self.tyres()
        self.select("own:soft", ST_AB)
        before = self.state()
        self.apply()
        self.assertEqual(self.state(), before)

    def test_apply_prints_nothing_and_the_command_prints_the_notes(self):
        self.tyres()
        self.select("own:soft")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.apply()
        self.assertEqual(out.getvalue(), "")
        code, out, err = self.run_main("apply", "--no-install")
        self.assertEqual((code, err), (0, ""))
        self.assertIn("note: garage: own tyre soft -> data/tyres/own_soft_front.tyre, data/tyres/own_soft_rear.tyre\n", out)
        self.assertIn("note: garage: 1 tyre(s), starting on Soft\n", out)
        self.assertIn("applied 0 setting(s)\n", out)

    def test_a_modded_car_builds_its_own_selection(self):
        self.tyres()
        tune.save_state(self.work, "ks_x", {"name_suffix": "_A"})
        tune.save_state(self.work, "ks_x", {"name_suffix": "_B", tune.TYRE_KEY: [ST_SS]}, "ax01")
        res = tune.apply(self.work, "ks_x", "ax01", install=False, catalogue=self.cat, game=self.game)
        self.assertEqual(self.lists(res)[0], [S, M])
        default = tune.apply(self.work, "ks_x", install=False, catalogue=self.cat, game=self.game)
        self.assertEqual(self.lists(default)[0], [A_UP, S, W, M])

    def test_the_new_files_are_in_the_files_the_package_is_packed_from(self):
        self.tyres()
        self.select("own:soft", "own:gt", ST_AB)
        res = self.apply()
        tree = self.tree(res)
        for name in ("own_soft_front", "own_soft_rear", "own_gt_front", "own_gt_rear"):
            self.assertIn("data/tyres/%s.tyre" % name, tree)
        self.assertEqual(self.packed[-1], sorted("content/cars/ax_x/" + t for t in tree))
        self.assertTrue(all(os.path.isfile(os.path.join(res["build_dir"], "content", "cars", "ax_x", *t.split("/"))) for t in tree))

    def test_the_real_package_contains_them(self):
        self.tyres()
        self.select("own:soft", ST_AB)
        self.real_pack = True
        res = self.apply()
        with open(res["package"], "rb") as f:
            entries = [e["path"] for e in kspkg.read_table(f)[1]]
        self.assertIn("content\\cars\\ax_x\\data\\tyres\\own_soft_front.tyre", entries)
        self.assertIn("content\\cars\\ax_x\\data\\tyres\\own_soft_rear.tyre", entries)
        self.assertIn("content\\cars\\ax_x\\data\\x.car", entries)

    def test_a_second_apply_starts_from_the_base_and_leaves_no_own_file_of_a_tyre_that_was_unticked(self):
        self.tyres()
        self.select("own:soft", "own:gt", ST_AB)
        first = self.apply()
        self.assertIn("data/tyres/own_gt_front.tyre", self.tree(first))
        self.select("own:soft", ST_AB)
        self.real_pack = True
        second = self.apply()
        tree = self.tree(second)
        self.assertEqual([t for t in tree if "own_" in t], ["data/tyres/own_soft_front.tyre", "data/tyres/own_soft_rear.tyre"])
        self.assertFalse(os.path.exists(first["build_dir"] + ".partial"))
        with open(second["package"], "rb") as f:
            self.assertEqual(sorted(e["path"] for e in kspkg.read_table(f)[1] if "own_" in e["path"]),
                             ["content\\cars\\ax_x\\data\\tyres\\own_soft_front.tyre", "content\\cars\\ax_x\\data\\tyres\\own_soft_rear.tyre"])
        self.assertEqual(self.lists(second), ([OWN_F % "soft", A_UP, M], [OWN_R % "soft", B]))
        reset = (tune.reset_garage(self.work, "ks_x"), self.apply())[1]
        self.assertEqual([t for t in self.tree(reset) if "own_" in t], [])
        self.assertEqual(self.lists(reset), ([A_UP, S, W, M], [B, S, W]))

    def test_the_garage_check_does_not_write_into_a_stale_partial_folder(self):
        self.select(ST_AB)
        stale = os.path.join(self.work, "ks_x", "build", "ax_x.partial", "stale.bin")
        self.write(stale, "x")
        with self.assertRaises(ValueError):
            self.apply({tune.TYRE_KEY: ["own:nope"]})
        self.assertTrue(os.path.isfile(stale))


class TestCommands(World):
    def test_garage_lists_the_choices_ticked_and_with_the_start(self):
        self.tyres()
        code, out, err = self.run_main("garage")
        self.assertEqual((code, err), (0, ""))
        lines = out.splitlines()
        self.assertEqual(lines[0], "garage of ks_x: default (all stock tyres, the car is not touched)")
        self.assertEqual([c.strip() for c in lines[1].split(" | ")], ["ticked", "start", "key", "label"])
        rows = [[c.strip() for c in line.split(" | ")] for line in lines[3:]]
        self.assertEqual(rows, [["", "", "own:gt", "gt"], ["", "", "own:slicky", "Slicky"], ["", "", "own:soft", "Soft"],
                                ["x", "start", ST_AB, "tyres\\road\\a + tyres\\road\\b"], ["x", "", ST_SS, "tyres\\slick\\s"],
                                ["x", "", ST_WW, "tyres\\wet\\w"]])

    def test_garage_set_stores_the_selection_and_garage_shows_it(self):
        self.tyres()
        code, out, err = self.run_main("garage-set", ST_WW, "own:soft")
        self.assertEqual((code, out, err), (0, "garage: 2 tyre(s), starting on own:soft\n", ""))
        self.assertEqual(self.state(), {tune.TYRE_KEY: ["own:soft", ST_WW]})
        code, out, err = self.run_main("garage")
        lines = out.splitlines()
        self.assertEqual(lines[0], "garage of ks_x: saved selection")
        rows = {line.split(" | ")[2].strip(): [c.strip() for c in line.split(" | ")][:2] for line in lines[3:]}
        self.assertEqual(rows["own:soft"], ["x", "start"])
        self.assertEqual(rows[ST_WW], ["x", ""])
        self.assertEqual(rows[ST_AB], ["", ""])

    def test_garage_set_with_the_default_selection_removes_the_key(self):
        self.run_main("garage-set", ST_SS)
        code, out, err = self.run_main("garage-set", *self.stock_keys())
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, "garage: 3 tyre(s), starting on %s (the default selection, nothing is stored)\n" % ST_AB)
        self.assertEqual(self.state(), {})

    def test_garage_reset_prints_what_happened(self):
        self.run_main("garage-set", ST_SS)
        self.assertEqual(self.run_main("garage-reset"), (0, "garage selection removed from the state\n", ""))
        self.assertEqual(self.run_main("garage-reset"), (0, "garage selection was not set\n", ""))
        self.assertEqual(self.state(), {})

    def test_the_commands_work_on_the_draft_and_on_a_modded_car(self):
        tune.save_state(self.work, "ks_x", {"name_suffix": "_A"}, "ax01")
        self.assertEqual(self.run_main("garage-set", ST_SS, "--draft")[0], 0)
        self.assertEqual(self.run_main("garage-set", ST_WW, "--tune", "ax01")[0], 0)
        self.assertEqual([self.state(t).get(tune.TYRE_KEY) for t in (None, "ax01", tune.DRAFT)], [None, [ST_WW], [ST_SS]])
        self.assertIn("tyres\\slick\\s", [l for l in self.run_main("garage", "--draft")[1].splitlines() if "start" in l][-1])
        self.assertIn("tyres\\wet\\w", [l for l in self.run_main("garage", "--tune", "ax01")[1].splitlines() if "start" in l][-1])
        self.assertEqual(self.run_main("garage-reset", "--draft")[1], "garage selection removed from the state\n")
        self.assertEqual(self.run_main("garage-reset", "--tune", "ax01")[1], "garage selection removed from the state\n")
        self.assertEqual(self.state("ax01"), {"name_suffix": "_A"})

    def test_a_car_can_be_chosen(self):
        code, out, err = self.run_main("garage", "--car", "ks_x")
        self.assertEqual((code, err), (0, ""))
        code, out, err = self.run_main("garage", "--car", "ks_nope")
        self.assertEqual((code, out), (1, ""))
        self.assertTrue(err.startswith("error: unknown car 'ks_nope'"), err)

    def test_missing_keys_are_warnings_on_stderr(self):
        tune.save_state(self.work, "ks_x", {tune.TYRE_KEY: ["own:gone", ST_SS]})
        code, out, err = self.run_main("garage")
        self.assertEqual((code, err), (0, "warning: the saved tyre own:gone is not available any more\n"))
        self.assertNotIn("own:gone", out)

    def test_a_car_without_tyres_says_so(self):
        for n in ("p", "q"):
            os.remove(os.path.join(self.x.car_root, "presets", n + ".compatibletyres"))
        code, out, err = self.run_main("garage")
        self.assertEqual((code, err), (0, ""))
        self.assertIn("note: no tyres to choose from", out)

    def test_runtime_errors_are_error_lines_with_exit_1(self):
        self.tyres()
        for argv, message in ((("garage-set", "own:nope"), "error: no tyre 'nope' in the library\n"),
                              (("garage-set", "stock:x|y"), "error: unknown stock tyre x|y of ks_x"),
                              (("garage-set", "junk"), "error: bad tyre key 'junk'"), (("garage-set", ST_SS, ST_SS), "error: tyre key %s is listed twice" % ST_SS),
                              (("garage", "--tune", "ax99"), "error: ks_x has no tune ax99"),
                              (("garage-set", ST_SS, "--tune", "ax99"), "error: ks_x has no tune ax99"),
                              (("garage-reset", "--tune", "ax99"), "error: ks_x has no tune ax99")):
            with self.subTest(argv):
                code, out, err = self.run_main(*argv)
                self.assertEqual((code, out), (1, ""))
                self.assertTrue(err.startswith(message), err)
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x")))

    def test_the_usage_block_lists_the_garage_commands_with_car_tune_and_draft(self):
        for cmd in ("garage", "garage-set", "garage-reset"):
            line = [l for l in USAGE.splitlines() if l.strip().startswith("python tools/tune.py " + cmd + " ")]
            self.assertEqual(len(line), 1, cmd)
            for option in ("--tune ID | --draft", "[--car ID]", "[--work <dir>]"):
                self.assertIn(option, line[0])
        self.assertIn("<key> [<key> ...]", USAGE)

    def test_a_wrong_command_line_prints_the_usage_on_stdout_and_exits_2(self):
        for argv in (("garage", "x"), ("garage-set",), ("garage-set", "--draft"), ("garage-reset", "x"), ("garage", "--tune", "ax01", "--draft"),
                     ("garage-set", ST_SS, "--tune", "ax01", "--draft"), ("garage-reset", "--tune", "ax01", "--draft"), ("garage", "--bogus", "1")):
            with self.subTest(argv):
                code, out, err = self.run_main(*argv)
                self.assertEqual((code, out.strip(), err), (2, USAGE.strip(), ""))
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "tune_state.json")))


def usage_case(name, argv):
    def test(self):
        with tmp() as d:
            r = run_tool("tune.py", *argv, cwd=d)
            self.assertEqual(os.listdir(d), [])
        self.assertEqual((r.returncode, r.stdout.strip(), r.stderr), (2, USAGE.strip(), ""))
    test.__name__ = "test_usage_" + name
    return test


class TestCliSubprocess(unittest.TestCase):
    def test_runtime_errors_are_error_lines_on_stderr_with_exit_1(self):
        with tmp() as d:
            for argv, message in ((("garage", "--car", "ks_no_such_car"), "error: unknown car 'ks_no_such_car'"),
                                  (("garage-set", "own:x", "--car", "ks_no_such_car"), "error: unknown car 'ks_no_such_car'"),
                                  (("garage-reset", "--car", "ks_no_such_car"), "error: unknown car 'ks_no_such_car'"),
                                  (("garage-set", "own:nope"), "error: no tyre 'nope' in the library\n"),
                                  (("garage-set", "stock:a|b"), "error: unknown stock tyre a|b of ")):
                with self.subTest(argv):
                    r = run_tool("tune.py", *argv, "--work", d / "w", cwd=d)
                    self.assertEqual((r.returncode, r.stdout), (1, ""))
                    self.assertTrue(r.stderr.startswith(message), r.stderr)
            self.assertEqual(os.listdir(d), [])

    def test_garage_and_garage_reset_on_an_empty_work_folder_write_nothing(self):
        with tmp() as d:
            r = run_tool("tune.py", "garage", "--work", d / "w", cwd=d)
            self.assertEqual((r.returncode, r.stderr), (0, ""))
            self.assertIn("default (all stock tyres, the car is not touched)", r.stdout)
            self.assertIn("note: no tyres to choose from", r.stdout)
            r = run_tool("tune.py", "garage-reset", "--work", d / "w", cwd=d)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "garage selection was not set\n", ""))
            self.assertEqual(os.listdir(d), [])


for _name, _argv in (("garage_with_a_positional", ["garage", "x"]), ("garage_set_without_keys", ["garage-set"]),
                     ("garage_set_with_only_options", ["garage-set", "--draft"]), ("garage_reset_with_a_positional", ["garage-reset", "x"]),
                     ("garage_tune_with_draft", ["garage", "--tune", "ax01", "--draft"]),
                     ("garage_set_tune_with_draft", ["garage-set", "own:x", "--tune", "ax01", "--draft"]),
                     ("garage_reset_tune_with_draft", ["garage-reset", "--tune", "ax01", "--draft"]),
                     ("garage_with_an_unknown_option", ["garage", "--bogus", "1"]), ("garage_option_without_value", ["garage", "--car"]),
                     ("garage_with_new_id", ["garage", "--new-id", "ax02"])):
    setattr(TestCliSubprocess, "test_usage_" + _name, usage_case(_name, _argv))


if __name__ == "__main__":
    unittest.main()
