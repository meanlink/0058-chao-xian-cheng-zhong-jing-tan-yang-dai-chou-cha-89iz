import {intro,stats} from './readout.js';
import {rounds,roundData} from './coast_client.js';
import {chooser,states} from './coast_scope.js';
import {transects} from './transect_list.js';
export async function render(outlet) {
  const list=await rounds();
  outlet.innerHTML=`${intro('分段袋册','每个净滩区段独立登记总袋数。抽中的袋号必须落在段长交来的号码区间。')}
   <div class="toolrow">${chooser(list)}</div><div class="split"><div class="shore-report"></div>
   <aside class="sampling"><h2>称重交接</h2><p>按区段发出抽查袋号，复称后按见证证据放大。</p><a href="#weigh">前往样袋复称</a></aside></div>`;
  const plan=outlet.querySelector('select');
  async function refresh(){
    if(!plan.value)return;
    const sections=await roundData(plan.value,'segments');
    outlet.querySelector('.shore-report').innerHTML=stats([['状态',states[list.find(r=>r.code===plan.value).status]],['区段',sections.length]])+transects(sections);
  }
  plan.onchange=refresh;await refresh();
}
