import {options} from './submit.js';
export const states={open:'抽查中',locked:'交接编制中',issued:'已发清运交接'};
export const samples={awaiting:'待见证',disputed:'双称分歧',accepted:'已见证'};
export const correctionStates={queued:'待重算',succeeded:'已接替旧单',stale:'需重新核对'};
export const sourceLabels={first:'首称秤纸',second:'复称秤纸'};
export const chooser=(rounds,id='round')=>`<label>净滩轮次<select name="${id}">${options(rounds.map(r=>[r.code,r.code+' · '+r.shore]))}</select></label>`;
