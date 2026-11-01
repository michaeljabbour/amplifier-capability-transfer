#!/usr/bin/env python3
"""Gene-transfer ledger — one row per amplifier-app-cli capability being ported.

Modeled on the attractor `semport` fixture's ledger contract. Rows are TSV:

    <issue>\t<slug>\t<state>

state ∈ {new, implemented, verified, acknowledged}
  new          — not yet ported
  implemented  — ported, validated (unit + forge), PR opened
  verified     — blind verifier (Loop 1) independently confirmed the behavior
  acknowledged — could not converge (or failed verification twice); human handoff

Commands (stdlib only; invalid input exits nonzero for the pipeline's guards):
  earliest              print "<key> <label>" of the first `new` row, or NONE
  earliest-implemented  print "<key> <label>" of the first `implemented` row, or NONE
                        (the blind verifier's queue — Loop 1)
                        The FIRST token is always the ledger KEY (col 0) — use it for
                        updates, artifact names, and result lines. The second token is
                        a label whose meaning varies by pipeline (HGT: target route;
                        GM: title slug) — never treat it as the key.
  update <issue> <st>   set a row's state
  stats                 counts by state
  sort                  rewrite file: new first, then implemented, then acknowledged
  add <issue> <slug>    append a new row (idempotent on issue)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ledger file is overridable so one tool can serve several pipelines
# (e.g. the app-cli backlog ledger and the opencode-transfer ledger).
# Back-compatible: unset LEDGER_FILE keeps the original ledger.tsv sibling.
_LEDGER_ENV = os.environ.get("LEDGER_FILE")
LEDGER = Path(_LEDGER_ENV) if _LEDGER_ENV else Path(__file__).with_name("ledger.tsv")
ORDER = {"new": 0, "implemented": 1, "verified": 2, "acknowledged": 3}


def _field(value: str) -> bool:
    # Queue selection prints exactly two whitespace-separated tokens. Python's
    # splitlines also recognizes Unicode separators beyond CR/LF.
    return bool(value) and not any(c.isspace() for c in value)


def _rows() -> list[list[str]]:
    if not LEDGER.exists():
        return []
    out = []
    seen: set[str] = set()
    for number, line in enumerate(LEDGER.read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = [part.strip() for part in line.split("\t")]
        if len(parts) != 3 or not all(_field(part) for part in parts):
            raise ValueError(f"line {number}: expected three nonempty whitespace-free TSV fields")
        if parts[2] not in ORDER:
            raise ValueError(f"line {number}: invalid state {parts[2]!r}")
        if parts[0] in seen:
            raise ValueError(f"line {number}: duplicate key {parts[0]!r}")
        seen.add(parts[0])
        out.append(parts)
    return out


def _write(rows: list[list[str]]) -> None:
    LEDGER.write_text("".join("\t".join(r) + "\n" for r in rows))


def _main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "stats"
    rows = _rows()

    if cmd == "earliest":
        for issue, slug, state in rows:
            if state == "new":
                print(f"{issue} {slug}")
                return 0
        print("NONE")
        return 0

    if cmd == "earliest-implemented":
        for issue, slug, state in rows:
            if state == "implemented":
                print(f"{issue} {slug}")
                return 0
        print("NONE")
        return 0

    if cmd == "update" and len(argv) == 3:
        issue, state = argv[1], argv[2]
        if state not in ORDER:
            raise ValueError(f"invalid state {state!r}")
        match = next((r for r in rows if r[0] == issue), None)
        if match is None:
            raise ValueError(f"unknown key {issue!r}")
        if match[2] == "verified" and state != "verified":
            raise ValueError(f"{issue!r}: verified is terminal")
        for r in rows:
            if r[0] == issue:
                r[2] = state
        _write(rows)
        print(f"{issue} -> {state}")
        return 0

    if cmd == "add" and len(argv) == 3:
        issue, slug = argv[1], argv[2]
        if not _field(issue) or issue.startswith("#") or not _field(slug):
            raise ValueError("key and target must be nonempty whitespace-free fields; keys cannot start with '#'")
        existing = next((r for r in rows if r[0] == issue), None)
        if existing is not None and existing[1] != slug:
            raise ValueError(f"{issue!r}: existing key has a different target")
        if not any(r[0] == issue for r in rows):
            rows.append([issue, slug, "new"])
            _write(rows)
        print(f"added {issue}")
        return 0

    if cmd == "sort":
        rows.sort(
            key=lambda r: (
                ORDER.get(r[2], 9),
                int(r[0]) if r[0].isdigit() else 0,
                r[0],
            )
        )
        _write(rows)
        print("sorted")
        return 0

    if cmd == "stats":
        counts: dict[str, int] = {}
        for _, _, state in rows:
            counts[state] = counts.get(state, 0) + 1
        print(" ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "empty")
        return 0

    print(f"unknown command: {cmd}", file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    try:
        return _main(argv)
    except (OSError, ValueError) as exc:
        print(f"invalid ledger operation: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
