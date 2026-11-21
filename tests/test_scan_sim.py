"""End-to-end scan against the simulators (no GUI, no hardware)."""
import threading
import unittest

from eps_visibility.analysis import analyse
from eps_visibility.hardware import SimCounts, SimStage, SimWorld
from eps_visibility.scan import run_scan


class TestSimScan(unittest.TestCase):
    def test_full_scan(self):
        world, events, logs = SimWorld(), [], []
        src = SimCounts(logs.append, world, interval_ms=50)
        stage = SimStage(logs.append, logs.append, world)
        stage.open(None)
        src.start()
        p = dict(stage="M1", offset=0, offset_dir="Clock", direction="AntiClock", nsteps=8,
                 step=90 / 8, settle_s=0.0, navg=2, interval_ms=50, home_end=True)
        try:
            status = run_scan(p, src, stage, threading.Event(),
                              lambda k, v: events.append((k, v)), logs.append)
        finally:
            src.stop()
        points = [v for k, v in events if k == "point"]
        self.assertEqual(status, "complete")
        self.assertEqual(len(points), 9)
        self.assertEqual(events[-1], ("scan_done", "complete"))
        self.assertEqual(world.angle, 0.0)                     # homed
        res = analyse(points, 4, hwp=True)
        self.assertGreater(res["fit"]["V"], 0.9)              # simulator's true V is 0.974

    def test_abort(self):
        world = SimWorld()
        src = SimCounts(lambda m: None, world, interval_ms=50)
        stage = SimStage(lambda m: None, lambda m: None, world)
        stage.open(None)
        src.start()
        abort = threading.Event()
        abort.set()
        p = dict(stage="M1", offset=0, offset_dir="Clock", direction="AntiClock", nsteps=4,
                 step=10, settle_s=0.0, navg=1, interval_ms=50, home_end=False)
        try:
            self.assertEqual(run_scan(p, src, stage, abort, lambda k, v: None, lambda m: None),
                             "aborted")
        finally:
            src.stop()


if __name__ == "__main__":
    unittest.main()
