"""Settings engine of the tuner: read defaults, keep the chosen values, build and install the tuned car.

usage:
  python tools/tune.py cars     [--tested] [--game <content.kspkg>] [--mods <dir>] [--work <dir>]
  python tools/tune.py init     [--car ID] [--game <content.kspkg>] [--work <dir>]
  python tools/tune.py defaults [--car ID] [--hidden] [--work <dir>]
  python tools/tune.py set      <id> <value> [--car ID] [--work <dir>]
  python tools/tune.py unset    <id> [--car ID] [--work <dir>]
  python tools/tune.py show     [--car ID] [--work <dir>]
  python tools/tune.py apply    [--car ID] [--new-id ID] [--no-install] [--mods <dir>] [--work <dir>]
  python tools/tune.py doc      [--car ID | --all] [--out <file>] [--work <dir>]

--car ID picks any car of the game (default: the default car of tuner/cars.json); an id that is not a game car is
rejected with the closest matches. The game's cars come from system/cars.table, read once and cached in
<work>/cars_index.json (id, display_name, brand, year of every car). When there is no cache and the game package is not
reachable, the tested cars of tuner/cars.json (a default car, a "note" and a list of {id, label}) are the only cars.
Cars outside that list are untested: init, apply and doc print "note: <id> is not in the tested list; results are
unverified". <car> below is the chosen stock car id, <new_id> its tuned copy (default: ax_ plus the stock id without
its ks_, e.g. ks_bmw_m3_e46_csl -> ax_bmw_m3_e46_csl; other prefixes: ax plus the id without its first two
characters; same length as the stock id).
Work folder layout: <work>/<car>/{base, build/<new_id>, tune_state.json, stock_info.json, defaults.json} per car,
shared <work>/backups, <work>/stock_loc/en.cars.loc and <work>/cars_index.json. The first command that runs moves the
old single-car layout (<work>/base, build, tune_state.json, stock_info.json, defaults.json) into <work>/<default car>
and prints what moved.

cars:    table of every game car sorted by display name: id, display name (stock_info.json when extracted, else the
          game's name), extracted yes/no, tested yes/no (listed in tuner/cars.json), new id, installed yes/no
          (<new_id>.kspkg in the mods folder), size of the extracted stock car. --tested lists only the tested cars.
          Without the cache and the game package (--game, default the Steam install) only the tested cars are
          listed, with a note.
init:    extracts the stock car from the game package into <work>/<car>/base (skipped when already there), the game's
          stock en.cars.loc into <work>/stock_loc once, and writes <work>/<car>/stock_info.json (car id, display name,
          brand, year, property_1..3 as enum names from the game's system/cars.table, variant_name = stock text of the
          car's *_preset_base line in en.cars.loc or "") when missing or incomplete. The other commands create that file
          on first need; without it the name is derived from the car's preset.
defaults: reads every applicable setting of tuner/catalogue.json from <work>/<car>/base, prints the table and writes
          <work>/<car>/defaults.json. A setting is applicable when all its required targets resolve for the car; the
          others are hidden: their number is printed, --hidden lists each with its reason. When the copies of a value of
          an applicable setting disagree in the stock data, they are listed in the section "copies differ in the stock
          data" (the default shown is the value of the first required target); that is not an error.
set/unset/show: edit and print <work>/<car>/tune_state.json ({setting id: value}). show lists applicable settings
          only, set refuses a setting that is not applicable to the car. Entries of the state whose id is not in the
          catalogue are ignored with a warning (show, apply) and kept in the file.
apply:    always starts from the pristine <work>/<car>/base: clones the car under the new id into
          <work>/<car>/build/<new_id>, writes every changed setting into ALL its resolved target files, packs
          <new_id>.kspkg and (unless --no-install) installs it to the mods folder (default
          %USERPROFILE%\\Saved Games\\ACE\\mods) with a backup of the previous package in <work>/backups. Only changed
          settings must be applicable. For a car other than the default car, the stock info must exist.
doc:      writes a Markdown reference of the settings applicable to the car with their defaults from
          <work>/<car>/base to <file> (default docs/settings/<car>.md in the repository); the car must be extracted.
          --all writes that file for every tested car of tuner/cars.json, extracting the cars that are not extracted
          yet first (--car and --out cannot be combined with --all).
<work> defaults to %USERPROFILE%\\ace_modded_cars_work. Writes nothing outside <work> and the mods folder. File
operations on car trees use extended-length paths (kspkg.long_path), so deep Windows paths work.

Catalogue field paths (inside the JSON that car_json decodes): dot-separated names, name[3] = list element by index,
name[key=VALUE] = the list element whose field key equals VALUE, e.g. gears[1].ratio or
car_specs.items[key=CarSpecs_KeyEnum_POWER].value. A missing last field reads as the proto3 default (flagged absent)
and is created on write; missing objects on the way are created on write; a missing list element is an error.

Catalogue target files ("file" of a target and of curve_from) are roles, resolved per car and case-insensitively from
its .car manifest: @engine, @drivetrain, @gearbox, @brakes (engine_path ... brakes_path), @setup (stock_setup), @limits
(setupLimits), @car (the .car file in data; with several, the one that decodes as CarData and has engine_path),
@mech_preset (first presets/*.mechanicalcarpreset in sorted order), @turbo[N] (the file named by turbos_to_load[N] of
the engine file). A target with "optional": true is written when it resolves and skipped otherwise; every other
target is required. A setting is applicable to a car when all its required targets resolve (an absent last field
counts as resolved, a missing object or list element on the way does not). "needs" is a list of further targets that
must resolve for the setting to be applicable but are never written and not compared. "hide_if_absent": true hides
the setting when the last field of all its required targets is absent in the stock data. meta settings: variant_name,
applicable only when the stock car has a variant name. The car name is not a setting: apply always names the tuned
car "<stock display name>_MY" (stock_info.json, else the car's mechanical preset), so it is listed next to the stock car.

Stdlib only. Needs schemas/acevo.desc (see tools/extract_protos.py).
"""
import contextlib
import difflib
import io
import json
import math
import os
import pathlib
import re
import shutil
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import car_json  # noqa: E402
import clone_car  # noqa: E402
import kspkg  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
CATALOGUE = REPO / "tuner" / "catalogue.json"
CARS_JSON = REPO / "tuner" / "cars.json"
DEFAULT_WORK = "%USERPROFILE%\\ace_modded_cars_work"
DEFAULT_GAME = "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Assetto Corsa EVO\\content.kspkg"
OLD_LAYOUT = ("base", "build", "tune_state.json", "stock_info.json", "defaults.json")
DOC_DIR = REPO / "docs" / "settings"
DOC_INTRO = (
    "This file lists the tuner settings (`tuner/catalogue.json`) of the %s (car id `%s`) with their defaults. It is "
    "generated by `python tools/tune.py doc --car %s`, do not edit it by hand. The defaults are read from the stock "
    "car in the game. Applicable settings only: settings this car does not have are hidden. \"unverified\" means the "
    "meaning is guessed from the field name and not confirmed in the game. The display values change only text. "
    "Setting limits is not yet tested in the game.")
