# Snipe report

## Scope

- Committed scope: range 9470e9d45a3e7473f646e8a99ba41828a1a730c3..46d4dadf71f59b50f402a0a154c49ccbf88b1498
- Revision: `46d4dadf71f59b50f402a0a154c49ccbf88b1498` (base `9470e9d45a3e7473f646e8a99ba41828a1a730c3`)
- Review coverage: complete
- Configured seat profile: `gpt-6-astra` / `medium` (actual model identity not independently verified)

## Seat outcomes

- Seat 1 · correctness: completed — validated; verdict approve; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_http.py, test_engineering_dashboard.cjs.
- Seat 2 · cascading-impact: completed — validated; verdict approve; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_dashboard.cjs, test_engineering_http.py.
- Seat 3 · test-fidelity: completed — validated; verdict approve; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_http.py, test_engineering_dashboard.cjs, test_app.py, test_snipe_usage.py, test_dashboard.cjs.
- Seat 4 · security: completed — validated; verdict approve; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_http.py, test_engineering_dashboard.cjs.

## Findings

### Minor · DST fixture does not discriminate incorrect daily clipping

- Seats: 3 (test-fidelity)
- Location: `test_engineering.py`
- Evidence: The fixture asserts identity counts and overlap peaks on the spring-transition date, but its only overlapping child span occurs well inside that date. Replacing evidence.activity's next-local-midnight clipping boundary with start plus 24 UTC hours would preserve these assertions: the root already ends at the correct midnight and no later spans compete for the peak. Thus the fixture cannot detect next-day activity leaking into a 23-hour day's overlap metric. The inspected production boundary uses local midnight correctly; this is a regression-evidence gap, not an observed runtime defect. Inspection was static; no tests or mutations were executed.
- Proposed correction: Extend the fixture with three overlapping identities active only between 2026-03-09T07:10:00Z and 07:20:00Z. Assert through the report that March 8 retains peak 2 and March 9 has peak 3. This distinguishes the correct local boundary from a fixed 24-hour UTC boundary.
- Disposition: absorb (classification only)
### Minor · Legacy normalization can turn an unknown counter into verified zero

- Seats: 1 (correctness)
- Location: `app.py:163`
- Evidence: The legacy branch passes normalized delta values to record_provenance, so known_counters examines synthesized integers rather than original counter availability. For a first cumulative record containing input_tokens=100, output_tokens=5 and cached_input_tokens=null, number() converts null to zero and delta contains cached_input_tokens=0. accounting consequently reports all 105 tokens as raw_verified with zero unknown-counter records. The detailed-response path correctly preserves this distinction. This is a narrower remaining instance of the earlier unknown-counter invariant: retained totals are unchanged, but reconciliation coverage and its dashboard/CSV/JSON projections overstate evidence for nullable legacy records. The inspected missing-counter tests exercise detailed responses, not this legacy path. This conclusion follows from pinned source inspection; no tests were executed.
- Proposed correction: Preserve counter-validity metadata from the original cumulative observations when deriving legacy deltas, including the predecessor where subtraction requires it, while retaining existing ledger normalization. Add a legacy fixture with a null cached counter and an explicit-zero mirror; require only the explicit-zero case to qualify as fully raw verified.
- Disposition: absorb (classification only)

No fixes, issue filing, PR comments, extra seats, or follow-up actions were performed.

Repair handoff: apply the packaged #2097 repair discipline only when the user separately authorizes fixes; suggested line edits are not the whole defect class.

