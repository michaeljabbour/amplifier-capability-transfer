# AGENTS.md — amplifier-bundle-genetransfer

**What this repo is:** a self-contained Amplifier bundle packaging **HGT**
(Horizontal Gene-Transfer) — a parameterized attractor that transfers a capability
from a donor repo into one or more host repos, re-expressed through each host's own
seams, gated by unit tests + a real-terminal forge check, one PR per capability.

**Read `PRINCIPLES.md` before changing behavior** — the non-negotiables (never copy
donor code; the forge check is the acceptance oracle; gate == CI; never a protected
branch) live there, not here.

## Key directories
| Path | What |
|---|---|
| `bundle.md` | Root bundle (thin; includes `hgt:behaviors/hgt-core`) |
| `behaviors/hgt-core.yaml` | The composable capability set (tools, mode system, agents, awareness) |
| `bundles/` | Launchers: `hgt-pipeline` (headless), `hgt-interactive` (run_pipeline) |
| `agents/` | `hgt-orchestrator` (executes a run), `hgt-expert` (explains/plans) |
| `modes/hgt.md` | The `/hgt` orchestrator-posture mode (auto-discovered) |
| `context/` | `hgt-awareness.md` (thin, always) · `hgt-runbook.md` (heavy, on-demand) |
| `pipelines/` | `hgt.dot` (the attractor graph) · `ledger.py` (stdlib transfer ledger) |
| `examples/opencode/` | Worked instance: opencode → newtui (py) + newtui-rust |
| `docs/DESIGN_DECISIONS.md` | Why the graph is shaped this way (param + gate-parity calls) |

## Verification gradient (before a PR)
- **Structural:** `graphviz` parses `pipelines/hgt.dot`; `python3 pipelines/ledger.py stats` runs.
- **Eval:** `python3 evals/hillclimb.py --self-test && python3 evals/hillclimb.py --fixture` (the hill-climbing eval and its regression detector both pass).
- **Conformance:** `/audit-bundle` (conformance auditor) + the `validate-bundle-repo` recipe.
- **Live run** (required when touching the graph/orchestration): drive HGT against a
  scratch source+host and confirm one capability transfers green end-to-end.
- Regenerate `bundle.dot`/`bundle.png` via the `bundle-to-dot` skill before the PR.
- Regenerate the pipeline doc diagrams after any graph change: `python3 docs/diagrams/generate.py` (derived views; the executable graphs in `pipelines/` are never edited by it).

## Pitfalls
- NEVER remove `hooks-logging` from the behavior: it is what makes sessions durable (creates the session dir + events.jsonl). Without it `amplifier run` finishes but persists nothing and errors `Session '<id>' not found` at finalize — found via DTU reality check.
- Params reach `tool_command` only via env vars / run_pipeline, **not** the mounted
  orchestrator's `config.params` (see DESIGN_DECISIONS.md). The graph uses `${VAR:?}`.
- Never remove the `... && printf pass || printf fail` idiom from a gate node — a
  non-zero exit leaves `tool.last_line` stale and misroutes.
- `hgt-orchestrator` declares an inline non-pipeline orchestrator to avoid recursion
  if spawned as a node — keep it.

## Market research upkeep

Local-only market research lives in `.research/market/` (gitignored; never commit it).

At session start, check `.research/market/last_updated`:
- If the file is missing, seed it from this repository's README and capability source/provenance links, using cited primary sources and local retrieval dates.
- If it is older than 30 days, or before any positioning, launch or naming work, refresh it with cited primary sources (URL + retrieved date).
- Keep it local. Never commit it and never copy private research into public docs.
- Log every change in `.research/market/CHANGELOG.md`.

## Capability identity

Public capability identity: `amplifier-capability-transfer`. Preserve the existing portable method folder, native interfaces and legacy installation routes across the approved repository rename.
