// parse-cfg-bin.mjs —— 按 Goodix 官方 goodix_cfg_bin.c 格式解析固件里的配置包
//
// 官方格式（#pragma pack(1)）：
//   Head(16B): u32 bin_len | u8 checksum | u8 ver[4] | u8 pkg_num | u8 reserved[6]
//   偏移表 @16: u16 LE × pkg_num（第 i 包的起始偏移）
//   包: const_info(56B) + reg_info(65B) + cfg(pkg_len-121)
//   校验: checksum == Σ(byte[5 .. bin_len-1]) & 0xFF
import fs from 'fs';

const path = process.argv[2];
const buf = fs.readFileSync(path);
console.log(`文件: ${path}  (${buf.length.toLocaleString()} B)`);

const CONST_LEN = 56, REG_LEN = 65, PKG_HEAD = CONST_LEN + REG_LEN; // 121
const HEAD_LEN = 16;

const REG_NAMES = ['cfg_send_flag','version_base','pid','vid','sensor_id','fw_mask','fw_status',
                   'cfg_addr','esd','command','coor','gesture','fw_request','proximity'];

function parseAt(off) {
  if (off + HEAD_LEN > buf.length) return null;
  const binLen = buf.readUInt32LE(off);
  if (binLen < 64 || binLen > buf.length - off) return null;
  const checksum = buf[off + 4];
  let s = 0;
  for (let i = off + 5; i < off + binLen; i++) s = (s + buf[i]) & 0xff;
  if (s !== checksum) return null;
  const ver = buf.subarray(off + 5, off + 9);
  const pkgNum = buf[off + 9];
  if (pkgNum < 1 || pkgNum > 16) return null;
  return { off, binLen, checksum, ver: [...ver], pkgNum };
}

// ── 扫描合法 cfg_bin ─────────────────────────────────────
console.log('\n=== 扫描合法 cfg_bin（校验和判据）===');
const found = [];
for (let off = 0; off < buf.length - HEAD_LEN; off++) {
  const c = parseAt(off);
  if (c) found.push(c);
}
if (!found.length) console.log('  未找到（校验和判据下无合法 cfg_bin）');
for (const c of found) {
  console.log(`\n★ @0x${c.off.toString(16)}  bin_len=${c.binLen.toLocaleString()}  checksum=0x${c.checksum.toString(16).padStart(2,'0')}  ver=[${c.ver.map(x=>x.toString(16)).join(' ')}]  pkg_num=${c.pkgNum}`);
  for (let i = 0; i < c.pkgNum; i++) {
    const o1 = buf.readUInt16LE(c.off + HEAD_LEN + i * 2);
    const o2 = (i === c.pkgNum - 1) ? c.binLen : buf.readUInt16LE(c.off + HEAD_LEN + (i + 1) * 2);
    const pkgLen = o2 - o1;
    const p = c.off + o1;
    if (p + PKG_HEAD > buf.length) { console.log(`  包${i}: 偏移越界 (${o1})`); continue; }
    const pkgLenField = buf.readUInt32LE(p);
    const icType = buf.subarray(p + 4, p + 19).toString('latin1').replace(/\0.*$/,'');
    const cfgType = buf[p + 19], sensorId = buf[p + 20];
    const hwPid = buf.subarray(p + 21, p + 29).toString('latin1').replace(/\0.*$/,'');
    const hwVid = buf.subarray(p + 29, p + 37).toString('latin1').replace(/\0.*$/,'');
    const fwMask = buf.subarray(p + 37, p + 46).toString('latin1').replace(/\0.*$/,'');
    const fwPatch = buf.subarray(p + 46, p + 50).toString('latin1').replace(/\0.*$/,'');
    const xRes = buf.readUInt16LE(p + 50), yRes = buf.readUInt16LE(p + 52), trig = buf.readUInt16LE(p + 54);
    console.log(`  ── 包${i} @0x${p.toString(16)}  pkg_len=${pkgLen} (字段=${pkgLenField})`);
    console.log(`     ic_type="${icType}"  cfg_type=0x${cfgType.toString(16)}  sensor_id=${sensorId}`);
    console.log(`     hw_pid="${hwPid}"  hw_vid="${hwVid}"`);
    console.log(`     fw_mask="${fwMask}"  fw_patch="${fwPatch}"`);
    console.log(`     x_res_offset=${xRes}  y_res_offset=${yRes}  ★trigger_offset=${trig}`);
    console.log(`     寄存器表:`);
    for (let k = 0; k < 14; k++) {
      const q = p + CONST_LEN + k * 4;
      console.log(`       ${REG_NAMES[k].padEnd(14)} addr=0x${buf.readUInt16LE(q).toString(16).padStart(4,'0')}  r1=${buf[q+2]}  r2=${buf[q+3]}`);
    }
    const cfgOff = p + PKG_HEAD, cfgLen = pkgLen - PKG_HEAD;
    console.log(`     cfg 数据: @0x${cfgOff.toString(16)}  ${cfgLen} B  (前 32: ${[...buf.subarray(cfgOff, cfgOff+32)].map(x=>x.toString(16).padStart(2,'0')).join(' ')})`);
  }
}

// ── 头部直接解读 ────────────────────────────────────────
console.log('\n=== 文件头 64 字节 ===');
console.log([...buf.subarray(0,64)].map(x=>x.toString(16).padStart(2,'0')).join(' '));
console.log('u32@0 =', buf.readUInt32LE(0), ' u32@4 =', buf.readUInt32LE(4), ' u32@8 =', buf.readUInt32LE(8));

// ── 找 YELSTO / 7868Q 的精确位置与字段归属 ──────────────
console.log('\n=== 标识串位置 ===');
for (const key of ['YELSTO','7868Q','TF100A_Test_FW','TF100A']) {
  let i = 0;
  while ((i = buf.indexOf(Buffer.from(key), i)) >= 0) {
    console.log(`  "${key}" @0x${i.toString(16)}  (文件偏移)`);
    i++;
  }
}
