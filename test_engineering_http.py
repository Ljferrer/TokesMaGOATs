"""Exercise the actual loopback handlers, including the read-side privacy boundary."""
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
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(); cls.root=Path(cls.tmp.name)
        (cls.root/'config.json').write_text(json.dumps(dict(timezone='UTC',sources=[],snipe_results=[],snipe_search_roots=[])))
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));cls.port=listener.getsockname()[1]
        cls.base='http://127.0.0.1:'+str(cls.port)
        script="""import app,sys,time
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
sys.argv=["app.py","--port",sys.argv[2]]
app.main()
"""
        cls.server=subprocess.Popen([sys.executable,'-c',script,str(cls.root),str(cls.port)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.base+'/api/state',timeout=.2).close();break
            except (OSError,urllib.error.URLError):time.sleep(.03)
        else:raise RuntimeError('Fixture server did not start')
    @classmethod
    def tearDownClass(cls):
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
    def test_foreign_host_cannot_read_private_evidence(self):
        for path in ('/api/usage','/api/engineering/assessment','/api/state'):
            with self.subTest(path=path):self.assertEqual(self.request(path,host='attacker.example:'+str(self.port))[0],403)
        for hostname in ('localhost','127.0.0.1'):
            self.assertEqual(self.request('/api/engineering/assessment',host=hostname+':'+str(self.port))[0],200)
    def test_post_scope_and_schema_validation(self):
        self.assertEqual(self.request('/api/engineering/import',{},origin='https://foreign.example')[0],403)
        for body in ({},[],{'filters':[],'privacy':True},{'filters':{'projects':'private'},'privacy':True},{'filters':{},'privacy':'yes'}):
            with self.subTest(body=body):self.assertEqual(self.request('/api/engineering/export',body)[0],400)
        self.assertEqual(self.request('/api/engineering/import',[])[0],400)
    def test_export_accepts_the_actual_applied_selection_shape(self):
        applied=dict(start='2026-01-01',end='2026-01-03',provider='',model='',role='',compare='previous',projects=[])
        status,result=self.request('/api/engineering/export',dict(filters=applied,privacy=True))
        self.assertEqual(status,200)
        self.assertEqual(result['report']['selection']['start'],applied['start'])
        self.assertNotIn('provider',result['report']['selection'])
        self.assertEqual(result['report']['selection']['project_count'],0)
        self.assertIn('metadata_json',result['csv'])

    def test_export_is_frozen_and_public(self):
        code,result=self.request('/api/engineering/export',{'filters':{'start':'2026-01-01','end':'2026-01-03'},'privacy':True})
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
        code,result=self.request('/api/engineering/export',dict(filters=filters,privacy=True));self.assertEqual(code,200)
        self.assertEqual(usage['engineering']['day_filter'],dict(threshold=.1,comparison_hours=12,basis='central'))
        self.assertEqual(result['report']['day_filter'],usage['engineering']['day_filter'])
        for key,value in [('effort_threshold','nan'),('effort_threshold','inf'),('effort_threshold','-0.01'),('effort_threshold','0.51'),('comparison_hours','5')]:
            bad=dict(filters,**{key:value})
            with self.subTest(key=key,value=value):
                self.assertEqual(self.request('/api/usage?'+urllib.parse.urlencode(bad))[0],400)
                self.assertEqual(self.request('/api/engineering/export',dict(filters=bad,privacy=True))[0],400)


if __name__=='__main__':unittest.main()
