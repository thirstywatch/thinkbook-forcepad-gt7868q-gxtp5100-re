# fw_deep3.py - 定位厂商命令分发器: 把 opcode 比较指令按函数聚类
import struct
from capstone import *

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
OFF = 0x19ABC
img = data[OFF:]
BASE = 0x08000000
N = len(img)

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))
byaddr = {i.address: i for i in insns}

# 函数入口集合: push{...,lr} / bl 目标 / 向量表
starts = set()
for i in insns:
    if i.mnemonic == "push" and "lr" in i.op_str:
        starts.add(i.address)
    if i.mnemonic in ("bl", "blx") and i.op_str.startswith("#"):
        try: starts.add(int(i.op_str[1:], 16))
        except Exception: pass
for k in range(2, 48):
    v = struct.unpack_from("<I", img, 4*k)[0]
    if v: starts.add(v & ~1)
starts = sorted(starts)

def owner(a):
    lo, hi = 0, len(starts)-1
    best = None
    for s in starts:
        if s <= a: best = s
        else: break
    return best

# 已知/可疑 opcode
OPS = [0x00,0x01,0x02,0x03,0x10,0x11,0x12,0x13,0x14,0x20,0x21,0x22,0x23,0x30,0x99,0xFF]
clusters = {}
for i in insns:
    if not i.mnemonic.startswith("cmp"): continue
    if "#" not in i.op_str: continue
    try: v = int(i.op_str.split("#")[1].split(",")[0], 0)
    except Exception: continue
    if v not in OPS: continue
    f = owner(i.address)
    if f is None: continue
    clusters.setdefault(f, []).append((i.address, v))

print("=== opcode-compare clusters (by function) ===")
rank = sorted(clusters.items(), key=lambda kv: -len(set(v for _, v in kv[1])))
for f, lst in rank[:14]:
    vals = sorted(set(v for _, v in lst))
    print("\n  fn 0x%08X : %d cmp, opcodes=%s" % (f, len(lst), [hex(v) for v in vals]))
    print("     sites: %s" % ["0x%X/0x%X" % (a, v) for a, v in lst[:18]])

def show(a0, n=60, title=""):
    print("\n----- %s @0x%08X -----" % (title, a0))
    c = 0
    for i in insns:
        if i.address < a0: continue
        print("  %08X: %-10s %s" % (i.address, i.mnemonic, i.op_str))
        c += 1
        if c >= n: break

# 重点看: 同时包含 0x20 与 (0x13 或 0x12) 的函数 = 最强分发器候选
print("\n\n=== 分发器候选 (含 0x20 且含 0x13/0x12/0x10/0x11) ===")
for f, lst in rank:
    vs = set(v for _, v in lst)
    if 0x20 in vs and (vs & {0x13, 0x12, 0x10, 0x11}):
        print("\n### candidate 0x%08X  opcodes=%s" % (f, [hex(v) for v in sorted(vs)]))
        show(f, 120, "candidate fn 0x%08X" % f)

# 若没有, 打印含 0x20 的簇
print("\n=== 含 0x20 的簇 ===")
for f, lst in rank:
    vs = set(v for _, v in lst)
    if 0x20 in vs:
        print("  fn 0x%08X  opcodes=%s  sites=%s" % (f, [hex(v) for v in sorted(vs)], ["0x%X" % a for a, v in lst[:10]]))
