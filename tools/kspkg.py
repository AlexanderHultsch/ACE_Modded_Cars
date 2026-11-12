"""Path-safe .kspkg tool for AC EVO 0.7+ mod packages. Python 3.9+, stdlib only.

usage:
  python tools/kspkg.py list    <pkg>
  python tools/kspkg.py extract <pkg> <outdir> [prefix]   # prefix e.g. content\\cars\\ks_bmw_m3_e46_csl (case-insensitive)
  python tools/kspkg.py pack    <indir> <pkg>      # indir contains content/cars/<car_id>/...
  python tools/kspkg.py verify  <pkgA> <pkgB>     # same entries + same file contents?

Format (reverse engineered, verified on all 6 Hina's Drift Club 1.4 packages, see HANDOVER.md):
  [0x000000 .. 0x100000)   1 MiB header, all zero
  [0x100000 .. data_end)   file data, contiguous, no alignment, largest file first
  pad with zeros to next 1 MiB boundary
  [size-64MiB .. size)     file table, 256-byte entries sorted by hash, rest zero,
                           whole table XOR'd with 8-byte KEY (repeating from table start)
  entry: +0x00 path (ascii/utf8, backslashes, lower case, max 0xE0 bytes)
         +0xE0 int32 0 | +0xE4 int16 flags (1=directory, 0x100=data XOR'd)
         +0xE6 int16 path length | +0xE8 u64 FNV-1a-64 of path encoded UTF-16LE
         +0xF0 int64 size | +0xF8 int64 offset (directories: 0/0)
Original format notes: ntpopgetdope/ace-kspkg (MIT, 32 MiB table, pre-0.7).
"""
import hashlib
import pathlib
import struct
import sys

TBL = 64 << 20          # 64 MiB file table (0.7+ packages; pre-0.7 game package used 32 MiB)
HEADER = 1 << 20
ENTRY = 0x100
FLAG_DIR, FLAG_XOR = 1, 1 << 8
KEY = bytes.fromhex("c135117da921979f")   # same key as the game's content.kspkg


