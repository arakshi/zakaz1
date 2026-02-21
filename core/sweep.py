"""Parameter sweep utilities."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd

from core.metrics import compute_metrics
from core.model import SimulationParams, run_simulation


def _expand_case(case: dict) -> dict:
    out = {}
    laser = {}
    bc = {}
    for key, value in case.items():
        if key.startswith("laser."):
            laser[key.split(".", 1)[1]] = value
        elif key.startswith("bc."):
            bc[key.split(".", 1)[1]] = value
        else:
            out[key] = value
    if laser:
        out["laser"] = laser
    if bc:
        out["bc"] = bc
    return out


def _run_single(case: dict) -> dict:
    payload = _expand_case(case)
    params = SimulationParams(**payload)
    result = run_simulation(params)
    metrics = compute_metrics(result)
    row = {**case, **metrics}
    return row


def run_sweep(
    cases_df: pd.DataFrame,
    max_workers: int = 2,
    progress_cb: callable | None = None,
) -> pd.DataFrame:
    """Execute sweep in parallel processes."""
    cases = cases_df.to_dict(orient="records")
    out = []
    total = len(cases)
    done = 0

    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_run_single, c) for c in cases]
        for fut in as_completed(futures):
            out.append(fut.result())
            done += 1
            if progress_cb:
                progress_cb(done / total)

    return pd.DataFrame(out)
