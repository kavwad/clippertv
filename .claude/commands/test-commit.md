Run pre-commit checks and commit with jj.

1. **Type-check** (always):
   `uv run ty check src/`

2. **Test** (skip if you already ran pytest with passing results since the last
   substantive code change — formatting-only or comment edits don't count):
   `uv run pytest -m "prepush" --tb=short`

3. If checks pass, run `jj status` and suggest a commit message (or suggest
   splitting/squashing if appropriate). Check recent commits with `jj log`.

4. Run `jj commit -m "<message>"` with the agreed-upon message.

If any check fails, stop and help me fix the issue before retrying.

Notes:
- Use `pytest -m "prepush"` not the full suite. Run broader markers
  (`integration`) only if explicitly relevant to the code changes during
  this session.
- `jj fix` already handles ruff check + format — no need to run ruff separately.
