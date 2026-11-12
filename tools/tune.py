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
<work>/cars_index.json (id, display_name, brand, year of every car), never refreshed by the tool: delete the file after a game update to rebuild it. When there is no cache and the game package is not
reachable, the tested cars of tuner/cars.json (a default car, a free-text "note" that no code reads, and a list of {id, label}) are the only cars.
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
          on first need; without it the name is derived from the car's preset. Also extracts the shared tyre files the
          car names (see below) next to the car folder, into <work>/<car>/base/content/cars/common_phsx/...; defaults,
          set, show and apply do that on first need for bases extracted earlier. Without the game package the tyre
          settings are hidden ("shared tyre files not extracted").
defaults: reads every applicable setting of tuner/catalogue.json from <work>/<car>/base, prints the table and writes
          <work>/<car>/defaults.json (the applicable rows with their targets, for inspection only: nothing reads it back). A setting is applicable when all its required targets resolve for the car; the
          others are hidden: their number is printed, --hidden lists each with its reason. When the copies of a value of
          an applicable setting disagree in the stock data, they are listed in the section "copies differ in the stock
          data" (the default shown is the value of the first required target); that is not an error.
set/unset/show: edit and print <work>/<car>/tune_state.json ({setting id: value}). show lists applicable settings
          only, set refuses a setting that is not applicable to the car. Entries of the state whose id is not in the
          catalogue are ignored with a warning (show, apply) and kept in the file (remove them with unset).
