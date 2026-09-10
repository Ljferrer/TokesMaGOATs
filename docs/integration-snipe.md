# Snipe report

## Scope

- Dirty advisory scope: working tree (advisory)
- Fingerprint before review: `8c691d7ab2ccb9d3202c7966408e2556c89fef6d839ab3c9cd64df3d5995fbff`
- Included: unstaged, untracked
- Stability: unchanged
- Review coverage: complete
- Configured seat profile: `gpt-5.6-sol` / `medium` (actual model identity not independently verified)

## Seat outcomes

- Seat 1 · correctness: completed — validated; verdict approve; confidence high
- Seat 2 · cascading-impact: completed — validated; verdict approve; confidence high

## Findings

### Minor · Completed imports can leave the dashboard displaying pre-import data

- Seats: 1 (correctness)
- Location: `index.html:329`
- Evidence: The new refresh flow has two races that violate the promise that usage appears when an import finishes. In Handler.do_GET, summary() is calculated before state.snapshot(); if the scan commits between those operations, the response combines an old summary with syncing=false, so load() starts no watcher. Separately, syncUsage() deliberately skips its post-scan load whenever another load is in progress. That in-progress request may have read before the scan committed, leaving the dashboard stale until a later automatic or manual refresh. The ImportState tests verify single-flight and state transitions but do not verify that a completed scan always causes a post-completion summary to be displayed.
- Proposed correction: Guarantee a load started after scan completion. Do not drop the refresh merely because loading is true; queue it or invoke the sequence-protected load after the current request settles. Also make /api/usage expose a state snapshot that cannot report syncing=false alongside a summary read before that scan completed, for example by snapshotting before the summary and retaining the watcher signal.
- Disposition: absorb (classification only)
### Minor · Daily drill-down no longer provides the documented exact token counts

- Seats: 1 (correctness)
- Location: `index.html:140`
- Evidence: renderDay and renderYear changed detailed values and hover/accessible labels from fmt() to short(). Large totals are therefore rounded, such as 1.2M, in the day detail, pie labels, legend amounts, and grid button title/aria-label. README still promises exact daily counts and says hovering abbreviated numbers reveals exact values. The dashboard tests use only small values, for which short() and fmt() are indistinguishable, so this regression survives their assertions.
- Proposed correction: Retain compact formatting for overview displays, but use fmt() for drill-down text, pie labels and token-bearing title/aria-label values. Add a test using a sufficiently large non-round value.
- Disposition: absorb (classification only)
### Minor · One-sided date queries bypass the effective range-order validation

- Seats: 1 (correctness)
- Location: `app.py:318`
- Evidence: Handler.do_GET compares start and end before supplying their defaults. A request containing only a future start date passes because the missing end is compared as 9999-12-31; end is then defaulted to today, producing a returned range with start after end. Likewise, an end date before the current year's default start bypasses the guard. The endpoint consequently returns an empty, internally reversed selected range and computes an incoherent comparison period instead of returning the intended 400 error.
- Proposed correction: Apply both date defaults first, then validate start <= end and end <= today using the normalized dates. Add cases for start-only and end-only requests whose effective range is reversed.
- Disposition: absorb (classification only)
### Minor · Turning privacy off leaves the filter summary and snapshot context anonymized

- Seats: 2 (cascading-impact)
- Location: `index.html`
- Evidence: The privacy click handler always rewrites the project portion of filterSummary as "Selected project" whenever activeFilters.projects is nonempty, even after preferences.privacy becomes false. The project selector itself correctly restores the real alias, so these mirrors diverge. share.js consumes filterSummary for exported-image context, causing exports made after privacy is disabled to remain generically labeled until another load occurs. The inspected dashboard regression verifies project option identity across privacy toggles but does not inspect filterSummary or its snapshot consumer.
- Proposed correction: When rebuilding the summary after a privacy toggle, use the same privacy-aware selected-project derivation as load(): show "Selected project" only while privacy is enabled and otherwise show the applied project's alias/raw label.
- Disposition: absorb (classification only)

No fixes, issue filing, PR comments, extra seats, or follow-up actions were performed.

Repair handoff: apply the packaged #2097 repair discipline only when the user separately authorizes fixes; suggested line edits are not the whole defect class.
