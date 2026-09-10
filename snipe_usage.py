"""Recover ephemeral Snipe CLI usage from retained coordinator result JSON."""
import ast
import re
import datetime as dt
import glob
import json
import os
import tempfile
import uuid
from pathlib import Path

DEFAULT_PATTERNS = list(dict.fromkeys([str(Path('/tmp')/'*snipe*.json'), str(Path(tempfile.gettempdir())/'*snipe*.json')]))

DEFAULT_ROOTS = [str(Path.home()/'GitHub'), str(Path.home()/'.codex/worktrees'), '/tmp', tempfile.gettempdir()]


def discover(patterns, roots):
    paths={Path(p).resolve() for pattern in patterns for p in glob.glob(str(Path(pattern).expanduser()))}
    for root in roots:
        for directory, dirs, files in os.walk(Path(root).expanduser()):
            dirs[:]=[d for d in dirs if d not in {'.git','node_modules','.venv','venv','__pycache__'}]
            for name in files:
                if name.endswith('.json') and ('snipe' in name.lower() or 'snipe' in Path(directory).parts):
                    paths.add((Path(directory)/name).resolve())
    return sorted(paths)


def embedded_results(value, depth=0):
    """Decode tool transport wrappers, never execute or interpret review instructions."""
    if depth>12:return
    if isinstance(value,dict):
        if 'request' in value and 'seats' in value:
            yield value
            return
        for key in ('output','text','content'):
            if key in value:yield from embedded_results(value[key],depth+1)
    elif isinstance(value,list):
        for item in value:yield from embedded_results(item,depth+1)
    elif isinstance(value,str) and 'input_tokens' in value and 'turn.completed' in value:
        for decode in (json.loads,ast.literal_eval):
            try:parsed=decode(value)
            except (ValueError,SyntaxError,TypeError,RecursionError):continue
            if parsed!=value:
                yield from embedded_results(parsed,depth+1)
                return
        decoder=json.JSONDecoder()
        for match in re.finditer(r'\{\s*"(?:request|coordinatorGuidance|chunk_id)"\s*:',value):
            try:parsed,_=decoder.raw_decode(value,match.start())
            except ValueError:continue
            yield from embedded_results(parsed,depth+1)


def saved_results(patterns, roots, transcripts):
    for path in discover(patterns,roots):
        try:yield path,json.loads(path.read_text())
        except (OSError,ValueError):continue
    for root in transcripts:
        for path in Path(root).expanduser().rglob('*.jsonl'):
            try:
                with path.open(errors='replace') as stream:
                    for line in stream:
                        if 'turn.completed' not in line or 'input_tokens' not in line:continue
                        try:entry=json.loads(line)
                        except ValueError:continue
                        payload=entry.get('payload') or {}
                        if entry.get('type')=='response_item' and payload.get('type') in ('custom_tool_call_output','function_call_output'):
                            for result in embedded_results(payload.get('output')):yield path,result
            except OSError:continue


def results(patterns, roots=(), coverage=None, transcripts=()):
    seen_missing=set()
    for path,result in saved_results(patterns, roots, transcripts):
        try:
            request=result['request'];model=request['profile']['model'];repository=request['scope']['repository']
            if not isinstance(model,str) or not isinstance(repository,str):continue
            seats=result['seats']
            if not isinstance(seats,list):continue
            if coverage is not None and seats and not any(isinstance(seat,dict) and 'input_tokens' in seat.get('stdout','') for seat in seats):
                identity=json.dumps([request,[(seat.get('seat'),seat.get('lens')) for seat in seats if isinstance(seat,dict)]],sort_keys=True)
                seen_missing.add(identity)
                coverage['results_without_usage']=len(seen_missing)
            for seat in seats:
                thread=None;turn=0
                for line in seat.get('stdout','').splitlines():
                    try:entry=json.loads(line)
                    except ValueError:continue
                    if not isinstance(entry,dict):continue
                    if entry.get('type')=='thread.started':
                        thread=None
                        try:
                            identity=uuid.UUID(entry['thread_id'])
                            if identity.version!=7:continue
                            thread=str(identity)
                            # CLI JSON has no completion timestamps. UUIDv7 records
                            # thread start time; use that day, not the copied file's mtime.
                            timestamp=dt.datetime.fromtimestamp((identity.int>>80)/1000,dt.timezone.utc).isoformat()
                        except (ValueError,KeyError,TypeError,OverflowError):thread=None
                    elif entry.get('type')=='turn.completed' and thread:
                        usage=entry.get('usage')
                        if not isinstance(usage,dict):continue
                        keys=('input_tokens','cached_input_tokens','cache_write_input_tokens','output_tokens','reasoning_output_tokens')
                        if not all(isinstance(usage.get(k,0),int) and not isinstance(usage.get(k,0),bool) and usage.get(k,0)>=0 for k in keys):continue
                        yield path,thread,turn,timestamp,model,repository,usage
                        turn+=1
        except (OSError,ValueError,TypeError,KeyError,AttributeError):
            continue  # Incomplete live result, unrelated JSON, or unavailable file.
