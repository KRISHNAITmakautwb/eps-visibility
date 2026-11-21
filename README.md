# EPS Visibility

A desktop app for measuring the polarization visibility of an entangled photon source.
It reads live singles and coincidence counts from a Qutess FPGA time tagger and steps an
Arduino-driven rotation stage. It plots the counts against angle and reports the visibility.

![layout](https://img.shields.io/badge/python-3.9%2B-blue) ![gui](https://img.shields.io/badge/GUI-PyQt6-green)

## Quick start

```bash
pip install -r requirements.txt
python -m eps_visibility --sim     # try it with simulated hardware
python -m eps_visibility           # real hardware
```

On Linux, `./run_visibility.sh [--sim]` also works. On Windows, use `run_visibility.bat`.

## Using it

1. **Photon counts.** Pick the FPGA port (a Digilent FT2232H is detected automatically), the
   report interval and the taps, then press **Start counts**. You can instead choose
   *Shared memory* to read counts that another process writes to `qutess_counts`.
2. **Rotation stage.** Pick the Arduino port and press **Connect**. The **Step** and **Home**
   buttons give manual control.
3. **Visibility scan.** Set the offset, direction, total rotation (default 90°) and number of
   steps (default 16), then press **Start scan**.

At each point the app moves the stage, waits for the Arduino's reply and a settle time, then
throws away the report that was in progress (it may include motion) and averages *N* reports.
Visibility is reported two ways:

- raw `(max − min) / (max + min)`
- a weighted cos² fit with an uncertainty. The fit period is 90° of stage angle with a
  half-wave plate and 180° without one.

Results are saved to `data/visibility_<time>.csv` and `.png`. The CSV header holds the scan
parameters and results.

## Hardware protocols

| Device | Link | Format |
|---|---|---|
| Rotation stage (Arduino) | 9600 baud | `<angle>A<Clock\|AntiClock>B<Step\|Home>D<M1..M4>\n`, one reply line per move (e.g. `CUR:12;FINAL:90`) |
| Qutess FPGA | 2 Mbaud UART | handled by `Qutess_1.py` and `source.py` |

**Note:** `Qutess_1.py` and `source.py` are the lab's FPGA driver and are **not included**.
Put them in the folder above this repository to use the direct FPGA mode. Simulation mode and
shared-memory mode work without them.

## Layout

```
eps_visibility/
  config.py      constants and paths
  scan.py        the step-scan loop (run_scan)
  analysis.py    raw and fitted visibility
  storage.py     CSV output
  gui.py         PyQt6 window
  hardware/      FPGA count sources, Arduino stage, simulators, port detection
tests/           unit tests and an end-to-end simulated scan
```

Run the tests with `python -m unittest discover -s tests -t .`
