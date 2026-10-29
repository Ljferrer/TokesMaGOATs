# Snipe report

## Scope

- Committed scope: range 9470e9d45a3e7473f646e8a99ba41828a1a730c3..c90a2a1ccaef85c0b52d3a2399efeb5ecdfc7efa
- Revision: `c90a2a1ccaef85c0b52d3a2399efeb5ecdfc7efa` (base `9470e9d45a3e7473f646e8a99ba41828a1a730c3`)
- Review coverage: complete
- Configured seat profile: `gpt-6-astra` / `medium` (actual model identity not independently verified)

## Seat outcomes

- Seat 1 · correctness: completed — validated; verdict request_changes; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_dashboard.cjs, test_engineering_http.py.
- Seat 2 · cascading-impact: completed — validated; verdict request_changes; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_dashboard.cjs, test_engineering_http.py.
- Seat 3 · test-fidelity: completed — validated; verdict request_changes; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_dashboard.cjs, test_engineering_http.py, test_app.py, test_snipe_usage.py.
- Seat 4 · security: completed — validated; verdict approve; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_http.py, test_engineering_dashboard.cjs.

## Findings

### Major · Applied dashboard filters break JSON and CSV exports — would block in a phase

- Seats: 2 (cascading-impact)
- Location: `app.py`
- Evidence: index.html applyFilters() always includes provider, model and role, using empty strings for unrestricted selections. load() preserves these in activeFilters. engineering.js sends activeFilters directly to /api/engineering/export, whose validation calls engineering.text() on every scalar filter and rejects empty strings. Consequently, applying an ordinary date/project selection and then exporting JSON or CSV returns HTTP 400 unless every optional scalar filter happens to be populated. The GET usage path explicitly omits empty values in filterQuery(), so the displayed selection works while its export fails. test_engineering_http.py tests export with only start/end, and test_engineering_dashboard.cjs never invokes the export handler; neither covers the actual producer-consumer payload. This would block in a phase.
- Proposed correction: Normalize optional empty filter values consistently across GET usage and POST export, preserving the applied selection. Add a regression using the exact activeFilters shape produced by applyFilters(), including empty provider/model/role values, through the export endpoint.
### Major · Codex child identity metadata depends on source-read order — would block in a phase

- Seats: 1 (correctness)
- Location: `evidence.py:304`
- Evidence: A parent history containing a token_usage_record whose thread_id identifies a child creates that identity with child=false and parent=null, because collect_activity derives child status only from the containing file's session_meta. The child's own history can supply authoritative child status and its parent link, but activity merges sources using setdefault and subsequently merges only points, spans, responses and terminal/request flags. If the parent-history observation arrives first, the authoritative child metadata never replaces the inferred root metadata. The later provenance fallback also uses setdefault. Consequently daily and weekly reports classify the child as a root, omit its known parent, and can label its merged estimated child span as an observed root turn. The inspected Codex child fixture uses separate identities without a copied child response in the parent history; the copied-response fixture covers Claude only. This violates the durable-identity and parent-link requirements and would block in a phase.
- Proposed correction: Merge identity metadata according to evidence authority, allowing explicit native child-session metadata to establish child status and parent links regardless of source order. Preserve accurate span provenance when combining observations. Add a fixture with the same child response in parent and native child histories, checking both import orders and daily/weekly root-child projections.
### Major · Copied legacy histories can resurrect superseded accounting — would block in a phase

- Seats: 1 (correctness)
- Location: `app.py:203`
- Evidence: The round-one repair deletes identifiable legacy events when their source gains detailed records, but deletes their durable associations too and retains no superseded-ID marker. After upgrading a source from a 105-token cumulative event to its equivalent detailed response, importing a newly discovered archived copy containing that same cumulative event inserts it again. The unchanged detailed source is skipped by the file-stamp check, and legacy-only sources never execute the cleanup branch. The ledger therefore returns to 210 tokens and remains inflated on subsequent unchanged syncs. This affects existing usage, costs, carbon and engineering accounting. The inspected supersession regressions cover replacement and reconciliation of one source, not later discovery of a legacy copy. This is a remaining instance of the previously reported precedence invariant and would block in a phase. The conclusion is from pinned source inspection; no tests were executed.
- Proposed correction: Preserve established supersession independently of source observations and reject or remove reimported legacy IDs already proven superseded. Apply the invariant regardless of source order or unchanged-file skipping, without deleting unrelated legacy usage. Cover discovery of an archived legacy copy after successful detailed supersession and repeated syncs.
### Major · Supersession regressions miss reimport from a copied legacy source — would block in a phase

