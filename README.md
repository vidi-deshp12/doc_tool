# docgen

A tool that reads an undocumented Python repository and produces **trustworthy, cited documentation that stays current**: architecture overview, module pages, API endpoint table, and dependency diagram. It detects when docs have drifted from the code and updates only the pages that need it.

Built with [IBM Bob](https://bob.ibm.com) as part of IBM Hackathon 2026 — Theme 1.

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -e ".[dev]"
```

## Run tests

```bash
pytest
```

## Usage

```bash
docgen extract    # extract facts from the target repo
docgen summarize  # generate cited summaries
docgen render     # render documentation pages
docgen check      # detect doc drift (exit 1 if stale)
docgen update     # regenerate stale pages only
docgen eval       # run the evaluation harness
```

Configure the target repo in [`docgen.toml`](docgen.toml).

## Project docs

- [`docs/PRD.md`](docs/PRD.md) — requirements
- [`docs/architecture.md`](docs/architecture.md) — design
- [`docs/tasks.md`](docs/tasks.md) — task list
- [`docs/memory.md`](docs/memory.md) — decisions and bugs
- [`docs/BOB_LOG.md`](docs/BOB_LOG.md) — Bob usage log
