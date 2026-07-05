---
name: build-pause
description: Gracefully pause a live firing at the current boundary — park in-flight work, write the resume marker, release the run marker. Use when the operator asks to pause, stop, or wind down the build loop; works from the firing session directly or by flagging a pause request the loop honors at its next tick.
user-invocable: true
---

# Pause a firing, cleanly

Two cases — decide by whether **you** are the orchestrator of the live firing (you hold the run marker in this conversation):

## You are the firing orchestrator → pause NOW

Perform the clean pause at the current boundary (identical to a governor `pause`):

0. **Acknowledge first (I23).** If `state/pause.request` exists, write the receipt before anything else: `harness.loop.acknowledge_pause('state/pause.request', 'state/pause.ack', draining=[<in-flight task:role ids>])` — the operator watching `state/pause.ack` learns the request landed and what is draining, even if this session dies mid-drain.
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

Report to the operator, including the latency expectation (I23, P3v2-8):

- **Acknowledgment:** the loop checks the flag at every tick AND stage boundary (worker handoff, panel return, gate exit) and writes `state/pause.ack` the moment it sees the request — watch that file for the receipt. With background-spawned workers the longest gap between checks is one poll interval.
- **Full pause:** bounded by the longest **in-flight worker attempt** — attempts are atomic (disk-is-memory applies at handoff boundaries, not mid-attempt; killing an attempt means redoing it), so the loop drains in-flight work to its handoff rather than killing it, then parks, writes the resume marker, and releases the run marker. `state/run.marker` disappearing confirms the pause landed. Zero rework is the point of the wait.
- **Do not type the pause into the live firing session:** an in-session message starves in the queue until the loop's turn yields — potentially the whole firing (P3v2-8: ~17 min behind one worker; unbounded behind a pipeline). The flag from a second terminal is the responsive channel.

**Never** "pause" by killing processes or editing state files directly — a hard interrupt is crash-safe (disk is the memory) but loses the parked-blocker record and the interrupted worker's telemetry.
