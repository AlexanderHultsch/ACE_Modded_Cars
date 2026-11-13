"""Shared helpers for the test suite: repo paths, tools/ on sys.path, run_tool() for CLI calls, tmp() temp dirs, protobuf byte builders.

tmp() is a context manager yielding a pathlib.Path that is removed on exit; run_tool() runs a tools/ script with `python -B -I`.
"""
import contextlib
import copy
import os
import pathlib
import re
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


def mini_setting(sid, kind="value", type="float", targets=None, **extra):
    """A catalogue setting with every required key; targets = [(file, path)] or [(file, path, True)] for an optional one."""
    s = {"id": sid, "group": "G", "label": "L " + sid, "kind": kind, "type": type, "unit": "", "description": "d " + sid,
         "verified": False}
    if kind in ("value", "flag"):
        s["targets"] = [dict(file=t[0], path=t[1], **({"optional": True} if len(t) > 2 else {})) for t in targets or ()]
    s.update(extra)
    return s


def mini_catalogue(*settings, car_id="ks_x"):
    groups = list(dict.fromkeys(s["group"] for s in settings if "group" in s))
    return {"car_id": car_id, "groups": [{"name": g, "description": "d " + g} for g in groups], "settings": list(settings)}


class FakeCar:
    """A synthetic extracted car below <work>/<car_id>/base for tune.py. The files on disk are empty placeholders; what
    tune.load_msg / save_msg decode and encode comes from self.store (absolute path -> object, or an exception instance
    to raise). install(test) patches tune.load_msg and tune.save_msg for the test and restores them afterwards."""

    def __init__(self, work, car_id="ks_x"):
        import tune
        self.tune, self.work, self.car_id = tune, str(work), car_id
        self.root = tune.base_dir(self.work, car_id)
        self.car_root = tune.car_root_of(self.root, car_id)
        self.shared = os.path.join(self.root, "content", "cars", "common_phsx")
        self.store, self.saved = {}, []

    def _put(self, base, rel, obj):
        path = os.path.join(base, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb"):
            pass
        if obj is not None:
            self.store[self.key(path)] = obj
        return path

    @staticmethod
    def key(path):
        import kspkg
        return os.path.realpath(kspkg.plain_path(path))

    def add(self, rel, obj=None):
        """A file below the car folder (rel with /), e.g. data/x.car."""
        return self._put(self.car_root, rel, obj)

    def add_shared(self, rel, obj=None):
        """A shared game file below content/cars/common_phsx."""
        return self._put(self.shared, rel, obj)

    def game_path(self, rel):
        return "content\\cars\\%s\\%s" % (self.car_id, rel.replace("/", "\\"))

    def install(self, test):
        from unittest import mock
        import car_json

        def load_msg(path):
            name = car_json.message_for(path)
            obj = self.store.get(self.key(path))
            if obj is None:
                raise ValueError("%s: no stub content" % path)
            if isinstance(obj, Exception):
                raise obj
            return copy.deepcopy(obj), name

        def save_msg(path, name, obj):
            self.store[self.key(path)] = copy.deepcopy(obj)
            self.saved.append(self.key(path))

        for attr, fn in (("load_msg", load_msg), ("save_msg", save_msg)):
            p = mock.patch.object(self.tune, attr, fn)
            p.start()
            test.addCleanup(p.stop)
        return self

    def clone_into(self, out_dir, new_id):
        """What clone_car.build does to the tree: copy base's car folder to <out_dir>/content/cars/<new_id> with the car id
        replaced in names and in text values (case-insensitive) and the stub contents copied along."""
        dst_root = os.path.join(out_dir, "content", "cars", new_id)
        for dp, _, names in os.walk(self.car_root):
            for n in names:
                src = os.path.join(dp, n)
                rel = os.path.relpath(src, self.car_root)
                dst = os.path.join(dst_root, re.sub(re.escape(self.car_id), new_id, rel, flags=re.IGNORECASE))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, "wb"):
                    pass
                if self.key(src) in self.store:
                    self.store[self.key(dst)] = self._renamed(self.store[self.key(src)], new_id)
        return dst_root

    def _renamed(self, obj, new_id):
        if isinstance(obj, str):
            return re.sub(re.escape(self.car_id), new_id, obj, flags=re.IGNORECASE)
        if isinstance(obj, list):
            return [self._renamed(v, new_id) for v in obj]
        if isinstance(obj, dict):
            return {k: self._renamed(v, new_id) for k, v in obj.items()}
        return copy.deepcopy(obj)
