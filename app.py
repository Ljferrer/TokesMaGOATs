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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo
from carbon import estimate as estimate_carbon

BASE = Path(__file__).resolve().parent
LOCK = threading.Lock()


def connect(path):
    db = sqlite3.connect(path)
    db.executescript('''
    CREATE TABLE IF NOT EXISTS events (
      id TEXT PRIMARY KEY, timestamp TEXT, provider TEXT, account TEXT,
      session TEXT, model TEXT, subagent INTEGER, input INTEGER,
      cached INTEGER, cache_write INTEGER, output INTEGER, reasoning INTEGER);
    CREATE TABLE IF NOT EXISTS event_roles (id TEXT PRIMARY KEY, role TEXT);
    CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, stamp TEXT);
    ''')
    return db


def number(u, key):
    return max(0, int(u.get(key) or 0))


def event(key, timestamp, provider, account, session, model, subagent, u):
    cached = number(u, 'cached_input_tokens' if provider == 'Codex' else 'cache_read_input_tokens')
    write = number(u, 'cache_write_input_tokens' if provider == 'Codex' else 'cache_creation_input_tokens')
    inp = number(u, 'input_tokens')
    # Anthropic reports cache reads/writes separately; OpenAI input includes cache.
    if provider != 'Codex':
        inp += cached + write
    return (provider + ':' + key, timestamp, provider, account, session, model,
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


def summary(db_path, config):
    zone = ZoneInfo(config.get('timezone', 'America/Los_Angeles'))
    days, providers, accounts, models = {}, {}, {}, {}
    total = dict(input=0, output=0, cached=0, cache_write=0, reasoning=0, total=0, subagent=0, auditor=0, other=0, responses=0)
    sessions = set()
    carbon_groups = {}
    with connect(db_path) as db:
        for row in db.execute('SELECT events.*, event_roles.role FROM events LEFT JOIN event_roles USING(id)'):
            _, timestamp, provider, account, session, model, sub, inp, cache, write, out, reasoning, recorded_role = row
            try:
                day = dt.datetime.fromisoformat(timestamp.replace('Z', '+00:00')).astimezone(zone).date().isoformat()
            except (ValueError, AttributeError):
                continue
            usage = carbon_groups.setdefault((day, model), dict(input=0, cached=0, output=0))
            for key, value in (('input', inp), ('cached', cache), ('output', out)):
                usage[key] += value
            n = inp + out
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
                carbon=estimate_carbon(carbon_groups, config.get('carbon')),
                sessions=len(sessions), timezone=str(zone), today=dt.datetime.now(zone).date().isoformat())


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
    state = {'sources': sync(db_path, config)}
    if args.sync:
        print(json.dumps(dict(**summary(db_path, config), **state), indent=2))
        return

    class Handler(BaseHTTPRequestHandler):
        def send(self, status, body, kind='application/json'):
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/api/usage':
                self.send(200, json.dumps(dict(**summary(db_path, config), **state)).encode())
            elif self.path == '/':
                self.send(200, (BASE / 'index.html').read_bytes(), 'text/html; charset=utf-8')
            else:
                self.send(404, b'{}')

        def do_POST(self):
            # Local endpoint: reject cross-site requests and foreign Host headers.
            if self.headers.get('Host') not in (f'127.0.0.1:{args.port}', f'localhost:{args.port}') or self.headers.get('Origin') not in (None, f'http://127.0.0.1:{args.port}', f'http://localhost:{args.port}'):
                self.send(403, b'{}')
            elif self.path == '/api/sync':
                state['sources'] = sync(db_path, config)
                self.send(200, json.dumps(state).encode())
            else:
                self.send(404, b'{}')

    print(f'TokesMaGOATs → http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