DOC_NOT_COVERED = (
    "tyre model and compound data (shared game files, not in the car folder)", "aero",
    "electronics (TC/ABS)", "bump stops and caster", "damper limits", "engine map (`maps[]`) values",
    "further turbo settings (lag, wastegate, controllers)")
CARS_TABLE = "system\\cars.table"
STOCK_LOC = "uiresources\\localization\\en.cars.loc"
STOCK_PROPERTIES = ("property_1", "property_2", "property_3")
CLONE_YEAR, CLONE_BRAND = 2003, "BMW"
CAR_NAME_SUFFIX = "_MY"
KINDS = ("value", "curve_scale", "meta")
VALUE_TYPES = ("int", "float", "string", "enum")
HANDLERS = ("variant_name",)
REQUIRED = ("id", "group", "label", "kind", "type", "unit", "description", "verified")
MANIFEST_ROLES = {"engine": "engine_path", "drivetrain": "drivetrain_path", "gearbox": "gearbox_path",
                  "brakes": "brakes_path", "setup": "stock_setup", "limits": "setupLimits"}
ROLE = re.compile(r"@(car|mech_preset|%s|turbo\[\d+\])" % "|".join(MANIFEST_ROLES))

_schema = []


def schema():
    if not _schema:
        _schema.append(car_json.load_schema())
    return _schema[0]


def work_dir(arg=None):
    path = os.path.abspath(os.path.expandvars(arg or DEFAULT_WORK))
    if "%" in path:
        raise ValueError("cannot expand the work directory %r" % (arg or DEFAULT_WORK))
    return path


def inside(root, path):
    root, path = os.path.realpath(root), os.path.realpath(path)
    if os.path.commonpath([root, path]) != root:
        raise ValueError("%s is not inside %s" % (path, root))
    return path


def remove_tree(work, path):
    if inside(work, path) == os.path.realpath(work):
        raise ValueError("refusing to remove the work directory itself")
    shutil.rmtree(kspkg.long_path(path))


def load_cars(path=CARS_JSON):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cars = data.get("cars") if isinstance(data, dict) else None
    if not isinstance(cars, list) or not cars or not isinstance(data.get("default"), str):
        raise ValueError("%s: needs default and a list of cars" % path)
    ids = []
    for c in cars:
        if not (isinstance(c, dict) and isinstance(c.get("id"), str) and re.fullmatch(r"[a-z0-9_]+", c["id"])
                and isinstance(c.get("label"), str) and c["label"]):
            raise ValueError("%s: every car needs an id (a-z, 0-9, _) and a label" % path)
        ids.append(c["id"])
    if len(set(ids)) != len(ids) or data["default"] not in ids:
        raise ValueError("%s: car ids must be unique and include the default" % path)
    return data


def pick_car(cars, car_id=None, index=None):
    car_id = car_id or cars["default"]
    if index is None:
        known = [c["id"] for c in cars["cars"]]
        if car_id not in known:
            raise ValueError("unknown car %r, the car list of the game is not available, the tested cars "
                             "(tuner/cars.json) are: %s" % (car_id, ", ".join(known)))
    else:
        known = [c["id"] for c in index]
        if car_id not in known:
            close = difflib.get_close_matches(car_id, known, n=5, cutoff=0.6)
            raise ValueError("unknown car %r, %s" % (car_id, "close matches: " + ", ".join(close) if close else
                                                     "the game has %d cars, tune.py cars lists them" % len(known)))
    return car_id


def new_id_for(car_id):
    return "ax_" + car_id[3:] if car_id.startswith("ks_") else "ax" + car_id[2:]


def car_work(work, car_id):
    return os.path.join(work, car_id)


def base_dir(work, car_id):
    return os.path.join(car_work(work, car_id), "base")


def build_dir(work, car_id):
    return os.path.join(car_work(work, car_id), "build")


def stock_loc_path(work):
    return os.path.join(work, "stock_loc", "en.cars.loc")


def migrate_old_layout(work, default_car):
    """Move the single-car layout of the first version into <work>/<default car>; returns the moved names."""
    dst = car_work(work, default_car)
    if not os.path.isdir(kspkg.long_path(os.path.join(work, "base"))) or os.path.exists(kspkg.long_path(dst)):
        return []
    os.makedirs(kspkg.long_path(dst))
    moved = []
    for name in OLD_LAYOUT:
        src = os.path.join(work, name)
        if os.path.exists(kspkg.long_path(src)):
            os.rename(kspkg.long_path(src), kspkg.long_path(os.path.join(dst, name)))
            moved.append(name)
    return moved


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def load_catalogue(path=CATALOGUE):
    with open(path, encoding="utf-8") as f:
        cat = json.load(f)
    if not isinstance(cat.get("car_id"), str) or not isinstance(cat.get("settings"), list):
        raise ValueError("%s: needs car_id and settings" % path)
    seen = set()
    for s in cat["settings"]:
        missing = [k for k in REQUIRED if k not in s]
        if missing:
            raise ValueError("%s: setting %r misses %s" % (path, s.get("id"), ", ".join(missing)))
        if s["id"] in seen:
            raise ValueError("%s: duplicate setting id %r" % (path, s["id"]))
        seen.add(s["id"])
        if s["kind"] not in KINDS or s["type"] not in VALUE_TYPES:
            raise ValueError("%s: setting %r has an unknown kind or type" % (path, s["id"]))
        if s["kind"] == "value" and not (s.get("targets") and all("file" in t and "path" in t for t in s["targets"])):
            raise ValueError("%s: setting %r needs targets with file and path" % (path, s["id"]))
        if s["kind"] == "curve_scale" and not ("default" in s and {"file", "path"} <= set(s.get("curve_from", {}))):
            raise ValueError("%s: setting %r needs default and curve_from with file and path" % (path, s["id"]))
        needs = s.get("needs", [])
        if not (isinstance(needs, list)
                and all(isinstance(t, dict) and isinstance(t.get("file"), str) and isinstance(t.get("path"), str)
                        for t in needs)):
            raise ValueError("%s: setting %r has needs that is not a list of targets with file and path"
                             % (path, s["id"]))
        if type(s.get("hide_if_absent", False)) is not bool:
            raise ValueError("%s: setting %r has a hide_if_absent that is not true or false" % (path, s["id"]))
        files = ([t["file"] for t in s.get("targets", [])] + [t["file"] for t in needs]
                 + ([s["curve_from"]["file"]] if s["kind"] == "curve_scale" else []))
        for f in files:
            if f.startswith("@") and not ROLE.fullmatch(f):
                raise ValueError("%s: setting %r has an unknown file role %r" % (path, s["id"], f))
        if not all(type(t.get("optional", False)) is bool for t in s.get("targets", [])):
            raise ValueError("%s: setting %r has a target whose optional is not true or false" % (path, s["id"]))
        if s["kind"] == "meta" and not (s.get("handler") in HANDLERS
                                        and (isinstance(s.get("default"), str) or isinstance(s.get("default_template"), str))):
            raise ValueError("%s: setting %r needs a handler (%s) and a string default or default_template"
                             % (path, s["id"], "/".join(HANDLERS)))
    return cat


