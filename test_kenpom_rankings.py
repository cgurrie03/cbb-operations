import unittest,json,tempfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
from kenpom_rankings import parse,collect

class KenPomTests(unittest.TestCase):
 def fixture(self,season=2027):
  return f'<TITLE>{season} Pomeroy College Basketball Ratings</TITLE>'+''.join(f'<td class="hard_left">{i}</td><td class="next_left"><a href="team.php?team=Team+{i}">' for i in range(1,366))
 def links(self):return {str(i):f'https://kenpom.com/team.php?team=Team+{i}' for i in range(1,366)}
 def test_identity_and_current_season(self):
  ranks=parse(self.fixture(),2027,self.links());self.assertEqual(len(ranks),365);self.assertEqual(ranks['22'],22)
  with self.assertRaises(ValueError):parse(self.fixture(2026),2027,self.links())
 def test_incomplete_and_duplicate_rejected(self):
  with self.assertRaises(ValueError):parse(self.fixture().replace('hard_left">365','hard_left">364'),2027,self.links())
  with self.assertRaises(ValueError):parse('<TITLE>2027 Pomeroy College Basketball Ratings</TITLE>',2027,self.links())
 def test_failure_retains_recent_dated_snapshot_only(self):
  now=datetime(2026,10,26,tzinfo=timezone.utc)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'kenpom-team-links.json').write_text(json.dumps(self.links()))
   for age,expected in [(12,{'1':1}),(72,{})]:
    data={'upcoming':[{'season':2027}],'externalRankings':{'kenpom':{'season':2027,'checkedAt':(now-timedelta(hours=age)).isoformat(),'ranks':{'1':1}}}}
    collect(data,p,now,lambda u:'blocked');self.assertEqual(data['externalRankings']['kenpom']['ranks'],expected)
    if expected:self.assertEqual(data['externalRankings']['kenpom']['checkedAt'],(now-timedelta(hours=age)).isoformat())
 def test_success_and_wrong_season_failure(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'kenpom-team-links.json').write_text(json.dumps(self.links()));data={'upcoming':[{'season':2027}]}
   collect(data,p,fetch=lambda u:self.fixture());self.assertEqual(data['externalRankings']['kenpom']['ranks']['1'],1)
   data['upcoming'][0]['season']=2028;collect(data,p,fetch=lambda u:self.fixture());self.assertEqual(data['externalRankings']['kenpom']['ranks'],{})
