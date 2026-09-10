# Snipe report

## Scope

- Dirty advisory scope: working tree (advisory)
- Fingerprint before review: `8dc978cc61986b7455a3a8a8b67497f5c516b58f4b0d3ff3b9dd8b12ceae443e`
- Included: unstaged, untracked
- Stability: unchanged
- Review coverage: complete
- Configured seat profile: `gpt-5.6-sol` / `medium` (actual model identity not independently verified)

## Seat outcomes

- Seat 1 · correctness: completed — validated; verdict approve; confidence high
- Seat 2 · cascading-impact: completed — validated; verdict request_changes; confidence high

## Findings

### Major · Privacy-mode project labels identify different projects in the filter and work-group views — would block in a phase

- Seats: 2 (cascading-impact)
- Location: `index.html:234`
- Evidence: The project filter and its downstream work-group mirror assign anonymized labels independently. populateFilters sorts raw project names and labels them Project 1, Project 2, and so on, while renderWork sorts groups by descending token total and assigns the same labels from that different order. For projects A and Z where Z has more usage, the work view calls Z “Project 1” but the filter's “Project 1” selects A. Applying that filter silently loads the wrong project relative to the identity presented elsewhere in the dashboard. Filtering can also change renderWork's ordering and numbering, making identities unstable between the unfiltered and filtered views. The dashboard test covers only one project in privacy mode, so it cannot detect this collision.
- Proposed correction: Create one stable privacy-safe project-label mapping from raw or aliased project identity and use it in both filter options and work-group rendering. Add a regression with at least two projects whose alphabetical and token-total orders differ, asserting that selecting each anonymized filter label returns the correspondingly labeled work group.
### Minor · Sub-cent priced usage is displayed as zero cost

- Seats: 1 (correctness)
- Location: `index.html:305`
- Evidence: In renderCosts, Intl.NumberFormat uses the default USD precision of two decimal places for both aggregate and per-model estimates. Any positive estimate below half a cent is therefore shown as "$0.00", making known, priced usage appear free even though costs.py calculated a nonzero value. The cost chart retains more precision in its accessible labels, but the headline and model breakdown—the primary visible outputs—do not. The inspected dashboard test covers only an exact $1.00 value, so it cannot reject this rounding defect.
- Proposed correction: Use adaptive currency precision for nonzero values below $0.01, such as four to six fractional digits, while retaining ordinary two-decimal formatting for larger amounts; add a dashboard assertion for a positive sub-cent estimate.
- Disposition: absorb (classification only)

No fixes, issue filing, PR comments, extra seats, or follow-up actions were performed.

Repair handoff: apply the packaged #2097 repair discipline only when the user separately authorizes fixes; suggested line edits are not the whole defect class.
