"""Fit the preregistered team-score candidates and write a deployment artifact."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from team_score import design, predict, total_offset

def load(root):
    feature_paths = [root/'blind-replay-20261014'/f'{part}-24.parquet' for part in ['train','pregame']]
    feature_paths += [root/'spread-v3-20261017/features-2026.parquet']
    feature = pd.concat([pd.read_parquet(p) for p in feature_paths], ignore_index=True)
    games = pd.concat([pd.read_parquet(root/'stage2/games.parquet'), pd.read_parquet(root/'spread-v3-20261017/games-2026.parquet')], ignore_index=True)
    assert feature.game_id.is_unique and games.game_id.is_unique
    assert (feature.rating_cutoff <= feature.decision_time).all()
    assert (feature.latest_result_used.dropna() <= feature.loc[feature.latest_result_used.notna(),'rating_cutoff']).all()
    cols = ['game_id','tipoff','home_team','away_team','home_score','away_score','margin','total','possessions','box_usable']
    data = feature.drop(columns=[c for c in cols[1:] if c in feature]).merge(games[cols], on='game_id', validate='one_to_one')
    assert len(data) == len(feature)
    data['min_history'] = 0
    for season, fold in data.groupby('season'):
        past = games[games.season == season]
        teams = pd.concat([past[[side+'_team','tipoff']].rename(columns={side+'_team':'team'}) for side in ['home','away']])
        times = {team: np.sort((rows.tipoff + pd.Timedelta(hours=24)).dt.as_unit('ns').astype('int64').to_numpy()) for team,rows in teams.groupby('team')}
        assert (fold.tipoff > fold.rating_cutoff).all()
        cutoffs = fold.rating_cutoff.dt.as_unit('ns').astype('int64').to_numpy()
        counts = [np.array([times[team].searchsorted(t, side='right') for team,t in zip(fold[side+'_team'], cutoffs)]) for side in ['home','away']]
        data.loc[fold.index,'min_history'] = np.minimum(*counts)
    return data

def fit(data, method):
    x, sign = design(data)
    y = data[['home_score','away_score']].to_numpy()
    y = np.where(sign[:,None] > 0, y, y[:,::-1])
    weights = np.exp2((data.season.to_numpy() - data.season.max()) / 2) if method == 'recent' else None
    def linear(x, y, weights=None):
        scale = StandardScaler().fit(x, sample_weight=weights)
        model = Ridge(alpha=40).fit(scale.transform(x),y,sample_weight=weights)
        weights = model.coef_ / scale.scale_
        return {'weights':weights.tolist(),'intercept':(model.intercept_ - weights @ scale.mean_).tolist()}
    if method == 'robust':
        scale = StandardScaler().fit(x)
        model = HuberRegressor(epsilon=1.35,max_iter=500).fit(scale.transform(x),data.total)
        weights=model.coef_/scale.scale_
        return {'method':method,'total':{'weights':weights.tolist(),'intercept':float(model.intercept_-weights@scale.mean_)}}
    if method != 'possession':
        return {'method':method,'scores':linear(x,y,weights)}
    possessions = data.possessions.to_numpy()
    usable = data.box_usable.to_numpy() & np.isfinite(possessions) & (possessions > 40)
    return {'method':method,'possessions':linear(x[usable],possessions[usable]),
            'efficiency':linear(x[usable],100*y[usable]/possessions[usable,None])}

def control(train, test):
    x = ['eff_margin','eff_total','expected_pace','venue_effect']
    models = [
        make_pipeline(StandardScaler(),Ridge(alpha=20)),
        HistGradientBoostingRegressor(max_iter=100,max_leaf_nodes=15,min_samples_leaf=50,l2_regularization=10,early_stopping=False,random_state=20261102),
        ExtraTreesRegressor(n_estimators=100,max_depth=12,min_samples_leaf=30,max_features=1.,n_jobs=4,random_state=20261102),
    ]
    return np.column_stack([np.mean([model.fit(train[x],train[target]).predict(test[x]) for model in models],axis=0) for target in ['margin','total']])

def score(test, values, baseline):
    errors = test[['margin','total']].to_numpy()-values
    november = test.tipoff.dt.tz_convert('America/New_York').dt.month.eq(11).to_numpy()
    tail = november & (abs(baseline[:,0]) >= 20)
    return {'games':len(test),'mae':abs(errors).mean(axis=0).tolist(),
            'novemberGames':int(november.sum()),'novemberMAE':abs(errors[november]).mean(axis=0).tolist(),
            'tailGames':int(tail.sum()),'tailFavoriteBias':float(np.mean(errors[tail,0]*np.sign(baseline[tail,0]))),
            'novemberTotalBias':float(errors[november,1].mean()),
            'marginResidualBand':np.quantile(errors[:,0],[.1,.9]).tolist()}

def run(root, output):
    data=load(root)
    methods=['direct','possession','recent','rolling','robust']
    folds=[]
    residuals={m:[] for m in [*methods,'control']}
    for season in range(2023,2027):
        train,test=data[data.season<season],data[data.season==season]
        assert train.tipoff.max()+pd.Timedelta(hours=24)<test.decision_time.min()
        baseline=control(train,test)
        forecasts={m:predict(test,fit(train,m)) for m in methods if m!='rolling'}
        forecasts['robust'][:,0]=baseline[:,0]
        forecasts['rolling']=baseline.copy()
        tipoffs=test.tipoff.dt.as_unit('ns').astype('int64').to_numpy()
        total_errors=test.total.to_numpy()-baseline[:,1]
        for cutoff, batch in test.groupby('rating_cutoff').indices.items():
            ages=(cutoff.value-tipoffs)/86_400_000_000_000
            forecasts['rolling'][batch,1]+=total_offset(total_errors,ages)
        forecasts['control']=baseline
        scores={m:score(test,p,baseline) for m,p in forecasts.items()}
        for m,p in forecasts.items():
            residuals[m].extend((test.margin.to_numpy()-p[:,0]).tolist())
        folds.append({'season':season,**scores})
        print(folds[-1],flush=True)
    def pooled(model,key,column,weight):
        return float(np.average([f[model][key][column] for f in folds],weights=[f[model][weight] for f in folds]))
    selected={}
    for i,target in enumerate(['margin','total']):
        qualified=[m for m in methods if pooled(m,'mae',i,'games')<pooled('control','mae',i,'games')
                   and sum(f[m]['mae'][i]<f['control']['mae'][i] for f in folds)>=3
                   and pooled(m,'novemberMAE',i,'novemberGames')<=pooled('control','novemberMAE',i,'novemberGames')+.15]
        if qualified:
            selected[target]=min(qualified,key=lambda m:pooled(m,'mae',i,'games'))
    artifact={'version':'team-score-v1-20261106','fitThrough':int(data.season.max()),'selected':selected,
              'specs':{m:fit(data,m) for m in sorted(set(selected.values())-{'rolling'})},'folds':folds,
              'pooled':{m:{'marginMAE':pooled(m,'mae',0,'games'),'totalMAE':pooled(m,'mae',1,'games'),
                           'novemberMarginMAE':pooled(m,'novemberMAE',0,'novemberGames'),'novemberTotalMAE':pooled(m,'novemberMAE',1,'novemberGames')} for m in [*methods,'control']}}
    artifact['games']=sum(f['control']['games'] for f in folds)
    artifact['marginResidualBand']=np.quantile(residuals[selected.get('margin','control')],[.1,.9]).tolist()
    print(json.dumps({'selected':selected,'pooled':artifact['pooled']},indent=2),flush=True)
    output.write_text(json.dumps(artifact,indent=2,allow_nan=False)+'\n',encoding='utf-8')

if __name__=='__main__':
    run(Path(sys.argv[1]),Path(sys.argv[2]))
