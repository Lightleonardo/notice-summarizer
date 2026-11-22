"""Tests for the Streamlit app (Step 8).

The app is driven with streamlit.testing.v1.AppTest. No API key is configured,
so the app takes the extractive-only path and never calls a real model.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parent.parent / "app.py"

NOTICE = (
    "Dear Parents. The PTA meeting holds on Tuesday, 8 December 2026 at "
    "10:00 a.m. Please bring your receipt booklet. Call 0803 123 4567."
)


@pytest.fixture(autouse=True)
def _no_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def _start():
    return AppTest.from_file(str(APP), default_timeout=30).run()


def test_app_summarises_without_a_model():
    at = _start()
    at.text_area(key="notice").set_value(NOTICE)
    at.button[0].click().run()
    assert not at.exception
    assert "8 December 2026" in at.text_area(key="final_text").value


def test_app_rejects_an_empty_notice():
    at = _start()
    at.text_area(key="notice").set_value("   ")
    at.button[0].click().run()
    assert not at.exception
    assert at.error


def test_app_uses_the_edited_version():
    at = _start()
    at.text_area(key="notice").set_value(NOTICE)
    at.button[0].click().run()

    at.text_area(key="final_text").set_value("Edited: meeting on 8 December 2026.")
    at.button[1].click().run()

    assert not at.exception
    assert at.text_area(key="final_text").value == "Edited: meeting on 8 December 2026."
