"""Hosted operations only. Frozen model code and fitted artifacts are never edited."""
from pathlib import Path
from datetime import datetime,timezone,timedelta,time
from zoneinfo import ZoneInfo
import argparse,gzip,hashlib,json,os,shutil,subprocess,sys,urllib.request,zipfile

ROOT=Path(__file__).resolve().parent
RUNTIME=ROOT/'runtime'
MODEL=RUNTIME/'outputs/basketball-model'
PUBLIC=RUNTIME/'outputs/court-signal/dist'
STATE=ROOT/'state-checkout'
PUBLISHED=ROOT/'public-checkout'
ET=ZoneInfo('America/New_York')
FILES=['data.json','preseason-2027.json','paper-ledger-2027.json','schedule.json','operations-health.json']

def now():return datetime.now(timezone.utc)
def stamp():return now().isoformat()
def dump(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(d,separators=(',',':'),allow_nan=False),encoding='utf8')
def read(p,default=None):return json.loads(p.read_text(encoding='utf8')) if p.exists() else default
def git(cwd,*args):
    p=subprocess.run(['git','-C',str(cwd),*args],capture_output=True,text=True)
    if p.returncode:raise RuntimeError('Git operation failed: '+args[0])
    return p.stdout.strip()
def commit(cwd,message):
    git(cwd,'add','--all')
    if not git(cwd,'status','--porcelain'):return git(cwd,'rev-parse','HEAD')
    git(cwd,'-c','user.name=CBB operations','-c','user.email=actions@users.noreply.github.com','commit','-m',message)
    git(cwd,'push','origin','HEAD')
    return git(cwd,'rev-parse','HEAD')

def mutable():
    for directory in [RUNTIME/'work',MODEL/'preseason-2027-20261018/raw']:
        if directory.exists():yield from (p for p in directory.rglob('*') if p.is_file() and not p.name.endswith(('.lock','.pending')))
    for name in ['rosters-latest.json','roster-audit.json','roster-audit.csv','readiness-latest.json']:
        p=MODEL/'preseason-2027-20261018'/name
        if p.exists():yield p
    yield from (p for p in PUBLIC.glob('*.json') if p.name in FILES)

def checkpoint():
    for p in mutable():
        dest=STATE/'state'/str(p.relative_to(RUNTIME))
        dest=dest.with_name(dest.name+'.gz');dest.parent.mkdir(parents=True,exist_ok=True)
        blob=gzip.compress(p.read_bytes(),compresslevel=6,mtime=0)
        if not dest.exists() or dest.read_bytes()!=blob:dest.write_bytes(blob)
    commit(STATE,'Persist collector state '+stamp())

def bootstrap():
    RUNTIME.mkdir(exist_ok=True)
    with zipfile.ZipFile(ROOT/'frozen-runtime.zip') as z:z.extractall(RUNTIME)
    for p in (STATE/'state').rglob('*.gz'):
        dest=RUNTIME/p.relative_to(STATE/'state');dest=dest.with_suffix('')
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(gzip.decompress(p.read_bytes()))
    PUBLIC.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(MODEL))

def next_due(t):
    local=t.astimezone(ET);slots=[]
    for offset in range(3):
        day=local.date()+timedelta(days=offset)
        times=[time(h) for h in [9,12,15,18,21]]
        if day.isoformat()=='2026-11-01':times.append(time(22,45))
        slots += [datetime.combine(day,v,ET) for v in times]
    return min(s for s in slots if s>local).astimezone(timezone.utc).isoformat()

def slot(t):
    local=t.astimezone(ET)
    if local.date().isoformat()=='2026-11-01' and time(22,45)<=local.time()<time(23,45):return '2026-11-01T22:45'
    if local.hour in [9,12,15,18,21]:return local.strftime('%Y-%m-%dT%H:00')
    return None

