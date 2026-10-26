"""Display-only team context. Never used in prediction or selection features."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
import json,urllib.request,math
BASE='https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/'
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'CBB research context/1.0'}),timeout=15) as r:return json.load(r)
def summarize(games,season):
    games=sorted(games,key=lambda g:g['date']);n=len(games);ats=[g for g in games if g.get('ats') in ['W','L','P']]
    return {'season':season,'games':n,'record':f"{sum(g['result']=='W' for g in games)}-{sum(g['result']=='L' for g in games)}",'ppg':sum(g['scored'] for g in games)/n if n else None,'allowed':sum(g['allowed'] for g in games)/n if n else None,'lastFive':list(reversed(games[-5:])),'lastFiveRecord':f"{sum(g['result']=='W' for g in games[-5:])}-{sum(g['result']=='L' for g in games[-5:])}",'ats':{'wins':sum(g['ats']=='W' for g in ats),'losses':sum(g['ats']=='L' for g in ats),'pushes':sum(g['ats']=='P' for g in ats),'coveredGames':len(ats),'totalGames':n}}
def schedule_games(payload,tid,season,at):
    out=[]
    for e in payload.get('events',[]):
        if e.get('season',{}).get('year')!=season:continue
        if int(e.get('seasonType',{}).get('type',0)) not in [2,3]:continue
        c=e.get('competitions',[{}])[0]
        if not c.get('status',{}).get('type',{}).get('completed'):continue
        if datetime.fromisoformat(e['date'].replace('Z','+00:00'))>=at:continue
        mine=next((v for v in c.get('competitors',[]) if str(v.get('id'))==tid),None);other=next((v for v in c.get('competitors',[]) if str(v.get('id'))!=tid),None)
        if not mine or not other:continue
        def score(v):
            x=v.get('score');return float(x.get('value',x.get('displayValue'))) if isinstance(x,dict) else float(x)
        try:a,b=score(mine),score(other)
        except (ValueError,TypeError):continue
        if not math.isfinite(a+b) or a==b:continue
        out.append({'id':'espn:'+str(e['id']),'date':e['date'],'opponent':other.get('team',{}).get('displayName','Unknown'),'opponentId':str(other['id']),'scored':a,'allowed':b,'result':'W' if a>b else 'L','ats':None,'spread':None,'book':None})
    return out

def collect(data,root,at=None,fetch=get):
    root=Path(root);at=at or datetime.now(timezone.utc);stamp=at.isoformat();season=max((g.get('season',0) for g in data['upcoming']),default=at.year)
    seeds=json.loads((root/'team-history.json').read_text());prior=data.get('teamContexts',{});teams={str(g[side+'TeamId']) for g in data['upcoming'] for side in ['away','home'] if g.get(side+'D1') and g.get(side+'TeamId')}
    def team(tid):
        prev=prior.get(tid,{});checked=prev.get('scheduleCheckedAt')
        if checked and prev.get('current',{}).get('season')==season and at-datetime.fromisoformat(checked)<timedelta(hours=3):return tid,prev
        current=[];status='available'
        try:
            types=[2,3] if at.month in [3,4,5,6] else [2]
            for phase in types:current+=schedule_games(fetch(BASE+f'teams/{tid}/schedule?season={season}&seasontype={phase}'),tid,season,at)
            current=list({g['id']:g for g in current}.values())
        except Exception:
            if prev:return tid,{**prev,'scheduleStatus':'delayed'}
            status='unavailable'
        cached_ats=prev.get('atsGames',{}) if prev.get('current',{}).get('season')==season else {}
        for game in current:
            if game['id'] in cached_ats:game.update(cached_ats[game['id']])
            source=next((g for g in data['upcoming'] if g['id']==game['id']),None)
            if source:
                side='home' if str(source.get('homeTeamId'))==tid else 'away';team_name=source.get(side)
                history=[h for h in source.get('odds',{}).get('history',[]) if h.get('market')=='spreads' and h.get('selection') in [side,team_name] and h.get('point') is not None and h.get('observed_at') and h['observed_at']<game['date']]
                if history:
                    h=max(history,key=lambda h:h['observed_at']);edge=game['scored']-game['allowed']+h['point'];game.update(ats='W' if edge>0 else 'L' if edge<0 else 'P',spread=h['point'],book=h.get('book_name',h.get('book')))
        previous=summarize(seeds.get(tid,{}).get('games',[]),season-1)
        return tid,{'current':summarize(current,season),'atsGames':{g['id']:{k:g[k] for k in ['ats','spread','book']} for g in current if g.get('ats')},'previous':previous,'scheduleCheckedAt':stamp,'scheduleStatus':status,'source':BASE+f'teams/{tid}/schedule?season={season}&seasontype=2','previousSource':'ESPN normalized final-score archive; ATS uses provider-labelled closing lines only'}
    with ThreadPoolExecutor(max_workers=6) as pool:contexts=dict(pool.map(team,sorted(teams)))
    # Current ATS uses only saved pre-tip quotes, one latest observation per game/team.
    for tid,context in contexts.items():
        context['injuries']=[];context['injuryCoverage']='No verified report';context['injuryCheckedAt']=stamp
    try:
        payload=fetch(BASE+'injuries');groups=payload.get('injuries',[])
        for group in groups:
            tid=str(group.get('team',{}).get('id',group.get('id','')));context=contexts.get(tid)
            if context is None:continue
            for row in group.get('injuries',[]):
                athlete=row.get('athlete',{});status=row.get('status') or row.get('type',{}).get('description');published=row.get('date')
                if not athlete.get('displayName') or not status or not published:continue
                issued=datetime.fromisoformat(published.replace('Z','+00:00'))
                if issued>at or at-issued>timedelta(days=7):continue
                ppg=None;ppg_season=season
                try:
                    stats=fetch(f'https://site.web.api.espn.com/apis/common/v3/sports/basketball/mens-college-basketball/athletes/{athlete["id"]}/overview?season={season}').get('statistics',{})
                    index=stats.get('names',[]).index('avgPoints')
                    for year in [season,season-1]:
                        split=next((v for v in stats.get('splits',[]) if v.get('displayName')==f'{year-1}-{str(year)[-2:]}'),None)
                        if split:
                            ppg=float(split['stats'][index]);ppg_season=year;break
                except Exception:pass
                context['injuries'].append({'name':athlete['displayName'],'position':athlete.get('position',{}).get('abbreviation','—'),'status':status,'reportedAt':published,'source':BASE+'injuries','sourceName':'ESPN report','ppg':ppg,'ppgSeason':ppg_season,'official':False})
            if context['injuries']:context['injuryCoverage']='Reported; coverage incomplete'
        injury_status='available' if groups else 'no_reports'
    except Exception:injury_status='unavailable'
    # Reviewed news notes expire automatically; they never become official game designations.
    for note in json.loads((root/'availability-notes.json').read_text()):
        tid=note['teamId'];context=contexts.get(tid)
        if context is None or datetime.fromisoformat(note['expiresAt'])<=at:continue
        if not any(v['name']==note['name'] for v in context['injuries']):context['injuries'].append(note)
        context['injuryCoverage']='Media report; not official game status'
    data['teamContexts']=contexts;data['teamContextFeed']={'checkedAt':stamp,'teams':len(contexts),'injuryStatus':injury_status,'source':'ESPN','displayOnly':True,'coverage':'Report absence does not establish player availability. Historical statistics are labelled by season.'}
    return data
