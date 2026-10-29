"""Exercise the actual loopback handlers, including the read-side privacy boundary."""
import copy
import csv
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request


class EngineeringHTTPTests(unittest.TestCase):
    def setUp(self):
        cls=self
        cls.tmp=tempfile.TemporaryDirectory(); cls.root=Path(cls.tmp.name)
        (cls.root/'config.json').write_text(json.dumps(dict(timezone='UTC',sources=[],snipe_results=[],snipe_search_roots=[])))
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));cls.port=listener.getsockname()[1]
        cls.base='http://127.0.0.1:'+str(cls.port)
        script="""import app,engineering,sys,time
from pathlib import Path
from contextlib import contextmanager
original=app.connect
@contextmanager
def delayed_commit(path):
    with original(path) as db:
        yield db
        if db.in_transaction: time.sleep(.05)
app.connect=delayed_commit
app.BASE=Path(sys.argv[1])
original_now=engineering.now
engineering.now=lambda: (app.BASE/'clock.txt').read_text().strip() if (app.BASE/'clock.txt').exists() else original_now()
sys.argv=["app.py","--port",sys.argv[2]]
app.main()
"""
        cls.server=subprocess.Popen([sys.executable,'-c',script,str(cls.root),str(cls.port)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.base+'/api/state',timeout=.2).close();break
            except (OSError,urllib.error.URLError):time.sleep(.03)
        else:raise RuntimeError('Fixture server did not start')
    def tearDown(self):
        cls=self
        cls.server.terminate();cls.server.communicate(timeout=5);cls.tmp.cleanup()
    def request(self,path,body=None,host=None,origin=None):
        headers={}
        if host:headers['Host']=host
        if origin:headers['Origin']=origin
        if body is not None:headers['Content-Type']='application/json'
        request=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(request,timeout=5) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as error:return error.code,json.load(error)
    def displayed(self,filters):
        code,result=self.request('/api/usage?'+urllib.parse.urlencode(filters,doseq=True))
        self.assertEqual(code,200)
        return result['engineering']
    def export(self,filters,privacy=True):
        report=self.displayed(filters)
        return self.request('/api/engineering/export',dict(report_id=report['report_id'],privacy=privacy))
    def test_foreign_host_cannot_read_private_evidence(self):
        for path in ('/api/usage','/api/engineering/assessment','/api/engineering/input-selection','/api/state'):
            with self.subTest(path=path):self.assertEqual(self.request(path,host='attacker.example:'+str(self.port))[0],403)
        for hostname in ('localhost','127.0.0.1'):
            self.assertEqual(self.request('/api/engineering/assessment',host=hostname+':'+str(self.port))[0],200)
    def test_post_scope_and_schema_validation(self):
        self.assertEqual(self.request('/api/engineering/import',{},origin='https://foreign.example')[0],403)
        self.assertEqual(self.request('/api/engineering/input-selection',{},origin='https://foreign.example')[0],403)
        for body in ({},[],{'filters':[],'privacy':True},{'filters':{'projects':'private'},'privacy':True},{'filters':{},'privacy':'yes'}):
            with self.subTest(body=body):self.assertEqual(self.request('/api/engineering/export',body)[0],400)
        self.assertEqual(self.request('/api/engineering/import',[])[0],400)
    def test_export_accepts_the_actual_applied_selection_shape(self):
        applied=dict(start='2026-01-01',end='2026-01-03',provider='',model='',role='',compare='previous',projects=[])
        status,result=self.export(applied)
        self.assertEqual(status,200)
        self.assertEqual(result['report']['selection']['start'],applied['start'])
        self.assertNotIn('provider',result['report']['selection'])
        self.assertEqual(result['report']['selection']['project_count'],0)
        self.assertIn('metadata_json',result['csv'])

    def test_export_is_frozen_and_public(self):
        code,result=self.export({'start':'2026-01-01','end':'2026-01-03'})
        self.assertEqual(code,200);self.assertTrue(result['report']['privacy_mode']);self.assertIn('metadata_json',result['csv'])
        import sqlite3
        with sqlite3.connect(self.root/'data/usage.sqlite3') as db:
            row=db.execute('SELECT body FROM engineering_reports WHERE id=?',(result['id'],)).fetchone()
            self.assertIsNotNone(row, 'Success must follow the durable commit')
            frozen=row[0]
        self.assertEqual(json.loads(frozen),result['report'])

    def test_effort_filter_is_shared_by_usage_and_export(self):
        filters=dict(start='2026-01-01',end='2026-01-03',effort_threshold='0.10',comparison_hours='12')
        code,usage=self.request('/api/usage?'+urllib.parse.urlencode(filters));self.assertEqual(code,200)
        code,result=self.export(filters);self.assertEqual(code,200)
        self.assertEqual(usage['engineering']['day_filter'],dict(threshold=.1,comparison_hours=12,basis='central'))
        self.assertEqual(result['report']['day_filter'],usage['engineering']['day_filter'])
        for key,value in [('effort_threshold','nan'),('effort_threshold','inf'),('effort_threshold','-0.01'),('effort_threshold','0.51'),('comparison_hours','5')]:
            bad=dict(filters,**{key:value})
            with self.subTest(key=key,value=value):
                self.assertEqual(self.request('/api/usage?'+urllib.parse.urlencode(bad))[0],400)
                self.assertEqual(self.request('/api/engineering/export',dict(filters=bad,privacy=True))[0],400)

    def test_timer_settings_and_missing_inputs_are_explicit_in_reports(self):
        filters=dict(start='2026-01-01',end='2026-01-03',effort_scenario='high',idle_timeout='10',input_population='inclusive')
        code,usage=self.request('/api/usage?'+urllib.parse.urlencode(filters));self.assertEqual(code,200)
        code,export=self.export(filters);self.assertEqual(code,200)
        timer=export['report']['message_timer']
        self.assertEqual(timer['options'],dict(effort_scenario='high',idle_timeout=10,input_population='inclusive'))
        self.assertEqual(timer['options'],usage['engineering']['message_timer']['options'])
        self.assertEqual(timer['cohort']['dates'],[])
        self.assertIsNone(timer['sensitivity']['inclusive']['10']['scenarios']['high']['pooled'])
        self.assertIn('message_timer_json',export['csv'])
        for key,value in [('effort_scenario','extreme'),('idle_timeout','0'),('idle_timeout','5.0'),('input_population','all')]:
            bad=dict(filters,**{key:value})
            with self.subTest(key=key,value=value):
                self.assertEqual(self.request('/api/usage?'+urllib.parse.urlencode(bad))[0],400)
                self.assertEqual(self.request('/api/engineering/export',dict(filters=bad,privacy=True))[0],400)

    def test_input_choices_persist_without_reclassifying_and_exports_pin_the_version(self):
        import app,human_inputs
        records=[dict(type='user',uuid='ambiguous-api',timestamp='2026-01-01T09:03:00Z',sessionId='private-api-session',
                      message=dict(role='user',content='PRIVATE API PROMPT')),
                 dict(type='user',uuid='excluded-api',timestamp='2026-01-01T09:04:00Z',sessionId='private-api-session',origin=dict(kind='agent'),
                      message=dict(role='user',content='PRIVATE AGENT INPUT'))]
        path=self.root/'api-inputs.jsonl';path.write_text(''.join(json.dumps(row)+'\n' for row in records))
        with app.connect(self.root/'data/usage.sqlite3') as db:
            human_inputs.save(db,path,'Claude Code',records)
        code,current=self.request('/api/engineering/input-selection');self.assertEqual(code,200)
        payload=dict(base_version=current['selection']['version'],entries=[dict(id='Claude Code:ambiguous-api',rationale='PRIVATE CHOICE REASON')])
        code,saved=self.request('/api/engineering/input-selection',payload);self.assertEqual(code,200)
        version=saved['selection']['version']
        self.assertEqual(saved['resolution']['valid_ids'],['Claude Code:ambiguous-api'])
        self.assertNotIn('PRIVATE CHOICE REASON',json.dumps(saved['resolution']))
        self.assertEqual(self.request('/api/engineering/input-selection',payload)[0],400)
        code,cleared=self.request('/api/engineering/input-selection',dict(base_version=version,entries=[]));self.assertEqual(code,200)
        self.assertEqual(cleared['resolution']['ids'],[])
        filters=dict(start='2026-01-01',end='2026-01-03',input_population='selected',input_selection_version=str(version))
        code,frozen=self.export(filters);self.assertEqual(code,200)
        self.assertEqual(frozen['report']['message_timer']['selection']['ids'],['Claude Code:ambiguous-api'])
        self.assertEqual(frozen['report']['message_timer']['selection']['version'],version)
        self.assertNotIn('PRIVATE',json.dumps(frozen['report']))
        code,restored=self.request('/api/engineering/input-selection',dict(base_version=cleared['selection']['version'],entries=saved['selection']['entries']));self.assertEqual(code,200)
        self.assertEqual(restored['resolution']['valid_ids'],saved['resolution']['valid_ids'])
        self.assertEqual(self.request('/api/engineering/input-selection',dict(base_version=restored['selection']['version'],entries=[dict(id='Claude Code:excluded-api')]))[0],400)
        with app.connect(self.root/'data/usage.sqlite3') as db:
            inputs={event['id']:event for event in human_inputs.inventory(db)['events']}
        self.assertEqual(inputs['Claude Code:ambiguous-api']['classification'],'ambiguous')
        code,reset=self.request('/api/engineering/input-selection',dict(base_version=restored['selection']['version'],entries=[]));self.assertEqual(code,200)
        self.assertEqual(reset['resolution']['valid_ids'],[])

    def test_applied_snapshot_survives_time_evidence_assessment_and_choice_changes(self):
        import app,engineering,human_inputs,sqlite3
        from test_engineering import EngineeringTests
        fixture=EngineeringTests();fixture.setUp()
        self.addCleanup(fixture.tearDown)
        engineering.import_assessment(fixture.db,fixture.doc,'UTC')
        fixture.db.execute('INSERT INTO session_topics VALUES (?,?,?,?,?,?)',('Claude Code','PRIVATE_HTTP_CHAT','Example','','','fixture'))
        records=[dict(type='user',uuid='supported-'+day,timestamp='2026-01-'+day+'T13:00:00Z',sessionId='PRIVATE_HTTP_CHAT',origin=dict(kind='human'),message=dict(role='user',content='PRIVATE_HTTP_PROMPT')) for day in ('01','02')]
        records.append(dict(type='user',uuid='ambiguous',timestamp='2026-01-02T13:00:30Z',sessionId='PRIVATE_HTTP_CHAT',message=dict(role='user',content='PRIVATE_HTTP_PROMPT')))
        source=fixture.root/'http-inputs.jsonl';source.write_text(''.join(json.dumps(r)+'\n' for r in records))
        human_inputs.save(fixture.db,source,'Claude Code',records);fixture.db.commit()
        with sqlite3.connect(self.root/'data/usage.sqlite3') as target:fixture.db.backup(target)
        self.request('/api/engineering/input-selection',dict(base_version=0,entries=[dict(id='Claude Code:ambiguous')]))
        clock=self.root/'clock.txt';clock.write_text('2026-01-02T13:01:00Z')
        filters=dict(start='2026-01-01',end='2026-01-03',input_population='selected')
        applied=self.displayed(filters)
        self.assertEqual(applied['message_timer']['cohort']['dates'],['2026-01-01','2026-01-02'])
        selected=applied['message_timer']['sensitivity']['selected']['5']
        self.assertAlmostEqual(selected['denominator_hours'],.1)
        self.assertEqual(selected['scenarios']['central']['numerator_hours'],32)
        self.assertAlmostEqual(selected['scenarios']['central']['pooled'],320)
        self.assertTrue('report_id' in applied,'The displayed calculation must identify its immutable export snapshot')
        clock.write_text('2026-01-02T13:04:00Z')
        advanced=self.displayed(filters)
        self.assertAlmostEqual(advanced['message_timer']['sensitivity']['selected']['5']['denominator_hours'],.15)
        self.assertNotEqual(applied['report_id'],advanced['report_id'])
        records.append(dict(type='user',uuid='supported-03',timestamp='2026-01-03T13:00:00Z',sessionId='PRIVATE_HTTP_CHAT',origin=dict(kind='human'),message=dict(role='user',content='PRIVATE_HTTP_PROMPT')))
        source.write_text(''.join(json.dumps(r)+'\n' for r in records))
        changed=copy.deepcopy(fixture.doc);changed['version']=2
        changed['work_items'][0]['effort'].update(hours_low=8,hours_central=16,hours_high=32)
        with app.connect(self.root/'data/usage.sqlite3') as db:
            human_inputs.save(db,source,'Claude Code',records)
            engineering.import_assessment(db,changed,'UTC')
        self.request('/api/engineering/input-selection',dict(base_version=1,entries=[]))
        clock.write_text('2026-01-03T13:04:00Z')
        newest=self.displayed(filters)
        self.assertEqual(newest['assessment_version'],2)
        self.assertEqual(newest['message_timer']['cohort']['dates'],['2026-01-01','2026-01-02','2026-01-03'])
        self.assertEqual(newest['message_timer']['selection']['version'],2)
        for privacy in (True,False,True):
            code,result=self.request('/api/engineering/export',dict(report_id=applied['report_id'],privacy=privacy))
            self.assertEqual(code,200)
            expected=engineering.export_report(applied,privacy)
            self.assertEqual(result['report'],expected,'Export must preserve every displayed calculation field')
            metadata=json.loads(next(csv.reader(io.StringIO(result['csv'])))[1])
            for key in ('cutoff','assessment_version','assessment_cutoff','message_timer','sensitivity','full_days','weekly'):
                self.assertEqual(metadata[key],expected[key],key)
            self.assertNotIn('PRIVATE_HTTP',json.dumps(result))
            with sqlite3.connect(self.root/'data/usage.sqlite3') as db:
                self.assertEqual(json.loads(db.execute('SELECT body FROM engineering_reports WHERE id=?',(result['id'],)).fetchone()[0]),result['report'])

    def test_snapshot_validation_expiration_and_bounded_storage(self):
        import app
        report=self.displayed(dict(start='2026-01-01',end='2026-01-03'))
        for identifier in (None,True,{},'', 'x'*64,'a'*63):
            code,error=self.request('/api/engineering/export',dict(report_id=identifier,privacy=True))
            self.assertEqual(code,400);self.assertEqual(error['error'],'Invalid report ID')
        code,error=self.request('/api/engineering/export',dict(report_id='0'*64,privacy=True))
        self.assertEqual(code,400);self.assertIn('refresh',error['error'].lower())
        self.assertEqual(self.request('/api/engineering/export',dict(report_id=report['report_id'],privacy='yes'))[0],400)
        self.assertEqual(self.request('/api/engineering/export',dict(report_id=report['report_id'],privacy=True,filters={}))[0],400)
        cache=app.ReportPreviews()
        first=cache.remember(report)
        for second in range(33):
            altered=dict(report,cutoff='2026-01-04T00:00:%02dZ'%second)
            last=cache.remember(altered)
        with self.assertRaisesRegex(ValueError,'[Rr]efresh'):cache.get(first)
        self.assertEqual(cache.get(last)['cutoff'],'2026-01-04T00:00:32Z')
        cache=app.ReportPreviews();first=cache.remember(report)
        others=[cache.remember(dict(report,cutoff='2026-01-04T00:00:%02dZ'%second)) for second in range(31)]
        self.assertEqual(cache.remember(report),first)
        cache.remember(dict(report,cutoff='2026-01-04T00:00:32Z'))
        try:retained=cache.get(first)
        except ValueError:self.fail('Redisplaying an existing snapshot must preserve its recency in the bounded cache')
        self.assertEqual(retained['cutoff'],report['cutoff'])
        with self.assertRaisesRegex(ValueError,'[Rr]efresh'):cache.get(others[0])


if __name__=='__main__':unittest.main()
