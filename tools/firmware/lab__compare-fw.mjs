// compare-fw.mjs —— 对比两份 Goodix 触控板固件容器的结构与区域
//   本机 : touchpad_GT7868Q_fw.bin (161,628 B, 型号标识 "7869")
//   样本 : goodix-fw/goodix_tp_payload.bin (133,628 B, 型号标识 "7868Q")
import fs from 'fs';

const A = process.argv[2], B = process.argv[3];
const a = fs.readFileSync(A), b = fs.readFileSync(B);

const ent = (buf, off, len) => {
  const c = new Array(256).fill(0);
  const n = Math.min(len, buf.length - off);
  for (let i = off; i < off + n; i++) c[buf[i]]++;
  let h = 0;
  for (const x of c) if (x) { const p = x / n; h -= p * Math.log2(p); }
  return h;
};
const hx = (buf, off, n) => [...buf.subarray(off, off + n)].map(x => x.toString(16).padStart(2, '0')).join(' ');
const asc = (buf, off, n) => [...buf.subarray(off, off + n)].map(x => (x >= 32 && x < 127) ? String.fromCharCode(x) : '.').join('');

console.log('='.repeat(90));
console.log(`A(本机 7869) ${a.length} B   ${A}`);
console.log(`B(样本 7868Q) ${b.length} B   ${B}`);
console.log('='.repeat(90));
console.log('\n--- 头部 256 字节 ---');
for (const [tag, buf] of [['A', a], ['B', b]]) {
  console.log(`[${tag}] 0x0000: ${hx(buf, 0, 64)}`);
  console.log(`[${tag}]        ${asc(buf, 0, 64)}`);
}

// 区域表假设：头块 1084 字节（项目已测），0x73 魔数 + 若干 4 字节字段
console.log('\n--- 前 0x100 字节里的 32 位小端值（找区域表）---');
for (const [tag, buf] of [['A', a], ['B', b]]) {
  const vals = [];
  for (let o = 0; o < 0x100; o += 4) {
    const v = buf.readUInt32LE(o);
    if (v !== 0 && v !== 0xffffffff) vals.push(`0x${o.toString(16)}=${v}(0x${v.toString(16)})`);
  }
  console.log(`[${tag}] ${vals.join('  ')}`);
}

// 熵剖面（每 4 KB，抽样 4 字节步长以省时）
console.log('\n--- 熵剖面（每 4 KB 一块）---');
const step = 4096;
const blocks = Math.ceil(Math.max(a.length, b.length) / step);
console.log('  offset      A(7869)   B(7868Q)');
for (let i = 0; i < blocks; i++) {
  const off = i * step;
  const ha = off < a.length ? ent(a, off, step).toFixed(2) : '  -  ';
  const hb = off < b.length ? ent(b, off, step).toFixed(2) : '  -  ';
  const mark = (off < a.length && ha < 6.0) || (off < b.length && hb < 6.0) ? '   <<< 低熵' : '';
  console.log(`  0x${off.toString(16).padStart(6, '0')}   ${ha}     ${hb}${mark}`);
}

// 明文/低熵区扫描（1 KB 粒度，找连续低熵段）
console.log('\n--- 低熵段（<6.0，1 KB 粒度，连续 >=2KB）---');
for (const [tag, buf] of [['A', a], ['B', b]]) {
  const runs = []; let start = -1;
  for (let off = 0; off < buf.length; off += 1024) {
    const h = ent(buf, off, 1024);
    if (h < 6.0) { if (start < 0) start = off; }
    else { if (start >= 0 && off - start >= 2048) runs.push([start, off]); start = -1; }
  }
  if (start >= 0) runs.push([start, buf.length]);
  console.log(`[${tag}] ${runs.length} 段`);
  for (const [s, e] of runs) console.log(`      0x${s.toString(16).padStart(6, '0')} .. 0x${e.toString(16).padStart(6, '0')}  (${(e - s).toLocaleString()} B)`);
}

// 共同/独有的 ASCII 关键字
console.log('\n--- 关键字出现次数 ---');
const keys = ['YELSTO', '7869', '7868Q', '7868', '7863', 'TF100A', 'TF100', 'Test_FW', 'GT7868', 'GXTP5100', 'Goodix', 'GOODIX', 'BERLIN', 'NORMANDYL'];
const cnt = (buf, k) => { let n = 0, i = 0; while ((i = buf.indexOf(Buffer.from(k), i)) >= 0) { n++; i++; } return n; };
console.log(`  ${'key'.padEnd(12)} A(7869)  B(7868Q)`);
for (const k of keys) console.log(`  ${k.padEnd(12)} ${String(cnt(a, k)).padEnd(8)} ${cnt(b, k)}`);
