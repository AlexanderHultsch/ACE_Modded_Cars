"""Tests for the turbo kit of tools/tune.py: the "_turbo" state key, turbo_parts, turbo_kind, list_turbo_donors, turbo_choice, set_turbo, reset_turbo and the commands turbo-donors, turbo-add and turbo-remove.

No game data and no schemas: the cars are synthetic (support.FakeCar replaces tune.load_msg / save_msg with in-memory messages, one shared store for all fake cars); the commands run in-process on those cars, and as a subprocess where nothing decodes a car file (usage, no cars).
"""
import contextlib
import io
import json
import os
import shutil
import sys
import unittest
from unittest import mock

from support import FakeCar, mini_catalogue, mini_setting, run_tool, tmp

import car_json
import tune

USAGE = tune.__doc__.split("\n\n")[1]
KEY = tune.TURBO_KEY
KIT_B = {"donor": "ks_b"}


def turbo_cat():
    return mini_catalogue(
        mini_setting("name_suffix", kind="meta", type="string", default="_MY", handler="name_suffix"),
        mini_setting("variant_name", kind="meta", type="string", default_template="{stock_variant_name}", handler="variant_name"),
        mini_setting("limiter", type="int", targets=[("@engine", "limiter")]))


class World(unittest.TestCase):
    """Fake cars in one work folder: ks_x and ks_n have no turbo, ks_a one turbo (boost 0.8, name Beta), ks_b two turbos (boost 1.0 and
    1.2, name Alpha), ks_c three turbos (no stock info), ks_m two turbo files of which one is not on disk, ks_u an engine that cannot be
    decoded, and ks_z only a build folder (no base)."""

    def setUp(self):
        cm = tmp()
        self.d = cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        self.work = str(self.d / "work")
        data = {"default": "ks_x", "cars": [{"id": c, "label": "Car " + c} for c in ("ks_x", "ks_n", "ks_a", "ks_b", "ks_c", "ks_m", "ks_u")]}
        self.patch(tune, "load_cars", lambda path=None: data)
        self.cat = turbo_cat()
        self.patch(tune, "load_catalogue", lambda path=None: self.cat)
        self.first, self.fakes = None, {}
        self.add_car("ks_x", name="Car X")
        self.add_car("ks_n")
        self.add_car("ks_a", ["t0.turbo"], [0.8], name="Beta")
        self.add_car("ks_b", ["t0.turbo", "t1.turbo"], [1.0, 1.2], name="Alpha")
        self.add_car("ks_c", ["a.turbo", "b.turbo", "c.turbo"], [0.5, 0.6, 0.7])
        self.add_car("ks_m", ["t0.turbo", "t1.turbo"], [1.0, 1.0], present=["t0.turbo"])
        u = self.add_car("ks_u", ["t0.turbo"], [1.0])
        u.store[u.key(os.path.join(u.car_root, "data", "engine.carengine"))] = ValueError("cannot decode")
        os.makedirs(os.path.join(self.work, "ks_z", "build"))

    def patch(self, target, name, value):
        p = mock.patch.object(target, name, value)
        p.start()
        self.addCleanup(p.stop)
        return value

    def add_car(self, car_id, turbos=(), boost=(), name=None, present=None):
        fc = FakeCar(self.work, car_id)
        if self.first is None:
            self.first = fc.install(self)
        else:
            fc.store = self.first.store
        gp = fc.game_path
        fc.add("data/%s.car" % car_id, {"engine_path": gp("data/engine.carengine")})
        fc.add("data/engine.carengine", {"limiter": 7000, "turbos_to_load": [gp("data/" + t) for t in turbos],
                                         "turbos": [{"max_boost": b} for b in boost]})
        for t in turbos if present is None else present:
            fc.add("data/" + t, {"max_boost": 1.0})
        fc.add("presets/p.mechanicalcarpreset", {"brand": "B", "description": "D"})
        if name:
            self.write(tune.stock_info_path(self.work, car_id),
                       {"car_id": car_id, "display_name": name, "brand": "Brand", "year": 1999, "property_1": "P1", "property_2": "P2",
                        "property_3": "P3", "variant_name": "Base"})
        self.fakes[car_id] = fc
        return fc

    def write(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
        return path

    def base_as_kit(self):
        """The kit root is out of scope of these tests (tests/test_turbo_build.py builds it): a car with a saved kit reads base."""
        self.patch(tune, "kit_root", lambda work, car_id, donor: tune.base_dir(work, car_id))

    def drop_base(self, *car_ids):
        for car_id in car_ids:
            shutil.rmtree(tune.base_dir(self.work, car_id))

    def parts(self, car_id, cache=None):
        return tune.turbo_parts(tune.base_dir(self.work, car_id), car_id, cache)

    def donor_ids(self):
        return [d["car"] for d in tune.list_turbo_donors(self.work)]

    def state(self, tune_id=None, car_id="ks_x"):
        return tune.load_state(self.work, car_id, tune_id)

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
        tune.save_state(self.work, "ks_x", {"limiter": 7000, KEY: KIT_B, "old": 1})
        self.assertEqual(tune.unknown_state_ids(self.work, "ks_x", self.cat), ["old"])
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            tune.warn_unknown_state(self.work, "ks_x", self.cat)
        self.assertEqual(err.getvalue(), "warning: ignoring unknown setting 'old' in the saved state\n")
        tune.save_state(self.work, "ks_x", {KEY: KIT_B}, tune.DRAFT)
        self.assertEqual(tune.unknown_state_ids(self.work, "ks_x", self.cat, tune.DRAFT), [])
        tune.save_state(self.work, "ks_x", {KEY: KIT_B}, "ax01")
        self.assertEqual(tune.unknown_state_ids(self.work, "ks_x", self.cat, "ax01"), [])

    def test_the_key_is_no_row_and_not_shown(self):
        self.base_as_kit()
        tune.save_state(self.work, "ks_x", {KEY: KIT_B})
        for hidden in (False, True):
            self.assertNotIn(KEY, [r["id"] for r in tune.effective_rows(self.work, "ks_x", self.cat, hidden=hidden)])
        for command in ("show", "defaults"):
            code, out, err = self.run_main(command)
            self.assertEqual((code, err), (0, ""))
            self.assertNotIn("_turbo", out)

    def test_the_key_is_never_an_applied_setting(self):
        self.base_as_kit()
        tune.save_state(self.work, "ks_x", {KEY: KIT_B})
        plan = tune.apply_plan(self.work, "ks_x", "ax_x", False, None, self.cat)
        self.assertEqual(plan["changed"], [])
        tune.save_state(self.work, "ks_x", {KEY: KIT_B, "limiter": 8000})
        plan = tune.apply_plan(self.work, "ks_x", "ax_x", False, None, self.cat)
        self.assertEqual([s["id"] for s, _ in plan["changed"]], ["limiter"])

    def test_set_and_unset_of_settings_keep_the_key_and_the_key_cannot_be_set_or_unset(self):
        self.base_as_kit()
        tune.save_state(self.work, "ks_x", {KEY: KIT_B})
        tune.set_value(self.work, "ks_x", "limiter", "8000", self.cat)
        self.assertEqual(self.state(), {KEY: KIT_B, "limiter": 8000})
        tune.unset_value(self.work, "ks_x", "limiter", self.cat)
        self.assertEqual(self.state(), {KEY: KIT_B})
        for call in (lambda: tune.unset_value(self.work, "ks_x", KEY, self.cat), lambda: tune.set_value(self.work, "ks_x", KEY, "x", self.cat)):
            with self.assertRaisesRegex(ValueError, "^unknown setting '_turbo'$"):
                call()
        self.assertEqual(self.state(), {KEY: KIT_B})
        code, out, err = self.run_main("unset", KEY)
        self.assertEqual((code, out, err), (1, "", "error: unknown setting '_turbo'\n"))

    def test_duplicate_tune_copies_the_key_with_the_rest_of_the_state(self):
        tune.save_state(self.work, "ks_x", {"limiter": 8000, KEY: KIT_B})
        res = tune.duplicate_tune(self.work, "ks_x", None)
        self.assertEqual(self.state(res["id"]), {"limiter": 8000, KEY: KIT_B, "name_suffix": "_MY2"})
        copied = self.state(res["id"])
        copied[KEY]["donor"] = "ks_a"
        tune.save_state(self.work, "ks_x", copied, res["id"])
        self.assertEqual(self.state()[KEY], KIT_B)
        again = tune.duplicate_tune(self.work, "ks_x", res["id"])
        self.assertEqual(self.state(again["id"])[KEY], {"donor": "ks_a"})
        tune.save_state(self.work, "ks_x", {KEY: {"donor": "ks_c"}}, tune.DRAFT)
        res = tune.duplicate_tune(self.work, "ks_x", tune.DRAFT)
        self.assertEqual(self.state(res["id"])[KEY], {"donor": "ks_c"})

    def test_new_tune_from_draft_copies_the_key_and_the_draft_keeps_it(self):
        tune.save_state(self.work, "ks_x", {"limiter": 9000, KEY: KIT_B}, tune.DRAFT)
        res = tune.new_tune_from_draft(self.work, "ks_x")
        self.assertEqual(self.state(res["id"]), {"limiter": 9000, KEY: KIT_B, "name_suffix": "_MY"})
        self.assertEqual(self.state(tune.DRAFT), {"limiter": 9000, KEY: KIT_B})
        tune.save_state(self.work, "ks_x", {}, tune.DRAFT)
        self.assertEqual(self.state(res["id"])[KEY], KIT_B)


class TestTurboParts(World):
    def test_a_car_without_turbo_files_has_count_0(self):
        self.assertEqual(self.parts("ks_x"), {"files": [], "boost": [], "count": 0})

    def test_a_single_turbo(self):
        self.assertEqual(self.parts("ks_a"), {"files": ["data/t0.turbo"], "boost": [0.8], "count": 1})

    def test_twin_turbos_keep_the_order_of_the_engine(self):
        self.assertEqual(self.parts("ks_b"), {"files": ["data/t0.turbo", "data/t1.turbo"], "boost": [1.0, 1.2], "count": 2})
        engine = self.fakes["ks_b"].store[self.fakes["ks_b"].key(os.path.join(self.fakes["ks_b"].car_root, "data", "engine.carengine"))]
        engine["turbos_to_load"].reverse()
        engine["turbos"].reverse()
        self.assertEqual(self.parts("ks_b"), {"files": ["data/t1.turbo", "data/t0.turbo"], "boost": [1.2, 1.0], "count": 2})

    def test_three_turbos(self):
        self.assertEqual(self.parts("ks_c"), {"files": ["data/a.turbo", "data/b.turbo", "data/c.turbo"], "boost": [0.5, 0.6, 0.7], "count": 3})

    def test_the_result_has_exactly_files_boost_and_count(self):
        self.assertEqual(set(self.parts("ks_a")), {"files", "boost", "count"})

    def test_files_are_those_the_turbo_role_resolves_whatever_their_case(self):
        fc = self.fakes["ks_a"]
        engine = fc.store[fc.key(os.path.join(fc.car_root, "data", "engine.carengine"))]
        engine["turbos_to_load"] = ["CONTENT\\Cars\\KS_A\\DATA\\T0.Turbo"]
        cache = {}
        self.assertEqual(self.parts("ks_a", cache)["files"], ["data/t0.turbo"])
        self.assertEqual(cache[("role", "@turbo[0]")], "data/t0.turbo")
        root = tune.base_dir(self.work, "ks_a")
        self.assertEqual(self.parts("ks_a")["files"], [tune.resolve_file("@turbo[0]", root, "ks_a", {})])

    def test_a_turbo_file_that_is_not_on_disk_is_still_listed_by_the_path_the_engine_names(self):
        self.assertEqual(self.parts("ks_m"), {"files": ["data/t0.turbo", "data/t1.turbo"], "boost": [1.0, 1.0], "count": 2})
        self.assertEqual(tune.turbo_listing(tune.base_dir(self.work, "ks_m"), "ks_m")["missing"], ["data/t1.turbo"])

    def test_an_engine_that_cannot_be_read_gives_count_0(self):
        self.assertEqual(self.parts("ks_u"), {"files": [], "boost": [], "count": 0})

    def test_a_car_without_a_base_or_without_an_engine_path_gives_count_0(self):
        self.assertEqual(self.parts("ks_none")["count"], 0)
        self.assertEqual(self.parts("ks_z")["count"], 0)
        fc = self.fakes["ks_a"]
        fc.store[fc.key(os.path.join(fc.car_root, "data", "ks_a.car"))] = {}
        self.assertEqual(self.parts("ks_a")["count"], 0)

    def test_a_damaged_turbos_to_load_gives_count_0(self):
        fc = self.fakes["ks_a"]
        engine = fc.store[fc.key(os.path.join(fc.car_root, "data", "engine.carengine"))]
        for bad in ("data/t0.turbo", {"a": 1}, [5], [""], ["x.turbo", None]):
            engine["turbos_to_load"] = bad
            with self.subTest(repr(bad)):
                self.assertEqual(self.parts("ks_a"), {"files": [], "boost": [], "count": 0})

    def test_boost_lists_only_the_turbos_that_have_a_number(self):
        fc = self.fakes["ks_a"]
        engine = fc.store[fc.key(os.path.join(fc.car_root, "data", "engine.carengine"))]
        engine["turbos"] = [{"max_boost": 1}, {"x": 1}, {"max_boost": "a"}, {"max_boost": True}, {"max_boost": float("inf")}, 5,
                            {"max_boost": tune.to_f32(0.8)}, {"max_boost": None}]
        parts = self.parts("ks_a")
        self.assertEqual(parts["boost"], [1.0, 0.8])
        self.assertEqual({type(b) for b in parts["boost"]}, {float})
        self.assertEqual(parts["count"], 1)
        for bad in (None, "x", {"max_boost": 1}):
            engine["turbos"] = bad
            self.assertEqual(self.parts("ks_a")["boost"], [])
        del engine["turbos"]
        self.assertEqual(self.parts("ks_a"), {"files": ["data/t0.turbo"], "boost": [], "count": 1})

    def test_a_float32_boost_is_its_shortest_decimal(self):
        fc = self.fakes["ks_a"]
        engine = fc.store[fc.key(os.path.join(fc.car_root, "data", "engine.carengine"))]
        engine["turbos"] = [{"max_boost": car_json.F32(0.800000011920929)}]
        engine["turbos"][0]["max_boost"].text = "0.8"
        self.assertEqual(self.parts("ks_a")["boost"], [0.8])

    def test_the_cache_is_filled_and_reused(self):
        cache = {}
        first = self.parts("ks_b", cache)
        self.assertIn(("role", "@engine"), cache)
        self.assertEqual(self.parts("ks_b", cache), first)

    def test_nothing_is_written(self):
        before = sorted(os.walk(self.work))
        self.parts("ks_b")
        self.assertEqual(sorted(os.walk(self.work)), before)


class TestTurboKind(unittest.TestCase):
    def test_the_words(self):
        self.assertEqual([tune.turbo_kind(n) for n in (0, 1, 2, 3, 4, 10)],
                         ["no turbo", "single turbo", "twin turbo", "3 turbos", "4 turbos", "10 turbos"])


class TestListDonors(World):
    def test_only_installed_cars_with_all_their_turbo_files_are_donors_in_order(self):
        self.assertEqual(tune.list_turbo_donors(self.work), [
            {"car": "ks_b", "label": "Alpha", "count": 2, "kind": "twin turbo", "boost": [1.0, 1.2]},
            {"car": "ks_a", "label": "Beta", "count": 1, "kind": "single turbo", "boost": [0.8]},
            {"car": "ks_c", "label": "ks_c", "count": 3, "kind": "3 turbos", "boost": [0.5, 0.6, 0.7]}])

    def test_cars_without_turbo_with_a_missing_file_with_an_unreadable_engine_or_without_a_base_are_skipped(self):
        for car_id in ("ks_x", "ks_n", "ks_m", "ks_u", "ks_z"):
            self.assertNotIn(car_id, self.donor_ids())

    def test_a_car_folder_without_the_car_files_is_skipped(self):
        os.makedirs(os.path.join(tune.base_dir(self.work, "ks_q"), "content"))
        self.assertEqual(self.donor_ids(), ["ks_b", "ks_a", "ks_c"])

    def test_the_label_comes_from_the_stock_info_then_the_cached_car_index_then_the_id(self):
        self.write(os.path.join(self.work, "cars_index.json"), [{"id": "ks_c", "display_name": "Gamma"}, {"id": "ks_a", "display_name": "Index A"}])
        self.assertEqual([(d["car"], d["label"]) for d in tune.list_turbo_donors(self.work)], [("ks_b", "Alpha"), ("ks_a", "Beta"), ("ks_c", "Gamma")])
        os.remove(os.path.join(self.work, "cars_index.json"))
        os.remove(tune.stock_info_path(self.work, "ks_a"))
        self.assertEqual([d["label"] for d in tune.list_turbo_donors(self.work)], ["Alpha", "ks_a", "ks_c"])
        self.write(tune.stock_info_path(self.work, "ks_a"), "{")
        self.assertEqual([d["label"] for d in tune.list_turbo_donors(self.work)], ["Alpha", "ks_a", "ks_c"])

    def test_the_sort_ignores_case_and_breaks_ties_by_id(self):
        self.add_car("ks_d", ["t0.turbo"], [0.9], name="beta")
        self.add_car("ks_e", ["t0.turbo"], [0.9], name="BETA")
        self.assertEqual(self.donor_ids(), ["ks_b", "ks_a", "ks_d", "ks_e", "ks_c"])

    def test_a_car_with_a_turbo_file_and_no_boost_number_is_a_donor_with_an_empty_boost(self):
        fc = self.fakes["ks_a"]
        del fc.store[fc.key(os.path.join(fc.car_root, "data", "engine.carengine"))]["turbos"]
        self.assertEqual(next(d for d in tune.list_turbo_donors(self.work) if d["car"] == "ks_a")["boost"], [])

    def test_a_work_folder_without_cars_has_no_donors(self):
        self.assertEqual(tune.list_turbo_donors(str(self.d / "empty")), [])

    def test_nothing_is_extracted_or_written(self):
        before = sorted(os.walk(self.work))
        tune.list_turbo_donors(self.work)
        self.assertEqual(sorted(os.walk(self.work)), before)


class TestTurboChoice(World):
    def test_a_car_without_a_turbo_can_choose_among_the_other_donors(self):
        res = tune.turbo_choice(self.work, "ks_x")
        self.assertEqual((res["donor"], res["available"], res["reason"], res["picked"]), (None, True, "", None))
        self.assertEqual([d["car"] for d in res["donors"]], ["ks_b", "ks_a", "ks_c"])
        self.assertEqual(set(res), {"donor", "available", "reason", "donors", "picked"})
        self.assertEqual(res["donors"], tune.list_turbo_donors(self.work))

    def test_a_car_with_a_turbo_cannot_and_is_not_its_own_donor(self):
        res = tune.turbo_choice(self.work, "ks_a")
        self.assertEqual((res["available"], res["reason"]), (False, "the car has a turbo already"))
        self.assertEqual([d["car"] for d in res["donors"]], ["ks_b", "ks_c"])

    def test_without_any_donor_nothing_is_available(self):
        self.drop_base("ks_a", "ks_b", "ks_c")
        res = tune.turbo_choice(self.work, "ks_x")
        self.assertEqual((res["available"], res["reason"], res["donors"], res["picked"]), (False, "no installed car has a turbo", [], None))

    def test_the_turbo_of_the_car_itself_is_reported_before_the_lack_of_donors(self):
        self.drop_base("ks_b", "ks_c")
        self.assertEqual(tune.turbo_choice(self.work, "ks_a")["reason"], "the car has a turbo already")

    def test_the_saved_donor_is_picked_with_its_data(self):
        tune.save_state(self.work, "ks_x", {KEY: KIT_B})
        res = tune.turbo_choice(self.work, "ks_x")
        self.assertEqual(res["donor"], "ks_b")
        self.assertEqual(res["picked"], {"car": "ks_b", "label": "Alpha", "count": 2, "kind": "twin turbo", "boost": [1.0, 1.2]})
        self.assertIs(res["picked"], next(d for d in res["donors"] if d["car"] == "ks_b"))

    def test_each_tune_and_the_draft_have_their_own_choice(self):
        tune.save_state(self.work, "ks_x", {KEY: KIT_B})
        tune.save_state(self.work, "ks_x", {KEY: {"donor": "ks_a"}}, "ax01")
        tune.save_state(self.work, "ks_x", {}, tune.DRAFT)
        self.assertEqual([tune.turbo_choice(self.work, "ks_x", t)["donor"] for t in (None, "ax_x", "ax01", tune.DRAFT)],
                         ["ks_b", "ks_b", "ks_a", None])

    def test_a_saved_donor_that_is_not_a_donor_any_more_is_not_picked(self):
        tune.save_state(self.work, "ks_x", {KEY: KIT_B})
        self.drop_base("ks_b")
        res = tune.turbo_choice(self.work, "ks_x")
        self.assertEqual((res["donor"], res["picked"], res["available"]), ("ks_b", None, True))
        tune.save_state(self.work, "ks_x", {KEY: {"donor": "ks_m"}})
        self.assertIsNone(tune.turbo_choice(self.work, "ks_x")["picked"])
        tune.save_state(self.work, "ks_x", {KEY: {"donor": "ks_x"}})
        self.assertIsNone(tune.turbo_choice(self.work, "ks_x")["picked"])

    def test_a_damaged_saved_value_is_an_error(self):
        for bad in ("ks_b", ["ks_b"], {}, {"donor": 5}, {"donor": None}, {"other": "ks_b"}, None, 5):
            tune.save_state(self.work, "ks_x", {KEY: bad})
            with self.subTest(repr(bad)):
                with self.assertRaisesRegex(ValueError, "^damaged turbo kit in the saved state$"):
                    tune.turbo_choice(self.work, "ks_x")

    def test_nothing_is_written(self):
        tune.save_state(self.work, "ks_x", {KEY: KIT_B})
        before = sorted(os.walk(self.work))
        tune.turbo_choice(self.work, "ks_x")
        self.assertEqual(sorted(os.walk(self.work)), before)


class TestSetTurbo(World):
    def test_the_donor_is_stored_and_described(self):
        res = tune.set_turbo(self.work, "ks_x", "ks_b")
        self.assertEqual(res, {"donor": "ks_b", "count": 2, "kind": "twin turbo", "boost": [1.0, 1.2]})
        self.assertEqual(self.state(), {KEY: KIT_B})
        with open(tune.state_path(self.work, "ks_x"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {KEY: KIT_B})

    def test_the_rest_of_the_state_stays_and_another_donor_replaces_the_first(self):
        tune.save_state(self.work, "ks_x", {"limiter": 8000, tune.TYRE_KEY: ["own:soft"]})
        tune.set_turbo(self.work, "ks_x", "ks_b")
        res = tune.set_turbo(self.work, "ks_x", "ks_c")
        self.assertEqual((res["donor"], res["count"], res["kind"]), ("ks_c", 3, "3 turbos"))
        self.assertEqual(self.state(), {"limiter": 8000, tune.TYRE_KEY: ["own:soft"], KEY: {"donor": "ks_c"}})

    def test_tunes_and_the_draft_are_separate_states(self):
        tune.save_state(self.work, "ks_x", {}, "ax01")
        tune.set_turbo(self.work, "ks_x", "ks_a", "ax01")
        tune.set_turbo(self.work, "ks_x", "ks_b", tune.DRAFT)
        self.assertEqual((self.state("ax01"), self.state(tune.DRAFT), os.path.exists(tune.state_path(self.work, "ks_x"))),
                         ({KEY: {"donor": "ks_a"}}, {KEY: KIT_B}, False))

    def test_the_state_is_written_only_when_something_changes(self):
        with mock.patch.object(tune, "save_state", wraps=tune.save_state) as save:
            tune.set_turbo(self.work, "ks_x", "ks_b")
            tune.set_turbo(self.work, "ks_x", "ks_b")
            self.assertEqual(save.call_count, 1)
            tune.set_turbo(self.work, "ks_x", "ks_a")
            self.assertEqual(save.call_count, 2)
        path = tune.state_path(self.work, "ks_x")
        stamp = os.stat(path).st_mtime_ns
        tune.set_turbo(self.work, "ks_x", "ks_a")
        self.assertEqual(os.stat(path).st_mtime_ns, stamp)

    def test_a_damaged_saved_value_is_replaced(self):
        tune.save_state(self.work, "ks_x", {KEY: "junk"})
        tune.set_turbo(self.work, "ks_x", "ks_a")
        self.assertEqual(self.state(), {KEY: {"donor": "ks_a"}})

    def test_a_car_with_a_turbo_is_refused(self):
        with self.assertRaisesRegex(ValueError, "^ks_a has a turbo already$"):
            tune.set_turbo(self.work, "ks_a", "ks_b")
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_a")))

    def test_a_donor_that_is_no_installed_car_with_a_turbo_is_refused(self):
        for donor in ("ks_nope", "ks_n", "ks_m", "ks_u", "ks_z", ""):
            with self.subTest(donor):
                with self.assertRaisesRegex(ValueError, "^%s is not an installed car with a turbo$" % donor):
                    tune.set_turbo(self.work, "ks_x", donor)
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x")))

    def test_the_car_cannot_be_its_own_donor(self):
        with self.assertRaisesRegex(ValueError, "^ks_x cannot be its own turbo donor$"):
            tune.set_turbo(self.work, "ks_x", "ks_x")
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x")))

    def test_a_donor_that_is_not_text_is_refused(self):
        for donor in (5, None, ["ks_b"], {"donor": "ks_b"}, b"ks_b"):
            with self.subTest(repr(donor)):
                with self.assertRaisesRegex(ValueError, "^the turbo donor must be a car id, got "):
                    tune.set_turbo(self.work, "ks_x", donor)
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x")))

    def test_a_car_without_a_base_is_refused(self):
        for car_id in ("ks_none", "ks_z"):
            with self.subTest(car_id):
                with self.assertRaisesRegex(ValueError, r"^no base car in .*, run init first$"):
                    tune.set_turbo(self.work, car_id, "ks_b")
                self.assertFalse(os.path.exists(tune.state_path(self.work, car_id)))


class TestResetTurbo(World):
    def test_the_choice_is_removed_and_the_rest_of_the_state_stays(self):
        tune.save_state(self.work, "ks_x", {"limiter": 8000, KEY: KIT_B})
        self.assertEqual(tune.reset_turbo(self.work, "ks_x"), {"removed": True})
        self.assertEqual(self.state(), {"limiter": 8000})
        self.assertEqual(tune.reset_turbo(self.work, "ks_x"), {"removed": False})

    def test_nothing_is_written_when_there_is_no_choice(self):
        self.assertEqual(tune.reset_turbo(self.work, "ks_x"), {"removed": False})
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x")))
        with mock.patch.object(tune, "save_state") as save:
            tune.reset_turbo(self.work, "ks_x", tune.DRAFT)
        save.assert_not_called()

    def test_a_tune_and_the_draft_are_reset_on_their_own(self):
        tune.set_turbo(self.work, "ks_x", "ks_b")
        tune.set_turbo(self.work, "ks_x", "ks_b", tune.DRAFT)
        self.assertEqual(tune.reset_turbo(self.work, "ks_x", tune.DRAFT), {"removed": True})
        self.assertEqual((self.state(), self.state(tune.DRAFT)), ({KEY: KIT_B}, {}))


class TestCommands(World):
    def test_the_usage_lists_the_commands_and_the_dispatch_has_them(self):
        for name in ("turbo-donors", "turbo-add", "turbo-remove"):
            self.assertIn("python tools/tune.py " + name, USAGE)
            self.assertEqual(tune.COMMANDS[name].__name__, "cmd_" + name.replace("-", "_"))
        self.assertEqual(list(tune.COMMANDS)[list(tune.COMMANDS).index("garage-reset") + 1:][:3], ["turbo-donors", "turbo-add", "turbo-remove"])

    def test_turbo_donors_prints_the_table(self):
        code, out, err = self.run_main("turbo-donors")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, tune.table(["car", "name", "kind", "boost (bar)"], [
            ["ks_b", "Alpha", "twin turbo", "1 / 1.2"], ["ks_a", "Beta", "single turbo", "0.8"],
            ["ks_c", "ks_c", "3 turbos", "0.5 / 0.6 / 0.7"]]) + "\n")
        self.assertEqual(out.splitlines()[0], "car  | name  | kind         | boost (bar)")
        self.assertEqual(len(out.splitlines()), 5)

    def test_turbo_donors_without_a_donor_says_so(self):
        self.drop_base("ks_a", "ks_b", "ks_c")
        self.assertEqual(self.run_main("turbo-donors"), (0, "no installed car has a turbo\n", ""))

    def test_turbo_donors_with_a_car_adds_the_chosen_kit(self):
        code, out, err = self.run_main("turbo-donors", "--car", "ks_x")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.splitlines()[-1], "no turbo kit chosen")
        self.assertEqual(len(out.splitlines()), 6)
        tune.set_turbo(self.work, "ks_x", "ks_b")
        code, out, err = self.run_main("turbo-donors", "--car", "ks_x")
        self.assertEqual((code, out.splitlines()[-1], err), (0, "chosen: ks_b", ""))
        self.assertEqual(self.run_main("turbo-donors")[1].count("chosen"), 0)

    def test_turbo_donors_with_a_car_without_a_donor_prints_both_lines(self):
        self.drop_base("ks_a", "ks_b", "ks_c")
        self.assertEqual(self.run_main("turbo-donors", "--car", "ks_x"), (0, "no installed car has a turbo\nno turbo kit chosen\n", ""))

    def test_turbo_donors_warns_about_a_saved_donor_that_is_gone(self):
        tune.save_state(self.work, "ks_x", {KEY: {"donor": "ks_gone"}})
        code, out, err = self.run_main("turbo-donors", "--car", "ks_x")
        self.assertEqual((code, out.splitlines()[-1]), (0, "chosen: ks_gone"))
        self.assertEqual(err, "warning: the saved turbo donor ks_gone is not available any more\n")

    def test_turbo_donors_with_a_damaged_state_or_an_unknown_car_is_an_error(self):
        tune.save_state(self.work, "ks_x", {KEY: 5})
        self.assertEqual(self.run_main("turbo-donors", "--car", "ks_x")[0::2], (1, "error: damaged turbo kit in the saved state\n"))
        code, out, err = self.run_main("turbo-donors", "--car", "ks_nope")
        self.assertEqual((code, out), (1, ""))
        self.assertTrue(err.startswith("error: unknown car 'ks_nope'"), err)

    def test_turbo_add_stores_the_donor_in_the_default_tune_of_the_chosen_car(self):
        self.assertEqual(self.run_main("turbo-add", "ks_b"), (0, "ks_b: twin turbo, boost 1 / 1.2 bar\n", ""))
        self.assertEqual(self.state(), {KEY: KIT_B})
        self.assertEqual(self.run_main("turbo-add", "ks_a", "--car", "ks_n")[1], "ks_a: single turbo, boost 0.8 bar\n")
        self.assertEqual(self.state(car_id="ks_n"), {KEY: {"donor": "ks_a"}})

    def test_turbo_add_on_the_draft_and_on_a_tune(self):
        self.assertEqual(self.run_main("turbo-add", "ks_c", "--draft", "--car", "ks_x"), (0, "ks_c: 3 turbos, boost 0.5 / 0.6 / 0.7 bar\n", ""))
        self.assertEqual((self.state(tune.DRAFT), os.path.exists(tune.state_path(self.work, "ks_x"))), ({KEY: {"donor": "ks_c"}}, False))
        tune.save_state(self.work, "ks_x", {}, "ax01")
        self.assertEqual(self.run_main("turbo-add", "ks_a", "--tune", "ax01")[0], 0)
        self.assertEqual(self.state("ax01"), {KEY: {"donor": "ks_a"}})
        code, out, err = self.run_main("turbo-add", "ks_a", "--tune", "ax02")
        self.assertEqual((code, out, err), (1, "", "error: ks_x has no tune ax02\n"))

    def test_turbo_add_without_boost_numbers_says_unknown(self):
        fc = self.fakes["ks_a"]
        del fc.store[fc.key(os.path.join(fc.car_root, "data", "engine.carengine"))]["turbos"]
        self.assertEqual(self.run_main("turbo-add", "ks_a", "--car", "ks_n")[1], "ks_a: single turbo, boost unknown bar\n")

    def test_turbo_add_errors_are_error_lines_with_exit_1(self):
        for argv, message in ((("turbo-add", "ks_nope"), "error: ks_nope is not an installed car with a turbo\n"),
                              (("turbo-add", "ks_x"), "error: ks_x cannot be its own turbo donor\n"),
                              (("turbo-add", "ks_b", "--car", "ks_a"), "error: ks_a has a turbo already\n")):
            with self.subTest(argv):
                self.assertEqual(self.run_main(*argv), (1, "", message))
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x")))

    def test_turbo_remove_removes_the_choice(self):
        tune.set_turbo(self.work, "ks_x", "ks_b")
        self.assertEqual(self.run_main("turbo-remove"), (0, "turbo kit removed from the state\n", ""))
        self.assertEqual(self.run_main("turbo-remove"), (0, "turbo kit was not set\n", ""))
        self.assertEqual(self.state(), {})

    def test_turbo_remove_on_the_draft_and_on_a_tune(self):
        tune.set_turbo(self.work, "ks_x", "ks_b", tune.DRAFT)
        tune.set_turbo(self.work, "ks_x", "ks_a", "ax01")
        self.assertEqual(self.run_main("turbo-remove", "--draft", "--car", "ks_x")[1], "turbo kit removed from the state\n")
        self.assertEqual(self.state(tune.DRAFT), {})
        self.assertEqual(self.state("ax01"), {KEY: {"donor": "ks_a"}})
        self.assertEqual(self.run_main("turbo-remove", "--tune", "ax01")[1], "turbo kit removed from the state\n")
        self.assertEqual(self.state("ax01"), {})
        self.assertEqual(self.run_main("turbo-remove", "--tune", "ax02")[0::2], (1, "error: ks_x has no tune ax02\n"))

    def test_wrong_arguments_print_the_usage_and_exit_2(self):
        for argv in (["turbo-add"], ["turbo-add", "ks_a", "ks_b"], ["turbo-donors", "x"], ["turbo-remove", "x"],
                     ["turbo-add", "ks_b", "--tune", "ax01", "--draft"], ["turbo-remove", "--tune", "ax01", "--draft"],
                     ["turbo-donors", "--draft"], ["turbo-donors", "--tune", "ax01"]):
            with self.subTest(argv):
                code, out, err = self.run_main(*argv)
                self.assertEqual((code, out.strip(), err), (2, USAGE.strip(), ""))
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x")))


