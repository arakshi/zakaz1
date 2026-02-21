"""Lightweight optimization routines."""

from __future__ import annotations

import random

import pandas as pd

from core.metrics import compute_metrics
from core.model import SimulationParams, run_simulation

BOUNDS = {
    "vessel_diameter": (30e-6, 200e-6),
    "vessel_depth": (0.2e-3, 1.5e-3),
    "laser.tp": (0.1e-3, 5e-3),
    "laser.f": (1.0, 50.0),
    "laser.w0": (0.2e-3, 2.0e-3),
}


def _sample_value(low: float, high: float) -> float:
    return low + random.random() * (high - low)


def random_search(
    base_params: dict,
    n_iter: int = 20,
    tmax_limit: float = 345.15,
    progress_cb: callable | None = None,
) -> pd.DataFrame:
    """Minimize UniformityIndex with Tmax constraint via random search."""
    records = []

    for i in range(n_iter):
        trial = dict(base_params)
        laser = dict(trial["laser"])
        for k, (low, high) in BOUNDS.items():
            if k.startswith("laser."):
                laser[k.split(".", 1)[1]] = _sample_value(low, high)
            else:
                trial[k] = _sample_value(low, high)
        if laser["tp"] >= 1.0 / laser["f"]:
            laser["tp"] = 0.7 / laser["f"]
        trial["laser"] = laser

        result = run_simulation(SimulationParams(**trial))
        m = compute_metrics(result)
        feasible = m["Tmax_vessel"] < tmax_limit
        score = m["UniformityIndex"] if feasible else m["UniformityIndex"] + 1.0
        records.append({**trial, **m, "feasible": feasible, "score": score})

        if progress_cb:
            progress_cb((i + 1) / n_iter)

    df = pd.DataFrame(records).sort_values("score", ascending=True)
    return df
