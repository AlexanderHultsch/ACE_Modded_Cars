"""Build the in-game test kit for the Hina's Drift Club E46: five package variants plus one loose tree.

usage:
  python tools/make_testkit.py <car_root> <sha256_file> <out_dir>

<car_root> is a directory containing content/cars/hdc_bmw_e46_01/ (e.g. hdc_1.4/extracted/e46).
<sha256_file> holds the sha256 of the original E46 package in sha256sum format (spec/e46_package.sha256).
<out_dir> must not exist. The spec is spec/e46_levers.json and the profiles are spec/profiles/<name>.json,
both resolved relative to the repo.
Each entry of VARIANTS is applied to a copy of <car_root> (tools/tune.py), packed (tools/kspkg.py) to
<out_dir>/<name>/hinas_drift_club_e46_v1.4.kspkg and described in <out_dir>/<name>/CHANGES.txt.
Checks, printed as they pass; a failing check exits 1 and removes <out_dir>:
  - the repack of the untouched tree has the sha256 from <sha256_file>
  - for every other variant the package entries whose content differs from the untouched repack
    (printed as `changed: <path>`) are exactly the files that differ between <car_root> and the tuned copy
Then <out_dir>/SHA256SUMS.txt (sha256sum format) is written and <out_dir>/F_loose_unchanged/content is
a plain copy of <car_root>/content.
"""
import hashlib
import pathlib
import shutil
import sys
import tempfile

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import kspkg  # noqa: E402
import tune  # noqa: E402

SPEC = ROOT / "spec" / "e46_levers.json"
PROFILES = ROOT / "spec" / "profiles"
PKG_NAME = "hinas_drift_club_e46_v1.4.kspkg"
LOOSE = "F_loose_unchanged"
LOOSE_NOTE = ("Loose unpacked tree, no kspkg. Tests whether the game loads cars from "
              "mods/content/cars/<id>/ without packing.")

VARIANTS = [
    {"name": "A_unchanged", "profile": None, "roles": None,
     "description": "Repack of the untouched tree. Must be byte-identical to the original package."},
    {"name": "B1_limiter_file", "profile": "test_limiter4000", "roles": ["file"],
     "description": "Rev limiter 4000 in the separate carengine file only."},
    {"name": "B2_limiter_inline", "profile": "test_limiter4000", "roles": ["inline", "devcopy"],
     "description": "Rev limiter 4000 in the copies inside cardata.car and hdc_bmw_e46_01.car only."},
    {"name": "C_torque_half", "profile": "test_torque_half", "roles": None,
     "description": "Engine torque x0.5 (curve file)."},
    {"name": "D_drift_v0", "profile": "drift_v0", "roles": None,
     "description": "First drift tune: all copies of diff lock/preload/limits set, torque x1.2. "
                    "Inferred meanings."},
]


def read_sha(path):
    words = pathlib.Path(path).read_text(encoding="utf-8").split()
    sha = words[0].lower() if words else ""
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError(f"no sha256 in {path}")
    return sha


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree(root):
    return {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}


def changed_files(a, b):
    ta, tb = tree(a), tree(b)
    if set(ta) != set(tb):
        raise ValueError("tuned copy has a different file set than " + str(a))
    return sorted(rel for rel in ta if ta[rel].read_bytes() != tb[rel].read_bytes())


def entry_name(rel):
    return rel.replace("/", "\\").lower()


def build_variant(variant, spec, car_root, pkg):
    if variant["profile"] is None:
        kspkg.cmd_pack(car_root, pkg)
        return ["no changes"], []
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "tree"
        profile = tune.load_spec(PROFILES / (variant["profile"] + ".json"))
        lines = tune.apply(spec, profile, car_root, out, variant["roles"])
        files = changed_files(car_root, out)
        kspkg.cmd_pack(out, pkg)
        return lines, files


def build(spec, car_root, want, out_dir):
    results, base = [], None
    for v in VARIANTS:
        print(f"== {v['name']}: {v['description']}")
        pkg_dir = out_dir / v["name"]
        pkg_dir.mkdir()
        pkg = pkg_dir / PKG_NAME
        lines, files = build_variant(v, spec, car_root, pkg)
        sha = file_sha256(pkg)
        if v["profile"] is None:
            if sha != want:
                raise ValueError(f"{v['name']}: sha256 {sha} is not the original package's {want}")
            print(f"ok: {v['name']} sha256 equals the original package")
            base = kspkg._contents(pkg)
            changed = []
        else:
            got = kspkg._contents(pkg)
            changed = sorted(k for k in set(base) | set(got) if base.get(k) != got.get(k))
            expected = sorted(entry_name(rel) for rel in files)
            if changed != expected:
                raise ValueError(f"{v['name']}: package entries that differ from A {changed} "
                                 f"are not the files the profile changed {expected}")
            for e in changed:
                print(f"changed: {e}")
        (pkg_dir / "CHANGES.txt").write_text(v["description"] + "\n\n" + "\n".join(lines) + "\n",
                                             encoding="utf-8")
        results.append(dict(name=v["name"], package=pkg, size=pkg.stat().st_size, sha256=sha,
                            changed=changed))
    sums = "".join(f"{r['sha256']}  {r['package'].relative_to(out_dir).as_posix()}\n" for r in results)
    (out_dir / "SHA256SUMS.txt").write_bytes(sums.encode("utf-8"))
    loose = out_dir / LOOSE
    shutil.copytree(car_root / "content", loose / "content")
    (loose / "CHANGES.txt").write_text(LOOSE_NOTE + "\n", encoding="utf-8")
    print(f"== {LOOSE}: {LOOSE_NOTE}")
    results.append(dict(name=LOOSE, package=None, size=None, sha256=None, changed=[]))
    return results


def build_variants(car_root, sha256_file, out_dir):
    car_root, out_dir = pathlib.Path(car_root), pathlib.Path(out_dir)
    if out_dir.exists():
        raise ValueError(f"output already exists: {out_dir}")
    want = read_sha(sha256_file)
    spec = tune.load_spec(SPEC)
    out_dir.mkdir(parents=True)
    try:
        return build(spec, car_root, want, out_dir)
    except BaseException:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise


def summary(results):
    rows = [("variant", "size", "sha256", "changed")]
    for r in results:
        loose = r["package"] is None
        rows.append((r["name"], "-" if loose else str(r["size"]),
                     "-" if loose else r["sha256"][:12], "-" if loose else str(len(r["changed"]))))
    widths = [max(len(row[i]) for row in rows) for i in range(4)]
    return "\n".join("  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip() for row in rows)


def main():
    a = sys.argv[1:]
    if len(a) != 3:
        print(__doc__)
        sys.exit(2)
    try:
        results = build_variants(*a)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    print(summary(results))


if __name__ == "__main__":
    main()
