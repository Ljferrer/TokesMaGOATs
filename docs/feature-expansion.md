# Dashboard feature expansion

Implement all six requested features. Existing accounting totals and four agent roles remain authoritative. All personal settings and data stay local and excluded from Git.

## Phase 1 — Sharing privacy and editable grouping

- Privacy toggle hides project names, task labels, and account labels in the dashboard and exports.
- Persist project renames/alias merges and session work-type corrections in local settings, separate from imported metadata so sync does not overwrite them.
- Provide reset controls; prevent prototype-key and HTML injection in user labels.
- Snipe 2 audit, fix findings, verify repairs before the phase closes.

## Phase 2 — Filters, comparisons, and cost

- Date presets/custom range, provider, model, project, and agent-role filters apply consistently to charts, work groups, and totals.
- Compare selected period against the preceding equal-length period, including zero-usage days.
- API-equivalent USD estimates and cache savings distinguish fresh input, cached reads, cache creation, and output. Cite verified provider rates; unknown models remain visibly unpriced until configured, never silently free.
- Preserve carbon estimation assumptions and distinguish subscriptions from estimated API equivalents.
- Snipe 2 audit, fix findings, verify repairs before the phase closes.

## Phase 3 — First launch, automatic refresh, and integration

- Explain detected clients, missing/empty/unreadable sources, and retained-history limitations on first launch, with usable setup instructions.
- Automatic refresh while open, configurable/persisted, with one in-flight sync, preserved filters and selections, and visible error/retry state.
- Verify complete user workflows, exports, accounting reconciliation, malformed settings, and empty datasets.
- Snipe 2 audit, fix findings, verify repairs and complete requirement-by-requirement evidence.

## Audit budget and evidence

Maximum nine audit/fix cycles across all phases, two independent seats per panel. Start with one cycle per phase; use remaining cycles to verify repairs or resolve findings. No more than nine panels. Track exact pinned scope, seat outcomes, stability, coverage, findings, repair class closure, and verification here.

Current audit count: 9 completed cycles; all permitted panels used and verified findings repaired. All panels use two Sol/medium seats. Initial coordinator permission refusal was resolved by explicit user authorization and did not consume a cycle.

### Phase 1 implementation evidence (audit pending)

- Added persisted browser-local privacy toggle; project labels become numbered aliases and task labels are hidden. Editor is hidden in privacy mode and excluded from PNG snapshots.
- Added project renames/merges and per-session work-type overrides, with individual reset controls. Imported metadata remains unchanged.
- Extended dashboard checks for rename grouping, corrected activity totals, and privacy rendering/restoration. Existing 15 Python tests and dashboard tests pass.
- Browser check: privacy toggle changes aria-pressed to true and completes without a page error.
- Remaining phase gate: two-seat Snipe audit and class-closure repairs. Host approval and explicit auditor profile remain unanswered. No panel has run.

### Phase 1 audit boundary

Cycle 1/9: two Sol/medium seats (correctness, cascading-impact) approved. Complete coverage, stable dirty advisory scope; no validated findings. Full runner report: [phase1-snipe.md](phase1-snipe.md). Host access and profile selection are now authorized. The requested header button ordering correction is applied after this audit.

### Phase 2 cycle 2 repairs

Both seats requested changes; scope stable and coverage complete. Full report: phase2-snipe.md.

- Nullable model metadata → normalized in event creation and historical summary consumption before catalogs, roles, costs, and carbon. Mixed-null/string regression failed with TypeError before repair and passes afterward.
- Alias/filter state divergence → both rename and reset use one transition that clears the applied project filter, reloads while preserving other filters, and explains the reset. Regression asserts raw membership is removed; disposable mutation deleting that guard fails the assertion.
- Historical insights → final week and trailing average use selected end date, with averaging denominator bounded to selected days. Historical fixture failed (0 versus expected 70) before repair and passes afterward.
- README now distinguishes API-equivalent estimates from billed charges.

Consequences: normalized unknowns remain unpriced; alias changes deliberately broaden only the project dimension; daily pie scaling retains the all-time peak. Existing Python/dashboard checks pass. Re-audit pending. Cycles launched: 2/9.

### Cycle 3 closure

Two completed seats requested changes; stable scope, complete coverage. Full report: phase2-recheck-snipe.md.

