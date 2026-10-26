"""Public homepage rank + team identity only. Display data, never model inputs."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from html import unescape
import json, re, urllib.request, urllib.parse

SOURCE='https://kenpom.com/'

def get(url):
    request=urllib.request.Request(url,headers={'User-Agent':'CBBResearch/1.0 (+https://cbb.coopergurrie.com/)'})
    with urllib.request.urlopen(request,timeout=20) as response:
        return response.read().decode('utf8')

def parse(html, season, links):
    if not re.search(rf'<title>\s*{season} Pomeroy College Basketball Ratings\s*</title>',html,re.I):
        raise ValueError('Ranking season does not match')
    rows=re.findall(r'<td class="hard_left">(\d+)</td>\s*<td class="next_left"><a href="([^"]+)">',html)
    by_name={};used=set()
    for rank,href in rows:
        name=urllib.parse.parse_qs(urllib.parse.urlparse(unescape(href)).query).get('team',[None])[0]
        rank=int(rank)
        if not name or name in by_name or rank in used or not 1<=rank<=500:
            raise ValueError('Ambiguous ranking identity')
        by_name[name]=rank;used.add(rank)
    if len(by_name)<300:raise ValueError('Incomplete public ranking table')
    mapped={tid:by_name[name] for tid,url in links.items() if (name:=urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get('team',[None])[0]) in by_name}
    if len(mapped)<300 or len(set(mapped.values()))!=len(mapped):raise ValueError('Insufficient unique mapped teams')
    return mapped

def collect(data, root, at=None, fetch=get):
    at=at or datetime.now(timezone.utc);root=Path(root)
    season=max(g['season'] for g in data['upcoming'])
    links=json.loads((root/'kenpom-team-links.json').read_text(encoding='utf8'))
    prior=data.setdefault('externalRankings',{}).get('kenpom',{})
    seed=root/'kenpom-seed.json'
    if not prior.get('ranks') and seed.exists():prior=json.loads(seed.read_text(encoding='utf8'))
    valid=prior.get('season')==season and prior.get('checkedAt') and timedelta(0)<=at-datetime.fromisoformat(prior['checkedAt'])<timedelta(days=2)
    if valid and at-datetime.fromisoformat(prior['checkedAt'])<timedelta(hours=6):
        data['externalRankings']['kenpom']=prior;return data
    try:
        ranks=parse(fetch(SOURCE),season,links)
        data['externalRankings']['kenpom']={'mode':'ranks','status':'available','season':season,'checkedAt':at.isoformat(),'source':SOURCE,'ranks':ranks}
    except Exception as error:
        data['externalRankings']['kenpom']={**(prior if valid else {}),'mode':'ranks','status':'delayed' if valid else 'unavailable','season':season,'source':SOURCE,'errorType':type(error).__name__,'errorCode':getattr(error,'code',None),'ranks':prior['ranks'] if valid else {}}
    return data
