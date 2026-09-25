"""Prove wheel ships config/ + schemas/ (Hatch force-include)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


@pytest.fixture()
def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_wheel_includes_config_and_schemas(package_root: Path, tmp_path: Path) -> None:
    out = tmp_path / "wheels"
    out.mkdir()
    env = os.environ.copy()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "-w",
            str(out),
            str(package_root),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    wheels = sorted(out.glob("*.whl"))
    if not wheels and proc.returncode != 0:
        # Retry with build isolation (needs network for hatchling)
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "-w",
                str(out),
                str(package_root),
            ],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        wheels = sorted(out.glob("*.whl"))
    if not wheels:
        pytest.skip(f"could not build wheel: {proc.stderr[:500] or proc.stdout[:500]}")

    whl = wheels[-1]
    with zipfile.ZipFile(whl, "r") as zf:
        names = zf.namelist()
    assert any(
        n == "config/experiments.yaml" or n.endswith("config/experiments.yaml") for n in names
    ), names[:30]
    assert any("schemas/" in n and n.endswith(".schema.json") for n in names), [
        n for n in names if "schema" in n
    ][:20]


def test_get_registry_none_uses_package_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_registry() with no args resolves via find_package_root (intentional)."""
    import research_forge as rf
    from research_forge.schemas_pkg.registry import get_experiment_registry, get_registry

    real = Path(__file__).resolve().parents[1]
    site = tmp_path / "site-packages"
    pkg = site / "research_forge"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("# stub\n", encoding="utf-8")
    shutil.copytree(real / "config", site / "config")
    shutil.copytree(real / "schemas", site / "schemas")

    monkeypatch.delenv("RF_PACKAGE_ROOT", raising=False)
    monkeypatch.setattr(rf, "__file__", str(pkg / "__init__.py"))
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)
    get_registry.cache_clear()
    get_experiment_registry.cache_clear()

    from research_forge.settings import find_package_root

    assert find_package_root() == site.resolve()
    reg = get_registry()
    assert reg.schema_dir == site / "schemas"
    get_registry.cache_clear()
    get_experiment_registry.cache_clear()
