import {intro} from './readout.js';
import {feedback,onSubmit,options} from './submit.js';
import {rounds,roundData,weigh} from './coast_client.js';
import {chooser} from './coast_scope.js';
import {weightTable} from './sample_weights.js';
export async function render(outlet,user){
  const list=await rounds();
  outlet.innerHTML=`${intro('样袋复称','记录独立首称和复称，差异大于 0.50 kg 会标成分歧，交给见证员裁定。')}
   <div class="toolrow">${chooser(list)}</div><div class="split"><section class="weights band"></section>
   ${user.role==='operator'?`<form class="entry"><h2>登记两次净重</h2><label>区段<select name="segment"></select></label>
   <label>区段袋号<input name="bag" type="number" min="1" required></label><label>首称 / kg<input name="first_kg" type="number" min=".01" step=".01" required></label>
   <label>复称 / kg<input name="second_kg" type="number" min=".01" step=".01" required></label><button>保存双称</button>${feedback}</form>`:''}</div>`;
  const picker=outlet.querySelector('[name=round]');
  async function refresh(){
    if(!picker.value)return;
    const [rows,segments]=await Promise.all([roundData(picker.value,'samples'),roundData(picker.value,'segments')]);
    outlet.querySelector('.weights').innerHTML=weightTable(rows);
    const segment=outlet.querySelector('[name=segment]');
    if(segment)segment.innerHTML=options(segments.map(r=>[r.code,r.name]));
  }
  picker.onchange=refresh;
  onSubmit(outlet.querySelector('form'),async input=>{
    const {segment,bag,...masses}=input;
    await weigh(segment,{bag:+bag,...masses});await refresh();return '双称证据已记录';
  });
  await refresh();
}
