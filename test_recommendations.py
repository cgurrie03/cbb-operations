import unittest
from operations import canonical
from recommendation_history import capture,attach

class ResultsTest(unittest.TestCase):
    def test_score_is_saved_only_from_source(self):
        e={'id':'42','date':'2026-11-01T14:30Z','season':{'year':2027,'type':2},'competitions':[{'timeValid':True,'status':{'type':{'name':'STATUS_FINAL','completed':True}},'competitors':[{'homeAway':'home','score':'75','team':{'id':'1','displayName':'Home'}},{'homeAway':'away','score':'70','team':{'id':'2','displayName':'Away'}}]}]}
        g=canonical([e],{'observed_at':'2026-11-02T12:00Z','sha256':'a'},{'espn:1','espn:2'},[])[0]
        self.assertEqual((g['homeScore'],g['awayScore']),(75,70))
        e['competitions'][0]['competitors'][0].pop('score')
        self.assertIsNone(canonical([e],{'observed_at':'2026-11-02T12:00Z','sha256':'b'},{'espn:1'},[g])[0]['homeScore'])

    def test_capture_refuses_completed_or_started_game(self):
        game=dict(id='g',homeTeamId='1',awayTeamId='2',tipoff='2026-11-01T14:30Z',homeD1=True,awayD1=True,timeValid=True,completed=True)
        prep={'previews':[dict(game_id='g',tipoff=game['tipoff'],time_confirmed=True,carryover_margin=5)]}
        history=capture({'upcoming':[game]},prep,{},'2026-11-01T15:00Z','source',{})
        self.assertEqual(history,{})
        game['completed']=False
        self.assertEqual(capture({'upcoming':[game]},prep,{},'2026-11-01T15:00Z','source',{}),{})

    def test_attach_rejects_rescheduled_or_changed_sides(self):
        g=dict(id='g',homeTeamId='1',awayTeamId='2',tipoff='2026-11-01T14:30Z')
        saved={**g,'capturedAt':'2026-11-01T14:00Z','markets':{}}
        data={'upcoming':[g]};attach(data,{'g':saved});self.assertEqual(g['recommendationHistory'],saved)
        g.pop('recommendationHistory');g['homeTeamId']='3';attach(data,{'g':saved});self.assertNotIn('recommendationHistory',g)

if __name__=='__main__':unittest.main()
