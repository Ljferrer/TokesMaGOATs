# Snipe report

## Scope

- Committed scope: range 9470e9d45a3e7473f646e8a99ba41828a1a730c3..570b924d903d4843ebdbd4715271f4a10da79753
- Revision: `570b924d903d4843ebdbd4715271f4a10da79753` (base `9470e9d45a3e7473f646e8a99ba41828a1a730c3`)
- Review coverage: complete
- Configured seat profile: `gpt-6-astra` / `medium` (actual model identity not independently verified)

## Seat outcomes

- Seat 1 · correctness: completed — validated; verdict request_changes; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_dashboard.cjs.
- Seat 2 · cascading-impact: completed — validated; verdict request_changes; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_dashboard.cjs.
- Seat 3 · test-fidelity: completed — validated; verdict request_changes; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_dashboard.cjs, test_app.py, test_snipe_usage.py.
- Seat 4 · security: completed — validated; verdict request_changes; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_dashboard.cjs.

## Findings

### Major · Activity-only dates disappear from the dashboard and CSV — would block in a phase

- Seats: 2 (cascading-impact)
- Location: `engineering.py`
- Evidence: The report's day rows are seeded only from delivery_usage and Git integrations. Dates present exclusively in agent_activity are never added. Both dashboard modes iterate these rows, and csv_report likewise iterates report['days']. Consequently, a response accounted before midnight with later fragments after midnight has its later-day activity collected but omitted from the dashboard and CSV when no other accounting or integration exists that day. Synthetic-only activity dates disappear for the same reason. test_maxima_earliest_accounting_cross_midnight_and_retention verifies the collector's later-day activity but never passes it through these consumers.
- Proposed correction: Include activity dates in the report's date-row union, preserving eligible=false when no positive-token accounting belongs to that date. Verify dashboard and CSV projections for cross-midnight and synthetic-only dates without adding them to the xEngineer denominator.
### Major · Cross-midnight fixture bypasses date filtering and dashboard day construction — would block in a phase

- Seats: 3 (test-fidelity)
- Location: `test_engineering.py`
- Evidence: The fixture checks ev.activity directly with an unrestricted date range. In evidence.py, selected_events first filters by the earliest accounting date, and activity builds response_identity/responding only from those selected events. Selecting January 2 alone for the fixture's response, accounted on January 1 but observed again on January 2, therefore loses its responding density; applying a model/role filter can remove the identity entirely. Independently, engineering.view constructs report days from delivery_usage and integrations, never activity-only dates, so even the unrestricted fixture's January 2 activity cannot appear in the dashboard's daily drilldown. The existing assertion of January 2 density does not exercise either public failure path.
- Proposed correction: Extend the fixture through engineering.view with the second date selected alone, and with matching model/role filters. Assert zero accounting on that date, preserved responding identity/density, and a visible report day outside the positive-token denominator. Select response observations independently of accounting-date inclusion, retain the rolling-window lookback, and include activity-only dates in report day construction without adding them to xEngineer eligibility.
### Major · Date filtering discards cross-midnight response activity — would block in a phase

- Seats: 1 (correctness)
- Location: `evidence.py`
- Evidence: Response identities and responding points are populated only from events selected by their accounting date. For a response first observed January 1 at 23:59:50 and updated January 2 at 00:00:10, selecting January 2 removes its event and provenance before activity calculation. The retained January 2 activity point cannot enter responding density because its key is absent from response_identity. Density therefore becomes N/A despite a retained response observation. Rolling windows likewise lose responses accounted before the selected start date. The cross-midnight test uses an unrestricted selection, so it misses this failure. Additionally, engineering.view builds drilldown days from accounting and integrations only, hiding activity-only dates. This would block in a phase.
- Proposed correction: Select response activity independently by observation timestamps, retaining the necessary window lookback and applying provider/model/role/project evidence consistently. Include activity-only dates in dashboard drilldowns while keeping them outside the positive-token denominator.
### Major · Date selection removes response evidence required for activity density — would block in a phase

- Seats: 2 (cascading-impact)
- Location: `evidence.py`
- Evidence: selected_events filters responses by their earliest accounting date before accounting returns provenance. activity then constructs response_identity exclusively from those selected responses and accepts retained response observations only when their key is in that map. For a response first observed January 1 at 23:59 and continuing January 2, selecting January 2 excludes its accounting record and therefore discards its January 2 response observations from density, despite retaining the identity's activity points. The same dependency loses pre-boundary observations required by rolling windows. The existing cross-midnight fixture uses an unrestricted date selection, so it cannot detect this selection-dependent result.
- Proposed correction: Separate accounting-date selection from activity-response selection. Retain response identity and observation evidence needed for the selected activity dates and preceding rolling-window lookback while continuing to assign token accounting exactly once. Add coverage for selecting only the later cross-midnight date.
### Major · Legacy-precedence regression test misses existing-ledger upgrades — would block in a phase

