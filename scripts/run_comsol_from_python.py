#!/usr/bin/env python3
"""
Beginner-friendly launcher for COMSOL Java API sweeps.

This script is designed for users running from PyCharm on Windows (COMSOL 6.2)
but also works on Linux/macOS.
"""

from __future__ import annotations

import argparse
import glob
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

JAVA_FILES = [
    "src/build_model_3d.java",
    "src/build_model_2d_axi.java",
    "src/postprocess.java",
    "src/run_sweeps.java",
]


def is_windows() -> bool:
    return platform.system().lower().startswith("win")


def _normalize_path_text(s: str) -> str:
    return s.strip().strip('"').strip("'")


def _has_project_layout(project_dir: Path) -> bool:
    return (project_dir / "src" / "run_sweeps.java").exists()


def resolve_project_dir(project_dir_arg: str) -> Path:
    candidate = Path(project_dir_arg).resolve()
    if _has_project_layout(candidate):
        return candidate

    script_dir = Path(__file__).resolve().parent
    if _has_project_layout(script_dir):
        return script_dir
    if _has_project_layout(script_dir.parent):
        return script_dir.parent

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

    for key in ("COMSOL_EXE", "COMSOL_PATH"):
        real_val = _normalize_path_text(os.environ.get(key, ""))
        if real_val:
            p = Path(real_val)
            if p.exists():
                candidates.append(p)

    if is_windows():
        for root in (Path("C:/Program Files/COMSOL"), Path("D:/COMSOL62"), Path("D:/COMSOL")):
            if root.exists():
                for p in sorted(root.glob("COMSOL*/Multiphysics/bin/win64/comsol.exe")):
                    candidates.append(p)
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


def _find_windows_direct_tools(comsol_path: str) -> Tuple[Optional[str], Optional[str]]:
    p = Path(comsol_path)
    if not p.exists():
        return None, None
    base = p.parent
    compile_exe = base / "comsolcompile.exe"
    batch_exe = base / "comsolbatch.exe"
    return (
        str(compile_exe) if compile_exe.exists() else None,
        str(batch_exe) if batch_exe.exists() else None,
    )


def run_cmd(cmd: Iterable[str], cwd: Path, dry_run: bool = False) -> None:
    cmd_list = list(cmd)
    print("\n>>>", " ".join(cmd_list))
    if dry_run:
        return
    proc = subprocess.run(cmd_list, cwd=str(cwd), text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed with code {proc.returncode}: {' '.join(cmd_list)}")


def run_compile_and_batch(comsol_path: str, project_dir: Path, dry_run: bool, prefer_direct_tools: bool) -> None:
    compile_exe = None
    batch_exe = None
    if is_windows() and prefer_direct_tools:
        compile_exe, batch_exe = _find_windows_direct_tools(comsol_path)

    build_out = "build\\" if is_windows() else "build/"

    if compile_exe and batch_exe:
        print("Using comsolcompile/comsolbatch executables (recommended on Windows).")
        for java_file in JAVA_FILES:
            run_cmd([compile_exe, "-inputfile", java_file, "-outputfile", build_out], cwd=project_dir, dry_run=dry_run)
        run_cmd(
            [batch_exe, "-classpath", "build", "-inputfile", "src/run_sweeps.java", "-outputfile", "results/log.txt"],
            cwd=project_dir,
            dry_run=dry_run,
        )
        return

    for java_file in JAVA_FILES:
        run_cmd([comsol_path, "compile", "-inputfile", java_file, "-outputfile", build_out], cwd=project_dir, dry_run=dry_run)
    run_cmd(
        [comsol_path, "batch", "-classpath", "build", "-inputfile", "src/run_sweeps.java", "-outputfile", "results/log.txt"],
        cwd=project_dir,
        dry_run=dry_run,
    )


def ensure_outputs(project_dir: Path) -> None:
    models = glob.glob(str(project_dir / "results" / "models" / "*.mph"))
    metrics = project_dir / "results" / "metrics.csv"
    if models and metrics.exists():
        return
    raise RuntimeError(
        "COMSOL finished but expected outputs were not found.\n"
        f"- models found: {len(models)} in {project_dir / 'results' / 'models'}\n"
        f"- metrics.csv exists: {metrics.exists()} ({metrics})\n"
        "Check results/log.txt for COMSOL-side errors (license/modules/API tags)."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run COMSOL Java API sweeps from Python.")
    parser.add_argument(
        "--project-dir",
        default=".",
        help="Project root (default: current dir; auto-detected from script location if needed)",
    )
    parser.add_argument("--comsol", default=None, help="Path to comsol executable")
    parser.add_argument("--dry-run", action="store_true", help="Print commands only")
    parser.add_argument(
        "--prefer-direct-tools",
        action="store_true",
        default=True,
        help="On Windows, prefer comsolcompile.exe/comsolbatch.exe if available",
    )
    parser.add_argument(
        "--skip-output-check",
        action="store_true",
        help="Do not fail when results/models/*.mph or results/metrics.csv are missing",
    )
    args = parser.parse_args()

    project_dir = resolve_project_dir(args.project_dir)
    comsol = "comsol" if args.dry_run and not args.comsol else pick_comsol(args.comsol)

    (project_dir / "build").mkdir(parents=True, exist_ok=True)
    (project_dir / "results" / "models").mkdir(parents=True, exist_ok=True)
    (project_dir / "results" / "figures").mkdir(parents=True, exist_ok=True)

    run_compile_and_batch(
        comsol_path=comsol,
        project_dir=project_dir,
        dry_run=args.dry_run,
        prefer_direct_tools=args.prefer_direct_tools,
    )

    if not args.dry_run and not args.skip_output_check:
        ensure_outputs(project_dir)

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
