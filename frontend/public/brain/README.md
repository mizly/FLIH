# FAFB-space brain anatomy

The viewer uses 78 JFRC2 neuropil meshes transformed into FlyWire FAFB14.1
coordinates by the flyconnectome/fafbseg-py project. These are registered atlas
volumes, not reconstructed individual neurons, synapses, or the ventral nerve
cord. The source neuron count describes the connectome, not the displayed dots.
Training telemetry currently has no neuron coordinates, so activity is shown in
the measured-state readout rather than assigned arbitrary anatomical positions.

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
