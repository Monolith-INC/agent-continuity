#!/usr/bin/env python3
"""Behavior tests for the SessionStart menu built from the session index."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS / "scripts"))

from registry import load_index, plugin_version  # noqa: E402

SCRIPT = HOOKS / "scripts" / "session_options.py"


def name_at(hours_ago: float, slug: str) -> str:
    return (datetime.now() - timedelta(hours=hours_ago)).strftime("%Y-%m-%d-%H%M%S") + f"-{slug}"


def record(title: str, status: str = "", forward: str = "") -> str:
    state = f"status: {status}\n" if status else ""
    link = f"\nNext: [[{forward}]]\n" if forward else ""
    return f"---\ndate: 2026-11-13\ntype: session\n{state}---\n\n# {title}\n{link}"


def git(project: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(project), *args], check=True, capture_output=True)


class StartMenuTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.vault = self.project / "AI_Codex"
        self.sessions = self.vault / "Agent_Sessions"
        self.sessions.mkdir(parents=True)
        git(self.project, "init", "-q", "-b", "main")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, name: str, text: str) -> Path:
        path = self.sessions / f"{name}.md"
        path.write_text(text, encoding="utf-8")
        return path

    def config(self, payload: dict) -> None:
        (self.project / ".claude").mkdir(exist_ok=True)
        (self.project / ".claude" / "agent-continuity.config.json").write_text(json.dumps(payload))

    def menu(self) -> str:
        env = {**os.environ, "CLAUDE_PROJECT_DIR": ""}
        return subprocess.run(
            ["python3", str(SCRIPT), str(self.project)],
            capture_output=True, text=True, check=True, env=env,
        ).stdout

    def test_no_records_and_no_vault_stay_silent(self) -> None:
        self.assertEqual(self.menu(), "")
        shutil.rmtree(self.vault)
        self.assertEqual(self.menu(), "")

    def test_menu_offers_resume_pick_and_fresh(self) -> None:
        old, new = name_at(30, "old-work"), name_at(1, "new-work")
        self.write(old, record("Old", "closed", new))
        self.write(new, record("New", "ongoing"))
        out = self.menu()
        self.assertIn(f"1. Resume the ongoing session: {new} (New)", out)
        self.assertIn(f"- {old} (Old) [closed]", out)
        self.assertIn("Start fresh", out)
        self.assertIn("wait for their choice", out)

    def test_old_orphan_is_upgraded_and_never_offered_for_resume(self) -> None:
        orphan, new = name_at(5000, "old-orphan"), name_at(1, "new-work")
        self.write(orphan, "# Old orphan\n")
        self.write(new, record("New", "closed"))
        out = self.menu()
        self.assertNotIn("Resume", out)
        self.assertIn("Upgraded 1 old-format session record", out)
        self.assertIn("status: closed", (self.sessions / f"{orphan}.md").read_text(encoding="utf-8"))

    def test_archived_hidden_and_recent_limit_applies(self) -> None:
        names = [name_at(h, f"s{h}") for h in (1, 2, 3, 4)]
        self.write(names[0], record("Gone", "archived"))
        self.write(names[1], record("B", "closed", names[0]))
        self.write(names[2], record("C", "closed", names[1]))
        self.write(names[3], record("D", "closed", names[2]))
        self.config({"vault": {"sessionOptions": {"recent": 2}}})
        out = self.menu()
        self.assertNotIn("Gone", out)
        self.assertIn(names[1], out)
        self.assertIn(names[2], out)
        self.assertNotIn(names[3], out)

    def test_session_over_eight_hours_is_closed_and_continued(self) -> None:
        long = name_at(9, "long-work")
        self.write(long, record("Long", "ongoing"))
        out = self.menu()
        self.assertNotIn("Resume the ongoing session", out)
        self.assertIn("more than 8 hours", out)
        self.assertIn(long, out)

    def test_different_checkout_asks_before_resuming(self) -> None:
        new = name_at(1, "new-work")
        self.write(new, record("New", "ongoing"))
        self.menu()
        git(self.project, "checkout", "-q", "-b", "other")
        out = self.menu()
        self.assertIn("Ask the user whether to close it and start a new session", out)
        self.assertIn("main", out)

    def test_unreadable_newest_record_recovers_from_last_readable(self) -> None:
        good, bad = name_at(3, "good-work"), name_at(1, "bad-work")
        self.write(good, record("Good", "closed", bad))
        self.write(bad, "")
        out = self.menu()
        self.assertIn(f"{bad} can't be read", out)
        self.assertIn(f"backlink to {good}", out)
        self.assertIn("without asking", out)

    def test_bad_vault_path_falls_back_and_asks_for_the_right_one(self) -> None:
        new = name_at(1, "new-work")
        self.write(new, record("New", "ongoing"))
        self.config({"vault": {"folder": "/somewhere/else"}})
        out = self.menu()
        self.assertIn("outside the project", out)
        self.assertIn(new, out)

    def test_index_records_plugin_version_and_ongoing(self) -> None:
        new = name_at(1, "new-work")
        self.write(new, record("New", "ongoing"))
        self.menu()
        index = load_index(self.vault)
        self.assertEqual(index["plugin"], plugin_version())
        self.assertEqual(index["ongoing"], new)
        self.assertEqual(index["checkout"]["branch"], "main")

    def test_menu_can_be_turned_off(self) -> None:
        self.write(name_at(1, "new-work"), record("New", "ongoing"))
        self.config({"vault": {"sessionOptions": {"enabled": False}}})
        self.assertEqual(self.menu(), "")


class BootstrapTests(unittest.TestCase):
    BOOTSTRAP = HOOKS / "scripts" / "bootstrap.sh"

    def run_bootstrap(self, project: Path) -> str:
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
        return subprocess.run(["bash", str(self.BOOTSTRAP)], capture_output=True, text=True, check=True, env=env).stdout

    def test_vault_outside_the_project_is_never_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, outside = Path(tmp) / "project", Path(tmp) / "outside"
            (project / ".claude").mkdir(parents=True)
            outside.mkdir()
            (outside / "README.md").write_text("SECRET OUTSIDE\n", encoding="utf-8")
            (project / "AI_Codex").mkdir()
            (project / "AI_Codex" / "README.md").write_text("inside readme\n", encoding="utf-8")
            for named in (str(outside), "../outside"):
                (project / ".claude" / "agent-continuity.config.json").write_text(json.dumps({"vault": {"folder": named}}))
                context = json.loads(self.run_bootstrap(project))["hookSpecificOutput"]["additionalContext"]
                self.assertNotIn("SECRET OUTSIDE", context)
                self.assertIn("inside readme", context)
                self.assertIn("outside the project", context)

    def test_bad_path_without_fallback_still_tells_the_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            (project / ".claude").mkdir(parents=True)
            (project / ".claude" / "agent-continuity.config.json").write_text(json.dumps({"vault": {"folder": "/nope"}}))
            context = json.loads(self.run_bootstrap(project))["hookSpecificOutput"]["additionalContext"]
            self.assertIn("Ask the user", context)


if __name__ == "__main__":
    unittest.main()
