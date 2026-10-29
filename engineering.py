"""Local Git snapshots, versioned manual assessments, and delivered-scope scenarios."""
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit

from evidence import instant, now, UTC, accounting, activity

SCENARIOS = ('low', 'central', 'high')
DIMENSIONS = ('correctness', 'regression_protection', 'maintainability', 'operational_safeguards')
BASELINE = 'Experienced engineer familiar with the codebase, conventional tools without coding agents; incremental design, implementation, debugging, verification, integration and review.'
DISCLAIMER = 'Under the selected conventional-effort assumptions and comparison day; not a measured causal productivity multiplier.'


def init(db):
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='engineering_reports'").fetchone():
        return
    db.executescript('''
    CREATE TABLE IF NOT EXISTS repository_snapshots (id TEXT PRIMARY KEY, repository TEXT, observed_at TEXT, body TEXT);
    CREATE TABLE IF NOT EXISTS engineering_assessments (version INTEGER PRIMARY KEY, imported_at TEXT, body TEXT);
    CREATE TABLE IF NOT EXISTS engineering_reports (id TEXT PRIMARY KEY, cutoff TEXT, body TEXT);
    ''')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def git(path, *args):
    env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS='0', GIT_NO_REPLACE_OBJECTS='1', GIT_TERMINAL_PROMPT='0', GIT_NO_LAZY_FETCH='1')
    try:
        process = subprocess.run(['git', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null', '-C', str(path), *args], env=env, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError('Local Git observation failed') from error
    if process.returncode:
        raise ValueError('Local Git observation failed: ' + process.stderr.decode(errors='replace')[:400])
    if len(process.stdout) > 16 * 1024 * 1024:
        raise ValueError('Git evidence exceeds the bounded snapshot size')
    return process.stdout.decode('utf-8', errors='replace').rstrip('\n')


def canonical_repository(path):
    remote = git(path, 'config', '--local', '--get-regexp', r'^remote\..*\.url$') if git(path, 'remote') else ''
    origin = next((line.split(' ', 1)[1] for line in remote.splitlines() if line.startswith('remote.origin.url ')), '')
    match = re.fullmatch(r'(?:https?://|ssh://(?:[^@/]+@)?|[^@/]+@)([^/:]+)[:/](.+?)(?:\.git)?/?', origin)
    if match:
        host, repo = match.groups()
        return host.lower() + '/' + (repo.lower() if host.lower() == 'github.com' else repo)
    common = git(path, 'rev-parse', '--path-format=absolute', '--git-common-dir')
    return 'local:' + hashlib.sha256(common.encode()).hexdigest()[:24]


def collect_repositories(db, config):
    """Explicit local-only operation. Never fetch, checkout, query a host, or run tests."""
    init(db)
    observed = now()
    seen, snapshots = {}, []
    for entry in config.get('engineering_repositories', []):
        path = Path(entry['path']).expanduser().resolve()
        require(git(path, 'rev-parse', '--is-shallow-repository') == 'false', 'Shallow history cannot establish first integration; use a complete local checkout')
        repository = canonical_repository(path)
        if entry.get('id') and entry['id'] != repository:
            raise ValueError(f'Repository id must match canonical identity {repository}')
        ref = entry.get('default_ref')
        if not isinstance(ref, str) or not ref.startswith(('refs/heads/', 'refs/remotes/')) or any(c in ref for c in ('\n', '\0')):
            raise ValueError('Configure an explicit local default_ref under refs/heads/ or refs/remotes/')
        tip = git(path, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}')
        if repository in seen:
            if seen[repository] != (tip, entry.get('project', path.name)):
                raise ValueError('Duplicated checkouts disagree on tip or project; choose one snapshot')
            continue
        seen[repository] = (tip, entry.get('project', path.name))
        history = git(path, 'rev-list', '--first-parent', '--reverse', tip).splitlines()
        if len(history) > 5000:
            raise ValueError('Default branch exceeds 5000 integrations; bounded collection is incomplete')
        integrations, adopted = [], set()
        personal = {value.casefold() for value in config.get('engineering_personal_emails', [])}
        for head in history:
            fields = git(path, 'show', '-s', '--format=%P%x00%cI%x00%aI%x00%ae%x00%s', head).split('\0')
            parents, timestamp, authored, email, subject = fields
            parents = parents.split()
            base = parents[0] if parents else None
            commits = git(path, 'rev-list', '--reverse', head, *(['^' + base] if base else [])).splitlines()
            details = []
            for commit in commits:
                author_time, author_email, commit_parents = git(path, 'show', '-s', '--format=%aI%x00%ae%x00%P', commit).split('\0')
                files = git(path, 'diff-tree', '--root', '--no-commit-id', '--name-only', '-r', '-m', '-z', commit).split('\0')
                tree_files = git(path, 'ls-tree', '-r', '--name-only', '-z', commit).split('\0')
                details.append(dict(revision=commit, author_date=author_time, personal=author_email.casefold() in personal, merge=len(commit_parents.split())>1, files=sorted(set(filter(None, files))), tree_files=sorted(filter(None, tree_files))))
            changes = git(path, 'diff-tree', '--root', '--no-commit-id', '--raw', '--no-abbrev', '-r', '-z', *([base, head] if base else [head])).split('\0')
            gitlinks = []
            for i in range(0, len(changes)-1, 2):
                raw, name = changes[i], changes[i+1]
                parts = raw.split()
                if len(parts) >= 5 and parts[1] == '160000':
                    key = (name, parts[3])
                    gitlinks.append(dict(path=name, revision=parts[3], repeated_adoption=key in adopted))
                    adopted.add(key)
            integrations.append(dict(repository=repository, head=head, base=base, timestamp=timestamp,
                                     author_date=authored, kind='merge' if len(parents)>1 else 'direct_commit',
                                     pr_evidence=None, deployment_evidence=None, subject=subject,
                                     integrator_personal=email.casefold() in personal, commits=details, gitlinks=gitlinks))
        branches = [dict(ref=line.split(' ', 1)[0], tip=line.split(' ', 1)[1]) for line in git(path, 'for-each-ref', '--format=%(refname) %(objectname)', 'refs/heads/').splitlines()]
        body = dict(repository=repository, project=entry.get('project', path.name), default_ref=ref, tip=tip,
                    observed_at=observed, integrations=integrations, branches=branches,
                    limitations=['Local refs may be stale; no fetch performed.', 'Merge does not imply deployment or customer success.',
                                 'PR identity requires explicit evidence; merge subjects are not authoritative.',
                                 'Personal implementation requires configured author identity or explicit attribution evidence.'])
        identifier = hashlib.sha256(encoded(body).encode()).hexdigest()
        db.execute('INSERT OR IGNORE INTO repository_snapshots VALUES (?,?,?,?)', (identifier, repository, observed, encoded(body)))
        snapshots.append(dict(id=identifier, **body))
    return snapshots


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value, label):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= 4000, label + ' must be nonempty text (at most 4000 characters)')
    return value


