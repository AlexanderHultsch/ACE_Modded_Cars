"""Apply named levers (every redundant copy of a car value) from a JSON spec to a copy of an extracted car.

usage:
  python tools/tune.py check <spec> <car_root> [<profile>]
  python tools/tune.py apply <spec> <profile> <car_root> -o <out_root> [--roles r1,r2,...]

<car_root> is a directory containing content/cars/<car_id>/ (e.g. hdc_1.4/extracted/e46).
Spec: {"car_id", "levers": [{"id", "meaning", "confidence", "kind": f32|int|curve_scale, "baseline",
  "targets": [{"file", "path", "role": file|inline|devcopy|setup|limits, "kind" (optional)}],
  "within": {"min": <lever id>, "max": <lever id>} (optional)}]}. `file` is relative to
content/cars/<car_id>/. A curve_scale lever has no baseline or path: its targets are {"file", "role"}
and the operation is pbedit.scale_curve_counted on field 10.
Profile: {"name", "description", "values": {<lever id>: number}, "scale": {<lever id>: factor}}.

`check` prints one line per target (lever, role, file, path, current value, ok|MISMATCH|MISSING),
the expected value being the lever baseline overridden by the profile's `values`, then one line per
lever whose targets disagree and a count line. Exit 0 iff everything is ok, 1 otherwise.
`apply` copies the whole tree to <out_root> (which must not exist), sets every target of every lever
in the profile (restricted to --roles when given) and prints one line per change. A profile entry
with no target left under --roles is skipped with a `SKIPPED:` line; it is an error only when nothing
at all is left to apply. Then a WARNING line for each changed lever whose new value lies outside the
out tree's min/max limit levers. Exit 0 even with skips or warnings. Errors are printed as
`error: ...` (exit 1); bad usage exits 2.
"""
import json
import pathlib
import shutil
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pbedit  # noqa: E402


