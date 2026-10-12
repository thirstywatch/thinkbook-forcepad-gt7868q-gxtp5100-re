#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gtx3_container_parse.py — 解析 Goodix **gtx3 / GT7868Q 固件镜像**（官方格式）

格式来源（两个独立权威出处，互为印证的【官方级】规范）：
  ① `goodix/gdix_hid_firmware_update`（Goodix 官方 GT7868Q 刷写工具）
     - `firmware_image.cpp :: GetDataFromFile()`   → 长度/校验和算法
     - `gt7868q_firmware_image.cpp`                → GT7868Q 专属偏移常量
     - `gt7868q_update.cpp :: fw_update()`         → 子固件表条目格式
  ② `fwupd/fwupd plugins/goodix-tp`（Goodix 工程师合入）
     - `fu-goodixtp.rs :: FuStructGoodixGtx8Hdr / Gtx8Img`
     - `fu-goodixtp-gtx8-firmware.c`               → 同算法，互相印证

布局（全部实测吻合）
--------------------------------------------------------------------
  偏移      大小   字段
  0x00       4     固件长度，**大端 u32**（不含本头 6 字节）
  0x04       2     校验和，**大端 u16**
  0x06       9     IC 家族代号 ASCII（本项目实测 = "_7YELSTO" ⇒ YELLOWSTONE）
  0x0F       8     PID ASCII（本项目 = "7868Q\\0\\0\\0"）
  0x17       1     CID
  0x18       3     VID，大端 u24
  0x1B       1     子固件个数 N
  0x20      N×8    子固件信息表（**步长 8**）
                     +0x00  type : u8
                     +0x01  len  : 大端 u32
                     +0x05  addr : 大端 u16，**再左移 8**（即 16 位页地址）
  0x100     ...    子固件数据区（各子固件按表中顺序**紧凑排列**，无间隙）

校验和算法
--------------------------------------------------------------------
  checksum = ( Σ bytes[6 : firmwareSize+6] ) mod 2^16
  必须等于 bytes[4]<<8 | bytes[5]

用法
----
  python gtx3_container_parse.py <container.bin> [--payload-offset 0x113C] [--payload-size 100608]
  python gtx3_container_parse.py <container.bin> --scan     # 自动扫描载荷起点