def find_setting(cat, setting_id):
    for s in cat["settings"]:
        if s["id"] == setting_id:
            return s
    raise ValueError("unknown setting %r" % setting_id)


def state_path(work, car_id):
    return os.path.join(car_work(work, car_id), "tune_state.json")


def load_state(work, car_id):
    path = state_path(work, car_id)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        state = json.load(f)
    if not isinstance(state, dict):
        raise ValueError("%s: expected an object" % path)
    return state


def save_state(work, car_id, state):
    save_json(state_path(work, car_id), state)


def unknown_state_ids(work, car_id, catalogue=None):
    known = {s["id"] for s in (catalogue or load_catalogue())["settings"]}
    return [sid for sid in load_state(work, car_id) if sid not in known]


def to_f32(x):
    try:
        y = struct.unpack("<f", struct.pack("<f", x))[0]
    except OverflowError:
        raise ValueError("float out of range: %r" % (x,))
    v = car_json.F32(y)
    v.text = car_json.f32_text(y)
    return v


def plain(v):
    return float(v.text) if isinstance(v, car_json.F32) else v


def fmt(v):
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "true" if v else "false"
    return v if isinstance(v, str) else repr(v) if isinstance(v, float) else str(v)


def zero(s):
    if s["type"] == "enum" and s.get("choices"):
        return s["choices"][0]
    return {"int": 0, "float": 0.0}.get(s["type"], "")


def coerce(s, v):
    t = s["type"]
    if t == "int":
        if isinstance(v, str):
            if not re.fullmatch(r"[+-]?\d+", v.strip()):
                raise ValueError("%s expects an integer, got %r" % (s["id"], v))
            v = int(v)
        if type(v) is not int:
            raise ValueError("%s expects an integer, got %r" % (s["id"], v))
    elif t == "float":
        try:
            if type(v) is bool or not isinstance(v, (str, int, float)):
                raise ValueError
            v = float(v)
        except ValueError:
            raise ValueError("%s expects a number, got %r" % (s["id"], v))
        if not math.isfinite(v):
            raise ValueError("%s expects a finite number, got %r" % (s["id"], v))
    else:
        if not isinstance(v, str) or not v or re.search(r"[\x00-\x1f]", v):
            raise ValueError("%s expects non-empty text without control characters" % s["id"])
        if t == "enum" and v not in s.get("choices", [v]):
            raise ValueError("%s must be one of: %s" % (s["id"], ", ".join(s["choices"])))
    return v


def range_warning(s, v):
    if s["type"] in ("int", "float") and (v < s.get("min", v) or v > s.get("max", v)):
        return "%s=%s is outside the suggested range %s..%s" % (
            s["id"], fmt(v), fmt(s.get("min", "-")), fmt(s.get("max", "-")))
    return None


def same(s, a, b):
    if s["type"] == "float" and a is not None and b is not None:
        a, b = to_f32(a), to_f32(b)
        return abs(a - b) <= 1e-5 * max(1, abs(a), abs(b))
    return a == b


def set_value(work, car_id, setting_id, text, catalogue=None):
    cat = catalogue or load_catalogue()
    s = find_setting(cat, setting_id)
    row = resolve_defaults(work, car_id, dict(cat, settings=[s]), hidden=True)[0]
    if not row["applicable"]:
        raise ValueError("%s is not applicable to %s: %s" % (setting_id, car_id, row["reason"]))
    v = coerce(s, text)
    state = load_state(work, car_id)
    state[setting_id] = v
    save_state(work, car_id, state)
    warning = range_warning(s, v)
    return {"id": setting_id, "value": v, "warnings": [warning] if warning else []}


def unset_value(work, car_id, setting_id, catalogue=None):
    find_setting(catalogue or load_catalogue(), setting_id)
    state = load_state(work, car_id)
    removed = state.pop(setting_id, None) is not None
    if removed:
        save_state(work, car_id, state)
    return {"id": setting_id, "removed": removed}


def parse_path(path):
    step = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)((?:\[[^\]]*\])*)")
    moves, pos = [], 0
    while True:
        m = step.match(path, pos)
        if not m:
            raise ValueError("bad field path %r" % path)
        moves.append(("key", m.group(1)))
        for sel in re.findall(r"\[([^\]]*)\]", m.group(2)):
            if sel.isdigit():
                moves.append(("idx", int(sel)))
            elif "=" in sel:
                moves.append(("find",) + tuple(sel.split("=", 1)))
            else:
                raise ValueError("bad selector [%s] in field path %r" % (sel, path))
        pos = m.end()
        if pos == len(path):
            return moves
        if path[pos] != ".":
            raise ValueError("bad field path %r" % path)
        pos += 1


def text_of(v):
    if isinstance(v, car_json.F32):
        return v.text
    return ("true" if v else "false") if isinstance(v, bool) else str(v)


def list_index(cur, move, path):
    if not isinstance(cur, list):
        raise ValueError("%s: expected a list before [%s]" % (path, "=".join(map(str, move[1:]))))
    if move[0] == "idx":
        if move[1] >= len(cur):
            raise ValueError("%s: list has no element %d" % (path, move[1]))
        return move[1]
    for i, el in enumerate(cur):
        if isinstance(el, dict) and move[1] in el and text_of(el[move[1]]) == move[2]:
            return i
    raise ValueError("%s: no list element with %s=%s" % (path, move[1], move[2]))


def add_key(d, key, value):
    d[key] = value
    if "_order" in d:
        d["_order"].append(key)