apply:    always starts from the pristine <work>/<car>/base: clones the car under the new id into
          <work>/<car>/build/<new_id>, writes every changed setting into ALL its resolved target files, packs
          <new_id>.kspkg and (unless --no-install) installs it to the mods folder (default
          %USERPROFILE%\\Saved Games\\ACE\\mods) with a backup of the previous package in <work>/backups. Only changed
          settings must be applicable. For a car other than the default car, the stock info must exist. Tyres: for each
          axle (front, rear) that has at least one changed tyre setting, the stock tyre file (shared, from base) is
          copied to content/cars/<new_id>/data/tyres/<new_id>_front.tyre (_rear), the changed values are written there,
          and the references to the stock file are pointed at the copy: the entries of the .car's frontTyreCompounds
          (rearTyreCompounds) and the front_tyre_data_path (rear_tyre_data_paths) of every presets/*.compatibletyres
          that name the stock file (compared case-insensitively). Other compounds and the shared files stay untouched;
          an axle without a changed tyre setting gets no file and no changed reference.
doc:      writes a Markdown reference of the settings applicable to the car with their defaults from
          <work>/<car>/base to <file> (default docs/settings/<car>.md in the repository); the car must be extracted.
          --all writes that file for every tested car of tuner/cars.json, extracting the cars that are not extracted
          yet first (--car and --out cannot be combined with --all).
<work> defaults to %USERPROFILE%\\ace_modded_cars_work. --game is accepted by cars and init only; the other commands use the default Steam path of the game package for what they extract on first need. Writes nothing outside <work>, the mods folder and, for doc, the Markdown file (default docs/settings/ in the repository, or --out). File
operations on car trees use extended-length paths (kspkg.long_path), so deep Windows paths work.

Catalogue settings: id, group, label, kind (value, curve_scale, meta, flag), type (int, float, string, enum, bool), unit, description and verified are required. min/max are a suggested range (a value outside it only gives a warning). Kind value writes the value into all its targets; the default is read from the first required target. Kind curve_scale has a default factor and curve_from (file role and path of a curve file name); apply multiplies the value of every point of that curve by the factor. Kind meta needs a handler (variant_name, name_suffix) and a default or a default_template (text with {stock_variant_name}). An enum lists its choices.

Catalogue field paths (inside the JSON that car_json decodes): dot-separated names, name[3] = list element by index,
name[key=VALUE] = the list element whose field key equals VALUE, name[*] = every element of the list (all existing
elements; the default and the consistency check read all of them and require them equal, like several targets; an
empty or absent list resolves to nothing, so a required target makes the setting not applicable), e.g. gears[1].ratio,
car_specs.items[key=CarSpecs_KeyEnum_POWER].value or performance_modes[*].electronics_settings.tc1. A missing last
field reads as the proto3 default (flagged absent) and is created on write; missing objects on the way are created on
write; a missing list element is an error. A setting with "create_missing": true also counts missing objects on the
way as resolved-absent (value = default 0) and creates them on write; without it they make the setting not applicable.

Catalogue target files ("file" of a target and of curve_from) are roles, resolved per car and case-insensitively from
its .car manifest: @engine, @drivetrain, @gearbox, @clutch, @brakes (engine_path ... brakes_path), @setup
(stock_setup), @limits (setupLimits), @coilover_front, @coilover_rear (suspensions.coilover_front_path and
suspensions.coilover_rear_path, the standalone .coilover files), @car (the .car file in data; with several, the one
that decodes as CarData and has engine_path), @mech_preset (first presets/*.mechanicalcarpreset in sorted order),
@turbo[N] (the file named by turbos_to_load[N] of the engine file), @tyre_front, @tyre_rear (the .tyre file named by
frontTyreCompounds[0] / rearTyreCompounds[0] of the .car; a shared game file in <base>/content/cars/common_phsx, reached
as "../common_phsx/..." relative to the car folder; apply never writes to it, see apply). A target with
"optional": true is written when it resolves and skipped otherwise; every other target is required. A setting is applicable to a car when all its required
targets resolve (an absent last field counts as resolved, a missing object or list element on the way does not).
"needs" is a list of further targets that must resolve for the setting to be applicable but are never written and not
compared. "hide_if_absent": true hides the setting when the last field of all its required targets is absent in the
stock data. Settings of kind "flag" have type bool, the default false and a fixed "value" (a number, 0 for the driver
aids switch): when a flag is true, apply writes that value into all its resolved targets (wildcards allowed, targets may
be optional) and nothing when it is false; a target whose field is absent in the data is skipped when the value is 0
(absent already reads as 0). The targets of a flag are neither compared nor give a default. Flags are applied after all
other settings, so a flag wins over a value on the same field. set accepts true/false, yes/no, 1/0, on/off for bool
(case-insensitive). An enum setting with "choice_values" (choice -> text) stores text in its field: the default is the
choice whose text equals the field (case-insensitive, slash and backslash alike; any other text makes the setting not
applicable), apply writes the text of the chosen choice. meta settings: variant_name, applicable only when the stock car has a variant name, and name_suffix (default _MY, 1 to 30 characters without
control characters, not trimmed): apply names the tuned car "<stock display name><name_suffix>" (stock_info.json, else
the car's mechanical preset), so the default lists it next to the stock car. "ui": "header" on a setting is only a hint
for the web page (it shows the setting in its header, not in the table).

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
import threading

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import car_json  # noqa: E402
import clone_car  # noqa: E402
import kspkg  # noqa: E402
from kspkg import parse_args  # noqa: E402

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
    "tyre data beyond the per-axle values and the thermal curve family (compound tables, wear curves; the other "
    "compounds a player can pick stay stock)", "aero",
    "electronics tables (TC / ABS / ESC slip ratios and gains; only the default levels and the all-off switch are "
    "covered)", "coilover bump stop force and length values, rear caster", "damper limits",
    "engine map (`maps[]`) values", "further turbo settings (lag, wastegate, controllers)")
CARS_TABLE = "system\\cars.table"
STOCK_LOC = "\\".join(clone_car.LOC_PATH)
STOCK_PROPERTIES = ("property_1", "property_2", "property_3")
# apply fallback for the default car when stock_info.json is missing and the game is not reachable: the values of the BMW M3 E46 CSL
CLONE_YEAR, CLONE_BRAND = 2003, "BMW"
NAME_SUFFIX_MAX = 30
KINDS = ("value", "curve_scale", "meta", "flag")
VALUE_TYPES = ("int", "float", "string", "enum", "bool")
HANDLERS = ("variant_name", "name_suffix")
REQUIRED = ("id", "group", "label", "kind", "type", "unit", "description", "verified")
MANIFEST_ROLES = {"engine": "engine_path", "drivetrain": "drivetrain_path", "gearbox": "gearbox_path",
                  "clutch": "clutch_path", "brakes": "brakes_path", "setup": "stock_setup", "limits": "setupLimits",
                  "coilover_front": "suspensions.coilover_front_path",
                  "coilover_rear": "suspensions.coilover_rear_path"}
TYRE_ROLES = {"tyre_front": "frontTyreCompounds", "tyre_rear": "rearTyreCompounds"}
ROLE = re.compile(r"@(car|mech_preset|%s|turbo\[\d+\])" % "|".join(list(MANIFEST_ROLES) + list(TYRE_ROLES)))
SHARED_DIR = "common_phsx"
SHARED = "../%s/" % SHARED_DIR
GAME_SHARED = "content\\cars\\%s\\" % SHARED_DIR
TYRE_UNAVAILABLE = "shared tyre files not extracted"

_index_error = []
_tyre_lock = threading.Lock()
_stdout_lock = threading.Lock()


def schema():
    return car_json.load_schema()


def work_dir(arg=None):
    try:
        return clone_car.expand(arg or DEFAULT_WORK)
    except ValueError:
        raise ValueError("cannot expand the work directory %r" % (arg or DEFAULT_WORK)) from None


def inside(root, path):
    root, path = os.path.realpath(root), os.path.realpath(path)
    if os.path.commonpath([root, path]) != root:
        raise ValueError("%s is not inside %s" % (path, root))
    return path


def remove_tree(work, path):
    if inside(work, path) == os.path.realpath(work):
        raise ValueError("refusing to remove the work directory itself")
    shutil.rmtree(kspkg.long_path(path))


def read_json(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except ValueError as e:
        raise ValueError("%s: %s" % (path, e)) from None


def load_cars(path=CARS_JSON):
    data = read_json(path)
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
            raise ValueError("unknown car %r, the car list of the game is not available%s, the tested cars "
                             "(tuner/cars.json) are: %s" % (car_id, " (reason: %s)" % _index_error[0] if _index_error else "",
                                                            ", ".join(known)))
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
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    part = path + ".tmp"
    try:
        with open(part, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(part, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(part)
        raise


def load_catalogue(path=CATALOGUE):
    cat = read_json(path)
    if not isinstance(cat.get("settings"), list):
        raise ValueError("%s: needs settings" % path)
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
        if (s["kind"] == "flag") != (s["type"] == "bool"):
            raise ValueError("%s: setting %r: kind flag and type bool belong together" % (path, s["id"]))
        if s["kind"] in ("value", "flag") and not (s.get("targets") and all("file" in t and "path" in t
                                                                              for t in s["targets"])):
            raise ValueError("%s: setting %r needs targets with file and path" % (path, s["id"]))
        if s["kind"] == "flag" and type(s.get("value")) not in (int, float):
            raise ValueError("%s: setting %r needs a numeric value to write" % (path, s["id"]))
        if type(s.get("create_missing", False)) is not bool:
            raise ValueError("%s: setting %r has a create_missing that is not true or false" % (path, s["id"]))
        cv = s.get("choice_values")
        if cv is not None and not (s["type"] == "enum" and isinstance(cv, dict) and set(cv) == set(s.get("choices", []))
                                   and all(isinstance(x, str) and x for x in cv.values())):
            raise ValueError("%s: setting %r needs choice_values to be an enum's text for every choice"
                             % (path, s["id"]))
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
    state = read_json(path)
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
        raise ValueError("float out of range: %r" % (x,)) from None
    v = car_json.F32(y)
    v.text = car_json.f32_text(y)
    return v


# the float32's shortest decimal as a double (0.1, not 0.10000000149011612), for display and for comparing with the typed value
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
    return {"int": 0, "float": 0.0, "bool": False}.get(s["type"], "")


BOOL_WORDS = {"true": True, "yes": True, "1": True, "on": True, "false": False, "no": False, "0": False, "off": False}


def coerce(s, v):
    t = s["type"]
    if t == "bool":
        if type(v) is bool:
            return v
        word = str(v).strip().lower() if type(v) in (int, str) else None
        if word not in BOOL_WORDS:
            raise ValueError("%s expects true or false (also yes/no, 1/0, on/off), got %r" % (s["id"], v))
        return BOOL_WORDS[word]
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
            raise ValueError("%s expects a number, got %r" % (s["id"], v)) from None
        if not math.isfinite(v):
            raise ValueError("%s expects a finite number, got %r" % (s["id"], v))
    elif s.get("handler") == "name_suffix":
        if not isinstance(v, str) or not 1 <= len(v) <= NAME_SUFFIX_MAX or re.search(r"[\x00-\x1f]", v):
            raise ValueError("%s expects 1 to %d characters without control characters" % (s["id"], NAME_SUFFIX_MAX))
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


# float copies from different files may differ in the last float32 digit; 1e-5 relative is well above float32 resolution (about 1.2e-7)
def same(s, a, b):
    if s["type"] == "float" and a is not None and b is not None:
        a, b = to_f32(a), to_f32(b)
        return abs(a - b) <= 1e-5 * max(1, abs(a), abs(b))
    return a == b


def set_value(work, car_id, setting_id, text, catalogue=None):
    cat = catalogue or load_catalogue()
    s = find_setting(cat, setting_id)
    v = coerce(s, text)
    row = resolve_defaults(work, car_id, dict(cat, settings=[s]), hidden=True)[0]
    if not row["applicable"]:
        raise ValueError("%s is not applicable to %s: %s" % (setting_id, car_id, row["reason"]))
    state = load_state(work, car_id)
    state[setting_id] = v
    save_state(work, car_id, state)
    warning = range_warning(s, v)
    return {"id": setting_id, "value": v, "warnings": [warning] if warning else []}


def unset_value(work, car_id, setting_id, catalogue=None):
    state = load_state(work, car_id)
    if setting_id not in state:
        find_setting(catalogue or load_catalogue(), setting_id)
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
            elif sel == "*":
                moves.append(("all",))
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
    if move[0] == "all":
        raise ValueError("%s: [*] must be expanded before use" % path)
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


def locate(obj, path, create=False, missing_ok=False):
    """Return (container, key) of the field named by path; create adds missing objects on the way, missing_ok
    returns (None, None) for a missing object on the way."""
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
                if missing_ok:
                    return None, None
                if not create:
                    raise ValueError("%s: missing field %r" % (path, move[1]))
                add_key(cur, move[1], {})
            cur = cur[move[1]]
        else:
            idx = list_index(cur, move, path)
            if last:
                return cur, idx
            cur = cur[idx]


def get_value(obj, path, missing_ok=False):
    container, key = locate(obj, path, missing_ok=missing_ok)
    if container is None or (isinstance(container, dict) and key not in container):
        return None, True
    return container[key], False


def expand_path(obj, path, missing_ok=False):
    """The concrete paths a path with [*] stands for (one per existing list element), [path] without one. An absent or
    empty list gives no paths."""
    if "[*]" not in path:
        return [path]
    prefix, _, rest = path.partition("[*]")
    items, absent = get_value(obj, prefix, missing_ok)
    if absent:
        return []
    if not isinstance(items, list):
        raise ValueError("%s: [*] needs a list at %s" % (path, prefix))
    return [p for i in range(len(items)) for p in expand_path(obj, "%s[%d]%s" % (prefix, i, rest), missing_ok)]


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
        raise ValueError("%s: %s" % (path, e.strerror or e)) from None
    obj, err = car_json.roundtrip(schema(), name, data, text=False)
    if err:
        raise ValueError("%s: %s" % (path, err))
    return obj, name


def save_msg(path, name, obj):
    try:
        data = car_json.encode_msg(schema(), name, obj)
    except ValueError as e:
        raise ValueError("%s: %s" % (path, e)) from None
    with open(kspkg.long_path(path), "wb") as f:
        f.write(data)


def car_root_of(root, car_id):
    return os.path.join(root, "content", "cars", car_id)


def car_path(car_root, rel):
    if rel.startswith(SHARED):
        shared = os.path.join(os.path.dirname(car_root), SHARED_DIR)
        return inside(shared, os.path.join(shared, *rel[len(SHARED):].split("/")))
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
    info = read_json(path)
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
        with _stdout_lock, contextlib.redirect_stdout(io.StringIO()):
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
    rows = [line["car_content"] for line in lines if line.get("car_content", {}).get("name") == car_id]
    if len(rows) != 1:
        raise ValueError("%s has %d rows for %s, expected 1" % (CARS_TABLE, len(rows), car_id))
    info = {"car_id": car_id, "display_name": rows[0].get("display_name"), "brand": rows[0].get("brand"),
            "year": rows[0].get("year")}
    if not valid_stock_info(info, car_id):
        raise ValueError("%s: the row of %s lacks display_name, brand or year" % (CARS_TABLE, car_id))
    # proto3 leaves an enum at value 0 off the wire: absent property = the enum's value 0 name
    for i, key in enumerate(STOCK_PROPERTIES, 1):
        info[key] = rows[0].get(key) or schema()["enums"]["CarContentData.Property%d" % i][1][0]
    info["variant_name"] = clone_car.stock_variant(stock_loc_path(work), car_id)
    save_json(stock_info_path(work, car_id), info)
    return "written"


# best effort: when the game or the schemas are unavailable the car keeps whatever stock_info.json it has (or none) and callers fall back to the preset name
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
    game package cannot be read or decoded."""
    path = cars_index_path(work)
    _index_error.clear()
    if os.path.isfile(path):
        try:
            index = read_json(path)
        except (ValueError, OSError):
            index = None
        if valid_cars_index(index):
            return index
    if not os.path.isfile(game):
        return None
    try:
        data = read_game_file(work, game, CARS_TABLE)
        lines = car_json.decode_msg(schema(), "TableData", data).get("preset", {}).get("lines", [])
    except (ValueError, OSError) as e:
        _index_error[:] = [str(e)]
        return None
    rows = {}
    for line in lines:
        c = line.get("car_content", {})
        if isinstance(c.get("name"), str) and c["name"]:
            rows[c["name"]] = {"id": c["name"], "display_name": c.get("display_name") or c["name"],
                               "brand": c.get("brand", ""), "year": c.get("year")}
    index = sorted(rows.values(), key=lambda c: (c["display_name"].lower(), c["id"]))
    if not valid_cars_index(index):
        return None
    save_json(path, index)
    return index


def preset_display_name(car_root):
    folder = find_ci(car_root, "presets")
    names = sorted(n for n in os.listdir(kspkg.long_path(folder)) if n.lower().endswith(".mechanicalcarpreset"))
    if not names:
        raise ValueError("no mechanical preset in %s to derive the stock car name from" % folder)
    preset = load_msg(os.path.join(folder, names[0]))[0]
    text = ("%s %s" % (preset.get("brand", ""), preset.get("description", ""))).strip()
    return re.sub(r" Preset Base$", "", text)


def init(work, car_id, game=DEFAULT_GAME):
    base = base_dir(work, car_id)
    car_root = car_root_of(base, car_id)
    present = count_tree(car_root) if os.path.isdir(kspkg.long_path(car_root)) else None
    if present and present["files"]:
        res = dict(present, present=True, dir=car_root)
    else:
        if not os.path.isfile(game):
            raise ValueError("game package not found: %s" % game)
        # extract next to base and rename, so an interrupted extraction never leaves a half-filled base that count_tree would accept
        part = base + ".partial"
        os.makedirs(kspkg.long_path(car_work(work, car_id)), exist_ok=True)
        if os.path.exists(kspkg.long_path(part)):
            remove_tree(work, part)
        with _stdout_lock, contextlib.redirect_stdout(io.StringIO()):
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
    try:
        res["tyre_files"] = ensure_tyre_files(work, car_id, game)
    except (ValueError, OSError) as e:
        res["tyre_files"] = "not extracted (%s)" % e
    return res


def read_file(car_root, rel, cache):
    """Decoded file below car_root (rel as returned by resolve_file), cached by rel; the same dict also holds the ("role", file) entries of resolve_file."""
    if rel not in cache:
        try:
            cache[rel] = load_msg(car_path(car_root, rel))[0]
        except ValueError as e:
            cache[rel] = e
    if isinstance(cache[rel], ValueError):
        raise cache[rel]
    return cache[rel]


def find_ci(base, rel):
    """Actual path of rel below base, every part matched case-insensitively."""
    cur = base
    for part in filter(None, re.split(r"[\\/]+", rel)):
        try:
            names = {n.lower(): n for n in os.listdir(kspkg.long_path(cur))}
        except OSError as e:
            raise ValueError("%s: %s" % (cur, e.strerror or e)) from None
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
    if isinstance(cache.get(key), ValueError):
        raise cache[key]
    if key not in cache:
        try:
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
            elif name in TYRE_ROLES:
                cache[key] = tyre_file(root, car_id, name, cache)
            else:
                field = MANIFEST_ROLES[name]
                car = read_file(car_root, resolve_file("@car", root, car_id, cache), cache)
                cache[key] = manifest_file(root, car_id, get_value(car, field)[0], "%s in the car file" % field)
        except ValueError as e:
            cache[key] = e
            raise
    return cache[key]


def game_path_key(text):
    return text.replace("/", "\\").lower()


def tyre_text(root, car_id, name, cache):
    """The path text of frontTyreCompounds[0] / rearTyreCompounds[0] (name tyre_front / tyre_rear) in the .car file."""
    car = read_file(car_root_of(root, car_id), resolve_file("@car", root, car_id, cache), cache)
    paths = car.get(TYRE_ROLES[name])
    if not paths or not isinstance(paths[0], str) or not paths[0]:
        raise ValueError("no %s in the car file" % TYRE_ROLES[name])
    return paths[0]


def tyre_file(root, car_id, name, cache):
    """Path relative to the car folder of the tyre file of a role: inside the car folder, or SHARED + the path below
    common_phsx for a shared game file."""
    found = tyre_found(root, tyre_text(root, car_id, name, cache))
    rel = os.path.relpath(found, car_root_of(root, car_id)).replace(os.sep, "/")
    if rel.split("/")[0] != "..":
        return rel
    shared = os.path.relpath(found, os.path.join(root, "content", "cars", SHARED_DIR)).replace(os.sep, "/")
    if shared.split("/")[0] == "..":
        raise ValueError("%s is neither in the car folder nor in the shared folder" % found)
    return SHARED + shared


def tyre_found(root, text):
    try:
        return find_ci(root, text)
    except ValueError:
        raise ValueError(TYRE_UNAVAILABLE) from None


def referenced_tyres(root, car_id, cache):
    """The shared tyre files (game paths below content\\cars\\common_phsx, lower case) that the car's .car
    (frontTyreCompounds, rearTyreCompounds) and presets/*.compatibletyres name, each once."""
    car_root = car_root_of(root, car_id)
    car = read_file(car_root, resolve_file("@car", root, car_id, cache), cache)
    texts = list(car.get("frontTyreCompounds", [])) + list(car.get("rearTyreCompounds", []))
    try:
        folder = find_ci(car_root, "presets")
    except ValueError:
        folder = None
    for n in sorted(os.listdir(kspkg.long_path(folder))) if folder else []:
        if n.lower().endswith(".compatibletyres"):
            for pc in load_msg(os.path.join(folder, n))[0].get("physic_compounds", []):
                rear = pc.get("rear_tyre_data_paths")
                texts += [pc.get("front_tyre_data_path")] + (rear if isinstance(rear, list) else [rear])
    keys = [game_path_key(t) for t in texts if isinstance(t, str)]
    return list(dict.fromkeys(k for k in keys if k.startswith(GAME_SHARED)))


def tyre_present(root, text):
    try:
        find_ci(root, text)
        return True
    except ValueError:
        return False


def ensure_tyre_files(work, car_id, game=DEFAULT_GAME, cache=None):
    """Make sure the shared tyre files the car names are in <work>/<car>/base next to the car folder (extracted from
    the game package, nothing else); returns "present" or "extracted N file(s)"."""
    root = base_dir(work, car_id)
    with _tyre_lock:
        missing = [p for p in referenced_tyres(root, car_id, {} if cache is None else cache)
                   if not tyre_present(root, p)]
        if not missing:
            return "present"
        if not os.path.isfile(game):
            raise ValueError("game package not found: %s" % game)
        for p in missing:
            # kspkg and clone_car print their progress: keep it out of this command's output
            with _stdout_lock, contextlib.redirect_stdout(io.StringIO()):
                kspkg.cmd_extract(game, root, p)
        gone = [p for p in missing if not tyre_present(root, p)]
        if gone:
            raise ValueError("%s not found in %s" % (gone[0], game))
    return "extracted %d file(s)" % len(missing)


def choice_of(s, text):
    for name, written in s["choice_values"].items():
        if game_path_key(written) == game_path_key(text):
            return name
    raise ValueError("%s is not one of the choices of %s" % (text, s["id"]))


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
    """The resolved copies of one catalogue target: one entry, or one per list element when the path has [*] (the
    path of each entry is the concrete one). A target that does not resolve gives one entry with the error."""
    base = {"file": t["file"], "path": t["path"], "resolved": False}
    if t.get("optional"):
        base["optional"] = True
    missing_ok = bool(s.get("create_missing"))
    try:
        base["rel"] = resolve_file(t["file"], root, car_id, cache)
        obj = read_file(car_root_of(root, car_id), base["rel"], cache)
        paths = expand_path(obj, t["path"], missing_ok)
        if not paths:
            raise ValueError("%s: the list has no elements" % t["path"])
        out = []
        for path in paths:
            value, absent = get_value(obj, path, missing_ok)
            value = plain(zero(s) if absent else value)
            if s["type"] == "int" and isinstance(value, float) and value.is_integer():
                value = int(value)
            if s.get("choice_values") and not absent:
                value = choice_of(s, value)
            out.append(dict(base, path=path, resolved=True, absent=absent, value=value))
    except (ValueError, OSError) as e:
        return [dict(base, error=str(e))]
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
    cache, rows, tyre_error = {}, [], None
    if any(t["file"].startswith("@tyre_") for s in cat["settings"] for t in s.get("targets", [])):
        try:
            ensure_tyre_files(work, car_id, game, cache)
        except (ValueError, OSError) as e:
            tyre_error = str(e)
    for s in cat["settings"]:
        row = {k: s[k] for k in REQUIRED if k != "description"}
        row.update({k: s[k] for k in ("min", "max", "description") if k in s})
        if s["kind"] == "meta":
            targets = []
        elif s["kind"] == "curve_scale":
            targets = [resolve_curve(s, root, car_id, cache)]
        else:
            targets = [c for t in s["targets"] for c in resolve_target(s, t, root, car_id, cache)]
        needs = [c for t in s.get("needs", []) for c in resolve_target(s, t, root, car_id, cache)]
        values = [t["value"] for t in targets if t["resolved"]] if s["kind"] != "flag" else []
        row["targets"] = targets
        row["resolved"] = all(t["resolved"] or t.get("optional") for t in targets)
        row["consistent"] = all(same(s, v, values[0]) for v in values)
        row["copies_differ"] = not row["consistent"]
        if row["copies_differ"]:
            row["copy_values"] = [{"target": "%s %s" % (t["file"], t["path"]), "value": t["value"]}
                                  for t in targets if t["resolved"]]
        row["default"] = (False if s["kind"] == "flag" else s["default"] if "default" in s
                          else s["default_template"].replace("{stock_display_name}", stock_name)
                                                    .replace("{stock_variant_name}", stock_variant)
                          if "default_template" in s else values[0] if values else None)
        row["absent"] = s["kind"] != "flag" and any(t.get("absent") for t in targets)
        row["ok"] = row["resolved"] and row["consistent"]
        missing = [t for t in targets + needs if not t["resolved"] and not t.get("optional")]
        required = [t for t in targets if not t.get("optional")]
        if s.get("handler") == "variant_name" and not (info or {}).get("variant_name"):
            row["reason"] = "the stock car has no variant name"
        elif missing:
            m = missing[0]
            row["reason"] = "%s %s: %s" % (m["file"], m["path"], m.get("error", "unresolved").removeprefix(m["path"] + ": "))
            if tyre_error and m["file"].startswith("@tyre_"):
                row["reason"] += " (%s)" % tyre_error
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


def repoint(obj, field, old_text, new_text):
    """Replace, in the text (or list of texts) field of obj, every value equal to old_text; returns how many."""
    hits = 0
    values = obj.get(field)
    for i, v in enumerate(values if isinstance(values, list) else [values]):
        if isinstance(v, str) and game_path_key(v) == game_path_key(old_text):
            if isinstance(values, list):
                values[i] = new_text
            else:
                obj[field] = new_text
            hits += 1
    return hits


def build_tyre(root, car_id, new_id, car_root, role, items, cache):
    """Give the tuned car its own copy of the stock tyre file of an axle (role tyre_front / tyre_rear): copy it from
    base to data/tyres/<new_id>_<axle>.tyre, write the changed values (items: (item, field, value)) and point the
    references of the stock file at the copy. Returns a note for the build log."""
    axle = role[len("tyre_"):]
    stock_text = tyre_text(root, car_id, role, cache)
    rel = "data/tyres/%s_%s.tyre" % (new_id, axle)
    new_text = "content\\cars\\%s\\%s" % (new_id, rel.replace("/", "\\"))
    path = car_path(car_root, rel)
    obj, name = load_msg(car_path(car_root_of(root, car_id), resolve_file("@" + role, root, car_id, cache)))
    for item, field, v in items:
        put_value(obj, field, v)
        if rel not in item["files"]:
            item["files"].append(rel)
    os.makedirs(kspkg.long_path(os.path.dirname(path)), exist_ok=True)
    save_msg(path, name, obj)
    car_rel = renamed(resolve_file("@car", root, car_id, cache), car_id, new_id)
    car_file = car_path(car_root, car_rel)
    car, car_name = load_msg(car_file)
    in_car = repoint(car, TYRE_ROLES[role], stock_text, new_text)
    if in_car:
        save_msg(car_file, car_name, car)
    in_presets = 0
    folder = os.path.join(car_root, "presets")
    for n in sorted(os.listdir(kspkg.long_path(folder))) if os.path.isdir(kspkg.long_path(folder)) else []:
        if n.lower().endswith(".compatibletyres"):
            preset, preset_name = load_msg(os.path.join(folder, n))
            hits = sum(repoint(pc, "front_tyre_data_path" if axle == "front" else "rear_tyre_data_paths",
                               stock_text, new_text) for pc in preset.get("physic_compounds", []))
            if hits:
                save_msg(os.path.join(folder, n), preset_name, preset)
                in_presets += hits
    return "note: tyre %s: own file %s replaces %s in %d .car entry(ies) and %d compatibletyres entry(ies)" % (
        axle, new_text, stock_text, in_car, in_presets)


def apply(work, car_id, new_id=None, install=True, mods_dir=None, catalogue=None, game=DEFAULT_GAME):
    cat = catalogue or load_catalogue()
    new_id = new_id or new_id_for(car_id)
    root = base_dir(work, car_id)
    if not os.path.isdir(kspkg.long_path(car_root_of(root, car_id))):
        raise ValueError("no base car in %s, run init first" % root)
    # ids only: the "unused" folder never exists, an old build of the same id is replaced below
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
    # the build always starts from the pristine base, a leftover build of this id is replaced
    if os.path.exists(kspkg.long_path(out_dir)):
        remove_tree(work, out_dir)
    meta = {s["handler"]: r["value"] for s, r in zip(cat["settings"], rows) if s["kind"] == "meta"}
    with contextlib.suppress(ValueError, OSError):
        ensure_stock_loc(work, game)
    stock_loc = stock_loc_path(work) if os.path.isfile(stock_loc_path(work)) else None
    car_name = (info.get("display_name") or preset_display_name(car_root_of(root, car_id))) + meta["name_suffix"]
    log = io.StringIO()
    try:
        # kspkg and clone_car print their progress: keep it out of this command's output
        with _stdout_lock, contextlib.redirect_stdout(log):
            notes = clone_car.build(car_root_of(root, car_id), new_id, out_dir, car_name,
                                    info.get("year", CLONE_YEAR), info.get("brand", CLONE_BRAND),
                                    meta["variant_name"], stock_loc, {k: info.get(k) for k in STOCK_PROPERTIES},
                                    pack=False)
    except ValueError as e:
        if not str(e).startswith("self-check failed"):
            raise
        raise ValueError("clone self-check failed:\n" + log.getvalue().rstrip()) from None
    car_root = car_root_of(out_dir, new_id)
    edits, tyre_edits, applied = {}, {}, []
    # flags last: a flag wins over a value on the same field
    for s, r in sorted(changed, key=lambda sr: sr[0]["kind"] == "flag"):
        item = {"id": s["id"], "old": r["default"], "new": r["value"], "files": []}
        applied.append(item)
        if s["kind"] == "meta":
            item["files"].append(new_id + "." + clone_car.MODDED_TYPE if s["handler"] == "name_suffix"
                                 else "/".join(clone_car.LOC_PATH))
        elif s["kind"] == "curve_scale":
            text, _ = get_value(load_msg(car_path(car_root, renamed(r["targets"][0]["rel"], car_id, new_id)))[0],
                                s["curve_from"]["path"])
            path = curve_path(out_dir, text)
            curve, name = load_msg(path)
            scale_curve(curve, r["value"])
            save_msg(path, name, curve)
            item["files"].append(os.path.relpath(path, car_root).replace(os.sep, "/"))
        elif s["kind"] == "flag":
            for t in r["targets"]:
                if t["resolved"] and not (t["absent"] and s["value"] == 0):
                    edits.setdefault(renamed(t["rel"], car_id, new_id), []).append((item, t["path"], s["value"]))
        else:
            v = to_f32(r["value"]) if s["type"] == "float" else r["value"]
            if s.get("choice_values"):
                v = s["choice_values"][v]
            for t in r["targets"]:
                if t["resolved"] and t["file"][1:] in TYRE_ROLES:
                    tyre_edits.setdefault(t["file"][1:], []).append((item, t["path"], v))
                elif t["resolved"]:
                    edits.setdefault(renamed(t["rel"], car_id, new_id), []).append((item, t["path"], v))
    for rel, items in edits.items():
        path = car_path(car_root, rel)
        obj, name = load_msg(path)
        for item, field, v in items:
            put_value(obj, field, v)
            if rel not in item["files"]:
                item["files"].append(rel)
        save_msg(path, name, obj)
    cache = {}
    for role, items in tyre_edits.items():
        notes.append(build_tyre(root, car_id, new_id, car_root, role, items, cache))
    pkg = os.path.join(out_dir, new_id + ".kspkg")
    # kspkg and clone_car print their progress: keep it out of this command's output
    with _stdout_lock, contextlib.redirect_stdout(io.StringIO()):
        kspkg.cmd_pack(out_dir, pkg)
    result = {"new_id": new_id, "build_dir": out_dir, "package": pkg, "size": os.path.getsize(pkg),
              "applied": applied, "notes": notes, "installed": None, "backup": None}
    if install:
        mods = os.path.abspath(os.path.expandvars(mods_dir or clone_car.DEFAULT_MODS))
        backups = os.path.join(work, "backups")
        # clone_car.install only prints the backup name, so find it as the new file in the backups folder
        before = listing(backups)
        # kspkg and clone_car print their progress: keep it out of this command's output
        with _stdout_lock, contextlib.redirect_stdout(io.StringIO()):
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
        try:
            info = load_stock_info(work, car_id) if extracted else None
        except ValueError:
            info = None
        display_name = info["display_name"] if info else names.get(car_id) or labels.get(car_id) or car_id
        new_id = new_id_for(car_id)
        rows.append({"id": car_id, "default": car_id == cars["default"], "label": labels.get(car_id, display_name),
                     "display_name": display_name, "extracted": extracted, "tested": car_id in labels,
                     "new_id": new_id, "installed": os.path.isfile(os.path.join(mods, new_id + ".kspkg")),
                     "bytes": count_tree(car_root)["bytes"] if extracted else None})
    return sorted(rows, key=lambda r: (r["display_name"].lower(), r["id"]))


def table(headers, rows):
    rows = [[str(c) for c in r] for r in rows]
    widths = [max(len(r[i]) for r in [headers] + rows) for i in range(len(headers))]
    lines = [" | ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in [headers] + rows]
    return "\n".join([lines[0], "-+-".join("-" * w for w in widths)] + lines[1:])


def consistency_text(row):
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


def warn_unknown_state(work, car_id, catalogue=None):
    for sid in unknown_state_ids(work, car_id, catalogue):
        print("warning: ignoring unknown setting '%s' in the saved state" % sid, file=sys.stderr)


def display_name_of(work, car_id):
    info = load_stock_info(work, car_id)
    if info:
        return info["display_name"]
    return next(r["display_name"] for r in list_cars(work) if r["id"] == car_id)


def note_untested(car_id):
    if car_id not in [c["id"] for c in load_cars()["cars"]]:
        print("note: %s is not in the tested list; results are unverified" % car_id)


def doc_text(car_id, display_name, rows):
    """Markdown reference of one car: one table per group, the copies-differ section when needed, the fixed "Not covered yet" list."""
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


def usage():
    print(__doc__.split("\n\n")[1])
    sys.exit(2)


def cli_args(flags, switches=()):
    try:
        return parse_args(sys.argv[2:], flags, switches)
    except ValueError:
        usage()


def mods_arg(opts):
    return clone_car.expand(opts["mods"]) if "mods" in opts else None


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if cmd == "cars":
            pos, opts = cli_args(("game", "mods", "work"), ("tested",))
            if pos:
                usage()
            work, _ = start(opts)
            game = os.path.expandvars(opts.get("game", DEFAULT_GAME))
            print(table(["id", "display name", "extracted", "tested", "new id", "installed", "size"],
                        [[r["id"], r["display_name"], "yes" if r["extracted"] else "no", "yes" if r["tested"] else "no",
                          r["new_id"], "yes" if r["installed"] else "no",
                          "%.1f MB" % (r["bytes"] / (1 << 20)) if r["extracted"] else "-"]
                         for r in list_cars(work, mods_arg(opts), "tested" in opts, game)]))
            if "tested" not in opts and load_cars_index(work, game) is None:
                print("note: the game package is not available and there is no car index, "
                      "only the tested cars are listed")
        elif cmd == "init":
            pos, opts = cli_args(("car", "game", "work"))
            if pos:
                usage()
            work, car_id = start(opts)
            note_untested(car_id)
            res = init(work, car_id, os.path.expandvars(opts.get("game", DEFAULT_GAME)))
            print("base already present" if res["present"] else "extracted the stock car")
            print("%s: %d files, %d folders, %d bytes" % (res["dir"], res["files"], res["dirs"], res["bytes"]))
            print("stock localization %s" % res["stock_loc"])
            print("stock info %s" % res["stock_info"])
            print("shared tyre files %s" % res["tyre_files"])
        elif cmd == "defaults":
            pos, opts = cli_args(("car", "work"), ("hidden",))
            if pos:
                usage()
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
            pos, opts = cli_args(("car", "work"))
            if len(pos) != 2:
                usage()
            res = set_value(*start(opts), pos[0], pos[1])
            for w in res["warnings"]:
                print("warning: " + w, file=sys.stderr)
            print("%s = %s" % (res["id"], fmt(res["value"])))
        elif cmd == "unset":
            pos, opts = cli_args(("car", "work"))
            if len(pos) != 1:
                usage()
            res = unset_value(*start(opts), pos[0])
            print("%s %s" % (res["id"], "removed from the state" if res["removed"] else "was not set"))
        elif cmd == "show":
            pos, opts = cli_args(("car", "work"))
            if pos:
                usage()
            work, car_id = start(opts)
            cat = load_catalogue()
            warn_unknown_state(work, car_id, cat)
            rows = effective_rows(work, car_id, cat)
            print(table(["", "id", "value", "default", "unit"],
                        [["*" if r["changed"] else "", r["id"], fmt(r["value"]), fmt(r["default"]), r["unit"]]
                         for r in rows]))
        elif cmd == "apply":
            pos, opts = cli_args(("car", "new-id", "mods", "work"), ("no-install",))
            if pos:
                usage()
            work, car_id = start(opts)
            note_untested(car_id)
            cat = load_catalogue()
            warn_unknown_state(work, car_id, cat)
            res = apply(work, car_id, opts.get("new-id"), "no-install" not in opts, mods_arg(opts), cat)
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
            pos, opts = cli_args(("car", "out", "work"), ("all",))
            if pos or ("all" in opts and ("car" in opts or "out" in opts)):
                usage()
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
            usage()
    except (ValueError, OSError) as e:
        sys.exit("error: %s" % e)


if __name__ == "__main__":
    main()
