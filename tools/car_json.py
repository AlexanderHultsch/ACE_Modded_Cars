"""Lossless schema-driven codec between AC EVO car protobuf files and editable JSON.

usage:
  python tools/car_json.py decode <file> [out.json]     # message type chosen from the file extension; prints to stdout if no out
  python tools/car_json.py encode <in.json> <out_file>  # message type chosen from out_file's extension
  python tools/car_json.py check  <dir>                 # round-trip every supported file under <dir> and print a summary
  python tools/car_json.py types                         # print the extension -> message table

Needs schemas/acevo.desc (a FileDescriptorSet, see tools/extract_protos.py). Stdlib only.
File reads and writes on car trees use extended-length paths (kspkg.long_path), so paths over 260 characters work;
printed paths stay normal.

JSON model (one object per message, keys = schema field names in wire order):
  - a key is present only if the field was on the wire; the encoder never invents defaults
  - repeated fields are arrays; nested messages are objects ({} when present but empty)
  - enum = value name (int if unknown), bytes = "hex:..", nan/inf = "nan"/"inf"/"-inf"
  - float = shortest decimal that parses back to the same float32 bits
Reserved keys (start with "_", only present when needed for an exact round trip):
  _order    [field names, one per wire occurrence] when the wire order is not ascending field number
  _packed   [field names] of repeated scalars stored packed on the wire
  _unknown  [[field_number, wire_type, value]] fields not in the schema ("hex:.." for wire type 2)
            (named "?<number>" in _order); a known field whose wire type cannot hold its schema type
            is kept here too, as [field_number, wire_type, value, {"mismatch": "<schema field name>"}]
Files that cannot be reproduced exactly (e.g. a repeated field split into several packed chunks,
or mixing packed and unpacked) are rejected with a reason instead of being approximated.
"""
import json
import os
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import extract_protos as ep  # noqa: E402
import kspkg  # noqa: E402

DESC = pathlib.Path(__file__).resolve().parent.parent / "schemas" / "acevo.desc"

# Only extensions where exactly one candidate message decoded every sample file strictly
# (no wire-type mismatch, no unknown fields, exact round trip).
TYPES = {
    "aicardata": "AiCarData",
    "brakesystem": "BrakesData",
    "car": "CarData",
    "caranalogicsystem": "CarAnalogicSystemData",
    "cardesign": "CarDesignData",
    "carelectronics": "ElectronicsData",
    "carengine": "EngineData",
    "carexhaustbackfire": "CarExhaustBackFireData",
    "carfinalstate": "CarFinalStateData",
    "carledsystem": "CarLedSystemData",
    "carlightingsystem": "CarLightingSystemData",
    "carsetup": "CarSetupData",
    "carsetuplimits": "CarSetupDataLimits",
    "cartests": "CarTestData",
    "clutch": "ClutchData",
    "coilover": "CoiloverData",
    "compatiblerim": "CompatibleRimData",
    "compatibletyres": "CompatibleTyresData",
    "curve": "CurveDataEx",
    "design": "DesignData",
    "drivetrain": "DrivetrainData",
    "gearbox": "GearBoxData",
    "mechanicalcarpreset": "MechanicalCarPresetData",
    "moddedcarcontent": "ModdedCarContentData",
    "oemmultilayercolor": "OemMultilayerColorData",
    "rimmesh": "RimMeshData",
    "suspension": "SuspensionGeometryData",
    "turbo": "TurboData",
    "tyre": "TyresCompoundData",
    "visualcarpreset": "VisualCarPresetData",
    "wing": "WingData",
}

WIRE = {1: 1, 2: 5, 3: 0, 4: 0, 5: 0, 6: 1, 7: 5, 8: 0, 9: 2, 11: 2, 12: 2, 13: 0, 14: 0,
        15: 5, 16: 1, 17: 0, 18: 0}
INTS = {3: (64, True), 4: (64, False), 5: (32, True), 13: (32, False), 17: (32, True),
        18: (64, True), 6: (64, False), 7: (32, False), 15: (32, True), 16: (64, True)}
