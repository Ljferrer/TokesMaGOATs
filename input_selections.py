"""Versioned ambiguous-input decisions, independent of source classification."""
import hashlib
import json
import re
import sqlite3

from evidence import instant, now


class SelectionConflict(ValueError):
    pass


def init(db):
    db.execute('''CREATE TABLE IF NOT EXISTS human_input_selections (
        version INTEGER PRIMARY KEY, updated_at TEXT, body TEXT)''')


def get(db, version=None):
    require(version is None or type(version) is int and version >= 0, 'Input selection version must be a nonnegative integer')
    if version == 0:
        return dict(schema_version=1, version=0, updated_at=None, entries=[])
    row = db.execute('SELECT version,updated_at,body FROM human_input_selections ORDER BY version DESC LIMIT 1').fetchone() if version is None else db.execute(
        'SELECT version,updated_at,body FROM human_input_selections WHERE version=?', (version,)).fetchone()
    if not row:
        require(version is None, 'Input selection version is not available')
        return dict(schema_version=1, version=0, updated_at=None, entries=[])
    return dict(schema_version=1, version=row[0], updated_at=row[1], entries=json.loads(row[2]))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identifier(value):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= 2048
            and not any(ord(char) < 32 for char in value), 'Input IDs must be nonempty strings without control characters')
    return value


def reference(event, classifier_version):
    """Bind the original input, not the changing source file or project label."""
    fields = {key:event[key] for key in ('id','provider','session','timestamp_basis','classification','reason')}
    fields['timestamp'] = instant(event['timestamp']).isoformat()
    fields['classifier_version'] = classifier_version
    fields['source_classifier_version'] = event.get('classifier_version', classifier_version)
    fields['source_classification'] = event.get('source_classification', event['classification'])
    fields['original_timestamp'] = instant(event.get('original_timestamp') or event['timestamp']).isoformat()
    fingerprint = hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return dict(fingerprint=fingerprint, classifier_version=classifier_version)


def known_inputs(events, classifier_version):
    result = {}
    for event in events:
        for key in set(event.get('aliases', [])) | {event.get('id')}:
            if not isinstance(key, str) or not key:
                continue
            try:
                item = None if event.get('provenance_conflict') else dict(
                    classification=event['classification'], id=event['id'],
                    reference=reference(dict(event, id=key), classifier_version))
            except (ValueError, TypeError, KeyError, AttributeError):
                item = None
            if key in result and result[key] != item:
                result[key] = None
            elif key not in result:
                result[key] = item
    return result


def imported_reference(value):
    require(isinstance(value, dict) and set(value) == {'fingerprint','classifier_version'}, 'Input references require fingerprint and classifier_version')
    fingerprint, classifier = value['fingerprint'], value['classifier_version']
    require(isinstance(fingerprint, str) and re.fullmatch(r'[0-9a-f]{64}', fingerprint) is not None, 'Invalid input reference fingerprint')
    require(isinstance(classifier, str) and bool(classifier.strip()) and len(classifier) <= 128, 'Invalid input reference classifier version')
    return dict(fingerprint=fingerprint, classifier_version=classifier)


def save(db, document, known_events, classifier_version):
    require(isinstance(document, dict) and {'base_version','entries'} <= set(document)
            and set(document) <= {'schema_version','base_version','entries'}, 'Input selection requires base_version and entries')
    require(type(document.get('schema_version', 1)) is int and document.get('schema_version', 1) == 1, 'Unsupported input selection schema version')
    require(type(document['base_version']) is int and document['base_version'] >= 0, 'Input selection base_version must be a nonnegative integer')
    require(isinstance(document['entries'], list), 'Input selection entries must be an array')
    current = get(db)
    if document['base_version'] != current['version']:
        raise SelectionConflict('Input selection changed in another request; reload the current selection before saving')
    existing = {entry['id']:entry for entry in current['entries']}
    known = known_inputs(known_events, classifier_version)
    selected = {}
    for value in document['entries']:
        require(isinstance(value, dict) and 'id' in value and set(value) <= {'id','reference','rationale'}, 'Each input selection requires id and optional reference/rationale')
        key = identifier(value['id'])
        rationale = value.get('rationale', '')
        require(isinstance(rationale, str) and len(rationale) <= 2000, 'Input rationale must be text of at most 2000 characters')
        if 'reference' in value:
            bound = imported_reference(value['reference'])
        elif key in existing:
            bound = existing[key]['reference']
        else:
            candidate = known.get(key)
            require(candidate is not None and candidate['classification'] == 'ambiguous',
                    'Cannot select unresolved, supported, or excluded input: ' + key)
            bound = candidate['reference']
        entry = dict(id=key, reference=bound)
        if rationale:
            entry['rationale'] = rationale
        require(key not in selected or selected[key] == entry, 'Conflicting duplicate selection for input: ' + key)
        selected[key] = entry
    entries = [selected[key] for key in sorted(selected)]
    if entries == current['entries']:
        return current
    version, updated = current['version'] + 1, now()
    try:
        db.execute('INSERT INTO human_input_selections VALUES (?,?,?)',
                   (version, updated, json.dumps(entries, sort_keys=True, separators=(',', ':'), allow_nan=False)))
    except sqlite3.IntegrityError as error:
        raise SelectionConflict('Input selection changed in another request; reload the current selection before saving') from error
    return dict(schema_version=1, version=version, updated_at=updated, entries=entries)


def resolve(db, known_events, classifier_version, version=None):
    current = get(db, version)
    known = known_inputs(known_events, classifier_version)
    result = dict(version=current['version'], ids=[entry['id'] for entry in current['entries']],
                  valid_ids=[], missing_ids=[], changed_ids=[], invalid_ids=[],
                  resolved_ids={}, classification='ambiguous', warnings=[])
    for entry in current['entries']:
        key = entry['id']
        if key not in known:
            category = 'missing_ids'
        elif known[key] is None or known[key]['classification'] != 'ambiguous':
            category = 'invalid_ids'
        elif entry['reference'] != known[key]['reference']:
            category = 'changed_ids'
        else:
            category = 'valid_ids'
            result['resolved_ids'][key] = known[key]['id']
        result[category].append(key)
    result.update(selected_count=len(result['ids']), valid_count=len(result['valid_ids']))
    reasons = {'missing_ids':'missing from retained input metadata',
               'changed_ids':'changed original time or provenance',
               'invalid_ids':'no longer ambiguous or have conflicting input evidence'}
    for key, reason in reasons.items():
        if result[key]:
            result['warnings'].append(f'{len(result[key])} selected input(s) {reason}; excluded from the selected-population timer until reviewed.')
    return result
