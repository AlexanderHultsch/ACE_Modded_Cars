"""Tests for tuner/catalogue.json, tuner/cars.json and docs/settings/*.md as data: the format tools/tune.py reads, the loaders' validation, the generated reference docs, counts quoted in the docs."""
import collections
import json
import re
import unittest

from support import ROOT, FakeCar, mini_catalogue, mini_setting, tmp

import clone_car
import tune

CARS = ROOT / "tuner" / "cars.json"
DOCS = ROOT / "docs" / "settings"
KNOWN_KEYS = set(tune.REQUIRED) | {"min", "max", "default", "default_template", "choices", "choice_values", "targets",
                                   "needs", "curve_from", "handler", "hide_if_absent", "create_missing", "ui", "value"}
ROLE_NAMES = set(tune.MANIFEST_ROLES) | set(tune.TYRE_ROLES) | {"car", "mech_preset", "turbo"}
TEMPLATE_FIELDS = {"stock_display_name", "stock_variant_name"}
COMMON = "content\\cars\\common_phsx\\"
GROUP_ORDER = ["Meta", "Display", "Engine", "Turbo", "Gearbox & clutch", "Differential", "Differential (hardware)", "Steering",
               "Brakes", "Vehicle (hardware)", "Springs & anti-roll", "Ride height & bump stops", "Dampers", "Suspension (physical)",
               "Alignment & tyres", "Tyres", "Fuel", "Electronics"]
MOVED = {"clutch_max_torque": "Gearbox & clutch", "steer_ratio": "Steering", "steer_ratio_min": "Steering",
         "steer_ratio_max": "Steering", "steer_rod_ratio": "Steering", "steer_lock_deg": "Steering",
         "caster_front": "Alignment & tyres", "brake_bias": "Brakes", "brake_bias_min": "Brakes", "brake_bias_max": "Brakes",
         "brake_bias_hw": "Brakes", "brake_torque": "Brakes", "handbrake_torque": "Brakes"}
CAT = tune.load_catalogue()
SETTINGS = CAT["settings"]
BY_ID = {s["id"]: s for s in SETTINGS}
BY_GROUP = {g["name"]: g for g in CAT["groups"]}
CARS_DATA = tune.load_cars()


def paths_of(s):
    """(file, path) of every target, need and curve source of a setting."""
    return [(t["file"], t["path"]) for t in s.get("targets", []) + s.get("needs", []) + ([s["curve_from"]] if "curve_from" in s else [])]


def role_name(file):
    return re.match(r"@([a-z_0-9]+)", file).group(1)


def sample(s):
    return {"int": 1, "float": 1.5, "bool": "yes", "string": "_X", "enum": (s.get("choices") or ["x"])[0]}[s["type"]]


def write_json(d, name, data):
    path = d / name
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return str(path)


