"""Display projections across the slate; never rewrites issued spread records."""
from pathlib import Path
import hashlib,json,math
import numpy as np,pandas as pd

def total_prediction(artifact,features):
    values=np.asarray([features[k] for k in artifact['features']],dtype=float)
    if not np.isfinite(values).all():return None
    result=float(np.dot((values-np.asarray(artifact['mean']))/np.asarray(artifact['scale']),np.asarray(artifact['coef']))+artifact['intercept'])
    return result if math.isfinite(result) and result>0 else None

def publish_previews(pr,data,preparation,artifact_path):
    artifact_path=Path(artifact_path);artifact=json.loads(artifact_path.read_text(encoding='utf8'));digest=hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    frames=[]
    for day in sorted({g['day'] for g in data['upcoming']}):
        frame,_=pr.slate(day)
        if len(frame):frames.append(frame)
    if not frames:return preparation
    frame=pd.concat(frames,ignore_index=True);cutoff=pd.Timestamp(pr.now())
    frame=frame[frame.eligible&frame.tipoff.gt(cutoff)&frame.decision_time.ge(cutoff)].drop_duplicates('game_id').copy()
    if frame.empty:return preparation
    x=pr.feature_rows(frame,cutoff);by_id=frame.set_index('game_id');previews=[]
    for row in x.to_dict('records'):
        g=by_id.loc[row['game_id']];confirmed=bool(g.time_confirmed)
        previews.append(dict(game_id=row['game_id'],home=g.home_name,away=g.away_name,tipoff=g.tipoff.isoformat() if confirmed else None,
            cutoff=g.decision_time.isoformat() if confirmed else None,time_confirmed=confirmed,carryover_margin=float(row['eff_margin']),
            projected_total=total_prediction(artifact,row),total_model_version=artifact['version'],total_model_sha256=digest,
            features_observed_at=cutoff.isoformat(),availability_verified=False,paper_status='research preview; issued records remain separate'))
    preparation['previews']=previews
    ranges_path=artifact_path.with_name('outcome-ranges.json')
    if ranges_path.exists():preparation['outcome_ranges']=json.loads(ranges_path.read_text())
    probability_path=artifact_path.with_name('bet-probabilities.json')
    if probability_path.exists():preparation['bet_probability_model']=json.loads(probability_path.read_text(encoding='utf8'))
    preparation['preview_scope']='All published future eligible D1-vs-D1 games, using only information available at publication'
    preparation['totals_model']={k:artifact[k] for k in ['version','fit_through','experimental','validation','pooled','folds','limitations']}
    preparation['totals_model']['sha256']=digest
    return preparation