def array(value, label):
    require(isinstance(value, list) and len(value) <= 10000, label + ' must be a bounded array')
    return value


def refs(value, label, required=True):
    array(value, label)
    require(not required or bool(value), label + ' requires evidence references')
    for entry in value:
        text(entry, label)


def exact_keys(value, required, optional=()):
    require(isinstance(value, dict), 'Expected an object')
    require(set(required) <= value.keys() and not value.keys()-set(required)-set(optional), 'Invalid fields: expected ' + ', '.join(required) + '; optional ' + ', '.join(optional))


def latest(db, approved=False):
    for (body,) in db.execute('SELECT body FROM engineering_assessments ORDER BY version DESC'):
        document = json.loads(body)
        if not approved or document['approval_status'] == 'approved':
            return document
    return None


def snapshots_for(db, identifiers):
    result = {}
    for identifier in identifiers:
        row = db.execute('SELECT body FROM repository_snapshots WHERE id=?', (identifier,)).fetchone()
        require(row is not None, 'Unknown repository snapshot: collect local evidence first')
        body = json.loads(row[0])
        require(body['repository'] not in result, 'Only one snapshot per canonical repository is allowed')
        result[body['repository']] = dict(id=identifier, **body)
    return result


def validate_assessment(db, document, timezone):
    exact_keys(document, ('schema_version', 'version', 'timezone', 'cutoff', 'reviewer', 'method', 'method_version', 'approval_status', 'snapshots', 'work_items', 'excluded_integrations', 'day_reviews'), ('integration_evidence',))
    require(document['schema_version'] == 1 and type(document['schema_version']) is int, 'Unsupported assessment schema')
    require(type(document['version']) is int and document['version'] > 0, 'version must be a positive integer')
    require(document['timezone'] == timezone, 'Assessment timezone must match configured timezone')
    cutoff = instant(document['cutoff'])
    require(cutoff <= instant(now()), 'Assessment cutoff cannot be in the future')
    for key in ('reviewer', 'method', 'method_version'):
        text(document[key], key)
    require(document['approval_status'] in ('proposed', 'approved'), 'approval_status must be proposed or approved')
    refs(document['snapshots'], 'snapshots', required=False)
    repositories = snapshots_for(db, document['snapshots'])
    for repo in repositories.values():
        require(instant(repo['observed_at']) >= cutoff, 'Snapshot must have been observed at or after assessment cutoff')
    integrations = {(r, i['head']): i for r, s in repositories.items() for i in s['integrations'] if instant(i['timestamp']) <= cutoff}
    item_ids, credits, allocations, linked = set(), set(), set(), set()
    for item in array(document['work_items'], 'work_items'):
        exact_keys(item, ('id', 'scope', 'kind', 'credit_key', 'incremental_rationale', 'related_items', 'integrations', 'allocations', 'effort', 'quality'), ('outcomes',))
        for field in ('id', 'scope', 'credit_key', 'incremental_rationale'):
            text(item[field], field)
        require(item['id'] not in item_ids, 'Duplicate work-item ID')
        require(item['credit_key'] not in credits, 'Shared scope must be grouped once; duplicate credit_key')
        item_ids.add(item['id']); credits.add(item['credit_key'])
        require(item['kind'] in ('engineering', 'publishing_admin', 'generated', 'revert_reapplication', 'dependency_adoption'), 'Unknown work-item kind')
        refs(item['related_items'], 'related_items', False)
        if 'outcomes' in item:
            refs(item['outcomes'], 'outcomes', False)
        item_links = set()
        for link in array(item['integrations'], 'integrations'):
            exact_keys(link, ('repository', 'head'))
            key = (text(link['repository'], 'repository'), text(link['head'], 'head'))
            require(key in integrations and key not in item_links, 'Unknown or duplicate integration; use exact collected revisions')
            item_links.add(key); linked.add(key)
        require(bool(item_links), 'Work item needs a first-parent delivery integration')
        for allocation in array(item['allocations'], 'allocations'):
            exact_keys(allocation, ('repository', 'integration', 'commit', 'paths', 'credit', 'scope', 'attribution_evidence'))
            key = (allocation['repository'], allocation['integration'])
            require(key in item_links, 'Allocation must reference a linked integration')
            commit = next((c for c in integrations[key]['commits'] if c['revision'] == allocation['commit']), None)
            require(commit is not None, 'Covered commit is not part of integration')
            require(allocation['credit'] in ('implementation', 'design', 'integration_review'), 'Unknown allocation credit')
            text(allocation['scope'], 'allocation scope')
            refs(allocation['attribution_evidence'], 'attribution_evidence', False)
            refs(allocation['paths'], 'paths', allocation['credit'] != 'integration_review')
            require(len(set(allocation['paths'])) == len(allocation['paths']), 'Duplicate allocation path')
            require(set(allocation['paths']) <= set(commit['files']), 'Allocation paths must be changed in the covered commit')
            if allocation['credit'] != 'integration_review':
                require(not commit['merge'], 'A merge author is not implementation attribution; allocate underlying commits or a separate integration/review allowance')
                require(commit['personal'] or bool(allocation['attribution_evidence']), 'Other-author implementation needs explicit attribution evidence')
                repeated = {g['path'] for g in integrations[key]['gitlinks'] if g['repeated_adoption']}
                require(not repeated.intersection(allocation['paths']), 'Repeated gitlink adoption cannot receive implementation credit')
            else:
                require(not allocation['paths'], 'Integration/review allowance uses no implementation paths')
                require(bool(allocation['attribution_evidence']), 'Integration/review allowance needs attribution evidence')
            for path in allocation['paths'] or ['<integration-review>']:
                claim = (allocation['repository'], allocation['commit'], path)
                require(claim not in allocations, 'Overlapping effort credit: split scope into explicit disjoint paths')
                allocations.add(claim)
        effort = item['effort']
        exact_keys(effort, ('status', 'hours_low', 'hours_central', 'hours_high', 'rationale', 'confidence', 'evidence', 'exclusions'))
        require(effort['status'] in ('unreviewed', 'assessed', 'unassessable'), 'Unknown effort review status')
        text(effort['rationale'], 'effort rationale')
        require(effort['confidence'] in ('low', 'medium', 'high'), 'Unknown confidence')
        refs(effort['evidence'], 'effort evidence', effort['status'] == 'assessed')
        refs(effort['exclusions'], 'effort exclusions', False)
        hours = [effort['hours_'+s] for s in SCENARIOS]
        if effort['status'] == 'assessed':
            require(all(type(h) in (int, float) and math.isfinite(h) and h >= 0 for h in hours) and hours == sorted(hours), 'Hours must be finite, nonnegative, ordered low ≤ central ≤ high')
            require(not hours[-1] or (item['kind'] == 'engineering' and bool(item['allocations'])), 'Positive effort needs engineering scope allocations; bookkeeping/generated/reapplications are excluded')
        else:
            require(all(h is None for h in hours), 'Unassessed effort must use null hours, not zero')
        for review in array(item['quality'], 'quality'):
            exact_keys(review, ('status', 'repository', 'revision', 'files', 'method', 'method_version', 'reviewer', 'reviewed_at', 'scores', 'confidence', 'strengths', 'reservations', 'unreviewed_scope', 'evidence', 'tests'))
            require(review['status'] in ('unreviewed', 'assessed', 'unassessable'), 'Unknown quality status')
            repo = repositories.get(review['repository'])
            require(repo is not None, 'Unknown quality repository')
            revision = next((c for i in repo['integrations'] if instant(i['timestamp']) <= cutoff for c in i['commits'] if c['revision'] == review['revision']), None)
            require(revision is not None, 'Quality revision must belong to observed delivery history before cutoff')
            refs(review['files'], 'quality files')
            # Scope may include unchanged dependencies; paths must remain repository-relative.
            require(all(not p.startswith('/') and '..' not in Path(p).parts for p in review['files']), 'Quality file scope must be repository-relative')
            require(set(review['files']) <= set(revision['tree_files']), 'Quality scope must exist at the exact reviewed revision')
            for field in ('method', 'method_version', 'reviewer', 'unreviewed_scope'):
                text(review[field], field)
            require(instant(review['reviewed_at']) <= instant(now()), 'Quality review date is in the future')
            exact_keys(review['scores'], DIMENSIONS)
            require(all(v is None or (type(v) is int and 0 <= v <= 5) for v in review['scores'].values()), 'Quality dimensions must be null or integer 0–5')
            require(review['status'] == 'assessed' or all(v is None for v in review['scores'].values()), 'Unassessed quality cannot contain scores')
            require(review['confidence'] in ('low', 'medium', 'high'), 'Unknown quality confidence')
            for key in ('strengths', 'reservations', 'evidence'):
                refs(review[key], key, key == 'evidence' and review['status'] == 'assessed')
            for test in array(review['tests'], 'tests'):
                exact_keys(test, ('classification', 'revision', 'date', 'applies_to_delivered', 'result', 'evidence'))
                require(test['classification'] in ('present_only', 'contemporaneous_result_inspected', 'later_historical_snapshot_rerun'), 'Unknown test evidence classification')
                require(any(c['revision'] == test['revision'] for i in repo['integrations'] for c in i['commits']), 'Unknown test revision')
                require(dt.date.fromisoformat(test['date']) <= instant(now()).astimezone(ZoneInfo(timezone)).date(), 'Test evidence date cannot be in the future')
                require(type(test['applies_to_delivered']) is bool, 'applies_to_delivered must be boolean')
                require(test['result'] in ('not_run', 'passed', 'failed', 'unknown'), 'Unknown test result')
                require(test['classification'] != 'present_only' or test['result'] == 'not_run', 'Test presence is not a passing result')
                refs(test['evidence'], 'test evidence')
    for item in document['work_items']:
        require(set(item['related_items']) <= item_ids-{item['id']}, 'Unknown or self-referential related item')
    excluded = set()
    for entry in array(document['excluded_integrations'], 'excluded_integrations'):
        exact_keys(entry, ('repository', 'head', 'reason', 'evidence'))
        key = (entry['repository'], entry['head'])
        require(key in integrations and key not in linked and key not in excluded, 'Exclusion must identify a unique uncredited integration')
        excluded.add(key)
        text(entry['reason'], 'exclusion reason'); refs(entry['evidence'], 'exclusion evidence')
    days = set()
    for review in array(document['day_reviews'], 'day_reviews'):
        exact_keys(review, ('date', 'status', 'rationale', 'evidence'))
        day = dt.date.fromisoformat(review['date']).isoformat()
        require(day == review['date'] and day not in days, 'Duplicate or noncanonical review date')
        days.add(day)
        require(review['status'] in ('unreviewed', 'assessed', 'unassessable'), 'Unknown date status')
        require(day <= cutoff.astimezone(ZoneInfo(timezone)).date().isoformat(), 'Date review exceeds cutoff')
        text(review['rationale'], 'date rationale'); refs(review['evidence'], 'date evidence', review['status'] == 'assessed')
    annotated, deployments = set(), set()
    for annotation in array(document.get('integration_evidence', []), 'integration_evidence'):
        exact_keys(annotation, ('repository','head','pr','deployments'))
        key = (annotation['repository'],annotation['head'])
        require(key in integrations and key not in annotated, 'Integration evidence must reference a unique observed integration')
        annotated.add(key)
        if annotation['pr'] is not None:
            exact_keys(annotation['pr'], ('url','evidence'))
            url = urlsplit(text(annotation['pr']['url'], 'PR URL'))
            require(url.scheme == 'https' and bool(url.hostname) and url.username is None and url.password is None, 'PR evidence requires an HTTPS URL without credentials')
            refs(annotation['pr']['evidence'], 'PR evidence')
        for deployment in array(annotation['deployments'], 'deployments'):
            exact_keys(deployment, ('id','timestamp','evidence'))
            text(deployment['id'], 'deployment id')
            require(deployment['id'] not in deployments, 'Duplicate deployment ID')
            deployments.add(deployment['id'])
            require(instant(integrations[key]['timestamp']) <= instant(deployment['timestamp']) <= cutoff, 'Deployment must follow integration and precede cutoff')
            refs(deployment['evidence'], 'deployment evidence')
    return document