def canonical(events,source,membership,old):
    """Display normalization only: stable IDs, explicit times and cancellation state."""
    rows=[];prior={g['id']:g for g in old}
    for e in events:
        if e.get('season',{}).get('year')!=2027 or e.get('season',{}).get('type') not in [2,3]:continue
        c=e['competitions'][0];teams={v['homeAway']:v['team'] for v in c['competitors']}
        if set(teams)!={'home','away'}:raise ValueError('Ambiguous schedule sides')
        key='espn:'+str(e['id']);g=dict(prior.get(key,{}));tip=e['date'];status=c.get('status',{}).get('type',{})
        g.update(id=key,season=2027,tipoff=tip,day=datetime.fromisoformat(tip.replace('Z','+00:00')).astimezone(ET).date().isoformat(),
                 observed=source['observed_at'],scheduleSourceSha256=source['sha256'],timeValid=c.get('timeValid') is True,
                 neutral=c.get('neutralSite'),status=status.get('name','STATUS_SCHEDULED'),statusDetail=status.get('description','Scheduled'),
                 completed=status.get('completed') is True,core=None,marginModel=None,blend=None,expectedMargin=None,expectedTotal=None)
        for side,t in teams.items():
            g[side]=t['displayName'];g[side+'School']=t.get('location',t['displayName']);g[side+'TeamId']=str(t['id'])
            g[side+'D1']='espn:'+str(t['id']) in membership
            logos=t.get('logos',[]);logo=t.get('logo') or (logos[0].get('href') if logos else None)
            if logo:g[side+'Logo']=logo;g[side+'LogoSource']=logo
            g.setdefault(side+'Conference','UNVERIFIED')
        venue=c.get('venue') or {}
        g['venue']=venue.get('fullName');g['city']=(venue.get('address') or {}).get('city');g['region']=(venue.get('address') or {}).get('state');g['designatedHome']=g['home']
        g['hasD1Team']=bool(g['homeD1'] or g['awayD1'])
        g['divisionVerified']=True
        g.setdefault('availability','unverified')
        g.pop('odds',None);rows.append(g)
    return sorted(rows,key=lambda g:(g['tipoff'],g['id']))

def attach_cached_odds(data,cache,history):
    """Display matching accepts swapped neutral-site designations, never fuzzy teams.
    Timing conflicts are disclosed; forecast issuance still uses frozen matching.
    """
    import re
    norm=lambda s:re.sub('[^a-z0-9]','',s.lower())
    matched=0
    for event in (cache or {}).get('events',[]):
        provider={norm(event['home_team']),norm(event['away_team'])}
        candidates=[g for g in data['upcoming'] if g['status'] not in ['STATUS_CANCELED','STATUS_CANCELLED','STATUS_POSTPONED'] and
                    {norm(g['home']),norm(g['away'])}==provider and
                    abs((datetime.fromisoformat(g['tipoff'].replace('Z','+00:00'))-datetime.fromisoformat(event['commence_time'].replace('Z','+00:00'))).total_seconds())<=129600]
        if len(candidates)==1:
            g=candidates[0]
            delta=abs((datetime.fromisoformat(g['tipoff'].replace('Z','+00:00'))-datetime.fromisoformat(event['commence_time'].replace('Z','+00:00'))).total_seconds())
            g['odds']=dict(eventId=event['id'],collectedAt=cache['collectedAt'],bookmakers=event.get('bookmakers',[]),
                homeName=next(n for n in [event['home_team'],event['away_team']] if norm(n)==norm(g['home'])),
                awayName=next(n for n in [event['home_team'],event['away_team']] if norm(n)==norm(g['away'])),
                providerTipoff=event['commence_time'],timingStatus='unconfirmed' if not g['timeValid'] else 'conflict' if delta>300 else 'aligned',
                designationReversed=norm(g['home'])!=norm(event['home_team']),history=history(event['id']))
            matched+=1
    return matched


def publish(health):
    health['lastPublicationAt']=stamp();health['nextExpectedRunAt']=next_due(now())
    public_health={k:v for k,v in health.items() if k not in ['lastReadbackAt','publicRevision']}
    public_health['readbackStatus']='Revision verified before activation'
    dump(PUBLIC/'operations-health.json',public_health)
    for name in FILES:
        if (PUBLIC/name).exists():shutil.copyfile(PUBLIC/name,PUBLISHED/name)
    revision=commit(PUBLISHED,'Publish website data '+stamp())
    # Immutable revision readback avoids branch-cache delay and verifies persisted bytes.
    for name in FILES:
        if not (PUBLIC/name).exists():continue
        url=f'https://raw.githubusercontent.com/cgurrie03/cbb-public-data/{revision}/{name}'
        with urllib.request.urlopen(url,timeout=45) as r:remote=r.read()
        if hashlib.sha256(remote).digest()!=hashlib.sha256((PUBLIC/name).read_bytes()).digest():raise RuntimeError('Public readback mismatch')
    # Switch one small pointer only after every file in this revision is readable.
    dump(PUBLISHED/'current.json',{'revision':revision,'publishedAt':health['lastPublicationAt'],'files':FILES})
    commit(PUBLISHED,'Activate verified data revision '+revision[:12])
    health['lastReadbackAt']=stamp();health['publicRevision']=revision
    dump(RUNTIME/'work/operations-health.json',health);checkpoint()
    print(json.dumps({'status':health['status'],'public_revision':revision,'readback':'verified'}))

