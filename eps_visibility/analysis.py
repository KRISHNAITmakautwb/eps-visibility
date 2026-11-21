"""Visibility calculation: raw (max-min)/(max+min) and a weighted cos^2 fit."""
import math

import numpy as np


def fit_visibility(x_deg, y, sigma, period_deg):
    """Weighted fit y = a + c cos(2 pi x / P) + s sin(2 pi x / P).

    Returns dict(V, dV, a, c, s, amp, x_max, period) or None when it cannot be fitted.
    """
    x = np.asarray(x_deg, float)
    y = np.asarray(y, float)
    if len(x) < 4:
        return None
    w = 2 * np.pi * x / period_deg
    A = np.column_stack([np.ones_like(x), np.cos(w), np.sin(w)])
    sig = np.where(np.asarray(sigma, float) > 0, sigma, 1.0)
    Aw, yw = A / sig[:, None], y / sig
    try:
        cov = np.linalg.inv(Aw.T @ Aw)
    except np.linalg.LinAlgError:
        return None
    a, c, s = cov @ Aw.T @ yw
    r = math.hypot(c, s)
    if a <= 0 or r == 0:
        return None
    g = np.array([-r / a ** 2, c / (r * a), s / (r * a)])
    dV = float(math.sqrt(max(g @ cov @ g, 0.0)))
    x_max = (math.degrees(math.atan2(s, c)) * period_deg / 360.0) % period_deg
    return dict(V=r / a, dV=dV, a=a, c=c, s=s, amp=r, x_max=x_max, period=period_deg)


def fit_curve(fit, xs):
    wv = 2 * np.pi * np.asarray(xs, float) / fit["period"]
    return fit["a"] + fit["c"] * np.cos(wv) + fit["s"] * np.sin(wv)


def raw_visibility(y):
    y = np.asarray(y, float)
    if len(y) < 2 or (y.max() + y.min()) <= 0:
        return None
    return (y.max() - y.min()) / (y.max() + y.min())


def series(points):
    """Scan points -> (angles, mean[N,10], Poisson error of the mean[N,10]), or None."""
    if not points:
        return None
    ang = np.array([pt["angle"] for pt in points])
    mean = np.array([pt["mean"] for pt in points])
    n = np.array([pt["n"] for pt in points])
    err = np.sqrt(np.maximum(mean, 1.0) / n[:, None])
    return ang, mean, err


def analyse(points, coinc_index, hwp):
    """Visibility of one coincidence channel. cos^2 period: 90° stage angle with a HWP, else 180°."""
    s = series(points)
    if s is None:
        return None
    ang, mean, err = s
    period = 90.0 if hwp else 180.0
    y = mean[:, coinc_index]
    return dict(ci=coinc_index, raw=raw_visibility(y),
                fit=fit_visibility(ang, y, err[:, coinc_index], period),
                ymax=float(y.max()), ymin=float(y.min()),
                at_max=float(ang[y.argmax()]), at_min=float(ang[y.argmin()]))
