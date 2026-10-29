import json
import tempfile
import unittest
from pathlib import Path
from app import sync, summary

class SnipeUsageTests(unittest.TestCase):
    def test_ephemeral_results_count_once_and_native_history_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=root/'usage.db';logs=root/'logs';logs.mkdir()
            thread='01a08d4d-27c0-75e2-b029-534c0d9ae24a'
            events=[{'type':'thread.started','thread_id':thread},{'type':'turn.completed','usage':{'input_tokens':100,'cached_input_tokens':80,'output_tokens':20}}]
            result={'request':{'profile':{'model':'gpt-5.6-sol'},'scope':{'repository':'/repo/Example'}},'seats':[{'seat':1,'lens':'correctness','stdout':'\n'.join(map(json.dumps,events))}]}
            for name in ('snipe-result.json','snipe-copy.json'):(root/name).write_text(json.dumps(result))
            config={'timezone':'America/Los_Angeles','sources':[{'provider':'Codex','path':str(logs)}],'snipe_results':[str(root/'*snipe*.json')]}
            sync(db,config);sync(db,config);r=summary(db,config)
            self.assertEqual(r['days']['2026-09-10']['auditor'],120)
            self.assertEqual(r['totals']['total'],120)
            self.assertEqual(r['totals']['cached'],80)
            self.assertEqual(r['work'][0]['project'],'Example')
            for path in root.glob('*snipe*.json'):path.unlink()
            # Later native records replace the aggregate rather than doubling it.
            (logs/'native.jsonl').write_text(json.dumps({'type':'token_usage_record','timestamp':'2026-09-10T22:00:00Z','payload':{'response_id':'native','thread_id':thread,'usage':{'input_tokens':100,'output_tokens':20}}})+'\n')
            sync(db,config);r=summary(db,config)
            self.assertEqual(r['totals']['total'],120)
            self.assertEqual(r['totals']['auditor'],120)

    def test_recursive_discovery_spans_dates_and_reports_missing_counters(self):
        from snipe_usage import results
        import datetime as dt
        import uuid
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);nested=root/'project/docs/snipe';nested.mkdir(parents=True)
            for day in (8,9,10):
                ms=int(dt.datetime(2026,9,day,20,tzinfo=dt.timezone.utc).timestamp()*1000)
                thread=str(uuid.UUID(int=(ms<<80)|(7<<76)|(2<<62)|day))
                stdout='\n'.join(map(json.dumps,[{'type':'thread.started','thread_id':thread},{'type':'turn.completed','usage':{'input_tokens':100,'output_tokens':20}}]))
                result={'request':{'profile':{'model':'gpt-5.6-sol'},'scope':{'repository':'/repo/Example'}},'seats':[{'seat':1,'lens':'correctness','stdout':stdout}]}
                (nested/f'{day}.json').write_text(json.dumps(result))
            del result['seats'][0]['stdout']
            for name in ('summary.json','summary-copy.json'):(nested/name).write_text(json.dumps(result))
            coverage={};rows=list(results([], [str(root)], coverage))
            self.assertEqual(len(rows),3)
            self.assertEqual({row[3][:10] for row in rows},{'2026-09-08','2026-09-09','2026-09-10'})
            self.assertEqual(coverage['results_without_usage'],1)

    def test_tool_output_recovery_deduplicates_file_and_ignores_quoted_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);logs=root/'logs';logs.mkdir();db=root/'usage.db'
            stdout='\n'.join(map(json.dumps,[{'type':'thread.started','thread_id':'01a08d4d-27c0-75e2-b029-534c0d9ae24a'},{'type':'turn.completed','usage':{'input_tokens':100,'output_tokens':20}}]))
            result={'request':{'profile':{'model':'gpt-5.6-sol'},'scope':{'repository':'/repo/Example'}},'seats':[{'seat':1,'stdout':stdout}]}
            wrapped=[{'type':'input_text','text':json.dumps({'chunk_id':'x','output':json.dumps(result)})}]
            row={'type':'response_item','payload':{'type':'custom_tool_call_output','output':wrapped}}
            (logs/'parent.jsonl').write_text(json.dumps(row)+'\n')
            config={'timezone':'UTC','sources':[{'provider':'Codex','path':str(logs)}],'snipe_results':[str(root/'snipe.json')]}
            sync(db,config)
            self.assertEqual(summary(db,config)['totals']['auditor'],120)
            (root/'snipe.json').write_text(json.dumps(result));sync(db,config)
            self.assertEqual(summary(db,config)['totals']['auditor'],120)
            from snipe_usage import saved_results
            row['payload']['type']='function_call';(logs/'parent.jsonl').write_text(json.dumps(row)+'\n')
            self.assertEqual(list(saved_results([],[],[logs])),[])
