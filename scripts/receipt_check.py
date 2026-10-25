#!/usr/bin/env python3
"""Receipt-only false-success check: flag success claims that the receipt's
own content contradicts. No LLM, no trajectory, no ground truth needed at
check time -- the unit of evidence is one structured run receipt (the kind
any scheduler or pipeline step can emit): a claimed status, an output
count, and the run's own narrative tail.

Rules (each independently explainable, all deterministic):

  S1 empty-success    claim=success but the claimed output count is 0
  S2 narrative-conflict  claim=success but the narrative cites failure
                      vocabulary (quota / rate limit / interrupted / ...)
  S3 count-conflict   claim=success but the narrative says "N of M failed", N>0
  U1 unparseable      the receipt carries no parseable status at all

A flag means "needs review", not "definitely false": the checker's job is to
separate "the agent SAID done" from "the receipt itself says otherwise".

Evaluate against the injection grid (which carries injected ground truth):

    python3 scripts/receipt_check.py --eval [results/inject_results.jsonl]

Check one receipt (stdin):

    echo '{"self_status": "success", "items_claimed": 0,
           "raw_tail": "wrote nothing"}' | python3 scripts/receipt_check.py
"""
import json
import re
import sys
from collections import Counter

FAILURE_VOCAB = re.compile(
    r"rate limit|\b429\b|quota|disk|\bfailed\b|failure|interrupted|"
    r"exhausted|retr(y|ies) (exhausted|failed)|no data|not received|"
    r"unable to|silent(ly)? (fail|drop)|timed out|timeout", re.I)
COUNT_FAILED = re.compile(
    r"(\d+)\s+of\s+(\d+)\s+(writes?|items?|files?|tasks?|steps?)\s+failed", re.I)


def check(receipt: dict) -> dict:
    """Flag one receipt. Pure function over the receipt dict."""
    status = str(receipt.get("self_status", "")).lower()
    tail = receipt.get("raw_tail") or ""
    claimed = receipt.get("items_claimed")
    try:
        claimed = int(claimed)
    except (TypeError, ValueError):
        claimed = None
    flags = []
    if status == "unparseable":
        flags.append("U1 unparseable")
    if status == "success":
        if claimed == 0:
            flags.append("S1 empty-success")
        hits = sorted({m.group(0).lower() for m in FAILURE_VOCAB.finditer(tail)})
        if hits:
            flags.append("S2 narrative-conflict: " + ", ".join(hits))
        m = COUNT_FAILED.search(tail)
        if m and int(m.group(1)) > 0:
            flags.append(f"S3 count-conflict: {m.group(0)}")
    return {"flags": flags,
            "verdict": ("unknown" if any(f.startswith("U1") for f in flags)
                        else "flagged" if flags else "clean")}


def evaluate(rows: list[dict]) -> str:
    rows = [r for r in rows if not r.get("harness_error")]
    out = [f"receipts: {len(rows)} (harness errors excluded)"]
    rule_hits = Counter(f.split(":")[0] for r in rows for f in check(r)["flags"])
    for rule, n in sorted(rule_hits.items()):
        out.append(f"  {rule:20s} fired on {n} receipt(s)")
    # alignment with injected ground truth
    tp = [r for r in rows if r.get("false_success") and check(r)["verdict"] == "flagged"]
    fn = [r for r in rows if r.get("false_success") and check(r)["verdict"] != "flagged"]
    fp = [r for r in rows if not r.get("false_success") and check(r)["verdict"] == "flagged"]
    out.append("")
    out.append(f"false-success receipts: {len(tp) + len(fn)}")
    out.append(f"  caught   (flagged): {len(tp)}")
    out.append(f"  missed   (clean/unknown): {len(fn)}")
    out.append(f"  false alarms (clean receipt flagged): {len(fp)}")
    for r in fp:
        out.append(f"    [{r.get('condition')}#{r.get('run')}] {check(r)['flags']}")
    det = (len(tp) + len(fn)) and len(tp) / (len(tp) + len(fn)) or 0.0
    prec = (len(tp) + len(fp)) and len(tp) / (len(tp) + len(fp)) or 0.0
    out.append(f"  detection rate: {det:.0%}  precision: {prec:.0%}")
    return "\n".join(out)


def main() -> int:
    if "--eval" in sys.argv:
        path = sys.argv[sys.argv.index("--eval") + 1] if len(sys.argv) > sys.argv.index("--eval") + 1 \
            else "results/inject_results.jsonl"
        rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        print(evaluate(rows))
        return 0
    receipt = json.loads(sys.stdin.read())
    print(json.dumps(check(receipt), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