def import_assessment(db, document, timezone):
    init(db)
    try:
        validate_assessment(db, document, timezone)
    except (TypeError, KeyError, AttributeError, OverflowError) as error:
        raise ValueError('Invalid assessment field shape') from error
    existing = db.execute('SELECT body FROM engineering_assessments WHERE version=?', (document['version'],)).fetchone()
    if existing:
        require(existing[0] == encoded(document), 'Versions are immutable; increment version to edit')
        return document['version']
    current = latest(db)
    require(document['version'] == (current['version'] if current else 0)+1, 'Version must increment the latest assessment by one')
    db.execute('INSERT INTO engineering_assessments VALUES (?,?,?)', (document['version'], now(), encoded(document)))
    return document['version']


def template(db, timezone):
    current = latest(db)
    if current:
        return dict(current, version=current['version']+1, approval_status='proposed')
    return dict(schema_version=1, version=1, timezone=timezone, cutoff=now(), reviewer='Local reviewer', method='manual', method_version='1', approval_status='proposed', snapshots=[], work_items=[], excluded_integrations=[], day_reviews=[])


def statistics_for(days, hours):
    eligible = [d for d in days if d['eligible']]
    known = [d for d in eligible if d['status'] == 'assessed']
    complete = bool(eligible) and len(known) == len(eligible)
    delivery_dates = [d for d in days if d['eligible'] or d['integrations']]
    delivery_complete = bool(delivery_dates) and all(d['status']=='assessed' for d in delivery_dates)
    scenarios = {}
    for s in SCENARIOS:
        values = [d['hours'][s]/hours for d in known]
        active_total = sum(d['hours'][s] for d in known)
        total = sum((d['hours'] if d['status']=='assessed' else d.get('known_item_hours', {})).get(s,0) or 0 for d in days)
        stats = dict(minimum=min(values) if values else None, maximum=max(values) if values else None,
                     median=statistics.median(values) if values else None, average=active_total/(hours*len(eligible)) if complete else None)
        scenarios[s] = dict(total_estimated_hours=total, active_date_estimated_hours=active_total,
                            engineer_days=total/hours,
                            average_daily_equivalent=total/(hours*len(eligible)) if delivery_complete and eligible else None,
                            assessed_date_mean=statistics.mean(values) if values else None,
                            **{k:v if complete else None for k,v in stats.items()})
    return dict(complete=complete, delivery_complete=delivery_complete, status='complete' if complete and delivery_complete else 'partial' if eligible or delivery_dates else 'no eligible dates',
                eligible_dates=len(eligible), assessed_dates=len(known), comparison_hours=hours,
                denominator_hours=hours*len(eligible), scenarios=scenarios)


