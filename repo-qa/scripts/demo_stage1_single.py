"""Stage1 refactor demo (single)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    out = repo_root / "experiments" / "comparison_reports" / "demo_single_report.json"
    cmd = [
        sys.executable,
        "scripts/run_single.py",
        "--offline",
        "--question-file",
        "q3_default_agent_action_flow.txt",
        "--report-file",
        str(out),
    ]
    proc = subprocess.run(cmd, cwd=repo_root)
    if proc.returncode != 0:
        return proc.returncode
    print(json.dumps(json.loads(out.read_text(encoding="utf-8")), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
