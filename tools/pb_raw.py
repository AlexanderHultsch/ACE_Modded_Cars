"""Schema-less protobuf dump: prints field numbers, wire types and guessed values.

usage: python tools/pb_raw.py <file>"""
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from extract_protos import varint  # noqa: E402


def dump(b, depth, out=print):
    i = 0
    while i < len(b):
        key, i = varint(b, i)
        fn, wt = key >> 3, key & 7
        if fn == 0:
            raise ValueError("field 0")
        pad = "  " * depth
        if wt == 0:
            v, i = varint(b, i)
            out and out(f"{pad}{fn}: {v}")
        elif wt == 1:
            v = struct.unpack_from("<d", b, i)[0]; i += 8
            out and out(f"{pad}{fn}: (f64) {v:g}")
        elif wt == 5:
            v = struct.unpack_from("<f", b, i)[0]; i += 4
            out and out(f"{pad}{fn}: (f32) {v:g}")
        elif wt == 2:
            n, i = varint(b, i)
            sub = b[i:i + n]
            if len(sub) != n:
                raise ValueError("truncated")
            i += n
            txt = None
            try:
                t = sub.decode("utf-8")
                if t.isprintable():
                    txt = t
            except UnicodeDecodeError:
                pass
            nested = None
            if txt is None or (n > 2 and not txt.isascii()):
                nested = []
                try:
                    dump(sub, depth + 1, nested.append)
                except Exception:
                    nested = None
            if nested is None and txt is not None:
                out and out(f'{pad}{fn}: "{txt}"')
            elif nested is not None:
                out and out(f"{pad}{fn} {{")
                for line in nested:
                    out and out(line)
                out and out(f"{pad}}}")
            else:
                out and out(f"{pad}{fn}: <{n} bytes>")
        else:
            raise ValueError(f"wire type {wt}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__.split("\n\n")[1])
        sys.exit(2)
    dump(pathlib.Path(sys.argv[1]).read_bytes(), 0)
