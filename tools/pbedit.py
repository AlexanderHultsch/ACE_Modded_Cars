"""Lossless schema-less protobuf editor: change single values, keep every other byte identical.

usage:
  python tools/pbedit.py get         <file> <path>
  python tools/pbedit.py set         <file> <path> <kind>:<value> -o <outfile>   # f32:1.0  int:6  str:hello
  python tools/pbedit.py scale-curve <file> <factor> -o <outfile>                # field 10 of every field-1 point
  python tools/pbedit.py roundtrip   <file-or-dir>...

Path: dot-separated steps, each `N` or `N[i]` (N = field number, i = 0-based occurrence among
sibling fields numbered N, default 0), e.g. `39.1`, `10[2].2`, `1[4].10`. Descending requires a
length-delimited field whose payload parses as a message. Fields are never created.

Untouched fields are re-emitted from their original bytes (tag, length varint, payload), so even
non-canonical (overlong) varints survive. Only the ancestors of an edited value get a freshly
computed canonical length varint. `set` needs `-o` and never overwrites the input implicitly.
`roundtrip` re-encodes the whole tree canonically and reports identical / canonical-differs /
not-protobuf per file (exit 1 only if a canonical-differs file changed semantically).
Wire types 0, 1, 2, 5 are supported; groups and malformed data raise ValueError.
"""
import pathlib
import re
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pb_raw  # noqa: E402

STEP = re.compile(r"^(\d+)(?:\[(\d+)\])?$")
KIND_WT = {"f32": 5, "int": 0, "str": 2}


def read_varint(b, i):
    r = s = 0
    while True:
        if i >= len(b):
            raise ValueError("truncated varint")
        c = b[i]; i += 1
        r |= (c & 0x7F) << s; s += 7
        if c < 0x80:
            return r, i
        if s >= 70:
            raise ValueError("varint too long")


def enc_varint(v):
    out = bytearray()
    while v > 0x7F:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    out.append(v)
    return bytes(out)


class Field:
    __slots__ = ("num", "wt", "tag", "lenraw", "payload", "child", "dirty")

    def __init__(self, num, wt, tag, lenraw, payload):
        self.num, self.wt, self.tag, self.lenraw, self.payload = num, wt, tag, lenraw, payload
        self.child = None
        self.dirty = False

    def message(self):
        if self.child is None:
            self.child = parse(self.payload)
        return self.child

    def encode(self):
        if self.dirty:
            body = self.child.encode()
            return self.tag + enc_varint(len(body)) + body
        return self.tag + self.lenraw + self.payload

    def encode_canonical(self):
        tag = enc_varint((self.num << 3) | self.wt)
        if self.wt == 0:
            return tag + enc_varint(read_varint(self.payload, 0)[0])
        if self.wt != 2:
            return tag + self.payload
        child = self.child if self.child is not None else try_parse(self.payload)
        body = child.encode_canonical() if child is not None else self.payload
        return tag + enc_varint(len(body)) + body

    def semantic(self):
        if self.wt == 0:
            return (self.num, 0, read_varint(self.payload, 0)[0])
        if self.wt == 2:
            child = self.child if self.child is not None else try_parse(self.payload)
            return (self.num, 2, child.semantic() if child is not None else self.payload)
        return (self.num, self.wt, self.payload)


class Message:
    def __init__(self, fields):
        self.fields = fields

    def find(self, num, idx=0):
        for f in self.fields:
            if f.num == num:
                if idx == 0:
                    return f
                idx -= 1
        return None

    def encode(self):
        return b"".join(f.encode() for f in self.fields)

    def encode_canonical(self):
        return b"".join(f.encode_canonical() for f in self.fields)

    def semantic(self):
        return tuple(f.semantic() for f in self.fields)


def parse(buf):
    buf = bytes(buf)
    n = len(buf)
    fields = []
    i = 0
    while i < n:
        start = i
        key, i = read_varint(buf, i)
        num, wt = key >> 3, key & 7
        if num == 0:
            raise ValueError("field 0")
        tag = buf[start:i]
        lenraw = b""
        if wt == 0:
            s = i
            _, i = read_varint(buf, i)
            payload = buf[s:i]
        elif wt in (1, 5):
            size = 8 if wt == 1 else 4
            if i + size > n:
                raise ValueError("truncated")
            payload = buf[i:i + size]; i += size
        elif wt == 2:
            s = i
            size, i = read_varint(buf, i)
            lenraw = buf[s:i]
            if i + size > n:
                raise ValueError("truncated")
            payload = buf[i:i + size]; i += size
        else:
            raise ValueError(f"wire type {wt}")
        fields.append(Field(num, wt, tag, lenraw, payload))
    return Message(fields)


def try_parse(buf):
    if not buf:
        return None
    try:
        return parse(buf)
    except ValueError:
        return None


def parse_path(path):
    steps = []
    for s in path.split("."):
        m = STEP.match(s)
        if not m or int(m.group(1)) == 0:
            raise ValueError(f"bad path: {path}")
        steps.append((int(m.group(1)), int(m.group(2) or 0), s))
    return steps


def walk(root, path):
    """Return the parsed fields along path, root-most first; the last one is the addressed field."""
    chain = []
    msg = root
    prefix = []
    for num, idx, s in parse_path(path):
        prefix.append(s)
        if chain:
            prev = chain[-1]
            if prev.wt != 2:
                raise ValueError(f"not a message: {'.'.join(prefix[:-1])}")
            try:
                msg = prev.message()
            except ValueError:
                raise ValueError(f"not a message: {'.'.join(prefix[:-1])}")
        f = msg.find(num, idx)
        if f is None:
            raise ValueError(f"no such field: {'.'.join(prefix)}")
        chain.append(f)
    return chain


