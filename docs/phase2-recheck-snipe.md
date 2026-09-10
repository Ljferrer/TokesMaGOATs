# Snipe report

## Scope

- Dirty advisory scope: working tree (advisory)
- Fingerprint before review: `c186440af1e9b36234813d467514cd13db72277616da829a3dca24c6d1a3d202`
- Included: unstaged, untracked
- Stability: unchanged
- Review coverage: complete
- Configured seat profile: `gpt-5.6-sol` / `medium` (actual model identity not independently verified)

## Seat outcomes

- Seat 1 · correctness: completed — validated; verdict request_changes; confidence high
- Seat 2 · cascading-impact: completed — validated; verdict request_changes; confidence high

## Findings

### Major · Privacy toggling desynchronizes the project-filter control from the applied filter — would block in a phase

- Seats: 2 (cascading-impact)
- Location: `index.html:331`
- Evidence: The privacy click handler rebuilds project options through populateFilters while retaining activeFilters.projects and the already-filtered dataset. The rebuilt options replace aliases with anonymized labels such as "Project 1"; because populateFilters restores selection by the previous displayed value, it falls back to "All" even though the raw project filter remains active. The summary then says "Selected project" while the control says "All", and applying another filter silently drops the hidden project constraint. This is a sibling path of the alias/filter invariant that projectChanged repairs. Its failed-load path has similar residue: projectChanged clears the visible selection before awaiting load, but a rejected load leaves the old applied filter and filtered data in place. The dashboard tests exercise privacy rendering and projectChanged separately, but not either transition with an applied project filter.
- Proposed correction: Make privacy changes and project-alias changes use one filter-state transition that keeps the control, activeFilters.projects, summary, and loaded dataset synchronized. Either map the active raw projects to the rebuilt anonymized option or explicitly clear and reload the project dimension; do not clear the visible selection until a reload succeeds, or restore it on failure.
### Major · Privacy toggling silently disconnects the visible project filter from the applied filter — would block in a phase

- Seats: 1 (correctness)
- Location: `index.html:286`
- Evidence: When a project filter is active, populateFilters stores the dropdown's current display-name value, rebuilds project option values as anonymized "Project N" names when privacy is enabled, and restores the selection only if the old value still exists. It therefore leaves the select on All while activeFilters.projects and the loaded totals remain project-restricted. The privacy handler does not reload or reconcile that state; its summary says only "Selected project." Pressing Apply from this apparently-All state then removes the project restriction. The reverse transition has the same problem because an anonymized value does not exist after privacy is disabled. This is an alternate path through the same filter-state invariant repaired for alias edits, and would block in a phase.
- Proposed correction: Derive the displayed project selection from activeFilters.projects after rebuilding options, mapping the applied raw-project set to its current public or privacy-safe alias. If no exact option represents that set, explicitly clear the applied project filter and reload through the same transition used for alias changes. Add a regression covering privacy on and off while a project filter is active.
### Minor · A failed alias-change reload leaves persisted aliases and filter controls out of sync with the displayed data

- Seats: 1 (correctness)
- Location: `index.html:334`
- Evidence: projectChanged persists the alias and clears filterProject before awaiting load(next). If the request fails, load does not replace data or activeFilters, so the dashboard still contains the old project-filtered result while the control shows All and the alias mutation remains saved. The catch handler only changes the general status text, leaving this inconsistent state in place. A later Apply silently broadens the data. The current projectChanged test stubs a successful load and does not exercise rejection.
- Proposed correction: Make the UI transition conditional on a successful reload, or restore/repopulate the project control from the still-applied activeFilters state on rejection. Preserve a clear retry path and add a rejection-path assertion that the visible filter continues to represent the loaded data.
- Disposition: absorb (classification only)
### Minor · Snapshot filenames still mirror the year selector instead of the selected range

- Seats: 2 (cascading-impact)
- Location: `share.js:65`
- Evidence: Snapshot context now correctly consumes filterSummary, but the filename continues to append document.getElementById('year').value. Custom and all-history filters can span multiple years while load preserves an unrelated year-selector value, so the exported image content and context describe one range while its filename advertises another. No snapshot test covers the new range-aware behavior.
- Proposed correction: Derive the filename suffix from the applied start and end dates, using the year only when the applied range actually represents that year.
- Disposition: absorb (classification only)

No fixes, issue filing, PR comments, extra seats, or follow-up actions were performed.

Repair handoff: apply the packaged #2097 repair discipline only when the user separately authorizes fixes; suggested line edits are not the whole defect class.
