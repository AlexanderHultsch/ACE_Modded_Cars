"""Extract the embedded protobuf schemas (serialized FileDescriptorProtos) from an executable.

usage: python tools/extract_protos.py <exe_path> <outdir>
  e.g. python tools/extract_protos.py AssettoCorsaEVOEditor.exe schemas

Writes <outdir>/acevo.desc (a FileDescriptorSet, dependencies first) and one
<name>.proto text rendering per descriptor. Each blob is located by its leading
`0x0A <len> "<Name>.proto"` bytes and delimited by a strict parse of the
FileDescriptorProto fields. Duplicates (same file name) keep the first copy.
Then re-reads acevo.desc and prints a self-check. Does not run or modify the exe.
"""
import pathlib
import re
import struct
import sys

NAME_RE = re.compile(rb"(?=\x0a[\x07-\x7f][A-Za-z_])")
FILE_FIELDS = {1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 2, 7: 2, 8: 2, 9: 2, 10: 0, 11: 0, 12: 2}
TYPES = {1: "double", 2: "float", 3: "int64", 4: "uint64", 5: "int32", 6: "fixed64",
         7: "fixed32", 8: "bool", 9: "string", 12: "bytes", 13: "uint32", 15: "sfixed32",
         16: "sfixed64", 17: "sint32", 18: "sint64"}
LABELS = {1: "optional", 2: "required", 3: "repeated"}


def varint(b, i):
    r = s = 0
    while True:
        if i >= len(b) or s > 63:
            raise ValueError("bad varint")
        c = b[i]; i += 1
        r |= (c & 0x7F) << s; s += 7
        if c < 0x80:
            return r, i


def fields(b):
    """Strict parse of one message level into [(field_number, wire_type, value)]."""
    out = []
    i = 0
    while i < len(b):
        key, i = varint(b, i)
        fn, wt = key >> 3, key & 7
        if fn == 0:
            raise ValueError("field 0")
        if wt == 0:
            v, i = varint(b, i)
        elif wt == 1:
            if i + 8 > len(b):
                raise ValueError("truncated")
            v = struct.unpack_from("<d", b, i)[0]; i += 8
        elif wt == 5:
            if i + 4 > len(b):
                raise ValueError("truncated")
            v = struct.unpack_from("<f", b, i)[0]; i += 4
        elif wt == 2:
            n, i = varint(b, i)
            if i + n > len(b):
                raise ValueError("truncated")
            v = b[i:i + n]; i += n
        else:
            raise ValueError(f"wire type {wt}")
        out.append((fn, wt, v))
    return out


def text(v, wt):
    if wt != 2:
        raise ValueError("string field has wire type %d" % wt)
    return v.decode("utf-8")


def file_end(d, start):
    """End offset of the FileDescriptorProto beginning at start (stops at first non-file field)."""
    i = start
    seen_name = False
    while i < len(d):
        try:
            key, j = varint(d, i)
            fn, wt = key >> 3, key & 7
            if FILE_FIELDS.get(fn) != wt or (fn == 1 and seen_name):
                break
            if wt == 2:
                n, j = varint(d, j)
                j += n
            else:
                _, j = varint(d, j)
        except ValueError:
            break
        if j > len(d):
            break
        seen_name |= fn == 1
        i = j
    return i


def parse_enum(b):
    e = {"name": "", "values": []}
    for fn, wt, v in fields(b):
        if fn == 1:
            e["name"] = text(v, wt)
        elif fn == 2:
            val = {"name": "", "number": 0}
            for f2, w2, v2 in fields(v):
                if f2 == 1:
                    val["name"] = text(v2, w2)
                elif f2 == 2:
                    val["number"] = v2 - (1 << 64) if v2 >> 63 else v2
            e["values"].append(val)
    if not e["name"]:
        raise ValueError("enum without name")
    return e


def parse_field(b):
    f = {"name": "", "number": 0, "label": 1, "type": 0, "type_name": "", "extendee": "",
         "oneof": None, "proto3_optional": False}
    for fn, wt, v in fields(b):
        if fn == 1:
            f["name"] = text(v, wt)
        elif fn == 2:
            f["extendee"] = text(v, wt)
        elif fn == 3:
            f["number"] = v
        elif fn == 4:
            f["label"] = v
        elif fn == 5:
            f["type"] = v
        elif fn == 6:
            f["type_name"] = text(v, wt)
        elif fn == 9:
            f["oneof"] = v
        elif fn == 17:
            f["proto3_optional"] = bool(v)
    if not f["name"] or not f["number"] or f["type"] not in range(1, 19):
        raise ValueError("bad field")
    return f


