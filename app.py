#!/usr/bin/env python3
"""Local token ledger. Python 3.9+, no dependencies."""
import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
import sqlite3
import threading
from urllib.parse import urlsplit, parse_qs
from costs import estimate as estimate_cost
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo
from carbon import estimate as estimate_carbon
from topics import contexts as topic_contexts

BASE = Path(__file__).resolve().parent
LOCK = threading.Lock()


def connect(path):
    db = sqlite3.connect(path)
    db.executescript('''
    CREATE TABLE IF NOT EXISTS events (
      id TEXT PRIMARY KEY, timestamp TEXT, provider TEXT, account TEXT,
      session TEXT, model TEXT, subagent INTEGER, input INTEGER,
      cached INTEGER, cache_write INTEGER, output INTEGER, reasoning INTEGER);
    CREATE TABLE IF NOT EXISTS session_topics (provider TEXT, session TEXT, project TEXT, title TEXT, activity TEXT, basis TEXT, PRIMARY KEY(provider,session));
    CREATE TABLE IF NOT EXISTS event_roles (id TEXT PRIMARY KEY, role TEXT);
    CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, stamp TEXT);
    ''')
    return db


def number(u, key):
    return max(0, int(u.get(key) or 0))


def model_name(value):
    return value.strip() if isinstance(value,str) and value.strip() else 'unknown'


def event(key, timestamp, provider, account, session, model, subagent, u):
    cached = number(u, 'cached_input_tokens' if provider == 'Codex' else 'cache_read_input_tokens')
    write = number(u, 'cache_write_input_tokens' if provider == 'Codex' else 'cache_creation_input_tokens')
    inp = number(u, 'input_tokens')
    # Anthropic reports cache reads/writes separately; OpenAI input includes cache.
    if provider != 'Codex':
        inp += cached + write
    return (provider + ':' + key, timestamp, provider, account, session, model_name(model),
            int(subagent), inp, cached, write, number(u, 'output_tokens'),
            number(u, 'reasoning_output_tokens'))


def json_lines(path):
    with path.open(errors='replace') as stream:
        for line in stream:
            try:
                row = json.loads(line)
            except (ValueError, TypeError):
                continue  # A live writer may not have finished its final line.
            if isinstance(row, dict):
                yield row


def codex_auditors(config):
    """Link explicit Snipe invocation turns to their started child sessions."""
    auditors = set()
    for source in config['sources']:
        if source['provider'] != 'Codex':
            continue
        for path in Path(source['path']).expanduser().rglob('*.jsonl'):
            active = False
            try:
                for x in json_lines(path):
                    p = x.get('payload') or {}
                    if p.get('type') == 'task_started':
                        active = False
                    if x.get('type') == 'response_item' and p.get('role') == 'user':
                        for c in p.get('content', []):
                            if re.search(r'(?m)^\s*\$(?:[\w-]+:)?snipe\b', c.get('text', '')):
                                active = True
                    item = p.get('item') or {}
                    if active and item.get('type') == 'SubAgentActivity' and item.get('kind') == 'started':
                        if item.get('agent_thread_id'):
                            auditors.add(item['agent_thread_id'])
            except OSError:
                continue
    return auditors


def is_war_auditor(value):
    return isinstance(value, str) and value.split(':')[-1] == 'war-auditor'


