"""Lightweight terminal progress without querying or synchronizing CUDA."""
import sys
import threading
import time


class OptimizationProgress:
    def __init__(self, label, batches, stream=None):
        self.label = label
        self.total = batches * 3 + 1
        self.completed = 0
        self.phase = "starting"
        self.stream = stream if stream is not None else sys.stdout
        self.interactive = self.stream.isatty()
        self.started = time.monotonic()
        self.stopped = threading.Event()
        self.lock = threading.Lock()
        self.thread = None
        self.width = 0

    def _render(self):
        filled = int(20 * self.completed / self.total)
        bar = "#" * filled + "-" * (20 - filled)
        elapsed = time.monotonic() - self.started
        line = f"[train {self.label}] [{bar}] {self.phase} | {elapsed:.1f}s elapsed"
        if self.interactive:
            self.width = max(self.width, len(line))
            self.stream.write("\r" + line.ljust(self.width))
        else:
            self.stream.write(line + "\n")
        self.stream.flush()

    def update(self, completed, phase):
        with self.lock:
            self.completed = completed
            self.phase = phase
            self._render()

    def _heartbeat(self):
        while not self.stopped.wait(1.0):
            with self.lock:
                self._render()

    def __enter__(self):
        self.update(0, "starting")
        if self.interactive:
            self.thread = threading.Thread(target=self._heartbeat, daemon=True)
            self.thread.start()
        return self

    def __exit__(self, kind, error, traceback):
        self.stopped.set()
        if self.thread is not None:
            self.thread.join()
        if kind is not None:
            self.update(self.completed, f"stopped: {kind.__name__}")
        if self.interactive:
            self.stream.write("\n")
            self.stream.flush()
