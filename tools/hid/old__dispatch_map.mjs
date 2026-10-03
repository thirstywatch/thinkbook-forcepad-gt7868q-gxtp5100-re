// dispatch_map.mjs — 从 TF100A 反汇编机械提取命令分派器 0x0800E1C0 的
// （命名空间, 子命令） → 处理块 → 该块调用的函数  全表。
// 用法： node dispatch_map.mjs <asm.txt>
import fs from 'fs';

const raw = fs.readFileSync(process.argv[2], 'utf8').split(/\r?\n/);
const E = [];
const RE = /^([0-9A-Fa-f]{8})\s{1,2}(\S.*)$/;
raw.forEach((l, k) => { const m = RE.exec(l); if (m) E.push({ a: parseInt(m[1], 16), t: m[2].trim(), k }); });
const h8 = a => a.toString(16).toUpperCase().padStart(8, '0');
const idx = a => { let lo = 0, hi = E.length - 1, r = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (E[m].a >= a) { r = m; hi = m - 1; } else lo = m + 1; } return r; };

// ---- 1. 抓比较链 ----
const chain = { '0xA0': [], '0xA1': [] };
let ns = null;
for (let i = 0; i < E.length; i++) {
  const t = E[i].t;
  if (/^cmp\s+r0,\s*#0xa0$/.test(t)) ns = '0xA0';
  if (/^cmp\s+r0,\s*#0xa1$/.test(t)) ns = '0xA1';
  if (/^cmp\s+r0,\s*#0x80$/.test(t)) ns = '0x80';
  // 形态 A: cmp.w r0, #0xNN00   / 形态 B: movw r1,#0xNNN + cmp r0,r1
  let sub = null;
  let m = /^cmp\.w\s+r0,\s*#0x([0-9a-f]+)$/.exec(t);
  if (m) sub = parseInt(m[1], 16);
  if (/^cmp\s+r0,\s*r1$/.test(t)) {
    const p = E[i - 1];
    const m2 = p && /^movw\s+r1,\s*#0x([0-9a-f]+)$/.exec(p.t);
    if (m2) sub = parseInt(m2[1], 16);
  }
  if (sub === null) continue;
  // 找紧随其后的 beq 目标
  for (let j = i + 1; j < Math.min(i + 3, E.length); j++) {
    const m3 = /^beq(?:\.w)?\s+#0x([0-9a-f]+)$/.exec(E[j].t);
    if (m3) { if (ns) chain[ns].push({ sub, target: parseInt(m3[1], 16) }); break; }
  }
}

// ---- 2. 对每个目标，列出块内 bl 目标 ----
function blockInfo(target) {
  const s = idx(target);
  const calls = [];
  const enders = [];
  for (let k = s; k < E.length; k++) {
    const t = E[k].t;
    const mb = /^bl\s+#0x([0-9a-f]+)$/.exec(t);
    if (mb) calls.push(h8(parseInt(mb[1], 16)));
    // 块结束：无条件跳到公共出口
    if (/^b\s+#0x(800e742|800e3c4|800e744|800e748|800e74a|800e3c2|800e740)$/.test(t)) {
      enders.push(k);
      // 再看是否是"紧邻下一个块"——若下一条是被链指向的另一个目标则停
      break;
    }
    if (k - s > 60) break;
  }
  return { start: h8(E[s].a), calls, lines: (enders.length ? enders[0] : s) - s + 1 };
}

const seen = new Set();
for (const n of ['0xA0', '0xA1']) {
  console.log(`\n#### 命名空间 ${n} —— 比较链命中 ${chain[n].length} 条`);
  for (const c of chain[n]) {
    const b = blockInfo(c.target);
    const key = n + ':' + c.sub;
    if (seen.has(key)) continue;
    seen.add(key);
    console.log(`  ${n} / 0x${c.sub.toString(16).toUpperCase().padStart(4, '0')}  → 块 ${b.start}  (${b.lines} 行)  calls: ${b.calls.join(', ') || '（无 bl）'}`);
  }
}
