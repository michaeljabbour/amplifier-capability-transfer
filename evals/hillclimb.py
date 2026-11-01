#!/usr/bin/env python3
"""Run monitor for the HGT attractor (ratchet over ledger snapshots).

SCOPE: inner run monitor. Rows only move forward, so this cannot rank technique
variants (v1 vs v2) — see docs/EVALUATION.md for the external objective function.

Two modes:

DEFAULT (builder loop): asserts
  1. landed_frac (implemented+verified) is non-decreasing, AND
  2. no landed row un-completes (implemented|verified -> new|acknowledged).

--verifier (Loop 1 in play): the blind verifier may legally REOPEN an implemented
row (implemented -> new, with findings), so landed may dip. Asserts instead
  1. verified_frac is non-decreasing, AND
  2. no row ever LEAVES `verified` (it is terminal).
Reopens are reported, not failed.

Usage:
    python3 evals/hillclimb.py [--verifier] <snap0.tsv> <snap1.tsv> ...
    python3 evals/hillclimb.py --fixture            # bundled builder-loop demo
    python3 evals/hillclimb.py --fixture-verify     # bundled Loop-1 demo (verifier mode)
    python3 evals/hillclimb.py --self-test          # detectors for BOTH modes
"""
from __future__ import annotations

import sys
from pathlib import Path

from fitness import fitness, read_rows, validate_rows

HERE = Path(__file__).parent
FIXTURE = sorted((HERE / "fixtures" / "run").glob("*.tsv"))
FIXTURE_VERIFY = sorted((HERE / "fixtures" / "verify").glob("*.tsv"))


def _bar(frac: float, width: int = 24) -> str:
    n = round(frac * width)
    return "█" * n + "·" * (width - n)


def check(series: list[list[tuple[str, str, str]]], verifier: bool = False) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if not series:
        return False, ["invalid run: no snapshots supplied"]
    ok = True
    prev_f = None
    prev_state: dict[str, str] = {}
    prev_target: dict[str, str] = {}
    for i, rows in enumerate(series):
        try:
            validate_rows(rows)
        except ValueError as exc:
            return False, notes + [f"    ✗ invalid snapshot {i}: {exc}"]
        f = fitness(rows)
        notes.append(
            f"  step {i}: {_bar(f['verified_frac'] if verifier else f['landed_frac'])} "
            f"impl={f['implemented']} ver={f['verified']}/{f['total']} "
            f"landed={f['landed_frac']:.2f} verified={f['verified_frac']:.2f}"
        )
        state = {r[0]: r[2] for r in rows}
        target = {r[0]: r[1] for r in rows}
        for key in sorted(prev_state.keys() - state.keys()):
            ok = False
            notes.append(f"    ✗ REGRESSION: row {key!r} disappeared from queue")
        for key in sorted(prev_target.keys() & target.keys()):
            if prev_target[key] != target[key]:
                ok = False
                notes.append(f"    ✗ REGRESSION: row {key!r} changed target")
        if prev_f is not None:
            if verifier:
                if f["verified_frac"] < prev_f["verified_frac"] - 1e-9:
                    ok = False
                    notes.append("    ✗ REGRESSION: verified_frac fell")
            else:
                if f["landed_frac"] < prev_f["landed_frac"] - 1e-9:
                    ok = False
                    notes.append("    ✗ REGRESSION: landed_frac fell")
        for slug, st in prev_state.items():
            now = state.get(slug)
            if st == "verified" and now != "verified":
                ok = False
                notes.append(f"    ✗ REGRESSION: '{slug}' left terminal state verified -> {now}")
            elif not verifier and st == "implemented" and now in ("new", "acknowledged"):
                ok = False
                notes.append(f"    ✗ REGRESSION: '{slug}' un-completed ({st} -> {now})")
            elif verifier and st == "implemented" and now == "new":
                notes.append(f"    ↺ reopened by verifier: '{slug}' (implemented -> new)")
        prev_f, prev_state, prev_target = f, state, target
    return ok, notes


def _self_test() -> int:
    ok_all = True
    # builder-loop detectors (legacy)
    good = [
        [("a", "python", "new"), ("b", "both", "new")],
        [("a", "python", "implemented"), ("b", "both", "new")],
        [("a", "python", "implemented"), ("b", "both", "implemented")],
    ]
    bad = [
        [("a", "python", "implemented"), ("b", "both", "implemented")],
        [("a", "python", "new"), ("b", "both", "implemented")],
    ]
    g, _ = check(good)
    b, _ = check(bad)
    print("builder mode: climbing detected:", g, "| un-complete rejected:", not b)
    ok_all &= g and not b
    # verifier-mode detectors
    v_good = [  # implement -> verify, plus a legal reopen dip
        [("a", "x", "implemented"), ("b", "y", "implemented")],
        [("a", "x", "verified"), ("b", "y", "implemented")],
        [("a", "x", "verified"), ("b", "y", "new")],  # b reopened: allowed
        [("a", "x", "verified"), ("b", "y", "implemented")],
        [("a", "x", "verified"), ("b", "y", "verified")],
    ]
    v_bad = [  # a row leaving verified is never legal
        [("a", "x", "verified"), ("b", "y", "new")],
        [("a", "x", "new"), ("b", "y", "new")],
    ]
    vg, _ = check(v_good, verifier=True)
    vb, _ = check(v_bad, verifier=True)
    print("verifier mode: reopen tolerated:", vg, "| verified-exit rejected:", not vb)
    ok_all &= vg and not vb
    print("SELF-TEST", "PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1


def main(argv: list[str]) -> int:
    verifier = False
    if argv[:1] == ["--verifier"]:
        verifier = True
        argv = argv[1:]
    if argv == ["--self-test"]:
        return _self_test()
    if argv == ["--fixture-verify"]:
        paths, verifier = [str(p) for p in FIXTURE_VERIFY], True
    elif argv == ["--fixture"] or not argv:
        paths = [str(p) for p in FIXTURE]
    else:
        paths = argv
    if not paths:
        print("no fixtures found", file=sys.stderr)
        return 2
    print(f"HGT hill-climb ({'verifier' if verifier else 'builder'} mode) over {len(paths)} snapshot(s):")
    try:
        ok, notes = check([read_rows(p) for p in paths], verifier)
    except (OSError, ValueError) as exc:
        print(f"invalid ledger: {exc}", file=sys.stderr)
        return 2
    print("\n".join(notes))
    print("VERDICT:", "CLIMBING ✓" if ok else "REGRESSION ✗")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
