from __future__ import annotations

import numpy as np

from core.metrics import compute_metrics
from core.model import SimulationParams, run_simulation


def test_model_runs_and_shapes() -> None:
    p = SimulationParams(nr=24, nz=28, dt=5e-4, n_pulses=2)
    res = run_simulation(p)
    assert res.fields.ndim == 3
    assert res.fields.shape[1:] == (p.nr, p.nz)
    assert len(res.times) == len(res.center_series)


def test_temperatures_finite() -> None:
    p = SimulationParams(nr=22, nz=24, dt=6e-4, n_pulses=1)
    res = run_simulation(p)
    assert np.isfinite(res.fields).all()


def test_metrics_present() -> None:
    p = SimulationParams(nr=20, nz=22, dt=6e-4, n_pulses=1)
    res = run_simulation(p)
    m = compute_metrics(res)
    for key in ["Tmax_vessel", "Tmin_vessel", "Tmean_vessel", "UniformityIndex", "HotSpotFraction"]:
        assert key in m
