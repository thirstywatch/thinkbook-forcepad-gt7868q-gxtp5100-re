"""步骤11：尾部未覆盖区 0x08011A86-0x08012C9F 的性质判定
+ 打印全部"看起来像代码指针"的字
"""
import sys, os, re, collections, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

data = seg()
m = md()
LO, HI = 0x08011A86, SEG_HI

print("=== 尾部区 0x%08X-0x%08X 的 movw/movt 常量 ===" % (LO, HI))
cnt = collections.Counter()
for o in range(LO - SEG_LO, HI - SEG_LO - 7, 2):
    a = SEG_LO + o
    i = insn_at(m, data, a)
    if i is None or i.mnemonic != "movw":
        continue
    mt = re.match(r"(r\d+),\s*#(0x[0-9a-fA-F]+)", i.op_str)
    if not mt:
        continue
    j = insn_at(m, data, a + 4)
    if j is None or j.mnemonic != "movt" or not j.op_str.startswith(mt.group(1) + ","):
        continue
    m2 = re.match(r"r\d+,\s*#(0x[0-9a-fA-F]+)", j.op_str)
    if m2:
        cnt[(int(m2.group(1), 16) << 16) | int(mt.group(2), 16)] += 1
for v, c in sorted(cnt.items()):
    print("  0x%08X x%d" % (v, c))
print("  合计 %d 个不同常量" % len(cnt))

print("\n=== 尾部区里 4 字节对齐字中：落在 0x08005000-0x08012C9F（代码指针）/0x20000000-0x20008000（RAM）的 ===")
code_ptr, ram_ptr = [], []
for o in range(LO - SEG_LO, HI - SEG_LO - 3, 4):
    w = int.from_bytes(data[o:o + 4], "little")
    a = SEG_LO + o
    if 0x08005000 <= w <= 0x08012C9F:
        code_ptr.append((a, w))
    if 0x20000000 <= w <= 0x20008000:
        ram_ptr.append((a, w))
print("  代码指针 %d 个: %s" % (len(code_ptr), ", ".join("0x%08X->0x%08X" % t for t in code_ptr[:20])))
print("  RAM 指针 %d 个: %s" % (len(ram_ptr), ", ".join("0x%08X->0x%08X" % t for t in ram_ptr[:20])))

print("\n=== 尾部区解码 64 字节 ===")
a = LO
for _ in range(24):
    i = insn_at(m, data, a)
    if i is None:
        print("  0x%08X  <undecodable>" % a); a += 2; continue
    print("  0x%08X  %-8s %s" % (a, i.mnemonic, i.op_str))
    a += i.size

print("\n=== 全镜像所有 4 字节对齐的代码指针（Thumb）===")
allp = []
for o in range(0, len(data) - 3, 4):
    w = int.from_bytes(data[o:o + 4], "little")
    if 0x08005000 <= w <= SEG_HI and (w & 1):
        allp.append((SEG_LO + o, w & ~1))
for a, t in allp:
    print("  0x%08X -> 0x%08X" % (a, t))
print("  合计 %d" % len(allp))

print("\n=== 尾部区字节熵 ===")
b = data[LO - SEG_LO:HI - SEG_LO + 1]
freq = collections.Counter(b)
ent = -sum((c / len(b)) * math.log2(c / len(b)) for c in freq.values())
print("  长度 %d, 熵 %.3f bits/byte, 零字节比例 %.3f" % (len(b), ent, freq[0] / len(b)))
