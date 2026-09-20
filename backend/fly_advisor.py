"""Experimental live advisor backed by the trained fly connectome checkpoint.

The policy never writes motors or changes the safety LED.  It consumes the same two
camera panes and LiDAR turn, then publishes a steering suggestion for observation
and later evaluation.  Model loading and inference stay off the LiDAR thread.
"""

import csv
import json
import math
import os
from pathlib import Path
import sys
import threading
import time


REPO_ROOT = Path(__file__).resolve().parents[1]
FLY_ROOT = REPO_ROOT / "fly-gym"
DEFAULT_CHECKPOINT = FLY_ROOT / "checkpoints" / "connectome_rnn_dagger_iter_10.pt"
LIDAR_BINS = 12
MAX_RANGE_M = 12.0
MIN_RANGE_M = 0.05
ACTIVITY_SAMPLE_SIZE = 64


def lidar_features(ranges, angles, bins=LIDAR_BINS):
    """Match fly-gym/core/lidar.py without importing the simulation stack."""
    nearest = [MAX_RANGE_M] * bins
    for angle, distance in zip(angles, ranges):
        if not (math.isfinite(angle) and math.isfinite(distance) and distance > 0):
            continue
        normalized = (angle + math.pi) % (2 * math.pi) - math.pi
        index = min(int((normalized + math.pi) / (2 * math.pi) * bins), bins - 1)
        nearest[index] = min(nearest[index], max(MIN_RANGE_M, min(distance, MAX_RANGE_M)))
    return [1.0 - distance / MAX_RANGE_M for distance in nearest]


def action_to_advice(velocity, heading_rad):
    if abs(velocity) < 0.1:
        motion = "stop"
    else:
        motion = "forward" if velocity > 0 else "reverse"
    if heading_rad > math.radians(10):
        turn = "left"
    elif heading_rad < math.radians(-10):
        turn = "right"
    else:
        turn = "straight"
    return {
        "motion": motion,
        "turn": turn,
        "velocity": round(float(velocity), 3),
        "headingDeg": round(math.degrees(float(heading_rad)), 1),
    }


