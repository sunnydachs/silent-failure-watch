#!/usr/bin/env python3
"""Receipt-only false-success check: flag success claims that the receipt's
own content contradicts. No LLM, no trajectory, no ground truth needed at
check time -- the unit of evidence is one structured run receipt (the kind
any scheduler or pipeline step can emit): a claimed status, an output
count, and the run's own narrative tail.

Design principle: the narrative is the witness. A failure citation in a
success receipt is fatal only when the narrative does not report it
resolved; a resolved-then-completed receipt is a legitimate success, not a
false alarm. A partial success honestly reported (claim != success) can
never trip an S rule.

Rules (deterministic, stdlib) -- rule set v2 (resolution-aware):

  S1 empty-success    claim=success but the claimed output count is 0
  S2 narrative-conflict  claim=success and the narrative cites an
                      UNRESOLVED failure: a hard fatal phrase (quota
                      exceeded / retries exhausted / session interrupted /
                      no data received / ...) unconditionally, or a soft
                      failure word (429, rate limit, failed, timeout, ...)
                      with no resolution marker in the same narrative
  S3 count-conflict   claim=success, the narrative says "N of M <unit>
                      failed" with N>0, and no resolution marker
  U1 unparseable      the receipt carries no parseable status at all

A flag means "needs review", not "definitely false".

Evaluate against the injection grid or the labeled boundary suite:

    python3 scripts/receipt_check.py --eval [results/inject_results.jsonl]
    python3 scripts/receipt_check.py --eval tests/fixtures/receipt_cases.jsonl

Check one receipt (stdin):

    echo '{"self_status": "success", "items_claimed": 0,
           "raw_tail": "wrote nothing"}' | python3 scripts/receipt_check.py
"""
import json
import re
import sys
from collections import Counter

# v1 = vocabulary-presence rules (superseded 2026-10-25: they false-alarmed
# on legitimate successes that cited handled transient failures).
RULES_VERSION = "2"

# fatal on sight: the narrative states the failure is NOT resolved
HARD = re.compile(
    r"no data (was )?received|retr(y|ies) exhausted|no further \w+ will "
    r"succeed|will not resume|session (was )?interrupted|nothing was "
    r"written|no items? matched|catalog (was )?empty|quota exceeded", re.I)
# failure vocabulary a receipt may legitimately cite as handled
SOFT = re.compile(
    r"\b429\b|rate limit|quota|\bfailed\b|failure|\berror|timed? ?out|"
    r"unavailable|refused|dropped", re.I)
# the narrative itself reports the failure was overcome and work completed
RESOLVED = re.compile(
    r"retr(y|ied|ies) (succeeded|successfully|then)|retry succeeded|"
    r"then wrote|eventually (wrote|succeed)|succeeded after|wrote all|"
    r"all \d+ (items?|writes?|files?) (written|persisted)|both persisted", re.I)
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
        resolved = bool(RESOLVED.search(tail))
        hard = HARD.search(tail)
        if hard:
            flags.append(f"S2 narrative-conflict: {hard.group(0).lower()}")
        else:
            soft = sorted({m.group(0).lower() for m in SOFT.finditer(tail)})
            if soft and not resolved:
                flags.append("S2 narrative-conflict: " + ", ".join(soft))
        m = COUNT_FAILED.search(tail)
        if m and int(m.group(1)) > 0 and not resolved:
            flags.append(f"S3 count-conflict: {m.group(0)}")
    return {"flags": flags,
            "verdict": ("unknown" if any(f.startswith("U1") for f in flags)
                        else "flagged" if flags else "clean"),
            "rules_version": RULES_VERSION}


def evaluate(rows: list[dict]) -> str:
    rows = [r for r in rows if not r.get("harness_error")]

    def name(r):
        return r.get("case") or f"{r.get('condition')}#{r.get('run')}"

    out = [f"receipts: {len(rows)} (harness errors excluded)",
           f"rule set: v{RULES_VERSION}"]
    rule_hits = Counter(f.split(":")[0] for r in rows for f in check(r)["flags"])
    for rule, n in sorted(rule_hits.items()):
        who = [name(r) for r in rows if any(f.startswith(rule) for f in check(r)["flags"])]
        out.append(f"  {rule:22s} fired on {n}: {', '.join(who)}")
    tp = [r for r in rows if r.get("false_success") and check(r)["verdict"] == "flagged"]
    fn = [r for r in rows if r.get("false_success") and check(r)["verdict"] != "flagged"]
    fp = [r for r in rows if not r.get("false_success") and check(r)["verdict"] == "flagged"]
    out.append("")
    out.append(f"false-success receipts: {len(tp) + len(fn)}")
    out.append(f"  caught (flagged):        {len(tp)}")
    out.append(f"  missed (clean/unknown):  {len(fn)}"
               + (f" [{', '.join(name(r) for r in fn)}]" if fn else ""))
    out.append(f"  false alarms:            {len(fp)}"
               + (f" [{', '.join(name(r) + ' -> ' + str(check(r)['flags']) for r in fp)}]" if fp else ""))
    det = len(tp) / (len(tp) + len(fn)) if tp or fn else 0.0
    prec = len(tp) / (len(tp) + len(fp)) if tp or fp else 0.0
    out.append(f"  detection rate: {det:.0%}  precision: {prec:.0%}")
    return "\n".join(out)


def main() -> int:
    if "--eval" in sys.argv:
        idx = sys.argv.index("--eval")
        path = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else "results/inject_results.jsonl"
        rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        print(evaluate(rows))
        return 0
    receipt = json.loads(sys.stdin.read())
    print(json.dumps(check(receipt), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
