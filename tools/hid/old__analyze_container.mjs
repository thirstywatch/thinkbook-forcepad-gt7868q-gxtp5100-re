// analyze_container.mjs —— 判定 GT7868Q 容器里"加密段"到底是代码还是数据
// 用法： node analyze_container.mjs <container.bin>
// 指标（按 1 KB 分块，并与已知明文代码段作对照）：
//   ① 香农熵        ② Thumb 函数序言密度（push {...,lr} = 0xB5xx 且 bit8=1）
//   ③ 32 位字里落在外设/Flash/RAM 地址区的比例   ④ 打印区域表候选
import fs from 'fs';

const C = fs.readFileSync(process.argv[2]);
const N = C.length;
console.log(`容器大小 ${N} (0x${N.toString(16).toUpperCase()})`);

function entropy(buf, a, b) {
  const h = new Uint32Array(256);
  for (let i = a; i < b; i++) h[buf[i]]++;
  const n = b - a; let e = 0;
  for (let i = 0; i < 256; i++) if (h[i]) { const p = h[i] / n; e -= p * Math.log2(p); }
  return e;
}
function prolog(buf, a, b) {           // Thumb push {..., lr} = 0xB5xx（小端字节序：低字节=寄存器掩码, 高字节=0xB5）
  let n = 0;
  for (let i = a; i + 1 < b; i += 2) if (buf[i + 1] === 0xB5) n++;
  return n / ((b - a) / 2);
}
function ptrRatio(buf, a, b) {         // 32 位小端值落在 0x08000000-0x08100000 / 0x20000000-0x20010000
  let n = 0, tot = 0;
  for (let i = a; i + 3 < b; i += 4) {
    const v = buf.readUInt32LE(i); tot++;
    if ((v >= 0x08000000 && v < 0x08100000) || (v >= 0x20000000 && v < 0x20010000)) n++;
  }
  return tot ? n / tot : 0;
}

const KB = 1024;
console.log('\n  偏移       熵    push/lr密度   指针比例   非零率');
for (let a = 0; a < N; a += KB) {
  const b = Math.min(a + KB, N);
  if (b - a < 64) break;
  let nz = 0; for (let i = a; i < b; i++) if (C[i]) nz++;
  console.log(`  0x${a.toString(16).toUpperCase().padStart(5, '0')}  ${entropy(C, a, b).toFixed(3)}   ${prolog(C, a, b).toFixed(4)}      ${ptrRatio(C, a, b).toFixed(4)}     ${(nz / (b - a)).toFixed(3)}`);
}

// ---- 区域表候选：找 type ∈ {2,3} 的 8 字节记录 ----
console.log('\n区域表候选（8 字节记录：type, ?, addr, ?）：');
let found = 0;
for (let o = 0; o < Math.min(0x1400, N - 8); o += 4) {
  const t = C.readUInt32LE(o), v = C.readUInt32LE(o + 4);
  if ((t === 2 || t === 3) && v >= 0x1000 && v <= 0x400000) {
    console.log(`  0x${o.toString(16).toUpperCase().padStart(4, '0')}: type=${t}  val=0x${v.toString(16).toUpperCase()}`);
    if (++found > 40) { console.log('  ...'); break; }
  }
}
if (!found) console.log('  （未找到明显的 8 字节区域表）');

// ---- 关键区间对照 ----
const regions = [
  ['头部/区域表', 0x0, 0x1400],
  ['“加密段”', 0x1400, 0x19800],
  ['★指针表候选 0x19800–0x19A00', 0x19800, 0x19A00],
  ['间隔区', 0x19A00, 0x19ABC],
  ['明文段(代码+rodata)', 0x19ABC, 0x26E00],
  ['明文段·向量表头 1KB', 0x19ABC, 0x19EBC],
  ['明文段·代码主体', 0x1A000, 0x26E00],
  ['尾部', 0x26E00, N],
];
console.log('\n区间对照（push/lr 密度已修正为"0xB5xx 占比"）：');
for (const [name, a, b] of regions) {
  if (b > N) continue;
  console.log(`  ${name.padEnd(26)} 0x${a.toString(16).toUpperCase()}–0x${b.toString(16).toUpperCase()}  熵=${entropy(C, a, b).toFixed(3)}  push/lr=${prolog(C, a, b).toFixed(4)}  ptr=${ptrRatio(C, a, b).toFixed(4)}  n=${b - a}`);
}

// ---- 0x19800 处的指针表候选，打印前 96 字节 ----
console.log('\n0x19800 起 96 字节（十六进制 + 32 位小端解释）：');
for (let o = 0x19800; o < 0x19860; o += 16) {
  const hx = [...C.subarray(o, o + 16)].map(b => b.toString(16).toUpperCase().padStart(2, '0')).join(' ');
  const ws = [];
  for (let k = 0; k < 16; k += 4) ws.push('0x' + C.readUInt32LE(o + k).toString(16).toUpperCase().padStart(8, '0'));
  console.log(`  0x${o.toString(16).toUpperCase()}: ${hx}   ${ws.join(' ')}`);
}

// ---- 高熵异常块（熵 ≥ 7.99 的 1KB 块）----
console.log('\n熵 ≥ 7.99 的 1KB 块（疑似密钥/签名材料）：');
let prev = -10;
for (let a = 0; a < N; a += KB) {
  const b = Math.min(a + KB, N); if (b - a < 64) break;
  if (entropy(C, a, b) >= 7.99) {
    if (a - prev !== KB) process.stdout.write('\n  ');
    process.stdout.write(`0x${a.toString(16).toUpperCase()} `);
    prev = a;
  }
}
console.log('');

// ---- 明文段头 16 字节（与真机读对账用） ----
console.log('\n明文段头 16 字节（真机 0x08005000 应对上这几个字节）：');
console.log('  ' + [...C.subarray(0x19ABC, 0x19ACC)].map(b => b.toString(16).toUpperCase().padStart(2, '0')).join(' '));
