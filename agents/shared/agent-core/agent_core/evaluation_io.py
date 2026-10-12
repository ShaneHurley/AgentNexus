"""Atomic local reports, separate from runtime authority."""
from pathlib import Path
import json
import os
import tempfile


def write_report(path, report):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("report symlink denied")
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".eval-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(text + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
