// align-diff.mjs —— 两份 GT7868Q 固件的全文件对齐差分
//   A = 本机 touchpad_GT7868Q_fw.bin (161,628 B)
//   B = Catalog 样本 goodix_tp_payload.bin (133,628 B)
//   锚点 = "YELSTO"，delta = 0xCA4
// 目的：分出「共用框架」与「按机型不同的配置」，后者就是配置数据（阈值所在）
import fs from 'fs';

const a = fs.readFileSync(process.argv[2]);
const b = fs.readFileSync(process.argv[3]);
const aY = a.indexOf(Buffer.from('YELSTO'));
const bY = b.indexOf(Buffer.from('YELSTO'));
const d = aY - bY;                       // 本机 = 样本 + d
console.log(`A(本机) ${a.length.toLocaleString()} B   B(样本) ${b.length.toLocaleString()} B   delta=0x${d.toString(16)}`);
console.log(`对齐：A[0x${aY.toString(16)}] ↔ B[0x${bY.toString(16)}]  (YELSTO)\n`);

// 在全重叠域内，逐字节判同，输出「相同/不同」游程
const loA = Math.max(0, d), hiA = Math.min(a.length, b.length + d);
console.log(`重叠域：A[0x${loA.toString(16)} .. 0x${hiA.toString(16)}]  (${(hiA-loA).toLocaleString()} B)\n`);

const runs = [];
let cur = null;
for (let oa = loA; oa < hiA; oa++) {
  const ob = oa - d;
  const same = a[oa] === b[ob];
  if (!cur || cur.same !== same) { if (cur) runs.push(cur); cur = { same, start: oa, len: 0 }; }
  cur.len++;
}
if (cur) runs.push(cur);

// 只报 >=256 B 的游程
console.log('段（>=256 B）  本机偏移          样本偏移          长度     性质');
console.log('-'.repeat(88));
const sig = runs.filter(r => r.len >= 256);
for (const r of sig) {
  const ob = r.start - d;
  const kind = r.same ? '★ 共用（相同）' : '✱ 差异（按机型）';
  console.log(`  A:0x${r.start.toString(16).padStart(6,'0')}  B:0x${ob.toString(16).padStart(6,'0')}  ${String(r.len).padStart(7)}  ${kind}`);
}

// 统计各类总长度
const sameTot = runs.filter(r => r.same).reduce((s, r) => s + r.len, 0);
const diffTot = runs.filter(r => !r.same).reduce((s, r) => s + r.len, 0);
console.log(`\n共用合计 ${sameTot.toLocaleString()} B   差异合计 ${diffTot.toLocaleString()} B   相同率 ${(100*sameTot/(sameTot+diffTot)).toFixed(1)}%`);

// 对最长的几个「差异段」做 ASCII / 16 位值扫描（配置最可能在这里）
console.log('\n=== 最长差异段的内容扫描（候选配置区）===');
const diffRuns = runs.filter(r => !r.same && r.len >= 512).sort((x, y) => y.len - x.len).slice(0, 5);
for (const r of diffRuns) {
  console.log(`\n── 差异段 A:0x${r.start.toString(16)} 长 ${r.len} B`);
  // 16 位小端值直方图（找像阈值的小整数）
  const hist = new Map();
  for (let o = r.start; o + 1 < r.start + r.len; o += 2) {
    const v = a[o] | (a[o + 1] << 8);
    if (v > 0 && v < 256) hist.set(v, (hist.get(v) || 0) + 1);
  }
  const top = [...hist.entries()].sort((x, y) => y[1] - x[1]).slice(0, 14);
  console.log(`   本机里出现的 16 位小值(<256) top: ${top.map(([v, n]) => `${v}×${n}`).join('  ')}`);
  const hist2 = new Map();
  for (let o = r.start - d; o + 1 < r.start - d + r.len; o += 2) {
    const v = b[o] | (b[o + 1] << 8);
    if (v > 0 && v < 256) hist2.set(v, (hist2.get(v) || 0) + 1);
  }
  const top2 = [...hist2.entries()].sort((x, y) => y[1] - x[1]).slice(0, 14);
  console.log(`   样本里出现的 16 位小值(<256) top: ${top2.map(([v, n]) => `${v}×${n}`).join('  ')}`);
}