Privacy option-value finding rejected with code and browser evidence: `o.value=value` remains the project alias; only `o.textContent` is anonymized. Applied WorkAuditRefine remained selected through privacy off and on. Added a DOM-model regression proving both label and value, and no production guard was needed.

Verified findings: failed alias reload now restores prior aliases and the selected control; persistence happens only after success, rename/reset share the same transaction. Regression rejects a simulated failed request and asserts original map/control. Export filenames use the applied range from the same summary as image context. Next integration audit includes these changes. Cycles launched: 3/9.

### Phase 3 implementation and integration evidence

Background imports let the server bind immediately; ImportState admits one scan shared across tabs. First-launch guidance distinguishes detected/empty/missing/unreadable histories and custom-path setup. Auto refresh supports Off/60s/300s with browser persistence and skips hidden pages. Manual sync preserves the applied range, provider, carbon choice, and selected day in range.

22 Python tests pass, including single-flight and failed-scan recovery. Dashboard checks pass including historical range cards, privacy option identity, alias success/failure paths, and cost-chart rendering. Rollback mutation omitting prior alias restoration fails its assertion. Live browser: August/Claude Code selection shows nonzero trailing average; sync retains 2026-08-15 selected day and August range. Filtered PNG export completed with range-aware filename. Integration audit cycle 4 pending.

### Cycle 4 closure

Both seats approved with minor findings; stable scope and complete coverage. Full report: integration-snipe.md.

- Completion refresh race → server captures import state before summary; client waits for any current load then always starts a post-completion read. Tests simulate a scan finishing during a read and a busy loader at completion. Removing the queued refresh fails its regression.
- Effective date validation → defaults and normalization occur before range-order and future-date validation; start-only/end-only reversed ranges are rejected.
- Privacy summary → one shared formatter drives load and toggles; both modes tested. A mutation forcing anonymized summary in privacy-off mode is rejected.
- Compact daily counts retained per explicit user instruction; conflicting README wording replaced. Large-count fixture checks 231.8M.
- Added calendar-month comparison option to complement equal-period comparison; leap/month-boundary behavior covered by date fixtures.
- PNGs retain a visible download link for browsers suppressing automatic downloads.

25 Python tests and dashboard checks pass. Cycle 5 audits the complete integrated scope and these consequences.

### Cycle 5 closure

Both seats approved with minor findings, stable scope and complete coverage. Full report: repair-snipe.md.

- Future-date preset bounds → available years and first date exclude future days; a future-only ledger has no year seeds and no first date.
- Range captions → carbon, weekly, ledger, empty states and daily fallback now describe selections rather than selected years. Year-preset wording remains intentional.
- Alias concurrency → compute edits privately, publish only after a successful non-superseded reload. Failed or superseded loads leave both preferences and UI untouched. Tests assert no transient alias is visible during the request; a mutation publishing aliases before load is rejected.

26 Python tests and dashboard checks pass. Cycle 6 verifies these repairs.

### Cycle 6 closure

Correctness requested changes; cascading-impact approved with a minor finding. Stable scope and complete coverage. Full report: final-repair-snipe.md.

- Malformed rate containers → reject every non-mapping non-null JSON shape before iterating. Vector validation remains separate. Real temporary-server probe confirms HTTP 400 with an actionable JSON error for cost_rates=[1].
- Reset/control mismatch → the year control always derives from the applied end date, including reset, custom ranges and presets. Regression runs the real load/reset flow from historical selection and asserts year, both dates, active range and total. Removing synchronization fails that test.
- Cross-tab scan ordering → generation increments on every accepted import, and usage_view compares before/after state to preserve a watcher signal for any intervening scan. Regression begins idle and completes a scan during reads; removing generation comparison fails it.

28 Python tests and dashboard checks pass. Cycle 7 verifies this repair set.

### Cycle 7 closure

Correctness approved; cascading-impact requested changes. Stable scope and complete coverage. Full report: privacy-cost-snipe.md.

- Shared privacy identity mapping now supplies both project filters and work charts, independent of ranking or selected subset. A two-project regression verifies identical labels across both views and filtering.
- Positive sub-cent costs retain up to six decimal places; still smaller amounts display a positive less-than threshold. Cost and savings displays share this formatter.

