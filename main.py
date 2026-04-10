import sys


def _check_dependencies() -> None:
    missing: list[str] = []
    for module in ("yfinance", "feedparser", "ddgs", "openai", "yaml"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        print(
            f"Error: missing packages: {', '.join(missing)}\n"
            f"Current Python: {sys.executable}\n"
            "\nThis may be caused by running inside a virtual environment "
            "that does not have the required packages installed.\n"
            "Try: pip install -r requirements.txt\n"
            "Or run with the system Python directly:\n"
            '  "C:\\Users\\junhe\\AppData\\Local\\Programs\\Python\\Python311\\python.exe" main.py',
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    _check_dependencies()
    from src.pipeline import run_pipeline

    run_pipeline()
