# Snipe report

## Scope

- Dirty advisory scope: working tree (advisory)
- Fingerprint before review: `86ba856e45f054ac79bd9b95ce4ccbf822ce23cd475c7a9570d71466138c1b51`
- Included: unstaged, untracked
- Stability: unchanged
- Review coverage: complete
- Configured seat profile: `gpt-5.6-sol` / `medium` (actual model identity not independently verified)

## Seat outcomes

- Seat 1 · correctness: completed — validated; verdict request_changes; confidence high
- Seat 2 · cascading-impact: completed — validated; verdict request_changes; confidence high

## Findings

### Major · A null recorded model can make every usage request fail — would block in a phase

- Seats: 1 (correctness)
- Location: `app.py:239`
- Evidence: The existing import paths can store an explicit null model because `dict.get('model', 'unknown')` does not replace a present null, and the SQLite model column is nullable. The new `available` projection adds raw model values to a set and sorts it. Once the ledger contains both a normal string model and null, `sorted(v)` raises TypeError because Python cannot order None and str. The HTTP handler catches only ValueError and OverflowError, so `/api/usage` terminates without a response and the dashboard cannot load. The inspected tests cover unknown string models but not explicit null model metadata.
- Proposed correction: Normalize falsey or non-string recorded model values to `unknown` before using them in filtering, grouping, cost estimation, and the sorted availability projection; add a mixed valid/null-model regression case.
### Major · Editing a project alias desynchronizes the visible filter from the applied server filter — would block in a phase

- Seats: 2 (cascading-impact)
- Location: `index.html:282`
- Evidence: applyFilters converts a displayed alias into raw project names, which is initially consistent. After an alias is saved, populateFilters rebuilds the dropdown but leaves activeFilters.projects and the already-loaded dataset unchanged; the visible selection can become All or represent a newly split alias while totals still contain the old raw-project set. resetProject does not rebuild the filter options at all, so the stale alias can remain selected; applying it then maps to an empty raw-project list and silently removes the project filter. The filter summary and snapshot context can likewise remain stale. This breaks the alias/filter mirror during an ordinary supported editing flow and would block in a phase.
- Proposed correction: Treat alias edits as a filter-state transition: preserve the selected display group intentionally, recompute its raw project membership, reload the server-filtered data, and regenerate the summary and options. Reset must follow the same path. Add a browser-side regression covering save and reset while an aliased project filter is active.
### Major · Historical selections produce today-relative insight cards — would block in a phase

- Seats: 2 (cascading-impact)
- Location: `index.html:188`
- Evidence: The API correctly bounds data to the selected range, but renderInsights always calls insights(data.days, data.today). Consequently, presets such as Last month and custom historical ranges calculate this-week usage and the seven-day average against the real current date, where the filtered dataset necessarily has no entries. The prominent cards therefore report zero despite usage at the end of the selection, contradicting labels such as “Daily average · last 7 days in selection.” This downstream projection defect would block in a phase.
- Proposed correction: Calculate range-relative insights using activeFilters.end (or pass the selected range explicitly), and label the weekly metric as the final week or week containing that endpoint when the range is historical.
### Minor · Editing aliases leaves an applied merged-project filter stale

- Seats: 1 (correctness)
- Location: `index.html:333`
- Evidence: Project filtering converts the selected display alias to its matching raw projects only when Apply is pressed. The project save/reset handlers mutate the alias map and rerender locally without recomputing `activeFilters.projects` or reloading. For example, after filtering project A, renaming project B to A's display alias leaves totals restricted to A even though the dropdown now represents the merged A+B alias. Resetting one member of an applied merged alias has the inverse problem: totals continue including it after it no longer belongs to the displayed alias. This violates the declared behavior that projects sharing a display name are selected together until the user manually reapplies the filter.
- Proposed correction: When an alias changes, recompute the raw-project list represented by the currently selected display alias and reload the active filter, or explicitly clear the project filter and reload if its meaning changed.
- Disposition: absorb (classification only)
### Nit · README simultaneously says the app does and does not estimate dollar cost

- Seats: 1 (correctness)
- Location: `README.md:21`
- Evidence: The new cost section documents API-equivalent dollar estimates, while the earlier Sources and accounts section still states that the app does not estimate dollar costs. These claims are contradictory.
- Proposed correction: Change the earlier sentence to distinguish subscription limits or billed costs from the newly added API-equivalent estimate.
- Disposition: absorb (classification only)

No fixes, issue filing, PR comments, extra seats, or follow-up actions were performed.

Repair handoff: apply the packaged #2097 repair discipline only when the user separately authorizes fixes; suggested line edits are not the whole defect class.
