"""Tests for the turbo kit root of tools/tune.py: kit_root (a tree like base with the donor's turbo files and fields built in), root_for, resolving and setting with a kit, apply from a kit root and the command turbo-kit.

No game data and no schemas: the cars are synthetic and their files are JSON text on disk (the tests replace tune.load_msg / save_msg by a JSON reader and a writer that opens the file in place, as the real save_msg does, so a patched file that is still a hard link of base would change base); clone_car.build is replaced by the real copy_renamed and kspkg.cmd_pack by a recorder. The wire bookkeeping (_order, _packed) of the copied fields is checked against car_json.encode_msg on a small schema built here.
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import struct
import sys
import unittest
from unittest import mock

from support import (FakeCar, desc_field, desc_file, desc_message, desc_set, mini_catalogue, mini_setting, pb_bytes, pb_f32, pb_int,
                     pb_msg, pb_str, run_tool, tmp)

import car_json
import clone_car
import kspkg
import tune

USAGE = tune.__doc__.split("\n\n")[1]
KEY = tune.TURBO_KEY
REAL_PATCH_KIT = tune.patch_kit
REAL_LINK_TREE = tune.link_tree
CARS = ("ks_x", "ks_n", "ks_a", "ks_b", "ks_s")
TURBO_ENTRY = "content\\cars\\ax_x\\data\\kit_turbo_%d.turbo"
KIT_ENTRY = "content\\cars\\ks_x\\data\\kit_turbo_%d.turbo"
ENGINE_FIELDS = ["turbos_to_load", "turbos", "max_turbo_boost", "bov_noise"]
INLINE_FIELDS = ["turbos_to_load", "turbos", "max_turbo_boost"]


def plain_tree(v):
    if isinstance(v, car_json.F32):
        return float(v.text)
    if isinstance(v, dict):
        return {k: plain_tree(x) for k, x in v.items()}
    if isinstance(v, list):
        return [plain_tree(x) for x in v]
    return v


def load_msg(path):
    name = car_json.message_for(path)
    try:
        with open(kspkg.long_path(path), encoding="utf-8") as f:
            return json.load(f), name
    except (OSError, ValueError) as e:
        raise ValueError("%s: %s" % (path, e)) from None


def save_msg(path, name, obj):
    with open(kspkg.long_path(path), "w", encoding="utf-8", newline="\n") as f:
        json.dump(plain_tree(obj), f)


def sha_tree(root):
    out = {}
    for dp, _, names in os.walk(root):
        for n in names:
            with open(os.path.join(dp, n), "rb") as f:
                out[os.path.relpath(os.path.join(dp, n), root).replace(os.sep, "/")] = hashlib.sha256(f.read()).hexdigest()
    return out


def kit_cat():
    boost = {"group": "Turbo", "min": 0, "max": 3, "hide_if_absent": True}
    return mini_catalogue(
        mini_setting("name_suffix", kind="meta", type="string", default="_MY", handler="name_suffix"),
        mini_setting("variant_name", kind="meta", type="string", default_template="{stock_variant_name}", handler="variant_name"),
        mini_setting("limiter", type="int", targets=[("@engine", "limiter")]),
        mini_setting("turbo_boost_1", targets=[("@engine", "turbos[0].max_boost"), ("@turbo[0]", "max_boost"),
                                               ("@car", "engine.turbos[0].max_boost", True)], **boost),
        mini_setting("turbo_boost_2", targets=[("@engine", "turbos[1].max_boost"), ("@turbo[1]", "max_boost"),
                                               ("@car", "engine.turbos[1].max_boost", True)], **boost),
        mini_setting("max_turbo_boost", needs=[{"file": "@turbo[0]", "path": "max_boost"}],
                     targets=[("@engine", "max_turbo_boost"), ("@car", "engine.max_turbo_boost", True)], **boost))


def assert_order_valid(test, obj):
    """The names in _order occur as often as the field has wire occurrences (the elements of a list, one for a packed list or a
    single value), the rule of car_json.encode_msg."""
    order = obj.get("_order")
    if order is not None:
        packed = obj.get("_packed", [])
        want = {k: (len(v) if isinstance(v, list) and k not in packed else 1) for k, v in obj.items() if not k.startswith("_")}
        test.assertEqual({k: order.count(k) for k in set(order)}, want)


class World(unittest.TestCase):
    """Fake cars in one work folder: ks_x (the car under test) and ks_n have no turbo (ks_x has an inline engine block in its .car, ks_n
    none), ks_a has one turbo (boost 0.8), ks_b two (1.0 and 1.2), ks_s one (0.9, entry written in capitals with slashes, file in a
    subfolder, no inline block in its .car). Every file is JSON text on disk."""

    def setUp(self):
        cm = tmp()
        self.d = cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        self.addCleanup(tune._resolved.clear)
        self.work = str(self.d / "work")
        data = {"default": "ks_x", "cars": [{"id": c, "label": "Car " + c} for c in CARS]}
        self.patch(tune, "load_cars", lambda path=None: data)
        self.cat = kit_cat()
        self.patch(tune, "load_catalogue", lambda path=None: self.cat)
        self.patch(tune, "load_msg", load_msg)
        self.patch(tune, "save_msg", save_msg)
        self.builds = []
        self.patch(tune, "patch_kit", self.spy_patch_kit)
        self.fakes = {}
        self.add_car("ks_x", inline=True)
        self.add_car("ks_n")
        self.add_car("ks_a", ["data/t0.turbo"], [0.8], inline=True)
        self.add_car("ks_b", ["data/turbo_a.turbo", "data/turbo_b.turbo"], [1.0, 1.2], inline=True)
        self.add_car("ks_s", ["data/turbos/s.turbo"], [0.9], style="slash")

    def patch(self, target, name, value):
        p = mock.patch.object(target, name, value)
        p.start()
        self.addCleanup(p.stop)
        return value

    def spy_patch_kit(self, work, car_id, donor, part):
        self.builds.append((car_id, donor))
        return REAL_PATCH_KIT(work, car_id, donor, part)

    def put(self, fc, rel, obj):
        path = fc.add(rel)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f)
        return path

    def add_car(self, car_id, turbos=(), boost=(), inline=False, style="backslash"):
        fc = FakeCar(self.work, car_id)
        texts = [fc.game_path(t) for t in turbos]
        if style == "slash":
            texts = [("content/cars/%s/%s" % (car_id, t)).upper() for t in turbos]
        n = len(turbos)
        if turbos:
            engine = {"limiter": 8800.0, "turbos_to_load": texts, "turbos": [{"max_boost": b, "lag": 0.5} for b in boost],
                      "max_turbo_boost": max(boost), "bov_noise": 0.4, "sound_turbine": 1, "controller": {"boost_gain": 5.0},
                      "_order": ["limiter"] + ["turbos_to_load"] * n + ["turbos"] * n + ["max_turbo_boost", "bov_noise", "sound_turbine", "controller"]}
        else:
            engine = {"limiter": 7000.0, "boost_display": 3, "name": "na", "_order": ["name", "limiter", "boost_display"]}
        car = {"engine_path": fc.game_path("data/engine.carengine")}
        if inline:
            car["engine"] = ({"limiter": 8800.0, "turbos_to_load": texts, "turbos": [{"max_boost": b} for b in boost],
                              "max_turbo_boost": max(boost), "idle": 900} if turbos else
                             {"limiter": 7000.0, "name": "inline_na", "_order": ["name", "limiter"]})
        self.put(fc, "data/%s.car" % car_id, car)
        self.put(fc, "data/engine.carengine", engine)
        for t, b in zip(turbos, boost):
            self.put(fc, t, {"max_boost": b, "lag": 0.3})
        self.put(fc, "presets/p.mechanicalcarpreset", {"brand": "B", "description": "D"})
        os.makedirs(os.path.dirname(fc.add_shared("tyres/a.tyre")), exist_ok=True)
        self.write(tune.stock_info_path(self.work, car_id),
                   {"car_id": car_id, "display_name": "Name " + car_id, "brand": "Brand", "year": 1999, "property_1": "P1",
                    "property_2": "P2", "property_3": "P3", "variant_name": "Base"})
        self.fakes[car_id] = fc
        return fc

    def write(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
        return path

    def car_file(self, root, car_id, rel):
        return os.path.join(root, "content", "cars", car_id, *rel.split("/"))

    def base_file(self, car_id, rel):
        return self.car_file(tune.base_dir(self.work, car_id), car_id, rel)

    def read(self, path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def edit(self, car_id, rel, fn):
        path = self.base_file(car_id, rel)
        obj = self.read(path)
        fn(obj)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f)

    def kit(self, donor, car_id="ks_x"):
        return tune.kit_root(self.work, car_id, donor)

    def kit_json(self, donor, car_id="ks_x"):
        return self.read(os.path.join(tune.kit_path(self.work, car_id, donor), "kit.json"))

    def state(self, tune_id=None, car_id="ks_x"):
        return tune.load_state(self.work, car_id, tune_id)

    def with_kit(self, donor, tune_id=None, car_id="ks_x"):
        state = tune.load_state(self.work, car_id, tune_id)
        state[KEY] = {"donor": donor}
        tune.save_state(self.work, car_id, state, tune_id)

    def two_tunes(self):
        """The default tune with the kit of ks_a and the tune ax01 (its own suffix) with the kit of ks_b."""
        self.with_kit("ks_a")
        tune.save_state(self.work, "ks_x", {"name_suffix": "_B", KEY: {"donor": "ks_b"}}, "ax01")

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


class TestKitRoot(World):
    def test_the_kit_is_a_tree_in_the_work_folder_next_to_base_with_a_kit_json(self):
        root = self.kit("ks_a")
        self.assertEqual(root, os.path.join(self.work, "ks_x", "kit", "ks_a"))
        self.assertTrue(os.path.isdir(self.car_file(root, "ks_x", "data")))
        self.assertEqual(sorted(os.listdir(os.path.join(self.work, "ks_x"))), ["base", "kit", "stock_info.json"])
        self.assertEqual(sorted(os.listdir(os.path.join(self.work, "ks_x", "kit"))), ["ks_a"])
        base_files = set(sha_tree(tune.base_dir(self.work, "ks_x")))
        self.assertEqual(set(sha_tree(root)) - base_files, {"kit.json", "content/cars/ks_x/data/kit_turbo_0.turbo"})
        self.assertEqual(base_files - set(sha_tree(root)), set())

    def test_the_turbo_file_of_the_donor_is_copied_into_the_data_folder_of_the_car(self):
        root = self.kit("ks_a")
        self.assertEqual(self.read(self.car_file(root, "ks_x", "data/kit_turbo_0.turbo")), {"max_boost": 0.8, "lag": 0.3})
        with open(self.base_file("ks_a", "data/t0.turbo"), "rb") as a, open(self.car_file(root, "ks_x", "data/kit_turbo_0.turbo"), "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_a_twin_donor_gives_two_files_in_the_order_of_its_engine(self):
        root = self.kit("ks_b")
        self.assertEqual([self.read(self.car_file(root, "ks_x", "data/kit_turbo_%d.turbo" % n))["max_boost"] for n in (0, 1)], [1.0, 1.2])
        engine = self.read(self.car_file(root, "ks_x", "data/engine.carengine"))
        self.assertEqual(engine["turbos_to_load"], [KIT_ENTRY % 0, KIT_ENTRY % 1])
        self.assertEqual([t["max_boost"] for t in engine["turbos"]], [1.0, 1.2])
        info = self.kit_json("ks_b")
        self.assertEqual((info["count"], info["kind"], info["files"]),
                         (2, "twin turbo", ["content/cars/ks_x/data/kit_turbo_0.turbo", "content/cars/ks_x/data/kit_turbo_1.turbo"]))

    def test_the_engine_gets_the_turbo_fields_of_the_donor_and_nothing_else(self):
        engine = self.read(self.car_file(self.kit("ks_a"), "ks_x", "data/engine.carengine"))
        donor = self.read(self.base_file("ks_a", "data/engine.carengine"))
        self.assertEqual(engine["turbos_to_load"], [KIT_ENTRY % 0])
        for key in ("turbos", "max_turbo_boost", "bov_noise"):
            self.assertEqual(engine[key], donor[key])
        self.assertEqual({k: v for k, v in engine.items() if k not in ENGINE_FIELDS + ["_order"]},
                         {"limiter": 7000.0, "boost_display": 3, "name": "na"})
        self.assertEqual(engine["limiter"], 7000.0)
        self.assertNotIn("sound_turbine", engine)
        self.assertNotIn("controller", engine)
        self.assertEqual(engine["_order"], ["name", "limiter", "boost_display", "turbos_to_load", "turbos", "max_turbo_boost", "bov_noise"])
        assert_order_valid(self, engine)

    def test_the_copied_values_are_copies_not_the_objects_of_the_donor(self):
        root = self.kit("ks_b")
        engine = self.read(self.car_file(root, "ks_x", "data/engine.carengine"))
        engine["turbos"][0]["max_boost"] = 9.0
        self.assertEqual(self.read(self.base_file("ks_b", "data/engine.carengine"))["turbos"][0]["max_boost"], 1.0)
        a = {"turbos": [{"max_boost": 1.0}], "_order": ["turbos"]}
        b = {}
        tune.copy_turbo_fields(b, a, [])
        b["turbos"][0]["max_boost"] = 2.0
        self.assertEqual(a["turbos"][0]["max_boost"], 1.0)

    def test_the_inline_engine_block_of_the_car_file_gets_the_same_fields_with_the_rewritten_list(self):
        car = self.read(self.car_file(self.kit("ks_b"), "ks_x", "data/ks_x.car"))
        donor = self.read(self.base_file("ks_b", "data/ks_b.car"))["engine"]
        inline = car["engine"]
        self.assertEqual(inline["turbos_to_load"], [KIT_ENTRY % 0, KIT_ENTRY % 1])
        self.assertEqual((inline["turbos"], inline["max_turbo_boost"]), (donor["turbos"], donor["max_turbo_boost"]))
        self.assertEqual({k: v for k, v in inline.items() if k not in INLINE_FIELDS + ["_order"]}, {"limiter": 7000.0, "name": "inline_na"})
        self.assertEqual(car["engine_path"], self.read(self.base_file("ks_x", "data/ks_x.car"))["engine_path"])
        self.assertEqual(inline["_order"], ["name", "limiter"] + ["turbos_to_load"] * 2 + ["turbos"] * 2 + ["max_turbo_boost"])
        assert_order_valid(self, inline)

    def test_a_donor_without_an_inline_block_or_a_car_without_one_leaves_the_car_file_alone(self):
        for car_id, donor in (("ks_x", "ks_s"), ("ks_n", "ks_a")):
            with self.subTest(car_id, donor=donor):
                root = self.kit(donor, car_id)
                self.assertEqual(self.kit_json(donor, car_id)["inline_fields"], [])
                with open(self.base_file(car_id, "data/%s.car" % car_id), "rb") as a, open(self.car_file(root, car_id, "data/%s.car" % car_id), "rb") as b:
                    self.assertEqual(a.read(), b.read())
                self.assertTrue(os.path.samefile(self.base_file(car_id, "data/%s.car" % car_id), self.car_file(root, car_id, "data/%s.car" % car_id)))

    def test_kit_json_names_what_was_built(self):
        self.kit("ks_a")
        info = self.kit_json("ks_a")
        self.assertEqual({k: v for k, v in info.items() if k != "stamp"},
                         {"donor": "ks_a", "kind": "single turbo", "count": 1, "files": ["content/cars/ks_x/data/kit_turbo_0.turbo"],
                          "fields": ENGINE_FIELDS, "inline_fields": INLINE_FIELDS})
        self.assertEqual(set(info), {"donor", "kind", "count", "files", "fields", "inline_fields", "stamp"})

    def test_the_stamp_has_size_and_time_of_the_engine_and_car_files_of_both_cars_and_the_turbo_files_of_the_donor(self):
        self.kit("ks_b")
        stamp = self.kit_json("ks_b")["stamp"]
        self.assertEqual([(s[0], s[1]) for s in stamp],
                         [("car", "data/ks_x.car"), ("car", "data/engine.carengine"), ("donor", "data/ks_b.car"),
                          ("donor", "data/engine.carengine"), ("donor", "data/turbo_a.turbo"), ("donor", "data/turbo_b.turbo")])
        for side, rel, size, mtime in stamp:
            st = os.stat(self.base_file("ks_x" if side == "car" else "ks_b", rel))
            self.assertEqual((size, mtime), (st.st_size, st.st_mtime_ns))

    def test_every_untouched_file_is_a_hard_link_of_base_and_a_patched_file_is_a_new_file(self):
        root = self.kit("ks_a")
        rel = "presets/p.mechanicalcarpreset"
        self.assertTrue(os.path.samefile(self.base_file("ks_x", rel), self.car_file(root, "ks_x", rel)))
        self.assertEqual(os.stat(self.base_file("ks_x", rel)).st_nlink, 2)
        shared = os.path.join("content", "cars", "common_phsx", "tyres", "a.tyre")
        self.assertTrue(os.path.samefile(os.path.join(tune.base_dir(self.work, "ks_x"), shared), os.path.join(root, shared)))
        self.assertFalse(os.path.samefile(self.base_file("ks_x", "data/engine.carengine"), self.car_file(root, "ks_x", "data/engine.carengine")))
        self.assertFalse(os.path.samefile(self.base_file("ks_x", "data/ks_x.car"), self.car_file(root, "ks_x", "data/ks_x.car")))
        self.assertEqual(os.stat(self.base_file("ks_x", "data/engine.carengine")).st_nlink, 1)

    def test_base_is_byte_identical_after_building_a_kit(self):
        before = {c: sha_tree(tune.base_dir(self.work, c)) for c in CARS}
        for donor in ("ks_a", "ks_b", "ks_s"):
            self.kit(donor)
        self.assertEqual({c: sha_tree(tune.base_dir(self.work, c)) for c in CARS}, before)

    def test_without_hard_links_the_tree_is_copied(self):
        before = sha_tree(tune.base_dir(self.work, "ks_x"))
        with mock.patch.object(os, "link", side_effect=OSError("no links here")) as link:
            root = self.kit("ks_a")
        self.assertTrue(link.called)
        rel = "presets/p.mechanicalcarpreset"
        self.assertFalse(os.path.samefile(self.base_file("ks_x", rel), self.car_file(root, "ks_x", rel)))
        self.assertEqual(os.stat(self.base_file("ks_x", rel)).st_nlink, 1)
        self.assertEqual(self.read(self.car_file(root, "ks_x", rel)), {"brand": "B", "description": "D"})
        self.assertEqual(self.read(self.car_file(root, "ks_x", "data/engine.carengine"))["turbos_to_load"], [KIT_ENTRY % 0])
        self.assertEqual(sha_tree(tune.base_dir(self.work, "ks_x")), before)

    def test_the_style_of_the_donor_entry_is_kept(self):
        root = self.kit("ks_s")
        engine = self.read(self.car_file(root, "ks_x", "data/engine.carengine"))
        self.assertEqual(engine["turbos_to_load"], ["CONTENT/CARS/KS_X/data/kit_turbo_0.turbo"])
        self.assertEqual(self.read(self.car_file(root, "ks_x", "data/kit_turbo_0.turbo")), {"max_boost": 0.9, "lag": 0.3})

    def test_entries_are_written_with_the_separators_and_case_of_the_donor_entry(self):
        for text, want in (("content\\cars\\ks_a\\data\\t0.turbo", "content\\cars\\ks_x\\data\\kit_turbo_0.turbo"),
                           ("content/cars/ks_a/data/turbos/t0.turbo", "content/cars/ks_x/data/kit_turbo_0.turbo"),
                           ("CONTENT\\CARS\\KS_A\\DATA\\T0.TURBO", "CONTENT\\CARS\\KS_X\\data\\kit_turbo_0.turbo"),
                           ("Content\\Cars\\Ks_A\\data\\x.turbo", "Content\\Cars\\ks_x\\data\\kit_turbo_0.turbo"),
                           ("content\\cars\\ks_a\\t0.turbo", "content\\cars\\ks_x\\data\\kit_turbo_0.turbo"),
                           ("content/cars\\ks_a/data\\t0.turbo", "content/cars\\ks_x/data\\kit_turbo_0.turbo")):
            with self.subTest(text):
                self.assertEqual(tune.kit_entry(text, "ks_a", "ks_x", "kit_turbo_0.turbo"), want)

    def test_an_entry_whose_style_cannot_be_read_is_an_error(self):
        for text in ("data\\t0.turbo", "content\\cars\\ks_z\\data\\t0.turbo", "content\\cars\\common_phsx\\t0.turbo", "content\\cars\\ks_a\\",
                     "\\content\\cars\\ks_a\\data\\t0.turbo", "../common_phsx/t0.turbo", "", "ks_a"):
            with self.subTest(text):
                with self.assertRaisesRegex(ValueError, r"^turbo kit: cannot read the style of the turbos_to_load entry"):
                    tune.kit_entry(text, "ks_a", "ks_x", "kit_turbo_0.turbo")

    def test_a_donor_entry_of_an_unreadable_style_fails_the_build_and_leaves_no_partial(self):
        self.edit("ks_a", "data/engine.carengine", lambda e: e.update(turbos_to_load=["content\\cars\\ks_a\\data\\t0.turbo "]))
        with self.assertRaisesRegex(ValueError, "^turbo kit: "):
            self.kit("ks_a")
        self.assertEqual(sorted(os.listdir(os.path.join(self.work, "ks_x"))), ["base", "stock_info.json"])

    def test_a_kit_turbo_file_that_is_in_the_data_folder_already_is_refused(self):
        self.put(self.fakes["ks_x"], "data/Kit_Turbo_0.turbo", {"max_boost": 1})
        with self.assertRaisesRegex(ValueError, "^turbo kit: ks_x has a data/kit_turbo_0.turbo already$"):
            self.kit("ks_a")
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "kit")) and os.listdir(os.path.join(self.work, "ks_x", "kit")))

    def test_the_inline_list_must_name_files_of_the_engine_list(self):
        self.edit("ks_a", "data/ks_a.car", lambda c: c["engine"].update(turbos_to_load=["content\\cars\\ks_a\\data\\other.turbo"]))
        with self.assertRaisesRegex(ValueError, "^turbo kit: the .car file of ks_a lists turbo files that its engine file does not list$"):
            self.kit("ks_a")
        self.edit("ks_a", "data/ks_a.car", lambda c: c["engine"].update(turbos_to_load=["CONTENT/CARS/KS_A/DATA/T0.TURBO"]))
        self.assertEqual(self.read(self.car_file(self.kit("ks_a"), "ks_x", "data/ks_x.car"))["engine"]["turbos_to_load"], [KIT_ENTRY % 0])

    def test_a_leftover_partial_folder_is_removed(self):
        stale = os.path.join(self.work, "ks_x", "kit", "ks_a.partial", "content", "stale.bin")
        self.write(stale, "x")
        root = self.kit("ks_a")
        self.assertEqual(sorted(os.listdir(os.path.dirname(root))), ["ks_a"])
        self.assertFalse(os.path.exists(os.path.join(root, "content", "stale.bin")))

    def test_a_failed_build_removes_its_partial_folder_and_keeps_an_older_kit(self):
        old = self.kit("ks_a")
        old_info = self.kit_json("ks_a")
        self.edit("ks_a", "data/engine.carengine", lambda e: e.update(max_turbo_boost=0.85))
        with mock.patch.object(tune, "patch_kit", side_effect=ValueError("boom")):
            with self.assertRaisesRegex(ValueError, "^boom$"):
                self.kit("ks_a")
        self.assertEqual(sorted(os.listdir(os.path.dirname(old))), ["ks_a"])
        self.assertEqual(self.kit_json("ks_a"), old_info)

    def test_a_failure_of_the_disk_is_an_os_error_and_leaves_no_partial_folder(self):
        def link_tree(src, dst):
            REAL_LINK_TREE(src, dst)
            raise OSError("disk full")
        with mock.patch.object(tune, "link_tree", link_tree):
            with self.assertRaisesRegex(OSError, "^disk full$"):
                self.kit("ks_a")
        self.assertEqual(os.listdir(os.path.join(self.work, "ks_x", "kit")), [])

    def test_the_kits_of_two_donors_are_separate_trees(self):
        a, b = self.kit("ks_a"), self.kit("ks_b")
        self.assertNotEqual(a, b)
        self.assertEqual(self.read(self.car_file(a, "ks_x", "data/engine.carengine"))["turbos_to_load"], [KIT_ENTRY % 0])
        self.assertEqual(len(self.read(self.car_file(b, "ks_x", "data/engine.carengine"))["turbos_to_load"]), 2)
        self.assertFalse(os.path.exists(self.car_file(a, "ks_x", "data/kit_turbo_1.turbo")))

    def test_a_car_gets_kits_of_its_own_in_its_own_folder(self):
        self.kit("ks_a", "ks_x")
        root = self.kit("ks_a", "ks_n")
        self.assertEqual(root, os.path.join(self.work, "ks_n", "kit", "ks_a"))
        self.assertTrue(os.path.exists(self.car_file(root, "ks_n", "data/kit_turbo_0.turbo")))
        self.assertEqual(self.read(self.car_file(root, "ks_n", "data/engine.carengine"))["turbos_to_load"],
                         ["content\\cars\\ks_n\\data\\kit_turbo_0.turbo"])


class TestKitStamp(World):
    def test_unchanged_inputs_do_not_build_again(self):
        first = self.kit("ks_a")
        self.assertEqual((self.kit("ks_a"), self.kit("ks_a"), self.builds), (first, first, [("ks_x", "ks_a")]))

    def test_a_changed_boost_of_the_donor_builds_again_with_the_new_value(self):
        self.kit("ks_a")
        self.edit("ks_a", "data/engine.carengine", lambda e: e["turbos"][0].update(max_boost=0.85))
        root = self.kit("ks_a")
        self.assertEqual(len(self.builds), 2)
        self.assertEqual(self.read(self.car_file(root, "ks_x", "data/engine.carengine"))["turbos"][0]["max_boost"], 0.85)
        self.kit("ks_a")
        self.assertEqual(len(self.builds), 2)

    def test_a_changed_turbo_file_of_the_donor_builds_again(self):
        self.kit("ks_a")
        self.edit("ks_a", "data/t0.turbo", lambda t: t.update(max_boost=0.85, lag=0.35))
        root = self.kit("ks_a")
        self.assertEqual((len(self.builds), self.read(self.car_file(root, "ks_x", "data/kit_turbo_0.turbo"))), (2, {"max_boost": 0.85, "lag": 0.35}))

    def test_a_changed_car_file_of_the_donor_builds_again(self):
        self.kit("ks_a")
        self.edit("ks_a", "data/ks_a.car", lambda c: c["engine"].update(idle=950))
        self.kit("ks_a")
        self.assertEqual(len(self.builds), 2)

    def test_a_changed_engine_file_of_the_car_builds_again(self):
        self.kit("ks_a")
        self.edit("ks_x", "data/engine.carengine", lambda e: e.update(limiter=7500.0))
        root = self.kit("ks_a")
        self.assertEqual((len(self.builds), self.read(self.car_file(root, "ks_x", "data/engine.carengine"))["limiter"]), (2, 7500.0))

    def test_a_changed_car_file_of_the_car_builds_again(self):
        self.kit("ks_a")
        self.edit("ks_x", "data/ks_x.car", lambda c: c["engine"].update(limiter=7500.0))
        self.kit("ks_a")
        self.assertEqual(len(self.builds), 2)

    def test_a_changed_time_alone_builds_again(self):
        self.kit("ks_a")
        path = self.base_file("ks_a", "data/engine.carengine")
        st = os.stat(path)
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
        self.kit("ks_a")
        self.assertEqual(len(self.builds), 2)

    def test_a_file_the_kit_does_not_depend_on_does_not_build_again(self):
        self.kit("ks_a")
        self.edit("ks_x", "presets/p.mechanicalcarpreset", lambda p: p.update(description="Other text"))
        self.edit("ks_a", "presets/p.mechanicalcarpreset", lambda p: p.update(description="Other text"))
        self.put(self.fakes["ks_b"], "data/extra.turbo", {"max_boost": 2.0})
        self.kit("ks_a")
        self.assertEqual(len(self.builds), 1)

    def test_a_missing_or_damaged_tree_is_built_again(self):
        root = self.kit("ks_a")
        os.remove(self.car_file(root, "ks_x", "data/kit_turbo_0.turbo"))
        self.kit("ks_a")
        self.assertEqual(len(self.builds), 2)
        os.remove(os.path.join(root, "kit.json"))
        self.kit("ks_a")
        self.assertEqual(len(self.builds), 3)
        with open(os.path.join(root, "kit.json"), "w") as f:
            f.write("{")
        self.kit("ks_a")
        self.assertEqual(len(self.builds), 4)
        with open(os.path.join(root, "kit.json"), "w") as f:
            f.write(json.dumps({"donor": "ks_a"}))
        self.kit("ks_a")
        self.assertEqual(len(self.builds), 5)
        self.assertTrue(os.path.exists(self.car_file(root, "ks_x", "data/kit_turbo_0.turbo")))

    def test_a_kit_of_another_donor_in_the_folder_is_not_taken(self):
        root = self.kit("ks_a")
        info = self.kit_json("ks_a")
        info["donor"] = "ks_b"
        with open(os.path.join(root, "kit.json"), "w") as f:
            json.dump(info, f)
        self.kit("ks_a")
        self.assertEqual(len(self.builds), 2)
        self.assertEqual(self.kit_json("ks_a")["donor"], "ks_a")

    def test_the_old_tree_is_replaced_not_merged(self):
        root = self.kit("ks_b")
        self.write(os.path.join(root, "content", "stale.bin"), "x")
        self.edit("ks_b", "data/engine.carengine", lambda e: e.update(max_turbo_boost=1.25))
        self.kit("ks_b")
        self.assertFalse(os.path.exists(os.path.join(root, "content", "stale.bin")))

    def test_a_donor_that_lost_its_files_or_its_base_is_an_error_at_the_next_use(self):
        self.kit("ks_a")
        os.remove(self.base_file("ks_a", "data/t0.turbo"))
        with self.assertRaisesRegex(ValueError, "^turbo kit: ks_a is not an installed car with a turbo$"):
            self.kit("ks_a")
        self.kit("ks_b")
        shutil.rmtree(tune.base_dir(self.work, "ks_b"))
        with self.assertRaisesRegex(ValueError, "^turbo kit: ks_b is not an installed car with a turbo$"):
            self.kit("ks_b")


class TestKitChecks(World):
    def test_a_car_with_a_turbo_of_its_own_gets_no_kit(self):
        with self.assertRaisesRegex(ValueError, "^turbo kit: ks_a has a turbo already$"):
            self.kit("ks_b", "ks_a")
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_a", "kit")))

    def test_a_car_that_gets_a_turbo_after_the_kit_was_built_is_refused_at_the_next_use(self):
        self.kit("ks_a")
        self.edit("ks_x", "data/engine.carengine", lambda e: e.update(turbos_to_load=[self.fakes["ks_x"].game_path("data/own.turbo")]))
        self.put(self.fakes["ks_x"], "data/own.turbo", {"max_boost": 1})
        with self.assertRaisesRegex(ValueError, "^turbo kit: ks_x has a turbo already$"):
            self.kit("ks_a")

    def test_the_car_cannot_be_its_own_donor(self):
        with self.assertRaisesRegex(ValueError, "^turbo kit: ks_x cannot be its own turbo donor$"):
            self.kit("ks_x")

    def test_a_donor_that_is_no_donor_is_refused(self):
        for donor in ("ks_n", "ks_gone", "", "../ks_a", "KS_A", "ks_a/..", 5, None, ["ks_a"]):
            with self.subTest(repr(donor)):
                with self.assertRaisesRegex(ValueError, "^turbo kit: .* is not an installed car with a turbo$"):
                    self.kit(donor)
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "kit")))
        self.assertEqual(self.builds, [])

    def test_a_car_without_a_base_is_refused(self):
        with self.assertRaisesRegex(ValueError, r"^turbo kit: no base car in .*, run init first$"):
            self.kit("ks_a", "ks_none")


class TestRootFor(World):
    def test_without_a_kit_the_root_is_base_and_nothing_is_built(self):
        base = tune.base_dir(self.work, "ks_x")
        self.assertEqual(tune.root_for(self.work, "ks_x"), base)
        tune.save_state(self.work, "ks_x", {"limiter": 8000})
        self.assertEqual([tune.root_for(self.work, "ks_x", t) for t in (None, "ax_x", tune.DRAFT)], [base, base, base])
        self.assertEqual(self.builds, [])
        self.assertEqual(sorted(os.listdir(os.path.join(self.work, "ks_x"))), ["base", "stock_info.json", "tune_state.json"])

    def test_with_a_kit_the_root_is_the_kit_root_of_the_donor(self):
        self.with_kit("ks_b")
        root = tune.root_for(self.work, "ks_x")
        self.assertEqual(root, os.path.join(self.work, "ks_x", "kit", "ks_b"))
        self.assertEqual(tune.root_for(self.work, "ks_x", "ax_x"), root)
        self.assertEqual(self.builds, [("ks_x", "ks_b")])

    def test_each_tune_and_the_draft_have_their_own_root(self):
        self.two_tunes()
        tune.save_state(self.work, "ks_x", {KEY: {"donor": "ks_s"}}, tune.DRAFT)
        roots = [tune.root_for(self.work, "ks_x", t) for t in (None, "ax01", tune.DRAFT)]
        self.assertEqual([os.path.basename(r) for r in roots], ["ks_a", "ks_b", "ks_s"])
        self.assertEqual(tune.root_for(self.work, "ks_x", "ax02"), tune.base_dir(self.work, "ks_x"))

    def test_the_draft_without_a_kit_is_base_while_the_default_tune_has_one(self):
        self.with_kit("ks_a")
        tune.save_state(self.work, "ks_x", {}, tune.DRAFT)
        self.assertEqual(tune.root_for(self.work, "ks_x", tune.DRAFT), tune.base_dir(self.work, "ks_x"))

    def test_a_donor_that_is_gone_is_an_error_with_a_kit_only(self):
        self.with_kit("ks_a")
        self.kit("ks_a")
        shutil.rmtree(tune.base_dir(self.work, "ks_a"))
        with self.assertRaisesRegex(ValueError, "^turbo kit: ks_a is not an installed car with a turbo$"):
            tune.root_for(self.work, "ks_x")
        tune.reset_turbo(self.work, "ks_x")
        self.assertEqual(tune.root_for(self.work, "ks_x"), tune.base_dir(self.work, "ks_x"))

    def test_a_car_that_has_a_turbo_itself_is_an_error(self):
        self.with_kit("ks_b", car_id="ks_a")
        with self.assertRaisesRegex(ValueError, "^turbo kit: ks_a has a turbo already$"):
            tune.root_for(self.work, "ks_a")

    def test_a_damaged_saved_kit_is_the_error_of_turbo_choice(self):
        for bad in ("ks_a", ["ks_a"], {}, {"donor": 5}, None):
            tune.save_state(self.work, "ks_x", {KEY: bad})
            with self.subTest(repr(bad)):
                with self.assertRaisesRegex(ValueError, "^damaged turbo kit in the saved state$"):
                    tune.root_for(self.work, "ks_x")
                with self.assertRaisesRegex(ValueError, "^damaged turbo kit in the saved state$"):
                    tune.turbo_choice(self.work, "ks_x")


class TestResolve(World):
    def rows(self, tune_id=None, hidden=True, car_id="ks_x"):
        return {r["id"]: r for r in tune.effective_rows(self.work, car_id, self.cat, hidden=hidden, tune=tune_id)}

    def test_a_car_without_a_kit_hides_the_turbo_settings(self):
        rows = self.rows()
        for sid in ("turbo_boost_1", "turbo_boost_2", "max_turbo_boost"):
            self.assertFalse(rows[sid]["applicable"], sid)
        self.assertEqual(rows["turbo_boost_1"]["reason"], "@engine turbos[0].max_boost: missing field 'turbos'")
        self.assertEqual(sorted(self.rows(hidden=False)), ["limiter", "name_suffix", "variant_name"])
        self.assertEqual(self.builds, [])

    def test_with_a_kit_the_turbo_settings_are_applicable_with_the_values_of_the_donor(self):
        self.with_kit("ks_b")
        rows = self.rows()
        self.assertEqual([(rows[s]["applicable"], rows[s]["default"], rows[s]["value"], rows[s]["changed"])
                          for s in ("turbo_boost_1", "turbo_boost_2", "max_turbo_boost")],
                         [(True, 1.0, 1.0, False), (True, 1.2, 1.2, False), (True, 1.2, 1.2, False)])
        self.assertEqual([t["file"] for t in rows["turbo_boost_1"]["targets"]], ["@engine", "@turbo[0]", "@car"])
        self.assertTrue(all(t["resolved"] for t in rows["turbo_boost_1"]["targets"]))
        self.assertTrue(all(t["resolved"] for t in rows["max_turbo_boost"]["targets"]))
        self.assertEqual(rows["turbo_boost_2"]["targets"][1]["rel"], "data/kit_turbo_1.turbo")

    def test_a_single_turbo_donor_gives_one_turbo_setting_and_the_engine_value(self):
        self.with_kit("ks_a")
        rows = self.rows()
        self.assertEqual([(rows[s]["applicable"], rows[s]["default"]) for s in ("turbo_boost_1", "max_turbo_boost")], [(True, 0.8), (True, 0.8)])
        self.assertFalse(rows["turbo_boost_2"]["applicable"])
        self.assertEqual(rows["turbo_boost_2"]["reason"], "@engine turbos[1].max_boost: list has no element 1")

    def test_a_donor_without_an_inline_block_still_makes_the_engine_targets_applicable(self):
        self.with_kit("ks_s")
        rows = self.rows()
        self.assertEqual((rows["turbo_boost_1"]["applicable"], rows["turbo_boost_1"]["default"]), (True, 0.9))
        self.assertFalse(rows["turbo_boost_1"]["targets"][2]["resolved"])
        self.assertTrue(rows["turbo_boost_1"]["targets"][2]["optional"])

    def test_a_value_set_in_the_state_is_the_effective_value_and_changed(self):
        tune.save_state(self.work, "ks_x", {KEY: {"donor": "ks_a"}, "turbo_boost_1": 1.1})
        row = self.rows()["turbo_boost_1"]
        self.assertEqual((row["default"], row["value"], row["changed"]), (0.8, 1.1, True))

    def test_resolve_defaults_without_a_tune_reads_the_stock_car_even_when_a_kit_is_saved(self):
        self.with_kit("ks_a")
        rows = {r["id"]: r for r in tune.resolve_defaults(self.work, "ks_x", self.cat, hidden=True)}
        self.assertFalse(rows["turbo_boost_1"]["applicable"])
        self.assertEqual(self.builds, [])
        rows = {r["id"]: r for r in tune.resolve_defaults(self.work, "ks_x", self.cat, hidden=True, tune="ax_x")}
        self.assertTrue(rows["turbo_boost_1"]["applicable"])
        rows = {r["id"]: r for r in tune.resolve_defaults(self.work, "ks_x", self.cat, hidden=True, tune="ax01")}
        self.assertFalse(rows["turbo_boost_1"]["applicable"])

    def test_the_draft_and_a_tune_resolve_with_their_own_kit(self):
        self.two_tunes()
        tune.save_state(self.work, "ks_x", {}, tune.DRAFT)
        self.assertEqual([self.rows(t)["turbo_boost_1"]["default"] for t in (None, "ax01")], [0.8, 1.0])
        self.assertFalse(self.rows(tune.DRAFT)["turbo_boost_1"]["applicable"])
        tune.set_turbo(self.work, "ks_x", "ks_s", tune.DRAFT)
        self.assertEqual(self.rows(tune.DRAFT)["turbo_boost_1"]["default"], 0.9)

    def test_two_tunes_with_different_donors_do_not_share_cached_rows(self):
        self.two_tunes()
        with mock.patch.object(tune, "resolve_rows", wraps=tune.resolve_rows) as resolve:
            first = [self.rows(t)["turbo_boost_1"]["default"] for t in (None, "ax01")]
            self.assertEqual((first, resolve.call_count), ([0.8, 1.0], 2))
            again = [self.rows(t)["turbo_boost_1"]["default"] for t in (None, "ax01", None, "ax01")]
            self.assertEqual((again, resolve.call_count), ([0.8, 1.0, 0.8, 1.0], 2))
            stock = tune.resolve_defaults(self.work, "ks_x", self.cat, hidden=True)
            self.assertEqual(resolve.call_count, 3)
            self.assertFalse(next(r for r in stock if r["id"] == "turbo_boost_1")["applicable"])
            tune.resolve_defaults(self.work, "ks_x", self.cat, hidden=True)
            self.assertEqual(resolve.call_count, 3)
            self.assertEqual({k[2] for k in tune._resolved if k[:2] == (self.work, "ks_x")},
                             {tune.base_dir(self.work, "ks_x"), tune.kit_path(self.work, "ks_x", "ks_a"), tune.kit_path(self.work, "ks_x", "ks_b")})

    def test_the_cached_rows_follow_a_rebuilt_kit(self):
        for donor, turbo, before, after in (("ks_a", "data/t0.turbo", 0.8, 0.85), ("ks_s", "data/turbos/s.turbo", 0.9, 0.95)):
            with self.subTest(donor):
                tune.save_state(self.work, "ks_x", {KEY: {"donor": donor}})
                builds = len(self.builds)
                self.assertEqual(self.rows()["turbo_boost_1"]["default"], before)
                self.edit(donor, "data/engine.carengine", lambda e: e["turbos"][0].update(max_boost=after))
                self.edit(donor, turbo, lambda t: t.update(max_boost=after))
                self.assertEqual(self.rows()["turbo_boost_1"]["default"], after)
                self.assertEqual(len(self.builds), builds + 2)

    def test_the_rows_of_a_kit_come_from_the_kit_files_not_from_a_cache_shared_with_base(self):
        self.with_kit("ks_a")
        stock_first = tune.resolve_defaults(self.work, "ks_x", self.cat, hidden=True)
        self.assertFalse(next(r for r in stock_first if r["id"] == "max_turbo_boost")["applicable"])
        self.assertEqual(self.rows()["max_turbo_boost"]["default"], 0.8)
        self.assertFalse(next(r for r in tune.resolve_defaults(self.work, "ks_x", self.cat, hidden=True) if r["id"] == "max_turbo_boost")["applicable"])

    def test_the_stamp_of_a_kit_root_includes_the_kit_stamp(self):
        root = self.kit("ks_a")
        base = tune.base_dir(self.work, "ks_x")
        self.assertEqual(tune.resolve_stamp(self.work, "ks_x", base), tune.resolve_stamp(self.work, "ks_x"))
        self.assertEqual(len(tune.resolve_stamp(self.work, "ks_x", root)), len(tune.resolve_stamp(self.work, "ks_x")) + 1)
        self.assertEqual(tune.resolve_stamp(self.work, "ks_x", root)[-1], self.kit_json("ks_a")["stamp"])

    def test_a_car_without_a_kit_beside_a_car_with_one_still_hides_the_turbo_settings(self):
        self.with_kit("ks_a")
        self.assertTrue(self.rows()["turbo_boost_1"]["applicable"])
        self.assertFalse(self.rows(car_id="ks_n")["turbo_boost_1"]["applicable"])
        self.assertFalse(self.rows("ax01")["turbo_boost_1"]["applicable"])


class TestSetValue(World):
    def test_a_turbo_setting_can_be_set_on_a_tune_with_a_kit(self):
        self.with_kit("ks_a")
        res = tune.set_value(self.work, "ks_x", "turbo_boost_1", "1.1", self.cat)
        self.assertEqual((res["id"], tune.plain(res["value"]), res["warnings"]), ("turbo_boost_1", 1.1, []))
        self.assertEqual(self.state(), {KEY: {"donor": "ks_a"}, "turbo_boost_1": 1.1})
        self.assertEqual(tune.set_value(self.work, "ks_x", "max_turbo_boost", "4", self.cat)["warnings"],
                         ["max_turbo_boost=4.0 is outside the suggested range 0..3"])

    def test_it_is_refused_without_a_kit_and_the_state_stays(self):
        with self.assertRaisesRegex(ValueError, r"^turbo_boost_1 is not applicable to ks_x: @engine turbos\[0\]\.max_boost: missing field 'turbos'$"):
            tune.set_value(self.work, "ks_x", "turbo_boost_1", "1.1", self.cat)
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x")))

    def test_a_tune_and_the_draft_are_checked_against_their_own_kit(self):
        tune.save_state(self.work, "ks_x", {"name_suffix": "_B"}, "ax01")
        tune.set_turbo(self.work, "ks_x", "ks_b", tune.DRAFT)
        self.with_kit("ks_a")
        tune.set_value(self.work, "ks_x", "turbo_boost_2", "1.1", self.cat, tune=tune.DRAFT)
        self.assertEqual(self.state(tune.DRAFT), {KEY: {"donor": "ks_b"}, "turbo_boost_2": 1.1})
        with self.assertRaisesRegex(ValueError, r"^turbo_boost_2 is not applicable to ks_x: @engine turbos\[1\]\.max_boost: list has no element 1$"):
            tune.set_value(self.work, "ks_x", "turbo_boost_2", "1.1", self.cat)
        with self.assertRaisesRegex(ValueError, "^turbo_boost_1 is not applicable to ks_x: "):
            tune.set_value(self.work, "ks_x", "turbo_boost_1", "1.1", self.cat, tune="ax01")
        tune.set_value(self.work, "ks_x", "turbo_boost_1", "1.1", self.cat, tune="ax_x")
        self.assertEqual(self.state()["turbo_boost_1"], 1.1)

    def test_a_setting_of_the_stock_car_is_set_as_before_with_or_without_a_kit(self):
        self.with_kit("ks_a")
        tune.set_value(self.work, "ks_x", "limiter", "8000", self.cat)
        tune.set_value(self.work, "ks_x", "limiter", "8100", self.cat, tune="ax01")
        self.assertEqual((self.state()["limiter"], self.state("ax01")), (8000, {"limiter": 8100}))

    def test_unset_removes_the_value_and_keeps_the_kit(self):
        self.with_kit("ks_a")
        tune.set_value(self.work, "ks_x", "turbo_boost_1", "1.1", self.cat)
        self.assertEqual(tune.unset_value(self.work, "ks_x", "turbo_boost_1", self.cat), {"id": "turbo_boost_1", "removed": True})
        self.assertEqual(self.state(), {KEY: {"donor": "ks_a"}})

    def test_a_kit_that_cannot_be_built_is_the_error_of_the_set(self):
        self.with_kit("ks_gone")
        with self.assertRaisesRegex(ValueError, "^turbo kit: ks_gone is not an installed car with a turbo$"):
            tune.set_value(self.work, "ks_x", "limiter", "8000", self.cat)


class Apply(World):
    """apply of ks_x with clone_car.build replaced by the real copy_renamed and kspkg.cmd_pack by a recorder."""

    def setUp(self):
        super().setUp()
        self.calls, self.packed = [], []
        self.patch(clone_car, "build", self.build)
        self.patch(kspkg, "cmd_pack", self.pack)
        self.patch(tune, "ensure_stock_loc", lambda work, game=None: "present")
        self.game = os.path.join(self.work, "no_game.kspkg")
        spy = tune.patch_kit

        def spy_patch_kit(work, car_id, donor, part):
            self.calls.append("kit")
            return spy(work, car_id, donor, part)
        self.patch(tune, "patch_kit", spy_patch_kit)

    def build(self, car_dir, new_id, out_dir, name, year, brand, variant, stock_loc, props, pack=True):
        self.calls.append("build")
        old = os.path.basename(car_dir)
        clone_car.validate(old, new_id, out_dir)
        clone_car.copy_renamed(car_dir, os.path.join(out_dir, "content", "cars", new_id), old, new_id)
        return ["note: from build"]

    def pack(self, indir, pkg):
        self.calls.append("pack")
        self.packed.append(sorted(os.path.relpath(os.path.join(dp, n), indir).replace(os.sep, "/") for dp, _, names in os.walk(indir) for n in names))
        with open(pkg, "wb") as f:
            f.write(b"PKG")

    def apply(self, state=None, new_id=None, **kw):
        if state is not None:
            tune.save_state(self.work, "ks_x", state, new_id)
        kw.setdefault("install", False)
        return tune.apply(self.work, "ks_x", new_id, catalogue=self.cat, game=self.game, **kw)

    def built(self, res, rel):
        return self.read(self.car_file(res["build_dir"], res["new_id"], rel))

    def tree(self, res):
        return sorted(os.path.relpath(os.path.join(dp, n), res["build_dir"]).replace(os.sep, "/")
                      for dp, _, names in os.walk(res["build_dir"]) for n in names)


class TestApplyWithAKit(Apply):
    def test_the_package_has_the_turbo_file_of_the_kit_under_the_new_id(self):
        self.with_kit("ks_a")
        res = self.apply({KEY: {"donor": "ks_a"}, "turbo_boost_1": 1.1})
        self.assertIn("content/cars/ax_x/data/kit_turbo_0.turbo", self.packed[-1])
        self.assertNotIn("content/cars/ax_x/data/kit_turbo_1.turbo", self.packed[-1])
        self.assertTrue(os.path.isfile(self.car_file(res["build_dir"], "ax_x", "data/kit_turbo_0.turbo")))
        self.assertEqual([p for p in self.packed[-1] if "kit_turbo" in p], ["content/cars/ax_x/data/kit_turbo_0.turbo"])

    def test_the_built_engine_lists_paths_of_the_new_car_that_exist_in_the_build(self):
        self.with_kit("ks_b")
        res = self.apply()
        engine = self.built(res, "data/engine.carengine")
        self.assertEqual(engine["turbos_to_load"], [TURBO_ENTRY % 0, TURBO_ENTRY % 1])
        for entry in engine["turbos_to_load"]:
            self.assertTrue(os.path.isfile(os.path.join(res["build_dir"], *entry.split("\\"))), entry)
        self.assertEqual(self.built(res, "data/ax_x.car")["engine"]["turbos_to_load"], [TURBO_ENTRY % 0, TURBO_ENTRY % 1])
        for dp, dn, names in os.walk(res["build_dir"]):
            for n in dn + names:
                self.assertNotIn("ks_x", n)
                if os.path.isfile(os.path.join(dp, n)):
                    with open(os.path.join(dp, n), "rb") as f:
                        self.assertNotIn(b"ks_x", f.read(), os.path.join(dp, n))

    def test_the_engine_of_the_build_has_the_turbo_fields_and_the_changed_value_is_in_all_three_copies(self):
        self.with_kit("ks_a")
        res = self.apply({KEY: {"donor": "ks_a"}, "turbo_boost_1": 1.1, "max_turbo_boost": 1.15})
        engine, car, turbo = (self.built(res, "data/engine.carengine"), self.built(res, "data/ax_x.car"), self.built(res, "data/kit_turbo_0.turbo"))
        self.assertEqual((engine["turbos"][0]["max_boost"], turbo["max_boost"], car["engine"]["turbos"][0]["max_boost"]), (1.1, 1.1, 1.1))
        self.assertEqual((engine["max_turbo_boost"], car["engine"]["max_turbo_boost"]), (1.15, 1.15))
        self.assertEqual((engine["bov_noise"], engine["turbos"][0]["lag"], turbo["lag"]), (0.4, 0.5, 0.3))
        self.assertEqual(engine["limiter"], 7000.0)
        self.assertEqual(sorted(a["id"] for a in res["applied"]), ["max_turbo_boost", "turbo_boost_1"])
        applied = next(a for a in res["applied"] if a["id"] == "turbo_boost_1")
        self.assertEqual((applied["old"], applied["new"], applied["files"]),
                         (0.8, 1.1, ["data/engine.carengine", "data/kit_turbo_0.turbo", "data/ax_x.car"]))

    def test_the_kit_files_and_base_keep_the_donor_values(self):
        self.with_kit("ks_a")
        before = {c: sha_tree(tune.base_dir(self.work, c)) for c in CARS}
        root = self.kit("ks_a")
        kit_before = sha_tree(root)
        self.apply({KEY: {"donor": "ks_a"}, "turbo_boost_1": 1.1, "limiter": 8000})
        self.assertEqual({c: sha_tree(tune.base_dir(self.work, c)) for c in CARS}, before)
        self.assertEqual(sha_tree(root), kit_before)
        self.assertEqual(self.read(self.car_file(root, "ks_x", "data/kit_turbo_0.turbo"))["max_boost"], 0.8)

    def test_the_result_has_the_notes_of_the_kit_after_those_of_the_build(self):
        self.with_kit("ks_a")
        res = self.apply()
        self.assertEqual(res["notes"], ["note: from build",
                                        "note: turbo kit: donor ks_a (single turbo): files data/kit_turbo_0.turbo, engine fields turbos_to_load, turbos, "
                                        "max_turbo_boost, bov_noise",
                                        "note: turbo kit: .car engine fields turbos_to_load, turbos, max_turbo_boost"])
        self.assertEqual(res["applied"], [])

    def test_a_donor_without_an_inline_block_gives_only_the_first_note(self):
        self.with_kit("ks_s")
        res = self.apply()
        self.assertEqual(res["notes"], ["note: from build",
                                        "note: turbo kit: donor ks_s (single turbo): files data/kit_turbo_0.turbo, engine fields turbos_to_load, turbos, "
                                        "max_turbo_boost, bov_noise"])
        self.assertEqual(self.built(res, "data/engine.carengine")["turbos_to_load"], ["CONTENT/CARS/AX_X/data/kit_turbo_0.turbo"])

    def test_a_twin_donor_gives_two_files_and_both_turbo_settings_write_their_own_copies(self):
        self.with_kit("ks_b")
        res = self.apply({KEY: {"donor": "ks_b"}, "turbo_boost_2": 1.3})
        self.assertEqual([p for p in self.packed[-1] if "kit_turbo" in p], ["content/cars/ax_x/data/kit_turbo_%d.turbo" % n for n in (0, 1)])
        self.assertEqual([self.built(res, "data/kit_turbo_%d.turbo" % n)["max_boost"] for n in (0, 1)], [1.0, 1.3])
        self.assertEqual([t["max_boost"] for t in self.built(res, "data/engine.carengine")["turbos"]], [1.0, 1.3])
        self.assertEqual([t["max_boost"] for t in self.built(res, "data/ax_x.car")["engine"]["turbos"]], [1.0, 1.3])
        self.assertIn("note: turbo kit: donor ks_b (twin turbo): files data/kit_turbo_0.turbo, data/kit_turbo_1.turbo, engine fields", res["notes"][1])

    def test_the_kit_is_built_before_the_build_folder_is_written(self):
        self.with_kit("ks_a")
        self.apply()
        self.assertEqual(self.calls, ["kit", "build", "pack"])

    def test_a_second_apply_with_unchanged_inputs_uses_the_kit_again(self):
        self.with_kit("ks_a")
        self.apply()
        self.apply({KEY: {"donor": "ks_a"}, "turbo_boost_1": 1.2})
        self.assertEqual(self.calls.count("kit"), 1)

    def test_a_changed_boost_of_the_donor_is_in_the_next_build(self):
        self.with_kit("ks_a")
        self.apply()
        for rel in ("data/engine.carengine", "data/t0.turbo"):
            self.edit("ks_a", rel, lambda o: (o["turbos"][0] if "turbos" in o else o).update(max_boost=0.85))
        res = self.apply()
        self.assertEqual((self.calls.count("kit"), self.built(res, "data/engine.carengine")["turbos"][0]["max_boost"],
                          self.built(res, "data/kit_turbo_0.turbo")["max_boost"]), (2, 0.85, 0.85))

    def test_base_is_byte_identical_after_an_apply_with_every_kit(self):
        before = {c: sha_tree(tune.base_dir(self.work, c)) for c in CARS}
        for donor in ("ks_a", "ks_b", "ks_s"):
            self.apply({KEY: {"donor": donor}, "limiter": 8000})
        self.assertEqual({c: sha_tree(tune.base_dir(self.work, c)) for c in CARS}, before)

    def test_without_hard_links_apply_builds_the_same_package_content(self):
        self.with_kit("ks_b")
        with_links = self.tree(self.apply({KEY: {"donor": "ks_b"}, "turbo_boost_1": 1.1}))
        sums = sha_tree(os.path.join(self.work, "ks_x", "build", "ax_x"))
        shutil.rmtree(os.path.join(self.work, "ks_x", "kit"))
        with mock.patch.object(os, "link", side_effect=OSError("no links")):
            res = self.apply()
        self.assertEqual((self.tree(res), sha_tree(res["build_dir"])), (with_links, sums))

    def test_the_new_car_may_be_a_tune_with_a_kit_of_its_own(self):
        self.two_tunes()
        first = self.apply(new_id=None)
        second = self.apply(new_id="ax01")
        self.assertEqual([p for p in self.packed[0] if "kit_turbo" in p], ["content/cars/ax_x/data/kit_turbo_0.turbo"])
        self.assertEqual([p for p in self.packed[1] if "kit_turbo" in p], ["content/cars/ax01/data/kit_turbo_%d.turbo" % n for n in (0, 1)])
        self.assertEqual(self.built(first, "data/engine.carengine")["turbos_to_load"], [TURBO_ENTRY % 0])
        self.assertEqual(self.built(second, "data/engine.carengine")["turbos_to_load"],
                         ["content\\cars\\ax01\\data\\kit_turbo_0.turbo", "content\\cars\\ax01\\data\\kit_turbo_1.turbo"])
        self.assertEqual(sorted(os.listdir(os.path.join(self.work, "ks_x", "kit"))), ["ks_a", "ks_b"])
        self.assertIn("donor ks_a (single turbo)", first["notes"][1])
        self.assertIn("donor ks_b (twin turbo)", second["notes"][1])

    def test_a_donor_that_is_gone_is_an_error_before_anything_is_built(self):
        self.with_kit("ks_a")
        self.apply()
        shutil.rmtree(tune.base_dir(self.work, "ks_a"))
        before = sha_tree(os.path.join(self.work, "ks_x", "build"))
        self.calls.clear()
        with self.assertRaisesRegex(ValueError, "^turbo kit: ks_a is not an installed car with a turbo$"):
            self.apply()
        self.assertEqual(self.calls, [])
        self.assertEqual(sha_tree(os.path.join(self.work, "ks_x", "build")), before)
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "build", "ax_x.partial")))

    def test_a_car_that_has_a_turbo_itself_cannot_apply_with_a_kit(self):
        tune.save_state(self.work, "ks_a", {KEY: {"donor": "ks_b"}})
        with self.assertRaisesRegex(ValueError, "^turbo kit: ks_a has a turbo already$"):
            tune.apply(self.work, "ks_a", catalogue=self.cat, game=self.game, install=False)
        self.assertEqual(self.calls, [])

    def test_a_damaged_saved_kit_is_an_error_before_anything_is_built(self):
        tune.save_state(self.work, "ks_x", {KEY: {"donor": 5}})
        with self.assertRaisesRegex(ValueError, "^damaged turbo kit in the saved state$"):
            self.apply()
        self.assertEqual(self.calls, [])

    def test_the_tyre_garage_and_the_kit_work_together(self):
        self.with_kit("ks_a")
        state = self.state()
        state[tune.TYRE_KEY] = ["stock:x|y"]
        with mock.patch.object(tune, "garage_plan", return_value={"garage": True}) as plan, \
                mock.patch.object(tune, "write_garage", return_value=["note: garage"]) as write:
            res = self.apply(state)
        self.assertEqual(res["notes"][-1], "note: garage")
        self.assertEqual(res["notes"][1][:25], "note: turbo kit: donor ks")
        self.assertEqual((plan.call_count, write.call_count), (1, 1))
        self.assertEqual(write.call_args[0][0], os.path.join(self.work, "ks_x", "kit", "ks_a"))


class TestApplyWithoutAKit(Apply):
    def snapshot(self, res):
        return {"result": {k: v for k, v in res.items()}, "tree": sha_tree(res["build_dir"]), "calls": list(self.calls)}

    def test_a_car_without_the_key_never_touches_a_kit(self):
        self.patch(tune, "kit_root", lambda *a: self.fail("kit_root"))
        self.patch(tune, "kit_notes", lambda *a: self.fail("kit_notes"))
        res = self.apply({"limiter": 8000, "name_suffix": "_Z"})
        self.assertEqual((res["notes"], [a["id"] for a in res["applied"]]), (["note: from build"], ["name_suffix", "limiter"]))
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "kit")))
        self.assertEqual([t for t in self.tree(res) if "kit_turbo" in t], [])
        self.assertEqual(self.built(res, "data/engine.carengine"), self.read(self.base_file("ks_x", "data/engine.carengine")) | {"limiter": 8000.0})
        self.assertEqual(self.calls, ["build", "pack"])

    def test_the_plan_has_no_kit_without_the_key(self):
        plan = tune.apply_plan(self.work, "ks_x", "ax_x", False, None, self.cat)
        self.assertIsNone(plan["kit"])
        self.assertEqual(plan["root"], tune.base_dir(self.work, "ks_x"))
        self.with_kit("ks_a")
        plan = tune.apply_plan(self.work, "ks_x", "ax_x", False, None, self.cat)
        self.assertEqual(plan["root"], tune.kit_path(self.work, "ks_x", "ks_a"))
        self.assertEqual(plan["kit"]["donor"], "ks_a")

    def test_unticking_the_kit_builds_like_a_car_that_never_had_one(self):
        first = self.apply({"limiter": 8000, "name_suffix": "_Z"})
        before = self.snapshot(first)
        self.assertEqual(before["calls"], ["build", "pack"])
        self.calls.clear()
        with_kit = self.apply({"limiter": 8000, "name_suffix": "_Z", KEY: {"donor": "ks_b"}})
        self.assertIn("content/cars/ax_x/data/kit_turbo_1.turbo", self.packed[-1])
        self.assertIn("kit_turbo_0.turbo", "".join(self.tree(with_kit)))
        self.assertEqual(len(self.built(with_kit, "data/engine.carengine")["turbos_to_load"]), 2)
        self.calls.clear()
        tune.reset_turbo(self.work, "ks_x")
        again = self.apply()
        self.assertEqual(self.snapshot(again), dict(before, calls=["build", "pack"]))
        self.assertEqual([t for t in self.tree(again) if "kit_turbo" in t], [])
        self.assertNotIn("turbos", self.built(again, "data/engine.carengine"))
        self.assertEqual(self.built(again, "data/engine.carengine").get("turbos_to_load"), None)
        self.assertEqual(self.built(again, "data/ax_x.car"), self.built(first, "data/ax_x.car"))

    def test_a_turbo_setting_without_a_kit_is_refused_at_apply_as_before(self):
        self.write(tune.state_path(self.work, "ks_x"), {"turbo_boost_1": 1.1})
        with self.assertRaisesRegex(ValueError, r"^cannot apply the changed setting\(s\), not applicable to ks_x: turbo_boost_1 \(@engine turbos\[0\]\.max_boost"):
            self.apply()
        self.assertEqual(self.calls, [])

    def test_a_turbo_car_applies_with_its_own_turbo_and_no_kit(self):
        tune.save_state(self.work, "ks_a", {"turbo_boost_1": 0.9})
        res = tune.apply(self.work, "ks_a", catalogue=self.cat, game=self.game, install=False)
        self.assertEqual(res["new_id"], "ax_a")
        self.assertEqual(self.read(self.car_file(res["build_dir"], "ax_a", "data/engine.carengine"))["turbos"][0]["max_boost"], 0.9)
        self.assertEqual(res["notes"], ["note: from build"])
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_a", "kit")))


def engine_schema():
    turbo = desc_message("TurboData", [desc_field("max_boost", 1, 2)])
    engine = desc_message("EngineData", [desc_field("limiter", 1, 5), desc_field("turbos_to_load", 2, 9, 3),
                                         desc_field("turbos", 3, 11, 3, ".TurboData"), desc_field("max_turbo_boost", 4, 2),
                                         desc_field("boost_levels", 5, 2, 3), desc_field("bov_ratio", 6, 2), desc_field("name", 7, 9)])
    return desc_set(desc_file("e.proto", messages=[turbo, engine]))


class TestWireBookkeeping(unittest.TestCase):
    """The copied fields keep the decoded message encodable: checked with car_json.encode_msg on a small schema."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tmp()
        base = cls._tmp.__enter__()
        (base / "e.desc").write_bytes(engine_schema())
        cls.sch = car_json.load_schema(base / "e.desc")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.__exit__(None, None, None)

    def decode(self, wire):
        return car_json.decode_msg(self.sch, "EngineData", wire)

    def encode(self, obj):
        return car_json.encode_msg(self.sch, "EngineData", obj)

    def donor(self, turbos=2, levels=3):
        return self.decode(pb_int(1, 8800) + b"".join(pb_str(2, "d%d" % i) for i in range(turbos))
                           + b"".join(pb_msg(3, pb_f32(1, 1.0 + i / 5)) for i in range(turbos)) + pb_f32(4, 1.2)
                           + pb_bytes(5, struct.pack("<%df" % levels, *[0.1 * (i + 1) for i in range(levels)])) + pb_f32(6, 0.5))

    def na(self, wire_order=True):
        """A car's engine: the name before the limiter (a wire order that is not ascending, so decode gives _order), or ascending."""
        return self.decode(pb_str(7, "na") + pb_int(1, 7000) if wire_order else pb_int(1, 7000) + pb_str(7, "na"))

    def test_the_synthetic_decode_has_the_bookkeeping_the_tests_rely_on(self):
        self.assertEqual(self.na()["_order"], ["name", "limiter"])
        self.assertNotIn("_order", self.na(False))
        donor = self.donor()
        self.assertEqual((donor["_packed"], "_order" in donor), (["boost_levels"], False))

    def test_fields_added_to_a_message_with_a_wire_order_are_encodable(self):
        engine = self.na()
        names = tune.copy_turbo_fields(engine, self.donor(), ["new_a", "new_b"])
        self.assertEqual(names, ["turbos_to_load", "turbos", "max_turbo_boost", "boost_levels", "bov_ratio"])
        self.assertEqual(engine["_order"], ["name", "limiter", "turbos_to_load", "turbos_to_load", "turbos", "turbos", "max_turbo_boost", "boost_levels",
                                            "bov_ratio"])
        assert_order_valid(self, engine)
        self.assertEqual(engine["_packed"], ["boost_levels"])
        back = self.decode(self.encode(engine))
        self.assertEqual((back["name"], back["limiter"], back["turbos_to_load"], len(back["turbos"]), back["_packed"]),
                         ("na", 7000, ["new_a", "new_b"], 2, ["boost_levels"]))
        self.assertAlmostEqual(back["max_turbo_boost"], 1.2, places=6)
        self.assertEqual(len(back["boost_levels"]), 3)

    def test_the_same_in_a_message_without_a_wire_order(self):
        engine = self.na(False)
        tune.copy_turbo_fields(engine, self.donor(), ["new_a", "new_b"])
        self.assertNotIn("_order", engine)
        back = self.decode(self.encode(engine))
        self.assertEqual((back["limiter"], back["turbos_to_load"], len(back["turbos"])), (7000, ["new_a", "new_b"], 2))

    def test_a_longer_or_shorter_list_than_the_one_in_the_message_follows_its_order_names(self):
        for have, want in ((3, 2), (1, 2), (0, 2), (2, 1), (2, 2)):
            with self.subTest(have=have, want=want):
                engine = self.decode(pb_str(7, "na") + pb_int(1, 7000) + b"".join(pb_str(2, "o%d" % i) for i in range(have)))
                self.assertEqual(engine["_order"], ["name", "limiter"] + ["turbos_to_load"] * have)
                tune.copy_turbo_fields(engine, self.donor(want), ["n%d" % i for i in range(want)])
                assert_order_valid(self, engine)
                self.assertEqual(self.decode(self.encode(engine))["turbos_to_load"], ["n%d" % i for i in range(want)])

    def test_a_field_the_car_has_and_the_donor_does_not_is_left_alone(self):
        engine = self.decode(pb_int(1, 7000) + pb_f32(6, 0.25) + pb_f32(4, 0.1))
        donor = self.decode(pb_int(1, 8800) + pb_f32(4, 1.2))
        self.assertEqual(tune.copy_turbo_fields(engine, donor, []), ["max_turbo_boost"])
        self.assertEqual((engine["limiter"], tune.plain(engine["bov_ratio"])), (7000, 0.25))
        self.assertAlmostEqual(engine["max_turbo_boost"], 1.2, places=6)

    def test_a_packed_list_of_the_donor_replaces_an_unpacked_one_of_the_car(self):
        engine = self.decode(pb_int(1, 7000) + pb_f32(5, 0.5) + pb_f32(5, 0.6))
        self.assertEqual((len(engine["boost_levels"]), "_packed" in engine), (2, False))
        tune.copy_turbo_fields(engine, self.donor(), [])
        self.assertEqual(engine["_packed"], ["boost_levels"])
        self.assertEqual(len(self.decode(self.encode(engine))["boost_levels"]), 3)

    def test_an_unpacked_list_of_the_donor_replaces_a_packed_one_of_the_car(self):
        engine = self.decode(pb_int(1, 7000) + pb_bytes(5, struct.pack("<2f", 0.5, 0.6)))
        self.assertEqual(engine["_packed"], ["boost_levels"])
        donor = self.decode(pb_f32(5, 0.1) + pb_f32(5, 0.2) + pb_f32(5, 0.3))
        self.assertNotIn("_packed", donor)
        tune.copy_turbo_fields(engine, donor, [])
        self.assertNotIn("_packed", engine)
        self.assertEqual(len(self.decode(self.encode(engine))["boost_levels"]), 3)

    def test_the_names_of_the_fields_decide_and_reserved_keys_never_copy(self):
        src = {"Turbo_A": 1, "x_BOOST": 2, "bOv": 3, "turbine": 4, "limiter": 5, "_order": ["turbo_x"], "_packed": ["turbo_x"],
               "_unknown": [[9, 0, 1]], "nested": {"turbo": 1}, "turbos_to_load": ["a"]}
        dst = {}
        self.assertEqual(tune.copy_turbo_fields(dst, src, ["z"]), ["Turbo_A", "x_BOOST", "bOv", "turbos_to_load"])
        self.assertEqual(dst, {"Turbo_A": 1, "x_BOOST": 2, "bOv": 3, "turbos_to_load": ["z"]})

    def test_the_listing_is_a_copy(self):
        listing = ["x"]
        dst = {}
        tune.copy_turbo_fields(dst, {"turbos_to_load": ["a"]}, listing)
        dst["turbos_to_load"].append("y")
        self.assertEqual(listing, ["x"])


