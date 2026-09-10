"""Local project and title-based work grouping. No model calls or transcript upload."""
import json
import re
from pathlib import Path


def project_name(cwd):
    if not cwd:
        return 'Unassigned'
    path = str(cwd).replace('\\', '/')
    path = path.split('/.claude/worktrees/')[0]
    parts = [p for p in path.split('/') if p]
    if '.codex' in parts:
        i = parts.index('.codex')
        if parts[i+1:i+2] == ['worktrees'] and len(parts) > i+3:
            return parts[i+3]
    if 'GitHub' in parts:
        i = parts.index('GitHub')
        # Organization folders contain repositories one level below.
        rest = parts[i+1:]
        if rest and rest[0] == 'SQP' and len(rest) > 1:
            return rest[1]
        if rest:
            return 'TokesMaGOATs' if rest[0].lower() == 'tokesmagoats' else rest[0]
    if 'Codex' in parts and any(re.fullmatch(r'\d{4}-\d{2}-\d{2}', p) for p in parts):
        return 'Standalone tasks'
    return parts[-1] if parts and parts[-1] not in ('ljf', 'Users') else 'Unassigned'


def activity(title):
    text = title.lower()
    rules = [
        ('Reviews & audits', r'^(?:\$[\w:-]*snipe|review\b|audit\b|re-audit\b|verify\b|assess\b)'),
        ('Fixes & reliability', r'\b(fix|debug|bug|regression|failure|repair|diagnose|broken)\w*\b'),
        ('Implementation', r'\b(implement|build|add|create|refactor|migrate|feature)\w*\b'),
        ('Research & planning', r'\b(research|analy[sz]e|investigate|plan|design|explore|compare|strategy)\w*\b'),
        ('Setup & maintenance', r'\b(setup|set up|install|configur|sync|updat|renam|deploy|release|commit|push)\w*\b'),
        ('Reviews & audits', r'\b(review|audit|snipe)\w*\b'),
    ]
    return next((label for label, pattern in rules if re.search(pattern, text)), 'Unclassified work')


def rows(path, tail=False):
    try:
        with path.open('rb') as stream:
            if tail:
                stream.seek(max(0, path.stat().st_size - 65536))
            for i, line in enumerate(stream):
                if not tail and i >= 40:
                    break
                try:
                    value = json.loads(line)
                    if isinstance(value, dict):
                        yield value
                except (ValueError, UnicodeDecodeError):
                    continue
    except OSError:
        return


def contexts(config):
    result = {}
    for source in config['sources']:
        provider, root = source['provider'], Path(source['path']).expanduser()
        titles = {}
        if provider == 'Codex':
            index = root.parent / 'session_index.jsonl'
            try:
                with index.open() as stream:
                    for line in stream:
                        try:
                            x = json.loads(line)
                            titles[x['id']] = x.get('thread_name', '')
                        except (ValueError, KeyError):
                            continue
            except OSError:
                pass
        files = sorted(root.rglob('*.jsonl'), key=lambda p: 'subagents' in p.parts)
        for path in files:
            if provider == 'Claude Code' and 'subagents' in path.parts:
                session = path.parts[path.parts.index('subagents')-1]
                if (provider, session) in result:
                    continue
            head = list(rows(path))
            if provider == 'Codex':
                meta = next((x.get('payload', {}) for x in head if x.get('type') == 'session_meta'), {})
                session = meta.get('id')
                if not session:
                    continue
                source_meta = meta.get('source') or {}
                parent = source_meta.get('subagent', {}).get('thread_spawn', {}).get('parent_thread_id') if isinstance(source_meta, dict) else None
                title = titles.get(session, '')
                result[(provider, session)] = dict(project=project_name(meta.get('cwd')), title=title, parent=parent, basis='Session title' if title else 'Project folder')
            else:
                meta = next((x for x in head if x.get('sessionId') and x.get('cwd')), {})
                session = meta.get('sessionId')
                if not session:
                    continue
                title, basis = '', 'Project folder'
                for x in head + list(rows(path, tail=True)):
                    candidate = x.get('customTitle') if x.get('type') == 'custom-title' else x.get('summary') if x.get('type') == 'summary' else None
                    if isinstance(candidate, str) and candidate.strip():
                        title, basis = candidate.strip()[:200], 'Saved title/summary'
                # Only a short label from a plain user request, never an entire prompt.
                if not title:
                    for x in head:
                        message = x.get('message') or {}
                        text = message.get('content')
                        if x.get('type') == 'user' and isinstance(text, str) and text.strip() and not text.lstrip().startswith(('<', '#', '[{')):
                            title, basis = ' '.join(text.split())[:140], 'Opening request excerpt'
                            break
                key = (provider, session)
                if key not in result or 'subagents' not in path.parts:
                    result[key] = dict(project=project_name(meta.get('cwd')), title=title, parent=None, basis=basis)
    # Child work belongs to its root task, not a generic auditor/subagent name.
    for key in result:
        current, seen = key, set()
        while current in result and result[current].get('parent') and current not in seen:
            seen.add(current)
            parent = (key[0], result[current]['parent'])
            if parent not in result:
                break
            current = parent
        if current != key and current in result:
            result[key] = dict(result[current], basis='Inherited parent task', parent=None)
    for value in result.values():
        value['activity'] = activity(value['title'])
    return result
