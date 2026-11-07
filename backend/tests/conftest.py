from types import SimpleNamespace

import pytest


def _offline_settings() -> SimpleNamespace:
    return SimpleNamespace(openai_api_key="", openai_model="gpt-4o-mini", vision_model="gpt-4o", max_vision_failures=2)


@pytest.fixture(autouse=True)
def offline_language_models(monkeypatch):
    """Pytest must not call a paid vision or semantic model."""
    monkeypatch.setattr("app.graph.tools.vision.get_settings", _offline_settings)
    monkeypatch.setattr("app.graph.tools.semantic.get_settings", _offline_settings)
    monkeypatch.setattr("app.config.get_settings", _offline_settings)