def records(path, provider, account, auditors=None):
    auditors = auditors or set()
    if provider == 'Claude Code':
        try:
            metadata = json.loads(path.with_suffix('.meta.json').read_text())
        except (OSError, ValueError):
            metadata = {}
        auditor = is_war_auditor(metadata.get('agentType'))
        for x in json_lines(path):
            msg = x.get('message') or {}
            if x.get('type') != 'assistant' or not msg.get('usage'):
                continue
            key = msg.get('id') or x.get('requestId') or x.get('uuid')
            if not key or not x.get('timestamp'):
                continue
            row = event(key, x['timestamp'], provider, account,
                        x.get('sessionId', path.stem), msg.get('model', 'unknown'),
                        x.get('isSidechain', False) or 'subagents' in path.parts, msg['usage'])
            yield row + ('auditor' if auditor or is_war_auditor(x.get('attributionAgent')) else 'subagent' if row[6] else 'main',)
        return
    # Keep only small accounting records; never retain transcript content.
    rows = []
    for x in json_lines(path):
        kind, payload = x.get('type'), x.get('payload') or {}
        if kind == 'session_meta':
            x['payload'] = {k: payload.get(k) for k in ('id', 'source')}
        elif kind == 'turn_context':
            x['payload'] = {'model': payload.get('model', 'unknown')}
        elif kind != 'token_usage_record' and payload.get('type') != 'token_count':
            continue
        rows.append(x)
    meta = next((x.get('payload', {}) for x in rows if x.get('type') == 'session_meta'), {})
    session = meta.get('id', path.stem)
    subagent = isinstance(meta.get('source'), dict) and 'subagent' in meta['source']
    model = 'unknown'
    detailed = any(x.get('type') == 'token_usage_record' for x in rows)
    previous = {}
    for x in rows:
        p = x.get('payload') or {}
        if x.get('type') == 'turn_context':
            model = p.get('model', model)
        if detailed:
            if x.get('type') != 'token_usage_record' or not p.get('response_id'):
                continue
            row = event(p['response_id'], x['timestamp'], provider, account,
                        p.get('thread_id', session), model,
                        subagent and p.get('thread_id', session) == session, p.get('usage', {}))
            yield row + ('auditor' if row[4] in auditors else 'subagent' if row[6] else 'main',)
        elif p.get('type') == 'token_count' and p.get('info'):
            total = p['info'].get('total_token_usage') or {}
            if not total or total == previous:
                continue
            delta = {k: max(0, number(total, k) - number(previous, k)) for k in total}
            previous = total
            # Old fork logs can include copied history; timestamp+totals dedup copies.
            key = hashlib.sha256(json.dumps([x['timestamp'], total], sort_keys=True).encode()).hexdigest()
            yield event(key, x['timestamp'], provider, account, session, model, subagent, delta) + ('auditor' if session in auditors else 'subagent' if subagent else 'main',)


def sync(db_path, config):
    with LOCK, connect(db_path) as db:
        report = []
        for (provider, session), topic in topic_contexts(config).items():
            db.execute('INSERT OR REPLACE INTO session_topics VALUES (?,?,?,?,?,?)', (provider, session, topic['project'], topic['title'], topic['activity'], topic['basis']))
        auditors = codex_auditors(config)
        for session in auditors:
            db.execute("INSERT OR REPLACE INTO event_roles SELECT id, 'auditor' FROM events WHERE provider='Codex' AND session=?", (session,))
        for source in config['sources']:
            root = Path(source['path']).expanduser()
            count = changed = errors = 0
            for path in root.rglob('*.jsonl') if root.exists() else []:
                count += 1
                try:
                    st = path.stat()
                    meta = path.with_suffix('.meta.json')
                    meta_stamp = meta.stat().st_mtime_ns if meta.exists() else 0
                    stamp = f'roles-v2:{st.st_mtime_ns}:{st.st_size}:{meta_stamp}'
                    old = db.execute('SELECT stamp FROM files WHERE path=?', (str(path),)).fetchone()
                    if old and old[0] == stamp:
                        continue
                    for row in records(path, source['provider'], source.get('account', 'Local · account unknown'), auditors):
                        # Streaming Claude messages repeat their ID; retain greatest reported usage.
                        db.execute('''INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(id) DO UPDATE SET input=MAX(input,excluded.input),
                        cached=MAX(cached,excluded.cached), cache_write=MAX(cache_write,excluded.cache_write),
                        output=MAX(output,excluded.output), reasoning=MAX(reasoning,excluded.reasoning),
                        subagent=MAX(subagent,excluded.subagent)''', row[:-1])
                        db.execute("INSERT INTO event_roles VALUES (?,?) ON CONFLICT(id) DO UPDATE SET role=CASE WHEN role='auditor' OR excluded.role='auditor' THEN 'auditor' WHEN role='subagent' OR excluded.role='subagent' THEN 'subagent' ELSE 'main' END", (row[0], row[-1]))
                    db.execute('INSERT OR REPLACE INTO files VALUES (?,?)', (str(path), stamp))
                    changed += 1
                except (OSError, ValueError, TypeError, KeyError):
                    errors += 1
            report.append(dict(provider=source['provider'], found=root.exists(), files=count, changed=changed, errors=errors))
        return report