def parse_message(b):
    m = {"name": "", "fields": [], "nested": [], "enums": [], "oneofs": [], "exts": [],
         "map_entry": False}
    for fn, wt, v in fields(b):
        if fn == 1:
            m["name"] = text(v, wt)
        elif fn == 2:
            m["fields"].append(parse_field(v))
        elif fn == 3:
            m["nested"].append(parse_message(v))
        elif fn == 4:
            m["enums"].append(parse_enum(v))
        elif fn == 6:
            m["exts"].append(parse_field(v))
        elif fn == 7:
            m["map_entry"] = any(f == 7 and v2 for f, _, v2 in fields(v))
        elif fn == 8:
            m["oneofs"].append(text(next((x for f, w, x in fields(v) if f == 1), b""), 2))
    if not m["name"]:
        raise ValueError("message without name")
    return m


def parse_file(b):
    f = {"name": "", "package": "", "deps": [], "messages": [], "enums": [], "services": [],
         "exts": [], "syntax": ""}
    for fn, wt, v in fields(b):
        if fn == 1:
            f["name"] = text(v, wt)
        elif fn == 2:
            f["package"] = text(v, wt)
        elif fn == 3:
            f["deps"].append(text(v, wt))
        elif fn == 4:
            f["messages"].append(parse_message(v))
        elif fn == 5:
            f["enums"].append(parse_enum(v))
        elif fn == 6:
            svc = {"name": "", "methods": []}
            for f2, w2, v2 in fields(v):
                if f2 == 1:
                    svc["name"] = text(v2, w2)
                elif f2 == 2:
                    meth = {"name": "", "input": "", "output": ""}
                    for f3, w3, v3 in fields(v2):
                        if f3 == 1:
                            meth["name"] = text(v3, w3)
                        elif f3 == 2:
                            meth["input"] = text(v3, w3)
                        elif f3 == 3:
                            meth["output"] = text(v3, w3)
                    svc["methods"].append(meth)
            f["services"].append(svc)
        elif fn == 7:
            f["exts"].append(parse_field(v))
        elif fn == 12:
            f["syntax"] = text(v, wt)
    if not f["name"].endswith(".proto"):
        raise ValueError("file name not .proto")
    return f


def scan(d):
    """Return [(offset, bytes)] for every strictly parsing FileDescriptorProto, in file order."""
    found = []
    for mt in NAME_RE.finditer(d):
        start = mt.start()
        n = d[start + 1]
        name = d[start + 2:start + 2 + n]
        if len(name) != n or not name.endswith(b".proto") or b"\x0a" in name:
            continue
        end = file_end(d, start)
        try:
            parse_file(d[start:end])
        except (ValueError, UnicodeDecodeError):
            continue
        found.append((start, d[start:end]))
    return found


def tname(t, pkg):
    t = t.lstrip(".")
    return t[len(pkg) + 1:] if pkg and t.startswith(pkg + ".") else t


def render_field(f, pkg, proto3, entries, ind, lines):
    tn = tname(f["type_name"], pkg)
    if f["type"] in (11, 14) and f["label"] == 3 and tn.split(".")[-1] in entries:
        k, v = entries[tn.split(".")[-1]]
        typ = f"map<{k}, {v}>"
        label = ""
    else:
        typ = tn if f["type"] in (11, 14) else "group" if f["type"] == 10 else TYPES[f["type"]]
        label = LABELS.get(f["label"], "") + " " if f["label"] != 1 or not proto3 else ""
        if proto3 and f["proto3_optional"]:
            label = "optional "
    lines.append(f"{ind}{label}{typ} {f['name']} = {f['number']};")


def render_enum(e, ind, lines):
    lines.append(f"{ind}enum {e['name']} {{")
    for v in e["values"]:
        lines.append(f"{ind}  {v['name']} = {v['number']};")
    lines.append(f"{ind}}}")


def render_message(m, pkg, proto3, ind, lines):
    entries = {}
    for n in m["nested"]:
        if n["map_entry"]:
            kv = {f["number"]: f for f in n["fields"]}
            ft = lambda f: tname(f["type_name"], pkg) if f["type"] in (11, 14) else TYPES.get(f["type"], "?")
            entries[n["name"]] = (ft(kv[1]), ft(kv[2]))
    lines.append(f"{ind}message {m['name']} {{")
    inner = ind + "  "
    # proto3 "optional" is stored as a synthetic oneof with a single proto3_optional field: render it as a plain optional field, not a oneof
    synth = {i for i, _ in enumerate(m["oneofs"])
             if all(f["proto3_optional"] for f in m["fields"] if f["oneof"] == i)}
    for f in m["fields"]:
        if f["oneof"] is None or f["oneof"] in synth:
            render_field(f, pkg, proto3, entries, inner, lines)
    for i, o in enumerate(m["oneofs"]):
        if i in synth:
            continue
        lines.append(f"{inner}oneof {o} {{")
        for f in m["fields"]:
            if f["oneof"] == i:
                lines.append(f"{inner}  {tname(f['type_name'], pkg) if f['type'] in (11, 14) else TYPES.get(f['type'], 'group')} {f['name']} = {f['number']};")
        lines.append(f"{inner}}}")
    if m["exts"]:
        for ex in m["exts"]:
            lines.append(f"{inner}extend {tname(ex['extendee'], pkg)} {{")
            render_field(ex, pkg, proto3, entries, inner + "  ", lines)
            lines.append(f"{inner}}}")
    for e in m["enums"]:
        render_enum(e, inner, lines)
    for n in m["nested"]:
        if not n["map_entry"]:
            render_message(n, pkg, proto3, inner, lines)
    lines.append(f"{ind}}}")


