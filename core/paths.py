"""Утилиты путей проекта для устойчивого запуска из разных рабочих директорий."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"
DATA_DIR = PROJECT_ROOT / "data"
PARAMS_DIR = PROJECT_ROOT / "params"
RESULTS_DIR = PROJECT_ROOT / "results"
RUNS_DIR = RESULTS_DIR / "runs"
REPORTS_DIR = RESULTS_DIR / "reports"


def data_file(name: str) -> Path:
    """Получить абсолютный путь к файлу из `data/`."""
    return DATA_DIR / name


def params_file(name: str) -> Path:
    """Получить абсолютный путь к файлу из `params/`."""
    return PARAMS_DIR / name
