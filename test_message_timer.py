import datetime as dt
import json
import unittest

import message_timer as timer


def day(date, hours, *, eligible=True, partial=False, excluded=False):
    values = dict(low=hours / 2, central=hours, high=hours * 2) if hours is not None else dict.fromkeys(('low', 'central', 'high'))
    return dict(date=date, eligible=eligible, status='assessed' if hours is not None else 'unknown',
                hours=values, known_item_hours=dict(low=0, central=0, high=0),
                partial_day=partial, excluded_low_effort=excluded)


def input_at(timestamp, id=None, classification='supported_human', provider='Codex', session='private-thread', project='Example'):
    return dict(id=id or timestamp, provider=provider, session=session, timestamp=timestamp,
                timestamp_basis='original event', classification=classification, project=project)


def active_hours(date, hours, start_hour=9):
    start = dt.datetime.fromisoformat(date + f'T{start_hour:02}:00:00+00:00')
    return [input_at((start + dt.timedelta(minutes=5 * n)).isoformat()) for n in range(hours * 12)]


def report(days, inputs=(), timezone='UTC', start='2026-01-01', end='2026-01-31', cutoff='2026-02-01T00:00:00Z', selection=None, **filters):
    human = dict(events=list(inputs), coverage=dict(retained_sources=1), classifier_version='fixture-v1', limitations=['Fixture retention is incomplete.'])
    if selection is not None:
        human['selection'] = selection
    return timer.build(days, human, timezone, dict(start=start, end=end, **filters), cutoff)


def rows(result):
    return {row['date']: row for row in result['days']}