def view(db, config, filters, cutoff=None):
    init(db)
    if not db.in_transaction:
        db.execute('BEGIN')
    cutoff = cutoff or now()
    zone_name = config.get('timezone', 'America/Los_Angeles'); zone = ZoneInfo(zone_name)
    today = instant(cutoff).astimezone(zone).date().isoformat()
    usage, events, provenance = accounting(db, filters, zone_name, cutoff)
    agent_activity = activity(db, filters, zone_name, events, provenance, cutoff)
    delivery_filters = {k:v for k,v in filters.items() if k not in ('provider', 'model', 'role')}
    delivery_usage, delivery_events, _ = accounting(db, delivery_filters, zone_name, cutoff)
    document = latest(db, approved=True)
    full_repositories = snapshots_for(db, document['snapshots']) if document else {}
    repositories = full_repositories
    repositories = {k:r for k,r in repositories.items() if not filters.get('projects') or r['project'] in filters['projects']}
    all_integrations = {(r,i['head']):i for r,s in full_repositories.items() for i in s['integrations']}
    days = {}
    def day_row(day):
        if not filters.get('start', '0001-01-01') <= day <= filters.get('end', '9999-12-31'):
            return None
        return days.setdefault(day, dict(date=day, eligible=False, partial_day=day==today, hours={s:0 for s in SCENARIOS}, items=[], integrations=[], deployments=[], unknown_items=[], unmapped_projects=[], status='unknown', review=None))
    for day,u in delivery_usage['days'].items():
        day_row(day)['eligible'] = u['total']>0
    for day in agent_activity['days']:
        day_row(day)
    mapped_projects = {r['project'] for r in repositories.values()}
    for event in delivery_events.values():
        row = day_row(event['date']) if event['total']>0 else None
        if row is not None and event['project'] not in mapped_projects and event['project'] not in row['unmapped_projects']:
            row['unmapped_projects'].append(event['project'])
    integration_lookup = {}
    if document:
        annotations = {(a['repository'],a['head']):a for a in document.get('integration_evidence', [])}
        for repository, snapshot in repositories.items():
            for integration in snapshot['integrations']:
                if instant(integration['timestamp']) > min(instant(document['cutoff']), instant(cutoff)):
                    continue
                key = (repository, integration['head'])
                annotation = annotations.get(key)
                integration = dict(integration, pr_evidence=annotation['pr'] if annotation else None,
                                   delivery_kind='pr_merge' if annotation and annotation['pr'] else integration['kind'])
                integration_lookup[key] = integration
                for deployment in annotation['deployments'] if annotation else []:
                    if instant(deployment['timestamp']) <= instant(cutoff):
                        deployed = day_row(instant(deployment['timestamp']).astimezone(zone).date().isoformat())
                        if deployed is not None:
                            deployed['deployments'].append(dict(deployment,repository=repository,head=integration['head']))
                day = instant(integration['timestamp']).astimezone(zone).date().isoformat()
                row = day_row(day)
                if row is not None:
                    row['integrations'].append(integration)
        linked = set()
        excluded = {(i['repository'], i['head']) for i in document['excluded_integrations']}
        for item in document['work_items']:
            # Cross-repository scope remains one item and is never prorated by commit count.
            all_links = [(i['repository'], i['head']) for i in item['integrations']]
            if not any(k in integration_lookup for k in all_links):
                continue
            date = min(instant(all_integrations[k]['timestamp']) for k in all_links).astimezone(zone).date().isoformat()
            row = day_row(date)
            linked.update(all_links)
            if row is None:
                continue
            enriched = dict(item, method=document['method'], method_version=document['method_version'], reviewer=document['reviewer'], assessment_version=document['version'], quality=[])
            for review in item['quality']:
                scores = review['scores']
                complete = review['status']=='assessed' and all(v is not None for v in scores.values())
                repo_integrations = full_repositories[review['repository']]['integrations']
                same_day = [i for i in repo_integrations if instant(i['timestamp']).astimezone(zone).date().isoformat()==date and instant(i['timestamp'])<=instant(document['cutoff'])]
                final_head = same_day[-1]['head'] if same_day else None
                enriched['quality'].append(dict(review, quality_score=5*sum(scores.values()) if complete else None,
                                               final_day_head=final_head, final_day_scope=review['revision']==final_head))
            row['items'].append(enriched)
            if item['effort']['status'] == 'assessed':
                for s in SCENARIOS:
                    row['hours'][s] += item['effort']['hours_'+s]
            else:
                row['unknown_items'].append(item['id'])
        reviews = {d['date']:d for d in document['day_reviews']}
        for date,row in days.items():
            row['review'] = reviews.get(date)
            for i in row['integrations']:
                if (i['repository'],i['head']) not in linked|excluded:
                    row['unknown_items'].append(i['repository']+':'+i['head'])
            day_end = dt.datetime.combine(dt.date.fromisoformat(date)+dt.timedelta(days=1), dt.time(), zone).astimezone(UTC)
            coverage_end = min(day_end, instant(cutoff))
            if repositories and row['review'] and row['review']['status']=='assessed' and not row['unknown_items'] and not row['unmapped_projects'] and instant(document['cutoff']) >= coverage_end:
                row['status']='assessed'
    ordered = [days[d] for d in sorted(days)]
    for row in ordered:
        if row['status'] != 'assessed':
            row['known_item_hours'] = row['hours']
            row['hours'] = {s:None for s in SCENARIOS}
    weeks = {}
    for row in ordered:
        day = dt.date.fromisoformat(row['date']); week = (day-dt.timedelta(days=day.weekday())).isoformat()
        weeks.setdefault(week, []).append(row)
    weekly = []
    for week, rows in weeks.items():
        stats = statistics_for(rows, 8)
        usage_rows = [usage['days'][row['date']] for row in rows if row['date'] in usage['days']]
        usage_week = {k:sum(r[k] for r in usage_rows) if all(r[k] is not None for r in usage_rows) else None for k in ('total','fresh_input','cache_read','cache_write','output','raw_verified','mismatched','ledger_only','unknown_counter_records','response_records','aggregate_records')}
        usage_week['raw_reconciliation_coverage'] = usage_week['raw_verified']/usage_week['total'] if usage_week['total'] else None
        usage_week['cache_read_share'] = usage_week['cache_read']/usage_week['total'] if usage_week['total'] else None
        activity_rows = [agent_activity['days'][r['date']] for r in rows if r['date'] in agent_activity['days']]
        identities = {a['id']:a for r in activity_rows for a in r['identities']}
        positive_ids = {i for r in activity_rows for i in r['positive_identity_ids']}
        peak = lambda key: max((r[key] for r in activity_rows if r[key] is not None), default=None)
        activity_week = dict(roots=sum(not a['child'] for a in identities.values()),children=sum(a['child'] for a in identities.values()),inclusive_identities=len(identities),positive_accounting_identities=len(positive_ids),zero_or_synthetic_only=len(set(identities)-positive_ids),task_span_peak=peak('task_span_peak'),positive_task_span_peak=peak('positive_task_span_peak'),missing_terminal_markers=sum(a['missing_terminal'] for a in identities.values()),responding_density={str(w):max((r['responding_density'][str(w)] for r in activity_rows if r['responding_density'][str(w)] is not None),default=None) for w in (60,300,600)}) if activity_rows else None
        weekly.append(dict(date=week, usage=usage_week, activity=activity_week, integrations=sum(len(r['integrations']) for r in rows), deployments=sum(len(r['deployments']) for r in rows), quality_scores=[q['quality_score'] for r in rows for item in r['items'] for q in item['quality']], **stats))
    return dict(label='xEngineer — estimated delivery equivalent', baseline=BASELINE, disclaimer=DISCLAIMER,
                selection=filters,
                cutoff=cutoff, assessment_cutoff=document['cutoff'] if document else None, timezone=zone_name,
                assessment_version=document['version'] if document else None, privacy_mode=False,
                delivery_scope='Date/project scope; provider/model/role filters apply only to usage and activity. No evidence-backed model attribution to Git changes.',
                repositories=[{k:r[k] for k in ('id','repository','project','default_ref','tip','observed_at','limitations')} for r in repositories.values()],
                days=ordered, weekly=weekly, usage=usage, activity=agent_activity,
                sensitivity={str(h):statistics_for(ordered,h) for h in (4,8,12)},
                full_days={str(h):statistics_for([r for r in ordered if not r['partial_day']],h) for h in (4,8,12)},
                assumptions=['Comparison hours are per token-active day, not recorded human time.',
                             'Scenarios are retrospective judgments, not observed hours or confidence intervals.',
                             'Quality is independent of effort; no token, LOC, PR or quality multiplier is applied.',
                             'Reviewed zero delivery can coexist with useful planning or branch work.',
                             'Grouped cross-repository scope is shown whole when any mapped repository is selected.',
                             'Assessments remain frozen at their cutoff; new integrations require a new assessment version.'])


