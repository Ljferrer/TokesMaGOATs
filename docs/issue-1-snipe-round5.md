# Snipe report

## Scope

- Committed scope: range 9470e9d45a3e7473f646e8a99ba41828a1a730c3..10c421844f821b2983c683b255e10340c72a5702
- Revision: `10c421844f821b2983c683b255e10340c72a5702` (base `9470e9d45a3e7473f646e8a99ba41828a1a730c3`)
- Review coverage: complete
- Configured seat profile: `gpt-6-astra` / `medium` (actual model identity not independently verified)

## Seat outcomes

- Seat 1 · correctness: completed — validated; verdict approve; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_dashboard.cjs, test_engineering_http.py.
- Seat 2 · cascading-impact: completed — validated; verdict approve; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_dashboard.cjs, test_engineering_http.py.
- Seat 3 · test-fidelity: completed — validated; verdict approve; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_http.py, test_engineering_dashboard.cjs, test_app.py, test_snipe_usage.py, test_dashboard.cjs.
- Seat 4 · security: completed — validated; verdict approve; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_http.py, test_engineering_dashboard.cjs.

## Findings

### Minor · Grouped-work first-integration dating lacks a discriminating fixture

- Seats: 3 (test-fidelity)
- Location: `test_engineering.py`
- Evidence: Every assessed work-item fixture contains one integration link. The design and implementation acceptance items are separate items, so they do not exercise grouping across integration dates. Changing engineering.view's minimum integration timestamp to the maximum would therefore preserve these assertions while moving grouped effort to the wrong delivery date, affecting daily estimates and peaks. The pinned implementation correctly selects the minimum; this is a regression-evidence gap, not an observed runtime defect. Inspection was static; no tests or mutations were executed.
- Proposed correction: Add an otherwise valid assessment containing one work item linked to the existing January 1 and January 2 integrations, with explicit allocations for both. Through import_assessment and view, assert that its hours appear once on January 1, January 2 remains assessed with zero incremental hours, both integrations remain visible, and period hours equal the single item estimate.
- Disposition: absorb (classification only)

No fixes, issue filing, PR comments, extra seats, or follow-up actions were performed.

Repair handoff: apply the packaged #2097 repair discipline only when the user separately authorizes fixes; suggested line edits are not the whole defect class.

