# Plan: Pluggable LLM Backends

**Status:** implemented 2026-11-21, including the review amendments recorded in the
[Planning and review log](#planning-and-review-log). The predecessor
[`docs/plan-retry-and-failure-recovery.md`](plan-retry-and-failure-recovery.md) landed: `BackendError`,
`FatalBackendError`, `RetryPolicy`, and `RetryGate` live in `base.py`, the driver owns retries, and
every backend makes exactly one classified attempt.

## Planning and review log

Append-only record of how this plan changed. Newest entries at the bottom. Each entry names the
trigger, the decisions, and where they landed, so an implemented detail can be traced back to the
planning step that asked for it. Later revisions get a new entry; earlier entries are not rewritten.

### 2026-11-21 — v1: initial API-first plan

- Scope: three new backends (`claude_shell`, `openai`, `anthropic`), `[summarize]` config, a
  backend registry, CLI precedence, docs, tests; no new dependencies.
- `openai` was the public default for CI and teams; `anthropic` was the native Claude API adapter.
- `claude_shell` was planned as the Claude Code/subscription adapter, but v1 did not yet make it
  this project's required runnable path and did not activate it in `docgen.toml`.
- Open issues the review would later catch: cache identity did not cover the `claude_shell` system
  prompt, the `Summarizer` protocol had no `context_limit`, and concurrent workers had no
  backend-specific warning.

### 2026-11-21 — v2: make `claude_shell` required

**Trigger:** the user has Claude Pro but no Bob subscription and no API key. The full pipeline must
run on the subscription, so `claude_shell` cannot be an optional convenience.

- `claude_shell` promoted to a required, first-class backend. Public docs keep the
  "local/interactive, uses your subscription" framing, but it is the reference path for this
  project.
- `docgen.toml` gets an active `[summarize]` block (`backend = "claude_shell"`, `model = "sonnet"`,
  `timeout = 180`).
- Done-when gains the 234-node Claude Pro run, `docgen validate`, and the zero-call replay.
- Usage budget measured from the existing `generated/` output and added here (~0.3-0.4M tokens for
  a full lean run; 2.3M+ extra without `--safe-mode`, `--tools ""`, and `--system-prompt`).
- Lean invocation, stdin prompt transport, subscription-only auth, and fatal plan limits become
  hard rules.

### 2026-11-21 — v3: external review amendments

**Trigger:** review of v2 (Claude, pasted by the user). All points were accepted; none were
rejected.

| # | Review point | Decision | Landed in |
|---|---|---|---|
| R-1 | The `claude_shell` system prompt is sent outside `build_prompt`, so editing it would not change the cache key and stale prose could be reused. | Hash the system prompt into `name`: `claude_shell:<model>:<sha256(prompt)[:8]>`. | Cache identity; sub-task 2; `claude_shell.py`; tests 9 and 13 |
| R-2 | `Summarizer` has no way to report a context limit, so backends cannot share overflow policy. | Add `context_limit: int \| None`; 200k for Claude, 8k local / 128k hosted for `openai`, `None` for stub/manual/Bob. | Design; sub-tasks 2-4; files table; `base.py`, `manual.py`, `bob_shell.py` |
| R-3 | `--workers > 1` with a subscription backend can burn the allowance faster with no warning. | Print a `WARN` at construction naming the backend and recommending `--workers 1`; not an error, output stays deterministic. | Sub-task 2 item 5; test 14 |
| R-4 | Add contract tests for failure modes that are easy to fake: prompt on stdin (not argv), key redaction, `URLError` as transient, and the Windows `.cmd` command as a pure function. | All added and mocked at the boundary. | Sub-tasks 2-4 test lists; the four new test modules |
| R-5 | Verify the Gemini compatibility URL and model before publishing them. | README and plan mark Gemini as "verify the current free model"; no unverified model is presented as guaranteed. | Sub-task 5; README matrix |
| R-6 | Implement in dependency order, with `claude_shell` on the critical path. | Registry/config first, then `claude_shell`, then the independent HTTP adapters, then docs and full verification. | Dependency order section |

### 2026-11-21 — v3.1: implementation follow-ups

- `ClaudeShellSummarizer` now stores one `_system_prompt` snapshot and uses it for both the cache
  hash and the argv value, so the key cannot describe a different prompt than the one sent.
- Added the missing `--workers 2` warning test (plan test 14): 68 focused tests, full suite 325
  passed + the known seeded failure.
- Added `base.py`, `manual.py`, and `bob_shell.py` to the files table, because the protocol change
  touched them.
- Live verification is still open: `claude` is not installed on this machine. The intended sequence
  is recorded in sub-task 5 (5-node fixture, `/usage`, full 234 at one worker, `docgen validate`,
  zero-call replay), but there is no live result yet.

### Entry template

```markdown
### YYYY-MM-DD — vN: <short title>

**Trigger:** what changed or what review prompted this revision.

- Decision and where it landed.

**Result:** implemented / deferred / rejected, and what verification followed.
```

---

## Goal

Make `docgen summarize` and `docgen update` work with the model access users actually have, without
adding a mandatory dependency or a per-vendor class:

1. **`claude_shell`** — Claude Code CLI in non-interactive mode, using a Claude Pro/Max
   subscription. **Required, not optional.** This project has Claude Pro and no Bob subscription and
   no API key, so `claude_shell` is the only backend that can run the full pipeline here. It is a
   first-class backend, not a convenience extra.
2. **`openai`** — stdlib HTTP to any OpenAI-compatible Chat Completions endpoint. One adapter covers
   OpenAI, Groq, Gemini's compatibility endpoint, OpenRouter, Together, DeepSeek, Mistral, xAI,
   Azure/LiteLLM gateways, Ollama, LM Studio, llama.cpp, and vLLM.
3. **`anthropic`** — stdlib HTTP to the Anthropic Messages API for users with an API key.
4. **`[summarize]` config + backend registry + CLI precedence** so a user sets a default once and
   overrides it per run.

`stub`, `manual`, and `bob_shell` stay as they are. `bob_shell` is no longer the reference backend.

**Done when:**

- `docgen summarize --backend claude_shell --model sonnet` completes the demo repo (234 calls) under
  Claude Pro, `docgen validate` passes, and an immediate re-run makes **zero** summarizer calls.
- `docgen summarize --backend openai --base-url http://localhost:11434/v1 --model qwen2.5-coder:7b`
  works against local Ollama with no API key.
- `docgen summarize --backend openai` works with `OPENAI_API_KEY` against the default endpoint.
- `docgen summarize --backend anthropic` works with `ANTHROPIC_API_KEY`.
- `docgen.toml` `[summarize]` supplies backend / model / base-url / timeout; CLI flags win; an absent
  section keeps the current `stub` default.
- All new code is covered by tests that mock `urllib.request.urlopen` or `subprocess.run`; no test
  makes a network call or launches Claude.
- A Claude usage-limit or auth failure exits 2 with the checkpoint intact; a transient failure is
  retried by the existing driver.
- The README tells a new user which command to run for the access they have.

**Hard rules:**

- **No new dependencies.** `openai` and `anthropic` SDKs are not used, not optional extras, not
  imported. HTTP is `urllib.request`; the shell backend is `subprocess`.
- Backends make **one** attempt and raise `BackendError`; `hierarchy._call_summarizer` owns retries.
- Never log, store, or commit an API key or OAuth token. `docgen.toml` holds env-var **names** only.
- `claude_shell` removes `ANTHROPIC_API_KEY` from the child environment. It must use the Claude
  subscription, never silently bill the API; API-key users select `--backend anthropic`.
- Do not use `claude --bare`: it ignores `CLAUDE_CODE_OAUTH_TOKEN`.
- Send prompts on stdin or through a temp file, never on the command line. The largest measured
  prompt is 69,374 chars, above the 32 KB Windows command-line limit.

---

## Usage budget on Claude Pro (measured, not estimated)

Measured from the current `generated/` output by rebuilding every prompt through
`build_prompt` (the same 234 calls the Bob run made):

| Metric | Value |
|---|---|
| Summarizer calls (233 nodes + system) | 234 |
| Prompt text, total | 918,240 chars |
| Prompt chars, avg / median / p90 / max | 3,924 / 2,780 / 5,687 / 69,374 |
| Output text, total | 293,387 chars |
| Output chars, avg / max | 1,254 / 10,941 |
| Input tokens at 3.5-4.2 chars/token | ~219k-262k |
| Output tokens at 3.5-4.2 chars/token | ~70k-84k |
| **Total per full run** | **~290k-346k tokens** |
| Lean CLI overhead (100-300 tokens x 234) | +23k-70k |
| **Expected total with lean flags** | **~315k-415k tokens** |

What this means:

- **The payload is the same one Bob saw.** `0.009 Bobcoins/call` is a price unit, not a token
  count. Per call the prompts are ~1,000-1,100 input tokens and the summaries ~300-360 output
  tokens. Claude does not multiply that. The difference is that Claude Pro has a usage cap instead
  of a per-call price.
- **The blow-up risk is Claude Code's default agent scaffolding, not the docgen prompt.** Without
  `--safe-mode`, `--tools ""`, and `--system-prompt`, each call carries the coding-agent prompt and
  tool schemas (roughly 10k+ extra tokens). 234 calls then costs **2.3M+ extra tokens**, which is
  the scenario that hits a Pro limit. The lean invocation is not an optimisation; it is required
  for this workload.
- **A fresh 5-hour window should absorb ~0.4M tokens, but this is not guaranteed.** Anthropic does
  not publish Pro's token allowance, and the 5-hour and weekly caps are shared with claude.ai and
  other Claude Code sessions. If the window is already partly used, the run can stop partway.
- **Stop early, measure, then continue.** Run 5 nodes first (a small fixture repo), check
  `/usage`, then run the full repo. Keep `--workers 1`: concurrency does not increase the
  allowance and makes a limit arrive sooner. The existing 25-node checkpoints mean a limit hit
  loses at most the current slice.
- **A limit hit is fatal, not retryable.** `claude_shell` raises `BackendError(transient=False,
  fatal=True)`; the CLI exits 2 and the checkpoint stays. Rerun after the reset; cached nodes are
  skipped by the prompt-hash key.
- **Development re-runs are cheap.** Only changed nodes call the model. The first full run is the
  expensive one; later runs are normally a handful of calls.

The 69 KB maximum prompt is the synthetic system node (all package summaries). At ~4 chars/token
that is ~17k tokens, well inside Claude's context window; the only reason it matters is Windows
argv length, hence stdin.

---

## Design

Two API shapes cover the market; one CLI covers a subscription:

| Backend | Transport | Covers | Role |
|---|---|---|---|
| `claude_shell` | subprocess `claude -p` | Claude Pro / Max | **Required local path for this project** |
| `openai` | HTTP Chat Completions, configurable `base_url` and key env | OpenAI, Groq, Gemini compat, OpenRouter, Together, DeepSeek, Mistral, xAI, Ollama, LM Studio, llama.cpp, vLLM, LiteLLM/Azure gateways | Broadest API coverage; default for CI/teams |
| `anthropic` | HTTP Messages API | Claude API | Paid Claude API users |
| `bob_shell` | subprocess | IBM Bob | Legacy/hackathon; keep, do not lead with it |
| `stub`, `manual` | none | — | Tests, offline, hand-written prose |

Why not one class per vendor: Groq, Gemini, OpenRouter, Together, DeepSeek, Mistral, xAI, Ollama,
LM Studio, llama.cpp, vLLM, and most corporate gateways all speak OpenAI Chat Completions. A vendor
class would duplicate the same request, parse, and error mapping. Anthropic is the one materially
different shape, so it gets the second adapter.

Why `claude_shell` is still required even though API-first is the right public architecture: it is
the only path this project can run today, and it is the cheapest on-ramp for an individual with
Pro. The public docs should present it as "local/interactive, uses your subscription", not as the
CI recommendation.

### `claude_shell` invocation

```text
claude -p
  --output-format json
  --safe-mode
  --no-session-persistence
  --tools ""
  --disallowedTools "mcp__*"
  --system-prompt "<short writer instruction>"
  --model sonnet
```

| Flag | Reason |
|---|---|
| `-p` | Non-interactive; reads the prompt from stdin and exits. |
| `--output-format json` | One JSON object: `result`, `is_error`, `subtype`, `usage`, `session_id`. |
| `--safe-mode` | Disables CLAUDE.md, skills, plugins, hooks, MCP, memory, and subagents while keeping auth, model, built-in tools, and permissions. Critical for both token cost and isolation. |
| `--no-session-persistence` | Avoids 234 transcript files. |
| `--tools ""` | No Read/Bash/Edit; the model only writes prose. |
| `--disallowedTools "mcp__*"` | `--tools` does not cover MCP; safe mode already disables MCP, this is belt-and-braces. |
| `--system-prompt` | Replaces the large coding-agent prompt. The docgen prompt already contains its own preamble and rules. |
| `--model sonnet` | Stable alias; `haiku` for smoke tests. Never hardcode a dated model ID. |

Auth: run `claude auth status` once in `__init__`, with `ANTHROPIC_API_KEY` removed from the
environment. Accept `authMethod` `claude.ai` (interactive login) or `oauth_token`
(`claude setup-token` -> `CLAUDE_CODE_OAUTH_TOKEN`). `none`, `api_key`, `api_key_helper`, or
`third_party` is a fatal construction error with instructions:

```text
Claude Code is not logged in with a Claude subscription.
Run `claude auth login` with your Pro/Max account, or set CLAUDE_CODE_OAUTH_TOKEN
from `claude setup-token`. claude_shell deliberately ignores ANTHROPIC_API_KEY;
use --backend anthropic for API-key billing.
```

On Windows, prefer the native `claude.exe` (`%USERPROFILE%\.local\bin\claude.exe`). `subprocess.run`
with `input=prompt` and `capture_output=True` is safe for a real `.exe`. If `shutil.which` resolves
a `.cmd` wrapper (npm install), reuse the Bob pattern: temp prompt file, PowerShell
`Get-Content -Raw | & claude ...`, stdout to a temp file, cleaned in `finally`.

### Error classification

| Failure | `transient` | `fatal` | Result |
|---|---|---|---|
| Executable missing | false | true | Exit 2 |
| Not logged in / wrong auth method | false | true | Exit 2 |
| 5-hour or weekly usage limit reached | false | true | Exit 2, checkpoint kept |
| Model not found / unsupported flag | false | true | Exit 2 |
| Timeout, connection reset, overloaded, 5xx | true | false | Driver retries |
| Generic 429 / rate limit | true | false | Driver retries with backoff |
| Invalid JSON, empty `result` | true | false | Driver retries |
| Context overflow (400) | false | false | Placeholder for that node |
| Output truncated (`finish_reason=length`) | false | false | Placeholder for that node |

Distinguish a **plan limit** from a **rate limit**: Claude Code's plan-limit text contains
`limit reached` and mentions a reset window; that is fatal. A generic 429 or `overloaded` is
transient.

### Cache identity

`hierarchy._summarizer_identity` uses the optional `name` attribute. Every new backend sets one:

- `claude_shell:<model>:<sha256(_SYSTEM_PROMPT)[:8]>` — the system prompt is sent
  outside `build_prompt`, so hashing it into `name` is what makes an edit there
  invalidate cached summaries.
- `openai:<normalized base_url>:<model>`
- `anthropic:<model>`

The API key is never part of the name. Switching from `sonnet` to `haiku`, or from OpenAI to
OpenRouter, must not reuse the other's prose.

---

## Sub-task 1 — Backend registry, `[summarize]` config, CLI precedence

**Intent:** One construction point and one settings resolver, so adding a backend is a factory entry
rather than another `if/elif` branch, and so config defaults work without breaking the current
`stub` default.

**Files:** `src/docgen/config.py`, `src/docgen/cli.py`, `docgen.toml`, `tests/test_config.py` (new).

1. Add `SummarizeConfig`:

   ```python
   @dataclass(frozen=True)
   class SummarizeConfig:
       backend: str = "stub"
       model: str = ""
       base_url: str = ""
       api_key_env: str = ""
       timeout: int = 0  # 0 -> backend default
   ```

2. Add `summarize: SummarizeConfig` to `Config`; parse `data.get("summarize", {})` in
   `load_config`. Validate only types/ranges here (`timeout >= 0`); the CLI validates the backend
   name so the error can list the registry.
3. In `cli.py`, add a `_resolve_summarize_settings(args, config)` helper:
   - backend: `args.backend` if not `None`, else `config.summarize.backend`, else `"stub"`.
   - model / base_url / api_key_env: CLI value if non-empty, else config, else `""`.
   - timeout: CLI if non-zero, else config, else `0`.
   - `--backend` **must default to `None`**, not `"stub"`; otherwise CLI-over-config precedence is
     impossible.
4. Add `--model`, `--base-url`, `--api-key-env`, `--timeout` to `summarize` **and** `update`. Keep
   `--backend` on both. Use a shared parent parser if one already exists, otherwise add the same
   arguments to both.
5. Replace the backend `if/elif` in `_build_summarizer` with a registry:

   ```python
   _BACKENDS = ("stub", "manual", "bob_shell", "claude_shell", "openai", "anthropic")
   ```

   Lazy-import each class inside its factory. Wrap every construction in one
   `try/except BackendError` that re-raises fatal errors as `FatalBackendError(name, exc)`, so a
   missing key/executable is handled the same way for every backend.
6. `_run_summarize` and `_run_update` both pass `config` into `_build_summarizer`. `_run_update`'s
   "real backend" gate includes `claude_shell`, `openai`, `anthropic`, and `bob_shell`.
7. Unknown backend message: `Unknown backend 'x' (expected one of: stub, manual, bob_shell,
   claude_shell, openai, anthropic).`
8. `docgen.toml`: add an active `[summarize]` block for this repo, because `claude_shell` is the
   only runnable backend here:

   ```toml
   [summarize]
   backend = "claude_shell"
   model = "sonnet"
   timeout = 180
   ```

   Include commented `openai` / `anthropic` examples in the README, not as active config.

**Tests (new `tests/test_config.py`, ~6):**

- No `[summarize]` -> defaults (`backend="stub"`, empty strings, timeout 0).
- Full `[summarize]` -> fields parsed.
- CLI `--backend` overrides config; config overrides default.
- CLI `--model` / `--base-url` override config; empty CLI values do not.
- Unknown backend -> `SystemExit` listing the valid names.
- `timeout < 0` -> `ValueError`.

---

## Sub-task 2 — `claude_shell` (critical path)

**Intent:** The full pipeline must run on Claude Pro before anything else. This is the reference
backend for the rest of the project.

**Files:** `src/docgen/summarize/claude_shell.py` (new), `tests/test_claude_shell.py` (new).

1. `class ClaudeShellError(BackendError)`.
2. `ClaudeShellSummarizer.__init__(model="sonnet", timeout=180, claude_exe=None)`:
   - `name = f"claude_shell:{model}:{sha256(_SYSTEM_PROMPT)[:8]}"`, and
     `context_limit = 200_000`. The hash covers the one input not present in
     `build_prompt`, so editing the system prompt cannot silently reuse prose.
   - Resolve the executable: `shutil.which("claude")`, `shutil.which("claude.cmd")`,
     `%USERPROFILE%\.local\bin\claude.exe`, `~/.local/bin/claude`. Missing -> fatal.
   - Run `claude auth status` with `env = {k: v for k, v in os.environ.items() if k !=
     "ANTHROPIC_API_KEY"}`. Parse JSON; require `authMethod in {"claude.ai", "oauth_token"}`.
     `returncode != 0`, unparseable output, `none`, `api_key`, `api_key_helper`, or `third_party`
     -> fatal with the message above.
   - Store the executable, model, timeout. Check auth once, not per call.
3. `summarize(req)`:
   - `prompt = build_prompt(req)`.
   - Build the argument list with the flags above. The system prompt is short:
     `"You are a careful technical writer. Follow the instructions in the user message exactly.
     Do not use tools."`
   - Child env: copy `os.environ`, remove `ANTHROPIC_API_KEY`, keep `CLAUDE_CODE_OAUTH_TOKEN`.
   - `.exe`: `subprocess.run(argv, input=prompt, capture_output=True, text=True,
     encoding="utf-8", timeout=self._timeout, env=env)`.
   - `.cmd`: temp prompt + PowerShell pipe + temp stdout, mirroring `bob_shell`'s Windows fix;
     delete both files in `finally`.
   - Timeout -> `ClaudeShellError(..., transient=True)`.
   - Non-zero exit: inspect stderr for fatal markers (auth, not logged in, model not found,
     `limit reached`, `usage limit`); otherwise transient.
   - Parse stdout as JSON. If a warning line precedes the object, try the last non-empty line.
     `is_error` true -> classify by the error text (`limit reached` fatal, otherwise transient).
     Missing or non-string `result` -> transient.
   - Return `SummaryResult(node_id=req.node_id, text=result,
     backend=f"claude_shell:{self.model}", hash_input=hash_input(req))`.
4. Do not pass `--max-turns`: with no tools there is no loop, and a low turn cap can turn a
   successful answer into an error. Do not pass `--bare` or `--dangerously-skip-permissions`.
5. Thread safety: every call owns its temp files and subprocess. The driver defaults to one worker.
   `_build_summarizer` prints a WARN when `claude_shell` is selected with `--workers > 1`: Pro limits
   are per account, concurrency does not add allowance, and the warning must appear before the run
   rather than after a limit hit. It is not an error — output stays deterministic.

**Tests (~10, all mocked):**

1. Missing executable -> fatal.
2. `auth status` `none` -> fatal; message mentions `claude auth login`.
3. `auth status` `api_key` -> fatal (subscription required).
4. `auth status` `claude.ai` / `oauth_token` -> constructs.
5. Child environment has no `ANTHROPIC_API_KEY` and keeps `CLAUDE_CODE_OAUTH_TOKEN`.
6. Argv contains `-p`, `--output-format json`, `--safe-mode`, `--no-session-persistence`,
   `--tools ""`, `--disallowedTools "mcp__*"`, `--model sonnet`, `--system-prompt`.
7. The prompt is on stdin, not argv: assert the prompt text is absent from the argument list and
   present in `subprocess.run(input=...)`. This is the large-prompt correctness guarantee.
8. Windows `.cmd`: a pure-function test of `_powershell_command` shows `Get-Content` over a prompt
   file and no prompt text in the command string.
9. Successful JSON -> correct `SummaryResult`, exactly one `subprocess.run` call; changing
   `_SYSTEM_PROMPT` changes `name` (cache invalidation).
10. `is_error` / non-zero exit -> one attempt, `BackendError`; no internal retry.
11. `limit reached` -> `fatal=True`, `transient=False`.
12. Timeout / invalid JSON / empty `result` -> `transient=True`, `fatal=False`.
13. `name` starts with `claude_shell:sonnet:` and the suffix is an 8-char system-prompt hash.
14. `--workers 2` with `claude_shell` prints a WARN naming the backend (not an error).

**Opt-in live test:** `DOCGEN_LIVE_CLAUDE=1 pytest tests/test_claude_shell.py -k live` summarizes
two nodes from a fixture and asserts every citation in the result is in the allowed ID set. Skipped
by default; no live call in CI.

---

## Sub-task 3 — OpenAI-compatible backend (stdlib HTTP)

**Intent:** One adapter for every provider that speaks Chat Completions, including local servers.
This is the public default for CI and teams.

**Files:** `src/docgen/summarize/openai_backend.py` (new), `tests/test_openai_backend.py` (new).

1. `class OpenAIError(BackendError)`.
2. `OpenAISummarizer(model="gpt-4o-mini", base_url=None, api_key=None,
   api_key_env="OPENAI_API_KEY", timeout=120, max_tokens=None)`.
   - `name = f"openai:{normalized_base_url}:{model}"`; `context_limit = 8_192` for a local
     base URL, `128_000` for a hosted one.
   - Default endpoint: `https://api.openai.com/v1`; normalize a trailing `/`; append
     `/chat/completions`.
   - Key resolution: explicit `api_key` -> `os.environ.get(api_key_env or "OPENAI_API_KEY")`.
   - No key:
     - local base URL (`localhost`, `127.0.0.1`, `0.0.0.0`, `::1`) -> dummy `"local"`.
     - any other explicit base URL -> fatal naming the env var (gateways still need a key).
     - default OpenAI endpoint -> fatal naming `OPENAI_API_KEY`.
3. `summarize(req)`:
   - `build_prompt(req)`, POST JSON:
     `{"model": ..., "messages": [{"role": "user", "content": prompt}], "temperature": 0}` plus
     `max_tokens` when set.
   - Headers: `Content-Type: application/json`, `Authorization: Bearer <key>`.
   - `urllib.request.urlopen(request, timeout=self._timeout)`.
   - Parse `choices[0].message.content`; empty -> `OpenAIError` (transient).
   - `finish_reason == "length"` -> `transient=False, fatal=False` (truncated summary; placeholder).
4. Error mapping:
   - `HTTPError` 401/403 -> fatal auth.
   - 404 -> fatal endpoint/model.
   - 400 with a context/length/token marker -> `transient=False, fatal=False`; other 400 -> fatal
     (bad request is configuration).
   - 429 -> transient; `retry_after` from the `Retry-After` header via `parse_retry_after`.
   - 5xx -> transient.
   - `URLError`, socket timeout -> transient.
   - Include the provider's `error.message` in `BackendError.message`; never include the key.
5. Return `SummaryResult(..., backend=f"openai:{self.model}", ...)`.

**Tests (~7, mock `urlopen`):**

- No key on the default endpoint -> fatal before network.
- Local base URL without a key -> request uses the dummy key.
- Request body contains model/messages/temperature; URL is `<base>/chat/completions`.
- Success -> correct `SummaryResult`; one call.
- 429 with `Retry-After: 17` -> `transient=True`, `retry_after=17`.
- 401 -> fatal; 400 context overflow -> non-transient, non-fatal.
- `finish_reason == "length"` -> non-transient error.
- `URLError` / socket timeout -> `transient=True`.
- A provider error that echoes the key is redacted: assert the key is absent from `BackendError.message`.
- `name` includes model and base URL (and changes when either changes).

---

## Sub-task 4 — Anthropic API backend (stdlib HTTP)

**Intent:** Native Claude API for users who have an API key. Keep it thin; the OpenAI compatibility
endpoint is an alternative, but native is the reliable primary for Claude.

**Files:** `src/docgen/summarize/anthropic_backend.py` (new), `tests/test_anthropic_backend.py`
(new).

1. `class AnthropicError(BackendError)`.
2. `AnthropicSummarizer(model="claude-sonnet-4-5", api_key=None,
   api_key_env="ANTHROPIC_API_KEY", max_tokens=4096, timeout=120)`.
   - `name = f"anthropic:{model}"`; `context_limit = 200_000`.
   - Missing key -> fatal before any network call, naming `ANTHROPIC_API_KEY` (or the configured
     env var).
3. `summarize(req)`:
   - POST `https://api.anthropic.com/v1/messages`.
   - Headers: `x-api-key`, `anthropic-version: 2023-06-01`, `content-type: application/json`.
   - Body: `{"model", "max_tokens": 4096, "temperature": 0,
     "messages": [{"role": "user", "content": build_prompt(req)}]}`.
   - Send the whole prompt as one user message. Do not add a separate system message: the prompt
     hash must describe the model's entire input.
   - Parse the first `type == "text"` content block.
4. Error mapping: 401/403 fatal; 404 fatal model; 400 context -> non-transient/non-fatal; 429 and
   529 `overloaded_error` -> transient with `retry_after`; other 5xx transient; network/timeout
   transient.
5. Return `SummaryResult(..., backend=f"anthropic:{self.model}", ...)`.

**Tests (~6, mock `urlopen`):**

- Missing key -> fatal before network.
- Request headers/body/URL are correct; `max_tokens` present.
- Success -> first text block, correct `SummaryResult`, one call.
- 429/529 -> transient with `Retry-After`.
- 401 -> fatal; 400 context -> non-transient, non-fatal.
- `name == "anthropic:<model>"`; a provider error that echoes the key is redacted from
  `BackendError.message`.

---

## Sub-task 5 — Docs, quickstart, full verification

**Intent:** A user should pick their access from a table and run one command. Also record the
measured Claude budget so the next person does not guess.

1. `README.md` — replace the "requires IBM Bob" setup section with a backend matrix:

   | Access | Command |
   |---|---|
   | Claude Pro/Max | install Claude Code, `claude auth login`, then `docgen summarize --backend claude_shell --model sonnet` |
   | Ollama | `ollama pull qwen2.5-coder:7b`, then `docgen summarize --backend openai --base-url http://localhost:11434/v1 --model qwen2.5-coder:7b` |
   | Groq | `OPENAI_API_KEY=... docgen summarize --backend openai --base-url https://api.groq.com/openai/v1 --model openai/gpt-oss-120b` |
   | Gemini | `OPENAI_API_KEY=... --base-url https://generativelanguage.googleapis.com/v1beta/openai/ --model gemini-2.5-flash` (verify the current free model) |
   | OpenRouter | `OPENAI_API_KEY=... --base-url https://openrouter.ai/api/v1 --model <model>:free` |
   | OpenAI | `OPENAI_API_KEY=... docgen summarize --backend openai --model gpt-4o-mini` |
   | Anthropic API | `ANTHROPIC_API_KEY=... docgen summarize --backend anthropic` |

   Add a short "Claude Pro usage" note: 234 calls, ~0.3-0.4M tokens with the lean flags, start with
   a small repo, check `/usage`, keep one worker, checkpoints make a limit hit resumable.

2. `docs/architecture.md` — backend section: two protocol adapters + shell backends, single-attempt
   contract, cache identity.
3. `docs/tasks.md` — add task `2b.10` with the five sub-tasks.
4. `docs/memory.md` — add `D-049`: API-first backend architecture; `claude_shell` required for this
   project; no SDK dependencies; cache identity includes backend/model/base URL.
5. `docs/BOB_LOG.md` — add the session entry. The file is the project log even though this work is
   not done with Bob; say so explicitly.
6. `docgen.toml` — active `[summarize]` block as in sub-task 1.
7. Full verification:
   - `pytest tests/test_claude_shell.py tests/test_openai_backend.py
     tests/test_anthropic_backend.py tests/test_config.py -q`
   - The full suite; the known seeded bug (`tests/test_seeded_bug.py`) is the only allowed failure.
   - Live: 5 nodes from a fixture, check `/usage`, then the full 234. `docgen validate`; immediate
     re-run must print 0 calls; `docgen update` on an unchanged repo must not call.
   - If the run stops on a usage limit, confirm `summaries.json` contains the completed slices and
     rerunning skips them.

---

## Files to touch

| File | Change |
|---|---|
| `src/docgen/summarize/claude_shell.py` | New — required Claude Pro backend |
| `src/docgen/summarize/openai_backend.py` | New — stdlib OpenAI-compatible HTTP |
| `src/docgen/summarize/anthropic_backend.py` | New — stdlib Anthropic Messages HTTP |
| `src/docgen/summarize/base.py` | Protocol `context_limit`; `StubSummarizer` sets it to `None` |
| `src/docgen/summarize/manual.py`, `bob_shell.py` | `context_limit = None` only |
| `src/docgen/config.py` | `SummarizeConfig`, `Config.summarize`, parse `[summarize]` |
| `src/docgen/cli.py` | Registry, settings resolver, new flags, wire `summarize` + `update` |
| `docgen.toml` | Active `[summarize]` block |
| `tests/test_config.py` | New — config parsing + precedence |
| `tests/test_claude_shell.py` | New — ~10 mocked tests + 1 opt-in live test |
| `tests/test_openai_backend.py` | New — ~7 mocked tests |
| `tests/test_anthropic_backend.py` | New — ~6 mocked tests |
| `README.md` | Backend quickstart + Claude Pro usage note |
| `docs/architecture.md` | Backend section |
| `docs/tasks.md` | Task 2b.10 |
| `docs/memory.md` | D-049 |
| `docs/BOB_LOG.md` | Session entry |

**Outside the three new backends:** `base.py` gains the protocol's `context_limit` attribute (and
`stub`/`manual`/`bob_shell` set it to `None`); `bob_shell.py` changes only for that attribute.
`hierarchy.py`, `prompts.py`, `store.py`, and `schema.py` are untouched: the protocol boundary,
retry loop, prompt builder, and cache key stay as they are.

