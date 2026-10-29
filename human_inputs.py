"""Compact human-input provenance, separate from token accounting and agent spans."""
from bisect import bisect_left
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from evidence import digest, instant, now, stamp

CLASSIFIER_VERSION = 'human-inputs-v2'
UTC = dt.timezone.utc
UI_TRIGGERS = {'composer', 'edit_user_message', 'send_user_message_async_question'}
AUTOMATED_TRIGGERS = {'goal', 'queue', 'guardian_review', 'automation_heartbeat_scheduled', 'automation', 'scheduled'}


def init(db):
    db.execute('''CREATE TABLE IF NOT EXISTS human_input_sources (
        source TEXT PRIMARY KEY, provider TEXT, stamp TEXT, source_hash TEXT,
        observed_at TEXT, classifier_version TEXT, body TEXT)''')
    db.execute('CREATE TABLE IF NOT EXISTS human_input_aliases (alias TEXT PRIMARY KEY, identity TEXT NOT NULL)')
    db.execute('CREATE INDEX IF NOT EXISTS human_input_aliases_identity ON human_input_aliases(identity)')


def remember_identities(db, events):
    """A richer representation may add aliases, but cannot rename an observed input."""
    for event in deduplicate(events):
        linked = set()
        for alias in event['aliases']:
            row = db.execute('SELECT identity FROM human_input_aliases WHERE alias=?', (alias,)).fetchone()
            if row:
                linked.add(row[0])
        identity = min(linked, key=lambda key: db.execute(
            'SELECT rowid FROM human_input_aliases WHERE identity=? ORDER BY rowid LIMIT 1', (key,)).fetchone()[0]) if linked else event['id']
        for old in linked - {identity}:
            db.execute('UPDATE human_input_aliases SET identity=? WHERE identity=?', (identity, old))
        for alias in event['aliases']:
            db.execute('INSERT OR IGNORE INTO human_input_aliases VALUES (?,?)', (alias, identity))


def mapping(value):
    return value if isinstance(value, dict) else {}


