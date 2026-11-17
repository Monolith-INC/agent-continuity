#!/usr/bin/env python3
"""Public JSON command for session continuation, checkpointing and recovery."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from session_codec import decode, document, encode, request
from session_model import Failure, Ready
from session_store import session_task


def reply(result: Ready | Failure, root: Path) -> dict:
    match result:
        case Failure(code=code, recovery=recovery):
            return {"ok": False, "code": code, "recovery": recovery, "workMayContinue": True}
        case Ready(session=saved, writes=writes, disposition=disposition):
            return {"ok": True, "disposition": disposition, "session": document(saved), "root": str(root),
                    "saved": tuple(s.id for s in writes), "approvalsAreHistorical": True}


def run(args) -> dict:
    project = Path(args.project).resolve()
    root = project / args.root
    try:
        supplied = request(decode(sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")))
        match supplied:
            case Failure():
                return reply(supplied, root)
            case _:
                return reply(session_task(project, root, supplied, int(datetime.now(timezone.utc).timestamp() * 1000))(), root)
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
        return reply(Failure("input-unavailable", "Check the input JSON and file access, then retry. No checkpoint was confirmed."), root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--root", required=True, help="Project-relative journal directory, selected by the project")
    parser.add_argument("--input", default="-", help="JSON file or - for stdin")
    result = run(parser.parse_args())
    print(encode(result), end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
