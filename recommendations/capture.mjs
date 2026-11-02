// Use the same exact-offer selector as the website, at the actual observation time.
import './odds-selection.js';
import {prepareBoard} from './board-data.js';
import {bestBet} from './bet-confidence.js';
let input='';for await(const chunk of process.stdin)input+=chunk;
const {data,preparation,paper,at,sourceRevision}=JSON.parse(input),time=Date.parse(at),records=[];
for(const g of prepareBoard(data,preparation,paper,time)){
 if(g.completed||g.timeValid!==true||!Number.isFinite(Date.parse(g.tipoff))||Date.parse(g.tipoff)<=time||(!g.preview&&!g.ensembleProjection))continue;
 const picks=Object.fromEntries(['spreads','totals','h2h'].map(m=>[m,bestBet(g,m,preparation.bet_probability_model,null,time)]));
 records.push({gameId:g.id,homeTeamId:g.homeTeamId,awayTeamId:g.awayTeamId,tipoff:g.tipoff,capturedAt:at,sourceRevision,
  recommendationPolicy:'projection-aligned-v2',modelComparison:g.modelComparison||null,ensembleProjection:g.ensembleProjection||null,modelVersion:preparation.model_version,probabilityVersion:preparation.bet_probability_model?.version,
  modelMargin:g.modelMargin,expectedTotal:g.expectedTotal,preview:g.preview,picks});
}
process.stdout.write(JSON.stringify(records));
