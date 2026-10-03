// diff-compare.mjs —— 判定项目当年「按压 vs 不按压」差分实验是否有效
// 关键：A 相有两次重复（A1/A2，同为"手指离开"）⇒ 用它做噪声基线。
//   若 A1 vs A2 的变化量 ≈ A vs B 的变化量 ⇒ 那些变化是"时变噪声"，实验结论无效。
// 用法： node diff-compare.mjs <dir>
import fs from 'fs';
import path from 'path';

const dir = process.argv[2] || '.';
function load(name) {
  const p = path.join(dir, name);
  if (!fs.existsSync(p)) return null;
  const map = {};
  for (const ln of fs.readFileSync(p, 'utf8').split(/\r?\n/)) {
    const m = /^0x([0-9A-Fa-f]{4})\s+(.*)$/.exec(ln.trim());
    if (!m) continue;
    const base = parseInt(m[1], 16);
    const b = [];
    for (const t of m[2].trim().split(/\s+/)) if (/^[0-9A-Fa-f]{2}$/.test(t)) b.push(parseInt(t, 16));
    map[base] = b;
  }
  return map;
}
const files = ['diff-A.txt', 'diff-A1.txt', 'diff-A2.txt', 'diff-B.txt'].map(f => [f, load(f)]);
for (const [n, m] of files) console.log(`${n}: ${m ? Object.keys(m).map(k => '0x' + (+k).toString(16).toUpperCase() + '(' + m[k].length + 'B)').join(' ') : '(缺失)'}`);

function cmp(n1, m1, n2, m2) {
  console.log(`\n=== ${n1}  vs  ${n2} ===`);
  if (!m1 || !m2) { console.log('  缺文件，跳过'); return; }
  for (const base of Object.keys(m1).sort((a, b) => a - b)) {
    const A = m1[base], B = m2[base];
    if (!B) { console.log(`  0x${(+base).toString(16).toUpperCase()}: 对侧缺失`); continue; }
    let cells = 0, bytes = 0;
    const lim = Math.min(A.length, B.length) - 1;
    for (let i = 0; i < lim; i += 2) {
      const va = A[i] | (A[i + 1] << 8), vb = B[i] | (B[i + 1] << 8);
      if (va !== vb) cells++;
    }
    for (let i = 0; i < Math.min(A.length, B.length); i++) if (A[i] !== B[i]) bytes++;
    const total = Math.floor(Math.min(A.length, B.length) / 2);
    console.log(`  窗口 0x${(+base).toString(16).toUpperCase().padStart(4, '0')}: ${total - cells}/${total} 未变  |  16 位单元变化 ${cells}  |  字节变化 ${bytes}`);
  }
}
cmp('A', files[0][1], 'A1', files[1][1]);
cmp('A1', files[1][1], 'A2', files[2][1]);
cmp('A', files[0][1], 'B', files[3][1]);
cmp('A1', files[1][1], 'B', files[3][1]);