def locate(obj, path, create=False):
    """Return (container, key) of the field named by path; create adds missing objects on the way."""
    moves = parse_path(path)
    cur = obj
    for i, move in enumerate(moves):
        last = i == len(moves) - 1
        if move[0] == "key":
            if not isinstance(cur, dict):
                raise ValueError("%s: %r is not inside an object" % (path, move[1]))
            if last:
                return cur, move[1]
            if move[1] not in cur:
                if not create:
                    raise ValueError("%s: missing field %r" % (path, move[1]))
                add_key(cur, move[1], {})
            cur = cur[move[1]]
        else:
            idx = list_index(cur, move, path)
            if last:
                return cur, idx
            cur = cur[idx]


def get_value(obj, path):
    container, key = locate(obj, path)
    if isinstance(container, dict) and key not in container:
        return None, True
    return container[key], False


def put_value(obj, path, value):
    container, key = locate(obj, path, create=True)
    if isinstance(container, dict) and key not in container:
        add_key(container, key, value)
    else:
        container[key] = value


def load_msg(path):
    name = car_json.message_for(path)
    try:
        with open(kspkg.long_path(path), "rb") as f:
            data = f.read()
    except OSError as e:
        raise ValueError("%s: %s" % (path, e.strerror or e))
    obj, err = car_json.roundtrip(schema(), name, data)
    if err:
        raise ValueError("%s: %s" % (path, err))
    return obj, name


def save_msg(path, name, obj):
    try:
        data = car_json.encode_msg(schema(), name, obj)
    except ValueError as e:
        raise ValueError("%s: %s" % (path, e))
    with open(kspkg.long_path(path), "wb") as f:
        f.write(data)


def car_root_of(root, car_id):
    return os.path.join(root, "content", "cars", car_id)


def car_path(car_root, rel):
    return inside(car_root, os.path.join(car_root, *rel.split("/")))


def renamed(rel, old_id, new_id):
    return re.sub(re.escape(old_id), new_id, rel, flags=re.IGNORECASE)


def curve_path(root, text):
    return inside(root, os.path.join(root, *text.replace("\\", "/").split("/")))


def count_tree(path):
    files = dirs = size = 0
    for dp, dn, fn in os.walk(kspkg.long_path(path)):
        dirs += len(dn)
        files += len(fn)
        size += sum(os.path.getsize(os.path.join(dp, n)) for n in fn)
    return {"files": files, "dirs": dirs, "bytes": size}


def listing(path):
    return set(os.listdir(path)) if os.path.isdir(path) else set()


def stock_info_path(work, car_id):
    return os.path.join(car_work(work, car_id), "stock_info.json")


def valid_stock_info(info, car_id):
    return (isinstance(info, dict) and info.get("car_id") == car_id
            and all(isinstance(info.get(k), str) and info[k] for k in ("display_name", "brand"))
            and type(info.get("year")) is int)


def complete_stock_info(info):
    return info is not None and all(isinstance(info.get(k), str) for k in STOCK_PROPERTIES + ("variant_name",))


def load_stock_info(work, car_id):
    path = stock_info_path(work, car_id)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        info = json.load(f)
    if not valid_stock_info(info, car_id):
        raise ValueError("%s: expected car_id %s with display_name, brand and year" % (path, car_id))
    return info


def read_game_file(work, game, rel):
    """Bytes of one file of the game package, extracted through <work>/stock_tmp."""
    if not os.path.isfile(game):
        raise ValueError("game package not found: %s" % game)
    tmp = os.path.join(work, "stock_tmp")
    os.makedirs(work, exist_ok=True)
    if os.path.exists(tmp):
        remove_tree(work, tmp)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            kspkg.cmd_extract(game, tmp, rel)
        extracted = os.path.join(tmp, *rel.split("\\"))
        if not os.path.isfile(extracted):
            raise ValueError("%s not found in %s" % (rel, game))
        with open(extracted, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp):
            remove_tree(work, tmp)


def ensure_stock_loc(work, game=DEFAULT_GAME):
    """Make sure the game's stock en.cars.loc is in <work>/stock_loc; returns "present" or "written"."""
    path = stock_loc_path(work)
    if os.path.isfile(path):
        return "present"
    data = read_game_file(work, game, STOCK_LOC)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return "written"


