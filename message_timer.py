"""Globally unioned human-input windows and fixed-cohort delivery comparisons."""
import datetime as dt
import statistics
from zoneinfo import ZoneInfo

from evidence import instant, merge_spans

METHOD_VERSION = 'message-timer-v1'
SCENARIOS = ('low', 'central', 'high')
TIMEOUTS = (2, 5, 10)
POPULATIONS = ('supported', 'selected', 'inclusive')
UTC = dt.timezone.utc


def options(filters):
    timeout = filters.get('idle_timeout', '5')
    population = filters.get('input_population', 'supported')
    scenario = filters.get('effort_scenario', 'central')
    if timeout not in ('2', '5', '10'):
        raise ValueError('Idle timeout must be 2, 5 or 10 minutes')
    if population not in POPULATIONS:
        raise ValueError('Input population must be supported, selected or inclusive')
    if scenario not in SCENARIOS:
        raise ValueError('Effort scenario must be low, central or high')
    return dict(idle_timeout=int(timeout), input_population=population, effort_scenario=scenario)


def midnight(date, zone):
    return dt.datetime.combine(date, dt.time(), zone).astimezone(UTC)


def union_hours(points, minutes, start, end, zone):
    """Union across identities first, then intersect the reporting window/local days."""
    duration = dt.timedelta(minutes=minutes)
    intervals = merge_spans((time, time + duration) for time in points if time < end and time + duration > start)
    days = {}
    for left, right in intervals:
        left, right = max(left, start), min(right, end)
        while left < right:
            date = left.astimezone(zone).date()
            stop = min(right, midnight(date + dt.timedelta(days=1), zone))
            key = date.isoformat()
            days[key] = days.get(key, 0) + (stop - left).total_seconds() / 3600
            left = stop
    return days


def period(dates, rows, times):
    denominator = sum(times.get(date, 0) for date in dates)
    defined = [date for date in dates if times.get(date, 0) > 0]
    scenarios = {}
    for scenario in SCENARIOS:
        numerator = sum(rows[date]['hours'][scenario] for date in dates)
        ratios = [rows[date]['hours'][scenario] / times[date] for date in defined]
        scenarios[scenario] = dict(numerator_hours=numerator,
                                   pooled=numerator / denominator if dates and denominator > 0 else None,
                                   daily_minimum=min(ratios) if ratios else None,
                                   daily_maximum=max(ratios) if ratios else None,
                                   daily_median=statistics.median(ratios) if ratios else None,
                                   daily_mean=statistics.mean(ratios) if ratios else None)
    return dict(cohort_dates=list(dates), denominator_hours=denominator,
                defined_daily_dates=defined, zero_timer_dates=[date for date in dates if date not in defined], scenarios=scenarios)


def comparisons(dates, rows, durations):
    sensitivity = {population: {str(timeout): period(dates, rows, durations[population][str(timeout)])
                               for timeout in TIMEOUTS} for population in POPULATIONS}
    joint = {population: dict(low=sensitivity[population]['10']['scenarios']['low']['pooled'],
                             high=sensitivity[population]['2']['scenarios']['high']['pooled'])
             for population in POPULATIONS}
    return dict(sensitivity=sensitivity, joint=joint)


def reconciliation(dates, cohort, rows, durations):
    timer_dates = {date for date in dates if any(durations[p][str(t)].get(date, 0) > 0 for p in POPULATIONS for t in TIMEOUTS)}
    outside = sorted(timer_dates - set(cohort))
    result = dict(input_only_dates=sorted(timer_dates - set(rows)), outside_cohort_dates=outside,
                  outside_token_active_dates=sorted(date for date in timer_dates if not rows.get(date, {}).get('eligible')))
    for population in POPULATIONS:
        result[population + '_hours'] = {str(t): sum(durations[population][str(t)].get(d, 0) for d in dates) for t in TIMEOUTS}
        result['outside_cohort_' + population + '_hours'] = {str(t): sum(durations[population][str(t)].get(d, 0) for d in outside) for t in TIMEOUTS}
    return result