def summary(db_path, config, filters=None):
    filters = filters or {}
    zone = ZoneInfo(config.get('timezone', 'America/Los_Angeles'))
    today=dt.datetime.now(zone).date().isoformat()
    days, providers, accounts, models = {}, {}, {}, {}
    total = dict(input=0, output=0, cached=0, cache_write=0, reasoning=0, total=0, subagent=0, auditor=0, other=0, responses=0)
    sessions = set()
    carbon_groups = {}
    work = {}
    cost_groups = {}
    available = {k:set() for k in ('providers','models','projects','years')}
    all_days = {}
    with connect(db_path) as db:
        topic_lookup = {(p,s):dict(project=project,title=title,activity=activity,basis=basis) for p,s,project,title,activity,basis in db.execute('SELECT * FROM session_topics')}
        for row in db.execute('SELECT events.*, event_roles.role FROM events LEFT JOIN event_roles USING(id)'):
            _, timestamp, provider, account, session, model, sub, inp, cache, write, out, reasoning, recorded_role = row
            model = model_name(model)
            try:
                day = dt.datetime.fromisoformat(timestamp.replace('Z', '+00:00')).astimezone(zone).date().isoformat()
            except (ValueError, AttributeError):
                continue
            category = 'other' if provider == 'Codex' and model == 'codex-auto-review' else recorded_role or ('subagent' if sub else 'main')
            project = topic_lookup.get((provider,session),{}).get('project','Unassigned')
            if day<=today:
                available['providers'].add(provider);available['models'].add(model);available['projects'].add(project);available['years'].add(day[:4])
            all_days[day]=all_days.get(day,0)+inp+out
            if any(filters.get(k) and filters[k] != value for k,value in [('provider',provider),('model',model),('role',category)]):
                continue
            if filters.get('projects') and project not in filters['projects']:
                continue
            if day < filters.get('start','0001-01-01') or day > filters.get('end','9999-12-31'):
                continue
            cost = cost_groups.setdefault((day,model),dict(input=0,cached=0,cache_write=0,output=0))
            for key,value in [('input',inp),('cached',cache),('cache_write',write),('output',out)]:cost[key]+=value
            usage = carbon_groups.setdefault((day, model), dict(input=0, cached=0, output=0))
            for key, value in (('input', inp), ('cached', cache), ('output', out)):
                usage[key] += value
            n = inp + out
            task = work.setdefault((provider, session), dict(provider=provider,session=session,**topic_lookup.get((provider,session),dict(project='Unassigned',title='',activity='Unclassified work',basis='Missing metadata')),days={}))
            task['days'][day] = task['days'].get(day,0) + n
            d = days.setdefault(day, dict(total=0, input=0, output=0, cached=0, subagent=0, auditor=0, other=0, responses=0, breakdown={"main": {}, "subagent": {}, "auditor": {}, "other": {}}))
            category = 'other' if provider == 'Codex' and model == 'codex-auto-review' else recorded_role or ('subagent' if sub else 'main')
            role = d['breakdown'][category]
            role[model] = role.get(model, 0) + n
            for target in (d, total):
                for key, value in [('total', n), ('input', inp), ('output', out), ('cached', cache), ('subagent', n if category == 'subagent' else 0), ('auditor', n if category == 'auditor' else 0), ('other', n if category == 'other' else 0), ('responses', 1)]:
                    target[key] += value
            total['cache_write'] += write
            total['reasoning'] += reasoning
            for group, label in [(providers, provider), (accounts, account), (models, model)]:
                group[label] = group.get(label, 0) + n
            sessions.add((provider, session))
    return dict(days=days, totals=total, providers=providers, accounts=accounts, models=models,
                work=list(work.values()), available=dict({k:sorted(v) for k,v in available.items()},first=min((d for d in all_days if d<=today),default=None)), largest_day_all_time=max((n for d,n in all_days.items() if d<=dt.datetime.now(zone).date().isoformat()),default=0), costs=estimate_cost(cost_groups, config.get('cost_rates')),
                carbon=estimate_carbon(carbon_groups, config.get('carbon')),
                sessions=len(sessions), timezone=str(zone), today=dt.datetime.now(zone).date().isoformat())


def validated_range(filters, today):
    start=dt.date.fromisoformat(filters.get('start',today[:4]+'-01-01')).isoformat()
    end=dt.date.fromisoformat(filters.get('end',today)).isoformat()
    if start>end:raise ValueError('Start must precede end.')
    if end>today:raise ValueError('End cannot be in the future.')
    return dict(start=start,end=end)


