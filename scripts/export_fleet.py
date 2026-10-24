#!/usr/bin/env python3
"""Sanitized export of a cron-execution ledger -> fleet_runs.jsonl.

SITE-SPECIFIC: reads a private executions DB and maps opaque job ids to
generic types via a mapping file that is NOT committed
(scripts/job_type_map.json, shape in job_type_map.example.json).
Only generic fields are exported:

  {"ts": <started_at ISO>, "type": <generic job type>, "status": ok|fail|wedged,
   "err_class": <taxonomy class>, "dur_s": <duration or null>,
   "late_s": <started_at - scheduled_instant, seconds or null>}

Raw error texts are NEVER exported (they contain URLs and site names);
only the taxonomy class survives. Usage:

    CRON_EXEC_DB=/path/to/cron-executions.sqlite \
    JOB_TYPE_MAP=scripts/job_type_map.json \
    python3 scripts/export_fleet.py > data/fleet_runs.jsonl
"""
import json
import os
import re
import sqlite3
import sys


def classify(err: str) -> str:
    """Raw execution error text -> taxonomy class (shared with analyze)."""
    e = (err or "").strip()
    el = e.lower()
    if not e:
        return "no-error-text"
    if "interrupted" in el:
        return "interrupted"
    if "-15" in e and "adopting" in el:
        return "worker-sigterm-adoption"
    if "claim outlived" in el or "stale bound" in el:
        return "claim-stale-bound"
    if "limit reached" in el:
        return "queue-cap-wait"
    if "rate limit" in el or "429" in el or "free-tier" in el or "free tier" in el:
        return "rate-limit-quota"
    if "repetition loop" in el:
        return "model-repetition-loop"
    if "timeout" in el or "timed out" in el:
        return "timeout"
    if "script exited" in el or "exit 1" in el or "exit code 1" in el:
        return "script-exit-1"
    return "other"


def main() -> int:
    db_path = os.environ["CRON_EXEC_DB"]
    map_path = os.environ.get("JOB_TYPE_MAP", "scripts/job_type_map.json")
    mapping = json.load(open(map_path, encoding="utf-8"))

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cur = con.cursor()
    rows = cur.execute(
        "SELECT job_id, started_at, status, error, finished_at, scheduled_instant "
        "FROM executions ORDER BY started_at"
    ).fetchall()
    con.close()

    for job_id, started_at, status, error, finished_at, sched in rows:
        st = {"completed": "ok", "failed": "fail", "unknown": "wedged"}.get(status, status)
        dur = None
        if started_at and finished_at:
            try:
                import datetime
                a = datetime.datetime.fromisoformat(started_at)
                b = datetime.datetime.fromisoformat(finished_at)
                dur = round((b - a).total_seconds(), 1)
            except ValueError:
                pass
        late = None
        if started_at and sched:
            try:
                import datetime
                late = round((datetime.datetime.fromisoformat(started_at)
                               - datetime.datetime.fromisoformat(sched)).total_seconds(), 1)
            except ValueError:
                pass
        rec = {"ts": started_at, "type": mapping.get(job_id, "misc"), "status": st,
               "err_class": classify(error) if st != "ok" else "-",
               "dur_s": dur, "late_s": late}
        print(json.dumps(rec, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
