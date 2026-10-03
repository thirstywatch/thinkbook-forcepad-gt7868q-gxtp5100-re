#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parse_cfg.py —— 把 tpcfgsid*.cfg（明文逗号分隔 0xNN）解析成结构化 XML-ish 块表 + I2C 序列提取
产出:
  cfg_parsed/sid0.blocks.txt / sid2.blocks.txt / sid3.blocks.txt   —— 按 0xNN 头推断的块划分
  cfg_parsed/i2c_seqs.txt                                          —— 疑似 I2C 写序列（含 0x5A/I2C 从地址）
  cfg_parsed/haptic_candidates.txt                                 —— 触觉/振动相关表候选
"""
import os, re, sys, json

BASE = os.path.dirname(os.path.abspath(__file__))
CFGD = os.path.join(BASE, "cfg")
OUT  = os.path.join(BASE, "cfg_parsed")
os.makedirs(OUT, exist_ok=True)

FILES = {
    "sid0": "tpcfgsid0_Xiaomi7867_20240307.cfg.txt",
    "sid2": "tpcfgsid2_20230407.cfg.txt",
    "sid3": "tpcfgsid3_LaiBao7986P_20220701.cfg.txt",
}


def load(name):
    p = os.path.join(CFGD, FILES[name])
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        txt = f.read()
    toks = [t.strip() for t in txt.split(",") if t.strip()]
    data = []
    for t in toks:
        try:
            data.append(int(t, 16))
        except ValueError:
            continue
    return data


def ascii_at(buf, off, n=16):
    s = bytes(buf[off:off + n])
    return "".join(chr(c) if 32 <= c < 127 else "." for c in s)


def block_scan(buf, tag, fh):
    """按 [0xNN][00] 头 + 长度字节的启发式切块：块头形如  tag,00,len,payload..."""
    n = len(buf)
    i = 0
    blocks = []
    while i < n - 2:
        t = buf[i]
        z = buf[i + 1]
        if z == 0x00 and 0x01 <= buf[i + 2] <= 0x40 and i + 3 + buf[i + 2] <= n:
            blen = buf[i + 2]
            blocks.append((i, t, blen, buf[i + 3:i + 3 + blen]))
            i += 3 + blen
        else:
            i += 1
    fh.write("# %s 共 %d 字节, 启发式切出 %d 个 [tag,00,len,...] 块\n\n" % (tag, n, len(blocks)))
    for off, t, blen, payload in blocks:
        hx = " ".join("%02X" % b for b in payload[:24])
        tail = " ..." if blen > 24 else ""
        fh.write("@0x%04X  tag=0x%02X  len=%3d  | %s%s\n" % (off, t, blen, hx, tail))
    return blocks


def i2c_scan(buf, tag, fh):
    """找疑似 I2C 写序列：形如 [len][devaddr][reg][data...] 或 [devaddr][00 00][reg] 结构。
    关键锚点 = 从地址 0x5A（AW86927）/ 0x5B / 0x50（常见 EEPROM 或本芯片 otra 地址）。"""
    n = len(buf)
    hits = []
    for i in range(n):
        if buf[i] == 0x5A:
            lo = max(0, i - 8)
            hi = min(n, i + 12)
            hits.append((i, buf[lo:hi]))
    fh.write("### %s 中 0x5A 出现 %d 次\n" % (tag, len(hits)))
    for off, ctx in hits:
        fh.write("@0x%04X (idx %d)  ctx: %s\n" % (off, off, " ".join("%02X" % b for b in ctx)))
    fh.write("\n### %s 中 0x5B 出现位置\n" % tag)
    for i in range(n):
        if buf[i] == 0x5B:
            lo = max(0, i - 6)
            hi = min(n, i + 10)
            fh.write("@0x%04X  ctx: %s\n" % (i, " ".join("%02X" % b for b in buf[lo:hi])))
    fh.write("\n")
    return hits


def u16_le_scan(buf, tag, fh, lo=1, hi=4000):
    """扫 u16 LE 表：连续 >=10 个 u16，值域在 [lo,hi]，步长稳定"""
    n = len(buf)
    runs = []
    i = 0
    while i + 2 <= n:
        start = i
        vals = []
        while i + 2 <= n:
            v = buf[i] | (buf[i + 1] << 8)
            if lo <= v <= hi:
                vals.append(v)
                i += 2
            else:
                break
        if len(vals) >= 10:
            runs.append((start, vals))
        i = max(i + 1, start + 1)
    fh.write("### %s 候选 u16LE 表（>=10 项, 值域[%d,%d]）共 %d 段\n" % (tag, lo, hi, len(runs)))
    for start, vals in runs:
        fh.write("@0x%04X  n=%3d  %s\n" % (start, len(vals), ", ".join(str(v) for v in vals[:40])))
    fh.write("\n")
    return runs


def main():
    summary = {}
    fb = open(os.path.join(OUT, "blocks_all.txt"), "w", encoding="utf-8")
    fi = open(os.path.join(OUT, "i2c_seqs.txt"), "w", encoding="utf-8")
    fh2 = open(os.path.join(OUT, "haptic_candidates.txt"), "w", encoding="utf-8")

    for tag in ("sid0", "sid2", "sid3"):
        buf = load(tag)
        summary[tag] = len(buf)
        # 头部 ASCII 识别
        print("[%s] size=%d  head-ascii=%r" % (tag, len(buf), ascii_at(buf, 0, 48)))
        fb.write("\n" + "=" * 78 + "\n=== %s ===\n" % tag)
        fb.write("size = %d\nhead[0:64] ascii = %r\n\n" % (len(buf), ascii_at(buf, 0, 64)))
        block_scan(buf, tag, fb)
        i2c_scan(buf, tag, fi)
        u16_le_scan(buf, tag, fh2)

    fb.close(); fi.close(); fh2.close()

    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print("\n[done] ->", OUT)


if __name__ == "__main__":
    main()
