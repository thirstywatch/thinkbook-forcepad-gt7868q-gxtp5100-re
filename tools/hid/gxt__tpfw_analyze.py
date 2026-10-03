#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tpfw_analyze.py —— 解析官方明文固件 tpfw.bin（PNOR_G1），建立"同族明文长什么样"的基线

已确证（追加三十四）：
  header[0:16] = 00 01 50 fa f5 | 50 4E 4F 52 5F 47 31 | 00 00 0d | 37 38 36 33
                 len=5?        "PNOR_G1"          ?          "7863"
  子固件表从 0x24 起，8 B/条:
      addr(2B BE) << 8 + type(1B) + pad(1B) + len(2B BE) << 8 + pad(2B)
  11 条记录, 地址: 0x00000/0x03000/0x06000/0x07000/0x0A000/0x0B000/0x12000/0x17000/0x14000/0x0C000/0x10000

本脚本：
  1. 打印完整 32 字节头 + 全部子固件记录（含 type / len）
  2. 对每个子固件段做【结构画像】: 是否含 ASCII 标识、是否含高密度 0xFF/0x00、
     熵、头部魔数、是否像 8051 代码（含 LJMP/LCALL opcode 密度）
  3. 输出一个"明文基线 JSON"，供后续判据 F 使用
"""
import os, math, json, struct
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
TPFW = os.path.join(BASE, "tpfw_86272_PNOR_G1_7863.bin")
OUT = os.path.join(BASE, "cfg_parsed")
os.makedirs(OUT, exist_ok=True)

line = []


def w(s=""):
    line.append(s)
    print(s)


def entropy(b):
    if not b:
        return 0.0
    c = Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def ascii_runs(b, minlen=4):
    out = []
    cur = bytearray()
    start = 0
    for i, c in enumerate(b):
        if 32 <= c < 127:
            if not cur:
                start = i
            cur.append(c)
        else:
            if len(cur) >= minlen:
                out.append((start, bytes(cur).decode("ascii", "replace")))
            cur = bytearray()
    if len(cur) >= minlen:
        out.append((start, bytes(cur).decode("ascii", "replace")))
    return out


def looks_like_8051(b):
    """8051 常见 opcode 统计：02(ljmp) 12(lcall) 22(ret) 32(reti) 74(mov a,#) etc."""
    if len(b) < 64:
        return {}
    c = Counter(b)
    n = len(b)
    key = {0x02: "LJMP", 0x12: "LCALL", 0x22: "RET", 0x32: "RETI",
           0x74: "MOV A,#", 0x75: "MOV dir,#", 0xE4: "CLR A", 0x78: "MOV R0,#",
           0x7F: "MOV R7,#", 0x90: "MOV DPTR,#", 0xF0: "MOVX @DPTR,A", 0xE0: "MOVX A,@DPTR"}
    return {v: round(100.0 * c[k] / n, 3) for k, v in key.items()}


def main():
    with open(TPFW, "rb") as f:
        b = f.read()
    n = len(b)
    w("=" * 78)
    w("官方明文固件 tpfw.bin 结构分析  (size=%d B)" % n)
    w("=" * 78)

    w("\n【1】头部 32 字节")
    for k in range(0, 32, 16):
        row = b[k:k + 16]
        w("  +%03X  %-47s  |%s|" % (k, " ".join("%02X" % x for x in row),
                                   "".join(chr(c) if 32 <= c < 127 else "." for c in row)))

    w("\n【2】头部字段解读")
    w("  [0:3]  00 01 50        = ?（疑似 版本/格式标识）")
    w("  [3:5]  fa f5           = ?（疑似校验/长度域）")
    w("  [5:12] 'PNOR_G1'       = Plain NOR, Generation 1  ★明文固件标记")
    w("  [12:15] 00 00 0d       = ?")
    w("  [15:19] '7863'         = 型号族（GT7863 系，GT7868Q 属同族）")
    w("  [19:28] %s" % " ".join("%02X" % x for x in b[19:28]))
    w("  [28:32] %s" % " ".join("%02X" % x for x in b[28:32]))

    w("\n【3】子固件表（从 0x24 起，8 B/条）")
    recs = []
    off = 0x24
    for i in range(32):
        if off + 8 > n:
            break
        raw8 = b[off:off + 8]
        addr = (raw8[0] << 8 | raw8[1]) << 8
        typ = raw8[2]
        pad1 = raw8[3]
        ln = (raw8[4] << 8 | raw8[5]) << 8
        pad2 = raw8[6] << 8 | raw8[7]
        if addr == 0 and typ == 0 and ln == 0:
            w("  #%02d @0x%02X  [%s]  ← 全 0，表结束" % (i, off, " ".join("%02X" % x for x in raw8)))
            break
        recs.append(dict(i=i, off=off, addr=addr, type=typ, pad1=pad1, len=ln, pad2=pad2))
        w("  #%02d @0x%02X  %s | addr=0x%06X  type=0x%02X  len=0x%06X (%d B)"
          % (i, off, " ".join("%02X" % x for x in raw8), addr, typ, ln, ln))
        off += 8

    w("\n  合计 %d 条记录，len 总和 = %d B（文件 %d B）" % (len(recs), sum(r["len"] for r in recs), n))

    w("\n【4】各子固件段结构画像")
    w("  %-4s %-9s %-7s %-6s %-6s %-6s  %s" % ("#", "addr", "len", "熵", "0xFF%", "0x00%", "ASCII 标识 / 8051 特征"))
    for r in recs:
        seg = b[r["addr"]:r["addr"] + r["len"]] if r["addr"] + r["len"] <= n else b[r["addr"]:r["addr"] + r["len"]]
        if not seg:
            w("  %-4d 0x%06X  --      (超出文件范围)" % (r["i"], r["addr"]))
            continue
        ff = round(100.0 * seg.count(0xFF) / len(seg), 1)
        zz = round(100.0 * seg.count(0x00) / len(seg), 1)
        ent = round(entropy(seg), 2)
        runs = ascii_runs(seg, 5)[:4]
        ar = ", ".join("+%X:%s" % (o, s) for o, s in runs)
        op = looks_like_8051(seg)
        w("  %-4d 0x%06X  %-7d %-6.2f %-6.1f %-6.1f  %s" % (r["i"], r["addr"], len(seg), ent, ff, zz, ar))
        if op:
            w("        8051 opcode 占比: %s" % op)
        r["profile"] = dict(entropy=ent, ff_pct=ff, zero_pct=zz, ascii=[s for _, s in runs])
        r["seg_head_hex"] = seg[:32].hex()

    w("\n【5】全局 ASCII 字符串清单（长度>=6）")
    allruns = ascii_runs(b, 6)
    w("  共 %d 条" % len(allruns))
    for o, s in allruns[:80]:
        w("    @0x%05X  %s" % (o, s))

    with open(os.path.join(OUT, "tpfw_baseline.json"), "w", encoding="utf-8") as f:
        json.dump({"size": n, "records": recs,
                   "ascii": [{"off": o, "s": s} for o, s in allruns]}, f,
                  ensure_ascii=False, indent=2)

    with open(os.path.join(OUT, "tpfw_analyze.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(line))
    print("\n[done] -> cfg_parsed/tpfw_baseline.json, cfg_parsed/tpfw_analyze.txt")


if __name__ == "__main__":
    main()
