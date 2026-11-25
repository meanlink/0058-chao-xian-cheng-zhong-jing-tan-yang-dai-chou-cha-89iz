import {waitJob} from './base.js';
import {intro} from './readout.js';
import {feedback,onSubmit} from './submit.js';
import {rounds,roundData,haul} from './coast_client.js';
import {chooser} from './coast_scope.js';
import {docket} from './haul_readout.js';
export async function render(outlet,user){
 const list=await rounds();
 outlet.innerHTML=`${intro('清运交接','得到每段平均净重后，用本段全部袋数分别放大。每段要具备足够见证样本。')}
  <form class="toolrow">${chooser(list)}${user.role==='reviewer'?'<button>锁定并出单</button>':''}${feedback}</form><div class="estimate band"></div>`;
 const picker=outlet.querySelector('select');
 async function refresh(){ if(picker.value)outlet.querySelector('.estimate').innerHTML=docket(await roundData(picker.value,'haul')); }
 picker.onchange=refresh;
 onSubmit(outlet.querySelector('form'),async()=>{const job=await haul(picker.value);await waitJob(job.job_id);await refresh();return '清运交接已生成';});
 await refresh();
}