class TestCatalogueData(unittest.TestCase):
    def test_loads_through_tune(self):
        self.assertGreater(len(SETTINGS), 100)
        self.assertIsInstance(CAT["car_id"], str)

    def test_ids_unique_and_well_formed(self):
        ids = [s["id"] for s in SETTINGS]
        self.assertEqual([i for i, n in collections.Counter(ids).items() if n > 1], [])
        self.assertEqual([i for i in ids if not re.fullmatch(r"[a-z][a-z0-9_]*", i)], [])

    def test_labels_unique_and_not_empty(self):
        labels = [s["label"] for s in SETTINGS]
        self.assertEqual([x for x, n in collections.Counter(labels).items() if n > 1], [])
        self.assertEqual([s["id"] for s in SETTINGS if not s["label"].strip() or not s["description"].strip()], [])

    def test_required_keys_and_their_types(self):
        for s in SETTINGS:
            with self.subTest(s["id"]):
                for key in tune.REQUIRED:
                    self.assertIn(key, s)
                for key in ("id", "group", "label", "unit", "description", "kind", "type"):
                    self.assertIsInstance(s[key], str)
                self.assertIs(type(s["verified"]), bool)

    def test_only_keys_the_code_knows(self):
        for s in SETTINGS:
            with self.subTest(s["id"]):
                self.assertLessEqual(set(s), KNOWN_KEYS)
                for t in s.get("targets", []) + s.get("needs", []):
                    self.assertLessEqual(set(t), {"file", "path", "optional"})
                self.assertLessEqual(set(s.get("curve_from", {})), {"file", "path"})

    def test_kinds_and_types_are_the_set_tune_handles(self):
        self.assertEqual({s["kind"] for s in SETTINGS}, set(tune.KINDS))
        self.assertEqual({s["type"] for s in SETTINGS}, set(tune.VALUE_TYPES))

    def test_kind_decides_type_and_keys(self):
        for s in SETTINGS:
            with self.subTest(s["id"]):
                if s["kind"] == "flag":
                    self.assertEqual(s["type"], "bool")
                    self.assertIn(type(s["value"]), (int, float))
                    self.assertTrue(s["targets"])
                    self.assertNotIn("default", s)
                elif s["kind"] == "meta":
                    self.assertEqual(s["type"], "string")
                    self.assertEqual(s["targets"], [])
                elif s["kind"] == "curve_scale":
                    self.assertEqual(s["type"], "float")
                    self.assertEqual(s["targets"], [])
                    self.assertIn("default", s)
                    self.assertTrue({"file", "path"} <= set(s["curve_from"]))
                else:
                    self.assertIn(s["type"], ("int", "float", "enum"))
                    self.assertTrue(s["targets"])
                    self.assertNotIn("default", s)

    def test_coerce_takes_a_sample_of_every_setting(self):
        types = {"int": int, "float": float, "bool": bool, "string": str, "enum": str}
        for s in SETTINGS:
            with self.subTest(s["id"]):
                self.assertIs(type(tune.coerce(s, sample(s))), types[s["type"]])

    def test_coerce_rejects_a_wrong_sample_of_every_setting(self):
        wrong = {"int": "1.5", "float": "abc", "bool": "maybe", "string": "", "enum": "no such choice"}
        for s in SETTINGS:
            with self.subTest(s["id"]):
                with self.assertRaises(ValueError) as cm:
                    tune.coerce(s, wrong[s["type"]])
                self.assertIn(s["id"], str(cm.exception))

    def test_handlers_are_the_two_tune_knows(self):
        handlers = [s["handler"] for s in SETTINGS if "handler" in s]
        self.assertEqual(sorted(handlers), sorted(tune.HANDLERS))
        self.assertTrue(all(s["kind"] == "meta" for s in SETTINGS if "handler" in s))

    def test_file_roles_match_the_role_pattern_and_name_a_known_role(self):
        for s in SETTINGS:
            with self.subTest(s["id"]):
                for file, _ in paths_of(s):
                    if file.startswith("@"):
                        self.assertRegex(file, tune.ROLE.pattern + "$")
                        self.assertIn(role_name(file), ROLE_NAMES)

    def test_the_catalogue_uses_roles_only_through_known_names(self):
        used = {role_name(f) for s in SETTINGS for f, _ in paths_of(s) if f.startswith("@")}
        self.assertLessEqual(used, ROLE_NAMES)
        self.assertTrue(used)

    def test_front_rear_role_agrees_with_the_id(self):
        for s in SETTINGS:
            with self.subTest(s["id"]):
                for file, _ in paths_of(s):
                    if file.endswith("_front"):
                        self.assertRegex(s["id"], r"_front($|_)")
                    if file.endswith("_rear"):
                        self.assertRegex(s["id"], r"_rear($|_)")

    def test_tyre_roles_only_in_value_targets(self):
        for s in SETTINGS:
            roles = [t["file"] for t in s.get("needs", [])] + [s.get("curve_from", {}).get("file", "")]
            self.assertFalse([r for r in roles if r.startswith("@tyre_")], s["id"])
            if s["kind"] != "value":
                self.assertFalse([t for t in s["targets"] if t["file"][1:] in tune.TYRE_ROLES], s["id"])

    def test_all_paths_parse(self):
        for s in SETTINGS:
            for file, path in paths_of(s):
                with self.subTest("%s %s" % (s["id"], path)):
                    moves = tune.parse_path(path)
                    self.assertEqual(moves[0][0], "key")

    def test_wildcard_only_where_expanded(self):
        starred = []
        for s in SETTINGS:
            if "curve_from" in s:
                self.assertNotIn("[*]", s["curve_from"]["path"], s["id"])
            for t in s["targets"]:
                if "[*]" in t["path"]:
                    starred.append(s["id"])
        self.assertEqual(set(starred), {"driver_aids_off"})

    def test_selector_values_are_text_the_matcher_can_compare(self):
        found = [(s["id"], m) for s in SETTINGS for _, p in paths_of(s) for m in tune.parse_path(p) if m[0] == "find"]
        self.assertTrue(found)
        for sid, m in found:
            self.assertRegex(m[1], r"^[A-Za-z_][A-Za-z0-9_]*$", sid)
            self.assertTrue(m[2], sid)

    def test_min_max_pairs_are_ordered_numbers(self):
        for s in SETTINGS:
            with self.subTest(s["id"]):
                self.assertEqual("min" in s, "max" in s)
                if "min" in s:
                    self.assertIn(s["type"], ("int", "float"))
                    for k in ("min", "max"):
                        self.assertIn(type(s[k]), (int, float))
                    self.assertLess(s["min"], s["max"])
                    if s["type"] == "int":
                        self.assertEqual((s["min"], s["max"]), (int(s["min"]), int(s["max"])))

    def test_numeric_value_settings_have_a_range(self):
        self.assertEqual([s["id"] for s in SETTINGS if s["kind"] == "value" and s["type"] in ("int", "float")
                          and "min" not in s], [])

    def test_catalogue_default_lies_inside_its_range(self):
        for s in SETTINGS:
            if "default" in s and "min" in s:
                with self.subTest(s["id"]):
                    self.assertLessEqual(s["min"], s["default"])
                    self.assertLessEqual(s["default"], s["max"])

    def test_meta_defaults(self):
        for s in SETTINGS:
            if s["kind"] == "meta":
                with self.subTest(s["id"]):
                    self.assertEqual(("default" in s) + ("default_template" in s), 1)
                    self.assertIsInstance(s.get("default", s.get("default_template")), str)

    def test_default_template_only_on_variant_name_with_known_placeholders(self):
        with_template = [s for s in SETTINGS if "default_template" in s]
        self.assertEqual([s["handler"] for s in with_template], ["variant_name"])
        for s in with_template:
            self.assertLessEqual(set(re.findall(r"\{([a-z_]+)\}", s["default_template"])), TEMPLATE_FIELDS)

    def test_name_suffix_default_passes_its_own_validation(self):
        s = BY_ID["name_suffix"]
        self.assertEqual(tune.coerce(s, s["default"]), s["default"])

    def test_optional_is_a_bool_on_targets_only(self):
        for s in SETTINGS:
            with self.subTest(s["id"]):
                self.assertNotIn("optional", s)
                self.assertNotIn("optional", s.get("curve_from", {}))
                for t in s.get("targets", []) + s.get("needs", []):
                    self.assertIs(type(t.get("optional", False)), bool)

    def test_needs_only_on_value_settings_and_never_optional(self):
        for s in SETTINGS:
            if "needs" in s:
                self.assertEqual(s["kind"], "value", s["id"])
                self.assertFalse([t for t in s["needs"] if t.get("optional")], s["id"])

    def test_create_missing_only_on_value_settings_with_a_nested_path(self):
        flagged = [s for s in SETTINGS if "create_missing" in s]
        self.assertTrue(flagged)
        for s in flagged:
            with self.subTest(s["id"]):
                self.assertIs(s["create_missing"], True)
                self.assertEqual(s["kind"], "value")
                self.assertTrue(any(len(tune.parse_path(t["path"])) > 1 for t in s["targets"] if not t.get("optional")))

    def test_hide_if_absent_only_on_value_settings_with_a_required_target(self):
        flagged = [s for s in SETTINGS if "hide_if_absent" in s]
        self.assertTrue(flagged)
        for s in flagged:
            with self.subTest(s["id"]):
                self.assertIs(s["hide_if_absent"], True)
                self.assertEqual(s["kind"], "value")
                self.assertTrue([t for t in s["targets"] if not t.get("optional")])

    def test_choices_only_on_enums_and_unique(self):
        for s in SETTINGS:
            with self.subTest(s["id"]):
                if s["type"] == "enum":
                    self.assertTrue(s["choices"])
                    self.assertEqual(len(set(s["choices"])), len(s["choices"]))
                    self.assertTrue(all(isinstance(c, str) and c for c in s["choices"]))
                else:
                    self.assertNotIn("choices", s)

    def test_choice_values_map_every_choice_to_a_shared_game_path(self):
        with_values = [s for s in SETTINGS if "choice_values" in s]
        self.assertTrue(with_values)
        for s in with_values:
            with self.subTest(s["id"]):
                self.assertEqual(s["type"], "enum")
                self.assertEqual(set(s["choice_values"]), set(s["choices"]))
                self.assertTrue(all(v.startswith(COMMON) for v in s["choice_values"].values()))
                self.assertEqual(len({tune.game_path_key(v) for v in s["choice_values"].values()}), len(s["choices"]))
                self.assertTrue(all(t["file"] in ("@tyre_front", "@tyre_rear") for t in s["targets"]))

    def test_thermal_curve_choices_are_the_same_front_and_rear(self):
        front, rear = BY_ID["tyre_thermal_curve_front"], BY_ID["tyre_thermal_curve_rear"]
        self.assertEqual(front["choices"], rear["choices"])
        self.assertEqual(front["choice_values"], rear["choice_values"])

    def test_only_the_regrouped_groups_are_split_in_the_file(self):
        runs = [s["group"] for i, s in enumerate(SETTINGS) if i == 0 or s["group"] != SETTINGS[i - 1]["group"]]
        self.assertEqual({g for g, n in collections.Counter(runs).items() if n > 1},
                         {"Gearbox & clutch", "Steering", "Brakes", "Alignment & tyres"})

    def test_the_group_list_is_the_decided_order(self):
        self.assertEqual([g["name"] for g in CAT["groups"]], GROUP_ORDER)
        self.assertEqual([g["name"] for g in tune.group_list()], GROUP_ORDER)

    def test_every_group_has_a_one_line_description_and_nothing_else(self):
        for g in CAT["groups"]:
            with self.subTest(g["name"]):
                self.assertEqual(set(g), {"name", "description"})
                self.assertTrue(0 < len(g["description"]) <= tune.GROUP_DESCRIPTION_MAX)
                self.assertEqual(g["description"], g["description"].strip())
                self.assertNotRegex(g["description"], r"[\x00-\x1f\x7f]")

    def test_every_setting_group_is_listed_and_every_listed_group_is_used(self):
        self.assertEqual({s["group"] for s in SETTINGS}, set(GROUP_ORDER))
        self.assertEqual([s["id"] for s in SETTINGS if s["group"] not in GROUP_ORDER], [])

    def test_the_regrouped_settings_are_in_their_new_groups(self):
        self.assertEqual({sid: BY_ID[sid]["group"] for sid in MOVED}, MOVED)

    def test_the_old_group_names_are_gone(self):
        self.assertFalse({"Gearing", "Steering & brakes (setup)", "Brakes & steering (hardware)"} & {s["group"] for s in SETTINGS})

    def test_the_group_sizes_after_the_regrouping(self):
        self.assertEqual(collections.Counter(s["group"] for s in SETTINGS),
                         {"Meta": 2, "Display": 2, "Engine": 10, "Turbo": 3, "Gearbox & clutch": 14, "Differential": 6,
                          "Differential (hardware)": 6, "Steering": 5, "Brakes": 6, "Vehicle (hardware)": 1,
                          "Springs & anti-roll": 12, "Ride height & bump stops": 12, "Dampers": 8, "Suspension (physical)": 12,
                          "Alignment & tyres": 15, "Tyres": 24, "Fuel": 1, "Electronics": 4})

    def test_ui_hint_is_header(self):
        self.assertEqual({s["ui"] for s in SETTINGS if "ui" in s}, {"header"})

    def test_no_target_listed_twice_in_a_setting(self):
        for s in SETTINGS:
            pairs = [(t["file"], t["path"]) for t in s.get("targets", [])]
            self.assertEqual(len(pairs), len(set(pairs)), s["id"])

    def test_flag_targets_are_all_optional(self):
        self.assertTrue(all(t.get("optional") for s in SETTINGS if s["kind"] == "flag" for t in s["targets"]))

    def test_the_kunos_documentation_facts_are_in_the_descriptions(self):
        text = BY_ID["max_turbo_boost"]["description"]
        self.assertIn("no physical effect", text)
        self.assertNotIn("seems to be the real cap", text)
        for sid in ("limiter_cycles", "gear_up_time", "steer_lock_deg", "tc_level"):
            with self.subTest(sid):
                self.assertIn("Kunos documentation:", BY_ID[sid]["description"])


