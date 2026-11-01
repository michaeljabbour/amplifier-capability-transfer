# HGT evals — simple hill-climbing eval

**What is measured (the criterion, before any code):** the attractor's one job is to
drive every ledger row to a green-gated PR. So the fitness the run hill-climbs is
`implemented_frac` — the fraction of ledger rows in state `implemented`. That state
is only ever set by the Commit node *after* both gates pass (unit suite + real-
terminal forge check), so the score bakes in quality as a precondition: the harness
cannot score by lowering the bar, and `acknowledged` (gave up / human handoff)
drains the queue but earns nothing — "do less" cannot score.

**The hill-climb property:** a healthy run only climbs. Two invariants (the ratchet):
1. `implemented_frac` is non-decreasing across successive ledger snapshots;
2. no row un-completes (`implemented` → `new`/`acknowledged`).

Any violation is a regression / Goodhart tripwire and fails the eval.

Queue identity is also checked: a key cannot disappear or change its target
between snapshots. New distinct keys may be added. A new scope or reassigned
target starts a separate run; it cannot inherit an earlier target's evidence.
Each snapshot must contain exactly three TSV fields per data row, unique
nonempty keys, nonempty targets and a declared state. Malformed rows, duplicate
keys and unknown states fail instead of being dropped or counted as progress.
An empty queue is valid; a run with no snapshots is not evidence of progress.

The ledger CLI also rejects malformed snapshots, unknown update keys/states,
reassignment of an existing key, and attempts to leave terminal `verified` state.
Invalid operations return nonzero without rewriting the ledger. These checks
protect state integrity; they do not authenticate a verifier or prove that the
unit, CI or real-surface gates actually ran.
Keys and targets are whitespace-free tokens; a new key cannot start with `#`
(the ledger comment marker). This keeps successful additions readable by the
same CLI and its two-token queue-selection output.

## Verifier command guards

`python3 -m unittest discover -s tests -p 'test_verifier_guards.py' -v`
exercises the actual `verify.dot` tool commands against authored temporary
ledgers and check scripts. Invalid rows, state files or helper failures route to
`blocked`; state files are parsed as data rather than sourced as shell code.
Verifier output logs live in the host's `.ai/verify_logs/<slug>.doctor.log` and
`<slug>.checks.log`, replacing the old shared `/tmp/hgt_verify*` scratch files.

These offline guards do not run a donor/host transfer or a model. The required
live scratch-source/host acceptance gate in `AGENTS.md` still applies to changes
to the verifier graph.

## Pipeline path and failure boundaries

Both graph loops require an existing readable ledger at a contained path relative
to the primary host. A missing configured ledger is blocked; an existing valid
empty ledger is done. This graph precondition does not change the standalone
ledger CLI's absolute-path or new-ledger support.

The graph preflight checks actual donor/host repository roots, distinct source
and targets, the selected ledger row, exact state fields, and known `.ai` files,
directories and descendants. Symbolic links in those artifact paths are refused.
State content is never sourced as shell code. Gate infrastructure and artifact
failures route to `blocked`; an executed gate that returns nonzero routes to
`fail`.

Main-loop logs now live under `.ai/hgt_logs/<slug>.*.log`. The current
`.ai/hgt_validation.json` names the stage, target, result and logs actually used.
Failure analysis reads only that record's logs, avoiding a skipped host or prior
stage's output. Log files are opened before gate execution or Git publication.
Retry state allows two retries after the initial attempt, then hands off after
the third failure; selection does not reset the allowance before branch setup.

For verification, the reopen marker is reserved before the ledger advances. If
marker creation fails, the ledger is unchanged. If the ledger update then fails,
the reservation stays and the graph stops. Retrying uses the already-consumed
allowance rather than silently allowing another reopen. This is a fail-closed
policy; do not erase the marker merely to make a failed run continue.

The fixtures exercise these command contracts only. Standalone concurrent
ledger writers and malicious concurrent path replacement are unvalidated;
no locking or transaction guarantee is supplied by these checks.

Run the separate `runtime_tests` suite with an existing Amplifier Python
environment before native graph use. It imports the installed loop-pipeline
parser directly, compiles every decoded embedded Python payload, and exercises
authored command fixtures. Missing native dependencies fail that test command;
there is no fallback parser or skipped success. Embedded Python expresses literal
line-feed values with `chr(10)` because the DOT parser decodes backslash-newline
escapes before Python sees them. This keeps retry matching and JSON record bytes
unchanged without modifying the SDK.

Both Git operations select literal paths from native Git's tracked/untracked
inventory, leaving ignored files alone. They omit root/nested `.ai`,
`__pycache__`, bytecode paths and the primary host's configured ledger/helper.
NUL-delimited path input preserves literal filenames without negative pathspecs
that can error on ignored parents. Commit refuses metadata or primary controls
already staged and leaves the index intact for owner review. Legacy tracked
control blobs remain unchanged; untracked controls do not enter the application
commit. The current queue/helper survive return to main. State is checked again
after branch setup. Standalone ledger CLI path support is unchanged.

An existing `hgt/<slug>` branch remains an ownership gate even after a verifier
reopens its row. The graph does not automatically reset or reuse that branch.
The [active runbook](../context/hgt-runbook.md) describes the required manual
recovery decision; this flow limitation is not repaired by the fixture guards.

## Loop 1 (verifier) mode

With `pipelines/verify.dot` in play the ledger gains the terminal state
`verified`, and the blind verifier may legally REOPEN an implemented row. Monitor
those runs with `--verifier`: the protected scalar becomes `verified_frac`, no row
may ever leave `verified`, and reopens are reported (↺) rather than failed.

## Run it

```sh
python3 evals/hillclimb.py --self-test   # detectors for BOTH modes     # the eval proves it detects regressions
python3 evals/hillclimb.py --fixture       # demo curve over a bundled 4-snapshot run
python3 evals/fitness.py <ledger.tsv>      # score one ledger state
python3 evals/hillclimb.py s0.tsv s1.tsv…  # evaluate a REAL run's snapshot series
```

## Evaluating a real run

Snapshot the ledger as the run progresses (e.g. `cp $LEDGER_FILE snaps/$(date +%s).tsv`
after each loop, or from git history of the ledger file:
`git log -p --follow -- <ledger>` → materialize each version), then feed the ordered
snapshots to `hillclimb.py`. Exit 0 = the run climbed monotonically; exit 1 = it
regressed somewhere, with the offending step named.

## Honest limits

**Scope (sharpened after external review):** this is the INNER run monitor.
Because ledger rows only ever move forward, within-run monotonicity is close to
tautological — this eval detects broken runs, it cannot rank technique variants.
The technique-level objective function (frozen answer key, external grading,
v1-vs-v2 on identical tasks) is designed in `docs/EVALUATION.md`.

This eval scores the ATTRACTOR's convergence behavior — progress, monotonicity, and
queue integrity. It does **not** re-judge the quality of an individual transfer
beyond what the gates enforced (that judgment lives in the gates themselves and in
PR review). Keep it that way: one high-signal criterion beats ten noisy ones.