class MessageTimerTests(unittest.TestCase):
    def test_options_are_independent_and_reject_unsupported_values(self):
        self.assertEqual(timer.options({}), dict(idle_timeout=5, input_population='supported', effort_scenario='central'))
        self.assertEqual(timer.options(dict(idle_timeout='2', input_population='inclusive', effort_scenario='high')),
                         dict(idle_timeout=2, input_population='inclusive', effort_scenario='high'))
        self.assertEqual(timer.options(dict(input_population='selected'))['input_population'], 'selected')
        for key, value in [('idle_timeout', '0'), ('idle_timeout', '3'), ('idle_timeout', 'nan'),
                           ('input_population', 'all'), ('effort_scenario', 'maximum')]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                timer.options({key: value})

    def test_variable_time_headline_is_ratio_of_sums_not_daily_mean(self):
        days = [day('2026-01-01', 10), day('2026-01-02', 18)]
        result = report(days, active_hours('2026-01-01', 1) + active_hours('2026-01-02', 9))
        stats = result['sensitivity']['supported']['5']
        self.assertEqual(result['cohort']['dates'], ['2026-01-01', '2026-01-02'])
        self.assertAlmostEqual(stats['denominator_hours'], 10)
        central = stats['scenarios']['central']
        self.assertEqual(central['numerator_hours'], 28)
        self.assertAlmostEqual(central['pooled'], 2.8)
        self.assertAlmostEqual(central['daily_minimum'], 2)
        self.assertAlmostEqual(central['daily_maximum'], 10)
        self.assertAlmostEqual(central['daily_median'], 6)
        self.assertAlmostEqual(central['daily_mean'], 6)
        self.assertAlmostEqual(stats['scenarios']['low']['pooled'], 1.4)
        self.assertAlmostEqual(stats['scenarios']['high']['pooled'], 5.6)
        self.assertAlmostEqual(result['joint']['supported']['low'], 14 / (10 + 10 / 60))
        self.assertAlmostEqual(result['joint']['supported']['high'], 56 / 4)

    def test_missing_timer_and_unknown_output_do_not_enter_matched_cohort(self):
        dates = ['2026-01-01', '2026-01-02', '2026-01-03', '2026-01-04']
        days = [day(date, effort) for date, effort in zip(dates, [8, 0, 16, None])]
        inputs = active_hours(dates[0], 2) + active_hours(dates[1], 2) + active_hours(dates[3], 1)
        result = report(days, inputs)
        self.assertEqual(result['cohort']['dates'], dates[:2])
        self.assertEqual(result['cohort']['unknown_dates'], [dates[3]])
        self.assertIn(dates[2], result['cohort']['no_supported_timer_dates'])
        self.assertEqual(result['cohort']['excluded_assessed_hours']['central'], 16)
        stats = result['sensitivity']['supported']['5']
        self.assertAlmostEqual(stats['denominator_hours'], 4)
        self.assertAlmostEqual(stats['scenarios']['central']['pooled'], 2)
        self.assertEqual(stats['scenarios']['central']['daily_minimum'], 0)
        details = rows(result)
        self.assertIsNone(details[dates[2]]['ratios']['supported']['5']['central'])
        self.assertIsNone(details[dates[3]]['ratios']['supported']['5']['central'])
        self.assertAlmostEqual(result['reconciliation']['outside_cohort_supported_hours']['5'], 1)

    def test_union_is_global_and_ambiguous_inputs_do_not_change_reference_cohort(self):
        inputs = [input_at('2026-01-01T09:00:00Z', 'same-message'),
                  input_at('2026-01-01T09:00:00Z', 'same-message', session='copied-thread'),
                  input_at('2026-01-01T09:03:00Z', 'other-chat', provider='Claude Code', session='another-thread'),
                  input_at('2026-01-01T09:04:00Z', 'assistant', classification='excluded'),
                  input_at('2026-01-01T09:20:00Z', 'legacy', classification='ambiguous'),
                  input_at('2026-01-02T09:00:00Z', 'ambiguous-only', classification='ambiguous')]
        result = report([day('2026-01-01', 8), day('2026-01-02', 16)], inputs,
                        idle_timeout='10', input_population='inclusive', effort_scenario='high')
        self.assertEqual(result['cohort']['dates'], ['2026-01-01'])
        self.assertAlmostEqual(result['sensitivity']['supported']['5']['denominator_hours'] * 60, 8)
        self.assertAlmostEqual(result['sensitivity']['inclusive']['5']['denominator_hours'] * 60, 13)
        for population in ('supported', 'selected', 'inclusive'):
            for timeout in ('2', '5', '10'):
                self.assertEqual(result['sensitivity'][population][timeout]['cohort_dates'], ['2026-01-01'])
        self.assertIn('2026-01-02', result['cohort']['no_supported_timer_dates'])

    def test_midnight_tail_and_cutoff_freeze_reference_cohort(self):
        dates = ['2026-01-01', '2026-01-02']
        result = report([day(dates[0], 8), day(dates[1], 16, partial=True)],
                        [input_at('2026-01-01T23:56:00Z'), input_at('2026-01-02T00:02:00Z', 'exact-cutoff')],
                        end='2026-01-02', cutoff='2026-01-02T00:02:00Z')
        self.assertEqual(result['cohort']['dates'], dates)
        details = rows(result)
        for timeout, expected in [('2', [2, 0]), ('5', [4, 1]), ('10', [4, 2])]:
            with self.subTest(timeout=timeout):
                actual = [details[date]['hours']['supported'][timeout] * 60 for date in dates]
                for value, wanted in zip(actual, expected):
                    self.assertAlmostEqual(value, wanted)
                self.assertEqual(result['sensitivity']['supported'][timeout]['cohort_dates'], dates)
        short = result['sensitivity']['supported']['2']
        self.assertEqual(short['zero_timer_dates'], [dates[1]])
        self.assertEqual(short['defined_daily_dates'], [dates[0]])
        self.assertEqual(short['scenarios']['central']['numerator_hours'], 24)
        self.assertAlmostEqual(short['scenarios']['central']['pooled'], 720)
        self.assertAlmostEqual(short['scenarios']['central']['daily_mean'], 240)
        self.assertIsNone(details[dates[1]]['ratios']['supported']['2']['central'])
        self.assertEqual(result['full_days']['dates'], [dates[0]])

    def test_second_date_selection_keeps_carry_in_and_zero_sensitivity_is_na(self):
        result = report([day('2026-01-02', 16, partial=True)], [input_at('2026-01-01T23:56:00Z')],
                        start='2026-01-02', end='2026-01-02', cutoff='2026-01-02T00:02:00Z')
        self.assertEqual(result['cohort']['dates'], ['2026-01-02'])
        self.assertAlmostEqual(result['sensitivity']['supported']['5']['denominator_hours'] * 60, 1)
        self.assertAlmostEqual(result['sensitivity']['supported']['10']['denominator_hours'] * 60, 2)
        self.assertEqual(result['sensitivity']['supported']['2']['denominator_hours'], 0)
        self.assertIsNone(result['sensitivity']['supported']['2']['scenarios']['central']['pooled'])
        self.assertIsNone(result['joint']['supported']['high'])
        self.assertEqual(result['full_days']['dates'], [])
        self.assertIsNone(result['full_days']['sensitivity']['supported']['5']['scenarios']['central']['pooled'])

    def test_dst_spring_and_fall_use_elapsed_time_instead_of_wall_clock(self):
        cases = [('2026-03-08', '2026-03-08T01:58:00-05:00', '2026-03-09T00:00:00-04:00'),
                 ('2026-11-01', '2026-11-01T01:58:00-04:00', '2026-11-02T00:00:00-05:00')]
        for date, timestamp, cutoff in cases:
            with self.subTest(date=date):
                result = report([day(date, 8)], [input_at(timestamp)], timezone='America/New_York',
                                start=date, end=date, cutoff=cutoff)
                for timeout in ('2', '5', '10'):
                    self.assertAlmostEqual(result['sensitivity']['supported'][timeout]['denominator_hours'] * 60, int(timeout))

    def test_reporting_end_and_half_open_tail_do_not_add_next_day(self):
        result = report([day('2026-01-01', 8)], [input_at('2026-01-01T23:55:00Z'), input_at('2026-01-02T00:00:00Z')],
                        end='2026-01-01')
        self.assertNotIn('2026-01-02', rows(result))
        self.assertAlmostEqual(result['sensitivity']['supported']['5']['denominator_hours'] * 60, 5)
        self.assertAlmostEqual(result['sensitivity']['supported']['10']['denominator_hours'] * 60, 5)

    def test_dst_dates_end_at_local_midnight_not_twenty_four_hours_later(self):
        for date, following, offset in [('2026-03-08', '2026-03-09', '-04:00'),
                                         ('2026-11-01', '2026-11-02', '-05:00')]:
            with self.subTest(date=date):
                result = report([day(date, 8), day(following, 16, partial=True)],
                                [input_at(date + 'T23:58:00' + offset)], timezone='America/New_York',
                                start=date, end=following, cutoff=following + 'T00:03:00' + offset)
                details = rows(result)
                self.assertAlmostEqual(details[date]['hours']['supported']['5'] * 60, 2)
                self.assertAlmostEqual(details[following]['hours']['supported']['5'] * 60, 3)
                self.assertEqual(result['cohort']['dates'], [date, following])

    def test_input_only_dates_are_disclosed_without_invented_zero_effort(self):
        result = report([day('2026-01-01', 8)], [input_at('2026-01-01T09:00:00Z'), input_at('2026-01-02T09:00:00Z')])
        self.assertEqual(result['reconciliation']['input_only_dates'], ['2026-01-02'])
        self.assertIn('2026-01-02', result['reconciliation']['outside_cohort_dates'])
        extra = rows(result)['2026-01-02']
        self.assertFalse(extra['in_cohort'])
        self.assertIsNone(extra['effort_hours']['central'])
        self.assertIsNone(extra['ratios']['supported']['5']['central'])
        self.assertAlmostEqual(result['reconciliation']['supported_hours']['5'] * 60, 10)
        self.assertAlmostEqual(result['reconciliation']['outside_cohort_supported_hours']['5'] * 60, 5)

    def test_empty_cohort_and_filtered_dates_never_impute_timer(self):
        result = report([day('2026-01-01', 8)], [])
        self.assertEqual(result['cohort']['dates'], [])
        self.assertEqual(result['cohort']['excluded_assessed_hours']['central'], 8)
        for population in ('supported', 'selected', 'inclusive'):
            for timeout in ('2', '5', '10'):
                stats = result['sensitivity'][population][timeout]
                self.assertEqual(stats['denominator_hours'], 0)
                self.assertIsNone(stats['scenarios']['central']['pooled'])
                self.assertIsNone(stats['scenarios']['central']['daily_mean'])
            self.assertIsNone(result['joint'][population]['low'])
            self.assertIsNone(result['joint'][population]['high'])
        filtered = report([day('2026-01-01', .1, excluded=True), day('2026-01-02', 8)],
                          [input_at('2026-01-01T09:00:00Z'), input_at('2026-01-02T09:00:00Z')])
        self.assertEqual(filtered['cohort']['dates'], ['2026-01-02'])
        self.assertEqual(filtered['cohort']['low_effort_excluded_dates'], ['2026-01-01'])
        self.assertEqual(filtered['cohort']['token_active_dates'], ['2026-01-01', '2026-01-02'])
        self.assertEqual(filtered['cohort']['eligible_after_filter_dates'], ['2026-01-02'])
        self.assertAlmostEqual(filtered['sensitivity']['supported']['5']['scenarios']['central']['numerator_hours'], 8)

    def test_weekly_and_full_day_views_keep_only_their_original_matched_dates(self):
        dates = ['2026-01-04', '2026-01-05', '2026-01-06']
        result = report([day(dates[0], 8), day(dates[1], 16), day(dates[2], 24, partial=True)],
                        [input_at(date + 'T09:00:00Z') for date in dates], end=dates[-1], cutoff=dates[-1] + 'T12:00:00Z')
        self.assertEqual(result['full_days']['dates'], dates[:2])
        self.assertEqual(result['full_days']['sensitivity']['supported']['5']['scenarios']['central']['numerator_hours'], 24)
        weeks = {week['date']: week for week in result['weekly']}
        self.assertEqual(weeks['2025-12-29']['dates'], dates[:1])
        self.assertEqual(weeks['2026-01-05']['dates'], dates[1:])
        self.assertEqual(weeks['2026-01-05']['sensitivity']['supported']['5']['scenarios']['central']['numerator_hours'], 40)

    def test_project_scope_does_not_mix_unrelated_or_unmapped_time(self):
        result = report([day('2026-01-01', 8)],
                        [input_at('2026-01-01T09:00:00Z', project='Example'),
                         input_at('2026-01-01T10:00:00Z', project='Unrelated private project'),
                         input_at('2026-01-01T11:00:00Z', project=None)], projects=['Example'])
        self.assertAlmostEqual(result['sensitivity']['supported']['5']['denominator_hours'] * 60, 5)
        serialized = json.dumps(result)
        self.assertNotIn('Unrelated private project', serialized)
        self.assertNotIn('private-thread', serialized)
        self.assertEqual(result['classifier_version'], 'fixture-v1')
        self.assertIn('Fixture retention is incomplete.', result['limitations'])

    def test_individual_choices_union_intervals_and_recompute_every_selected_view(self):
        dates = [day('2026-01-01', 2)]
        inputs = [input_at('2026-01-01T09:00:00Z', 'S'),
                  input_at('2026-01-01T09:03:00Z', 'A', classification='ambiguous'),
                  input_at('2026-01-01T09:20:00Z', 'B', classification='ambiguous'),
                  input_at('2026-01-01T09:22:00Z', 'C', classification='ambiguous'),
                  input_at('2026-01-01T09:03:00Z', 'A', classification='ambiguous', session='copied-thread')]
        unchanged = json.dumps([dates, inputs], sort_keys=True)
        baseline = report(dates, inputs)
        chosen = report(dates, inputs, input_population='selected',
                        selection=dict(version=7, ids=['A', 'B', 'A'], valid_ids=['A', 'B', 'A']))
        self.assertEqual(chosen['cohort'], baseline['cohort'])
        for population in ('supported', 'inclusive'):
            self.assertEqual(chosen['sensitivity'][population], baseline['sensitivity'][population])
        self.assertAlmostEqual(chosen['sensitivity']['supported']['5']['denominator_hours'] * 60, 5)
        self.assertAlmostEqual(chosen['sensitivity']['inclusive']['5']['denominator_hours'] * 60, 15)
        self.assertAlmostEqual(chosen['sensitivity']['supported']['5']['scenarios']['central']['pooled'], 24)
        self.assertAlmostEqual(chosen['sensitivity']['inclusive']['5']['scenarios']['central']['pooled'], 8)
        for timeout, minutes in [('2', 6), ('5', 13), ('10', 23)]:
            with self.subTest(timeout=timeout):
                stats = chosen['sensitivity']['selected'][timeout]
                self.assertEqual(stats['cohort_dates'], ['2026-01-01'])
                self.assertEqual(stats['scenarios']['central']['numerator_hours'], 2)
                self.assertAlmostEqual(stats['denominator_hours'] * 60, minutes)
                self.assertAlmostEqual(stats['scenarios']['central']['pooled'], 120 / minutes)
                self.assertAlmostEqual(stats['scenarios']['central']['daily_mean'], 120 / minutes)
                self.assertAlmostEqual(rows(chosen)['2026-01-01']['hours']['selected'][timeout] * 60, minutes)
        self.assertAlmostEqual(chosen['joint']['selected']['low'], 60 / 23)
        self.assertAlmostEqual(chosen['joint']['selected']['high'], 40)
        self.assertAlmostEqual(chosen['full_days']['sensitivity']['selected']['5']['scenarios']['central']['pooled'], 120 / 13)
        self.assertAlmostEqual(chosen['weekly'][0]['sensitivity']['selected']['5']['scenarios']['central']['pooled'], 120 / 13)
        detail = rows(chosen)['2026-01-01']
        self.assertEqual(detail['included_inputs'], dict(supported=1, selected=3, inclusive=4))
        self.assertEqual(set(detail['selected_ambiguous_ids']), {'A', 'B'})
        self.assertAlmostEqual(detail['ratios']['selected']['5']['central'], 120 / 13)
        self.assertEqual(chosen['selection']['version'], 7)
        self.assertEqual(chosen['selection']['selected_count'], 2)
        self.assertEqual(chosen['selection']['valid_count'], 2)
        self.assertEqual(chosen['selection']['in_scope_count'], 2)
        self.assertEqual(json.dumps([dates, inputs], sort_keys=True), unchanged)
        deselected = report(dates, inputs, input_population='selected',
                            selection=dict(version=8, ids=['A'], valid_ids=['A']))
        self.assertAlmostEqual(deselected['sensitivity']['selected']['5']['denominator_hours'] * 60, 8)
        reset = report(dates, inputs, input_population='selected', selection=dict(version=9, ids=[], valid_ids=[]))
        self.assertEqual(reset['sensitivity']['selected'], reset['sensitivity']['supported'])
        self.assertEqual(reset['cohort'], baseline['cohort'])

    def test_selected_population_requires_resolved_ambiguous_ids(self):
        inputs = [input_at('2026-01-01T09:00:00Z', 'S'),
                  input_at('2026-01-01T09:20:00Z', 'A', classification='ambiguous'),
                  input_at('2026-01-01T09:40:00Z', 'changed', classification='ambiguous'),
                  input_at('2026-01-01T10:00:00Z', 'machine', classification='excluded'),
                  input_at('2026-01-01T10:20:00Z', 'invalid', classification='ambiguous')]
        selection = dict(version=3, ids=['A', 'changed', 'missing', 'machine', 'invalid', 'S'],
                         valid_ids=['A', 'machine', 'S'], changed_ids=['changed'], missing_ids=['missing'], invalid_ids=['invalid'])
        result = report([day('2026-01-01', 2)], inputs, selection=selection, input_population='selected')
        self.assertAlmostEqual(result['sensitivity']['selected']['5']['denominator_hours'] * 60, 10)
        self.assertEqual(set(result['selection']['valid_ids']), {'A'})
        self.assertIn('changed', result['selection']['changed_ids'])
        self.assertIn('missing', result['selection']['missing_ids'])
        self.assertEqual(set(result['selection']['invalid_ids']), {'machine', 'invalid', 'S'})
        self.assertEqual(result['selection']['selected_count'], 6)
        self.assertEqual(result['selection']['valid_count'], 1)
        self.assertEqual(rows(result)['2026-01-01']['included_inputs']['selected'], 2)
        unresolved = report([day('2026-01-01', 2)], inputs,
                            selection=dict(version=4, ids=['A']), input_population='selected')
        self.assertEqual(unresolved['sensitivity']['selected'], unresolved['sensitivity']['supported'])

    def test_choices_outside_cohort_and_applied_scope_do_not_expand_headline(self):
        dates = [day('2026-01-01', 2), day('2026-01-02', 20)]
        inputs = [input_at('2026-01-01T09:00:00Z', 'S'),
                  input_at('2026-01-01T09:03:00Z', 'A', classification='ambiguous'),
                  input_at('2026-01-02T09:00:00Z', 'B', classification='ambiguous'),
                  input_at('2026-01-03T09:00:00Z', 'C', classification='ambiguous'),
                  input_at('2026-01-04T09:00:00Z', 'D', classification='ambiguous'),
                  input_at('2026-01-01T10:00:00Z', 'X', classification='ambiguous', project='Private other project')]
        selected = ['A', 'B', 'C', 'D', 'X']
        result = report(dates, inputs, end='2026-01-03', projects=['Example'], input_population='selected',
                        selection=dict(version=2, ids=selected, valid_ids=selected))
        self.assertEqual(result['cohort']['dates'], ['2026-01-01'])
        self.assertEqual(result['sensitivity']['selected']['5']['scenarios']['central']['numerator_hours'], 2)
        self.assertAlmostEqual(result['sensitivity']['selected']['5']['denominator_hours'] * 60, 8)
        self.assertEqual(set(result['selection']['in_scope_ids']), {'A', 'B', 'C'})
        self.assertEqual(set(result['selection']['outside_scope_ids']), {'D', 'X'})
        self.assertEqual(result['selection']['ids'], selected)
        self.assertEqual(result['selection']['selected_count'], 5)
        self.assertEqual(result['selection']['in_scope_count'], 3)
        for timeout in ('2', '5', '10'):
            self.assertEqual(set(result['selection']['headline_scope_ids'][timeout]), {'A'})
            self.assertEqual(set(result['selection']['outside_cohort_ids'][timeout]), {'B', 'C'})
        self.assertFalse(rows(result)['2026-01-02']['in_cohort'])
        self.assertEqual(rows(result)['2026-01-02']['included_inputs']['selected'], 1)
        self.assertIn('2026-01-03', result['reconciliation']['input_only_dates'])
        self.assertNotIn('Private other project', json.dumps(result))
        self.assertNotIn('private-thread', json.dumps(result))

    def test_selected_midnight_tails_preserve_cohort_zero_endpoints_and_input_counts(self):
        inputs = [input_at('2026-01-01T23:56:00Z', 'S'),
                  input_at('2026-01-01T23:57:00Z', 'A', classification='ambiguous'),
                  input_at('2026-01-02T00:02:00Z', 'cutoff', classification='ambiguous')]
        result = report([day('2026-01-02', 2, partial=True)], inputs,
                        start='2026-01-02', end='2026-01-02', cutoff='2026-01-02T00:02:00Z',
                        input_population='selected', selection=dict(version=1, ids=['A', 'cutoff'], valid_ids=['A', 'cutoff']))
        self.assertEqual(result['cohort']['dates'], ['2026-01-02'])
        detail = rows(result)['2026-01-02']
        self.assertEqual(detail['included_inputs'], dict(supported=0, selected=0, inclusive=0))
        self.assertAlmostEqual(detail['hours']['selected']['5'] * 60, 2)
        self.assertAlmostEqual(detail['hours']['selected']['10'] * 60, 2)
        self.assertAlmostEqual(detail['ratios']['selected']['5']['central'], 60)
        self.assertEqual(detail['hours']['selected']['2'], 0)
        self.assertIsNone(detail['ratios']['selected']['2']['central'])
        self.assertIsNone(result['sensitivity']['selected']['2']['scenarios']['central']['pooled'])
        self.assertIsNone(result['joint']['selected']['high'])
        self.assertEqual(result['selection']['headline_scope_ids']['2'], [])
        self.assertEqual(result['selection']['headline_scope_ids']['5'], ['A'])
        self.assertIn('cutoff', result['selection']['outside_scope_ids'])


if __name__ == '__main__':
    unittest.main()
