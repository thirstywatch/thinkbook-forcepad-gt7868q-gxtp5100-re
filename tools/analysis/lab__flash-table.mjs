// flash-table.mjs —— 解析 GT7868Q 固件里的 flash 分区/子系统表
//
// 依据（官方 goodix_gtx8_update.c）：
//   FW_SUBSYS_INFO_SIZE   8        每项 8 字节
//   FW_SUBSYS_INFO_OFFSET 32       表在 firmware_info 内偏移 32
//   FW_SUBSYS_MAX_NUM     28
//   FLASH_SUBSYS_TYPE_CONFIG  0x03
//   FLASH_ADDR_CONFIG_DATA    0x1E000
//   subsys_base_addr = subsys->flash_addr << 8     (update.c:757)
//   struct fw_subsys_info { u8 type; u32 size; u16 flash_addr; }
//
// 实测校验出的磁盘编码（本机与 Catalog 样本共用明文段内一致成立）：
//   byte[0]      = type                    (0x03 = CONFIG)
//   byte[1..4]   = size   (big-endian u32) (0x2000 = 8 KB)
//   byte[4..7]   = flash_addr (big-endian u32, 绝对 flash 字节地址)
// 注：size 与 flash 有 1 字节重叠读数，取能同时自洽的解读（见输出中的两种并列）
import fs from 'fs';

const OFFICIAL = {
  0xC000:  'HW_REG_ISP_ADDR',
  0x6100:  'HW_REG_ISP_BUFFER',
  0x6020:  'HW_REG_SUBSYS_TYPE',
  0x6022:  'HW_REG_FLASH_FLAG',
  0x6006:  'HW_REG_ISP_RUN_FLAG',
  0x1E000: 'FLASH_ADDR_CONFIG_DATA',
  0x4000:  'HW_REG_CPU_RUN_FROM_YS',
  0x2014:  'HW_REG_GIO_YS',
  0x2180:  'HW_REG_CPU_CTRL',
  0x2184:  'HW_REG_RESET',
  0x4506:  'HW_REG_CPU_RUN_FROM (nor_L 0x4006)',
  0x4160:  'CMD_ADDR (官方 HID 工具)',
  0x96F8:  'CFG_START_ADDR (官方 HID 工具)',
  0x19000: 'CFG_FLASH_ADDR (官方 HID 工具)',
};

function decode(buf, tableOff, label) {
  console.log(`\n${'='.repeat(96)}`);
  console.log(`${label}  表偏移 0x${tableOff.toString(16)}`);
  console.log('='.repeat(96));
  console.log(' idx  type  size(BE)    flash_addr(BE)      备注');
  console.log('-'.repeat(96));
  const rows = [];
  for (let i = 0; i < 28; i++) {
    const o = tableOff + i * 8;
    if (o + 8 > buf.length) break;
    const type = buf[o];
    const sizeBE = buf.readUInt32BE(o + 1);
    const addrBE = buf.readUInt32BE(o + 4);
    const sizeLE = buf.readUInt32LE(o + 1);
    const addrLE = buf.readUInt32LE(o + 4);
    const note = [];
    if (OFFICIAL[addrBE]) note.push('★ ' + OFFICIAL[addrBE]);
    if (addrBE && addrBE % 0x2000 === 0) note.push('(8K 对齐)');
    rows.push({ i, type, sizeBE, addrBE });
    if (type === 0 && sizeBE === 0 && addrBE === 0) { console.log(` ${String(i).padStart(3)}   —— 空项，表在此结束 ——`); break; }
    console.log(` ${String(i).padStart(3)}  0x${type.toString(16).padStart(2,'0')}  0x${sizeBE.toString(16).padStart(8,'0')}  0x${addrBE.toString(16).padStart(8,'0')}      ${note.join(' ')}`);
  }
  // 交叉参考：表里出现的地址 vs 官方常量
  console.log('\n  --- 与官方常量交叉参考 ---');
  for (const r of rows) {
    if (OFFICIAL[r.addrBE]) console.log(`    分区${r.i}: flash 0x${r.addrBE.toString(16)} == ${OFFICIAL[r.addrBE]}`);
  }
  return rows;
}

const A = process.argv[2], B = process.argv[3];
const a = fs.readFileSync(A), b = fs.readFileSync(B);

// 锚点：YELSTO。两份的共用明文段起点 = YELSTO 前推固定量
const aY = a.indexOf(Buffer.from('YELSTO'));
const bY = b.indexOf(Buffer.from('YELSTO'));
console.log(`本机 YELSTO @0x${aY.toString(16)}   样本 YELSTO @0x${bY.toString(16)}   delta=0x${(aY-bY).toString(16)}`);

// 表起点：实测本机在 0x1164（YELSTO+0x22），样本在 0x4C0（YELSTO+0x22）
decode(a, aY + 0x22, '【本机 GT7868Q 固件】');
decode(b, bY + 0x22, '【Catalog 样本 GT7868Q 固件】');

// 共用明文段统计
console.log(`\n${'='.repeat(96)}`);
console.log('共用明文段（对齐后逐字节相同）');
console.log('='.repeat(96));
const d = aY - bY;
let run = 0, best = 0, bestStart = 0;
for (let k = 0; k < 0x4000; k++) {
  const oa = aY + k, ob = bY + k;
  if (oa >= a.length || ob >= b.length) break;
  if (a[oa] === b[ob]) { run++; if (run > best) { best = run; bestStart = oa - run + 1; } } else run = 0;
}
console.log(`  最长完全相同段: ${best.toLocaleString()} 字节  @本机 0x${bestStart.toString(16)} / 样本 0x${(bestStart-d).toString(16)}`);
console.log(`  段内 ASCII 串:`);
const seg = a.subarray(bestStart, bestStart + best);
const s = [...seg].map(x => (x >= 32 && x < 127) ? String.fromCharCode(x) : '\0').join('');
const strs = s.match(/[\x20-\x7E]{4,}/g) || [];
console.log('    ' + (strs.length ? [...new Set(strs)].slice(0, 25).join(' | ') : '（无）'));
