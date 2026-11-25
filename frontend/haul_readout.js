import {stats,table} from './readout.js';
import {states} from './coast_scope.js';
export function docket(report){
  const rows=report.report?.pieces ?? report.coverage.map(r=>({...r,segment:r.name}));
  return stats([['交接状态',states[report.status]],['净重估计',report.report?report.report.estimated_kg+' kg':'待出单']])+
    table('分段清运重量依据',['区段','全部袋数','见证样本','样本净重 / kg','推算 / kg'],rows.map(r=>[r.segment,r.bags,r.witness_count,r.sample_kg,r.estimated_kg??'—']));
}