def export_report(report, private=True):
    """Allowlisted share representation. Free text, revisions, paths and identities stay local."""
    result = {k:report[k] for k in ('label','baseline','disclaimer','cutoff','assessment_cutoff','timezone','assessment_version','delivery_scope','sensitivity','full_days','weekly','assumptions')}
    result['privacy_mode'] = private
    result['selection'] = {k:v for k,v in report['selection'].items() if k != 'projects'}
    result['selection']['project_count'] = len(report['selection'].get('projects', []))
    result['evidence_detail'] = 'References, scope text, source paths/hashes, identities and repository revisions omitted from share exports. Use explicit local assessment export for editing.'
    result['days'] = [{k:row[k] for k in ('date','eligible','partial_day','hours','status')} | dict(unknown_items=len(row['unknown_items']), unmapped_projects=len(row['unmapped_projects']), work_items=len(row['items']), integrations=len(row['integrations']), deployments=len(row['deployments']), quality_scores=[q['quality_score'] for item in row['items'] for q in item['quality']]) for row in report['days']]
    result['usage'] = report['usage']
    result['activity'] = dict(report['activity'], days={d:{k:v for k,v in row.items() if k not in ('identities','positive_identity_ids')} for d,row in report['activity']['days'].items()})
    return result


def csv_report(report):
    stream = io.StringIO(); writer = csv.writer(stream)
    writer.writerow(['metadata_json', encoded({k:v for k,v in report.items() if k not in ('days','usage','activity')})])
    writer.writerow(['date','status','eligible','partial_day','hours_low','hours_central','hours_high','unknown_items','unmapped_projects','work_items','integrations','deployments','usage_json','activity_json','quality_scores'])
    for row in report['days']:
        writer.writerow([row['date'],row['status'],row['eligible'],row['partial_day'],*[row['hours'][s] for s in SCENARIOS],row['unknown_items'],row['unmapped_projects'],row['work_items'],row['integrations'],row['deployments'],encoded(report['usage']['days'].get(row['date'])),encoded(report['activity']['days'].get(row['date'])),encoded(row['quality_scores'])])
    return stream.getvalue()
