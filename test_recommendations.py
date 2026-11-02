import unittest
from operations import canonical,normalize_unpriced_metadata
from recommendation_history import capture,attach

class ResultsTest(unittest.TestCase):
    def test_unmatched_book_nan_is_unpriced_without_changing_forecast(self):
        r={'bookmaker':float('nan'),'home_cover_probability':None,'projected_margin':4.5,'features':{'x':1}}
        fixed=normalize_unpriced_metadata(r)
        self.assertEqual(fixed['bookmaker'],'unpriced');self.assertEqual(fixed['projected_margin'],4.5);self.assertEqual(fixed['features'],r['features'])
        priced={**r,'home_cover_probability':.6};self.assertIs(normalize_unpriced_metadata(priced),priced)
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