def write_stock_info(work, car_id, game=DEFAULT_GAME):
    """Make sure <work>/<car>/stock_info.json is complete, read from the game's cars.table and en.cars.loc;
    returns "present" or "written"."""
    if complete_stock_info(load_stock_info(work, car_id)):
        return "present"
    data = read_game_file(work, game, CARS_TABLE)
    ensure_stock_loc(work, game)
    lines = car_json.decode_msg(schema(), "TableData", data).get("preset", {}).get("lines", [])
    rows = [l["car_content"] for l in lines if l.get("car_content", {}).get("name") == car_id]
    if len(rows) != 1:
        raise ValueError("%s has %d rows for %s, expected 1" % (CARS_TABLE, len(rows), car_id))
    info = {"car_id": car_id, "display_name": rows[0].get("display_name"), "brand": rows[0].get("brand"),
            "year": rows[0].get("year")}
    if not valid_stock_info(info, car_id):
        raise ValueError("%s: the row of %s lacks display_name, brand or year" % (CARS_TABLE, car_id))
    for i, key in enumerate(STOCK_PROPERTIES, 1):
        info[key] = rows[0].get(key) or schema()["enums"]["CarContentData.Property%d" % i][1][0]
    info["variant_name"] = clone_car.stock_variant(stock_loc_path(work), car_id)
    os.makedirs(car_work(work, car_id), exist_ok=True)
    with open(stock_info_path(work, car_id), "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(info, indent=2, ensure_ascii=False) + "\n")
    return "written"


def stock_info_or_none(work, car_id, game=DEFAULT_GAME):
    info = load_stock_info(work, car_id)
    if not complete_stock_info(info):
        try:
            write_stock_info(work, car_id, game)
            info = load_stock_info(work, car_id)
        except (ValueError, OSError):
            return info
    return info


def cars_index_path(work):
    return os.path.join(work, "cars_index.json")


def valid_cars_index(index):
    return (isinstance(index, list) and bool(index)
            and all(isinstance(c, dict) and isinstance(c.get("id"), str) and isinstance(c.get("display_name"), str)
                    for c in index))


def load_cars_index(work, game=DEFAULT_GAME):
    """[{id, display_name, brand, year}] of every car of the game sorted by display name, from the cache
    <work>/cars_index.json; created from the game's cars.table when missing. None when there is no cache and the
    game package cannot be read."""
    path = cars_index_path(work)
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                index = json.load(f)
        except (ValueError, OSError):
            index = None
        if valid_cars_index(index):
            return index
    if not os.path.isfile(game):
        return None
    try:
        data = read_game_file(work, game, CARS_TABLE)
        lines = car_json.decode_msg(schema(), "TableData", data).get("preset", {}).get("lines", [])
    except (ValueError, OSError):
        return None
    rows = {}
    for l in lines:
        c = l.get("car_content", {})
        if isinstance(c.get("name"), str) and c["name"]:
            rows[c["name"]] = {"id": c["name"], "display_name": c.get("display_name") or c["name"],
                               "brand": c.get("brand", ""), "year": c.get("year")}
    index = sorted(rows.values(), key=lambda c: (c["display_name"].lower(), c["id"]))
    if not valid_cars_index(index):
        return None
    save_json(path, index)
    return index


def preset_display_name(car_root):
    folder = os.path.join(car_root, "presets")
    names = sorted(n for n in listing(folder) if n.endswith(".mechanicalcarpreset"))
    if not names:
        raise ValueError("no mechanical preset in %s to derive the stock car name from" % folder)
    preset = load_msg(os.path.join(folder, names[0]))[0]
    text = ("%s %s" % (preset.get("brand", ""), preset.get("description", ""))).strip()
    return re.sub(r" Preset Base$", "", text)


def init(work, car_id, game=DEFAULT_GAME):
    base = base_dir(work, car_id)
    car_root = car_root_of(base, car_id)
    if os.path.isdir(kspkg.long_path(car_root)) and count_tree(car_root)["files"]:
        res = dict(count_tree(car_root), present=True, dir=car_root)
    else:
        if not os.path.isfile(game):
            raise ValueError("game package not found: %s" % game)
        part = base + ".partial"
        os.makedirs(kspkg.long_path(car_work(work, car_id)), exist_ok=True)
        if os.path.exists(kspkg.long_path(part)):
            remove_tree(work, part)
        with contextlib.redirect_stdout(io.StringIO()):
            kspkg.cmd_extract(game, part, "content\\cars\\" + car_id)
        part_car = car_root_of(part, car_id)
        if not os.path.isdir(kspkg.long_path(part_car)) or not count_tree(part_car)["files"]:
            remove_tree(work, part)
            raise ValueError("%s not found in %s" % (car_id, game))
        if os.path.exists(kspkg.long_path(base)):
            remove_tree(work, base)
        os.rename(kspkg.long_path(part), kspkg.long_path(base))
        res = dict(count_tree(car_root), present=False, dir=car_root)
    res["stock_loc"] = ensure_stock_loc(work, game)
    res["stock_info"] = write_stock_info(work, car_id, game)
    return res


def read_file(car_root, rel, cache):
    if rel not in cache:
        cache[rel] = load_msg(car_path(car_root, rel))[0]
    return cache[rel]


def find_ci(base, rel):
    """Actual path of rel below base, every part matched case-insensitively."""
    cur = base
    for part in filter(None, re.split(r"[\\/]+", rel)):
        try:
            names = {n.lower(): n for n in os.listdir(kspkg.long_path(cur))}
        except OSError as e:
            raise ValueError("%s: %s" % (cur, e.strerror or e))
        if part.lower() not in names:
            raise ValueError("%s not found in %s" % (part, cur))
        cur = os.path.join(cur, names[part.lower()])
    return cur


def rel_of(root, car_id, found):
    rel = os.path.relpath(found, car_root_of(root, car_id))
    if rel.split(os.sep)[0] == "..":
        raise ValueError("%s is outside the car folder" % found)
    return rel.replace(os.sep, "/")


def manifest_file(root, car_id, text, what):
    if not isinstance(text, str) or not text:
        raise ValueError("no %s" % what)
    return rel_of(root, car_id, find_ci(root, text))


def car_manifest(root, car_id, cache):
    car_root = car_root_of(root, car_id)
    data = find_ci(car_root, "data")
    names = sorted(n for n in os.listdir(kspkg.long_path(data))
                   if n.lower().endswith(".car") and os.path.isfile(kspkg.long_path(os.path.join(data, n))))
    if len(names) > 1:
        valid = []
        for n in names:
            rel = rel_of(root, car_id, os.path.join(data, n))
            try:
                if read_file(car_root, rel, cache).get("engine_path"):
                    valid.append(n)
            except ValueError:
                pass
        if len(valid) != 1:
            raise ValueError("ambiguous: %d .car files in %s (%s), %d of them with an engine_path"
                             % (len(names), data, ", ".join(names), len(valid)))
        names = valid
    if not names:
        raise ValueError("no .car file in %s" % data)
    return rel_of(root, car_id, os.path.join(data, names[0]))


def resolve_file(file, root, car_id, cache):
    """Path of a target file relative to the car folder: a role (@engine, ..., @turbo[N]) is resolved for the car,
    anything else is taken as it is."""
    if not file.startswith("@"):
        return file
    key = ("role", file)
    if key not in cache:
        car_root = car_root_of(root, car_id)
        name, _, index = file[1:].rstrip("]").partition("[")
        if name == "car":
            cache[key] = car_manifest(root, car_id, cache)
        elif name == "mech_preset":
            folder = find_ci(car_root, "presets")
            names = sorted(n for n in os.listdir(kspkg.long_path(folder)) if n.lower().endswith(".mechanicalcarpreset"))
            if not names:
                raise ValueError("no mechanical preset in %s" % folder)
            cache[key] = rel_of(root, car_id, os.path.join(folder, names[0]))
        elif name == "turbo":
            engine = read_file(car_root, resolve_file("@engine", root, car_id, cache), cache)
            paths = engine.get("turbos_to_load", [])
            if int(index) >= len(paths):
                raise ValueError("the engine file lists %d turbo file(s), no turbos_to_load[%s]" % (len(paths), index))
            cache[key] = manifest_file(root, car_id, paths[int(index)], "turbos_to_load[%s]" % index)
        else:
            field = MANIFEST_ROLES[name]
            car = read_file(car_root, resolve_file("@car", root, car_id, cache), cache)
            cache[key] = manifest_file(root, car_id, car.get(field), "%s in the car file" % field)
    return cache[key]


def resolve_curve(s, root, car_id, cache):
    cf = s["curve_from"]
    out = {"file": cf["file"], "path": cf["path"], "resolved": False}
    try:
        out["rel"] = resolve_file(cf["file"], root, car_id, cache)
        text, absent = get_value(read_file(car_root_of(root, car_id), out["rel"], cache), cf["path"])
        if absent or not isinstance(text, str):
            raise ValueError("%s holds no curve file name" % cf["path"])
        curve, _ = load_msg(curve_path(root, text))
        values = [p["value"] for p in curve.get("points", []) if "value" in p]
        if not values:
            raise ValueError("curve %s has no points with a value" % text)
    except (ValueError, OSError) as e:
        out["error"] = str(e)
        return out
    out.update(resolved=True, absent=False, curve=text, value=s["default"],
               info="%d points, peak %s" % (len(curve["points"]), fmt(plain(max(values)))))
    return out


def resolve_target(s, t, root, car_id, cache):
    out = {"file": t["file"], "path": t["path"], "resolved": False}
    if t.get("optional"):
        out["optional"] = True
    try:
        out["rel"] = resolve_file(t["file"], root, car_id, cache)
        value, absent = get_value(read_file(car_root_of(root, car_id), out["rel"], cache), t["path"])
    except (ValueError, OSError) as e:
        out["error"] = str(e)
        return out
    out.update(resolved=True, absent=absent, value=plain(zero(s) if absent else value))
    return out


def resolve_defaults(work, car_id, catalogue=None, game=DEFAULT_GAME, hidden=False):
    """Every setting with its default; hidden=False keeps only the settings applicable to the car, hidden=True
    returns all of them, each with applicable and reason (None when applicable)."""
    cat = catalogue or load_catalogue()
    root = base_dir(work, car_id)
    car_root = car_root_of(root, car_id)
    if not os.path.isdir(kspkg.long_path(car_root)):
        raise ValueError("no base car in %s, run init first" % root)
    info = stock_name = stock_variant = None
    if any("default_template" in s for s in cat["settings"]):
        info = stock_info_or_none(work, car_id, game)
        stock_name = info["display_name"] if info else preset_display_name(car_root)
        stock_variant = (info or {}).get("variant_name") or stock_name
    cache, rows = {}, []
    for s in cat["settings"]:
        row = {k: s[k] for k in REQUIRED if k != "description"}
        row.update({k: s[k] for k in ("min", "max", "description") if k in s})
        if s["kind"] == "meta":
            targets = []
        elif s["kind"] == "curve_scale":
            targets = [resolve_curve(s, root, car_id, cache)]
        else:
            targets = [resolve_target(s, t, root, car_id, cache) for t in s["targets"]]
        needs = [resolve_target(s, t, root, car_id, cache) for t in s.get("needs", [])]
        values = [t["value"] for t in targets if t["resolved"]]
        row["targets"] = targets
        row["resolved"] = all(t["resolved"] or t.get("optional") for t in targets)
        row["consistent"] = all(same(s, v, values[0]) for v in values)
        row["copies_differ"] = not row["consistent"]
        if row["copies_differ"]:
            row["copy_values"] = [{"target": "%s %s" % (t["file"], t["path"]), "value": t["value"]}
                                  for t in targets if t["resolved"]]
        row["default"] = (s["default"] if "default" in s
                          else s["default_template"].replace("{stock_display_name}", stock_name)
                                                    .replace("{stock_variant_name}", stock_variant)
                          if "default_template" in s else values[0] if values else None)
        row["absent"] = any(t.get("absent") for t in targets)
        row["ok"] = row["resolved"] and row["consistent"]
        missing = [t for t in targets + needs if not t["resolved"] and not t.get("optional")]
        required = [t for t in targets if not t.get("optional")]
        if s.get("handler") == "variant_name" and not (info or {}).get("variant_name"):
            row["reason"] = "the stock car has no variant name"
        elif missing:
            m = missing[0]
            row["reason"] = "%s %s: %s" % (m["file"], m["path"], m.get("error", "unresolved").removeprefix(m["path"] + ": "))
        elif s.get("hide_if_absent") and required and all(t["absent"] for t in required):
            row["reason"] = "field absent in the stock data"
        else:
            row["reason"] = None
        row["applicable"] = row["reason"] is None
        rows.append(row)
    return rows if hidden else [r for r in rows if r["applicable"]]


def effective_rows(work, car_id, catalogue=None, hidden=False):
    cat = catalogue or load_catalogue()
    state = load_state(work, car_id)
    rows = resolve_defaults(work, car_id, cat, hidden=hidden)
    for row in rows:
        s = find_setting(cat, row["id"])
        row["value"] = coerce(s, state[s["id"]]) if s["id"] in state else row["default"]
        row["changed"] = s["id"] in state and not same(s, row["value"], row["default"])
    return rows


def scale_curve(curve, factor):
    for p in curve.get("points", []):
        if "value" in p:
            p["value"] = to_f32(p["value"] * factor)


def apply(work, car_id, new_id=None, install=True, mods_dir=None, catalogue=None, game=DEFAULT_GAME):
    cat = catalogue or load_catalogue()
    new_id = new_id or new_id_for(car_id)
    root = base_dir(work, car_id)
    if not os.path.isdir(kspkg.long_path(car_root_of(root, car_id))):
        raise ValueError("no base car in %s, run init first" % root)
    clone_car.validate(car_id, new_id, os.path.join(build_dir(work, car_id), "unused"))
    rows = effective_rows(work, car_id, cat, hidden=True)
    changed = [(s, r) for s, r in zip(cat["settings"], rows) if r["changed"]]
    bad = ["%s (%s)" % (s["id"], r["reason"]) for s, r in changed if not r["applicable"]]
    if bad:
        raise ValueError("cannot apply the changed setting(s), not applicable to %s: %s" % (car_id, ", ".join(bad)))
    info = load_stock_info(work, car_id)
    if info is None and car_id != load_cars()["default"]:
        raise ValueError("stock info missing, run init with the game installed")
    info = info or {}
    out_dir = os.path.join(build_dir(work, car_id), new_id)
    if os.path.exists(kspkg.long_path(out_dir)):
        remove_tree(work, out_dir)
    meta = {s["handler"]: r["value"] for s, r in zip(cat["settings"], rows) if s["kind"] == "meta"}
    try:
        ensure_stock_loc(work, game)
    except (ValueError, OSError):
        pass
    stock_loc = stock_loc_path(work) if os.path.isfile(stock_loc_path(work)) else None
    car_name = (info.get("display_name") or preset_display_name(car_root_of(root, car_id))) + CAR_NAME_SUFFIX
    log = io.StringIO()
    try:
        with contextlib.redirect_stdout(log):
            notes = clone_car.build(car_root_of(root, car_id), new_id, out_dir, car_name,
                                    info.get("year", CLONE_YEAR), info.get("brand", CLONE_BRAND),
                                    meta["variant_name"], stock_loc, {k: info.get(k) for k in STOCK_PROPERTIES},
                                    pack=False)
    except SystemExit:
        raise ValueError("clone self-check failed:\n" + log.getvalue().rstrip())
    car_root = car_root_of(out_dir, new_id)
    edits, applied = {}, []
    for s, r in changed:
        item = {"id": s["id"], "old": r["default"], "new": r["value"], "files": []}
        applied.append(item)
        if s["kind"] == "meta":
            item["files"].append("uiresources/localization/en.cars.loc")
        elif s["kind"] == "curve_scale":
            text, _ = get_value(load_msg(car_path(car_root, renamed(r["targets"][0]["rel"], car_id, new_id)))[0],
                                s["curve_from"]["path"])
            path = curve_path(out_dir, text)
            curve, name = load_msg(path)
            scale_curve(curve, r["value"])
            save_msg(path, name, curve)
            item["files"].append(os.path.relpath(path, car_root).replace(os.sep, "/"))
        else:
            v = to_f32(r["value"]) if s["type"] == "float" else r["value"]
            for t in r["targets"]:
                if t["resolved"]:
                    edits.setdefault(renamed(t["rel"], car_id, new_id), []).append((item, t["path"], v))
    for rel, items in edits.items():
        path = car_path(car_root, rel)
        obj, name = load_msg(path)
        for item, field, v in items:
            put_value(obj, field, v)
            if rel not in item["files"]:
                item["files"].append(rel)
        save_msg(path, name, obj)
    pkg = os.path.join(out_dir, new_id + ".kspkg")
    with contextlib.redirect_stdout(io.StringIO()):
        kspkg.cmd_pack(out_dir, pkg)
    result = {"new_id": new_id, "build_dir": out_dir, "package": pkg, "size": os.path.getsize(pkg),
              "applied": applied, "notes": notes, "installed": None, "backup": None}
    if install:
        mods = os.path.abspath(os.path.expandvars(mods_dir or clone_car.DEFAULT_MODS))
        backups = os.path.join(work, "backups")
        before = listing(backups)
        with contextlib.redirect_stdout(io.StringIO()):
            clone_car.install(pkg, mods, backups)
        new = sorted(listing(backups) - before)
        result["installed"] = os.path.join(mods, os.path.basename(pkg))
        result["backup"] = os.path.join(backups, new[0]) if new else None
    return result


def list_cars(work, mods_dir=None, tested_only=False, game=DEFAULT_GAME):
    """Every car of the game (the tested cars only when the car index is not available or tested_only), sorted by
    display name."""
    cars = load_cars()
    mods = os.path.abspath(os.path.expandvars(mods_dir or clone_car.DEFAULT_MODS))
    labels = {c["id"]: c["label"] for c in cars["cars"]}
    names = {c["id"]: c["display_name"] for c in load_cars_index(work, game) or []}
    rows = []
    for car_id in labels if tested_only else list(dict.fromkeys(list(labels) + list(names))):
        car_root = car_root_of(base_dir(work, car_id), car_id)
        extracted = os.path.isdir(kspkg.long_path(car_root)) and bool(os.listdir(kspkg.long_path(car_root)))
        info = load_stock_info(work, car_id) if extracted else None
        display_name = info["display_name"] if info else names.get(car_id) or labels.get(car_id) or car_id
        new_id = new_id_for(car_id)
        rows.append({"id": car_id, "default": car_id == cars["default"], "label": labels.get(car_id, display_name),
                     "display_name": display_name, "extracted": extracted, "tested": car_id in labels,
                     "new_id": new_id, "installed": os.path.isfile(os.path.join(mods, new_id + ".kspkg")),
                     "bytes": count_tree(car_root)["bytes"] if extracted else None})
    return sorted(rows, key=lambda r: (r["display_name"].lower(), r["id"]))


def parse_args(args, flags, switches=()):
    pos, opts = [], {}
    i = 0
    while i < len(args):
        if args[i].startswith("--") and args[i][2:] in switches:
            opts[args[i][2:]] = True
            i += 1
        elif args[i].startswith("--"):
            if args[i][2:] not in flags or i + 1 >= len(args):
                raise ValueError("bad option %s" % args[i])
            opts[args[i][2:]] = args[i + 1]
            i += 2
        else:
            pos.append(args[i])
            i += 1
    return pos, opts


def table(headers, rows):
    rows = [[str(c) for c in r] for r in rows]
    widths = [max(len(r[i]) for r in [headers] + rows) for i in range(len(headers))]
    lines = [" | ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in [headers] + rows]
    return "\n".join([lines[0], "-+-".join("-" * w for w in widths)] + lines[1:])


def consistency_text(row):
    if not row["targets"]:
        return "yes"
    if row["consistent"]:
        return "yes"
    return "NO (%s)" % " / ".join(fmt(t["value"]) for t in row["targets"] if t["resolved"])


def print_defaults(rows):
    print(table(["id", "group", "default", "unit", "targets resolved", "consistent"],
                [[r["id"], r["group"], fmt(r["default"]) + (" (absent)" if r["absent"] else ""), r["unit"],
                  "%d/%d" % (sum(t["resolved"] for t in r["targets"]), len(r["targets"])) if r["targets"] else "-",
                  consistency_text(r)] for r in rows]))


def print_copy_differences(rows):
    differing = [r for r in rows if r["copies_differ"]]
    if not differing:
        return
    print("copies differ in the stock data (%d setting(s), the default shown is the first required target):"
          % len(differing))
    for r in differing:
        print("  " + r["id"])
        for c in r["copy_values"]:
            print("    %s = %s" % (c["target"], fmt(c["value"])))


def warn_unknown_state(work, car_id):
    for sid in unknown_state_ids(work, car_id):
        print("warning: ignoring unknown setting '%s' in the saved state" % sid)


def display_name_of(work, car_id):
    info = load_stock_info(work, car_id)
    if info:
        return info["display_name"]
    return next(r["display_name"] for r in list_cars(work) if r["id"] == car_id)


def note_untested(car_id):
    if car_id not in [c["id"] for c in load_cars()["cars"]]:
        print("note: %s is not in the tested list; results are unverified" % car_id)


def doc_text(car_id, display_name, rows):
    def cell(text):
        return str(text).replace("|", "\\|")

    groups = {}
    for r in rows:
        groups.setdefault(r["group"], []).append(r)
    lines = ["# %s: tuner settings" % display_name, "", DOC_INTRO % (display_name, car_id, car_id)]
    for group, items in groups.items():
        lines += ["", "## " + cell(group), "", "| Variable | Name | Default | Unit | Description | Status |",
                  "| --- | --- | --- | --- | --- | --- |"]
        lines += ["| %s |" % " | ".join([
            "`%s`" % r["id"], cell(r["label"]), cell(fmt(r["default"]) + (" (absent)" if r["absent"] else "")),
            cell(r["unit"]), cell(r["description"]), "verified" if r["verified"] else "unverified"]) for r in items]
    differing = [r for r in rows if r["copies_differ"]]
    if differing:
        lines += ["", "## Copies differ in the stock data", "",
                  "Copies differ in the stock data: %s. The default shown is the value of the first copy; applying a "
                  "value writes the same value to all copies." % ", ".join("`%s`" % r["id"] for r in differing), ""]
        lines += ["- `%s`: %s" % (r["id"], "; ".join("`%s` = %s" % (c["target"], fmt(c["value"]))
                                                     for c in r["copy_values"])) for r in differing]
    return "\n".join(lines + ["", "## Not covered yet", ""] + ["- " + n for n in DOC_NOT_COVERED]) + "\n"


def write_doc(work, car_id, out):
    rows = resolve_defaults(work, car_id)
    text = doc_text(car_id, display_name_of(work, car_id), rows)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return out


def start(opts):
    """Work folder and chosen car of a command; moves the old single-car layout first and says so."""
    work = work_dir(opts.get("work"))
    cars = load_cars()
    car_id = pick_car(cars, opts.get("car"), load_cars_index(work, os.path.expandvars(opts.get("game", DEFAULT_GAME))))
    moved = migrate_old_layout(work, cars["default"])
    if moved:
        print("moved the old single-car layout of %s into %s: %s" % (work, car_work(work, cars["default"]),
                                                                    ", ".join(moved)))
    return work, car_id


def main():
    cmd =sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if cmd == "cars":
            pos, opts = parse_args(sys.argv[2:], ("game", "mods", "work"), ("tested",))
            if pos:
                sys.exit(__doc__.split("\n\n")[1])
            work, _ = start(opts)
            game = os.path.expandvars(opts.get("game", DEFAULT_GAME))
            print(table(["id", "display name", "extracted", "tested", "new id", "installed", "size"],
                        [[r["id"], r["display_name"], "yes" if r["extracted"] else "no", "yes" if r["tested"] else "no",
                          r["new_id"], "yes" if r["installed"] else "no",
                          "%.1f MB" % (r["bytes"] / (1 << 20)) if r["extracted"] else "-"]
                         for r in list_cars(work, opts.get("mods"), "tested" in opts, game)]))
            if "tested" not in opts and load_cars_index(work, game) is None:
                print("note: the game package is not available and there is no car index, "
                      "only the tested cars are listed")
        elif cmd == "init":
            pos, opts = parse_args(sys.argv[2:], ("car", "game", "work"))
            if pos:
                sys.exit(__doc__.split("\n\n")[1])
            work, car_id = start(opts)
            note_untested(car_id)
            res = init(work, car_id, os.path.expandvars(opts.get("game", DEFAULT_GAME)))
            print("base already present" if res["present"] else "extracted the stock car")
            print("%s: %d files, %d folders, %d bytes" % (res["dir"], res["files"], res["dirs"], res["bytes"]))
            print("stock localization %s" % res["stock_loc"])
            print("stock info %s" % res["stock_info"])
        elif cmd == "defaults":
            pos, opts = parse_args(sys.argv[2:], ("car", "work"), ("hidden",))
            if pos:
                sys.exit(__doc__.split("\n\n")[1])
            work, car_id = start(opts)
            every = resolve_defaults(work, car_id, hidden=True)
            rows = [r for r in every if r["applicable"]]
            save_json(os.path.join(car_work(work, car_id), "defaults.json"), rows)
            print_defaults(rows)
            print("%d hidden for this car (not applicable)" % (len(every) - len(rows)))
            if "hidden" in opts:
                for r in every:
                    if not r["applicable"]:
                        print("  %s: %s" % (r["id"], r["reason"]))
            print_copy_differences(rows)
        elif cmd == "set":
            pos, opts = parse_args(sys.argv[2:], ("car", "work"))
            if len(pos) != 2:
                sys.exit(__doc__.split("\n\n")[1])
            res = set_value(*start(opts), pos[0], pos[1])
            for w in res["warnings"]:
                print("warning: " + w)
            print("%s = %s" % (res["id"], fmt(res["value"])))
        elif cmd == "unset":
            pos, opts = parse_args(sys.argv[2:], ("car", "work"))
            if len(pos) != 1:
                sys.exit(__doc__.split("\n\n")[1])
            res = unset_value(*start(opts), pos[0])
            print("%s %s" % (res["id"], "removed from the state" if res["removed"] else "was not set"))
        elif cmd == "show":
            pos, opts = parse_args(sys.argv[2:], ("car", "work"))
            if pos:
                sys.exit(__doc__.split("\n\n")[1])
            work, car_id = start(opts)
            warn_unknown_state(work, car_id)
            rows = effective_rows(work, car_id)
            print(table(["", "id", "value", "default", "unit"],
                        [["*" if r["changed"] else "", r["id"], fmt(r["value"]), fmt(r["default"]), r["unit"]]
                         for r in rows]))
        elif cmd == "apply":
            pos, opts = parse_args(sys.argv[2:], ("car", "new-id", "mods", "work"), ("no-install",))
            if pos:
                sys.exit(__doc__.split("\n\n")[1])
            work, car_id = start(opts)
            note_untested(car_id)
            warn_unknown_state(work, car_id)
            res = apply(work, car_id, opts.get("new-id"), "no-install" not in opts, opts.get("mods"))
            print("car: %s, new id: %s" % (car_id, res["new_id"]))
            print("applied %d setting(s)" % len(res["applied"]))
            for a in res["applied"]:
                print("  %s: %s -> %s  [%s]" % (a["id"], fmt(a["old"]), fmt(a["new"]), ", ".join(a["files"])))
            for n in res["notes"]:
                print(n)
            print("package: %s (%d bytes)" % (res["package"], res["size"]))
            if res["installed"]:
                print("installed: %s" % res["installed"])
                print("backup: %s" % (res["backup"] or "no previous install"))
        elif cmd == "doc":
            pos, opts = parse_args(sys.argv[2:], ("car", "out", "work"), ("all",))
            if pos or ("all" in opts and ("car" in opts or "out" in opts)):
                sys.exit(__doc__.split("\n\n")[1])
            work, car_id = start(opts)
            if "all" in opts:
                for c in load_cars()["cars"]:
                    if not init(work, c["id"])["present"]:
                        print("extracted the stock car %s" % c["id"])
                    print("wrote %s" % write_doc(work, c["id"], str(DOC_DIR / (c["id"] + ".md"))))
            else:
                note_untested(car_id)
                print("wrote %s" % write_doc(work, car_id, os.path.abspath(opts.get("out", DOC_DIR / (car_id + ".md")))))
        else:
            sys.exit(__doc__.split("\n\n")[1])
    except (ValueError, OSError) as e:
        sys.exit("error: %s" % e)


if __name__ == "__main__":
    main()