def passthrough(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return mapping(value)


def input_time(row, metadata):
    original = metadata.get('create_time')
    if isinstance(original,str):
        return instant(original).isoformat(), 'input_create_time', original
    if isinstance(original, (int, float)) and not isinstance(original, bool) and math.isfinite(original):
        timestamp = dt.datetime.fromtimestamp(original, UTC).isoformat()
        return timestamp, 'input_create_time', timestamp
    if original is not None:
        raise ValueError('Input original timestamp is invalid')
    for key in ('original_timestamp', 'originalTimestamp', 'timestamp'):
        if row.get(key):
            return instant(row[key]).isoformat(), 'original_timestamp' if key != 'timestamp' else 'source_record_timestamp', row[key]
    raise ValueError('Input has no timestamp')


def collect(path, provider, rows):
    """Inspect bodies transiently; return identifiers, times and controlled labels only."""
    events, turns, questions, representations = [], {}, set(), []
    owner, mapping_session, owner_known, child = Path(path).stem, Path(path).stem, False, 'subagents' in Path(path).parts
    active_turn, current_owner, history_start, session_source = {}, None, None, None
    seen_session_metadata = False
    recognized, invalid = False, 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        payload, message, metadata = mapping(row.get('payload')), mapping(row.get('message')), mapping(row.get('metadata'))
        kind = row.get('type')
        if provider == 'Codex':
            if kind == 'session_meta':
                recognized = True
                current_owner = payload.get('id') if isinstance(payload.get('id'), str) and payload['id'].strip() else None
                if not seen_session_metadata:
                    seen_session_metadata = True
                    if current_owner:
                        owner = mapping_session = current_owner
                        owner_known = True
                    session_source = payload.get('source')
                    child = isinstance(session_source, dict) and 'subagent' in session_source
                    history_start = payload.get('subagent_history_start_ordinal')
                continue
            if kind == 'event_msg' and payload.get('type') == 'task_started':
                recognized = True
                active_turn = dict(mapping(payload.get('turn_attribution')))
                turn_id = active_turn.get('turn_id') or payload.get('turn_id')
                if isinstance(turn_id, str) and turn_id:
                    active_turn['turn_id'] = turn_id
                    turns[turn_id] = active_turn
                continue
            candidate = (kind == 'response_item' and payload.get('role') == 'user') or (kind == 'event_msg' and payload.get('type') == 'user_message')
            if not candidate:
                continue
            recognized = True
            details = passthrough(payload.get('internal_chat_message_metadata_passthrough'))
            input_turn = details.get('turn_id') or payload.get('turn_id')
            attribution = turns.get(input_turn, {}) if isinstance(input_turn, str) and input_turn else active_turn
            raw_trigger = attribution.get('turn_trigger')
            trigger = raw_trigger if isinstance(raw_trigger,str) or raw_trigger is None else 'unsupported'
            items = details.get('content_item_metadata')
            provenance = [mapping(item.get('provenance')).get('type') for item in items if isinstance(item, dict)] if isinstance(items, list) else []
            original_id = mapping(mapping(metadata.get('retained_source')).get('id')).get('message_id')
            aliases = [v for v in (original_id, payload.get('message_id'), payload.get('id')) if isinstance(v, str) and v]
            inherited = bool(metadata.get('inherited_user_message'))
            if isinstance(history_start, int) and isinstance(row.get('ordinal'), int):
                inherited |= row['ordinal'] < history_start
            elif owner_known and current_owner and current_owner != owner:
                inherited = True
            classification, reason = 'ambiguous', 'User-shaped input lacks verified human-origin metadata'
            if inherited:
                classification, reason = 'excluded', 'Inherited or copied context'
            elif isinstance(session_source, str) and session_source in ('exec', 'sdk', 'api'):
                classification, reason = 'excluded', 'Programmatic session origin'
            elif attribution.get('initiating_agent_path') or trigger in AUTOMATED_TRIGGERS or (isinstance(trigger, str) and trigger.startswith('automation_')):
                classification, reason = 'excluded', 'Agent-directed or automated turn'
            elif provenance and all(isinstance(p,str) and p in ('harness','agents_md','skills','system','developer','context') for p in provenance):
                classification, reason = 'excluded', 'Harness, skill or injected context'
            elif 'user' in provenance and owner_known and (trigger in UI_TRIGGERS or (trigger is None and not child)):
                classification, reason = 'supported_human', 'Explicit user-item provenance with human UI origin'
            elif child:
                classification, reason = 'excluded', 'Agent-directed child input without human-origin evidence'
        elif provider == 'Claude Code':
            if kind in ('user', 'assistant'):
                recognized = True
            if not owner_known and isinstance(row.get('sessionId'),str) and row['sessionId'].strip():
                mapping_session = row['sessionId']
                child |= bool(row.get('isSidechain') or row.get('agentId'))
                agent = row.get('agentId') if isinstance(row.get('agentId'),str) and row['agentId'] else (Path(path).stem.removeprefix('agent-') if child else None)
                owner = mapping_session + ':child:' + agent if child and agent else mapping_session
                owner_known = True
                session_source = row.get('entrypoint')
            if session_source is None and row.get('sessionId') == mapping_session and isinstance(row.get('entrypoint'),str):
                session_source = row['entrypoint']
            content = message.get('content')
            blocks = content if isinstance(content, list) else []
            if kind == 'assistant':
                for block in blocks:
                    if isinstance(block, dict) and block.get('type') == 'tool_use' and block.get('name') == 'AskUserQuestion' and isinstance(block.get('id'),str) and block['id']:
                        questions.add(block['id'])
                continue
            if kind != 'user':
                continue
            details = {}
            aliases = [v for v in (row.get('uuid'), message.get('id')) if isinstance(v, str) and v]
            origin = mapping(row.get('origin')).get('kind') or row.get('turnOrigin')
            inherited = bool(row.get('isCompactSummary') or row.get('inherited') or row.get('isReplay'))
            inherited |= bool(owner_known and row.get('sessionId') and row['sessionId'] != mapping_session)
            inherited |= bool(child and row.get('isSidechain') is False and not row.get('agentId'))
            tool_results = [b for b in blocks if isinstance(b, dict) and b.get('type') == 'tool_result']
            result = mapping(row.get('toolUseResult'))
            answered = any(isinstance(b.get('tool_use_id'),str) and b['tool_use_id'] in questions for b in tool_results) and isinstance(result.get('answers'), dict) and any(isinstance(v,str) and bool(v.strip()) for v in result['answers'].values())
            classification, reason = 'ambiguous', 'User-shaped input lacks verified human-origin metadata'
            if inherited:
                classification, reason = 'excluded', 'Inherited or copied context'
            elif row.get('isMeta') or row.get('isVisibleInTranscriptOnly') or row.get('turnCompanion'):
                classification, reason = 'excluded', 'Meta expansion or transcript-only context'
            elif any(str(value or '').lower() in ('sdk', 'sdk-cli', 'api', 'programmatic') for value in (session_source,row.get('entrypoint'))):
                classification, reason = 'excluded', 'Programmatic session origin'
            elif origin and origin != 'human':
                classification, reason = 'excluded', 'Agent, notification or automated origin'
            elif answered and owner_known:
                classification, reason = 'supported_human', 'Submitted answer to a recorded AskUserQuestion input'
            elif tool_results or row.get('sourceToolAssistantUUID') or row.get('toolUseResult'):
                classification, reason = 'excluded', 'Tool result, not a human input'
            elif origin == 'human' and owner_known:
                classification, reason = 'supported_human', 'Explicit human origin on input record'
            elif child:
                classification, reason = 'excluded', 'Agent-directed child input without human-origin evidence'
        else:
            continue
        try:
            timestamp, basis, original_timestamp = input_time(row, details)
        except (ValueError, TypeError, AttributeError, OverflowError, OSError):
            invalid += 1
            continue
        no_message_id = not aliases
        identity_basis = 'source_position' if no_message_id else 'retained_message_id' if provider == 'Codex' and isinstance(original_id,str) and original_id else 'provider_message_id'
        if no_message_id:
            key = hashlib.sha256(json.dumps([owner, timestamp, row.get('ordinal', index)], separators=(',', ':')).encode()).hexdigest()
            aliases = ['observed:' + key]
        events.append(dict(id=provider + ':' + aliases[0], aliases=[provider + ':' + a for a in aliases], provider=provider,
                           session=owner, mapping_session=mapping_session, timestamp=timestamp, timestamp_basis=basis, original_timestamp=original_timestamp,
                           classification=classification, reason=reason, inherited=inherited, identity_basis=identity_basis))
        if provider == 'Codex':
            turn = input_turn if isinstance(input_turn,str) and input_turn else active_turn.get('turn_id')
            content = payload.get('content')
            text = payload.get('message') if kind == 'event_msg' else None
            if kind == 'response_item' and isinstance(content,list):
                text = '\n'.join(c['text'] for c in content if isinstance(c,dict) and isinstance(c.get('text'),str) and c.get('type') in ('input_text','text'))
            if isinstance(turn,str) and turn and isinstance(text,str) and text:
                # Pair the two native representations within their recorded turn, never independent replies by text alone.
                fingerprint = hashlib.sha256(text.encode()).hexdigest()
                representations.append((owner, turn, fingerprint, kind, no_message_id, index, events[-1]))
    responses = {}
    for owner, turn, fingerprint, kind, no_id, index, event in representations:
        if kind == 'response_item':
            positions, candidates = responses.setdefault((owner, turn, fingerprint), ([], []))
            positions.append(index)
            candidates.append(event)
    for owner, turn, fingerprint, kind, no_id, index, event in representations:
        if kind != 'event_msg' or not no_id:
            continue
        positions, candidates = responses.get((owner, turn, fingerprint), ([], []))
        if positions:
            insertion = bisect_left(positions, index)
            nearest = min((i for i in (insertion-1, insertion) if 0 <= i < len(positions)),
                          key=lambda i: (abs(positions[i]-index), positions[i]))
            event['aliases'].extend(candidates[nearest]['aliases'])
    return dict(events=events, schema_supported=recognized, invalid_timestamp_records=invalid)


def save(db, path, provider, rows, source_stamp=None):
    path = Path(path)
    expected = source_stamp or stamp(path)
    body = collect(path, provider, rows)
    source_hash = digest(path)
    if stamp(path) != expected:
        raise ValueError('Human-input history changed while reading; retry sync')
    if not db.execute('SELECT 1 FROM human_input_aliases LIMIT 1').fetchone():
        retained = [event for (body,) in db.execute('SELECT body FROM human_input_sources')
                    for event in json.loads(body)['events']]
        remember_identities(db, retained)
    remember_identities(db, body['events'])
    db.execute('INSERT OR REPLACE INTO human_input_sources VALUES (?,?,?,?,?,?,?)',
               (str(path), provider, expected, source_hash, now(), CLASSIFIER_VERSION, json.dumps(body, sort_keys=True)))


def deduplicate(events):
    groups, aliases = {}, {}
    for event in events:
        linked = {aliases[a] for a in event['aliases'] if a in aliases}
        key = min(linked) if linked else event['id']
        group = groups.setdefault(key, [])
        for other in linked - {key}:
            group.extend(groups.pop(other))
            for alias, existing in list(aliases.items()):
                if existing == other:
                    aliases[alias] = key
        group.append(event)
        for alias in event['aliases']:
            aliases[alias] = key
    result = []
    for group in groups.values():
        originals = [e for e in group if not e['inherited']]
        candidates = originals or group
        original_times = [e for e in candidates if e['timestamp_basis'] != 'source_record_timestamp' or e['provider'] == 'Claude Code']
        chosen = dict(min(original_times or candidates, key=lambda e:(e['timestamp'],e['session'],e['id'])))
        identity_priority = {'retained_message_id':0, 'provider_message_id':1, 'source_position':2}
        identity = min(candidates,key=lambda e:(identity_priority.get(e.get('identity_basis'),1),e['id']))
        chosen['id'] = identity.get('stable_id', identity['id'])
        chosen['aliases'] = sorted({alias for event in group for alias in event['aliases']})
        classes = {e['classification'] for e in candidates}
        owners = {e['session'] for e in candidates}
        time_conflict = bool(originals) and len({e['timestamp'] for e in original_times}) > 1
        origin_conflict = bool(originals) and (len(owners) > 1 or ('excluded' in classes and len(classes) > 1))
        chosen['provenance_conflict'] = time_conflict or origin_conflict
        if origin_conflict:
            chosen.update(classification='ambiguous', reason='Conflicting original input provenance', mapping_session=None)
        elif time_conflict:
            chosen.update(classification='ambiguous', reason='Conflicting original input timestamps')
        elif 'supported_human' in classes:
            supported = next(e for e in candidates if e['classification']=='supported_human')
            chosen.update(classification='supported_human', reason=supported['reason'])
            for key in ('classifier_version','source_classification'):
                if key in supported:
                    chosen[key] = supported[key]
        chosen['source_statuses'] = sorted({e['source_status'] for e in group if 'source_status' in e})
        result.append(chosen)
    return result


def inventory(db, sources=None):
    """All retained inputs, including those outside a current report or cutoff."""
    coverage = dict(scope='All retained input sources and events', complete=False, retained_sources=0,
                    current_sources=0, missing_sources=0, changed_sources=0, unsupported_sources=0,
                    invalid_timestamp_records=0, selected_events=0, supported_human=0, ambiguous=0, excluded=0,
                    carry_in_events=0, unmapped_events=0, outside_project_events=0, configured_roots=len(sources or []),
                    missing_roots=sum(not Path(s['path']).expanduser().exists() for s in sources or []),
                    boundary_context='unavailable', boundary_context_complete=False)
    identities = dict(db.execute('SELECT alias,identity FROM human_input_aliases'))
    identity_aliases = {}
    for alias, identity in identities.items():
        identity_aliases.setdefault(identity, []).append(alias)
    collected = []
    for source, expected, version, body_text in db.execute('SELECT source,stamp,classifier_version,body FROM human_input_sources'):
        body = json.loads(body_text)
        coverage['retained_sources'] += 1
        coverage['invalid_timestamp_records'] += body['invalid_timestamp_records']
        unsupported = not body['schema_supported'] or version != CLASSIFIER_VERSION
        coverage['unsupported_sources'] += unsupported
        try:
            current = stamp(source) == expected
            coverage['current_sources' if current else 'changed_sources'] += 1
            source_status = 'current' if current else 'changed'
        except OSError:
            coverage['missing_sources'] += 1
            source_status = 'missing'
        for event in body['events']:
            event.update(classifier_version=version, source_classification=event['classification'], source_status=source_status)
            if version != CLASSIFIER_VERSION and event['classification'] == 'supported_human':
                event.update(classification='ambiguous', reason='Retained input uses an older classifier version')
            stable_id = next((identities[alias] for alias in event['aliases'] if alias in identities), event['id'])
            event.update(stable_id=stable_id, aliases=sorted(set(event['aliases']) | set(identity_aliases.get(stable_id, []))))
            collected.append(event)
    topics = {(p,s):project for p,s,project in db.execute('SELECT provider,session,project FROM session_topics')}
    events = []
    for event in deduplicate(collected):
        project = topics.get((event['provider'],event['mapping_session'])) or None
        public = {k:event[k] for k in ('id','aliases','provider','session','timestamp','timestamp_basis','classification','reason','classifier_version','source_classification','source_statuses','provenance_conflict')}
        public.update(project=project, original_timestamp=event.get('original_timestamp'))
        events.append(public)
        coverage['selected_events'] += 1
        coverage[event['classification']] += 1
        coverage['unmapped_events'] += project is None and event['classification'] != 'excluded'
    if coverage['retained_sources']:
        coverage['boundary_context'] = 'retained_only'
    limitations = [
        'Human-input evidence covers retained local histories only; matched dates do not establish complete human-time coverage.',
        'Legacy user roles and root sessions alone are ambiguous; ambiguous-inclusive inputs may include automation and are not a time upper bound.',
        'Up to ten minutes of preceding retained inputs are included for boundary tails; unavailable earlier or deleted history cannot be reconstructed.',
        'Provider, model and role token filters do not narrow human-input time. Project mapping uses the original physical session owner.',
        'Source hashes and original input metadata are retained locally; prompt, tool and assistant bodies are not stored in this index.'
    ]
    if coverage['missing_sources'] or coverage['missing_roots']:
        limitations.append('Some source files or configured roots are unavailable; previously indexed input metadata remains retained.')
    if coverage['changed_sources']:
        limitations.append('Some source files changed since indexing; sync is required to include their latest human inputs.')
    if coverage['unsupported_sources'] or coverage['invalid_timestamp_records']:
        limitations.append('Unsupported schemas or invalid timestamps leave human-input evidence incomplete.')
    if not coverage['retained_sources']:
        limitations.append('No human-input sources have been indexed; sync local histories to collect supported input metadata.')
    return dict(events=sorted(events,key=lambda e:(e['timestamp'],e['id'])),
                classifier_version=CLASSIFIER_VERSION, coverage=coverage, limitations=limitations)


def select(db, filters, timezone, cutoff, sources=None, retained=None):
    retained = inventory(db, sources) if retained is None else retained
    zone, upper = ZoneInfo(timezone), instant(cutoff)
    lower = dt.datetime.combine(dt.date.fromisoformat(filters['start']), dt.time(), zone).astimezone(UTC) if filters.get('start') else dt.datetime.min.replace(tzinfo=UTC)
    if filters.get('end'):
        day_after = dt.date.fromisoformat(filters['end']) + dt.timedelta(days=1)
        upper = min(upper, dt.datetime.combine(day_after, dt.time(), zone).astimezone(UTC))
    lookback = lower - dt.timedelta(minutes=10) if lower.year > 1 else lower
    coverage = dict(retained['coverage'], scope='All retained input sources; event counts follow date/project selection',
                    selected_events=0,supported_human=0,ambiguous=0,excluded=0,carry_in_events=0,unmapped_events=0,outside_project_events=0)
    selected, unmatched = [], []
    projects = set(filters.get('projects') or [])
    for event in retained['events']:
        timestamp = instant(event['timestamp'])
        if not lookback <= timestamp < upper:
            continue
        in_window = timestamp >= lower
        item = dict(event, in_reporting_window=in_window)
        project = event['project']
        if in_window and event['classification'] != 'excluded':
            coverage['unmapped_events'] += project is None
            coverage['outside_project_events'] += bool(projects and project is not None and project not in projects)
        if projects and project not in projects:
            unmatched.append(item)
            continue
        selected.append(item)
        coverage['selected_events'] += 1
        coverage[event['classification']] += 1
        coverage['carry_in_events'] += not in_window
    return dict(retained, events=selected, unmatched_events=unmatched, coverage=coverage)