def usage_case(name, argv):
    def test(self):
        with tmp() as d:
            r = run_tool("tune.py", *argv, cwd=d)
        self.assertEqual((r.returncode, r.stdout.strip(), r.stderr), (2, USAGE.strip(), ""))
    test.__name__ = "test_" + name
    return test


class TestCliProcess(unittest.TestCase):
    def test_the_usage_on_stdout_names_the_three_commands(self):
        with tmp() as d:
            r = run_tool("tune.py", cwd=d)
        self.assertEqual((r.returncode, r.stderr), (2, ""))
        for line in ("turbo-donors [--car ID] [--work <dir>]", "turbo-add    <donor> [--tune ID | --draft] [--car ID] [--work <dir>]",
                     "turbo-remove [--tune ID | --draft] [--car ID] [--work <dir>]"):
            self.assertIn("python tools/tune.py " + line, r.stdout)

    def test_turbo_donors_without_any_car_says_so(self):
        with tmp() as d:
            r = run_tool("tune.py", "turbo-donors", "--work", d / "w", cwd=d)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "no installed car has a turbo\n", ""))
            self.assertEqual(os.listdir(d), [])


for _name, _argv in (("no_arguments", []), ("turbo_donors_with_a_positional", ["turbo-donors", "x"]),
                     ("turbo_donors_with_draft", ["turbo-donors", "--draft"]), ("turbo_add_without_operand", ["turbo-add"]),
                     ("turbo_add_with_two_operands", ["turbo-add", "ks_a", "ks_b"]),
                     ("turbo_add_tune_with_draft", ["turbo-add", "ks_a", "--tune", "ax01", "--draft"]),
                     ("turbo_add_option_without_value", ["turbo-add", "ks_a", "--car"]),
                     ("turbo_remove_with_a_positional", ["turbo-remove", "x"]),
                     ("turbo_remove_tune_with_draft", ["turbo-remove", "--tune", "ax01", "--draft"])):
    setattr(TestCliProcess, "test_usage_" + _name, usage_case(_name, _argv))


if __name__ == "__main__":
    unittest.main()
