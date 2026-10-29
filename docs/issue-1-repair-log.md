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

## Round 2 — cause and consumer sweep before repair

Stable scope, complete coverage. Correctness, cascading-impact and test-fidelity requested changes; security approved with a Minor privacy error-path finding.

- **Supersession is permanent ledger identity, not a one-time source cleanup.** The previous repair retained source associations but still allowed a newly discovered legacy copy to reinsert a proven superseded ID. The initial copied-source sweep was incomplete. Sweep insertion, unchanged-file skipping, either source order, repeated sync, raw-only classification, archive discovery and unrelated legacy preservation. Establish a durable superseded-ID record and consult it at the legacy insertion boundary.
- **Identity relationships follow authoritative evidence, not file order.** A copied child response in a parent log inferred a root before native child metadata arrived. Sweep native versus copied metadata, parent edges, child span labels, both source orders, fallback identities, daily and weekly projections.
- **Displayed and exported selections share a normalizer.** Applied controls produce empty optional filter strings; GET omitted them while POST rejected them. Sweep actual `activeFilters` payload, date defaults, project arrays, both export formats and invalid shapes; normalize once at the API boundary.
- **Private errors and test qualifications survive projection correctly.** Keep detailed errors in the excluded local editor and use a fixed public status. Render test date and applicability in the PNG-safe summary. Populate privacy fixtures with real root/child metadata before asserting identity redaction.
- **Finite inputs must produce finite aggregates.** A self-review probe admitted two finite `1e308` hour estimates whose total is infinity. Validate the combined scenario totals before persistence; the new fixture fails on the pinned implementation. Check statistics, JSON serialization and exports as consumers.

A separate mirror fixture now exercises genuinely disjoint paths in one shared commit and a behavior-changing JSON configuration review; both must remain valid.

### Round 2 closure evidence

Before repair, newly discovered legacy archives restored superseded usage (230 instead of 125 tokens including an unrelated legacy event), copied child observations became roots in one source order, and the real applied filter payload returned HTTP 400 on export. New assertions also exposed private error text in the public snapshot, lost historical-test applicability, and infinite combined estimates. The privacy regression now proves root/child identities exist internally before testing their absence from both public export modes.

Identity aggregation now unions explicit child/parent facts instead of ranking files or treating missing metadata as evidence of a root. Tests cover both source orders, native metadata appearing later within one stream, children without known parents, later parent completion, and three conflicting parents. An intermediate rank-based downgrade guard survived mutation; that redundant approach was removed rather than claimed as verified.

Two additional Git boundary probes failed before repair. A fake signed commit with a configured signature program executed that program during observation; collection now disables signature display explicitly. An authenticated HTTPS origin included its user information in the canonical repository ID; URL parsing now discards user information, normalizes default transport ports, and preserves nondefault ports. Both probes use disposable repositories and synthetic credentials.

Eighteen independent disposable mutations were killed by regression assertions: credential stripping, default-port normalization, custom-port preservation, signature-helper suppression, parent union, incoming and retained child facts, legacy supersession insertion and lookup, superseded raw-only exclusion, cross-source and within-source identity merging, empty filter normalization, finite total validation, both identity export exclusions, public error redaction, and historical test applicability. Results were generated at `/tmp/tokes-issue1-round2-mutations.json`.

Validation: 79 Python tests and both Node suites pass; whitespace checks pass. The third panel reviews the full accumulated implementation.

## Round 3 — cause and consumer sweep before repair

All four seats approved with three Minor findings; scope and coverage were complete. Two are small behavioral gaps in previously repaired classes, so they are being closed before the PR.

- **Identity merging must preserve already-merged evidence.** The scalar-parent sweep missed an incoming history with multiple parent alternatives. Check both source orders, one conflicted history and two conflicted histories, within-source merging, daily detail, weekly counts and public redaction. Preserve the union of both candidate sets as well as scalar parents.
- **Accounting qualifications must survive every report projection.** JSON kept global raw-only counts and caveats; CSV discarded all non-day usage/activity metadata and the dashboard did not show raw-only observations. Sweep daily/weekly UI, empty selections, PNG, CSV metadata, JSON and frozen totals. Keep global raw-only observations visibly separate from selected retained tokens; also preserve parser and activity limitations in CSV.
- **Attribution tests must reach the import boundary.** Extend the existing merge and repeated-gitlink fixtures with otherwise valid forbidden implementation claims, require the specific rejection, and allow explicit integration/review allowances as mirror cases. Production rejection rules are unchanged.

### Round 3 closure evidence

The conflicted-history regression failed for a scalar parent followed by a conflicted history and for both source orders of two conflicted histories. The raw-only CSV regression failed because `usage` metadata was absent; the browser projection assertion failed on an empty raw-only display. Both behavioral repairs are now covered through their public consumers. Empty selections still display the global reconciliation scope, zero observations stay explicit, and raw-only tokens remain excluded from the 15-token retained fixture. CSV preserves non-day activity availability and limitations as well as usage metadata.

Eleven disposable mutations were killed: incoming and retained parent candidate sets; CSV usage metadata, activity metadata, nested-day exclusion and top-level day exclusion; UI raw-only counts, qualification and HTML wiring; merge implementation rejection; repeated-gitlink implementation rejection. The last two prove the strengthened tests reach the existing guards rather than failing for unrelated invalid fixture data. Explicit review-only allowances pass. Results were generated at `/tmp/tokes-issue1-round3-mutations.json`.