class TestLoaderValidation(unittest.TestCase):
    def load(self, *settings, **top):
        with tmp() as d:
            data = mini_catalogue(*settings)
            data.update(top)
            return tune.load_catalogue(write_json(d, "c.json", data))

    def test_a_minimal_catalogue_loads(self):
        cat = self.load(mini_setting("a", targets=[("@engine", "limiter")]))
        self.assertEqual([s["id"] for s in cat["settings"]], ["a"])

    def test_every_role_form_is_accepted(self):
        roles = ["@car", "@mech_preset", "@turbo[0]", "@turbo[12]"] + ["@" + r for r in list(tune.MANIFEST_ROLES) + list(tune.TYRE_ROLES)]
        self.load(*[mini_setting("s%d" % i, targets=[(r, "a.b")]) for i, r in enumerate(roles)])

    def test_invalid_catalogues_are_refused_with_the_setting_named(self):
        good = lambda **kw: mini_setting("bad", targets=[("@engine", "limiter")], **kw)  # noqa: E731
        cases = [
            ("duplicate id", [good(), good()], "duplicate setting id 'bad'"),
            ("missing key", [{k: v for k, v in good().items() if k != "unit"}], "misses unit"),
            ("unknown kind", [good(kind="weird")], "unknown kind or type"),
            ("unknown type", [good(type="complex")], "unknown kind or type"),
            ("flag with a float type", [mini_setting("bad", kind="flag", type="float", targets=[("@car", "a")], value=0)],
             "flag and type bool"),
            ("bool value setting", [good(type="bool")], "flag and type bool"),
            ("value without targets", [mini_setting("bad", targets=[])], "needs targets"),
            ("target without a path", [dict(good(), targets=[{"file": "@car"}])], "needs targets"),
            ("flag without a value", [mini_setting("bad", kind="flag", type="bool", targets=[("@car", "a")])], "numeric value"),
            ("flag with a bool value", [mini_setting("bad", kind="flag", type="bool", targets=[("@car", "a")], value=True)],
             "numeric value"),
            ("create_missing text", [good(create_missing="yes")], "create_missing"),
            ("hide_if_absent text", [good(hide_if_absent=1)], "hide_if_absent"),
            ("optional text", [dict(good(), targets=[{"file": "@car", "path": "a", "optional": "yes"}])], "optional"),
            ("unknown role", [dict(good(), targets=[{"file": "@bogus", "path": "a"}])], "unknown file role '@bogus'"),
            ("role with a text index", [dict(good(), targets=[{"file": "@turbo[x]", "path": "a"}])], "unknown file role"),
            ("unknown role in needs", [good(needs=[{"file": "@bogus", "path": "a"}])], "unknown file role"),
            ("needs not a list", [good(needs={"file": "@car", "path": "a"})], "needs"),
            ("needs entry without a path", [good(needs=[{"file": "@car"}])], "needs"),
            ("choice_values on a float", [good(choice_values={"a": "x"})], "choice_values"),
            ("choice_values keys differ", [good(type="enum", choices=["a", "b"], choice_values={"a": "x"})], "choice_values"),
            ("choice_values empty text", [good(type="enum", choices=["a"], choice_values={"a": ""})], "choice_values"),
            ("curve_scale without default", [mini_setting("bad", kind="curve_scale", curve_from={"file": "@engine", "path": "p"})],
             "default and curve_from"),
            ("curve_scale without curve path", [mini_setting("bad", kind="curve_scale", default=1.0, curve_from={"file": "@engine"})],
             "default and curve_from"),
            ("curve_scale with unknown role", [mini_setting("bad", kind="curve_scale", default=1.0,
                                                           curve_from={"file": "@bogus", "path": "p"})], "unknown file role"),
            ("meta without a handler", [mini_setting("bad", kind="meta", type="string", default="x")], "handler"),
            ("meta with an unknown handler", [mini_setting("bad", kind="meta", type="string", default="x", handler="other")],
             "handler"),
            ("meta without a default", [mini_setting("bad", kind="meta", type="string", handler="name_suffix")], "default"),
        ]
        for name, settings, message in cases:
            with self.subTest(name):
                with self.assertRaisesRegex(ValueError, message):
                    self.load(*settings)

    def test_settings_must_be_a_list(self):
        with self.assertRaisesRegex(ValueError, "needs settings"):
            self.load(settings={"a": 1})

    def test_car_id_is_not_required(self):
        with tmp() as d:
            data = mini_catalogue(mini_setting("a", targets=[("@engine", "limiter")]))
            del data["car_id"]
            tune.load_catalogue(write_json(d, "c.json", data))


