"""Fictional fixtures are available to tests, never the default user workspace."""

import pytest


@pytest.fixture(autouse=True)
def isolated_history_and_fixtures(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_RESEARCH_TEST_FIXTURES", "1")
    monkeypatch.setenv("STOCK_RESEARCH_HISTORY", str(tmp_path / "history"))
    monkeypatch.setenv("STOCK_RESEARCH_DB", str(tmp_path / "research.sqlite"))