- Seats: 3 (test-fidelity)
- Location: `test_engineering.py`
- Evidence: All three fixtures update one source file. They cannot detect resurrection of superseded accounting from another copy. In pinned app.py, sync inserts legacy rows unconditionally; cleanup runs only while processing a source containing detailed responses, and deletes the corresponding legacy_origins entries. After r.jsonl advances from a 105-token cumulative record to matching detailed evidence, introducing an archive containing the original cumulative record reinserts those 105 tokens. The unchanged detailed source is skipped by its file stamp, so no cleanup removes the duplicate. Both summary and engineering accounting then include 210 tokens. This is a static code-path finding, not an executed reproduction. It leaves the prior supersession invariant broken despite the repair log's claimed copied-source sweep and would block in a phase.
- Proposed correction: Extend the public sync regression with an archived cumulative copy introduced or changed after detailed supersession. Assert that both summary and engineering totals remain 105 across subsequent syncs, while unrelated legacy usage remains retained. Preserve enough durable supersession identity to prevent matching legacy records from being reinserted, independently of source processing order and whether the detailed source changes.
### Minor · Export privacy assertion has no agent identities to redact

- Seats: 3 (test-fidelity)
- Location: `test_engineering.py`
- Evidence: The fixture inserts ledger events directly without response provenance or activity metadata. Consequently, engineering.view produces no activity identities, and asserting that 'session' is absent from JSON/CSV does not exercise identity redaction. The HTTP export fixture also uses an empty ledger. Removing the identities/positive_identity_ids exclusion from export_report would therefore evade these privacy assertions, although populated reports contain durable agent identities. This is a discriminating-test gap; the inspected production projection currently excludes those fields.
- Proposed correction: Populate the export fixture through sync with a recognizable root and child identity, assert that the internal report actually contains those identities, then verify that JSON and CSV omit them in both privacy modes while retaining the expected numeric activity counts.
- Disposition: absorb (classification only)
### Minor · Private engineering errors escape the PNG exclusion boundary

- Seats: 4 (security)
- Location: `engineering.js`
- Evidence: The action wrapper copies error.message into both engineeringStatus and the global status element. engineering.git includes Git stderr in errors; a missing configured checkout therefore exposes its absolute private path. engineeringStatus is inside the snapshot-excluded editor, but index.html places global status inside main without exclusion, and share.js clones it into dashboard PNGs. Enabling privacy hides the editor but does not clear or redact global status. Thus the repaired editor boundary still permits private repository paths in shared PNGs after a collection failure. The inspected dashboard test checks engineeringDays and editor visibility, not this error consumer. This conclusion is from pinned source inspection; no tests were executed.
- Proposed correction: Keep detailed engineering errors in the excluded local status and use a fixed, non-sensitive message in global status. Add an assertion covering a collection error containing a private path, privacy toggling, and the dashboard snapshot projection.
- Disposition: absorb (classification only)
### Minor · Rendered test results lose their applicability and historical scope

- Seats: 2 (cascading-impact)
- Location: `engineering.js`
- Evidence: The assessment validator accepts and preserves test revision, date and applies_to_delivered, including false. engineeringDay projects each test to classification and result only. A final-day source review with a passed historical test explicitly marked applies_to_delivered=false therefore renders 'final-day revision inspected' alongside 'later_historical_snapshot_rerun: passed' without the applicability qualification. This paragraph is outside snapshot-excluded nodes, so PNG exports repeat the omission, while the private JSON drill-down that contains the qualification is removed. The dashboard fixture covers only present_only/not_run and cannot distinguish these cases.
- Proposed correction: Include test date and whether the result applies to delivered code in the visible, PNG-safe quality summary. Keep exact revisions in the private drill-down if needed for privacy, and test a passed historical rerun with applies_to_delivered=false.
- Disposition: absorb (classification only)

No fixes, issue filing, PR comments, extra seats, or follow-up actions were performed.

Repair handoff: apply the packaged #2097 repair discipline only when the user separately authorizes fixes; suggested line edits are not the whole defect class.

