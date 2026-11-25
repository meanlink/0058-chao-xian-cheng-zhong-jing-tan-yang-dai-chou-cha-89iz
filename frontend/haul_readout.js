import {h} from './base.js';
import {stats,table} from './readout.js';
import {states,correctionStates,sourceLabels} from './coast_scope.js';

const pickVersion=(report,version)=>{
  if(!report.versions?.length) return null;
  return report.versions.find(item=>item.version===version) ?? report.report;
};

export function docket(report,selected=report.current_version){
  if(!report.report) {
    return stats([['交接状态',states[report.status]],['净重估计','待出单']])+
      table('分段清运重量依据',['区段','全部袋数','见证样本','样本净重 / kg','推算 / kg'],
        (report.coverage ?? []).map(r=>[r.name,r.bags,r.witness_count,r.sample_kg,'—']));
  }
  const version=pickVersion(report,selected) ?? report.report;
  const isCurrent=version.version===report.current_version;
  const rows=version.pieces ?? [];
  return stats([
    ['交接状态',states[report.status]],
    ['清运单版本',`v${version.version}${isCurrent?'（当前）':'（历史版）'}`],
    ['净重估计',version.estimated_kg+' kg'],
  ])+
  versionTabs(report,version.version)+
  table('分段清运重量依据',['区段','全部袋数','见证样本','样本净重 / kg','推算 / kg'],
    rows.map(r=>[r.segment,r.bags,r.witness_count,r.sample_kg,r.estimated_kg??'—']))+
  basisTable(version);
}

function versionTabs(report,active){
  if(report.versions.length<2) return '';
  return `<div class="toolrow version-tabs" role="group" aria-label="清运单版本">`+
    report.versions.map(item=>`<button type="button" class="quiet version-chip${item.version===active?' active':''}"
      data-version="${item.version}" aria-current="${item.version===active}">v${item.version}
      ${item.version===report.current_version?'· 当前':''}</button>`).join('')+`</div>`;
}

function basisTable(version){
  const rows=version.basis ?? [];
  return table(`v${version.version} 采用的样袋重量依据`,
    ['区段','袋号','采用称重','净重 / kg','见证/更正人','原因'],
    rows.map(r=>[r.segment,r.bag,sourceLabels[r.source]??r.source,r.accepted_kg,r.witness,r.note||'—']));
}

export function correctionHistory(report){
  const items=report.corrections ?? [];
  if(!items.length) return '';
  const head=['编号','基于版本','原因','更正取证','申请人','状态','最近任务','操作'];
  const body=items.map(c=>{
    const evidence=c.evidence
      .map(e=>`${h(e.segment)}#${h(e.bag)} → ${h(sourceLabels[e.source]??e.source)}（${h(e.accepted_kg)}kg）`)
      .join('；');
    const job=c.job;
    const jobText=job?`${h(job.status)}${job.error?'：'+h(job.error):''}`:'—';
    const retry=(job&&job.status==='failed')
      ?`<button type="button" class="quiet" data-retry="${c.id}">重试</button>`:'';
    return `<tr><td>${h(c.id)}</td><td>v${h(c.base_version)}</td><td>${h(c.reason)}</td>`+
      `<td>${evidence}</td><td>${h(c.created_by)}</td>`+
      `<td>${h(correctionStates[c.status]??c.status)}</td><td>${jobText}</td><td>${retry}</td></tr>`;
  }).join('');
  return `<div class="data-frame"><table><caption>${h('更正申请')}</caption>`+
    `<thead><tr>${head.map(c=>`<th scope="col">${h(c)}</th>`).join('')}</tr></thead>`+
    `<tbody>${body}</tbody></table></div>`;
}
