---
name: build-pause
description: Gracefully pause a live firing at the current boundary — park in-flight work, write the resume marker, release the run marker. Use when the operator asks to pause, stop, or wind down the build loop; works from the firing session directly or by flagging a pause request the loop honors at its next tick.
user-invocable: true
---

# Pause a firing, cleanly

Two cases — decide by whether **you** are the orchestrator of the live firing (you hold the run marker in this conversation):

## You are the firing orchestrator → pause NOW

Perform the clean pause at the current boundary (identical to a governor `pause`):

1. **No new admissions** — do not start the next tick or spawn new workers.
2. **Finish or park the in-flight worker.** Park = a blocker record (schema `blocker.json`) routed as an E3 card — never silent abandonment. Append its run-log + event-log records **write-ahead**, with `outcome: "aborted"` or `"parked"` and the spawn's resolved `model`/`tier`/`effort` — an interrupted routing choice is still telemetry.
3. **Reconcile worktrees** (leases stay durable; a parked pipeline keeps its home for the disk resume).
4. **Write the resume marker**: `EventLog.set_resume_marker({...reason, next task...})`.
5. **Release the run marker**: `harness.loop.release_run_marker(state/run.marker)` — the closure Stop gate goes inert only after this; an unreleased marker will (correctly) block your stop.
6. If `state/pause.request` exists, clear it now — **after** the pause completed: `harness.loop.clear_pause_request(...)`.
7. End with the ledger digest as the handoff. The next firing resumes from disk, never from your summary.

## You are NOT the firing orchestrator → flag the request

Write the pause flag; the loop checks it at every tick boundary and runs the sequence above itself:

```
python3 -c "from harness import loop; print(loop.request_pause('state/pause.request', reason='<why>', requested_by='<operator>'))"
```

Report to the operator: the request is durable on disk, the firing will pause at its next boundary (between tasks — an in-flight worker finishes or parks first), and `state/run.marker` disappearing is the confirmation the pause landed.

**Never** "pause" by killing processes or editing state files directly — a hard interrupt is crash-safe (disk is the memory) but loses the parked-blocker record and the interrupted worker's telemetry.
