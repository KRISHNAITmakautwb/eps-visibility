"""Simulated FPGA counts and rotation stage, for running the app without devices."""
import math
import threading
import time

import numpy as np

from .counts import CountsSource
from .stage import Stage, stage_command


class SimWorld:
    """Shared state: singles ~50k, Coinc 1-2 follows cos^2 of the HWP-rotated polarization."""

    def __init__(self):
        self.angle = 0.0       # mechanical stage angle, degrees
        self.lock = threading.Lock()


class SimCounts(CountsSource):
    def __init__(self, log, world, interval_ms):
        super().__init__(log)
        self.world, self.interval_ms = world, interval_ms

    def _run(self):
        rng = np.random.default_rng()
        self.log("Simulated counts started")
        while not self._stop.wait(self.interval_ms / 1000.0):
            with self.world.lock:
                th = math.radians(self.world.angle)
            k = self.interval_ms / 500.0
            c12 = 40 + 3000 * math.cos(2 * (th - math.radians(7))) ** 2
            lam = np.array([52000, 48000, 300, 280, c12, 3, 2, 2, 2, 1]) * k
            self._publish(rng.poisson(lam))


class SimStage(Stage):
    def __init__(self, log, reply_cb, world):
        super().__init__(log, reply_cb)
        self.world = world
        self._open = False

    @property
    def connected(self):
        return self._open

    def open(self, port):
        self._open = True
        self.reply_cb("SIM stage ready")

    def close(self):
        self._open = False

    def move(self, angle, direction, mode, stage, timeout=20.0, abort=None):
        self.log(f"Stage <- {stage_command(angle, direction, mode, stage).strip()} (sim)")
        time.sleep(0.3)
        with self.world.lock:
            if mode == "Home":
                self.world.angle = 0.0
            else:
                self.world.angle += angle if direction == "Clock" else -angle
            cur = self.world.angle
        msg = f"CUR:{cur:g};FINAL:{cur:g}"
        self.reply_cb(msg)
        return msg
