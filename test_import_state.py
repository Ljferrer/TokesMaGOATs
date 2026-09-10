import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from app import ImportState

class ImportTests(unittest.TestCase):
    def test_single_flight_and_completion(self):
        entered=threading.Event();release=threading.Event();finished=threading.Event()
        def scan(*args):
            entered.set();release.wait(5);return [dict(provider='Codex',files=2)]
        state=ImportState(Path('/tmp/test-unused.db'),{'sources':[]})
        original=state._run
        def run():
            try:original()
            finally:finished.set()
        state._run=run
        with patch('app.sync',side_effect=scan) as mocked:
            self.assertTrue(state.start());self.assertTrue(entered.wait(2))
            self.assertTrue(state.snapshot()['syncing']);self.assertFalse(state.start())
            release.set();self.assertTrue(finished.wait(2));self.assertEqual(mocked.call_count,1)
        self.assertFalse(state.snapshot()['syncing']);self.assertEqual(state.snapshot()['sources'][0]['files'],2)
        self.assertIsNotNone(state.snapshot()['last_sync'])
    def test_failed_scan_can_retry(self):
        state=ImportState(Path('/tmp/test-unused.db'),{'sources':[]})
        with patch('app.sync',side_effect=OSError('private path')):
            state.running=True;state._run()
        self.assertFalse(state.snapshot()['syncing']);self.assertIn('failed',state.snapshot()['sync_error'])
        self.assertNotIn('private path',state.snapshot()['sync_error'])
        with patch('app.sync',return_value=[]):
            state.running=True;state.error=None;state._run()
        self.assertIsNone(state.snapshot()['sync_error'])
    def test_completion_during_summary_keeps_watcher_signal(self):
        from app import usage_view
        state=ImportState(Path('/tmp/test-unused.db'),{'sources':[]});state.running=True
        def read(*args):
            state.running=False
            return {'totals':{'total':10}}
        with patch('app.summary',side_effect=read):
            result=usage_view(state.db_path,{},dict(start='2026-09-01',end='2026-09-10'),state)
        self.assertTrue(result['syncing'])
        self.assertFalse(state.snapshot()['syncing'])
    def test_scan_begins_and_finishes_between_summary_reads(self):
        from app import usage_view
        state=ImportState(Path('/tmp/test-unused.db'),{'sources':[]})
        def read(*args):
            state.generation+=1
            return {'totals':{'total':10}}
        with patch('app.summary',side_effect=read):
            result=usage_view(state.db_path,{},dict(start='2026-09-01',end='2026-09-10'),state)
        self.assertTrue(result['syncing'])
