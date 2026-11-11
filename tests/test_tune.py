"""Tests for tools/tune.py. Run: python3 -m unittest discover -s tests"""
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import tune  # noqa: E402

CAR_ROOT = ROOT / "hdc_1.4" / "extracted" / "e46"
SPEC = ROOT / "spec" / "e46_levers.json"
PROFILE = ROOT / "spec" / "profiles" / "drift_v0.json"
CAR = "content/cars/hdc_bmw_e46_01/"
DRIFT_V0_CHANGED = {CAR + p for p in (
    "data/ks_bmw_m3_e46_1.drivetrain", "data/cardata.car", "data/hdc_bmw_e46_01.car",
    "data/setup/hdc_bmw_e46_01.carsetup", "data/setup/limits_m3_e46.carsetuplimits",
    "data/bmw_m3_e46_coupe_engine_power_1.curve")}


def tree(root):
    return {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}


def changed_files(a, b):
    ta, tb = tree(a), tree(b)
    assert set(ta) == set(tb)
    return {rel for rel in ta if ta[rel].read_bytes() != tb[rel].read_bytes()}, ta, tb


class Base(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CAR_ROOT.is_dir(), f"missing {CAR_ROOT}")
        self.spec = tune.load_spec(SPEC)
        self.profile = tune.load_spec(PROFILE)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = pathlib.Path(tmp.name) / "out"


class Check(Base):
    def test_untouched_e46_is_ok_and_covers_every_target(self):
        lines, ok = tune.check(self.spec, CAR_ROOT)
        self.assertTrue(ok, "\n".join(lines))
        self.assertEqual(len(lines), sum(len(lv["targets"]) for lv in self.spec["levers"]))
        for lv in self.spec["levers"]:
            self.assertEqual(sum(ln.startswith(lv["id"] + "  ") for ln in lines), len(lv["targets"]))
        self.assertTrue(all(ln.endswith("  ok") for ln in lines))

    def test_profile_on_untouched_e46_is_not_ok(self):
        lines, ok = tune.check(self.spec, CAR_ROOT, self.profile)
        self.assertFalse(ok)
        self.assertTrue(any(ln.endswith("  MISMATCH") for ln in lines))

    def test_missing_file_is_reported(self):
        lines, ok = tune.check(self.spec, self.out)
        self.assertFalse(ok)
        self.assertTrue(all(ln.endswith("  MISSING") for ln in lines))