def load_spec(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def car_dir(spec, root):
    return pathlib.Path(root) / "content" / "cars" / spec["car_id"]


def target_kind(lever, target):
    return target.get("kind", lever["kind"])


def curve_peak(buf):
    points = [f for f in pbedit.parse(buf).fields if f.num == 1]
    vals = [struct.unpack("<f", g.payload)[0] for p in points for g in p.message().fields
            if g.num == 10 and g.wt == 5]
    if not vals:
        raise ValueError("no field 10 values in curve points")
    return max(vals)


def read_number(buf, kind, path):
    wt, v = pbedit.get_field(buf, path)
    text = pbedit.format_value(wt, v).replace("\n", " ")
    if kind == "int" and wt == 0:
        return text, v
    if kind == "f32" and wt == 5:
        return text, struct.unpack("<f", v)[0]
    return text, None


def plan_profile(spec, profile, roles=None):
    levers = {lv["id"]: lv for lv in spec["levers"]}
    known = {t["role"] for lv in spec["levers"] for t in lv["targets"]}
    if roles is not None:
        bad = [r for r in roles if r not in known]
        if bad:
            raise ValueError(f"unknown role: {','.join(bad)}")
    plan, skipped = [], []
    for section, curve in (("values", False), ("scale", True)):
        for lid, val in profile.get(section, {}).items():
            lever = levers.get(lid)
            if lever is None:
                raise ValueError(f"unknown lever: {lid}")
            if (lever["kind"] == "curve_scale") != curve:
                raise ValueError(f"lever {lid} does not belong in profile '{section}'")
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise ValueError(f"{lid}: not a number: {val!r}")
            targets = [t for t in lever["targets"] if roles is None or t["role"] in roles]
            if not targets:
                skipped.append(f"SKIPPED: {lid}: no target for roles {','.join(roles)}")
                continue
            if not curve:
                for t in targets:
                    if target_kind(lever, t) == "int" and not float(val).is_integer():
                        raise ValueError(f"{lid}: {t['file']} {t['path']} is an int target, "
                                         f"value {val} is not integral")
            plan.append((lever, val, targets))
    if skipped and not plan:
        raise ValueError("no profile entry has a target for roles " + ",".join(roles))
    return plan, skipped


def check(spec, root, profile=None):
    plan_profile(spec, profile or {})
    values = (profile or {}).get("values", {})
    base = car_dir(spec, root)
    lines, numbers, bad = [], {}, False
    for lever in spec["levers"]:
        for t in lever["targets"]:
            head = f"{lever['id']}  {t['role']}  {t['file']}  {t.get('path', '-')}"
            try:
                buf = (base / t["file"]).read_bytes()
                if lever["kind"] == "curve_scale":
                    peak = curve_peak(buf)
                    text, num, status = "peak %.9g" % peak, peak, "ok"
                else:
                    kind = target_kind(lever, t)
                    text, num = read_number(buf, kind, t["path"])
                    want = values.get(lever["id"], lever["baseline"])
                    if num is None:
                        status = "MISMATCH"
                    else:
                        status = "ok" if num == (f32(want) if kind == "f32" else want) else "MISMATCH"
            except OSError:
                text, num, status = "-", None, "MISSING"
            except ValueError:
                text, num, status = "-", None, ("MISMATCH" if lever["kind"] == "curve_scale" else "MISSING")
            bad |= status != "ok"
            if num is not None:
                numbers.setdefault(lever["id"], set()).add(num)
            lines.append(f"{head}  {text}  {status}")
    for lever in spec["levers"]:
        if len(numbers.get(lever["id"], ())) > 1:
            bad = True
            lines.append(f"INCONSISTENT {lever['id']}")
    return lines, not bad


def summary(lines):
    rows = [ln for ln in lines if not ln.startswith("INCONSISTENT ")]
    n_ok = sum(ln.endswith("  ok") for ln in rows)
    n_mis = sum(ln.endswith("  MISMATCH") for ln in rows)
    n_miss = sum(ln.endswith("  MISSING") for ln in rows)
    return f"{len(rows)} targets, {n_ok} ok, {n_mis} mismatch, {n_miss} missing"


def get_buf(bufs, base, rel):
    if rel not in bufs:
        try:
            bufs[rel] = (base / rel).read_bytes()
        except OSError:
            raise ValueError(f"cannot read {rel}")
    return bufs[rel]


def limit_value(spec, bufs, base, lid):
    lever = next(lv for lv in spec["levers"] if lv["id"] == lid)
    t = next((t for t in lever["targets"] if t["role"] == "limits"), None)
    if t is None:
        return None
    return read_number(get_buf(bufs, base, t["file"]), target_kind(lever, t), t["path"])[1]


def apply(spec, profile, root, out_root, roles=None):
    out_root = pathlib.Path(out_root)
    if out_root.exists():
        raise ValueError(f"output already exists: {out_root}")
    plan, skipped = plan_profile(spec, profile, roles)
    base = car_dir(spec, root)
    bufs, edited, lines = {}, set(), []
    for lever, val, targets in plan:
        for t in targets:
            rel, path = t["file"], t.get("path", "-")
            buf = get_buf(bufs, base, rel)
            try:
                if lever["kind"] == "curve_scale":
                    new, count = pbedit.scale_curve_counted(buf, float(val))
                    lines.append(f"{lever['id']}  {t['role']}  {rel}  scaled {count} points by {val:g}")
                else:
                    old = pbedit.format_value(*pbedit.get_field(buf, path)).replace("\n", " ")
                    new = pbedit.set_value(buf, path, target_kind(lever, t), val)
                    cur = pbedit.format_value(*pbedit.get_field(new, path)).replace("\n", " ")
                    lines.append(f"{lever['id']}  {t['role']}  {rel}  {path}  {old} -> {cur}")
            except ValueError as e:
                raise ValueError(f"{rel}: {e}")
            bufs[rel] = new
            edited.add(rel)
    lines.extend(skipped)
    for lever, val, targets in plan:
        within = lever.get("within")
        if not within:
            continue
        lo = limit_value(spec, bufs, base, within["min"])
        hi = limit_value(spec, bufs, base, within["max"])
        v = f32(val) if lever["kind"] == "f32" else val
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            lines.append(f"WARNING: {lever['id']} {val:g} is outside {within['min']} {lo:g} .. "
                         f"{within['max']} {hi:g}")
    shutil.copytree(root, out_root)
    dest = car_dir(spec, out_root)
    for rel in sorted(edited):
        (dest / rel).write_bytes(bufs[rel])
    return lines


def parse_apply_args(args):
    pos, out, roles = [], None, None
    i = 0
    while i < len(args):
        if args[i] in ("-o", "--roles") and i + 1 < len(args):
            if args[i] == "-o":
                out = args[i + 1]
            else:
                roles = args[i + 1].split(",")
            i += 2
        else:
            pos.append(args[i])
            i += 1
    return pos, out, roles


def cmd_check(spec_path, root, profile_path=None):
    spec = load_spec(spec_path)
    profile = load_spec(profile_path) if profile_path else None
    lines, ok = check(spec, root, profile)
    print("\n".join(lines))
    print(summary(lines))
    return 0 if ok else 1


def cmd_apply(spec_path, profile_path, root, out_root, roles):
    lines = apply(load_spec(spec_path), load_spec(profile_path), root, out_root, roles)
    print("\n".join(lines))


def main():
    a = sys.argv[1:]
    cmd = a[0] if a else None
    try:
        if cmd == "check" and len(a) in (3, 4):
            sys.exit(cmd_check(*a[1:]))
        elif cmd == "apply":
            pos, out, roles = parse_apply_args(a[1:])
            if len(pos) != 3 or out is None:
                print(__doc__)
                sys.exit(2)
            cmd_apply(*pos, out, roles)
        else:
            print(__doc__)
            sys.exit(2)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
