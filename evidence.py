"""Retained accounting provenance and bounded activity metadata; no transcript storage."""
import datetime as dt
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

PARSER_VERSION = 'engineering-evidence-v5'
UTC = dt.timezone.utc


def instant(value):
    if not isinstance(value, str):
        raise ValueError('Evidence timestamps must be offset-bearing strings')
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Evidence timestamps must include an offset')
    return result.astimezone(UTC)


def now():
    return dt.datetime.now(UTC).isoformat()


def init(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS response_sources (
      event_id TEXT, source TEXT, source_hash TEXT, stamp TEXT, parser TEXT,
      observed_at TEXT, counters TEXT, known TEXT, identity TEXT,
      first_event TEXT, last_event TEXT, granularity TEXT,
      PRIMARY KEY(event_id,source));
    CREATE INDEX IF NOT EXISTS response_sources_source ON response_sources(source,granularity);
    CREATE TABLE IF NOT EXISTS activity_sources (
      source TEXT PRIMARY KEY, stamp TEXT, observed_at TEXT, body TEXT);
    CREATE TABLE IF NOT EXISTS legacy_origins (
      event_id TEXT, source TEXT, PRIMARY KEY(event_id,source));
    CREATE INDEX IF NOT EXISTS legacy_origins_source ON legacy_origins(source);
    CREATE TABLE IF NOT EXISTS superseded_legacy (
      event_id TEXT PRIMARY KEY, source TEXT, observed_at TEXT);
    ''')


def stamp(path):
    stat = Path(path).stat()
    return f'{stat.st_mtime_ns}:{stat.st_size}'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def known_counters(usage, provider, legacy=False):
    keys = {'input': 'input_tokens', 'output': 'output_tokens',
            'cached': 'cached_input_tokens' if provider == 'Codex' else 'cache_read_input_tokens',
            'cache_write': 'cache_write_input_tokens' if provider == 'Codex' else 'cache_creation_input_tokens',
            'reasoning': 'reasoning_output_tokens'}
    known = {name: key in usage and isinstance(usage[key], int) and not isinstance(usage[key], bool) and usage[key] >= 0 for name, key in keys.items()}
    # Codex has no native cache-write counter; the normalization defines it as zero.
    if provider == 'Codex' and 'cache_write_input_tokens' not in usage:
        known['cache_write'] = True
    if provider != 'Codex':
        known['input'] = all(known[k] for k in ('input', 'cached', 'cache_write'))
    if legacy:
        known['legacy_without_response_id'] = True
    return known


def record_provenance(target, row, usage, provider, identity=None, granularity='response', previous_usage=None):
    if target is None:
        return
    timestamp = instant(row[1]).isoformat()
    counters = dict(zip(('input', 'cached', 'cache_write', 'output', 'reasoning'), row[7:12]))
    known = known_counters(usage, provider, granularity == 'legacy_delta')
    if previous_usage:
        prior = known_counters(previous_usage, provider, granularity == 'legacy_delta')
        known = {key: valid and prior[key] for key, valid in known.items()}
    item = target.get(row[0])
    if item:
        for key, value in counters.items():
            if value > item['counters'][key]:
                item['known'][key] = known.get(key, False)
            elif value == item['counters'][key]:
                item['known'][key] = item['known'].get(key, False) or known.get(key, False)
            item['counters'][key] = max(item['counters'][key], value)
        item['first_event'] = min(item['first_event'], timestamp)
        item['last_event'] = max(item['last_event'], timestamp)
    else:
        target[row[0]] = dict(counters=counters, known=known,
                             identity=identity or provider + ':' + row[4],
                             first_event=timestamp, last_event=timestamp, granularity=granularity)


def save_provenance(db, path, observations, source_stamp=None):
    path = Path(path)
    source_stamp = source_stamp or stamp(path)
    source_hash = digest(path)
    if stamp(path) != source_stamp:
        raise ValueError('History changed while reading; retry sync')
    db.execute("INSERT OR IGNORE INTO legacy_origins SELECT event_id,source FROM response_sources WHERE source=? AND granularity='legacy_delta'", (str(path),))
    db.execute('DELETE FROM response_sources WHERE source=?', (str(path),))
    observed = now()
    for key, item in observations.items():
        db.execute('INSERT INTO response_sources VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                   (key, str(path), source_hash, source_stamp, PARSER_VERSION, observed,
                    json.dumps(item['counters']), json.dumps(item['known']), item['identity'],
                    item['first_event'], item['last_event'], item['granularity']))


def claude_identity(path, row):
    session = row.get('sessionId', Path(path).stem)
    agent = row.get('agentId')
    if not agent and 'subagents' in Path(path).parts:
        agent = Path(path).stem.removeprefix('agent-')
    if agent:
        return f'Claude Code:{session}:child:{agent}', f'Claude Code:{session}'
    if row.get('isSidechain'):
        # Missing agent IDs cannot establish how many distinct children existed.
        return f'Claude Code:{session}:child:unknown', f'Claude Code:{session}'
    return f'Claude Code:{session}', None


def merge_identity(target, incoming):
    # Missing child metadata in a copied record is not evidence of a root.
    parents = set(target.get('parent_candidates', [])) | set(incoming.get('parent_candidates', []))
    parents.update(p for p in (target['parent'], incoming['parent']) if p)
    target['child'] = target['child'] or incoming['child'] or bool(parents)
    target['parent'] = next(iter(parents)) if len(parents) == 1 else None
    target['identity_uncertain'] |= incoming['identity_uncertain'] or len(parents) > 1
    if len(parents) > 1:
        target['parent_candidates'] = sorted(parents)
    if 'span_basis' in incoming:
        target['span_basis'] = 'estimated child observation span' if target['child'] else incoming['span_basis']


def collect_activity(path, provider, rows):
    """Retain timestamps/identity edges only, with roots bounded by observed turns."""
    agents, points, spans, open_turns, terminal = {}, defaultdict(set), defaultdict(list), {}, set()
    session, parent, child = Path(path).stem, None, False
    for row in rows:
        payload = row.get('payload') or {}
        if provider == 'Codex' and row.get('type') == 'session_meta':
            session = payload.get('id') or session
            source = payload.get('source') or {}
            child = isinstance(source, dict) and 'subagent' in source
            spawn = source.get('subagent', {}).get('thread_spawn', {}) if isinstance(source, dict) and isinstance(source.get('subagent'), dict) else {}
            parent = 'Codex:' + spawn['parent_thread_id'] if spawn.get('parent_thread_id') else None
        if provider == 'Claude Code':
            identity, edge = claude_identity(path, row)
            session = row.get('sessionId', session)
            is_child = edge is not None
        else:
            identity = 'Codex:' + (payload.get('thread_id') or session)
            is_child = child and identity == 'Codex:' + session
            edge = parent if is_child else None
        metadata = dict(id=identity, provider=provider, session=identity[6:] if provider == 'Codex' else session, parent=edge, child=is_child, missing_terminal=False, identity_uncertain=identity.endswith(':child:unknown'), responses=[], request_observed=False)
        agent = agents.setdefault(identity, metadata)
        merge_identity(agent, metadata)
        if not row.get('timestamp'):
            continue
        try:
            timestamp = instant(row['timestamp']).isoformat()
        except (ValueError, TypeError, AttributeError):
            continue
        points[identity].add(timestamp)
        response_id = payload.get('response_id') if provider == 'Codex' and row.get('type') == 'token_usage_record' else (row.get('message') or {}).get('id') if provider == 'Claude Code' and row.get('type') == 'assistant' else None
        if response_id:
            agent['responses'].append([provider + ':' + response_id, timestamp])
        start = (payload.get('type') == 'task_started' or (row.get('type') == 'response_item' and payload.get('role') == 'user')) if provider == 'Codex' else row.get('type') == 'user' and isinstance((row.get('message') or {}).get('content'), str)
        end = payload.get('type') in ('task_complete', 'task_completed', 'turn_aborted') if provider == 'Codex' else (row.get('message') or {}).get('stop_reason') in ('end_turn', 'stop_sequence')
        if start and identity not in open_turns:
            agent['request_observed'] = True
            open_turns[identity] = timestamp
        if end and identity in open_turns:
            spans[identity].append([open_turns.pop(identity), timestamp])
        if end:
            terminal.add(identity)
    for identity, agent in agents.items():
        observed = sorted(points[identity])
        agent['points'] = observed
        agent['span_basis'] = 'observed root turns' if not agent['child'] else 'estimated child observation span'
        if agent['child']:
            agent['spans'] = [[observed[0], observed[-1]]] if len(observed) > 1 else []
            agent['missing_terminal'] = identity in open_turns or (bool(observed) and identity not in terminal)
        else:
            agent['spans'] = spans[identity]
            if identity in open_turns:
                agent['missing_terminal'] = True
                if observed:
                    agent['spans'].append([open_turns[identity], observed[-1]])
    return list(agents.values())


def merge_spans(spans):
    result = []
    for start, end in sorted(set(map(tuple, spans))):
        if start >= end:
            continue
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def overlap(spans):
    events = sorted((t, delta) for intervals in spans.values() for a, b in merge_spans(intervals) for t, delta in ((a, 1), (b, -1)))
    active = peak = 0
    for _, change in events:
        active += change
        peak = max(peak, active)
    return peak


def density(points, window, start=None, end=None):
    """Peak distinct identities in (t-window,t], evaluated at response observations."""
    values = sorted((instant(t).timestamp(), identity) for identity, times in points.items() for t in set(times))
    return response_density(values, window, start, end)


def response_density(values, window, start=None, end=None):
    counts, left, peak = defaultdict(int), 0, 0
    for right, (time, identity) in enumerate(values):
        counts[identity] += 1
        while left <= right and values[left][0] <= time - window:
            old = values[left][1]
            counts[old] -= 1
            if not counts[old]:
                del counts[old]
            left += 1
        if (start is None or time >= start) and (end is None or time < end):
            peak = max(peak, len(counts))
    return peak


def selected_events(db, filters, zone, cutoff):
    topics = {(p, s): project for p, s, project in db.execute('SELECT provider,session,project FROM session_topics')}
    result = {}
    for row in db.execute('SELECT e.*,r.role FROM events e LEFT JOIN event_roles r USING(id)'):
        key, timestamp, provider, account, session, model, sub, inp, cache, write, out, reasoning, role = row
        try:
            time = instant(timestamp)
        except (ValueError, TypeError, AttributeError):
            continue
        day = time.astimezone(zone).date().isoformat()
        role = 'other' if model == 'codex-auto-review' else role or ('subagent' if sub else 'main')
        project = topics.get((provider, session), 'Unassigned')
        if time > cutoff or not filters.get('start', '0001-01-01') <= day <= filters.get('end', '9999-12-31'):
            continue
        if any(filters.get(k) and filters[k] != value for k, value in (('provider', provider), ('model', model), ('role', role))):
            continue
        if filters.get('projects') and project not in filters['projects']:
            continue
        result[key] = dict(id=key, date=day, provider=provider, session=session, role=role, child=bool(sub), project=project,
                           counters=dict(input=inp, cached=cache, cache_write=write, output=out, reasoning=reasoning), total=inp+out)
    return result


def accounting(db, filters, timezone, cutoff=None):
    zone, cutoff = ZoneInfo(timezone), instant(cutoff) if cutoff else dt.datetime.now(UTC)
    events = selected_events(db, filters, zone, cutoff)
    activity_events = selected_events(db, {k:v for k,v in filters.items() if k not in ('start','end')}, zone, cutoff)
    ledger_ids = {row[0] for row in db.execute('SELECT id FROM events')}
    superseded = {row[0] for row in db.execute('SELECT event_id FROM superseded_legacy')}
    provenance, available = defaultdict(list), {}
    raw_only = {}
    for row in db.execute('SELECT * FROM response_sources'):
        key, source, source_hash, recorded_stamp, parser, observed, counters, known, identity, first, last, granularity = row
        if source not in available:
            try:
                available[source] = stamp(source) == recorded_stamp
            except OSError:
                available[source] = False
        item = dict(counters=json.loads(counters), known=json.loads(known), identity=identity, first=first, last=last,
                    granularity=granularity, available=available[source], source_hash=source_hash, parser=parser, observed_at=observed)
        if key in activity_events:
            provenance[key].append(item)
        elif available[source] and key not in ledger_ids and key not in superseded:
            raw_only.setdefault(key, []).append(item)
    for key in provenance:
        # A copied Claude response may lose its nested child path. Prefer its
        # specific durable child identity over the copied parent/unknown label.
        identities = {p['identity'] for p in provenance[key]}
        specific = {i for i in identities if ':child:' in i and not i.endswith(':child:unknown')}
        if len(specific) == 1:
            for p in provenance[key]:
                p['identity'] = next(iter(specific))
    days = {}
    for key, row in events.items():
        d = days.setdefault(row['date'], dict(total=0, fresh_input=0, cache_read=0, cache_write=0, output=0, raw_verified=0, mismatched=0, ledger_only=0, unknown_counter_records=0, response_records=0, aggregate_records=0))
        c = row['counters']
        d['total'] += row['total']; d['cache_read'] += c['cached']; d['cache_write'] += c['cache_write']; d['output'] += c['output']
        fresh = c['input'] - c['cached'] - c['cache_write']
        d['fresh_input'] = None if fresh < 0 or d['fresh_input'] is None else d['fresh_input'] + fresh
        sources = [p for p in provenance[key] if p['available']]
        complete = [p for p in sources if all(p['known'].get(k) for k in ('input', 'output', 'cached', 'cache_write'))]
        maxima = {k: max((p['counters'][k] for p in complete), default=0) for k in c}
        if complete and all(maxima[k] == c[k] for k in ('input', 'output', 'cached', 'cache_write')):
            d['raw_verified'] += row['total']
        elif complete:
            d['mismatched'] += row['total']
        else:
            d['ledger_only'] += row['total']
        if not sources or not all(any(p['known'].get(k) for p in sources) for k in ('input', 'output', 'cached', 'cache_write')):
            d['unknown_counter_records'] += 1
        aggregate = key.startswith('Codex:snipe:')
        d['aggregate_records' if aggregate else 'response_records'] += 1
    for d in days.values():
        d['cache_read_share'] = d['cache_read']/d['total'] if d['total'] else None
        d['raw_reconciliation_coverage'] = d['raw_verified']/d['total'] if d['total'] else None
    raw_only_tokens = sum(max(p['counters']['input'] for p in items)+max(p['counters']['output'] for p in items) for items in raw_only.values())
    return dict(days=days, raw_only_records=len(raw_only), raw_only_tokens=raw_only_tokens, raw_only_scope='All reconciled sources; excluded from ledger totals until sync. Unknown counters make raw-only totals lower bounds.',
                parser_version=PARSER_VERSION, cutoff=cutoff.isoformat(),
                limitations=['Coverage is relative to retained local evidence, not every account or device.',
                             'Missing counters remain unknown; existing ledger normalization may contain zero placeholders.',
                             'Legacy deltas lack response IDs. Completed-turn aggregates have no per-response timing.',
                             'Accounting uses the earliest observed event; later fragments establish activity only.']), activity_events, provenance


def activity(db, filters, timezone, events, provenance, cutoff):
    zone, cutoff = ZoneInfo(timezone), instant(cutoff)
    agents = {}
    topics = {(p, s): project for p, s, project in db.execute('SELECT provider,session,project FROM session_topics')}
    for source, recorded_stamp, observed, body in db.execute('SELECT * FROM activity_sources'):
        for a in json.loads(body):
            if filters.get('provider') and filters['provider'] != a['provider']:
                continue
            if filters.get('projects') and topics.get((a['provider'], a['session']), 'Unassigned') not in filters['projects']:
                continue
            target = agents.setdefault(a['id'], dict(a, points=set(), spans=[], responses=[]))
            merge_identity(target, a)
            target['points'].update(a['points']); target['spans'].extend(a['spans'])
            target['responses'].extend(a.get('responses', []))
            target['missing_terminal'] |= a['missing_terminal']
            target['request_observed'] |= a.get('request_observed', False)
    positive, responding = defaultdict(set), defaultdict(set)
    selected_identities = set()
    response_identity = {}
    for key, row in events.items():
        for p in provenance[key]:
            identity = p['identity']
            agents.setdefault(identity, dict(id=identity, provider=row['provider'], session=row['session'], parent=identity.split(':child:')[0] if ':child:' in identity else None, child=row['child'], missing_terminal=True, identity_uncertain=identity.endswith(':child:unknown'), points={p['first'],p['last']}, spans=[], responses=[], request_observed=False, span_basis='response observations; lifecycle unavailable'))
            selected_identities.add(identity)
            if row['total'] > 0 and filters.get('start','0001-01-01') <= row['date'] <= filters.get('end','9999-12-31'):
                positive[row['date']].add(identity)
            if p['granularity'] == 'response':
                response_identity[key] = identity
                responding[identity].update([p['first'], p['last']])
            if p['granularity'] == 'completed_turn':
                agents[identity]['span_basis'] = 'aggregate; timing unavailable'
    for identity, a in list(agents.items()):
        for key, timestamp in a['responses']:
            if key in response_identity:
                responding[response_identity[key]].add(timestamp)
        if a['responses'] and not a['request_observed'] and all(key in response_identity and response_identity[key]!=identity for key,t in a['responses']):
            del agents[identity]
    responding = {identity: {instant(t) for t in times} for identity, times in responding.items()}
    if filters.get('model') or filters.get('role'):
        selected_identities = set().union(*positive.values()) if positive else set()
        for identity,times in responding.items():
            if any(filters.get('start','0001-01-01') <= t.astimezone(zone).date().isoformat() <= filters.get('end','9999-12-31') for t in times):
                selected_identities.add(identity)
        agents = {k: a for k, a in agents.items() if k in selected_identities}
    days = {}
    day_spans = defaultdict(lambda: defaultdict(list))
    day_responses = defaultdict(list)
    first_date = dt.date.fromisoformat(filters.get('start', '0001-01-01'))
    last_date = dt.date.fromisoformat(filters.get('end', '9999-12-31'))
    for identity, times in responding.items():
        for time in times:
            if time >= cutoff:
                continue
            date = time.astimezone(zone).date()
            if first_date <= date <= last_date:
                day_responses[date.isoformat()].append((time.timestamp(), identity))
            if date < last_date and date < dt.date.max:
                following = date + dt.timedelta(days=1)
                midnight = dt.datetime.combine(following, dt.time(), zone).astimezone(UTC)
                if following >= first_date and time > midnight - dt.timedelta(seconds=600):
                    day_responses[following.isoformat()].append((time.timestamp(), identity))
    for identity, a in agents.items():
        for t in a['points']:
            time = instant(t)
            if time > cutoff:
                continue
            day = time.astimezone(zone).date().isoformat()
            if first_date.isoformat() <= day <= last_date.isoformat():
                days.setdefault(day, set()).add(identity)
        for begin, finish in a['spans']:
            left = max(instant(begin), dt.datetime.combine(first_date, dt.time(), zone).astimezone(UTC)) if first_date > dt.date.min else instant(begin)
            right = min(instant(finish), cutoff)
            date = left.astimezone(zone).date()
            while left < right and date <= last_date:
                day = date.isoformat()
                next_date = date + dt.timedelta(days=1)
                midnight = dt.datetime.combine(next_date, dt.time(), zone).astimezone(UTC)
                clipped_end = min(midnight, right)
                days.setdefault(day, set()).add(identity)
                day_spans[day][identity].append([left.isoformat(), clipped_end.isoformat()])
                left, date = midnight, next_date
    for day, identities in positive.items():
        days.setdefault(day, set()).update(identities)
    result = {}
    for day, identities in sorted(days.items()):
        start = dt.datetime.combine(dt.date.fromisoformat(day), dt.time(), zone).astimezone(UTC)
        end = min(dt.datetime.combine(dt.date.fromisoformat(day)+dt.timedelta(days=1), dt.time(), zone).astimezone(UTC), cutoff)
        bounds = day_spans[day]
        values = sorted(day_responses[day])
        has_response = any(start.timestamp() <= time < end.timestamp() for time, identity in values)
        positive_ids = positive[day]
        result[day] = dict(roots=sum(not agents.get(i, {}).get('child', i.startswith('Codex:snipe:')) for i in identities if i in agents),
                           children=sum(agents.get(i, {}).get('child', False) for i in identities),
                           inclusive_identities=len(identities), positive_accounting_identities=len(positive_ids),
                           zero_or_synthetic_only=len(identities-positive_ids),
                           task_span_peak=overlap(bounds) if bounds else None,
                           positive_task_span_peak=overlap({k:v for k,v in bounds.items() if k in positive_ids}) if any(k in positive_ids for k in bounds) else None,
                           responding_density={str(w): response_density(values, w, start.timestamp(), end.timestamp()) if has_response else None for w in (60, 300, 600)},
                           missing_terminal_markers=sum(agents.get(i, {}).get('missing_terminal', False) for i in identities),
                           positive_identity_ids=sorted(positive_ids),
                           identities=[{k:v for k,v in agents[i].items() if k not in ('points', 'spans', 'responses', 'request_observed')} for i in sorted(identities) if i in agents])
    return dict(days=result, evidence_available=bool(agents), limitations=[
        'Task-span overlap and responding-identity density are not simultaneous API-call concurrency.',
        'Child first-to-last spans and roots missing terminal markers are bounded estimates.',
        'Retained metadata survives log deletion; incomplete retention can miss agents and turns.',
        'Unknown Claude child identities are grouped and explicitly marked uncertain.',
        'Model/role selections include identities with matching accounting or response observations; spans describe their observed tasks.',
        'Aggregate reviewer timestamps are excluded from spans and response density.'])
