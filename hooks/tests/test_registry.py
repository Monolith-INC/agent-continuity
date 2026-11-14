#!/usr/bin/env python3
"""Behavior tests for the session registry core: records, index, vault path, git triggers."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

HOOKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS / "scripts"))

import registry  # noqa: E402
from registry import (  # noqa: E402
    load_index,
    needs_reconcile,
    ongoing_of,
    over_cap,
    parse_record,
    refresh,
    resolve_vault,
    save_index,
    triggers,
)

OLD = "2025-01-01-100000-old-orphan"
MID = "2026-11-12-101500-mid-work"
NEW = "2026-11-13-200000-new-work"


def body(title: str, status: str = "", forward: str = "") -> str:
    state = f"status: {status}\n" if status else ""
    link = f"\nNext: [[{forward}]]\n" if forward else ""
    return f"---\ndate: 2026-11-13\ntype: session\n{state}---\n\n# {title}\n{link}"


def write(folder: Path, name: str, text: str) -> Path:
    path = folder / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return path


class ParseRecordTests(unittest.TestCase):
    def test_explicit_status_and_title(self) -> None:
        rec = parse_record(NEW, body("New", "closed"), 1.0)
        self.assertEqual((rec.status, rec.explicit, rec.title), ("closed", True, "New"))

    def test_missing_status_uses_forward_link_rule(self) -> None:
        self.assertEqual(parse_record(MID, body("Mid", forward=NEW), 1.0).status, "closed")
        self.assertEqual(parse_record(MID, body("Mid", forward=OLD), 1.0).status, "ongoing")
        self.assertFalse(parse_record(MID, body("Mid"), 1.0).explicit)

    def test_empty_or_broken_records_are_unreadable(self) -> None:
        self.assertEqual(parse_record(NEW, "  \n", 1.0).status, "unreadable")
        broken = parse_record(NEW, "---\nstatus: ongoing\n# never closed\n", 1.0)
        self.assertEqual(broken.status, "unreadable")
        self.assertIn("frontmatter", broken.problem)


class OngoingTests(unittest.TestCase):
    def test_only_the_newest_record_can_be_ongoing(self) -> None:
        records = (parse_record(NEW, body("New", "closed"), 1.0), parse_record(OLD, body("Old"), 1.0))
        self.assertIsNone(ongoing_of(records))

    def test_archived_records_are_skipped(self) -> None:
        records = (parse_record(NEW, body("New", "archived"), 1.0), parse_record(MID, body("Mid", "ongoing"), 1.0))
        self.assertEqual(ongoing_of(records).name, MID)

    def test_unreadable_newest_means_nothing_is_ongoing(self) -> None:
        records = (parse_record(NEW, "", 1.0), parse_record(MID, body("Mid", "ongoing"), 1.0))
        self.assertIsNone(ongoing_of(records))

    def test_eight_hour_cap(self) -> None:
        self.assertFalse(over_cap(NEW, datetime(2026, 11, 14, 3, 59)))
        self.assertTrue(over_cap(NEW, datetime(2026, 11, 14, 4, 1)))


class ReconcileNeedTests(unittest.TestCase):
    def test_current_format_chain_needs_nothing(self) -> None:
        records = (parse_record(NEW, body("New", "ongoing"), 1.0), parse_record(MID, body("Mid", "closed", NEW), 1.0))
        self.assertFalse(needs_reconcile(records))

    def test_missing_status_or_missing_forward_link_needs_work(self) -> None:
        self.assertTrue(needs_reconcile((parse_record(NEW, body("New"), 1.0),)))
        records = (parse_record(NEW, body("New", "ongoing"), 1.0), parse_record(MID, body("Mid", "closed"), 1.0))
        self.assertTrue(needs_reconcile(records))


class IndexTests(unittest.TestCase):
    def test_refresh_builds_newest_first_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            sessions = vault / "Agent_Sessions"
            sessions.mkdir()
            write(sessions, MID, body("Mid", "closed", NEW))
            write(sessions, NEW, body("New", "ongoing"))
            write(sessions, "README", "# not a record\n")
            records = refresh(sessions, {}, full=True)
            self.assertEqual([r.name for r in records], [NEW, MID])
            save_index(vault, {"records": records, "ongoing": NEW})
            self.assertEqual([r.name for r in registry.records_of(load_index(vault))], [NEW, MID])
            self.assertEqual((vault / ".agent-continuity" / ".gitignore").read_text(), "*\n")

    def test_refresh_reuses_unchanged_records_without_reading_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sessions = Path(tmp)
            path = write(sessions, MID, body("Mid", "closed", NEW))
            write(sessions, NEW, body("New", "ongoing"))
            first = refresh(sessions, {}, full=True)
            later = path.stat().st_mtime + 5
            os.utime(path, (later, later))
            seen = []
            original = registry.read_record
            with mock.patch.object(registry, "read_record", side_effect=lambda p: seen.append(p.stem) or original(p)):
                again = refresh(sessions, {"records": first}, full=True)
            self.assertEqual(seen, [MID])
            self.assertEqual([r.name for r in again], [NEW, MID])

    def test_light_refresh_picks_up_new_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sessions = Path(tmp)
            write(sessions, MID, body("Mid", "closed", NEW))
            first = refresh(sessions, {}, full=True)
            write(sessions, NEW, body("New", "ongoing"))
            self.assertEqual(ongoing_of(refresh(sessions, {"records": first}, full=False)).name, NEW)

    def test_corrupt_index_reads_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / ".agent-continuity").mkdir()
            (vault / ".agent-continuity" / "session-index.json").write_text("{not json")
            self.assertEqual(load_index(vault), {})


class VaultPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "project"
        (self.project / "AI_Codex").mkdir(parents=True)
        self.outside = Path(self.tmp.name) / "elsewhere"
        self.outside.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_default_vault_is_found_inside_the_project(self) -> None:
        self.assertEqual(resolve_vault(self.project, {}), (self.project / "AI_Codex", ""))

    def test_configured_folder_inside_the_project_is_used(self) -> None:
        (self.project / "Notes").mkdir()
        self.assertEqual(resolve_vault(self.project, {"vault": {"folder": "Notes"}}), (self.project / "Notes", ""))

    def test_outside_paths_are_refused_and_fall_back_to_the_default(self) -> None:
        link = self.project / "Linked"
        link.symlink_to(self.outside)
        for named in (str(self.outside), "../elsewhere", "Linked"):
            vault, notice = resolve_vault(self.project, {"vault": {"folder": named}})
            self.assertEqual(vault, self.project / "AI_Codex", named)
            self.assertIn("outside the project", notice)
            self.assertIn("Ask the user", notice)

    def test_no_fallback_still_explains_the_problem(self) -> None:
        (self.project / "AI_Codex").rmdir()
        vault, notice = resolve_vault(self.project, {"vault": {"folder": str(self.outside)}})
        self.assertIsNone(vault)
        self.assertIn("Ask the user", notice)


class TriggerTests(unittest.TestCase):
    BASE = {"head": "a", "upstream": "a", "pushed": False, "dirty": ["app.py"]}

    def test_nothing_changed_means_no_trigger(self) -> None:
        self.assertEqual(triggers(self.BASE, dict(self.BASE), ancestor=True), ())

    def test_first_change_to_a_file(self) -> None:
        now = {**self.BASE, "dirty": ["app.py", "lib.py"]}
        self.assertEqual(triggers(self.BASE, now, ancestor=True), ("first change to lib.py",))

    def test_editing_an_already_changed_file_is_not_a_trigger(self) -> None:
        self.assertEqual(triggers(self.BASE, {**self.BASE, "dirty": ["app.py"]}, ancestor=True), ())

    def test_new_commit_versus_rollback_or_amend(self) -> None:
        moved = {**self.BASE, "head": "b", "dirty": []}
        self.assertEqual(triggers(self.BASE, moved, ancestor=True), ("new commit",))
        self.assertEqual(triggers(self.BASE, moved, ancestor=False), ("commit rolled back or amended",))

    def test_push(self) -> None:
        pushed = {**self.BASE, "head": "a", "upstream": "b", "pushed": True}
        self.assertIn("push", triggers({**self.BASE, "upstream": "c"}, pushed, ancestor=True))
        fetched = {**pushed, "pushed": False}
        self.assertNotIn("push", triggers({**self.BASE, "upstream": "c"}, fetched, ancestor=True))


if __name__ == "__main__":
    unittest.main()