MISSING = object()


class TestGroupsValidation(unittest.TestCase):
    def load(self, groups, *settings):
        with tmp() as d:
            data = mini_catalogue(*(settings or (mini_setting("a", targets=[("@engine", "limiter")]),)))
            if groups is MISSING:
                del data["groups"]
            else:
                data["groups"] = groups
            return tune.load_catalogue(write_json(d, "c.json", data))

    def test_listed_groups_load_and_keep_their_order(self):
        a, b = mini_setting("a", group="B", targets=[("@engine", "limiter")]), mini_setting("b", group="A", targets=[("@engine", "x")])
        groups = [{"name": "A", "description": "da"}, {"name": "B", "description": "db"}]
        self.assertEqual(self.load(groups, a, b)["groups"], groups)

    def test_a_description_of_exactly_the_limit_is_accepted(self):
        self.load([{"name": "G", "description": "x" * tune.GROUP_DESCRIPTION_MAX}])

    def test_invalid_groups_are_refused(self):
        ok = {"name": "G", "description": "d"}
        cases = [
            ("missing key", MISSING, "needs groups"),
            ("empty list", [], "needs groups"),
            ("not a list", {"G": "d"}, "needs groups"),
            ("entry not an object", ["G"], "every group needs a name and a description"),
            ("name missing", [{"description": "d"}], "every group needs a name and a description"),
            ("name empty", [{"name": "", "description": "d"}], "every group needs a name and a description"),
            ("name not text", [{"name": 1, "description": "d"}], "every group needs a name and a description"),
            ("description missing", [{"name": "G"}], "every group needs a name and a description"),
            ("description empty", [{"name": "G", "description": ""}], "every group needs a name and a description"),
            ("description not text", [{"name": "G", "description": None}], "every group needs a name and a description"),
            ("description too long", [{"name": "G", "description": "x" * (tune.GROUP_DESCRIPTION_MAX + 1)}],
             "every group needs a name and a description"),
            ("newline in the description", [{"name": "G", "description": "a\nb"}], "group 'G' has a tab, a newline"),
            ("tab in the description", [{"name": "G", "description": "a\tb"}], "group 'G' has a tab, a newline"),
            ("control character in the name", [{"name": "G\x01", "description": "d"}], "tab, a newline or another control"),
            ("duplicate name", [ok, dict(ok, description="other")], "duplicate group name 'G'"),
        ]
        for name, groups, message in cases:
            with self.subTest(name):
                with self.assertRaisesRegex(ValueError, message):
                    self.load(groups)

    def test_a_setting_group_that_is_not_listed_is_refused_with_the_setting_named(self):
        with self.assertRaisesRegex(ValueError, "setting 'a' has the group 'G', which is not listed in groups"):
            self.load([{"name": "H", "description": "d"}])

    def test_a_listed_group_that_no_setting_uses_is_refused(self):
        with self.assertRaisesRegex(ValueError, "group 'Unused' is listed in groups but no setting uses it"):
            self.load([{"name": "G", "description": "d"}, {"name": "Unused", "description": "d"}])

    def test_the_error_names_the_catalogue_file(self):
        with tmp() as d:
            data = mini_catalogue(mini_setting("a", targets=[("@engine", "limiter")]))
            del data["groups"]
            path = write_json(d, "c.json", data)
            with self.assertRaises(ValueError) as cm:
                tune.load_catalogue(path)
            self.assertIn(path, str(cm.exception))


