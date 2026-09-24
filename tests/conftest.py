from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from grymbl.config import Settings
from grymbl.store import Store


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(tmp_path)
    settings.data_dir.mkdir()
    return settings


@pytest.fixture
def store(settings: Settings) -> Iterator[Store]:
    with Store(settings.db_path) as store:
        yield store
