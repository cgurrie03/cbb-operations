"""Frozen three-structure forecasts with an append-only prospective comparison."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,math
import joblib,numpy as np,pandas as pd

from team_score import predict as predict_team_scores

IDS=['regression','boosted_trees','extra_trees']
def read(path,default=None):return json.loads(Path(path).read_text(encoding='utf8')) if Path(path).exists() else default
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,separators=(',',':'),allow_nan=False),encoding='utf8')
def parse(t):return datetime.fromisoformat(t.replace('Z','+00:00'))
def aggregate(models):
    if set(models)!=set(IDS):raise ValueError('All three structures required')
    result={k:sum(models[m][k] for m in IDS)/3 for k in ['margin','total','homeWinProbability']}
    if not all(math.isfinite(v) for v in result.values()) or result['total']<=0 or not 0<=result['homeWinProbability']<=1:raise ValueError('Invalid ensemble')
    return result
def eligible(record,game):
    return (record['tipoff']==game['tipoff'] and record['homeTeamId']==game['homeTeamId'] and record['awayTeamId']==game['awayTeamId'] and parse(game['tipoff'])-timedelta(hours=24)<=parse(record['observedAt'])<=parse(game['tipoff'])-timedelta(minutes=60))
def metrics(rows):
    result={}
    for model in [*IDS,'ensemble']:
        if not rows:result[model]={'games':0,'marginMAE':None,'totalMAE':None,'winnerLogLoss':None,'winnerBrier':None,'winnerAccuracy':None};continue
        errors=[]
        for r,g in rows:
            pred=r['models'][model] if model!='ensemble' else r['ensemble']
            margin=g['homeScore']-g['awayScore'];total=g['homeScore']+g['awayScore'];y=int(margin>0);p=min(.999999,max(.000001,pred['homeWinProbability']))
            errors.append((abs(pred['margin']-margin),abs(pred['total']-total),-y*math.log(p)-(1-y)*math.log(1-p),(p-y)**2,int((p>=.5)==bool(y))))
        means=np.mean(errors,axis=0);result[model]=dict(games=len(rows),**dict(zip(['marginMAE','totalMAE','winnerLogLoss','winnerBrier','winnerAccuracy'],map(float,means))))
    return result

def publish(pr,data,root,state,at):
    root,state=Path(root),Path(state);manifest=read(root/'three-models-manifest.json');artifact=root/'three-models.joblib'
    if hashlib.sha256(artifact.read_bytes()).hexdigest()!=manifest['modelHash']:raise ValueError('Three-model artifact mismatch')
    score_spec=read(root/'team-score.json')
    bundle=joblib.load(artifact);games={g['id']:g for g in data['upcoming']};frames=[]
    for day in sorted({g['day'] for g in data['upcoming'] if not g.get('completed') and parse(g['tipoff'])>parse(at)}):
        frame,_=pr.slate(day)
        if len(frame):frames.append(frame)
    if frames:
        frame=pd.concat(frames,ignore_index=True).drop_duplicates('game_id');frame=frame[frame.eligible&frame.tipoff.gt(pd.Timestamp(at))]
        if len(frame):
            x=pr.feature_rows(frame,pd.Timestamp(at));features=x[bundle['features']]
            if not np.isfinite(features.to_numpy()).all():raise ValueError('Missing three-model features')
            values={k:np.column_stack([m['margin'].predict(features),m['total'].predict(features),m['winner'].predict_proba(features)[:,1]]) for k,m in bundle['models'].items()}
            score_values={}
            if score_spec:
                forecasts={name:predict_team_scores(x,spec) for name,spec in score_spec['specs'].items()}
                score_values={target:forecasts[method][:,['margin','total'].index(target)] for target,method in score_spec['selected'].items()}
            for i,row in enumerate(x.to_dict('records')):
                g=games.get(row['game_id'])
                if not g or g.get('completed') or g.get('timeValid') is not True:continue
                predictions={k:dict(zip(['margin','total','homeWinProbability'],map(float,v[i]))) for k,v in values.items()}
                issued=datetime.now(timezone.utc).isoformat()
                if parse(issued)>=parse(g['tipoff']):continue
                record=dict(gameId=g['id'],homeTeamId=g['homeTeamId'],awayTeamId=g['awayTeamId'],tipoff=g['tipoff'],observedAt=issued,featuresObservedAt=at,version=manifest['version'],modelHash=manifest['modelHash'],models=predictions,ensemble=aggregate(predictions))
                if score_values:
                    adjusted={target:float(v[i]) for target,v in score_values.items()}
                    margin=adjusted.get('margin',record['ensemble']['margin'])
                    total=adjusted.get('total',record['ensemble']['total'])
                    if not all(math.isfinite(v) for v in adjusted.values()) or total<=abs(margin):
                        raise ValueError('Invalid team-score projection')
                    record['teamScore']={'version':score_spec['version'],**adjusted}
                g['modelComparison']=record
                if eligible(record,g):
                    payload=json.dumps(record,sort_keys=True,separators=(',',':'),allow_nan=False).encode();key=hashlib.sha256(payload).hexdigest()
                    path=state/'forecasts'/(key+'.json');path.parent.mkdir(parents=True,exist_ok=True)
                    if not path.exists():
                        with path.open('xb') as f:f.write(payload)
    canonical={}
    for path in (state/'forecasts').glob('*.json'):
        r=read(path);g=games.get(r['gameId'])
        if r['version']!=manifest['version'] or r['modelHash']!=manifest['modelHash'] or not g or not eligible(r,g):continue
        prior=canonical.get(g['id'])
        if not prior or parse(r['observedAt'])>parse(prior['observedAt']):canonical[g['id']]=r
    graded=[]
    for key,r in canonical.items():
        g=games[key]
        if not g.get('modelComparison'):g['modelComparison']=r
        if g.get('completed') and all(isinstance(g.get(k),(int,float)) and math.isfinite(g[k]) for k in ['homeScore','awayScore']):graded.append((r,g))
    data['modelComparison']={k:manifest[k] for k in ['version','createdAt','fitThrough','features','aggregation','names','modelHash','trainingGames','folds','limitations']}
    data['modelComparison'].update(updatedAt=at,forward=metrics(graded),forwardForecasts=len(canonical),forwardPending=len(canonical)-len(graded),earliestForecastAt=min((r['observedAt'] for r in canonical.values()),default=None))
    if score_spec:
        paired={}
        for target in score_spec['selected']:
            errors=[]
            for r,g in graded:
                projection=r.get('teamScore',{})
                if projection.get('version')!=score_spec['version'] or target not in projection:continue
                actual=g['homeScore']-g['awayScore'] if target=='margin' else g['homeScore']+g['awayScore']
                errors.append([abs(actual-projection[target]),abs(actual-r['ensemble'][target])])
            means=np.mean(errors,axis=0).tolist() if errors else [None,None]
            paired[target]=dict(games=len(errors),mae=means[0],controlMAE=means[1])
        data['teamScoreModel']={k:score_spec[k] for k in ['version','fitThrough','selected','games','pooled','folds','marginResidualBand']}
        data['teamScoreModel']['forward']=paired
    write(state/'comparison-latest.json',data['modelComparison'])
    return data
