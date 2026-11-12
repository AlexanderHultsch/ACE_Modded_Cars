"""Shared helpers for the test suite: repo paths, tools/ on sys.path, run_tool() for CLI calls, tmp() temp dirs, protobuf byte builders.

tmp() is a context manager yielding a pathlib.Path that is removed on exit; run_tool() runs a tools/ script with `python -B -I`.
"""
import contextlib
import pathlib
import struct
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.dont_write_bytecode = True
sys.path.insert(0, str(TOOLS))


def run_tool(name, *args, cwd=None, input=None):
    return subprocess.run([sys.executable, "-B", "-I", str(TOOLS / name), *map(str, args)],
                          capture_output=True, text=True, cwd=cwd, input=input)


@contextlib.contextmanager
def tmp():
    with tempfile.TemporaryDirectory() as d:
        yield pathlib.Path(d)


def pb_varint(n):
    out = bytearray()
    while n > 0x7F:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


def pb_key(fn, wt):
    return pb_varint(fn << 3 | wt)


def pb_int(fn, v):
    return pb_key(fn, 0) + pb_varint(v)


def pb_f32(fn, v):
    return pb_key(fn, 5) + struct.pack("<f", v)


def pb_f64(fn, v):
    return pb_key(fn, 1) + struct.pack("<d", v)


def pb_bytes(fn, b):
    return pb_key(fn, 2) + pb_varint(len(b)) + b


def pb_str(fn, s):
    return pb_bytes(fn, s.encode("utf-8"))


def pb_msg(fn, *parts):
    return pb_bytes(fn, b"".join(parts))


def pb_vint(fn, v):
    """Varint field; a negative v is sent as 64-bit two's complement like protobuf int32/int64/enum values."""
    return pb_key(fn, 0) + pb_varint(v & (1 << 64) - 1)


def desc_field(name, number, typ, label=1, type_name="", oneof=None, extendee="", options=None, proto3_optional=False):
    """FieldDescriptorProto body."""
    parts = [pb_str(1, name), pb_int(3, number), pb_int(4, label), pb_int(5, typ)]
    if extendee:
        parts.append(pb_str(2, extendee))
    if type_name:
        parts.append(pb_str(6, type_name))
    if options is not None:
        parts.append(pb_bytes(8, options))
    if oneof is not None:
        parts.append(pb_int(9, oneof))
    if proto3_optional:
        parts.append(pb_int(17, 1))
    return b"".join(parts)


def desc_enum(name, values):
    """EnumDescriptorProto body; values = [(name, number)]."""
    return pb_str(1, name) + b"".join(pb_msg(2, pb_str(1, n), pb_vint(2, v)) for n, v in values)


def desc_message(name, fields=(), nested=(), enums=(), oneofs=(), exts=(), options=None):
    """DescriptorProto body; fields/nested/enums/exts are bodies from desc_*, oneofs are names, options is raw MessageOptions bytes."""
    parts = [pb_str(1, name)]
    parts += [pb_bytes(2, f) for f in fields]
    parts += [pb_bytes(3, m) for m in nested]
    parts += [pb_bytes(4, e) for e in enums]
    parts += [pb_bytes(6, x) for x in exts]
    if options is not None:
        parts.append(pb_bytes(7, options))
    parts += [pb_msg(8, pb_str(1, o)) for o in oneofs]
    return b"".join(parts)


def desc_file(name, package="", deps=(), messages=(), enums=(), services=(), exts=(), syntax=""):
    """FileDescriptorProto body; services = [(name, [(method, input_type, output_type)])]."""
    parts = [pb_str(1, name)]
    if package:
        parts.append(pb_str(2, package))
    parts += [pb_str(3, d) for d in deps]
    parts += [pb_bytes(4, m) for m in messages]
    parts += [pb_bytes(5, e) for e in enums]
    for sname, methods in services:
        parts.append(pb_msg(6, pb_str(1, sname), *[pb_msg(2, pb_str(1, m), pb_str(2, i), pb_str(3, o)) for m, i, o in methods]))
    parts += [pb_bytes(7, x) for x in exts]
    if syntax:
        parts.append(pb_str(12, syntax))
    return b"".join(parts)


def desc_set(*files):
    """FileDescriptorSet (the layout of schemas/acevo.desc) from FileDescriptorProto bodies."""
    return b"".join(pb_bytes(1, f) for f in files)
