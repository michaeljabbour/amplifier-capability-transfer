# Transfer

Bring a proven capability to the host you use.

Developers bringing an observed donor capability into one or more existing hosts. Use for a bounded capability transfer across architectures or languages, while keeping host boundaries intact.

## Install the portable method

```sh
python3 scripts/capability.py doctor
python3 scripts/capability.py install --dest ~/.agents/skills
```

Keep the complete `skills/transfer` folder together. Installation copies only that method, references, and license; it starts no service and installs no runtime. Use a different skills-parent path for your host.

## Choose the mode

- **Gap check** — A donor seems useful but host overlap is unclear. Observed donor contract and an explicit keep/drop rationale per host.
- **Re-express** — A missing capability and host seam are known. A native host slice with tests, real-surface probe, and CI parity.
- **Verify** — The builder reports a transfer complete. A donor-derived check, bounded reopen, and retained evidence or blocker.

## What was consolidated

[Migration map](docs/MIGRATION.md) records the original source paths and current roles. Primary Git history, native engines, tests, examples, and evaluation assets remain in this checkout. [Native guide](docs/NATIVE-README.md) preserves the original project documentation; old install URLs and runtime claims there are historical and need current verification. [Validation](docs/VALIDATION.md) records actual checks and limits.

## Build the local site

```sh
python3 scripts/capability.py build
python3 scripts/capability.py check
```

Open `_site/index.html` or serve `_site` with a local static server. The downloadable ZIP is built from canonical method bytes. The fictional before/after example illustrates intended judgment; it is not a measured improvement. Nothing has been published or renamed remotely.
