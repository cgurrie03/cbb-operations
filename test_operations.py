import unittest
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

if __name__=='__main__':unittest.main()
