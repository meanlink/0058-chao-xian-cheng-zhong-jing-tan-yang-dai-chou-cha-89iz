import {mount} from './base.js';
import {render as shore} from './shore_page.js';
import {render as weigh} from './weigh_page.js';
import {render as witness} from './witness_page.js';
import {render as haul} from './haul_page.js';
const pages = {"shore": "分段袋册", "weigh": "样袋复称", "witness": "分歧裁定", "haul": "清运交接"};
const screens = {shore, weigh, witness, haul};
mount({title: "潮线称重 · 净滩样袋抽查", kicker: "南湾清滩 / 分段称重", pages, render: (page, outlet, user) => screens[page](outlet, user)});
