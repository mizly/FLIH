"""Map FlyWire v783 neuron anchors into the bundled brain atlas display space."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1] / "frontend/public/brain"


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def main():
    manifest = ROOT / "neurons-source.json"
    if manifest.exists():
        commit = json.loads(manifest.read_text())["commit"]
    else:
        commit = json.loads(fetch("https://api.github.com/repos/flyconnectome/flywire_annotations/commits/main"))["sha"]
    base = f"https://raw.githubusercontent.com/flyconnectome/flywire_annotations/{commit}/"
    url = base + "supplemental_files/Supplemental_file1_neuron_annotations.tsv"
    data = fetch(url)
    transform = json.loads((ROOT / "source.json").read_text())["transform"]
    positions = {}
    for row in csv.DictReader(io.StringIO(data.decode()), delimiter="\t"):
        root_id = row["root_id"]  # Never round 64-bit identifiers through floats.
        try:
            nm = [float(row[f"pos_{a}"]) * unit for a, unit in zip("xyz", [4, 4, 40])]
        except ValueError:
            continue
        if not root_id.isdigit() or not all(math.isfinite(v) for v in nm):
            continue
        positions[root_id] = [round((v - c) * transform["scale"] * sign, 5)
                              for v, c, sign in zip(nm, transform["center_nm"], transform["axis_signs"])]
    (ROOT / "neuron-positions.json").write_text(json.dumps(positions, separators=(",", ":")))
    manifest.write_text(json.dumps({
        "commit": commit, "source": url, "sha256": hashlib.sha256(data).hexdigest(),
        "dataset": "FlyWire v783", "count": len(positions),
        "coordinate_kind": "Neuron backbone annotation anchor (not soma or reconstructed morphology)",
        "input_voxel_size_nm": [4, 4, 40], "transform": transform,
        "column_documentation": base + "supplemental_files/README.md",
        "citation": "Schlegel et al. Whole-brain annotation and multi-connectome cell typing of Drosophila. Nature (2024). https://doi.org/10.1038/s41586-024-07686-5",
    }, indent=2))
    print(f"Mapped {len(positions):,} FlyWire v783 neuron anchors")
    snapshot = ROOT.parents[2] / "fly-gym/training/latest.json"
    if snapshot.exists():
        neurons = json.loads(snapshot.read_text()).get("neural_activity", {}).get("neurons", [])
        print(f"Current sample coverage: {sum(n['root_id'] in positions for n in neurons)}/{len(neurons)}")


if __name__ == "__main__":
    main()