class TestGroupList(unittest.TestCase):
    CAT = {"groups": [{"name": "B", "description": "db"}, {"name": "A", "description": "da"}], "settings": []}

    def test_it_returns_the_groups_in_order(self):
        self.assertEqual(tune.group_list(self.CAT), [{"name": "B", "description": "db"}, {"name": "A", "description": "da"}])

    def test_the_result_is_a_copy_the_caller_may_change(self):
        cat = {"groups": [{"name": "B", "description": "db"}], "settings": []}
        first = tune.group_list(cat)
        first[0]["name"] = "changed"
        first.append({"name": "x", "description": "y"})
        self.assertEqual(cat["groups"], [{"name": "B", "description": "db"}])
        self.assertEqual(tune.group_list(cat), [{"name": "B", "description": "db"}])
        self.assertIsNot(tune.group_list(cat)[0], tune.group_list(cat)[0])

    def test_without_an_argument_it_reads_the_catalogue_file(self):
        self.assertEqual(tune.group_list(), CAT["groups"])
        self.assertIsNot(tune.group_list()[0], CAT["groups"][0])


class TestCarsJson(unittest.TestCase):
    def test_default_car_is_in_the_list(self):
        self.assertIn(CARS_DATA["default"], [c["id"] for c in CARS_DATA["cars"]])

    def test_ids_unique_with_labels(self):
        ids = [c["id"] for c in CARS_DATA["cars"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(c["label"].strip() for c in CARS_DATA["cars"]))
        self.assertTrue(all(re.fullmatch(r"[a-z0-9_]+", i) for i in ids))

    def test_new_ids_are_valid_clone_ids_and_do_not_collide(self):
        ids = [c["id"] for c in CARS_DATA["cars"]]
        with tmp() as d:
            for car_id in ids:
                with self.subTest(car_id):
                    new_id = tune.new_id_for(car_id)
                    clone_car.validate(car_id, new_id, str(d))
                    self.assertNotIn(new_id, ids)

    def test_each_tested_car_has_a_reference_doc_and_nothing_else_is_there(self):
        docs = sorted(p.name for p in DOCS.glob("*.md"))
        self.assertEqual(docs, sorted([c["id"] + ".md" for c in CARS_DATA["cars"]] + ["coverage.md"]))

    def test_cars_file_has_the_keys_load_cars_checks(self):
        raw = json.loads(CARS.read_text(encoding="utf-8"))
        self.assertLessEqual({"default", "cars"}, set(raw))
        self.assertTrue(all(set(c) == {"id", "label"} for c in raw["cars"]))


class TestCarsLoaderValidation(unittest.TestCase):
    def load(self, data):
        with tmp() as d:
            return tune.load_cars(write_json(d, "cars.json", data))

    def test_valid_file_loads(self):
        data = {"default": "ks_a", "cars": [{"id": "ks_a", "label": "A"}, {"id": "ks_b", "label": "B"}]}
        self.assertEqual(self.load(data), data)

    def test_invalid_files_are_refused(self):
        a = {"id": "ks_a", "label": "A"}
        cases = [("not an object", [a], "needs default and a list"), ("no default", {"cars": [a]}, "needs default"),
                 ("no cars", {"default": "ks_a"}, "needs default"), ("empty list", {"default": "ks_a", "cars": []}, "needs default"),
                 ("default numeric", {"default": 1, "cars": [a]}, "needs default"),
                 ("default not listed", {"default": "ks_b", "cars": [a]}, "unique and include the default"),
                 ("duplicate ids", {"default": "ks_a", "cars": [a, a]}, "unique and include the default"),
                 ("bad id chars", {"default": "Ks A", "cars": [{"id": "Ks A", "label": "A"}]}, "every car needs an id"),
                 ("empty label", {"default": "ks_a", "cars": [{"id": "ks_a", "label": ""}]}, "every car needs an id"),
                 ("no label", {"default": "ks_a", "cars": [{"id": "ks_a"}]}, "every car needs an id"),
                 ("car not an object", {"default": "ks_a", "cars": ["ks_a"]}, "every car needs an id")]
        for name, data, message in cases:
            with self.subTest(name):
                with self.assertRaisesRegex(ValueError, message):
                    self.load(data)


def parse_doc(text):
    """Title, groups with their table rows, and the copies-differ bullets of a generated reference doc."""
    def cells(line):
        return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]

    lines = text.split("\n")
    out = {"name": re.fullmatch(r"# (.*): tuner settings", lines[0]).group(1), "rows": [], "copies": {}}
    group = None
    for line in lines:
        if line.startswith("## "):
            group = line[3:]
        elif line.startswith("| `"):
            rid, label, default, unit, desc, status = cells(line)
            out["rows"].append(dict(group=group, id=rid.strip("`"), label=label, default=default, unit=unit, description=desc,
                                    status=status))
        elif group == "Copies differ in the stock data" and line.startswith("- `"):
            rid, rest = re.fullmatch(r"- `([a-z0-9_]+)`: (.*)", line).groups()
            out["copies"][rid] = re.findall(r"`([^`]+)` = ([^;]+)(?:; |$)", rest)
    return out


