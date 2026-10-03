#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tlv_decode.py —— 正确解码 tpcfgsid*.cfg 的 TLV 结构

✔ 已确证：块头 = [TAG][LEN]（不是 [TAG][00][LEN]！我此前多插了一个字节）
   证据：sid3 偏移 0x013C 处 `3A 0C` 起、长度 0x3A=58 的块，
   恰好覆盖 idx 325..382 = 这正是 0x0190(u16LE=0x0190) 那段的长度。

修正后的切块规则：
   while i < n:
       tag = b[i]; ln = b[i+1]
       payload = b[i+2:i+2+ln]
       i += 2 + ln
   —— 但 TLV 流中夹杂裸字符串/查表区，需要容错回退。

产出：把三个 cfg 的 TLV 流打印出来，并标注每块的 tag/长度/首若干字节。
"""
import os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
CFGD = os.path.join(BASE, "cfg")
FILES = {
    "sid0": "tpcfgsid0_Xiaomi7867_20240307.cfg.txt",
    "sid2": "tpcfgsid2_20230407.cfg.txt",
    "sid3": "tpcfgsid3_LaiBao7986P_20220701.cfg.txt",
}


def load(name):
    with open(os.path.join(CFGD, FILES[name]), encoding="utf-8") as f:
        toks = [t.strip() for t in f.read().split(",") if t.strip()]
    return [int(t, 16) for t in toks if t.lower().startswith("0x")]


def tlv_walk(b, start, fh, tag):
    """从 start 起按 [TAG][LEN][payload] 走；遇到明显不合法则单字节滑窗。"""
    i = start
    n = len(b)
    out = []
    while i + 2 <= n:
        tg = b[i]
        ln = b[i + 1]
        if i + 2 + ln > n or ln > 200:
            i += 1
            continue
        payload = b[i + 2:i + 2 + ln]
        out.append((i, tg, ln, payload))
        i += 2 + ln
    fh.write("\n### %s : TLV 流 (%d 块)\n" % (tag, len(out)))
    for off, tg, ln, pl in out:
        hx = " ".join("%02X" % x for x in pl[:20])
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in pl[:20])
        fh.write("@0x%04X TAG=0x%02X LEN=%3d | %-60s | %s\n" % (off, tg, ln, hx, asc))
    return out


if __name__ == "__main__":
    outdir = os.path.join(BASE, "cfg_parsed")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "tlv_walk.txt"), "w", encoding="utf-8") as fh:
        summary = {}
        for tag in ("sid0", "sid2", "sid3"):
            b = load(tag)
            # 跳过 64 字节头部信息区（PCB/厂商/日期），从 0x40 开始
            blocks = tlv_walk(b, 0x40, fh, tag)
            summary[tag] = {"size": len(b), "tlv_from_0x40": len(blocks),
                            "coverage": sum(2 + ln for _, _, ln, _ in blocks)}
        fh.write("\n\n=== 覆盖率 ===\n")
        for k, v in summary.items():
            pct = 100.0 * v["coverage"] / (v["size"] - 0x40)
            fh.write("%s size=%d  TLV 覆盖 %d 字节 (%.1f%%)\n"
                     % (k, v["size"], v["coverage"], pct))

    # 单独把 sid3 的 0x0190/0x0258 块完整吐出
    b = load("sid3")
    with open(os.path.join(outdir, "sid3_haptic_blocks.txt"), "w", encoding="utf-8") as f:
        for start in (0x13C, 0x154):
            ln = b[start + 1]
            blk = b[start:start + 2 + ln]
            f.write("\n>>> 块 @0x%04X  TAG=0x%02X LEN=%d (%d B)\n" % (start, b[start], ln, len(blk)))
            for k in range(0, len(blk), 16):
                row = blk[k:k + 16]
                hx = " ".join("%02X" % x for x in row)
                asc = "".join(chr(c) if 32 <= c < 127 else "." for c in row)
                f.write("    +%03X  %-47s  %s\n" % (k, hx, asc))
    print("[done] cfg_parsed/tlv_walk.txt, cfg_parsed/sid3_haptic_blocks.txt")
