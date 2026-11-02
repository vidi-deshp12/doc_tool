# Plan: Pluggable LLM Backends

## Goal

Make `docgen summarize` work with any instruction-following LLM by adding:
1. An **OpenAI-compatible backend** (`openai_backend.py`) — covers OpenAI GPT models
   and any endpoint that speaks the OpenAI chat completions API (Ollama, vLLM, LM Studio).
2. An **Anthropic backend** (`anthropic_backend.py`) — covers Claude models via the
   Anthropic SDK, which has a different API shape from OpenAI.
3. A **`[summarize]` section in `docgen.toml`** so users can set a default backend and
   model without passing `--backend` / `--model` every time.

**Done when:**
- `docgen summarize --backend openai` works with `OPENAI_API_KEY` set.
- `docgen summarize --backend openai --base-url http://localhost:11434/v1` works
  against a local Ollama instance (zero code change, just a URL flag).
- `docgen summarize --backend anthropic` works with `ANTHROPIC_API_KEY` set.
- `docgen.toml` `[summarize]` section sets defaults for backend / model / base-url.
- CLI `--backend` still overrides the config file.
- All new code is covered by tests that do not call real APIs (mock the HTTP layer).
- No new mandatory dependencies — `openai` and `anthropic` are optional; the CLI
  gives a clear `pip install` instruction when they are missing.

**Hard rule:** `openai` and `anthropic` are NOT added to `pyproject.toml` as required
dependencies. They are imported inside the backend class `__init__` with a
`try/except ImportError` that raises a clear installation message. stdlib + pytest
remain the only required deps.

---

## Sub-task 1 — OpenAI-compatible backend [pending]

**Intent:** Implement `OpenAISummarizer` in a new file. It calls the OpenAI chat
completions endpoint with the prompt built by `build_prompt(req)` and returns a
`SummaryResult`. By accepting a `base_url` parameter it also covers Ollama and any
other OpenAI-compatible server without a separate class.

**Expected outcomes:**
- `docgen summarize --backend openai [--model gpt-4o] [--base-url URL]` runs.
- A missing `openai` package gives `pip install openai` in the error message.
- A missing `OPENAI_API_KEY` (when base-url is the default OpenAI endpoint) gives a
  clear error before making any network calls.
- The `backend` field in `SummaryResult` is `"openai:<model>"` (e.g. `"openai:gpt-4o"`).
- Retry logic: 2 attempts with 5s backoff, same pattern as `BobShellSummarizer`.

**Todo list:**
1. Create `src/docgen/summarize/openai_backend.py`.
2. Define `OpenAIError(Exception)` — analogous to `BobShellError`.
3. Implement `OpenAISummarizer.__init__(model, base_url, api_key, timeout)`:
   - Import `openai` inside `__init__`; on `ImportError` raise `OpenAIError` with
     `pip install openai` in the message.
   - Default model: `"gpt-4o"`.
   - Default `base_url`: `None` (uses the OpenAI SDK default).
   - `api_key`: defaults to `None` (SDK reads `OPENAI_API_KEY` from env). When
     `base_url` is not the OpenAI default and no key is set, no error — local servers
     like Ollama don't require one.
4. Implement `summarize(req) -> SummaryResult`:
   - Call `build_prompt(req)` for the prompt text.
   - Call `client.chat.completions.create(model=..., messages=[{"role":"user","content":prompt}])`.
   - Extract `response.choices[0].message.content`.
   - Return `SummaryResult(node_id, text, backend=f"openai:{self.model}", hash_input=hash_input(req))`.
   - Retry once on any exception (same 2-attempt, 5s pattern as bob_shell).
5. Write `tests/test_openai_backend.py`:
   - Test 1: `OpenAISummarizer` raises `OpenAIError` when `openai` is not importable
     (mock `builtins.__import__` to raise `ImportError` for `"openai"`).
   - Test 2: `summarize` returns correct `SummaryResult` (mock `openai.OpenAI` client).
   - Test 3: retry on first failure, success on second (mock client raises then succeeds).
   - Test 4: `backend` field is `"openai:<model>"`.
   - Test 5: `base_url` is passed through to the OpenAI client constructor.