⚠️ 只读，不修改任何文件。
"""
import sys, os, argparse, struct


def le_or_be(data, off, n, endian):
    return int.from_bytes(data[off:off + n], endian)


def parse_payload(b, label="payload"):
    """解析一个 Goodix gtx3 镜像。返回 dict 或 None。"""
    if len(b) < 0x100:
        return None
    size = int.from_bytes(b[0:4], 'big')
    ck_field = int.from_bytes(b[4:6], 'big')
    if size <= 0 or size + 6 > len(b):
        return None
    ck_calc = sum(b[6:size + 6]) & 0xFFFF

    N = b[0x1B]
    entries = []
    pos = 0x20
    for i in range(N):
        if pos + 8 > 0x100:
            break
        t = b[pos]
        ln = int.from_bytes(b[pos + 1:pos + 5], 'big')
        ad = int.from_bytes(b[pos + 5:pos + 7], 'big') << 8
        entries.append({"type": t, "len": ln, "addr": ad, "entry_off": pos})
        pos += 8

    # 数据区起点固定 0x100；各子固件紧凑排列
    data_off = 0x100
    cur = data_off
    for e in entries:
        e["data_off"] = cur
        cur += e["len"]
    data_end = cur

    return {
        "label": label,
        "declared_size": size,
        "expected_total": size + 6,
        "actual_total": len(b),
        "len_ok": (size + 6) == len(b),
        "ck_field": ck_field,
        "ck_calc": ck_calc,
        "ck_ok": ck_field == ck_calc,
        "magic": b[6:0x0F],
        "pid": b[0x0F:0x17],
        "cid": b[0x17],
        "vid": int.from_bytes(b[0x18:0x1B], 'big'),
        "n_sub": N,
        "entries": entries,
        "data_off": data_off,
        "data_end": data_end,
        "data_total": sum(e["len"] for e in entries),
        "data_fits": data_end <= (size + 6),
        "header32": b[:0x20],
    }


def report(r):
    if r is None:
        print("  （不是有效的 gtx3 镜像）")
        return False
    print("  长度字段 @0x00 (be32)     = %d (0x%X)" % (r["declared_size"], r["declared_size"]))
    print("  期望总长 = len+6          = %d ; 实际 = %d   %s"
          % (r["expected_total"], r["actual_total"], "✅" if r["len_ok"] else "❌"))
    print("  校验和 @0x04 (be16)       = 0x%04X" % r["ck_field"])
    print("  实算 Σ bytes[6:len+6]     = 0x%04X   %s"
          % (r["ck_calc"], "★★★★★ 校验和通过" if r["ck_ok"] else "❌ 校验和不符"))
    print("  IC 家族代号 @0x06         = %r" % r["magic"])
    print("  PID @0x0F                 = %r" % r["pid"])
    print("  CID @0x17 = 0x%02X   VID @0x18 (be24) = 0x%06X" % (r["cid"], r["vid"]))
    print("  子固件个数 @0x1B          = %d" % r["n_sub"])
    print()
    print("  子固件表 @0x20（步长 8: type u8, len be32, addr be16<<8）")
    print("    %-6s %-6s %-10s %-10s %-12s %s"
          % ("idx", "type", "len", "addr", "data_off", "data_off+len"))
    tot = 0
    for i, e in enumerate(r["entries"]):
        print("    %-6d 0x%02X   %-10d 0x%06X   0x%05X      0x%05X"
              % (i, e["type"], e["len"], e["addr"], e["data_off"], e["data_off"] + e["len"]))
        tot += e["len"]
    print("    ----")
    print("    合计 len = %d ; 数据区 @0x%03X 起，终点 0x%05X" % (tot, r["data_off"], r["data_end"]))
    print("    镜像总长 = %d ; 数据区占用 = %d ; 头 0x100 = 256" % (r["expected_total"], tot))
    gap = r["expected_total"] - r["data_off"] - tot
    print("    ⇒ 头(256) + 数据(%d) = %d ，与总长相差 %d 字节  %s"
          % (tot, r["data_off"] + tot, gap, "✅ 零剩余（完全吻合）" if gap == 0 else "⚠️ 有剩余"))
    print()
    print("  头部 32 字节：")
    for off in range(0, 0x20, 16):
        row = r["header32"][off:off + 16]
        asc = ''.join(chr(c) if 32 <= c < 127 else '.' for c in row)
        print("    +0x%02X  %s  %s" % (off, row.hex(' '), asc))
    return r["ck_ok"] and r["len_ok"] and r["data_fits"] and (gap == 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--payload-offset", type=lambda x: int(x, 0), default=0x113C)
    ap.add_argument("--payload-size", type=lambda x: int(x, 0), default=100608)
    ap.add_argument("--scan", action="store_true", help="在文件里自动扫描 gtx3 镜像起点")
    a = ap.parse_args()

    d = open(a.file, 'rb').read()
    print("文件 %s  (%d B, 0x%X)" % (a.file, len(d), len(d)))
    print("=" * 78)

    if a.scan:
        print("[扫描] 找所有 'bytes[0:4] 大端值 + 6 == 某长度' 的位置…")
        found = 0
        for off in range(0, len(d) - 0x100):
            size = int.from_bytes(d[off:off + 4], 'big')
            if size < 0x100 or off + size + 6 > len(d):
                continue
            if sum(d[off + 6:off + size + 6]) & 0xFFFF == int.from_bytes(d[off + 4:off + 6], 'big'):
                print("  ★ 命中 @0x%05X  声明长度=%d  子固件数=%d  PID=%r"
                      % (off, size, d[off + 0x1B], d[off + 0x0F:off + 0x17]))
                found += 1
                if found > 8:
                    break
        if not found:
            print("  未找到")
        return 0

    b = d[a.payload_offset:a.payload_offset + a.payload_size]
    print("[载荷] @0x%05X  长度 %d" % (a.payload_offset, len(b)))
    print()
    ok = report(parse_payload(b, "payloadA"))
    print()
    print("=" * 78)
    print("结论：%s" % ("★★★★★ 载荷 A 已确认为合法 Goodix gtx3/GT7868Q 固件镜像"
                     if ok else "⚠️ 未能完全确认（见上方 ❌/⚠️ 标记）"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
