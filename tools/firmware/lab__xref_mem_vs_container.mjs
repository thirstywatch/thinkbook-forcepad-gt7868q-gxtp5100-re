// xref_mem_vs_container.mjs —— 把设备实际可读的 16 位窗口（mem-scan-16bit.txt）
// 与本地固件容器（touchpad_GT7868Q_fw.bin）做交叉比对。
// 目的：回答"这个窗口里到底有没有暴露容器内容、暴露了哪一段"。
// 用法： node xref_mem_vs_container.mjs <mem-scan-16bit.txt> <container.bin>
import fs from 'fs';

const [, , scanPath, binPath] = process.argv;
const WIN = 0x10000;

// ---- 1. 解析设备窗口 ----
const scan = fs.readFileSync(scanPath, 'utf8').split(/\r?\n/);
const W = new Uint8Array(WIN);          // 内容（缺失处为 0）
const mask = new Uint8Array(WIN);       // 1 = 该字节有效
let okLines = 0, failLines = 0;
for (const line of scan) {
  const m = /^0x([0-9A-Fa-f]{4})\s+(.*)$/.exec(line.trim());
  if (!m) continue;
  if (/<FAIL/.test(m[2])) { failLines++; continue; }
  const addr = parseInt(m[1], 16);
  const bytes = m[2].trim().split(/\s+/).map(h => parseInt(h, 16));
  for (let i = 0; i < bytes.length && addr + i < WIN; i++) {
    if (!Number.isNaN(bytes[i])) { W[addr + i] = bytes[i]; mask[addr + i] = 1; }
  }
  okLines++;
}
console.log(`窗口: 有效行 ${okLines} / 失败行 ${failLines}；有效字节 ${mask.reduce((a, b) => a + b, 0)} / ${WIN}`);

// ---- 2. 建 8 字节索引（只索引全部有效、且"熵够高"的窗口位置） ----
const K = 8;
function entropyOK(bytes) {                    // 至少 5 个不同字节值 ⇒ 排除 0000/FFFF/4600 这类填充串
  const s = new Set(bytes);
  return s.size >= 5;
}
const index = new Map();
let skipped = 0;
for (let a = 0; a + K <= WIN; a++) {
  let valid = true;
  const bs = [];
  for (let i = 0; i < K; i++) { if (!mask[a + i]) { valid = false; break; } bs.push(W[a + i]); }
  if (!valid) continue;
  if (!entropyOK(bs)) { skipped++; continue; }
  const key = bs.map(b => b.toString(16).padStart(2, '0')).join('');
  if (!index.has(key)) index.set(key, []);
  index.get(key).push(a);
}
console.log(`窗口索引: ${index.size} 个高熵 8 字节键（跳过 ${skipped} 个低熵位置）`);

// ---- 3. 拿容器每个偏移去查 ----
const C = fs.readFileSync(binPath);
const hits = [];
for (let o = 0; o + K <= C.length; o++) {
  const bs = [];
  for (let i = 0; i < K; i++) bs.push(C[o + i]);
  if (!entropyOK(bs)) continue;
  const key = bs.map(b => b.toString(16).padStart(2, '0')).join('');
  const at = index.get(key);
  if (at) for (const a of at) hits.push({ cOff: o, wAddr: a });
}
console.log(`高熵 8 字节锚点命中: ${hits.length} 处`);

// ---- 4. 按"容器偏移 - 窗口地址"的差值聚类，找出成片对应 ----
const byDelta = new Map();
for (const h of hits) {
  const d = h.cOff - h.wAddr;
  if (!byDelta.has(d)) byDelta.set(d, []);
  byDelta.get(d).push(h);
}
const rows = [...byDelta.entries()].map(([d, arr]) => {
  // 对每个 delta，量最长连续一致区段
  let best = 0, bestAt = null;
  for (const h of arr) {
    let n = 0;
    while (h.cOff + n < C.length && h.wAddr + n < WIN &&
           mask[h.wAddr + n] && C[h.cOff + n] === W[h.wAddr + n]) n++;
    if (n > best) { best = n; bestAt = h; }
  }
  return { delta: d, anchors: arr.length, best, cOff: bestAt ? bestAt.cOff : -1, wAddr: bestAt ? bestAt.wAddr : -1 };
}).sort((a, b) => b.best - a.best);

console.log('\n按"容器偏移 − 窗口地址"差值聚类（只显示最长连续一致 ≥ 16 字节的）:');
console.log('  delta(容器偏移-窗口地址)  锚点数  最长一致  容器偏移   窗口地址');
let shown = 0;
for (const r of rows) {
  if (r.best < 16) continue;
  console.log(`  ${r.delta >= 0 ? ' ' : ''}${r.delta.toString(16).padStart(8, '0')}   ${String(r.anchors).padStart(6)}   ${String(r.best).padStart(6)}   0x${r.cOff.toString(16).padStart(6, '0')}   0x${r.wAddr.toString(16).padStart(4, '0')}`);
  if (++shown > 25) { console.log('  ...'); break; }
}
if (shown === 0) console.log('  （无：窗口与容器没有 ≥16 字节的连续一致区段）');

// ---- 5. 顺带：把已知标识串在两个文件里的位置都打出来 ----
function findAll(buf, ascii) {
  const pat = Buffer.from(ascii, 'latin1');
  const out = [];
  let i = buf.indexOf(pat);
  while (i >= 0) { out.push(i); i = buf.indexOf(pat, i + 1); }
  return out;
}
console.log('\n标识串位置:');
for (const s of ['YELSTO', '7869', '7868Q', 'TF100A']) {
  const inC = findAll(Buffer.from(C), s).map(x => '0x' + x.toString(16).toUpperCase());
  const inW = findAll(Buffer.from(W), s).map(x => '0x' + x.toString(16).toUpperCase());
  console.log(`  "${s}"  容器: ${inC.join(', ') || '—'}   窗口: ${inW.join(', ') || '—'}`);
}
