export function betProbability(game,market,selection,line,artifact){
 if(artifact?.version!=='exact-bet-cdf-v1-20261026')return null;
 const key=market==='totals'?'totals':'spreads',point=key==='totals'?game.expectedTotal:game.modelMargin,curve=artifact.curves?.[key]?.cdf;
 if(!Number.isFinite(point)||!curve?.length||!game.preview)return null;
 if(key==='spreads'&&Math.abs(point-game.preview.carryover_margin)>1e-6)return null;
 const cdf=v=>{const x=(v-point-artifact.grid_start)/artifact.grid_step,i=Math.floor(x),a=curve[Math.max(0,Math.min(curve.length-1,i))],b=curve[Math.max(0,Math.min(curve.length-1,i+1))];return x<0?curve[0]:x>=curve.length-1?curve.at(-1):a+(b-a)*(x-i)};
 let win,loss,push;
 if(market==='h2h'){win=1-cdf(.5);loss=cdf(-.5);const sum=win+loss;win/=sum;loss/=sum;push=0}
 else{
  if(!Number.isFinite(line))return null;const threshold=market==='totals'?line:-line;win=1-cdf(Math.floor(threshold)+.5);loss=cdf(Math.ceil(threshold)-.5);push=Math.max(0,1-win-loss);
  const m=artifact.calibrators?.[market];if(!m||!Number.isFinite(m.coef)||m.coef<0)return null;
  const raw=Math.max(.005,Math.min(.995,win/(win+loss))),p=1/(1+Math.exp(-(m.coef*Math.log(raw/(1-raw))+m.intercept)));win=p*(1-push);loss=(1-p)*(1-push);
 }
 // Spread line is expressed as the home handicap for both selections.
 if(selection==='away'||selection==='Under')[win,loss]=[loss,win];
 return {win,loss,push};
}
export function bestBet(game,market,artifact,books=null,at=Date.now()){
 if(game.timeValid===true&&Date.parse(game.tipoff)<=at)return null;
 if(game.completed||['STATUS_CANCELED','STATUS_CANCELLED','STATUS_POSTPONED'].includes(game.status))return null;
 const picks=[];
 for(const selection of market==='totals'?['Over','Under']:['home','away']){
  // Compare the best available line for each side; price breaks equal-line ties.
  // A recommendation always links to the same real offer shown for that side.
  const quote=globalThis.OddsSelection.best(game,market,selection,{books,now:at});
  for(const q of quote?[quote]:[]){
   const p=betProbability(game,market,selection,market==='spreads'&&selection==='away'?-q.point:q.point,artifact);if(!p)continue;
   const ev=p.win*(globalThis.OddsSelection.decimal(q.price)-1)-p.loss;picks.push({...q,market,selection,...p,ev});
  }
 }
 return picks.sort((a,b)=>b.ev-a.ev||b.win-a.win||a.bookKey.localeCompare(b.bookKey))[0]||null;
}
export function gameBestBet(game,artifact,books=null){return ['spreads','totals','h2h'].map(m=>bestBet(game,m,artifact,books)).filter(Boolean).sort((a,b)=>b.ev-a.ev)[0]||null}