**Relevant context:**
- [`src/docgen/summarize/bob_shell.py`](src/docgen/summarize/bob_shell.py) — reference for the retry pattern and error class
- [`src/docgen/summarize/base.py`](src/docgen/summarize/base.py) — `SummaryRequest`, `SummaryResult`, `hash_input`
- [`src/docgen/summarize/prompts.py`](src/docgen/summarize/prompts.py) — `build_prompt`

---

## Sub-task 2 — Anthropic backend [pending]

**Intent:** Implement `AnthropicSummarizer` in a new file. The Anthropic SDK has a
different shape from OpenAI: messages use `anthropic.Anthropic().messages.create(...)`,
the response is `response.content[0].text`, and the model names are different
(`claude-3-5-sonnet-20241022` etc.). Everything else — prompt, retry, error handling,
`SummaryResult` shape — is identical.

**Expected outcomes:**
- `docgen summarize --backend anthropic [--model claude-3-5-sonnet-20241022]` runs.
- A missing `anthropic` package gives `pip install anthropic` in the error message.
- A missing `ANTHROPIC_API_KEY` raises a clear error before any network call.
- The `backend` field is `"anthropic:<model>"`.

**Todo list:**
1. Create `src/docgen/summarize/anthropic_backend.py`.
2. Define `AnthropicError(Exception)`.
3. Implement `AnthropicSummarizer.__init__(model, api_key, max_tokens, timeout)`:
   - Import `anthropic` inside `__init__`; on `ImportError` raise `AnthropicError`
     with `pip install anthropic` in the message.
   - Default model: `"claude-3-5-sonnet-20241022"`.
   - `api_key`: defaults to `None` (SDK reads `ANTHROPIC_API_KEY` from env). Raise
     `AnthropicError` explicitly if neither `api_key` nor `ANTHROPIC_API_KEY` is set.
   - `max_tokens`: default `4096` (Anthropic requires this parameter; OpenAI does not).
4. Implement `summarize(req) -> SummaryResult`:
   - Call `client.messages.create(model=..., max_tokens=..., messages=[{"role":"user","content":prompt}])`.
   - Extract `response.content[0].text`.
   - Return `SummaryResult(..., backend=f"anthropic:{self.model}", ...)`.
   - Same 2-attempt retry pattern.
5. Write `tests/test_anthropic_backend.py` (5 tests, same structure as openai tests):
   - ImportError → `AnthropicError` with install hint.
   - Successful call → correct `SummaryResult`.
   - Retry on first failure.
   - `backend` field format.
   - Missing API key → `AnthropicError` before any network call.

**Relevant context:**
- [`src/docgen/summarize/openai_backend.py`](src/docgen/summarize/openai_backend.py) — reference (write after sub-task 1)
- Anthropic SDK: `anthropic.Anthropic(api_key=...).messages.create(model, max_tokens, messages)`
  response: `response.content[0].text`

---

## Sub-task 3 — `[summarize]` config section + CLI wiring [pending]

**Intent:** Wire both new backends into the CLI and add a `[summarize]` section to
`docgen.toml` so users don't have to pass `--backend --model` every time. CLI flags
still take precedence over config file values (same pattern as other tools).

**Expected outcomes:**
- `docgen.toml` accepts:
  ```toml
  [summarize]
  backend = "openai"           # or "anthropic", "bob_shell", "stub", "manual"
  model   = "gpt-4o"           # optional; backend uses its own default if absent
  base_url = "http://localhost:11434/v1"  # openai backend only; omit for real OpenAI
  ```
- `docgen summarize` without `--backend` reads from `[summarize].backend`; if the
  section is absent it falls back to `"stub"` (existing default — no breaking change).
- `--backend`, `--model`, `--base-url` CLI flags override the config file.
- `_run_update` in `cli.py` follows the same backend-selection logic.
- The error message in `cli.py` for an unknown backend is updated to list the new
  backend names.

**Todo list:**
1. Add a `SummarizeConfig` dataclass to `config.py`:
   ```python
   @dataclass(frozen=True)
   class SummarizeConfig:
       backend: str = "stub"
       model: str = ""        # empty → backend uses its own default
       base_url: str = ""     # empty → backend uses its own default
   ```
