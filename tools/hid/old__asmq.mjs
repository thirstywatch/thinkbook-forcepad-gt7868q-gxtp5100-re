// asmq.mjs — TF100A 明文反汇编查询器（按地址索引）
// 用法：
//   node asmq.mjs <asm.txt> at   <hexaddr> [n]     从地址起打印 n 行
//   node asmq.mjs <asm.txt> fn   <hexaddr> [n]     自动回溯函数入口后打印
//   node asmq.mjs <asm.txt> xref <hexaddr>         所有跳转到该地址的站点
//   node asmq.mjs <asm.txt> lit  <hex32>           movw/movt 加载该 32 位常量的站点
//   node asmq.mjs <asm.txt> callees <hexaddr>      该函数内的 bl/字面量调用目标
//   node asmq.mjs <asm.txt> peek <hexaddr>         打印该地址前后 1 行（判断是否函数入口）
//   node asmq.mjs <asm.txt> grep <regex>           正则检索
//   node asmq.mjs <asm.txt> blx                    所有 blx rN 间接调用点
import fs from 'fs';

const file = process.argv[2];
const cmd  = process.argv[3];
const raw  = fs.readFileSync(file, 'utf8').split(/\r?\n/);

const E = [];                       // {a, t, i}
const RE = /^([0-9A-Fa-f]{8})\s{1,2}(\S.*)$/;
raw.forEach((l, k) => {
  const m = RE.exec(l);
  if (m) E.push({ a: parseInt(m[1], 16), t: m[2].trim(), i: k });
});

const hex = s => parseInt(String(s).replace(/^0x/i, ''), 16);
const h8  = a => a.toString(16).toUpperCase().padStart(8, '0');

function idxOf(addr) {              // 最近的 >= addr 的条目
  let lo = 0, hi = E.length - 1, r = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1;
    if (E[m].a >= addr) { r = m; hi = m - 1; } else lo = m + 1; }
  return r;
}
const ENDER = /(pop\s*\{[^}]*\bpc\b\}|bx\s+lr$|movs\s+r0, r0$)/i;

function fnStart(idx) {             // 回溯到函数入口：优先最近的 push {…}
  for (let k = idx; k >= 0 && idx - k < 500; k--) {
    if (/^push\s+\{/.test(E[k].t)) return k;
  }
  for (let k = idx; k > 0; k--) {   // 兜底：上一条是函数结尾
    if (ENDER.test(E[k - 1].t)) return k;
  }
  return 0;
}
function show(from, n) {
  for (let k = from; k < Math.min(from + n, E.length); k++)
    console.log(h8(E[k].a) + '  ' + E[k].t);
}
function fnEnd(idx) {               // 函数结束：下一个入口
  for (let k = idx + 1; k < E.length; k++) if (/^push\s+\{/.test(E[k].t)) return k;
  return E.length;
}

switch (cmd) {
  case 'at': {
    const i = idxOf(hex(process.argv[4]));
    show(i, parseInt(process.argv[5] || '40'));
    break;
  }
  case 'fn': {
    const i = idxOf(hex(process.argv[4]));
    const s = fnStart(i);
    const lim = parseInt(process.argv[5] || '0') || (fnEnd(s) - s);
    console.log(`; fn start ${h8(E[s].a)}  (查到 ${h8(E[i].a)}), 共 ${fnEnd(s) - s} 行`);
    show(s, lim);
    break;
  }
  case 'peek': {
    const i = idxOf(hex(process.argv[4]));
    for (let k = Math.max(0, i - 2); k < i + 3; k++) console.log((k === i ? '>>' : '  ') + h8(E[k].a) + '  ' + E[k].t);
    break;
  }
  case 'xref': {
    const a = hex(process.argv[4]);
    const pats = [`#0x${a.toString(16)}`, `#0x0${a.toString(16)}`, h8(a).toLowerCase()];
    let n = 0;
    E.forEach(e => {
      const t = e.t.toLowerCase();
      if (pats.some(p => t.includes(p)) && /(bl|blx|b|beq|bne|bgt|ble|bhi|bls|bcs|bcc|bge|blt|cbz|cbnz)\b/.test(t)) {
        const s = fnStart(idxOf(e.a));
        console.log(`${h8(e.a)}  ${e.t}      ; 在函数 ${h8(E[s].a)}`);
        n++;
      }
    });
    console.log(`; xref 命中 ${n} 处`);
    break;
  }
  case 'lit': {
    const v = hex(process.argv[4]);
    const lo = (v & 0xFFFF), hi = (v >>> 16) & 0xFFFF;
    for (let k = 0; k < E.length; k++) {
      const m = /^movw\s+(r\d+|sl|fp|ip),\s*#0x([0-9a-f]+)$/.exec(E[k].t);
      if (!m || parseInt(m[2], 16) !== lo) continue;
      for (let j = k + 1; j < Math.min(k + 5, E.length); j++) {
        const m2 = /^movt\s+(r\d+|sl|fp|ip),\s*#0x([0-9a-f]+)$/.exec(E[j].t);
        if (m2 && m2[1] === m[1] && parseInt(m2[2], 16) === hi) {
          const s = fnStart(idxOf(E[k].a));
          console.log(`${h8(E[k].a)}  ${E[k].t} / ${E[j].t}   ; 在函数 ${h8(E[s].a)}`);
          k = j; break;
        }
      }
    }
    break;
  }
  case 'callees': {
    const i = idxOf(hex(process.argv[4]));
    const s = fnStart(i), e = fnEnd(s), set = new Set();
    for (let k = s; k < e; k++) {
      const m = /^bl\s+#0x([0-9a-f]+)$/.exec(E[k].t);
      if (m) set.add(parseInt(m[1], 16));
    }
    console.log(`; ${h8(E[s].a)} 的直接 bl 目标 ${set.size} 个：`);
    [...set].sort((x, y) => x - y).forEach(t => console.log(`  bl ${h8(t)}`));
    break;
  }
  case 'grep': {
    const re = new RegExp(process.argv[4], 'i');
    E.forEach(e => { if (re.test(e.t)) console.log(`${h8(e.a)}  ${e.t}`); });
    break;
  }
  case 'blx': {
    const out = E.filter(e => /^blx\s+r\d+$/.test(e.t));
    out.forEach(e => { const s = fnStart(idxOf(e.a)); console.log(`${h8(e.a)}  ${e.t}   ; 函数 ${h8(E[s].a)}`); });
    console.log(`; blx rN 共 ${out.length} 处`);
    break;
  }
  default: console.log('未知命令');
}
