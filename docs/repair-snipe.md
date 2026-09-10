# Snipe report

## Scope

- Dirty advisory scope: working tree (advisory)
- Fingerprint before review: `335b1fe1caf3713212edbeade2e930ca12677061ad593e5bc8acacc9a0f76c48`
- Included: unstaged, untracked
- Stability: unchanged
- Review coverage: complete
- Configured seat profile: `gpt-5.6-sol` / `medium` (actual model identity not independently verified)

## Seat outcomes

- Seat 1 · correctness: completed — validated; verdict approve; confidence high
- Seat 2 · cascading-impact: completed — validated; verdict approve; confidence high

## Findings

### Minor · Future-dated records leak into date-filter options

- Seats: 2 (cascading-impact)
- Location: `app.py:215`
- Evidence: summary excludes future events from selected totals through the effective end date and excludes them from largest_day_all_time, but it populates available.years and available.first before applying that boundary. load consumes available.years directly for the year selector, so a clock-skewed future record creates a year option that presetRange turns into a future range which applyFilters then rejects. If all retained records are future-dated, the All history preset likewise produces start greater than today. The previous year projection explicitly excluded dates after today, so this is a producer-consumer regression in the new availability projection.
- Proposed correction: Exclude days after the configured-zone today from available.years and from the available.first boundary consumed by date presets.
- Disposition: absorb (classification only)
### Minor · Range-aware charts retain year-only labels

- Seats: 2 (cascading-impact)
- Location: `index.html:265`
- Evidence: The new selectedRange flow correctly drives custom, monthly, and multi-year data into the dashboard, but several downstream labels still describe that data as a selected year: the carbon heading, daily-ledger summary, weekly subtitle, empty-chart message, and daily-chart fallback. A custom or all-history snapshot therefore contains correct range-filtered values alongside misleading year-specific captions. The dashboard tests inspect rendered values but do not assert these mirrors under a non-year selection.
- Proposed correction: Replace the remaining year-specific captions with selection/range wording, using the applied start and end dates where useful.
- Disposition: absorb (classification only)
### Minor · Superseded project rename leaves UI rendered with rolled-back aliases

- Seats: 1 (correctness)
- Location: `index.html:383`
- Evidence: projectChanged temporarily mutates preferences.projects before awaiting load. If another filter load supersedes that request, load returns false after the newer request has rendered using the temporary alias. The catch branch restores the preference map and select value but does not rerender project groups, filter options, or the filter summary. The displayed alias can therefore disagree with persisted state; selecting that stale alias may match no raw project under the restored map and silently apply no project filter.
- Proposed correction: After restoring preferences in the catch branch, rebuild alias-dependent UI from the restored map and then restore the project selection if it still exists, or serialize project edits against other loads.
- Disposition: absorb (classification only)

No fixes, issue filing, PR comments, extra seats, or follow-up actions were performed.

Repair handoff: apply the packaged #2097 repair discipline only when the user separately authorizes fixes; suggested line edits are not the whole defect class.
