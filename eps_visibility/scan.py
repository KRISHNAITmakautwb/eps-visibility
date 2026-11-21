"""The visibility step scan (the main work loop). Runs in a worker thread."""
import numpy as np

from .config import CHANNEL_LABELS


def run_scan(p, src, stage, abort, emit, log):
    """Step the stage, average counts at each angle.

    p      : scan parameters (stage, offset, offset_dir, direction, nsteps, step, settle_s,
             navg, interval_ms, home_end)
    src    : running CountsSource
    stage  : connected Stage
    abort  : threading.Event; set it to stop the scan
    emit   : emit(kind, value) -> ("point", dict) per point, then ("scan_done", status)
    log    : log(str)
    """
    report_s = p["interval_ms"] / 1000.0
    timeout = report_s * 3 + 5
    status = "complete"
    try:
        log(f"Scan: {p['nsteps']} steps of {p['step']:g}° {p['direction']} on {p['stage']}, "
            f"{p['navg']} report(s) per point")
        if p["offset"]:
            stage.move(p["offset"], p["offset_dir"], "Step", p["stage"], abort=abort)
        for i in range(p["nsteps"] + 1):
            if abort.is_set():
                raise InterruptedError
            if i > 0:
                stage.move(p["step"], p["direction"], "Step", p["stage"], abort=abort)
            if abort.wait(p["settle_s"]):
                raise InterruptedError
            # The report in progress may include motion time: wait for it, then discard it.
            seq, _ = src.wait_after(src.seq, timeout, abort)
            samples = []
            while len(samples) < p["navg"]:
                seq, counts = src.wait_after(seq, timeout, abort)
                samples.append(counts)
            arr = np.array(samples, float)
            point = dict(index=i, angle=i * p["step"], n=len(samples),
                         mean=arr.mean(0), std=arr.std(0, ddof=1) if len(samples) > 1
                         else np.zeros(10))
            emit("point", point)
            log(f"Point {i}/{p['nsteps']}: angle {point['angle']:g}°  "
                + "  ".join(f"{CHANNEL_LABELS[k]}={point['mean'][k]:,.0f}" for k in (0, 1, 4)))
    except InterruptedError:
        status = "aborted"
    except Exception as exc:
        status = f"failed ({type(exc).__name__}: {exc})"
    finally:
        if p["home_end"] and stage.connected:
            try:
                stage.move(0, p["direction"], "Home", p["stage"])
            except Exception as exc:
                log(f"Homing failed: {exc}")
        emit("scan_done", status)
    return status