def render(f):
    pkg, proto3 = f["package"], f["syntax"] == "proto3"
    lines = [f'syntax = "{f["syntax"] or "proto2"}";']
    if pkg:
        lines.append(f"package {pkg};")
    for dep in f["deps"]:
        lines.append(f'import "{dep}";')
    for e in f["enums"]:
        lines.append("")
        render_enum(e, "", lines)
    for ex in f["exts"]:
        lines.append("")
        lines.append(f"extend {tname(ex['extendee'], pkg)} {{")
        render_field(ex, pkg, proto3, {}, "  ", lines)
        lines.append("}")
    for m in f["messages"]:
        lines.append("")
        render_message(m, pkg, proto3, "", lines)
    for s in f["services"]:
        lines.append("")
        lines.append(f"service {s['name']} {{")
        for m in s["methods"]:
            lines.append(f"  rpc {m['name']}({tname(m['input'], pkg)}) returns ({tname(m['output'], pkg)});")
        lines.append("}")
    return "\n".join(lines) + "\n"


def sort_deps(blobs):
    """Order {name: bytes} so dependencies come first; unresolved cycles keep discovery order."""
    deps = {n: parse_file(b)["deps"] for n, b in blobs.items()}
    order, done = [], set()

    def visit(n, stack):
        if n in done or n in stack or n not in blobs:
            return
        for d in deps[n]:
            visit(d, stack | {n})
        done.add(n)
        order.append(n)

    for n in blobs:
        visit(n, frozenset())
    return order


def split_set(data):
    recs = []
    for fn, wt, v in fields(data):
        if fn != 1 or wt != 2:
            raise ValueError(f"unexpected field {fn} in FileDescriptorSet")
        recs.append(v)
    return recs


def main():
    exe, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    d = exe.read_bytes()
    blobs, dups = {}, []
    for off, b in scan(d):
        name = parse_file(b)["name"]
        if name in blobs:
            dups.append((name, off, b == blobs[name]))
        else:
            blobs[name] = b
            print(f"0x{off:08x} {len(b):7d} bytes  {name}")
    print(f"{exe}: {len(blobs)} descriptors found, {len(dups)} duplicates skipped")
    for name, off, same in dups:
        print(f"  duplicate {name} at 0x{off:08x} ({'identical' if same else 'DIFFERENT'})")
    order = sort_deps(blobs)
    out.mkdir(parents=True, exist_ok=True)
    desc = bytearray()
    for n in order:
        desc += b"\x0a" + varint_bytes(len(blobs[n])) + blobs[n]
        p = out / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render(parse_file(blobs[n])), encoding="utf-8")
    (out / "acevo.desc").write_bytes(bytes(desc))
    print(f"wrote {out / 'acevo.desc'} ({len(desc)} bytes) and {len(order)} .proto files")

    recs = split_set((out / "acevo.desc").read_bytes())
    parsed = [parse_file(r) for r in recs]
    names = {f["name"] for f in parsed}
    missing = sorted({dep for f in parsed for dep in f["deps"] if dep not in names})
    nproto = len(list(out.rglob("*.proto")))
    seen, misordered = set(), 0
    for f in parsed:
        misordered += any(dep not in seen for dep in f["deps"] if dep in names)
        seen.add(f["name"])
    print(f"self-check: {len(recs)} records parse strictly, {len(names)} unique names, "
          f"{nproto} .proto files on disk, {len(missing)} missing dependencies, "
          f"{misordered} files listed before a dependency")
    if missing:
        print("  missing: " + ", ".join(missing))
    if len(recs) != len(blobs) or nproto != len(blobs) or len(names) != len(blobs):
        sys.exit("self-check FAILED: count mismatch")


def varint_bytes(n):
    out = bytearray()
    while n > 0x7F:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


if __name__ == "__main__":
    main()