def field_value(f):
    if f.wt == 0:
        return read_varint(f.payload, 0)[0]
    return f.payload


def get_field(buf, path):
    f = walk(parse(buf), path)[-1]
    return f.wt, field_value(f)


def set_value(buf, path, kind, value):
    if kind not in KIND_WT:
        raise ValueError(f"unknown kind: {kind}")
    root = parse(buf)
    chain = walk(root, path)
    f = chain[-1]
    if f.wt != KIND_WT[kind]:
        raise ValueError(f"kind {kind} does not match wire type {f.wt}: {path}")
    if kind == "f32":
        try:
            f.payload = struct.pack("<f", float(value))
        except OverflowError:
            raise ValueError(f"f32 out of range: {value}")
    elif kind == "int":
        v = int(value)
        if v < 0:
            v += 1 << 64
        if not 0 <= v < 1 << 64:
            raise ValueError(f"int out of range: {value}")
        f.payload = enc_varint(v)
    else:
        f.payload = value.encode("utf-8")
        f.lenraw = enc_varint(len(f.payload))
        f.child = None
    for a in chain[:-1]:
        a.dirty = True
    return root.encode()


def scale_curve_counted(buf, factor, field=10):
    root = parse(buf)
    points = [f for f in root.fields if f.num == 1]
    if not points:
        raise ValueError("no field 1 points")
    count = 0
    for p in points:
        if p.wt != 2:
            raise ValueError("not a message: 1")
        for g in p.message().fields:
            if g.num == field and g.wt == 5:
                try:
                    g.payload = struct.pack("<f", struct.unpack("<f", g.payload)[0] * factor)
                except OverflowError:
                    raise ValueError(f"f32 out of range after scaling by {factor}")
                p.dirty = True
                count += 1
                break
    return root.encode(), count


def scale_curve(buf, factor, field=10):
    return scale_curve_counted(buf, factor, field)[0]


def reencode_full(buf):
    return parse(buf).encode_canonical()


def semantic(buf):
    return parse(buf).semantic()


def roundtrip_status(buf):
    """Return (status, semantic_equal); status is identical, canonical-differs or not-protobuf."""
    try:
        msg = parse(buf)
        sem = msg.semantic()
        out = msg.encode_canonical()
        if out == buf:
            return "identical", True
        return "canonical-differs", parse(out).semantic() == sem
    except ValueError:
        return "not-protobuf", True


def format_value(wt, v):
    if wt == 0:
        return str(v)
    if wt == 5:
        return "(f32) %.9g" % struct.unpack("<f", v)[0]
    if wt == 1:
        return "(f64) %.17g" % struct.unpack("<d", v)[0]
    txt = None
    try:
        t = v.decode("utf-8")
        if t.isprintable():
            txt = t
    except UnicodeDecodeError:
        pass
    if txt is not None and not (len(v) > 2 and pb_raw.looks_like_msg(v) and not txt.isascii()):
        return f'"{txt}"'
    lines = []
    try:
        pb_raw.dump(v, 0, out=lines.append)
    except Exception:
        return f"<{len(v)} bytes>"
    return "\n".join(lines)


def cmd_get(file, path):
    wt, v = get_field(pathlib.Path(file).read_bytes(), path)
    lines = format_value(wt, v).split("\n")
    if len(lines) == 1:
        print(f"{path}: {lines[0]}")
    else:
        print(f"{path} {{")
        for ln in lines:
            print("  " + ln)
        print("}")


def cmd_set(file, path, spec, outfile):
    kind, sep, value = spec.partition(":")
    if not sep or kind not in KIND_WT:
        raise ValueError(f"bad value {spec!r}, expected f32:<float> | int:<int> | str:<text>")
    if kind == "f32":
        value = float(value)
    elif kind == "int":
        value = int(value)
    buf = pathlib.Path(file).read_bytes()
    new = set_value(buf, path, kind, value)
    old_txt = format_value(*get_field(buf, path)).replace("\n", " ")
    new_txt = format_value(*get_field(new, path)).replace("\n", " ")
    pathlib.Path(outfile).write_bytes(new)
    print(f"{path}: {old_txt} -> {new_txt}")


def cmd_scale_curve(file, factor, outfile):
    new, count = scale_curve_counted(pathlib.Path(file).read_bytes(), float(factor))
    pathlib.Path(outfile).write_bytes(new)
    print(f"scaled {count} points by {float(factor):g}")


def cmd_roundtrip(targets):
    counts = {"identical": 0, "canonical-differs": 0, "not-protobuf": 0}
    bad = 0
    for t in targets:
        t = pathlib.Path(t)
        files = sorted(p for p in t.rglob("*") if p.is_file()) if t.is_dir() else [t]
        for f in files:
            status, same = roundtrip_status(f.read_bytes())
            counts[status] += 1
            note = "" if same else "  SEMANTIC MISMATCH"
            bad += not same
            print(f"{status}  {f}{note}")
    print(f"{sum(counts.values())} files: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    return 1 if bad else 0


def split_out(args):
    if len(args) >= 2 and args[-2] == "-o":
        return args[:-2], args[-1]
    return args, None


def main():
    a = sys.argv[1:]
    cmd = a[0] if a else None
    rest, out = split_out(a[1:])
    try:
        if cmd == "get" and len(rest) == 2 and out is None:
            cmd_get(*rest)
        elif cmd == "set" and len(rest) == 3 and out:
            cmd_set(*rest, out)
        elif cmd == "scale-curve" and len(rest) == 2 and out:
            cmd_scale_curve(*rest, out)
        elif cmd == "roundtrip" and rest and out is None:
            sys.exit(cmd_roundtrip(rest))
        else:
            print(__doc__)
            sys.exit(2)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