def rows_of_doc(doc):
    rows = []
    for r in doc["rows"]:
        absent = r["default"].endswith(" (absent)")
        row = dict(group=r["group"], id=r["id"], label=r["label"], absent=absent, unit=r["unit"], description=r["description"],
                   default=r["default"][:-len(" (absent)")] if absent else r["default"], verified=r["status"] == "verified",
                   copies_differ=r["id"] in doc["copies"])
        if row["copies_differ"]:
            row["copy_values"] = [{"target": t, "value": v} for t, v in doc["copies"][r["id"]]]
        rows.append(row)
    return rows


class TestReferenceDocs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texts = {c["id"]: (DOCS / (c["id"] + ".md")).read_bytes().decode("utf-8") for c in CARS_DATA["cars"]}
        cls.docs = {car: parse_doc(text) for car, text in cls.texts.items()}

    def test_rows_are_a_subset_of_the_catalogue_in_group_order_then_catalogue_order(self):
        order = [s["id"] for s in sorted(SETTINGS, key=lambda s: GROUP_ORDER.index(s["group"]))]
        for car, doc in self.docs.items():
            with self.subTest(car):
                ids = [r["id"] for r in doc["rows"]]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertLessEqual(set(ids), set(order))
                self.assertEqual(ids, [i for i in order if i in set(ids)])

    def test_each_group_heading_is_followed_by_the_description_of_the_group(self):
        descriptions = {g["name"]: g["description"] for g in CAT["groups"]}
        for car, text in self.texts.items():
            with self.subTest(car):
                headings = re.findall(r"^## (.*)$", text, re.M)
                groups = [h for h in headings if h not in ("Copies differ in the stock data", "Not covered yet")]
                self.assertEqual(groups, [g for g in GROUP_ORDER if g in set(groups)])
                self.assertEqual(set(groups), {r["group"] for r in self.docs[car]["rows"]})
                for g in groups:
                    self.assertIn("\n## %s\n\n%s\n\n| Variable | Name |" % (g, descriptions[g]), text)

    def test_labels_groups_units_descriptions_and_status_equal_the_catalogue(self):
        for car, doc in self.docs.items():
            for r in doc["rows"]:
                with self.subTest("%s %s" % (car, r["id"])):
                    s = BY_ID[r["id"]]
                    self.assertEqual((r["group"], r["label"], r["unit"], r["description"], r["status"]),
                                     (s["group"], s["label"], s["unit"], s["description"], "verified" if s["verified"] else "unverified"))

    def test_always_available_settings_are_in_every_doc(self):
        for car, doc in self.docs.items():
            ids = {r["id"] for r in doc["rows"]}
            self.assertLessEqual({"name_suffix", "limiter", "tyre_pressure_front"}, ids, car)

    def test_doc_text_reproduces_the_committed_docs(self):
        for car, doc in self.docs.items():
            with self.subTest(car):
                self.assertEqual(tune.doc_text(car, doc["name"], rows_of_doc(doc)), self.texts[car])

    def test_docs_are_lf_utf8_and_end_with_one_newline(self):
        for car, text in self.texts.items():
            with self.subTest(car):
                self.assertNotIn("\r", text)
                self.assertTrue(text.endswith("\n") and not text.endswith("\n\n"))

    def test_intro_names_the_car_and_the_generating_command(self):
        for car, text in self.texts.items():
            with self.subTest(car):
                self.assertIn("(car id `%s`)" % car, text)
                self.assertIn("`python tools/tune.py doc --car %s`" % car, text)

    def test_not_covered_list_is_the_one_in_tune(self):
        for car, text in self.texts.items():
            with self.subTest(car):
                tail = text.split("## Not covered yet\n\n")[1]
                self.assertEqual([line[2:] for line in tail.strip().split("\n")], list(tune.DOC_NOT_COVERED))

    def test_copies_differ_section_lists_exactly_the_rows_it_names(self):
        for car, text in self.texts.items():
            with self.subTest(car):
                m = re.search(r"Copies differ in the stock data: (.*?)\. The default shown", text)
                if m is None:
                    self.assertNotIn("## Copies differ in the stock data", text)
                    continue
                named = re.findall(r"`([a-z0-9_]+)`", m.group(1))
                self.assertEqual(named, list(self.docs[car]["copies"]))
                self.assertLessEqual(set(named), {r["id"] for r in self.docs[car]["rows"]})

    def test_doc_text_of_synthetic_rows(self):
        rows = [dict(group="G1", id="a", label="A|B", absent=True, unit="u", description="x|y", verified=True, default=0.5,
                     copies_differ=True, copy_values=[{"target": "@car p", "value": 1}, {"target": "@engine p", "value": 2}]),
                dict(group="G2", id="b", label="B", absent=False, unit="", description="d", verified=False, default=None,
                     copies_differ=False)]
        text = tune.doc_text("ks_x", "Car X", rows)
        self.assertTrue(text.startswith("# Car X: tuner settings\n\nThis file lists the tuner settings"))
        self.assertIn("## G1\n\n| Variable | Name | Default | Unit | Description | Status |\n| --- | --- | --- | --- | --- | --- |\n"
                      "| `a` | A\\|B | 0.5 (absent) | u | x\\|y | verified |\n", text)
        self.assertIn("| `b` | B | - |  | d | unverified |\n", text)
        self.assertIn("- `a`: `@car p` = 1; `@engine p` = 2\n", text)
        self.assertNotIn("(`b`)", text)
        self.assertTrue(text.endswith("\n- " + tune.DOC_NOT_COVERED[-1] + "\n"))

    def test_doc_text_orders_the_groups_by_the_group_list_and_puts_the_description_under_the_heading(self):
        def row(rid, group):
            return dict(group=group, id=rid, label=rid, absent=False, unit="", description="x", verified=True, default=1,
                        copies_differ=False)

        rows = [row("a", "G1"), row("b", "G2"), row("c", "G1"), row("d", "G3"), row("e", "G0")]
        groups = [{"name": "G2", "description": "second first"}, {"name": "G1", "description": "then first"},
                  {"name": "Unused", "description": "not in the rows"}]
        text = tune.doc_text("ks_x", "Car X", rows, groups)
        self.assertEqual(re.findall(r"^## (.*)$", text, re.M), ["G2", "G1", "G3", "G0", "Not covered yet"])
        self.assertIn("## G2\n\nsecond first\n\n| Variable |", text)
        self.assertIn("## G1\n\nthen first\n\n| Variable |", text)
        self.assertIn("## G3\n\n| Variable |", text)
        self.assertEqual(re.findall(r"^\| `(\w)`", text, re.M), ["b", "a", "c", "d", "e"])
        self.assertNotIn("not in the rows", text)

    def test_doc_text_takes_the_group_list_of_the_catalogue_by_default(self):
        text = tune.doc_text("ks_x", "Car X", [dict(group="Fuel", id="f", label="F", absent=False, unit="", description="x",
                                                   verified=True, default=1, copies_differ=False)])
        self.assertIn("## Fuel\n\n%s\n\n| Variable |" % BY_GROUP["Fuel"]["description"], text)


