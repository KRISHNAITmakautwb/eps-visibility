"""Saving scan results."""
import csv

from .config import APP_TITLE, CHANNEL_LABELS

PARAM_KEYS = ("stage", "offset", "offset_dir", "direction", "nsteps", "step", "settle_s",
              "navg", "interval_ms", "coinc", "hwp", "simulated")


def save_scan_csv(path, points, params, res):
    """CSV with '# key = value' header lines (parameters and visibility), then one row per point."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        if params.get("simulated"):
            fh.write("# *** SIMULATION - NOT REAL DATA (counts and stage were simulated) ***\n")
        fh.write(f"# {APP_TITLE} scan, started {params.get('started')}\n")
        for k in PARAM_KEYS:
            fh.write(f"# {k} = {params.get(k)}\n")
        if res and res["raw"] is not None:
            fh.write(f"# visibility_raw = {res['raw']:.6f}\n")
        if res and res["fit"]:
            fh.write(f"# visibility_fit = {res['fit']['V']:.6f} +- {res['fit']['dV']:.6f}\n")
            fh.write(f"# fit_max_stage_angle_deg = {res['fit']['x_max']:.4f}\n")
        w = csv.writer(fh)
        w.writerow(["index", "stage_angle_deg", "polarization_deg", "reports"]
                   + [f"{c} mean" for c in CHANNEL_LABELS] + [f"{c} std" for c in CHANNEL_LABELS])
        for pt in points:
            pol = pt["angle"] * (2 if params.get("hwp") else 1)
            w.writerow([pt["index"], f"{pt['angle']:.6g}", f"{pol:.6g}", pt["n"]]
                       + [f"{v:.3f}" for v in pt["mean"]] + [f"{v:.3f}" for v in pt["std"]])
