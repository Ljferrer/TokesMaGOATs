# Engineering evidence and xEngineer

The engineering panel is part of the existing applied date/project selection. Provider, model and role filters change token/activity evidence; delivery estimates keep an explicitly independent scope. Token counts, cache usage, agent duration/counts, diff size and PR counts never determine effort or quality.

An experienced engineer familiar with the repository, using conventional tools without coding agents, is the comparison baseline. Low/central/high hours represent retrospective incremental design, implementation, debugging, verification, integration and review scenarios. They are not observed human time or statistical confidence intervals. The comparison day defaults to 8 hours and offers 4 and 12 hours. Quality never discounts or multiplies effort.

## Local workflow

1. Add explicit repository mappings to private `config.json`:

   ```json
   {
     "engineering_personal_emails": ["your-commit-email@example.com"],
     "engineering_repositories": [
       {"path": "/absolute/path/to/repository", "default_ref": "refs/heads/main", "project": "Existing token project label"}
     ]
   }
   ```

   Keep your existing timezone and sources. `project` maps to the original token project label, not a browser alias. Multiple checkouts of the same origin are one canonical repository; conflicting tips or mappings require choosing one. Canonical remote IDs omit URL credentials and default transport ports; nondefault ports remain distinct. Repositories without an origin use a local common-Git-directory identity. An optional `id` must equal the collector's canonical identity.
2. Click **Observe configured Git refs**, or run `python3 app.py --collect-engineering`. This explicit operation reads local Git only. It does not fetch, query GitHub, run tests, check out files or infer deployments. Normal usage sync does not collect repositories. Snapshots retain the chosen ref, tip, observation time, first-parent integrations, underlying commits, author dates, personal-author matches, paths, gitlink adoption history and branch tips. Source content and author emails are not stored in these snapshots. Histories over 5000 first-parent integrations, shallow histories and failed Git reads are refused, rather than treated as complete.
3. Open **Local assessments and evidence**, then **Load next assessment version**. The snapshot details supply exact IDs/revisions. Edit the JSON in the local editor or import a locally produced JSON file. Save a proposed version while preparing it; change `approval_status` to `approved` only after review. Calculations use the latest approved version. Every new version is immutable; replaying identical JSON is idempotent. Per-item hours and combined scenario totals must remain finite.
4. Click **Validate and save assessment**. CLI equivalents are `--import-assessment /path/review.json` and `--export-assessment /path/private-review.json`. The latter exports an editable next version and includes private evidence. Use a new filename if you need to preserve an earlier export.

There are no automatic reviewers, model/API calls, uploads or transcript exports. The dashboard does not assign hour estimates from file names or keywords. Manual approval is explicit in the structured document; it is not inferred from test presence or auditor prose.

## Assessment contract (schema version 1)

A document has `schema_version`, monotonically increasing `version`, configured `timezone`, offset-bearing `cutoff`, `reviewer`, `method`, `method_version`, `approval_status` (`proposed` or `approved`), and arrays `snapshots`, `work_items`, `excluded_integrations`, `day_reviews`. Optional `integration_evidence` carries explicitly reviewed PR/deployment references. Snapshots must already exist locally and have been observed at or after the assessment cutoff. All references use exact collected revisions; imports cannot nominate arbitrary paths to execute Git against.

Each work item contains:

```json
{
  "id": "feature-phase-1",
  "scope": "Describe the specific delivered behavior or engineering design",
  "kind": "engineering",
  "credit_key": "original-feature-phase-1",
  "incremental_rationale": "What is newly credited, excluding earlier design, copied plans and dependency adoption",
  "related_items": [],
  "integrations": [{"repository": "github.com/owner/repo", "head": "EXACT_INTEGRATION_SHA"}],
  "allocations": [{
    "repository": "github.com/owner/repo", "integration": "EXACT_INTEGRATION_SHA",
    "commit": "EXACT_COVERED_COMMIT_SHA", "paths": ["changed/file.py"],
    "credit": "implementation", "scope": "Specific new behavior in this file",
    "attribution_evidence": []
  }],
  "effort": {
    "status": "assessed", "hours_low": 4, "hours_central": 8, "hours_high": 12,
    "rationale": "Explain the conventional design, implementation and verification work",
    "confidence": "medium", "evidence": ["local-review:reference"],
    "exclusions": ["Previously credited design, generated output and publishing"]
  },
  "quality": []
}
```