- Seats: 3 (test-fidelity)
- Location: `test_engineering.py`
- Evidence: The test imports its initial legacy record through the new sync implementation, which creates response_sources metadata. Existing ledgers from the pinned base have no such metadata. In app.py:sync, removal of superseded legacy events depends exclusively on finding legacy_delta IDs in response_sources. If an existing ledger contains a 105-token cumulative event and its source gains the equivalent detailed response before the first upgraded sync, records() yields only the detailed response, legacy_ids is empty, and both events remain: 210 tokens. The test passes despite this upgrade path violating detailed-record precedence and inflating existing accounting and downstream metrics. This conclusion follows from pinned source inspection; tests were not executed.
- Proposed correction: Add a fixture representing the base-version ledger, with an imported legacy event and no provenance, then sync a source containing its cumulative record and matching detailed response. Assert one retained accounting contribution through both summary and engineering accounting. Reconcile identifiable legacy records during migration without relying solely on provenance created by the new implementation or deleting unrelated session usage.
### Major · Private engineering GET endpoints lack Host validation — would block in a phase

- Seats: 4 (security)
- Location: `app.py`
- Evidence: The new assessment endpoint returns complete private assessments and repository snapshots without validating Host. The expanded usage endpoint also returns private work-item evidence. Host/Origin validation exists only in do_POST. An attacker-controlled origin that rebinds to 127.0.0.1 can therefore read these GET responses in browsers permitting the connection: the browser sees a same-origin request while the server accepts the foreign Host. Loopback binding and absent CORS headers do not close that boundary. This exposes repository paths, commit subjects, scope descriptions and private review references despite the share-export redaction. The underlying GET guard omission predates this change, but the new routes and expanded responses expose additional private evidence through it. This would block in a phase. Inspection was static; no browser exploit or tests were executed.
- Proposed correction: Apply the existing exact localhost/127.0.0.1 Host allowlist before dispatching GET requests as well as POST requests. Add HTTP regression coverage showing that a foreign Host cannot retrieve either assessment or usage evidence, while supported local Hosts continue to work.
### Major · Reconciliation can prevent legacy accounting from being superseded — would block in a phase

- Seats: 1 (correctness)
- Location: `app.py`
- Evidence: Legacy removal depends on response_sources still containing legacy_delta rows for the same source. Starting with an imported cumulative record, append detailed records and run --reconcile before sync: save_provenance deletes the old provenance and replaces it with detailed provenance without changing events. The next sync finds no legacy_ids, so it retains the cumulative event and inserts the detailed response, double-counting usage. The same dependency fails for pre-feature ledgers without provenance. The inspected supersession test covers only direct sync, not reconciliation between imports. This would block in a phase.
- Proposed correction: Preserve durable supersession information independently of replaceable raw observations, and remove matched legacy accounting when detailed history becomes authoritative. Cover reconcile-before-sync and upgrading an existing ledger.
### Major · Unknown cache counters can be reported as raw verified — would block in a phase

- Seats: 1 (correctness)
- Location: `evidence.py`
- Evidence: The complete-source check requires only known input and output. A Codex record with input_tokens and output_tokens but no cached_input_tokens is normalized to cached=0, passes the equality check, and contributes all tokens to raw_verified and potentially 100% reconciliation coverage. The same record is simultaneously counted as having unknown counters. This treats an absent raw cache counter as a reproduced explicit zero, contrary to the required unknown-counter distinction. The missing-counter fixture deletes output_tokens and does not exercise this branch. This would block in a phase.
- Proposed correction: Require known values for every counter used to establish normalized accounting reconciliation, allowing only explicitly defined provider zeros. Keep partially reproduced records distinguishable from fully verified records and test missing cache counters.
### Major · Weekly output and total estimated hours omit assessed delivery on non-token dates — would block in a phase

- Seats: 1 (correctness)
- Location: `engineering.py`
- Evidence: statistics_for filters to eligible token-active dates before calculating total_estimated_hours. Weekly engineer_days then divides that restricted total by eight. An assessed Saturday integration with eight estimated hours and no Saturday tokens appears in the daily evidence but contributes nothing to weekly output or reported total estimated hours. If the week's token-active dates have reviewed zero delivery, the weekly view reports zero engineer-days despite the assessed delivery. The active-date restriction is appropriate for the specified daily statistics, but silently dropping delivered scope from total hours and weekly output does not satisfy the separate sum(E)/H output metric. This would block in a phase.
- Proposed correction: Calculate delivered-scope totals and weekly output over assessed delivery dates separately from active-date statistics. Explicitly label any total restricted to D, preserve unknown coverage, and add a fixture with delivery on a non-token date.
### Minor · Aggregate-only reviewer evidence displays zero overlap instead of unavailable timing

- Seats: 2 (cascading-impact)
- Location: `evidence.py`
- Evidence: Completed-turn aggregates create entries in agents with no spans and span_basis='aggregate; timing unavailable'. The overlap projections nevertheless use 'if agents', so aggregate-only dates produce task_span_peak=0 and positive_task_span_peak=0. engineeringDay renders those values as observed peaks, and JSON/CSV preserve them. This turns explicitly unavailable timing into a numeric observation; responding_density correctly remains null.
- Proposed correction: Gate overlap metrics on applicable interval evidence rather than the existence of an identity. Return null for aggregate-only timing and verify the resulting N/A dashboard label and null exports.
- Disposition: absorb (classification only)

No fixes, issue filing, PR comments, extra seats, or follow-up actions were performed.

Repair handoff: apply the packaged #2097 repair discipline only when the user separately authorizes fixes; suggested line edits are not the whole defect class.

