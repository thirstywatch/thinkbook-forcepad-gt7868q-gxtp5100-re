#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND47: 解 flash 偏移 0x1800 / 0x3800 的语义
方法:
  1. 反汇编 0x1AB90 (读 0x1800) / 0x1BA7C (写 0x1800) / 0x1AC30 & 0x1AE68 (写 0x3800)
     看它们对这块数据做什么、用什么结构体
  2. 把 sid0/sid2/sid3 明文 cfg 解析成字节数组, 看偏移 0x1800/0x3800 落在哪个字段
  3. 关键: 找到"cfg 在 flash 中的落点基址" —— 看是否 0x1800 是 cfg 内部偏移
"""
import os, sys, struct, re
from capstone import *

FW = r"<WORKSPACE>"
if not os.path.exists(FW):
    for c in [r"<WORKSPACE>",
              r"<WORKSPACE>",
              r"<WORKSPACE>"]:
        p = os.path.join(c, "TB14P_GT7868Q_14030522_20240202.BIN")
        if os.path.exists(p):
            FW = p; break
print("FW =", FW, os.path.exists(FW))
if not os.path.exists(FW):
    import glob
    g = glob.glob(r"<HOME>\**\TB14P_GT7868Q*.BIN", recursive=True)
    print("glob:", g)
    if g: FW = g[0]
print("USING:", FW)

D = open(FW, "rb").read()
BASE = 0x08000000

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS)
md.detail = True

def dis(off, n=40, title=""):
    print(f"\n===== {title} @ file 0x{off:X} (rt 0x{BASE+off:08X}) =====")
    for i in md.disasm(D[off:off+n*4], BASE+off):
        print(f"  0x{i.address:08X}  {i.bytes.hex():<10} {i.mnemonic:<8} {i.op_str}")

def hexdump(off, n, title=""):
    print(f"\n===== HEX {title} @ 0x{off:X} ({n} B) =====")
    for r in range(0, n, 16):
        chunk = D[off+r:off+r+16]
        if not chunk: break
        h = " ".join(f"{b:02X}" for b in chunk)
        a = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"  {off+r:06X}  {h:<48} {a}")

# ── 1. 反汇编关键函数 ──
dis(0x1AB90, 32, "cmd 0x1B handler: 读 flash 0x1800")
dis(0x1BA7C, 30, "写 flash 0x1800 (单字节)")
dis(0x1AC30, 20, "写 0x3800 (来自协议 type4)")
dis(0x1AE68, 24, "cmd 0x1700: 写 0x3800")

# ── 2. dump flash 里的 0x1800 / 0x3800 实际内容 ──
# 注意: 0x1800 是"相对 0x08019000 的偏移" → 绝对 0x0801A800 → file 0x1A800
hexdump(0x1A800, 64, "flash@0x1800 (file 0x1A800)")
hexdump(0x1C800, 64, "flash@0x3800 (file 0x1C800)")

# ── 3. 解析明文 cfg ──
CFGDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg")
def load_cfg(name):
    p = os.path.join(CFGDIR, name)
    txt = open(p, "r", encoding="utf-8", errors="replace").read()
    toks = [t.strip() for t in txt.split(",")]
    out = []
    for t in toks:
        if t.startswith("0x") or t.startswith("0X"):
            try: out.append(int(t, 16))
            except: pass
    return bytes(out)

for nm in ["tpcfgsid0_Xiaomi7867_20240307.cfg.txt",
           "tpcfgsid2_20230407.cfg.txt",
           "tpcfgsid3_LaiBao7986P_20220701.cfg.txt"]:
    b = load_cfg(nm)
    print(f"\n===== {nm}: {len(b)} B =====")
    print("  header[0:16]:", " ".join(f"{x:02X}" for x in b[:16]))
    print("  ascii        :", "".join(chr(x) if 32<=x<127 else "." for x in b[:64]))
    # 找 0x1800 / 0x3800 是否在范围内
    for o in (0x1800, 0x3800):
        print(f"  offset 0x{o:X}: " + ("IN RANGE -> " + " ".join(f"{x:02X}" for x in b[o:o+16]) if o+1 < len(b) else "OUT OF RANGE"))
