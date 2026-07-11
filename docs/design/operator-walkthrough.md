# The design, as a day in the operator's life

**Companion to [evidence-based-harness.md](evidence-based-harness.md) (draft 1, 2026-07-10).**
A plain-language walkthrough of one concrete job — *"add a password-reset flow to my web app"* —
from the evening it's handed over to the morning it's reviewed. Where the design is
undetermined, the text says so in the form "some TBD mechanism will do X" and names the ledger
item. This document decides nothing; if it disagrees with the design plan, the design plan wins.

## The evening: you hand it the job

You don't hand the harness a spec. You hand it a sentence, and it **interviews you** — one
question at a time, and it doesn't stop until the job is actually pinned down. *"When a reset
token is used, does it expire immediately or after the whole window? What happens to other
active sessions? Is the email provider already wired, or is that in scope?"* The grilling feels
pedantic, but it is the single best-evidenced step in the whole design: under-specified jobs
fail hard, and talking it out beforehand recovers almost all of the loss (D7). The interview is
deliberately relentless, and it's **Decided**.

When the interview's done, the harness shows you a **plan and asks you to ratify it** — and
this is the one interaction designed to feel slightly awkward on purpose. It does *not* say
"here's my plan, looks good, approve?" with a pre-ticked box. It makes you commit to your own
read *before* it shows its recommendation, it shows you the strongest argument *against* its
own plan, and it explicitly asks *"what did I probably miss?"* The evidence is brutal here: the
moment a machine shows a confident recommendation first, you rubber-stamp it whether it's right
or wrong (D8). The card's shape is **Decided**; whether it actually cuts your mistake rate in
practice is **T6 — settled only by measuring you against the rubber-stamp card**.

Between your approval and any work starting, the harness **checks the plan is even buildable**
— no circular dependencies, and the hand-off points between tasks nailed down before anything
is split up. The "no circles" part is **Decided** (a mathematical precondition — an
unrestricted plan cannot be soundly checked at all, M7). But *how strict* the determinacy check
is, and whether a machine gate beats you just eyeballing the plan, is **T3 — TBD**: some TBD
gate will decide the seams are "determinate enough," and if T3 says the machine version isn't
worth it, that gate becomes your eyeballs.

## Overnight: the work, which you don't watch

**One worker writes code at a time.** Not a swarm. At equal effort a single focused agent
matches or beats a committee, and multiple agents writing into one codebase came out *slower*
once the merge mess is counted (D4). Single writer: **Decided**. The harness fans out only for
*reading* work — hunting through the codebase to find where sessions are managed — where
parallel readers genuinely help.

**The tests that judge the code are written by someone who never sees the code**, from your
ratified spec, and the coding worker literally cannot read or reach them — enforced by the
operating system, not by asking nicely (D2). Every piece of evidence says an agent graded on
its own tests games them, so the graders are walled off. **Decided, non-negotiable.**

**Nothing marks itself "done."** A task completes only when a real verifier — the tests
actually running, the type-checker actually passing — says so, and the harness is built so it
*can't* fake that (D3, D5). The dominant failure mode of long unattended runs is agents
declaring victory early; here victory isn't the agent's to declare. Every gate is a hard stop
with no "override and continue" button. **Decided.**

One honest soft spot: when the graders say *"no problems found,"* the harness **does not fully
trust the silence** — reviewers have unanimously "confirmed" bugs that didn't exist (D6). What
*earns* trust in a clean bill of health is **T4 — TBD**: the current idea is to occasionally
slip in a known, planted bug and check the graders catch it, like testing a smoke detector —
unbuilt and unproven. Until it exists, a clean result is believed but flagged as unverified.

**It will hit the usage wall, and that's fine.** On a subscription plan an unattended run
eventually runs out of window. The harness doesn't crash or overspend — it **parks**: writes
down exactly where it was and wakes when the window resets (D12). **Decided** and cheap. Two
related things are *not* settled: how aggressively it reuses cached context depends on **T1** —
the one measurement of whether cached reads count against your limit, which only you can run —
and whether it needs anything *smarter* than park-and-wait (predictive throttling) is **T5 —
TBD**, deliberately out of v1 because our own past attempt at that cleverness once deadlocked
and refused to start any work at all.

Its **memory is just files in your git repo** — no exotic database, because the fancy stuff
doesn't beat plain files — and anything it "learned" is written through a gate so a poisoned
note can't quietly corrupt future runs (D9). Be clear-eyed: whether accumulated memory helps
*at all* is **T8 — TBD**, and the best evidence says memory saves *time* on hard tasks, not
*quality*. In v1 it's on probation — measured, not trusted.

Each worker runs in its **own sandboxed process** with its own file and network permissions —
OS-enforced, because a prompt saying "please stay in your lane" is not a boundary (D11).
**Decided.**

## The morning: you review

You come back to a **batch** of everything routine — approved, merged, summarized for skimming,
because interrupting you for every trivial step is how oversight fatigue sets in and you start
approving blind. Anything that needed *your* judgment is broken into **small pieces**, because
human review falls apart past a few hundred changed lines (D8). If it hit something
irreversible or externally visible — sending real reset emails to real users — it **stopped and
waited**, and if you didn't answer, it **stayed parked**. It never auto-approves its way past
you. The fail-safe direction is **Decided**; the escalation frequency that keeps you responsive
without spamming you is **T7 — TBD, tuned to you over time**.

One thing you won't find: the harness did **not** improve or rewrite its own machinery
overnight. Deliberate omission (D10) — every self-improving loop in the literature eventually
cheated its own scoring, so v1 has no ability to edit itself. If ever built, it'll be
proposals-only behind the strictest version of the commit-before-reveal card. **Parked on
purpose.** Improvements arrive the way the design itself did: new evidence — external research
or the harness's own measurements — through the design doc, ratified by you (R6).

Underneath it all, from the first run, the harness **keeps score on itself** — logging what
each mechanism cost and, where feasible, running a quiet "would plain Claude Code have done
just as well?" comparison (D14). That's the promise that keeps the machine small: anything that
can't beat doing nothing gets deleted, and the deletion is a result, not a failure.

---

**The one-line version:** you argue with it up front, it works alone and honestly overnight
behind graders it can't reach, it parks instead of failing, and it wakes you only for things
you'd actually want to decide. The Decided spine: single writer, walled-off graders, hard
gates, park-and-resume. The TBDs are about *tuning and trust* — plan-gate strictness (T3),
trust in silent verdicts (T4), whether the forcing card and memory pay off (T6, T8), and the
window economics (T1, T5) — not about the spine.

**And a note on the machinery's own shape (R5/D15):** what ran overnight is a *toolbox, not a
monolith*. The interview, the merge gate, the ratification card, and the park-and-resume
wrapper are each standalone tools that talk through files — you can adopt the interview alone
with plain Claude Code, or call the gate from a workflow that contains nothing else from this
design. The "harness" is just one composition of them, and dropping a stage for low-risk work
is configuration, not surgery.
