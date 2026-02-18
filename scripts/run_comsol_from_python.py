#!/usr/bin/env python3
"""
Beginner-friendly launcher for COMSOL Java API sweeps.

This script is designed for users running from PyCharm on Windows (COMSOL 6.2)
but also works on Linux/macOS.

What it does:
1) Ensures output folders exist.
2) Compiles Java files via COMSOL.
3) Runs src/run_sweeps.java in COMSOL batch mode.

Typical usage:
  python scripts/run_comsol_from_python.py
  python scripts/run_comsol_from_python.py --comsol "D:/COMSOL62/Multiphysics/bin/win64/comsol.exe"
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
from typing import Iterable, List, Optional


JAVA_FILES = [
    "src/build_model_3d.java",
    "src/build_model_2d_axi.java",
    "src/postprocess.java",
    "src/run_sweeps.java",
]


def is_windows() -> bool:
    return platform.system().lower().startswith("win")


def _normalize_path_text(s: str) -> str:
    # Helps when a path is copied with quotes from chat/terminal.
    return s.strip().strip('"').strip("'")


def _has_project_layout(project_dir: Path) -> bool:
    return (project_dir / "src" / "run_sweeps.java").exists()


def resolve_project_dir(project_dir_arg: str) -> Path:
    # 1) user-provided/current working dir
    candidate = Path(project_dir_arg).resolve()
    if _has_project_layout(candidate):
        return candidate

    # 2) folder where this script lives, then its parent
    script_dir = Path(__file__).resolve().parent
    if _has_project_layout(script_dir):
        return script_dir
    if _has_project_layout(script_dir.parent):
        return script_dir.parent

    # 3) fail with a concrete hint
    raise FileNotFoundError(
        "Project root looks wrong. Missing:\n- "
        + str(candidate / "src" / "run_sweeps.java")
        + "\nUse --project-dir to point to repository root."
    )


def candidate_comsol_paths() -> List[Path]:
    candidates: List[Path] = []

    from_path = shutil.which("comsol")
    if from_path:
        candidates.append(Path(from_path))

    # Dedicated env variables (user can set once and forget).
    for key in ("COMSOL_EXE", "COMSOL_PATH"):
        real_val = _normalize_path_text(os.environ.get(key, ""))
        if real_val:
            p = Path(real_val)
            if p.exists():
                candidates.append(p)

    if is_windows():
        # Common install roots.
        for root in (Path("C:/Program Files/COMSOL"), Path("D:/COMSOL62"), Path("D:/COMSOL")):
            if root.exists():
                # canonical 6.x layout under Program Files
                for p in sorted(root.glob("COMSOL*/Multiphysics/bin/win64/comsol.exe")):
                    candidates.append(p)
                # direct layout like D:/COMSOL62/Multiphysics/bin/win64/comsol.exe
                direct = root / "Multiphysics" / "bin" / "win64" / "comsol.exe"
                if direct.exists():
                    candidates.append(direct)
    else:
        for p in (Path("/usr/local/bin/comsol"), Path("/opt/comsol/bin/comsol")):
            if p.exists():
                candidates.append(p)

    uniq: List[Path] = []
    seen = set()
    for p in candidates:
        key = str(p.resolve()) if p.exists() else str(p)
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def pick_comsol(user_value: Optional[str]) -> str:
    if user_value:
        p = Path(_normalize_path_text(user_value))
        if not p.exists():
            raise FileNotFoundError(
                f"COMSOL executable not found: {p}\n"
                "Tip: pass full path to comsol.exe, e.g.\n"
                "--comsol \"D:/COMSOL62/Multiphysics/bin/win64/comsol.exe\""
            )
        return str(p)

    candidates = candidate_comsol_paths()
    if not candidates:
        raise FileNotFoundError(
            "COMSOL executable not found.\n"
            "Pass --comsol <path_to_comsol.exe> or set COMSOL_EXE env var.\n"
            "Example:\n"
            "  --comsol \"D:/COMSOL62/Multiphysics/bin/win64/comsol.exe\""
        )
    return str(candidates[0])


def run_cmd(cmd: Iterable[str], cwd: Path, dry_run: bool = False) -> None:
    cmd_list = list(cmd)
    print("\n>>>", " ".join(cmd_list))
    if dry_run:
        return
    proc = subprocess.run(cmd_list, cwd=str(cwd), text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed with code {proc.returncode}: {' '.join(cmd_list)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run COMSOL Java API sweeps from Python.")
    parser.add_argument(
        "--project-dir",
        default=".",
        help="Project root (default: current dir; auto-detected from script location if needed)",
    )
    parser.add_argument("--comsol", default=None, help="Path to comsol executable")
    parser.add_argument("--dry-run", action="store_true", help="Print commands only")
    args = parser.parse_args()

    project_dir = resolve_project_dir(args.project_dir)
    comsol = "comsol" if args.dry_run and not args.comsol else pick_comsol(args.comsol)

    (project_dir / "build").mkdir(parents=True, exist_ok=True)
    (project_dir / "results" / "models").mkdir(parents=True, exist_ok=True)
    (project_dir / "results" / "figures").mkdir(parents=True, exist_ok=True)

    build_out = "build\\" if is_windows() else "build/"
    for java_file in JAVA_FILES:
        run_cmd(
            [comsol, "compile", "-inputfile", java_file, "-outputfile", build_out],
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
