"""Display rankings only; never model features. Explicit season and identity matching."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,re,unicodedata,urllib.request,urllib.parse

def normalize(s):
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
    s=re.sub(r'\bstate\b','st',s);s=re.sub(r'\bsaint\b','st',s)
    return re.sub('[^a-z0-9]','',s)
def get(url):
    with urllib.request.urlopen(url,timeout=20) as r:return json.load(r)
def collect(data,root,at=None,fetch=get):
    at=at or datetime.now(timezone.utc);data.setdefault('externalRankings',{})['kenpom']={'mode':'links','teams':json.loads((Path(root)/'kenpom-team-links.json').read_text(encoding='utf8'))};season=max(g['season'] for g in data['upcoming']);prior=data.get('externalRankings',{}).get('torvik',{});url=f'https://barttorvik.com/{season}_team_results.json'
    try:
        if prior.get('season')==season and prior.get('checkedAt') and at-datetime.fromisoformat(prior['checkedAt'])<timedelta(hours=6):return data
        rows=fetch(url)
        if not isinstance(rows,list) or len(rows)<300:raise ValueError('Incomplete ranking feed')
        names={};ranks=set()
        for row in rows:
            rank,name=row[0],row[1]
            if not isinstance(rank,int) or not 1<=rank<=500 or not isinstance(name,str) or rank in ranks or normalize(name) in names:raise ValueError('Invalid ranking')
            ranks.add(rank);names[normalize(name)]=(rank,name)
        aliases=json.loads((Path(root)/'torvik-team-aliases.json').read_text(encoding='utf8'))
        teams={str(g[s+'TeamId']):g[s+'School'] for g in data['upcoming'] for s in ['home','away'] if g.get(s+'D1') and g.get(s+'TeamId')}
        mapped={};used=set()
        for tid,name in teams.items():
            match=names.get(normalize(aliases.get(tid,name)))
            if match:
                rank,source_name=match
                if rank in used:raise ValueError('Ambiguous team identity')
                used.add(rank);mapped[tid]={'rank':rank,'sourceName':source_name,'url':'https://barttorvik.com/team.php?'+urllib.parse.urlencode({'team':source_name,'year':season})}
        if len(mapped)<300:raise ValueError('Insufficient matched coverage')
        data.setdefault('externalRankings',{})['torvik']={'status':'available','season':season,'checkedAt':at.isoformat(),'source':url,'teams':mapped}
    except Exception:
        data.setdefault('externalRankings',{})['torvik']={**prior,'status':'delayed' if prior.get('teams') and prior.get('season')==season else 'unavailable','season':season,'source':url}
        if prior.get('season')!=season:data['externalRankings']['torvik']['teams']={}
    return data
