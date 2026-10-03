// handlers_report.mjs —— 把 TF100A 命令分派器里 38 条命令的处理函数一次性"过筛"：
//   每个 handler 的：入口 / 行数 / 直接调用 / 加载的 32 位常量 / 引用的 RAM 与 外设地址 / 是否构造 A2 回复 / 首几行
// 用法： node handlers_report.mjs <asm.txt>
import fs from 'fs';

const raw = fs.readFileSync(process.argv[2], 'utf8').split(/\r?\n/);
const E = [];
const RE = /^([0-9A-Fa-f]{8})\s{1,2}(\S.*)$/;
raw.forEach((l, k) => { const m = RE.exec(l); if (m) E.push({ a: parseInt(m[1], 16), t: m[2].trim() }); });
const h8 = a => a.toString(16).toUpperCase().padStart(8, '0');
const idxOf = a => { let lo = 0, hi = E.length - 1, r = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (E[m].a >= a) { r = m; hi = m - 1; } else lo = m + 1; } return r; };
function fnStart(i) { for (let k = i; k >= 0 && i - k < 600; k--) if (/^push\s+\{/.test(E[k].t)) return k; return i; }
function fnEnd(s) { for (let k = s + 1; k < E.length; k++) if (/^push\s+\{/.test(E[k].t)) return k; return E.length; }

// 分派表（由 dispatch_map.mjs 得出，硬编码以便报告自洽）
const MAP = [
  ['0x80',  '0x08006628'], ['0x80', '0x08006628'],
  ['0xA0/0x0100','0x08006F8C'], ['0xA0/0x0500','0x08006694'], ['0xA0/0x0B00','0x0800D8C0'],
  ['0xA0/0x0D00','0x0800D6B4'], ['0xA0/0x0E00','0x0800BE28'], ['0xA0/0x1100','0x0800BE28'],
  ['0xA0/0x1200','0x08009CD4'], ['0xA0/0x1400','0x08007F30'], ['0xA0/0x1700','0x080063AC'],
  ['0xA0/0x1F00','0x0800BE28'], ['0xA0/0x2000','0x080099EC'], ['0xA0/0x2400','0x08009CD4'],
  ['0xA0/0x2600','0x08006F70'], ['0xA0/0x3200','0x08006FC0'], ['0xA0/0x3300','0x08006F68'],
  ['0xA0/0x3500','0x08009A20'],
  ['0xA1/0x0203','0x08009B8C'], ['0xA1/0x0400','0x08008784'], ['0xA1/0x0700','0x080065AC'],
  ['0xA1/0x0800','0x08009A78'], ['0xA1/0x0A00','0x0800A2A8'], ['0xA1/0x0B00','0x0800D868'],
  ['0xA1/0x0F00','0x08009C98'], ['0xA1/0x1300','0x0800A2A8'], ['0xA1/0x1500','0x0800764C'],
  ['0xA1/0x1600','0x08007D6C'], ['0xA1/0x1800','0x0800A3F8'], ['0xA1/0x1D00','0x08006554'],
  ['0xA1/0x2300','0x0800A3F8'], ['0xA1/0x2800','0x08007C04'], ['0xA1/0x2900','0x08007944'],
  ['0xA1/0x2B00','0x080099A4'], ['0xA1/0x2C00','0x08007CB8'], ['0xA1/0x2E00','0x08006520'],
  ['0xA1/0x3200','0x0800D65C'], ['0xA1/0x3400','0x080065F8'], ['0xA1/0x3500','0x08009A48'],
  ['0xA1/0x3600','0x08009F78'],
];

const seen = new Set();
for (const [cmd, hs] of MAP) {
  const h = parseInt(hs, 16);
  if (seen.has(h)) continue;
  seen.add(h);
  const i = idxOf(h);
  const s = i, e = fnEnd(s);            // ★ 起点就用分派表给的地址（不再回溯，避免吞掉前一个函数）
  const calls = [], consts = new Set(), ram = new Set(), per = new Set();
  let a2 = false;
  for (let k = s; k < e; k++) {
    const t = E[k].t;
    const mb = /^bl\s+#0x([0-9a-f]+)$/.exec(t);
    if (mb) calls.push(h8(parseInt(mb[1], 16)));
    const mw = /^movw\s+(r\d+|sl|fp|ip),\s*#0x([0-9a-f]+)$/.exec(t);
    if (mw) {
      const reg = mw[1], lo = parseInt(mw[2], 16);
      const next = E[k + 1] ? E[k + 1].t : '';
      const m2 = new RegExp('^movt\\s+' + reg + ',\\s*#0x([0-9a-f]+)$').exec(next);
      if (m2) {
        const v = (parseInt(m2[1], 16) << 16) | lo;
        consts.add(v);
        if ((v & 0xFFFF0000) === 0x20000000) ram.add(v);
        else if (v >= 0x40000000 && v < 0x50000000) per.add(v);
      }
    }
    if (/^movs\s+r\d+,\s*#0xa2$/.test(t)) a2 = true;
  }
  // A2 回复的长度标签：movs rX,#0xa2 … 其后 12 条内找 movs rZ,#len + strb rZ,[rW,#1]
  let a2len = null;
  for (let k = s; k < e && a2len === null; k++) {
    if (!/^movs\s+r\d+,\s*#0xa2$/.test(E[k].t)) continue;
    for (let j = k + 1; j < Math.min(k + 14, e); j++) {
      const m1 = /^movs\s+(r\d+),\s*#0x([0-9a-f]+)$/.exec(E[j].t);
      if (!m1) continue;
      const m2 = new RegExp('^strb\\s+' + m1[1] + ',\\s*\\[[^\\]]*#1\\]$').exec(E[j + 1] ? E[j + 1].t : '');
      if (m2) { a2len = parseInt(m1[2], 16); break; }
    }
  }
  const f = v => '0x' + v.toString(16).toUpperCase();
  console.log(`\n### ${cmd}  →  ${f(h)}   (${e - s} 行)`);
  console.log(`  bl: ${[...new Set(calls)].map(x => '0x' + x).join(' ') || '（无）'}`);
  console.log(`  RAM: ${[...ram].sort((a, b) => a - b).map(f).join(' ') || '—'}`);
  console.log(`  外设: ${[...per].sort((a, b) => a - b).map(f).join(' ') || '—'}`);
  console.log(`  构造 A2 回复: ${a2 ? '是' : '否'}${a2len !== null ? `，长度标签 = 0x${a2len.toString(16).toUpperCase()} (${a2len} 字节)` : ''}`);
  const head = [];
  for (let k = s; k < Math.min(s + 14, e); k++) head.push('    ' + h8(E[k].a) + '  ' + E[k].t);
  console.log(head.join('\n'));
}
console.log(`\n（唯一 handler 共 ${seen.size} 个）`);
