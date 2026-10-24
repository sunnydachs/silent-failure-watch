# silent-failure-watch

Evidence repo for the article series on **false success in unattended agent
pipelines**: agents that report a job as done when the artifact, the data, or
the run itself never happened.

Two datasets live here, both measured on a real single-machine agent fleet
(a WSL2 laptop running cron-driven agents, ~1,000 tracked executions):

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
| `scripts/export_fleet.py` | site-specific exporter (reads a private cron DB; the mapping file is not committed) |
| `scripts/job_type_map.example.json` | shape of the site-specific job-type mapping |
| `experiments/inject/run_grid.py` | the controlled false-success grid |
| `tests/` | unit tests for the classifier and the verdict parser |
| `results/` | raw run records of the grid as executed (model names live here, in trace metadata only) |

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
```

The grid needs a reasoning-capable chat model with a controllable thinking
budget; long default reasoning can exhaust `max_tokens` before any content is
emitted (observed: 570 reasoning tokens, zero answer tokens, `finish_reason:
length` at a 512-token cap). `run_grid.py` therefore sends a low effort by
default; traces in `results/` record the exact model and parameters used.

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
