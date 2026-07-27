from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import training.collect as collect
from backend.dependencies import get_repository
from backend.main import app
from database.repository import SQLiteRepository


@pytest.fixture
def repository(tmp_path: Path) -> SQLiteRepository:
    """A throwaway database, so tests never touch the real session history."""
    return SQLiteRepository(tmp_path / "test.sqlite3")


@pytest.fixture
def client(repository: SQLiteRepository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(collect, "DATASET_PATH", tmp_path / "showdowns.jsonl")
    app.dependency_overrides[get_repository] = lambda: repository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def dataset_path(tmp_path: Path) -> Path:
    return tmp_path / "showdowns.jsonl"
