# Research Forge

Evidence-first deep research agent (Waves 0–6 mock-by-default) plus a human-gated **local experiment** subsystem (Creator / Pre-Reviewer / Runner / Post-Reviewer).

**Requirements:** Python 3.10+

```bash
python -m pip install -e ".[dev]"
python -m research_forge doctor
python -m research_forge validate --gate wave_0
python -m pytest -q
```

On Windows you can use the launcher: `py -3.10 -m pip install -e ".[dev]"`.

**Install vs checkout:** Experiment commands resolve assets via `find_package_root()` (works after a normal/editable install that ships `config/` + `schemas/`). Many wave CLI paths still use `find_repo_root()` and expect a Research Forge checkout (or `RF_PACKAGE_ROOT`).

Live providers require `--live` plus decision gate approval. Local experiments: see [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md).

**Workspace hub:** [../docs/README.md](../docs/README.md) (Research Forge deep dive, waves, experiments, lineage).