2. Extend `Config` with a `summarize: SummarizeConfig` field.
3. In `load_config`, read `data.get("summarize", {})` and populate `SummarizeConfig`.
   No validation of backend name here — the CLI validates it.
4. In `_run_summarize` in `cli.py`:
   - Resolve effective backend: `args.backend` if explicitly set, else
     `config.summarize.backend`.
   - Resolve effective model: `args.model` if set, else `config.summarize.model`
     (empty → each backend uses its own default).
   - Resolve effective base_url (openai only): `args.base_url` if set, else
     `config.summarize.base_url`.
   - Add the new backends to the `if/elif` chain:
     ```python
     elif backend == "openai":
         from docgen.summarize.openai_backend import OpenAISummarizer
         summarizer = OpenAISummarizer(
             model=model or "gpt-4o",
             base_url=base_url or None,
         )
     elif backend == "anthropic":
         from docgen.summarize.anthropic_backend import AnthropicSummarizer
         summarizer = AnthropicSummarizer(model=model or "claude-3-5-sonnet-20241022")
     ```
   - Update the error message to list all valid backends.
5. Add `--model` and `--base-url` flags to the `summarize` subparser.
6. Apply the same backend logic to `_run_update` (only bob_shell / openai / anthropic
   are meaningful there; stub is still the default).
7. Update `docgen.toml` with a commented-out `[summarize]` example:
   ```toml
   # [summarize]
   # backend = "openai"
   # model   = "gpt-4o"
   # base_url = ""   # set to http://localhost:11434/v1 for Ollama
   ```
8. Write `tests/test_config.py` additions (or update the existing test file):
   - Config with no `[summarize]` section → `SummarizeConfig` uses defaults.
   - Config with `[summarize]` section → fields parsed correctly.
   - `--backend` CLI flag overrides `config.summarize.backend`.

**Relevant context:**
- [`src/docgen/config.py`](src/docgen/config.py) — current `Config` and `load_config`
- [`src/docgen/cli.py:243-256`](src/docgen/cli.py:243) — current backend `if/elif` in `_run_summarize`
- [`src/docgen/cli.py:598-619`](src/docgen/cli.py:598) — current `summarize` subparser args

---

## Files to touch

| File | Change |
|---|---|
| `src/docgen/summarize/openai_backend.py` | New — sub-task 1 |
| `src/docgen/summarize/anthropic_backend.py` | New — sub-task 2 |
| `src/docgen/config.py` | Add `SummarizeConfig`, extend `Config`, parse `[summarize]` |
| `src/docgen/cli.py` | Wire new backends in `_run_summarize` + `_run_update`; add `--model`, `--base-url` flags |
| `docgen.toml` | Add commented-out `[summarize]` example |
| `tests/test_openai_backend.py` | New — 5 tests |
| `tests/test_anthropic_backend.py` | New — 5 tests |
| `tests/test_config.py` | Add 3 tests for `SummarizeConfig` parsing |
| `docs/tasks.md` | Add new task entry |
| `docs/memory.md` | Add D-046 |
| `BOB_LOG.md` | Add entry |

**Not touched:** `base.py`, `hierarchy.py`, `prompts.py`, `bob_shell.py`,
`store.py`, `schema.py` — the protocol boundary is already correct and no core
logic changes.

---

## Dependency order

```
Sub-task 1 (OpenAI backend)
    ↓
Sub-task 2 (Anthropic backend)   ← can be done in parallel with 1, but 1 is the template
    ↓
Sub-task 3 (config + CLI wiring) ← needs both backends to exist before wiring them in
```

Sub-tasks 1 and 2 are independent of each other; sub-task 3 requires both.

---

## Key design decisions (confirmed — do not re-debate)

| Decision | Detail |
|---|---|
| Optional deps | `openai` and `anthropic` imported inside `__init__`; `ImportError` → clear message; not in `pyproject.toml` |
| Ollama / vLLM | Handled by `OpenAISummarizer(base_url="http://...")` — no separate class |
| Config precedence | CLI flag > `[summarize]` config > backend default |
| `max_tokens` | Anthropic requires it; OpenAI does not. Anthropic default: 4096 |
| Retry pattern | 2 attempts, 5s backoff — same as `BobShellSummarizer` |
| `SummarizeConfig` defaults | `backend="stub"` — no breaking change for existing users |
