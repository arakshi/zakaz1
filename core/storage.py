"""SQLite persistence layer for simulation runs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    select,
)


class Storage:
    """Persist run metadata and artifacts."""

    def __init__(self, db_path: str = "results/laservesselheatlab.sqlite") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.meta = MetaData()

        self.runs = Table(
            "runs",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("name", String(256), nullable=False),
            Column("created_at", DateTime, default=datetime.utcnow),
            Column("parameters", JSON, nullable=False),
            Column("metrics", JSON, nullable=False),
            Column("uniformity", Float, nullable=False),
            Column("tmax", Float, nullable=False),
            Column("run_dir", String(512), nullable=False),
        )

        self.meta.create_all(self.engine)

    def add_run(self, name: str, parameters: dict, metrics: dict, run_dir: str) -> int:
        """Insert a run record and return ID."""
        stmt = self.runs.insert().values(
            name=name,
            created_at=datetime.utcnow(),
            parameters=parameters,
            metrics=metrics,
            uniformity=float(metrics.get("UniformityIndex", 0.0)),
            tmax=float(metrics.get("Tmax_vessel", 0.0)),
            run_dir=run_dir,
        )
        with self.engine.begin() as conn:
            res = conn.execute(stmt)
            return int(res.inserted_primary_key[0])

    def list_runs(self, limit: int = 200) -> pd.DataFrame:
        """Load recent run list."""
        stmt = select(self.runs).order_by(self.runs.c.created_at.desc()).limit(limit)
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return pd.DataFrame(rows)

    def update_run_dir(self, run_id: int, run_dir: str) -> None:
        """Update run directory after artifact write."""
        stmt = self.runs.update().where(self.runs.c.id == run_id).values(run_dir=run_dir)
        with self.engine.begin() as conn:
            conn.execute(stmt)

    def get_run(self, run_id: int) -> dict | None:
        """Fetch a run by ID."""
        stmt = select(self.runs).where(self.runs.c.id == run_id)
        with self.engine.begin() as conn:
            row = conn.execute(stmt).mappings().first()
        return dict(row) if row else None


def save_run_artifacts(
    base_dir: str,
    run_id: int,
    params: dict,
    metrics: dict,
    series: pd.DataFrame,
    fields: object,
    times: object,
) -> str:
    """Save output files for one run."""
    run_dir = Path(base_dir) / f"run_{run_id:05d}"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "params.json").write_text(json.dumps(params, indent=2), encoding="utf-8")
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    series.to_csv(run_dir / "series.csv", index=False)

    import numpy as np

    np.savez_compressed(run_dir / "fields.npz", fields=fields, times=times)
    return str(run_dir)