def xor(buf, key):
    n = len(buf)
    if n == 0:
        return b""
    k = (key * (n // 8 + 1))[:n]
    return (int.from_bytes(buf, "little") ^ int.from_bytes(k, "little")).to_bytes(n, "little")


def path_hash(p):
    h = 0xCBF29CE484222325
    for b in p.encode("utf-16le"):
        h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def read_table(f):
    f.seek(0, 2)
    size = f.tell()
    f.seek(size - TBL)
    raw = f.read(TBL)
    key = raw[-8:]           # table tail is zero padding -> equals key
    entries = []
    for i in range(0, TBL, ENTRY):
        e = xor(raw[i:i + ENTRY], key)
        flags, plen = struct.unpack_from("<hh", e, 0xE4)
        h, fsize, foff = struct.unpack_from("<Qqq", e, 0xE8)
        if h == 0:
            break
        entries.append(dict(path=e[:plen].decode("utf-8", "replace"), flags=flags,
                            hash=h, size=fsize, off=foff))
    return key, entries, size


def safe_path(root, p):
    parts = [x for x in p.replace("\\", "/").split("/") if x not in ("", ".", "..")]
    out = root.joinpath(*parts).resolve()
    if root.resolve() not in out.parents and out != root.resolve():
        raise ValueError(f"unsafe path {p!r}")
    return out


def cmd_list(pkg):
    with open(pkg, "rb") as f:
        key, entries, size = read_table(f)
    print(f"key={key.hex()} entries={len(entries)} pkgsize={size}")
    for e in entries:
        kind = "D" if e["flags"] & FLAG_DIR else ("X" if e["flags"] & FLAG_XOR else "-")
        print(f"{kind} {e['size']:>10} {e['path']}")


def cmd_extract(pkg, outdir, prefix=None):
    root = pathlib.Path(outdir)
    root.mkdir(parents=True, exist_ok=True)
    if prefix is not None:
        prefix = prefix.lower().rstrip("\\")
    count = 0
    with open(pkg, "rb") as f:
        key, entries, _ = read_table(f)
        for e in entries:
            if prefix is not None:
                p = e["path"].lower()
                if p != prefix and not p.startswith(prefix + "\\"):
                    continue
            count += 1
            dst = safe_path(root, e["path"])
            if e["flags"] & FLAG_DIR:
                dst.mkdir(parents=True, exist_ok=True)
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            f.seek(e["off"])
            data = f.read(e["size"])
            if e["flags"] & FLAG_XOR:
                data = xor(data, key)
            dst.write_bytes(data)
    print(f"extracted {count} entries to {root}")


def cmd_pack(indir, pkg):
    root = pathlib.Path(indir)
    files, dirs = [], []
    for p in sorted(root.rglob("*")):
        rel = "\\".join(p.relative_to(root).parts).lower()
        if p.is_dir():
            # observed: only folders at depth >= 3 (content\cars\<id>...) get entries
            if len(p.relative_to(root).parts) >= 3:
                dirs.append(rel)
        elif p.is_file():
            files.append((rel, p))
    for rel, _ in files + [(d, None) for d in dirs]:
        if len(rel.encode()) > 0xE0:
            raise ValueError(f"path too long for table: {rel}")
    files.sort(key=lambda t: (-t[1].stat().st_size, t[0]))   # largest first
    entries = []
    with open(pkg, "wb") as out:
        out.write(b"\0" * HEADER)
        off = HEADER
        for rel, p in files:
            data = p.read_bytes()
            out.write(data)
            entries.append((rel, 0, len(data), off))
            off += len(data)
        pad = (-off) % (1 << 20)
        out.write(b"\0" * pad)
        entries += [(d, FLAG_DIR, 0, 0) for d in dirs]
        entries.sort(key=lambda e: path_hash(e[0]))
        table = bytearray(TBL)
        for i, (rel, flags, size, o) in enumerate(entries):
            pb = rel.encode()
            base = i * ENTRY
            table[base:base + len(pb)] = pb
            struct.pack_into("<ihhQqq", table, base + 0xE0, 0, flags, len(pb), path_hash(rel), size, o)
        out.write(xor(bytes(table), KEY))
    print(f"packed {len(files)} files + {len(dirs)} dirs -> {pkg}")


def _contents(pkg):
    with open(pkg, "rb") as f:
        key, entries, _ = read_table(f)
        res = {}
        for e in entries:
            if e["flags"] & FLAG_DIR:
                res[e["path"]] = ("D", e["hash"])
                continue
            f.seek(e["off"])
            data = f.read(e["size"])
            if e["flags"] & FLAG_XOR:
                data = xor(data, key)
            res[e["path"]] = (hashlib.sha256(data).hexdigest(), e["hash"])
    return res


def cmd_verify(a, b):
    ca, cb = _contents(a), _contents(b)
    only_a, only_b = sorted(set(ca) - set(cb)), sorted(set(cb) - set(ca))
    diff = sorted(k for k in set(ca) & set(cb) if ca[k] != cb[k])
    for k in only_a:
        print("only in A:", k)
    for k in only_b:
        print("only in B:", k)
    for k in diff:
        print("differs:  ", k)
    ok = not (only_a or only_b or diff)
    print("IDENTICAL CONTENT" if ok else f"{len(only_a)}/{len(only_b)}/{len(diff)} differences")
    return ok


def main():
    cmd = sys.argv[1]
    if cmd == "list":
        cmd_list(sys.argv[2])
    elif cmd == "extract":
        cmd_extract(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    elif cmd == "pack":
        cmd_pack(sys.argv[2], sys.argv[3])
    elif cmd == "verify":
        sys.exit(0 if cmd_verify(sys.argv[2], sys.argv[3]) else 1)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
