import unittest,json,tempfile
from pathlib import Path
from datetime import datetime,timezone
from display_rankings import collect
class DisplayRankingTests(unittest.TestCase):
 def setup_files(self,p):
  (p/'kenpom-team-links.json').write_text('{}');(p/'torvik-team-aliases.json').write_text('{}')
 def fixture(self):return {'upcoming':[{'season':2027,'homeD1':True,'homeTeamId':str(i),'homeSchool':f'Team {i}'} for i in range(1,366)]}
 def test_identity_rank_and_explicit_season(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);self.setup_files(p);data=self.fixture();urls=[]
   def fetch(u):urls.append(u);return [[i,f'Team {i}'] for i in range(1,366)]
   collect(data,p,datetime(2026,10,26,tzinfo=timezone.utc),fetch);r=data['externalRankings']['torvik'];self.assertEqual(len(r['teams']),365);self.assertEqual(r['teams']['1']['rank'],1);self.assertIn('/2027_team_results.json',urls[0])
 def test_wrong_season_ranks_never_survive_source_failure(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);self.setup_files(p);data=self.fixture();data['externalRankings']={'torvik':{'season':2026,'teams':{'1':{'rank':99}}}}
   collect(data,p,datetime(2026,10,26,tzinfo=timezone.utc),lambda u:[]);self.assertEqual(data['externalRankings']['torvik']['teams'],{});self.assertEqual(data['externalRankings']['torvik']['status'],'unavailable')
 def test_duplicate_ranks_are_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);self.setup_files(p);data=self.fixture();collect(data,p,datetime(2026,10,26,tzinfo=timezone.utc),lambda u:[[1,f'Team {i}'] for i in range(1,366)]);self.assertEqual(data['externalRankings']['torvik']['status'],'unavailable')
if __name__=='__main__':unittest.main()
