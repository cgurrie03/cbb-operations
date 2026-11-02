from pathlib import Path
import hashlib,json,sys
import numpy as np,pandas as pd,joblib,sklearn
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge,LogisticRegression
from sklearn.ensemble import HistGradientBoostingRegressor,HistGradientBoostingClassifier,ExtraTreesRegressor,ExtraTreesClassifier
from sklearn.metrics import mean_absolute_error,mean_squared_error,log_loss,brier_score_loss

ROOT=Path('C:/Users/coope/Documents/Codex/2026-10-13/als/outputs/basketball-model')
OUT=Path('C:/Users/coope/Documents/Codex/2026-10-25/add/work/cbb-operations')
FEATURES=['eff_margin','eff_total','expected_pace','venue_effect']
PATHS=[ROOT/'blind-replay-20261014/train-24.parquet',ROOT/'blind-replay-20261014/pregame-24.parquet',ROOT/'spread-v3-20261017/features-2026.parquet']
cols=['game_id','season','decision_time','rating_cutoff','latest_result_used',*FEATURES]
x=pd.concat([pd.read_parquet(p,columns=cols) for p in PATHS],ignore_index=True)
games=pd.concat([pd.read_parquet(ROOT/'stage2/games.parquet'),pd.read_parquet(ROOT/'spread-v3-20261017/games-2026.parquet')],ignore_index=True)
assert x.game_id.is_unique and games.game_id.is_unique
assert (x.rating_cutoff<=x.decision_time).all()
known=x.latest_result_used.notna();assert (x.loc[known,'latest_result_used']<=x.loc[known,'rating_cutoff']).all()
d=x.merge(games[['game_id','margin','total','tipoff']],on='game_id',validate='one_to_one')
assert len(d)==len(x) and np.isfinite(d[FEATURES+['margin','total']].to_numpy()).all()
d['home_win']=(d.margin>0).astype(int)
def structures():
 return {
  'regression':(make_pipeline(StandardScaler(),Ridge(alpha=20)),make_pipeline(StandardScaler(),LogisticRegression(C=.1,max_iter=1500))),
  'boosted_trees':(HistGradientBoostingRegressor(max_iter=100,max_leaf_nodes=15,min_samples_leaf=50,l2_regularization=10,early_stopping=False,random_state=20261102),HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=15,min_samples_leaf=50,l2_regularization=10,early_stopping=False,random_state=20261102)),
  'extra_trees':(ExtraTreesRegressor(n_estimators=100,max_depth=12,min_samples_leaf=30,max_features=1.,n_jobs=4,random_state=20261102),ExtraTreesClassifier(n_estimators=100,max_depth=12,min_samples_leaf=30,max_features=1.,n_jobs=4,random_state=20261102))}
def fit(train):
 from sklearn.base import clone
 return {k:{'margin':clone(r).fit(train[FEATURES],train.margin),'total':clone(r).fit(train[FEATURES],train.total),'winner':clone(c).fit(train[FEATURES],train.home_win)} for k,(r,c) in structures().items()}
def predictions(models,test):
 return {k:np.column_stack([m['margin'].predict(test[FEATURES]),m['total'].predict(test[FEATURES]),m['winner'].predict_proba(test[FEATURES])[:,1]]) for k,m in models.items()}
def scores(test,p):
 return dict(games=len(test),marginMAE=float(mean_absolute_error(test.margin,p[:,0])),marginRMSE=float(np.sqrt(mean_squared_error(test.margin,p[:,0]))),totalMAE=float(mean_absolute_error(test.total,p[:,1])),totalRMSE=float(np.sqrt(mean_squared_error(test.total,p[:,1]))),winnerLogLoss=float(log_loss(test.home_win,np.clip(p[:,2],.000001,.999999),labels=[0,1])),winnerBrier=float(brier_score_loss(test.home_win,p[:,2])),winnerAccuracy=float(np.mean((p[:,2]>=.5)==test.home_win)))
folds=[]
for season in [2023,2024,2025,2026]:
 train=d[d.season<season];test=d[d.season==season]
 assert train.tipoff.max()+pd.Timedelta(hours=24)<test.decision_time.min()
 models=fit(train);pred=predictions(models,test)
 pred['ensemble']=np.mean(list(pred.values()),axis=0)
 pred['constant_baseline']=np.tile([train.margin.mean(),train.total.mean(),train.home_win.mean()],(len(test),1))
 pred['efficiency_baseline']=np.column_stack([test.eff_margin,test.eff_total,1/(1+np.exp(-test.eff_margin/10))])
 poison=test.copy();poison[['margin','total','home_win']]=999
 for k,p in predictions(models,poison).items():np.testing.assert_allclose(p,pred[k],rtol=0,atol=1e-10)
 folds.extend(dict(season=season,model=k,**scores(test,p)) for k,p in pred.items())
 print('fold',season,'games',len(test),flush=True)
models=fit(d);joblib.dump({'features':FEATURES,'models':models},OUT/'three-models.joblib',compress=3)
manifest={'version':'three-models-v1-20261102','createdAt':pd.Timestamp.now(tz='UTC').isoformat(),'sklearnVersion':sklearn.__version__,'fitThrough':2026,'features':FEATURES,'aggregation':'equal_weight_mean','names':{'regression':'Regularized regression','boosted_trees':'Boosted trees','extra_trees':'Randomized trees','ensemble':'Three-model average'},'modelHash':hashlib.sha256((OUT/'three-models.joblib').read_bytes()).hexdigest(),'trainingGames':len(d),'folds':folds,'sources':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in PATHS},'limitations':['Historical seasons were previously inspected; retrospective replay, not fresh blind validation','Original historical publication/revision timing remains incompletely reconstructed','Spread and total confidence is not established by point forecasts','Forward comparison starts with genuinely saved pregame forecasts only']}
(OUT/'three-models-manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False),encoding='utf8')
print(json.dumps({'status':'trained','models':list(models),'games':len(d),'artifactBytes':(OUT/'three-models.joblib').stat().st_size}),flush=True)

