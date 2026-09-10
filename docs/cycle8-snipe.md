# Snipe report

## Scope

- Dirty advisory scope: working tree (advisory)
- Fingerprint before review: `f4839773bbb71e9402c946ca1d9a3f53002eab76af12fbaec9e4395228cb8508`
- Included: unstaged, untracked
- Stability: unchanged
- Review coverage: complete
- Configured seat profile: `gpt-5.6-sol` / `medium` (actual model identity not independently verified)

## Seat outcomes

- Seat 1 · correctness: completed — validated; verdict approve; confidence high
- Seat 2 · cascading-impact: completed — validated; verdict approve; confidence high

## Findings

### Minor · Daily drill-down silently loses exact role/model token counts

- Seats: 1 (correctness)
- Location: `index.html:140`
- Evidence: The changed renderDay and renderYear paths replace fmt() with compact short() formatting for the day summary, pie labels, pie legend amounts, heatmap title/aria-label, and largest-day reference. Values such as 1,234,567 are therefore exposed only as 1.2M, and the exact per-model values cannot be recovered from the daily ledger. This regresses the baseline drill-down behavior; the README change removes the prior exact-count promise instead of preserving it. The inspected dashboard tests exercise only small public-detail values, where fmt() and short() produce identical output, while the new large-number assertion tests short() in isolation and cannot reject the regression.
- Proposed correction: Retain compact formatting for overview displays, but restore fmt() for drill-down text, pie labels and legends, and token-bearing title/aria-label values. Add a public-render regression using a large non-round role/model total.
- Disposition: absorb (classification only)
### Minor · Empty filtered selections reopen the dismissed first-launch panel

- Seats: 2 (cascading-impact)
- Location: `index.html:372`
- Evidence: summary() now makes sessions a count of sessions matching the applied filters, but renderSetup() still consumes data.sessions===0 as evidence that the installation has no imported history. After a user dismisses setup, applying any valid filter with no matches reopens the panel even when the database and source reports contain retained histories. This conflates selection emptiness with source emptiness and is an uncovered downstream consequence of filtering the summary contract.
- Proposed correction: Drive the setup panel's empty-history decision from an unfiltered has-history/session signal (or source/import state), while retaining data.sessions for the selected-usage summary. Add a dismissed-panel regression with a zero-result filter over a nonempty history.
- Disposition: absorb (classification only)
### Minor · The dashboard discards actionable API configuration errors

- Seats: 2 (cascading-impact)
- Location: `index.html:326`
- Evidence: Handler.do_GET returns structured JSON containing the specific ValueError for malformed cost-rate settings, but load() converts every non-OK response into the generic message "Could not load usage" without reading that body. Consequently the repaired server-side diagnostic never reaches its dashboard consumer, and a malformed local cost_rates value leaves the entire UI unavailable without telling the user which setting is invalid. The direct cost tests verify validation but not propagation through this consumer.
- Proposed correction: For non-OK usage responses, parse the JSON error field when available and surface it in the existing status path, falling back to the generic message only when no safe diagnostic is returned. Cover the malformed-rate HTTP response through the load error projection.
- Disposition: absorb (classification only)

No fixes, issue filing, PR comments, extra seats, or follow-up actions were performed.

Repair handoff: apply the packaged #2097 repair discipline only when the user separately authorizes fixes; suggested line edits are not the whole defect class.