def run(public_only=False,scheduled=False):
    bootstrap()
    previous=read(RUNTIME/'work/operations-health.json',{})
    current_slot=slot(now())
    if scheduled and (not current_slot or previous.get('lastCompletedSlot')==current_slot):
        print('No due slot; duplicate or daylight-saving alternate skipped');return
    health={**previous,'lastAttemptAt':stamp(),'status':'running','hosting':'GitHub Actions','cadence':'09:00, 12:00, 15:00, 18:00, 21:00 Eastern',
            'openingNightCheck':'2026-11-01T22:45:00-05:00','slot':current_slot,'errorStage':None}
    dump(RUNTIME/'work/operations-health.json',health);checkpoint()
    stage='schedule'
    failed=False
    previous_public={name:(PUBLIC/name).read_bytes() if (PUBLIC/name).exists() else None for name in FILES if name!='operations-health.json'}
    try:
        import prospective_run as pr,preseason_prepare as prep,odds_collector as odds,odds_history
        today=now().astimezone(ET).date();date=max(today.isoformat(),'2026-11-01')
        original_fetch=pr.fetch;schedules={};allrows=[];sources=[]
        data=read(PUBLIC/'data.json');members=prep.members()
        for offset in range(14):
            day=(datetime.fromisoformat(date).date()+timedelta(days=offset)).isoformat()
            url=prep.BASE+'scoreboard?dates='+day.replace('-','')+'&groups=50&limit=1000'
            body,source=original_fetch(url,'schedules')
            if 'events' not in body or len(body['events'])>=1000:raise RuntimeError('Invalid or truncated schedule')
            schedules[url]=(body,source);sources.append({k:v for k,v in source.items() if k!='path'})
            allrows.extend(canonical(body['events'],source,members,data['upcoming']))
        # Both the paper pipeline and main view consume exactly these observations.
        pr.fetch=lambda url,kind:schedules[url] if kind=='schedules' and url in schedules else original_fetch(url,kind)
        original_slate=pr.slate
        def slate(day):
            frame,source=original_slate(day)
            if frame.empty:
                import pandas as pd
                frame=pd.DataFrame(columns=['game_id','eligible','tipoff','decision_time'])
                frame['tipoff']=pd.to_datetime(frame.tipoff,utc=True);frame['decision_time']=pd.to_datetime(frame.decision_time,utc=True)
            cancelled={g['id'] for g in allrows if g['status'] in ['STATUS_CANCELED','STATUS_CANCELLED','STATUS_POSTPONED'] or g['completed']}
            frame.loc[frame.game_id.isin(cancelled),'eligible']=False
            return frame,source
        pr.slate=slate
        revision=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()
        unique={g['id']:g for g in allrows};data['upcoming']=sorted(unique.values(),key=lambda g:(g['tipoff'],g['id']))
        data['snapshotDate']=now().astimezone(ET).date().isoformat();data['scheduleFeed']={'observedAt':max(s['observed_at'] for s in sources),'revision':revision,'dateStart':date,'days':14,'games':len(unique)}
        dump(PUBLIC/'schedule.json',{'revision':revision,'sources':sources,'games':data['upcoming']});dump(PUBLIC/'data.json',data)
        health['scheduleObservedAt']=data['scheduleFeed']['observedAt'];health['scheduleRevision']=revision;health['scheduleGames']=len(unique)
        stage='odds'
        original_write=odds.write
        def durable_write(path,value):
            original_write(path,value)
            if path.name=='usage.json':checkpoint()
        odds.write=durable_write;odds.load_key=lambda:os.environ['ODDS_API_KEY']
        # Ten US operators cost the same one region-equivalent as the prior request.
        # Keep the frozen quota reservation and request accounting intact.
        from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
        original_urlopen=odds.urlopen
        def major_books(request,**kwargs):
            parts=urlsplit(request.full_url);params=dict(parse_qsl(parts.query))
            if parts.hostname=='api.the-odds-api.com' and parts.path.endswith('/odds/'):
                params.pop('regions',None)
                params['bookmakers']='draftkings,fanduel,betmgm,betrivers,williamhill_us,fanatics,hardrockbet,ballybet,betparx,espnbet'
                request=urllib.request.Request(urlunsplit((parts.scheme,parts.netloc,parts.path,urlencode(params),parts.fragment)),headers=dict(request.header_items()))
            return original_urlopen(request,**kwargs)
        odds.urlopen=major_books
        reserve=today.isoformat()=='2026-11-01' and now().astimezone(ET).hour==21
        result={'status':'public_only_check' if public_only else 'opening_night_credit_reserved'} if public_only or reserve else odds.collect()
        health['oddsAttemptStatus']=result['status'];health['lastPaidAttemptAt']=read(odds.OUT/'usage.json',{'calls':[]})['calls'][-1:][0]['at'] if read(odds.OUT/'usage.json',{'calls':[]})['calls'] else None
        if result['status'] in ['provider_error','connection_or_response_error']:failed=True;health['errorStage']='odds'
        cache=read(odds.OUT/'latest.json');data=read(PUBLIC/'data.json')
        for g in data['upcoming']:g.pop('odds',None)
        matched=attach_cached_odds(data,cache,odds_history.history_for)
        if cache:
            data['oddsFeed']={k:v for k,v in cache.items() if k not in ['events','snapshotFile']}
            data['oddsFeed'].update(matchedGames=matched,status='failed' if failed else 'success',attemptStatus=result['status'],mode='five periodic snapshots/day')
            health['oddsLastSuccessAt']=cache['collectedAt'];health['oddsEventCount']=cache['eventCount'];health['oddsMatchedGames']=matched
            data['oddsFeed']['requestedBookmakers']=['draftkings','fanduel','betmgm','betrivers','williamhill_us','fanatics','hardrockbet','ballybet','betparx','espnbet']
        dump(PUBLIC/'data.json',data)
        stage='paper'
        pr.run(date)
        preparation=read(PUBLIC/'preseason-2027.json');preparation.update(collection='Hosted GitHub Actions collector; runs while this computer is offline',schedule_revision=revision)
        dump(PUBLIC/'preseason-2027.json',preparation)
        # Publish existing immutable model outputs; never recompute or edit a forecast.
        issued={ (r['game_id'],r['candidate'],r['issued_at']):r for p in (pr.PRIVATE/'forecasts').glob('*.json') for r in [read(p)] }
        paper=read(PUBLIC/'paper-ledger-2027.json')
        for row in paper['records']:
            original=issued.get((row['game_id'],row['candidate'],row['issued_at']),{})
            row['projected_margin']=original.get('projected_margin')
            row['model_sha256']=original.get('model_sha256')
        dump(PUBLIC/'paper-ledger-2027.json',paper)
        health['paperLastSuccessAt']=preparation['updated_at'];health['formalReviewDue']=preparation['formal_review_eligible'];health['collectionReviewDue']=preparation['collection_review_due']
        stage='rankings'
        import refresh_site_rankings
        refresh_site_rankings.main()
        ledger=read(odds.OUT/'usage.json',{'calls':[]})
        health['quota']={'remainingCredits':ledger.get('remaining'),'attemptsToday':sum(c['day']==today.isoformat() for c in ledger['calls']),
            'rolling31DayCredits':sum(c.get('credits',3) for c in ledger['calls'] if datetime.fromisoformat(c['at'])>now()-timedelta(days=31)),
            'maximumAttemptsPerDay':5,'maximumRollingCredits':500,'lastOutcome':result['status']}
        health['lastSuccessAt']=stamp();health['lastCompletedSlot']=current_slot;health['status']='degraded' if failed else 'success'
    except Exception as error:
        failed=True;health.update(status='failed',errorStage=stage,errorType=type(error).__name__)
        # A partial pipeline must not activate a new schedule with an old paper view.
        for name,blob in previous_public.items():
            if blob is not None:(PUBLIC/name).write_bytes(blob)
            elif (PUBLIC/name).exists():(PUBLIC/name).unlink()
        for field in ['scheduleObservedAt','scheduleRevision','scheduleGames','paperLastSuccessAt']:
            health[field]=previous.get(field)
        # Never expose URLs, tokens, credentials or full exception text.
        print('Collection stage failed:',stage,type(error).__name__)
    try:publish(health)
    finally:checkpoint()
    if failed:raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--public-only',action='store_true');parser.add_argument('--scheduled',action='store_true');parser.add_argument('--gate',action='store_true')
    args=parser.parse_args()
    if args.gate:print('true' if slot(now()) else 'false')
    else:run(args.public_only,args.scheduled)