Group related commits and repositories before estimating. One item is credited on its first integration date; later incremental design/implementation phases need distinct items/credit keys and `related_items` links. Shared scope has one credit key. Shared commits require explicit disjoint path allocations, enforced across the whole approved document. A cross-repository item appears whole when any mapped repository is selected; estimates are never prorated by commit count.

`kind` also permits `publishing_admin`, `generated`, `revert_reapplication` and `dependency_adoption`; these cannot receive positive engineering hours. Human review must classify scope and explicitly exclude copied plans, release bookkeeping and already-credited work. A filename or diff size cannot establish that classification. Repeated identical gitlink adoption is detected and excluded from implementation credit.

Allocation credit is `implementation`, `design` or `integration_review`. Other-author implementation requires explicit attribution evidence. A merge author's identity cannot credit the merged implementation: allocate underlying commits instead. An integration/review allowance has empty `paths` and requires its own attribution evidence. Commit author matching is evidence, not proof of who did all work.

Effort status is `unreviewed`, `assessed` or `unassessable`; unassessed hours must be null. Assessed hours are finite, nonnegative and ordered. Confidence is `low`, `medium` or `high`; rationale, evidence, method/version and reviewer remain inspectable with every estimate.

`excluded_integrations` contains `{repository, head, reason, evidence}` for integrations that receive no credit. An integration cannot be both excluded and credited. `day_reviews` contains `{date, status, rationale, evidence}`. Every eligible date needs an assessed review; uncovered integrations and unestimated items keep the date unknown. A reviewed date with no retained delivery may be zero, including useful planning/branch work, but requires repository evidence and an explanation.

Dates after the assessed cutoff remain unknown. The current local date is partial; assessments cover it only through their own cutoff. A full-day-only comparison is always shown. Old local snapshots remain explicitly dated, not silently replaced when the branch advances.

## Calculations

For every positive-token local date in the independent delivery date/project scope, sum the incremental conventional hours of items first integrated that day. Divide by 4, 8 or 12 comparison hours. Reviewed zeros stay in the denominator. Only a fully assessed period has minimum, maximum, median and full-period average; otherwise these are null, with assessed/eligible counts and known-item evidence. `assessed_date_mean` is separately labeled and never substituted for the period average.

For `[8,24,0]` central hours, the 8-hour view is `[1,3,0]×`: min 0, max 3, median 1, average 4/3, total 32 hours. Known estimated hours include all assessed items, including delivery on non-token dates and known items on partly assessed dates. Weekly assessed engineer-days divide that total by comparison hours. The separately labeled weekly average daily equivalent also divides by active-date count and remains unknown until delivery coverage is complete. Daily minimum/maximum/median/average still use only D; `active_date_estimated_hours` makes that reconciliation explicit. Activity-only dates remain visible outside D. Unmapped positive-token projects keep their dates unknown.

## Quality and test evidence

Quality reviews are independent objects within an item. Required fields are `status`, `repository`, exact `revision`, `files`, `method`, `method_version`, `reviewer`, `reviewed_at`, `scores`, `confidence`, `strengths`, `reservations`, `unreviewed_scope`, `evidence`, `tests`. File scopes must exist at the reviewed revision. Configuration and Markdown can be reviewed; neither file classification nor prose approval establishes test success.

`scores` has `correctness`, `regression_protection`, `maintainability`, `operational_safeguards`, each null or integer 0–5. The ordinal rubric is: 0 severe gaps, 1 major weaknesses, 2 material reservations, 3 adequate within the sampled scope, 4 strong evidence with limited reservations, 5 exceptionally strong scoped evidence. The composite is `5 * sum(scores)` only for an assessed review with all four dimensions available. It is null otherwise. Confidence and limitations remain separate.

Tests contain `classification` (`present_only`, `contemporaneous_result_inspected`, `later_historical_snapshot_rerun`), `revision`, local `date`, boolean `applies_to_delivered`, `result` (`not_run`, `passed`, `failed`, `unknown`), and `evidence`. Present-only tests must use `not_run`. Later reruns identify the historical revision. The UI compares reviews to the final integration of the delivery date, including later fixes by other authors, and marks historical/partial scope explicitly. A recorded failed intermediate test is not automatically an unresolved final defect.

