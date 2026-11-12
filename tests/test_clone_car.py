"""Tests for tools/clone_car.py on synthetic trees: same-length id replacement, renaming of a car tree, modded content and en.cars.loc, build orchestration (codec and packer stubbed), install with backup, CLI conventions."""
import contextlib
import datetime
import io
import json
import os
import re
import shutil
import unittest
from unittest import mock

from support import run_tool, tmp

import car_json
import clone_car
import kspkg

USAGE = clone_car.__doc__.split("\n\n")[1]
BOM = b"\xef\xbb\xbf"


class Base(unittest.TestCase):
    def setUp(self):
        cm = tmp()
        self.d = cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)

    def patch(self, target, name, value):
        p = mock.patch.object(target, name, value)
        p.start()
        self.addCleanup(p.stop)
        return value

    def write(self, path, data):
        path = str(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def read(self, path):
        with open(str(path), "rb") as f:
            return f.read()

    def stub_codec(self):
        self.patch(car_json, "load_schema", lambda path=None: {"stub": True})
        self.patch(car_json, "encode_msg", lambda sch, msg, fields: b"MODDED" + json.dumps(fields, sort_keys=True).encode())
        self.patch(car_json, "decode_msg", lambda sch, msg, data: json.loads(data[6:]))

    def capture(self, fn, *a, **k):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = fn(*a, **k)
        return result, out.getvalue()


class TestReplacer(unittest.TestCase):
    def sub(self, old, new, data):
        return re.compile(re.escape(old.encode()), re.IGNORECASE).sub(clone_car.replacer(new), data)

    def test_lower_case_and_upper_case_matches_keep_their_case(self):
        self.assertEqual(self.sub("ks_x", "ax_x", b"ks_x KS_X"), b"ax_x AX_X")

    def test_mixed_case_matches_become_lower_case(self):
        self.assertEqual(self.sub("ks_x", "ax_x", b"Ks_X kS_x"), b"ax_x ax_x")

    def test_plain_substring_replacement_also_inside_longer_words(self):
        self.assertEqual(self.sub("ks_x", "ax_x", b"ks_xyz_ks_x"), b"ax_xyz_ax_x")
        self.assertEqual(self.sub("ks_x", "ax_x", b"prefix_ks_x_suffix"), b"prefix_ax_x_suffix")

    def test_no_change_when_the_id_is_absent(self):
        data = bytes(range(256))
        self.assertEqual(self.sub("ks_x", "ax_x", data), data)
        self.assertEqual(self.sub("ks_x", "ax_x", b"ks_ x k s_x"), b"ks_ x k s_x")

    def test_length_is_kept_for_a_same_length_id(self):
        data = b"\x0a\x04ks_x\x12\x04KS_X" * 3
        self.assertEqual(len(self.sub("ks_x", "ax_x", data)), len(data))

    def test_returns_bytes(self):
        self.assertIsInstance(clone_car.replacer("ax_x")(re.match(b"ks_x", b"ks_x")), bytes)


class TestValidateAndArgs(Base):
    def test_valid_new_id(self):
        clone_car.validate("ks_x", "ax_x", str(self.d))

    def test_bad_new_ids(self):
        for new, message in (("AX_X", "may only contain lowercase"), ("ax x", "may only contain"), ("ax-x", "may only contain"),
                             ("", "may only contain"), ("ax_xy", "has 5 characters, it must have exactly 4"), ("ks_x", "equals the old id")):
            with self.subTest(new):
                with self.assertRaisesRegex(ValueError, message):
                    clone_car.validate("ks_x", new, str(self.d))

    def test_existing_target_folder_is_refused(self):
        os.makedirs(self.d / "content" / "cars" / "ax_x")
        with self.assertRaisesRegex(ValueError, "already exists, refusing to overwrite"):
            clone_car.validate("ks_x", "ax_x", str(self.d))

    def test_parse_args(self):
        pos, opts = clone_car.parse_args(["a", "--name", "N N", "b", "--year", "2001"], ("name", "year"))
        self.assertEqual((pos, opts), (["a", "b"], {"name": "N N", "year": "2001"}))

    def test_parse_args_bad_option_or_missing_value(self):
        with self.assertRaisesRegex(ValueError, "bad option --bogus"):
            clone_car.parse_args(["--bogus", "1"], ("name",))
        with self.assertRaisesRegex(ValueError, "--name"):
            clone_car.parse_args(["--name"], ("name",))


class TestCopyRenamed(Base):
    def make_src(self):
        src = self.d / "ks_x"
        blob = bytes(range(256)) * 4
        files = {"data/ks_x.car": b"\x0a\x04ks_x" + blob + b"KS_X" + blob + b"Ks_X",
                 "meshes/KS_X_body.mesh": blob[:100] + b"ks_x" + blob[:7],
                 "sub/deep/ks_xyz.txt": b"name=ks_xyz\n",
                 "plain.txt": b"nothing to see\n",
                 "ui/KS_X/icon.png": b"\x89PNG ks_x"}
        for rel, data in files.items():
            self.write(src / rel, data)
        os.makedirs(src / "empty_ks_x_dir")
        os.makedirs(src / "empty")
        return src, files

    def test_names_folders_and_contents_are_renamed(self):
        src, files = self.make_src()
        dst = self.d / "out"
        n, counts = clone_car.copy_renamed(str(src), str(dst), "ks_x", "ax_x")
        self.assertEqual(n, 5)
        self.assertEqual(sorted(os.path.relpath(os.path.join(dp, f), dst) for dp, _, fs in os.walk(dst) for f in fs),
                         sorted(["data/ax_x.car", "meshes/AX_X_body.mesh", "sub/deep/ax_xyz.txt", "plain.txt", "ui/AX_X/icon.png"]))
        self.assertTrue((dst / "empty_ax_x_dir").is_dir())
        self.assertTrue((dst / "empty").is_dir())
        car = self.read(dst / "data" / "ax_x.car")
        self.assertEqual(car, files["data/ks_x.car"].replace(b"ks_x", b"ax_x").replace(b"KS_X", b"AX_X").replace(b"Ks_X", b"ax_x"))
        self.assertEqual(self.read(dst / "sub" / "deep" / "ax_xyz.txt"), b"name=ax_xyz\n")
        self.assertEqual(self.read(dst / "plain.txt"), files["plain.txt"])

    def test_counts_name_the_renamed_files_with_hits(self):
        src, _ = self.make_src()
        _, counts = clone_car.copy_renamed(str(src), str(self.d / "out"), "ks_x", "ax_x")
        self.assertEqual(counts, {os.path.join("data", "ax_x.car"): 3, os.path.join("meshes", "AX_X_body.mesh"): 1,
                                  os.path.join("sub", "deep", "ax_xyz.txt"): 1, os.path.join("ui", "AX_X", "icon.png"): 1})

    def test_file_sizes_do_not_change(self):
        src, files = self.make_src()
        dst = self.d / "out"
        clone_car.copy_renamed(str(src), str(dst), "ks_x", "ax_x")
        self.assertEqual(os.path.getsize(dst / "data" / "ax_x.car"), len(files["data/ks_x.car"]))
        self.assertEqual(os.path.getsize(dst / "meshes" / "AX_X_body.mesh"), len(files["meshes/KS_X_body.mesh"]))

    def test_no_old_id_is_left_in_names_or_contents(self):
        src, _ = self.make_src()
        dst = self.d / "out"
        clone_car.copy_renamed(str(src), str(dst), "ks_x", "ax_x")
        for dp, dn, fs in os.walk(dst):
            for n in dn + fs:
                self.assertNotIn("ks_x", n.lower())
            for n in fs:
                self.assertNotIn(b"ks_x", self.read(os.path.join(dp, n)).lower())

    def test_source_is_untouched(self):
        src, files = self.make_src()
        clone_car.copy_renamed(str(src), str(self.d / "out"), "ks_x", "ax_x")
        self.assertEqual(self.read(src / "data" / "ks_x.car"), files["data/ks_x.car"])

    def test_tree_without_the_id_is_copied_unchanged(self):
        src = self.d / "ks_x"
        self.write(src / "a" / "b.bin", bytes(range(256)))
        n, counts = clone_car.copy_renamed(str(src), str(self.d / "out"), "ks_x", "ax_x")
        self.assertEqual((n, counts), (1, {}))
        self.assertEqual(self.read(self.d / "out" / "a" / "b.bin"), bytes(range(256)))

    def test_case_insensitive_name_match_in_a_folder_of_a_different_case(self):
        src = self.d / "ks_x"
        self.write(src / "Ks_X_data" / "f.txt", b"x")
        clone_car.copy_renamed(str(src), str(self.d / "out"), "ks_x", "ax_x")
        self.assertTrue((self.d / "out" / "ax_x_data" / "f.txt").is_file())


class TestModdedContentAndLocalization(Base):
    LOC = ("ks_x_name=Car X\r\nks_x_preset_base=Stock Variant\r\nks_x_desc=D = é ü\r\nKS_X_upper=U\r\n"
           "ks_y_name=Other\r\nks_xyz_name=Not ours\r\nplain=1\r\nks_x_no_equals_sign\r\n").encode("utf-8")

    def loc(self, data=None):
        return self.write(self.d / "stock" / "en.cars.loc", self.LOC if data is None else data)

    def test_modded_content_fields_default_properties_and_file(self):
        self.stub_codec()
        root = self.d / "car"
        os.makedirs(root)
        path, sch, msg, fields = clone_car.write_modded_content(str(root), "ax_x", "Name", "Brand", 2001)
        self.assertEqual((path, msg), (os.path.join(str(root), "ax_x.moddedcarcontent"), "ModdedCarContentData"))
        self.assertEqual(fields, {"display_name": "Name", "year": 2001, "brand": "Brand", "property_1": "Property1_Road",
                                  "property_2": "Property2_YoungTimer", "property_3": "Property3_ICE"})
        self.assertEqual(json.loads(self.read(path)[6:]), fields)

    def test_modded_content_properties_override_and_none_keeps_the_default(self):
        self.stub_codec()
        root = self.d / "car"
        os.makedirs(root)
        _, _, _, fields = clone_car.write_modded_content(str(root), "ax_x", "N", "B", 1, {"property_1": "Property1_Race", "property_2": None, "property_3": ""})
        self.assertEqual((fields["property_1"], fields["property_2"], fields["property_3"]),
                         ("Property1_Race", "Property2_YoungTimer", "Property3_ICE"))

    def test_stock_lines_are_the_cars_lines_of_either_line_ending(self):
        self.assertEqual(clone_car.stock_lines(self.loc(), "ks_x"),
                         ["ks_x_name=Car X", "ks_x_preset_base=Stock Variant", "ks_x_desc=D = é ü", "KS_X_upper=U"])
        self.assertEqual(clone_car.stock_lines(self.loc(b"ks_x_a=1\nks_x_b=2\n"), "ks_x"), ["ks_x_a=1", "ks_x_b=2"])

    def test_stock_lines_of_a_car_that_is_not_there(self):
        self.assertEqual(clone_car.stock_lines(self.loc(), "ks_q"), [])

    def test_stock_variant(self):
        self.assertEqual(clone_car.stock_variant(self.loc(), "ks_x"), "Stock Variant")
        self.assertEqual(clone_car.stock_variant(self.loc(b"ks_x_preset_base=A = B\r\n"), "ks_x"), "A = B")
        self.assertEqual(clone_car.stock_variant(self.loc(b"ks_x_name=A\r\n"), "ks_x"), "")
        self.assertEqual(clone_car.stock_variant(self.loc(b"ks_x_preset_base=A\r\nks_x_b_preset_base=B\r\n"), "ks_x"), "")

    def test_localization_lines_are_copied_under_the_new_id_as_utf8_crlf_without_bom(self):
        path, notes = clone_car.write_localization(str(self.d / "car"), "ks_x", "ax_x", self.loc(), None)
        self.assertEqual(path, os.path.join(str(self.d / "car"), "uiresources", "localization", "en.cars.loc"))
        data = self.read(path)
        self.assertEqual(data, "ax_x_name=Car X\r\nax_x_preset_base=Stock Variant\r\nax_x_desc=D = é ü\r\nax_x_upper=U\r\n".encode("utf-8"))
        self.assertFalse(data.startswith(BOM))
        self.assertEqual(notes, [])

    def test_variant_text_replaces_the_preset_base_line_only(self):
        path, _ = clone_car.write_localization(str(self.d / "car"), "ks_x", "ax_x", self.loc(), "My = Variant")
        lines = self.read(path).decode("utf-8").split("\r\n")
        self.assertEqual(lines[:2], ["ax_x_name=Car X", "ax_x_preset_base=My = Variant"])

    def test_no_line_for_the_car_writes_no_file_and_notes_it(self):
        loc = self.loc()
        path, notes = clone_car.write_localization(str(self.d / "car"), "ks_q", "ax_q", loc, None)
        self.assertEqual((path, notes), (None, ["note: %s has no line for ks_q, no en.cars.loc written" % loc]))
        self.assertFalse((self.d / "car").exists())

    def test_two_preset_base_lines_keep_the_stock_text_and_note_it(self):
        loc = self.loc(b"ks_x_a_preset_base=A\r\nks_x_b_preset_base=B\r\n")
        path, notes = clone_car.write_localization(str(self.d / "car"), "ks_x", "ax_x", loc, "V")
        self.assertEqual(self.read(path), b"ax_x_a_preset_base=A\r\nax_x_b_preset_base=B\r\n")
        self.assertEqual(notes, ["note: 2 stock lines end with _preset_base, the variant name is not applied"])

    def test_a_variant_that_cannot_be_applied_is_noted(self):
        loc = self.loc(b"ks_x_name=A\r\n")
        _, notes = clone_car.write_localization(str(self.d / "car"), "ks_x", "ax_x", loc, "V")
        self.assertEqual(notes, ["note: 0 stock lines end with _preset_base, the variant name is not applied"])

    # R1-026: nothing was asked to be applied (variant None), so there is nothing to note
    @unittest.expectedFailure
    def test_no_note_when_no_variant_was_requested(self):
        loc = self.loc(b"ks_x_name=A\r\n")
        _, notes = clone_car.write_localization(str(self.d / "car"), "ks_x", "ax_x", loc, None)
        self.assertEqual(notes, [])


class TestSelfCheck(Base):
    def modded(self):
        self.stub_codec()
        root = self.d / "out" / "content" / "cars" / "ax_x"
        os.makedirs(root)
        return clone_car.write_modded_content(str(root), "ax_x", "N", "B", 2000)

    def test_clean_tree_passes(self):
        modded = self.modded()
        self.write(self.d / "out" / "content" / "cars" / "ax_x" / "a.bin", b"ax_x only")
        ok, out = self.capture(clone_car.self_check, str(self.d / "out"), "ks_x", modded)
        self.assertTrue(ok)
        self.assertEqual(out.splitlines(), ["self-check (a) old id in names: none", "self-check (a) old id in contents: none",
                                            "self-check (b) ax_x.moddedcarcontent decodes to the written values: ok"])

    def test_old_id_in_a_name_or_content_fails(self):
        modded = self.modded()
        base = self.d / "out" / "content" / "cars" / "ax_x"
        self.write(base / "KS_X_left.txt", b"x")
        self.write(base / "b.bin", b"Ks_X")
        ok, out = self.capture(clone_car.self_check, str(self.d / "out"), "ks_x", modded)
        self.assertFalse(ok)
        self.assertIn("self-check (a) old id in names: 1 FOUND", out)
        self.assertIn("self-check (a) old id in contents: 1 FOUND", out)

    def test_modded_content_that_does_not_decode_to_the_written_values_fails(self):
        modded = self.modded()
        self.patch(car_json, "decode_msg", lambda sch, msg, data: {"display_name": "other"})
        ok, out = self.capture(clone_car.self_check, str(self.d / "out"), "ks_x", modded)
        self.assertFalse(ok)
        self.assertIn("MISMATCH", out)


class TestBuild(Base):
    def setUp(self):
        super().setUp()
        self.stub_codec()
        self.src = self.d / "src" / "ks_x"
        self.write(self.src / "data" / "ks_x.car", b"\x0a\x04ks_x data")
        self.write(self.src / "KS_X_thumb.png", b"png")
        self.out = self.d / "out"
        self.packed = []

        def pack(indir, pkg):
            self.packed.append((indir, pkg))
            self.write(pkg, b"PACKAGE")
        self.patch(kspkg, "cmd_pack", pack)

    def build(self, **kw):
        args = dict(name="Car X_MY", year=1999, brand="Brand", variant=None, stock_loc=None, properties=None, pack=False)
        args.update(kw)
        return self.capture(clone_car.build, str(self.src), "ax_x", str(self.out), args.pop("name"), args.pop("year"), args.pop("brand"), **args)

    def test_build_writes_the_renamed_tree_and_the_modded_content(self):
        notes, out = self.build()
        root = self.out / "content" / "cars" / "ax_x"
        self.assertEqual(self.read(root / "data" / "ax_x.car"), b"\x0a\x04ax_x data")
        self.assertTrue((root / "AX_X_thumb.png").is_file())
        self.assertEqual(json.loads(self.read(root / "ax_x.moddedcarcontent")[6:])["display_name"], "Car X_MY")
        self.assertIn("copied 2 files to %s" % root, out)
        self.assertIn("changed by replacement: 1 files, 1 replacements", out)
        self.assertIn("self-check (b) ax_x.moddedcarcontent decodes to the written values: ok", out)
        self.assertEqual(notes, ["note: no stock localization given, no en.cars.loc written"])
        self.assertEqual(self.packed, [])

    def test_build_with_a_stock_localization_writes_en_cars_loc(self):
        loc = self.write(self.d / "stock.loc", b"ks_x_name=Car X\r\nks_x_preset_base=Base\r\n")
        notes, out = self.build(stock_loc=loc, variant="Tuned")
        path = self.out / "content" / "cars" / "ax_x" / "uiresources" / "localization" / "en.cars.loc"
        self.assertEqual(self.read(path), b"ax_x_name=Car X\r\nax_x_preset_base=Tuned\r\n")
        self.assertEqual(notes, [])
        self.assertIn("localization: %s" % path, out)

    def test_build_packs_when_asked(self):
        _, out = self.build(pack=True)
        pkg = str(self.out / "ax_x.kspkg")
        self.assertEqual(self.packed, [(str(self.out), pkg)])
        self.assertIn("package: %s (7 bytes)" % pkg, out)

    def test_build_refuses_a_source_that_has_a_localization_already(self):
        self.write(self.src / "uiresources" / "localization" / "en.cars.loc", b"x")
        with self.assertRaisesRegex(ValueError, "already exists in the source car"):
            self.build()
        self.assertFalse((self.out / "content").exists())

    def test_build_refuses_a_missing_source_folder(self):
        shutil.rmtree(self.src)
        with self.assertRaisesRegex(ValueError, "is not a directory"):
            self.build()

    def test_build_refuses_an_existing_target(self):
        os.makedirs(self.out / "content" / "cars" / "ax_x")
        with self.assertRaisesRegex(ValueError, "already exists, refusing to overwrite"):
            self.build()

    def test_build_refuses_a_new_id_of_another_length_before_copying(self):
        with self.assertRaisesRegex(ValueError, "must have exactly 4"):
            self.capture(clone_car.build, str(self.src), "ax_xy", str(self.out), "N", 1, "B")
        self.assertFalse(self.out.exists())

    # R1-027: build() is a library function and must signal a failed self-check with an exception, not sys.exit
    @unittest.expectedFailure
    def test_failed_self_check_raises_value_error(self):
        self.patch(car_json, "decode_msg", lambda sch, msg, data: {"display_name": "other"})
        with self.assertRaises(ValueError):
            self.build()


class TestInstall(Base):
    def setUp(self):
        super().setUp()
        self.mods = self.d / "mods"
        self.backups = self.d / "backups"
        self.pkg = self.write(self.d / "pkg" / "ax_x.kspkg", b"N" * 5000)

    def install(self):
        return self.capture(clone_car.install, self.pkg, str(self.mods), str(self.backups))

    def test_first_install_copies_and_reports_no_backup(self):
        _, out = self.install()
        target = self.mods / "ax_x.kspkg"
        self.assertEqual(self.read(target), b"N" * 5000)
        self.assertEqual(out, "installed: %s (5000 bytes)\nbackup: no previous install\n" % target)
        self.assertFalse(self.backups.exists())

    def test_mods_folder_is_created(self):
        self.assertFalse(self.mods.exists())
        self.install()
        self.assertTrue(self.mods.is_dir())

    def test_previous_package_is_backed_up_with_a_time_stamp_before_it_is_replaced(self):
        self.write(self.mods / "ax_x.kspkg", b"G" * 1000)
        _, out = self.install()
        (backup,) = os.listdir(self.backups)
        self.assertRegex(backup, r"^ax_x_\d{8}_\d{6}\.kspkg$")
        self.assertEqual(self.read(self.backups / backup), b"G" * 1000)
        self.assertEqual(self.read(self.mods / "ax_x.kspkg"), b"N" * 5000)
        self.assertIn("backup: %s (1000 bytes)" % (self.backups / backup), out)

    def test_other_packages_in_the_mods_folder_are_left_alone(self):
        self.write(self.mods / "other.kspkg", b"keep")
        self.install()
        self.assertEqual(self.read(self.mods / "other.kspkg"), b"keep")
        self.assertFalse(self.backups.exists())

    def test_backup_name_uses_the_clock_and_a_second_install_in_the_same_second_is_refused(self):
        fake = mock.MagicMock()
        fake.datetime.now.return_value = datetime.datetime(2026, 1, 2, 3, 4, 5)
        self.patch(clone_car, "datetime", fake)
        self.write(self.mods / "ax_x.kspkg", b"G" * 10)
        self.install()
        self.assertEqual(os.listdir(self.backups), ["ax_x_20260102_030405.kspkg"])
        with self.assertRaisesRegex(ValueError, "backup .* already exists, try again in a second"):
            self.install()
        self.assertEqual(self.read(self.mods / "ax_x.kspkg"), b"N" * 5000)

    def test_not_a_kspkg_or_not_a_file_is_refused(self):
        txt = self.write(self.d / "pkg" / "a.txt", b"x")
        for bad in (txt, str(self.d / "pkg" / "missing.kspkg"), str(self.d / "pkg")):
            with self.subTest(bad):
                with self.assertRaisesRegex(ValueError, "is not an existing .kspkg file"):
                    clone_car.install(bad, str(self.mods), str(self.backups))
        self.assertFalse(self.mods.exists())

    def test_upper_case_extension_is_accepted(self):
        pkg = self.write(self.d / "pkg" / "AX_Y.KSPKG", b"x")
        self.capture(clone_car.install, pkg, str(self.mods), str(self.backups))
        self.assertTrue((self.mods / "AX_Y.KSPKG").is_file())

    def test_backup_size_mismatch_leaves_the_target_untouched(self):
        self.write(self.mods / "ax_x.kspkg", b"G" * 1000)

        def short_copy(src, dst):
            with open(dst, "wb") as f:
                f.write(b"G" * 10)
        self.patch(shutil, "copy2", short_copy)
        with self.assertRaisesRegex(ValueError, "backup size mismatch"):
            self.install()
        self.assertEqual(self.read(self.mods / "ax_x.kspkg"), b"G" * 1000)

    def test_installed_size_mismatch_is_an_error(self):
        def short_copy(src, dst):
            with open(dst, "wb") as f:
                f.write(b"N" * 10)
        self.patch(shutil, "copyfile", short_copy)
        with self.assertRaisesRegex(ValueError, "installed size mismatch"):
            self.install()

    # R3-002: a copy that dies half way must not leave a truncated package under the real name
    @unittest.expectedFailure
    def test_failure_half_way_keeps_the_old_package(self):
        self.write(self.mods / "ax_x.kspkg", b"G" * 1000)
        real = shutil.copyfile

        def dying(src, dst, **kw):
            if os.path.dirname(dst) == str(self.mods):
                with open(dst, "wb") as f:
                    f.write(b"N" * 100)
                raise OSError(28, "No space left on device")
            return real(src, dst, **kw)
        self.patch(shutil, "copyfile", dying)
        with self.assertRaises((OSError, ValueError)):
            self.install()
        self.assertEqual(self.read(self.mods / "ax_x.kspkg"), b"G" * 1000)

    def test_failure_half_way_keeps_the_backup(self):
        self.write(self.mods / "ax_x.kspkg", b"G" * 1000)
        real = shutil.copyfile

        def dying(src, dst, **kw):
            if os.path.dirname(dst) == str(self.mods):
                raise OSError(28, "No space left on device")
            return real(src, dst, **kw)
        self.patch(shutil, "copyfile", dying)
        with self.assertRaises(OSError):
            self.install()
        (backup,) = os.listdir(self.backups)
        self.assertEqual(self.read(self.backups / backup), b"G" * 1000)


class TestCli(Base):
    def run_in(self, *args):
        cwd = self.d / "cwd"
        os.makedirs(cwd, exist_ok=True)
        return run_tool("clone_car.py", *args, cwd=cwd)

    def test_install_prints_the_installed_package_and_the_backup(self):
        pkg = self.write(self.d / "pkg" / "ax_x.kspkg", b"N" * 20)
        mods, backups = self.d / "mods", self.d / "backups"
        r = self.run_in("install", pkg, "--mods", mods, "--backups", backups)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(r.stdout, "installed: %s (20 bytes)\nbackup: no previous install\n" % (mods / "ax_x.kspkg"))
        r = self.run_in("install", pkg, "--mods", mods, "--backups", backups)
        self.assertEqual(r.returncode, 0)
        self.assertRegex(r.stdout.splitlines()[1], r"^backup: .*ax_x_\d{8}_\d{6}\.kspkg \(20 bytes\)$")

    def test_runtime_errors_are_error_lines_on_stderr_with_exit_1(self):
        for args, message in ((("install", self.d / "nope.kspkg"), "is not an existing .kspkg file"),
                              (("build", self.d / "ks_x", "ax_xy", self.d / "out"), "has 5 characters, it must have exactly 4"),
                              (("build", self.d / "ks_x", "AX_X", self.d / "out"), "may only contain lowercase"),
                              (("build", self.d / "ks_x", "ax_x", self.d / "out", "--year", "x"), "--year must be an integer"),
                              (("build", self.d / "ks_x", "ax_x", self.d / "out"), "is not a directory")):
            with self.subTest(args):
                r = self.run_in(*args)
                self.assertEqual((r.returncode, r.stdout), (1, ""))
                self.assertRegex(r.stderr, r"^error: .*%s.*\n$" % re.escape(message))

    # R1-028: a mods path with an unexpanded %VAR% must be an error that creates no folder
    @unittest.expectedFailure
    def test_unexpanded_mods_path_is_an_error_and_creates_nothing(self):
        pkg = self.write(self.d / "pkg" / "ax_x.kspkg", b"N" * 20)
        r = self.run_in("install", pkg, "--mods", "%ACE_TEST_NO_SUCH_VAR%/mods", "--backups", self.d / "backups")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("error:"), r.stderr)
        self.assertEqual(os.listdir(self.d / "cwd"), [])

    # R1-028
    @unittest.expectedFailure
    def test_unexpanded_backups_path_is_an_error_and_creates_nothing(self):
        pkg = self.write(self.d / "pkg" / "ax_x.kspkg", b"N" * 20)
        self.write(self.d / "mods" / "ax_x.kspkg", b"old")
        r = self.run_in("install", pkg, "--mods", self.d / "mods", "--backups", "%ACE_TEST_NO_SUCH_VAR%/backups")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("error:"), r.stderr)
        self.assertEqual(os.listdir(self.d / "cwd"), [])
        self.assertEqual(self.read(self.d / "mods" / "ax_x.kspkg"), b"old")