class Apply(Base):
    def test_drift_v0_changes_exactly_the_expected_files(self):
        lines = tune.apply(self.spec, self.profile, CAR_ROOT, self.out)
        self.assertFalse([ln for ln in lines if ln.startswith("WARNING:")])
        ok_lines, ok = tune.check(self.spec, self.out, self.profile)
        self.assertTrue(ok, "\n".join(ok_lines))
        self.assertFalse(tune.check(self.spec, self.out)[1])
        changed, ta, tb = changed_files(CAR_ROOT, self.out)
        self.assertEqual(changed, DRIFT_V0_CHANGED)
        for rel in changed:
            self.assertEqual(ta[rel].stat().st_size, tb[rel].stat().st_size, rel)

    def test_roles_file_changes_only_file_targets(self):
        lines = tune.apply(self.spec, self.profile, CAR_ROOT, self.out, roles=["file"])
        changed, _, _ = changed_files(CAR_ROOT, self.out)
        self.assertEqual(changed, {CAR + "data/ks_bmw_m3_e46_1.drivetrain",
                                   CAR + "data/bmw_m3_e46_coupe_engine_power_1.curve"})
        self.assertNotIn(CAR + "data/cardata.car", changed)
        skipped = [ln for ln in lines if ln.startswith("SKIPPED:")]
        for lid in ("diff_coast_lock_max", "diff_preload_max", "diff_power_lock_max"):
            self.assertIn(f"SKIPPED: {lid}: no target for roles file", skipped)
        self.assertEqual(len(skipped), 3)
        self.assertTrue(any(ln.startswith("WARNING: diff_preload 80") for ln in lines))
        last_skipped = max(i for i, ln in enumerate(lines) if ln.startswith("SKIPPED:"))
        first_warning = min(i for i, ln in enumerate(lines) if ln.startswith("WARNING:"))
        self.assertLess(last_skipped, first_warning)

    def test_roles_filter_leaving_nothing_is_an_error(self):
        with self.assertRaises(ValueError):
            tune.apply(self.spec, {"values": {"diff_preload_max": 120}}, CAR_ROOT, self.out, roles=["file"])
        self.assertFalse(self.out.exists())

    def test_unknown_role_is_an_error(self):
        with self.assertRaises(ValueError):
            tune.apply(self.spec, self.profile, CAR_ROOT, self.out, roles=["nope"])
        self.assertFalse(self.out.exists())

    def test_existing_out_root_is_refused_and_untouched(self):
        self.out.mkdir()
        marker = self.out / "marker.txt"
        marker.write_text("keep")
        with self.assertRaises(ValueError):
            tune.apply(self.spec, self.profile, CAR_ROOT, self.out)
        self.assertEqual([p.name for p in self.out.iterdir()], ["marker.txt"])
        self.assertEqual(marker.read_text(), "keep")

    def test_unknown_lever_errors_and_creates_nothing(self):
        with self.assertRaises(ValueError):
            tune.apply(self.spec, {"values": {"no_such_lever": 1.0}}, CAR_ROOT, self.out)
        self.assertFalse(self.out.exists())

    def test_non_integral_value_for_int_target_errors(self):
        with self.assertRaises(ValueError):
            tune.apply(self.spec, {"values": {"rev_limiter_rpm": 8100.5}}, CAR_ROOT, self.out)
        self.assertFalse(self.out.exists())

    def test_int_target_takes_integral_value(self):
        tune.apply(self.spec, {"values": {"rev_limiter_rpm": 8200}}, CAR_ROOT, self.out)
        profile = {"values": {"rev_limiter_rpm": 8200}}
        lines, ok = tune.check(self.spec, self.out, profile)
        self.assertTrue(ok, "\n".join(lines))

    def test_warning_when_value_exceeds_unchanged_limit(self):
        lines = tune.apply(self.spec, {"values": {"diff_preload": 80}}, CAR_ROOT, self.out)
        warnings = [ln for ln in lines if ln.startswith("WARNING:")]
        self.assertEqual(len(warnings), 1)
        self.assertIn("diff_preload", warnings[0])

    def test_no_warning_when_limit_is_raised_too(self):
        profile = {"values": {"diff_preload": 80, "diff_preload_max": 120}}
        lines = tune.apply(self.spec, profile, CAR_ROOT, self.out)
        self.assertFalse([ln for ln in lines if ln.startswith("WARNING:")])


class SpecFile(unittest.TestCase):
    def test_structure(self):
        spec = tune.load_spec(SPEC)
        ids = [lv["id"] for lv in spec["levers"]]
        self.assertEqual(len(ids), len(set(ids)))
        for lv in spec["levers"]:
            with self.subTest(lever=lv["id"]):
                self.assertTrue(lv["id"])
                self.assertTrue(lv["targets"])
                self.assertIn(lv["confidence"], ("inferred", "unknown", "verified"))
                self.assertIn(lv["kind"], ("f32", "int", "curve_scale"))
                for t in lv["targets"]:
                    self.assertIn(t["role"], ("file", "inline", "devcopy", "setup", "limits"))
                    self.assertTrue(t["file"])
                    if lv["kind"] != "curve_scale":
                        self.assertTrue(t["path"])
                for key in ("min", "max"):
                    if "within" in lv:
                        self.assertIn(lv["within"][key], ids)

    def test_profile_refers_to_spec_levers(self):
        spec = tune.load_spec(SPEC)
        ids = {lv["id"] for lv in spec["levers"]}
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        self.assertLessEqual(set(profile["values"]) | set(profile["scale"]), ids)


if __name__ == "__main__":
    unittest.main()
