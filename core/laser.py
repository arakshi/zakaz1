"""Laser source models for LaserVesselHeatLab."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field, model_validator


class LaserModeParams(BaseModel):
    """Laser source parameters in SI units."""

    mode: str = Field(default="578", description="578 or 578_511")
    a578: float = 5e8
    mu578: float = 1500.0
    a511: float = 4.5e8
    mu511: float = 2200.0
    p578: float = 0.7
    p511: float = 0.3
    w0: float = 6e-4
    tp: float = 1.5e-3
    f: float = 10.0

    @model_validator(mode="after")
    def validate_mode(self) -> LaserModeParams:
        if self.tp >= 1.0 / self.f:
            raise ValueError("Pulse duration tp must be less than period 1/f.")
        if self.mode not in {"578", "578_511"}:
            raise ValueError("mode must be '578' or '578_511'.")
        if self.mode == "578_511" and not np.isclose(self.p578 + self.p511, 1.0, atol=1e-6):
            raise ValueError("For mode 578_511, p578 + p511 must be 1.")
        return self


def pulse_train(t: float | np.ndarray, tp: float, f: float) -> np.ndarray:
    """Return pulse train values for time(s) t."""
    period = 1.0 / f
    tmod = np.mod(t, period)
    return (tmod < tp).astype(float)


def gaussian_beam_profile(r: np.ndarray, w0: float) -> np.ndarray:
    """Radial Gaussian beam profile."""
    return np.exp(-2.0 * (r**2) / (w0**2))


def depth_profile(z: np.ndarray, mu_eff: float) -> np.ndarray:
    """Exponential attenuation with depth."""
    return np.exp(-mu_eff * z)


def compute_source_grid(
    r_grid: np.ndarray,
    z_grid: np.ndarray,
    t: float,
    params: LaserModeParams,
) -> np.ndarray:
    """Compute volumetric heat source Q_laser(r,z,t) [W/m^3]."""
    gate = pulse_train(np.asarray([t]), params.tp, params.f)[0]
    if gate <= 0.0:
        return np.zeros((r_grid.size, z_grid.size), dtype=float)

    rr = gaussian_beam_profile(r_grid[:, None], params.w0)
    q578 = params.a578 * rr * depth_profile(z_grid[None, :], params.mu578)

    if params.mode == "578":
        return q578

    q511 = params.a511 * rr * depth_profile(z_grid[None, :], params.mu511)
    return params.p578 * q578 + params.p511 * q511
