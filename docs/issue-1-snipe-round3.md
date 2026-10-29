# Snipe report

## Scope

- Committed scope: range 9470e9d45a3e7473f646e8a99ba41828a1a730c3..6b6c55efa1d5474a2392aeddd93da1add1d3502f
- Revision: `6b6c55efa1d5474a2392aeddd93da1add1d3502f` (base `9470e9d45a3e7473f646e8a99ba41828a1a730c3`)
- Review coverage: complete
- Configured seat profile: `gpt-6-astra` / `medium` (actual model identity not independently verified)

## Seat outcomes

- Seat 1 · correctness: completed — validated; verdict approve; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_http.py, test_engineering_dashboard.cjs.
- Seat 2 · cascading-impact: completed — validated; verdict approve; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_dashboard.cjs, test_engineering_http.py.
- Seat 3 · test-fidelity: completed — validated; verdict approve; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_dashboard.cjs, test_engineering_http.py, test_app.py, test_snipe_usage.py.
- Seat 4 · security: completed — validated; verdict approve; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_http.py, test_engineering_dashboard.cjs.

## Findings

### Minor · Git attribution fixtures stop before testing forbidden effort credit

- Seats: 3 (test-fidelity)
- Location: `test_engineering.py`
- Evidence: test_git_first_parent_merges_stale_refs_and_duplicate_checkouts verifies collected merge topology, and test_same_timestamp_order_and_repeated_gitlink_adoption verifies repeated_adoption flags. Neither submits an assessment claiming implementation credit for the personally authored merge or repeated gitlink adoption. The other-author assessment test uses a direct commit. Consequently, removing either the merge-allocation rejection or repeated-adoption rejection in engineering.validate_assessment would evade these assertions. Both production guards are present at the pinned revision; this is a regression-evidence gap, not an observed attribution failure. Inspection was static; no tests or mutations were executed.
- Proposed correction: Extend the existing Git fixtures with otherwise valid assessments passed through import_assessment: reject implementation credit allocated to the merge commit and reject implementation credit for the repeated gitlink path. Assert the specific validation reasons so unrelated fixture errors cannot satisfy the tests.
- Disposition: absorb (classification only)
### Minor · Merging an already-conflicted identity drops incoming parent alternatives

- Seats: 1 (correctness)
- Location: `evidence.py`
- Evidence: merge_identity unions the target's parent_candidates and both scalar parent fields, but omits incoming.parent_candidates. collect_activity can produce an incoming identity with parent=null and parent_candidates=[B,C] after conflicting metadata within one history. If activity has already loaded that identity with parent=A from another source, merging the conflicted history leaves parent=A and loses B/C. Reversing source order preserves all three alternatives. identity_uncertain remains true, limiting the consequence, but the retained parent evidence is incomplete and order-dependent. The inspected conflicting-parent regression supplies one parent per source and does not exercise this composition. This finding follows from pinned source inspection; no tests were executed.
- Proposed correction: Include incoming parent_candidates in the union before deriving parent and uncertainty. Extend the existing regression with a history containing conflicting parent metadata merged with another history in both source orders; require parent=null and all alternatives retained.
- Disposition: absorb (classification only)
### Minor · Raw-only reconciliation evidence disappears from CSV and dashboard projections

- Seats: 2 (cascading-impact)
- Location: `engineering.py:514`
- Evidence: evidence.accounting produces raw_only_records, raw_only_tokens and raw_only_scope separately from retained ledger totals. export_report preserves these in JSON, but csv_report excludes the entire top-level usage object from metadata and writes only usage.days into rows. Consequently CSV loses the raw-only counts and their global-scope/lower-bound qualification, as well as parser_version and accounting limitations. engineering.js likewise renders daily/weekly accounting and limitations without displaying the raw-only fields. After reconciliation discovers an unimported response, JSON discloses it while CSV and the dashboard omit it. Retained totals remain correct. The inspected raw-only fixture checks accounting directly, without asserting these consumer projections. This finding follows from pinned source inspection; no tests were run.
- Proposed correction: Preserve non-day usage metadata in the CSV metadata row and display raw-only counts with their existing global-scope and lower-bound qualification in the engineering panel. Extend the raw-only fixture through CSV export and the dashboard projection, ensuring these tokens remain excluded from retained totals.
- Disposition: absorb (classification only)

No fixes, issue filing, PR comments, extra seats, or follow-up actions were performed.

Repair handoff: apply the packaged #2097 repair discipline only when the user separately authorizes fixes; suggested line edits are not the whole defect class.

