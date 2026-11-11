"""Schema-less protobuf dump: prints field numbers, wire types and guessed values."""
import struct
import sys


def varint(b, i):
    r = s = 0
    while True:
        c = b[i]; i += 1
        r |= (c & 0x7F) << s; s += 7
        if c < 0x80:
            return r, i


def looks_like_msg(b):
    try:
        dump(b, 0, out=None)
        return len(b) > 0
    except Exception:
        return False


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
            if txt is not None and not (n > 2 and looks_like_msg(sub) and not txt.isascii()):
                out and out(f'{pad}{fn}: "{txt}"')
            elif looks_like_msg(sub):
                out and out(f"{pad}{fn} {{")
                dump(sub, depth + 1, out)
                out and out(f"{pad}}}")
            else:
                out and out(f"{pad}{fn}: <{n} bytes>")
        else:
            raise ValueError(f"wire type {wt}")


if __name__ == "__main__":
    dump(open(sys.argv[1], "rb").read(), 0)