Validation: 80 Python tests and both Node suites pass. The browser independently verified Apply filters followed by JSON/CSV/PNG download, acceptance statistics, private-error isolation and editor privacy, with no console errors. No attribution policy or retained token total changed. The fourth panel reviews the full accumulated diff.

## Round 4 — cause and consumer sweep before repair

All four seats approved with two Minor findings; scope and coverage remained complete.

- **Counter validity must follow the values that produced the retained result.** Legacy deltas passed normalized integers to provenance, losing original null/missing status and predecessor uncertainty. The producer sweep also reproduced a sibling defect: a valid smaller streamed counter validated a larger coerced string value, in both providers and both arrival orders. Sweep native responses, Claude normalization, cumulative deltas, completed-turn imports, maxima, equal maxima, lower observations, first cumulative observations, predecessor/current unknowns, source refresh and every reconciliation projection. Completed-turn imports retain their original usage dictionary and already reject invalid explicit counter types; absent fields remain unknown. Preserve ledger normalization and positive-delta behavior, but derive legacy validity from both cumulative observations and maximum validity only from observations at that maximum.
- **DST tests must compete at the actual boundary.** Add next-day overlap after spring midnight and final-hour overlap on the fall transition. The existing local-midnight production calculation is retained. Both fixtures must fail if it is replaced with a fixed 24-hour UTC day.

Before repair, null legacy counters were incorrectly verified (including 105 tokens for the cached-null example), and streamed numeric strings were verified as 25 tokens despite invalid counter types. The new fixtures also cover explicit zeros, missing fields, both providers, both source orders, same-maximum valid/invalid mirrors, and valid higher maxima. A parser-version migration fixture preserves 105 retained tokens while rebuilding falsely verified old metadata.

### Round 4 closure evidence

Legacy provenance now consumes original cumulative counters plus the predecessor, rather than normalized deltas. Initial cumulative observations retain the implicit-zero baseline; known→unknown, unknown→known and fully known transitions are tested. The shared streaming recorder associates validity with the maximum value, retaining valid evidence at equal maxima and ignoring smaller values as proof of a larger maximum. This changes reconciliation classification, not accounting totals. Parser v5 forces source metadata refresh on normal sync; the migration fixture starts with falsely verified v4 metadata and confirms unchanged ledger totals after refresh.

Fourteen disposable mutation checks were killed: original legacy counters, predecessor handoff, current and predecessor validity, implicit-zero baseline, higher-maximum invalidation, equality handling, validity recovery at a higher maximum, rejection of lower-value evidence, both equal-maximum evidence arms, parser upgrade, and fixed-24-hour clipping against both spring and fall fixtures. Results were generated at `/tmp/tokes-issue1-round4-mutations.json`.

Validation: 85 Python tests, both Node suites and whitespace checks pass. Round 5 is the final authorized panel. The remaining work after that panel is reporting its outcome and opening the PR when the requested severity threshold is met.

## Round 5 — final outcome

The final panel reviewed the complete diff through `10c421844f821b2983c683b255e10340c72a5702` against `9470e9d45a3e7473f646e8a99ba41828a1a730c3`. All four seats (correctness, cascading-impact, test-fidelity and security) completed and approved with high confidence. Scope was stable and coverage complete. The configured profile was `gpt-6-astra` / `medium`; the runner does not independently attest actual model identity.

One Minor regression-evidence gap remains: the tests do not discriminate earliest-versus-latest integration dating for a single grouped work item spanning multiple integration dates. The reviewed implementation correctly chooses the earliest integration. This does not require a behavior change, and is disclosed as residual test coverage rather than claimed as verified. The requested only-Minor/Nit threshold was met within five panels. The original completion commit `0449a53` recorded audit documentation only; the separately requested feature below came afterward.

Final coordinator validation: 85 Python tests and both Node suites pass, with 56 targeted successful mutation checks across the repair rounds. Actual browser checks and exported artifacts cover the acceptance example, comparison-hour sensitivity, weekly output labels, applied-filter exports, unknowns/privacy/error projection and separate raw-only evidence. The final browser fixture keeps retained usage at 300 tokens while reporting 35 raw-only tokens with their global scope and lower-bound qualification.

## Follow-up — optional low-effort cutoff

After PR #2 opened, the user requested a toggle and slider to omit days off and minimal-effort days from calculations. The filter defaults off with a 0.10× cutoff, permits 0.00×–0.50×, and removes assessed dates strictly below the selected central-equivalent threshold from both effort and denominator. Unknown dates remain eligible. Daily evidence and usage totals retain all dates; reports record the applied cutoff, comparison hours, exclusion counts and per-day flags. Preferences persist in the browser, and exports use applied settings even while a new slider value is pending.

Behavioral coverage includes the `[0.09,3,0]×` example, all scenarios, comparison-hour changes, full-day and weekly calculations, empty results, zero cutoff, unknowns, strict boundaries, persistence and export consistency. A fixture with 0.7 + 0.1 central hours failed at the exact 0.10× boundary before the comparison was changed to sum the original decimal estimates. The isolated browser verified 1.03× unfiltered versus 3× filtered, retained the 0.09× date at an exact 0.09× cutoff, restored the original average when disabled, persisted the setting after reload and exported JSON/CSV/PNG with unchanged retained usage of 300 tokens. This follow-up is tested separately; it was not included in the five completed Snipe panels, and no sixth panel was run.

Validation: 91 Python tests, both Node suites and `git diff --check` pass.
