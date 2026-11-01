> Local paths in this document are illustrative placeholders. Replace each with the appropriate absolute path on your machine before following an example.

# Example instance — opencode → newtui (Python) + newtui-rust (Rust)

HGT **instance #1**: transfer capabilities from the SST **opencode** agent (a
TypeScript/Bun monorepo) into the two amplifier terminal clients.

## The three knobs

- **source:** `/absolute/path/to/donor-repository` (read-only; TypeScript)
- **hosts:**
  - Host A — `/absolute/path/to/host-python-repository` · `kind=python` ·
    owns the backend (kernel/model/commands) **and** the `serve` stdio protocol.
  - Host B — `/absolute/path/to/host-rust-repository` · `kind=rust` ·
    a **pure protocol client** of Host A's `amplifier-newtui serve` (codex-tui /
    codex-core split) — renders protocol state, owns no session/agent logic.
- **scope:** "Transfer opencode capabilities absent from BOTH clients; skip
  cloud/hosted/plugin-system/desktop features and anything already present."

Because Host B is a *client* of Host A, `target` maps to layer:
`a` (backend, Host A only — Rust gets it over the protocol) · `ab` (pure client UX,
both) · `split` (Host A backend/protocol first, then client in both).

## Env vars for a run

```sh
export DONOR_PATH=/absolute/path/to/donor-repository
export HOST_A_PATH=/absolute/path/to/host-python-repository   HOST_A_KIND=python
export HOST_B_PATH=/absolute/path/to/host-rust-repository HOST_B_KIND=rust
export FORGE_TOOL=/absolute/path/to/forge-tool
export LEDGER_FILE=pipelines/hgt-ledger.tsv
export SCOPE="opencode caps absent from both clients; skip hosted/plugin/desktop"
```

## Candidate capabilities (after the gap-check prunes already-haves)

codemode-execute (split) · question-tool (split) · apply-patch-tool (a) · lsp-tool
(a) · prompt-stash (ab) · prompt-frecency-history (ab) · model-variant-cycle (split) ·
session-tags (split) · stats-dashboard (a) · sanitized-export-import (a).

**Skip** (out of scope / philosophy): cloud workspaces, ACP, Slack, Electron,
enterprise console, hosted stats, GitHub-Action bot, hosted share links, the ~30-hook
plugin system, bundled provider adapters, embedded SDK. **Verify-then-skip** (already
in newtui): sessions/fork/subagents/plan/permissions/providers/routing/MCP/skills/
notifications/themes/tool-invoke/reset.

> The full triage table + a ready-to-paste orchestrator launch prompt live in the
> newtui repo at `pipelines/OPENCODE.md` and `pipelines/opencode-run-prompt.md`
> (the first place this instance was drafted, before HGT was extracted here).
