import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import input_selections as selections


CLASSIFIER = 'human-inputs-v1'


def event(id='Codex:ambiguous-a', **changes):
    value = dict(id=id, provider='Codex', session='private-session',
                 timestamp='2026-01-01T09:03:00Z', timestamp_basis='input_create_time',
                 classification='ambiguous', reason='User-shaped input lacks verified origin',
                 project='private-project')
    value.update(changes)
    return value


class InputSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'selections.sqlite3'
        self.db = sqlite3.connect(self.path)
        selections.init(self.db)
        self.a = event()
        self.b = event('Codex:ambiguous-b', timestamp='2026-01-01T09:20:00Z')
        self.known = [self.a, self.b]

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def save(self, entries, known=None, classifier=CLASSIFIER):
        return selections.save(self.db, dict(base_version=selections.get(self.db)['version'], entries=entries),
                               self.known if known is None else known, classifier)

    def resolve(self, known=None, classifier=CLASSIFIER):
        return selections.resolve(self.db, self.known if known is None else known, classifier)

    def test_default_selection_is_empty_and_has_no_human_time_claim(self):
        document = selections.get(self.db)
        self.assertEqual(document['schema_version'], 1)
        self.assertEqual(document['version'], 0)
        self.assertEqual(document['entries'], [])
        resolved = self.resolve()
        self.assertEqual(resolved['ids'], [])
        self.assertEqual(resolved['valid_ids'], [])
        self.assertEqual(resolved['selected_count'], 0)
        self.assertEqual(resolved['valid_count'], 0)
        self.assertEqual(resolved['classification'], 'ambiguous')

    def test_selection_persists_after_reopen_without_mutating_classification(self):
        before = copy.deepcopy(self.known)
        saved = self.save([dict(id=self.a['id'], rationale='I submitted this legacy input')])
        self.assertEqual(saved['version'], 1)
        self.assertEqual(saved['entries'][0]['reference']['classifier_version'], CLASSIFIER)
        self.assertRegex(saved['entries'][0]['reference']['fingerprint'], r'^[0-9a-f]{64}$')
        self.db.commit()
        self.db.close()
        self.db = sqlite3.connect(self.path)
        selections.init(self.db)
        self.assertEqual(selections.get(self.db), saved)
        self.assertEqual(self.resolve()['valid_ids'], [self.a['id']])
        self.assertEqual(self.known, before)
        self.assertEqual(self.a['classification'], 'ambiguous')

    def test_identical_duplicates_and_source_order_do_not_add_selections(self):
        saved = self.save([dict(id=self.a['id']), dict(id=self.b['id']), dict(id=self.a['id'])],
                          known=[self.b, self.a, dict(self.a)])
        self.assertEqual(len(saved['entries']), 2)
        resolved = self.resolve(known=[self.a, self.b, dict(self.a)])
        self.assertEqual(set(resolved['valid_ids']), {self.a['id'], self.b['id']})
        self.assertEqual(resolved['valid_count'], 2)
        unchanged = self.save(list(reversed(saved['entries'])))
        self.assertEqual(unchanged, saved)

    def test_stale_writes_cannot_overwrite_another_selection(self):
        saved = self.save([dict(id=self.a['id'])])
        with self.assertRaises(selections.SelectionConflict):
            selections.save(self.db, dict(base_version=0, entries=[dict(id=self.b['id'])]), self.known, CLASSIFIER)
        self.assertEqual(selections.get(self.db), saved)

    def test_reset_and_deselection_append_history_without_deleting_old_decisions(self):
        first = self.save([dict(id=self.a['id'], rationale='original decision'), dict(id=self.b['id'])])
        second = self.save([entry for entry in first['entries'] if entry['id'] == self.a['id']])
        self.assertEqual(second['version'], 2)
        self.assertEqual(self.resolve()['valid_ids'], [self.a['id']])
        cleared = self.save([])
        self.assertEqual(cleared['version'], 3)
        self.assertEqual(self.resolve()['ids'], [])
        self.assertEqual(self.save([]), cleared)
        dump = '\n'.join(self.db.iterdump())
        self.assertIn(self.b['id'], dump)
        self.assertIn('original decision', dump)

    def test_private_rationale_and_source_fields_do_not_enter_public_metadata(self):
        known = [event(content='PRIVATE RAW PROMPT', source='/private/log.jsonl', source_hash='private-file-hash')]
        saved = self.save([dict(id=self.a['id'], rationale='PRIVATE DECISION RATIONALE')], known=known)
        public = json.dumps(self.resolve(known=known))
        stored = json.dumps(saved)
        for value in ['PRIVATE RAW PROMPT', '/private/log.jsonl', 'private-file-hash', 'private-session', 'private-project']:
            self.assertNotIn(value, stored)
            self.assertNotIn(value, public)
        self.assertNotIn('PRIVATE DECISION RATIONALE', public)
        self.assertEqual(saved['entries'][0]['rationale'], 'PRIVATE DECISION RATIONALE')
        saved['entries'].clear()
        self.assertEqual(len(selections.get(self.db)['entries']), 1)

    def test_fresh_unknown_supported_and_excluded_ids_reject_without_partial_write(self):
        known = self.known + [event('Codex:supported', classification='supported_human'),
                             event('Codex:machine', classification='excluded')]
        for invalid in ['Codex:missing', 'Codex:supported', 'Codex:machine']:
            with self.subTest(id=invalid), self.assertRaises(ValueError):
                self.save([dict(id=self.a['id']), dict(id=invalid)], known=known)
            self.assertEqual(selections.get(self.db)['version'], 0)
            self.assertEqual(selections.get(self.db)['entries'], [])

    def test_import_export_reproduces_the_reference_and_result(self):
        original = self.save([dict(id=self.a['id'], rationale='Reviewed individually'), dict(id=self.b['id'])])
        imported = json.loads(json.dumps(original))
        other = sqlite3.connect(':memory:')
        try:
            selections.init(other)
            saved = selections.save(other, dict(schema_version=1, base_version=0, entries=imported['entries']),
                                    self.known, CLASSIFIER)
            self.assertEqual(saved['entries'], original['entries'])
            self.assertEqual(selections.resolve(other, self.known, CLASSIFIER)['valid_ids'], self.resolve()['valid_ids'])
        finally:
            other.close()

    def test_imported_missing_or_non_ambiguous_ids_are_retained_but_never_counted(self):
        reference = self.save([dict(id=self.a['id'])])['entries'][0]['reference']
        self.save([])
        chosen = [dict(id='Codex:missing', reference=reference), dict(id='Codex:machine', reference=reference),
                  dict(id='Codex:supported', reference=reference)]
        known = self.known + [event('Codex:machine', classification='excluded'),
                             event('Codex:supported', classification='supported_human')]
        saved = self.save(chosen, known=known)
        self.assertEqual(len(saved['entries']), 3)
        resolved = self.resolve(known=known)
        self.assertEqual(resolved['valid_ids'], [])
        self.assertEqual(resolved['missing_ids'], ['Codex:missing'])
        self.assertEqual(set(resolved['invalid_ids']), {'Codex:machine', 'Codex:supported'})
        self.assertEqual(resolved['selected_count'], 3)
        self.assertTrue(resolved['warnings'])
        self.assertEqual(len(selections.get(self.db)['entries']), 3)

    def test_changed_origin_fields_or_classifier_require_review(self):
        self.save([dict(id=self.a['id'])])
        cases = [dict(timestamp='2026-01-01T09:04:00Z'), dict(session='different-owner'),
                 dict(provider='Claude Code'), dict(timestamp_basis='source_record_timestamp'),
                 dict(reason='Conflicting original input provenance')]
        for change in cases:
            with self.subTest(change=change):
                resolved = self.resolve(known=[dict(self.a, **change), self.b])
                self.assertEqual(resolved['valid_ids'], [])
                self.assertEqual(resolved['changed_ids'], [self.a['id']])
                self.assertTrue(resolved['warnings'])
        upgraded = self.resolve(classifier='human-inputs-v2')
        self.assertEqual(upgraded['changed_ids'], [self.a['id']])
        self.assertEqual(upgraded['valid_ids'], [])

    def test_timestamp_format_project_names_and_growing_source_hash_do_not_change_identity(self):
        self.save([dict(id=self.a['id'])])
        changed = dict(self.a, timestamp='2026-01-01T01:03:00-08:00', project='renamed project',
                       source_hash='new snapshot hash', content='Later source contains additional body text')
        resolved = self.resolve(known=[changed, self.b])
        self.assertEqual(resolved['valid_ids'], [self.a['id']])
        self.assertEqual(resolved['changed_ids'], [])
        enriched = dict(changed, classifier_version=CLASSIFIER, source_classification='ambiguous',
                        original_timestamp='2026-01-01T09:03:00Z')
        self.assertEqual(self.resolve(known=[enriched, self.b])['valid_ids'], [self.a['id']])

    def test_existing_id_without_reference_does_not_silently_rebind_changed_evidence(self):
        original = self.save([dict(id=self.a['id'])])
        changed = [dict(self.a, timestamp='2026-01-01T10:00:00Z'), self.b]
        revised = self.save([dict(id=self.a['id'], rationale='Added rationale only')], known=changed)
        self.assertEqual(revised['entries'][0]['reference'], original['entries'][0]['reference'])
        self.assertEqual(self.resolve(known=changed)['changed_ids'], [self.a['id']])
        self.save([], known=changed)
        selected_again = self.save([dict(id=self.a['id'])], known=changed)
        self.assertNotEqual(selected_again['entries'][0]['reference'], original['entries'][0]['reference'])
        self.assertEqual(self.resolve(known=changed)['valid_ids'], [self.a['id']])

    def test_missing_or_newly_excluded_existing_choice_is_preserved_and_flagged(self):
        saved = self.save([dict(id=self.a['id'])])
        self.save([dict(id=self.a['id'])], known=[self.b])
        missing = self.resolve(known=[self.b])
        self.assertEqual(missing['missing_ids'], [self.a['id']])
        self.assertEqual(missing['valid_ids'], [])
        self.assertEqual(selections.get(self.db), saved)
        excluded = self.resolve(known=[dict(self.a, classification='excluded'), self.b])
        self.assertEqual(excluded['invalid_ids'], [self.a['id']])
        self.assertEqual(excluded['valid_ids'], [])

    def test_conflicting_copies_of_a_stable_id_never_qualify_as_resolved_input(self):
        self.save([dict(id=self.a['id'])])
        conflicts = [self.a, dict(self.a, timestamp='2026-01-01T10:00:00Z')]
        resolved = self.resolve(known=conflicts)
        self.assertEqual(resolved['valid_ids'], [])
        self.assertEqual(resolved['invalid_ids'], [self.a['id']])
        self.assertTrue(resolved['warnings'])

    def test_conflicting_duplicate_decisions_reject_atomically(self):
        for entries in [[dict(id=self.a['id'], rationale='one'), dict(id=self.a['id'], rationale='two')],
                        [dict(id=self.a['id']), dict(id=self.a['id'], reference=dict(fingerprint='f'*64, classifier_version=CLASSIFIER))]]:
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                self.save(entries)
            self.assertEqual(selections.get(self.db)['version'], 0)

    def test_malformed_imports_do_not_create_partial_versions(self):
        bad_documents = [[], {}, dict(base_version=True, entries=[]), dict(base_version=0, entries='not a list'),
                         dict(base_version=0, entries=[], schema_version=2), dict(base_version=0, entries=[], unknown='field')]
        bad_entries = [None, {}, dict(id=''), dict(id=2), dict(id=self.a['id'], content='RAW BODY'),
                       dict(id=self.a['id'], rationale=[]), dict(id=self.a['id'], reference={}),
                       dict(id=self.a['id'], reference=dict(fingerprint='not a digest', classifier_version=CLASSIFIER)),
                       dict(id=self.a['id'], reference=dict(fingerprint='f'*64, classifier_version=CLASSIFIER, source='/private/log'))]
        bad_documents += [dict(base_version=0, entries=[dict(id=self.b['id']), entry]) for entry in bad_entries]
        for document in bad_documents:
            with self.subTest(document=document), self.assertRaises(ValueError):
                selections.save(self.db, document, self.known, CLASSIFIER)
            self.assertEqual(selections.get(self.db)['version'], 0)
            self.assertEqual(selections.get(self.db)['entries'], [])

    def test_init_and_save_preserve_the_callers_transaction_and_savepoint(self):
        self.db.execute('CREATE TABLE scratch (value TEXT)')
        self.db.execute('INSERT INTO scratch VALUES (?)', ('before savepoint',))
        self.db.execute('SAVEPOINT caller')
        selections.init(self.db)
        self.save([dict(id=self.a['id'])])
        self.db.execute('ROLLBACK TO caller')
        self.db.execute('RELEASE caller')
        self.assertEqual(selections.get(self.db)['version'], 0)
        self.assertEqual(self.db.execute('SELECT value FROM scratch').fetchall(), [('before savepoint',)])
        self.assertTrue(self.db.in_transaction)

    def test_pinned_versions_preserve_previous_choices_after_change_and_reset(self):
        first = self.save([dict(id=self.a['id'])])
        second = self.save([dict(id=self.b['id'])])
        self.save([])
        self.assertEqual(selections.get(self.db, version=first['version']), first)
        self.assertEqual(selections.get(self.db, version=second['version']), second)
        self.assertEqual(selections.resolve(self.db, self.known, CLASSIFIER, version=first['version'])['valid_ids'], [self.a['id']])
        self.assertEqual(selections.resolve(self.db, self.known, CLASSIFIER, version=second['version'])['valid_ids'], [self.b['id']])
        self.assertEqual(selections.get(self.db, version=0)['entries'], [])
        self.assertEqual(selections.resolve(self.db, self.known, CLASSIFIER, version=0)['ids'], [])
        self.assertEqual(self.resolve()['ids'], [])
        for invalid in [-1, True, '1', 999]:
            with self.subTest(version=invalid), self.assertRaises(ValueError):
                selections.get(self.db, version=invalid)
            with self.subTest(version=invalid), self.assertRaises(ValueError):
                selections.resolve(self.db, self.known, CLASSIFIER, version=invalid)

    def test_retained_original_provenance_fields_are_bound_to_the_decision(self):
        original = dict(self.a, classifier_version=CLASSIFIER, source_classification='ambiguous',
                        original_timestamp='2026-01-01T09:03:00Z')
        self.save([dict(id=self.a['id'])], known=[original])
        for change in [dict(classifier_version='human-inputs-v0'), dict(source_classification='excluded'),
                       dict(original_timestamp='2026-01-01T10:03:00Z')]:
            with self.subTest(change=change):
                result = self.resolve(known=[dict(original, **change)])
                self.assertEqual(result['valid_ids'], [])
                self.assertEqual(result['changed_ids'], [self.a['id']])


if __name__ == '__main__':
    unittest.main()
