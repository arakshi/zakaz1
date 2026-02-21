"""Генерация отчетов по запускам."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def generate_html_report(run_payload: dict, out_path: str) -> str:
    """Сформировать standalone HTML-отчет по одному прогону."""
    params = json.dumps(run_payload.get("parameters", {}), indent=2, ensure_ascii=False)
    metrics = json.dumps(run_payload.get("metrics", {}), indent=2, ensure_ascii=False)

    html = f"""
    <html>
    <head><meta charset='utf-8'><title>LaserVesselHeatLab — Отчет</title></head>
    <body>
      <h1>LaserVesselHeatLab: отчет по прогону</h1>
      <p><b>ID прогона:</b> {run_payload.get('id')}</p>
      <p><b>Название:</b> {run_payload.get('name')}</p>
      <h2>Метрики</h2>
      <pre>{metrics}</pre>
      <h2>Параметры</h2>
      <pre>{params}</pre>
      <h2>Артефакты</h2>
      <p>Папка: {run_payload.get('run_dir')}</p>
    </body>
    </html>
    """
    Path(out_path).write_text(html, encoding="utf-8")
    return out_path


def export_dataframe_csv(df: pd.DataFrame, out_path: str) -> str:
    """Экспортировать таблицу в CSV."""
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return out_path
