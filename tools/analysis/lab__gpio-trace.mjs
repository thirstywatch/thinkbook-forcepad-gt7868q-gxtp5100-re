// gpio-trace.mjs —— 枚举 TF100A 固件里所有 GPIO_SetBits / GPIO_ResetBits 调用点，
// 解出 (端口, 引脚掩码, 置位/复位)，并定位「马达驱动级使能」候选引脚。
//
// 依据（从反汇编实测确认）：
//   0x0800F7FC(r0 = GPIO base, r1 = mask)  →  *(u32*)(base + 0x14) = mask   ⇒ BSRR（置位）
//   0x0800F80C(r0 = GPIO base, r1 = mask)  →  *(u32*)(base + 0x10) = mask   ⇒ BRR（复位）
//   GPIO 基址（STM32F1）：GPIOA=0x40010800  GPIOB=0x40010C00  GPIOC=0x40011000
//                          GPIOD=0x40011400  GPIOE=0x40011800
import fs from 'fs';

const asm = fs.readFileSync(process.argv[2], 'utf8').split(/\r?\n/);
const PORTS = {
  0x40010800: 'GPIOA', 0x40010c00: 'GPIOB', 0x40011000: 'GPIOC',
  0x40011400: 'GPIOD', 0x40011800: 'GPIOE',
};
const SET = '0x800f7fc', RST = '0x800f80c';

// 解析一行 → { addr, mnem, ops }
function parse(line) {
  const m = line.match(/^\s*([0-9a-f]{8})\s+(\S+)\s*(.*)$/i);
  if (!m) return null;
  return { addr: parseInt(m[1], 16), mnem: m[2], ops: m[3].trim() };
}

// 往上找最近一次构造 GPIO 基址的 movw/movt 对（同寄存器），以及 mask 的来源
function findBaseBackwards(idx) {
  // 往回最多 40 行找  movw rX,#lo / movt rX,#hi  且 hi==0x4001
  const regs = {};
  for (let k = idx - 1; k >= Math.max(0, idx - 40); k--) {
    const p = parse(asm[k]); if (!p) continue;
    let m = p.mnem.match(/^movw$/i) && p.ops.match(/^(r\d+),\s*#(0x[0-9a-f]+)$/i);
    if (m) { regs[m[1]] = { lo: parseInt(m[2], 16) }; continue; }
    m = p.mnem.match(/^movt$/i) && p.ops.match(/^(r\d+),\s*#(0x[0-9a-f]+)$/i);
    if (m && regs[m[1]]) {
      const hi = parseInt(m[2], 16);
      if (hi === 0x4001) return { base: (hi << 16) | regs[m[1]].lo, line: k };
    }
  }
  return null;
}

// 找 mask：往回找  movs rY, #imm  或  movw rY,#imm ，然后看是否 str 到 sp（栈传参）
function findMaskBackwards(idx, base) {
  // 简化策略：在调用点前 12 行内，找所有 "movs/movw rX, #imm" 里 imm 像引脚掩码的
  const cands = [];
  for (let k = idx - 1; k >= Math.max(0, idx - 14); k--) {
    const p = parse(asm[k]); if (!p) continue;
    let m = p.ops.match(/^(r\d+),\s*#(0x[0-9a-f]+)$/i);
    if (m && /^movs$|^movw$/i.test(p.mnem)) {
      const v = parseInt(m[2], 16);
      if (v > 0 && v <= 0xffff) cands.push({ reg: m[1], val: v, line: k });
    }
  }
  return cands;
}

const fmtPin = (v) => {
  const bits = [];
  for (let i = 0; i < 16; i++) if (v & (1 << i)) bits.push(i);
  return bits.length ? bits.map(b => `P?${b}`).join(',') : `0x${v.toString(16)}`;
};

for (const [target, kind] of [[SET, 'SET 置位'], [RST, 'RST 复位']]) {
  console.log(`\n${'='.repeat(100)}`);
  console.log(`${kind}  ——  bl #${target}`);
  console.log('='.repeat(100));
  console.log(' 调用点地址    端口      掩码        引脚        紧跟的用途线索');
  console.log('-'.repeat(100));
  for (let i = 0; i < asm.length; i++) {
    const p = parse(asm[i]); if (!p) continue;
    if (!(p.mnem === 'bl' && p.ops.replace(/\s/g, '') === `#${target}`)) continue;
    const b = findBaseBackwards(i);
    const masks = findMaskBackwards(i, b?.base);
    const portName = b ? (PORTS[b.base] || `0x${b.base.toString(16)}`) : '?';
    const maskStr = masks.length ? masks.map(c => `0x${c.val.toString(16)}`).join('|') : '?';
    const pinStr = masks.map(c => fmtPin(c.val).replace(/P\?/g, portName === '?' ? 'P?' : portName.slice(4) + '')).join(' ');
    // 用途线索：看紧邻的上一行或两行
    const ctxLine = (asm[i - 1] || '').trim().slice(0, 40);
    console.log(` 0x${p.addr.toString(16)}  ${portName.padEnd(9)} ${maskStr.padEnd(11)} ${pinStr.padEnd(11)} ${ctxLine}`);
  }
}
