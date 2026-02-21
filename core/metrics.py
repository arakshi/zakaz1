"""Metrics for vessel heating uniformity and thresholds."""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.model import SimulationResult


def compute_metrics(
    result: SimulationResult,
    threshold_k: float = 333.15,
    use_peak_mean_time: bool = True,
) -> dict[str, float | int | None]:
    """Compute requested vessel metrics."""
    vessel_mask = result.vessel_mask
    mean_vessel = np.asarray([f[vessel_mask].mean() for f in result.fields])
    eval_idx = int(np.argmax(mean_vessel)) if use_peak_mean_time else -1
    field = result.fields[eval_idx]
    vessel_t = field[vessel_mask]

    tmax = float(vessel_t.max())
    tmin = float(vessel_t.min())
    tmean = float(vessel_t.mean())
    std = float(vessel_t.std())

    center_i = 0
    center_j = int(np.argmin(np.abs(result.z - result.params.vessel_depth)))
    wall_i = int(np.argmin(np.abs(result.r - result.params.vessel_diameter * 0.5)))
    wall_core_delta = float(field[wall_i, center_j] - field[center_i, center_j])

    above = vessel_t > threshold_k
    hot_frac = float(np.mean(above))

    threshold_hits = np.where(mean_vessel >= threshold_k)[0]
    time_to_threshold = (
        float(result.times[threshold_hits[0]]) if threshold_hits.size else None
    )

    return {
        "eval_time_s": float(result.times[eval_idx]),
        "Tmax_vessel": tmax,
        "Tmin_vessel": tmin,
        "Tmean_vessel": tmean,
        "Std_vessel": std,
        "UniformityIndex": float((tmax - tmin) / max(tmean, 1e-9)),
        "WallCoreDelta": wall_core_delta,
        "HotSpotFraction": hot_frac,
        "TimeToThreshold": time_to_threshold,
    }


def series_dataframe(result: SimulationResult) -> pd.DataFrame:
    """Create a time-series dataframe for export."""
    return pd.DataFrame(
        {
            "time_s": result.times,
            "center_K": result.center_series,
            "wall_K": result.wall_series,
        }
    )
