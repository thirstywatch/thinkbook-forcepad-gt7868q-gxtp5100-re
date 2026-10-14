#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描全部候选文件，测试是否 = Goodix gtx8 的 `goodix_cfg_bin` 格式。

格式（来源：github.com/sm7150-mainline/goodix-cfg-bin/src/main.rs，与官方
        goodix/gtx8_driver_linux 的 goodix_cfg_bin.h/c 逐字段一致）：

  GoodixCfgBinHead  10 B（packed）
      u32 bin_len          必须 == 文件长度
      u8  checksum        必须 == sum(input[5 .. end]) & 0xFF
      u8  bin_version[4]
      u8  pkg_num
  + 6 B 保留                            → TS_CFG_BIN_HEAD_LEN = 16
  然后 pkg_num × u16 LE 偏移表           → 每个 2 B
  各包在偏移处，结构：
      GoodixCfgPkgConstInfo 56 B: u32 pkg_len | u8 ic_type[15] | u8 cfg_type |
          u8 sensor_id | u8 hw_pid[8] | u8 hw_vid[8] | u8 fw_mask[9] |
          u8 fw_patch[4] | u16 x_res_offset | u16 y_res_offset | u16 trigger_offset
      GoodixCfgPkgRegInfo  65 B: 14 × {u16 addr; u8 r1; u8 r2} + u8 reserved[9]
          → cfg_send_flag, version_base, pid, vid, sensor_id, fw_mask, fw_status,
            cfg_addr, esd, command, coor, gesture, fw_request, proximity
      cfg 数据 …
"""
import sys, os, struct, json

# Windows 控制台默认 GBK：打印 emoji / 生僻字会让 print 抛 UnicodeEncodeError（2026-10-14 实测）
try:  # 只把不可编码字符降级为 '?'，不改变可读内容
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

HEAD_LEN = 16
CONST_LEN = 56          # 4+15+1+1+8+8+9+4+2+2+2
REG_LEN = 65            # 14*4 + 9
PKG_HEAD = CONST_LEN + REG_LEN   # 121

REG_NAMES = ["cfg_send_flag","version_base","pid","vid","sensor_id","fw_mask",
             "fw_status","cfg_addr","esd","command","coor","gesture",
             "fw_request","proximity"]


def try_parse(d):
    if len(d) < HEAD_LEN:
        return None
    bin_len = struct.unpack_from('<I', d, 0)[0]
    if bin_len != len(d):
        return None
    ck = d[4]
    s = sum(d[5:]) & 0xFF
    if s != ck:
        return None
    pkg_num = d[9]
    if pkg_num == 0 or pkg_num > 20:
        return None
    offs = []
    for i in range(pkg_num):
        p = HEAD_LEN + i * 2
        if p + 2 > len(d):
            return None
        offs.append(struct.unpack_from('<H', d, p)[0])
    pkgs = []
    for i, o in enumerate(offs):
        if o + PKG_HEAD > len(d):
            return None
        pkg_len = struct.unpack_from('<I', d, o)[0]
        ic_type = d[o+4:o+19].split(b'\0')[0].decode('ascii', 'replace')
        cfg_type = d[o+19]
        sensor_id = d[o+20]
        hw_pid = d[o+21:o+29].hex().upper()
        hw_vid = d[o+29:o+37].hex().upper()
        fw_patch = d[o+50:o+54].hex().upper()
        xo, yo, to = struct.unpack_from('<HHH', d, o+54)
        regs = {}
        base = o + CONST_LEN
        for k, nm in enumerate(REG_NAMES):
            addr = struct.unpack_from('<H', d, base + k*4)[0]
            regs[nm] = addr
        pkgs.append(dict(idx=i, off=o, pkg_len=pkg_len, ic_type=ic_type,
                         cfg_type=cfg_type, sensor_id=sensor_id,
                         hw_pid=hw_pid, hw_vid=hw_vid, fw_patch=fw_patch,
                         x_off=xo, y_off=yo, trig_off=to, regs=regs))
    return dict(bin_len=bin_len, checksum=ck, bin_version=d[5:9].hex().upper(),
                pkg_num=pkg_num, pkgs=pkgs)


def main():
    if len(sys.argv) < 2:
        sys.exit("用法：gdix_cfgbin_scan.py <目录或文件> [更多路径 …]")
    roots = sys.argv[1:]
    exts = {'.bin', '.cfg', '.dat', '.img', '.fw', '.hex', '.rom', ''}
    hits, tried = [], 0
    for root in roots:
        for dp, dn, fn in os.walk(root):
            dn[:] = [x for x in dn if x not in ('.git', 'node_modules', '__pycache__')]
            for f in fn:
                p = os.path.join(dp, f)
                ext = os.path.splitext(f)[1].lower()
                base = os.path.basename(f).lower()
                if ext not in exts and 'cfg' not in base and 'sid' not in base:
                    continue
                try:
                    sz = os.path.getsize(p)
                except OSError:
                    continue
                if not (64 <= sz <= 2_000_000):
                    continue
                tried += 1
                try:
                    d = open(p, 'rb').read()
                except OSError:
                    continue
                r = try_parse(d)
                if r:
                    hits.append((p, r))
    print("扫描候选文件 %d 个，命中 goodix_cfg_bin 格式：%d 个\n" % (tried, len(hits)))
    for p, r in hits:
        print("=" * 90)
        print("命中:", p)
        print("  bin_len=%d checksum=%#04x bin_version=%s pkg_num=%d"
              % (r['bin_len'], r['checksum'], r['bin_version'], r['pkg_num']))
        for pk in r['pkgs']:
            print("  --- pkg #%d @%#x len=%d ic_type=%r cfg_type=%d sensor_id=%d pid=%s patch=%s"
                  % (pk['idx'], pk['off'], pk['pkg_len'], pk['ic_type'],
                     pk['cfg_type'], pk['sensor_id'], pk['hw_pid'], pk['fw_patch']))
            print("      regs:", json.dumps(pk['regs']))
    if not hits:
        print("（未命中。已扫的候选里没有 goodix_cfg_group.bin 这种格式。）")


if __name__ == "__main__":
    main()
