# Build Command

Build the project locally for testing.

## Steps
1. Run `ruff check src/` — fix any lint issues
2. Run `ruff format src/` — format code
3. Run `mypy src/` — check types
4. Run `pytest --tb=short -q` — run tests
5. If all pass, report "Build OK ✅"
6. If any fail, report issues and suggest fixes
