import unittest,tempfile,json
from pathlib import Path
from datetime import datetime,timezone
from operations import canonical
from team_context import collect
class DetailMetadataTests(unittest.TestCase):
 def test_tournament_round_and_showcase_are_not_invented(self):
  e={'id':'1','date':'2026-11-02T20:00Z','season':{'year':2027,'type':2},'competitions':[{'notes':[{'headline':'Sample Invitational - Semifinal'}],'competitors':[{'homeAway':s,'team':{'id':str(i),'displayName':s}} for i,s in [(1,'home'),(2,'away')]]}]}
  d=canonical([e],{'observed_at':'2026-10-26T12:00Z','sha256':'x'},{'espn:1'},[])[0];self.assertEqual(d['eventLabel'],'Sample Invitational - Semifinal');self.assertEqual(d['tournamentRound'],'Semifinal')
  e['competitions'][0]['notes']=[{'headline':"NCAA Men's Basketball Championship"}];d=canonical([e],{'observed_at':'2026-10-26T12:00Z','sha256':'x'},{'espn:1'},[])[0];self.assertIsNone(d['tournamentRound'])
 def test_current_season_upcoming_fills_empty_form_without_old_stats(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder);(p/'team-history.json').write_text('{}');(p/'availability-notes.json').write_text('[]')
   event={'id':'2','date':'2026-11-02T20:00Z','season':{'year':2027},'seasonType':{'type':2},'competitions':[{'timeValid':True,'status':{'type':{'completed':False}},'competitors':[{'id':'1','team':{'displayName':'Home'}},{'id':'2','team':{'displayName':'Opponent','logos':[{'href':'https://example.com/logo.png'}]}}]}]}
   data={'upcoming':[{'season':2027,'homeD1':True,'homeTeamId':'1'}]};collect(data,p,datetime(2026,10,26,tzinfo=timezone.utc),fetch=lambda url:{'events':[event]} if 'schedule?' in url else {})
   c=data['teamContexts']['1'];self.assertEqual(c['current']['games'],0);self.assertIsNone(c['current']['ppg']);self.assertEqual(c['upcoming'][0]['opponent'],'Opponent');self.assertTrue(c['upcoming'][0]['timeConfirmed']);self.assertEqual(c['upcoming'][0]['logo'],'https://example.com/logo.png')
if __name__=='__main__':unittest.main()
