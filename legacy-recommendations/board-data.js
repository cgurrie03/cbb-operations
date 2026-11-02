export const cancelled=g=>['STATUS_CANCELED','STATUS_CANCELLED','STATUS_POSTPONED'].includes(g.status);
export const eligibleToDisplay=g=>typeof g.homeD1==='boolean'&&typeof g.awayD1==='boolean'?g.homeD1||g.awayD1:Boolean(g.homeD1||g.awayD1||g.hasD1Team);
export function prepareBoard(data,preseason,paper,at=Date.now()){
 const previews=new Map((preseason?.previews||[]).map(r=>[r.game_id,r]));
 const byGame=new Map();for(const r of paper?.records||[]){if(r.candidate!=='enhanced_raw'||r.model_version!==preseason?.model_version)continue;const rows=byGame.get(r.game_id)||[];rows.push(r);byGame.set(r.game_id,rows)}
 return data.upcoming.filter(eligibleToDisplay).map(source=>{
  const g={...source};const preview=previews.get(g.id);
  const time=t=>Date.parse(t),sameTip=t=>Number.isFinite(time(t))&&Math.abs(time(t)-time(g.tipoff))<=300000;
  const records=(byGame.get(g.id)||[]).filter(r=>(!preseason?.model_sha256||r.model_sha256===preseason.model_sha256)&&sameTip(r.tipoff)&&time(r.issued_at)<=at&&time(r.tipoff)-time(r.issued_at)<=86400000&&time(r.issued_at)<=time(r.cutoff)&&time(r.cutoff)<=time(r.tipoff)-3600000).sort((a,b)=>time(b.issued_at)-time(a.issued_at));
  g.paperForecast=!cancelled(g)&&g.timeValid===true?records[0]||null:null;
  g.preview=!cancelled(g)&&preview&&(!preview.time_confirmed||sameTip(preview.tipoff))?preview:null;
  g.modelMargin=Number.isFinite(g.paperForecast?.projected_margin)?g.paperForecast.projected_margin:Number.isFinite(g.preview?.carryover_margin)?g.preview.carryover_margin:null;
  g.expectedTotal=Number.isFinite(g.preview?.projected_total)&&g.preview.total_model_version===preseason?.totals_model?.version&&g.preview.total_model_sha256===preseason?.totals_model?.sha256?g.preview.projected_total:null;
  g.modelState=cancelled(g)?'Unavailable':g.paperForecast?'Paper forecast':g.preview?'Preview':'Not issued';
  return g;
 });
}
