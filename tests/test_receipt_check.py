"""Tests for the receipt-only false-success checker (scripts/receipt_check.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from receipt_check import check, evaluate  # noqa: E402


def test_s1_empty_success_flags():
    r = check({"self_status": "success", "items_claimed": 0,
               "raw_tail": '{"status": "success", "items_written": 0}'})
    assert r["verdict"] == "flagged" and any(f.startswith("S1") for f in r["flags"])


def test_s2_narrative_conflict_flags():
    r = check({"self_status": "success", "items_claimed": 4,
               "raw_tail": "wrote items 1,3,5,9 after the disk quota was exceeded on the first try"})
    assert r["verdict"] == "flagged" and any(f.startswith("S2") for f in r["flags"])


def test_s3_count_conflict_flags():
    r = check({"self_status": "success", "items_claimed": 4,
               "raw_tail": 'tool said: "2 of 4 writes failed (disk quota exceeded)." status ok'})
    assert r["verdict"] == "flagged" and any(f.startswith("S3") for f in r["flags"])


def test_clean_control_receipt_passes():
    r = check({"self_status": "success", "items_claimed": 4,
               "raw_tail": 'Filtered catalog for price >= 100; wrote ids 1, 3, 5, 9.'})
    assert r["verdict"] == "clean" and r["flags"] == []


def test_unparseable_is_unknown_not_flagged():
    r = check({"self_status": "unparseable", "items_claimed": None, "raw_tail": "..."})
    assert r["verdict"] == "unknown"


def test_correctly_reported_failure_is_not_a_false_alarm():
    # an honest failure claim can never trip S1-S3 (they require claim=success)
    r = check({"self_status": "failed", "items_claimed": 2,
               "raw_tail": "2 of 4 writes failed (disk quota exceeded)"})
    assert r["verdict"] == "clean"


def test_eval_alignment_on_fixture():
    rows = [
        {"condition": "control", "run": 1, "ground_truth": "ok", "self_status": "success",
         "items_claimed": 4, "raw_tail": "wrote ids 1, 3", "false_success": False},
        {"condition": "empty-input", "run": 1, "ground_truth": "fail", "self_status": "success",
         "items_claimed": 0, "raw_tail": "catalog empty", "false_success": True},
        {"condition": "empty-input", "run": 2, "ground_truth": "fail", "self_status": "failed",
         "items_claimed": 0, "raw_tail": "catalog empty", "false_success": False},
    ]
    text = evaluate(rows)
    assert "caught   (flagged): 1" in text
    assert "false alarms (clean receipt flagged): 0" in text
    assert "detection rate: 100%" in text and "precision: 100%" in text
