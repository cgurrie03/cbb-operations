import unittest,tempfile,json,copy
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone,timedelta
import pandas as pd
from three_models import aggregate,eligible,publish,IDS

class ThreeModelsTest(unittest.TestCase):
    def test_average_requires_all_three_and_uses_all_three(self):
        values={k:dict(margin=i,total=130+i,homeWinProbability=.4+i*.01) for i,k in enumerate(IDS)}
        self.assertEqual(aggregate(values)['margin'],1)
        self.assertEqual(aggregate(values)['total'],131)
        with self.assertRaises(ValueError):aggregate({IDS[0]:values[IDS[0]]})
    def test_actual_snapshot_window_and_identity(self):
        g=dict(tipoff='2026-11-03T18:00Z',homeTeamId='1',awayTeamId='2')
        self.assertTrue(eligible({**g,'observedAt':'2026-11-03T16:00Z'},g))
        self.assertFalse(eligible({**g,'observedAt':'2026-11-03T17:01Z'},g))
        self.assertFalse(eligible({**g,'observedAt':'2026-11-02T16:00Z'},g))
        self.assertFalse(eligible({**g,'homeTeamId':'3','observedAt':'2026-11-03T16:00Z'},g))
    def test_real_bundle_records_before_game_and_scores_without_rewriting(self):
        at=datetime.now(timezone.utc);tip=at+timedelta(hours=3)
        g=dict(id='test:1',tipoff=tip.isoformat(),day=tip.date().isoformat(),homeTeamId='1',awayTeamId='2',timeValid=True,completed=False)
        frame=pd.DataFrame([dict(game_id=g['id'],eligible=True,tipoff=pd.Timestamp(tip))])
        features=pd.DataFrame([dict(game_id=g['id'],eff_margin=2.8,eff_total=140,expected_pace=70,venue_effect=1,min_history=0)])
        pr=SimpleNamespace(slate=lambda _: (frame,{}),feature_rows=lambda *_:features)
        with tempfile.TemporaryDirectory() as directory:
            data={'upcoming':[g]};publish(pr,data,Path(__file__).parent,directory,at.isoformat())
            self.assertEqual(set(g['modelComparison']['models']),set(IDS));self.assertEqual(data['modelComparison']['forwardForecasts'],1)
            self.assertTrue(set(data['teamScoreModel']['selected'])<=g['modelComparison']['teamScore'].keys())
            paths=list((Path(directory)/'forecasts').glob('*.json'));before={p.name:p.read_bytes() for p in paths};saved=copy.deepcopy(g['modelComparison'])
            g.update(completed=True,homeScore=80,awayScore=70);g.pop('modelComparison')
            publish(pr,data,Path(__file__).parent,directory,datetime.now(timezone.utc).isoformat())
            self.assertEqual(data['modelComparison']['forward']['ensemble']['games'],1);self.assertEqual(g['modelComparison'],saved)
            self.assertEqual(data['teamScoreModel']['forward']['margin']['games'],1)
            self.assertEqual(before,{p.name:p.read_bytes() for p in (Path(directory)/'forecasts').glob('*.json')})
            g2={**g,'id':'test:2'};g2.pop('modelComparison');data['upcoming'].append(g2)
            publish(pr,data,Path(__file__).parent,directory,datetime.now(timezone.utc).isoformat());self.assertNotIn('modelComparison',g2)
            self.assertEqual(data['modelComparison']['forward']['ensemble']['games'],1)

if __name__=='__main__':unittest.main()
