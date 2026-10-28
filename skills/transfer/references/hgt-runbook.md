# HGT Runbook — how to drive a Horizontal Gene-Transfer run

You are the **orchestrator/engine** for an HGT transfer. This is the proven path:
you drive the loop that `hgt:pipelines/hgt.dot` specifies, using self-delegated
workers in git worktrees. (The graph can also run under the `run_pipeline` engine —
see below — but orchestrator-as-engine is the reliable default.)

## The three knobs

| Knob | Meaning |
|---|---|
| **source(s)** | Donor repo(s), read-only, any language. You transfer the *capability*, never the code. |
| **host(s)** | Target repo(s), each with a `kind` (`python` / `rust` / `new:<lang>`) that selects its gate stack. A host may be a **new/empty repo** — transfer #1 scaffolds its CI. |
| **scope** | Free-text: which capabilities transfer, and what's excluded. Apply it as a **gap-check first** — only capabilities absent from *every* host get a ledger row. |

Per-capability `target` (ledger column 2): `a` (host A only) · `ab` (pure client UX
in both hosts) · `split` (host-A backend/protocol first, then client in both — seed
as two ordered rows `<slug>-backend` then `<slug>-client`).

## Phase 0 — gap-check (defines scope; do first)

Read the scope. For each candidate capability, verify whether it ALREADY exists in
each host (grep the host's command/UI/model layers). Where UX matters, boot the donor
via forge to see the real behavior. **Keep only capabilities missing from every host
and not excluded by scope.** Seed the ledger with the survivors
(`LEDGER_FILE=<ledger> python3 pipelines/ledger.py add <slug> <target>`); expand
`split` into its two ordered rows. Print the seeded ledger and the keep/drop
rationale before building.

## Phase 1 — max-parallel build

Build a dependency-aware wave plan and run at **maximum useful parallelism**:
- One self-delegated `claude-opus-4-8` worker per capability, each in its own git
  worktree per targeted host. (`claude-fable-5` refuses autonomous porting.)
- Independent capabilities (disjoint files) run concurrently. Ordering: a `split`
  client row starts only after its backend PR is green; capabilities touching the
  same file run in sequence.
- **Cap concurrency ~4–6 lanes.** Forge screen-scrape probes flake under heavy load;
  if a forge assertion is the *only* failure, re-run it in isolation before treating
  it as real or burning a retry.

Each worker performs the HGT slice (the `hgt.dot` nodes):
1. **Locate** the donor capability — document the behavioral contract only; never copy.
2. **Plan** the re-expression through each host's own seams; **author the forge probe
   first** from the acceptance (the probe is the spec).
3. **Implement the vertical slice** — feature + unit tests + forge probe + CI parity
   in one pass; the local gate must equal the host's CI. Never build-now-test-later.
4. **Unit gate** — run the host's exact gate stack per kind.
5. **Forge gate** — boot the real host app(s) via forge and assert. An LLM never
   declares success; the terminal does.
6. **Land** — you (orchestrator) re-verify gates independently, then commit + push +
   PR per targeted host (branch `hgt/<slug>`, label `hgt`), and mark the ledger
   `implemented`.

**Bounded:** ≤3 attempts per capability; then mark `acknowledged`, save the plan to
`.ai/hgt_blocked/<slug>.md`, and move on — never stall the queue.

## Hard rules (see PRINCIPLES.md)

Never commit to a protected branch (branch + PR; protection re-runs the gates) ·
never import/vendor/copy donor code · obey each host's layering/conventions · a PR
opens only when its gates are green.

## Alternative launch — the run_pipeline engine

`hgt.dot` is a valid loop-pipeline graph. To run it under the real engine, pass
params so they reach BOTH prompts and `tool_command` (the mounted-orchestrator path
does NOT substitute params into `tool_command` — a real engine limitation):

```python
from amplifier_module_pipeline_runner.runner import run_pipeline
await run_pipeline(open("pipelines/hgt.dot").read(),
    params={"DONOR_PATH": "...", "HOST_A_PATH": "...", "HOST_A_KIND": "python",
            "HOST_B_PATH": "...", "HOST_B_KIND": "rust",
            "FORGE_TOOL": "~/.claude/skills/amplifier-skill-forge/tools/forge.py",
            "LEDGER_FILE": "pipelines/hgt-ledger.tsv", "SCOPE": "..."},
    cwd="<HOST_A_PATH>", logs_root="./runs")
```

Or export the same names as UPPERCASE env vars before `amplifier run` — the graph's
`${VAR:?}` guards fail loud if any are missing.

## Loop 1 — blind verification (after rows land)

Rows landed by the build loop are `implemented` — gated, but by gates the flow
itself authored. Loop 1 (`hgt:pipelines/verify.dot` · the `hgt-verifier` agent)
independently drives them to the terminal state **`verified`**: a verifier BLIND to
every builder artifact derives its own checks from the ground truth (the donor app)
and validates through a real terminal. Fail ⇒ findings in `.ai/verify_findings/`,
row reopens ONCE (`implemented → new` — the build loop rebuilds with findings
readable), then `acknowledged`. Verifier → builder info flow is allowed; builder →
verifier is forbidden.
Run order: build loop to quiescence → verify loop to quiescence → done when every
row is `verified` or `acknowledged`. Monitor with `evals/hillclimb.py --verifier`.
