# -*- coding: utf-8 -*-
"""R7-1: 全盘按官方 cfg_bin 格式扫真实样本（稳健版）"""
import os, sys

ROOTS = [r"<LAB>", r"<HOME>\WorkBuddy",
         r"E:\AAA\WorkBuddy", r"<HOME>\.workbuddy"]
SKIP = ("node_modules", "\\obj\\", "AppData", "$RECYCLE", "\\Windows\\",
        ".git\\objects", "\\dist\\")

def u32(b, o): return int.from_bytes(b[o:o + 4], 'little')


def scan():
    n = 0; hits = []
    for R in ROOTS:
        if not os.path.isdir(R):
            print(f"  (跳过不存在的根 {R})"); continue
        for dp, dn, fn in os.walk(R):
            if any(s in dp for s in SKIP):
                dn[:] = []
                continue
            for f in fn:
                p = os.path.join(dp, f)
                try:
                    sz = os.path.getsize(p)
                    if sz < 32 or sz > 4_000_000:
                        continue
                    b = open(p, 'rb').read()
                    if u32(b, 0) != sz:
                        continue
                    if b[4] != (sum(b[5:]) & 0xFF):
                        continue
                    if not (1 <= b[9] <= 32):
                        continue
                    hits.append((p, sz, b[9], b[5:9].hex(' '), b[:16].hex(' ')))
                    print(f"  ★命中 {p}\n        size={sz} pkg_num={b[9]} ver={b[5:9].hex(' ')} head={b[:16].hex(' ')}")
                except Exception:
                    pass
                n += 1
    print(f"  扫描 {n} 个文件, 命中 {len(hits)}")
    return hits


if __name__ == "__main__":
    scan()
