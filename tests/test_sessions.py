"""Lifecycle contracts exercised through the production planner and filesystem interpreter."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/session-continue/scripts"))

from session_codec import decode, document, encode, request, session
from session_model import Active, Closed, EIGHT_HOURS, Event, Failure, Progress, Ready, Request, identity, latest, plan
from session_store import execute, exclusive, observe, persist, save

BASE = Request("continue", "chat-1", "/project", "deliver the story")
PROGRESS = Progress(("docs/design.md",), ("docs/adr/001.md",), ("test run passed",), ("finish adapter",))
EVENT = Event("commit-abc", "commit", "succeeded", "", PROGRESS)


def started() -> Ready:
    return plan(BASE, (), (), 1000)


class SessionModelTests(unittest.TestCase):
    def test_first_session_round_trips_without_invented_context(self):
        first = started()
        self.assertEqual(first.session.progress, Progress())
        self.assertEqual(session(decode(encode(document(first.session)))), first.session)
        self.assertIsInstance(first.session.state, Active)

    def test_checkpoint_restores_all_evidence_and_unfinished_work(self):
        result = plan(replace(BASE, operation="checkpoint", event=EVENT), (started().session,), (), 2000)
        restored = plan(BASE, (result.session,), (), 3000)
        self.assertEqual(restored.session.progress, PROGRESS)
        self.assertEqual(restored.writes, ())
        self.assertEqual(session(decode(encode(document(result.session)))), result.session)

    def test_exact_eight_hour_boundary_and_idle_wakeup(self):
        first = started().session
        self.assertEqual(plan(BASE, (first,), (), 1000 + EIGHT_HOURS - 1).writes, ())
        boundary = plan(BASE, (first,), (), 1000 + EIGHT_HOURS)
        self.assertEqual(boundary.writes[0].state, Closed(1000 + EIGHT_HOURS, "elapsed"))
        awake = plan(BASE, (first,), (), 1000 + 5 * 24 * 60 * 60 * 1000)
        self.assertEqual(len(awake.writes), 2)
        self.assertEqual(awake.writes[0].state.at, 1000 + EIGHT_HOURS)
        self.assertEqual(awake.session.previous, first.id)
        self.assertEqual(plan(BASE, awake.writes, (), awake.session.started_at).writes, ())
        self.assertEqual(session(decode(encode(document(awake.writes[0])))), awake.writes[0])

    def test_checkpoint_retry_after_rollover_does_not_duplicate_event(self):
        saved = plan(replace(BASE, operation="checkpoint", event=EVENT), (started().session,), (), 2000)
        replay = plan(replace(BASE, operation="checkpoint", event=EVENT), (saved.session,), (), 2000 + EIGHT_HOURS)
        self.assertEqual(replay.disposition, "already-recorded")
        self.assertEqual(replay.writes, ())
        conflict = plan(replace(BASE, operation="checkpoint", event=replace(EVENT, outcome="failed")), (saved.session,), (), 3000)
        self.assertEqual(conflict.code, "event-conflict")

    def test_first_edit_is_once_per_file_per_session(self):
        edit = replace(EVENT, id="edit-1", kind="first-edit", path="src/a.py")
        saved = plan(replace(BASE, operation="checkpoint", event=edit), (started().session,), (), 2000)
        duplicate = plan(replace(BASE, operation="checkpoint", event=replace(edit, id="edit-2")), (saved.session,), (), 3000)
        self.assertEqual(len(duplicate.session.events), 1)
        self.assertEqual(len(duplicate.session.receipts), 1)
        next_session = plan(replace(BASE, operation="checkpoint", event=replace(edit, id="edit-3")), (saved.session,), (), 1000 + EIGHT_HOURS)
        self.assertEqual(len(next_session.session.events), 1)
        failed = plan(replace(BASE, operation="checkpoint", event=replace(edit, outcome="failed")), (started().session,), (), 2000)
        successful = plan(replace(BASE, operation="checkpoint", event=replace(edit, id="retry")), (failed.session,), (), 3000)
        self.assertEqual(len(successful.session.events), 2)

    def test_explicit_session_end_links_next_session_even_at_same_time(self):
        ended = plan(replace(BASE, operation="checkpoint", event=replace(EVENT, kind="session-end")), (), (), 1000)
        continued = plan(BASE, (ended.session,), (), 1000)
        self.assertEqual(continued.session.progress, PROGRESS)
        self.assertEqual(latest((ended.session, continued.session)), continued.session)
        self.assertEqual(continued.session.previous, ended.session.id)

    def test_checkout_or_explicit_intention_change_needs_consent(self):
        first = started().session
        changed = replace(BASE, checkout="/another-checkout")
        self.assertEqual(plan(changed, (first,), (), 2000).code, "needs-decision")
        accepted = plan(replace(changed, confirm_change=True), (first,), (), 2000)
        self.assertEqual(accepted.session.checkout, "/another-checkout")
        self.assertEqual(plan(replace(BASE, intention="different task"), (first,), (), 2000).code, "needs-decision")
        self.assertEqual(plan(replace(BASE, intention=""), (first,), (), 2000).writes, ())

    def test_first_explicit_intention_is_retained_for_later_change_detection(self):
        first = plan(replace(BASE, intention=""), (), (), 1000)
        adopted = plan(BASE, (first.session,), (), 2000)
        self.assertEqual(adopted.session.intention, BASE.intention)
        self.assertEqual(plan(replace(BASE, intention="another task"), (adopted.session,), (), 3000).code, "needs-decision")

    def test_suppressed_edit_receipt_survives_rollover(self):
        edit = replace(EVENT, kind="first-edit", id="edit-1", path="src/a.py")
        first = plan(replace(BASE, operation="checkpoint", event=edit), (), (), 1000)
        suppressed_event = replace(edit, id="edit-2")
        suppressed = plan(replace(BASE, operation="checkpoint", event=suppressed_event), (first.session,), (), 2000)
        rolled = plan(BASE, (suppressed.session,), (), 1000 + EIGHT_HOURS)
        replayed = plan(replace(BASE, operation="checkpoint", event=suppressed_event), rolled.writes, (), 2000 + EIGHT_HOURS)
        self.assertEqual(replayed.disposition, "already-recorded")
        self.assertEqual(replayed.writes, ())
        self.assertEqual(session(decode(encode(document(suppressed.session)))), suppressed.session)

    def test_clock_regression_is_recoverable_without_overwriting_evidence(self):
        self.assertEqual(plan(BASE, (started().session,), (), 999).code, "clock-regressed")

    def test_recovery_diagnostic_and_no_repeated_recovery_for_unchanged_damage(self):
        recovered = plan(BASE, (started().session,), ("bad.json:abc",), 2000)
        self.assertEqual(recovered.session.previous, started().session.id)
        self.assertEqual(recovered.session.notes, ("restored-readable-history",))
        self.assertEqual(plan(BASE, recovered.writes, ("bad.json:abc",), 3000).writes, ())
        changed_damage = plan(BASE, recovered.writes, ("bad.json:def",), 3000)
        self.assertEqual(changed_damage.disposition, "recovered")

    def test_recover_without_history_states_the_gap(self):
        fresh = plan(replace(BASE, operation="recover"), (), (), 1000)
        self.assertEqual(fresh.session.notes, ("history-unavailable",))

    def test_boundary_rejects_bad_json_and_unsafe_paths(self):
        raw = {"operation": "checkpoint", "chat": "a", "checkout": "b", "event": {
            "id": "e", "kind": "first-edit", "outcome": "succeeded", "path": "../outside", "progress": {
                "orientation": [], "decisions": [], "evidence": [], "unfinished": []}}}
        self.assertIsInstance(request(raw), Failure)
        self.assertIsInstance(request({**raw, "event": {**raw["event"], "kind": []}}), Failure)
        self.assertIsInstance(decode("broken"), Failure)
        self.assertIsInstance(session({**document(started().session), "observed_at": 0}), Failure)


class SessionStoreTests(unittest.TestCase):
    def test_real_files_restore_progress_and_replay_without_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            root = project / "docs/sessions"
            saved = execute(project, root, replace(BASE, operation="checkpoint", event=EVENT), 1000)
            path = root / identity(BASE.chat) / f"{saved.session.id}.json"
            raw = path.read_bytes()
            replayed = execute(project, root, replace(BASE, operation="checkpoint", event=EVENT), 2000)
            self.assertEqual(replayed.writes, ())
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(execute(project, root, BASE, 3000).session.progress, PROGRESS)

    def test_corrupt_latest_is_preserved_and_previous_state_recovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            root = project / "sessions"
            first = execute(project, root, replace(BASE, operation="checkpoint", event=EVENT), 1000)
            next_session = execute(project, root, BASE, 1000 + EIGHT_HOURS)
            damaged = root / identity(BASE.chat) / f"{next_session.session.id}.json"
            damaged.write_text("broken", encoding="utf-8")
            recovered = execute(project, root, BASE, 2000 + EIGHT_HOURS)
            self.assertEqual(recovered.session.previous, first.session.id)
            self.assertEqual(recovered.session.progress, PROGRESS)
            self.assertEqual(damaged.read_text(encoding="utf-8"), "broken")
            self.assertEqual(execute(project, root, BASE, 3000 + EIGHT_HOURS).writes, ())

    def test_two_chats_have_independent_chains(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            root = project / "sessions"
            first = execute(project, root, replace(BASE, operation="checkpoint", event=EVENT), 1000)
            other = execute(project, root, replace(BASE, chat="chat-2"), 1000)
            self.assertNotEqual(first.session.id, other.session.id)
            self.assertEqual(other.session.previous, first.session.id)
            self.assertEqual(other.session.progress, PROGRESS)
            self.assertEqual(execute(project, root, BASE, 2000).writes, ())
            different_checkout = execute(project, root, replace(BASE, chat="chat-3", checkout="/different"), 2000)
            self.assertEqual(different_checkout.session.previous, "")

    def test_new_chat_restores_successor_progress_when_rollover_times_tie(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            root = project / "sessions"
            base = replace(BASE, chat="a")
            execute(project, root, base, 1000)
            checkpoint = execute(project, root, replace(base, operation="checkpoint", event=EVENT), 1000 + EIGHT_HOURS)
            new_chat = execute(project, root, replace(BASE, chat="b"), 2000 + EIGHT_HOURS)
            self.assertEqual(new_chat.session.previous, checkpoint.session.id)
            self.assertEqual(new_chat.session.progress, PROGRESS)

    def test_same_time_recovery_preserves_corrupt_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            root = project / "sessions"
            first = execute(project, root, BASE, 1000)
            damaged = root / identity(BASE.chat) / f"{first.session.id}.json"
            damaged.write_text("broken", encoding="utf-8")
            recovered = execute(project, root, replace(BASE, operation="recover"), 1000)
            self.assertNotEqual(recovered.session.id, first.session.id)
            self.assertEqual(damaged.read_text(), "broken")

    def test_writer_lock_is_nonblocking_and_releases(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            root = project / "sessions"
            first = execute(project, root, BASE, 1000)
            with exclusive(root / identity(BASE.chat) / ".writer.lock"):
                self.assertEqual(execute(project, root, BASE, 2000).code, "storage-unavailable")
            self.assertEqual(execute(project, root, BASE, 2000).session.id, first.session.id)

    def test_changed_snapshot_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            root = project / "sessions"
            first = execute(project, root, BASE, 1000)
            directory = root / identity(BASE.chat)
            observed = observe(directory, BASE.chat)
            (directory / "external.json").write_text("{}", encoding="utf-8")
            result = persist(directory, BASE, observed, plan(BASE, observed.sessions, (), 1000 + EIGHT_HOURS))
            self.assertEqual(result.code, "concurrent-change")
            self.assertIsInstance(session(json.loads((directory / f"{first.session.id}.json").read_text() )).state, Active)

    def test_interrupted_rollover_keeps_saved_progress_and_can_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            root = project / "sessions"
            first = execute(project, root, replace(BASE, operation="checkpoint", event=EVENT), 1000)
            next_plan = plan(BASE, (first.session,), (), 1000 + EIGHT_HOURS)
            blocked = root / identity(BASE.chat) / f"{next_plan.session.id}.json"
            blocked.mkdir()
            with self.assertRaises(OSError):
                save(blocked.parent, next_plan.writes)
            closed = session(json.loads((blocked.parent / f"{first.session.id}.json").read_text()))
            self.assertIsInstance(closed.state, Closed)
            self.assertEqual(closed.progress, PROGRESS)
            blocked.rmdir()  # Remove only this test's empty obstacle.
            continued = execute(project, root, BASE, 2000 + EIGHT_HOURS)
            self.assertEqual(continued.session.previous, first.session.id)
            self.assertEqual(continued.session.progress, PROGRESS)

    @unittest.skipUnless(hasattr(Path, "symlink_to"), "requires symbolic links")
    def test_symbolic_link_or_traversal_cannot_redirect_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            outside = project / "outside"
            outside.mkdir()
            (project / "linked").symlink_to(outside, target_is_directory=True)
            self.assertEqual(execute(project, project / "linked/sessions", BASE, 1000).code, "unsafe-root")
            self.assertEqual(execute(project, project / "../escape", BASE, 1000).code, "unsafe-root")
            self.assertEqual(tuple(outside.iterdir()), ())


if __name__ == "__main__":
    unittest.main()
