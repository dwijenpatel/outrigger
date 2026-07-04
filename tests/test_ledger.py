"""Tests for harness.ledger — event-log state architecture (design §3 p4, B4).

Covers the four B4 mechanics: append-only durable event log (torn-tail crash
model), derived reconciliation (artifacts beat the log tail), write-ahead cursor
(no advance past durable, no rewind), and generation-stamped mutations (stale
reads fail loudly). B1 semantics that survived the rework (validated transitions,
phantom-task rejection, loud corruption, resume marker) keep their coverage.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import ledger as ledger_mod
from harness.ledger import (
    EventLog, Ledger, LedgerError, StaleGenerationError,
)


def tasks_doc():
    return {"tasks": [
        {"id": "t1", "phase": "p1", "profile": "routine", "deps": []},
        {"id": "t2", "phase": "p1", "profile": "elevated", "deps": ["t1"]},
        {"id": "t3", "phase": "p2", "profile": "high", "deps": ["t1"],
         "may_be_invalidated_by": ["t2"]},
    ]}


class ValidateTasksTests(unittest.TestCase):
    def test_valid_doc_normalizes(self):
        tasks = ledger_mod.validate_tasks(tasks_doc())
        self.assertEqual(set(tasks), {"t1", "t2", "t3"})
        self.assertEqual(tasks["t1"]["may_be_invalidated_by"], [])

    def test_duplicate_id_rejected(self):
        doc = tasks_doc()
        doc["tasks"].append(dict(doc["tasks"][0]))
        with self.assertRaises(LedgerError):
            ledger_mod.validate_tasks(doc)

    def test_unknown_dep_rejected(self):
        doc = tasks_doc()
        doc["tasks"][0]["deps"] = ["ghost"]
        with self.assertRaises(LedgerError):
            ledger_mod.validate_tasks(doc)

    def test_self_dep_rejected(self):
        doc = tasks_doc()
        doc["tasks"][0]["deps"] = ["t1"]
        with self.assertRaises(LedgerError):
            ledger_mod.validate_tasks(doc)

    def test_unknown_soft_edge_rejected(self):
        doc = tasks_doc()
        doc["tasks"][0]["may_be_invalidated_by"] = ["ghost"]
        with self.assertRaises(LedgerError):
            ledger_mod.validate_tasks(doc)

    def test_bad_profile_and_missing_phase_rejected(self):
        for patch in ({"profile": "mega"}, {"phase": ""}):
            doc = tasks_doc()
            doc["tasks"][0].update(patch)
            with self.assertRaises(LedgerError):
                ledger_mod.validate_tasks(doc)

    def test_load_from_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(tasks_doc(), fh)
            path = fh.name
        try:
            self.assertIn("t2", Ledger.load(path))
        finally:
            os.unlink(path)


class EventLogBase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.log = EventLog(os.path.join(self.dir.name, "state", "events.jsonl"))
        self.ledger = Ledger(ledger_mod.validate_tasks(tasks_doc()))

    def tearDown(self):
        self.dir.cleanup()


class EventLogAppendTests(EventLogBase):
    def test_missing_file_means_all_not_started(self):
        proj = ledger_mod.project(self.log.read())
        self.assertEqual(proj["tasks"], {})
        self.assertEqual(self.log.generation(), 0)

    def test_legal_lifecycle_persists_as_events(self):
        self.log.record_status("t1", "in_progress", ledger=self.ledger)
        self.log.record_status("t1", "done", ledger=self.ledger)
        events = self.log.read()
        self.assertEqual([e["seq"] for e in events], [1, 2])
        proj = ledger_mod.project(events)
        self.assertEqual(proj["tasks"]["t1"]["status"], "done")

    def test_illegal_transitions_rejected(self):
        with self.assertRaises(LedgerError):
            self.log.record_status("t1", "done")  # not_started -> done skips work
        self.log.record_status("t1", "in_progress")
        self.log.record_status("t1", "done")
        with self.assertRaises(LedgerError):
            self.log.record_status("t1", "in_progress")  # done is terminal

    def test_same_status_is_idempotent(self):
        self.log.record_status("t1", "in_progress")
        self.log.record_status("t1", "in_progress", note="still going")
        proj = ledger_mod.project(self.log.read())
        self.assertEqual(proj["tasks"]["t1"]["status"], "in_progress")
        self.assertEqual(proj["tasks"]["t1"]["note"], "still going")

    def test_parked_roundtrip_with_note(self):
        self.log.record_status("t2", "in_progress")
        event = self.log.record_status("t2", "parked",
                                       note="blocked on operator answer")
        self.assertEqual(event["note"], "blocked on operator answer")
        self.log.record_status("t2", "in_progress")

    def test_failed_allows_retry(self):
        self.log.record_status("t1", "in_progress")
        self.log.record_status("t1", "failed")
        self.log.record_status("t1", "in_progress")

    def test_unknown_status_rejected(self):
        with self.assertRaises(LedgerError):
            self.log.record_status("t1", "half_done")

    def test_phantom_task_rejected_when_ledger_given(self):
        with self.assertRaises(LedgerError):
            self.log.record_status("t9", "in_progress", ledger=self.ledger)

    def test_resume_marker_roundtrip(self):
        self.assertIsNone(self.log.get_resume_marker())
        self.log.set_resume_marker({"reason": "pause threshold",
                                    "binding_window": "five_hour"})
        marker = self.log.get_resume_marker()
        self.assertEqual(marker["reason"], "pause threshold")
        self.assertIn("set_at", marker)
        self.log.clear_resume_marker()
        self.assertIsNone(self.log.get_resume_marker())

    def test_history_is_never_lost(self):
        # The event log keeps the full transition history — an audit trail the old
        # snapshot index destroyed on every write.
        self.log.record_status("t1", "in_progress")
        self.log.record_status("t1", "failed", note="gate FAIL r1")
        self.log.record_status("t1", "in_progress")
        self.log.record_status("t1", "done")
        statuses = [e["status"] for e in self.log.read()]
        self.assertEqual(statuses, ["in_progress", "failed", "in_progress", "done"])


class CrashModelTests(EventLogBase):
    def test_torn_tail_is_ignored_on_read(self):
        self.log.record_status("t1", "in_progress")
        with open(self.log.path, "ab") as fh:
            fh.write(b'{"seq": 2, "kind": "status", "task_id": "t1", "st')  # torn
        events = self.log.read()
        self.assertEqual(len(events), 1)  # unacknowledged fragment ignored

    def test_append_after_torn_tail_repairs_the_log(self):
        self.log.record_status("t1", "in_progress")
        with open(self.log.path, "ab") as fh:
            fh.write(b'{"torn": ')
        self.log.record_status("t1", "done")
        events = self.log.read()
        self.assertEqual([e["seq"] for e in events], [1, 2])
        self.assertEqual(events[1]["status"], "done")

    def test_interior_corruption_is_a_loud_stop_not_a_reset(self):
        self.log.record_status("t1", "in_progress")
        self.log.record_status("t1", "done")
        with open(self.log.path, "r+b") as fh:
            fh.seek(3)
            fh.write(b"\x00\x00")  # corrupt the first (non-tail) event
        with self.assertRaises(LedgerError):
            self.log.read()

    def test_broken_seq_chain_is_loud(self):
        self.log.record_status("t1", "in_progress")
        event = {"seq": 5, "ts": "2026-07-04T00:00:00Z", "kind": "status",
                 "task_id": "t1", "status": "done"}
        with open(self.log.path, "ab") as fh:
            fh.write((json.dumps(event) + "\n").encode())
        with self.assertRaises(LedgerError):
            self.log.read()


class GenerationStampTests(EventLogBase):
    def test_correct_expectation_passes_and_increments(self):
        self.assertEqual(self.log.generation(), 0)
        self.log.record_status("t1", "in_progress", expected_generation=0)
        self.assertEqual(self.log.generation(), 1)

    def test_stale_expectation_fails_loudly(self):
        self.log.record_status("t1", "in_progress")
        with self.assertRaises(StaleGenerationError):
            self.log.record_status("t1", "done", expected_generation=0)
        # the failed mutation appended nothing
        self.assertEqual(self.log.generation(), 1)

    def test_concurrent_writer_simulation(self):
        # Two actors read at generation 0; the second's write must fail loudly.
        gen = self.log.generation()
        self.log.record_status("t1", "in_progress", expected_generation=gen)
        with self.assertRaises(StaleGenerationError):
            self.log.set_resume_marker({"reason": "pause"}, expected_generation=gen)

    def test_no_expectation_skips_the_check(self):
        self.log.record_status("t1", "in_progress")
        self.log.record_status("t1", "done")  # no expected_generation: allowed


class CursorTests(EventLogBase):
    def test_pending_drains_forward(self):
        self.log.record_status("t1", "in_progress")
        self.log.record_status("t1", "done")
        self.assertEqual([e["seq"] for e in self.log.pending()], [1, 2])
        self.log.advance_cursor(1)
        self.assertEqual([e["seq"] for e in self.log.pending()], [2])
        self.log.advance_cursor(2)
        self.assertEqual(self.log.pending(), [])

    def test_cannot_advance_past_durable_events(self):
        self.log.record_status("t1", "in_progress")
        with self.assertRaises(LedgerError):
            self.log.advance_cursor(2)  # nothing durable at seq 2 yet

    def test_cannot_rewind(self):
        self.log.record_status("t1", "in_progress")
        self.log.advance_cursor(1)
        with self.assertRaises(LedgerError):
            self.log.advance_cursor(0)

    def test_corrupt_cursor_is_loud(self):
        self.log.record_status("t1", "in_progress")
        self.log.advance_cursor(1)
        with open(self.log.cursor_path, "w") as fh:
            fh.write("{broken")
        with self.assertRaises(LedgerError):
            self.log.processed_seq()


class ReconcileTests(EventLogBase):
    def test_no_artifacts_is_claims_only(self):
        self.log.record_status("t1", "in_progress")
        view = ledger_mod.reconcile(self.ledger, self.log)
        self.assertTrue(view["claims_only"])
        self.assertEqual(view["tasks"]["t1"],
                         {"status": "in_progress", "source": "events"})
        self.assertEqual(view["discrepancies"], [])

    def test_gate_pass_beats_stale_claim(self):
        self.log.record_status("t1", "in_progress")
        view = ledger_mod.reconcile(self.ledger, self.log,
                                    artifacts={"t1": {"gate": "pass"}})
        self.assertEqual(view["tasks"]["t1"]["status"], "done")
        self.assertEqual(view["tasks"]["t1"]["source"], "gate")
        self.assertEqual(len(view["discrepancies"]), 1)

    def test_gate_fail_beats_done_claim(self):
        self.log.record_status("t1", "in_progress")
        self.log.record_status("t1", "done")
        view = ledger_mod.reconcile(self.ledger, self.log,
                                    artifacts={"t1": {"gate": "fail"}})
        self.assertEqual(view["tasks"]["t1"]["status"], "failed")
        self.assertEqual(view["tasks"]["t1"]["source"], "gate")
        self.assertEqual(len(view["discrepancies"]), 1)

    def test_dead_run_makes_in_progress_unknown_not_guessed(self):
        self.log.record_status("t1", "in_progress")
        view = ledger_mod.reconcile(self.ledger, self.log,
                                    artifacts={"t1": {"run_active": False}})
        self.assertEqual(view["tasks"]["t1"]["status"], "unknown")
        self.assertEqual(view["tasks"]["t1"]["source"], "reconciliation")
        self.assertEqual(len(view["discrepancies"]), 1)

    def test_live_run_beats_stale_failed_claim(self):
        self.log.record_status("t1", "in_progress")
        self.log.record_status("t1", "failed")
        view = ledger_mod.reconcile(self.ledger, self.log,
                                    artifacts={"t1": {"run_active": True}})
        self.assertEqual(view["tasks"]["t1"]["status"], "in_progress")
        self.assertEqual(view["tasks"]["t1"]["source"], "run")

    def test_consistent_artifacts_produce_no_discrepancies(self):
        self.log.record_status("t1", "in_progress")
        self.log.record_status("t1", "done")
        view = ledger_mod.reconcile(
            self.ledger, self.log,
            artifacts={"t1": {"gate": "pass"},
                       "t2": {"run_active": False},
                       "t3": {}})
        self.assertEqual(view["discrepancies"], [])
        self.assertFalse(view["claims_only"])


class RunnableAndSummaryTests(EventLogBase):
    def test_fresh_state_only_root_runnable(self):
        self.assertEqual(ledger_mod.runnable(self.ledger, self.log), ["t1"])

    def test_dep_completion_unlocks_cross_phase(self):
        self.log.record_status("t1", "in_progress")
        self.assertEqual(ledger_mod.runnable(self.ledger, self.log), [])
        self.log.record_status("t1", "done")
        # t3 is in phase p2 but becomes runnable alongside p1's t2 (§6.1 cross-phase)
        self.assertEqual(sorted(ledger_mod.runnable(self.ledger, self.log)),
                         ["t2", "t3"])

    def test_gate_artifact_alone_unlocks_dependents(self):
        # Events never recorded done, but the gate artifact is authoritative.
        self.log.record_status("t1", "in_progress")
        got = ledger_mod.runnable(self.ledger, self.log,
                                  artifacts={"t1": {"gate": "pass"}})
        self.assertEqual(sorted(got), ["t2", "t3"])

    def test_unknown_dep_blocks_dependents(self):
        self.log.record_status("t1", "in_progress")
        self.log.record_status("t1", "done")
        self.log.record_status("t2", "in_progress")
        # t2's run died: t2 is unknown, but that doesn't affect t3 (dep on t1 only)
        got = ledger_mod.runnable(self.ledger, self.log,
                                  artifacts={"t2": {"run_active": False}})
        self.assertEqual(got, ["t3"])
        # ...whereas an unknown t1 would block everything downstream
        log2 = EventLog(os.path.join(self.dir.name, "events2.jsonl"))
        log2.record_status("t1", "in_progress")
        self.assertEqual(
            ledger_mod.runnable(self.ledger, log2,
                                artifacts={"t1": {"run_active": False}}), [])

    def test_cycle_tasks_never_runnable_not_crash(self):
        doc = {"tasks": [
            {"id": "a", "phase": "p", "profile": "routine", "deps": ["b"]},
            {"id": "b", "phase": "p", "profile": "routine", "deps": ["a"]},
        ]}
        cyclic = Ledger(ledger_mod.validate_tasks(doc))
        self.assertEqual(ledger_mod.runnable(cyclic, self.log), [])

    def test_summary_resume_view(self):
        self.log.record_status("t1", "in_progress")
        self.log.record_status("t1", "done")
        self.log.record_status("t2", "in_progress")
        self.log.record_status("t2", "parked", note="waiting")
        view = ledger_mod.summary(self.ledger, self.log)
        self.assertEqual(view["counts"]["done"], 1)
        self.assertEqual(view["parked"], ["t2"])
        self.assertEqual(view["runnable"], ["t3"])
        self.assertFalse(view["complete"])
        self.assertTrue(view["claims_only"])
        self.assertEqual(view["generation"], 4)

    def test_summary_complete_flag(self):
        for tid in ("t1", "t2", "t3"):
            self.log.record_status(tid, "in_progress")
            self.log.record_status(tid, "done")
        self.assertTrue(ledger_mod.summary(self.ledger, self.log)["complete"])


class DigestTests(EventLogBase):
    def test_header_aggregates_come_first(self):
        self.log.record_status("t1", "in_progress")
        self.log.record_status("t1", "done")
        out = ledger_mod.digest(self.ledger, self.log)
        first = out.splitlines()[0]
        self.assertEqual(first, "tasks: 1 of 3 done · 0 in-flight · 0 parked · "
                                "0 failed · 0 unknown")

    def test_runnable_line_lists_ids(self):
        out = ledger_mod.digest(self.ledger, self.log)
        self.assertIn("runnable: 1 — t1", out)

    def test_empty_runnable_is_definitive(self):
        self.log.record_status("t1", "in_progress")
        out = ledger_mod.digest(self.ledger, self.log)
        self.assertIn("runnable: 0 (1 in-flight, 2 blocked on deps)", out)

    def test_claims_only_flag_surfaces(self):
        self.assertIn("claims-only", ledger_mod.digest(self.ledger, self.log))
        with_artifacts = ledger_mod.digest(self.ledger, self.log, artifacts={})
        self.assertNotIn("claims-only", with_artifacts)

    def test_markdown_table_is_flattened_and_sorted(self):
        self.log.record_status("t1", "in_progress",
                               note="RLS policies: owner bypass covered")
        out = ledger_mod.digest(self.ledger, self.log)
        lines = out.splitlines()
        table = [ln for ln in lines if ln.startswith("|")]
        self.assertEqual(table[0], "| id | phase | profile | status | deps | note |")
        self.assertIn("| t1 | p1 | routine | in_progress | — | "
                      "RLS policies: owner bypass covered |", table)
        self.assertIn("| t3 | p2 | high | not_started | t1 |  |", table)
        # sorted by (phase, id): t1, t2 (p1) before t3 (p2)
        ids = [row.split("|")[1].strip() for row in table[2:]]
        self.assertEqual(ids, ["t1", "t2", "t3"])

    def test_discrepancies_surface_in_digest(self):
        self.log.record_status("t1", "in_progress")
        out = ledger_mod.digest(self.ledger, self.log,
                                artifacts={"t1": {"gate": "pass"}})
        self.assertIn("discrepancies: 1", out)
        self.assertIn("merge-gate artifact says pass", out)


if __name__ == "__main__":
    unittest.main()
