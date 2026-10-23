# Offline fixes and dashboard follow-up

**Date:** 24 October 2026. This follows the correctness audit of baseline `43a9b8c`.
No authenticated provider requests or new paid services were used.

## Delivered

| Audit item | Current behaviour |
| --- | --- |
| A01: demo provenance | Evidence receives an explicit dataset flag. Unknown provenance blocks the research gate; explicitly synthetic attachments also retain the synthetic label. Exported cards and reports carry the same evidence. |
| A02: quote identity | The adapter requires exactly one quote with an exact instrument token. Missing, mismatched, ambiguous and malformed identities are rejected. Verified using mocked responses; broker access remains untested. |
| A03: monitoring state | Live alert baselines and event deduplication use the exchange instrument key. Changing the instrument behind a display label starts a new baseline. Legacy symbol-only alert baselines are ignored. |
| A04: empty depth levels | Deferred at the user's request. The dashboard depth lab has been removed. The old native depth function is retained and still has the documented zero-quantity limitation; do not use it as validated research. |
| A05: daily frequency | CSV experiments require the user to confirm completed daily bars. Python experiment calls reject intraday, weekly and very sparse date spacing. The native CLI remains a daily-only interface and does not independently establish frequency. |
| A06: news cutoff | Date-only evidence requires an explicit timezone-aware decision time. Before-cutoff news is eligible and after-cutoff news is excluded. Missing cutoff blocks the evidence gate. The UI's editable 15:30 India-time default is a research convention, not an exchange-calendar lookup. |
| A07: SQLite startup | Initialization is serialized within a process, WAL activation retries only busy/locked errors for a bounded period, and connections close on initialization failure. Quota reservations remain atomic. Thread and separate-process cold-start tests pass. |

## Dashboard changes

Navigation and data selection are visible in the main page on a narrow screen.
Overview explains the workflow in a collapsed help panel, has fewer repeated labels,
and clearly distinguishes fictional prices from an imported historical file.
Market analysis calculates price structure independently, so there is no mandatory
Overview step. The indicator library, three-strategy comparison, simulations and
educational assistant remain available offline. Stock identifiers and connection
pages no longer show a misleading demo-dataset badge.

The existing C++17 / Python / Streamlit / SQLite architecture is retained. No new
application language, framework, service, or dependency was added. Small validation
helpers and ordinary functions are used instead of a new agent/orchestration framework.

## Verification and remaining work

- Full Python suite: **246 passed**, including native integration and Streamlit workflows.
- Ruff lint passed. Audit fixtures now show rejected unidentified quotes and weekly bars,
  retained synthetic provenance, correct same-day news inclusion and independent baselines.
- Six simultaneous Python processes against a new database respect the shared quota.
- The actual dashboard was restarted to clear cached modules and reviewed in the browser.
- [Current fixture output](followup_reproductions.json) is separate from the original audit evidence.

Daily-spacing checks do not prove calendar completeness or honest source metadata.
Corporate-action accounting, a dated India fee model, walk-forward evaluation,
survivorship-aware data and measured agent-quality comparisons remain research work.
Real quotes/news and OpenRouter require later credentials and provider validation.
Level 2/3 and executed order flow are outside the present implementation scope.

Suggested next offline sequence: corporate-action fixtures and accounting decisions;
then dated cost assumptions; then chronological evaluation with frozen strategy rules.
Validate those on permitted real historical data before making performance claims.
