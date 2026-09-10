import tempfile
import unittest
from pathlib import Path
from app import connect, summary

class FilterTests(unittest.TestCase):
    def test_joint_filter_reconciles_all_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'usage.db'
            with connect(path) as db:
                for key,day,provider,model,session,role in [('a','09','Codex','gpt-5.6-sol','s','auditor'),('b','10','Codex','gpt-5.6-sol','s','main'),('c','10','Claude Code','claude-opus-5','t','main')]:
                    db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(key,'2026-09-'+day+'T12:00:00Z',provider,'a',session,model,role!='main',100,50,10,20,0))
                    db.execute('INSERT INTO event_roles VALUES (?,?)',(key,role))
                    db.execute('INSERT OR REPLACE INTO session_topics VALUES (?,?,?,?,?,?)',(provider,session,'Project '+session,'Title','Implementation','Session title'))
            config={'timezone':'UTC'}
            result=summary(path,config,dict(start='2026-09-09',end='2026-09-09',provider='Codex',model='gpt-5.6-sol',role='auditor',projects=['Project s']))
            self.assertEqual(result['totals']['total'],120)
            self.assertEqual(result['totals']['auditor'],120)
            self.assertEqual(sum(result['providers'].values()),120)
            self.assertEqual(result['costs']['priced_tokens'],120)
            self.assertEqual(sum(m['tokens'] for m in result['carbon']['models'].values()),120)
            self.assertEqual(sum(sum(t['days'].values()) for t in result['work']),120)
            self.assertEqual(result['available']['projects'],['Project s','Project t'])
            self.assertEqual(result['largest_day_all_time'],240)
            empty=summary(path,config,{'projects':['Missing']})
            self.assertEqual(empty['totals']['total'],0)
            self.assertEqual(empty['costs']['usd'],0)
    def test_null_and_string_models_coexist(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'usage.db'
            with connect(path) as db:
                for key,model in [('a',None),('b','gpt-5.6-sol')]:
                    db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(key,'2026-09-10T12:00:00Z','Codex','a','s',model,0,10,0,0,0,0))
            result=summary(path,{'timezone':'UTC'})
            self.assertEqual(result['available']['models'],['gpt-5.6-sol','unknown'])
            self.assertEqual(result['costs']['unpriced_tokens'],10)
    def test_defaults_are_validated_as_effective_range(self):
        from app import validated_range
        for query in ({'start':'2027-01-01'},{'end':'2025-12-31'},{'end':'2026-09-11'}):
            with self.assertRaises(ValueError):validated_range(query,'2026-09-10')
        self.assertEqual(validated_range({'start':'2026-09-01'},'2026-09-10'),{'start':'2026-09-01','end':'2026-09-10'})
    def test_calendar_month_and_equal_period_comparisons(self):
        from app import comparison_range
        self.assertEqual(comparison_range({'start':'2026-03-01','end':'2026-03-10','compare':'month'}),{'start':'2026-02-01','end':'2026-02-28','kind':'month'})
        self.assertEqual(comparison_range({'start':'2026-03-01','end':'2026-03-10'}),{'start':'2026-02-19','end':'2026-02-28','kind':'previous'})
    def test_future_records_do_not_seed_date_presets(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'usage.db'
            with connect(path) as db:
                db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',('future','2999-01-01T00:00:00Z','Codex','a','s','unknown',0,10,0,0,0,0))
            result=summary(path,{'timezone':'UTC'})
            self.assertEqual(result['available']['years'],[])
            for dimension in ('providers','models','projects'):
                self.assertEqual(result['available'][dimension],[])
            self.assertIsNone(result['available']['first'])
