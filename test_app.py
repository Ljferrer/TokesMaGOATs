import json
from pathlib import Path
import tempfile
import unittest
from app import records, sync, summary

class UsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / 'usage.db'
    def tearDown(self):
        self.tmp.cleanup()
    def write(self, name, rows):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
        return p
    def config(self, provider):
        return {'timezone':'America/Los_Angeles','sources':[{'provider':provider,'path':str(self.root)}]}
    def test_claude_stream_duplicates_subagents_and_midnight(self):
        x={'type':'assistant','timestamp':'2026-09-10T01:00:00Z','sessionId':'parent','message':{'id':'m1','model':'test','usage':{'input_tokens':10,'cache_read_input_tokens':20,'cache_creation_input_tokens':5,'output_tokens':3}}}
        p=self.write('subagents/a.jsonl',[x,x])
        self.write('copy.jsonl',[x])
        config=self.config('Claude Code')
        sync(self.db,config);sync(self.db,config)
        s=summary(self.db,config)
        self.assertEqual(s['totals']['total'],38)
        self.assertEqual(s['totals']['subagent'],38)
        self.assertEqual(s['totals']['responses'],1)
        self.assertEqual(s['days']['2026-09-09']['total'],38)
        x['message']['usage']['output_tokens']=8
        self.write('subagents/a.jsonl',[x])
        sync(self.db,config)
        self.assertEqual(summary(self.db,config)['totals']['total'],43)
    def test_codex_response_dedup_and_cache_subset(self):
        x={'type':'token_usage_record','timestamp':'2026-09-09T12:00:00Z','payload':{'response_id':'resp1','thread_id':'t1','usage':{'input_tokens':100,'cached_input_tokens':80,'output_tokens':10,'reasoning_output_tokens':5}}}
        self.write('a.jsonl',[x,x]);self.write('archive.jsonl',[x])
        sync(self.db,self.config('Codex'))
        s=summary(self.db,self.config('Codex'))
        self.assertEqual(s['totals']['total'],110)
        self.assertEqual(s['totals']['responses'],1)
    def test_copied_parent_usage_is_not_subagent_usage(self):
        meta={'type':'session_meta','payload':{'id':'child','source':{'subagent':{}}}}
        parent={'type':'token_usage_record','timestamp':'2026-09-09T12:00:00Z','payload':{'response_id':'parent-response','thread_id':'parent','usage':{'input_tokens':100}}}
        child={'type':'token_usage_record','timestamp':'2026-09-09T12:01:00Z','payload':{'response_id':'child-response','thread_id':'child','usage':{'input_tokens':50}}}
        self.write('child.jsonl',[meta,parent,child])
        self.write('parent.jsonl',[parent])
        sync(self.db,self.config('Codex'))
        s=summary(self.db,self.config('Codex'))
        self.assertEqual(s['totals']['total'],150)
        self.assertEqual(s['totals']['subagent'],50)

    def test_daily_role_and_model_breakdown_reconciles(self):
        rows=[]
        for key,model,sub,tokens in [('a','alpha',False,10),('b','beta',False,20),('c','alpha',True,30)]:
            rows.append({'type':'assistant','timestamp':'2026-09-10T01:00:00Z','sessionId':'s','isSidechain':sub,'message':{'id':key,'model':model,'usage':{'input_tokens':tokens}}})
        self.write('a.jsonl',rows)
        sync(self.db,self.config('Claude Code'))
        day=summary(self.db,self.config('Claude Code'))['days']['2026-09-09']
        self.assertEqual(day['breakdown'],{'main':{'alpha':10,'beta':20},'subagent':{'alpha':30}})
        self.assertEqual(sum(sum(group.values()) for group in day['breakdown'].values()),day['total'])
        self.assertEqual(sum(day['breakdown']['subagent'].values()),day['subagent'])

    def test_legacy_cumulative_deltas(self):
        def row(n,t):return {'type':'event_msg','timestamp':t,'payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':n,'output_tokens':0}}}}
        a=row(100,'2026-09-09T12:00:00Z');b=row(140,'2026-09-10T12:00:00Z')
        p=self.write('a.jsonl',[a,a,b])
        with p.open('a') as stream:
            stream.write('{unfinished')
        sync(self.db,self.config('Codex'))
        s=summary(self.db,self.config('Codex'))
        self.assertEqual(s['totals']['total'],140)
        self.assertEqual(s['days']['2026-09-10']['total'],40)

if __name__=='__main__':unittest.main()