class TestCommand(World):
    def test_the_usage_and_the_dispatch_name_the_command_after_turbo_remove(self):
        self.assertIn("python tools/tune.py turbo-kit    [--tune ID | --draft] [--car ID] [--work <dir>]", USAGE)
        names = list(tune.COMMANDS)
        self.assertEqual(names[names.index("turbo-remove") + 1], "turbo-kit")
        self.assertEqual(tune.COMMANDS["turbo-kit"].__name__, "cmd_turbo_kit")

    def test_turbo_kit_builds_the_kit_and_prints_what_it_holds(self):
        tune.set_turbo(self.work, "ks_x", "ks_a")
        code, out, err = self.run_main("turbo-kit")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, "kit root: %s\ndonor: ks_a (single turbo)\nfiles: content/cars/ks_x/data/kit_turbo_0.turbo\n"
                              "engine fields: turbos_to_load, turbos, max_turbo_boost, bov_noise\n.car fields: turbos_to_load, turbos, max_turbo_boost\n"
                         % tune.kit_path(self.work, "ks_x", "ks_a"))
        self.assertTrue(os.path.isfile(os.path.join(tune.kit_path(self.work, "ks_x", "ks_a"), "kit.json")))
        self.assertEqual(self.builds, [("ks_x", "ks_a")])
        self.assertEqual(self.run_main("turbo-kit")[1], out)
        self.assertEqual(len(self.builds), 1)

    def test_turbo_kit_for_a_twin_donor_and_a_car_without_an_inline_block(self):
        tune.set_turbo(self.work, "ks_n", "ks_b")
        code, out, err = self.run_main("turbo-kit", "--car", "ks_n")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.splitlines()[1:], ["donor: ks_b (twin turbo)",
                                                "files: content/cars/ks_n/data/kit_turbo_0.turbo, content/cars/ks_n/data/kit_turbo_1.turbo",
                                                "engine fields: turbos_to_load, turbos, max_turbo_boost, bov_noise", ".car fields: none"])

    def test_turbo_kit_on_the_draft_and_on_a_tune(self):
        tune.set_turbo(self.work, "ks_x", "ks_s", tune.DRAFT)
        tune.save_state(self.work, "ks_x", {"name_suffix": "_B", KEY: {"donor": "ks_b"}}, "ax01")
        code, out, err = self.run_main("turbo-kit", "--draft", "--car", "ks_x")
        self.assertEqual((code, err, out.splitlines()[1]), (0, "", "donor: ks_s (single turbo)"))
        self.assertEqual(self.run_main("turbo-kit", "--tune", "ax01")[1].splitlines()[1], "donor: ks_b (twin turbo)")
        self.assertEqual(self.run_main("turbo-kit", "--tune", "ax_x")[0::2], (1, "error: no turbo kit chosen for ax_x, turbo-add chooses one\n"))

    def test_turbo_kit_without_a_choice_or_with_a_wrong_tune_is_an_error(self):
        self.assertEqual(self.run_main("turbo-kit"), (1, "", "error: no turbo kit chosen for ax_x, turbo-add chooses one\n"))
        tune.save_state(self.work, "ks_x", {}, "ax01")
        self.assertEqual(self.run_main("turbo-kit", "--tune", "ax01"), (1, "", "error: no turbo kit chosen for ax01, turbo-add chooses one\n"))
        self.assertEqual(self.run_main("turbo-kit", "--tune", "ax02"), (1, "", "error: ks_x has no tune ax02\n"))
        self.assertEqual(self.run_main("turbo-kit", "--draft"), (1, "", "error: no turbo kit chosen for draft, turbo-add chooses one\n"))
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "kit")))

    def test_turbo_kit_reports_a_kit_that_cannot_be_built(self):
        tune.save_state(self.work, "ks_x", {KEY: {"donor": "ks_gone"}})
        self.assertEqual(self.run_main("turbo-kit"), (1, "", "error: turbo kit: ks_gone is not an installed car with a turbo\n"))
        tune.save_state(self.work, "ks_x", {KEY: 5})
        self.assertEqual(self.run_main("turbo-kit"), (1, "", "error: damaged turbo kit in the saved state\n"))

    def test_wrong_arguments_print_the_usage_and_exit_2(self):
        for argv in (["turbo-kit", "ks_a"], ["turbo-kit", "--tune", "ax01", "--draft"], ["turbo-kit", "--car"], ["turbo-kit", "--nope"]):
            with self.subTest(argv):
                code, out, err = self.run_main(*argv)
                self.assertEqual((code, out.strip(), err), (2, USAGE.strip(), ""))
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "kit")))

    def test_the_command_is_documented_in_the_module_docstring(self):
        doc = tune.__doc__
        self.assertIn("Kit root (library functions kit_root, root_for)", doc)
        self.assertIn("turbo-kit:    builds or refreshes the kit root", doc)