def usage_case(name, argv):
    # D5: wrong or missing arguments print the usage block on stdout and exit 2, today it goes to stderr and exits 1
    @unittest.expectedFailure
    def test(self):
        r = self.run_in(*argv)
        self.assertEqual((r.returncode, r.stdout.strip(), r.stderr), (2, USAGE.strip(), ""))
    test.__name__ = "test_usage_" + name
    return test


for _name, _argv in (("no_arguments", []), ("unknown_command", ["frobnicate"]), ("build_with_two_operands", ["build", "a", "b"]),
                     ("build_with_four_operands", ["build", "a", "b", "c", "d"]), ("build_unknown_option", ["build", "a", "b", "c", "--bogus", "1"]),
                     ("build_option_without_value", ["build", "a", "b", "c", "--name"]), ("install_without_operand", ["install"]),
                     ("install_with_two_operands", ["install", "a.kspkg", "b.kspkg"]), ("install_unknown_option", ["install", "a.kspkg", "--bogus", "1"]),
                     ("install_option_without_value", ["install", "a.kspkg", "--mods"])):
    setattr(TestCli, "test_usage_" + _name, usage_case(_name, _argv))


class TestUsageText(unittest.TestCase):
    def test_usage_block_is_the_first_paragraph_after_the_title(self):
        self.assertTrue(USAGE.startswith("usage:\n  python tools/clone_car.py build"))
        self.assertIn("python tools/clone_car.py install", USAGE)
        self.assertEqual(len(clone_car.__doc__.split("\n\n")[0].splitlines()), 1)

    def test_every_documented_option_is_accepted_by_the_parser(self):
        flags = set(re.findall(r"\[--([a-z0-9]+) ", USAGE))
        self.assertEqual(flags, {"name", "year", "brand", "variant", "loc", "property1", "property2", "property3", "mods", "backups"})
        pos, opts = clone_car.parse_args(sum((["--" + f, "v"] for f in sorted(flags)), []), flags)
        self.assertEqual(set(opts), flags)
        self.assertIn("[--no-pack]", USAGE)


if __name__ == "__main__":
    unittest.main()
