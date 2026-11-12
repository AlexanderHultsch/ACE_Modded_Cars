"""Clone an extracted game car into an installable mod package under a new car id.

usage:
  python tools/clone_car.py build   <car_dir> <new_id> <out_dir> [--name "Display name"] [--year N] [--brand TEXT] [--variant TEXT]
                                     [--loc <stock en.cars.loc>] [--property1 NAME] [--property2 NAME] [--property3 NAME] [--no-pack]
  python tools/clone_car.py install <pkg> [--mods <mods_dir>] [--backups <dir>]

build:   copies <car_dir> (basename = old car id) to <out_dir>/content/cars/<new_id>/, replaces the old id by
         <new_id> in every file name, folder name and file content (case-insensitive, all-upper matches stay upper),
         writes <new_id>.moddedcarcontent (default --name <new id> + "_MY"; --year defaults to 2003 and --brand to BMW (the values of the BMW M3 E46 CSL, not read from the car; tune.py passes the real ones); --property1/2/3 are enum names such as
         Property1_Road, default Property1_Road / Property2_YoungTimer / Property3_ICE) and, when --loc is given,
         uiresources/localization/en.cars.loc (UTF-8 without BOM, CRLF; <car_dir> must not contain that file):
         every line of the stock file whose key starts with <old id>_ with that prefix renamed to <new_id>; the
         one line whose key ends with _preset_base gets --variant as its value (default: the stock text). Without
         --loc, or when the stock file has no line for the car, no file is written (a note is printed). Then
         self-checks and packs <out_dir>/<new_id>.kspkg (--no-pack skips the packing).
         <new_id> must have the same length as the old id (plain byte replacement, no length prefix changes),
         use only a-z, 0-9 and _, and <out_dir>/content/cars/<new_id> must not exist yet.
         All file operations use extended-length paths (see kspkg.long_path), printed paths stay normal.
install: copies <pkg> to the mods folder (default %USERPROFILE%\\Saved Games\\ACE\\mods). An existing package of the
         same name is first copied to <backups>/<name>_<YYYYmmdd_HHMMSS>.kspkg (default %USERPROFILE%\\ace_modded_cars_work\\backups).

Stdlib only. Needs schemas/acevo.desc for the .moddedcarcontent file (see tools/extract_protos.py).
"""
import datetime
import os
import pathlib
import re
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import car_json  # noqa: E402
import kspkg  # noqa: E402

DEFAULT_MODS = "%USERPROFILE%\\Saved Games\\ACE\\mods"
DEFAULT_BACKUPS = "%USERPROFILE%\\ace_modded_cars_work\\backups"
MODDED_TYPE = "moddedcarcontent"
DEFAULT_PROPERTIES = {"property_1": "Property1_Road", "property_2": "Property2_YoungTimer",
                      "property_3": "Property3_ICE"}
VARIANT_SUFFIX = "_preset_base"
LOC_PATH = ("uiresources", "localization", "en.cars.loc")


def replacer(new_id):
    up, low = new_id.upper().encode(), new_id.encode()

    def repl(m):
        g = m.group(0)
        return up if g == g.upper() else low
    return repl


def parse_args(args, flags):
    pos, opts = [], {}
    i = 0
    while i < len(args):
        if args[i].startswith("--"):
            if args[i][2:] not in flags or i + 1 >= len(args):
                raise ValueError("bad option %s" % args[i])
            opts[args[i][2:]] = args[i + 1]
            i += 2
        else:
            pos.append(args[i])
            i += 1
    return pos, opts


def validate(old_id, new_id, out_dir):
    if not re.fullmatch(r"[a-z0-9_]+", new_id):
        raise ValueError("new id %r may only contain lowercase a-z, 0-9 and underscore" % new_id)
    if len(new_id) != len(old_id):
        raise ValueError("new id %r has %d characters, it must have exactly %d (same length as %r)"
                         % (new_id, len(new_id), len(old_id), old_id))
    if new_id == old_id:
        raise ValueError("new id equals the old id %r" % old_id)
    if os.path.exists(kspkg.long_path(os.path.join(out_dir, "content", "cars", new_id))):
        raise ValueError("%s already exists, refusing to overwrite"
                         % os.path.join(out_dir, "content", "cars", new_id))


