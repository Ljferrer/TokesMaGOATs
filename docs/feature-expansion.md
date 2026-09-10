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

Cycles used: 0. Coordinator profile discovery was rejected before any audit seat started. Awaiting host permission and explicit auditor profile; no audit coverage claimed.

### Phase 1 implementation evidence (audit pending)

- Added persisted browser-local privacy toggle; project labels become numbered aliases and task labels are hidden. Editor is hidden in privacy mode and excluded from PNG snapshots.
- Added project renames/merges and per-session work-type overrides, with individual reset controls. Imported metadata remains unchanged.
- Extended dashboard checks for rename grouping, corrected activity totals, and privacy rendering/restoration. Existing 15 Python tests and dashboard tests pass.
- Browser check: privacy toggle changes aria-pressed to true and completes without a page error.
- Remaining phase gate: two-seat Snipe audit and class-closure repairs. Host approval and explicit auditor profile remain unanswered. No panel has run.

### Phase 1 audit boundary

Cycle 1/9: two Sol/medium seats (correctness, cascading-impact) approved. Complete coverage, stable dirty advisory scope; no validated findings. Full runner report: [phase1-snipe.md](phase1-snipe.md). Host access and profile selection are now authorized. The requested header button ordering correction is applied after this audit.
