> Original native guide, preserved at source commit `49889d5cd0bcd0c50f670be960051dacb1c8975d`. Install locations, model names, service availability, and claims below are historical and must be verified before use. Current portable installation is in INSTALL.md.

# amplifier-bundle-genetransfer

**HGT — the Horizontal Gene-Transfer attractor.** A self-contained Amplifier bundle
that packages a reusable, parameterized *capability-transfer* pipeline: it moves a
capability from a donor repo (any language) into **one or more host repos**,
re-expressed through each host's own seams — **never** by copying donor code — gated
by the host's unit suite **and** a real-terminal [forge](https://github.com/michaeljabbour/amplifier-skill-forge)
check, one PR per capability per host.

Where the earlier `gene-transfer` was *vertical* (one donor → one host, same
ecosystem), **HGT is horizontal**: across a species boundary (a foreign codebase),
into multiple hosts. `opencode → {newtui-py, newtui-rust}` is instance #1
(`examples/opencode/`).

## The three knobs

| Knob | What |
|---|---|
| **source(s)** | Donor repo(s), read-only, any language. You transfer the capability, not the code. |
| **host(s)** | Target repo(s), each `path:kind` (`python` / `rust` / `new:<lang>`). A host may be a **new/empty repo** — transfer #1 scaffolds its CI. |
| **scope** | Free-text: which capabilities transfer, what's excluded. Applied as a **gap-check first**. |

## What makes it a distinct type

- **Forge-woven QA at three points, not one final gate:** observe the real donor in
  forge, author the forge probe *before* the code (acceptance-first), then validate
  by booting the real host app(s). The terminal is the acceptance oracle.
- **Feature + tests + CI co-built as one vertical slice.** The local gate *is* the CI
  gate (per host kind) → no green-locally/red-in-CI tax. New host ⇒ CI ships with
  capability #1.
- **Cross-ecosystem + multi-host, first-class.** Donor language is irrelevant;
  heterogeneous hosts land the same capability in different layers via the ledger
  `target` (`a` / `ab` / `split`).

## Usage

**1. Install and activate**

```sh
amplifier bundle add git+https://github.com/michaeljabbour/amplifier-bundle-genetransfer@main
amplifier bundle use hgt          # /hgt mode + hgt-orchestrator/hgt-expert agents
```

**2. Define the three knobs** (see `examples/opencode/` for a filled-in instance):

```sh
export DONOR_PATH=/abs/path/to/donor            # source repo, read-only, any language
export HOST_A_PATH=/abs/path/to/hostA HOST_A_KIND=python
export HOST_B_PATH=/abs/path/to/hostB HOST_B_KIND=rust     # optional second host
export FORGE_TOOL=~/.claude/skills/amplifier-skill-forge/tools/forge.py
export LEDGER_FILE=pipelines/hgt-ledger.tsv     # relative to HOST_A_PATH
export SCOPE="which capabilities transfer; what's excluded"
```

**3. Gap-check + seed the ledger** — only capabilities absent from every host get a
row (`python3 pipelines/ledger.py add <slug> <target>` with `LEDGER_FILE` set;
target ∈ `a` | `ab` | `split`). Not sure? Ask `hgt-expert` to plan the instance.

**4. Run** — two launch paths:
- **Orchestrator-as-engine (recommended, proven):** activate `/hgt` or
  `delegate(agent="hgt:hgt-orchestrator", …)` — it gap-checks, seeds, and runs a
  max-parallel wave of self-delegated workers in git worktrees.
- **run_pipeline engine:** `bundles/hgt-interactive.yaml` provides `run_pipeline`;
  pass the same names as params. (`bundles/hgt-pipeline.yaml` = headless; export the
  env vars and launch from the repo root.) See `context/hgt-runbook.md`.

**5. Monitor & finish** — the ledger is the source of truth:
`LEDGER_FILE=… python3 pipelines/ledger.py stats`. Done = no `new` rows: every row
is `implemented` (green-gated PR open) or `acknowledged` (human handoff, with a plan
saved under `.ai/hgt_blocked/`).

