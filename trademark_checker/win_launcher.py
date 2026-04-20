from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from streamlit.web import cli as stcli


def _app_path() -> str:
    candidate = Path(__file__).resolve().parent / "app.py"
    return str(candidate)


def main() -> None:
    webbrowser.open("http://127.0.0.1:8501/")
    sys.argv = [
        "streamlit",
        "run",
        _app_path(),
        "--server.address",
        "127.0.0.1",
        "--server.port",
        "8501",
        "--server.headless",
        "true",
    ]
    stcli.main()


if __name__ == "__main__":
    main()
