"""Tests for tools/make_testkit.py (no test packs a package). Run: python3 -m unittest discover -s tests"""
import contextlib
import io
import json
import pathlib
import re
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import make_testkit  # noqa: E402
import tune  # noqa: E402

CAR_ROOT = ROOT / "hdc_1.4" / "extracted" / "e46"
SPEC = ROOT / "spec" / "e46_levers.json"
PROFILES = ROOT / "spec" / "profiles"
SHA_FILE = ROOT / "spec" / "e46_package.sha256"


def profile_of(variant):
    return json.loads((PROFILES / (variant["profile"] + ".json")).read_text(encoding="utf-8"))


class Variants(unittest.TestCase):
    def setUp(self):
        self.spec = tune.load_spec(SPEC)
        self.with_profile = [v for v in make_testkit.VARIANTS if v["profile"] is not None]

    def test_profiles_exist_and_load(self):
        for v in self.with_profile:
            with self.subTest(variant=v["name"]):
                self.assertTrue((PROFILES / (v["profile"] + ".json")).is_file())
                self.assertIsInstance(profile_of(v), dict)

    def test_roles_occur_in_spec(self):
        known = {t["role"] for lv in self.spec["levers"] for t in lv["targets"]}
        for v in self.with_profile:
            with self.subTest(variant=v["name"]):
                self.assertLessEqual(set(v["roles"] or ()), known)

    def test_profile_levers_exist_in_spec(self):
        ids = {lv["id"] for lv in self.spec["levers"]}
        for v in self.with_profile:
            with self.subTest(variant=v["name"]):
                profile = profile_of(v)
                self.assertLessEqual(set(profile.get("values", {})) | set(profile.get("scale", {})), ids)

    def test_every_variant_has_a_plan_for_its_roles(self):
        for v in self.with_profile:
            with self.subTest(variant=v["name"]):
                plan, skipped = tune.plan_profile(self.spec, profile_of(v), v["roles"])
                self.assertTrue(plan)
                self.assertFalse(skipped)

    def test_names_unique_and_a_first(self):
        names = [v["name"] for v in make_testkit.VARIANTS]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(names, ["A_unchanged", "B1_limiter_file", "B2_limiter_inline",
                                 "C_torque_half", "D_drift_v0"])
        self.assertIsNone(make_testkit.VARIANTS[0]["profile"])
        self.assertTrue(all(v["description"] for v in make_testkit.VARIANTS))

    def test_only_a_has_no_profile(self):
        self.assertEqual([v["name"] for v in make_testkit.VARIANTS if v["profile"] is None],
                         ["A_unchanged"])


class ShaFile(unittest.TestCase):
    def test_one_line_hash_and_package_name(self):
        text = SHA_FILE.read_text(encoding="utf-8")
        self.assertRegex(text, r"\A[0-9a-f]{64}  hinas_drift_club_e46_v1\.4\.kspkg\n\Z")
        self.assertEqual(len(text.splitlines()), 1)
        self.assertEqual(make_testkit.read_sha(SHA_FILE), text[:64])
        self.assertEqual(make_testkit.PKG_NAME, text.split()[1])

    def test_read_sha_rejects_garbage(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = pathlib.Path(tmp) / "bad.sha256"
            for text in ("", "xyz  file\n", "abc  file\n"):
                bad.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    make_testkit.read_sha(bad)


class Refusal(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = pathlib.Path(tmp.name) / "kit"
        self.out.mkdir()
        self.marker = self.out / "marker.txt"
        self.marker.write_text("keep")

    def assert_untouched(self):
        self.assertEqual([p.name for p in self.out.iterdir()], ["marker.txt"])
        self.assertEqual(self.marker.read_text(), "keep")

    def test_build_variants_refuses_existing_out_dir(self):
        with mock.patch.object(make_testkit.kspkg, "cmd_pack", side_effect=AssertionError("packed")):
            with self.assertRaises(ValueError):
                make_testkit.build_variants(CAR_ROOT, SHA_FILE, self.out)
        self.assert_untouched()

    def test_main_exits_1_on_existing_out_dir(self):
        argv = ["make_testkit.py", str(CAR_ROOT), str(SHA_FILE), str(self.out)]
        err = io.StringIO()
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(make_testkit.kspkg, "cmd_pack", side_effect=AssertionError("packed")), \
                contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                make_testkit.main()
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("output already exists", err.getvalue())
        self.assert_untouched()

    def test_bad_sha_file_creates_nothing(self):
        out = self.out.parent / "kit2"
        bad = self.out.parent / "bad.sha256"
        bad.write_text("nothing\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            make_testkit.build_variants(CAR_ROOT, bad, out)
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
