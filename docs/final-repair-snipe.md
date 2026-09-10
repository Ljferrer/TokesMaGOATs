# Snipe report

## Scope

- Dirty advisory scope: working tree (advisory)
- Fingerprint before review: `dd1dd21513f9049bf08f0646b7741c6cdc7a311895702eb1199f1d228e811090`
- Included: unstaged, untracked
- Stability: unchanged
- Review coverage: complete
- Configured seat profile: `gpt-5.6-sol` / `medium` (actual model identity not independently verified)

## Seat outcomes

- Seat 1 · correctness: completed — validated; verdict request_changes; confidence high
- Seat 2 · cascading-impact: completed — validated; verdict approve; confidence high

## Findings

### Major · Malformed cost-rate container crashes every usage response — would block in a phase

- Seats: 1 (correctness)
- Location: `costs.py:17`
- Evidence: The documented `cost_rates` setting is passed directly to `estimate`, which calls `(overrides or {}).items()` before validating its shape. A valid JSON configuration such as a nonempty array or string therefore raises AttributeError rather than the intended ValueError. `Handler.do_GET` catches only ValueError and OverflowError, so the request terminates without a structured response and the dashboard cannot load any usage. The cost tests cover malformed per-model arrays but not a malformed top-level `cost_rates` value, despite the integration scope explicitly calling for malformed-settings verification.
- Proposed correction: Validate that `cost_rates` is an object/mapping before iterating it and raise the same actionable ValueError used for invalid rate vectors. Add coverage for nonempty list, string, and other non-mapping JSON values, including the API error path.
### Major · Reset leaves the year control inconsistent with the applied current-year range — would block in a phase

- Seats: 1 (correctness)
- Location: `index.html:392`
- Evidence: The Reset handler sets the period to `year` and calls `load(null)`, whose server defaults correctly return the current-year range. However, `load` preserves the year selector's previous value whenever that year still exists. After viewing a historical year and pressing Reset, the dashboard therefore displays current-year data and dates while the selected-year control still shows the historical year. This contradicts README.md's declared behavior that Reset returns to the current year and leaves a normal filter workflow with mutually inconsistent controls and data. The dashboard test harness stops before control bindings and does not exercise Reset.
- Proposed correction: Make Reset explicitly select the current year as part of the same state transition, or make `load(null)` avoid restoring a historical year. Add a regression starting from a historical selection and asserting that Reset aligns the year control, date fields, active range, and rendered data.
### Minor · A scan started during a usage read can still leave another tab stale

- Seats: 2 (cascading-impact)
- Location: `app.py:272`
- Evidence: usage_view captures ImportState only before reading the selected and comparison summaries. If another tab starts and completes a scan after that snapshot, the response retains syncing=false even though either summary may predate the import or the two summaries may observe different database versions. load therefore starts no watcher, so this consumer can display stale or internally mismatched data until its next automatic or manual refresh. The existing completion-during-summary test covers a scan that was already running at the initial snapshot, but not this alternate multi-tab ordering.
- Proposed correction: Track an import generation such as last_sync across the summary reads, or compare snapshots before and after them, and force the response's syncing signal when a scan ran or began during the read so the client performs a post-completion load. Add a regression where the initial snapshot is idle and sync starts during summary construction.
- Disposition: absorb (classification only)

No fixes, issue filing, PR comments, extra seats, or follow-up actions were performed.

Repair handoff: apply the packaged #2097 repair discipline only when the user separately authorizes fixes; suggested line edits are not the whole defect class.
