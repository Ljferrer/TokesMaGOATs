import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import human_inputs


SECRET = 'PRIVATE_BODY_SHOULD_NEVER_ENTER_HUMAN_INPUT_METADATA_8af391'
BASE_TIME = '2026-01-01T09:00:00Z'


def instant(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


def codex_meta(session='root', *, child=False):
    source = {'subagent': {'thread_spawn': {'parent_thread_id': 'parent'}}} if child else 'vscode'
    return dict(type='session_meta', timestamp=BASE_TIME,
                payload=dict(id=session, source=source, originator='Codex Desktop'))


def codex_start(turn='turn', *, trigger='composer', agent=None):
    return dict(type='event_msg', timestamp=BASE_TIME,
                payload=dict(type='task_started', turn_attribution=dict(
                    turn_id=turn, turn_trigger=trigger, initiating_agent_path=agent)))


def codex_input(message_id='message', timestamp=BASE_TIME, *, turn='turn', human=True,
                inherited=False, original_time=None, canonical_id=None):
    passthrough = dict(turn_id=turn)
    if human:
        passthrough['content_item_metadata'] = [dict(provenance=dict(type='user'))]
    if original_time is not None:
        passthrough['create_time'] = instant(original_time).timestamp()
    metadata = {}
    if inherited:
        metadata['inherited_user_message'] = True
    if canonical_id is not None:
        metadata['retained_source'] = dict(id=dict(message_id=canonical_id))
    return dict(type='response_item', timestamp=timestamp, metadata=metadata, payload=dict(
        type='message', id=message_id, role='user', content=[dict(type='input_text', text=SECRET)],
        internal_chat_message_metadata_passthrough=passthrough))


def claude_input(message_id='message', timestamp=BASE_TIME, *, session='claude-root', human=True, **fields):
    row = dict(type='user', uuid=message_id, timestamp=timestamp, sessionId=session,
               isSidechain=False, userType='external', entrypoint='cli',
               message=dict(role='user', content=SECRET))
    if human:
        row.update(origin=dict(kind='human'), turnOrigin='human')
    row.update(fields)
    return row


class HumanInputsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = sqlite3.connect(self.root / 'fixture.db')
        self.addCleanup(self.db.close)
        self.db.execute('''CREATE TABLE session_topics (
            provider TEXT, session TEXT, project TEXT, title TEXT, activity TEXT, basis TEXT,
            PRIMARY KEY(provider,session))''')
        human_inputs.init(self.db)
        self.sequence = 0

    def save(self, rows, provider='Codex', name=None):
        self.sequence += 1
        path = self.root / (name or f'source-{self.sequence}.jsonl')
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        stat = path.stat()
        human_inputs.save(self.db, path, provider, iter(rows),
                          source_stamp=f'{stat.st_mtime_ns}:{stat.st_size}')
        return path

    def select(self, *, timezone='UTC', cutoff='2026-02-01T00:00:00Z', sources=None, **filters):
        return human_inputs.select(self.db, {'start': '2026-01-01', 'end': '2026-01-31', **filters},
                                   timezone, cutoff, sources=sources)

    def topic(self, provider, session, project):
        self.db.execute('INSERT OR REPLACE INTO session_topics VALUES (?,?,?,?,?,?)',
                        (provider, session, project, 'Fixture', 'Implementation', 'Fixture mapping'))

    def assert_private(self, result):
        self.assertNotIn(SECRET, '\n'.join(self.db.iterdump()))
        self.assertNotIn(SECRET, json.dumps(result))

    def test_supported_codex_input_uses_original_time_and_compact_metadata(self):
        self.save([codex_meta(), codex_start(), codex_input(
            timestamp='2026-01-03T12:00:00Z', original_time=BASE_TIME)])
        self.topic('Codex', 'root', 'Example')
        report = self.select()
        self.assertEqual(len(report['events']), 1)
        event = report['events'][0]
        self.assertEqual(event['classification'], 'supported_human')
        self.assertEqual(instant(event['timestamp']), instant(BASE_TIME))
        self.assertIn('create_time', event['timestamp_basis'])
        self.assertEqual(event['provider'], 'Codex')
        self.assertEqual(event['session'], 'root')
        self.assertEqual(event['project'], 'Example')
        self.assertTrue(event['in_reporting_window'])
        self.assertTrue(event['reason'])
        self.assertTrue(report['classifier_version'])
        self.assertFalse(report['coverage']['complete'])
        self.assertTrue(report['limitations'])
        self.assert_private(report)

    def test_user_role_and_root_session_alone_are_ambiguous(self):
        self.save([codex_meta(), codex_input(human=False)])
        self.save([claude_input(human=False)], 'Claude Code')
        report = self.select()
        self.assertEqual(len(report['events']), 2)
        self.assertEqual({row['classification'] for row in report['events']}, {'ambiguous'})
        self.assertEqual(report['coverage']['supported_human'], 0)

    def test_invalid_original_time_is_not_replaced_with_replay_time(self):
        for index,value in enumerate((float('nan'), True, 'not-a-timestamp', 10**100)):
            row=codex_input(str(index))
            row['payload']['internal_chat_message_metadata_passthrough']['create_time']=value
            self.save([codex_meta(str(index)),codex_start(),row])
        report=self.select()
        self.assertEqual(report['events'],[])
        self.assertEqual(report['coverage']['invalid_timestamp_records'],4)

    def test_selection_can_reuse_inventory_without_reloading_or_mutating_it(self):
        self.save([claude_input()], 'Claude Code')
        retained=human_inputs.inventory(self.db)
        before=copy.deepcopy(retained)
        with patch.object(human_inputs,'inventory',side_effect=AssertionError('Unnecessary second inventory load')):
            selected=human_inputs.select(self.db,dict(start='2026-01-01',end='2026-01-01'),'UTC','2026-01-02T00:00:00Z',retained=retained)
        self.assertEqual(len(selected['events']),1)
        self.assertEqual(retained,before)

    def test_claude_explicit_human_origin_is_supported(self):
        self.save([claude_input()], 'Claude Code')
        report = self.select()
        self.assertEqual(len(report['events']), 1)
        self.assertEqual(report['events'][0]['classification'], 'supported_human')
        self.assertEqual(report['events'][0]['session'], 'claude-root')
        self.assert_private(report)

    def test_codex_autonomous_and_agent_directed_inputs_are_excluded(self):
        for index, options in enumerate([dict(trigger='goal'), dict(agent='/root/worker')]):
            self.save([codex_meta(f'root-{index}'), codex_start(**options), codex_input(str(index))])
        report = self.select()
        self.assertEqual(len(report['events']), 2)
        self.assertEqual({row['classification'] for row in report['events']}, {'excluded'})

    def test_inherited_input_does_not_seed_a_timer(self):
        self.save([codex_meta(), codex_start(), codex_input(inherited=True)])
        report = self.select()
        self.assertEqual(len(report['events']), 1)
        self.assertEqual(report['events'][0]['classification'], 'excluded')
        self.assertEqual(report['coverage']['supported_human'], 0)

    def test_original_child_metadata_cannot_be_replaced_by_copied_parent_metadata(self):
        self.save([codex_meta('child', child=True), codex_meta('parent'), codex_start(), codex_input()])
        self.topic('Codex', 'parent', 'Parent project')
        self.topic('Codex', 'child', 'Child project')
        report = self.select()
        event = report['events'][0]
        self.assertEqual(event['session'], 'child')
        self.assertEqual(event['project'], 'Child project')
        self.assertEqual(event['classification'], 'excluded')

    def test_codex_submitted_question_answer_uses_ui_provenance(self):
        self.save([codex_meta(), codex_start(trigger='send_user_message_async_question'), codex_input()])
        report = self.select()
        self.assertEqual(len(report['events']), 1)
        self.assertEqual(report['events'][0]['classification'], 'supported_human')

    def test_malformed_codex_content_metadata_remains_ambiguous_without_aborting_save(self):
        for index, malformed in enumerate([None, {'provenance': {'type': 'user'}}, 'user', 1]):
            row = codex_input(f'malformed-content-{index}')
            row['payload']['internal_chat_message_metadata_passthrough']['content_item_metadata'] = malformed
            self.save([codex_meta(f'content-{index}'), codex_start(), row])
        report = self.select()
        self.assertEqual(len(report['events']), 4)
        self.assertEqual({row['classification'] for row in report['events']}, {'ambiguous'})

    def test_malformed_codex_turn_trigger_remains_ambiguous_without_aborting_save(self):
        for index, trigger in enumerate([[], {}, 1, True]):
            self.save([codex_meta(f'trigger-{index}'), codex_start(trigger=trigger),
                       codex_input(f'malformed-trigger-{index}')])
        report = self.select()
        self.assertEqual(len(report['events']), 4)
        self.assertEqual({row['classification'] for row in report['events']}, {'ambiguous'})

    def test_codex_child_user_provenance_requires_a_known_ui_trigger(self):
        self.save([codex_meta('child-without-ui', child=True), codex_input('without-ui')])
        self.save([codex_meta('child-with-ui', child=True), codex_start(), codex_input('with-ui')])
        report = self.select()
        classes = {row['id'].split(':')[-1]: row['classification'] for row in report['events']}
        self.assertEqual(classes['without-ui'], 'excluded')
        self.assertEqual(classes['with-ui'], 'supported_human')

    def test_invalid_first_codex_owner_is_not_replaced_by_later_copied_root_metadata(self):
        first_rows = [dict(type='session_meta', timestamp=BASE_TIME,
                           payload=dict(source='vscode', originator='Codex Desktop')),
                      codex_meta(123), codex_meta({}), codex_meta('')]
        for index, first in enumerate(first_rows):
            self.save([first, codex_meta('copied-parent'), codex_start(), codex_input(f'unknown-owner-{index}')])
        report = self.select()
        self.assertEqual(len(report['events']), len(first_rows))
        self.assertEqual({row['classification'] for row in report['events']}, {'ambiguous'})
        self.assertNotIn('copied-parent', {row['session'] for row in report['events']})

    def test_claude_programmatic_meta_and_sidechain_records_are_excluded(self):
        rows = [claude_input('sdk', human=False, entrypoint='sdk', origin=dict(kind='programmatic'),
                             turnOrigin='programmatic'),
                claude_input('meta', isMeta=True),
                claude_input('child', human=False, isSidechain=True)]
        for row in rows:
            self.save([row], 'Claude Code')
        report = self.select()
        self.assertEqual(len(report['events']), 3)
        self.assertEqual({row['classification'] for row in report['events']}, {'excluded'})

    def test_claude_sdk_session_origin_persists_when_later_input_omits_entrypoint(self):
        first = claude_input('sdk-first', human=False, entrypoint='sdk', origin=dict(kind='programmatic'))
        later = claude_input('sdk-later')
        later.pop('entrypoint')
        self.save([first, later], 'Claude Code')
        report = self.select()
        self.assertEqual(len(report['events']), 2)
        self.assertEqual({row['classification'] for row in report['events']}, {'excluded'})

    def test_claude_sdk_question_result_does_not_become_human_when_entrypoint_is_omitted(self):
        assistant = dict(type='assistant', timestamp=BASE_TIME, sessionId='claude-root', entrypoint='sdk',
                         message=dict(role='assistant', content=[dict(
                             type='tool_use', id='sdk-question', name='AskUserQuestion',
                             input=dict(questions=[SECRET]))]))
        answer = claude_input('sdk-answer', human=False, message=dict(role='user', content=[dict(
            type='tool_result', tool_use_id='sdk-question', content=SECRET)]),
            toolUseResult=dict(questions=[dict(question=SECRET)], answers={SECRET: SECRET}))
        answer.pop('entrypoint')
        self.save([assistant, answer], 'Claude Code')
        report = self.select()
        self.assertEqual(len(report['events']), 1)
        self.assertEqual(report['events'][0]['classification'], 'excluded')

    def test_malformed_claude_tool_ids_do_not_abort_later_valid_input(self):
        rows = []
        for index, malformed in enumerate([{}, []]):
            rows.append(dict(type='assistant', timestamp=BASE_TIME, sessionId='claude-root',
                             message=dict(role='assistant', content=[dict(
                                 type='tool_use', id=malformed, name='AskUserQuestion',
                                 input=dict(questions=[SECRET]))])))
            rows.append(claude_input(f'malformed-tool-{index}', human=False,
                                    message=dict(role='user', content=[dict(
                                        type='tool_result', tool_use_id=malformed, content=SECRET)]),
                                    toolUseResult=dict(answers={SECRET: SECRET})))
        rows.append(claude_input('valid-after-malformed'))
        self.save(rows, 'Claude Code')
        report = self.select()
        classes = {row['id'].split(':')[-1]: row['classification'] for row in report['events']}
        self.assertEqual(classes, {'malformed-tool-0': 'excluded', 'malformed-tool-1': 'excluded',
                                   'valid-after-malformed': 'supported_human'})
        self.assert_private(report)

    def test_notification_classification_uses_structured_origin_instead_of_body_text(self):
        legacy = claude_input('quoted-notification', human=False,
                              message=dict(role='user', content='<task-notification>' + SECRET))
        notification = claude_input('notification', human=False, origin=dict(kind='notification'))
        self.save([legacy, notification], 'Claude Code')
        report = self.select()
        classes = {row['id'].split(':')[-1]: row['classification'] for row in report['events']}
        self.assertEqual(classes['quoted-notification'], 'ambiguous')
        self.assertEqual(classes['notification'], 'excluded')
        self.assert_private(report)

    def test_tool_result_requires_evidence_of_a_submitted_question_answer(self):
        assistant = dict(type='assistant', timestamp=BASE_TIME, sessionId='claude-root',
                         message=dict(role='assistant', content=[dict(
                             type='tool_use', id='question', name='AskUserQuestion', input=dict(questions=[SECRET]))]))
        answer = claude_input('answer', human=False, message=dict(role='user', content=[dict(
            type='tool_result', tool_use_id='question', content=SECRET)]),
            toolUseResult=dict(questions=[dict(question=SECRET)], answers={SECRET: SECRET}))
        ordinary = claude_input('ordinary-tool', message=dict(role='user', content=[dict(
            type='tool_result', tool_use_id='some-shell-call', content=SECRET)]))
        self.save([assistant, answer, ordinary], 'Claude Code')
        report = self.select()
        self.assertEqual(len(report['events']), 2)
        classes = {row['id'].split(':')[-1]: row['classification'] for row in report['events']}
        self.assertEqual(classes['answer'], 'supported_human')
        self.assertEqual(classes['ordinary-tool'], 'excluded')
        self.assert_private(report)

    def test_same_text_with_independent_stable_ids_is_not_deduplicated(self):
        self.save([codex_meta(), codex_start(), codex_input('one'), codex_input('two')])
        self.save([claude_input('three'), claude_input('four')], 'Claude Code')
        report = self.select()
        self.assertEqual(len(report['events']), 4)
        self.assertEqual(len({event['id'] for event in report['events']}), 4)
        self.assertEqual(report['coverage']['supported_human'], 4)

    def test_copied_stable_id_keeps_native_ownership_in_either_import_order(self):
        native = [codex_meta('native'), codex_start(), codex_input('original', canonical_id='stable')]
        copied = [codex_meta('copy', child=True), codex_meta('native'), codex_start(),
                  codex_input('replayed', canonical_id='stable', inherited=True, timestamp='2026-01-02T09:00:00Z')]
        for index, groups in enumerate([(copied, native), (native, copied)]):
            with self.subTest(order=index):
                records = copy.deepcopy(groups)
                for group in records:
                    group[-1]['metadata']['retained_source']['id']['message_id'] += str(index)
                    group[-1]['payload']['id'] += str(index)
                    self.save(group)
                candidates = [event for event in self.select()['events'] if event['id'].endswith('stable' + str(index))]
                self.assertEqual(len(candidates), 1)
                self.assertEqual(candidates[0]['session'], 'native')
                self.assertEqual(candidates[0]['classification'], 'supported_human')
                self.assertEqual(instant(candidates[0]['timestamp']), instant(BASE_TIME))

    def test_event_and_response_forms_share_the_canonical_message_id(self):
        response = codex_input('response-id', canonical_id='canonical')
        event = dict(type='event_msg', timestamp=BASE_TIME,
                     metadata=dict(retained_source=dict(id=dict(message_id='canonical'))),
                     payload=dict(type='user_message', message=SECRET))
        self.save([codex_meta(), codex_start(), event, response])
        report = self.select()
        self.assertEqual(len(report['events']), 1)
        self.assertTrue(report['events'][0]['id'].endswith('canonical'))
        self.assertEqual(report['events'][0]['classification'], 'supported_human')

    def test_idless_event_wrapper_merges_with_its_recorded_turns_original_input(self):
        response = codex_input('response', timestamp='2026-01-01T09:01:00Z',
                               original_time=BASE_TIME, canonical_id='canonical-original')
        wrapper = dict(type='event_msg', timestamp='2026-01-01T09:02:00Z',
                       payload=dict(type='user_message', turn_id='turn', message=SECRET))
        self.save([codex_meta(), codex_start(), response, wrapper])
        report = self.select()
        self.assertEqual(len(report['events']), 1)
        event = report['events'][0]
        self.assertTrue(event['id'].endswith('canonical-original'))
        self.assertEqual(instant(event['timestamp']), instant(BASE_TIME))
        self.assertIn('create_time', event['timestamp_basis'])
        self.assertEqual(event['classification'], 'supported_human')
        self.assertEqual(report['coverage']['supported_human'], 1)
        self.assert_private(report)
        fingerprint = hashlib.sha256(SECRET.encode()).hexdigest()
        self.assertNotIn(fingerprint, '\n'.join(self.db.iterdump()))
        self.assertNotIn(fingerprint, json.dumps(report))

    def test_idless_wrappers_do_not_merge_repeated_replies_from_distinct_turns(self):
        rows = [codex_meta()]
        original_times = ['2026-01-01T09:00:00Z', '2026-01-01T09:03:00Z']
        for index, original in enumerate(original_times):
            turn = f'repeated-turn-{index}'
            rows.extend([codex_start(turn), codex_input(
                f'repeated-response-{index}', timestamp='2026-01-01T09:04:00Z', turn=turn,
                original_time=original, canonical_id=f'independent-{index}'),
                dict(type='event_msg', timestamp='2026-01-01T09:05:00Z',
                     payload=dict(type='user_message', turn_id=turn, message=SECRET))])
        self.save(rows)
        report = self.select()
        self.assertEqual(len(report['events']), 2)
        self.assertEqual({event['id'] for event in report['events']},
                         {'Codex:independent-0', 'Codex:independent-1'})
        self.assertEqual([instant(event['timestamp']) for event in report['events']],
                         [instant(timestamp) for timestamp in original_times])
        self.assertEqual(report['coverage']['supported_human'], 2)
        self.assert_private(report)

    def test_selection_includes_ten_minute_carry_in_and_excludes_exact_cutoff(self):
        times = [('too-early', '2026-01-01T23:49:59Z'), ('oldest-carry', '2026-01-01T23:50:00Z'),
                 ('carry', '2026-01-01T23:56:00Z'), ('inside', '2026-01-02T00:00:00Z'),
                 ('cutoff', '2026-01-02T00:02:00Z')]
        self.save([claude_input(key, stamp) for key, stamp in times], 'Claude Code')
        report = self.select(start='2026-01-02', end='2026-01-02', cutoff='2026-01-02T00:02:00Z')
        self.assertEqual(len(report['events']), 3)
        self.assertEqual(sum(event['in_reporting_window'] for event in report['events']), 1)
        self.assertEqual(report['coverage']['carry_in_events'], 2)
        self.assertNotIn('Claude Code:cutoff', {event['id'] for event in report['events']})

    def test_selection_excludes_next_day_at_reporting_end(self):
        self.save([claude_input('last', '2026-01-01T23:59:59Z'),
                   claude_input('next', '2026-01-02T00:00:00Z')], 'Claude Code')
        report = self.select(end='2026-01-01')
        self.assertEqual(len(report['events']), 1)
        self.assertTrue(report['events'][0]['id'].endswith('last'))

    def test_local_midnight_carry_in_uses_timezone_including_dst(self):
        self.save([claude_input('carry', '2026-03-09T03:56:00Z'),
                   claude_input('inside', '2026-03-09T04:00:00Z'),
                   claude_input('outside', '2026-03-10T04:00:00Z')], 'Claude Code')
        report = self.select(start='2026-03-09', end='2026-03-09', timezone='America/New_York',
                             cutoff='2026-03-11T00:00:00Z')
        self.assertEqual(len(report['events']), 2)
        self.assertEqual(report['coverage']['carry_in_events'], 1)
        self.assertEqual(sum(event['in_reporting_window'] for event in report['events']), 1)

    def test_project_scope_uses_session_mapping_and_discloses_unmatched_inputs(self):
        for key, session in [('chosen', 'a'), ('other', 'b'), ('unknown', 'c')]:
            self.save([claude_input(key, session=session)], 'Claude Code')
        self.topic('Claude Code', 'a', 'Chosen')
        self.topic('Claude Code', 'b', 'Other')
        report = self.select(projects=['Chosen'])
        self.assertEqual(len(report['events']), 1)
        self.assertEqual(report['events'][0]['project'], 'Chosen')
        self.assertEqual(report['coverage']['unmapped_events'], 1)
        self.assertEqual(report['coverage']['outside_project_events'], 1)
        self.assertEqual(len(report['unmatched_events']), 2)

    def test_inventory_keeps_all_dates_projects_and_classifications_outside_current_selection(self):
        fixtures = [('past', '2025-01-01T09:00:00Z', 'Chosen', {}),
                    ('selected', BASE_TIME, 'Chosen', {}),
                    ('other-project', '2026-01-01T10:00:00Z', 'Other', {}),
                    ('ambiguous', '2026-01-01T11:00:00Z', 'Chosen', {'human': False}),
                    ('excluded', '2026-01-01T11:30:00Z', 'Chosen', {'isMeta': True}),
                    ('cutoff', '2026-01-01T12:00:00Z', 'Chosen', {}),
                    ('future', '2027-01-01T09:00:00Z', 'Chosen', {})]
        for key, timestamp, project, fields in fixtures:
            self.save([claude_input(key, timestamp, session=key, **fields)], 'Claude Code')
            self.topic('Claude Code', key, project)
        before = '\n'.join(self.db.iterdump())
        changes = self.db.total_changes
        self.db.execute('PRAGMA query_only=ON')
        inventory = human_inputs.inventory(self.db, [dict(provider='Claude Code', path=str(self.root))])
        selected = self.select(start='2026-01-01', end='2026-01-01',
                               cutoff='2026-01-01T12:00:00Z', projects=['Chosen'])
        self.assertEqual({event['id'] for event in inventory['events']},
                         {'Claude Code:' + key for key, *_ in fixtures})
        self.assertEqual(inventory['coverage']['selected_events'], 7)
        self.assertEqual({event['classification'] for event in inventory['events']},
                         {'supported_human', 'ambiguous', 'excluded'})
        self.assertEqual({event['id'] for event in selected['events']},
                         {'Claude Code:selected', 'Claude Code:ambiguous', 'Claude Code:excluded'})
        self.assertEqual([event['id'] for event in selected['unmatched_events']], ['Claude Code:other-project'])
        self.assertTrue(inventory['classifier_version'])
        self.assertTrue(inventory['limitations'])
        self.assertEqual(self.db.total_changes, changes)
        self.assertEqual('\n'.join(self.db.iterdump()), before)

    def test_inventory_preserves_original_offset_and_normalizes_calculation_timestamp(self):
        offset_time = '2026-01-01T09:00:00+05:30'
        self.save([claude_input('offset', offset_time)], 'Claude Code')
        self.save([codex_meta(), codex_start(), codex_input('unix-original',
                   timestamp='2026-01-03T09:00:00Z', original_time=offset_time)])
        events = {event['id']: event for event in human_inputs.inventory(self.db)['events']}
        claude = events['Claude Code:offset']
        codex = events['Codex:unix-original']
        self.assertEqual(claude['original_timestamp'], offset_time)
        self.assertEqual(claude['timestamp'], '2026-01-01T03:30:00+00:00')
        self.assertEqual(codex['original_timestamp'], '2026-01-01T03:30:00+00:00')
        self.assertEqual(codex['timestamp'], '2026-01-01T03:30:00+00:00')
        for event in events.values():
            self.assertEqual(event['classifier_version'], human_inputs.CLASSIFIER_VERSION)
            self.assertEqual(event['source_classification'], 'supported_human')
            self.assertEqual(event['source_statuses'], ['current'])

    def test_inventory_retains_deleted_sources_with_controlled_per_event_statuses(self):
        paths = {key: self.save([claude_input(key)], 'Claude Code') for key in ('current', 'changed', 'missing')}
        paths['changed'].write_text(paths['changed'].read_text() + '\n')
        paths['missing'].unlink()
        report = human_inputs.inventory(self.db)
        self.assertEqual(len(report['events']), 3)
        for event in report['events']:
            self.assertEqual(event['source_statuses'], [event['id'].split(':')[-1]])
            self.assertEqual(event['source_classification'], 'supported_human')
            self.assertEqual(event['classification'], 'supported_human')
        self.assertEqual(report['coverage']['current_sources'], 1)
        self.assertEqual(report['coverage']['changed_sources'], 1)
        self.assertEqual(report['coverage']['missing_sources'], 1)
        self.assert_private(report)

    def test_older_classifier_downgrades_operational_support_but_preserves_source_evidence(self):
        path = self.save([claude_input()], 'Claude Code')
        old_version = 'human-inputs-v1'
        self.assertNotEqual(old_version, human_inputs.CLASSIFIER_VERSION)
        self.db.execute('UPDATE human_input_sources SET classifier_version=? WHERE source=?',
                        (old_version, str(path)))
        before = '\n'.join(self.db.iterdump())
        inventory = human_inputs.inventory(self.db)
        selected = self.select()
        for report in (inventory, selected):
            self.assertEqual(len(report['events']), 1)
            event = report['events'][0]
            self.assertEqual(event['classification'], 'ambiguous')
            self.assertEqual(event['source_classification'], 'supported_human')
            self.assertEqual(event['classifier_version'], old_version)
            self.assertEqual(event['source_statuses'], ['current'])
            self.assertEqual(report['classifier_version'], human_inputs.CLASSIFIER_VERSION)
            self.assertEqual(report['coverage']['unsupported_sources'], 1)
            self.assertEqual(report['coverage']['supported_human'], 0)
        self.assertEqual('\n'.join(self.db.iterdump()), before)

    def test_earlier_idless_wrapper_does_not_change_an_existing_canonical_input_id(self):
        rows = [codex_meta(), codex_start(), codex_input('native-id',
                timestamp='2026-01-01T09:00:01Z', canonical_id='stable-selection-id')]
        self.save(rows, name='stable-selection.jsonl')
        before = human_inputs.inventory(self.db)['events']
        self.assertEqual([event['id'] for event in before], ['Codex:stable-selection-id'])
        rows.append(dict(type='event_msg', timestamp=BASE_TIME,
                         payload=dict(type='user_message', turn_id='turn', message=SECRET)))
        self.save(rows, name='stable-selection.jsonl')
        after = human_inputs.inventory(self.db)['events']
        self.assertEqual(len(after), 1)
        self.assertEqual(after[0]['id'], before[0]['id'])
        self.assertEqual(after[0]['classification'], 'supported_human')
        self.assertEqual(after[0]['original_timestamp'], BASE_TIME)

    def test_provider_model_and_role_filters_do_not_claim_delivery_attribution(self):
        self.save([codex_meta(), codex_start(), codex_input()])
        self.save([claude_input()], 'Claude Code')
        unfiltered = self.select()
        filtered = self.select(provider='Codex', model='does-not-exist', role='auditor')
        self.assertEqual(filtered['events'], unfiltered['events'])
        self.assertEqual(filtered['coverage']['selected_events'], 2)

    def test_missing_and_changed_sources_keep_imported_metadata_without_mutating_db(self):
        missing = self.save([claude_input('missing')], 'Claude Code')
        changed = self.save([claude_input('changed')], 'Claude Code')
        missing.unlink()
        changed.write_text(changed.read_text() + json.dumps(dict(changed=True)) + '\n')
        before = '\n'.join(self.db.iterdump())
        changes = self.db.total_changes
        self.db.execute('PRAGMA query_only=ON')
        report = self.select(sources=[dict(provider='Claude Code', path=str(self.root))])
        self.assertEqual(len(report['events']), 2)
        self.assertEqual(report['coverage']['retained_sources'], 2)
        self.assertEqual(report['coverage']['missing_sources'], 1)
        self.assertEqual(report['coverage']['changed_sources'], 1)
        self.assertFalse(report['coverage']['complete'])
        self.assertEqual('\n'.join(self.db.iterdump()), before)
        self.assertEqual(self.db.total_changes, changes)

    def test_claude_copied_uuid_retains_native_session_and_original_timestamp(self):
        self.save([claude_input('copied-uuid', session='native')], 'Claude Code')
        self.save([claude_input('copied-uuid', '2026-01-03T09:00:00Z', session='copy', isReplay=True)],
                  'Claude Code')
        report = self.select()
        self.assertEqual(len(report['events']), 1)
        event = report['events'][0]
        self.assertEqual(event['session'], 'native')
        self.assertEqual(instant(event['timestamp']), instant(BASE_TIME))
        self.assertEqual(event['classification'], 'supported_human')

    def test_task_start_without_an_actual_input_never_seeds_a_timer(self):
        self.save([codex_meta(), codex_start()])
        report = self.select()
        self.assertEqual(report['events'], [])
        self.assertEqual(report['coverage']['supported_human'], 0)

    def test_another_turns_trigger_cannot_certify_a_legacy_input(self):
        self.save([codex_meta(), codex_start(turn='other'), codex_input(turn='this', human=False)])
        report = self.select()
        self.assertEqual(len(report['events']), 1)
        self.assertEqual(report['events'][0]['classification'], 'ambiguous')

    def test_another_turns_automation_trigger_does_not_override_explicit_human_provenance(self):
        self.save([codex_meta(), codex_start(turn='automatic', trigger='goal'), codex_input(turn='human')])
        report = self.select()
        self.assertEqual(len(report['events']), 1)
        self.assertEqual(report['events'][0]['classification'], 'supported_human')

    def test_verified_human_input_is_not_excluded_solely_for_child_thread_name(self):
        self.save([claude_input(isSidechain=True)], 'Claude Code')
        report = self.select()
        self.assertEqual(len(report['events']), 1)
        self.assertEqual(report['events'][0]['classification'], 'supported_human')

    def test_unsupported_schema_invalid_timestamp_and_missing_configured_root_are_explicit(self):
        self.save([dict(type='future-record', timestamp=BASE_TIME, body=SECRET)])
        self.save([claude_input('bad-time', timestamp='not-a-timestamp')], 'Claude Code')
        sources = [dict(provider='Codex', path=str(self.root)),
                   dict(provider='Claude Code', path=str(self.root / 'missing-root'))]
        report = self.select(sources=sources)
        coverage = report['coverage']
        self.assertGreaterEqual(coverage['unsupported_sources'], 1)
        self.assertEqual(coverage['invalid_timestamp_records'], 1)
        self.assertEqual(coverage['configured_roots'], 2)
        self.assertEqual(coverage['missing_roots'], 1)
        self.assertEqual(coverage['selected_events'], 0)
        self.assertFalse(coverage['complete'])
        self.assert_private(report)

    def test_empty_evidence_and_retained_boundary_context_remain_incomplete(self):
        empty = self.select()
        self.assertEqual(empty['events'], [])
        self.assertEqual(empty['coverage']['boundary_context'], 'unavailable')
        self.assertFalse(empty['coverage']['complete'])
        self.save([claude_input()], 'Claude Code')
        retained = self.select()
        self.assertEqual(retained['coverage']['boundary_context'], 'retained_only')
        self.assertFalse(retained['coverage']['complete'])

    def test_save_preserves_the_callers_savepoint_and_does_not_commit(self):
        self.db.commit()
        self.db.execute('SAVEPOINT caller_file')
        self.save([claude_input()], 'Claude Code')
        self.assertEqual(len(self.select()['events']), 1)
        self.db.execute('ROLLBACK TO caller_file')
        self.db.execute('RELEASE caller_file')
        self.assertEqual(self.select()['events'], [])
        self.assertEqual(self.select()['coverage']['retained_sources'], 0)

    def test_reimport_is_idempotent_and_source_contents_never_enter_storage(self):
        rows = [codex_meta(), codex_start(), codex_input()]
        path = self.save(rows, name='repeat.jsonl')
        human_inputs.save(self.db, path, 'Codex', iter(rows))
        report = self.select()
        self.assertEqual(len(report['events']), 1)
        self.assertEqual(report['coverage']['retained_sources'], 1)
        self.assert_private(report)

    def test_sync_refreshes_classifier_version_without_changing_token_accounting(self):
        from app import connect, sync

        histories = self.root / 'sync-fixture'
        histories.mkdir()
        path = histories / 'session.jsonl'
        token = dict(type='token_usage_record', timestamp=BASE_TIME, payload=dict(
            response_id='response', thread_id='root', usage=dict(
                input_tokens=100, cached_input_tokens=80, output_tokens=10, reasoning_output_tokens=5)))
        rows = [codex_meta(), codex_start(), codex_input(), token]
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        ledger = self.root / 'sync.db'
        config = dict(timezone='UTC', sources=[dict(provider='Codex', path=str(histories))])
        first = sync(ledger, config)
        self.assertEqual(first[0]['changed'], 1)
        self.assertEqual(first[0]['errors'], 0)
        self.assertEqual(sync(ledger, config)[0]['changed'], 0)
        with connect(ledger) as db:
            baseline = db.execute('SELECT * FROM events ORDER BY id').fetchall()
            self.assertEqual(len(baseline), 1)
            self.assertEqual(baseline[0][7:12], (100, 80, 0, 10, 5))
        updated_version = human_inputs.CLASSIFIER_VERSION + '-fixture'
        with patch.object(human_inputs, 'CLASSIFIER_VERSION', updated_version):
            refreshed = sync(ledger, config)
            self.assertEqual(refreshed[0]['changed'], 1)
            self.assertEqual(refreshed[0]['errors'], 0)
            with connect(ledger) as db:
                self.assertEqual(db.execute('SELECT * FROM events ORDER BY id').fetchall(), baseline)
                report = human_inputs.select(db, dict(start='2026-01-01', end='2026-01-01'),
                                             'UTC', '2026-01-02T00:00:00Z', config['sources'])
                self.assertEqual(report['coverage']['supported_human'], 1)
                self.assertEqual(report['coverage']['unsupported_sources'], 0)
                self.assertEqual(report['classifier_version'], updated_version)
                self.assertNotIn(SECRET, '\n'.join(db.iterdump()))


if __name__ == '__main__':
    unittest.main()