def build(days, human, timezone, filters, cutoff):
    selected = options(filters)
    zone = ZoneInfo(timezone)
    stop = instant(cutoff)
    projects = set(filters.get('projects', []))
    resolution = human.get('selection', {})
    chosen_ids = set(resolution.get('ids', []))
    valid_ids = set(resolution.get('valid_ids', [])) & chosen_ids
    resolved_ids = {key:resolution.get('resolved_ids', {}).get(key, key) for key in valid_ids}
    invalid_events = {event.get('id') for event in human.get('events', [])
                      if event.get('classification') != 'ambiguous' or event.get('provenance_conflict')}
    invalid_ids = set(resolution.get('invalid_ids', [])) | {key for key, value in resolved_ids.items() if value in invalid_events}
    valid_ids -= invalid_ids | set(resolution.get('missing_ids', [])) | set(resolution.get('changed_ids', []))
    resolved_ids = {key:resolved_ids[key] for key in valid_ids}
    choices_by_input = {}
    for key, identity in resolved_ids.items():
        choices_by_input.setdefault(identity, []).append(key)
    points = {population: [] for population in POPULATIONS}
    inputs = {population: {} for population in POPULATIONS}
    chosen_inputs = {}
    event_dates, invalid_timestamps, rejected_projects = [], 0, 0
    for event in human.get('events', []):
        if projects and event.get('project') not in projects:
            rejected_projects += 1
            continue
        classification = event.get('classification')
        if classification not in ('supported_human', 'ambiguous') or event.get('provenance_conflict'):
            continue
        try:
            time = instant(event['timestamp'])
        except (ValueError, TypeError, KeyError):
            invalid_timestamps += 1
            continue
        if time >= stop:
            continue
        key = event.get('id') or (event.get('provider'), event.get('session'), time)
        event_dates.append(time.astimezone(zone).date())
        points['inclusive'].append(time)
        inputs['inclusive'].setdefault(key, time)
        if classification == 'supported_human':
            points['supported'].append(time)
            points['selected'].append(time)
            inputs['supported'].setdefault(key, time)
            inputs['selected'].setdefault(key, time)
        elif key in choices_by_input:
            # Selectors reference immutable input identities, not table positions.
            if key not in inputs['selected']:
                chosen_inputs.update((choice, time) for choice in choices_by_input[key])
                points['selected'].append(time)
                inputs['selected'][key] = time
    first_date = dt.date.fromisoformat(filters['start']) if filters.get('start') else min(
        [dt.date.fromisoformat(row['date']) for row in days] + event_dates or [stop.astimezone(zone).date()])
    last_date = dt.date.fromisoformat(filters['end']) if filters.get('end') else stop.astimezone(zone).date()
    start, end = midnight(first_date, zone), min(stop, midnight(last_date + dt.timedelta(days=1), zone))
    rows = {row['date']: row for row in days
            if midnight(dt.date.fromisoformat(row['date']), zone) < end
            and midnight(dt.date.fromisoformat(row['date']) + dt.timedelta(days=1), zone) > start}
    durations = {population: {str(t): union_hours(points[population], t, start, end, zone) for t in TIMEOUTS}
                 for population in POPULATIONS}
    token_dates = sorted(date for date, row in rows.items() if row['eligible'])
    eligible = [date for date in token_dates if not rows[date].get('excluded_low_effort')]
    assessed = [date for date in eligible if rows[date]['status'] == 'assessed']
    cohort = [date for date in assessed if durations['supported']['5'].get(date, 0) > 0]
    cohort_set = set(cohort)
    full_days = [date for date in cohort if not rows[date].get('partial_day', date == stop.astimezone(zone).date().isoformat())]
    all_dates = sorted(set(rows) | {date for p in durations.values() for times in p.values() for date in times})
    input_counts = {p: {} for p in POPULATIONS}
    for population, events in inputs.items():
        for time in events.values():
            if start <= time < end:
                date = time.astimezone(zone).date().isoformat()
                input_counts[population][date] = input_counts[population].get(date, 0) + 1
    selected_dates = {}
    for key, time in chosen_inputs.items():
        if start <= time < end:
            selected_dates.setdefault(time.astimezone(zone).date().isoformat(), []).append(key)
    daily = []
    for date in all_dates:
        row = rows.get(date)
        effort_status = row['status'] if row else 'unassessed'
        effort = {s: row['hours'][s] if row and row['status'] == 'assessed' else None for s in SCENARIOS}
        hours = {p: {str(t): durations[p][str(t)].get(date, 0) for t in TIMEOUTS} for p in POPULATIONS}
        if date in cohort_set:
            reason = None
        elif not row or not row['eligible']:
            reason = 'outside_token_active_scope'
        elif row.get('excluded_low_effort'):
            reason = 'low_effort_filter'
        elif row['status'] != 'assessed':
            reason = 'unknown_output'
        else:
            reason = 'no_supported_reference_timer'
        daily.append(dict(date=date, partial_day=row.get('partial_day', False) if row else date == stop.astimezone(zone).date().isoformat(),
                          in_cohort=date in cohort_set, effort_status=effort_status, effort_hours=effort,
                          known_item_hours={s: (row or {}).get('known_item_hours', {}).get(s) for s in SCENARIOS},
                          exclusion_reason=reason, hours=hours,
                          included_inputs={p: input_counts[p].get(date, 0) for p in POPULATIONS},
                          selected_ambiguous_ids=sorted(selected_dates.get(date, [])),
                          ratios={p: {str(t): {s: effort[s] / hours[p][str(t)] if effort[s] is not None and hours[p][str(t)] > 0 else None
                                             for s in SCENARIOS} for t in TIMEOUTS} for p in POPULATIONS}))
    excluded = [date for date in token_dates if date not in cohort_set]
    scope = dict(dates=cohort, full_day_dates=full_days, token_active_dates=token_dates,
                 eligible_after_filter_dates=eligible, assessed_dates=assessed,
                 unknown_dates=[date for date in token_dates if rows[date]['status'] != 'assessed'],
                 no_supported_timer_dates=[date for date in eligible if durations['supported']['5'].get(date, 0) <= 0],
                 low_effort_excluded_dates=[date for date in token_dates if rows[date].get('excluded_low_effort')],
                 excluded_assessed_hours={s: sum(rows[date]['hours'][s] for date in excluded if rows[date]['status'] == 'assessed') for s in SCENARIOS},
                 excluded_known_item_hours={s: sum(rows[date].get('known_item_hours', {}).get(s, 0) or 0 for date in excluded if rows[date]['status'] != 'assessed') for s in SCENARIOS})
    weeks = {}
    for date in all_dates:
        day = dt.date.fromisoformat(date)
        weeks.setdefault((day - dt.timedelta(days=day.weekday())).isoformat(), []).append(date)
    weekly = []
    for week, dates in weeks.items():
        matched = [date for date in cohort if date in dates]
        weekly.append(dict(date=week, dates=matched, scope_dates=dates,
                           reconciliation=reconciliation(dates, matched, rows, durations),
                           **comparisons(matched, rows, durations)))
    limits = list(human.get('limitations', [])) + [
        'This timer models chat hours; it is not measured hands-on time or a causal productivity multiplier.',
        'Intervals are globally unioned across chats/providers before clipping to local dates and the frozen cutoff. Project durations are not additive.',
        'The matched cohort is assessed token-active dates with supported input time at five minutes, after the optional low-effort filter. It stays fixed across sensitivities.',
        'A zero retained timer is not evidence of zero actual work. No missing-time imputation or token-retention adjustment is applied.',
        'Inputs can include waiting and miss reading, typing, PR review, Slack, meetings and other off-chat work. Matched dates can still have incomplete logs.',
        'Ambiguous-inclusive inputs may contain automation. Joint low/high values are assumption sensitivities, not confidence intervals or true bounds.',
        'Daily statistics are unweighted over defined ratios; the period headline divides total conventional effort by total modeled timer hours on the fixed cohort.']
    recon = reconciliation(all_dates, cohort, rows, durations)
    recon['excluded_project_inputs'] = rejected_projects + len(human.get('unmatched_events', []))
    recon['invalid_timestamp_inputs'] = invalid_timestamps
    in_scope = {key: time for key, time in chosen_inputs.items() if time < end and time + dt.timedelta(minutes=max(TIMEOUTS)) > start}
    headline_scope, outside_cohort = {}, {}
    for timeout in TIMEOUTS:
        headline_scope[str(timeout)] = sorted(key for key, time in in_scope.items()
                                             if any(date in cohort_set for date in union_hours([time], timeout, start, end, zone)))
        outside_cohort[str(timeout)] = sorted(set(in_scope) - set(headline_scope[str(timeout)]))
    selection = dict(version=resolution.get('version', 0), ids=sorted(chosen_ids), valid_ids=sorted(valid_ids),
                     resolved_ids=resolved_ids,
                     missing_ids=sorted(set(resolution.get('missing_ids', []))),
                     changed_ids=sorted(set(resolution.get('changed_ids', []))), invalid_ids=sorted(invalid_ids),
                     selected_count=len(chosen_ids), valid_count=len(valid_ids), classification='ambiguous',
                     in_scope_ids=sorted(in_scope), outside_scope_ids=sorted(valid_ids - set(in_scope)), in_scope_count=len(in_scope),
                     headline_scope_ids=headline_scope, outside_cohort_ids=outside_cohort,
                     label=f'Supported + {len({resolved_ids[key] for key in in_scope})} user-included ambiguous inputs',
                     warnings=list(resolution.get('warnings', [])),
                     limitations=['User inclusion does not change the ambiguous source classification or establish human origin.',
                                  'Within-headline-cohort windows may overlap existing time; counts are not additive durations.',
                                  'In-scope counts include timer tails entering the report at any supported timeout; daily input counts use original input dates.'])
    return dict(method_version=METHOD_VERSION,
                interval_method='Global union of half-open [human input, input + idle timeout) windows; clipped at local-day and report boundaries.',
                options=selected, selection=selection, reference=dict(idle_timeout=5, input_population='supported'),
                window=dict(start=start.isoformat(), end=end.isoformat()), cohort=scope, days=daily,
                **comparisons(cohort, rows, durations),
                full_days=dict(dates=full_days, **comparisons(full_days, rows, durations)), weekly=weekly,
                reconciliation=recon, coverage=human.get('coverage', {}), classifier_version=human.get('classifier_version'), limitations=limits)
