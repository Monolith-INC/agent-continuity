#!/usr/bin/env python3
"""Behavior tests for the hooks that keep the session registry fresh."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def name_at(hours_ago: float, slug: str) -> str:
    return (datetime.now() - timedelta(hours=hours_ago)).strftime("%Y-%m-%d-%H%M%S") + f"-{slug}"


def git(project: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(project), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True, capture_output=True, text=True,
    ).stdout


def age(path: Path, seconds: int) -> None:
    past = time.time() - seconds
    os.utime(path, (past, past))


class FreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "project"
        self.sessions = self.project / "AI_Codex" / "Agent_Sessions"
        self.sessions.mkdir(parents=True)
        git(self.project, "init", "-q", "-b", "main")
        (self.project / "app.py").write_text("print('v1')\n", encoding="utf-8")
        git(self.project, "add", "app.py")
        git(self.project, "commit", "-qm", "init")
        self.name = name_at(1, "new-work")
        self.record = self.write(self.name, "ongoing")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, name: str, status: str, extra: str = "") -> Path:
        path = self.sessions / f"{name}.md"
        path.write_text(f"---\ndate: 2026-11-13\ntype: session\nstatus: {status}\n---\n# Work\n{extra}", encoding="utf-8")
        age(path, 600)
        return path

    def run_script(self, script: str, *args: str, payload: dict | None = None) -> str:
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.project)}
        return subprocess.run(
            ["python3", str(SCRIPTS / script), *args],
            input=json.dumps(payload or {}), env=env, capture_output=True, text=True, check=True,
        ).stdout

    def start(self) -> str:
        return self.run_script("session_options.py", str(self.project))

    def stop(self, active: bool = False) -> dict:
        out = self.run_script("session_freshness.py", "stop", payload={"stop_hook_active": active})
        return json.loads(out) if out else {}

    def edit(self, name: str = "app.py", text: str = "print('v2')\n") -> None:
        (self.project / name).write_text(text, encoding="utf-8")

    def test_quiet_when_nothing_happened(self) -> None:
        self.start()
        self.assertEqual(self.stop(), {})

    def test_first_change_to_a_file_asks_once(self) -> None:
        self.start()
        self.edit()
        out = self.stop()
        self.assertEqual(out["decision"], "block")
        self.assertIn("first change to app.py", out["reason"])
        self.assertIn(self.name, out["reason"])
        self.assertEqual(self.stop(), {})
        self.edit(text="print('v3')\n")
        self.assertEqual(self.stop(), {})

    def test_changes_from_before_the_session_do_not_count(self) -> None:
        self.edit()
        self.start()
        self.assertEqual(self.stop(), {})

    def test_new_commit_and_amend(self) -> None:
        self.start()
        self.edit()
        self.stop()
        git(self.project, "commit", "-qam", "v2")
        self.assertIn("new commit", self.stop()["reason"])
        git(self.project, "commit", "-q", "--amend", "-m", "v2 amended")
        self.assertIn("rolled back or amended", self.stop()["reason"])

    def test_push(self) -> None:
        remote = Path(self.tmp.name) / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        git(self.project, "remote", "add", "origin", str(remote))
        git(self.project, "push", "-q", "-u", "origin", "main")
        self.start()
        self.edit()
        git(self.project, "commit", "-qam", "v2")
        self.stop()
        git(self.project, "push", "-q")
        self.assertIn("push", self.stop()["reason"])

    def test_no_block_when_the_record_was_already_updated(self) -> None:
        self.start()
        self.stop()
        self.edit()
        time.sleep(0.05)
        self.record.write_text(self.record.read_text() + "\n## Implementation Checkpoint - now\n", encoding="utf-8")
        self.assertEqual(self.stop(), {})

    def test_never_blocks_twice_in_a_row(self) -> None:
        self.start()
        self.edit()
        self.assertEqual(self.stop(active=True), {})

    def test_vault_edits_alone_do_not_count(self) -> None:
        self.start()
        (self.project / "AI_Codex" / "note.md").write_text("x", encoding="utf-8")
        self.assertEqual(self.stop(), {})

    def test_asks_to_open_a_record_when_none_is_ongoing(self) -> None:
        self.write(self.name, "closed")
        self.start()
        self.edit()
        reason = self.stop()["reason"]
        self.assertIn("no session record is ongoing", reason)
        self.assertIn("status: ongoing", reason)

    def test_unreadable_newest_record_recovers_without_asking(self) -> None:
        self.write(self.name, "closed")
        bad = name_at(0.5, "bad-work")
        (self.sessions / f"{bad}.md").write_text("", encoding="utf-8")
        self.start()
        self.edit()
        reason = self.stop()["reason"]
        self.assertIn(f"{bad} can't be read", reason)
        self.assertIn(f"backlink to {self.name}", reason)

    def test_eight_hour_cap_reached_mid_session_asks_once(self) -> None:
        self.record.unlink()
        self.write(name_at(9, "long-work"), "ongoing")
        reason = self.stop()["reason"]  # no session start: the index is built on demand
        self.assertIn("more than 8 hours", reason)
        self.assertIn("backlink", reason)
        self.assertEqual(self.stop(), {})

    def test_cap_reported_at_start_is_not_repeated(self) -> None:
        self.record.unlink()
        self.write(name_at(9, "long-work"), "ongoing")
        self.assertIn("more than 8 hours", self.start())
        self.assertEqual(self.stop(), {})

    def test_prompt_reminder_reads_only_the_index(self) -> None:
        self.assertEqual(self.run_script("session_freshness.py", "prompt"), "")
        self.start()
        out = json.loads(self.run_script("session_freshness.py", "prompt"))
        context = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Decision", context)
        self.assertIn(self.name, context)

    def test_can_be_turned_off(self) -> None:
        (self.project / ".claude").mkdir()
        (self.project / ".claude" / "agent-continuity.config.json").write_text(
            json.dumps({"vault": {"freshness": {"enabled": False}}})
        )
        self.start()
        self.edit()
        self.assertEqual(self.stop(), {})
        self.assertEqual(self.run_script("session_freshness.py", "prompt"), "")


if __name__ == "__main__":
    unittest.main()
