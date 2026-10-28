# HGT Principles

The non-negotiables. If a run violates one of these, stop it.

1. **Re-express, never graft.** You transfer the *capability*, not the code. Never
   import, vendor, or copy donor source — document its behavioral contract, then
   rebuild it in the host's own idioms, module layout, and test style. (Cross-
   ecosystem transfers make copying impossible anyway; this rule keeps intra-
   ecosystem transfers honest too.)

2. **The terminal is the acceptance oracle.** A transfer is done only when the
   capability works through a *real terminal* (a forge check), not merely when unit
   tests pass. Unit fixtures miss what real terminals catch.

3. **Gate == CI.** The local gate runs the exact commands the host's CI runs. Feature
   + tests + CI parity are built as one vertical slice — never build-now-test-later.
   Branch protection re-runs the same gate as a second oracle.

4. **Never a protected branch.** One PR per capability per host, on an `hgt/<slug>`
   branch. A PR opens only when its gates are green.

5. **Obey the host.** Each host's layering, conventions, and discipline win. A pure
   protocol-client host stays a client; a layered host keeps its layers.

6. **Bounded, never stalled.** ≤3 attempts per capability; then mark `acknowledged`,
   save the plan for a human, and move on. The queue keeps moving.

7. **Gap-check first.** Only transfer capabilities absent from *every* host and
   inside the run's scope. Porting what already exists is busywork.