## Accounting and activity

The ledger still uses normalized input + output, with reasoning inside output. Fresh input = input − cache reads − cache writes. Claude's native fresh input has its separate cache fields added once; Codex normalized input already includes cached input. Repeated response/message IDs use maximum counters, detailed records take precedence over legacy cumulative snapshots, and legacy totals yield positive deltas. Proven superseded legacy IDs remain recorded, so a later archived copy cannot resurrect their tokens. Accounting is assigned once to the earliest observed timestamp; later streaming observations can establish activity on another date.

`response_sources` retains parser version, response ID, source reference/hash/stamp, observation time, counter availability, identity, earliest/latest observation and granularity. Missing counters stay distinguishable from explicit zeros even where the historic ledger uses zero placeholders. Current readable source observations that reproduce retained counters contribute to raw-reconciliation coverage. Mismatches, ledger-only totals and raw-only responses remain separate; zero denominators are N/A. File/source discovery coverage is not reconciliation coverage.

`python3 app.py --reconcile` explicitly reproduces current native history counters without changing retained usage totals. Raw-only counters are global to reconciled sources and excluded from selected ledger totals until a normal sync. Retained events survive deleted files. Share exports are frozen in `engineering_reports`; later imports or raw changes never rewrite them. Coverage is limited to retained evidence across configured local sources.

Activity metadata stores identities and parent links separately from sessions. Codex children use thread IDs; Claude children use session + agent identity, with uncertain missing identities marked. Overlapping spans are unioned per identity, clipped to local-day bounds (including DST), and processed as half-open intervals. Root turns use request/terminal markers where available; child observation spans and missing-terminal roots are estimates. Response density counts distinct identities in `(t-window,t]` for 60/300/600 seconds. Inclusive, positive-accounting and zero/synthetic-only counts remain separate. Neither metric is simultaneous API-call concurrency. Completed-turn Snipe aggregates never manufacture per-response timing or spans; native histories supersede matching retained aggregates.

## Privacy and exports

JSON/CSV share exports contain selections (project count without private labels), assumptions, cutoffs, coverage, partial-day status, privacy mode and numeric evidence. They always omit raw/private free text, source references/hashes, repository revisions/paths and agent identities. PNGs omit local evidence/editor controls and show the visible privacy mode. Changing aliases only changes display labels; it does not merge canonical repositories or allocate effort. Explicit **Save local assessment JSON** retains review details for editing and is labeled private.

Validation: `python3 -m unittest -v`, `node test_dashboard.cjs`, and `node test_engineering_dashboard.cjs`.

An optional integration annotation is `{repository, head, pr, deployments}`. `pr` is null or `{url, evidence}` with an HTTPS PR URL and explicit evidence references. It labels the delivery as a PR integration while retaining Git topology (`merge`/`direct_commit`); no PR is guessed from a subject. `deployments` contains `{id, timestamp, evidence}` objects with unique IDs and offset-bearing timestamps between integration and cutoff. Independently evidenced deployments appear on their observed dates and never create another effort credit. Weekly views aggregate token categories, reconciliation coverage, distinct identities, observed peaks, integrations, deployments and sampled quality; daily drilldowns retain the evidence.

Explicit identity relationships survive copied response observations, regardless of source order; missing metadata does not erase a known child relationship. An explicit child relationship and known parent fill missing metadata; conflicting native parents remain listed as uncertain. Private engineering errors stay inside the excluded local editor; the public status uses a fixed message. Visible test summaries retain their date and applicability to delivered code, including in PNGs.

Raw-only observations are global across reconciled sources, even with a date/project selection. The dashboard and PNG retain that qualification; CSV metadata includes non-day usage and activity coverage, parser version and limitations. These observations do not increase retained ledger totals until normal sync imports them.

Legacy delta verification requires valid counters in the current cumulative observation and its predecessor (the first observation uses an implicit zero baseline). Streaming validity follows observations at the retained maximum; a valid smaller value cannot validate a larger normalized placeholder. Parser-version changes rebuild provenance on the next sync while preserving retained ledger identities and totals.
