#!/usr/bin/env python3
"""Behavior tests for upgrading old-format session records to the current format."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS / "scripts"))

from reconcile_sessions import apply, plan, set_frontmatter  # noqa: E402
from registry import parse_record  # noqa: E402

SCRIPT = HOOKS / "scripts" / "reconcile_sessions.py"
OLD = "2025-01-01-100000-old-orphan"
MID = "2026-11-12-101500-mid-work"
NEW = "2026-11-13-200000-new-work"


def write(folder: Path, name: str, text: str) -> Path:
    path = folder / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return path


class FrontmatterTests(unittest.TestCase):
    def test_adds_a_block_when_there_is_none(self) -> None:
        out = set_frontmatter("# Old\nbody\n", MID, "closed")
        self.assertTrue(out.startswith("---\ndate: 2026-11-12\ntype: session\nstatus: closed\n---\n"))
        self.assertTrue(out.endswith("# Old\nbody\n"))

    def test_replaces_a_bad_status_and_keeps_other_keys(self) -> None:
        out = set_frontmatter("---\ndate: 2026-11-12\ntype: session\nstatus: done\ntags: [a]\n---\n# Mid\n", MID, "closed")
        self.assertIn("status: closed\n", out)
        self.assertNotIn("status: done", out)
        self.assertIn("tags: [a]\n", out)
        self.assertEqual(out.count("date:"), 1)


class PlanTests(unittest.TestCase):
    def test_orphan_old_record_is_closed_and_linked_forward(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sessions = Path(tmp)
            write(sessions, OLD, "# Old orphan\nno status\n")
            write(sessions, NEW, f"---\ndate: 2026-11-13\ntype: session\nstatus: closed\n---\n# New\n")
            changes = {c.name: c for c in plan(sessions)}
            self.assertEqual(set(changes), {OLD})
            fixed = parse_record(OLD, changes[OLD].text, 1.0)
            self.assertEqual((fixed.status, fixed.explicit, fixed.forward), ("closed", True, True))

    def test_newest_unlinked_legacy_record_stays_ongoing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sessions = Path(tmp)
            write(sessions, MID, f"# Mid\n[[{NEW}]]\n")
            write(sessions, NEW, f"# New\n[[{MID}]]\n")
            changes = {c.name: c for c in plan(sessions)}
            self.assertEqual(parse_record(NEW, changes[NEW].text, 1.0).status, "ongoing")
            self.assertEqual(parse_record(MID, changes[MID].text, 1.0).status, "closed")

    def test_extra_ongoing_records_are_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sessions = Path(tmp)
            write(sessions, MID, f"---\ndate: 2026-11-12\ntype: session\nstatus: ongoing\n---\n# Mid\n[[{NEW}]]\n")
            write(sessions, NEW, "---\ndate: 2026-11-13\ntype: session\nstatus: ongoing\n---\n# New\n")
            changes = {c.name: c for c in plan(sessions)}
            self.assertEqual(set(changes), {MID})
            self.assertEqual(parse_record(MID, changes[MID].text, 1.0).status, "closed")

    def test_current_format_and_unreadable_records_are_left_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sessions = Path(tmp)
            write(sessions, MID, "---\nstatus: closed\n# never closed\n")
            write(sessions, NEW, "---\ndate: 2026-11-13\ntype: session\nstatus: ongoing\n---\n# New\n")
            self.assertEqual(plan(sessions), ())


class ApplyTests(unittest.TestCase):
    def test_apply_writes_and_keeps_a_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            sessions = vault / "Agent_Sessions"
            sessions.mkdir()
            original = "# Old orphan\n"
            path = write(sessions, OLD, original)
            write(sessions, NEW, "---\ndate: 2026-11-13\ntype: session\nstatus: ongoing\n---\n# New\n")
            backup = apply(vault, sessions, plan(sessions), "20261114-010000")
            self.assertIn("status: closed", path.read_text(encoding="utf-8"))
            self.assertEqual((backup / f"{OLD}.md.bak").read_text(encoding="utf-8"), original)
            self.assertEqual(plan(sessions), ())

    def test_cli_is_a_dry_run_unless_asked_to_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            sessions = project / "AI_Codex" / "Agent_Sessions"
            sessions.mkdir(parents=True)
            path = write(sessions, OLD, "# Old orphan\n")
            env = {**os.environ, "CLAUDE_PROJECT_DIR": ""}
            run = lambda *a: subprocess.run(  # noqa: E731
                ["python3", str(SCRIPT), "--project", str(project), *a],
                capture_output=True, text=True, check=True, env=env,
            ).stdout
            self.assertIn(OLD, run())
            self.assertEqual(path.read_text(encoding="utf-8"), "# Old orphan\n")
            self.assertIn("Upgraded 1", run("--apply"))
            self.assertIn("status: ongoing", path.read_text(encoding="utf-8"))
            self.assertIn("already in the current format", run())


if __name__ == "__main__":
    unittest.main()
