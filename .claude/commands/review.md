# Review Command

Review recent code changes for quality and safety.

## Steps
1. Run `git diff` to see unstaged changes
2. Run `git diff --staged` to see staged changes
3. Check against the reviewer agent checklist:
   - File safety (no delete/copy)
   - Type hints
   - Docstrings
   - Error handling
   - Tests
   - Architecture consistency
4. Run `ruff check src/` for lint issues
5. Run `mypy src/` for type errors
6. Report findings with severity levels
