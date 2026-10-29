# Issue #1 audit and repair evidence

Requested panel: four auto lenses, gpt-6-astra / medium, at most five rounds. Target is the complete change from `9470e9d`; PR base is `main`, as confirmed by the user. Audit results are kept verbatim in the adjacent round reports. Auditors inspect pinned source and do not execute tests. Validation below is coordinator-run.

## Round 1 — cause and consumer sweep before repair

All four seats completed; scope stable and coverage complete. Verified findings group into these invariants:

- **Accounting and observation dates are different selections.** Earliest accounting date must not remove later response observations or the rolling-window lookback. Sweep: selected events/provenance → activity identities and spans → engineering day union → daily/weekly UI and JSON/CSV. Also preserve aggregate timing as unavailable, and accurate terminal-marker status. Baseline reproduction: January 2 alone yields null density for a response observed after midnight, where unrestricted selection yields 1.
- **Supersession identity outlives replaceable raw observations.** Legacy cleanup cannot depend on the last reconciliation's provenance table. Sweep: upgrade from the base ledger, normal sync, explicit reconcile, copied sources, truncated histories, new detailed records and aggregates. Retain durable legacy/source associations and recover identifiable baseline legacy IDs from raw cumulative records. Do not delete unrelated retained usage.
- **Verified counters must actually be known.** Sweep both providers, each normalized counter, explicit provider-defined zero, source maxima, missing fields and report labels. Full verification must not report unknown cached input as reproduced zero.
- **Delivery totals and active-date ratios have different populations.** Sweep daily statistics, period totals, weekly engineer-days, weekly average, non-token days, unknown dates, sensitivity, share exports and labels. Keep D for the requested daily ratios; report all assessed delivery hours separately.
- **Private evidence shares one trust boundary.** Sweep GET and POST dispatch, both allowed loopback Hosts, foreign Host/Origin, JSON import/export shape and loaded editor privacy. Browser reproduction: enabling privacy leaves the loaded evidence editor visible. PNG exclusion already works; the editor itself must hide.
- **Coverage cannot silently omit a selected project.** Sweep the positive-token day population, canonical project mappings, unknown dates, project aliases and filter disclosure. Baseline reproduction: adding positive-token usage from an unmapped project still reports complete.

A real isolated browser run reproduced the acceptance example, 4-hour sensitivity, weekly labels, JSON download and PNG output. HTTP checks exercised import rejection and stored export equality. Existing baseline validation: 55 Python tests plus both Node suites passed. These passing tests did not cover the defects above; discriminating regression and mutation evidence follows below.

### Round 1 closure evidence

Before repair, the new Python regressions failed for activity-only projection, aggregate-only overlap, base-ledger/reconcile supersession (210 instead of 105 tokens), missing cached counters (15 incorrectly verified tokens), non-token delivery totals (32 instead of 40 hours), and unmapped project coverage. The dashboard assertion failed because the private editor was not hidden. A live request to the pinned fixture server with a foreign Host returned 200. The repaired HTTP suite rejects it with 403 and accepts both supported local Hosts.

The sweep found two consequences and closed them before another panel: a model/role-filtered rolling window lost another identity's previous-day observation (1 instead of 2), and the export handler sent success before committing SQLite. The former has a second public-path regression; the latter uses a deliberately delayed transaction exit and immediately reads the frozen row after the response. Export and assessment mutation responses now share the after-commit send path.

Disposable mutation checks removed or inverted these repairs independently: activity date scope, activity-only date union, rolling lookback, known cache requirement, baseline legacy recovery, durable legacy associations, unmapped-project guard, non-token output total, aggregate overlap null, positive aggregate overlap null, GET Host guard, editor privacy, and commit-before-success. Each was killed by its corresponding regression assertion; no production source was mutated. Evidence was generated at `/tmp/tokes-issue1-mutations.json` during this run.

Consumers remain consistent: active-day ratios use D; total known hours and weekly output include non-token delivery; incomplete delivery coverage leaves the weekly daily average null. Model/role activity selection preserves matching observation lookback. Zero/synthetic and aggregate-only dates remain inspectable without entering D or inventing timing. Public exports omit identities, paths, revisions and private prose; private local assessment export remains explicit.

The completeness sweep also added explicit manual PR/deployment references and numeric weekly usage/activity/quality summaries, so a first-parent merge is never silently labeled a PR or deployment. These annotations cannot add effort credit. Fixture coverage checks PR classification, deployment chronology and unchanged effort.

Residual limitation: a pre-feature legacy event whose original cumulative snapshots and all source associations have already disappeared cannot be reliably matched to a later detailed response. Cleanup only removes identifiable legacy contributions; it does not guess or delete unrelated retained usage. This is the same missing-evidence boundary exposed by provenance coverage.

Validation after repair: 69 Python tests and both Node suites pass. Audit seats still do not execute tests. Round 2 reviews the complete accumulated diff, including the consumers changed by repair.
