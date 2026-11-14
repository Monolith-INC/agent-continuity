#!/usr/bin/env python3
"""Behavior tests for the hooks that keep the session registry fresh."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "session_freshness.py"
RECORD = "2026-11-13-200000-new-work"


def run(mode: str, project: Path, payload: dict) -> str:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
    result = subprocess.run(
        ["python3", str(SCRIPT), mode],
        input=json.dumps(payload), env=env, capture_output=True, text=True, check=True,
    )
    return result.stdout


def git(project: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(project), *args], check=True, capture_output=True)


def make_project(root: Path, status: str = "ongoing") -> Path:
    sessions = root / "AI_Codex" / "Agent_Sessions"
    sessions.mkdir(parents=True)
    git(root, "init", "-q")
    (root / "app.py").write_text("print('v1')\n", encoding="utf-8")
    git(root, "add", "app.py")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    record = sessions / f"{RECORD}.md"
    record.write_text(f"---\ndate: 2026-11-13\ntype: session\nstatus: {status}\n---\n# New\n", encoding="utf-8")
    return record


def age(path: Path, seconds: int) -> None:
    past = time.time() - seconds
    os.utime(path, (past, past))


class StopHookTests(unittest.TestCase):
    def test_blocks_when_work_is_newer_than_the_ongoing_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            age(make_project(root), 600)
            (root / "app.py").write_text("print('v2')\n", encoding="utf-8")
            out = json.loads(run("stop", root, {"stop_hook_active": False}))
            self.assertEqual(out["decision"], "block")
            self.assertIn(RECORD, out["reason"])
            self.assertIn("Implementation Checkpoint", out["reason"])

    def test_allows_when_record_is_up_to_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = make_project(root)
            (root / "app.py").write_text("print('v2')\n", encoding="utf-8")
            age(root / "app.py", 600)
            record.touch()
            self.assertEqual(run("stop", root, {"stop_hook_active": False}), "")

    def test_never_blocks_twice_in_a_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            age(make_project(root), 600)
            (root / "app.py").write_text("print('v2')\n", encoding="utf-8")
            self.assertEqual(run("stop", root, {"stop_hook_active": True}), "")

    def test_vault_edits_alone_do_not_count_as_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            age(make_project(root), 600)
            (root / "AI_Codex" / "note.md").write_text("x", encoding="utf-8")
            self.assertEqual(run("stop", root, {"stop_hook_active": False}), "")

    def test_asks_to_open_a_record_when_none_is_ongoing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            age(make_project(root, status="closed"), 600)
            (root / "app.py").write_text("print('v2')\n", encoding="utf-8")
            out = json.loads(run("stop", root, {"stop_hook_active": False}))
            self.assertEqual(out["decision"], "block")
            self.assertIn("status: ongoing", out["reason"])

    def test_silent_without_a_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run("stop", Path(tmp), {"stop_hook_active": False}), "")

    def test_respects_disable_switch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            age(make_project(root), 600)
            (root / "app.py").write_text("print('v2')\n", encoding="utf-8")
            (root / ".claude").mkdir()
            (root / ".claude" / "agent-continuity.config.json").write_text(
                json.dumps({"vault": {"freshness": {"enabled": False}}}), encoding="utf-8")
            self.assertEqual(run("stop", root, {"stop_hook_active": False}), "")


class PromptHookTests(unittest.TestCase):
    def test_reminds_to_log_decisions_in_the_ongoing_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_project(root)
            out = json.loads(run("prompt", root, {"prompt": "go with option B"}))
            context = out["hookSpecificOutput"]["additionalContext"]
            self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
            self.assertIn("## Decision", context)
            self.assertIn(RECORD, context)

    def test_silent_when_no_record_is_ongoing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_project(root, status="closed")
            self.assertEqual(run("prompt", root, {"prompt": "hi"}), "")


class StatusEnforcementTests(unittest.TestCase):
    NAMING = Path(__file__).resolve().parents[1] / "scripts" / "naming-enforcement.py"

    def write_hook(self, vault: Path, status_line: str) -> str:
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(vault / "Agent_Sessions" / f"{RECORD}.md"),
                "content": f"---\ndate: 2026-11-13\ntype: session\n{status_line}---\n# New\n",
            },
        }
        result = subprocess.run(["python3", str(self.NAMING)], input=json.dumps(payload),
                                capture_output=True, text=True, check=True)
        return result.stdout

    def make_vault(self, root: Path) -> Path:
        vault = root / "AI_Codex"
        (vault / "Agent_Sessions").mkdir(parents=True)
        (vault / ".agent-continuity-vault.json").write_text('{"type": "software-project"}', encoding="utf-8")
        return vault

    def test_accepts_each_allowed_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = self.make_vault(Path(tmp))
            for status in ("ongoing", "closed", "archived"):
                self.assertEqual(self.write_hook(vault, f"status: {status}\n"), "")

    def test_rejects_unknown_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = self.make_vault(Path(tmp))
            out = json.loads(self.write_hook(vault, "status: paused\n"))
            self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("ongoing", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_rejects_missing_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = self.make_vault(Path(tmp))
            out = json.loads(self.write_hook(vault, ""))
            self.assertIn("status", out["hookSpecificOutput"]["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()
