# silent-failure-watch

English | [日本語](README.ja.md)

Evidence repo for the article series on **false success in unattended agent
pipelines**: agents that report a job as done when the artifact, the data, or
the run itself never happened.

Two datasets live here, both measured on a real single-machine agent fleet
(a WSL2 laptop running cron-driven agents, 1,000 tracked executions,
exported 2026-10-24):

1. `data/fleet_runs.jsonl` — sanitized export of 1,000 real cron executions
   (status, generic job type, error class, duration, schedule lateness).
   Reproduce the summary with `python3 scripts/analyze_fleet.py`.
2. `experiments/inject/` — a small controlled grid: 4 environmental failure
   classes injected into a toy extraction task; each run scores the agent's
   own structured status report against a rule-based, state-checking
   verifier. Reproduce with `python3 experiments/inject/run_grid.py`.

The external anchor is arXiv:2606.09863 ("From Confident Closing to Silent
Failure"), which measures false success across 9,876 tau2-bench and 1,879
AppWorld trajectories. This repo contributes the two things a benchmark
cannot: what unattended failure looks like in a real fleet, and how much of
it a five-line state check catches that the agent's own status field does not.

## Layout

| Path | What it is |
|---|---|
| `data/fleet_runs.jsonl` | 1,000 sanitized execution records (the fleet numbers) |
| `scripts/analyze_fleet.py` | taxonomy + schedule-adherence summary over the export |
| `scripts/receipt_check.py` | receipt-only false-success checker: deterministic S1-S3 rules over one run's claim + narrative; `--eval` aligns flags with the grid's ground truth |
| `scripts/export_fleet.py` | site-specific exporter (reads a private cron DB; the mapping file is not committed) |
| `scripts/job_type_map.example.json` | shape of the site-specific job-type mapping |
| `experiments/inject/run_grid.py` | the controlled false-success grid |
| `tests/` | unit tests for the classifier and the verdict parser |
| `results/` | raw run records of the grid as executed (the subject model is deliberately unnamed — see limits) |

## Running

```bash
# fleet summary (stdlib only)
python3 scripts/analyze_fleet.py

# injection grid (any OpenAI-compatible endpoint)
export LLM_BASE_URL=...   # e.g. https://your-endpoint/v1
export LLM_API_KEY=...
export LLM_MODEL=...      # a general-purpose chat model
python3 experiments/inject/run_grid.py            # 5 conditions x 8 runs
python3 experiments/inject/run_grid.py --analyze   # summary from results JSONL

# tests
python3 -m pytest tests/ -q

# receipt-only false-success check (stdlib only, no LLM, no trajectory)
python3 scripts/receipt_check.py --eval             # flags vs the grid's ground truth
python3 scripts/receipt_check.py --eval tests/fixtures/receipt_cases.jsonl
echo '{"self_status": "success", "items_claimed": 0, "raw_tail": "wrote nothing"}' \
  | python3 scripts/receipt_check.py                # check one receipt on stdin
```

Two evaluations, two different claims:

- **Injection grid (40 real-model receipts):** 8/8 injected false successes
  flagged, 0 false alarms on the 8 clean runs — every false success in this
  grid claims `items_written: 0` with `status: "success"`, so all are caught
  by the empty-success rule (S1), with S2 corroborating via the
  "no items matched / catalog empty" citations. A demonstration on one task
  shape and one model, not a benchmark score.
- **Labeled boundary suite (`tests/fixtures/receipt_cases.jsonl`, 14
  synthetic cases):** 5/6 false successes caught, 0 false alarms. The
  must-not-flag set proves the two failure modes a naive vocabulary check
  gets wrong: a legitimate success that honestly cites a *handled*
  transient failure (429 retried, timeout recovered) stays clean, and an
  honest partial report (`status: "failed"/"partial"` with "2 of 4
  persisted") never trips an S rule. The one miss is the documented
  ceiling: doubt phrased outside the failure vocabulary ("assuming it
  landed") is invisible to a receipt-only check.

The grid needs a reasoning-capable chat model with a controllable thinking
budget; long default reasoning can exhaust `max_tokens` before any content is
emitted (observed: 570 reasoning tokens, zero answer tokens, `finish_reason:
length` at a 512-token cap). `run_grid.py` therefore sends a low effort by
default; traces in `results/` record the exact model and parameters used.

## Relation to prior work

The detection line that exists today operates **inside one episode, on the
trajectory**:

- arXiv:2511.04032 (2025-11) — first systematic anomaly detection over agent
  trajectories (drift, cycles, missing details): supervised XGBoost / SVDD on
  curated trajectory datasets (4,275 + 894). Needs the full trajectory stream
  and labeled data.
- arXiv:2608.02464 (2026-08, `agent-trajectory-sentinel`) — real-time one-class
  behavioural monitor at ~200 µs/step, with committed traces. Needs per-step
  telemetry.
- AgentTelemetry (ACM 2026) — span-level observability conventions for agent
  orchestration phases. Needs instrumented spans.

This repo's tool works one layer down, where none of those inputs exist: an
**unattended scheduled job** whose evidence is a per-run receipt (claimed
status, output count, narrative tail) plus the scheduler's own records.
Trajectories are impractical to keep for cron-driven jobs; the check must be
LLM-free because it runs next to the scheduler, not next to the model. The
receipt checker therefore complements trajectory-level detection rather than
competing with it — it closes the scheduler-to-artifact gap that
trajectory stream does not reach. We do not claim detection tooling is
absent from the field; we claim this layer and this evidence unit are not
what those systems consume.

## Honest limits

- n=1,000 fleet executions on ONE machine with ONE scheduling stack: a case
  study, not an estimate for agent fleets in general.
- The injection grid is a toy task with known injected ground truth; it
  measures self-report reliability under failure, not end-to-end agent
  capability.
- The verifier in the grid is trivially correct because it reads state the
  harness controls. That is the point (a cheap state check beats a
  self-report), but it means the verifier column is a demonstration, not a
  benchmark score.
- The receipt checker's grid result (8/8 caught, 0 false alarms) rests on the
  one false-success class this grid produced (empty-success), one task shape,
  one unnamed model. S2/S3 are exercised by the synthetic boundary suite only
  (5/6 caught; the miss is a rule-ceiling case — doubt with no failure
  vocabulary) — a rule-level demonstration, not a model benchmark.
- The grid's subject model is deliberately unnamed — nowhere in the repo,
  traces included. Rerun the grid against any OpenAI-compatible chat model
  to test your own.

## Contributing

Issue reports with reproduction steps are welcome — especially additional
failure classes for the injection grid. A PR adding a condition should add
its ground-truth entry and a parser test alongside it.

## License

MIT — see [LICENSE](LICENSE).
