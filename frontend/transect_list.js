import {h} from './base.js';
export const transects=rows=>`<div class="transects">${rows.map(r=>`<article class="transect"><strong>${h(r.name)}</strong><code>${h(r.code)}</code><span>${h(r.bags)} 袋</span></article>`).join('')}</div>`;