def _csv_rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _connectome_neuron_ids(path):
    """Recreate the stable tensor-index to FAFB root-ID mapping used in training."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        aliases = (
            ("pre", "post"),
            ("Presynaptic_ID", "Postsynaptic_ID"),
            ("Pre", "Post"),
            ("pre_root_id", "post_root_id"),
        )
        columns = next((pair for pair in aliases if set(pair) <= fields), None)
        if columns is None:
            raise ValueError("connectome edge list has no recognised neuron columns")
        neuron_ids = set()
        for row in reader:
            neuron_ids.add(int(row[columns[0]]))
            neuron_ids.add(int(row[columns[1]]))
    return [str(root_id) for root_id in sorted(neuron_ids)]


def activity_sample(hidden, neuron_ids, limit=ACTIVITY_SAMPLE_SIZE):
    """Return the strongest measured signed hidden states for the live viewer."""
    state = hidden.detach().float().flatten()
    count = min(int(limit), int(state.numel()))
    magnitudes, indices = state.abs().topk(count, sorted=True)
    values = state.index_select(0, indices)
    indices = indices.cpu().tolist()
    values = values.cpu().tolist()
    magnitudes = magnitudes.cpu().tolist()
    return {
        "semantics": "signed_tanh_hidden_state",
        "neurons": [
            {
                "index": int(index),
                "rootId": neuron_ids[index],
                "activation": round(float(value), 5),
                "magnitude": round(float(magnitude), 5),
            }
            for index, value, magnitude in zip(indices, values, magnitudes)
        ],
    }


def _load_model(checkpoint):
    """Rebuild inference directly from checkpoint buffers, without MuJoCo."""
    import cv2
    import numpy as np
    import torch

    if str(FLY_ROOT) not in sys.path:
        sys.path.insert(0, str(FLY_ROOT))
    from agents.connectome_rnn_agent import ConnectomeAgent
    from models.connectome_rnn_model import LeakyConnectomeRNNCell

    metadata_path = Path(str(checkpoint) + ".robot.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("lidar_feature_bins") != LIDAR_BINS:
        raise ValueError("checkpoint does not use the expected 12 LiDAR bins")
    if metadata.get("frame") != "x forward, y left, z up; metres":
        raise ValueError("checkpoint robot frame does not match the live scanner")

    requested = os.environ.get("ROBOT_FLY_DEVICE", "auto")
    device = torch.device("cuda" if requested == "auto" and torch.cuda.is_available()
                          else "cpu" if requested == "auto" else requested)
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)

    rows = state["cell.W_coo_rows"].to(device)
    columns = state["cell.W_col_indices"].to(device)
    values = state["cell.W_values"].to(device)
    size = tuple(int(value) for value in state["cell.W_size"])
    weights = torch.sparse_coo_tensor(
        torch.stack([rows, columns]), values, size=size, device=device,
        check_invariants=False,
    ).coalesce()
    cell = LeakyConnectomeRNNCell(
        weights,
        state["cell.input_nodes"].tolist(),
        state["cell.output_nodes"].tolist(),
        state["cell.neuron_type_ids"],
        int(state["cell.alpha_logits"].numel()),
        train_rnn_weights=False,
        train_readout_head=False,
        dtype=torch.float32,
        batch_chunk=8,
        row_tile_size=69320,
    ).to(device)

    visual_names = (
        "pr_L1_left", "pr_L2_left", "pr_L3_left",
        "pr_L1_right", "pr_L2_right", "pr_L3_right",
    )
    grid_names = (
        "grid_L1_left", "grid_L2_left", "grid_L3_left",
        "grid_L1_right", "grid_L2_right", "grid_L3_right",
    )
    visual_lengths = [int(state[name].shape[1]) for name in grid_names]
    connectome = FLY_ROOT / "connectomes" / "drosophila adult connectome"
    tactile_lengths = [
        _csv_rows(connectome / "head_bristles_left.csv"),
        _csv_rows(connectome / "head_bristles_right.csv"),
    ]
    wind_length = int(state["wind_mlp.2.bias"].numel())
    lengths = visual_lengths + tactile_lengths + [wind_length]
    names = visual_names + ("tactile_left", "tactile_right", "wind")
    if sum(lengths) != int(state["cell.input_nodes"].numel()):
        raise ValueError("checkpoint input layout cannot be reconstructed")
    splits, start = {}, 0
    for name, length in zip(names, lengths):
        splits[name] = (start, start + length)
        start += length

    # Grid buffers from the checkpoint replace these dummy positions on load.
    positions = [(0.0, 0.0)] * sum(visual_lengths)
    agent = ConnectomeAgent(
        cell, positions, splits, dtype=torch.float32, lidar_bins=LIDAR_BINS
    ).to(device)
    agent.load_state_dict(state, strict=True)
    agent.eval()
    hidden = torch.zeros(1, agent.cell.N, device=device, dtype=torch.float32)
    neuron_ids = _connectome_neuron_ids(connectome / "connections_princeton.csv")
    if len(neuron_ids) != agent.cell.N:
        raise ValueError("connectome neuron IDs do not match checkpoint shape")
    return agent, hidden, device, cv2, np, torch, neuron_ids


class FlyPolicyAdvisor:
    """Run the checkpoint opportunistically and expose only its latest advice."""

    def __init__(self, checkpoint=DEFAULT_CHECKPOINT, interval_s=0.1, enabled=True):
        self.checkpoint = Path(checkpoint) if checkpoint else DEFAULT_CHECKPOINT
        self.enabled = enabled and self.checkpoint.is_file() and Path(
            str(self.checkpoint) + ".robot.json"
        ).is_file()
        self.interval_s = max(float(interval_s), 0.05)
        self._frames = {}
        self._model = None
        self._last_started = 0.0
        self._worker = None
        self._result = None
        self._active_direction = "stopped"
        self._reset_requested = True
        self._lock = threading.Lock()

    def offer_camera(self, pane, jpeg):
        if pane in (0, 1) and jpeg:
            with self._lock:
                self._frames[pane] = bytes(jpeg)

    def observe_scan(self, scan, direction):
        if not self.enabled:
            return None
        now = time.monotonic()
        with self._lock:
            if direction != self._active_direction:
                self._active_direction = direction
                self._reset_requested = True
            if direction == "stopped":
                self._result = {"status": "idle", "advisoryOnly": True}
                return self._result
            ready = len(self._frames) == 2 and direction != "stopped"
            busy = self._worker is not None and self._worker.is_alive()
            if ready and not busy and now - self._last_started >= self.interval_s:
                frames = dict(self._frames)
                features = lidar_features(scan.ranges, scan.angles)
                self._last_started = now
                if self._result is None:
                    self._result = {"status": "loading", "advisoryOnly": True}
                self._worker = threading.Thread(
                    target=self._infer,
                    args=(frames, features, direction),
                    name="fly-policy",
                    daemon=True,
                )
                self._worker.start()
            return self._result

    def _infer(self, frames, features, direction):
        try:
            if self._model is None:
                self._model = _load_model(self.checkpoint)
            agent, hidden, device, cv2, np, torch, neuron_ids = self._model
            with self._lock:
                reset = self._reset_requested
                self._reset_requested = False
            if reset:
                agent.reset_vision_state()
                hidden = torch.zeros_like(hidden)
            images = []
            for pane in (0, 1):
                encoded = np.frombuffer(frames[pane], dtype=np.uint8)
                bgr = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
                if bgr is None:
                    raise ValueError("camera JPEG could not be decoded")
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                rgb = cv2.resize(rgb, (128, 128), interpolation=cv2.INTER_AREA)
                images.append(
                    torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0)
                    .to(device=device, dtype=torch.float32)
                )
            goal = (1.0, 0.0) if direction == "forward" else (-1.0, 0.0)
            sensors = {
                "collision": torch.zeros(1, device=device),
                "collision_angle": torch.zeros(1, device=device),
                "wind_direction": torch.tensor([goal], device=device),
                "lidar_features": torch.tensor([features], device=device),
            }
            with torch.no_grad():
                hidden, action = agent.step(
                    hidden, {"cam_left": images[0], "cam_right": images[1], "sensors": sensors}
                )
            self._model = (agent, hidden, device, cv2, np, torch, neuron_ids)
            advice = action_to_advice(action[0, 0].item(), action[0, 1].item())
            result = {
                "status": "ready",
                "advisoryOnly": True,
                "checkpoint": self.checkpoint.name,
                "goalDirection": direction,
                "activity": activity_sample(hidden, neuron_ids),
                **advice,
            }
        except Exception as error:
            result = {
                "status": "error", "advisoryOnly": True,
                "error": "%s: %s" % (type(error).__name__, error),
            }
            self.enabled = False
        with self._lock:
            if self._active_direction == direction:
                self._result = result

    def close(self):
        pass