## Evaluation (hill-climbing)

The bundle ships a simple hill-climbing eval (`evals/`): fitness =
`implemented_frac` (quality is a precondition — only green-gated rows count), and a
**ratchet check** — across successive ledger snapshots the fitness must never fall
and no row may un-complete. Regressions fail the eval.

```sh
python3 evals/hillclimb.py --self-test    # prove the detector works
python3 evals/hillclimb.py --fixture      # demo curve
python3 evals/hillclimb.py snap0.tsv snap1.tsv …   # score a real run
```

See `evals/README.md` for what is measured and why. **Loop 1 is now built:**
`pipelines/verify.dot` + the blind `hgt-verifier` agent drive `implemented`
rows to the terminal `verified` state against independently-derived checks
(monitor with `evals/hillclimb.py --verifier`); `docs/EVALUATION.md` holds the
full three-loop design.

## Validation (DTU reality check)

The smallest successful hillclimber has been proven end-to-end in an isolated
Digital Twin Universe (bundle v0.1.1, 2026-07-28): a real `amplifier run --bundle
hgt` session (`58c7b5b6…`, claude-opus-4-8, 32 persisted messages) transferred one
capability (`shout-flag`) donor→host — behavioral contract documented (never
copied), unit gate + real-terminal forge gate genuinely green, branch
`hgt/shout-flag` pushed, `main` untouched, ledger `new → implemented` — and the
bundle's own eval scored the run **CLIMBING ✓** (0.00 → 1.00).

Sessions are durable: root session persisted with `events.jsonl` +
`metadata.json` + `transcript.jsonl` and is resumable via `amplifier session
resume`. That property is load-bearing — the reality check is what exposed the
v0.1.1 `hooks-logging` fix (without it, runs completed but persisted nothing;
see `docs/DESIGN_DECISIONS.md` §9). The same check also caught the pipeline
committing `__pycache__` artifacts — the Commit node now excludes them.

## Diagrams

- **Pipeline flow** (the attractor loop, edge labels = routing): [`docs/diagrams/hgt.png`](https://github.com/michaeljabbour/amplifier-bundle-genetransfer/blob/49889d5cd0bcd0c50f670be960051dacb1c8975d/docs/diagrams/hgt.png) — derived from the executable graph by `python3 docs/diagrams/generate.py`.
- **Bundle structure** (composition + token costs): [`bundle.png`](https://github.com/michaeljabbour/amplifier-bundle-genetransfer/blob/49889d5cd0bcd0c50f670be960051dacb1c8975d/bundle.png) / [`bundle.dot`](https://github.com/michaeljabbour/amplifier-bundle-genetransfer/blob/49889d5cd0bcd0c50f670be960051dacb1c8975d/bundle.dot) (bundle-to-dot v3).

## Layout

| Path | What |
|---|---|
| `bundle.md` · `behaviors/hgt-core.yaml` | Root bundle + composable capability set |
| `bundles/` | `hgt-pipeline` (headless) · `hgt-interactive` (run_pipeline) launchers |
| `agents/` | `hgt-orchestrator` (execute) · `hgt-verifier` (Loop 1: blind verification) · `hgt-expert` (explain/plan) |
| `modes/hgt.md` | `/hgt` orchestrator posture |
| `context/` | `hgt-awareness.md` (thin) · `hgt-runbook.md` (method) |
| `pipelines/` | `hgt.dot` (build loop) · `verify.dot` (Loop 1: blind verification) · `ledger.py` (stdlib ledger) |
| `examples/opencode/` | Worked instance |
| `PRINCIPLES.md` · `docs/DESIGN_DECISIONS.md` | Non-negotiables · why it's shaped this way |

## Principles (full list in `PRINCIPLES.md`)

Re-express, never graft · the terminal is the acceptance oracle · gate == CI · never a
protected branch · obey the host · bounded & never stalled · gap-check first.