def copy_renamed(src, dst, old_id, new_id):
    pat = re.compile(re.escape(old_id.encode()), re.IGNORECASE)
    repl = replacer(new_id)

    def rename(name):
        return pat.sub(repl, name.encode()).decode()

    src, dst = kspkg.long_path(src), kspkg.long_path(dst)
    files, counts = 0, {}
    for root, dirs, names in os.walk(src):
        rel = root[len(src):].strip(os.sep)
        parts = [] if not rel else [rename(p) for p in rel.split(os.sep)]
        out = os.path.join(dst, *parts)
        os.makedirs(out, exist_ok=True)
        for d in dirs:
            os.makedirs(os.path.join(out, rename(d)), exist_ok=True)
        for n in names:
            with open(os.path.join(root, n), "rb") as f:
                data, hits = pat.subn(repl, f.read())
            target = os.path.join(out, rename(n))
            with open(target, "wb") as f:
                f.write(data)
            files += 1
            if hits:
                counts[target[len(dst):].strip(os.sep)] = hits
    return files, counts


def write_modded_content(car_root, new_id, name, brand, year, properties=None):
    fields = {"display_name": name, "year": year, "brand": brand}
    fields.update({k: (properties or {}).get(k) or v for k, v in DEFAULT_PROPERTIES.items()})
    path = os.path.join(car_root, new_id + "." + MODDED_TYPE)
    msg = car_json.message_for(path)
    sch = car_json.load_schema()
    with open(kspkg.long_path(path), "wb") as f:
        f.write(car_json.encode_msg(sch, msg, fields))
    return path, sch, msg, fields


def stock_lines(stock_loc, old_id):
    """The 'key=value' lines of the stock en.cars.loc whose key starts with <old_id>_ (case-insensitive)."""
    with open(kspkg.long_path(stock_loc), "rb") as f:
        text = f.read().decode("utf-8")
    prefix = old_id.lower() + "_"
    return [l for l in re.split(r"\r?\n", text) if l.lower().startswith(prefix) and "=" in l]


def stock_variant(stock_loc, old_id):
    """Stock text of the one line whose key ends with _preset_base, "" when there is not exactly one."""
    texts = [l.split("=", 1)[1] for l in stock_lines(stock_loc, old_id) if l.split("=", 1)[0].endswith(VARIANT_SUFFIX)]
    return texts[0] if len(texts) == 1 else ""


def write_localization(car_root, old_id, new_id, stock_loc, variant):
    """Copy the stock lines of the car under the new id; returns (path or None, notes)."""
    lines = [new_id + "_" + l[len(old_id) + 1:] for l in stock_lines(stock_loc, old_id)]
    if not lines:
        return None, ["note: %s has no line for %s, no en.cars.loc written" % (stock_loc, old_id)]
    notes = []
    base = [i for i, l in enumerate(lines) if l.split("=", 1)[0].endswith(VARIANT_SUFFIX)]
    if len(base) == 1:
        if variant is not None:
            lines[base[0]] = lines[base[0]].split("=", 1)[0] + "=" + variant
    else:
        notes.append("note: %d stock lines end with %s, the variant name is not applied" % (len(base), VARIANT_SUFFIX))
    folder = os.path.join(car_root, *LOC_PATH[:-1])
    os.makedirs(kspkg.long_path(folder), exist_ok=True)
    path = os.path.join(folder, LOC_PATH[-1])
    with open(kspkg.long_path(path), "wb") as f:
        f.write("".join(l + "\r\n" for l in lines).encode("utf-8"))
    return path, notes


def self_check(out_dir, old_id, modded):
    path, sch, msg, fields = modded
    pat = re.compile(re.escape(old_id.encode()), re.IGNORECASE)
    bad_names, bad_content = [], []
    for root, dirs, names in os.walk(kspkg.long_path(out_dir)):
        for n in dirs + names:
            if pat.search(n.encode()):
                bad_names.append(kspkg.plain_path(os.path.join(root, n)))
        for n in names:
            with open(os.path.join(root, n), "rb") as f:
                if pat.search(f.read()):
                    bad_content.append(kspkg.plain_path(os.path.join(root, n)))
    with open(kspkg.long_path(path), "rb") as f:
        decoded = car_json.decode_msg(sch, msg, f.read())
    ok_modded = decoded == fields
    print("self-check (a) old id in names: %s" % ("none" if not bad_names else "%d FOUND" % len(bad_names)))
    print("self-check (a) old id in contents: %s" % ("none" if not bad_content else "%d FOUND" % len(bad_content)))
    for p in (bad_names + bad_content)[:15]:
        print("  " + p)
    print("self-check (b) %s decodes to the written values: %s" % (os.path.basename(path), "ok" if ok_modded else "MISMATCH"))
    return not (bad_names or bad_content) and ok_modded


