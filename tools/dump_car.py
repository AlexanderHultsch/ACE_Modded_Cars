"""Dump all physics/setup/config files of an extracted car as schema-less protobuf text.

usage: python tools/dump_car.py <extracted_car_root> <out_dir>
  e.g. python tools/dump_car.py work/car/content/cars/<car_id> work/decoded/<car_id>

Skips meshes, textures, materials and other heavy render assets.
Numbers only, no field names: this is the schema-less fallback. For named, editable output use tools/car_json.py decode (needs schemas/, see tools/extract_protos.py).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pb_raw  # noqa: E402

SKIP = {".mesh", ".rimmesh", ".texture", ".texturemips", ".material", ".scene",
        ".actor", ".js", ".png", ".jpg", ".svg", ".animation", ".graphicsoverride",
        ".bank", ".ttf", ".bin", ".webm", ".mp4", ".ogg", ".wav", ".dds"}
TEXT = {".loc", ".json", ".txt", ".lut", ".ini", ".css", ".less", ".html", ".data"}


def main():
    src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    ok = fail = 0
    for f in sorted(src.rglob("*")):
        if not f.is_file() or f.suffix.lower() in SKIP:
            continue
        rel = f.relative_to(src)
        out = dst / rel.with_name(rel.name + ".txt")
        out.parent.mkdir(parents=True, exist_ok=True)
        data = f.read_bytes()
        if f.suffix.lower() in TEXT:
            out.write_text(data.decode("utf-8", "replace"), encoding="utf-8")
            ok += 1
            continue
        lines = []
        try:
            pb_raw.dump(data, 0, out=lines.append)
            ok += 1
        except Exception as e:  # not protobuf or unknown layout
            lines = [f"# DECODE FAILED: {e}", f"# size={len(data)} first bytes={data[:32].hex(' ')}"]
            fail += 1
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{src}: decoded {ok}, failed {fail}")


if __name__ == "__main__":
    main()
