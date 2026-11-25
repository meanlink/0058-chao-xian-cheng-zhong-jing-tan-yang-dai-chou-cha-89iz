import {intro,table} from './readout.js';
import {feedback,onSubmit,options} from './submit.js';
import {rounds,roundData,witness} from './coast_client.js';
import {chooser,samples} from './coast_scope.js';
export async function render(outlet,user){
  const list=await rounds();
  outlet.innerHTML=`${intro('分歧裁定','接受首称或者复称作为样袋净重。遇到分歧需写下秤纸、见证人或复核凭据。')}
    <div class="toolrow">${chooser(list)}</div><div class="split"><div class="witness-data band"></div>
    ${user.role==='reviewer'?`<form class="entry"><h2>见证盖章</h2><label>样袋<select name="sample"></select></label>
    <label>取用证据<select name="source"><option value="first">首称秤纸</option><option value="second" selected>复称秤纸</option></select></label>
    <label>依据<textarea name="note" placeholder="分歧样袋必填"></textarea></label><button>保存见证</button>${feedback}</form>`:''}</div>`;
  const picker=outlet.querySelector('[name=round]');
  async function refresh(){
    const rows=await roundData(picker.value,'samples');
    const target=outlet.querySelector('[name=sample]');
    if(target)target.innerHTML=options(rows.filter(x=>!x.witness).map(r=>[`${r.segment}/${r.bag}`,`${r.name} #${r.bag} · ${samples[r.status]}`]));
    outlet.querySelector('.witness-data').innerHTML=table('见证记录',['区段','袋号','状态','采纳净重','裁定依据'],rows.map(r=>[r.name,r.bag,samples[r.status],r.accepted_kg??'—',r.note||'—']));
  }
  picker.onchange=refresh;
  onSubmit(outlet.querySelector('form'),async({sample,...data})=>{
    if(!sample)throw Error('当前轮次无待见证样袋');
    const [segment,bag]=sample.split('/');
    await witness(segment,bag,data);await refresh();return '样袋已见证';
  });
  if(picker.value)await refresh();
}
