"""Click every button in every state (simulated hardware, no window on screen)."""
import os
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", tempfile.gettempdir())

from PyQt6.QtCore import Qt                                      # noqa: E402
from PyQt6.QtTest import QTest                                   # noqa: E402
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

from eps_visibility import config                                # noqa: E402
from eps_visibility.theme import QSS                             # noqa: E402

app = QApplication.instance() or QApplication([])
app.setStyle("Fusion")
app.setStyleSheet(QSS)
from eps_visibility.gui import EpsVisibilityApp                  # noqa: E402


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.02)


class TestButtons(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._data, config.DATA_DIR = config.DATA_DIR, self.tmp
        self.popups = []
        self._warn, self._info = QMessageBox.warning, QMessageBox.information
        self._save = QFileDialog.getSaveFileName
        QMessageBox.warning = lambda *a, **k: self.popups.append(a[2])
        QMessageBox.information = lambda *a, **k: self.popups.append(a[2])
        QFileDialog.getSaveFileName = staticmethod(
            lambda *a, **k: (os.path.join(self.tmp, "manual.csv"), ""))
        self.w = EpsVisibilityApp()
        self.w.resize(1400, 900)
        self.w.show()
        pump(0.2)

    def tearDown(self):
        self.w.close()
        config.DATA_DIR = self._data
        QMessageBox.warning, QMessageBox.information = self._warn, self._info
        QFileDialog.getSaveFileName = self._save

    def click(self, btn, wait=0.15):
        btn.click()
        pump(wait)

    def start_sim(self, nsteps=4):
        w = self.w
        w.sim_cb.setChecked(True)
        w.interval.setValue(100)
        w.navg.setValue(1)
        w.settle.setValue(0)
        w.nsteps.setValue(nsteps)
        self.click(w.counts_btn, 0.4)
        self.click(w.stage_btn, 0.6)

    def wait_scan(self, limit=30):
        t = time.time()
        while self.w.scan_thread is not None and time.time() - t < limit:
            pump(0.1)
        pump(0.3)

    def test_guards_when_nothing_is_ready(self):
        w = self.w
        self.assertFalse(w.step_btn.isEnabled())
        self.assertFalse(w.home_btn.isEnabled())
        self.click(w.scan_btn)
        self.click(w.save_btn)
        self.click(w.refresh_btn)
        self.assertEqual(self.popups, ["Start the counts first.", "No scan data yet."])

    def test_counts_stage_and_manual_moves(self):
        w = self.w
        self.start_sim()
        self.assertEqual(w.counts_btn.text(), "Stop counts")
        self.assertEqual(w.counts_btn.property("role"), "stop")
        self.assertFalse(w.sim_cb.isEnabled())
        self.assertEqual(w.stage_btn.text(), "Disconnect")
        w.man_dir.setCurrentText("Clock")
        w.man_angle.setValue(30)
        self.click(w.step_btn, 0.6)
        self.assertEqual(w.world.angle, 30.0)
        self.click(w.home_btn, 0.6)
        self.assertEqual(w.world.angle, 0.0)
        self.click(w.stage_btn)
        self.assertEqual(w.stage_btn.text(), "Connect")
        self.assertFalse(w.step_btn.isEnabled())
        self.click(w.counts_btn, 0.3)
        self.assertEqual(w.counts_btn.text(), "Start counts")
        self.assertTrue(w.sim_cb.isEnabled())

    def test_scan_locks_buttons_and_esc_stops_it(self):
        w = self.w
        self.start_sim(nsteps=20)
        self.click(w.scan_btn, 0.4)
        self.assertEqual(w.scan_btn.text(), "Stop scan")
        for b in (w.counts_btn, w.stage_btn, w.step_btn, w.home_btn):
            self.assertFalse(b.isEnabled(), b.text())
        QTest.keyClick(w, Qt.Key.Key_Escape)
        self.wait_scan(10)
        self.assertIn("Scan aborted", w.log_box.toPlainText())
        self.assertEqual(w.scan_btn.text(), "Start scan")
        self.assertTrue(w.step_btn.isEnabled())

    def test_full_scan_and_ctrl_s(self):
        w = self.w
        self.start_sim()
        self.click(w.scan_btn)
        self.wait_scan()
        self.assertEqual(len(w.points), 5)
        QTest.keyClick(w, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
        pump(0.3)
        for ext in (".csv", ".png"):
            self.assertTrue(os.path.exists(os.path.join(self.tmp, "manual" + ext)), ext)

    def test_every_button_has_tooltip_and_steady_width(self):
        w = self.w
        buttons = (w.counts_btn, w.refresh_btn, w.stage_btn, w.step_btn, w.home_btn,
                   w.scan_btn, w.save_btn)
        for b in buttons:
            self.assertTrue(b.toolTip(), b.text())
            self.assertGreaterEqual(b.height(), 34, b.text())
        width = w.stage_btn.width()
        self.start_sim()                                   # Connect -> Disconnect
        self.assertEqual(w.stage_btn.width(), width)       # row does not jump
        self.assertEqual(w.step_btn.width(), w.home_btn.width())


if __name__ == "__main__":
    unittest.main()
