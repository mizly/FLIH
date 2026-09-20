#!/usr/bin/env python3
"""Live cameras + LiDAR -> FLYNN actions. SHADOW ONLY: never opens the motor board.

From the repo root (stop camera_stream/lidar_stream/other sensor owners first):
    python3 backend/live_flynn_shadow.py --smoke-test
    python3 backend/live_flynn_shadow.py --lidar-port /dev/ttyUSB0 --duration 30

Requires working torch, numpy, pandas, Jetson OpenCV with GStreamer, and pyserial.
No simulator/ROS dependencies. Goal is robot-relative forward, not a world waypoint.
Speed output is normalized [-1,1]; heading is radians, NOT angular velocity.
Camera freshness uses serial-change time, not an unavailable capture timestamp.
"""

import argparse
from contextlib import ExitStack
import json
import math
from pathlib import Path
import signal
import sys
import time
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parent
FLY_GYM = BACKEND.parent / "fly-gym"
DEFAULT_CHECKPOINT = FLY_GYM / "checkpoints/connectome_rnn_dagger_iter_1.pt"


def positive_float(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return value


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    parser.add_argument("--hz", type=positive_float, default=50.0,
                        help="RNN tick rate; latest sensor samples held between updates")
    parser.add_argument("--duration", type=positive_float,
                        help="seconds after sensors become ready; default runs until Ctrl-C")
    parser.add_argument("--sensor-timeout", type=positive_float, default=1.0)
    parser.add_argument("--startup-timeout", type=positive_float, default=10.0)
    parser.add_argument("--log-every", type=positive_float, default=1.0,
                        help="seconds between action/timing reports")
    parser.add_argument("--lidar-port", help="default: /dev/ydlidar or detected USB scanner")
    parser.add_argument("--smoke-test", action="store_true",
                        help="ten synthetic forward passes, without opening hardware")
    return parser.parse_args(argv)


def load_model(args):
    # Lazy imports keep --help usable even if a CUDA shared library is missing.
    sys.path.insert(0, str(FLY_GYM))
    try:
        import torch
    except (ImportError, OSError) as exc:
        raise RuntimeError(f"PyTorch cannot import: {exc}. Fix the torch/CUDA "
                           "environment for this Python before running the loop.") from exc
    import shared_config as cfg
    from agents.connectome_rnn_agent import ConnectomeAgent
    from core.utils import build_connectome_cell, obs_to_torch
    from robot_config import LIDAR_FEATURE_BINS

    checkpoint = args.checkpoint.resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Checkpoint missing: {checkpoint}")
    with Path(str(checkpoint) + ".robot.json").open() as handle:
        metadata = json.load(handle)
    if metadata["observation_size"] != [128, 128]:
        raise ValueError("This adapter expects checkpoint observation_size [128,128]")
    if metadata["lidar_feature_bins"] != LIDAR_FEATURE_BINS:
        raise ValueError("Checkpoint and shared LiDAR preprocessing disagree on bin count")
    trained_hz = 1 / metadata["control_period_s"]
    if not math.isclose(args.hz, trained_hz):
        print(f"WARNING: requested {args.hz:g} Hz; checkpoint trained at {trained_hz:g} Hz",
              flush=True)
    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available()
                          else "cpu" if args.device == "auto" else args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable to PyTorch")
    if device.type == "cpu":
        print("WARNING: CPU inference selected; 50 Hz is not guaranteed.", flush=True)

    path_names = {
        "edge_path": "EDGE_PATH", "photoreceptor_left_csv": "PHOTORECEPTOR_LEFT_CSV",
        "photoreceptor_right_csv": "PHOTORECEPTOR_RIGHT_CSV",
        "tactile_left_csv": "TACTILE_LEFT_CSV", "tactile_right_csv": "TACTILE_RIGHT_CSV",
        "descending_neurons_csv": "DESCENDING_NEURONS_CSV",
        "cell_types_csv": "CELL_TYPES_CSV", "wind_sensing_csv": "WIND_SENSING_CSV",
    }
    paths = {key: str(FLY_GYM / getattr(cfg, value)) for key, value in path_names.items()}
    for path in paths.values():
        if not Path(path).is_file():
            raise FileNotFoundError(f"Required connectome CSV missing: {path}")
    print(f"Loading {checkpoint.name} on {device}; rebuilding connectome may take a while.",
          flush=True)
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    bins = state["wind_mlp.0.weight"].shape[1] - 2
    if bins != LIDAR_FEATURE_BINS:
        raise ValueError(f"Checkpoint weights expect {bins} LiDAR bins, not {LIDAR_FEATURE_BINS}")
    cell, positions, splits, id_map = build_connectome_cell(
        **paths, device=device, dtype=cfg.DTYPE, target_rho=cfg.TARGET_RHO,
        leak_alpha=cfg.LEAK_ALPHA, activation=cfg.ACTIVATION,
        train_rnn_weights=False, train_readout_head=False,
        batch_chunk=cfg.BATCH_CHUNK, row_tile_size=cfg.ROW_TILE_SIZE)
    del id_map
    agent = ConnectomeAgent(cell, photoreceptor_positions=positions, input_splits=splits,
                            dtype=cfg.DTYPE, input_scale_init=cfg.INPUT_SCALE_INIT,
                            lidar_bins=bins).to(device)
    agent.load_state_dict(state, strict=True)
    del state
    agent.eval().requires_grad_(False)
    agent.reset_vision_state()
    return torch, agent, obs_to_torch, SimpleNamespace(**metadata["lidar"])


def make_observation(left_rgb, right_rgb, lidar_features):
    import numpy as np
    return {"cam_left": left_rgb, "cam_right": right_rgb, "sensors": {
        "vec_to_goal": np.array([1.0, 0.0], dtype=np.float32),
        "wind_direction": np.array([1.0, 0.0], dtype=np.float32),
        "collision": 0.0, "collision_angle": 0.0, "lidar_features": lidar_features,
    }}


class LiveInputs:
    """Sample-and-hold adapter. None means waiting for initial sensor samples."""

    def __init__(self, cameras, rectifiers, scanner, lidar_config, timeout):
        self.cameras, self.rectifiers, self.scanner = cameras, rectifiers, scanner
        self.lidar_config, self.timeout = lidar_config, timeout
        self.serials = [None, None, None]
        self.seen = [None, None, None]
        self.images = [None, None]
        self.features = None

    def read(self, now=None, wall_now=None):
        import cv2
        from camera_geometry import to_network_input
        from core.lidar import lidar_proximity_features
        now = time.monotonic() if now is None else now
        wall_now = time.time() if wall_now is None else wall_now
        for index, camera in enumerate(self.cameras):
            if not camera.running:
                raise RuntimeError(f"{'Left' if index == 0 else 'Right'} camera stopped")
            frame, serial, _fps = camera.read()
            if frame is not None and serial != self.serials[index]:
                self.images[index] = cv2.cvtColor(
                    to_network_input(self.rectifiers[index](frame)), cv2.COLOR_BGR2RGB)
                self.serials[index], self.seen[index] = serial, now
        if not self.scanner.running:
            raise RuntimeError(f"LiDAR stopped: {self.scanner.error}")
        scan, serial = self.scanner.read()
        if scan is not None:
            if wall_now - scan.stamp > self.timeout:
                raise TimeoutError("LiDAR scan timestamp is stale")
            if serial != self.serials[2]:
                if not scan.returns:
                    raise RuntimeError("LiDAR scan has no valid returns; refusing all-clear input")
                # Driver already returns robot-frame CCW radians; no second rotation/flip.
                self.features = lidar_proximity_features(scan.ranges, scan.angles,
                                                        self.lidar_config)
                self.serials[2], self.seen[2] = serial, now
        ages = [None if stamp is None else now - stamp for stamp in self.seen]
        for name, age in zip(("left camera", "right camera", "LiDAR"), ages):
            if age is not None and age > self.timeout:
                raise TimeoutError(f"Stale {name}: no new sample for {age:.2f}s")
        if any(age is None for age in ages):
            return None
        return make_observation(*self.images, self.features), ages


def open_inputs(stack, args, lidar_config):
    import cv2
    from camera_geometry import Rectifier, CAPTURE_WIDTH, CAPTURE_HEIGHT, CAPTURE_FPS
    from csi_camera import CsiCamera
    from lidar import TminiPlus, find_port
    if not any("GStreamer" in line and "YES" in line
               for line in cv2.getBuildInformation().splitlines()):
        raise RuntimeError("OpenCV lacks GStreamer; use Jetson's GStreamer-enabled cv2 build")
    port = args.lidar_port or ("/dev/ydlidar" if Path("/dev/ydlidar").exists() else find_port())
    if not port:
        raise RuntimeError("No LiDAR serial port found; pass --lidar-port /dev/ttyUSB0")
    cameras, rectifiers = [], []
    for sensor_id, side in ((1, "left"), (0, "right")):
        rectifier = Rectifier(sensor_id)
        if not rectifier.calibrated:
            print(f"WARNING: {side} camera uses nominal calibration.", flush=True)
        camera = CsiCamera(sensor_id, width=CAPTURE_WIDTH, height=CAPTURE_HEIGHT,
                           fps=CAPTURE_FPS)
        stack.callback(camera.release)
        if not camera.start():
            raise RuntimeError(f"Cannot start {side} camera (sensor {sensor_id}); "
                               "check camera ownership and Argus/GStreamer")
        cameras.append(camera)
        rectifiers.append(rectifier)
    scanner = TminiPlus(port=port)
    stack.callback(scanner.release)
    if not scanner.start():
        raise RuntimeError(f"Cannot start LiDAR at {port}: {scanner.error}")
    return LiveInputs(cameras, rectifiers, scanner, lidar_config, args.sensor_timeout)


def run(args, action_sink=None):
    """Run live inference; an optional sink is used only by the motor-test entrypoint."""
    if action_sink is not None and args.smoke_test:
        raise ValueError("Motor output cannot be used with synthetic inputs")
    import numpy as np
    torch, agent, convert, lidar_config = load_model(args)
    hidden = torch.zeros((1, agent.cell.N), device=agent.device, dtype=torch.float32)
    with ExitStack() as stack, torch.inference_mode():
        if args.smoke_test:
            inputs = None
            observation = make_observation(np.zeros((128, 128, 3), dtype=np.uint8),
                                           np.zeros((128, 128, 3), dtype=np.uint8),
                                           np.zeros(agent.lidar_bins, dtype=np.float32))
        else:
            inputs = open_inputs(stack, args, lidar_config)
            deadline = time.monotonic() + args.startup_timeout
            print("Waiting for both cameras and a fresh LiDAR scan...", flush=True)
            while inputs.read() is None:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Timed out waiting for initial camera/LiDAR samples")
                time.sleep(0.01)
        if action_sink is not None:
            stack.callback(action_sink.close)  # stop motors BEFORE releasing sensors
        print("LIVE MOTOR TEST — goal=robot-forward [1,0]." if action_sink is not None
              else "SHADOW ONLY — goal=robot-forward [1,0]; no motor commands.", flush=True)
        start = next_tick = last_report = time.monotonic()
        ticks = reported_ticks = missed = 0
        period = 1 / args.hz
        while True:
            now = time.monotonic()
            if args.duration is not None and now - start >= args.duration:
                break
            ages = [0.0, 0.0, 0.0]
            if inputs is not None:
                sample = inputs.read()
                if sample is None:
                    raise RuntimeError("Sensor sample disappeared after startup")
                observation, ages = sample
            inference_start = time.monotonic()
            obs = convert(observation, agent.device, torch.float32)
            hidden, action = agent.step(hidden, obs)
            if not torch.isfinite(hidden).all().item() or not torch.isfinite(action).all().item():
                raise RuntimeError("Non-finite model state/action; stopping shadow loop")
            speed, heading = action[0].detach().cpu().tolist()  # synchronizes CUDA timing
            done = time.monotonic()
            inference_ms = 1000 * (done - inference_start)
            if action_sink is not None:
                if args.duration is not None and done - start >= args.duration:
                    break
                # Include capture/preprocessing/inference time in freshness checks.
                action_sink(speed, heading, [age + done - now for age in ages])
            ticks += 1
            if args.smoke_test or ticks == 1 or done - last_report >= args.log_every:
                rate = (ticks - reported_ticks) / max(done - last_report, 1e-9)
                print(f"tick={ticks} speed_norm={speed:+.3f} heading_rad={heading:+.3f} "
                      f"forward_ms={inference_ms:.1f} loop_hz={rate:.1f}/{args.hz:g} "
                      f"sample_age_ms=L:{ages[0]*1000:.0f},R:{ages[1]*1000:.0f},"
                      f"lidar:{ages[2]*1000:.0f} missed_deadlines={missed}", flush=True)
                last_report, reported_ticks = done, ticks
            if args.smoke_test and ticks >= 10:
                print("PASS: ten synthetic recurrent forward passes (hardware not tested).")
                break
            next_tick += period
            now = time.monotonic()
            if now > next_tick:
                skipped = math.floor((now - next_tick) / period) + 1
                missed += skipped
                next_tick += skipped * period  # no catch-up bursts through the RNN
            time.sleep(max(0, next_tick - time.monotonic()))


def main(argv=None):
    args = parse_args(argv)

    def stop(_signum, _frame):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, stop)
    try:
        run(args)
    except KeyboardInterrupt:
        print("Shadow loop stopped; sensors released.")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)
    return 0


if __name__ == "__main__":
    sys.exit(main())