RESERVED = ("_order", "_packed", "_unknown")


class F32(float):
    """float32 value carrying its shortest decimal text."""


def load_schema(path=DESC):
    if not path.is_file():
        raise ValueError("missing schema file %s (run tools/extract_protos.py)" % path)
    sch = {"msgs": {}, "enums": {}}
    for rec in ep.split_set(path.read_bytes()):
        f = ep.parse_file(rec)
        prefix = f["package"] + "." if f["package"] else ""
        for e in f["enums"]:
            add_enum(sch, prefix + e["name"], e)
        for m in f["messages"]:
            add_message(sch, prefix, m)
    return sch


def add_enum(sch, name, e):
    by_num = {}
    for v in e["values"]:
        by_num.setdefault(v["number"], v["name"])
    sch["enums"][name] = ({v["name"]: v["number"] for v in e["values"]}, by_num)


def add_message(sch, prefix, m):
    full = prefix + m["name"]
    sch["msgs"][full] = ({f["number"]: f for f in m["fields"]}, {f["name"]: f for f in m["fields"]})
    for e in m["enums"]:
        add_enum(sch, full + "." + e["name"], e)
    for n in m["nested"]:
        add_message(sch, full + ".", n)


def type_name(f):
    return f["type_name"].lstrip(".")


def wire_fields(b):
    out = []
    i = 0
    while i < len(b):
        key, i = ep.varint(b, i)
        fn, wt = key >> 3, key & 7
        if fn == 0:
            raise ValueError("field number 0")
        if wt == 0:
            v, i = ep.varint(b, i)
        elif wt in (1, 5):
            n = 8 if wt == 1 else 4
            if i + n > len(b):
                raise ValueError("truncated")
            v = int.from_bytes(b[i:i + n], "little"); i += n
        elif wt == 2:
            n, i = ep.varint(b, i)
            if i + n > len(b):
                raise ValueError("truncated")
            v = b[i:i + n]; i += n
        else:
            raise ValueError("wire type %d (groups are not supported)" % wt)
        out.append((fn, wt, v))
    return out


def sgn(v, bits):
    return v - (1 << bits) if v >> (bits - 1) else v


def f32_text(x):
    packed = struct.pack("<f", x)
    for n in range(1, 10):
        s = "%.*g" % (n, x)
        try:
            if struct.pack("<f", float(s)) == packed:
                break
        except OverflowError:
            pass
    return repr(float(s))


def dec_scalar(sch, f, raw):
    t = f["type"]
    if t == 1:
        x = struct.unpack("<d", raw.to_bytes(8, "little"))[0]
        return x if x == x and abs(x) != float("inf") else str(x)
    if t == 2:
        x = struct.unpack("<f", raw.to_bytes(4, "little"))[0]
        if x != x or abs(x) == float("inf"):
            return str(x)
        v = F32(x)
        v.text = f32_text(x)
        return v
    if t == 8:
        if raw > 1:
            raise ValueError("bool value %d" % raw)
        return bool(raw)
    if t in (5, 14):
        if raw >= 1 << 32 and raw < (1 << 64) - (1 << 31):
            raise ValueError("int32 value out of range")
        v = sgn(raw & 0xFFFFFFFF, 32)
        if t == 5:
            return v
        return sch["enums"][type_name(f)][1].get(v, v)
    if t in (13, 17) and raw >= 1 << 32:
        raise ValueError("32-bit value out of range")
    bits, signed = INTS[t]
    if t in (17, 18):
        return (raw >> 1) ^ -(raw & 1)
    return sgn(raw, bits) if signed else raw


def dec_value(sch, f, wt, raw):
    t = f["type"]
    if t == 11:
        return decode_msg(sch, type_name(f), raw)
    if t == 9:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("string is not valid UTF-8")
    if t == 12:
        return "hex:" + raw.hex()
    return dec_scalar(sch, f, raw)


def packed_is_valid(f, raw):
    n = {1: 8, 5: 4}.get(WIRE[f["type"]])
    if n:
        return len(raw) % n == 0
    i = 0
    try:
        while i < len(raw):
            _, i = ep.varint(raw, i)
    except ValueError:
        return False
    return True


