# Snipe report

## Scope

- Committed scope: range 6f96999193b544a20945298cfe79573b38694758..64bd53dae03855db625dab9406d45a2cfd710e02
- Revision: `64bd53dae03855db625dab9406d45a2cfd710e02` (base `6f96999193b544a20945298cfe79573b38694758`)
- Review coverage: complete
- Configured seat profile: `gpt-6-astra` / `medium` (actual model identity not independently verified)

## Seat outcomes

- Seat 1 · correctness: completed — validated; verdict request_changes; confidence high
  Seat-reported tests: test_human_inputs.py, test_input_selections.py, test_message_timer.py, test_engineering.py, test_engineering_http.py, test_engineering_dashboard.cjs, test_engineering_table.cjs.
- Seat 2 · cascading-impact: completed — validated; verdict request_changes; confidence high
  Seat-reported tests: test_engineering_dashboard.cjs, test_engineering_table.cjs, test_engineering_http.py, test_human_inputs.py, test_input_selections.py, test_message_timer.py.
- Seat 3 · test-fidelity: completed — validated; verdict request_changes; confidence high
  Seat-reported tests: test_engineering.py, test_engineering_dashboard.cjs, test_engineering_http.py, test_engineering_table.cjs, test_human_inputs.py, test_input_selections.py, test_message_timer.py.
- Seat 4 · security: completed — validated; verdict approve; confidence high
  Seat-reported tests: test_human_inputs.py, test_input_selections.py, test_engineering.py, test_engineering_http.py, test_engineering_dashboard.cjs.

## Findings

### Major · A later duplicate representation can invalidate a saved input choice — would block in a phase

- Seats: 2 (cascading-impact)
- Location: `human_inputs.py:228`
- Evidence: Deduplication chooses the preferred ID anew from the currently available representations, prioritizing retained_message_id over provider_message_id. For example, an ambiguous Codex input initially exposed as Codex:native can be selected, then acquire a duplicate representation with retained_source.id.message_id=canonical and the same payload ID, owner, timestamp and classification. The aliases correctly merge the records, but the exposed ID becomes Codex:canonical. inventory drops the alias set, and selection resolution indexes only the new ID, so the saved Codex:native choice becomes missing and its timer contribution disappears. The original input remains present and unchanged; only its representation improved. The fingerprint also incorporates the exposed ID, so simply forwarding the alias would not preserve validation. Existing tests cover identical IDs and adding a wrapper after a canonical ID already exists, but not this reverse arrival order through persisted selections. This would block in a phase.
- Proposed correction: Preserve a durable logical input identity across alias enrichment, and resolve saved references through retained alias relationships without weakening checks for genuinely changed provenance. Cover selecting the provider-ID representation first, importing its canonical duplicate later, and verifying unchanged selection validity, timer totals and exported selection metadata.
### Major · Applied exports recompute timer results at a different cutoff — would block in a phase

- Seats: 2 (cascading-impact)
- Location: `engineering.js:290`
- Evidence: The export request carries applied controls and the selection version, but does not identify the displayed report or its cutoff. The handler calls engineering.view again, which defaults cutoff to now() and reads current evidence and assessments. A supported input at 09:00 therefore contributes one minute to a report displayed at 09:01 but four minutes to an export requested at 09:04, even without a sync or selection change. Newly synced evidence can also change C. JSON and CSV can consequently disagree with the displayed cards and PNG while appearing to export the applied calculation. The inspected HTTP tests verify settings, selection-version pinning and persistence of the newly generated export, not equality with the displayed report across advancing time or evidence changes. This would block in a phase.
- Proposed correction: Bind exports to the immutable calculation snapshot used for the displayed report, including its cutoff, evidence, assessment and selection versions. Add a consumer-level regression that advances time across an active timer tail and changes retained evidence between display and export, asserting that the exported calculation still matches the displayed snapshot.
### Major · Applied-export tests do not verify preservation of the displayed calculation — would block in a phase

- Seats: 3 (test-fidelity)
- Location: `test_engineering_http.py:132`
- Evidence: The HTTP fixture checks exported IDs and selection version but has no assessed matched cohort and never compares an earlier displayed calculation with its export. The dashboard test likewise mocks the export response and checks request settings. Production engineeringSelection(true) pins choices and controls, while app.py's export handler calls engineering.view() again with a fresh cutoff, latest assessment and current input inventory. Consequently, a timer tail can grow between display and export, or a sync/new assessment can change the denominator, numerator or cohort despite an unchanged selection version. A current-day assessment can also become incomplete as the fresh cutoff advances. These tests remain green when JSON/CSV disagree with the displayed cards and PNG. This violates the frozen-window and applied-export acceptance requirements and would block in a phase.
- Proposed correction: Add a populated public-path fixture that loads an assessed report with supported and selected ambiguous inputs, then advances time or changes retained evidence before exporting. Compare cutoff, assessment version, cohort, numerator, all timer denominators and pooled results with the applied report, including CSV metadata. Bind exports to the displayed report snapshot, or require an explicit refresh before exporting a different calculation.
### Major · Conflicting-copy regression bypasses the production deduplication boundary — would block in a phase

- Seats: 3 (test-fidelity)
- Location: `test_input_selections.py:200`
- Evidence: The test passes two conflicting events directly to selections.resolve(), but production passes human_inputs.inventory()['events'], which has already deduplicated them. In human_inputs.deduplicate(), two non-inherited ambiguous records with the same ID and owner but different explicit original timestamps collapse to the earlier record; timestamp disagreements are not retained as conflicts. If that earlier record was previously selected, its fingerprint remains unchanged and the choice still resolves as valid without warning. Thus the test proves a guard whose distinguishing input cannot reach it through the actual collector, leaving the claimed conflicting-reference protection ineffective. This would block in a phase. The consequence follows from pinned source inspection; no tests were executed.
- Proposed correction: Exercise this regression through saved source records, inventory, selection resolution and the resulting timer. Save an ambiguous input and its choice, then introduce a same-ID/same-owner original with a conflicting explicit original timestamp. Assert an unresolved or changed choice, a visible warning and exclusion from selected time. Preserve conflicts at the deduplication boundary while retaining valid inherited-copy and replay-time deduplication cases.
### Major · Deduplication hides conflicting original timestamps from selection validation — would block in a phase

- Seats: 1 (correctness)
- Location: `human_inputs.py:227`
- Evidence: Conflicting original input evidence must invalidate or flag an existing choice rather than silently retain its timer contribution. deduplicate selects the earliest original timestamp and checks conflicts only in ownership and classification. For example, save an ambiguous Codex input with create_time 09:00, select it, then index another non-inherited representation with the same canonical ID and owner but create_time 10:00. Both timestamps claim to be original, yet inventory collapses them to the unchanged 09:00 event. resolve therefore retains the old fingerprint in valid_ids without any changed/invalid warning, and message_timer continues using 09:00 in daily, pooled and exported calculations. The existing test_conflicting_copies_of_a_stable_id_never_qualify_as_resolved_input passes conflicting events directly to resolve; production calls inventory first, which removes the conflicting evidence. This would block in a phase.
- Proposed correction: Detect conflicting authoritative original timestamps while deduplicating, preserve that conflict through inventory, and prevent the affected selection from resolving as valid until reviewed. Continue distinguishing replay timestamps from original timestamps. Add a regression through source collection, inventory, selection resolution and timer calculation, including both source orders and an already-saved choice.

No fixes, issue filing, PR comments, extra seats, or follow-up actions were performed.

Repair handoff: apply the packaged #2097 repair discipline only when the user separately authorizes fixes; suggested line edits are not the whole defect class.