---

## Dependency order

```text
Sub-task 1 (registry + config + CLI)
        |
        v
Sub-task 2 (claude_shell)  <-- critical path; full pipeline runs here
        |
        +--> Sub-task 3 (openai)      (independent of 2; needs 1)
        |
        +--> Sub-task 4 (anthropic)   (independent of 2; needs 1)
        |
        v
Sub-task 5 (docs + full verification)
```

Sub-tasks 3 and 4 can be done in parallel after 1. Sub-task 2 comes first because it is the only
backend that can be verified live in this environment.

---

## Key design decisions (confirmed — do not re-debate)

| Decision | Detail |
|---|---|
| No SDKs | `urllib.request` and `subprocess` only; `pyproject.toml` dependencies stay empty |
| `claude_shell` is required | It is the project's only live backend (Claude Pro, no Bob, no API key) |
| Two protocol adapters | OpenAI-compatible + Anthropic Messages; no per-vendor classes |
| Local servers | `openai` with `--base-url`; dummy key for localhost |
| Config precedence | CLI flag > `[summarize]` > backend default |
| Retry | Backends make one attempt; the driver owns retries and `Retry-After` |
| Cache identity | `name` includes backend, model, and base URL; never the key |
| Secrets | Env vars only; `docgen.toml` stores variable names |
| Claude auth | Subscription only; `ANTHROPIC_API_KEY` stripped from the child env |
| Claude prompt transport | stdin/temp file, never argv |
| Concurrency | Default one worker; Pro limits are per account and concurrency does not add allowance |

## Non-goals

- Azure OpenAI, Bedrock, or Vertex native authentication. Use an OpenAI-compatible gateway or
  `--base-url`; add a dedicated backend only if users ask.
- Streaming responses. Summaries are short and non-interactive.
- Plugin entry points or third-party installable backends. A registry dict is enough.
- Parallel summarization. It does not increase a subscription allowance and makes limits arrive
  sooner.
- Changing hashing, citation validation, rendering, or drift detection.
- Removing `bob_shell`; it stays available for anyone who still has Bob.
