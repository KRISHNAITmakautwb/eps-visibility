import unittest

import numpy as np

from eps_visibility.analysis import analyse, fit_visibility, raw_visibility
from eps_visibility.hardware.stage import parse_stage_reply, stage_command


class TestAnalysis(unittest.TestCase):
    def test_fit_recovers_known_visibility(self):
        x = np.linspace(0, 90, 17)                      # HWP: period 90° in stage angle
        a, amp = 1000.0, 900.0                          # V = 0.9
        y = a + amp * np.cos(2 * np.pi * (x - 20) / 90)
        fit = fit_visibility(x, y, np.sqrt(y), 90.0)
        self.assertAlmostEqual(fit["V"], 0.9, places=6)
        self.assertAlmostEqual(fit["x_max"], 20.0, places=4)

    def test_raw_visibility(self):
        self.assertAlmostEqual(raw_visibility([10, 50, 90]), 0.8)
        self.assertIsNone(raw_visibility([5]))

    def test_too_few_points_no_fit(self):
        self.assertIsNone(fit_visibility([0, 1, 2], [1, 2, 3], [1, 1, 1], 90.0))

    def test_analyse_points(self):
        pts = [dict(index=i, angle=a, n=4, mean=np.r_[np.full(4, 5e4), c, np.zeros(5)],
                    std=np.zeros(10))
               for i, (a, c) in enumerate(zip(range(0, 91, 15), (900, 600, 200, 50, 200, 600, 900)))]
        res = analyse(pts, 4, hwp=True)
        self.assertEqual(res["ci"], 4)
        self.assertAlmostEqual(res["raw"], 850 / 950)
        self.assertIsNotNone(res["fit"])


class TestStageProtocol(unittest.TestCase):
    def test_command_matches_v2_format(self):
        self.assertEqual(stage_command(5.625, "AntiClock", "Step", "M1"), "5.625AAntiClockBStepDM1\n")
        self.assertEqual(stage_command(0, "AntiClock", "Home", "M1"), "0AAntiClockBHomeDM1\n")

    def test_parse_reply(self):
        self.assertEqual(parse_stage_reply("CUR:12;FINAL:90"), {"CUR": "12", "FINAL": "90"})


if __name__ == "__main__":
    unittest.main()
