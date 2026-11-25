import {table} from './readout.js';
import {samples} from './coast_scope.js';
export const weightTable=rows=>table('样袋双称证据',['区段','袋号','首称 / kg','复称 / kg','状态'],rows.map(r=>[r.name,r.bag,r.first_kg,r.second_kg,samples[r.status]]));
