"""Stage1 refactor demo (batch)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


QUESTIONS = [
    "q1_timeout_exception.txt",
    "q2_config_loading.txt",
]


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    output_dir = repo_root / "experiments" / "comparison_reports" / "demo_batch"
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for q in QUESTIONS:
        report = output_dir / f"{Path(q).stem}.json"
        cmd = [
            sys.executable,
            "scripts/run_single.py",
            "--offline",
            "--question-file",
            q,
            "--report-file",
            str(report),
        ]
        proc = subprocess.run(cmd, cwd=repo_root)
        if proc.returncode != 0:
            return proc.returncode
        reports.append(json.loads(report.read_text(encoding="utf-8")))

    aggregate = {
        "schema_version": "stage1_batch_report.v1",
        "total": len(reports),
        "completion_rate_avg": round(sum(r.get("completion_rate", 0.0) for r in reports) / max(1, len(reports)), 4),
        "reports": reports,
    }
    out = output_dir / "aggregate.json"
    out.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
