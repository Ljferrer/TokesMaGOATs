import copy
import csv
import datetime as dt
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from app import connect, event, records, sync, summary
import engineering as eng
import evidence as ev


class EngineeringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name); self.repo = self.root/'repo'; self.repo.mkdir()
        self.db = connect(self.root/'ledger.sqlite3')
        self.config = dict(timezone='UTC', sources=[], engineering_personal_emails=['me@example.test'], engineering_repositories=[dict(path=str(self.repo), default_ref='refs/heads/main', project='Example')])
        self.git('init', '-b', 'main'); self.git('config', 'user.name', 'Test'); self.git('config', 'user.email', 'me@example.test')
        self.first = self.commit('a.py','x=1\n','2026-01-01T12:00:00Z')
        self.second = self.commit('b.py','y=2\n','2026-01-02T12:00:00Z')
        self.snapshot = eng.collect_repositories(self.db,self.config)[0]
        for day in ('01','02','03'):
            row=event(day,'2026-01-'+day+'T13:00:00Z','Codex','local','session','model',False,dict(input_tokens=90,output_tokens=10))
            self.db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',row)
        self.db.execute('INSERT INTO session_topics VALUES (?,?,?,?,?,?)',('Codex','session','Example','','','fixture'))
        self.doc=self.document()
    def tearDown(self):
        self.db.close(); self.temp.cleanup()
    def git(self,*args,env=None):
        result=subprocess.run(['git','-C',str(self.repo),*args],env=env,capture_output=True,text=True,check=True)
        return result.stdout.strip()
    def commit(self,path,content,date,email=None):
        (self.repo/path).write_text(content); self.git('add',path)
        env=dict(os.environ,GIT_AUTHOR_DATE=date,GIT_COMMITTER_DATE=date)
        if email:env['GIT_AUTHOR_EMAIL']=email
        self.git('commit','-m','Fixture '+path,env=env)
        return self.git('rev-parse','HEAD')
    def item(self,id,head,path,hours):
        return dict(id=id,scope='Incremental '+id,kind='engineering',credit_key=id,incremental_rationale='Only newly delivered behavior; excludes earlier work and bookkeeping',related_items=[],
                    integrations=[dict(repository=self.snapshot['repository'],head=head)],
                    allocations=[dict(repository=self.snapshot['repository'],integration=head,commit=head,paths=[path],credit='implementation',scope='New behavior',attribution_evidence=[])],
                    effort=dict(status='assessed',hours_low=hours/2,hours_central=hours,hours_high=hours*2,rationale='Manual retrospective conventional effort scenario',confidence='medium',evidence=['local-review:1'],exclusions=['No copied/generated/release/reapplied scope']),quality=[])
    def document(self):
        return dict(schema_version=1,version=1,timezone='UTC',cutoff='2026-01-04T00:00:00Z',reviewer='Human reviewer',method='manual',method_version='1',approval_status='approved',snapshots=[self.snapshot['id']],
                    work_items=[self.item('design',self.first,'a.py',8),self.item('implementation',self.second,'b.py',24)],excluded_integrations=[],
                    day_reviews=[dict(date='2026-01-'+day,status='assessed',rationale='All retained integrations reviewed; zero can include useful branch work',evidence=['review:'+day]) for day in ('01','02','03')])
    def view(self,**filters):
        return eng.view(self.db,self.config,dict(start='2026-01-01',end='2026-01-03',**filters),cutoff='2026-01-04T00:00:00Z')
    def test_synthetic_acceptance_and_sensitivity(self):
        eng.import_assessment(self.db,self.doc,'UTC'); result=self.view()
        s=result['sensitivity']['8']; c=s['scenarios']['central']
        self.assertTrue(s['complete']);self.assertEqual(s['eligible_dates'],3)
        self.assertEqual([c[k] for k in ('minimum','maximum','median','average')],[0,3,1,4/3])
        self.assertEqual(c['total_estimated_hours'],32)
        self.assertEqual(result['sensitivity']['4']['scenarios']['central']['average'],8/3)
        self.assertAlmostEqual(result['sensitivity']['12']['scenarios']['central']['average'],8/9)
        self.assertEqual(result['weekly'][0]['scenarios']['central']['engineer_days'],4)
    def test_unmapped_project_keeps_scope_unknown(self):
        self.db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',event('unmapped','2026-01-03T14:00:00Z','Codex','local','unmapped','model',False,dict(input_tokens=1,output_tokens=0)))
        eng.import_assessment(self.db,self.doc,'UTC')
        result=self.view();self.assertFalse(result['sensitivity']['8']['complete'])
        self.assertEqual(result['days'][-1]['unmapped_projects'],['Unassigned'])
        self.assertTrue(self.view(projects=['Example'])['sensitivity']['8']['complete'])
    def test_non_token_delivery_contributes_to_total_and_weekly_output(self):
        self.db.execute("DELETE FROM events WHERE id='Codex:03'")
        third=self.commit('weekend.py','weekend=1\n','2026-01-03T12:00:00Z')
        self.snapshot=eng.collect_repositories(self.db,self.config)[0];self.doc['snapshots']=[self.snapshot['id']]
        self.doc['work_items'].append(self.item('weekend',third,'weekend.py',8))
        eng.import_assessment(self.db,self.doc,'UTC');result=self.view()
        stats=result['sensitivity']['8'];c=stats['scenarios']['central']
        self.assertEqual(c['total_estimated_hours'],40);self.assertEqual(c['active_date_estimated_hours'],32)
        self.assertEqual(c['average'],2);self.assertEqual(stats['eligible_dates'],2)
        weekly=result['weekly'][0]['scenarios']['central'];self.assertEqual(weekly['engineer_days'],5)
        self.assertEqual(weekly['average_daily_equivalent'],2.5)

    def test_unknown_date_is_not_zero_or_dropped(self):
        self.doc['day_reviews'].pop();eng.import_assessment(self.db,self.doc,'UTC');result=self.view()
        s=result['sensitivity']['8']; self.assertEqual((s['eligible_dates'],s['assessed_dates']),(3,2))
        self.assertIsNone(s['scenarios']['central']['average']);self.assertIsNone(s['scenarios']['central']['minimum'])
        self.assertIsNone(result['days'][-1]['hours']['central']);self.assertEqual(s['scenarios']['central']['assessed_date_mean'],2)
    def test_unestimated_or_unallocated_integration_prevents_complete(self):
        effort=self.doc['work_items'][1]['effort']; effort.update(status='unassessable',hours_low=None,hours_central=None,hours_high=None)
        eng.import_assessment(self.db,self.doc,'UTC');result=self.view()
        self.assertIn('implementation',result['days'][1]['unknown_items']);self.assertFalse(result['sensitivity']['8']['complete'])
        self.doc['version']=2;self.doc['work_items'].pop();eng.import_assessment(self.db,self.doc,'UTC')
        self.assertEqual(len(self.view()['days'][1]['unknown_items']),1)
    def test_reviewed_zero_requires_repository_evidence(self):
        self.doc.update(snapshots=[],work_items=[]);eng.import_assessment(self.db,self.doc,'UTC')
        self.assertEqual(self.view()['sensitivity']['8']['assessed_dates'],0)
    def test_current_partial_day_full_day_comparison(self):
        self.doc['cutoff']='2026-01-03T14:00:00Z';eng.import_assessment(self.db,self.doc,'UTC')
        result=eng.view(self.db,self.config,dict(start='2026-01-01',end='2026-01-03'),cutoff='2026-01-03T14:00:00Z')
        self.assertTrue(result['days'][-1]['partial_day']);self.assertEqual(result['full_days']['8']['eligible_dates'],2)
        self.assertEqual(result['sensitivity']['8']['scenarios']['central']['average'],4/3)
        self.assertEqual(result['full_days']['8']['scenarios']['central']['average'],2)
        later=eng.view(self.db,self.config,dict(start='2026-01-01',end='2026-01-03'),cutoff='2026-01-03T15:00:00Z')
        self.assertFalse(later['sensitivity']['8']['complete'])
    def test_model_scope_is_independent_and_project_mapping_is_exact(self):
        eng.import_assessment(self.db,self.doc,'UTC')
        result=self.view(model='absent');self.assertEqual(result['usage']['days'],{})
        self.assertEqual(result['sensitivity']['8']['eligible_dates'],3)
        self.assertEqual(self.view(projects=['Unmapped'])['days'],[])
    def test_versions_idempotency_proposals_and_validation(self):
        eng.import_assessment(self.db,self.doc,'UTC');eng.import_assessment(self.db,self.doc,'UTC')
        changed=copy.deepcopy(self.doc);changed['work_items'][0]['effort']['hours_central']=9
        with self.assertRaisesRegex(ValueError,'immutable'):eng.import_assessment(self.db,changed,'UTC')
        changed['version']=2;changed['approval_status']='proposed';eng.import_assessment(self.db,changed,'UTC')
        self.assertEqual(self.view()['assessment_version'],1);self.assertEqual(eng.template(self.db,'UTC')['version'],3)
        for invalid in (float('nan'),float('inf'),-1,True,100):
            bad=copy.deepcopy(changed);bad['version']=3;bad['work_items'][0]['effort']['hours_low']=invalid
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):eng.import_assessment(self.db,bad,'UTC')
    def test_total_hours_cannot_overflow_even_when_individual_values_are_finite(self):
        for item in self.doc['work_items']:
            item['effort'].update(hours_low=1e308,hours_central=1e308,hours_high=1e308)
        with self.assertRaisesRegex(ValueError,'combined'):
            eng.import_assessment(self.db,self.doc,'UTC')

    def test_shared_commit_accepts_disjoint_scopes_and_configuration_quality(self):
        (self.repo/'config.json').write_text('{"enabled":true}')
        self.git('add','config.json')
        head=self.commit('other.py','other=1\n','2026-01-03T12:00:00Z')
        self.snapshot=eng.collect_repositories(self.db,self.config)[0];self.doc['snapshots']=[self.snapshot['id']]
        config_item=self.item('configuration',head,'config.json',2)
        review=self.quality();review.update(revision=head,files=['config.json']);review['tests']=[]
        config_item['quality']=[review]
        self.doc['work_items'].extend([config_item,self.item('disjoint',head,'other.py',3)])
        eng.import_assessment(self.db,self.doc,'UTC');result=self.view()
        self.assertEqual(result['days'][2]['hours']['central'],5)
        self.assertEqual(result['days'][2]['items'][0]['quality'][0]['quality_score'],70)

    def test_unique_ids_credit_keys_and_scope(self):
        for field in ('id','credit_key'):
            bad=copy.deepcopy(self.doc);bad['work_items'][1][field]=bad['work_items'][0][field]
            with self.assertRaises(ValueError):eng.import_assessment(self.db,bad,'UTC')
        bad=copy.deepcopy(self.doc);item=copy.deepcopy(bad['work_items'][0]);item.update(id='duplicate',credit_key='duplicate');bad['work_items'].append(item)
        with self.assertRaisesRegex(ValueError,'Overlapping'):eng.import_assessment(self.db,bad,'UTC')
        bad=copy.deepcopy(self.doc);bad['work_items'][0]['allocations'][0]['commit']=self.second
        with self.assertRaisesRegex(ValueError,'Covered commit'):eng.import_assessment(self.db,bad,'UTC')
    def test_disjoint_scope_and_other_author_attribution(self):
        third=self.commit('c.py','z=3\n','2026-01-03T12:00:00Z','other@example.test')
        self.snapshot=eng.collect_repositories(self.db,self.config)[0];self.doc['snapshots']=[self.snapshot['id']]
        item=self.item('other',third,'c.py',10);self.doc['work_items'].append(item)
        with self.assertRaisesRegex(ValueError,'Other-author'):eng.import_assessment(self.db,self.doc,'UTC')
        item['allocations'][0].update(paths=[],credit='integration_review',attribution_evidence=['review:personal integration only'])
        eng.import_assessment(self.db,self.doc,'UTC')
    def test_nonengineering_scope_cannot_receive_effort(self):
        for kind in ('publishing_admin','generated','revert_reapplication','dependency_adoption'):
            bad=copy.deepcopy(self.doc);bad['work_items'][0]['kind']=kind
            with self.subTest(kind=kind),self.assertRaises(ValueError):eng.import_assessment(self.db,bad,'UTC')
    def quality(self):
        return dict(status='assessed',repository=self.snapshot['repository'],revision=self.second,files=['a.py','b.py'],method='manual source review',method_version='1',reviewer='Local reviewer',reviewed_at='2026-01-04T00:00:00Z',scores=dict(zip(eng.DIMENSIONS,[3,4,2,5])),confidence='medium',strengths=['Configuration behavior inspected'],reservations=['Limited runtime evidence'],unreviewed_scope='External deployments',evidence=['source:revision'],tests=[dict(classification='present_only',revision=self.second,date='2026-01-02',applies_to_delivered=True,result='not_run',evidence=['test-file:present'])])
    def test_quality_null_test_evidence_and_final_revision(self):
        review=self.quality();self.doc['work_items'][1]['quality']=[review]
        eng.import_assessment(self.db,self.doc,'UTC');quality=self.view()['days'][1]['items'][0]['quality'][0]
        self.assertEqual(quality['quality_score'],70);self.assertTrue(quality['final_day_scope'])
        self.doc['version']=2;review['scores']['correctness']=None;eng.import_assessment(self.db,self.doc,'UTC')
        self.assertIsNone(self.view()['days'][1]['items'][0]['quality'][0]['quality_score'])
        self.doc['version']=3;review['tests'][0]['result']='passed'
        with self.assertRaisesRegex(ValueError,'presence'):eng.import_assessment(self.db,self.doc,'UTC')
        review['tests'][0].update(classification='later_historical_snapshot_rerun',date='2026-01-04');eng.import_assessment(self.db,self.doc,'UTC')
    def test_quality_paths_must_exist_and_final_day_later_fix_is_visible(self):
        review=self.quality();review['files']=['missing.py'];self.doc['work_items'][1]['quality']=[review]
        with self.assertRaisesRegex(ValueError,'exact reviewed revision'):eng.import_assessment(self.db,self.doc,'UTC')
        third=self.commit('b.py','y=3\n','2026-01-02T18:00:00Z','other@example.test');self.snapshot=eng.collect_repositories(self.db,self.config)[0]
        self.doc['snapshots']=[self.snapshot['id']];review['files']=['b.py']
        self.doc['excluded_integrations']=[dict(repository=self.snapshot['repository'],head=third,reason='Other-author follow-up; no personal implementation credit',evidence=['fix:revision'])]
        eng.import_assessment(self.db,self.doc,'UTC');q=self.view()['days'][1]['items'][0]['quality'][0]
        self.assertFalse(q['final_day_scope']);self.assertEqual(q['final_day_head'],third)
    def test_explicit_pr_and_deployment_evidence_does_not_duplicate_effort(self):
        self.doc['integration_evidence']=[dict(repository=self.snapshot['repository'],head=self.second,pr=dict(url='https://github.com/example/repo/pull/1',evidence=['local:PR metadata']),deployments=[dict(id='deploy-1',timestamp='2026-01-03T16:00:00Z',evidence=['local:deployment record'])])]
        eng.import_assessment(self.db,self.doc,'UTC');result=self.view()
        self.assertEqual(result['days'][1]['integrations'][0]['delivery_kind'],'pr_merge')
        self.assertEqual(len(result['days'][2]['deployments']),1);self.assertEqual(result['days'][2]['hours']['central'],0)
        self.assertEqual(result['weekly'][0]['deployments'],1);self.assertEqual(result['weekly'][0]['usage']['total'],300)
        self.doc['version']=2;self.doc['integration_evidence'][0]['deployments'][0]['timestamp']='2026-01-01T12:00:00Z'
        with self.assertRaisesRegex(ValueError,'Deployment'):eng.import_assessment(self.db,self.doc,'UTC')
    def test_import_rejects_wrong_timestamp_and_nested_shapes(self):
        for key,value in [('cutoff',123),('work_items',[[]]),('snapshots',[{}])]:
            bad=copy.deepcopy(self.doc);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):eng.import_assessment(self.db,bad,'UTC')

    def test_share_exports_do_not_leak_private_evidence(self):
        self.doc['work_items'][0]['scope']='SECRET/customer';self.doc['work_items'][0]['effort']['evidence']=['SECRET/prompt']
        eng.import_assessment(self.db,self.doc,'UTC');report=self.view(projects=['Example'])
        for private in (True,False):
            shared=eng.export_report(report,private);value=json.dumps(shared)+eng.csv_report(shared)
            for secret in ('SECRET',self.first,str(self.repo),'session','me@example.test','Example'):
                self.assertNotIn(secret,value)
            self.assertEqual(shared['privacy_mode'],private);self.assertEqual(shared['selection']['project_count'],1)
    def test_collector_does_not_execute_configured_signature_helpers(self):
        marker=self.root/'verification-program-ran'
        probe=self.root/'gpg-probe';probe.write_text('#!/bin/sh\ntouch "'+str(marker)+'"\nexit 1\n');probe.chmod(0o700)
        self.git('config','log.showSignature','true');self.git('config','gpg.program',str(probe))
        raw=self.git('cat-file','commit','HEAD');headers,message=raw.split('\n\n',1)
        signed=headers+'\ngpgsig -----BEGIN PGP SIGNATURE-----\n fake\n -----END PGP SIGNATURE-----\n\n'+message+'\n'
        sha=subprocess.check_output(['git','-C',str(self.repo),'hash-object','-t','commit','-w','--stdin'],input=signed,text=True).strip()
        self.git('update-ref','refs/heads/main',sha)
        eng.collect_repositories(self.db,self.config)
        self.assertFalse(marker.exists(), 'Local observation must not execute a configured signature helper')

    def test_canonical_repository_strips_credentials_and_default_ports(self):
        self.git('remote','add','origin','https://user:SECRET@github.com:443/Example/Repo.git')
        self.assertEqual(eng.canonical_repository(self.repo),'github.com/example/repo')
        self.git('remote','set-url','origin','ssh://git@github.com:22/Example/Repo.git')
        self.assertEqual(eng.canonical_repository(self.repo),'github.com/example/repo')
        self.git('remote','set-url','origin','ssh://git@example.test:2222/Team/Repo.git')
        self.assertEqual(eng.canonical_repository(self.repo),'example.test:2222/Team/Repo')

    def test_git_first_parent_merges_stale_refs_and_duplicate_checkouts(self):
        self.git('remote','add','origin','git@github.com:Example/Repo.git')
        self.git('checkout','-b','feature');branch=self.commit('feature.py','f=1\n','2026-01-02T14:00:00Z','other@example.test')
        self.git('checkout','main');env=dict(os.environ,GIT_AUTHOR_DATE='2026-01-03T12:00:00Z',GIT_COMMITTER_DATE='2026-01-03T12:00:00Z')
        self.git('merge','--no-ff','feature','-m','Merge feature',env=env)
        snap=eng.collect_repositories(self.db,self.config)[0]
        self.assertEqual(snap['repository'],'github.com/example/repo');self.assertEqual(len(snap['integrations']),3)
        self.assertNotIn(branch,[i['head'] for i in snap['integrations']]);self.assertIn(branch,[c['revision'] for c in snap['integrations'][-1]['commits']])
        self.assertIsNone(snap['integrations'][-1]['pr_evidence']);self.assertIsNone(snap['integrations'][-1]['deployment_evidence'])
        self.snapshot=snap;document=self.document();merge=self.item('merge',snap['tip'],'feature.py',8)
        document['work_items'].append(merge)
        with self.assertRaisesRegex(ValueError,'A merge author is not implementation attribution'):
            eng.import_assessment(self.db,document,'UTC')
        merge['allocations'][0].update(credit='integration_review',paths=[],attribution_evidence=['review:integration'])
        eng.import_assessment(self.db,document,'UTC')
        clone=self.root/'copy';subprocess.run(['git','clone',str(self.repo),str(clone)],check=True,capture_output=True)
        subprocess.run(['git','-C',str(clone),'remote','set-url','origin','https://github.com/example/repo.git'],check=True)
        self.config['engineering_repositories'].append(dict(path=str(clone),default_ref='refs/heads/main',project='Example'))
        self.assertEqual(len(eng.collect_repositories(self.db,self.config)),1)
        self.commit('late.py','later=1\n','2026-01-03T18:00:00Z')
        with self.assertRaisesRegex(ValueError,'Duplicated checkouts disagree'):eng.collect_repositories(self.db,self.config)
        saved=json.loads(self.db.execute('SELECT body FROM repository_snapshots WHERE id=?',(snap['id'],)).fetchone()[0]);self.assertEqual(saved['tip'],snap['tip'])
    def test_same_timestamp_order_and_repeated_gitlink_adoption(self):
        # Gitlink entries need no submodule checkout or network access.
        for revision in (self.first,self.second,self.first):
            self.git('update-index','--add','--cacheinfo','160000,'+revision+',dependency')
            env=dict(os.environ,GIT_AUTHOR_DATE='2026-01-03T12:00:00Z',GIT_COMMITTER_DATE='2026-01-03T12:00:00Z')
            self.git('commit','-m','Adopt dependency',env=env)
        snap=eng.collect_repositories(self.db,self.config)[0]
        self.assertEqual(len(snap['integrations']),5)
        self.assertEqual([i['gitlinks'][0]['repeated_adoption'] for i in snap['integrations'][-3:]],[False,False,True])
        self.snapshot=snap;document=self.document();repeat=self.item('repeat',snap['tip'],'dependency',8)
        document['work_items'].append(repeat)
        with self.assertRaisesRegex(ValueError,'Repeated gitlink adoption cannot receive implementation credit'):
            eng.import_assessment(self.db,document,'UTC')
        repeat['allocations'][0].update(credit='integration_review',paths=[],attribution_evidence=['review:integration'])
        eng.import_assessment(self.db,document,'UTC')


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.db=self.root/'ledger.sqlite3'
        self.config=dict(timezone='UTC',sources=[dict(provider='Codex',path=str(self.root/'logs'))])
    def tearDown(self):self.temp.cleanup()
    def write(self,name,rows):
        path=self.root/'logs'/name;path.parent.mkdir(exist_ok=True,parents=True);path.write_text(''.join(json.dumps(r)+'\n' for r in rows));return path
    def response(self,id,time,inp=10,out=5):
        return dict(type='token_usage_record',timestamp=time,payload=dict(response_id=id,thread_id='root',usage=dict(input_tokens=inp,cached_input_tokens=0,output_tokens=out)))
    def evidence(self,**filters):
        with connect(self.db) as db:
            usage,events,provenance=ev.accounting(db,filters,self.config['timezone'],cutoff='2026-12-01T00:00:00Z')
            return usage,ev.activity(db,filters,self.config['timezone'],events,provenance,'2026-12-01T00:00:00Z')
    def test_maxima_earliest_accounting_cross_midnight_and_retention(self):
        later=self.response('r','2026-01-02T00:00:10Z',out=8);earlier=self.response('r','2026-01-01T23:59:50Z')
        self.write('a.jsonl',[later]);path=self.write('b.jsonl',[earlier,later]);sync(self.db,self.config)
        usage,activity=self.evidence();self.assertEqual(usage['days']['2026-01-01']['total'],18)
        self.assertNotIn('2026-01-02',usage['days']);self.assertEqual(activity['days']['2026-01-02']['positive_accounting_identities'],0)
        self.assertEqual(activity['days']['2026-01-02']['responding_density']['60'],1)
        self.assertEqual(usage['days']['2026-01-01']['raw_verified'],18)
        for path in (self.root/'logs').glob('*.jsonl'):path.unlink()
        sync(self.db,self.config);usage,activity=self.evidence()
        self.assertEqual(usage['days']['2026-01-01']['ledger_only'],18);self.assertEqual(usage['days']['2026-01-01']['total'],18)
    def test_detailed_records_supersede_previously_imported_legacy(self):
        legacy=dict(type='event_msg',timestamp='2026-01-01T12:00:00Z',payload=dict(type='token_count',info=dict(total_token_usage=dict(input_tokens=100,output_tokens=5))))
        self.write('r.jsonl',[legacy]);sync(self.db,self.config)
        self.write('r.jsonl',[legacy,self.response('detailed','2026-01-01T12:00:00Z',100,5)]);sync(self.db,self.config)
        usage,_=self.evidence();self.assertEqual(usage['days']['2026-01-01']['total'],105)
        with connect(self.db) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)

    def test_filtered_cross_midnight_public_report_preserves_activity_and_lookback(self):
        self.write('cross.jsonl',[dict(type='turn_context',payload=dict(model='model')),self.response('r','2026-01-01T23:59:50Z'),self.response('r','2026-01-02T00:00:10Z',out=8)])
        sync(self.db,self.config)
        for extra in ({},{'model':'model','role':'main'}):
            with connect(self.db) as db:
                report=eng.view(db,self.config,dict(start='2026-01-02',end='2026-01-02',**extra),cutoff='2026-01-03T00:00:00Z')
            self.assertEqual(len(report['days']),1)
            self.assertFalse(report['days'][0]['eligible']);self.assertEqual(report['usage']['days'],{})
            self.assertEqual(report['activity']['days']['2026-01-02']['responding_density']['60'],1)
            self.assertEqual(report['activity']['days']['2026-01-02']['positive_accounting_identities'],0)
            self.assertIn('2026-01-02',eng.csv_report(eng.export_report(report)))
    def test_filtered_density_keeps_other_identity_lookback(self):
        early=self.response('early','2026-01-01T23:59:50Z');early['payload']['thread_id']='earlier'
        later=self.response('later','2026-01-02T00:00:10Z')
        self.write('cross.jsonl',[dict(type='turn_context',payload=dict(model='model')),early,later]);sync(self.db,self.config)
        _,activity=self.evidence(start='2026-01-02',end='2026-01-02',model='model',role='main')
        self.assertEqual(activity['days']['2026-01-02']['responding_density']['60'],2)

    def test_activity_only_identity_survives_public_projection(self):
        self.write('zero.jsonl',[dict(type='session_meta',timestamp='2026-01-02T12:00:00Z',payload=dict(id='synthetic'))]);sync(self.db,self.config)
        with connect(self.db) as db:report=eng.view(db,self.config,dict(start='2026-01-02',end='2026-01-02'))
        self.assertEqual(len(report['days']),1);self.assertFalse(report['days'][0]['eligible'])
        self.assertEqual(report['sensitivity']['8']['eligible_dates'],0)
    def test_base_ledger_legacy_upgrade_and_reconcile_order(self):
        legacy=dict(type='event_msg',timestamp='2026-01-01T12:00:00Z',payload=dict(type='token_count',info=dict(total_token_usage=dict(input_tokens=100,output_tokens=5))))
        path=self.write('r.jsonl',[legacy])
        with connect(self.db) as db:
            for row in records(path,'Codex','local'):db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',row[:-1])
        self.write('r.jsonl',[legacy,self.response('detailed','2026-01-01T12:00:00Z',100,5)])
        # Exact raw-observation replacement used by --reconcile, before sync.
        with connect(self.db) as db:
            observations={};list(records(path,'Codex','local',provenance=observations));ev.save_provenance(db,path,observations)
        sync(self.db,self.config)
        self.assertEqual(summary(self.db,self.config)['totals']['total'],105)
        self.assertEqual(self.evidence()[0]['days']['2026-01-01']['total'],105)
    def test_superseded_legacy_cannot_return_from_a_later_archive(self):
        legacy=dict(type='event_msg',timestamp='2026-01-01T12:00:00Z',payload=dict(type='token_count',info=dict(total_token_usage=dict(input_tokens=100,output_tokens=5))))
        self.write('r.jsonl',[legacy]);sync(self.db,self.config)
        self.write('r.jsonl',[legacy,self.response('detailed','2026-01-01T12:00:00Z',100,5)]);sync(self.db,self.config)
        self.write('archive/old.jsonl',[legacy])
        unrelated=copy.deepcopy(legacy);unrelated['timestamp']='2026-01-03T12:00:00Z';unrelated['payload']['info']['total_token_usage']={'input_tokens':20,'output_tokens':0}
        self.write('unrelated.jsonl',[unrelated])
        for _ in range(2):
            sync(self.db,self.config)
            self.assertEqual(summary(self.db,self.config)['totals']['total'],125)
            usage,_=self.evidence();self.assertEqual(usage['days']['2026-01-01']['total'],105);self.assertEqual(usage['raw_only_records'],0)
        # A changed legacy copy must not resurrect the established identity either.
        self.write('archive/old.jsonl',[legacy,legacy]);sync(self.db,self.config)
        self.assertEqual(summary(self.db,self.config)['totals']['total'],125)

    def test_native_child_relationship_wins_over_copy_in_either_source_order(self):
        child=self.response('child-response','2026-01-01T12:01:00Z');child['payload']['thread_id']='CHILD_SECRET'
        parent_meta=dict(type='session_meta',timestamp='2026-01-01T12:00:00Z',payload=dict(id='ROOT_SECRET'))
        child_meta=dict(type='session_meta',timestamp='2026-01-01T12:00:30Z',payload=dict(id='CHILD_SECRET',source=dict(subagent=dict(thread_spawn=dict(parent_thread_id='ROOT_SECRET')))))
        self.write('parent/parent.jsonl',[parent_meta,child])
        self.write('child/child.jsonl',[child_meta,child,dict(type='event_msg',timestamp='2026-01-01T12:02:00Z',payload=dict(type='task_completed'))])
        for first in ('parent','child'):
            database=self.root/(first+'.sqlite3')
            self.config['sources']=[dict(provider='Codex',path=str(self.root/'logs'/name)) for name in (first,'child' if first=='parent' else 'parent')]
            sync(database,self.config)
            with connect(database) as db:report=eng.view(db,self.config,dict(start='2026-01-01',end='2026-01-01'))
            day=report['activity']['days']['2026-01-01'];identity=next(a for a in day['identities'] if a['id']=='Codex:CHILD_SECRET')
            self.assertTrue(identity['child']);self.assertEqual(identity['parent'],'Codex:ROOT_SECRET');self.assertIn('estimated child',identity['span_basis'])
            self.assertEqual((day['roots'],day['children']),(1,1));self.assertEqual(report['weekly'][0]['activity']['children'],1)
            self.assertIn('CHILD_SECRET',day['positive_identity_ids'][0])
            for private in (True,False):
                public=eng.export_report(report,private);serialized=json.dumps(public)+eng.csv_report(public)
                self.assertNotIn('ROOT_SECRET',serialized);self.assertNotIn('CHILD_SECRET',serialized)
                self.assertEqual(public['activity']['days']['2026-01-01']['children'],1)

    def test_native_child_without_parent_is_still_a_child_in_both_orders(self):
        response=self.response('r','2026-01-01T12:01:00Z');response['payload']['thread_id']='child'
        self.write('parent/copy.jsonl',[dict(type='session_meta',payload=dict(id='parent')),response])
        self.write('child/native.jsonl',[dict(type='session_meta',payload=dict(id='child',source=dict(subagent={}))),response])
        for order in (('parent','child'),('child','parent')):
            self.config['sources']=[dict(provider='Codex',path=str(self.root/'logs'/name)) for name in order]
            database=self.root/('no-edge-'+order[0]+'.sqlite3');sync(database,self.config)
            with connect(database) as db:report=eng.view(db,self.config,dict(start='2026-01-01',end='2026-01-01'))
            child=next(a for a in report['activity']['days']['2026-01-01']['identities'] if a['id']=='Codex:child')
            self.assertTrue(child['child']);self.assertIsNone(child['parent'])

    def test_native_child_metadata_can_fill_previously_missing_parent(self):
        incomplete=dict(type='session_meta',timestamp='2026-01-01T12:00:00Z',payload=dict(id='child',source=dict(subagent={})))
        complete=copy.deepcopy(incomplete);complete['payload']['source']['subagent']={'thread_spawn':{'parent_thread_id':'parent'}}
        response=self.response('r','2026-01-01T12:01:00Z');response['payload']['thread_id']='child'
        self.write('a.jsonl',[incomplete,response]);self.write('b.jsonl',[complete,response]);sync(self.db,self.config)
        _,activity=self.evidence();identity=activity['days']['2026-01-01']['identities'][0]
        self.assertEqual(identity['parent'],'Codex:parent');self.assertTrue(identity['child'])
        # Explicit native metadata later in the same stream also supersedes a copy.
        body=ev.collect_activity(Path('late.jsonl'),'Codex',[response,complete,response])
        child=next(a for a in body if a['id']=='Codex:child')
        self.assertTrue(child['child']);self.assertEqual(child['parent'],'Codex:parent')

    def test_conflicting_native_parent_edges_are_explicitly_uncertain(self):
        response=self.response('r','2026-01-01T12:01:00Z');response['payload']['thread_id']='child'
        for name in ('one','two','three'):
            meta=dict(type='session_meta',timestamp='2026-01-01T12:00:00Z',payload=dict(id='child',source=dict(subagent=dict(thread_spawn=dict(parent_thread_id=name)))))
            self.write(name+'.jsonl',[meta,response])
        sync(self.db,self.config);identity=self.evidence()[1]['days']['2026-01-01']['identities'][0]
        self.assertIsNone(identity['parent']);self.assertTrue(identity['identity_uncertain']);self.assertEqual(identity['parent_candidates'],['Codex:one','Codex:three','Codex:two'])

    def test_conflicted_histories_preserve_all_parent_alternatives_in_both_orders(self):
        response=self.response('r','2026-01-01T12:01:00Z');response['payload']['thread_id']='child'
        for groups in ((('one',),('two','three')), (('one','two'),('three','four'))):
            for index,parents in enumerate(groups):
                rows=[dict(type='session_meta',timestamp='2026-01-01T12:00:00Z',payload=dict(id='child',source=dict(subagent=dict(thread_spawn=dict(parent_thread_id=p))))) for p in parents]
                self.write(str(index)+'/history.jsonl',rows+[response])
            for order in ((0,1),(1,0)):
                with self.subTest(groups=groups,order=order):
                    self.config['sources']=[dict(provider='Codex',path=str(self.root/'logs'/str(i))) for i in order]
                    database=self.root/(str(len(groups[0]))+'-'+str(order[0])+'.sqlite3');sync(database,self.config)
                    with connect(database) as db:report=eng.view(db,self.config,dict(start='2026-01-01',end='2026-01-01'))
                    identity=report['activity']['days']['2026-01-01']['identities'][0]
                    self.assertIsNone(identity['parent']);self.assertTrue(identity['identity_uncertain'])
                    self.assertEqual(identity['parent_candidates'],sorted('Codex:'+p for group in groups for p in group))

    def test_trimmed_raw_reconcile_retains_legacy_supersession(self):
        legacy=dict(type='event_msg',timestamp='2026-01-01T12:00:00Z',payload=dict(type='token_count',info=dict(total_token_usage=dict(input_tokens=100,output_tokens=5))))
        path=self.write('r.jsonl',[legacy]);sync(self.db,self.config)
        self.write('r.jsonl',[self.response('detailed','2026-01-01T12:00:00Z',100,5)])
        with connect(self.db) as db:
            observations={};list(records(path,'Codex','local',provenance=observations));ev.save_provenance(db,path,observations)
        sync(self.db,self.config);self.assertEqual(summary(self.db,self.config)['totals']['total'],105)

    def test_missing_cached_counter_is_not_fully_verified(self):
        row=self.response('r','2026-01-01T12:00:00Z');del row['payload']['usage']['cached_input_tokens']
        self.write('r.jsonl',[row]);sync(self.db,self.config)
        day=self.evidence()[0]['days']['2026-01-01'];self.assertEqual(day['raw_verified'],0);self.assertEqual(day['unknown_counter_records'],1)
    def test_aggregate_only_timing_is_unknown(self):
        path=self.write('aggregate.jsonl',[])
        with connect(self.db) as db:
            usage=dict(input_tokens=10,cached_input_tokens=0,output_tokens=5)
            row=event('snipe:aggregate:0','2026-01-01T12:00:00Z','Codex','local','aggregate','model',True,usage)
            db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',row)
            observations={};ev.record_provenance(observations,row,usage,'Codex',granularity='completed_turn');ev.save_provenance(db,path,observations)
        day=self.evidence()[1]['days']['2026-01-01']
        self.assertIsNone(day['task_span_peak']);self.assertIsNone(day['positive_task_span_peak']);self.assertIsNone(day['responding_density']['60'])

    def test_unknown_counters_are_not_verified_zero(self):
        row=self.response('missing','2026-01-01T00:00:00Z');del row['payload']['usage']['output_tokens']
        self.write('r.jsonl',[row]);sync(self.db,self.config);usage,_=self.evidence()
        day=usage['days']['2026-01-01'];self.assertEqual(day['raw_verified'],0);self.assertEqual(day['unknown_counter_records'],1)
    def test_raw_mismatch_raw_only_and_frozen_ledger(self):
        path=self.write('r.jsonl',[self.response('r','2026-01-01T00:00:00Z')]);sync(self.db,self.config)
        self.write('r.jsonl',[self.response('r','2026-01-01T00:00:00Z',20),self.response('new','2026-01-01T01:00:00Z',30)])
        with connect(self.db) as db:
            observations={};list(records(path,'Codex','local',provenance=observations));ev.save_provenance(db,path,observations)
        usage,_=self.evidence();self.assertEqual(usage['raw_only_records'],1);self.assertEqual(usage['raw_only_tokens'],35)
        self.assertEqual(usage['days']['2026-01-01']['mismatched'],15);self.assertEqual(usage['days']['2026-01-01']['total'],15)
        with connect(self.db) as db:
            public=eng.export_report(eng.view(db,self.config,dict(start='2026-01-01',end='2026-01-01')))
        exported=list(csv.reader(io.StringIO(eng.csv_report(public))));metadata=json.loads(exported[0][1])
        self.assertIn('usage',metadata);self.assertIn('activity',metadata);self.assertNotIn('days',metadata)
        self.assertTrue({'raw_only_records','raw_only_tokens','raw_only_scope','parser_version','limitations'} <= metadata['usage'].keys())
        self.assertTrue({'evidence_available','limitations'} <= metadata['activity'].keys())
        self.assertEqual(metadata['usage']['raw_only_records'],1);self.assertEqual(metadata['usage']['raw_only_tokens'],35)
        self.assertIn('All reconciled sources',metadata['usage']['raw_only_scope']);self.assertIn('lower bounds',metadata['usage']['raw_only_scope'])
        self.assertEqual(metadata['usage']['parser_version'],ev.PARSER_VERSION)
        self.assertEqual(metadata['usage']['limitations'],usage['limitations'])
        self.assertEqual(metadata['activity']['limitations'],public['activity']['limitations'])
        self.assertEqual(metadata['activity']['evidence_available'],public['activity']['evidence_available'])
        self.assertNotIn('days',metadata['usage']);self.assertNotIn('days',metadata['activity'])
        self.assertEqual(json.loads(exported[2][12])['total'],15)
    def test_half_open_ties_union_and_distinct_density(self):
        spans={'a':[['2026-01-01T00:00:00Z','2026-01-01T00:01:00Z'],['2026-01-01T00:00:30Z','2026-01-01T00:01:00Z']], 'b':[['2026-01-01T00:01:00Z','2026-01-01T00:02:00Z']]}
        self.assertEqual(ev.overlap(spans),1)
        points={'a':['2026-01-01T00:00:00Z','2026-01-01T00:00:30Z'],'b':['2026-01-01T00:01:30Z']}
        self.assertEqual(ev.density(points,60),1);self.assertEqual(ev.density(points,61),2)
    def test_roots_children_zero_identities_and_dst_day_bounds(self):
        self.config['timezone']='America/Los_Angeles'
        self.write('root.jsonl',[dict(type='session_meta',payload=dict(id='root')),dict(type='event_msg',timestamp='2026-03-08T08:00:00Z',payload=dict(type='task_started')),self.response('r','2026-03-08T09:59:00Z'),dict(type='event_msg',timestamp='2026-03-09T07:00:00Z',payload=dict(type='task_completed'))])
        self.write('child.jsonl',[dict(type='session_meta',payload=dict(id='child',source=dict(subagent=dict(thread_spawn=dict(parent_thread_id='root'))))),dict(type='event_msg',timestamp='2026-03-08T10:00:00Z',payload=dict(type='task_started')),dict(type='event_msg',timestamp='2026-03-08T10:01:00Z',payload=dict(type='task_completed'))])
        sync(self.db,self.config);_,activity=self.evidence();day=activity['days']['2026-03-08']
        self.assertEqual((day['roots'],day['children'],day['positive_accounting_identities'],day['zero_or_synthetic_only']),(1,1,1,1));self.assertEqual(day['task_span_peak'],2)
        self.assertEqual(day['positive_task_span_peak'],1)
    def test_claude_children_sharing_session_and_copied_response(self):
        self.config['sources'][0]['provider']='Claude Code'
        def row(id):return dict(type='assistant',timestamp='2026-01-01T12:00:00Z',sessionId='parent',message=dict(id=id,usage=dict(input_tokens=1,output_tokens=1,cache_creation_input_tokens=0,cache_read_input_tokens=0)))
        self.write('subagents/agent-a.jsonl',[row('a')]);self.write('subagents/agent-b.jsonl',[row('b')]);self.write('copied.jsonl',[row('a')])
        sync(self.db,self.config);usage,activity=self.evidence()
        self.assertEqual(usage['days']['2026-01-01']['total'],4);self.assertEqual(activity['days']['2026-01-01']['positive_accounting_identities'],2)
        self.assertEqual(activity['days']['2026-01-01']['children'],2)
    def test_absent_activity_is_na_and_zero_denominator_na(self):
        with connect(self.db):pass
        usage,activity=self.evidence();self.assertFalse(activity['evidence_available']);self.assertEqual(usage['days'],{})
        self.write('zero.jsonl',[self.response('zero','2026-01-01T12:00:00Z',0,0)]);sync(self.db,self.config)
        usage,activity=self.evidence();self.assertIsNone(usage['days']['2026-01-01']['raw_reconciliation_coverage'])
        self.assertEqual(activity['days']['2026-01-01']['positive_accounting_identities'],0)


if __name__=='__main__':unittest.main()
