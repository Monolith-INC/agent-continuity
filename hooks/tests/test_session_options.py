#!/usr/bin/env python3
"""Behavior tests for the SessionStart menu built from Agent_Sessions/."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS / "scripts"))

from session_options import build_menu, is_unfinished, read_status, recent_records  # noqa: E402

OLD = "2026-11-10-090000-old-work"
MID = "2026-11-12-101500-mid-work"
NEW = "2026-11-13-200000-new-work"


def write(folder: Path, name: str, body: str) -> None:
    (folder / f"{name}.md").write_text(body, encoding="utf-8")


def record(title: str, forward: str = "", status: str = "") -> str:
    link = f"\nNext: [[{forward}]]\n" if forward else ""
    state = f"status: {status}\n" if status else ""
    return f"---\ndate: 2026-11-13\ntype: session\n{state}---\n\n# {title}\n{link}"


class RecentRecordsTests(unittest.TestCase):
    def test_missing_folder_yields_no_records(self) -> None:
        self.assertEqual(recent_records(Path("/nonexistent/Agent_Sessions"), 3), ())

    def test_newest_first_limited_and_ignores_non_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write(folder, OLD, record("Old"))
            write(folder, NEW, record("New"))
            write(folder, MID, record("Mid"))
            write(folder, "README", "# Sessions")
            (folder / "Agent_Sessions.base").write_text("views: []", encoding="utf-8")
            names = tuple(r.name for r in recent_records(folder, 2))
            self.assertEqual(names, (NEW, MID))

    def test_title_comes_from_first_heading_or_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write(folder, NEW, record("Ship the start menu"))
            write(folder, MID, "no heading here")
            titles = tuple(r.title for r in recent_records(folder, 3))
            self.assertEqual(titles, ("Ship the start menu", "mid work"))


class UnfinishedTests(unittest.TestCase):
    def test_record_without_forward_link_is_unfinished(self) -> None:
        self.assertTrue(is_unfinished(MID, record("Mid")))

    def test_record_linking_to_a_newer_record_is_closed(self) -> None:
        self.assertFalse(is_unfinished(MID, record("Mid", forward=NEW)))

    def test_backlink_to_an_older_record_does_not_close_it(self) -> None:
        self.assertTrue(is_unfinished(MID, f"Previous: [[{OLD}]]"))

    def test_aliased_and_pathed_links_count(self) -> None:
        self.assertFalse(is_unfinished(MID, f"Next: [[Agent_Sessions/{NEW}|next]]"))


class StatusTests(unittest.TestCase):
    def test_status_is_read_from_frontmatter(self) -> None:
        self.assertEqual(read_status(record("Mid", status="ongoing")), "ongoing")
        self.assertEqual(read_status(record("Mid", status="Closed")), "closed")

    def test_unknown_or_missing_status_reads_as_empty(self) -> None:
        self.assertEqual(read_status(record("Mid")), "")
        self.assertEqual(read_status(record("Mid", status="paused")), "")
        self.assertEqual(read_status("status: ongoing\n# not frontmatter"), "")

    def test_explicit_status_wins_over_forward_link_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write(folder, MID, record("Mid", forward=NEW, status="ongoing"))
            write(folder, NEW, record("New", status="closed"))
            states = {r.name: r.status for r in recent_records(folder, 3)}
            self.assertEqual(states, {NEW: "closed", MID: "ongoing"})

    def test_missing_status_falls_back_to_forward_link_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write(folder, MID, record("Mid", forward=NEW))
            write(folder, NEW, record("New"))
            states = {r.name: r.status for r in recent_records(folder, 3)}
            self.assertEqual(states, {NEW: "ongoing", MID: "closed"})

    def test_archived_records_are_left_out_and_do_not_use_up_the_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write(folder, OLD, record("Old", status="closed"))
            write(folder, MID, record("Mid", status="archived"))
            write(folder, NEW, record("New", status="ongoing"))
            names = tuple(r.name for r in recent_records(folder, 2))
            self.assertEqual(names, (NEW, OLD))


class MenuTests(unittest.TestCase):
    def test_no_records_yields_empty_menu(self) -> None:
        self.assertEqual(build_menu(()), "")

    def test_menu_offers_resume_pick_and_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write(folder, OLD, record("Old", forward=MID))
            write(folder, MID, record("Mid", forward=NEW))
            write(folder, NEW, record("New"))
            menu = build_menu(recent_records(folder, 3))
            self.assertIn("1. Resume the most recent ongoing session", menu)
            self.assertIn(f"{NEW} (New) [ongoing]", menu)
            self.assertIn("2. Pick a recent session (last 3, newest first)", menu)
            self.assertIn(f"{MID} (Mid) [closed]", menu)
            self.assertIn("3. Start fresh", menu)
            self.assertLess(menu.index(NEW), menu.index(MID))

    def test_menu_skips_resume_when_all_recent_are_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write(folder, NEW, record("New", forward="2026-11-14-000000-future"))
            menu = build_menu(recent_records(folder, 3))
            self.assertNotIn("Resume", menu)
            self.assertIn("1. Pick a recent session (last 1, newest first)", menu)
            self.assertIn("2. Start fresh", menu)


class BootstrapHookTests(unittest.TestCase):
    def run_hook(self, project: Path) -> str:
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
        result = subprocess.run(
            [str(HOOKS / "scripts" / "bootstrap.sh")],
            env=env, capture_output=True, text=True, check=True,
        )
        return result.stdout

    def make_vault(self, root: Path) -> Path:
        sessions = root / "AI_Codex" / "Agent_Sessions"
        sessions.mkdir(parents=True)
        (root / "AI_Codex" / "README.md").write_text("# Vault", encoding="utf-8")
        write(sessions, NEW, record("New"))
        return sessions

    def test_hook_appends_menu_to_bootstrap_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_vault(root)
            context = json.loads(self.run_hook(root))["hookSpecificOutput"]["additionalContext"]
            self.assertIn("# Vault", context)
            self.assertIn("Session start options", context)
            self.assertIn(NEW, context)

    def test_hook_respects_disable_switch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_vault(root)
            (root / ".claude").mkdir()
            (root / ".claude" / "agent-continuity.config.json").write_text(
                json.dumps({"vault": {"folder": "AI_Codex", "sessionOptions": {"enabled": False}}}),
                encoding="utf-8",
            )
            context = json.loads(self.run_hook(root))["hookSpecificOutput"]["additionalContext"]
            self.assertNotIn("Session start options", context)

    def test_hook_honors_recent_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sessions = self.make_vault(root)
            write(sessions, MID, record("Mid", forward=NEW))
            (root / ".claude").mkdir()
            (root / ".claude" / "agent-continuity.config.json").write_text(
                json.dumps({"vault": {"folder": "AI_Codex", "sessionOptions": {"recent": 1}}}),
                encoding="utf-8",
            )
            context = json.loads(self.run_hook(root))["hookSpecificOutput"]["additionalContext"]
            self.assertIn(NEW, context)
            self.assertNotIn(MID, context)


if __name__ == "__main__":
    unittest.main()