def build(car_dir, new_id, out_dir, name, year, brand, variant=None, stock_loc=None, properties=None, pack=True):
    """Returns the notes printed while building (empty list when there were none)."""
    car_dir = os.path.abspath(car_dir)
    out_dir = os.path.abspath(out_dir)
    old_id = os.path.basename(car_dir)
    validate(old_id, new_id, out_dir)
    if not os.path.isdir(kspkg.long_path(car_dir)):
        raise ValueError("%s is not a directory" % car_dir)
    loc_src = os.path.join(car_dir, *LOC_PATH)
    if os.path.exists(kspkg.long_path(loc_src)):
        raise ValueError("%s already exists in the source car, refusing to overwrite its localization" % loc_src)
    car_root = os.path.join(out_dir, "content", "cars", new_id)
    files, counts = copy_renamed(car_dir, car_root, old_id, new_id)
    print("copied %d files to %s" % (files, car_root))
    print("changed by replacement: %d files, %d replacements" % (len(counts), sum(counts.values())))
    for rel, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:15]:
        print("  %6d  %s" % (n, rel))
    modded = write_modded_content(car_root, new_id, name, brand, year, properties)
    if stock_loc is None:
        loc, notes = None, ["note: no stock localization given, no en.cars.loc written"]
    else:
        loc, notes = write_localization(car_root, old_id, new_id, stock_loc, variant)
    print("localization: %s" % (loc or "none"))
    for n in notes:
        print(n)
    if not self_check(out_dir, old_id, modded):
        sys.exit(1)
    if pack:
        pkg = os.path.join(out_dir, new_id + ".kspkg")
        kspkg.cmd_pack(out_dir, pkg)
        print("package: %s (%d bytes)" % (pkg, os.path.getsize(pkg)))
    return notes


def install(pkg, mods_dir, backups):
    if not pkg.lower().endswith(".kspkg") or not os.path.isfile(pkg):
        raise ValueError("%s is not an existing .kspkg file" % pkg)
    os.makedirs(mods_dir, exist_ok=True)
    target = os.path.join(mods_dir, os.path.basename(pkg))
    backup = None
    if os.path.exists(target):
        os.makedirs(backups, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = os.path.join(backups, "%s_%s.kspkg" % (os.path.basename(pkg)[:-len(".kspkg")], stamp))
        if os.path.exists(backup):
            raise ValueError("backup %s already exists, try again in a second" % backup)
        shutil.copy2(target, backup)
        if os.path.getsize(backup) != os.path.getsize(target):
            raise ValueError("backup size mismatch for %s, target left untouched" % backup)
    shutil.copyfile(pkg, target)
    if os.path.getsize(target) != os.path.getsize(pkg):
        raise ValueError("installed size mismatch for %s" % target)
    print("installed: %s (%d bytes)" % (target, os.path.getsize(target)))
    print("backup: %s" % ("%s (%d bytes)" % (backup, os.path.getsize(backup)) if backup else "no previous install"))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if cmd == "build":
            rest = [a for a in sys.argv[2:] if a != "--no-pack"]
            pos, opts = parse_args(rest, ("name", "year", "brand", "variant", "loc", "property1", "property2", "property3"))
            if len(pos) != 3:
                sys.exit(__doc__.split("\n\n")[1])
            try:
                year = int(opts.get("year", 2003))
            except ValueError:
                raise ValueError("--year must be an integer")
            props = {"property_%d" % i: opts.get("property%d" % i) for i in (1, 2, 3)}
            build(pos[0], pos[1], pos[2], opts.get("name", pos[1] + "_MY"), year,
                  opts.get("brand", "BMW"), opts.get("variant"), opts.get("loc"), props, len(rest) == len(sys.argv[2:]))
        elif cmd == "install":
            pos, opts = parse_args(sys.argv[2:], ("mods", "backups"))
            if len(pos) != 1:
                sys.exit(__doc__.split("\n\n")[1])
            install(pos[0], os.path.expandvars(opts.get("mods", DEFAULT_MODS)),
                    os.path.expandvars(opts.get("backups", DEFAULT_BACKUPS)))
        else:
            sys.exit(__doc__.split("\n\n")[1])
    except (ValueError, OSError) as e:
        sys.exit("error: %s" % e)


if __name__ == "__main__":
    main()
