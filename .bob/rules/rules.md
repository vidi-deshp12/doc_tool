# Project rules (read every time)

## Context
This project builds `docgen`: a tool that extracts facts from a Python repo with `ast`, writes cited docs on top of those facts, and detects doc drift. Before starting any task, read:
`docs/PRD.md`, `docs/architecture.md`, `docs/tasks.md` (find the current task), `docs/memory.md`.

## Workflow
1. Work on ONE task from `docs/tasks.md` at a time, identified by its full ID (e.g. `2a.3`). Do not start the next one. If the task ID is missing or ambiguous, ask which one.
2. Plan first (Plan mode): list the files you'll touch and the tests you'll add, then **STOP and wait for the user's approval before writing any code.** Then implement. Then review.
3. Done = acceptance criteria in the task are met AND tests pass. Say which tests you ran.
4. After each task: tick it in `docs/tasks.md`; add decisions, bugs, and fixes to `docs/memory.md`; add a short entry to `BOB_LOG.md`.
5. If something in the docs is wrong or unclear, stop and ask. Do not silently change scope.

## Hard rules
- **No repo-specific code.** Never hardcode file names, folder names, or function names from the analysed repo. Repo-specific settings go in `docgen.toml`.
- **Facts are deterministic.** Only the summarize/ package may call an LLM.
- **Never guess.** Anything unresolved goes in the `unresolved` list with a reason and location.
- **Do not modify `target/`** except the seeded bug/feature tasks, and log those in `docs/memory.md`.
- **Do not run or import analysed code** outside the FastAPI adapter, and there only in a subprocess with a timeout.
- **No new dependencies** without asking. Allowed: stdlib, pytest, streamlit. Ask before anything else.
- Do not write secrets, tokens, or API keys into files.

## Code conventions
- Python 3.11+, type hints on all public functions, `dataclasses` for data, `pathlib` for paths.
- IDs and stored paths are **relative to the repo root with forward slashes** (`Path.as_posix()`).
- All file I/O uses `encoding="utf-8"` explicitly. Never rely on shell redirects (`>`) for JSON on Windows.
- JSON output: `sort_keys=True`, `indent=2`, no timestamps, no absolute paths.
- Small functions, one job each. Docstrings on modules and public functions explaining *why*.
- Must run on Windows and Linux. Do not use shell-specific commands in code.

## Errors
- A bad file must never crash a run: catch per file, record `unresolved`, continue.
- Raise specific exceptions for programmer errors. Never use bare `except:`.
- CLI exit codes: 0 ok, 1 drift or check failure, 2 usage/config error.

## Tests
- Every feature gets pytest tests. Prefer small fixture repos in `tests/fixtures/` over `target/`.
- Tests must not call an LLM. Use `StubSummarizer`.
- When fixing a bug, add a test that fails without the fix.

## Communication
- Be concise. State assumptions explicitly. List files changed at the end of each task.
- The user is new to Python beyond algorithms: explain non-obvious constructs (decorators, `Depends`, AST node types) in one or two sentences in code comments or in your reply.
