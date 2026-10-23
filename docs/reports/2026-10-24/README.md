# Research review — 24 October 2026

- [Implementation follow-up](IMPLEMENTATION_FOLLOWUP.md): six audit items addressed,
  depth deferred, simpler dashboard and 246 passing tests. **Read this for current status.**
- [Implementation audit](AUDIT_REPORT.md): seven original findings, reproduction evidence,
  code locations, corrections to earlier descriptions and existing limitations.
- [Future research programme](FUTURE_RESEARCH.md): twelve study/engineering areas,
  primary sources, experiments, completion gates and planning estimates.
- [Raw reproduction results](reproductions.json).
- SQLite cold-start output: [trial 1](sqlite-trial-1.txt),
  [trial 2](sqlite-trial-2.txt), [trial 3](sqlite-trial-3.txt).

## Original audit note (before the fixes)

The C++ and Python prototype was reviewed for correctness, information timing,
provenance and research validity. The core next-open backtest and modular numerical
boundary provide useful foundations. Live-data and authenticated model evaluation
remain pending.

Seven areas require correction: explicit synthetic provenance, quote identity,
instrument-specific monitoring state, zero-quantity depth, bar-frequency validation,
daily-bar news cutoffs and concurrent database initialization. Controlled fixtures
reproduce the boundary cases. The full suite produced 235 passes and one concurrency
failure; two of three isolated cold-start reruns also failed. This qualifies the
earlier successful test run.

The next phase should address those issues, establish data/session contracts and
corporate-action/cost handling, and compare deterministic, single-model and multi-role
workflows using point-in-time evidence. Prospective logging should start once data
access is available. No investment-performance claim is established. The proposed
8–12 week part-time programme is an estimate; access and observation time affect it.

Application behaviour was left unchanged during that original audit. The subsequent
[implementation follow-up](IMPLEMENTATION_FOLLOWUP.md) records the fixes and remaining limits.
