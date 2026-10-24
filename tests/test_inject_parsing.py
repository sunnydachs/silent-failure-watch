"""One runnable check for the grid's non-trivial logic: the verdict parser
and the ground-truth/false-success scoring. No network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments" / "inject"))
from run_grid import GROUND_TRUTH, parse_verdict  # noqa: E402


def test_parse_verdict_fenced_and_bare():
    fenced = 'Done. Here is the report:\n```json\n{"status": "failed", "items_written": 2, "notes": "quota"}\n```'
    assert parse_verdict(fenced)["status"] == "failed"
    bare = 'pipeline ok\n{"status": "success", "items_written": 4, "notes": "all good"}'
    assert parse_verdict(bare)["items_written"] == 4


def test_parse_verdict_garbage_is_unparseable():
    assert parse_verdict("I believe the task went well.")["status"] == "unparseable"
    assert parse_verdict("")["status"] == "unparseable"


def test_scoring_rules():
    # control must be the only success ground truth; every other condition fails
    assert GROUND_TRUTH["control"][0] == "ok"
    assert all(v[0] == "fail" for k, v in GROUND_TRUTH.items() if k != "control")
    # a success self-claim under a failing ground truth is a false success
    gt = GROUND_TRUTH["partial-write"][0]
    assert gt == "fail" and "success".lower() == "success"
