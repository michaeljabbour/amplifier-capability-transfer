# Transfer

Bring the behavior to the app you use.

A skill for moving a bounded capability between applications. Understand the donor, check what the host already does and rebuild the missing behavior through the host’s own architecture.

[Explore the site](https://michaeljabbour.github.io/amplifier-skill-transfer/) · [Read the method](skills/transfer/SKILL.md) · [Install guide](docs/INSTALL.md)

## What you get

- **Transfer the useful part.** Describe the behavior and failure paths, then drop features the host already has or does not need.
- **Keep the host coherent.** Re-express the capability through native interfaces instead of grafting donor source into a different system.
- **Verify against the donor.** Use donor-derived acceptance checks and actual host surfaces to challenge the builder’s completion claim.

## Install and try it

Requires Git and Python 3.11+. Run these commands from a terminal:

```sh
git clone https://github.com/michaeljabbour/amplifier-skill-transfer.git
cd amplifier-skill-transfer
python3 scripts/capability.py doctor
python3 scripts/capability.py install --dest ~/.agents/skills
```

The installer copies `skills/transfer` as a complete folder into your chosen skills parent. Use the discovery path supported by your agent. It starts no service and configures no provider. Restart or refresh skill discovery in your host, then ask:

```text
Use Transfer to compare pause/resume behavior in this fictional donor with two host clients. Keep donor source read-only. Identify current host overlap and shared runtime prerequisites, then propose one donor-derived acceptance probe per slice.
```

If your agent does not discover installed skills, point it directly at the complete folder and ask it to read `SKILL.md`. Reading the method needs no Python runtime. [Installation details](docs/INSTALL.md) cover conflict handling and optional native execution.

## How the work proceeds

1. **Compare donor and host.** Observe the behavior, inspect both architectures and record the genuine gap.
2. **Build through the host’s seams.** Land shared backend prerequisites first, then one bounded client slice with normal CI and a real-surface probe.
3. **Verify the transferred behavior.** Derive checks from the donor, preserve gaps and hand over evidence and rollback.

## Example output

Fictional worked example. It illustrates the intended output; it is not a measured result or a real customer story.

```text
Fictional transfer: pause a job
Donor contract: running → paused → resumed
Runtime prerequisite: explicit pause/resume operation
Client A: wire existing control
Client B: add control through native UI seam
Verification: observe state transitions in each host
State: gap checked; implementation not yet verified
```

## What is checked

Retained graph syntax and ledger regression fixtures pass, and the portable install is checked. A ledger state is not donor-host equivalence; a real transfer still needs its source-derived and actual-surface evidence. See [validation](docs/VALIDATION.md) for the exact checks and limits.

## Retained implementation and references

[Migration map](docs/MIGRATION.md) records the original source paths and current roles. Primary Git history, native engines, tests, examples, and evaluation assets remain in this checkout. [Native guide](docs/NATIVE-README.md) preserves the original project documentation; old install URLs and runtime claims there are historical and need current verification. [Validation](docs/VALIDATION.md) records actual checks and limits.

## Build the site

```sh
python3 scripts/capability.py build
python3 scripts/capability.py check
```

The static site includes a ZIP built from the canonical method, references and license. Runtime and provider setup remain separate from installing the portable method.
