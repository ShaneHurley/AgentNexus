"""Status readers never see a truncated JSON artifact during publication."""
import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from research_forge.experiments.store import ExperimentStore

@pytest.fixture
def store(tmp_path):
    return ExperimentStore(tmp_path, cfg={"workspace_relative": "experiments"})

def test_reader_during_status_publication_sees_complete_previous_version(store):
    store.set_status("EXP-race", "running")
    target = store.path("EXP-race", "status.json")
    original_open = Path.open
    original_replace = os.replace
    observations = []
    def observe():
        try:
            observations.append(store.read_json("EXP-race", "status.json")["status"])
        except json.JSONDecodeError:
            observations.append("truncated-json")
    def intercepted_open(path, mode="r", *args, **kwargs):
        fh = original_open(path, mode, *args, **kwargs)
        if path == target and "w" in mode:
            observe()  # Immediately after the old implementation truncates status.
        return fh
    def intercepted_replace(source, destination):
        assert Path(source).parent == target.parent
        observe()  # Atomic implementation publishes only after full temp write.
        return original_replace(source, destination)
    with patch.object(Path, "open", intercepted_open), patch("os.replace", intercepted_replace):
        store.set_status("EXP-race", "succeeded")
    assert observations == ["running"]
    assert store.read_json("EXP-race", "status.json")["status"] == "succeeded"

def test_atomic_write_fsyncs_file_before_replace_and_directory_after(store):
    events = []
    original_fsync, original_replace = os.fsync, os.replace
    def synced(fd):
        events.append("sync")
        return original_fsync(fd)
    def replaced(src, dst):
        events.append("replace")
        return original_replace(src, dst)
    with patch("os.fsync", synced), patch("os.replace", replaced):
        store.set_status("EXP-durable", "running")
    assert events == ["sync", "replace", "sync"]

def test_failed_replace_preserves_status_and_removes_temp_file(store):
    store.set_status("EXP-failed", "running")
    directory = store.exp_dir("EXP-failed")
    with patch("os.replace", side_effect=OSError("replace failed")):
        with pytest.raises(OSError, match="replace failed"):
            store.set_status("EXP-failed", "succeeded")
    assert store.read_json("EXP-failed", "status.json")["status"] == "running"
    assert sorted(p.name for p in directory.iterdir()) == ["status.json"]

def test_malformed_json_remains_a_visible_error(store):
    store.path("EXP-corrupt", "status.json").write_text("{")
    with pytest.raises(json.JSONDecodeError):
        store.read_json("EXP-corrupt", "status.json")
