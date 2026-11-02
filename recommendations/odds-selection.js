/* One actual sportsbook offer per selection. No synthetic line/price pairs. */
(function(root){
 'use strict';
 const decimal=price=>price>0?1+price/100:1+100/Math.abs(price);
 const age=(time,now)=>Number.isFinite(Date.parse(time))?(now-Date.parse(time))/60000:Infinity;
 function quotes(game,market,selection,{books=null,now=Date.now(),maxAge=180}={}){
  const feed=game.odds;
  if(!feed||age(feed.collectedAt,now)>maxAge||age(feed.collectedAt,now)<-5)return [];
  const name=market==='totals'?selection:selection==='home'?feed.homeName:feed.awayName;
  return (feed.bookmakers||[]).filter(b=>books===null||books.includes(b.key)).flatMap(book=>(book.markets||[]).filter(m=>m.key===market).flatMap(m=>(m.outcomes||[]).filter(o=>o.name===name).map(o=>({...o,book:book.title,bookKey:book.key,updated:m.last_update||book.last_update,link:o.link||m.link||book.link}))))
   .filter(q=>Number.isFinite(q.price)&&Math.abs(q.price)>=100&&(market==='h2h'||Number.isFinite(q.point))&&age(q.updated,now)<=maxAge&&age(q.updated,now)>=-5);
 }
 function best(game,market,selection,options={}){
  const offers=quotes(game,market,selection,options);
  const pointScore=q=>market==='h2h'?0:market==='totals'&&selection==='Over'?-q.point:q.point;
  offers.sort((a,b)=>pointScore(b)-pointScore(a)||decimal(b.price)-decimal(a.price)||Date.parse(b.updated)-Date.parse(a.updated)||a.bookKey.localeCompare(b.bookKey));
  return offers[0]||null;
 }
 root.OddsSelection={quotes,best,decimal};
 if(typeof module!=='undefined')module.exports=root.OddsSelection;
})(typeof globalThis==='undefined'?this:globalThis);
