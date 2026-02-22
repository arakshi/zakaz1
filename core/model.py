"""Axisymmetric bioheat PDE solver using implicit Euler and sparse matrices."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from pydantic import BaseModel, Field, model_validator
from scipy.sparse import csc_matrix, lil_matrix
from scipy.sparse.linalg import factorized

from core.laser import LaserModeParams, compute_source_grid


class MaterialProps(BaseModel):
    """Material properties for bioheat equation."""

    rho: float
    cp: float
    k: float
    w: float = 0.0


class BoundaryConfig(BaseModel):
    """Boundary condition setup."""

    outer_r: str = "insulated"  # insulated|convective
    outer_h: float = 12.0
    top_h: float = 22.0
    tamb: float = 293.15
    zmax: str = "dirichlet"  # dirichlet|insulated


class SimulationParams(BaseModel):
    """Main simulation setup in SI units."""

    r_max: float = 4e-3
    z_max: float = 3e-3
    vessel_diameter: float = 80e-6
    vessel_depth: float = 7e-4
    nr: int = 72
    nz: int = 84
    dt: float = 2e-4
    n_pulses: int = 6
    t0: float = 310.15
    t_blood: float = 310.15
    perfusion_on: bool = True
    store_every: int = 2

    tissue: MaterialProps = Field(
        default_factory=lambda: MaterialProps(rho=1050.0, cp=3600.0, k=0.45, w=0.0015)
    )
    blood: MaterialProps = Field(
        default_factory=lambda: MaterialProps(rho=1060.0, cp=3770.0, k=0.52, w=0.0)
    )
    bc: BoundaryConfig = Field(default_factory=BoundaryConfig)
    laser: LaserModeParams = Field(default_factory=LaserModeParams)

    @model_validator(mode="after")
    def validate_geometry(self) -> SimulationParams:
        if self.vessel_diameter <= 0 or self.vessel_depth <= 0:
            raise ValueError("Vessel diameter and depth must be positive.")
        if self.vessel_depth + 0.5 * self.vessel_diameter >= self.z_max:
            raise ValueError("Vessel exceeds z_max boundary.")
        if 0.5 * self.vessel_diameter >= self.r_max:
            raise ValueError("Vessel radius exceeds r_max.")
        if self.nr < 12 or self.nz < 12:
            raise ValueError("Grid resolution too low.")
        return self


@dataclass
class SimulationResult:
    """Container for simulation outputs."""

    params: SimulationParams
    r: np.ndarray
    z: np.ndarray
    times: np.ndarray
    fields: np.ndarray
    center_series: np.ndarray
    wall_series: np.ndarray
    vessel_mask: np.ndarray


def vessel_mask(r: np.ndarray, z: np.ndarray, diameter: float, depth: float) -> np.ndarray:
    """Generate vessel mask in axisymmetric r-z grid."""
    rad = diameter * 0.5
    rr, zz = np.meshgrid(r, z, indexing="ij")
    mask = (rr**2 + (zz - depth) ** 2) <= rad**2

    # На грубых сетках сосуд может не зацепить ни одну ячейку.
    # В таком случае принудительно отмечаем ближайший узел к центру сосуда,
    # чтобы метрики и расчет не падали на пустых массивах.
    if not np.any(mask):
        i0 = int(np.argmin(np.abs(r - 0.0)))
        j0 = int(np.argmin(np.abs(z - depth)))
        mask[i0, j0] = True

    return mask


def _harmonic(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        return 0.0
    return 2.0 * a * b / (a + b)


@lru_cache(maxsize=16)
def _cached_factorized(
    key: tuple,
    matrix_data: bytes,
    indices: bytes,
    indptr: bytes,
    shape: tuple,
) -> object:
    """Create and cache factorization for implicit matrix."""
    a = csc_matrix(
        (
            np.frombuffer(matrix_data, dtype=np.float64),
            np.frombuffer(indices, dtype=np.int32),
            np.frombuffer(indptr, dtype=np.int32),
        ),
        shape=shape,
    )
    return factorized(a)


def _build_system_matrix(
    params: SimulationParams,
    rho_cp: np.ndarray,
    k_map: np.ndarray,
    w_map: np.ndarray,
) -> csc_matrix:
    nr, nz = params.nr, params.nz
    dr = params.r_max / (nr - 1)
    dz = params.z_max / (nz - 1)
    n = nr * nz
    mat = lil_matrix((n, n), dtype=float)

    def idx(i: int, j: int) -> int:
        return i * nz + j

    r_vec = np.linspace(0.0, params.r_max, nr)

    for i in range(nr):
        r_i = r_vec[i]
        for j in range(nz):
            p = idx(i, j)

            if j == nz - 1 and params.bc.zmax == "dirichlet":
                mat[p, p] = 1.0
                continue

            rho_cp_ij = rho_cp[i, j]
            perf = w_map[i, j] if params.perfusion_on else 0.0
            diag = rho_cp_ij / params.dt + perf * params.blood.rho * params.blood.cp
            rhs_neighbors = []

            if i == 0:
                k_face = _harmonic(k_map[i, j], k_map[i + 1, j])
                coeff = 2.0 * k_face / (dr * dr)
                diag += coeff
                rhs_neighbors.append((idx(i + 1, j), coeff))
            elif i == nr - 1:
                if params.bc.outer_r == "insulated":
                    k_face = _harmonic(k_map[i, j], k_map[i - 1, j])
                    coeff = k_face / (dr * dr)
                    diag += coeff
                    rhs_neighbors.append((idx(i - 1, j), coeff))
                else:
                    k_face = _harmonic(k_map[i, j], k_map[i - 1, j])
                    coeff = k_face / (dr * dr)
                    hterm = params.bc.outer_h / dr
                    diag += coeff + hterm
                    rhs_neighbors.append((idx(i - 1, j), coeff))
            else:
                r_ip = r_i + 0.5 * dr
                r_im = max(r_i - 0.5 * dr, 1e-12)
                k_ip = _harmonic(k_map[i, j], k_map[i + 1, j])
                k_im = _harmonic(k_map[i, j], k_map[i - 1, j])
                coeff_p = (r_ip * k_ip) / (r_i * dr * dr + 1e-12)
                coeff_m = (r_im * k_im) / (r_i * dr * dr + 1e-12)
                diag += coeff_p + coeff_m
                rhs_neighbors.extend([(idx(i + 1, j), coeff_p), (idx(i - 1, j), coeff_m)])

            if j == 0:
                k_face = _harmonic(k_map[i, j], k_map[i, j + 1])
                coeff = k_face / (dz * dz)
                hterm = params.bc.top_h / dz
                diag += coeff + hterm
                rhs_neighbors.append((idx(i, j + 1), coeff))
            elif j == nz - 1:
                k_face = _harmonic(k_map[i, j], k_map[i, j - 1])
                coeff = k_face / (dz * dz)
                diag += coeff
                rhs_neighbors.append((idx(i, j - 1), coeff))
            else:
                k_jp = _harmonic(k_map[i, j], k_map[i, j + 1])
                k_jm = _harmonic(k_map[i, j], k_map[i, j - 1])
                coeff_p = k_jp / (dz * dz)
                coeff_m = k_jm / (dz * dz)
                diag += coeff_p + coeff_m
                rhs_neighbors.extend([(idx(i, j + 1), coeff_p), (idx(i, j - 1), coeff_m)])

            mat[p, p] = diag
            for q, c in rhs_neighbors:
                mat[p, q] = -c

    return mat.tocsc()


def run_simulation(
    params: SimulationParams,
    progress_callback: callable | None = None,
    stop_flag: callable | None = None,
) -> SimulationResult:
    """Run full transient simulation with implicit Euler."""
    r = np.linspace(0.0, params.r_max, params.nr)
    z = np.linspace(0.0, params.z_max, params.nz)
    dr = params.r_max / (params.nr - 1)
    dz = params.z_max / (params.nz - 1)

    mask = vessel_mask(r, z, params.vessel_diameter, params.vessel_depth)
    rho_map = np.where(mask, params.blood.rho, params.tissue.rho)
    cp_map = np.where(mask, params.blood.cp, params.tissue.cp)
    k_map = np.where(mask, params.blood.k, params.tissue.k)
    w_map = np.where(mask, params.blood.w, params.tissue.w)
    rho_cp = rho_map * cp_map

    period = 1.0 / params.laser.f
    t_end = params.n_pulses * period
    n_steps = int(np.ceil(t_end / params.dt))

    a = _build_system_matrix(params, rho_cp, k_map, w_map)
    solve = _cached_factorized(
        (params.nr, params.nz, params.dt, params.bc.outer_r, params.bc.zmax, params.perfusion_on),
        a.data.tobytes(),
        a.indices.astype(np.int32).tobytes(),
        a.indptr.astype(np.int32).tobytes(),
        a.shape,
    )

    t = params.t0 * np.ones((params.nr, params.nz), dtype=float)
    center_i, center_j = 0, int(np.argmin(np.abs(z - params.vessel_depth)))
    wall_i, wall_j = int(np.argmin(np.abs(r - params.vessel_diameter * 0.5))), center_j

    stored_fields = []
    times = []
    center_series = []
    wall_series = []

    for step in range(n_steps + 1):
        t_now = step * params.dt

        if step % params.store_every == 0 or step == n_steps:
            stored_fields.append(t.copy())
            times.append(t_now)
            center_series.append(float(t[center_i, center_j]))
            wall_series.append(float(t[wall_i, wall_j]))

        if step == n_steps:
            break
        if stop_flag and stop_flag():
            break

        q = compute_source_grid(r, z, t_now, params.laser)
        rhs = (rho_cp / params.dt) * t + q

        if params.perfusion_on:
            rhs += w_map * params.blood.rho * params.blood.cp * params.t_blood

        if params.bc.outer_r == "convective":
            rhs[-1, :] += params.bc.outer_h / dr * params.bc.tamb
        rhs[:, 0] += params.bc.top_h / dz * params.bc.tamb
        if params.bc.zmax == "dirichlet":
            rhs[:, -1] = params.t0

        t_flat = solve(rhs.reshape(-1))
        t = t_flat.reshape(params.nr, params.nz)

        if progress_callback:
            progress_callback((step + 1) / n_steps)

    return SimulationResult(
        params=params,
        r=r,
        z=z,
        times=np.asarray(times),
        fields=np.asarray(stored_fields),
        center_series=np.asarray(center_series),
        wall_series=np.asarray(wall_series),
        vessel_mask=mask,
    )
