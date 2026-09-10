# Snipe report

## Scope

- Dirty advisory scope: working tree (advisory)
- Fingerprint before review: `b2b6e71420637d4e77ea2c3d77474a4f130cb1a82f83a04a28f337970c4c34ba`
- Included: unstaged, untracked
- Stability: unchanged
- Review coverage: complete
- Configured seat profile: `gpt-5.6-sol` / `medium` (actual model identity not independently verified)

## Seat outcomes

- Seat 1 · correctness: completed — validated; verdict approve; confidence high
- Seat 2 · cascading-impact: completed — validated; verdict approve; confidence high

## Findings

### Minor · Future-only records remain exposed through non-date filter options

- Seats: 2 (cascading-impact)
- Location: `app.py:216`
- Evidence: In summary(), providers, models, and projects are added to available before the day<=today boundary is applied; only available.years and available.first exclude future dates. populateFilters() consumes those projections directly, so a clock-skewed future-only provider, model, or project appears selectable even though validated_range() prevents any valid request from including its event. Applying that option consequently produces an inexplicably empty dashboard. The future-record regression test verifies years and first but not these sibling availability projections.
- Proposed correction: Apply the today boundary to every availability dimension consumed by the filter UI, while continuing to expose dimensions from all eligible historical dates; extend the future-record test to reject future-only provider, model, and project options.
- Disposition: absorb (classification only)
### Minor · Project edits falsely report success when browser persistence fails

- Seats: 1 (correctness)
- Location: `index.html:392`
- Evidence: savePreferences() correctly reports when localStorage.setItem throws, explaining that the edit applies only until reload. projectChanged() immediately overwrites that diagnostic with "Saved" for both project renames and resets. A storage-denied or quota error therefore silently leaves the edit nonpersistent despite the feature's browser-local persistence contract. The inspected dashboard tests cover failed reloads but not failed preference storage.
- Proposed correction: Have savePreferences return whether persistence succeeded, and only emit the project-edit success message on success; otherwise preserve its storage-unavailable diagnostic. Add a projectChanged regression where localStorage.setItem throws.
- Disposition: absorb (classification only)
### Minor · Refresh restores day details but drops the selected-day highlight

- Seats: 2 (cascading-impact)
- Location: `index.html:259`
- Evidence: load() now calls renderDay(selectedDay) when the selected date remains in range, preserving the detail panel as documented. Its preceding renderYear() rebuilds the heatmap from scratch, however, and no rebuilt button receives the selected class. The details and selectedDay state therefore identify a day while the heatmap mirror shows no selection, including in snapshots after refresh. The inspected sync test verifies that a reload occurs but does not verify this downstream selection state.
- Proposed correction: When rebuilding the heatmap, mark the button whose key equals selectedDay before restoring its detail panel, and add a refresh regression asserting both the details and heatmap selection remain synchronized.
- Disposition: absorb (classification only)

No fixes, issue filing, PR comments, extra seats, or follow-up actions were performed.

Repair handoff: apply the packaged #2097 repair discipline only when the user separately authorizes fixes; suggested line edits are not the whole defect class.
