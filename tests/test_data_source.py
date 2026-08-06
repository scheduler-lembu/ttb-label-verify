"""Tests for the application data-source layer (offline — no AI, no network).

Points ``DemoCsvSource`` at ``sample_data/demo_applications.csv`` relative to the
repo root (pytest runs from there).
"""

from __future__ import annotations

from app.data_source import DemoCsvSource
from app.fields import FIELD_REGISTRY

CSV_PATH = "sample_data/demo_applications.csv"
_REGISTRY_KEYS = {f.key for f in FIELD_REGISTRY}


def test_lists_ten_applications():
    assert len(DemoCsvSource(CSV_PATH).list_applications()) == 10


def test_get_known_application():
    app = DemoCsvSource(CSV_PATH).get_application("APP-0001")
    assert app is not None
    # Matches the first test_labels.csv row (label_01_compliant).
    assert app.expected["brand"] == "Old Tom Distillery"
    assert app.expected["alcohol_content"] == "45%"


def test_expected_keys_are_registry_only():
    for app in DemoCsvSource(CSV_PATH).list_applications():
        for key in app.expected:
            assert key in _REGISTRY_KEYS
        assert "beverage_type" not in app.expected


def test_extra_field_preserved():
    apps = DemoCsvSource(CSV_PATH).list_applications()
    assert any(a.extra.get("beverage_type") for a in apps)


def test_unknown_id_returns_none():
    assert DemoCsvSource(CSV_PATH).get_application("APP-9999") is None
