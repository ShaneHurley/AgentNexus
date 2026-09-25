# Wave 0 release tag evidence

- **Version:** `0.1.0+wave0`
- **Schema baseline:** `1.0.0`
- **Rollback:** checkout tag `wave0`; delete `runs/` workspace; reinstall editable package.
- **Reproduce tests:** `pip install -e ".[dev]"` then `pytest`, `ruff check`, `mypy src/research_forge`.
