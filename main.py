import os
import subprocess
import sys
import argparse
from pathlib import Path

REQUIRED_MODULES = ("yfinance", "feedparser", "ddgs", "openai", "yaml")
_RELAUNCH_FLAG = "PKRICH_RELAUNCHED"


def _missing_modules() -> list[str]:
    missing: list[str] = []
    for module in REQUIRED_MODULES:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    return missing


def _candidate_pythons() -> list[Path]:
    candidates: list[Path] = []
    local_programs = os.environ.get("LOCALAPPDATA", "")
    if local_programs:
        base = Path(local_programs) / "Programs" / "Python"
        if base.exists():
            for entry in sorted(base.iterdir(), reverse=True):
                exe = entry / "python.exe"
                if exe.exists():
                    candidates.append(exe)
    program_files = os.environ.get("ProgramFiles", "")
    if program_files:
        for entry in sorted(Path(program_files).glob("Python*"), reverse=True):
            exe = entry / "python.exe"
            if exe.exists():
                candidates.append(exe)
    return candidates


def _python_has_modules(python_exe: Path) -> bool:
    check_cmd = [str(python_exe), "-c", "import " + ", ".join(REQUIRED_MODULES)]
    try:
        result = subprocess.run(check_cmd, capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _relaunch_with_system_python(missing: list[str]) -> None:
    if os.environ.get(_RELAUNCH_FLAG):
        _abort_with_message(missing, attempted_relaunch=True)
    for python_exe in _candidate_pythons():
        if python_exe.resolve() == Path(sys.executable).resolve():
            continue
        if not _python_has_modules(python_exe):
            continue
        env = os.environ.copy()
        env[_RELAUNCH_FLAG] = "1"
        print(f"Relaunching with system Python: {python_exe}", file=sys.stderr)
        completed = subprocess.run([str(python_exe), *sys.argv], env=env)
        sys.exit(completed.returncode)
    _abort_with_message(missing, attempted_relaunch=False)


def _abort_with_message(missing: list[str], *, attempted_relaunch: bool) -> None:
    extra = (
        "\nAlready relaunched once but packages are still missing — install them manually."
        if attempted_relaunch
        else "\nNo system Python with the required packages was found automatically."
    )
    print(
        f"Error: missing packages: {', '.join(missing)}\n"
        f"Current Python: {sys.executable}{extra}\n\n"
        "Install with:\n"
        "  pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)


def _check_dependencies() -> None:
    missing = _missing_modules()
    if missing:
        _relaunch_with_system_python(missing)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect-only", action="store_true", help="Run collector-only intraday refresh")
    parser.add_argument(
        "--with-sectors",
        action="store_true",
        help="Run sector explorer refresh after the main watchlist pipeline. Skipped by default to keep normal runs fast.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    _check_dependencies()
    args = _build_parser().parse_args(argv)

    from src.pipeline import collect_only, run_pipeline

    if args.collect_only:
        collect_only()
    else:
        run_pipeline(with_sectors=args.with_sectors)


if __name__ == "__main__":
    main()
