import {waitJob,notice} from './base.js';
import {intro} from './readout.js';
import {feedback,onSubmit,options} from './submit.js';
import {rounds,roundData,haul,correct,retryCorrection} from './coast_client.js';
import {chooser,sourceLabels} from './coast_scope.js';
import {docket,correctionHistory} from './haul_readout.js';

export async function render(outlet,user){
 const list=await rounds();
 outlet.innerHTML=`${intro('清运交接','得到每段平均净重后，用本段全部袋数分别放大。清运单已发给班组后若发现认错秤单，可固定取证发起更正，先完成的更正接替旧单。')}
  <form class="toolrow">${chooser(list)}${user.role==='reviewer'?'<button>锁定并出单</button>':''}${feedback}</form>
  <div class="estimate band"></div><div class="corrections band"></div>`;
 const picker=outlet.querySelector('select');
 const statusEl=outlet.querySelector('[role=status]');
 let selectedVersion=null;
 const polling=new Set();

 async function load(){
   const [report,samples]=await Promise.all([
     roundData(picker.value,'haul'),
     roundData(picker.value,'samples').catch(()=>[]),
   ]);
   if(selectedVersion===null || !report.versions.some(v=>v.version===selectedVersion)){
     selectedVersion=report.current_version;
   }
   outlet.querySelector('.estimate').innerHTML=docket(report,selectedVersion);
   outlet.querySelector('.corrections').innerHTML=correctionPanel(report,samples,user.role);
   return report;
 }
 async function refresh(){ if(picker.value){ const report=await load(); settle(report); } }

 function correctionPanel(report,samples,role){
   const witnessed=samples.filter(row=>row.witness);
   const form=role==='reviewer' && report.report ? `<form class="entry correction-form">
     <h2>发起清运单更正</h2>
     <p class="callout">提交后本次采用的称重与原因即被固定，后台按该取证重算；旧单保留可查。</p>
     <label>样袋<select name="sample">${options(witnessed.map(r=>[
       `${r.segment}/${r.bag}`,
       `${r.name} #${r.bag} · 首称 ${r.first_kg}kg / 复称 ${r.second_kg}kg（现采纳 ${r.accepted_kg}kg）`,
     ]))}</select></label>
     <label>改用称重<select name="source">
       <option value="first">${sourceLabels.first}</option>
       <option value="second" selected>${sourceLabels.second}</option>
     </select></label>
     <label>袋级原因<input name="note" maxlength="160" placeholder="如：原始秤纸显示首称为准"></label>
     <label>更正说明（必填，至少 5 字）<textarea name="reason" required minlength="5"
       placeholder="说明为何认错秤单、依据哪张秤纸"></textarea></label>
     <button>固定取证并更正</button>${feedback}</form>`:'';
   return `<h2>版本与更正记录</h2>${correctionHistory(report)}${form}`;
 }

 function settle(report){
   for(const c of report.corrections ?? []){
     const job=c.job;
     if(!job || !['queued','running'].includes(job.status) || polling.has(job.id)) continue;
     polling.add(job.id);
     waitJob(job.id)
       .then(result=>{ if(result?.stale) notice(statusEl,result.message,true); })
       .catch(error=>notice(statusEl,error.message,true))
       .finally(()=>{ polling.delete(job.id); refresh(); });
   }
 }

 picker.onchange=()=>{ selectedVersion=null; refresh(); };

 onSubmit(outlet.querySelector('.toolrow form'),async()=>{
   const job=await haul(picker.value);
   await waitJob(job.job_id); selectedVersion=null; await refresh();
   return '清运交接已生成';
 });

 outlet.querySelector('.estimate').addEventListener('click',async event=>{
   const chip=event.target.closest('[data-version]');
   if(chip){ selectedVersion=Number(chip.dataset.version); await refresh(); }
 });

 // 更正表单随数据刷新重建，用委托保证监听不丢失。
 outlet.querySelector('.corrections').addEventListener('submit',event=>{
   const form=event.target.closest('.correction-form');
   if(!form) return;
   event.preventDefault();
   const button=form.querySelector('button');
   const formStatus=form.querySelector('[role=status]');
   button.disabled=true;
   (async()=>{
     try{
       const input=Object.fromEntries(new FormData(form));
       if(!input.sample) throw Error('当前轮次没有可更正的见证样袋');
       const [segment,bag]=input.sample.split('/');
       const job=await correct(picker.value,{reason:input.reason,choices:[{
         segment,bag:Number(bag),source:input.source,note:input.note ?? '',
       }]});
       const result=await waitJob(job.job_id);
       if(result?.stale) throw Error(result.message);
       selectedVersion=null; await refresh();
       notice(formStatus,'更正已生成新版清运单');
     }catch(error){
       notice(formStatus,error.message,true);
     }finally{ button.disabled=false; }
   })();
 });

 outlet.querySelector('.corrections').addEventListener('click',async event=>{
   const button=event.target.closest('[data-retry]');
   if(!button) return;
   button.disabled=true;
   try{
     const job=await retryCorrection(picker.value,button.dataset.retry);
     notice(statusEl,'已重新排队，沿用同一份更正取证');
     await waitJob(job.job_id); await refresh();
   }catch(error){ notice(statusEl,error.message,true); button.disabled=false; }
 });

 await refresh();
}
