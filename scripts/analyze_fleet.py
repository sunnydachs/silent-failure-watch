#!/usr/bin/env python3
"""Summary over the sanitized fleet export: status mix, failure taxonomy,
schedule adherence. Stdlib only, deterministic.

    python3 scripts/analyze_fleet.py [data/fleet_runs.jsonl]
"""
import json
import sys
from collections import Counter


def load(path: str):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def summarize(runs: list[dict]) -> str:
    n = len(runs)
    by_status = Counter(r["status"] for r in runs)
    non_ok = [r for r in runs if r["status"] != "ok"]
    by_class = Counter(r["err_class"] for r in non_ok)
    by_type_fail = Counter(r["type"] for r in non_ok)

    late = [r["late_s"] for r in runs if r.get("late_s") is not None]
    late.sort()
    def pct(p):
        return late[int(len(late) * p)] if late else None
    late_over_60 = sum(1 for x in late if x > 60)

    out = []
    out.append(f"executions: {n}")
    out.append("status: " + ", ".join(f"{k}={v}" for k, v in by_status.most_common()))
    out.append(f"non-ok rate: {len(non_ok)}/{n} = {len(non_ok)/n:.1%}")
    out.append("")
    if non_ok:
        out.append("failure taxonomy (non-ok runs):")
        for cls, c in by_class.most_common():
            out.append(f"  {cls:26s} {c:3d} ({c/len(non_ok):.0%})")
        out.append("")
        out.append("non-ok by job type:")
        for t, c in by_type_fail.most_common():
            out.append(f"  {t:22s} {c:3d}")
    else:
        out.append("failure taxonomy: (no non-ok runs)")
    out.append("")
    if late:
        out.append("schedule adherence (start minus scheduled, seconds):")
        out.append(f"  n={len(late)} median={late[len(late)//2]}s p90={pct(0.9)}s max={late[-1]}s")
        out.append(f"  started >60s late: {late_over_60}/{len(late)} = {late_over_60/len(late):.1%}")
    return "\n".join(out)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/fleet_runs.jsonl"
    print(summarize(load(path)))