def wire_conflict(f, wt, raw):
    """True when this occurrence cannot be a value of the schema field's type."""
    t = f["type"]
    if wt == WIRE.get(t):
        return False
    if f["label"] == 3 and t not in (9, 11, 12) and wt == 2:
        return not packed_is_valid(f, raw)
    return True


def decode_msg(sch, name, b):
    by_num = sch["msgs"][name][0]
    out, order, nums, unknown, packed = {}, [], [], [], []
    for fn, wt, raw in wire_fields(b):
        nums.append(fn)
        f = by_num.get(fn)
        if f is None or wire_conflict(f, wt, raw):
            entry = [fn, wt, "hex:" + raw.hex() if wt == 2 else raw]
            if f is not None:
                entry.append({"mismatch": f["name"]})
            unknown.append(entry)
            order.append("?%d" % fn)
            continue
        key, t = f["name"], f["type"]
        order.append(key)
        try:
            if f["label"] == 3 and t not in (9, 11, 12) and wt == 2:
                if key in out:
                    raise ValueError("repeated field split into several chunks or mixed packed/unpacked")
                out[key] = packed_values(sch, f, raw)
                packed.append(key)
            elif f["label"] == 3:
                if key in packed:
                    raise ValueError("repeated field mixes packed and unpacked")
                out.setdefault(key, []).append(dec_value(sch, f, wt, raw))
            elif key in out:
                raise ValueError("singular field occurs more than once")
            else:
                out[key] = dec_value(sch, f, wt, raw)
        except ValueError as e:
            raise ValueError("%s: %s" % (key, e))
    if any(a > b or (a == b and x != y) for a, b, x, y in zip(nums, nums[1:], order, order[1:])):
        out["_order"] = order
    if packed:
        out["_packed"] = packed
    if unknown:
        out["_unknown"] = unknown
    return out


def packed_values(sch, f, raw):
    vals = []
    i = 0
    n = {1: 8, 5: 4}.get(WIRE[f["type"]])
    while i < len(raw):
        if n:
            if i + n > len(raw):
                raise ValueError("truncated packed data")
            v = int.from_bytes(raw[i:i + n], "little"); i += n
        else:
            v, i = ep.varint(raw, i)
        vals.append(dec_scalar(sch, f, v))
    return vals


def flt(v):
    if type(v) is bool or not isinstance(v, (int, float, str)):
        raise ValueError("expected a number, got %r" % (v,))
    return float(v)


