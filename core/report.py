"""Report generation for simulation runs."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def generate_html_report(run_payload: dict, out_path: str) -> str:
    """Generate a standalone HTML report for one run."""
    params = json.dumps(run_payload.get("parameters", {}), indent=2)
    metrics = json.dumps(run_payload.get("metrics", {}), indent=2)

    html = f"""
    <html>
    <head><title>LaserVesselHeatLab Report</title></head>
    <body>
      <h1>LaserVesselHeatLab Run Report</h1>
      <p><b>Run ID:</b> {run_payload.get('id')}</p>
      <p><b>Name:</b> {run_payload.get('name')}</p>
      <h2>Metrics</h2>
      <pre>{metrics}</pre>
      <h2>Parameters</h2>
      <pre>{params}</pre>
      <h2>Artifacts</h2>
      <p>Directory: {run_payload.get('run_dir')}</p>
    </body>
    </html>
    """
    Path(out_path).write_text(html, encoding="utf-8")
    return out_path


def export_dataframe_csv(df: pd.DataFrame, out_path: str) -> str:
    """Export dataframe to CSV."""
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return out_path
