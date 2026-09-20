"""Bundle the public FAFB-space neuropil atlas; Python standard library only."""

import io
import json
from pathlib import Path
import re
import struct
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1] / "frontend/public/brain"
REPO = "https://api.github.com/repos/flyconnectome/fafbseg-py"


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    # Keep the exact original archive and license alongside the derived asset.
    manifest = ROOT / "source.json"
    if manifest.exists():
        commit = json.loads(manifest.read_text())["commit"]
    else:
        commit = json.loads(fetch(REPO + "/commits/master"))["sha"]
    base = f"https://raw.githubusercontent.com/flyconnectome/fafbseg-py/{commit}"
    source = base + "/fafbseg/data/JFRC2NP.surf.fw.zip"
    archive_path = ROOT / "JFRC2NP.surf.fw.zip"
    if not archive_path.exists():
        archive_path.write_bytes(fetch(source))
    (ROOT / "LICENSE.txt").write_bytes(fetch(base + "/LICENSE"))
    meshes = []
    with zipfile.ZipFile(io.BytesIO(archive_path.read_bytes())) as archive:
        for name in sorted(archive.namelist()):
            if "/" in name or not name.endswith(".ply"):
                continue
            data = archive.read(name)
            header, body = data.split(b"end_header\n", 1)
            assert b"format binary_little_endian 1.0" in header
            assert b"property list int int vertex_indices" in header
            nv = int(re.search(rb"element vertex (\d+)", header)[1])
            nf = int(re.search(rb"element face (\d+)", header)[1])
            vertices = list(struct.unpack_from(f"<{nv * 3}f", body))
            faces = []
            offset = nv * 12
            for _ in range(nf):
                count = struct.unpack_from("<i", body, offset)[0]
                assert count == 3
                faces.extend(struct.unpack_from("<3i", body, offset + 4))
                offset += 16
            meshes.append({"name": name[:-4], "positions": vertices, "indices": faces})
    # Center and scale as one atlas, retaining relative positions and shapes.
    minimum = [min(min(m["positions"][a::3]) for m in meshes) for a in range(3)]
    maximum = [max(max(m["positions"][a::3]) for m in meshes) for a in range(3)]
    center = [(lo + hi) / 2 for lo, hi in zip(minimum, maximum)]
    scale = 6 / (maximum[0] - minimum[0])
    for mesh in meshes:
        mesh["positions"] = [
            round((v - center[i % 3]) * scale * (1 if i % 3 == 0 else -1), 5)
            for i, v in enumerate(mesh["positions"])
        ]
    (ROOT / "neuropils.json").write_text(json.dumps(meshes, separators=(",", ":")))
    manifest.write_text(json.dumps({
        "commit": commit, "source": source, "regions": len(meshes),
        "description": "JFRC2 neuropil template meshes transformed to FlyWire FAFB14.1 space by fafbseg. Not individual neuron reconstructions.",
        "original_atlas": "https://doi.org/10.5281/zenodo.10567",
        "transform": {"center_nm": center, "scale": scale, "axis_signs": [1, -1, -1]},
    }, indent=2))
    print(f"Bundled {len(meshes)} neuropils; {sum(len(m['positions']) // 3 for m in meshes):,} vertices")


if __name__ == "__main__":
    main()
