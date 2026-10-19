"""Smoke test: the Streamlit app runs from top to bottom without an exception."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


def test_app_runs_without_exception():
    app = AppTest.from_file(str(APP_PATH), default_timeout=120)
    app.run()
    assert not app.exception
    assert len(app.tabs) == 5
    labels = [m.label for m in app.metric]
    assert "Revenue" in labels
    assert "Overstock alerts" in labels


def test_app_handles_filter_change():
    app = AppTest.from_file(str(APP_PATH), default_timeout=120)
    app.run()
    app.multiselect[0].set_value(["West"]).run()   # the Region filter
    assert not app.exception
