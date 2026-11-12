r"""Cross-reference check for an extracted car: which files point at which content\... paths.

usage: python tools/refgraph.py <extracted_root>
  e.g. python tools/refgraph.py <work>/<car>/base
  or   python tools/refgraph.py <work>/<car>/build/<new_id>   (a tuned build: finds dangling references)

<extracted_root> contains content/cars/<car_id>/... (see tools/kspkg.py extract).
Every file is scanned as raw bytes for strings starting with content\ (or content/),
lower-cased and normalized to backslashes. Refs under content\cars\<car_id>\ of a car
present in <extracted_root> are ok/MISSING (target file or directory exists or not),
everything else is external. Prints a per-file section, then a summary with counts,
MISSING refs, external refs grouped by their first three path segments, and files
that no other file refers to.

Exit code 0 if no MISSING refs, 1 if MISSING refs are found or on a runtime error
(error: ... on stderr), 2 on bad usage (usage block on stdout).
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import kspkg  # noqa: E402

START = re.compile(rb"content[\\/]", re.IGNORECASE)
REF = re.compile(rb"content[\\/][A-Za-z0-9_.\-\\/]*", re.IGNORECASE)
PATH = re.compile(rb"[A-Za-z0-9_.\-\\/]+")


def normalize(raw):
    ref = raw.decode("ascii").lower().replace("/", "\\").rstrip(".\\")
    return ref if "\\" in ref or "." in ref else None


# A protobuf string is stored as <length varint><text>: the 1-2 bytes before `content\` give the exact end of the
# path, a plain regex would run on into following printable bytes. Raw text files have no prefix and use the regex
# fallback in find_refs.
def prefixed(data, s):
    lengths = []
    if s >= 1 and data[s - 1] < 0x80:
        lengths.append(data[s - 1])
    if s >= 2 and data[s - 2] >= 0x80 and data[s - 1] < 0x80:
        lengths.append((data[s - 1] << 7) | (data[s - 2] & 0x7F))
    for n in lengths:
        raw = data[s:s + n]
        if n > len("content\\") and len(raw) == n and PATH.fullmatch(raw):
            return raw
    return None


def find_refs(data):
    exact, fallback = set(), set()
    for m in START.finditer(data):
        s = m.start()
        raw = prefixed(data, s)
        if raw is not None:
            ref = normalize(raw)
            if ref:
                exact.add(ref)
        else:
            ref = normalize(REF.match(data, s).group())
            if ref:
                fallback.add(ref)
    return exact, fallback - exact


def scan(root):
    files, dirs, refs, fallback = [], set(), {}, {}
    for p in sorted(root.rglob("*")):
        rel = "\\".join(p.relative_to(root).parts)
        if p.is_dir():
            dirs.add(rel.lower())
        elif p.is_file():
            files.append(rel)
            exact, fb = find_refs(p.read_bytes())
            refs[rel] = exact | fb
            fallback[rel] = fb
    return files, dirs, refs, fallback


def classify(ref, car_ids, exists):
    parts = ref.split("\\")
    if len(parts) >= 3 and parts[:2] == ["content", "cars"] and parts[2] in car_ids:
        return "ok" if ref in exists else "MISSING"
    return "external"


def main():
    if len(sys.argv) != 2 or not pathlib.Path(kspkg.long_path(sys.argv[1])).is_dir():
        print(__doc__.split("\n\n")[1])
        sys.exit(2)
    root = pathlib.Path(kspkg.long_path(sys.argv[1]))
    try:
        cars = root / "content" / "cars"
        car_ids = {p.name.lower() for p in cars.iterdir() if p.is_dir()} if cars.is_dir() else set()
        files, dirs, refs, fallback = scan(root)
    except OSError as e:
        sys.exit("error: %s" % e)
    exists = dirs | {f.lower() for f in files}
    status = {r: classify(r, car_ids, exists) for r in set().union(*refs.values())}
    exact = set().union(*(refs[rel] - fallback[rel] for rel in files))
    fb_refs = set().union(*fallback.values()) - exact

    print("== per-file references ==")
    for rel in sorted(files, key=str.lower):
        if refs[rel]:
            print(rel)
            for r in sorted(refs[rel]):
                print(f"  {status[r]:<8} {r}")

    by_ref = {}
    for rel, rs in refs.items():
        for r in rs:
            by_ref.setdefault(r, set()).add(rel)
    count = {s: sum(1 for v in status.values() if v == s) for s in ("ok", "MISSING", "external")}

    print()
    print("== summary ==")
    print(f"files scanned: {len(files)}, files with refs: {sum(1 for rs in refs.values() if rs)}, "
          f"distinct refs: {len(status)} (ok {count['ok']}, missing {count['MISSING']}, "
          f"external {count['external']}, fallback {len(fb_refs)})")

    print()
    print(f"MISSING refs ({count['MISSING']}):")
    for r in sorted(r for r, s in status.items() if s == "MISSING"):
        print(f"  {r}")
        for rel in sorted(by_ref[r], key=str.lower):
            print(f"    in {rel}")

    groups = {}
    for r, s in status.items():
        if s == "external":
            groups.setdefault("\\".join(r.split("\\")[:3]), set()).add(r)
    print()
    print(f"EXTERNAL refs by group ({len(groups)} groups):")
    for g in sorted(groups):
        users = set().union(*(by_ref[r] for r in groups[g]))
        print(f"  {g}  refs={len(groups[g])} files={len(users)}")

    print()
    print(f"FALLBACK refs ({len(fb_refs)}):")
    for r in sorted(fb_refs):
        print(f"  {r}")
        for rel in sorted((f for f in files if r in fallback[f]), key=str.lower):
            print(f"    in {rel}")

    referenced = {r for rel, rs in refs.items() for r in rs if r != rel.lower()}
    unref = sorted((f for f in files if f.lower() not in referenced), key=str.lower)
    print()
    print(f"Files never referenced by any other file ({len(unref)}):")
    for f in unref:
        print(f"  {f}")

    sys.exit(1 if count["MISSING"] else 0)


if __name__ == "__main__":
    main()
