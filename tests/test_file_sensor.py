from __future__ import annotations

from grymbl.config import Settings
from grymbl.events import EventKind
from grymbl.sensors.files import FileSensor
from grymbl.store import Store


def test_saving_identical_content_is_dropped(store: Store, settings: Settings) -> None:
    sensor = FileSensor(store, settings, "dev")
    target = settings.repo_root / "app.py"
    target.write_text("x = 1\n", encoding="utf-8")

    first = sensor.on_changed(target)
    assert first is not None and first.kind is EventKind.FILE_CHANGED
    assert sensor.on_changed(target) is None  # same content saved again

    target.write_text("x = 2\n", encoding="utf-8")
    second = sensor.on_changed(target)
    assert second is not None
    assert "-x = 1" in second.payload["diff"]
    assert len(store.unassigned_events()) == 2


def test_pure_rename_is_dropped(store: Store, settings: Settings) -> None:
    sensor = FileSensor(store, settings, "dev")
    old = settings.repo_root / "old.py"
    old.write_text("def f():\n    return 1\n", encoding="utf-8")
    sensor.on_changed(old)

    new = settings.repo_root / "new.py"
    old.rename(new)
    assert sensor.on_moved(old, new) == []
    assert store.known_files() == {"new.py"}


def test_delete_reports_lost_logic(store: Store, settings: Settings) -> None:
    sensor = FileSensor(store, settings, "dev")
    target = settings.repo_root / "gone.py"
    target.write_text("a = 1\nb = 2\n", encoding="utf-8")
    sensor.on_changed(target)
    target.unlink()

    event = sensor.on_deleted(target)
    assert event is not None and event.payload["removed"] == 2


def test_ignored_and_binary_files_are_skipped(store: Store, settings: Settings) -> None:
    sensor = FileSensor(store, settings, "dev")
    modules = settings.repo_root / "node_modules"
    modules.mkdir()
    (modules / "lib.js").write_text("x", encoding="utf-8")
    (settings.repo_root / "logo.png").write_bytes(b"\x89PNG\0\0")
    assert sensor.on_changed(modules / "lib.js") is None
    assert sensor.on_changed(settings.repo_root / "logo.png") is None
    assert sensor.on_changed(settings.db_path) is None


def test_resync_sets_baseline_and_import_graph(store: Store, settings: Settings) -> None:
    root = settings.repo_root
    (root / "app").mkdir()
    (root / "app" / "auth.py").write_text("TOKEN_TTL = 3600\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_auth.py").write_text("from app import auth\n", encoding="utf-8")

    assert FileSensor(store, settings, "dev").resync() == 2
    assert store.unassigned_events() == []  # baseline is silent
    assert store.import_graph()["tests/test_auth.py"] == {"app/auth.py"}