def enc_scalar(sch, f, v):
    t = f["type"]
    if t == 1:
        return struct.pack("<d", flt(v))
    if t == 2:
        try:
            return struct.pack("<f", flt(v))
        except OverflowError:
            raise ValueError("float out of range: %r" % (v,))
    if t == 8:
        if type(v) is not bool:
            raise ValueError("expected true/false, got %r" % (v,))
        return ep.varint_bytes(int(v))
    if t == 14 and isinstance(v, str):
        names = sch["enums"][type_name(f)][0]
        if v not in names:
            raise ValueError("unknown enum value %r" % v)
        v = names[v]
    bits, signed = INTS[5 if t == 14 else t]
    if type(v) is not int:
        raise ValueError("expected an integer, got %r" % (v,))
    lo, hi = (-(1 << (bits - 1)), 1 << (bits - 1)) if signed else (0, 1 << bits)
    if not lo <= v < hi:
        raise ValueError("integer %d out of range" % v)
    if t in (17, 18):
        return ep.varint_bytes((v << 1) ^ (v >> (bits - 1)))
    if t in (6, 7, 15, 16):
        return (v & ((1 << bits) - 1)).to_bytes(bits // 8, "little")
    return ep.varint_bytes(v & ((1 << 64) - 1))


def enc_value(sch, f, v):
    t = f["type"]
    if t == 11:
        return encode_msg(sch, type_name(f), v)
    if t == 9:
        if not isinstance(v, str):
            raise ValueError("expected a string, got %r" % (v,))
        return v.encode("utf-8")
    if t == 12:
        if not (isinstance(v, str) and v.startswith("hex:")):
            raise ValueError("expected \"hex:..\", got %r" % (v,))
        return bytes.fromhex(v[4:])
    return enc_scalar(sch, f, v)


def tag(fn, wt):
    return ep.varint_bytes(fn << 3 | wt)


def occurrence(f, wt, body):
    if wt == 2:
        body = ep.varint_bytes(len(body)) + body
    return tag(f["number"], wt) + body


def encode_msg(sch, name, obj):
    if not isinstance(obj, dict):
        raise ValueError("%s: expected an object" % name)
    by_name = sch["msgs"][name][1]
    for k in obj:
        if k not in by_name and k not in RESERVED:
            raise ValueError("%s: unknown field %r" % (name, k))
    packed = obj.get("_packed", [])
    occ = {}
    for key, val in obj.items():
        if key in RESERVED:
            continue
        f = by_name[key]
        wt = WIRE[f["type"]]
        try:
            if f["label"] == 3:
                if not isinstance(val, list):
                    raise ValueError("expected an array")
                if key in packed:
                    body = b"".join(enc_value(sch, f, v) for v in val)
                    occ[key] = [(f["number"], occurrence(f, 2, body))]
                else:
                    occ[key] = [(f["number"], occurrence(f, wt, enc_value(sch, f, v))) for v in val]
            else:
                occ[key] = [(f["number"], occurrence(f, wt, enc_value(sch, f, val)))]
        except ValueError as e:
            raise ValueError("%s: %s" % (key, e))
    for fn, wt, v, *_ in obj.get("_unknown", []):
        if wt == 0:
            body = ep.varint_bytes(v)
        elif wt in (1, 5):
            body = v.to_bytes(8 if wt == 1 else 4, "little")
        elif wt == 2:
            body = bytes.fromhex(v[4:])
            body = ep.varint_bytes(len(body)) + body
        else:
            raise ValueError("_unknown: wire type %d" % wt)
        occ.setdefault("?%d" % fn, []).append((fn, tag(fn, wt) + body))
    if "_order" not in obj:
        return b"".join(b for _, b in sorted((x for xs in occ.values() for x in xs), key=lambda x: x[0]))
    pos = dict.fromkeys(occ, 0)
    out = []
    for key in obj["_order"]:
        if key not in occ or pos[key] >= len(occ[key]):
            raise ValueError("_order names %r more often than it occurs" % key)
        out.append(occ[key][pos[key]][1])
        pos[key] += 1
    if any(pos[k] != len(occ[k]) for k in occ):
        raise ValueError("_order does not cover every field occurrence")
    return b"".join(out)


def count_unknown(obj, mismatch=False):
    if isinstance(obj, dict):
        own = [e for e in obj.get("_unknown", []) if len(e) > 3 or not mismatch]
        return len(own) + sum(count_unknown(v, mismatch) for v in obj.values())
    if isinstance(obj, list):
        return sum(count_unknown(v, mismatch) for v in obj)
    return 0


def scalar_text(v):
    if isinstance(v, F32):
        return v.text
    if isinstance(v, float):
        return repr(v)
    return json.dumps(v, ensure_ascii=False)


def dumps(v, ind=0):
    pad = "  " * (ind + 1)
    if isinstance(v, dict):
        if not v:
            return "{}"
        rows = ["%s%s: %s" % (pad, json.dumps(k), dumps(x, ind + 1)) for k, x in v.items()]
        return "{\n" + ",\n".join(rows) + "\n" + "  " * ind + "}"
    if isinstance(v, list):
        if not v:
            return "[]"
        if any(isinstance(x, (dict, list)) for x in v):
            return "[\n" + ",\n".join(pad + dumps(x, ind + 1) for x in v) + "\n" + "  " * ind + "]"
        items = [scalar_text(x) for x in v]
        if len(items) <= 10:
            return "[" + ", ".join(items) + "]"
        rows = [", ".join(items[i:i + 10]) for i in range(0, len(items), 10)]
        return "[\n" + ",\n".join(pad + r for r in rows) + "\n" + "  " * ind + "]"
    return scalar_text(v)


def loads(text):
    return json.loads(text, parse_float=str)


def message_for(path):
    ext = pathlib.Path(path).suffix.lower().lstrip(".")
    if ext not in TYPES:
        raise ValueError("no message type for extension .%s (see: types)" % ext)
    return TYPES[ext]


def roundtrip(sch, name, data):
    """Return (obj, error_or_None) for decode -> JSON text -> encode compared to data."""
    try:
        obj = decode_msg(sch, name, data)
        back = encode_msg(sch, name, loads(dumps(obj)))
    except (ValueError, KeyError, IndexError, TypeError, RecursionError) as e:
        return None, "%s: %s" % (type(e).__name__, e)
    if back != data:
        i = next((i for i, (a, b) in enumerate(zip(back, data)) if a != b), min(len(back), len(data)))
        return obj, "round-trip mismatch at byte %d (encoded %d bytes, original %d)" % (i, len(back), len(data))
    return obj, None


def check(root):
    sch = load_schema()
    stats, skipped, failed = {}, {}, []
    found = [os.path.join(dp, n) for dp, _, names in os.walk(kspkg.long_path(root)) for n in names]
    for p in sorted(found):
        ext = pathlib.PurePath(p).suffix.lower().lstrip(".")
        if ext not in TYPES:
            skipped[ext] = skipped.get(ext, 0) + 1
            continue
        with open(p, "rb") as f:
            obj, err = roundtrip(sch, TYPES[ext], f.read())
        s = stats.setdefault(ext, [0, 0, 0, 0, 0])
        s[0] += 1
        if err:
            s[2] += 1
            failed.append((kspkg.plain_path(p), err))
        else:
            s[1] += 1
            s[3] += count_unknown(obj)
            s[4] += count_unknown(obj, True)
    print("%-20s %-28s %6s %6s %6s %8s %8s" % ("extension", "message", "files", "ok", "failed", "unknown", "mismatch"))
    for ext, (n, ok, bad, unk, mis) in sorted(stats.items()):
        print("%-20s %-28s %6d %6d %6d %8d %8d" % ("." + ext, TYPES[ext], n, ok, bad, unk, mis))
    for p, err in failed:
        print("FAILED %s\n  %s" % (p, err))
    print("total: ok %d, failed %d" % (sum(s[1] for s in stats.values()), len(failed)))
    if skipped:
        print("skipped (no mapped message): " + ", ".join(
            "%s x%d" % ("." + e if e else "(none)", n) for e, n in sorted(skipped.items())))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    args = sys.argv[2:]
    try:
        if cmd == "decode" and len(args) in (1, 2):
            name = message_for(args[0])
            data = pathlib.Path(kspkg.long_path(args[0])).read_bytes()
            sch = load_schema()
            obj, err = roundtrip(sch, name, data)
            if obj is None:
                sys.exit("error: " + err)
            if err:
                print("warning: " + err, file=sys.stderr)
            text = dumps(obj) + "\n"
            if len(args) == 2:
                pathlib.Path(args[1]).write_bytes(text.encode("utf-8"))
            else:
                sys.stdout.buffer.write(text.encode("utf-8"))
        elif cmd == "encode" and len(args) == 2:
            name = message_for(args[1])
            obj = loads(pathlib.Path(args[0]).read_text(encoding="utf-8-sig"))
            pathlib.Path(kspkg.long_path(args[1])).write_bytes(encode_msg(load_schema(), name, obj))
        elif cmd == "check" and len(args) == 1:
            check(args[0])
        elif cmd == "types" and not args:
            for ext, name in sorted(TYPES.items()):
                print(".%-20s %s" % (ext, name))
        else:
            sys.exit(__doc__.split("\n\n")[1])
    except (ValueError, OSError) as e:
        sys.exit("error: %s" % e)


if __name__ == "__main__":
    main()
