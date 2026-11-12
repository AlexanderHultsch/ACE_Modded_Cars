"""Synthetic-data tests for tools/kspkg.py: primitives, pack/list/extract/verify, hand-built packages, CLI conventions."""
import contextlib
import io
import os
import pathlib
import struct
import unittest

from support import run_tool, tmp

import kspkg

KEY = bytes.fromhex("c135117da921979f")
MIB = 1 << 20
HEADER_SIZE = MIB
TABLE_SIZE = 64 * MIB
ENTRY_SIZE = 256
DIR, XOR = 1, 0x100


def fnv(path):
    h = 0xCBF29CE484222325
    for b in path.encode("utf-16le"):
        h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def xor(buf):
    return bytes(b ^ KEY[i % 8] for i, b in enumerate(buf))


def write_package(path, rows, body=b""):
    """rows = (name, flags, size, offset); the table is written independently of kspkg.cmd_pack."""
    entries = bytearray()
    for name, flags, size, off in sorted(rows, key=lambda r: fnv(r[0])):
        raw = name.encode("utf-8")
        e = bytearray(ENTRY_SIZE)
        e[:len(raw)] = raw
        struct.pack_into("<ihhQqq", e, 0xE0, 0, flags, len(raw), fnv(name), size, off)
        entries += e
    table = xor(bytes(entries)) + KEY * ((TABLE_SIZE - len(entries)) // 8)
    with open(path, "wb") as f:
        f.write(bytes(HEADER_SIZE) + body)
        f.write(bytes((-f.tell()) % MIB))
        f.write(table)


def build_package(path, items):
    """items = (name, flags, data); XOR-flagged data is stored encrypted, each entry starting at key phase 0."""
    body, rows, off = bytearray(), [], HEADER_SIZE
    for name, flags, data in items:
        if flags & DIR:
            rows.append((name, flags, 0, 0))
            continue
        body += xor(data) if flags & XOR else data
        rows.append((name, flags, len(data), off))
        off += len(data)
    write_package(path, rows, bytes(body))


def read_entries(path, limit=64):
    """(entries, table bytes after the last entry, raw table tail, package size), decoded without kspkg."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        f.seek(size - TABLE_SIZE)
        raw = f.read(TABLE_SIZE)
    entries, i = [], 0
    while i < limit * ENTRY_SIZE:
        e = xor(raw[i:i + ENTRY_SIZE])
        flags, plen = struct.unpack_from("<hh", e, 0xE4)
        h, fsize, foff = struct.unpack_from("<Qqq", e, 0xE8)
        if h == 0:
            break
        entries.append(dict(path=e[:plen].decode("utf-8", "replace"), pathlen=plen, zero=struct.unpack_from("<i", e, 0xE0)[0],
                            flags=flags, hash=h, size=fsize, off=foff))
        i += ENTRY_SIZE
    return entries, raw[i:], raw[-8:], size


def capture(fn, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn(*args)
    return result, buf.getvalue()


def tree(root):
    files = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    dirs = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir()}
    return files, dirs


def usage_block():
    return kspkg.__doc__.split("\n\n")[1].strip()


CAR = "content\\cars\\abc\\"
ITEMS = [
    (CAR[:-1], DIR, b""),
    (CAR + "pad.bin", 0, b"\x01\x02\x03"),
    (CAR + "data\\a.txt", XOR, b"hello xor world, longer than one key period"),
    (CAR + "data\\big.dat", XOR, bytes(range(256)) * 20),
    (CAR + "plain.bin", 0, b"plain bytes"),
    (CAR + "empty.bin", XOR, b""),
    (CAR + "data", DIR, b""),
    ("content\\cars\\abcd\\other.bin", 0, b"other"),
]
FILES = {name: data for name, flags, data in ITEMS if not flags & DIR}


class Primitives(unittest.TestCase):
    def test_format_constants(self):
        self.assertEqual((kspkg.HEADER, kspkg.TBL, kspkg.ENTRY), (HEADER_SIZE, TABLE_SIZE, ENTRY_SIZE))
        self.assertEqual((kspkg.FLAG_DIR, kspkg.FLAG_XOR), (DIR, XOR))
        self.assertEqual(kspkg.KEY, KEY)

    def test_xor_of_zeros_is_the_repeating_key_from_the_first_byte(self):
        for n in (0, 1, 7, 8, 9, 20, 64):
            self.assertEqual(kspkg.xor(bytes(n), KEY), (KEY * (n // 8 + 1))[:n])

    def test_xor_matches_bytewise_reference(self):
        data = bytes(range(256)) * 3
        for n in (1, 7, 8, 9, 17, 300, 768):
            self.assertEqual(kspkg.xor(data[:n], KEY), xor(data[:n]))

    def test_xor_is_an_involution(self):
        data = bytes(range(256)) * 4
        for n in (0, 1, 7, 8, 9, 1000):
            self.assertEqual(kspkg.xor(kspkg.xor(data[:n], KEY), KEY), data[:n])

    def test_xor_empty_input_gives_empty_bytes(self):
        self.assertEqual(kspkg.xor(b"", KEY), b"")

    def test_path_hash_of_empty_string_is_the_fnv_offset_basis(self):
        self.assertEqual(kspkg.path_hash(""), 0xCBF29CE484222325)

    def test_path_hash_is_fnv1a_64_over_utf16le(self):
        for p in ("a", "content\\cars\\abc\\b.bin", "content\\cars\\abc\\\u00fc.txt"):
            self.assertEqual(kspkg.path_hash(p), fnv(p), p)

    def test_path_hash_known_value(self):
        self.assertEqual(kspkg.path_hash("a"), 0x089BE207B544F1E4)

    def test_path_hash_is_case_sensitive(self):
        self.assertNotEqual(kspkg.path_hash("A"), kspkg.path_hash("a"))


class Paths(unittest.TestCase):
    def test_plain_path_strips_the_extended_length_prefix(self):
        self.assertEqual(kspkg.plain_path("\\\\?\\C:\\very\\long"), "C:\\very\\long")

    def test_plain_path_restores_unc_form(self):
        self.assertEqual(kspkg.plain_path("\\\\?\\UNC\\srv\\share\\f"), "\\\\srv\\share\\f")

    def test_plain_path_leaves_ordinary_paths_alone(self):
        self.assertEqual(kspkg.plain_path(os.path.join("some", "dir")), os.path.join("some", "dir"))

    def test_long_path_is_identity_off_windows_and_prefixed_on_windows(self):
        p = os.path.join("some", "dir", "file.bin")
        if os.name == "nt":
            self.assertTrue(kspkg.long_path(p).startswith(kspkg.LONG_PREFIX))
            self.assertEqual(kspkg.plain_path(kspkg.long_path(p)), os.path.abspath(p))
        else:
            self.assertEqual(kspkg.long_path(p), p)

    def test_long_path_accepts_pathlib_and_returns_str(self):
        p = pathlib.Path("some") / "dir"
        self.assertIsInstance(kspkg.long_path(p), str)

    def test_long_path_keeps_an_already_prefixed_path(self):
        p = "\\\\?\\C:\\already\\long"
        self.assertEqual(kspkg.long_path(p), p)

    def test_safe_path_joins_backslash_separated_names_below_root(self):
        with tmp() as root:
            got = kspkg.plain_path(kspkg.safe_path(root, "content\\cars\\abc\\b.bin"))
            self.assertEqual(got, os.path.join(os.path.abspath(root), "content", "cars", "abc", "b.bin"))

    def test_safe_path_accepts_forward_slashes(self):
        with tmp() as root:
            got = kspkg.plain_path(kspkg.safe_path(root, "content/cars/abc/b.bin"))
            self.assertEqual(got, os.path.join(os.path.abspath(root), "content", "cars", "abc", "b.bin"))

    def test_safe_path_never_leaves_the_root(self):
        hostile = ["..\\..\\evil.txt", "../../evil.txt", "a\\..\\..\\evil.txt", "\\windows\\system32\\x", "/etc/passwd",
                   "C:\\evil.txt", "C:/evil.txt", "\\\\server\\share\\x", "..", "."]
        with tmp() as d:
            root = os.path.abspath(d)
            for name in hostile:
                with self.subTest(name=name):
                    try:
                        got = kspkg.plain_path(kspkg.safe_path(root, name))
                    except ValueError:
                        continue
                    self.assertEqual(os.path.normcase(os.path.commonpath([root, got])), os.path.normcase(root))

    def test_safe_path_drops_dotdot_and_leading_separators_instead_of_following_them(self):
        with tmp() as d:
            root = os.path.abspath(d)
            self.assertEqual(kspkg.plain_path(kspkg.safe_path(root, "..\\..\\evil.txt")), os.path.join(root, "evil.txt"))
            self.assertEqual(kspkg.plain_path(kspkg.safe_path(root, "/etc/passwd")), os.path.join(root, "etc", "passwd"))


class Packed(unittest.TestCase):
    SOURCES = {
        "content/cars/abc/data/a.txt": b"hello",
        "content/cars/abc/big.bin": bytes(range(256)) * 4688,
        "content/cars/abc/\u00fc.txt": b"unicode name",
        "content/cars/abc/empty.bin": b"",
        "content/cars/abc/Mixed.TXT": b"mixed case",
    }
    EXPECTED_FILES = {k.lower(): v for k, v in SOURCES.items()}
    EXPECTED_NAMES = sorted(k.replace("/", "\\") for k in EXPECTED_FILES)
    EXPECTED_DIRS = ["content\\cars\\abc", "content\\cars\\abc\\data", "content\\cars\\abc\\emptydir"]

    @classmethod
    def setUpClass(cls):
        cls._tmp = tmp()
        cls.base = cls._tmp.__enter__()
        cls.src = cls.base / "src"
        for rel, data in cls.SOURCES.items():
            p = cls.src / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        (cls.src / "content" / "cars" / "abc" / "emptydir").mkdir()
        cls.pkg = cls.base / "packed.kspkg"
        cls.pack_run = run_tool("kspkg.py", "pack", cls.src, cls.pkg)
        cls.entries, cls.tail, cls.raw_key, cls.size = read_entries(cls.pkg)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.__exit__(None, None, None)

    def file_entries(self):
        return [e for e in self.entries if not e["flags"] & DIR]

    def test_cli_pack_succeeds_and_reports_the_file_count(self):
        self.assertEqual(self.pack_run.returncode, 0, self.pack_run.stderr)
        self.assertTrue(self.pack_run.stdout.startswith("packed 5 files + "), self.pack_run.stdout)
        self.assertEqual(self.pack_run.stderr, "")

    def test_pack_then_extract_round_trips_every_file(self):
        with tmp() as out:
            capture(kspkg.cmd_extract, str(self.pkg), str(out))
            files, _ = tree(out)
        self.assertEqual(files, self.EXPECTED_FILES)

    def test_pack_lowercases_entry_names(self):
        for e in self.entries:
            self.assertEqual(e["path"], e["path"].lower())

    def test_pack_entry_names_use_backslashes_on_every_os(self):
        self.assertEqual(sorted(e["path"] for e in self.file_entries()), self.EXPECTED_NAMES)

    def test_pack_writes_directory_entries_including_empty_ones(self):
        self.assertEqual(sorted(e["path"] for e in self.entries if e["flags"] & DIR), self.EXPECTED_DIRS)

    def test_package_size_is_header_padded_data_and_64_mib_table(self):
        data_end = HEADER_SIZE + sum(len(v) for v in self.SOURCES.values())
        self.assertEqual(self.size, -(-data_end // MIB) * MIB + TABLE_SIZE)

    def test_header_and_padding_are_zero(self):
        data_end = HEADER_SIZE + sum(len(v) for v in self.SOURCES.values())
        with open(self.pkg, "rb") as f:
            self.assertEqual(f.read(HEADER_SIZE), bytes(HEADER_SIZE))
            f.seek(data_end)
            self.assertEqual(f.read(self.size - TABLE_SIZE - data_end), bytes(self.size - TABLE_SIZE - data_end))

    def test_data_is_contiguous_from_1_mib_largest_file_first(self):
        files = sorted(self.file_entries(), key=lambda e: e["off"])
        self.assertEqual(files[0]["off"], HEADER_SIZE)
        for a, b in zip(files, files[1:]):
            self.assertEqual(b["off"], a["off"] + a["size"])
            self.assertGreaterEqual(a["size"], b["size"])

    def test_stored_data_matches_the_sources_and_is_not_xored(self):
        with open(self.pkg, "rb") as f:
            stored = []
            for e in self.file_entries():
                f.seek(e["off"])
                stored.append(f.read(e["size"]))
        self.assertEqual(sorted(stored), sorted(self.SOURCES.values()))

    def test_table_entries_are_sorted_by_hash(self):
        hashes = [e["hash"] for e in self.entries]
        self.assertGreater(len(hashes), 4)
        self.assertEqual(hashes, sorted(set(hashes)))

    def test_entry_fields_are_consistent(self):
        for e in self.entries:
            with self.subTest(path=e["path"]):
                self.assertEqual(e["hash"], fnv(e["path"]))
                self.assertEqual(e["pathlen"], len(e["path"].encode("utf-8")))
                self.assertLessEqual(e["pathlen"], 0xE0)
                self.assertEqual(e["zero"], 0)
                self.assertIn(e["flags"], (0, DIR))
                if e["flags"] & DIR:
                    self.assertEqual((e["size"], e["off"]), (0, 0))

    def test_table_after_the_last_entry_is_the_key_pattern_and_ends_with_the_key(self):
        self.assertEqual(self.tail, KEY * (len(self.tail) // 8))
        self.assertEqual(self.raw_key, KEY)

    def test_kspkg_reads_back_what_pack_wrote(self):
        with open(self.pkg, "rb") as f:
            key, entries, size = kspkg.read_table(f)
        self.assertEqual(key, KEY)
        self.assertEqual(size, self.size)
        self.assertEqual([(e["path"], e["flags"], e["hash"], e["size"], e["off"]) for e in entries],
                         [(e["path"], e["flags"], e["hash"], e["size"], e["off"]) for e in self.entries])

    def test_cli_list_prints_key_line_and_one_line_per_entry(self):
        r = run_tool("kspkg.py", "list", self.pkg)
        lines = r.stdout.splitlines()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(lines[0], f"key={KEY.hex()} entries={len(self.entries)} pkgsize={self.size}")
        self.assertEqual(len(lines), 1 + len(self.entries))

    def test_read_table_parses_the_table_once_per_unchanged_package(self):
        with tmp() as d:
            pkg = d / "cache.kspkg"
            build_package(pkg, [(CAR + "a.bin", 0, b"one")])
            real, calls = kspkg.xor, []
            kspkg.xor = lambda buf, key: calls.append(1) or real(buf, key)
            try:
                for _ in range(2):
                    with open(pkg, "rb") as f:
                        key, entries, _ = kspkg.read_table(f)
                self.assertEqual(len(calls), len(entries) + 1)
                build_package(pkg, [(CAR + "a.bin", 0, b"one"), (CAR + "b.bin", 0, b"two")])
                os.utime(pkg, ns=(0, os.stat(pkg).st_mtime_ns + 10 ** 9))
                with open(pkg, "rb") as f:
                    key, entries, _ = kspkg.read_table(f)
            finally:
                kspkg.xor = real
            self.assertEqual(sorted(e["path"] for e in entries), [CAR + "a.bin", CAR + "b.bin"])

    def test_cli_verify_of_a_package_with_itself_is_identical(self):
        r = run_tool("kspkg.py", "verify", self.pkg, self.pkg)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "IDENTICAL CONTENT"))

    def test_pack_rejects_a_path_longer_than_the_entry_name_field(self):
        with tmp() as d:
            deep = d / "src" / "content" / "cars" / "x" / ("a" * 120) / ("b" * 120)
            deep.mkdir(parents=True)
            (deep / "f.bin").write_bytes(b"x")
            pkg = d / "long.kspkg"
            with self.assertRaisesRegex(ValueError, "path too long"):
                capture(kspkg.cmd_pack, str(d / "src"), str(pkg))
            self.assertFalse(pkg.exists())


class HandBuilt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tmp()
        base = cls._tmp.__enter__()
        cls.pkg = base / "hand.kspkg"
        build_package(cls.pkg, ITEMS)
        cls.relayout = base / "relayout.kspkg"
        build_package(cls.relayout, [(n, f if f & DIR else f ^ XOR, d) for n, f, d in reversed(ITEMS)])
        cls.changed = base / "changed.kspkg"
        build_package(cls.changed, [(n, f, d + b"!" if n.endswith("plain.bin") else d) for n, f, d in ITEMS])
        cls.missing = base / "missing.kspkg"
        build_package(cls.missing, [i for i in ITEMS if not i[0].endswith("other.bin")])
        cls.truncated = base / "truncated.kspkg"
        write_package(cls.truncated, [("content\\cars\\x\\big.bin", 0, 5000, HEADER_SIZE + TABLE_SIZE - 100)])

    @classmethod
    def tearDownClass(cls):
        cls._tmp.__exit__(None, None, None)

    def extract(self, *prefix):
        with tmp() as out:
            _, text = capture(kspkg.cmd_extract, str(self.pkg), str(out), *prefix)
            return text, tree(out)

    def test_extract_decodes_xor_flagged_and_plain_entries(self):
        _, (files, _) = self.extract()
        self.assertEqual(files, {k.replace("\\", "/"): v for k, v in FILES.items()})

    def test_extract_creates_directory_entries(self):
        _, (_, dirs) = self.extract()
        self.assertTrue({"content/cars/abc", "content/cars/abc/data"} <= dirs)

    def test_extract_reports_entry_count_and_target(self):
        with tmp() as out:
            _, text = capture(kspkg.cmd_extract, str(self.pkg), str(out))
        self.assertEqual(text.strip(), f"extracted {len(ITEMS)} entries to {os.path.abspath(out)}")

    def test_xor_flagged_entry_stored_at_an_odd_offset_is_decoded_from_key_phase_zero(self):
        entries = read_entries(self.pkg)[0]
        a = next(e for e in entries if e["path"].endswith("a.txt"))
        with open(self.pkg, "rb") as f:
            f.seek(a["off"])
            self.assertEqual(f.read(a["size"]), xor(FILES[CAR + "data\\a.txt"]))
        self.assertNotEqual(a["off"] % 8, 0)
        _, (files, _) = self.extract()
        self.assertEqual(files["content/cars/abc/data/a.txt"], FILES[CAR + "data\\a.txt"])

    def test_list_marks_directories_xor_entries_and_plain_entries(self):
        _, text = capture(kspkg.cmd_list, str(self.pkg))
        lines = text.splitlines()
        size = os.path.getsize(self.pkg)
        self.assertEqual(lines[0], f"key={KEY.hex()} entries={len(ITEMS)} pkgsize={size}")
        expected = []
        for name, flags, data in ITEMS:
            kind = "D" if flags & DIR else ("X" if flags & XOR else "-")
            expected.append(f"{kind} {len(data):>10} {name}")
        self.assertEqual(sorted(lines[1:]), sorted(expected))

    def test_list_follows_table_order(self):
        _, text = capture(kspkg.cmd_list, str(self.pkg))
        names = [line[13:] for line in text.splitlines()[1:]]
        self.assertEqual(names, [e["path"] for e in read_entries(self.pkg)[0]])

    def test_extract_prefix_selects_a_subtree_case_insensitively_ignoring_a_trailing_backslash(self):
        text, (files, dirs) = self.extract("CONTENT\\Cars\\ABC\\")
        self.assertTrue(text.startswith("extracted 7 entries to "), text)
        self.assertEqual(sorted(files), sorted(k.replace("\\", "/") for k in FILES if k.startswith(CAR)))
        self.assertNotIn("content/cars/abcd", dirs)

    def test_extract_prefix_can_name_a_single_file(self):
        text, (files, _) = self.extract(CAR + "plain.bin")
        self.assertTrue(text.startswith("extracted 1 entries to "), text)
        self.assertEqual(files, {"content/cars/abc/plain.bin": b"plain bytes"})

    def test_extract_prefix_matches_whole_path_components_only(self):
        text, (files, _) = self.extract("content\\cars\\ab")
        self.assertTrue(text.startswith("extracted 0 entries to "), text)
        self.assertEqual(files, {})

    def test_extract_prefix_without_any_match_still_succeeds(self):
        with tmp() as d:
            r = run_tool("kspkg.py", "extract", self.pkg, d / "out", "content\\cars\\nothing")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(r.stdout.startswith("extracted 0 entries to "), r.stdout)
            self.assertEqual(tree(d / "out"), ({}, set()))

    def test_verify_ignores_flags_and_layout(self):
        ok, text = capture(kspkg.cmd_verify, str(self.pkg), str(self.relayout))
        self.assertTrue(ok)
        self.assertEqual(text.strip(), "IDENTICAL CONTENT")

    def test_verify_reports_a_changed_file(self):
        ok, text = capture(kspkg.cmd_verify, str(self.pkg), str(self.changed))
        self.assertFalse(ok)
        self.assertEqual(text.splitlines(), ["differs:   " + CAR + "plain.bin", "0/0/1 differences"])

    def test_verify_reports_an_entry_only_in_a(self):
        ok, text = capture(kspkg.cmd_verify, str(self.pkg), str(self.missing))
        self.assertFalse(ok)
        self.assertEqual(text.splitlines(), ["only in A: content\\cars\\abcd\\other.bin", "1/0/0 differences"])

    def test_verify_reports_an_entry_only_in_b(self):
        ok, text = capture(kspkg.cmd_verify, str(self.missing), str(self.pkg))
        self.assertFalse(ok)
        self.assertEqual(text.splitlines(), ["only in B: content\\cars\\abcd\\other.bin", "0/1/0 differences"])

    def test_cli_verify_exit_codes(self):
        same = run_tool("kspkg.py", "verify", self.pkg, self.relayout)
        diff = run_tool("kspkg.py", "verify", self.pkg, self.changed)
        self.assertEqual((same.returncode, diff.returncode), (0, 1))
        self.assertIn("IDENTICAL CONTENT", same.stdout)
        self.assertIn("differs:", diff.stdout)

    def test_extract_of_a_truncated_package_raises(self):
        with tmp() as d, self.assertRaises(ValueError):
            capture(kspkg.cmd_extract, str(self.truncated), str(d / "out"))

    def test_verify_of_a_truncated_package_raises(self):
        with self.assertRaises(ValueError):
            capture(kspkg.cmd_verify, str(self.truncated), str(self.truncated))


class CommandLine(unittest.TestCase):
    def test_unknown_command_exits_2_with_the_usage_block_on_stdout(self):
        r = run_tool("kspkg.py", "frobnicate")
        self.assertEqual(r.returncode, 2)
        self.assertIn(usage_block(), r.stdout)

    def test_unknown_command_prints_only_the_usage_block(self):
        r = run_tool("kspkg.py", "frobnicate")
        self.assertEqual(r.stdout.strip(), usage_block())

    def test_no_arguments_exits_2_with_usage_on_stdout(self):
        r = run_tool("kspkg.py")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout.strip(), usage_block())

    def test_list_without_operand_exits_2_with_usage_on_stdout(self):
        r = run_tool("kspkg.py", "list")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout.strip(), usage_block())

    def test_extract_without_outdir_exits_2_with_usage_on_stdout(self):
        r = run_tool("kspkg.py", "extract", "only-one-operand.kspkg")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout.strip(), usage_block())

    def test_list_of_a_missing_file_prints_error_on_stderr_and_exits_1(self):
        with tmp() as d:
            r = run_tool("kspkg.py", "list", d / "missing.kspkg")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("error:"), r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_list_of_a_file_smaller_than_the_table_prints_error_on_stderr_and_exits_1(self):
        with tmp() as d:
            small = d / "small.kspkg"
            small.write_bytes(b"abc\n")
            r = run_tool("kspkg.py", "list", small)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("error:"), r.stderr)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
