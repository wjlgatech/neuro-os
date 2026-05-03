"""
Streamlit Cloud entry point.

Streamlit Cloud looks for ``streamlit_app.py`` at the repo root by
default. This file just delegates to ``ui/app.py`` so all UI code
stays in one place.
"""
import runpy
from pathlib import Path

UI = Path(__file__).resolve().parent / "ui" / "app.py"
runpy.run_path(str(UI), run_name="__main__")
