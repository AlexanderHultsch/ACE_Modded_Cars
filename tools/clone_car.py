"""Clone an extracted game car into an installable mod package under a new car id.

usage:
  python tools/clone_car.py build   <car_dir> <new_id> <out_dir> [--name "Display name"] [--year N] [--brand TEXT] [--variant TEXT] [--no-pack]
  python tools/clone_car.py install <pkg> [--mods <mods_dir>] [--backups <dir>]

build:   copies <car_dir> (basename = old car id) to <out_dir>/content/cars/<new_id>/, replaces the old id by
         <new_id> in every file name, folder name and file content (case-insensitive, all-upper matches stay upper),
         writes <new_id>.moddedcarcontent and uiresources/localization/en.cars.loc (variant and trim names,
         UTF-8 without BOM, CRLF; <car_dir> must not contain that file, default --variant "E46 CSL Drift"), self-checks and packs <out_dir>/<new_id>.kspkg
         (--no-pack skips the packing).
         <new_id> must have the same length as the old id (plain byte replacement, no length prefix changes),
         use only a-z, 0-9 and _, and <out_dir>/content/cars/<new_id> must not exist yet.
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
    if os.path.exists(os.path.join(out_dir, "content", "cars", new_id)):
        raise ValueError("%s already exists, refusing to overwrite"
                         % os.path.join(out_dir, "content", "cars", new_id))


def copy_renamed(src, dst, old_id, new_id):
    pat = re.compile(re.escape(old_id.encode()), re.IGNORECASE)
    repl = replacer(new_id)

    def rename(name):
        return pat.sub(repl, name.encode()).decode()

    files, counts = 0, {}
    for root, dirs, names in os.walk(src):
        rel = os.path.relpath(root, src)
        parts = [] if rel == "." else [rename(p) for p in rel.split(os.sep)]
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
                counts[os.path.relpath(target, dst)] = hits
    return files, counts


def write_modded_content(car_root, new_id, name, brand, year):
    fields = {"display_name": name, "year": year, "brand": brand, "property_1": "Property1_Road",
              "property_2": "Property2_YoungTimer", "property_3": "Property3_ICE"}
    path = os.path.join(car_root, new_id + "." + MODDED_TYPE)
    msg = car_json.message_for(path)
    sch = car_json.load_schema()
    with open(path, "wb") as f:
        f.write(car_json.encode_msg(sch, msg, fields))
    return path, sch, msg, fields


def write_localization(car_root, new_id, variant):
    lines = ["%s_m3_e46_csl_preset_base=%s" % (new_id, variant),
             "%s_m3_e46_csl_visual_1=Single Colour" % new_id,
             "%s_EXT_SKIN=Body Colour" % new_id,
             "%s_RIM=Wheel Colour" % new_id]
    folder = os.path.join(car_root, "uiresources", "localization")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "en.cars.loc")
    with open(path, "wb") as f:
        f.write("".join(l + "\r\n" for l in lines).encode("utf-8"))
    return path


def self_check(out_dir, old_id, modded):
    path, sch, msg, fields = modded
    pat = re.compile(re.escape(old_id.encode()), re.IGNORECASE)
    bad_names, bad_content = [], []
    for root, dirs, names in os.walk(out_dir):
        for n in dirs + names:
            if pat.search(n.encode()):
                bad_names.append(os.path.join(root, n))
        for n in names:
            with open(os.path.join(root, n), "rb") as f:
                if pat.search(f.read()):
                    bad_content.append(os.path.join(root, n))
    with open(path, "rb") as f:
        decoded = car_json.decode_msg(sch, msg, f.read())
    ok_modded = decoded == fields
    print("self-check (a) old id in names: %s" % ("none" if not bad_names else "%d FOUND" % len(bad_names)))
    print("self-check (a) old id in contents: %s" % ("none" if not bad_content else "%d FOUND" % len(bad_content)))
    for p in (bad_names + bad_content)[:15]:
        print("  " + p)
    print("self-check (b) %s decodes to the written values: %s" % (os.path.basename(path), "ok" if ok_modded else "MISMATCH"))
    return not (bad_names or bad_content) and ok_modded


def build(car_dir, new_id, out_dir, name, year, brand, variant, pack=True):
    car_dir = os.path.abspath(car_dir)
    out_dir = os.path.abspath(out_dir)
    old_id = os.path.basename(car_dir)
    validate(old_id, new_id, out_dir)
    if not os.path.isdir(car_dir):
        raise ValueError("%s is not a directory" % car_dir)
    loc_src = os.path.join(car_dir, "uiresources", "localization", "en.cars.loc")
    if os.path.exists(loc_src):
        raise ValueError("%s already exists in the source car, refusing to overwrite its localization" % loc_src)
    car_root = os.path.join(out_dir, "content", "cars", new_id)
    files, counts = copy_renamed(car_dir, car_root, old_id, new_id)
    print("copied %d files to %s" % (files, car_root))
    print("changed by replacement: %d files, %d replacements" % (len(counts), sum(counts.values())))
    for rel, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:15]:
        print("  %6d  %s" % (n, rel))
    modded = write_modded_content(car_root, new_id, name, brand, year)
    print("localization: %s" % write_localization(car_root, new_id, variant))
    if not self_check(out_dir, old_id, modded):
        sys.exit(1)
    if pack:
        pkg = os.path.join(out_dir, new_id + ".kspkg")
        kspkg.cmd_pack(out_dir, pkg)
        print("package: %s (%d bytes)" % (pkg, os.path.getsize(pkg)))


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
            pos, opts = parse_args(rest, ("name", "year", "brand", "variant"))
            if len(pos) != 3:
                sys.exit(__doc__.split("\n\n")[1])
            try:
                year = int(opts.get("year", 2003))
            except ValueError:
                raise ValueError("--year must be an integer")
            build(pos[0], pos[1], pos[2], opts.get("name", "Alex E46 Drift"), year, opts.get("brand", "BMW"),
                  opts.get("variant", "E46 CSL Drift"), len(rest) == len(sys.argv[2:]))
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
