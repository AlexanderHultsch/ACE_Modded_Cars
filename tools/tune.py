"""Settings engine of the tuner: read defaults, keep the chosen values, build and install the tuned car.

usage:
  python tools/tune.py cars     [--tested | --modded] [--game <content.kspkg>] [--mods <dir>] [--work <dir>]
  python tools/tune.py init     [--car ID] [--game <content.kspkg>] [--work <dir>]
  python tools/tune.py defaults [--car ID] [--tune ID] [--hidden] [--work <dir>]
  python tools/tune.py set      <id> <value> [--car ID] [--tune ID] [--work <dir>]
  python tools/tune.py unset    <id> [--car ID] [--tune ID] [--work <dir>]
  python tools/tune.py show     [--car ID] [--tune ID] [--work <dir>]
  python tools/tune.py apply    [--car ID] [--tune ID | --new-id ID] [--no-install] [--mods <dir>] [--work <dir>]
  python tools/tune.py duplicate [--car ID] [--tune ID | --draft] [--new-id ID] [--suffix TEXT] [--mods <dir>] [--work <dir>]
  python tools/tune.py doc      [--car ID | --all] [--out <file>] [--work <dir>]
  python tools/tune.py tyres        [--work <dir>]
  python tools/tune.py tyre-sources [--work <dir>]
  python tools/tune.py tyre-new     --name <text> --source <key> [--work <dir>]
  python tools/tune.py tyre-show    <id> [--work <dir>]
  python tools/tune.py tyre-set     <id> <setting> <value> [--work <dir>]
  python tools/tune.py tyre-unset   <id> <setting> [--work <dir>]
  python tools/tune.py tyre-delete  <id> [--work <dir>]
  python tools/tune.py garage       [--tune ID | --draft] [--car ID] [--work <dir>]
  python tools/tune.py garage-set   <key> [<key> ...] [--tune ID | --draft] [--car ID] [--work <dir>]
  python tools/tune.py garage-reset [--tune ID | --draft] [--car ID] [--work <dir>]

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
Modded cars (tuned copies of a stock car; library functions list_tunes, list_modded, duplicate_tune, new_tune_from_draft):
the first one is the default tune <new_id> with the files above; every further one has its own tuned-car id (same length
as the stock id) and lives in <work>/<car>/tunes/<id>/{tune_state.json, meta.json = {"stock": <car>}}; the unsaved working
state of a stock car is <work>/<car>/draft_state.json (state functions take tune=None for the default tune, DRAFT or an id).
Every modded car of a stock car has its own name suffix; the suffix of a copy is counted up (_MY -> _MY2 -> _MY3).

cars:    table of every game car sorted by display name: id, display name (stock_info.json when extracted, else the
          game's name), extracted yes/no, tested yes/no (listed in tuner/cars.json), new id, installed yes/no
          (<new_id>.kspkg in the mods folder), size of the extracted stock car. --tested lists only the tested cars.
          Without the cache and the game package (--game, default the Steam install) only the tested cars are
          listed, with a note. --modded lists the modded cars instead: id, stock car, label (stock name plus suffix),
          suffix, installed yes/no (<id>.kspkg in the mods folder), built yes/no (build/<id>/<id>.kspkg).
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
          --tune ID (also accepted by defaults and apply) picks the modded car whose state is shown or changed, an id
          from cars --modded (default: the default tune <new_id>, the state file above); an unknown id is an error.
          defaults prints the stock values, which do not depend on a tune: --tune is only checked there.
apply:    refuses to install while AssettoCorsaEVO.exe runs (--no-install builds anyway). Always starts from the pristine <work>/<car>/base: clones the car
          under the new id into <work>/<car>/build/<new_id>.partial, writes every changed setting into ALL its resolved
          target files, packs <new_id>.kspkg, renames the folder to build/<new_id> (a failed run keeps the previous
          build and leaves only the .partial folder, removed by the next run) and (unless --no-install) installs the
          package to the mods folder (default %USERPROFILE%\\Saved Games\\ACE\\mods) with a backup of the previous package in <work>/backups. Only changed
          settings must be applicable. For a car other than the default car, the stock info must exist. Tyres: for each
          axle (front, rear) that has at least one changed tyre setting, the stock tyre file (shared, from base) is
          copied to content/cars/<new_id>/data/tyres/<new_id>_front.tyre (_rear), the changed values are written there,
          and the references to the stock file are pointed at the copy: the entries of the .car's frontTyreCompounds
          (rearTyreCompounds) and the front_tyre_data_path (rear_tyre_data_paths) of every presets/*.compatibletyres
          that name the stock file (compared case-insensitively). Other compounds and the shared files stay untouched;
          an axle without a changed tyre setting gets no file and no changed reference. A changed tyre setting of a
          car whose tyre file is inside the car folder (not shared) is refused: not supported yet.
          --tune ID builds that modded car: its own state, its id as the new id, its name suffix; --tune and --new-id
          cannot be combined. A suffix that another modded car of the same stock car uses is refused before building.
          --new-id ID alone builds the state of the tune with that id (the default tune when it is left out); an id
          that is not a modded car is refused once the stock car has modded cars, but accepted for a stock car without any
          (old "new copy" use: no state, defaults only).
duplicate: copies the saved values of a modded car (--tune SRC; default the default tune), or of the unsaved draft (--draft),
          to a new modded car of the stock car and prints its id and name suffix. --new-id picks the id (valid, same length
          as the stock id, unused; the default id <new_id> only while the default tune has neither state nor build),
          default the first free <new_id> with its last two characters replaced by 01 .. 99; --mods adds the packages in
          that folder to the ids that are taken. --suffix picks the name suffix (must not be used by another modded car of
          the stock car); default the suffix of the source, counted up when taken.
doc:      writes a Markdown reference of the settings applicable to the car with their defaults from
          <work>/<car>/base to <file> (default docs/settings/<car>.md in the repository); the car must be extracted.
          --all writes that file for every tested car of tuner/cars.json, extracting the cars that are not extracted
          yet first (--car and --out cannot be combined with --all).
Tyre library (library functions list_source_tyres, list_tyres, load_tyre, create_tyre, rename_tyre, set_tyre_source, set_tyre_value,
unset_tyre_value, reset_tyre, tyre_rows, tyre_users, delete_tyre; no car needed, so these commands take no --car): a library tyre is
a name, a source (a front and a rear game tyre file, shared files below content\\cars\\common_phsx) and the changed values of the
tyre settings of the catalogue (the ones whose targets are @tyre_front or @tyre_rear) relative to that source. It is kept in
<work>/tyres/<id>.json = {"version": 1, "name", "source": {"front", "rear"}, "values": {setting id: value}}; the id is 1 to 24
characters a-z, 0-9, _ made from the name, the name is 1 to 40 characters and unique ignoring case. The garage tyre selection of a
modded car (which tyres its garage offers) is the list "_tyres" in its state file (tune_state.json, draft_state.json): ordered
entries "own:<tyre id>" (a library tyre) and "stock:<front>|<rear>" (a stock compound of the car: the pair keys of tyre-sources,
read from the presets of the car's own base). It is not a setting: it is never reported as unknown, shown in show or counted
as an applied setting, and duplicate and Create copy it with the rest of the state. No "_tyres" entry = the car is not touched
(all stock compounds, apply as before). The order is always: own tyres first (by name, then id), then the stock compounds in
the order of the car's presets; the first ticked entry is the starting tyre. tyre-delete refuses while a state lists the
library tyre (the draft counts). The garage commands take --car, --tune and --draft like show. Library functions car_stock_tyres, garage_choices, set_garage, reset_garage. apply with a
selection writes data/tyres/own_<id>_front.tyre and _rear.tyre (the source files with the changed values) of every ticked
own tyre into the car, and sets frontTyreCompounds / rearTyreCompounds of the .car and physic_compounds of every
presets/*.compatibletyres to the ticked tyres in that order (unticked stock compounds are dropped, entries that no preset
pair names stay at the end); it runs before the per-car tyre values above, which need the stock starting tyre ticked. Whether
the game accepts such lists is not tested.
tyres:        lists the library: id, name, source, number of changed values; a damaged file is listed with its error.
tyre-sources: lists the tyre pairs the extracted cars offer (physic_compounds of their presets/*.compatibletyres whose front and rear
          files are shared game files present in the car's base): key (front|rear), label, cars. It extracts nothing.
tyre-new:     creates a library tyre from a source key of tyre-sources and prints its id.
tyre-show:    prints the tyre settings with their value, the default read from the source files and the unit; changed ones are
          marked *; a setting whose default cannot be read from the source file is listed with the reason.
tyre-set/tyre-unset: change or remove one value of a library tyre; set refuses a setting that is not a tyre setting.
tyre-delete:  removes a library tyre that no modded car uses.
garage:       shows the choices of the car with their key: ticked (x), start (the first ticked tyre) and the label; a saved key that
          is no longer valid is listed as a warning. Without a saved selection every stock compound is ticked.
garage-set:   ticks exactly the given keys (own:<id>, stock:<front>|<rear>), at least one; all stock tyres and no own tyre is
          the default and removes the entry.
garage-reset: removes the selection (the car is not touched any more).
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
import copy
import difflib
import io
import json
import math
import os
import pathlib
import re
import shutil
import struct
import subprocess
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
GAME_EXE = "AssettoCorsaEVO.exe"
OLD_LAYOUT = ("base", "build", "tune_state.json", "stock_info.json", "defaults.json")
TUNES = "tunes"
DRAFT = "draft"
DOC_DIR = REPO / "docs" / "settings"
DOC_INTRO = (
    "This file lists the tuner settings (`tuner/catalogue.json`) of the %s (car id `%s`) with their defaults. It is "
    "generated by `python tools/tune.py doc --car %s`, do not edit it by hand. The defaults are read from the stock "
    "car in the game. Applicable settings only: settings this car does not have are hidden. \"unverified\" means the "
    "meaning is guessed from the field name and not confirmed in the game. The settings of the group Display change only text. "
    "The setup limits (the settings ending in _min or _max) are not yet tested in the game.")
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
TYRES_DIR = "tyres"
TYRE_KEY = "_tyres"
TYRE_ID = re.compile(r"[a-z0-9_]{1,24}")
TYRE_ID_MAX = 24
TYRE_NAME_MAX = 40
TYRE_VERSION = 1
TYRE_FILES = tuple("@" + r for r in TYRE_ROLES)
OWN_KEY = "own:"
STOCK_KEY = "stock:"

_index_error = []
_tyre_lock = threading.Lock()
_resolve_lock = threading.Lock()
_resolved = {}
_stdout_lock = threading.Lock()


def schema():
    return car_json.load_schema()


def work_dir(arg=None):
    try:
        return clone_car.expand(arg or DEFAULT_WORK)
    except ValueError:
        raise ValueError("cannot expand the work directory %r" % (arg or DEFAULT_WORK)) from None


def game_running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + GAME_EXE, "/NH", "/FO", "CSV"],
                             capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0 and GAME_EXE.lower() in out.stdout.decode("ascii", "replace").lower()


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


def check_tune_id(work, car_id, tune):
    if not isinstance(tune, str):
        raise ValueError("tune id must be text, got %r" % (tune,))
    # ids only: the "unused" folder never exists (as in apply)
    clone_car.validate(car_id, tune, os.path.join(build_dir(work, car_id), "unused"))


def is_default_tune(car_id, tune):
    return tune is None or tune == new_id_for(car_id)


def tune_dir(work, car_id, tune):
    """Folder of the state file of a tune: the car folder for the default tune (None or new_id_for) and for the draft,
    <car>/tunes/<id> for any other tuned-car id (which must be valid for the car)."""
    if is_default_tune(car_id, tune) or tune == DRAFT:
        return car_work(work, car_id)
    check_tune_id(work, car_id, tune)
    return os.path.join(car_work(work, car_id), TUNES, tune)


def state_path(work, car_id, tune=None):
    return os.path.join(tune_dir(work, car_id, tune), "draft_state.json" if tune == DRAFT else "tune_state.json")


def load_state(work, car_id, tune=None):
    path = state_path(work, car_id, tune)
    if not os.path.exists(path):
        return {}
    state = read_json(path)
    if not isinstance(state, dict):
        raise ValueError("%s: expected an object" % path)
    return state


def save_state(work, car_id, state, tune=None):
    path = state_path(work, car_id, tune)
    save_json(path, state)
    meta = os.path.join(os.path.dirname(path), "meta.json")
    if not (is_default_tune(car_id, tune) or tune == DRAFT) and not os.path.exists(meta):
        save_json(meta, {"stock": car_id})


def unknown_state_ids(work, car_id, catalogue=None, tune=None):
    known = {s["id"] for s in (catalogue or load_catalogue())["settings"]}
    return [sid for sid in load_state(work, car_id, tune) if sid not in known and sid != TYRE_KEY]


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


def set_value(work, car_id, setting_id, text, catalogue=None, tune=None):
    cat = catalogue or load_catalogue()
    s = find_setting(cat, setting_id)
    v = coerce(s, text)
    row = resolve_defaults(work, car_id, dict(cat, settings=[s]), hidden=True)[0]
    if not row["applicable"]:
        raise ValueError("%s is not applicable to %s: %s" % (setting_id, car_id, row["reason"]))
    state = load_state(work, car_id, tune)
    state[setting_id] = v
    save_state(work, car_id, state, tune)
    warning = range_warning(s, v)
    return {"id": setting_id, "value": v, "warnings": [warning] if warning else []}


def unset_value(work, car_id, setting_id, catalogue=None, tune=None):
    state = load_state(work, car_id, tune)
    if setting_id not in state or setting_id == TYRE_KEY:
        find_setting(catalogue or load_catalogue(), setting_id)
    removed = state.pop(setting_id, None) is not None
    if removed:
        save_state(work, car_id, state, tune)
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
        forget_resolved(work, car_id)
        res = dict(count_tree(car_root), present=False, dir=car_root)
    res["stock_loc"] = ensure_stock_loc(work, game)
    res["stock_info"] = write_stock_info(work, car_id, game)
    try:
        res["tyre_files"] = ensure_tyre_files(work, car_id, game)
    except (ValueError, OSError) as e:
        res["tyre_files"] = "not extracted (%s)" % e
    forget_resolved(work, car_id)
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
        forget_resolved(work, car_id)
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


def forget_resolved(work, car_id):
    """Drop the cached rows of resolve_defaults for a car (its base or its shared tyre files changed)."""
    with _resolve_lock:
        for key in [k for k in _resolved if k[:2] == (work, car_id)]:
            del _resolved[key]


def resolve_stamp(work, car_id):
    # init rewrites every .car file when it extracts, so their (mtime_ns, size) changes whenever what resolve_defaults reads can have changed
    try:
        data = find_ci(car_root_of(base_dir(work, car_id), car_id), "data")
        paths = [os.path.join(data, n) for n in sorted(os.listdir(kspkg.long_path(data))) if n.lower().endswith(".car")]
        paths.append(stock_info_path(work, car_id))
        return [(st.st_mtime_ns, st.st_size) if st else None for st in map(stat_or_none, paths)]
    except (ValueError, OSError):
        return None


def stat_or_none(path):
    try:
        return os.stat(kspkg.long_path(path))
    except FileNotFoundError:
        return None


def resolve_defaults(work, car_id, catalogue=None, game=DEFAULT_GAME, hidden=False):
    """Every setting with its default; hidden=False keeps only the settings applicable to the car, hidden=True
    returns all of them, each with applicable and reason (None when applicable). The resolved rows are cached per
    (work, car, catalogue) while resolve_stamp is unchanged (not when the tyre files or the stock info could not be
    read); the caller gets its own copy."""
    cat = catalogue or load_catalogue()
    root = base_dir(work, car_id)
    if not os.path.isdir(kspkg.long_path(car_root_of(root, car_id))):
        raise ValueError("no base car in %s, run init first" % root)
    key, stamp = (work, car_id, json.dumps(cat, sort_keys=True)), resolve_stamp(work, car_id)
    with _resolve_lock:
        hit = _resolved.get(key)
    if hit and stamp is not None and hit[0] == stamp:
        rows = copy.deepcopy(hit[1])
    else:
        rows, cacheable = resolve_rows(work, car_id, cat, game)
        if cacheable and stamp is not None and resolve_stamp(work, car_id) == stamp:
            with _resolve_lock:
                _resolved[key] = (stamp, copy.deepcopy(rows))
    return rows if hidden else [r for r in rows if r["applicable"]]


def resolve_rows(work, car_id, cat, game):
    """All rows of resolve_defaults and whether they may be cached."""
    root = base_dir(work, car_id)
    car_root = car_root_of(root, car_id)
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
    return rows, tyre_error is None and (stock_name is None or complete_stock_info(info))


def effective_rows(work, car_id, catalogue=None, hidden=False, tune=None):
    cat = catalogue or load_catalogue()
    state = load_state(work, car_id, tune)
    rows = resolve_defaults(work, car_id, cat, hidden=hidden)
    for row in rows:
        s = find_setting(cat, row["id"])
        row["value"] = coerce(s, state[s["id"]]) if s["id"] in state else row["default"]
        row["changed"] = s["id"] in state and not same(s, row["value"], row["default"])
    return rows


def effective_row(work, car_id, setting_id, catalogue=None, tune=None):
    """The row of one setting as effective_rows(hidden=True) gives it, resolving only that setting."""
    cat = catalogue or load_catalogue()
    return effective_rows(work, car_id, dict(cat, settings=[find_setting(cat, setting_id)]), hidden=True, tune=tune)[0]


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


def build_tyre(root, car_id, new_id, car_root, role, items, cache, counts=None):
    """Give the tuned car its own copy of the stock tyre file of an axle (role tyre_front / tyre_rear): copy it from
    base to data/tyres/<new_id>_<axle>.tyre, write the changed values (items: (item, field, value)) and point the
    references of the stock file at the copy. Returns a note for the build log; counts, when given, gets the number of
    references that were pointed at the copy (.car entries and compatibletyres entries together)."""
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
    if counts is not None:
        counts.append(in_car + in_presets)
    return "note: tyre %s: own file %s replaces %s in %d .car entry(ies) and %d compatibletyres entry(ies)" % (
        axle, new_text, stock_text, in_car, in_presets)


def apply(work, car_id, new_id=None, install=True, mods_dir=None, catalogue=None, game=DEFAULT_GAME):
    cat = catalogue or load_catalogue()
    new_id = new_id or new_id_for(car_id)
    root = base_dir(work, car_id)
    if not os.path.isdir(kspkg.long_path(car_root_of(root, car_id))):
        raise ValueError("no base car in %s, run init first" % root)
    mods = clone_car.expand(mods_dir or clone_car.DEFAULT_MODS) if install else None
    # ids only: the "unused" folder never exists, an old build of the same id is replaced below
    clone_car.validate(car_id, new_id, os.path.join(build_dir(work, car_id), "unused"))
    if (not is_default_tune(car_id, new_id) and not os.path.isdir(kspkg.long_path(tune_dir(work, car_id, new_id)))
            and list_tunes(work, car_id)):
        raise ValueError("%s is not a modded car of %s, create it with duplicate first" % (new_id, car_id))
    rows = effective_rows(work, car_id, cat, hidden=True, tune=new_id)
    changed = [(s, r) for s, r in zip(cat["settings"], rows) if r["changed"]]
    bad = ["%s (%s)" % (s["id"], r["reason"]) for s, r in changed if not r["applicable"]]
    if bad:
        raise ValueError("cannot apply the changed setting(s), not applicable to %s: %s" % (car_id, ", ".join(bad)))
    for s, r in changed:
        for t in r["targets"] if s["kind"] == "value" else []:
            if t["resolved"] and t["file"][1:] in TYRE_ROLES and not t["rel"].startswith(SHARED):
                raise ValueError("%s: the tyre file is inside the car folder, not supported yet" % t["file"])
    info = load_stock_info(work, car_id)
    if info is None and car_id != load_cars()["default"]:
        raise ValueError("stock info missing, run init with the game installed")
    info = info or {}
    name_suffix = next(r["value"] for r in rows if r["id"] == name_suffix_setting(cat)["id"])
    owner = suffix_owner(work, car_id, name_suffix, exclude=new_id)
    if owner:
        raise ValueError("name suffix %s is already used by %s" % (name_suffix, owner))
    state = load_state(work, car_id, new_id)
    garage = garage_plan(work, car_id, new_id, state, cat) if TYRE_KEY in state else None
    out_dir = os.path.join(build_dir(work, car_id), new_id)
    # the build always starts from the pristine base, in <new_id>.partial: the previous build of this id stays until the new one is complete
    part = out_dir + ".partial"
    if os.path.exists(kspkg.long_path(part)):
        remove_tree(work, part)
    meta = {s["handler"]: r["value"] for s, r in zip(cat["settings"], rows) if s["kind"] == "meta"}
    with contextlib.suppress(ValueError, OSError):
        ensure_stock_loc(work, game)
    stock_loc = stock_loc_path(work) if os.path.isfile(stock_loc_path(work)) else None
    car_name = (info.get("display_name") or preset_display_name(car_root_of(root, car_id))) + meta["name_suffix"]
    log = io.StringIO()
    try:
        # kspkg and clone_car print their progress: keep it out of this command's output
        with _stdout_lock, contextlib.redirect_stdout(log):
            notes = clone_car.build(car_root_of(root, car_id), new_id, part, car_name,
                                    info.get("year", CLONE_YEAR), info.get("brand", CLONE_BRAND),
                                    meta["variant_name"], stock_loc, {k: info.get(k) for k in STOCK_PROPERTIES},
                                    pack=False)
    except ValueError as e:
        if not str(e).startswith("self-check failed"):
            raise
        raise ValueError("clone self-check failed:\n" + log.getvalue().rstrip()) from None
    car_root = car_root_of(part, new_id)
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
            path = curve_path(part, text)
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
    if garage:
        notes += write_garage(root, car_id, new_id, car_root, garage, cache)
    for role, items in tyre_edits.items():
        counts = []
        notes.append(build_tyre(root, car_id, new_id, car_root, role, items, cache, counts))
        if garage and not sum(counts):
            raise ValueError("tyre settings are changed but the stock starting tyre of the car is not ticked in the garage, "
                             "tick it or reset the tyre values")
    # kspkg and clone_car print their progress: keep it out of this command's output
    with _stdout_lock, contextlib.redirect_stdout(io.StringIO()):
        kspkg.cmd_pack(part, os.path.join(part, new_id + ".kspkg"))
    if os.path.exists(kspkg.long_path(out_dir)):
        remove_tree(work, out_dir)
    os.rename(kspkg.long_path(part), kspkg.long_path(out_dir))
    pkg = os.path.join(out_dir, new_id + ".kspkg")
    result = {"new_id": new_id, "tune": new_id, "name_suffix": meta["name_suffix"], "build_dir": out_dir, "package": pkg, "size": os.path.getsize(pkg),
              "applied": applied, "notes": notes, "installed": None, "backup": None}
    if install:
        # kspkg and clone_car print their progress: keep it out of this command's output
        with _stdout_lock, contextlib.redirect_stdout(io.StringIO()):
            result["backup"] = clone_car.install(pkg, mods, os.path.join(work, "backups"))
        result["installed"] = os.path.join(mods, os.path.basename(pkg))
    return result


def list_cars(work, mods_dir=None, tested_only=False, game=DEFAULT_GAME, sizes=True):
    """Every car of the game (the tested cars only when the car index is not available or tested_only), sorted by
    display name. sizes=False leaves bytes None without walking the car folders."""
    cars = load_cars()
    mods = clone_car.expand(mods_dir or clone_car.DEFAULT_MODS)
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
                     "bytes": count_tree(car_root)["bytes"] if extracted and sizes else None})
    return sorted(rows, key=lambda r: (r["display_name"].lower(), r["id"]))


def name_suffix_setting(catalogue=None):
    for s in (catalogue or load_catalogue())["settings"]:
        if s.get("handler") == "name_suffix":
            return s
    raise ValueError("the catalogue has no name_suffix setting")


def state_suffix(state, s):
    return coerce(s, state[s["id"]]) if s["id"] in state else s["default"]


def is_tune_id(work, car_id, name):
    try:
        check_tune_id(work, car_id, name)
    except ValueError:
        return False
    return name != DRAFT


def tunes_of(work, car_id, s):
    """The tunes of a stock car for the name suffix setting s, default tune first, then by id. The default tune is
    listed when its state file or its build folder exists, every other tune when tunes/<id>/tune_state.json exists."""
    default = new_id_for(car_id)
    found = []
    has_state = os.path.isfile(kspkg.long_path(state_path(work, car_id)))
    if has_state or os.path.isdir(kspkg.long_path(os.path.join(build_dir(work, car_id), default))):
        found.append((default, has_state))
    folder = os.path.join(car_work(work, car_id), TUNES)
    for name in sorted(os.listdir(kspkg.long_path(folder))) if os.path.isdir(kspkg.long_path(folder)) else []:
        if name != default and is_tune_id(work, car_id, name) and os.path.isfile(kspkg.long_path(state_path(work, car_id, name))):
            found.append((name, True))
    return sorted(({"id": i, "stock": car_id, "default": i == default, "name_suffix": state_suffix(load_state(work, car_id, i), s),
                    "has_state": h} for i, h in found), key=lambda t: (not t["default"], t["id"]))


def list_tunes(work, car_id):
    """The modded cars (tuned copies) of a stock car: {id, stock, default, name_suffix, has_state}, default tune first,
    then by id. name_suffix is the suffix in the saved state, the catalogue default when the state has none."""
    return tunes_of(work, car_id, name_suffix_setting())


def car_folders(work):
    """Ids of the stock cars that have a folder in the work folder (a base, a build, a state, a draft or tunes), sorted."""
    if not os.path.isdir(kspkg.long_path(work)):
        return []
    return sorted(n for n in os.listdir(kspkg.long_path(work)) if re.fullmatch(r"[a-z0-9_]+", n)
                  and any(os.path.exists(kspkg.long_path(os.path.join(work, n, x)))
                          for x in ("base", "build", "tune_state.json", "draft_state.json", TUNES)))


def known_tune_ids(work, mods_dir=None):
    """Every tuned-car id that must not be reused: the default tune id of each tested car, each car of the cached car
    index and each car folder of the work folder, every tune folder below <work>/*/tunes and, when mods_dir is given,
    every <id>.kspkg in it. Offline: the car index is read from its cache only."""
    # "" is never a file, so load_cars_index never reads the game package
    cars = {c["id"] for c in load_cars()["cars"]} | {c["id"] for c in load_cars_index(work, "") or []} | set(car_folders(work))
    known = {new_id_for(c) for c in cars}
    for car_id in car_folders(work):
        folder = os.path.join(car_work(work, car_id), TUNES)
        if os.path.isdir(kspkg.long_path(folder)):
            known.update(n for n in os.listdir(kspkg.long_path(folder)) if os.path.isdir(kspkg.long_path(os.path.join(folder, n))))
    if mods_dir is not None:
        mods = clone_car.expand(mods_dir)
        if os.path.isdir(kspkg.long_path(mods)):
            known.update(n[:-len(".kspkg")].lower() for n in os.listdir(kspkg.long_path(mods)) if n.lower().endswith(".kspkg"))
    return known


def free_tune_id(work, car_id, mods_dir=None):
    """The first unused tuned-car id of a stock car: the default id with its last two characters replaced by 01, 02, ...
    99 (same length as the stock id)."""
    base, known = new_id_for(car_id), known_tune_ids(work, mods_dir)
    for n in range(1, 100):
        candidate = base[:-2] + "%02d" % n
        if candidate in known:
            continue
        try:
            check_tune_id(work, car_id, candidate)
        except ValueError:
            continue
        return candidate
    raise ValueError("no free tuned car id left for %s (%s01 .. %s99 are taken or invalid)" % (car_id, base[:-2], base[:-2]))


def suffix_owner(work, car_id, suffix, exclude=None):
    """Id of a tune of the stock car (other than exclude) that uses the name suffix, else None."""
    for t in list_tunes(work, car_id):
        if t["id"] != exclude and t["name_suffix"] == suffix:
            return t["id"]
    return None


def suffix_taken(work, car_id, suffix, exclude=None):
    return suffix_owner(work, car_id, suffix, exclude) is not None


def free_suffix(work, car_id, wanted, exclude=None):
    """wanted when no other tune of the stock car uses it, else the number at its end counted up (_MY -> _MY2 -> _MY3,
    _T1 -> _T2; leading zeros keep their width), the stem cut to stay within the length limit of the setting."""
    coerce(name_suffix_setting(), wanted)
    stem, digits = re.fullmatch(r"(.*?)(\d*)", wanted).groups()
    candidate, n = wanted, int(digits or 1)
    while suffix_taken(work, car_id, candidate, exclude):
        n += 1
        number = str(n).zfill(len(digits))
        if len(number) > NAME_SUFFIX_MAX:
            raise ValueError("no free name suffix left for %s" % wanted)
        candidate = stem[:NAME_SUFFIX_MAX - len(number)] + number
    return candidate


def duplicate_tune(work, car_id, src, new_id=None, suffix=None, mods_dir=None):
    """Copy the saved values of a tune (src: a tune id, None for the default tune, or DRAFT) to a new tune of the stock
    car; returns {id, stock, name_suffix}. new_id None picks free_tune_id; an explicit id must be valid, unused
    (the default id only while the default tune does not exist) and not DRAFT. suffix None keeps the suffix of src
    made unique with free_suffix; an explicit one must not be used by another tune. Nothing is written on an error."""
    s = name_suffix_setting()
    default = new_id_for(car_id)
    if not (is_default_tune(car_id, src) or src == DRAFT) and not os.path.isfile(kspkg.long_path(state_path(work, car_id, src))):
        raise ValueError("%s has no tune %s" % (car_id, src))
    state = copy.deepcopy(load_state(work, car_id, src))
    if new_id is None:
        new_id = free_tune_id(work, car_id, mods_dir)
    else:
        check_tune_id(work, car_id, new_id)
        known = known_tune_ids(work, mods_dir)
        if new_id == default:
            if any(t["default"] for t in list_tunes(work, car_id)):
                raise ValueError("%s is already a tune of %s" % (new_id, car_id))
            known.discard(default)
        if new_id == DRAFT or new_id in known:
            raise ValueError("tuned car id %s is already used or reserved" % new_id)
    if suffix is None:
        suffix = free_suffix(work, car_id, state_suffix(state, s))
    else:
        coerce(s, suffix)
        owner = suffix_owner(work, car_id, suffix)
        if owner:
            raise ValueError("name suffix already used by %s" % owner)
    state[s["id"]] = suffix
    save_state(work, car_id, state, new_id)
    return {"id": new_id, "stock": car_id, "name_suffix": suffix}


def new_tune_from_draft(work, car_id, suffix=None, new_id=None, mods_dir=None):
    """duplicate_tune(DRAFT) for the Apply of a stock car: new_id None takes the default id while the default tune does
    not exist yet (no state, no build), else free_tune_id."""
    if new_id is None and not any(t["default"] for t in list_tunes(work, car_id)):
        new_id = new_id_for(car_id)
    return duplicate_tune(work, car_id, DRAFT, new_id, suffix, mods_dir)


def list_modded(work, mods_dir=None):
    """Every modded car of every stock car with a work folder: {id, stock, label (stock display name + suffix), name_suffix,
    default, installed (<id>.kspkg in the mods folder), built (build/<id>/<id>.kspkg)}, sorted by label. Stock cars without
    tunes give nothing; a damaged stock_info.json falls back to the cached car index, the tested label or the car id."""
    s = name_suffix_setting()
    mods = clone_car.expand(mods_dir or clone_car.DEFAULT_MODS)
    labels = {c["id"]: c["label"] for c in load_cars()["cars"]}
    names = {c["id"]: c["display_name"] for c in load_cars_index(work, "") or []}
    rows = []
    for car_id in car_folders(work):
        tunes = tunes_of(work, car_id, s)
        try:
            info = load_stock_info(work, car_id) if tunes else None
        except (ValueError, OSError):
            info = None
        stock_name = info["display_name"] if info else names.get(car_id) or labels.get(car_id) or car_id
        for t in tunes:
            rows.append({"id": t["id"], "stock": car_id, "label": stock_name + t["name_suffix"], "name_suffix": t["name_suffix"],
                         "default": t["default"], "installed": os.path.isfile(os.path.join(mods, t["id"] + ".kspkg")),
                         "built": os.path.isfile(kspkg.long_path(os.path.join(build_dir(work, car_id), t["id"], t["id"] + ".kspkg")))})
    return sorted(rows, key=lambda r: (r["label"].lower(), r["id"]))


def tyres_dir(work):
    return os.path.join(work, TYRES_DIR)


def check_tyre_id(tyre_id):
    if not isinstance(tyre_id, str) or not TYRE_ID.fullmatch(tyre_id):
        raise ValueError("bad tyre id %r: use 1 to %d characters a-z, 0-9 and _" % (tyre_id, TYRE_ID_MAX))


def tyre_path(work, tyre_id):
    check_tyre_id(tyre_id)
    return os.path.join(tyres_dir(work), tyre_id + ".json")


def tyre_exists(work, tyre_id):
    return os.path.isfile(kspkg.long_path(tyre_path(work, tyre_id)))


def free_tyre_id(work, name):
    """An unused library id made from a name: lower case, every run of other characters one _, at most 24 characters,
    "tyre" for an empty result; a taken id gets 2, 3, ... appended (the base cut to keep the id within 24 characters)."""
    base = re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")[:TYRE_ID_MAX] or "tyre"
    candidate, n = base, 1
    while tyre_exists(work, candidate):
        n += 1
        candidate = base[:TYRE_ID_MAX - len(str(n))] + str(n)
    return candidate


def check_tyre_name(work, name, own_id=None):
    """The stripped name when it is 1 to 40 characters without control characters and no other library tyre has it
    (ignoring case)."""
    if not isinstance(name, str):
        raise ValueError("a tyre name must be text, got %r" % (name,))
    name = name.strip()
    if not 1 <= len(name) <= TYRE_NAME_MAX or re.search(r"[\x00-\x1f\x7f]", name):
        raise ValueError("a tyre name needs 1 to %d characters without control characters" % TYRE_NAME_MAX)
    for t in list_tyres(work):
        if t["id"] != own_id and t.get("name", "").lower() == name.lower():
            raise ValueError("a tyre named %r exists already (%s)" % (t["name"], t["id"]))
    return name


def tyre_label(path):
    text = path[len(GAME_SHARED):] if path.startswith(GAME_SHARED) else path
    return text[:-len(".tyre")] if text.endswith(".tyre") else text


def source_label(front, rear):
    return tyre_label(front) if rear == front else "%s + %s" % (tyre_label(front), tyre_label(rear))


def tyre_settings(catalogue=None):
    """The catalogue settings that write a tyre file (a target with the role @tyre_front or @tyre_rear)."""
    return [s for s in (catalogue or load_catalogue())["settings"] if any(t["file"] in TYRE_FILES for t in s.get("targets", []))]


def tyre_axle(s):
    return next(t["file"] for t in s["targets"] if t["file"] in TYRE_FILES)[len("@tyre_"):]


def tyre_setting(cat, setting_id):
    for s in tyre_settings(cat):
        if s["id"] == setting_id:
            return s
    find_setting(cat, setting_id)
    raise ValueError("%s is not a tyre setting" % setting_id)


def compound_pair(pc):
    """The (front, rear) game paths (game_path_key) of a physic compound: the rear is the first of rear_tyre_data_paths; None
    when the compound has no text front or rear."""
    front = pc.get("front_tyre_data_path") if isinstance(pc, dict) else None
    rear = pc.get("rear_tyre_data_paths") if isinstance(pc, dict) else None
    if isinstance(rear, list):
        rear = rear[0] if rear else None
    if not (isinstance(front, str) and isinstance(rear, str)):
        return None
    return game_path_key(front), game_path_key(rear)


def preset_tyre_pairs(root, car_id):
    """The (front, rear) game paths (game_path_key) of the physic compounds in presets/*.compatibletyres of a car in
    root: the rear is the first of rear_tyre_data_paths; both must be shared game files present below root."""
    folder = find_ci(car_root_of(root, car_id), "presets")
    pairs = []
    for n in sorted(os.listdir(kspkg.long_path(folder))):
        if not n.lower().endswith(".compatibletyres"):
            continue
        try:
            compounds = load_msg(os.path.join(folder, n))[0].get("physic_compounds", [])
        except (ValueError, OSError):
            continue
        for pc in compounds if isinstance(compounds, list) else []:
            pair = compound_pair(pc)
            if pair is None:
                continue
            front, rear = pair
            if (front.startswith(GAME_SHARED) and rear.startswith(GAME_SHARED) and tyre_present(root, front)
                    and tyre_present(root, rear) and (front, rear) not in pairs):
                pairs.append((front, rear))
    return pairs


def list_source_tyres(work):
    """The tyre pairs an extracted car offers as a source for a library tyre: {key (front|rear), front, rear, label, cars},
    sorted by label, then key. Reads the presets of the extracted cars only: nothing is extracted, the game package is not
    needed; a car or preset that cannot be read is skipped."""
    found = {}
    for car_id in car_folders(work):
        try:
            pairs = preset_tyre_pairs(base_dir(work, car_id), car_id)
        except (ValueError, OSError):
            continue
        for front, rear in pairs:
            key = front + "|" + rear
            entry = found.setdefault(key, {"key": key, "front": front, "rear": rear, "label": source_label(front, rear), "cars": []})
            if car_id not in entry["cars"]:
                entry["cars"].append(car_id)
    for entry in found.values():
        entry["cars"].sort()
    return sorted(found.values(), key=lambda e: (e["label"], e["key"]))


def source_tyre(work, source_key):
    for e in list_source_tyres(work):
        if e["key"] == source_key:
            return e
    raise ValueError("unknown tyre source %r, tyre-sources lists the tyre pairs of the extracted cars" % (source_key,))


def load_tyre(work, tyre_id):
    """The library tyre {version, name, source: {front, rear}, values} of <work>/tyres/<id>.json, checked for its shape."""
    path = tyre_path(work, tyre_id)
    if not os.path.isfile(kspkg.long_path(path)):
        raise ValueError("no tyre %r in the library" % tyre_id)
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError("%s: expected an object" % path)
    if type(data.get("version")) is not int or data["version"] != TYRE_VERSION:
        raise ValueError("%s: version %r is not supported (expected %d)" % (path, data.get("version"), TYRE_VERSION))
    if not isinstance(data.get("name"), str) or not data["name"]:
        raise ValueError("%s: name must be text" % path)
    source = data.get("source")
    if not (isinstance(source, dict) and all(isinstance(source.get(k), str) and source[k] for k in ("front", "rear"))):
        raise ValueError("%s: source needs a front and a rear tyre path" % path)
    if not isinstance(data.get("values"), dict):
        raise ValueError("%s: values must be an object" % path)
    return data


def save_tyre(work, tyre_id, name, source, values):
    save_json(tyre_path(work, tyre_id), {"version": TYRE_VERSION, "name": name,
                                         "source": {"front": source["front"], "rear": source["rear"]}, "values": values})


def list_tyres(work):
    """The library, sorted by name (ignoring case), then id: {id, name, source, changed}; a file that cannot be read or has
    a wrong shape is {id, error} and comes last."""
    folder = tyres_dir(work)
    good, bad = [], []
    for n in sorted(os.listdir(kspkg.long_path(folder))) if os.path.isdir(kspkg.long_path(folder)) else []:
        tyre_id = n[:-len(".json")]
        if not n.endswith(".json") or not TYRE_ID.fullmatch(tyre_id):
            continue
        try:
            t = load_tyre(work, tyre_id)
        except (ValueError, OSError) as e:
            bad.append({"id": tyre_id, "error": str(e)})
        else:
            good.append({"id": tyre_id, "name": t["name"], "source": t["source"], "changed": len(t["values"])})
    return sorted(good, key=lambda t: (t["name"].lower(), t["id"])) + bad


def create_tyre(work, name, source_key):
    """A new library tyre named name from a source key of list_source_tyres, without changed values; returns {id, name, source}."""
    name = check_tyre_name(work, name)
    source = source_tyre(work, source_key)
    tyre_id = free_tyre_id(work, name)
    save_tyre(work, tyre_id, name, source, {})
    return {"id": tyre_id, "name": name, "source": {"front": source["front"], "rear": source["rear"]}}


def rename_tyre(work, tyre_id, name):
    tyre = load_tyre(work, tyre_id)
    tyre["name"] = check_tyre_name(work, name, tyre_id)
    save_tyre(work, tyre_id, tyre["name"], tyre["source"], tyre["values"])
    return {"id": tyre_id, "name": tyre["name"]}


def set_tyre_source(work, tyre_id, source_key):
    """Point a library tyre at another source; the values are kept."""
    tyre = load_tyre(work, tyre_id)
    source = source_tyre(work, source_key)
    save_tyre(work, tyre_id, tyre["name"], source, tyre["values"])
    return {"id": tyre_id, "source": {"front": source["front"], "rear": source["rear"]}}


def set_tyre_value(work, tyre_id, setting_id, text, catalogue=None):
    """Like set_value for a library tyre: id and value of the setting, and the range warnings."""
    tyre = load_tyre(work, tyre_id)
    cat = catalogue or load_catalogue()
    s = tyre_setting(cat, setting_id)
    v = coerce(s, text)
    tyre["values"][setting_id] = v
    save_tyre(work, tyre_id, tyre["name"], tyre["source"], tyre["values"])
    warning = range_warning(s, v)
    return {"id": setting_id, "value": v, "warnings": [warning] if warning else []}


def unset_tyre_value(work, tyre_id, setting_id, catalogue=None):
    tyre = load_tyre(work, tyre_id)
    if setting_id not in tyre["values"]:
        tyre_setting(catalogue or load_catalogue(), setting_id)
    removed = tyre["values"].pop(setting_id, None) is not None
    if removed:
        save_tyre(work, tyre_id, tyre["name"], tyre["source"], tyre["values"])
    return {"id": setting_id, "removed": removed}


def reset_tyre(work, tyre_id):
    """Drop every changed value of a library tyre; returns {id, cleared} (the number of values dropped)."""
    tyre = load_tyre(work, tyre_id)
    cleared = len(tyre["values"])
    if cleared:
        save_tyre(work, tyre_id, tyre["name"], tyre["source"], {})
    return {"id": tyre_id, "cleared": cleared}


def shared_rel(root, game_path):
    """Path relative to a car folder (SHARED + the path below common_phsx) of a shared game tyre file present in root."""
    found = tyre_found(root, game_path)
    rel = os.path.relpath(found, os.path.join(root, "content", "cars", SHARED_DIR)).replace(os.sep, "/")
    if rel.split("/")[0] == "..":
        raise ValueError("%s is not in the shared folder" % found)
    return SHARED + rel


def tyre_rows(work, tyre_id, catalogue=None):
    """One row per tyre setting for the tyre editor: the setting's fields, axle, default (read from the source file of that
    axle in the base of an extracted car that offers the source), value (the override or the default) and changed. A setting
    whose default cannot be read from the file gets applicable False and a reason (default None); the others applicable
    True and reason None."""
    tyre = load_tyre(work, tyre_id)
    cat = catalogue or load_catalogue()
    source = tyre["source"]
    offer = next((e for e in list_source_tyres(work) if e["key"] == source["front"] + "|" + source["rear"]), None)
    if offer is None:
        raise ValueError("tyre %s: no extracted car offers its source %s any more, extract one with init or pick another "
                         "source" % (tyre_id, source_label(source["front"], source["rear"])))
    car_id = offer["cars"][0]
    root, cache, rels = base_dir(work, car_id), {}, {}
    for axle in ("front", "rear"):
        try:
            rels[axle] = shared_rel(root, source[axle])
        except ValueError as e:
            rels[axle] = e
    rows = []
    for s in tyre_settings(cat):
        axle = tyre_axle(s)
        row = {k: s[k] for k in ("id", "label", "group", "unit", "type", "kind", "description", "verified")}
        row.update({k: s[k] for k in ("min", "max") if k in s})
        if s["type"] == "enum":
            row["choices"] = list(s["choices"])
        row["axle"] = axle
        if isinstance(rels[axle], ValueError):
            targets, reason = [], str(rels[axle])
        else:
            targets = [c for t in s["targets"] if t["file"] == "@tyre_" + axle
                       for c in resolve_target(s, dict(t, file=rels[axle]), root, car_id, cache)]
            missing = [t for t in targets if not t["resolved"] and not t.get("optional")]
            reason = ("%s: %s" % (missing[0]["path"], missing[0].get("error", "unresolved").removeprefix(missing[0]["path"] + ": "))
                      if missing else None)
        values = [t["value"] for t in targets if t["resolved"]]
        if reason is None and not values:
            reason = "no value in the source file"
        default = values[0] if reason is None else None
        try:
            value = coerce(s, tyre["values"][s["id"]]) if s["id"] in tyre["values"] else default
        except ValueError as e:
            raise ValueError("tyre %s: %s" % (tyre_id, e)) from None
        row.update(default=default, value=value, changed=s["id"] in tyre["values"] and not same(s, value, default),
                   applicable=reason is None, reason=reason)
        rows.append(row)
    return rows


def garage_key(text):
    """("own", tyre id) or ("stock", "<front>|<rear>") for an entry of the "_tyres" list of a state, None for anything else."""
    if isinstance(text, str):
        for kind, prefix in (("own", OWN_KEY), ("stock", STOCK_KEY)):
            if text.startswith(prefix) and len(text) > len(prefix):
                return kind, text[len(prefix):]
    return None


def tyre_in_state(work, car_id, tune, tyre_id):
    try:
        used = load_state(work, car_id, tune).get(TYRE_KEY)
    except (ValueError, OSError):
        return False
    return isinstance(used, list) and any(garage_key(k) == ("own", tyre_id) for k in used)


def tyre_users(work, tyre_id):
    """The saved states that list the library tyre in their "_tyres": {car (stock car id), tune (tune id, or DRAFT)}, per
    stock car the default tune, the other tunes by id, then the draft. Unreadable state files are ignored."""
    check_tyre_id(tyre_id)
    users = []
    for car_id in car_folders(work):
        default = new_id_for(car_id)
        folder = os.path.join(car_work(work, car_id), TUNES)
        names = sorted(os.listdir(kspkg.long_path(folder))) if os.path.isdir(kspkg.long_path(folder)) else []
        others = [n for n in names if n != default and is_tune_id(work, car_id, n)]
        for label, tune in [(default, None)] + [(n, n) for n in others] + [(DRAFT, DRAFT)]:
            if tyre_in_state(work, car_id, tune, tyre_id):
                users.append({"car": car_id, "tune": label})
    return users


def delete_tyre(work, tyre_id):
    """Remove a library tyre; refused while a saved state (the draft included) of a modded car lists it."""
    if not tyre_exists(work, tyre_id):
        raise ValueError("no tyre %r in the library" % tyre_id)
    users = tyre_users(work, tyre_id)
    if users:
        raise ValueError("tyre %s is used by %s" % (tyre_id, ", ".join(
            "%s (draft)" % u["car"] if u["tune"] == DRAFT else "%s / %s" % (u["car"], u["tune"]) for u in users)))
    os.remove(kspkg.long_path(tyre_path(work, tyre_id)))
    return {"id": tyre_id, "deleted": True}


def car_stock_tyres(work, car_id):
    """The stock tyre pairs of a car from the presets of its own base (preset_tyre_pairs: shared game files present in the
    base), in the order of the presets: [{key ("stock:<front>|<rear>"), label, front, rear}]. A car without a base or
    without presets has none."""
    try:
        pairs = preset_tyre_pairs(base_dir(work, car_id), car_id)
    except (ValueError, OSError):
        return []
    return [{"key": "%s%s|%s" % (STOCK_KEY, front, rear), "label": source_label(front, rear), "front": front, "rear": rear}
            for front, rear in pairs]


def garage_entries(work, car_id):
    """The choices of a car's garage in their fixed order: [{key, kind, label}], the library tyres first (by name, then id;
    a damaged file is left out), then the stock tyres."""
    own = [{"key": OWN_KEY + t["id"], "kind": "own", "label": t["name"]} for t in list_tyres(work) if "error" not in t]
    return own + [{"key": s["key"], "kind": "stock", "label": s["label"]} for s in car_stock_tyres(work, car_id)]


def saved_garage(state):
    """The list of the "_tyres" entry of a state, None when it has none."""
    if TYRE_KEY not in state:
        return None
    saved = state[TYRE_KEY]
    if not (isinstance(saved, list) and all(isinstance(k, str) for k in saved)):
        raise ValueError("the saved tyre selection (%s) must be a list of tyre keys" % TYRE_KEY)
    return saved


def garage_choices(work, car_id, tune=None):
    """The garage of a car: {choices: [{key, kind (own, stock), label, ticked, start}], custom, missing}. Without a saved
    selection every stock tyre is ticked; start marks the first ticked choice; missing lists the saved keys that are no
    choice any more (deleted or damaged library tyre, stock pair gone)."""
    saved = saved_garage(load_state(work, car_id, tune))
    entries = garage_entries(work, car_id)
    ticked = {e["key"] for e in entries if e["kind"] == "stock"} if saved is None else set(saved)
    choices = [dict(e, ticked=e["key"] in ticked, start=False) for e in entries]
    first = next((c for c in choices if c["ticked"]), None)
    if first:
        first["start"] = True
    known = {e["key"] for e in entries}
    return {"choices": choices, "custom": saved is not None,
            "missing": list(dict.fromkeys(k for k in saved or [] if k not in known))}


def set_garage(work, car_id, keys, tune=None):
    """Tick exactly the tyres in keys (own:<tyre id> of a library tyre, stock:<front>|<rear> of car_stock_tyres) and store
    them in the state in the fixed order; returns {keys, start}. All stock tyres and no own tyre is the default: the entry
    is removed and the result has default True."""
    if not isinstance(keys, list):
        raise ValueError("the tyre keys must be a list, got %r" % (keys,))
    if not keys:
        raise ValueError("tick at least one tyre")
    entries = garage_entries(work, car_id)
    stock = [e["key"] for e in entries if e["kind"] == "stock"]
    for key in keys:
        if not isinstance(key, str):
            raise ValueError("a tyre key must be text, got %r" % (key,))
        if keys.count(key) > 1:
            raise ValueError("tyre key %s is listed twice" % key)
        parsed = garage_key(key)
        if parsed is None:
            raise ValueError("bad tyre key %r: use own:<tyre id> or stock:<front>|<rear>, garage lists them" % key)
        if parsed[0] == "own":
            load_tyre(work, parsed[1])
        elif key not in stock:
            raise ValueError("unknown stock tyre %s of %s, garage lists the tyres of the car" % (parsed[1], car_id))
    order = {e["key"]: i for i, e in enumerate(entries)}
    keys = sorted(keys, key=lambda k: order[k])
    state = load_state(work, car_id, tune)
    if keys == stock:
        if state.pop(TYRE_KEY, None) is not None:
            save_state(work, car_id, state, tune)
        return {"keys": keys, "start": keys[0], "default": True}
    state[TYRE_KEY] = keys
    save_state(work, car_id, state, tune)
    return {"keys": keys, "start": keys[0]}


def reset_garage(work, car_id, tune=None):
    """Remove the garage selection of a state: the car is not touched any more. Returns {removed}."""
    state = load_state(work, car_id, tune)
    removed = state.pop(TYRE_KEY, None) is not None
    if removed:
        save_state(work, car_id, state, tune)
    return {"removed": removed}


def garage_selection(work, car_id, state):
    """Check the saved selection of a state against the library and the car and resolve it for apply: the ticked entries in
    the fixed order, each {key, kind, label} plus front and rear (stock) or id, tyre, source (front, rear game paths) and
    files (front, rear: the source tyre file in the base of the extracted car that offers the source; own). Writes nothing."""
    saved = saved_garage(state)
    if not saved:
        raise ValueError("garage: the tyre selection is empty, tick at least one tyre or reset it")
    stock = {s["key"]: s for s in car_stock_tyres(work, car_id)}
    offers, chosen = None, {}
    for key in saved:
        parsed = garage_key(key)
        if parsed is None:
            raise ValueError("garage: bad tyre key %r" % key)
        kind, rest = parsed
        if kind == "stock":
            if key not in stock:
                raise ValueError("garage: the stock tyre %s is not in the presets of %s" % (rest, car_id))
            chosen[key] = dict(stock[key], kind="stock")
            continue
        try:
            tyre = load_tyre(work, rest)
        except ValueError as e:
            raise ValueError("garage: %s" % e) from None
        src = tyre["source"]
        if offers is None:
            offers = {e["key"]: e for e in list_source_tyres(work)}
        offer = offers.get(src["front"] + "|" + src["rear"])
        if offer is None:
            raise ValueError("garage: tyre %s: no extracted car offers its source %s, extract one with init or pick another "
                             "source" % (rest, source_label(src["front"], src["rear"])))
        src_car = offer["cars"][0]
        src_root = base_dir(work, src_car)
        files = {}
        for axle in ("front", "rear"):
            try:
                files[axle] = car_path(car_root_of(src_root, src_car), shared_rel(src_root, src[axle]))
            except ValueError as e:
                raise ValueError("garage: tyre %s: %s" % (rest, e)) from None
        chosen[key] = {"key": key, "kind": "own", "label": tyre["name"], "id": rest, "tyre": tyre, "files": files,
                       "source": (game_path_key(src["front"]), game_path_key(src["rear"]))}
    order = {e["key"]: i for i, e in enumerate(garage_entries(work, car_id))}
    return sorted(chosen.values(), key=lambda e: order[e["key"]])


def tyre_values_into(obj, entry, axle, cat):
    """Write the changed values of the library tyre of an entry that target the file of an axle into obj (the loaded source
    file): the same value handling as the per-car tyre values (float32, choice text), every target of a setting."""
    tyre = entry["tyre"]
    for s in tyre_settings(cat):
        if s["id"] not in tyre["values"]:
            continue
        try:
            v = coerce(s, tyre["values"][s["id"]])
        except ValueError as e:
            raise ValueError("garage: tyre %s: %s" % (entry["id"], e)) from None
        v = to_f32(v) if s["type"] == "float" else v
        if s.get("choice_values"):
            v = s["choice_values"][v]
        for t in s["targets"]:
            if t["file"] != "@tyre_" + axle:
                continue
            try:
                paths = expand_path(obj, t["path"], bool(s.get("create_missing")))
                if not paths:
                    raise ValueError("%s: the list has no elements" % t["path"])
                for path in paths:
                    get_value(obj, path, bool(s.get("create_missing")))
            except ValueError as e:
                if t.get("optional"):
                    continue
                raise ValueError("garage: tyre %s: %s cannot be written into the source file: %s" % (entry["id"], s["id"], e)) from None
            for path in paths:
                put_value(obj, path, v)


def set_list(obj, key, values):
    """Replace a repeated field of obj; the names of the field in the wire order (_order) follow the new length."""
    obj[key] = values
    order = obj.get("_order")
    if isinstance(order, list):
        at = order.index(key) if key in order else len(order)
        order[:] = [k for k in order if k != key]
        order[at:at] = [key] * len(values)


def compounds_of(preset):
    compounds = preset.get("physic_compounds", [])
    return compounds if isinstance(compounds, list) else []


def own_compound(template, entry):
    """A physic compound for an own tyre: a copy of the template compound with the own front and rear files."""
    pc = copy.deepcopy(template)
    put_value(pc, "front_tyre_data_path", entry["front_text"])
    if isinstance(pc.get("rear_tyre_data_paths"), list):
        set_list(pc, "rear_tyre_data_paths", [entry["rear_text"]])
    else:
        put_value(pc, "rear_tyre_data_paths", entry["rear_text"])
    return pc


def garage_compounds(compounds, plan, name):
    """The physic_compounds of one presets/*.compatibletyres (named name in errors) for the garage selection: one compound
    per ticked tyre in order (a stock tyre keeps its compound of this file and is skipped when the file has none; an own tyre
    is a copy of the compound of its source pair, else of the first compound), then the compounds that no stock pair of the
    car names, unchanged."""
    pairs = [compound_pair(pc) for pc in compounds]
    first = {}
    for pc, pair in zip(compounds, pairs):
        if pair is not None:
            first.setdefault(pair, pc)
    out = []
    for e in plan["entries"]:
        if e["kind"] == "stock":
            if (e["front"], e["rear"]) in first:
                out.append(first[(e["front"], e["rear"])])
        elif compounds:
            out.append(own_compound(first.get(e["source"]) or compounds[0], e))
    out += [pc for pc, pair in zip(compounds, pairs) if pair not in plan["pairs"]]
    if not out:
        raise ValueError("garage: presets/%s would be left without a tyre compound, tick a tyre it lists or an own tyre" % name)
    return out


def garage_list(current, plan, axle, texts):
    """frontTyreCompounds / rearTyreCompounds (axle front / rear) for the garage selection: the ticked tyres in order (the
    path text of a stock tyre as the list or else the presets have it), then the entries that no stock pair names."""
    have = {}
    for t in current:
        if isinstance(t, str):
            have.setdefault(game_path_key(t), t)
    out = {}
    for e in plan["entries"]:
        text = e[axle + "_text"] if e["kind"] == "own" else have.get(e[axle]) or texts.get(e[axle]) or e[axle]
        out.setdefault(game_path_key(text), text)
    seen, tail = set(out), []
    for t in current:
        key = game_path_key(t) if isinstance(t, str) else None
        if key is None or (key not in plan[axle + "_known"] and key not in seen):
            tail.append(t)
            seen.add(key)
    return list(out.values()) + tail


def preset_files(folder):
    return [n for n in sorted(os.listdir(kspkg.long_path(folder))) if n.lower().endswith(".compatibletyres")] \
        if os.path.isdir(kspkg.long_path(folder)) else []


def garage_plan(work, car_id, new_id, state, cat):
    """Everything apply needs for the garage selection of a state, checked before anything is built: the entries (see
    garage_selection, own ones with the game path text and the path below the car folder of their two files), files (path
    below the car folder, message name, object: the source files with the changed values), the stock pairs of the car and
    their fronts and rears. Raises ValueError for a tyre or source that is gone and for a preset file that would be left
    without a compound."""
    entries = garage_selection(work, car_id, state)
    for e in entries:
        for axle in ("front", "rear"):
            if e["kind"] == "own":
                e[axle + "_rel"] = "data/tyres/own_%s_%s.tyre" % (e["id"], axle)
                e[axle + "_text"] = "content\\cars\\%s\\%s" % (new_id, e[axle + "_rel"].replace("/", "\\"))
    files = []
    for e in entries:
        for axle in ("front", "rear") if e["kind"] == "own" else ():
            obj, name = load_msg(e["files"][axle])
            tyre_values_into(obj, e, axle, cat)
            files.append((e[axle + "_rel"], name, obj))
    pairs = {(s["front"], s["rear"]) for s in car_stock_tyres(work, car_id)}
    plan = {"entries": entries, "files": files, "pairs": pairs, "front_known": {f for f, _ in pairs},
            "rear_known": {r for _, r in pairs}}
    root = base_dir(work, car_id)
    try:
        folder = find_ci(car_root_of(root, car_id), "presets")
    except ValueError:
        folder = None
    for n in preset_files(folder) if folder else []:
        garage_compounds(compounds_of(load_msg(os.path.join(folder, n))[0]), plan, n)
    return plan


def write_garage(root, car_id, new_id, car_root, plan, cache):
    """Write the garage selection of a plan into the build of the tuned car: the own tyre files, the tyre lists of the .car
    and the physic_compounds of every presets/*.compatibletyres. Returns the notes for the build log."""
    for rel, name, obj in plan["files"]:
        path = car_path(car_root, rel)
        os.makedirs(kspkg.long_path(os.path.dirname(path)), exist_ok=True)
        save_msg(path, name, obj)
    folder = os.path.join(car_root, "presets")
    presets = [(n,) + load_msg(os.path.join(folder, n)) for n in preset_files(folder)]
    texts = {}
    for _, preset, _ in presets:
        for pc in compounds_of(preset):
            pair = compound_pair(pc)
            if pair:
                rear = pc["rear_tyre_data_paths"]
                texts.setdefault(pair[0], pc["front_tyre_data_path"])
                texts.setdefault(pair[1], rear[0] if isinstance(rear, list) else rear)
    car_file = car_path(car_root, renamed(resolve_file("@car", root, car_id, cache), car_id, new_id))
    car, car_name = load_msg(car_file)
    for axle, field in (("front", "frontTyreCompounds"), ("rear", "rearTyreCompounds")):
        current = car.get(field)
        set_list(car, field, garage_list(current if isinstance(current, list) else [], plan, axle, texts))
    save_msg(car_file, car_name, car)
    for n, preset, name in presets:
        set_list(preset, "physic_compounds", garage_compounds(compounds_of(preset), plan, n))
        save_msg(os.path.join(folder, n), name, preset)
    first = plan["entries"][0]
    return (["note: garage: own tyre %s -> %s, %s" % (e["id"], e["front_rel"], e["rear_rel"]) for e in plan["entries"] if e["kind"] == "own"]
            + ["note: garage: %d tyre(s), starting on %s" % (len(plan["entries"]), first["label"])])


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


def warn_unknown_state(work, car_id, catalogue=None, tune=None):
    for sid in unknown_state_ids(work, car_id, catalogue, tune):
        print("warning: ignoring unknown setting '%s' in the saved state" % sid, file=sys.stderr)


def display_name_of(work, car_id):
    info = load_stock_info(work, car_id)
    if info:
        return info["display_name"]
    # only the name is needed: any expandable folder will do for the mods folder
    return next(r["display_name"] for r in list_cars(work, work, sizes=False) if r["id"] == car_id)


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


def work_arg(opts):
    return work_dir(opts.get("work"))


def mods_arg(opts):
    return clone_car.expand(opts["mods"]) if "mods" in opts else None


def tune_arg(work, car_id, opts):
    """The tune chosen with --tune: None when not given, the default id as given, else the id of an existing modded car."""
    tune_id = opts.get("tune")
    if tune_id is None or tune_id == new_id_for(car_id):
        return tune_id
    if tune_id == DRAFT or not os.path.isfile(kspkg.long_path(state_path(work, car_id, tune_id))):
        raise ValueError("%s has no tune %s" % (car_id, tune_id))
    return tune_id


def cmd_cars():
    pos, opts = cli_args(("game", "mods", "work"), ("tested", "modded"))
    if pos or ("tested" in opts and "modded" in opts):
        usage()
    work, _ = start(opts)
    game = os.path.expandvars(opts.get("game", DEFAULT_GAME))
    if "modded" in opts:
        print(table(["id", "stock", "label", "suffix", "installed", "built"],
                    [[r["id"], r["stock"], r["label"], r["name_suffix"], "yes" if r["installed"] else "no",
                      "yes" if r["built"] else "no"] for r in list_modded(work, mods_arg(opts))]))
        return
    print(table(["id", "display name", "extracted", "tested", "new id", "installed", "size"],
                [[r["id"], r["display_name"], "yes" if r["extracted"] else "no", "yes" if r["tested"] else "no",
                  r["new_id"], "yes" if r["installed"] else "no",
                  "%.1f MB" % (r["bytes"] / (1 << 20)) if r["extracted"] else "-"]
                 for r in list_cars(work, mods_arg(opts), "tested" in opts, game)]))
    if "tested" not in opts and load_cars_index(work, game) is None:
        print("note: the game package is not available and there is no car index, "
              "only the tested cars are listed")


def cmd_init():
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


def cmd_defaults():
    pos, opts = cli_args(("car", "tune", "work"), ("hidden",))
    if pos:
        usage()
    work, car_id = start(opts)
    tune_arg(work, car_id, opts)
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


def cmd_set():
    pos, opts = cli_args(("car", "tune", "work"))
    if len(pos) != 2:
        usage()
    work, car_id = start(opts)
    res = set_value(work, car_id, pos[0], pos[1], tune=tune_arg(work, car_id, opts))
    for w in res["warnings"]:
        print("warning: " + w, file=sys.stderr)
    print("%s = %s" % (res["id"], fmt(res["value"])))


def cmd_unset():
    pos, opts = cli_args(("car", "tune", "work"))
    if len(pos) != 1:
        usage()
    work, car_id = start(opts)
    res = unset_value(work, car_id, pos[0], tune=tune_arg(work, car_id, opts))
    print("%s %s" % (res["id"], "removed from the state" if res["removed"] else "was not set"))


def cmd_show():
    pos, opts = cli_args(("car", "tune", "work"))
    if pos:
        usage()
    work, car_id = start(opts)
    tune_id = tune_arg(work, car_id, opts)
    cat = load_catalogue()
    warn_unknown_state(work, car_id, cat, tune_id)
    rows = effective_rows(work, car_id, cat, tune=tune_id)
    print(table(["", "id", "value", "default", "unit"],
                [["*" if r["changed"] else "", r["id"], fmt(r["value"]), fmt(r["default"]), r["unit"]]
                 for r in rows]))


def cmd_apply():
    pos, opts = cli_args(("car", "tune", "new-id", "mods", "work"), ("no-install",))
    if pos:
        usage()
    if "tune" in opts and "new-id" in opts:
        raise ValueError("--tune and --new-id cannot be combined")
    if "no-install" not in opts and game_running():
        raise ValueError("the game is running, close it first")
    work, car_id = start(opts)
    note_untested(car_id)
    new_id = tune_arg(work, car_id, opts) or opts.get("new-id")
    cat = load_catalogue()
    warn_unknown_state(work, car_id, cat, new_id)
    res = apply(work, car_id, new_id, "no-install" not in opts, mods_arg(opts), cat)
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


def cmd_duplicate():
    pos, opts = cli_args(("car", "tune", "new-id", "suffix", "mods", "work"), ("draft",))
    if pos or ("tune" in opts and "draft" in opts):
        usage()
    work, car_id = start(opts)
    src = DRAFT if "draft" in opts else tune_arg(work, car_id, opts)
    res = duplicate_tune(work, car_id, src, opts.get("new-id"), opts.get("suffix"), mods_arg(opts))
    print("car: %s, new id: %s" % (car_id, res["id"]))
    print("name suffix: %s" % res["name_suffix"])


def cmd_doc():
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


def cmd_tyres():
    pos, opts = cli_args(("work",))
    if pos:
        usage()
    work = work_arg(opts)
    tyres = list_tyres(work)
    if not tyres:
        print("no tyres in the library")
    else:
        print(table(["id", "name", "source", "changed"],
                    [[t["id"], t["name"], source_label(t["source"]["front"], t["source"]["rear"]), t["changed"]]
                     if "error" not in t else [t["id"], "-", "error: " + t["error"], "-"] for t in tyres]))


def cmd_tyre_sources():
    pos, opts = cli_args(("work",))
    if pos:
        usage()
    sources = list_source_tyres(work_arg(opts))
    if not sources:
        print("note: no extracted car offers a tyre pair (init extracts a car and its shared tyre files)")
    else:
        print(table(["label", "cars", "key"], [[e["label"], ", ".join(e["cars"]), e["key"]] for e in sources]))


def cmd_tyre_new():
    pos, opts = cli_args(("name", "source", "work"))
    if pos or "name" not in opts or "source" not in opts:
        usage()
    res = create_tyre(work_arg(opts), opts["name"], opts["source"])
    print("created tyre %s: %s (%s)" % (res["id"], res["name"], source_label(res["source"]["front"], res["source"]["rear"])))


def cmd_tyre_show():
    pos, opts = cli_args(("work",))
    if len(pos) != 1:
        usage()
    work = work_arg(opts)
    tyre = load_tyre(work, pos[0])
    rows = tyre_rows(work, pos[0])
    print("tyre %s: %s, source %s" % (pos[0], tyre["name"], source_label(tyre["source"]["front"], tyre["source"]["rear"])))
    print(table(["", "id", "value", "default", "unit", "note"],
                [["*" if r["changed"] else "", r["id"], fmt(r["value"]), fmt(r["default"]), r["unit"], r["reason"] or ""]
                 for r in rows]))


def cmd_tyre_set():
    pos, opts = cli_args(("work",))
    if len(pos) != 3:
        usage()
    res = set_tyre_value(work_arg(opts), pos[0], pos[1], pos[2])
    for w in res["warnings"]:
        print("warning: " + w, file=sys.stderr)
    print("%s = %s" % (res["id"], fmt(res["value"])))


def cmd_tyre_unset():
    pos, opts = cli_args(("work",))
    if len(pos) != 2:
        usage()
    res = unset_tyre_value(work_arg(opts), pos[0], pos[1])
    print("%s %s" % (res["id"], "removed from the tyre" if res["removed"] else "was not set"))


def cmd_tyre_delete():
    pos, opts = cli_args(("work",))
    if len(pos) != 1:
        usage()
    res = delete_tyre(work_arg(opts), pos[0])
    print("deleted tyre %s" % res["id"])


def cmd_garage():
    pos, opts = cli_args(("car", "tune", "work"), ("draft",))
    if pos or ("tune" in opts and "draft" in opts):
        usage()
    work, car_id = start(opts)
    res = garage_choices(work, car_id, DRAFT if "draft" in opts else tune_arg(work, car_id, opts))
    print("garage of %s: %s" % (car_id, "saved selection" if res["custom"] else "default (all stock tyres, the car is not touched)"))
    if res["choices"]:
        print(table(["ticked", "start", "key", "label"],
                    [["x" if c["ticked"] else "", "start" if c["start"] else "", c["key"], c["label"]] for c in res["choices"]]))
    else:
        print("note: no tyres to choose from (the presets of the car offer no tyre pair and the library is empty)")
    for key in res["missing"]:
        print("warning: the saved tyre %s is not available any more" % key, file=sys.stderr)


def cmd_garage_set():
    pos, opts = cli_args(("car", "tune", "work"), ("draft",))
    if not pos or ("tune" in opts and "draft" in opts):
        usage()
    work, car_id = start(opts)
    res = set_garage(work, car_id, pos, DRAFT if "draft" in opts else tune_arg(work, car_id, opts))
    print("garage: %d tyre(s), starting on %s%s" % (len(res["keys"]), res["start"],
                                                   " (the default selection, nothing is stored)" if res.get("default") else ""))


def cmd_garage_reset():
    pos, opts = cli_args(("car", "tune", "work"), ("draft",))
    if pos or ("tune" in opts and "draft" in opts):
        usage()
    work, car_id = start(opts)
    res = reset_garage(work, car_id, DRAFT if "draft" in opts else tune_arg(work, car_id, opts))
    print("garage selection %s" % ("removed from the state" if res["removed"] else "was not set"))


COMMANDS = {
    "cars": cmd_cars,
    "init": cmd_init,
    "defaults": cmd_defaults,
    "set": cmd_set,
    "unset": cmd_unset,
    "show": cmd_show,
    "apply": cmd_apply,
    "duplicate": cmd_duplicate,
    "doc": cmd_doc,
    "tyres": cmd_tyres,
    "tyre-sources": cmd_tyre_sources,
    "tyre-new": cmd_tyre_new,
    "tyre-show": cmd_tyre_show,
    "tyre-set": cmd_tyre_set,
    "tyre-unset": cmd_tyre_unset,
    "tyre-delete": cmd_tyre_delete,
    "garage": cmd_garage,
    "garage-set": cmd_garage_set,
    "garage-reset": cmd_garage_reset,
}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        COMMANDS.get(cmd, usage)()
    except (ValueError, OSError) as e:
        sys.exit("error: %s" % e)


if __name__ == "__main__":
    main()
