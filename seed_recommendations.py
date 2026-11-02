import json,subprocess
from pathlib import Path
from recommendation_history import capture
repo=Path('../cbb-public-data');history={}
def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True,encoding='utf8')
commits=git('log','--reverse','--format=%H','--since=2026-10-26','--','data.json').splitlines()
for sha in commits:
 try:
  data=json.loads(git('show',sha+':data.json'));prep=json.loads(git('show',sha+':preseason-2027.json'));paper=json.loads(git('show',sha+':paper-ledger-2027.json'));health=json.loads(git('show',sha+':operations-health.json'))
  capture(data,prep,paper,health['lastPublicationAt'],sha,history)
 except (KeyError,subprocess.CalledProcessError):continue
Path('recommendation-seed.json').write_text(json.dumps(history,separators=(',',':')),encoding='utf8')
print('Recovered original snapshots:',len(commits),'games:',len(history),'games with picks:',sum(bool(g['markets']) for g in history.values()))
print('Villanova:',{k:v for k,v in history.get('espn:401920982',{}).items() if k not in ['preview','markets']});print('markets:',list(history.get('espn:401920982',{}).get('markets',{})))
