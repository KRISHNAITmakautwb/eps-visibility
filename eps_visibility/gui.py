"""PyQt6 main window. All hardware and scan work runs in threads; results come back via a queue."""
import os
import queue
import threading
import time

import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QTextEdit, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from . import config
from .analysis import analyse, fit_curve, series
from .config import APP_TITLE, CHANNEL_LABELS, DIRECTIONS, STAGE_IDS
from .hardware import (ShmCounts, SimCounts, SimStage, SimWorld, Stage, UartCounts,
                       detect_fpga_port, guess_stage_port, list_serial_ports, parse_stage_reply)
from .scan import run_scan
from .storage import save_scan_csv
from .theme import C, set_role, status_dot, style_axes

SIM_TEXT = "SIMULATION – NOT REAL DATA"


def spin(lo, hi, val, step=1, dec=None, suffix=""):
    if dec is None:
        w = QSpinBox()
    else:
        w = QDoubleSpinBox()
        w.setDecimals(dec)
    w.setRange(lo, hi)
    w.setSingleStep(step)
    w.setValue(val)
    if suffix:
        w.setSuffix(suffix)
    return w


def hbox(*widgets, stretch=None):
    """Widgets side by side in one form row."""
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    for i, wid in enumerate(widgets):
        row.addWidget(wid, (stretch or {}).get(i, 0))
    w = QWidget()
    w.setLayout(row)
    return w


class EpsVisibilityApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1400, 900)
        self.events = queue.Queue()
        self.world = SimWorld()
        self.source = None
        self.stage = None
        self.scan_thread = None
        self.stage_busy = False    # connecting, or a manual move in progress
        self.abort = threading.Event()
        self.points = []           # dicts: index, angle, n, mean[10], std[10]
        self.scan_params = {}
        self.last_saved = None
        self._build_ui()
        self.refresh_ports()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(100)

    # ---------------- layout
    def _build_ui(self):
        left = QWidget()
        lv = QVBoxLayout(left)
        self.sim_cb = QCheckBox("Simulate hardware (no devices)")
        lv.addWidget(self.sim_cb)
        lv.addWidget(self._build_counts_box())
        lv.addWidget(self._build_live_box())
        lv.addWidget(self._build_stage_box())
        lv.addWidget(self._build_scan_box())
        lv.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(left)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        side = QWidget()                     # settings scroll; the action bar stays put
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(0)
        sv.addWidget(scroll, 1)
        sv.addWidget(self._build_action_bar())
        side.setMinimumWidth(440)

        right = QWidget()
        rv = QVBoxLayout(right)
        self.sim_banner = QLabel(SIM_TEXT + "  —  counts and stage are fake (untick 'Simulate hardware')")
        self.sim_banner.setProperty("role", "sim-banner")
        self.sim_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sim_banner.setVisible(False)
        rv.addWidget(self.sim_banner)
        self.sim_cb.toggled.connect(self._update_sim_marks)
        self.result_lbl = QLabel("Visibility: —")
        self.result_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        rv.addWidget(self.result_lbl)
        self.fig = Figure(figsize=(8, 6), layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.ax_s, self.ax_c = self.fig.subplots(2, 1, sharex=True)
        rv.addWidget(self.canvas, 3)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        rv.addWidget(self.log_box, 1)

        split = QSplitter()
        split.addWidget(side)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        self.setCentralWidget(split)
        self._standardise_buttons()
        self.redraw()
        self._set_buttons()

    def _standardise_buttons(self):
        """One convention for every button: tooltip, fixed size (no jumping), standard shortcuts."""
        from PyQt6.QtGui import QKeySequence, QShortcut

        def fix(btn, width, tip):
            btn.setMinimumWidth(width)
            btn.setMinimumHeight(34)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        fix(self.counts_btn, 200, "Start or stop reading counts from the FPGA (or the simulator)")
        fix(self.refresh_btn, 96, "Search again for serial ports (FPGA and Arduino)")
        fix(self.stage_btn, 120, "Connect to or disconnect from the Arduino rotation stage")
        fix(self.step_btn, 80, "Rotate the selected stage by the angle, in the chosen direction")
        fix(self.home_btn, 80, "Send the selected stage to its home position")
        fix(self.scan_btn, 200, "Start the visibility scan  ·  Esc stops a running scan")
        fix(self.save_btn, 120, "Save the current scan as CSV + PNG  ·  Ctrl+S")
        self.step_btn.setMaximumWidth(80)
        self.home_btn.setMaximumWidth(80)

        QShortcut(QKeySequence.StandardKey.Save, self, activated=self.save_as)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self._stop_scan_if_running)

    def _stop_scan_if_running(self):
        if self._scanning():
            self.toggle_scan()

    def _build_counts_box(self):
        g = QGroupBox("Photon counts (Qutess FPGA)")
        f = QFormLayout(g)
        self.src_cb = QComboBox()
        self.src_cb.addItems(["FPGA UART (direct)", "Shared memory (producer.py)"])
        f.addRow("Source", self.src_cb)
        self.fpga_port = QComboBox()
        self.fpga_port.setEditable(True)
        f.addRow("FPGA port", self.fpga_port)
        self.interval = spin(1, 42949, 500, 100, suffix=" ms")
        f.addRow("Report interval", self.interval)
        self.taps = [spin(0, 31, 0) for _ in range(4)]
        f.addRow("Taps ch1-4", hbox(*self.taps))
        self.shm_pub = QCheckBox("Also publish to shared memory (for old scripts)")
        f.addRow(self.shm_pub)
        self.counts_btn = QPushButton("Start counts")
        self.counts_btn.clicked.connect(self.toggle_counts)
        self.counts_dot = QLabel()
        self.counts_state = QLabel("Stopped")
        self.counts_state.setProperty("role", "muted")
        f.addRow(hbox(self.counts_btn, self.counts_dot, self.counts_state, stretch={0: 1}))
        return g

    def _build_live_box(self):
        g = QGroupBox("Live counts (last report)")
        grid = QGridLayout(g)
        self.count_lbls = []
        for i, name in enumerate(CHANNEL_LABELS):
            grid.addWidget(QLabel(name), i % 5, (i // 5) * 2)
            lbl = QLabel("—")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            lbl.setProperty("role", "count-single" if i < 4 else "count-coinc")
            grid.addWidget(lbl, i % 5, (i // 5) * 2 + 1)
            self.count_lbls.append(lbl)
        self.seq_lbl = QLabel("report #0")
        self.seq_lbl.setProperty("role", "muted")
        grid.addWidget(self.seq_lbl, 5, 0, 1, 4)
        return g

    def _build_stage_box(self):
        g = QGroupBox("Rotation stage (Arduino)")
        f = QFormLayout(g)
        self.stage_port = QComboBox()
        self.stage_port.setEditable(True)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        self.stage_btn = QPushButton("Connect")
        self.stage_btn.clicked.connect(self.toggle_stage)
        self.stage_dot = QLabel()
        f.addRow("Port", hbox(self.stage_port, self.refresh_btn, self.stage_btn, self.stage_dot,
                              stretch={0: 1}))
        self.stage_sel = QComboBox()
        self.stage_sel.addItems(STAGE_IDS)
        f.addRow("Stage", self.stage_sel)
        self.man_dir = QComboBox()
        self.man_dir.addItems(DIRECTIONS)
        self.man_angle = spin(0, 360, 0, 1, dec=3, suffix=" °")
        self.step_btn = QPushButton("Step")
        self.step_btn.clicked.connect(lambda: self.manual_move("Step"))
        self.home_btn = QPushButton("Home")
        self.home_btn.clicked.connect(lambda: self.manual_move("Home"))
        f.addRow("Manual", hbox(self.man_dir, self.man_angle, self.step_btn, self.home_btn))
        self.stage_status = QLabel("Current: N/A    Final: N/A")
        f.addRow(self.stage_status)
        return g

    def _build_scan_box(self):
        g = QGroupBox("Visibility scan")
        f = QFormLayout(g)
        self.offset = spin(0, 360, 0, 1, dec=3, suffix=" °")
        self.offset_dir = QComboBox()
        self.offset_dir.addItems(DIRECTIONS)
        f.addRow("Start offset", hbox(self.offset, self.offset_dir))
        self.scan_dir = QComboBox()
        self.scan_dir.addItems(DIRECTIONS[::-1])          # AntiClock first, as in Visibility.py
        f.addRow("Scan direction", self.scan_dir)
        self.span = spin(0.1, 360, 90, 5, dec=3, suffix=" °")
        f.addRow("Total stage rotation", self.span)
        self.nsteps = spin(1, 1000, 16)
        f.addRow("Number of steps", self.nsteps)
        self.step_lbl = QLabel()
        f.addRow("Step size", self.step_lbl)
        self.span.valueChanged.connect(self._update_step_lbl)
        self.nsteps.valueChanged.connect(self._update_step_lbl)
        self._update_step_lbl()
        self.settle = spin(0, 60, 1.0, 0.5, dec=1, suffix=" s")
        f.addRow("Settle after move", self.settle)
        self.navg = spin(1, 1000, 6)
        f.addRow("Reports averaged / point", self.navg)
        self.coinc_ch = QComboBox()
        self.coinc_ch.addItems(CHANNEL_LABELS[4:])
        f.addRow("Coincidence channel", self.coinc_ch)
        self.hwp = QCheckBox("Half-wave plate (polarization = 2 × stage angle)")
        self.hwp.setChecked(True)
        self.hwp.toggled.connect(self.redraw)
        f.addRow(self.hwp)
        self.home_end = QCheckBox("Home the stage when the scan ends")
        self.home_end.setChecked(True)
        f.addRow(self.home_end)
        self.autosave = QCheckBox("Auto-save CSV + PNG to eps/data/")
        self.autosave.setChecked(True)
        f.addRow(self.autosave)
        return g

    def _build_action_bar(self):
        """Start scan / Save as, pinned under the scrolling settings so they are always visible."""
        self.scan_btn = QPushButton("Start scan")
        self.scan_btn.clicked.connect(self.toggle_scan)
        self.save_btn = QPushButton("Save as…")
        self.save_btn.clicked.connect(self.save_as)
        bar = hbox(self.scan_btn, self.save_btn, stretch={0: 2, 1: 1})
        bar.setObjectName("actionBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.layout().setContentsMargins(10, 8, 10, 8)
        return bar

    def _showing_sim(self):
        """True when what is on screen is fake: sim mode now, or the plotted scan was simulated."""
        if self.points:
            return bool(self.scan_params.get("simulated"))
        return self.sim_cb.isChecked()

    def _update_sim_marks(self, *_):
        sim_now = self.sim_cb.isChecked()
        self.sim_banner.setVisible(sim_now or self._showing_sim())
        self.setWindowTitle(f"{APP_TITLE}  —  {SIM_TEXT}" if sim_now else APP_TITLE)
        self.redraw()

    def _update_step_lbl(self):
        self.step_lbl.setText(f"{self.span.value() / self.nsteps.value():.4g} °  "
                              f"({self.nsteps.value() + 1} points)")

    # ---------------- helpers
    def log(self, msg):
        """Thread-safe: worker threads call this too."""
        self.events.put(("log", f"{time.strftime('%H:%M:%S')}  {msg}"))

    def refresh_ports(self):
        ports = list_serial_ports()
        defaults = {self.fpga_port: detect_fpga_port(), self.stage_port: guess_stage_port()}
        for cb, default in defaults.items():
            cur = cb.currentText().strip()
            cb.clear()
            cb.addItems(ports)
            # keep a still-present user choice; otherwise use the detected port
            choice = cur if cur in ports else (default or cur)
            cb.setCurrentText(choice or "")
        if not ports:
            self.log("No serial ports found (tick 'Simulate hardware' to try the app without devices)")

    def _scanning(self):
        return self.scan_thread is not None and self.scan_thread.is_alive()

    def _set_buttons(self):
        busy = self._scanning()
        conn = self.stage is not None and self.stage.connected
        running = self.source is not None and self.source.alive
        sbusy = self.stage_busy
        self.step_btn.setEnabled(conn and not busy and not sbusy)
        self.home_btn.setEnabled(conn and not busy and not sbusy)
        self.stage_btn.setEnabled(not busy and not sbusy)
        self.stage_btn.setText("Working…" if sbusy else ("Disconnect" if conn else "Connect"))
        self.counts_btn.setText("Stop counts" if running else "Start counts")
        self.counts_btn.setEnabled(not busy)
        self.sim_cb.setEnabled(not running and not conn)
        self.scan_btn.setText("Stop scan" if busy else "Start scan")
        self.scan_btn.setEnabled(busy or not sbusy)
        # colours: green = start, red = stop; status lights next to counts and stage
        set_role(self.counts_btn, "stop" if running else "go")
        set_role(self.scan_btn, "stop" if busy else "go")
        failed = self.source is not None and self.source.error
        self.counts_dot.setStyleSheet(status_dot(C["ok"] if running else
                                                 C["bad"] if failed else C["idle"]))
        self.counts_state.setText("Running" if running else "Error - see log" if failed else "Stopped")
        self.stage_dot.setStyleSheet(status_dot(C["ok"] if conn else C["idle"]))

    # ---------------- counts
    def toggle_counts(self):
        if self.source is not None and self.source.alive:
            self.source.stop()
            self.log("Counts stopped")
            self.source = None
            self._set_buttons()
            return
        os.makedirs(config.DATA_DIR, exist_ok=True)
        if self.sim_cb.isChecked():
            self.source = SimCounts(self.log, self.world, self.interval.value())
        elif self.src_cb.currentIndex() == 1:
            self.source = ShmCounts(self.log)
        else:
            port = self.fpga_port.currentText().strip()
            if not port:
                QMessageBox.warning(self, APP_TITLE, "Choose the FPGA serial port first.")
                return
            if isinstance(self.stage, Stage) and self.stage.connected and self.stage.ser is not None \
                    and self.stage.ser.port == port:
                QMessageBox.warning(self, APP_TITLE, "That port is the rotation stage; pick the FPGA port.")
                return
            raw = os.path.join(config.DATA_DIR, f"raw_counts_{time.strftime('%Y%m%d_%H%M%S')}.csv")
            self.source = UartCounts(self.log, port, self.interval.value(),
                                     [t.value() for t in self.taps], raw, self.shm_pub.isChecked())
        self.source.start()
        self._set_buttons()

    # ---------------- stage
    def _stage_reply(self, msg):
        self.events.put(("stage", msg))

    def toggle_stage(self):
        if self.stage is not None and self.stage.connected:
            self.stage.close()
            self.log("Stage disconnected")
            self._set_buttons()
            return
        sim = self.sim_cb.isChecked()
        port = self.stage_port.currentText().strip()
        if not sim and not port:
            QMessageBox.warning(self, APP_TITLE, "Choose the rotation-stage serial port first.")
            return
        if not sim and isinstance(self.source, UartCounts) and self.source.alive \
                and port == self.source.port:
            QMessageBox.warning(self, APP_TITLE, "That port is the FPGA port; pick the Arduino port.")
            return
        self.stage = SimStage(self.log, self._stage_reply, self.world) if sim \
            else Stage(self.log, self._stage_reply)
        self.stage_busy = True
        self._set_buttons()

        def work():
            try:
                self.stage.open(port)
                self.log(f"Stage connected on {port or 'SIM'}")
            except Exception as exc:
                self.log(f"Stage connection error: {exc}")
                if self.stage is not None:
                    self.stage.close()
                self.stage = None
            self.events.put(("stage_idle", None))
        threading.Thread(target=work, daemon=True).start()

    def manual_move(self, mode):
        stage, d, a = self.stage_sel.currentText(), self.man_dir.currentText(), self.man_angle.value()
        if mode == "Home":
            a = 0
        self.stage_busy = True
        self._set_buttons()

        def work():
            try:
                self.stage.move(a, d, mode, stage)
            except Exception as exc:
                self.log(f"Stage error: {exc}")
            self.events.put(("stage_idle", None))
        threading.Thread(target=work, daemon=True).start()

    # ---------------- scan
    def toggle_scan(self):
        if self._scanning():
            self.abort.set()
            self.log("Stopping scan…")
            return
        if self.source is None or not self.source.alive:
            QMessageBox.warning(self, APP_TITLE, "Start the counts first.")
            return
        if self.stage is None or not self.stage.connected:
            QMessageBox.warning(self, APP_TITLE, "Connect the rotation stage first.")
            return
        p = dict(stage=self.stage_sel.currentText(), offset=self.offset.value(),
                 offset_dir=self.offset_dir.currentText(), direction=self.scan_dir.currentText(),
                 nsteps=self.nsteps.value(), step=self.span.value() / self.nsteps.value(),
                 settle_s=self.settle.value(), navg=self.navg.value(),
                 # the interval the counts were actually started with (the box may have changed)
                 interval_ms=getattr(self.source, "interval_ms", self.interval.value()), coinc=self.coinc_ch.currentText(),
                 hwp=self.hwp.isChecked(), home_end=self.home_end.isChecked(),
                 simulated=self.sim_cb.isChecked(),
                 started=time.strftime("%Y-%m-%d %H:%M:%S"))
        self.scan_params = p
        self.points = []
        self.last_saved = None
        self.abort.clear()
        self._update_sim_marks()      # banner follows the new scan (redraws too)
        self.scan_thread = threading.Thread(
            target=run_scan, daemon=True,
            args=(p, self.source, self.stage, self.abort,
                  lambda kind, val: self.events.put((kind, val)), self.log))
        self.scan_thread.start()
        self._set_buttons()

    # ---------------- analysis / plotting
    def analysis(self):
        name = self.scan_params.get("coinc") or self.coinc_ch.currentText()
        return analyse(self.points, CHANNEL_LABELS.index(name), self.hwp.isChecked())

    def redraw(self):
        self.ax_s.clear()
        self.ax_c.clear()
        for ax in (self.ax_s, self.ax_c):
            for child in list(ax.child_axes):
                child.remove()
        self.ax_s.set_ylabel("Singles / report")
        self.ax_c.set_ylabel("Coincidences / report")
        self.ax_c.set_xlabel("Stage angle (°)")
        style_axes(self.fig, (self.ax_s, self.ax_c))
        for t in list(self.fig.texts):
            t.remove()
        if self._showing_sim():   # stamped on the figure itself, so it is also in every saved PNG
            self.fig.text(0.5, 0.5, SIM_TEXT, ha="center", va="center", rotation=22,
                          fontsize=34, fontweight="bold", color=C["bad"], alpha=0.16, zorder=0)
        if self.hwp.isChecked():
            sec = self.ax_s.secondary_xaxis("top", functions=(lambda x: 2 * x, lambda x: x / 2))
            sec.set_xlabel("Polarization angle (°)", color=C["muted"])
            sec.tick_params(colors=C["muted"])
            sec.spines["top"].set_color(C["border"])
        s = series(self.points)
        res = self.analysis()
        if s is not None:
            ang, mean, err = s
            for k, col in ((0, C["accent"]), (1, C["accent2"])):
                self.ax_s.errorbar(ang, mean[:, k], err[:, k], fmt="o-", ms=4, color=col,
                                   label=CHANNEL_LABELS[k], capsize=2)
            self.ax_s.legend(loc="best", fontsize=8, frameon=False)
            ci = res["ci"]
            if res["fit"]:
                xs = np.linspace(ang.min(), ang.max(), 400)
                self.ax_c.plot(xs, fit_curve(res["fit"], xs), "-", color=C["fit"], lw=1.4,
                               label="cos² fit", zorder=1)
            self.ax_c.errorbar(ang, mean[:, ci], err[:, ci], fmt="o", ms=6, color=C["coinc"],
                               mec="white", mew=0.8, label=CHANNEL_LABELS[ci], capsize=2, zorder=2)
            self.ax_c.legend(loc="best", fontsize=8, frameon=False)
        self.canvas.draw_idle()
        self._show_result(res)

    def _show_result(self, res):
        if not res or res["raw"] is None:
            set_role(self.result_lbl, "result-empty")
            self.result_lbl.setText("Visibility: —")
            return
        set_role(self.result_lbl, "result")
        txt = (f"Visibility (max−min)/(max+min) = {res['raw']:.4f}   "
               f"[max {res['ymax']:,.0f} @ {res['at_max']:g}°, min {res['ymin']:,.0f} @ {res['at_min']:g}°]")
        if res["fit"]:
            f = res["fit"]
            txt += f"\nFitted visibility = {f['V']:.4f} ± {f['dV']:.4f}   (fit max at stage {f['x_max']:.2f}°)"
        if self._showing_sim():
            txt = "[SIMULATED]  " + txt
            set_role(self.result_lbl, "result-empty")   # never the green "real result" box
        self.result_lbl.setText(txt)

    # ---------------- saving
    def _save(self, csv_path):
        self.redraw()     # make sure the figure has every point before it is written
        # record the HWP setting the visibility was computed with (it can be toggled after a scan)
        params = dict(self.scan_params, hwp=self.hwp.isChecked())
        save_scan_csv(csv_path, self.points, params, self.analysis())
        self.fig.savefig(os.path.splitext(csv_path)[0] + ".png", dpi=150)

    def save_as(self):
        if not self.points:
            QMessageBox.information(self, APP_TITLE, "No scan data yet.")
            return
        os.makedirs(config.DATA_DIR, exist_ok=True)
        default = "visibility_SIM.csv" if self._showing_sim() else "visibility.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Save scan", self.last_saved or
                                              os.path.join(config.DATA_DIR, default),
                                              "CSV (*.csv)")
        if path:
            self._save(path)
            self.log(f"Saved {path} (+ .png)")

    def _autosave(self):
        if not (self.autosave.isChecked() and self.points):
            return
        os.makedirs(config.DATA_DIR, exist_ok=True)
        tag = "_SIM" if self._showing_sim() else ""
        path = os.path.join(config.DATA_DIR, f"visibility_{time.strftime('%Y%m%d_%H%M%S')}{tag}.csv")
        self._save(path)
        self.last_saved = path
        self.log(f"Saved {path} and .png")

    # ---------------- event pump (GUI thread)
    def _tick(self):
        redraw = False
        while True:
            try:
                kind, val = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self.log_box.append(val)
            elif kind == "stage":
                self.log_box.append(f"{time.strftime('%H:%M:%S')}  Stage -> {val}")
                parts = parse_stage_reply(val)
                if "CUR" in parts or "FINAL" in parts:
                    self.stage_status.setText(f"Current: {parts.get('CUR', '?')}    "
                                              f"Final: {parts.get('FINAL', '?')}")
            elif kind == "point":
                self.points.append(val)
                redraw = True
            elif kind == "scan_done":
                self.log_box.append(f"{time.strftime('%H:%M:%S')}  Scan {val}: "
                                    f"{len(self.points)} point(s)")
                redraw = True
                self.scan_thread = None
                self.events.put(("autosave", None))
            elif kind == "autosave":
                self._autosave()
            elif kind == "stage_idle":
                self.stage_busy = False
            self._set_buttons()
        if redraw:
            self.redraw()
        src = self.source
        if src is not None:
            if src.counts is not None:
                for lbl, v in zip(self.count_lbls, src.counts):
                    lbl.setText(f"{v:,}")
                self.seq_lbl.setText(f"report #{src.seq}")
            if not src.alive and self.counts_btn.text() == "Stop counts":
                self._set_buttons()

    def closeEvent(self, ev):
        self.abort.set()
        if self.scan_thread is not None:
            self.scan_thread.join(3)
        if self.source is not None:
            self.source.stop()
        if self.stage is not None:
            self.stage.close()
        ev.accept()
