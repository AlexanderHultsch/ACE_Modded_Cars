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
