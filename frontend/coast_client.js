import {api} from './base.js';
const roundsBase='/api/coast-rounds';
export const rounds=()=>api(roundsBase);
export const roundData=(id,scope)=>api(`${roundsBase}/${encodeURIComponent(id)}/${scope}`);
export const weigh=(code,body)=>api(`/api/coast-segments/${code}/samples`,'POST',body);
export const witness=(code,bag,body)=>api(`/api/coast-segments/${code}/samples/${bag}/witness`,'POST',body);
export const haul=id=>api(`${roundsBase}/${id}/haul`,'POST');
