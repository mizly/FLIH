# FAFB-space brain anatomy

The viewer uses 78 JFRC2 neuropil meshes transformed into FlyWire FAFB14.1
coordinates by the flyconnectome/fafbseg-py project. These are registered atlas
volumes, not reconstructed individual neurons, synapses, or the ventral nerve
cord. The source neuron count describes the connectome, not the displayed dots.
The training API joins sampled neuron root IDs to official FlyWire v783 backbone
anchor coordinates. Luminous markers display the signed hidden-state magnitude
at those anchors. Green is positive and orange is negative; zero is invisible.
Markers are an X-ray overlay so they remain visible in solid surface mode.
The neuron count describes the full source connectome; only sampled states are
colored. Unmapped IDs are counted explicitly and are never assigned positions.
Unchanged values stay lit, including saturated states at +1 or -1. There is no
synthetic spiking animation. Stale/optimization snapshots retain their last values.

- Original atlas: https://doi.org/10.5281/zenodo.10567
- Mesh provider: https://github.com/flyconnectome/fafbseg-py
- Dataset explorer: https://codex.flywire.ai/?dataset=fafb
- `source.json`: pinned source commit, URL, and coordinate transformation.
- `JFRC2NP.surf.fw.zip`: unmodified source PLY archive.
- `LICENSE.txt`: upstream repository license, preserved verbatim.
- `neuropils.json`: derived mesh vertices and triangular faces. Vertices are
  centered, uniformly scaled, and rotated 180 degrees about X for display;
  region geometry is otherwise unchanged.

Regenerate from the repository root with `python scripts/build-brain-asset.py`.
The script uses the pinned commit in `source.json` and the bundled archive.
The renderer samples points on the actual triangle surfaces, using a fixed seed.
All browser assets are local; viewing requires no FlyWire login or external API.
Camera changes render on demand, with no background animation loop.

## Neuron coordinates

`neuron-positions.json` is generated with `python scripts/build-neuron-positions.py`.
It maps string root IDs (without JavaScript numeric precision loss) to atlas-space
coordinates. `neurons-source.json` records the pinned source, citation, input
checksum, and transform. Source `pos_x/y/z` annotation anchors use 4×4×40 nm
voxels; these are converted to nm before applying the atlas transform. These are
points on neurons, not full neuron reconstructions or soma estimates.

Attribution: Schlegel et al., *Whole-brain annotation and multi-connectome cell
typing of Drosophila*, Nature (2024), https://doi.org/10.1038/s41586-024-07686-5.
Data: https://github.com/flyconnectome/flywire_annotations.
The full lookup stays cached on the server; only sampled coordinates reach the
browser. No trainer changes or restart are needed. Unsupported dataset versions
and lookup failures preserve training metrics and show an explicit status.
