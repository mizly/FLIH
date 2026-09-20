# fly-gym: FLYNN — Robust Neural Network for Robot Navigation using Fly Brain Topology

Code accompanying **"FLYNN: Robust Neural Network for Robot Navigation using Fly Brain Topology"**
([arXiv:2607.00025](https://arxiv.org/abs/2607.00025); see [Citation](#citation)).

FLYNN is a recurrent neural network whose connectivity is derived directly from the FlyWire FAFB v783
*Drosophila* connectome (139,255 neurons, 5,342,445 synaptic connections). It's trained with DAgger
imitation learning to drive a four-wheel, two-camera robot to a goal around randomly placed obstacles
in a MuJoCo arena, and is benchmarked against a synthetic Watts-Strogatz control network
("SmallWorldNet", matched on the connectome's degree/path-length statistics) and two conventional CNN
baselines (EfficientNet-B0, MobileNetV3-Large) to ask how much of its navigation ability is
attributable to the real fly wiring diagram, as opposed to network size, topology, or a conventional
vision pipeline.

## Overview

- **Body / world:** a four-wheel skid-steer robot with two cameras and planar LiDAR, simulated
  in [MuJoCo](https://mujoco.org/), navigating toward a goal in an arena scattered with cylindrical
  obstacles. Checkerboard (training/in-distribution) and photo-realistic (out-of-distribution eval)
  scene variants are selected via `MuJoCoTwoCamEnv(texture_mode=...)`.
- **Brain:** every unit in the RNN corresponds to one neuron in the fly connectome, and every recurrent
  weight corresponds to a synapse-count-weighted connection from the connectome edge list. Camera
  pixels are sampled at the real photoreceptor-column positions and passed through a virtual-retina
  model (log transform + high-pass L1/L2 / low-pass L3 filtering) before entering the RNN,
  approximating the fly's early visual processing (photoreceptors -> lamina L1-L3); a fixed set of
  descending neurons is read out through a small MLP into `[velocity, heading]`. The connectome weight
  matrix is rescaled to a target spectral radius at load time for stable recurrent dynamics, and a
  custom `MemoryEfficientSparseMM` autograd function (CSR forward pass, cached-COO O(NNZ) backward
  pass) makes training a ~140k-neuron recurrent cell tractable on a single GPU.
- **Training:** DAgger imitation learning against an analytic **VFH\*** (Vector Field Histogram + A*)
  planner + PID teacher.
- **Comparisons:** the same task/training pipeline trains the Watts-Strogatz "SmallWorldNet" control
  (isolating topology from the real wiring diagram) and the EfficientNet-B0/MobileNetV3-Large CNN
  baselines, so navigation performance, robustness, and internal dynamics (via PCA of hidden-state
  trajectories) can be compared across architectures.

## Physical robot configuration

The updated `wheel_positions.png` is the layout reference. Both texture scenes
include `environment/robot_geometry.xml`. Coordinates in the
diagram are millimetres, with x right and y forward. MuJoCo uses metres with x
forward and y left: `(x_sim, y_sim, z_sim) = (y_diagram, -x_diagram, z_diagram)/1000`.
The body origin has the mounting-screw centroid's horizontal position; its nominal
simulation height is 100 mm. Sensor local z offsets account for that height.

| Item | Nominal geometry from the diagram |
| --- | --- |
| Four wheel centers | x = ±108 mm, y = ±124 mm in diagram coordinates |
| Track / wheelbase | 216 / 248 mm |
| Camera centers | L: (-35, 103, 175), R: (35, 103, 175) mm |
| Camera orientation | 29.73° outward yaw per camera, 5° downward pitch |
| Camera field of view | 69.47° horizontal × 42.61° vertical, nominal 77° diagonal |
| Top deck / LiDAR plane | 130 / 210 mm above ground; LiDAR centered horizontally |

Cameras render at 16:9 before resizing the entire image to the network's configured
input size (128×128 by default). This preserves angular coverage even for square
network inputs. Camera intrinsics are nominal and still require calibration on
the actual camera stream. The 150 mm screw spacing locates the origin; it is not
treated as a measured chassis width.

The supplied tire drawing specifies **67.50 mm outer diameter and 26.50 mm tread
width** (33.75 mm radius, 13.25 mm half-width). These dimensioned values take precedence
over its “65 mm” product label. The 30.60 mm overall dimension includes the hub;
the cylindrical tire collision shape uses tread width. Wheel centers sit 33.75 mm
above ground; their body-relative z offsets preserve the deck/camera/LiDAR heights.
`robot_config.py` derives wheel radius, track, wheelbase and footprint from the
shared XML. The provisional chassis half-extents remain 145×85×30 mm, with a lumped
2 kg mass (including onboard components); wheel mass, tire friction, suspension
compliance, motor inertia and servo gains still need hardware calibration.

The selected [Yahboom L-type 520 motor kit](https://category.yahboom.net/products/l-type-encoder-dc-reduction-motor?variant=51500753846588)
uses 12 V motors with 40:1 gearing. The [motor specification table](https://cdn.shopify.com/s/files/1/0066/9686/1780/files/520_encoder_geared_motor_2.jpg)
lists 300 RPM ±5% output, 4.4 kgf·cm rated torque, and 10 kgf·cm stall torque.
All four velocity actuators now allow ±31.416 rad/s and limit sustained torque
to ±0.431493 N·m. The 0.980665 N·m stall figure is recorded as a specification,
not used as a continuous operating limit. At 300 RPM the wheel's kinematic speed
is 1.0603 m/s; this does not guarantee loaded ground speed. The navigation command
ceiling remains 0.4 m/s. The velocity servo is an approximation of a closed-loop
motor controller; current, voltage sag, thermal effects and the full torque-speed
curve are not simulated. Published current, power and motor mass are recorded in
checkpoint metadata, not treated as measured drivetrain dynamics.

The 11-line motor encoder, 40:1 reduction and x4 quadrature decoding give **1760
counts per wheel revolution**. Observations expose signed `wheel_encoder_counts`
and `wheel_angular_velocity` (rad/s), ordered FL, FR, RL, RR. Counts reset with each
episode; they measure shaft rotation, not slip-corrected chassis displacement.
These channels support odometry/debugging; the current connectome policy still
uses cameras, LiDAR, goal direction and contact inputs rather than encoder inputs.

`LidarConfig` in `robot_config.py` targets the **YDLIDAR T-mini Plus 12M**, Yahboom
variant `52514639020348`: **360°, 0.05–12 m, 4000 samples/s, default 6 Hz**
(adjustable 6–12 Hz). The simulation uses 667 uniformly spaced rays at 6 Hz,
approximately 0.54° apart; ray count follows sample rate divided by scan rate.
See the [manufacturer specifications](https://www.ydlidar.com/products/view/27.html)
and [datasheet](https://www.ydlidar.com/Public/upload/files/2024-05-24/YDLIDAR%20T-mini%20Plus%20Data%20Sheet_V1.1%20%28240131%29.pdf).
The 12 m rating is for 80% reflectivity; the datasheet gives 4 m at 10% reflectivity
and a typical 20 mm systematic error. These material/error effects are not yet
simulated. The scan remains nominally horizontal as specified by the robot layout;
the actual unit's optical tilt still needs calibration.
Scans use MuJoCo ray intersections at the mounted
sensor pose, include walls/obstacles, exclude robot geometry, and hold between
updates, with scan deadlines maintained independently of the control period.
Angles run from -FOV/2 toward +FOV/2 without duplicating the endpoint;
zero is forward, positive is left. Ranges are metres; missing/out-of-range returns
are max-range, and too-close returns are clipped to min-range. The model is ideal:
it does not yet model material reflectivity, noise, dropouts or rolling-scan motion.

DAgger now learns from cameras **and 12 LiDAR proximity sectors**, alongside the
existing goal direction/contact inputs. Each sector is `1 - min(range)/max_range`;
the sectors follow scan-angle order. Raw sectors survive replay storage and enter
the trainable goal/sensor MLP. This uses the existing wind input segment as an
engineering sensor adapter, not a biological claim about LiDAR. The VFH+ teacher
continues to use privileged obstacle positions, with clearance based on the full
four-wheel footprint. CNN baselines remain vision-only.

Actions are `[normalized_speed, heading_error_radians]`: speed is bounded to [-1,1]
and mapped to a configured 0.4 m/s maximum; heading error produces yaw rate with
gain 0.5/s. Wheel targets use the 216 mm track and wheel radius, with both wheels
on each side driven together. Actual skid-steer response depends on tire slip.
The default training/evaluation horizon is now 4000 steps (80 seconds), allowing
time to traverse the arena at these lower speeds.

Train a fresh policy with `python train_connectome_rnn_dagger.py` from `fly-gym`.
Each checkpoint gets a `.robot.json` sidecar containing geometry, scan settings,
control settings and assumptions. The checkpoint runner detects the LiDAR input
width automatically. Old vision-only weights can still load, but their geometry
and action calibration differ; they do not acquire LiDAR capability without
retraining. Old two-input sensor MLP weights cannot directly resume LiDAR training.
`core/lidar.py::lidar_proximity_features` accepts arbitrary scan lengths and angles
to produce the same 12 inputs on hardware. For ROS LaserScan, supply angles from
`angle_min + arange(N)*angle_increment` in radians. For raw device angles, use
`clockwise=True`: [Yahboom documents clockwise raw angles](https://www.yahboom.net/public/upload/upload-html/1726051408/Tmini-Plus%20lidar-Reading%20data%20%28USART%29.html).
Use `yaw_offset` if the sensor arrow is rotated relative to robot forward. Convert
raw distances to metres first. Missing/invalid returns and empty sectors currently
map to max range (zero proximity), not a separate unknown-space channel.
Real deployment must provide matching scan sectors and camera preprocessing; this
change supplies the simulation sensor interface, not a device-specific LiDAR driver.

Verify the geometry, camera coverage, scan distances, drive direction and LiDAR
training gradients from the repository root:

```powershell
python -m unittest discover -s fly-gym/tests -p test_robot_geometry.py -v
```

## Live training dashboard

Open `http://localhost:3000/training` with the web app running (`npm run dev`
from the repository root). Start `python train_connectome_rnn_dagger.py` from
`fly-gym` in another terminal. The page refreshes every two seconds with live
optimization losses, episode rewards, goal/contact rates, DAgger progress,
buffer composition and saved checkpoints. Collection metrics include the
teacher/student action mixture; they are not held-out evaluation results.

The trainer writes atomic JSON snapshots to `fly-gym/training/latest.json` on a
background thread. No dashboard server is required for training to run. The web
API is read-only, and the dashboard never starts or stops the trainer. Restart
an already-running trainer to enable the new telemetry hooks. Training errors,
interruptions and completion are recorded; a missing heartbeat for 15 seconds
shows as paused instead of live. The latest snapshot remains available after exit.

To use another directory or a trainer on another machine, set the same absolute
`FLY_GYM_TRAINING_FILE` path for Python and Next.js, on a filesystem both can
access. One snapshot file represents one active/latest run; use separate paths
for concurrent runs. Browser history is bounded to 2,000 loss points, 200 episode
summaries and 100 checkpoints; existing CSV/checkpoint outputs remain unchanged.

## Repository structure

```
core/                    Shared utilities: connectome/edge-list loading + cell construction
                         (utils.py), A* global path planning (astar.py), the VFH*+PID teacher
                         algorithm (vfhplus.py)
environment/             MuJoCo environment: four-wheel robot, two cameras, LiDAR, randomized
                         obstacles/goal, checkerboard (training) vs. photo-realistic (OOD-eval)
                         scene variants selected via MuJoCoTwoCamEnv(texture_mode=...)
agents/                  Per-architecture agent wrappers: FLYNN/SmallWorldNet sensory front-end
                         (connectome_rnn_agent.py), EfficientNet/MobileNet CNN baselines, and the
                         VFH*+PID DAgger teacher (teacher_analytic_agent.py)
models/                  FLYNN's core RNN cell with a custom memory-efficient sparse-autograd
                         backward pass (connectome_rnn_model.py), and the teacher's path-follow
                         controller
connectomes/             Connectome data. Small per-modality neuron-ID CSVs and the SmallWorldNet
                         generator script are tracked; the large raw edge lists (hundreds of MB)
                         are not -- see Data below.
tests/                   Dev/diagnostic tools: gradient-correctness sanity check for the custom
                         sparse autograd (debug_rnn_grad.py), turn-vs-straight threshold tuning
                         (tune_direction_threshold.py)

shared_config.py         Shared paths/hyperparameters for the FLYNN/SmallWorldNet training and
                         eval scripts. Defaults to FLYNN; see the comment at the top to switch to
                         SmallWorldNet.
train_connectome_rnn_dagger.py   DAgger training for FLYNN / SmallWorldNet
train_visionnet_dagger.py        DAgger + camera-dropout training for the EfficientNet/MobileNet
                                  baselines
run_connectome_rnn_checkpoint.py Evaluation rollouts for a trained FLYNN/SmallWorldNet checkpoint
run_vision_agent_checkpoint.py   Evaluation rollouts for a trained EfficientNet/MobileNet checkpoint
test_vfhplus.py                  Sanity-check tool for the VFH*+PID teacher

collision_statistics.py  Aggregates raw per-episode eval data into the collision/success-rate/SPL/
                         speed statistics and bar charts reported in the paper
count_collisions.py      Per-episode collision/SPL/speed augmentation of raw eval rollout data
compare_trajectories.py  Trajectory-overlay comparison figures
visualize_episodes.py    Per-episode top-down trajectory plots (obstacles, path, start/end, target)
analysis_pca_statistics.py  KDE + vector-arithmetic (full-vision ≈ left-eye + right-eye) analysis
                             of FLYNN's internal hidden-state trajectories
analysis_pca.py          PCA visualization of hidden-state trajectories from a single eval run
```

## Models

### FLYNN (`agents/connectome_rnn_agent.py`, `models/connectome_rnn_model.py`)

Each unit is one neuron from the connectome edge list; its state follows a leaky recurrent update
`h_new = (1 - alpha_type) * h + alpha_type * phi(W_sparse @ h + b)`, where `alpha_type` is a learnable
per-cell-type leak rate and `phi` is `tanh`/`relu`. Sensory input: camera pixels through the virtual
retina into visual-column neurons, tactile head-bristle neurons driven by collision/contact angle, and
wind-direction input routed through a small MLP into the Johnston's organ neurons. Cell types
parameterize per-type leak rates and let training scripts selectively freeze/train weights, biases, or
per-type alphas.

### SmallWorldNet control

The same `LeakyConnectomeRNNCell` architecture, but wired with a Watts-Strogatz small-world graph
(`connections_ws_small_world.csv`, matched on the real connectome's node/edge/degree statistics)
instead of the real connectome — isolating whether small-world topology alone (a property the fly
connectome is known to have) explains task performance, independent of the real wiring diagram. Select
it via `BASE_PATH`/`EDGE_PATH` in `shared_config.py`.

### Vision-CNN baselines (non-connectome)

- **`MobileNetAgent`** (`agents/mobilenet_agent.py`) — ImageNet-pretrained MobileNetV3-Large (first
  conv adapted to 1-channel grayscale, classifier removed) feeding a `GRUCell`, plus wind-direction and
  collision scalars, into a small MLP policy head.
- **`EfficientNetAgent`** (`agents/efficientnet_agent.py`) — identical scheme with an EfficientNet-B0
  backbone.

### Analytic teacher (`agents/teacher_analytic_agent.py`, `core/vfhplus.py`)

`PlannerAnalyticTeacher` is not a trained network but a classical controller used to generate expert
demonstrations for DAgger: a VFH\* planner (polar obstacle histogram + short-horizon A\* search with
heading-consistency costs) produces a local waypoint, a PID line-follower steers toward it, and a
scripted back-up/turn/forward recovery sequence handles collisions.

## Setup

Requires Python 3.10+.

```bash
pip install -r requirements.txt
```

For a reproducible Windows setup, use the included local virtual environment:

```powershell
.\setup.ps1
.\.venv\Scripts\Activate.ps1
```

`setup.ps1` installs the dependencies and runs `smoke_test.py`, which checks the
MuJoCo cameras, observation/action spaces, and the analytic obstacle-avoidance
teacher without opening a window. The smoke test is useful before downloading
the large connectome edge list.

On Windows, `setup.ps1` installs and verifies the tested CUDA 12.8 builds of
PyTorch 2.9.0 and torchvision 0.24.0. The CUDA runtime is included in those
wheels; an NVIDIA driver compatible with CUDA 12.8 is still required. Use
`.\setup.ps1 -CpuOnly` only on a machine where GPU training is not required.
A plain `pip install -r requirements.txt` may select a CPU-only PyTorch wheel.

## Data and checkpoints

Connectome data and trained checkpoints are excluded from version control due to size. The
connectome's small per-modality CSVs and the SmallWorldNet generator script are tracked under
`connectomes/`. Not tracked:

- `connectomes/drosophila adult connectome/connections_princeton.csv` (~261MB) — the real FAFB v783
  edge list (`pre_root_id`, `post_root_id`, `syn_count` or equivalent aliases), sourced from
  FlyWire.ai / the `philshiu/Drosophila_brain_model` project (see
  `connectomes/drosophila adult connectome/data source.txt` for provenance).
- `connectomes/ws_small_world/connections_ws_small_world.csv` (~169MB) — the synthetic SmallWorldNet
  control edge list. Regeneratable from a fixed seed via
  `connectomes/ws_small_world/generate_ws_network_new.py`.
- `connectomes/drosophila adult connectome/visual_column_L1_L2_L3_rear_view_{left,right}.csv`,
  `head_bristles_{left,right}.csv`, `descending_neurons.csv`, `consolidated_cell_types.csv`,
  `JO-C_and_JO-E.csv` — small per-modality neuron-ID CSVs (photoreceptor/lamina positions, tactile
  head bristles, descending/output neurons, cell types, Johnston's organ wind-sensing neurons) *are*
  tracked and load automatically once the large edge list above is in place.
- Trained checkpoints (`checkpoints/*.pt`).

<!-- TODO: host the files above (Zenodo/HuggingFace/institutional storage) and link them here, along
     with a small download script, so a fresh clone can reproduce Table I without a full retrain. -->

The simulator and teacher do not require the large edge list. The fly-brain
trainer does: place the real connectome file at
`connectomes/drosophila adult connectome/connections_princeton.csv`, with columns
`pre`, `post`, and `weight` (the loader also accepts the documented aliases).
This file is intentionally not included in the repository.

## Usage

Train FLYNN or SmallWorldNet (edit the `BASE_PATH` toggle at the top of `shared_config.py` to choose
which):

```bash
python train_connectome_rnn_dagger.py
```

For a short pilot run, override the defaults without editing the trainer:

```powershell
$env:FLY_GYM_DAGGER_ITERS = "1"
$env:FLY_GYM_EPISODES_PER_ITER = "10"
$env:FLY_GYM_TRAIN_STEPS_PER_ITER = "5"
$env:FLY_GYM_N_ENVS = "2"
python train_connectome_rnn_dagger.py
```

Train an EfficientNet/MobileNet baseline (edit `AGENT` at the top of the file):

```bash
python train_visionnet_dagger.py
```

Evaluate a trained checkpoint (checkpoint path is a required argument for both):

```bash
python run_connectome_rnn_checkpoint.py checkpoints/<your_checkpoint>.pt
python run_vision_agent_checkpoint.py checkpoints/<your_checkpoint>.pt
```

Both eval scripts write per-episode rollout data to `eval_data/<run_name>/`. Aggregate that into the
reported statistics and figures with:

```bash
python collision_statistics.py
python count_collisions.py
python compare_trajectories.py
python visualize_episodes.py
python analysis_pca_statistics.py
```

`analysis_pca.py` and `compare_trajectories.py` still have local data-path constants near the top of
each file that need to point at your own eval-data location before running them.

## Live training preview

The `/training` dashboard displays a lightweight 3D arena for new connectome
DAgger runs. One environment publishes CPU position, heading, goal, and obstacle
geometry at most twice per wall-clock second through the existing telemetry
heartbeat. The browser receives it with the existing two-second metrics poll;
intermediate steps are skipped. The fly is a stylized avatar of the navigation
robot, not a biomechanical fly simulation. It holds the last scene during optimization.

There is no extra inference, simulator rendering, GPU readback, or frame queue.
Sampling drops updates if the telemetry lock is busy and retains only 64 trail
points. Browser interpolation is capped at 20 FPS for 400 ms after a new sample,
then stops; hidden/off-screen views stop drawing. Reduced motion disables
interpolation. Small CPU-copy and payload costs remain; zero throughput impact
has not been established with a full training benchmark.

Existing training processes need a restart to publish geometry; do not interrupt
an expensive run just for the preview. To disable sampling entirely for your next
run, set `$env:FLY_GYM_PREVIEW = "0"` in PowerShell before starting the trainer.

## License

[MIT](LICENSE).

## Citation

<!-- TODO: confirm the full author list before publishing -- neither this file nor arXiv:2607.00025's
     metadata gave a reliable full author list at the time this was written. -->

If you use this code, please cite the accompanying paper:

```bibtex
@misc{flynn2026,
  title         = {FLYNN: Robust Neural Network for Robot Navigation using Fly Brain Topology},
  eprint        = {2607.00025},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2607.00025},
  year          = {2026}
}
```
