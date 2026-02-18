#!/usr/bin/env python3
"""
Beginner-friendly launcher for COMSOL Java API sweeps.
Designed for PyCharm + Windows COMSOL 6.2 but works on Linux/macOS.
"""

from __future__ import annotations

import argparse
import glob
import os
import platform
import shutil
import subprocess
import sys
import time
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

    search_dirs = [p.parent, p.parent.parent, p.parent.parent / "bin", p.parent.parent / "win64"]
    compile_candidates: List[Path] = []
    batch_candidates: List[Path] = []

    for d in search_dirs:
        if not d.exists():
            continue
        compile_candidates.extend(sorted(d.glob("comsolcompile.*")))
        batch_candidates.extend(sorted(d.glob("comsolbatch.*")))

    def pick(paths: List[Path]) -> Optional[str]:
        preferred_ext = [".exe", ".bat", ".cmd", ".ps1"]
        for ext in preferred_ext:
            for q in paths:
                if q.suffix.lower() == ext:
                    return str(q)
        return str(paths[0]) if paths else None

    return pick(compile_candidates), pick(batch_candidates)


def run_cmd(cmd: Iterable[str], cwd: Path, dry_run: bool = False) -> subprocess.CompletedProcess:
    cmd_list = list(cmd)
    print("\n>>>", " ".join(cmd_list))
    if dry_run:
        return subprocess.CompletedProcess(cmd_list, 0, "", "")

    proc = subprocess.run(cmd_list, cwd=str(cwd), text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)

    if proc.returncode != 0:
        raise RuntimeError(f"Command failed with code {proc.returncode}: {' '.join(cmd_list)}")
    return proc


def _looks_failed(proc: subprocess.CompletedProcess) -> bool:
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    low = out.lower()
    return (
        "error:" in low
        or "compilation failed" in low
        or "input filename is not specified" in low
    )


def _run_first_success(variants: List[List[str]], cwd: Path, dry_run: bool) -> None:
    last_error = None
    for variant in variants:
        try:
            proc = run_cmd(variant, cwd=cwd, dry_run=dry_run)
            if not dry_run and _looks_failed(proc):
                last_error = RuntimeError(f"Tool reported failure: {' '.join(variant)}")
                continue
            return
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error


def run_compile_and_batch(comsol_path: str, project_dir: Path, dry_run: bool, prefer_direct_tools: bool) -> None:
    compile_tool: Optional[str] = None
    batch_tool: Optional[str] = None

    if is_windows() and prefer_direct_tools:
        compile_tool, batch_tool = _find_windows_direct_tools(comsol_path)

    build_out = "build\\" if is_windows() else "build/"

    if compile_tool and batch_tool:
        print(f"Using direct tools: compile={compile_tool}, batch={batch_tool}")

        for java_file in JAVA_FILES:
            compile_variants = [
                [compile_tool, java_file],
                [compile_tool, "-inputfile", java_file, "-outputfile", build_out],
            ]
            _run_first_success(compile_variants, cwd=project_dir, dry_run=dry_run)

        cp_sep = ";" if is_windows() else ":"
        classpath = cp_sep.join(["build", "src", "."])
        batch_variants = [
            [batch_tool, "-classpath", classpath, "run_sweeps"],
            [batch_tool, "-classpath", "build", "run_sweeps"],
            [batch_tool, "-classpath", "build", "-inputfile", "src/run_sweeps.java", "-outputfile", "results/log.txt"],
        ]
        _run_first_success(batch_variants, cwd=project_dir, dry_run=dry_run)
        return

    if is_windows() and prefer_direct_tools:
        print("WARNING: comsolcompile/comsolbatch not found near comsol.exe, fallback to 'comsol.exe compile/batch'.")

    for java_file in JAVA_FILES:
        run_cmd([comsol_path, "compile", "-inputfile", java_file, "-outputfile", build_out], cwd=project_dir, dry_run=dry_run)
    run_cmd([comsol_path, "batch", "-classpath", "build", "-inputfile", "src/run_sweeps.java", "-outputfile", "results/log.txt"], cwd=project_dir, dry_run=dry_run)


def ensure_outputs(project_dir: Path, started_at: float) -> None:
    models = [Path(x) for x in glob.glob(str(project_dir / "results" / "models" / "*.mph"))]
    metrics = project_dir / "results" / "metrics.csv"

    fresh_models = [m for m in models if m.stat().st_mtime >= started_at]
    fresh_metrics = metrics.exists() and metrics.stat().st_mtime >= started_at

    if fresh_models and fresh_metrics:
        return

    raise RuntimeError(
        "COMSOL finished but NEW expected outputs were not found for this run.\n"
        f"- fresh .mph files: {len(fresh_models)}\n"
        f"- fresh metrics.csv: {fresh_metrics}\n"
        f"- log path: {project_dir / 'results' / 'log.txt'}\n"
        "Check log for COMSOL-side errors (license/modules/API tags)."
    )


def clear_outputs(project_dir: Path) -> None:
    for p in glob.glob(str(project_dir / "results" / "models" / "*.mph")):
        Path(p).unlink(missing_ok=True)
    for p in glob.glob(str(project_dir / "results" / "figures" / "*.png")):
        Path(p).unlink(missing_ok=True)
    for p in (project_dir / "results" / "metrics.csv", project_dir / "results" / "log.txt"):
        p.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run COMSOL Java API sweeps from Python.")
    parser.add_argument("--project-dir", default=".", help="Project root (auto-detected from script location if needed)")
    parser.add_argument("--comsol", default=None, help="Path to comsol executable")
    parser.add_argument("--dry-run", action="store_true", help="Print commands only")
    parser.add_argument("--prefer-direct-tools", action="store_true", default=True, help="On Windows, prefer comsolcompile/comsolbatch")
    parser.add_argument("--skip-output-check", action="store_true", help="Do not fail when output files are missing")
    parser.add_argument("--clean-results", action="store_true", default=True, help="Remove old results before run")
    args = parser.parse_args()

    project_dir = resolve_project_dir(args.project_dir)
    comsol = "comsol" if args.dry_run and not args.comsol else pick_comsol(args.comsol)

    print(f"Project dir: {project_dir}")
    print(f"COMSOL path: {comsol}")

    (project_dir / "build").mkdir(parents=True, exist_ok=True)
    (project_dir / "results" / "models").mkdir(parents=True, exist_ok=True)
    (project_dir / "results" / "figures").mkdir(parents=True, exist_ok=True)

    if args.clean_results and not args.dry_run:
        clear_outputs(project_dir)

    started_at = time.time()
    run_compile_and_batch(comsol_path=comsol, project_dir=project_dir, dry_run=args.dry_run, prefer_direct_tools=args.prefer_direct_tools)

    if not args.dry_run and not args.skip_output_check:
        ensure_outputs(project_dir, started_at)

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
