"""Persist contemporaneous website picks; never generate a pick after tipoff."""
import json,subprocess
from pathlib import Path
from datetime import datetime

def capture(data,preparation,paper,at,revision,history,selector='recommendations'):
    payload=dict(data=data,preparation=preparation,paper=paper,at=at,sourceRevision=revision)
    result=subprocess.run(['node',str(Path(__file__).parent/selector/'capture.mjs')],input=json.dumps(payload),text=True,capture_output=True,check=True)
    for record in json.loads(result.stdout):
        existing=history.setdefault(record['gameId'],{})
        # A changed matchup or start time must not inherit a different game's pick.
        if existing and any(existing.get(k)!=record.get(k) for k in ['homeTeamId','awayTeamId','tipoff']):existing.clear()
        if existing.get('capturedAt','')>record['capturedAt']:continue
        previous=existing.get('markets',{}) if existing.get('recommendationPolicy')==record.get('recommendationPolicy') and (existing.get('modelComparison') or {}).get('version')==(record.get('modelComparison') or {}).get('version') else {}
        existing.update({k:v for k,v in record.items() if k!='picks'})
        existing['markets']=previous
        for market,pick in record['picks'].items():
            if pick:
                previous[market]={k:v for k,v in record.items() if k not in ['picks','preview']}
                previous[market]['pick']=pick
    return history

def attach(data,history):
    for game in data['upcoming']:
        saved=history.get(game['id'])
        if not saved:continue
        if any(saved.get(k)!=game.get(k) for k in ['homeTeamId','awayTeamId','tipoff']):continue
        if datetime.fromisoformat(saved['capturedAt'].replace('Z','+00:00'))>=datetime.fromisoformat(game['tipoff'].replace('Z','+00:00')):continue
        game['recommendationHistory']=saved

def update(data,preparation,paper,path,at,revision):
    path=Path(path);seed=Path(__file__).with_name('recommendation-seed.json')
    history=json.loads(seed.read_text()) if seed.exists() else {}
    if path.exists():history.update(json.loads(path.read_text()))
    capture(data,preparation,paper,at,revision,history)
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(history,separators=(',',':')),encoding='utf8')
    attach(data,history)
