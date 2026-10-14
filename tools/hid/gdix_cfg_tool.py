#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gdix_cfg_tool.py —— Goodix GTX8/Yellowstone cfg 的【校验 / 合法修改 / 重算校验和】

算法来源（官方 goodix/gtx8_driver_linux，Apache-2.0）：
  goodix_ts_core.h:568-576   checksum_u8()    NOR : sum(data[0..n-1]) == 0
  goodix_ts_core.h:579-587   checksum_u8_ys() YS  : sum(data[0..n-3]) - BE16(data[n-2..n-1]) == 0
  goodix_ts_i2c.c:1063-1120  goodix_read_config_ys()  袋链走法
  goodix_gtx8_update.c:645   原文注释 "checksum rule: sum of data in one format is equal to zero"

本机 cfg 结构（实测 1084 B，来自 tools/hid/lab__cfg_backup_*.bin）：
  head[0]   cfg_version   实测 0x22
  head[1]   0x01（固定/保留）
  head[2]   bag_num       实测 0x1B = 27   ← 不是「版本字节」！
  head[3:5] u16 BE 校验和 = sum(head[0..2])
  袋链      自 off=5 起，每袋 = {u8 bag_id, u8 len, data[len], u16 BE ck}，总长 len+4
            bag_id 稀疏：实测 {1..14,16..19,23,26,29,31..36}，缺 {15,20,21,22,24,25,27,28,30}

用法：
  python gdix_cfg_tool.py verify <cfg.bin>
  python gdix_cfg_tool.py bags   <cfg.bin>
  python gdix_cfg_tool.py setver <cfg.bin> <new_ver_hex> <out.bin>
  python gdix_cfg_tool.py setbyte <cfg.bin> <abs_off_hex> <val_hex> <out.bin>
"""
import sys, os

HEAD_LEN_YS = 5
BAG_START_YS = 5


def ys_ck(seg):
    """checksum_u8_ys：返回 sum(前 n-2) - BE16(末 2)，合法时为 0"""
    if len(seg) < 2:
        return None
    return (sum(seg[:-2]) & 0xFFFF) - ((seg[-2] << 8) | seg[-1])


def fix_tail(seg_no_tail):
    """给定不带校验尾的段，返回该段（含 2 字节 BE 校验尾），使 ys_ck == 0"""
    s = sum(seg_no_tail) & 0xFFFF
    return bytes(seg_no_tail) + bytes([(s >> 8) & 0xFF, s & 0xFF])


def parse(buf):
    """返回 (head_ok, head_ck, bags[])；bags = [(bag_id, off, len, ck, end)]"""
    if len(buf) < HEAD_LEN_YS:
        return None, None, []
    head_ck = ys_ck(buf[:HEAD_LEN_YS])
    bags = []
    off = BAG_START_YS
    for j in range(buf[2]):
        if off + 2 > len(buf):
            bags.append((None, off, None, None, off, "OVERFLOW_HEAD")); break
        ln = buf[off + 1]
        end = off + ln + 4
        if end > len(buf):
            bags.append((buf[off], off, ln, None, len(buf), "OVERFLOW_END")); break
        ck = ys_ck(buf[off:end])
        bags.append((buf[off], off, ln, ck, end, "OK" if ck == 0 else "CKSUM_FAIL"))
        off = end
    return head_ck, head_ck, bags


def cmd_verify(path):
    b = open(path, 'rb').read()
    h_ck, _, bags = parse(b)
    print(f"文件 {os.path.basename(path)}  长 {len(b)} B")
    print(f"头 {b[:5].hex(' ').upper()}  cfg_version={b[0]:#04x} bag_num={b[2]}  头校验={h_ck}")
    bad = [x for x in bags if x[5] != "OK"]
    print(f"袋: 共 {len(bags)}，通过 {len(bags)-len(bad)}，失败 {len(bad)}")
    for x in bad[:8]:
        print(f"   ✗ bag_id={x[0]} off={x[1]:#x} len={x[2]} ck={x[3]} {x[5]}")
    ok = (h_ck == 0) and not bad
    print(f"\n{'✅ 结构合法（IC 应接受）' if ok else '🔴 结构不合法（IC 会拒绝并回退默认）'}")
    return ok


def cmd_bags(path):
    b = open(path, 'rb').read()
    _, _, bags = parse(b)
    print(f"{'bag#':>4} {'id':>4} {'off':>7} {'len':>5} {'ck':>4}  状态")
    for j, x in enumerate(bags):
        print(f"{j:>4} {str(x[0]):>4} {x[1]:#07x} {str(x[2]):>5} {str(x[3]):>4}  {x[5]}")


def cmd_setver(path, ver_hex, out):
    b = bytearray(open(path, 'rb').read())
    old = b[0]
    b[0] = int(ver_hex, 16)
    # 重算头部 16-bit BE 校验和 = sum(head[0..2])
    s = sum(b[0:3]) & 0xFFFF
    b[3] = (s >> 8) & 0xFF
    b[4] = s & 0xFF
    open(out, 'wb').write(bytes(b))
    print(f"cfg_version: {old:#04x} -> {b[0]:#04x}")
    print(f"重算头部校验: b[3:5] = {b[3]:#04x} {b[4]:#04x}  (sum={s:#x})")
    print(f"bag_num 保持 = {b[2]}（未改动）")
    cmd_verify(out)


def cmd_setbyte(path, off_hex, val_hex, out):
    b = bytearray(open(path, 'rb').read())
    off = int(off_hex, 16); val = int(val_hex, 16)
    old = b[off]
    b[off] = val
    # 若该字节落在某袋内，重算该袋尾校验
    _, _, bags = parse(bytes(b))
    fixed = None
    for x in bags:
        bid, o, ln, ck, end, st = x
        if ln is None:
            continue
        if o <= off < end:
            body = bytes(b[o:end - 2])
            s = sum(body) & 0xFFFF
            b[end - 2] = (s >> 8) & 0xFF
            b[end - 1] = s & 0xFF
            fixed = (bid, o, end, s)
            break
    open(out, 'wb').write(bytes(b))
    print(f"+{off:#x}: {old:#04x} -> {val:#04x}")
    if fixed:
        bid, o, end, s = fixed
        print(f"落在 bag_id={bid} (off={o:#x}..{end:#x})，已重算袋尾校验 = {s:#x}")
    else:
        print("⚠️ 未落在任何袋内（可能改到了头部或尾部残留字节）")
    cmd_verify(out)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    c = sys.argv[1].lower()
    if c == "verify":  cmd_verify(sys.argv[2])
    elif c == "bags":  cmd_bags(sys.argv[2])
    elif c == "setver": cmd_setver(sys.argv[2], sys.argv[3], sys.argv[4])
    elif c == "setbyte": cmd_setbyte(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    else: print(__doc__)