28 Python tests and dashboard checks pass. Cycle 8 verifies these repairs.

### Cycle 8 closure

Both seats approved with minor findings; complete coverage and unchanged scope. Full report: cycle8-snipe.md.

- Exact daily drill-down recommendation conflicts with the explicit user request for compact daily counts; keep compact counts, as documented. Exact ledgers remain available.
- Setup consumed filtered session counts as installation state. It now uses the existing unfiltered first-history date from available metadata. A dismissed setup regression over an empty selection failed before repair; truly empty history still opens setup.
- Load discarded structured configuration errors. The shared load path now projects the server error into its existing caller status handlers, using textContent, with a generic fallback for non-JSON responses. The configuration-error regression failed before repair; both diagnostic and fallback pass afterward.
- Cycle 7 repair mutation proofs: reverting chart labels to rank numbering fails Project 1 versus Project 2; restoring two-decimal currency formatting fails $0.00 versus $0.00012. Browser confirms identical Project 18 across filter, full work chart and filtered work chart.

Consequences: selected session totals retain their original meaning; setup uses global source history; startup, apply/reset, alias reload and sync share actionable errors. 28 Python tests and dashboard checks pass. Final permitted cycle 9 follows.

### Final cycle and closure

Cycle 9: both Sol/medium seats approved with minor findings; complete coverage and unchanged scope. Full exact runner report: [final-snipe.md](final-snipe.md). No tenth panel was launched. The following final repairs were verified locally after that panel:

- All filter availability dimensions now share the same today boundary. Future-only provider/model/project options are excluded; real historical options still survive selected filters. The future-only regression failed before repair and passes afterward.
- Preference persistence returns success; project rename/reset no longer overwrite the storage-unavailable warning. Both operations preserve the warning in denied-storage fixtures; the rename fixture failed with the false Saved message before repair. Privacy and activity callers already retain the shared warning.
- Rebuilt heatmap cells retain selectedDay highlighting. The real reset/load regression checks both the selected cell and restored date detail; it failed with an unselected day before repair. Out-of-range days have no matching cell or restored detail.

Consequences: accounting and imported histories remain intact; only eligible filter choices, truthful save status and selection presentation change. No unresolved verified findings remain. Compact daily counts intentionally follow the user's explicit request, overriding the reviewer preference for exact drill-down labels.

## Completion evidence

| Requirement | Evidence |
| --- | --- |
| API-equivalent costs and cache savings | costs.py partitions fresh/cache-read/cache-write/output; test_costs checks numeric oracle, unknown coverage and malformed overrides. UI shows rate sources and exclusions. |
| Filters and comparisons | test_filters reconciles date/provider/model/project/role outputs and month/equal-length comparisons. Live HTTP combined date/provider/role query reconciled days, providers, models, work and cost coverage. Browser Apply/Reset verified. |
| Editable groups | Browser-local aliases/merges and session activity overrides with resets; dashboard tests cover grouping, failed/superseded loads and storage denial. Prior browser rename/reset verification recorded above. |
| Privacy sharing | Shared stable project identities, hidden task labels/editor; browser full and filtered charts match dropdown Project 18. Exports clone visible state and exclude editor/actions. |
| First launch/source detection | Background server startup verified, both client source inventories detected. Import tests cover single-flight/failure/retry. Empty filtered browser view stays dismissed; true empty-history fixture opens setup. README covers custom paths and retained-history limits. |
| Automatic refresh | Off/60/300s persisted setting, hidden-page skip, shared ImportState single-flight; concurrency regression fixtures and live manual sync preservation recorded above. Selection highlight now covered through actual load. |
| Existing dashboard/sharing requirements | Compact daily counts, four roles, daily hover/click pie with all-time linear sizing, collapsible ledger, carbon below weekly, leftmost Save PNG. Dashboard regressions pass; live weekly PNG blob and date-aware download filename verified. Browser download completion itself is not observable in this in-app browser; a persistent download link is provided. |
| Audits | Nine two-seat Sol/medium panels; complete reports preserved. Final panel approved; final minor repairs locally verified, not independently re-audited beyond budget. |

Final checks: 28 Python tests, dashboard checks, share.js syntax and git diff whitespace check pass. Personal database/config remain ignored. Local server restarted with final code. Source commit/push follows this record.