def comparison_range(filters):
    start,end=dt.date.fromisoformat(filters['start']),dt.date.fromisoformat(filters['end'])
    kind=filters.get('compare','previous')
    if kind=='month':
        previous_end=start.replace(day=1)-dt.timedelta(days=1)
        previous_start=previous_end.replace(day=1)
    elif kind=='previous':
        previous_end=start-dt.timedelta(days=1)
        previous_start=start-dt.timedelta(days=(end-start).days+1)
    else:raise ValueError('Unknown comparison mode.')
    return dict(start=str(previous_start),end=str(previous_end),kind=kind)


def usage_view(db_path, config, filters, state):
    # Keep the running signal if an import commits during these reads, so the
    # client performs a fresh read after completion rather than showing old data.
    import_status=state.snapshot()
    result=summary(db_path,config,filters)
    result['range']={'start':filters['start'],'end':filters['end']}
    period=comparison_range(filters)
    previous=summary(db_path,config,dict(filters,start=period['start'],end=period['end']))
    result['comparison']=dict(period,total=previous['totals']['total'])
    after=state.snapshot()
    after['syncing']=import_status['syncing'] or after['syncing'] or import_status['generation']!=after['generation']
    return dict(result,**after)


class ImportState:
    """One background history scan shared by manual and automatic refresh."""
    def __init__(self, db_path, config):
        self.db_path, self.config = db_path, config
        self.lock = threading.Lock()
        self.running = False
        self.generation = 0
        self.error = None
        self.updated = None
        self.sources = [dict(provider=s['provider'],found=Path(s['path']).expanduser().exists(),files=0,changed=0,errors=0) for s in config['sources']]

    def snapshot(self):
        with self.lock:
            return dict(sources=self.sources,generation=self.generation,syncing=self.running,sync_error=self.error,last_sync=self.updated)

    def start(self):
        with self.lock:
            if self.running:
                return False
            self.running = True
            self.generation += 1
            self.error = None
        threading.Thread(target=self._run,daemon=True).start()
        return True

    def _run(self):
        try:
            sources=sync(self.db_path,self.config)
            with self.lock:
                self.sources=sources
                self.updated=dt.datetime.now(dt.timezone.utc).isoformat()
        except Exception:
            with self.lock:
                self.error='History scan failed. Check local source permissions and configuration, then retry.'
        finally:
            with self.lock:
                self.running=False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--sync', action='store_true', help='Import histories and exit')
    args = parser.parse_args()
    data = BASE / 'data'
    data.mkdir(exist_ok=True)
    config_path = BASE / 'config.json'
    config = json.loads(config_path.read_text() if config_path.exists() else (BASE / 'config.example.json').read_text())
    db_path = data / 'usage.sqlite3'
    if args.sync:
        sources=sync(db_path,config)
        print(json.dumps(dict(**summary(db_path, config), sources=sources), indent=2))
        return
    with connect(db_path):pass
    state=ImportState(db_path,config)
    state.start()

    class Handler(BaseHTTPRequestHandler):
        def send(self, status, body, kind='application/json'):
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if urlsplit(self.path).path == '/api/usage':
                try:
                    query=parse_qs(urlsplit(self.path).query)
                    filters={k:query[k][0] for k in ('start','end','provider','model','role','compare') if query.get(k)}
                    today=dt.datetime.now(ZoneInfo(config.get('timezone','America/Los_Angeles'))).date().isoformat()
                    filters.update(validated_range(filters,today))
                    if query.get('project'):filters['projects']=query['project']
                    self.send(200,json.dumps(usage_view(db_path,config,filters,state)).encode())
                except (ValueError,OverflowError) as error:
                    self.send(400,json.dumps({'error':str(error)}).encode())
            elif self.path == '/api/state':
                self.send(200,json.dumps(state.snapshot()).encode())
            elif self.path in ('/share.js', '/vendor/html-to-image.js'):
                self.send(200, (BASE / self.path.lstrip('/')).read_bytes(), 'application/javascript; charset=utf-8')
            elif self.path == '/':
                self.send(200, (BASE / 'index.html').read_bytes(), 'text/html; charset=utf-8')
            else:
                self.send(404, b'{}')

        def do_POST(self):
            # Local endpoint: reject cross-site requests and foreign Host headers.
            if self.headers.get('Host') not in (f'127.0.0.1:{args.port}', f'localhost:{args.port}') or self.headers.get('Origin') not in (None, f'http://127.0.0.1:{args.port}', f'http://localhost:{args.port}'):
                self.send(403, b'{}')
            elif self.path == '/api/sync':
                state.start()
                self.send(202, json.dumps(state.snapshot()).encode())
            else:
                self.send(404, b'{}')

    print(f'TokesMaGOATs → http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
