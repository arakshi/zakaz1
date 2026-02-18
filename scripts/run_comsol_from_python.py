#!/usr/bin/env python3
"""
Beginner-friendly launcher for COMSOL Java API sweeps.

What it does:
1) Ensures output folders exist.
2) Compiles Java files via COMSOL.
3) Runs sweep entrypoint src/run_sweeps.java in batch mode.

Usage examples:
  python scripts/run_comsol_from_python.py
  python scripts/run_comsol_from_python.py --comsol "C:/Program Files/COMSOL/COMSOL62/Multiphysics/bin/win64/comsol.exe"
  python scripts/run_comsol_from_python.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


JAVA_FILES = [
    "src/build_model_3d.java",
    "src/build_model_2d_axi.java",
    "src/postprocess.java",
    "src/run_sweeps.java",
]


def is_windows() -> bool:
    return platform.system().lower().startswith("win")


def candidate_comsol_paths() -> List[Path]:
    candidates: List[Path] = []

    which = shutil.which("comsol")
    if which:
        candidates.append(Path(which))

    if is_windows():
        base = Path("C:/Program Files/COMSOL")
        if base.exists():
            for p in sorted(base.glob("COMSOL*/Multiphysics/bin/win64/comsol.exe")):
                candidates.append(p)
    else:
        for p in [Path("/usr/local/bin/comsol"), Path("/opt/comsol/bin/comsol")]:
            if p.exists():
                candidates.append(p)

    unique: List[Path] = []
    seen = set()
    for p in candidates:
        s = str(p)
        if s not in seen:
            seen.add(s)
            unique.append(p)
    return unique


def pick_comsol(user_value: Optional[str]) -> str:
    if user_value:
        p = Path(user_value)
        if not p.exists():
            raise FileNotFoundError(f"COMSOL executable not found: {p}")
        return str(p)

    candidates = candidate_comsol_paths()
    if not candidates:
        raise FileNotFoundError(
            "COMSOL executable not found. Pass --comsol <path_to_comsol.exe> "
            "or run from COMSOL Command Prompt."
        )
    return str(candidates[0])


def run_cmd(cmd: List[str], cwd: Path, dry_run: bool = False) -> None:
    print("\n>>>", " ".join(cmd))
    if dry_run:
        return
    proc = subprocess.run(cmd, cwd=str(cwd), text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed with code {proc.returncode}: {' '.join(cmd)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run COMSOL Java API sweeps from Python.")
    parser.add_argument("--project-dir", default=".", help="Project root (default: current dir)")
    parser.add_argument("--comsol", default=None, help="Path to comsol executable")
    parser.add_argument("--dry-run", action="store_true", help="Print commands only")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    if not (project_dir / "src" / "run_sweeps.java").exists():
        raise FileNotFoundError(
            f"run_sweeps.java not found under {project_dir}. "
            "Use --project-dir to point to repository root."
        )

    comsol = "comsol" if args.dry_run and not args.comsol else pick_comsol(args.comsol)

    (project_dir / "build").mkdir(parents=True, exist_ok=True)
    (project_dir / "results" / "models").mkdir(parents=True, exist_ok=True)
    (project_dir / "results" / "figures").mkdir(parents=True, exist_ok=True)

    for jf in JAVA_FILES:
        run_cmd(
            [
                comsol,
                "compile",
                "-inputfile",
                jf,
                "-outputfile",
                "build" + ("\\" if is_windows() else "/"),
            ],
            cwd=project_dir,
            dry_run=args.dry_run,
        )

    run_cmd(
        [
            comsol,
            "batch",
            "-classpath",
            "build",
            "-inputfile",
            "src/run_sweeps.java",
            "-outputfile",
            "results/log.txt",
        ],
        cwd=project_dir,
        dry_run=args.dry_run,
    )

    print("\nDone. Check:")
    print("- results/log.txt")
    print("- results/metrics.csv")
    print("- results/models/*.mph")
    print("- results/figures/*.png")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
