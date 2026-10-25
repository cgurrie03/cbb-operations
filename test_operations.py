import unittest
import tempfile,json,types,zipfile,sys
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone
from operations import next_due,slot,canonical,attach_cached_odds

class OperationsTest(unittest.TestCase):
    def test_dst_and_opening_exception(self):
        self.assertEqual(next_due(datetime.fromisoformat('2026-10-31T22:00:00-04:00')),'2026-11-01T14:00:00+00:00')
        self.assertEqual(next_due(datetime.fromisoformat('2026-11-01T21:01:00-05:00')),'2026-11-02T03:45:00+00:00')
        self.assertEqual(slot(datetime.fromisoformat('2026-11-02T03:45:00+00:00')),'2026-11-01T22:45')
        self.assertIsNone(slot(datetime.fromisoformat('2026-11-02T04:45:00+00:00')))

    def test_changed_tbd_cancelled_and_non_d1_schedule(self):
        event={'id':'42','date':'2026-11-02T23:30:00Z','season':{'year':2027,'type':2},'competitions':[{'timeValid':False,'neutralSite':False,'status':{'type':{'name':'STATUS_POSTPONED','description':'Postponed'}},'competitors':[{'homeAway':'home','team':{'id':'1','displayName':'Home'}},{'homeAway':'away','team':{'id':'2','displayName':'Away'}}]}]}
        rows=canonical([event],{'observed_at':'2026-10-25T12:00:00Z','sha256':'new'},{'espn:1'},[{'id':'espn:42','tipoff':'2026-11-02T20:00:00Z','odds':{'stale':True}}])
        self.assertEqual(rows[0]['tipoff'],'2026-11-02T23:30:00Z');self.assertFalse(rows[0]['timeValid']);self.assertFalse(rows[0]['awayD1']);self.assertEqual(rows[0]['status'],'STATUS_POSTPONED');self.assertNotIn('odds',rows[0])

    def test_quotes_require_confirmed_compatible_time(self):
        game={'home':'Home','away':'Away','tipoff':'2026-11-02T23:30:00Z','timeValid':True,'status':'STATUS_SCHEDULED'}
        cache={'collectedAt':'2026-10-25T12:00:00Z','events':[{'id':'q','home_team':'Home','away_team':'Away','commence_time':'2026-11-02T20:00:00Z'}]}
        self.assertEqual(attach_cached_odds({'upcoming':[game]},cache,lambda _:[]),0)
        cache['events'][0]['commence_time']=game['tipoff'];self.assertEqual(attach_cached_odds({'upcoming':[game]},cache,lambda _:[]),1)
        game['status']='STATUS_CANCELED';self.assertEqual(attach_cached_odds({'upcoming':[game]},cache,lambda _:[]),0)
    def test_failed_readback_never_activates_partial_publication(self):
        import operations
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';dest=root/'dest';source.mkdir();dest.mkdir()
            (source/'data.json').write_text('{"revision":"new"}')
            (dest/'current.json').write_text('{"revision":"old"}')
            with patch.object(operations,'PUBLIC',source),patch.object(operations,'PUBLISHED',dest),patch.object(operations,'FILES',['data.json','operations-health.json']),patch.object(operations,'commit',return_value='a'*40) as commit,patch.object(operations.urllib.request,'urlopen',side_effect=TimeoutError):
                with self.assertRaises(TimeoutError):operations.publish({'status':'success'})
                self.assertEqual(commit.call_count,1)
                self.assertEqual(json.loads((dest/'current.json').read_text())['revision'],'old')

class QuotaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import operations
        cls.temp=tempfile.TemporaryDirectory()
        root=Path(cls.temp.name)
        with zipfile.ZipFile(Path(__file__).parent/'frozen-runtime.zip') as z:z.extractall(root)
        sys.path.insert(0,str(root/'outputs/basketball-model'))
        cls.odds=types.ModuleType('hosted_odds');cls.odds.__file__=str(root/'outputs/basketball-model/odds_collector.py')
        exec(compile(Path(cls.odds.__file__).read_text(),cls.odds.__file__,'exec'),cls.odds.__dict__)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        self.state=tempfile.TemporaryDirectory();self.addCleanup(self.state.cleanup)
        self.odds.OUT=Path(self.state.name)
        self.t=datetime.fromisoformat('2026-11-02T05:10:00+00:00')
        class Clock(datetime):
            @classmethod
            def now(c,tz=None):return self.t
        self.clock=patch.object(self.odds,'datetime',Clock);self.clock.start();self.addCleanup(self.clock.stop)
    def ledger(self,calls,**kwargs):
        (self.odds.OUT/'usage.json').write_text(json.dumps({'calls':calls,'credits_since_setup':0,**kwargs}))
    def call(self,age=7200,credits=3):
        from datetime import timedelta
        at=self.t-timedelta(seconds=age)
        return {'at':at.isoformat(),'day':at.astimezone(self.odds.ZoneInfo('America/New_York')).date().isoformat(),'credits':credits}
    def test_guarded_calls_never_open_secret(self):
        scenarios=[([self.call(600)],{},'recent_snapshot_reused'),([],{'remaining':2},'quota_limit_reached'),([self.call(7200,498)],{},'local_credit_guard_reached')]
        # One-hour spacing also applies across Eastern midnight.
        for calls,options,expected in scenarios:
            self.ledger(calls,**options)
            with patch.object(self.odds,'load_key',side_effect=AssertionError('Secret must not be opened')):
                self.assertEqual(self.odds.collect()['status'],expected)
    def test_daily_attempt_limit(self):
        calls=[self.call(120+i) for i in range(5)]
        # A fixed ledger with five attempts on the new Eastern date.
        for c in calls:c['day']='2026-11-02'
        self.ledger(calls)
        self.assertEqual(self.odds.collect()['status'],'daily_limit_reached')
    def test_failed_network_attempt_is_persisted_and_not_retried(self):
        self.ledger([])
        def key():
            self.assertEqual(len(json.loads((self.odds.OUT/'usage.json').read_text())['calls']),1)
            return 'test-only-key'
        with patch.object(self.odds,'load_key',side_effect=key),patch.object(self.odds,'urlopen',side_effect=TimeoutError) as http:
            self.assertEqual(self.odds.collect()['status'],'connection_or_response_error')
            self.assertEqual(http.call_count,1)
        self.assertEqual(len(json.loads((self.odds.OUT/'usage.json').read_text())['calls']),1)

if __name__=='__main__':unittest.main()
