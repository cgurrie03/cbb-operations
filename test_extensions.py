import unittest
from unittest.mock import patch
import io
from model_extensions import total_prediction
import public_betting
class ExtensionsTest(unittest.TestCase):
    def test_total_uses_only_declared_features(self):
        a={'features':['eff_total','expected_pace','venue_effect'],'mean':[140,70,0],'scale':[10,5,1],'coef':[8,2,1],'intercept':145}
        row={'eff_total':150,'expected_pace':75,'venue_effect':1,'total':999,'home_score':999}
        self.assertEqual(total_prediction(a,row),156)
        row['total']=-999;self.assertEqual(total_prediction(a,row),156)
        row['eff_total']=float('nan');self.assertIsNone(total_prediction(a,row))
    def test_example_shares_never_become_game_data(self):
        page=b'<html>College Basketball feed lists 25 games outside this range. Worked example: Bets 30% Money 44%<script>{"money":99}</script></html>'
        with patch.object(public_betting.urllib.request,'urlopen',return_value=io.BytesIO(page)):
            result=public_betting.collect();self.assertEqual(result['records'],[]);self.assertEqual(result['future_source_games'],25)
    def test_source_failure_remains_unavailable(self):
        with patch.object(public_betting.urllib.request,'urlopen',side_effect=TimeoutError):
            result=public_betting.collect();self.assertEqual(result['status'],'unavailable');self.assertEqual(result['records'],[])
if __name__=='__main__':unittest.main()