class TestStatedCounts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.counts = {c["id"]: len(re.findall(r"^\| `", (DOCS / (c["id"] + ".md")).read_text(encoding="utf-8"), re.M))
                      for c in CARS_DATA["cars"]}

    def read(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_tuner_spec_states_the_catalogue_size(self):
        m = re.search(r"(\d+) settings in the catalogue", self.read("docs/TUNER_SPEC.md"))
        self.assertIsNotNone(m)
        self.assertEqual(int(m.group(1)), len(SETTINGS))

    def test_no_doc_states_another_catalogue_size(self):
        for rel in ("README.md", "docs/HANDOVER.md", "docs/TUNER_SPEC.md"):
            for m in re.finditer(r"(\d+) settings in the catalogue|catalogue (?:of|with) (\d+) settings", self.read(rel)):
                self.assertEqual(int(m.group(1) or m.group(2)), len(SETTINGS), rel)

    def test_tuner_spec_states_the_applicable_range_of_the_tested_cars(self):
        m = re.search(r"(\d+)-(\d+) applicable per tested car", self.read("docs/TUNER_SPEC.md"))
        self.assertIsNotNone(m)
        self.assertEqual((int(m.group(1)), int(m.group(2))), (min(self.counts.values()), max(self.counts.values())))

    def test_doc_rows_never_exceed_the_catalogue(self):
        self.assertTrue(all(0 < n <= len(SETTINGS) for n in self.counts.values()))

    def test_readme_range_covers_the_tested_cars(self):
        m = re.search(r"About (\d+)\D+(\d+) settings per car", self.read("README.md"))
        self.assertIsNotNone(m)
        self.assertLessEqual(int(m.group(1)), min(self.counts.values()))
        self.assertGreaterEqual(int(m.group(2)), max(self.counts.values()))

    def test_coverage_doc_states_the_current_catalogue_size(self):
        intro = self.read("docs/settings/coverage.md").split("## Summary")[0]
        self.assertRegex(intro, r"\b%d\b" % len(SETTINGS))


# a stub .car without the objects that steer_lock_deg and car_mass live in (R3-004)
class TestOnlyOptionalTargets(unittest.TestCase):
    def setUp(self):
        self._d = tmp()
        self.work = str(self._d.__enter__())
        self.addCleanup(self._d.__exit__, None, None, None)
        self.fc = FakeCar(self.work).install(self)
        self.fc.add("presets/p.mechanicalcarpreset", {"brand": "B", "description": "D Preset Base"})

    def rows(self, ids):
        return {r["id"]: r for r in tune.resolve_defaults(self.work, "ks_x", dict(CAT, settings=[BY_ID[i] for i in ids]),
                                                          hidden=True)}

    def test_both_settings_have_a_single_required_target(self):
        for sid in ("steer_lock_deg", "car_mass"):
            self.assertEqual([t.get("optional") for t in BY_ID[sid]["targets"]], [None])

    def test_stored_values_are_read_when_the_car_has_the_objects(self):
        self.fc.add("data/x.car", {"controls": {"steer_lock": 540.0}, "general": {"totalMass": 1495.0}})
        rows = self.rows(["steer_lock_deg", "car_mass"])
        self.assertEqual([(r["applicable"], r["default"]) for r in rows.values()], [(True, 540.0), (True, 1495.0)])

    def test_a_missing_last_field_reads_as_absent_zero(self):
        self.fc.add("data/x.car", {"controls": {}, "general": {}})
        rows = self.rows(["steer_lock_deg", "car_mass"])
        self.assertEqual([(r["applicable"], r["default"], r["absent"]) for r in rows.values()],
                         [(True, 0.0, True), (True, 0.0, True)])

    def test_steer_lock_is_not_applicable_without_a_controls_object(self):
        self.fc.add("data/x.car", {"engine_path": "e"})
        self.assertFalse(self.rows(["steer_lock_deg"])["steer_lock_deg"]["applicable"])

    def test_car_mass_is_not_applicable_without_a_general_object(self):
        self.fc.add("data/x.car", {"engine_path": "e"})
        self.assertFalse(self.rows(["car_mass"])["car_mass"]["applicable"])

    def test_set_refuses_car_mass_without_a_general_object(self):
        self.fc.add("data/x.car", {"engine_path": "e"})
        with self.assertRaisesRegex(ValueError, "not applicable"):
            tune.set_value(self.work, "ks_x", "car_mass", "1200", dict(CAT, settings=[BY_ID["car_mass"]]))


if __name__ == "__main__":
    unittest.main()
