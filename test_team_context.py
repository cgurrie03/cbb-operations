import unittest,json,tempfile
from pathlib import Path
from datetime import datetime,timezone
from team_context import summarize,schedule_games,collect
class TeamContextTests(unittest.TestCase):
 def test_missing_prices_are_excluded_from_ats(self):
  games=[dict(id=str(i),date=f'2026-01-0{i+1}',scored=80,allowed=70,result='W',ats=a) for i,a in enumerate(['W',None,'L','P'])]
  s=summarize(games,2026);self.assertEqual(s['ats']['coveredGames'],3);self.assertEqual(s['ats']['wins'],1);self.assertEqual(s['ppg'],80)
 def test_schedule_excludes_other_seasons_future_and_unfinished(self):
  e={'id':'1','date':'2026-11-01T10:00Z','season':{'year':2027},'seasonType':{'type':2},'competitions':[{'status':{'type':{'completed':True}},'competitors':[{'id':'1','score':{'value':80}},{'id':'2','score':{'value':70},'team':{'displayName':'Opponent'}}]}]}
  self.assertEqual(schedule_games({'events':[e]},'1',2027,datetime(2026,10,26,tzinfo=timezone.utc)),[])
  self.assertEqual(schedule_games({'events':[e]},'1',2026,datetime(2027,1,1,tzinfo=timezone.utc)),[])
  s=schedule_games({'events':[e]},'1',2027,datetime(2027,1,1,tzinfo=timezone.utc));self.assertEqual(s[0]['scored'],80);self.assertIsNone(s[0]['ats'])
 def test_expired_news_never_becomes_current_injury_status(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'team-history.json').write_text('{}');(root/'availability-notes.json').write_text(json.dumps([{'teamId':'1','name':'Player','expiresAt':'2026-10-20T00:00:00+00:00'}]))
   d={'upcoming':[{'season':2027,'homeD1':True,'homeTeamId':'1'}]};collect(d,root,datetime(2026,10,26,tzinfo=timezone.utc),fetch=lambda u:{})
   self.assertEqual(d['teamContexts']['1']['injuries'],[]);self.assertEqual(d['teamContexts']['1']['injuryCoverage'],'No verified report');self.assertIsNone(d['teamContexts']['1']['current']['ppg'])
if __name__=='__main__':unittest.main()