class TestCliProcess(unittest.TestCase):
    def test_the_usage_on_stdout_names_the_command(self):
        with tmp() as d:
            r = run_tool("tune.py", cwd=d)
        self.assertEqual((r.returncode, r.stderr), (2, ""))
        self.assertIn("python tools/tune.py turbo-kit    [--tune ID | --draft] [--car ID] [--work <dir>]", r.stdout)

    def test_the_wrong_arguments_exit_2_with_the_usage(self):
        with tmp() as d:
            for argv in (["turbo-kit", "x"], ["turbo-kit", "--tune", "ax01", "--draft"]):
                r = run_tool("tune.py", *argv, cwd=d)
                self.assertEqual((r.returncode, r.stdout.strip(), r.stderr), (2, USAGE.strip(), ""))

    def test_a_work_folder_without_cars_has_no_kit_to_show(self):
        with tmp() as d:
            r = run_tool("tune.py", "turbo-kit", "--work", d / "w", "--car", "ks_bmw_m3_e46_csl", cwd=d)
            self.assertEqual((r.returncode, r.stdout), (1, ""))
            self.assertEqual(r.stderr, "error: no turbo kit chosen for ax_bmw_m3_e46_csl, turbo-add chooses one\n")
            self.assertFalse(os.path.exists(d / "w" / "ks_bmw_m3_e46_csl" / "kit"))


if __name__ == "__main__":
    unittest.main()
